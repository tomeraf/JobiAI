@echo off
:: JobiAI Background Launcher
:: Starts backend and frontend as hidden processes with SQLite database
:: No Docker required!

setlocal

:: Set paths
set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "DATA_DIR=%LOCALAPPDATA%\JobiAI"

:: Create data directory
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"

:: Set SQLite database (no Docker needed)
set "DATABASE_URL=sqlite+aiosqlite:///%DATA_DIR%\jobiai.db"

:: Kill any existing processes
taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq JobiAI*" >nul 2>&1
taskkill /F /IM "node.exe" /FI "WINDOWTITLE eq JobiAI*" >nul 2>&1

:: Start backend (hidden)
start /B /MIN "" pythonw -m uvicorn app.main:app --host 127.0.0.1 --port 9000 --log-level warning

:: Wait for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend (hidden)
cd /d "%FRONTEND_DIR%"
start /B /MIN "" npm run dev -- --port 5173

:: Wait for frontend to start
timeout /t 3 /nobreak >nul

:: Open browser
start http://localhost:5173

echo JobiAI started in background!
echo Backend: http://localhost:9000
echo Frontend: http://localhost:5173
echo.
echo Close this window - the app will keep running.
echo To stop: Use Task Manager or run stop-background.bat
