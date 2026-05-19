"""CRG LPO Processor.

Watches an INBOX folder for scanned LPO PDFs, extracts the 8-digit LPO
number from page 1 (P.O No: <8 digits>/L<n>), renames the file to
LPO_<8 digits>.pdf and moves it to CONVERTED. Ambiguous or unreadable
files are routed to REVIEW. Every action is appended to a CSV audit log.

CLI:
    python processor.py watch     # default: long-running watcher (service mode)
    python processor.py batch     # one-pass sweep of INBOX, then exit
"""

from __future__ import annotations

import argparse
import configparser
import csv
import logging
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

LPO_REGEX = re.compile(r"P\.?\s*O\s*No\.?\s*[:\-]?\s*(\d{8})\s*/\s*L\d+", re.IGNORECASE)
CSV_COLUMNS = ["timestamp", "original_name", "extracted_lpo", "status", "output_path", "method"]
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.ini"
MAX_STABLE_WAIT_SECONDS = 60
LOG = logging.getLogger("crg-processor")


@dataclass(frozen=True)
class Config:
    inbox: Path
    converted: Path
    review: Path
    logs: Path
    workers: int
    stable_seconds: float
    ocr_dpi: int
    poppler_path: str
    tesseract_cmd: str


def load_config(path: Path) -> Config:
    if not path.exists():
        raise SystemExit(f"config.ini not found at {path}. Copy config.ini.example to config.ini and edit it.")
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    paths = parser["paths"]
    settings = parser["settings"] if parser.has_section("settings") else {}
    return Config(
        inbox=Path(paths["inbox"]),
        converted=Path(paths["converted"]),
        review=Path(paths["review"]),
        logs=Path(paths["logs"]),
        workers=int(settings.get("workers", 4)),
        stable_seconds=float(settings.get("stable_seconds", 2)),
        ocr_dpi=int(settings.get("ocr_dpi", 300)),
        poppler_path=settings.get("poppler_path", "").strip(),
        tesseract_cmd=settings.get("tesseract_cmd", "").strip(),
    )


def extract_text_native(pdf_path: Path, poppler_path: str) -> str:
    """Fast path: pull embedded text from page 1 with pdftotext, fallback to pdfminer."""
    pdftotext = _which_pdftotext(poppler_path)
    if pdftotext:
        import subprocess
        try:
            result = subprocess.run(
                [pdftotext, "-f", "1", "-l", "1", "-layout", str(pdf_path), "-"],
                capture_output=True, text=True, timeout=20, check=False,
            )
            if result.returncode == 0:
                # Return whatever pdftotext produced (empty string for image-only
                # scans). Falling through to pdfminer would be redundant since
                # both read embedded text — if pdftotext sees nothing, pdfminer
                # will too. Skip straight to OCR.
                return result.stdout
        except (subprocess.TimeoutExpired, OSError) as exc:
            LOG.debug("pdftotext failed for %s: %s", pdf_path.name, exc)

    try:
        from pdfminer.high_level import extract_text
        return extract_text(str(pdf_path), maxpages=1) or ""
    except BaseException as exc:  # catches pyo3 panics from broken cryptography installs
        LOG.debug("pdfminer failed for %s: %s", pdf_path.name, exc)
        return ""


def _which_pdftotext(poppler_path: str) -> str | None:
    if poppler_path:
        candidate = Path(poppler_path) / ("pdftotext.exe" if os.name == "nt" else "pdftotext")
        if candidate.exists():
            return str(candidate)
    return shutil.which("pdftotext")


def extract_text_ocr(pdf_path: Path, cfg: Config) -> str:
    """Fallback: render page 1 to an image and OCR it with Tesseract."""
    from pdf2image import convert_from_path
    import pytesseract

    if cfg.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd

    kwargs = {"dpi": cfg.ocr_dpi, "first_page": 1, "last_page": 1}
    if cfg.poppler_path:
        kwargs["poppler_path"] = cfg.poppler_path
    images = convert_from_path(str(pdf_path), **kwargs)
    if not images:
        return ""
    # PSM 6 (uniform block of text) reads CRG's table-heavy LPO forms
    # reliably; the default PSM 3 mis-segments the top-right P.O No cell.
    text = pytesseract.image_to_string(images[0], config="--psm 6") or ""
    if not LPO_REGEX.search(text):
        text += "\n" + (pytesseract.image_to_string(images[0], config="--psm 4") or "")
    return text


def extract_lpos(text: str) -> list[str]:
    return list(dict.fromkeys(LPO_REGEX.findall(text)))


def wait_until_stable(pdf_path: Path, stable_seconds: float) -> bool:
    """Wait for a file's size to stop changing. Returns False if it never stabilises."""
    deadline = time.monotonic() + MAX_STABLE_WAIT_SECONDS
    last_size = -1
    last_change = time.monotonic()
    while time.monotonic() < deadline:
        try:
            size = pdf_path.stat().st_size
        except FileNotFoundError:
            return False
        if size != last_size:
            last_size = size
            last_change = time.monotonic()
        elif time.monotonic() - last_change >= stable_seconds and size > 0:
            return True
        time.sleep(0.5)
    return False


def unique_destination(target: Path) -> tuple[Path, bool]:
    """Return a non-colliding path. Adds _dup1, _dup2, ... if needed."""
    if not target.exists():
        return target, False
    stem, suffix = target.stem, target.suffix
    for n in range(1, 1000):
        candidate = target.with_name(f"{stem}_dup{n}{suffix}")
        if not candidate.exists():
            return candidate, True
    raise RuntimeError(f"too many duplicates for {target}")


def audit_row(log_path: Path, row: dict, lock: threading.Lock) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with lock:
        is_new = not log_path.exists()
        with log_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            if is_new:
                writer.writeheader()
            writer.writerow(row)


class Processor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.log_lock = threading.Lock()
        self.in_flight: set[str] = set()
        self.in_flight_lock = threading.Lock()
        for folder in (cfg.converted, cfg.review, cfg.logs):
            folder.mkdir(parents=True, exist_ok=True)

    def claim(self, pdf_path: Path) -> bool:
        key = str(pdf_path.resolve())
        with self.in_flight_lock:
            if key in self.in_flight:
                return False
            self.in_flight.add(key)
            return True

    def release(self, pdf_path: Path) -> None:
        with self.in_flight_lock:
            self.in_flight.discard(str(pdf_path.resolve()))

    def process(self, pdf_path: Path) -> None:
        if not self.claim(pdf_path):
            return
        try:
            self._process_inner(pdf_path)
        finally:
            self.release(pdf_path)

    def _process_inner(self, pdf_path: Path) -> None:
        if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
            return

        if not wait_until_stable(pdf_path, self.cfg.stable_seconds):
            self._log(pdf_path, "", "skipped_unstable", "", "")
            LOG.warning("Skipped (still being written after %ds): %s", MAX_STABLE_WAIT_SECONDS, pdf_path.name)
            return

        text = extract_text_native(pdf_path, self.cfg.poppler_path)
        method = "native"
        lpos = extract_lpos(text)
        if not lpos:
            try:
                text = extract_text_ocr(pdf_path, self.cfg)
                method = "ocr"
                lpos = extract_lpos(text)
            except Exception as exc:
                LOG.error("OCR failed for %s: %s", pdf_path.name, exc)

        if len(lpos) == 1:
            self._route_success(pdf_path, lpos[0], method)
        elif len(lpos) > 1:
            self._route_review(pdf_path, ";".join(lpos), "multi_po", method)
        else:
            self._route_review(pdf_path, "", "no_lpo_found", method)

    def _route_success(self, pdf_path: Path, lpo: str, method: str) -> None:
        target = self.cfg.converted / f"LPO_{lpo}.pdf"
        final, collided = unique_destination(target)
        try:
            shutil.move(str(pdf_path), str(final))
        except OSError as exc:
            LOG.error("Move failed for %s: %s", pdf_path.name, exc)
            self._log(pdf_path, lpo, "error_move", "", method)
            return
        status = "ok_dup" if collided else "ok"
        self._log(pdf_path, lpo, status, str(final), method)
        LOG.info("%s -> %s [%s, %s]", pdf_path.name, final.name, status, method)

    def _route_review(self, pdf_path: Path, lpos: str, status: str, method: str) -> None:
        target = self.cfg.review / pdf_path.name
        final, _ = unique_destination(target)
        try:
            shutil.move(str(pdf_path), str(final))
        except OSError as exc:
            LOG.error("Move failed for %s: %s", pdf_path.name, exc)
            self._log(pdf_path, lpos, "error_move", "", method)
            return
        self._log(pdf_path, lpos, status, str(final), method)
        LOG.info("%s -> REVIEW/%s [%s, %s]", pdf_path.name, final.name, status, method)

    def _log(self, pdf_path: Path, lpo: str, status: str, output: str, method: str) -> None:
        audit_row(
            self.cfg.logs / "processing.log.csv",
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "original_name": pdf_path.name,
                "extracted_lpo": lpo,
                "status": status,
                "output_path": output,
                "method": method,
            },
            self.log_lock,
        )


def run_batch(cfg: Config) -> int:
    processor = Processor(cfg)
    pdfs = sorted(p for p in cfg.inbox.glob("*.pdf") if p.is_file())
    if not pdfs:
        LOG.info("Batch: no PDFs in %s", cfg.inbox)
        return 0
    LOG.info("Batch: processing %d PDFs with %d workers", len(pdfs), cfg.workers)
    with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
        list(pool.map(processor.process, pdfs))
    return 0


def run_watch(cfg: Config) -> int:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    processor = Processor(cfg)
    pool = ThreadPoolExecutor(max_workers=cfg.workers)

    def submit(path: Path) -> None:
        if path.suffix.lower() == ".pdf":
            pool.submit(processor.process, path)

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                submit(Path(event.src_path))

        def on_moved(self, event):
            if not event.is_directory:
                submit(Path(event.dest_path))

    backlog = sorted(p for p in cfg.inbox.glob("*.pdf") if p.is_file())
    if backlog:
        LOG.info("Startup sweep: %d backlog PDFs", len(backlog))
        for p in backlog:
            submit(p)

    observer = Observer()
    observer.schedule(Handler(), str(cfg.inbox), recursive=False)
    observer.start()
    LOG.info("Watching %s (workers=%d, stable=%.1fs)", cfg.inbox, cfg.workers, cfg.stable_seconds)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        LOG.info("Shutdown requested")
    finally:
        observer.stop()
        observer.join()
        pool.shutdown(wait=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CRG LPO Processor")
    parser.add_argument("mode", nargs="?", default="watch", choices=["watch", "batch"])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cfg = load_config(args.config)
    if args.mode == "batch":
        return run_batch(cfg)
    return run_watch(cfg)


if __name__ == "__main__":
    sys.exit(main())
