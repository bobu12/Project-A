@echo off
REM Install ScanDocRename as a Windows Service named "CRG-Processor".
REM Run this script from an elevated (Administrator) Command Prompt.

setlocal

set SERVICE_NAME=CRG-Processor
set SCRIPT_DIR=%~dp0
set PYTHON_EXE=
for /f "delims=" %%i in ('where python') do (
    if not defined PYTHON_EXE set PYTHON_EXE=%%i
)

if not defined PYTHON_EXE (
    echo ERROR: python.exe not found on PATH. Install Python 3.12 first.
    exit /b 1
)

where nssm >nul 2>&1
if errorlevel 1 (
    echo ERROR: nssm.exe not found on PATH. Install NSSM first (see README).
    exit /b 1
)

echo Installing service "%SERVICE_NAME%"...
nssm install "%SERVICE_NAME%" "%PYTHON_EXE%" "%SCRIPT_DIR%processor.py" watch
nssm set "%SERVICE_NAME%" AppDirectory "%SCRIPT_DIR%"
nssm set "%SERVICE_NAME%" Start SERVICE_AUTO_START
nssm set "%SERVICE_NAME%" AppStdout "%SCRIPT_DIR%service.stdout.log"
nssm set "%SERVICE_NAME%" AppStderr "%SCRIPT_DIR%service.stderr.log"
nssm set "%SERVICE_NAME%" AppRotateFiles 1
nssm set "%SERVICE_NAME%" AppRotateOnline 1
nssm set "%SERVICE_NAME%" AppRotateBytes 10485760
nssm set "%SERVICE_NAME%" AppThrottle 5000

echo Starting service...
nssm start "%SERVICE_NAME%"

nssm status "%SERVICE_NAME%"
echo.
echo Done. Manage the service with:
echo   nssm status   %SERVICE_NAME%
echo   nssm stop     %SERVICE_NAME%
echo   nssm restart  %SERVICE_NAME%
echo   nssm remove   %SERVICE_NAME% confirm

endlocal
