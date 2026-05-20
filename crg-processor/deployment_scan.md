# CRG LPO Processor — Deployment Guide

End-to-end install + smoke test + Windows Service deployment on a clean
Windows VM. Every step in this document was validated during the
deployment that produced this package. Issues encountered along the
way (VC++ runtime missing, NSSM mirror down, Tesseract PATH stale,
OCR mis-segmentation) are covered in the Troubleshooting section.

---

## 0. What you're deploying

A small Python service that watches the shared scan folder, extracts the
8-digit LPO number from page 1 of each scanned PDF
(`P.O No: <8 digits>/L<n>`), renames the file to `LPO_<8 digits>.pdf` and
moves it to a `CONVERTED` folder. Ambiguous or unreadable files are
routed to `REVIEW`. Every action appends one row to a CSV audit log.

Folder layout after deployment:

```
C:\crg-processor\          # the code (this package)
C:\Scans\CRG\              # INBOX  (scanners write here)
C:\Scans\CRG\CONVERTED\    # renamed LPO PDFs land here
C:\Scans\CRG\REVIEW\       # exceptions land here
C:\Scans\CRG\LOGS\         # processing.log.csv
```

*(If your scan share is on a different path or a UNC, swap
`C:\Scans\CRG` accordingly throughout — only `config.ini` cares.)*

---

## 1. Prerequisites

Install these on the Windows VM in this order. Every step has a
verification command — don't skip them.

### 1.1 Python 3.12

1. Browse to https://www.python.org/downloads/windows/
2. Download the **Windows installer (64-bit)** for Python 3.12.x.
3. Run the installer. **TICK "Add python.exe to PATH"** on the first
   screen, then click **Install Now**.
4. Open a NEW Command Prompt and verify:

   ```
   python --version
   ```

   Expect: `Python 3.12.x`.

### 1.2 Microsoft Visual C++ 2015-2022 Redistributable (x64)

Poppler and Tesseract are compiled against `MSVCP140.dll`. Without this
redistributable, both fail with: *"The code execution cannot proceed
because MSVCP140.dll was not found"*.

In Admin PowerShell:

```powershell
$url = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
$dst = "$env:TEMP\vc_redist.x64.exe"
Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing
Start-Process -FilePath $dst -ArgumentList '/install','/quiet','/norestart' -Wait
```

No reboot required in almost all cases. If the installer asks for one, accept.

### 1.3 Poppler for Windows

Provides `pdftotext.exe` (fast embedded-text extraction) and the
rendering backend that `pdf2image` uses for OCR.

1. Browse to https://github.com/oschwartz10612/poppler-windows/releases/
2. Download the latest `Release-XX.X.X-0.zip`.
3. Extract the ZIP to `C:\poppler\` so the binaries land at
   `C:\poppler\poppler-XX.X.X\Library\bin\`.

   *(In the validated deployment the path was
   `C:\poppler\poppler-24.08.0\Library\bin`. Yours will match whichever
   version you downloaded.)*

4. Add that bin folder to System PATH. Use PowerShell (avoids the
   `setx` 1024-char truncation bug):

   ```powershell
   [Environment]::SetEnvironmentVariable(
       'Path',
       [Environment]::GetEnvironmentVariable('Path','Machine') + ';C:\poppler\poppler-24.08.0\Library\bin',
       'Machine')
   ```

   Substitute your actual version folder.

5. Close every cmd / PowerShell window. Open a NEW Admin Command Prompt
   and verify:

   ```
   pdftotext -v
   ```

   Expect: `pdftotext version 24.08.0` plus copyright lines.

### 1.4 Tesseract OCR

Required for image-only scans (no embedded text). Default install path
is `C:\Program Files\Tesseract-OCR\`. **The processor expects exactly
this path** — don't change it unless you also update `config.ini`.

Easiest path:

```powershell
$url = 'https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.4.0.20240606.exe'
$dst = "$env:TEMP\tesseract-installer.exe"
Invoke-WebRequest -Uri $url -OutFile $dst -UseBasicParsing
Start-Process -FilePath $dst -ArgumentList '/S' -Wait
```

Verify:

```powershell
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --version
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --list-langs
```

`--version` should print a banner. `--list-langs` should include `eng`.

*(If the Mannheim mirror is blocked, browse to
https://github.com/UB-Mannheim/tesseract/wiki and run the 64-bit
installer manually.)*

The default installer does NOT add Tesseract to PATH. The processor
calls Tesseract via its absolute path from `config.ini`, so that's fine
— but if you want `tesseract --version` to work from any cmd window:

```powershell
[Environment]::SetEnvironmentVariable(
    'Path',
    [Environment]::GetEnvironmentVariable('Path','Machine') + ';C:\Program Files\Tesseract-OCR',
    'Machine')
```

### 1.5 NSSM (service wrapper, only needed for Section 5)

Skip this section if you're only doing a smoke test today.

`nssm.cc` is frequently down (HTTP 503). The most reliable source is the
Chocolatey CDN. In Admin PowerShell:

```powershell
$url = 'https://packages.chocolatey.org/NSSM.2.24.0.20180307.nupkg'
$zip = "$env:TEMP\nssm.zip"
$ext = "$env:TEMP\nssm-extract"
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $ext -Force
$exe = Get-ChildItem -Path $ext -Recurse -Filter 'nssm.exe' |
       Where-Object { $_.FullName -like '*win64*' } |
       Select-Object -First 1
New-Item -ItemType Directory -Force -Path C:\nssm | Out-Null
Copy-Item $exe.FullName -Destination C:\nssm\nssm.exe -Force
[Environment]::SetEnvironmentVariable(
    'Path',
    [Environment]::GetEnvironmentVariable('Path','Machine') + ';C:\nssm',
    'Machine')
```

Close every cmd window. Open a NEW Admin cmd and verify:

```
nssm --help
```

Expect the `NSSM: The non-sucking service manager` banner.

### 1.6 Final prerequisite check

Open a NEW Admin cmd window. Run all four:

```
python --version
pdftotext -v
"C:\Program Files\Tesseract-OCR\tesseract.exe" --version
nssm --help
```

All four must succeed before continuing.

---

## 2. Deploy the processor

### 2.1 Extract this package

Unzip `CRG_SCAN.zip` (or copy the `crg-processor` folder out of it)
to `C:\crg-processor\` so you end up with:

```
C:\crg-processor\processor.py
C:\crg-processor\requirements.txt
C:\crg-processor\config.ini.example
C:\crg-processor\install_service.bat
C:\crg-processor\README.md
```

### 2.2 Install the Python dependencies

In Admin cmd:

```
cd C:\crg-processor
pip install -r requirements.txt
```

Installs `watchdog`, `pdf2image`, `pytesseract`, `pdfminer.six`. ~30 sec.

### 2.3 Create the working folders

For the smoke test, use a local folder (faster, simpler than UNC):

```powershell
New-Item -ItemType Directory -Force -Path C:\Scans\CRG            | Out-Null
New-Item -ItemType Directory -Force -Path C:\Scans\CRG\CONVERTED  | Out-Null
New-Item -ItemType Directory -Force -Path C:\Scans\CRG\REVIEW     | Out-Null
New-Item -ItemType Directory -Force -Path C:\Scans\CRG\LOGS       | Out-Null
```

For production, point the four `[paths]` entries in `config.ini` at
your real shared scan folder (UNC or local — both work).

### 2.4 Create `config.ini`

In Admin PowerShell:

```powershell
@'
[paths]
inbox     = C:\Scans\CRG
converted = C:\Scans\CRG\CONVERTED
review    = C:\Scans\CRG\REVIEW
logs      = C:\Scans\CRG\LOGS

[settings]
workers        = 4
stable_seconds = 2
ocr_dpi        = 400
poppler_path   = C:\poppler\poppler-24.08.0\Library\bin
tesseract_cmd  = C:\Program Files\Tesseract-OCR\tesseract.exe
'@ | Set-Content -Path C:\crg-processor\config.ini -Encoding ASCII
```

**Important — adjust two values to match your install:**

| Key | Edit if… |
|---|---|
| `poppler_path` | your Poppler version folder isn't `poppler-24.08.0` |
| Any `[paths]` value | your scan folder isn't `C:\Scans\CRG` |

`ocr_dpi = 400` was tuned during validation — at 300 DPI the small red
`P.O No:` cell on CRG's purchase-order template was mis-segmented and
Tesseract dropped digits. 400 DPI captures it reliably.

---

## 3. Smoke test

### 3.1 Drop sample PDFs into INBOX

Copy a few known LPO PDFs (e.g. `L2-LPO.pdf`, `L9-LPO.pdf`) directly
into `C:\Scans\CRG\` — NOT into the subfolders.

### 3.2 Run a one-pass batch

```
cd C:\crg-processor
python processor.py batch
```

Expected log lines (one per file):
```
L2-LPO.pdf -> CONVERTED\LPO_26000553.pdf [ok, ocr]
L9-LPO.pdf -> CONVERTED\LPO_26001451.pdf [ok, ocr]
...
```

### 3.3 Inspect the results

```powershell
Get-ChildItem C:\Scans\CRG\CONVERTED
Get-ChildItem C:\Scans\CRG\REVIEW
Get-Content   C:\Scans\CRG\LOGS\processing.log.csv
```

`processing.log.csv` columns:

| Column          | Description |
| --------------- | ----------- |
| `timestamp`     | UTC ISO-8601 |
| `original_name` | Filename the scanner produced |
| `extracted_lpo` | 8-digit LPO (`;`-separated for multi-PO) |
| `status`        | `ok` / `ok_dup` / `no_lpo_found` / `multi_po` / `skipped_unstable` / `error_move` |
| `output_path`   | Final destination |
| `method`        | `native` (pdftotext) or `ocr` (Tesseract) |

Files that genuinely aren't LPOs (e.g. insurance estimates with
`Order Number ... /B6` instead of `P.O No: ... /L<n>`) are correctly
routed to `REVIEW` with `status = no_lpo_found` — that's expected
behaviour, not a bug.

---

## 4. Live watch mode (foreground)

To watch the INBOX continuously without installing the service yet:

```
cd C:\crg-processor
python processor.py watch
```

The script logs `Watching C:\Scans\CRG (workers=4, stable=2.0s)` and
processes files as they arrive. Press Ctrl+C to stop.

Use this for an end-to-end test with the actual scanners before
committing to running it as a service.

---

## 5. Install as a Windows Service

Once the smoke test passes, register the script with NSSM so it
auto-starts on boot and auto-restarts on crash.

### 5.1 Run the installer

Open an **elevated** Command Prompt (the script needs Administrator
rights to register the service):

```
cd C:\crg-processor
install_service.bat
```

The script:
- Registers a service named `CRG-Processor`.
- Sets it to start automatically on boot.
- Configures stdout/stderr log rotation at 10 MB.
- Sets auto-restart on crash with a 5-second delay.
- Starts the service immediately.

### 5.2 Verify

```
nssm status CRG-Processor
```

Expect: `SERVICE_RUNNING`.

Watch the live log:
```
type C:\crg-processor\service.stdout.log
```

You should see `Watching ...` near the bottom.

### 5.3 Day-to-day commands

| Action                   | Command                            |
| ------------------------ | ---------------------------------- |
| Status                   | `nssm status CRG-Processor`        |
| Stop                     | `nssm stop CRG-Processor`          |
| Start                    | `nssm start CRG-Processor`         |
| Restart (after config)   | `nssm restart CRG-Processor`       |
| Uninstall                | `nssm remove CRG-Processor confirm`|

### 5.4 Service account (only if INBOX is a UNC share)

By default the service runs as `LocalSystem`. That works if the INBOX
is local to the VM.

If INBOX is a UNC path to a different server, change the service
account to a domain user that has read+delete on INBOX and write on
the other folders:

```
nssm edit CRG-Processor
```

Switch to the **Log on** tab → **This account** → enter credentials.

---

## 6. Troubleshooting

### 6.1 `pdftotext: not recognized as an internal or external command`

PATH wasn't updated, or the cmd window started before the PATH change.

1. Open a brand-new Admin cmd window (close all existing ones first).
2. `echo %PATH%` — confirm Poppler's bin folder is listed.
3. If not, re-run the PowerShell command from section 1.3.

### 6.2 `MSVCP140.dll was not found`

VC++ Redistributable missing. Re-run section 1.2.

### 6.3 OCR fails: *"tesseract.exe is not installed or it's not in your PATH"*

Tesseract isn't installed at `C:\Program Files\Tesseract-OCR\`. Re-run
section 1.4 and verify with `Test-Path 'C:\Program Files\Tesseract-OCR\tesseract.exe'`.

### 6.4 Every LPO lands in REVIEW with `no_lpo_found`

Two possible causes:

| Check | What to do |
|---|---|
| `tesseract --version` works? | If no, fix section 1.4 |
| OCR method is `ocr` in log? | If `native`, file has no embedded text and OCR isn't being called — see 6.3 |
| LPO not in the documented format `P.O No: <8 digits>/L<n>` | Open the PDF, confirm the format; for genuine non-LPO docs (estimates, invoices), routing to REVIEW is correct |
| Small / red / tightly-laid-out form text? | Try `ocr_dpi = 600` in `config.ini` and restart |

### 6.5 Files keep landing in REVIEW with `multi_po`

The PDF genuinely contains more than one purchase order. Office staff
should split it manually and re-drop the single-PO pieces into INBOX.

### 6.6 Service won't start

```
type C:\crg-processor\service.stderr.log
```

Almost always a bad path in `config.ini`. As a quick check, run the
script manually:

```
cd C:\crg-processor
python processor.py batch
```

The live error message will be obvious.

### 6.7 NSSM not recognized after install

`C:\nssm` not on PATH, or the cmd window is stale. Open a new Admin
window. If still failing, run `Test-Path C:\nssm\nssm.exe` — if `False`,
the binary wasn't placed; re-run section 1.5.

---

## 7. Architecture cheat sheet

```
Scanner 1
Scanner 2          \\FILESERVER\Scans\CRG\  (INBOX)
   ...    ----->         |
Scanner 10               v
                  CRG-Processor (Windows Service via NSSM)
                         |
                         |  watchdog event ──► stable wait (2s)
                         |  pdftotext (fast path)
                         |  Tesseract OCR @ 400 DPI, PSM 6 (fallback)
                         |  regex: P.O No: (\d{8})/L\d+
                         v
            CONVERTED\LPO_<8digits>.pdf            ── success
            REVIEW\<original>.pdf                  ── exception
            LOGS\processing.log.csv                ── audit row
```

Six pipeline stages, ~1–3 seconds per file, 4 workers in parallel by
default. Tuned for 1,000+ files/day on a single VM with zero cloud
dependencies.

---

## 8. Rollout sequence (recommended)

| When | Action |
|---|---|
| Day 1 | Complete sections 1–3 on the VM. Smoke-test with 5–10 known PDFs. |
| Day 2 | Run section 5 (install service). Pilot with 2 of the 10 scanners pointed at the existing INBOX. Watch the log for a full day. |
| Day 3 | If Day 2 clean, the remaining 8 scanners need no change — they're already writing to the same share. |
| Week 2 | Open `processing.log.csv` in Excel; pivot by `status`. If REVIEW > 5% of volume, bump `ocr_dpi` and/or refine the regex in `processor.py`. |

---

## 9. File manifest in this package

```
deployment_scan.md            ← this document
crg-processor/
  processor.py                ← main script (watch + batch modes)
  requirements.txt            ← Python deps
  config.ini.example          ← template; copy to config.ini and edit
  install_service.bat         ← NSSM service installer
  README.md                   ← project README
```

The same code lives on GitHub:
`https://github.com/bobu12/Project-A` branch
`claude/add-poppler-to-path-gYiMI`, folder `crg-processor/`.

---

End of document.
