@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m app.main --generate-images --resume %*
set "result=%errorlevel%"
echo Exit code: %result%
pause
exit /b %result%
