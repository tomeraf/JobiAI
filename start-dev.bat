@echo off
echo ========================================
echo    JobiAI Development Environment
echo ========================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running. Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting for Docker to start...
    timeout /t 30 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Docker failed to start. Please start it manually.
        pause
        exit /b 1
    )
)

:: Start PostgreSQL in Docker
echo [1/3] Starting PostgreSQL database...
cd /d %~dp0
docker-compose up -d db
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start PostgreSQL
    pause
    exit /b 1
)

:: Wait for PostgreSQL to be ready
echo Waiting for PostgreSQL to be ready...
timeout /t 5 /nobreak >nul

:: Start Backend
echo.
echo [2/3] Starting Backend (FastAPI)...
cd /d %~dp0backend
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
start "JobiAI Backend" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Start Frontend
echo.
echo [3/3] Starting Frontend (Vite)...
cd /d %~dp0frontend
start "JobiAI Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo    All services started!
echo ========================================
echo.
echo    Frontend: http://localhost:5173
echo    Backend:  http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo    (This window will close in 3 seconds)
timeout /t 3 /nobreak >nul
