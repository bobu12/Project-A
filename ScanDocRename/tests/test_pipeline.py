"""End-to-end pipeline test with text extraction stubbed out."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import processor  # noqa: E402
from processor import AuditLog, Config, Result, process_file  # noqa: E402


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    inbox = tmp_path / "INBOX"
    converted = tmp_path / "CONVERTED"
    review = tmp_path / "REVIEW"
    logs = tmp_path / "LOGS"
    for d in (inbox, converted, review, logs):
        d.mkdir()
    return Config(
        inbox=inbox,
        converted=converted,
        review=review,
        logs=logs,
        workers=1,
        stable_seconds=0.1,
        stable_timeout=2.0,
        ocr_dpi=300,
        ocr_max_pages=1,
        poppler_path=None,
        tesseract_cmd="",
    )


def _drop_pdf(folder: Path, name: str) -> Path:
    p = folder / name
    p.write_bytes(b"%PDF-1.4\nfake\n%%EOF\n")
    return p


def test_single_lpo_routes_to_converted(cfg: Config, monkeypatch):
    monkeypatch.setattr(processor, "extract_text_native", lambda *a, **k: "P.O No: 26000553/L2")
    pdf = _drop_pdf(cfg.inbox, "L2-LPO.pdf")
    result: Result = process_file(pdf, cfg)
    assert result.status == "ok"
    assert result.extracted_lpo == "26000553"
    assert (cfg.converted / "LPO_26000553.pdf").exists()
    assert not pdf.exists()


def test_no_match_routes_to_review(cfg: Config, monkeypatch):
    monkeypatch.setattr(processor, "extract_text_native", lambda *a, **k: "no header here")
    # Also block OCR fallback (which would import pdf2image)
    monkeypatch.setattr(processor, "extract_text_ocr", lambda *a, **k: "")
    pdf = _drop_pdf(cfg.inbox, "noisy.pdf")
    result = process_file(pdf, cfg)
    assert result.status == "no_lpo_found"
    assert (cfg.review / "noisy.pdf").exists()


def test_multi_po_routes_to_review(cfg: Config, monkeypatch):
    text = "P.O No: 26000553/L2 ... P.O No: 26000008/L4"
    monkeypatch.setattr(processor, "extract_text_native", lambda *a, **k: text)
    pdf = _drop_pdf(cfg.inbox, "bundle.pdf")
    result = process_file(pdf, cfg)
    assert result.status == "multi_po"
    assert result.extracted_lpo == "26000553;26000008"
    assert (cfg.review / "bundle.pdf").exists()


def test_duplicate_target_gets_dup_suffix(cfg: Config, monkeypatch):
    monkeypatch.setattr(processor, "extract_text_native", lambda *a, **k: "P.O No: 26000553/L2")
    (cfg.converted / "LPO_26000553.pdf").write_bytes(b"previous")
    pdf = _drop_pdf(cfg.inbox, "scan.pdf")
    result = process_file(pdf, cfg)
    assert result.status == "ok_dup"
    assert (cfg.converted / "LPO_26000553_dup1.pdf").exists()


def test_audit_log_appends_row(cfg: Config):
    audit = AuditLog(cfg.logs / "processing.log.csv")
    audit.write(Result("scan.pdf", "26000553", "ok",
                       str(cfg.converted / "LPO_26000553.pdf"), "native"))
    text = (cfg.logs / "processing.log.csv").read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    assert lines[0].startswith("timestamp,")
    assert "scan.pdf" in lines[1]
    assert "26000553" in lines[1]
    assert "ok" in lines[1]


def test_ocr_fallback_used_when_native_empty(cfg: Config, monkeypatch):
    monkeypatch.setattr(processor, "extract_text_native", lambda *a, **k: "")
    monkeypatch.setattr(processor, "extract_text_ocr", lambda *a, **k: "P.O No: 26000008/L4")
    pdf = _drop_pdf(cfg.inbox, "image-only.pdf")
    result = process_file(pdf, cfg)
    assert result.status == "ok"
    assert result.method == "ocr"
    assert result.extracted_lpo == "26000008"
