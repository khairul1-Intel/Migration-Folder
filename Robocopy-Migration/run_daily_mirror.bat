@echo off
setlocal

REM Destination is read from config.yaml.
REM Source is read from config.yaml.
REM Allowed destination values:
REM   E:\Production
REM   E:\Development
REM Generated files:
REM   first_time_setup_report.txt (first-time job)
REM   daily_update_history.txt (daily job)

set "SCRIPT_DIR=%~dp0"
set "PYTHON_CMD=py -3"

if not exist "%SCRIPT_DIR%config.yaml" (
    echo Missing config file: %SCRIPT_DIR%config.yaml
    exit /b 2
)

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher 'py' was not found in PATH.
    exit /b 2
)

%PYTHON_CMD% "%SCRIPT_DIR%daily_mirror.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo Daily mirror failed with exit code %EXIT_CODE%.
)

exit /b %EXIT_CODE%
