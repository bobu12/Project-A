# ScanDocRename — CRG LPO Processor

Automated rename + routing of scanned LPO purchase orders on a Windows
file-server VM. Watches `D:\D` (the existing scan folder for the 10 office
scanners), extracts the 8-digit LPO number from each PDF
(`P.O No: 26000553/L2`), renames the file to `LPO_26000553.pdf`, and moves
it to `D:\D\CONVERTED`. Files without a recognisable LPO header land in
`D:\D\REVIEW` for manual handling. Every action is logged to
`D:\D\LOGS\processing.log.csv`.

```
D:\D\                          <- INBOX (existing; scanners write here)
   ├── CONVERTED\              <- LPO_xxxxxxxx.pdf
   ├── REVIEW\                 <- exceptions (no_lpo_found / multi_po)
   └── LOGS\
       └── processing.log.csv  <- audit trail
```

## Files in this folder

| File | Purpose |
|------|---------|
| `processor.py` | The watcher / renamer. Run modes: `batch`, `watch`. |
| `requirements.txt` | Python deps (`watchdog`, `pdf2image`, `pytesseract`, `pdfminer.six`). |
| `config.ini.example` | Template config — copy to `config.ini` and edit. |
| `install_service.bat` | Registers the script as the `CRG-Processor` Windows Service via NSSM. |
| `tests/` | Unit tests (regex, dedup, stable-file detection). |

## Quick install on the Windows VM

Run every step in an **Administrator** Command Prompt on the VM. The full
narrative version is in the *Implementation Document*; the bullet list
below is the short form, tailored for `D:\D`.

1. **Install Python 3.12** from https://www.python.org/downloads/windows/.
   Tick *Add python.exe to PATH*. Verify: `python --version`.
2. **Install Poppler** from
   https://github.com/oschwartz10612/poppler-windows/releases/. Extract to
   `C:\poppler\` so `C:\poppler\Library\bin\pdftotext.exe` exists. Add
   `C:\poppler\Library\bin` to System PATH. Verify: `pdftotext -v`.
3. **Install Tesseract OCR** from
   https://github.com/UB-Mannheim/tesseract/wiki. Accept default path
   `C:\Program Files\Tesseract-OCR\`. Add to PATH. Verify:
   `tesseract --version`.
4. **Install NSSM** from https://nssm.cc/download. Copy `win64\nssm.exe`
   to `C:\nssm\nssm.exe`. Add `C:\nssm` to PATH. Verify: `nssm --help`.
5. **Copy this folder** to `C:\ScanDocRename\` on the VM.
6. **Install Python deps**:
   ```
   cd C:\ScanDocRename
   pip install -r requirements.txt
   ```
7. **Create the working folders**:
   ```
   mkdir D:\D\CONVERTED
   mkdir D:\D\REVIEW
   mkdir D:\D\LOGS
   ```
   `D:\D` itself already exists (scanners write there today).
8. **Configure**:
   ```
   copy config.ini.example config.ini
   notepad config.ini
   ```
   The defaults already point at `D:\D`. Only edit if Poppler / Tesseract
   landed in a non-default location.
9. **Smoke test** (interactive, no service yet):
   ```
   python processor.py batch
   ```
   Drop 2-3 sample PDFs into `D:\D` first. Confirm:
   - Renamed files appear in `D:\D\CONVERTED\` as `LPO_xxxxxxxx.pdf`.
   - One row per file in `D:\D\LOGS\processing.log.csv` with `status=ok`.
10. **Install as a Windows Service** (auto-starts on boot, auto-restarts on crash):
    ```
    install_service.bat
    ```
    Verify with `nssm status CRG-Processor` — expect `SERVICE_RUNNING`.

## Service management

| Action | Command |
|--------|---------|
| Status | `nssm status CRG-Processor` |
| Stop | `nssm stop CRG-Processor` |
| Start | `nssm start CRG-Processor` |
| Restart after config change | `nssm restart CRG-Processor` |
| Uninstall | `nssm remove CRG-Processor confirm` |

## CSV audit log columns

```
timestamp,original_name,extracted_lpo,status,output_path,method
```

`status` is one of: `ok`, `ok_dup`, `no_lpo_found`, `multi_po`,
`skipped_unstable`, `error_move`. `method` is `native` (pdftotext fast
path) or `ocr` (Tesseract fallback).

## Running the tests

The tests cover the pure-Python logic (regex, dedup, stable-file
detection). No Poppler or Tesseract required.

```
cd C:\ScanDocRename
pip install pytest
python -m pytest tests -v
```

## Troubleshooting

| Symptom | First thing to check |
|---------|----------------------|
| Service won't start | `service.stderr.log` next to `processor.py`. Usually a wrong path in `config.ini` or missing `poppler_path` / `tesseract_cmd`. |
| Every file goes to REVIEW with `no_lpo_found` | OCR not working. Run `tesseract --version` and confirm `tesseract_cmd` in `config.ini`. Try `ocr_dpi = 400`. |
| Files keep landing in REVIEW with `multi_po` | Correct behavior — the PDF really does contain more than one LPO. Split it manually. |
| New scans not processed | Confirm `inbox` in `config.ini` matches the exact path the scanners write to (`D:\D`). Check `service.stdout.log` for the `watching ...` line. |

## How the matcher works

The regex (in `processor.py`) is:

```python
P\.?\s*O\.?\s*No\.?\s*[:#]?\s*(\d{8})\s*/\s*L\s*\d+
```

It matches headers like `P.O No: 26000553/L2`, `P O No 26000008 / L4`, etc.
The capture group returns the 8-digit LPO number. Anything that fails this
match (e.g. an *Order Number : 26003160 /B6* line from an Insurance
Estimate) is routed to REVIEW rather than mis-named.
