param(
    [switch]$SkipDependencyCheck
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run scripts/bootstrap.ps1 first.' }
$envFile = Join-Path $root '.env'
if (Test-Path $envFile) {
    Get-Content -LiteralPath $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$' -and $matches[2] -ne '') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
}
if (-not $env:POSTGRES_PASSWORD) { throw 'Set POSTGRES_PASSWORD in .env before starting services.' }
$env:DATABASE_URL = "postgresql+asyncpg://$($env:POSTGRES_USER ?? 'industrial'):$($env:POSTGRES_PASSWORD)@127.0.0.1:5432/$($env:POSTGRES_DB ?? 'industrial_ai')"
$env:AUTO_CREATE_SCHEMA = 'true'
$env:KAFKA_BOOTSTRAP_SERVERS = '127.0.0.1:19092'
$env:REDIS_URL = 'redis://127.0.0.1:6379/0'
$env:TEMPORAL_ADDRESS = '127.0.0.1:7233'

if (-not $SkipDependencyCheck) {
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ((Test-NetConnection -ComputerName 127.0.0.1 -Port 5432 -InformationLevel Quiet) -and
            (Test-NetConnection -ComputerName 127.0.0.1 -Port 6379 -InformationLevel Quiet)) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'PostgreSQL/Redis are not ready. Start infra/docker/compose.dev.yml first, or rerun with -SkipDependencyCheck.' }
}

Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory (Join-Path $root 'services\platform-gateway')
Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001' -WorkingDirectory (Join-Path $root 'services\agent-runtime')
Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8002' -WorkingDirectory (Join-Path $root 'services\tool-gateway')
Write-Host 'Started platform-gateway :8000, agent-runtime :8001, tool-gateway :8002'

