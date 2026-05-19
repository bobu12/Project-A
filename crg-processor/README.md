# CRG LPO Processor

Watches a shared scan folder for LPO PDFs, extracts the 8-digit LPO number
from page 1 (`P.O No: <8 digits>/L<n>`), renames the file to
`LPO_<8 digits>.pdf` and moves it to a `CONVERTED` folder. Ambiguous or
unreadable files are routed to `REVIEW`. Every action is logged to
`LOGS\processing.log.csv`.

Designed to run as an always-on Windows Service on the existing
file-server VM that already hosts the scan share. See
`../ImplementDoc.docx` and `../SolutionArchitecture.docx` for the full
design.

## Layout

```
crg-processor/
  processor.py            # main script (watch + batch modes)
  requirements.txt        # Python deps
  config.ini.example      # template -> copy to config.ini and edit
  install_service.bat     # registers the Windows Service via NSSM
  README.md               # this file
```

## Prerequisites

Install these on the Windows VM and confirm each is on `PATH`:

| Component        | Verify with         |
| ---------------- | ------------------- |
| Python 3.12      | `python --version`  |
| Poppler          | `pdftotext -v`      |
| Tesseract OCR    | `tesseract --version` |
| NSSM             | `nssm --help`       |

Full step-by-step install (download URLs, PATH edits, screenshots) is in
`ImplementDoc.docx`, section 4.

## Setup

```cmd
cd C:\crg-processor
pip install -r requirements.txt
copy config.ini.example config.ini
notepad config.ini
```

Edit `config.ini` so `inbox`, `converted`, `review` and `logs` match
your environment. Set `poppler_path` to the folder containing
`pdftotext.exe`, and `tesseract_cmd` to the full path of
`tesseract.exe`.

## Smoke test (before installing the service)

```cmd
cd C:\crg-processor
python processor.py batch
```

A one-pass sweep over `inbox`. Each PDF either moves to `converted`
(named `LPO_<8 digits>.pdf`) or to `review`. Open
`logs\processing.log.csv` in Excel to confirm one row per file with
`status = ok`.

## Run as a Windows Service

From an elevated Command Prompt:

```cmd
cd C:\crg-processor
install_service.bat
```

This registers `CRG-Processor` to start on boot and auto-restart on
crash. Day-to-day management:

| Action     | Command                            |
| ---------- | ---------------------------------- |
| Status     | `nssm status CRG-Processor`        |
| Stop       | `nssm stop CRG-Processor`          |
| Start      | `nssm start CRG-Processor`         |
| Restart    | `nssm restart CRG-Processor`       |
| Uninstall  | `nssm remove CRG-Processor confirm`|

## Audit log

`logs\processing.log.csv` columns:

| Column          | Description |
| --------------- | ----------- |
| `timestamp`     | UTC ISO-8601 timestamp when the file was processed |
| `original_name` | Filename the scanner produced |
| `extracted_lpo` | 8-digit LPO (`;`-separated for multi-PO files) |
| `status`        | `ok` / `ok_dup` / `no_lpo_found` / `multi_po` / `skipped_unstable` / `error_move` |
| `output_path`   | Final destination in `CONVERTED` or `REVIEW` |
| `method`        | `native` (pdftotext) or `ocr` (Tesseract) |

## Troubleshooting

| Symptom | Likely cause | Fix |
| ------- | ------------ | --- |
| Service won't start | Bad path in `config.ini` | Run `python processor.py batch` to see the live error |
| Every file lands in REVIEW | Tesseract not on PATH or wrong `tesseract_cmd` | `tesseract --version`; correct `config.ini` |
| Some scans missed | Path mismatch with what scanners write | Compare `inbox` to the scanner's Scan-to-Folder target |
| Low OCR accuracy | DPI too low | Bump `ocr_dpi` from 300 to 400 and restart |
