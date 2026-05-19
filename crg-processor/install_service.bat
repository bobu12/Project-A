@echo off
REM Registers the CRG LPO Processor as an auto-starting Windows Service via NSSM.
REM Must be run from an elevated (Administrator) Command Prompt.

setlocal

set SERVICE_NAME=CRG-Processor
set APP_DIR=%~dp0
set APP_DIR=%APP_DIR:~0,-1%

where nssm >nul 2>&1
if errorlevel 1 (
    echo ERROR: nssm.exe not found on PATH. Install NSSM and add it to PATH first.
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found on PATH. Install Python 3.12 and add it to PATH first.
    exit /b 1
)

for /f "delims=" %%i in ('where python') do set PYTHON_EXE=%%i & goto :found
:found

echo Installing service "%SERVICE_NAME%" using:
echo   python: %PYTHON_EXE%
echo   script: %APP_DIR%\processor.py

nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%APP_DIR%\processor.py" watch
if errorlevel 1 goto :error

nssm set %SERVICE_NAME% AppDirectory "%APP_DIR%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% AppStdout "%APP_DIR%\service.stdout.log"
nssm set %SERVICE_NAME% AppStderr "%APP_DIR%\service.stderr.log"
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateBytes 10485760
nssm set %SERVICE_NAME% AppExit Default Restart
nssm set %SERVICE_NAME% AppRestartDelay 5000

nssm start %SERVICE_NAME%
if errorlevel 1 goto :error

echo.
echo Service "%SERVICE_NAME%" installed and started.
echo Check status with: nssm status %SERVICE_NAME%
exit /b 0

:error
echo.
echo ERROR: service installation failed. See messages above.
exit /b 1
