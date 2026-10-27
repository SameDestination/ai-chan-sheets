@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Diagnose-CharacterSheets.ps1" %*
pause
