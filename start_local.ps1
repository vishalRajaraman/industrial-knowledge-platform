# start_local.ps1
# This script starts the Industrial Knowledge Platform locally without Docker

Write-Host "Starting Industrial Knowledge Platform without Docker..." -ForegroundColor Cyan

# 1. Start the MCP Server (Runs on port 8080 by default in server.py, but FastAPI default is 8000)
# Wait, server.py uses fastmcp.run(). Let's run it.
Write-Host "Starting Unified MCP Server..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "mcp-server/server.py"

Start-Sleep -Seconds 3

# 2. Start the Orchestrator API
Write-Host "Starting Orchestrator API (Port 8000)..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m uvicorn orchestrator.main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Seconds 3

# 3. Start the API Gateway (which also serves the static frontend)
Write-Host "Starting API Gateway & Frontend (Port 8100)..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m uvicorn api_gateway.baseline.app.main:app --host 0.0.0.0 --port 8100 --reload"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "✅ All services started in the background!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host "Gateway & UI:       http://localhost:8100"
Write-Host "Orchestrator API:   http://localhost:8000"
Write-Host "MCP AI Server:      Runs as a FastMCP subprocess"
Write-Host ""
Write-Host "To stop the servers, close this terminal or press Ctrl+C." -ForegroundColor Gray
