@echo off
REM Start Heimdall frontend
setlocal

cd /d "%~dp0frontend"

REM Install dependencies if package.json is newer than the marker (or marker absent)
powershell -NoProfile -Command ^
  "if (-not (Test-Path 'node_modules\.install_ok') -or (Get-Item 'package.json').LastWriteTime -gt (Get-Item 'node_modules\.install_ok').LastWriteTime) { exit 1 } else { exit 0 }" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    npm install
    if errorlevel 1 ( echo ERROR: npm install failed. & exit /b 1 )
    copy /b package.json node_modules\.install_ok >nul
)

REM Start dev server
echo Starting frontend...
npm run dev
