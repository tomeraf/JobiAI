@echo off
echo Stopping JobiAI...

:: Kill Python/uvicorn processes on port 9000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :9000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)

echo JobiAI stopped.
timeout /t 2
