@echo off
setlocal enabledelayedexpansion
echo ========================================
echo    Stopping JobiAI Services
echo ========================================
echo.

:: Kill Backend (Python/uvicorn on port 9000)
echo [1/3] Stopping Backend (port 9000)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":9000" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%p >nul 2>&1
)
echo [OK] Backend stopped

:: Kill Frontend (Node/Vite on port 3000)
echo [2/3] Stopping Frontend (port 3000)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
    taskkill /F /T /PID %%p >nul 2>&1
)
echo [OK] Frontend stopped

:: Stop Docker containers (but keep them for faster restart)
echo [3/3] Stopping Docker containers...
docker stop jobiai-db >nul 2>&1
echo [OK] Docker containers stopped

echo.
echo ========================================
echo    All services stopped!
echo ========================================
echo.
endlocal
