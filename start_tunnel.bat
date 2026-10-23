@echo off
title Chartbot Local & Cloudflare Tunnel Launcher
echo ======================================================
echo    Starting Chartbot Server & Cloudflare Tunnel
echo ======================================================
echo.
echo [1/2] Launching FastAPI Backend on http://127.0.0.1:8000...
start "Chartbot Backend (Port 8000)" cmd /k "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [2/2] Waiting for server to initialize...
timeout /t 3 /nobreak >nul

echo.
echo Launching Cloudflare Tunnel...
echo Your public live HTTPS link will appear below:
echo ======================================================
.\cloudflared.exe tunnel --url http://127.0.0.1:8000
