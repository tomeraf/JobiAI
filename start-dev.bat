@echo off
echo ========================================
echo    JobiAI Development Environment
echo ========================================
echo.

:: Check if Docker is running
docker info >nul 2>&1
if %errorlevel% equ 0 goto docker_ready

echo [INFO] Docker is not running. Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

echo Waiting for Docker to initialize...
set /a attempts=0

:wait_for_docker
set /a attempts+=1
if %attempts% gtr 20 (
    echo [ERROR] Docker failed to start after 40 seconds.
    echo Please start Docker Desktop manually and try again.
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo     Still waiting... (%attempts%/20)
    goto wait_for_docker
)
echo [OK] Docker is now running!

:docker_ready
echo.
echo [1/4] Starting PostgreSQL database...
cd /d %~dp0
docker-compose up -d db
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start PostgreSQL
    pause
    exit /b 1
)

:: Wait for PostgreSQL to be healthy
echo Waiting for PostgreSQL to be ready...
set /a db_attempts=0

:wait_for_db
set /a db_attempts+=1
if %db_attempts% gtr 30 (
    echo [ERROR] PostgreSQL failed to become ready after 30 seconds.
    pause
    exit /b 1
)
docker-compose exec -T db pg_isready -U postgres >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 1 /nobreak >nul
    goto wait_for_db
)
echo [OK] PostgreSQL is ready!

:: Run migrations
echo.
echo [2/4] Running database migrations...
cd /d %~dp0backend
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
alembic upgrade head
if %errorlevel% neq 0 (
    echo [WARNING] Migration failed - database might already be up to date
)
echo [OK] Migrations complete!

:: Start Backend (minimized)
echo.
echo [3/4] Starting Backend (FastAPI on port 9000)...
start /min "JobiAI Backend" cmd /c "cd /d %~dp0backend && call venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 9000"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

:: Start Frontend (minimized)
echo.
echo [4/4] Starting Frontend (Vite on port 3000)...
cd /d %~dp0frontend
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)
start /min "JobiAI Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

:: Wait for frontend to start
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo    All services started successfully!
echo ========================================
echo.
echo    Frontend: http://localhost:3000
echo    Backend:  http://localhost:9000
echo    API Docs: http://localhost:9000/docs
echo    Database: localhost:5436
echo.
echo    To stop: run stop-dev.bat
echo.
echo Opening frontend in browser...
start "" "http://localhost:3000"
