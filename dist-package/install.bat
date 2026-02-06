@echo off
echo ========================================
echo   JobiAI Installation
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed!
    echo Please install Python 3.11 or later from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
cd /d "%~dp0backend"
python -m venv venv
if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

echo [2/4] Installing Python packages...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages
    pause
    exit /b 1
)

echo [3/4] Installing Chromium browser for automation...
playwright install chromium
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Chromium
    pause
    exit /b 1
)

echo [4/4] Creating data directory...
if not exist "%LOCALAPPDATA%\JobiAI" mkdir "%LOCALAPPDATA%\JobiAI"

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo To start JobiAI, double-click: JobiAI.vbs
echo.
echo First time users: After launching, go to Settings
echo and login to LinkedIn.
echo.
pause
