$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$node = 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$vite = Join-Path $root 'apps\web-console\node_modules\vite\bin\vite.js'
if (-not (Test-Path $node)) { throw "Bundled Node runtime not found: $node" }
if (-not (Test-Path $vite)) { throw 'Install the web-console dependencies first.' }
& $node $vite --host 127.0.0.1

