param([string]$Destination = (Join-Path $env:USERPROFILE 'ai-chan-sheets-local'),
      [string]$DataRoot = '', [string]$Python = '', [switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
$SourceRoot = $PSScriptRoot
$ResolvedDestination = [IO.Path]::GetFullPath($Destination)
if (-not $DataRoot) { $DataRoot = Join-Path $env:USERPROFILE 'Documents\CharacterSheets' }
$ResolvedDataRoot = [IO.Path]::GetFullPath($DataRoot)
if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot 'requirements.txt'))) { throw 'Pinned requirements.txt is missing.' }
if (-not $Python) {
    $Candidates = @()
    $PyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        $DetectedPython = & $PyLauncher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $Candidates += $DetectedPython }
    }
    $PythonCommand = Get-Command 'python.exe' -ErrorAction SilentlyContinue
    if ($PythonCommand) { $Candidates += $PythonCommand.Source }
    $Candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe')
    $Candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
    $Candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path -LiteralPath $Candidate)) {
            & $Candidate -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { $Python = $Candidate; break }
        }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { throw 'Python 3.11+ was not found. Pass -Python with an existing interpreter path.' }
& $Python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
New-Item -ItemType Directory -Path $ResolvedDestination -Force | Out-Null
New-Item -ItemType Directory -Path $ResolvedDataRoot -Force | Out-Null
$RuntimeFile = Join-Path $ResolvedDestination '.runtime\server.json'
if (Test-Path -LiteralPath $RuntimeFile) {
    $RuntimeRecord = Get-Content -LiteralPath $RuntimeFile -Raw | ConvertFrom-Json
    if ($RuntimeRecord.pid -and (Get-Process -Id $RuntimeRecord.pid -ErrorAction SilentlyContinue)) {
        throw 'An installed instance may still be running. Use Stop-CharacterSheets.cmd, then reinstall.'
    }
}
if ([IO.Path]::GetFullPath($SourceRoot).TrimEnd('\') -ne $ResolvedDestination.TrimEnd('\')) {
    # Copy only application sources and notices. Existing files are backed up; user data is never copied.
    $BackupRoot = Join-Path $ResolvedDestination ('.install-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff'))
    $Selected = @('local_app', 'requirements.txt', 'LICENSE', 'README.md', 'LOCAL_README.zh-CN.md',
                  'NOTICE.local.md', 'AI_CONTEXT.md', 'LOCAL_VALIDATION.md', 'LOCAL_HANDOFF.md',
                  'UPSTREAM_COMPATIBILITY.md', 'CAPABILITY_AUDIT.md', '.env.example',
                  'Start-CharacterSheets.cmd', 'Start-CharacterSheets.ps1',
                  'Stop-CharacterSheets.cmd', 'Stop-CharacterSheets.ps1',
                  'Diagnose-CharacterSheets.cmd', 'Diagnose-CharacterSheets.ps1', 'Install-CharacterSheets.ps1')
    foreach ($RelativePath in $Selected) {
        $SourceItem = Join-Path $SourceRoot $RelativePath
        if (-not (Test-Path -LiteralPath $SourceItem)) { continue }
        $DestinationItem = Join-Path $ResolvedDestination $RelativePath
        if (Test-Path -LiteralPath $DestinationItem) {
            $BackupItem = Join-Path $BackupRoot $RelativePath
            $BackupParent = Split-Path -Parent $BackupItem
            New-Item -ItemType Directory -Path $BackupParent -Force | Out-Null
            Copy-Item -LiteralPath $DestinationItem -Destination $BackupItem -Recurse
        }
        if ((Get-Item -LiteralPath $SourceItem).PSIsContainer) {
            New-Item -ItemType Directory -Path $DestinationItem -Force | Out-Null
            $SourceAbsolute = [IO.Path]::GetFullPath($SourceItem).TrimEnd('\')
            Get-ChildItem -LiteralPath $SourceItem -Recurse -File | Where-Object {
                $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'
            } | ForEach-Object {
                $ChildRelative = $_.FullName.Substring($SourceAbsolute.Length).TrimStart('\')
                $ChildTarget = Join-Path $DestinationItem $ChildRelative
                New-Item -ItemType Directory -Path (Split-Path -Parent $ChildTarget) -Force | Out-Null
                Copy-Item -LiteralPath $_.FullName -Destination $ChildTarget -Force
            }
        } else { Copy-Item -LiteralPath $SourceItem -Destination $DestinationItem -Force }
    }
    # Preserve the upstream Chinese copyright/authorization notice without hard-coded non-ASCII PS source.
    Get-ChildItem -LiteralPath $SourceRoot -File -Filter '*.md' | Where-Object { $_.Name -match '[^\x00-\x7F]' } | ForEach-Object {
        $NoticeTarget = Join-Path $ResolvedDestination $_.Name
        if (-not (Test-Path -LiteralPath $NoticeTarget)) { Copy-Item -LiteralPath $_.FullName -Destination $NoticeTarget }
    }
}
$VenvRoot = Join-Path $ResolvedDestination '.venv'
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython)) {
    if (Test-Path -LiteralPath $VenvRoot) { throw 'Existing .venv is incomplete; preserve it and choose a new install directory.' }
    & $Python -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create isolated virtual environment.' }
}
& $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $ResolvedDestination 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency installation failed. No global packages were changed.' }
Write-Output ('INSTALLED: ' + $ResolvedDestination)
Write-Output ('DATA: ' + $ResolvedDataRoot)
Write-Output 'Image generation mode: interactive subscription-only handoff; no API billing.'
if (-not $NoLaunch) {
    & (Join-Path $ResolvedDestination 'Start-CharacterSheets.ps1') -DataRoot $ResolvedDataRoot
}
