@echo off
setlocal enabledelayedexpansion
echo ========================================
echo    Stopping JobiAI Services
echo ========================================
echo.

:: Read ports from config file (or use defaults)
set BACKEND_PORT=9000
set FRONTEND_PORT=5173
set DATABASE_PORT=5436

if exist ".ports.json" (
    for /f "delims=" %%i in ('powershell -Command "(Get-Content .ports.json | ConvertFrom-Json).backend_port"') do set BACKEND_PORT=%%i
    for /f "delims=" %%i in ('powershell -Command "(Get-Content .ports.json | ConvertFrom-Json).frontend_port"') do set FRONTEND_PORT=%%i
    for /f "delims=" %%i in ('powershell -Command "(Get-Content .ports.json | ConvertFrom-Json).database_port"') do set DATABASE_PORT=%%i
    echo [INFO] Using ports from .ports.json
) else (
    echo [INFO] No .ports.json found, using default ports
)

echo        Backend:  !BACKEND_PORT!
echo        Frontend: !FRONTEND_PORT!
echo        Database: !DATABASE_PORT!
echo.

:: Kill Backend
echo [1/3] Stopping Backend (port !BACKEND_PORT!)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":!BACKEND_PORT!" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%p >nul 2>&1
)
echo [OK] Backend stopped

:: Kill Frontend
echo [2/3] Stopping Frontend (port !FRONTEND_PORT!)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":!FRONTEND_PORT!" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%p >nul 2>&1
)
echo [OK] Frontend stopped

:: Stop Docker containers
echo [3/3] Stopping Docker containers...
docker stop jobiai-db >nul 2>&1
echo [OK] Docker containers stopped

echo.
echo ========================================
echo    All services stopped!
echo ========================================
echo.
endlocal
