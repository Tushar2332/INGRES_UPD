Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "          INGRES AI Assistant v2.0 (Review 2 Verified)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $rootDir

# Check frontend node_modules
if (-not (Test-Path "$rootDir\frontend\node_modules")) {
    Write-Host "[INFO] Installing frontend dependencies (one-time setup)..." -ForegroundColor Yellow
    Set-Location "$rootDir\frontend"
    npm install
    Set-Location $rootDir
} else {
    Write-Host "[OK] Frontend dependencies detected." -ForegroundColor Green
}

Write-Host ""
Write-Host "[INFO] Starting Backend API Server (Port 8000)..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\backend'; python -m uvicorn app.main:app --reload --port 8000"

Write-Host "[INFO] Starting Frontend React Application (Port 3000)..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\frontend'; npm start"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "Services started successfully!" -ForegroundColor Green
Write-Host "- Backend API:  http://localhost:8000" -ForegroundColor Gray
Write-Host "- Swagger Docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "- Frontend UI:  http://localhost:3000" -ForegroundColor Gray
Write-Host "======================================================================" -ForegroundColor Green
Read-Host -Prompt "Press Enter to exit this window..."
