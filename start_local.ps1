# start_local.ps1
# This script starts the Industrial Knowledge Platform locally without Docker

Write-Host "Starting Industrial Knowledge Platform without Docker..." -ForegroundColor Cyan

$PythonExec = "python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $PythonExec = ".\.venv\Scripts\python.exe"
    Write-Host "Using Virtual Environment Python at $PythonExec" -ForegroundColor Gray
}

# 1. Start the MCP Server
Write-Host "Starting Unified MCP Server..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath $PythonExec -ArgumentList "mcp-server/server.py"

Start-Sleep -Seconds 3

# 2. Start the Orchestrator API
Write-Host "Starting Orchestrator API (Port 8000)..." -ForegroundColor Yellow
Set-Location -Path "orchestrator"
$OrchPythonExec = if (Test-Path "..\.venv\Scripts\python.exe") { "..\.venv\Scripts\python.exe" } else { "python" }
Start-Process -NoNewWindow -FilePath $OrchPythonExec -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
Set-Location -Path ".."

Start-Sleep -Seconds 3

# 3. Start the API Gateway (which also serves the static frontend)
Write-Host "Starting API Gateway & Frontend (Port 8100)..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath $PythonExec -ArgumentList "-m uvicorn api_gateway.baseline.app.main:app --host 0.0.0.0 --port 8100 --reload"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "✅ All services started in the background!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host "Gateway & UI:       http://localhost:8100"
Write-Host "Orchestrator API:   http://localhost:8000"
Write-Host "MCP AI Server:      Runs as a FastMCP subprocess"
Write-Host ""
Write-Host "To stop the servers, close this terminal or press Ctrl+C." -ForegroundColor Gray
