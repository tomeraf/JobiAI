@echo off
setlocal enabledelayedexpansion
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
set attempts=0

:wait_for_docker
set /a attempts+=1
if %attempts% gtr 30 (
    echo [ERROR] Docker failed to start after 90 seconds.
    pause
    exit /b 1
)
timeout /t 3 /nobreak >nul
docker info >nul 2>&1
set docker_result=!errorlevel!
if !docker_result! equ 0 goto docker_is_ready
echo     Still waiting... (!attempts!/30)
goto wait_for_docker

:docker_is_ready
echo [OK] Docker is now running!

:: Stop any auto-started containers
echo Stopping other containers...
for /f "tokens=*" %%i in ('docker ps -q') do docker stop %%i >nul 2>&1

:docker_ready
echo.

:: Setup Python environment first (needed for port detection)
echo [1/6] Setting up Python environment...
cd /d %~dp0backend
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q 2>nul
pip install -r requirements.txt -q 2>nul

:: Detect available ports (including database port)
echo.
echo [2/6] Detecting available ports...
python -m app.utils.port_finder
if %errorlevel% neq 0 (
    echo [ERROR] Port detection failed
    pause
    exit /b 1
)

:: Read port configuration
cd /d %~dp0
for /f "delims=" %%i in ('powershell -Command "(Get-Content .ports.json | ConvertFrom-Json).backend_port"') do set BACKEND_PORT=%%i
for /f "delims=" %%i in ('powershell -Command "(Get-Content .ports.json | ConvertFrom-Json).frontend_port"') do set FRONTEND_PORT=%%i
for /f "delims=" %%i in ('powershell -Command "(Get-Content .ports.json | ConvertFrom-Json).database_port"') do set DATABASE_PORT=%%i

echo [OK] Ports detected:
echo     Backend:  %BACKEND_PORT%
echo     Frontend: %FRONTEND_PORT%
echo     Database: %DATABASE_PORT%

:: Create dynamic docker-compose override with the detected port
echo.
echo [3/6] Creating docker-compose override...
(
echo services:
echo   db:
echo     ports:
echo       - "%DATABASE_PORT%:5432"
) > docker-compose.override.yml
echo [OK] docker-compose.override.yml created with port %DATABASE_PORT%

:: Start PostgreSQL with dynamic port
echo.
echo [4/6] Starting PostgreSQL database on port %DATABASE_PORT%...

:: Stop and remove existing container (it might be on wrong port)
docker stop jobiai-db >nul 2>&1
docker rm jobiai-db >nul 2>&1

:: Start with override
docker-compose up -d db
if !errorlevel! neq 0 (
    echo [ERROR] Failed to start PostgreSQL
    pause
    exit /b 1
)

:: Wait for PostgreSQL to be healthy
echo Waiting for PostgreSQL to be ready...
set db_attempts=0

:wait_for_db
set /a db_attempts+=1
if !db_attempts! gtr 30 (
    echo [ERROR] PostgreSQL failed to become ready after 30 seconds.
    pause
    exit /b 1
)
docker exec jobiai-db pg_isready -U postgres >nul 2>&1
if !errorlevel! equ 0 goto db_ready_ok
timeout /t 1 /nobreak >nul
goto wait_for_db

:db_ready_ok
echo [OK] PostgreSQL is ready on port %DATABASE_PORT%!

:: Run migrations with dynamic DATABASE_URL
echo.
echo [5/6] Running database migrations...
cd /d %~dp0backend
set "DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:%DATABASE_PORT%/jobiai"
alembic upgrade head
if %errorlevel% neq 0 (
    echo [WARNING] Migration failed - database might already be up to date
)
echo [OK] Migrations complete!

:: Start Backend with dynamic DATABASE_URL
echo.
echo [6/6] Starting services...
echo     Starting Backend on port %BACKEND_PORT%...
set "BACKEND_DB_URL=postgresql+asyncpg://postgres:postgres@localhost:%DATABASE_PORT%/jobiai"
start /min "JobiAI Backend" cmd /c "cd /d %~dp0backend && call venv\Scripts\activate.bat && set DATABASE_URL=%BACKEND_DB_URL% && uvicorn app.main:app --reload --host 0.0.0.0 --port %BACKEND_PORT%"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

:: Install frontend dependencies if needed
cd /d %~dp0frontend
if not exist "node_modules" (
    echo     Installing frontend dependencies...
    call npm install
)

:: Start Frontend (minimized)
echo     Starting Frontend on port %FRONTEND_PORT%...
start /min "JobiAI Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

:: Wait for frontend to start
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo    All services started successfully!
echo ========================================
echo.
echo    Frontend: http://localhost:%FRONTEND_PORT%
echo    Backend:  http://localhost:%BACKEND_PORT%
echo    API Docs: http://localhost:%BACKEND_PORT%/docs
echo    Database: localhost:%DATABASE_PORT%
echo.
echo    Port config saved to: .ports.json
echo    To stop: run stop-dev.bat
echo.
echo Opening frontend in browser...
start "" "http://localhost:%FRONTEND_PORT%"
