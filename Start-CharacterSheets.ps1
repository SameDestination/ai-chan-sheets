param([string]$DataRoot = '', [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$AppRoot = $PSScriptRoot
$PythonExe = Join-Path $AppRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw 'Isolated Python environment is missing. Run Install-CharacterSheets.ps1 first.'
}
$LaunchArgs = @('-m', 'local_app.lifecycle', 'start')
if ($DataRoot) { $LaunchArgs += @('--data-root', $DataRoot) }
if ($NoBrowser) { $LaunchArgs += '--no-browser' }
Push-Location -LiteralPath $AppRoot
try {
    & $PythonExe @LaunchArgs
    if ($LASTEXITCODE -ne 0) { throw 'Character Sheets startup failed. Run Diagnose-CharacterSheets.cmd.' }
} finally { Pop-Location }
