# Start Autorox frontend + backend together (local dev).
# Usage: .\scripts\start-app.ps1
# Or double-click: scripts\start-app.cmd

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$BackendPort = 8003
$FrontendPort = 5173
$AppUrl = "http://127.0.0.1:$FrontendPort"

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

Write-Host ""
Write-Host "Autorox AI Command Center"
Write-Host "  App:  $AppUrl"
Write-Host "  API:  http://127.0.0.1:$BackendPort"
Write-Host ""
Write-Host "Starting backend and frontend in separate windows..."
Write-Host "Close those windows (or Ctrl+C in each) to stop the app."
Write-Host ""

Stop-PortListeners -ListenPort $BackendPort
Stop-PortListeners -ListenPort $FrontendPort

$backendCmd = "title Autorox Backend && cd /d `"$Backend`" && echo. && echo Autorox Backend - http://127.0.0.1:$BackendPort && echo Press Ctrl+C to stop. && echo. && python -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --reload"
Start-Process cmd -ArgumentList @("/k", $backendCmd)

Start-Sleep -Seconds 1

$frontendCmd = "title Autorox Frontend && cd /d `"$Frontend`" && echo. && echo Autorox Frontend - $AppUrl && echo Press Ctrl+C to stop. && echo. && npm run dev"
Start-Process cmd -ArgumentList @("/k", $frontendCmd)

Write-Host "Waiting for services to start..."
Start-Sleep -Seconds 5

Start-Process $AppUrl
Write-Host "Opened $AppUrl in your browser."
Write-Host ""
Write-Host "You can close this launcher window. Backend and frontend keep running."
