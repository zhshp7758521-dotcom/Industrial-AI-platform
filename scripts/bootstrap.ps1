$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$runtimePython = 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path $runtimePython)) { throw "Bundled Python runtime not found: $runtimePython" }
$venv = Join-Path $root '.venv'
if (-not (Test-Path $venv)) { & $runtimePython -m venv $venv }
$pip = Join-Path $venv 'Scripts\pip.exe'
& $pip install --upgrade pip
& $pip install -r (Join-Path $root 'requirements-dev.txt')
Write-Host 'Development dependencies installed.'

