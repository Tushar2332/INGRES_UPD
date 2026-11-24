@echo off
title INGRES AI Assistant - Unified Launcher
color 0B

echo ======================================================================
echo           INGRES AI Assistant v2.0 (Review 2 Verified)
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Frontend Dependencies...
if not exist "frontend\node_modules" (
    echo [INFO] 'node_modules' not found. Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
) else (
    echo [OK] Frontend dependencies detected.
)

echo.
echo [2/3] Starting Backend API Server (Port 8000)...
start "INGRES Backend (FastAPI)" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --reload --port 8000"

echo.
echo [3/3] Starting Frontend React Application (Port 3000)...
start "INGRES Frontend (React)" cmd /k "cd /d "%~dp0frontend" && npm start"

echo.
echo ======================================================================
echo INGRES AI Assistant services have been launched!
echo - Backend API:  http://localhost:8000
echo - Swagger Docs: http://localhost:8000/docs
echo - Frontend UI:  http://localhost:3000
echo ======================================================================
echo Keep the backend and frontend terminal windows open while using the app.
echo You may close this launcher window at any time.
echo.
pause
