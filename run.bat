@echo off
rem One-click start for WordStep: installs what is missing, picks a free port
rem (8000, or the next free one) and opens the browser. Options are passed on:
rem   run.bat --host 0.0.0.0     let other devices on the network connect
rem   run.bat --port 9000        start looking for a free port at 9000
rem   run.bat --no-browser       don't open the browser
setlocal
title WordStep
cd /d "%~dp0"

set "UV="
where uv >nul 2>nul && set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"

if defined UV (
    "%UV%" run python -m app.launch %*
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m app.launch %*
) else (
    echo WordStep needs uv to install its Python packages. Install it with:
    echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    echo and then run this file again.
    pause
    exit /b 1
)
if errorlevel 1 pause
