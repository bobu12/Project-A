"""ScanDocRename - CRG LPO Processor.

Watches a Windows scan folder for new PDF files, extracts the 8-digit LPO
number from the document (P.O No: <8 digits>/L<n>), renames the file to
LPO_<8digits>.pdf, and moves it to CONVERTED. Ambiguous files go to REVIEW.
Every action is appended to LOGS\\processing.log.csv.

Run modes:
    python processor.py batch    # one-pass over INBOX, then exit
    python processor.py watch    # long-running watcher (used by the service)
"""

from __future__ import annotations

import configparser
import csv
import logging
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterable

# Page-1 pattern: "P.O No: 26000553/L2" (whitespace and trailing junk tolerated)
LPO_PATTERN = re.compile(
    r"P\.?\s*O\.?\s*No\.?\s*[:#]?\s*(\d{8})\s*/\s*L\s*\d+",
    re.IGNORECASE,
)

DEFAULT_CONFIG = {
    "paths": {
        "inbox": r"D:\D",
        "converted": r"D:\D\CONVERTED",
        "review": r"D:\D\REVIEW",
        "logs": r"D:\D\LOGS",
    },
    "settings": {
        "workers": "4",
        "stable_seconds": "2",
        "stable_timeout": "60",
        "ocr_dpi": "300",
        "ocr_max_pages": "3",
        "poppler_path": r"C:\poppler\Library\bin",
        "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    },
}

LOG_FIELDS = [
    "timestamp",
    "original_name",
    "extracted_lpo",
    "status",
    "output_path",
    "method",
]


@dataclass
class Config:
    inbox: Path
    converted: Path
    review: Path
    logs: Path
    workers: int
    stable_seconds: float
    stable_timeout: float
    ocr_dpi: int
    ocr_max_pages: int
    poppler_path: str
    tesseract_cmd: str

    @classmethod
    def load(cls, path: Path) -> "Config":
        parser = configparser.ConfigParser()
        parser.read_dict(DEFAULT_CONFIG)
        if path.exists():
            parser.read(path, encoding="utf-8")
        p = parser["paths"]
        s = parser["settings"]
        return cls(
            inbox=Path(p["inbox"]),
            converted=Path(p["converted"]),
            review=Path(p["review"]),
            logs=Path(p["logs"]),
            workers=int(s["workers"]),
            stable_seconds=float(s["stable_seconds"]),
            stable_timeout=float(s["stable_timeout"]),
            ocr_dpi=int(s["ocr_dpi"]),
            ocr_max_pages=int(s["ocr_max_pages"]),
            poppler_path=s["poppler_path"].strip() or None,
            tesseract_cmd=s["tesseract_cmd"].strip(),
        )


def find_lpos(text: str) -> list[str]:
    """Return all distinct 8-digit LPO numbers found in `text`, in order."""
    seen: list[str] = []
    for match in LPO_PATTERN.finditer(text or ""):
        lpo = match.group(1)
        if lpo not in seen:
            seen.append(lpo)
    return seen


def wait_until_stable(path: Path, stable_seconds: float, timeout: float) -> bool:
    """Return True once file size is unchanged for `stable_seconds` (within `timeout`)."""
    deadline = time.monotonic() + timeout
    last_size = -1
    last_change = time.monotonic()
    while time.monotonic() < deadline:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        now = time.monotonic()
        if size != last_size:
            last_size = size
            last_change = now
        elif now - last_change >= stable_seconds and size > 0:
            return True
        time.sleep(0.25)
    return False


def unique_destination(folder: Path, filename: str) -> Path:
    """Return a destination path; suffix _dup1, _dup2... if `filename` already exists."""
    target = folder / filename
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    n = 1
    while True:
        candidate = folder / f"{stem}_dup{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def is_duplicate(target: Path) -> bool:
    return target.exists()


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def extract_text_native(pdf: Path, poppler_path: str | None) -> str:
    """Fast path: native PDF text via pdftotext. Returns '' if no embedded text."""
    try:
        from pdfminer.high_level import extract_text  # lazy
    except ImportError:
        extract_text = None  # type: ignore

    # Prefer Poppler's pdftotext binary (faster, more accurate on layout)
    import subprocess

    pdftotext = "pdftotext"
    if poppler_path:
        candidate = Path(poppler_path) / ("pdftotext.exe" if os.name == "nt" else "pdftotext")
        if candidate.exists():
            pdftotext = str(candidate)
    try:
        result = subprocess.run(
            [pdftotext, "-layout", "-q", str(pdf), "-"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        text = result.stdout.decode("utf-8", errors="ignore")
        if text.strip():
            return text
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if extract_text is not None:
        try:
            return extract_text(str(pdf)) or ""
        except Exception:  # noqa: BLE001
            return ""
    return ""


def extract_text_ocr(pdf: Path, cfg: Config) -> str:
    """Fallback OCR via Tesseract. Renders first `ocr_max_pages` pages."""
    from pdf2image import convert_from_path  # lazy
    import pytesseract  # lazy

    if cfg.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd

    images = convert_from_path(
        str(pdf),
        dpi=cfg.ocr_dpi,
        first_page=1,
        last_page=cfg.ocr_max_pages,
        poppler_path=cfg.poppler_path,
    )
    parts: list[str] = []
    for img in images:
        parts.append(pytesseract.image_to_string(img, config="--psm 6"))
        # short-circuit once we have a match
        if LPO_PATTERN.search("\n".join(parts)):
            break
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@dataclass
class Result:
    original_name: str
    extracted_lpo: str
    status: str
    output_path: str
    method: str


def process_file(pdf: Path, cfg: Config) -> Result:
    log = logging.getLogger("processor")
    original = pdf.name
    method = "native"

    if not wait_until_stable(pdf, cfg.stable_seconds, cfg.stable_timeout):
        return Result(original, "", "skipped_unstable", str(pdf), "")

    text = ""
    try:
        text = extract_text_native(pdf, cfg.poppler_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("native extract failed for %s: %s", original, exc)

    lpos = find_lpos(text)
    if not lpos:
        try:
            text = extract_text_ocr(pdf, cfg)
            method = "ocr"
            lpos = find_lpos(text)
        except Exception as exc:  # noqa: BLE001
            log.error("OCR failed for %s: %s", original, exc)

    if len(lpos) == 1:
        target = cfg.converted / f"LPO_{lpos[0]}.pdf"
        if is_duplicate(target):
            target = unique_destination(cfg.converted, f"LPO_{lpos[0]}.pdf")
            status = "ok_dup"
        else:
            status = "ok"
        try:
            shutil.move(str(pdf), str(target))
        except Exception as exc:  # noqa: BLE001
            log.error("move failed for %s -> %s: %s", pdf, target, exc)
            return Result(original, lpos[0], "error_move", str(pdf), method)
        return Result(original, lpos[0], status, str(target), method)

    # 0 or 2+ LPOs -> REVIEW with original name
    target = unique_destination(cfg.review, original)
    try:
        shutil.move(str(pdf), str(target))
    except Exception as exc:  # noqa: BLE001
        log.error("review-move failed for %s -> %s: %s", pdf, target, exc)
        return Result(original, ";".join(lpos), "error_move", str(pdf), method)

    if len(lpos) == 0:
        return Result(original, "", "no_lpo_found", str(target), method)
    return Result(original, ";".join(lpos), "multi_po", str(target), method)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(LOG_FIELDS)

    def write(self, result: Result) -> None:
        row = [
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            result.original_name,
            result.extracted_lpo,
            result.status,
            result.output_path,
            result.method,
        ]
        with self.lock, self.path.open("a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------


def iter_inbox_pdfs(inbox: Path) -> Iterable[Path]:
    for entry in sorted(inbox.iterdir()):
        if entry.is_file() and entry.suffix.lower() == ".pdf":
            yield entry


def ensure_dirs(cfg: Config) -> None:
    for p in (cfg.inbox, cfg.converted, cfg.review, cfg.logs):
        p.mkdir(parents=True, exist_ok=True)


def run_batch(cfg: Config) -> int:
    log = logging.getLogger("processor")
    audit = AuditLog(cfg.logs / "processing.log.csv")
    pdfs = list(iter_inbox_pdfs(cfg.inbox))
    if not pdfs:
        log.info("inbox empty: %s", cfg.inbox)
        return 0
    log.info("processing %d file(s) from %s", len(pdfs), cfg.inbox)
    with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
        for result in pool.map(lambda p: process_file(p, cfg), pdfs):
            audit.write(result)
            log.info("%-18s %-12s %s", result.status, result.extracted_lpo, result.original_name)
    return len(pdfs)


def run_watch(cfg: Config) -> None:
    """Long-running watcher. Sweeps backlog on startup, then listens for new files."""
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    log = logging.getLogger("processor")
    audit = AuditLog(cfg.logs / "processing.log.csv")
    pool = ThreadPoolExecutor(max_workers=cfg.workers)

    def handle(pdf: Path) -> None:
        try:
            result = process_file(pdf, cfg)
            audit.write(result)
            log.info("%-18s %-12s %s", result.status, result.extracted_lpo, result.original_name)
        except Exception:  # noqa: BLE001
            log.exception("processing crashed for %s", pdf)

    log.info("startup sweep of %s", cfg.inbox)
    for pdf in list(iter_inbox_pdfs(cfg.inbox)):
        pool.submit(handle, pdf)

    class Handler(FileSystemEventHandler):
        def on_created(self, event):  # type: ignore[override]
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() == ".pdf":
                pool.submit(handle, path)

        def on_moved(self, event):  # type: ignore[override]
            if event.is_directory:
                return
            path = Path(event.dest_path)
            if path.suffix.lower() == ".pdf" and path.parent == cfg.inbox:
                pool.submit(handle, path)

    observer = Observer()
    observer.schedule(Handler(), str(cfg.inbox), recursive=False)
    observer.start()
    log.info("watching %s", cfg.inbox)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("stopping...")
    finally:
        observer.stop()
        observer.join()
        pool.shutdown(wait=True)


def configure_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(logs_dir / "service.stdout.log", encoding="utf-8"),
        ],
    )


def main(argv: list[str]) -> int:
    cfg_path = Path(__file__).with_name("config.ini")
    cfg = Config.load(cfg_path)
    ensure_dirs(cfg)
    configure_logging(cfg.logs)
    log = logging.getLogger("processor")
    log.info("config loaded from %s", cfg_path if cfg_path.exists() else "(defaults)")
    log.info("INBOX=%s  CONVERTED=%s  REVIEW=%s  LOGS=%s",
             cfg.inbox, cfg.converted, cfg.review, cfg.logs)

    mode = argv[1] if len(argv) > 1 else "watch"
    if mode == "batch":
        run_batch(cfg)
    elif mode == "watch":
        run_watch(cfg)
    else:
        print(f"unknown mode: {mode!r}. Use 'batch' or 'watch'.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
