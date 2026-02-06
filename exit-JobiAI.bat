@echo off
:: Exit JobiAI - Force stop all background processes
:: Note: JobiAI normally auto-exits when you close the browser tab

echo Stopping JobiAI...

:: Find and kill uvicorn (backend)
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| find "PID:"') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | find "uvicorn" >nul && taskkill /F /PID %%a >nul 2>&1
)

:: Find and kill node (frontend)
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq node.exe" /FO LIST ^| find "PID:"') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: Also try by port
for /f "tokens=5" %%a in ('netstat -ano ^| find ":9000" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| find ":5173" ^| find "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo JobiAI stopped.
pause
