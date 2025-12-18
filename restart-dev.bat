@echo off
echo Restarting JobiAI...

REM Run stop-dev
call "%~dp0stop-dev.bat"

REM Small delay to ensure everything is stopped
timeout /t 2 /nobreak >nul

REM Run start-dev
call "%~dp0start-dev.bat"
