@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_comfyui.ps1"
if errorlevel 1 (
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app.main --config config/config.cpu.yaml --generate-images --resume %*
set "result=%errorlevel%"
echo Exit code: %result%
pause
exit /b %result%
