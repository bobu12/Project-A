@echo off
REM Launch the GCC Markets Dashboard locally (Windows).
REM Usage: serve.bat [port]
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
  python serve.py %*
  goto :eof
)
where py >nul 2>nul
if %errorlevel%==0 (
  py serve.py %*
  goto :eof
)
echo Python 3 is required. Install it from https://www.python.org/downloads/
