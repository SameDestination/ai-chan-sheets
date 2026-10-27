param()
$ErrorActionPreference = 'Stop'
$PythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Isolated Python environment is missing.' }
Push-Location -LiteralPath $PSScriptRoot
try {
    & $PythonExe -m local_app.lifecycle diagnose
    if ($LASTEXITCODE -ne 0) { throw 'Diagnostic command failed.' }
} finally { Pop-Location }
