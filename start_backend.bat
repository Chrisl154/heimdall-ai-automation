@echo off
REM Start Heimdall backend
setlocal enabledelayedexpansion

REM Run from project root so .env relative paths resolve correctly
cd /d "%~dp0"

REM Create venv if it doesn't exist
if not exist "backend\.venv" (
    echo Creating virtual environment...
    python -m venv backend\.venv
    if errorlevel 1 ( echo ERROR: Failed to create virtual environment. & exit /b 1 )
)

REM Activate venv
call backend\.venv\Scripts\activate.bat

REM Install requirements if requirements.txt is newer than the marker (or marker absent)
powershell -NoProfile -Command ^
  "if (-not (Test-Path 'backend\.venv\requirements_installed') -or (Get-Item 'backend\requirements.txt').LastWriteTime -gt (Get-Item 'backend\.venv\requirements_installed').LastWriteTime) { exit 1 } else { exit 0 }" >nul 2>&1
if errorlevel 1 (
    echo Installing requirements...
    pip install -r backend\requirements.txt
    if errorlevel 1 ( echo ERROR: pip install failed. & exit /b 1 )
    copy /b backend\requirements.txt backend\.venv\requirements_installed >nul
)

REM Start backend
echo Starting backend...
python backend\main.py
