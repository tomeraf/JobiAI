@echo off
echo ============================================
echo JobiAI Desktop App Build Script
echo ============================================
echo.

cd /d %~dp0

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

:: Step 1: Create icon if not exists
echo [1/5] Checking icons...
if not exist "assets\icon.ico" (
    echo Creating icons...
    cd assets
    python create_icon.py
    cd ..
) else (
    echo Icons already exist.
)
echo.

:: Step 2: Install backend dependencies
echo [2/5] Installing backend dependencies...
cd backend
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
cd ..
echo.

:: Step 3: Build frontend
echo [3/5] Building frontend...
cd frontend
call npm install --silent
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed
    pause
    exit /b 1
)
cd ..
echo.

:: Step 4: Run PyInstaller
echo [4/5] Building executable...
call backend\venv\Scripts\activate.bat
set PYTHONPATH=%cd%\backend
pyinstaller jobiai.spec --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed
    pause
    exit /b 1
)
echo.

:: Step 5: Done
echo [5/5] Build complete!
echo.
echo ============================================
echo Output: dist\JobiAI.exe
echo ============================================
echo.
echo NOTE: On first run, JobiAI will download the browser
echo       (Playwright Chromium) which takes ~180MB.
echo.

dir dist\JobiAI.exe

pause
