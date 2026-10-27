param()
$ErrorActionPreference = 'Stop'
$PythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Isolated Python environment is missing.' }
Push-Location -LiteralPath $PSScriptRoot
try {
    & $PythonExe -m local_app.lifecycle stop
    if ($LASTEXITCODE -ne 0) { throw 'Safe shutdown could not be confirmed. No process was force-killed.' }
} finally { Pop-Location }
