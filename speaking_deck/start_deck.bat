@echo off
rem Opens the speaking deck through a tiny local web server (localhost only).
rem Double-clicking the .html directly also works, but YouTube will not play
rem embedded videos from a file:// page (Error 153) - the deck then shows the talk's lines as text instead.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve_deck.ps1"
if errorlevel 1 pause
