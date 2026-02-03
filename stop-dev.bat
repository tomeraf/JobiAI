@echo off
echo ========================================
echo    Stopping JobiAI Services
echo ========================================
echo.

:: Use default ports (no PowerShell needed)
set BACKEND_PORT=9000
set FRONTEND_PORT=5173

:: Kill Backend
echo [1/3] Stopping Backend (port %BACKEND_PORT%)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%BACKEND_PORT%" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /T /PID %%p >nul 2>&1
)
echo [OK] Backend stopped

:: Kill Frontend
echo [2/3] Stopping Frontend (port %FRONTEND_PORT%)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%FRONTEND_PORT%" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /T /PID %%p >nul 2>&1
)
echo [OK] Frontend stopped

:: Stop Docker containers (use timeout to not wait forever)
echo [3/3] Stopping Docker containers...
docker stop jobiai-db -t 2 >nul 2>&1
echo [OK] Docker containers stopped

echo.
echo ========================================
echo    All services stopped!
echo ========================================
