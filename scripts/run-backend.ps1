# Keep Autorox backend running on port 8003 - auto-restarts if it crashes or stops.
# Usage: .\scripts\run-backend.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Port = 8003

Write-Host ""
Write-Host "Autorox backend watchdog - http://127.0.0.1:$Port"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

function Stop-PortListeners {
    param([int]$ListenPort)
    $conns = Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        $procId = $conn.OwningProcess
        if ($procId -and $procId -ne $PID) {
            Write-Host "Stopping process $procId on port $ListenPort..."
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

while ($true) {
    Stop-PortListeners -ListenPort $Port
    $started = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$started] Starting backend on port $Port..."
    Push-Location $Backend
    try {
        python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
        $exit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $stopped = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$stopped] Backend stopped (exit code $exit). Restarting in 5s..."
    Start-Sleep -Seconds 5
}
