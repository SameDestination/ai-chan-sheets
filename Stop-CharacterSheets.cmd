@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Stop-CharacterSheets.ps1" %*
if errorlevel 1 pause
