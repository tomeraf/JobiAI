@echo off
echo ========================================
echo    JobiAI Port Detection
echo ========================================
echo.

cd /d %~dp0backend
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
echo Detecting available ports...
python -m app.utils.port_finder

if %errorlevel% neq 0 (
    echo [ERROR] Port detection failed
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Port configuration created at .ports.json
echo.

type ..\\.ports.json

echo.
pause
