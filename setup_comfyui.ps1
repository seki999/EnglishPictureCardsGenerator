$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File '.\setup.ps1'
    if ($LASTEXITCODE -ne 0) { throw 'Project setup failed.' }
}
New-Item -ItemType Directory -Path '.runtime' -Force | Out-Null
if (-not (Test-Path -LiteralPath '.runtime\ComfyUI\main.py')) {
    git clone --depth 1 --branch v0.39.0 https://github.com/Comfy-Org/ComfyUI.git .runtime/ComfyUI
    if ($LASTEXITCODE -ne 0) { throw 'ComfyUI download failed.' }
}
if (-not (Test-Path -LiteralPath '.runtime\comfy-venv\Scripts\python.exe')) {
    & '.\.venv\Scripts\python.exe' -m venv .runtime/comfy-venv
    if ($LASTEXITCODE -ne 0) { throw 'ComfyUI venv creation failed.' }
}
& '.\.runtime\comfy-venv\Scripts\python.exe' -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed.' }
& '.\.runtime\comfy-venv\Scripts\python.exe' -m pip install -r .runtime/ComfyUI/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'ComfyUI dependencies installation failed.' }
& '.\.venv\Scripts\python.exe' scripts/download_sdxl.py
if ($LASTEXITCODE -ne 0) { throw 'Model download/verification failed. Rerun to resume.' }
& '.\.venv\Scripts\python.exe' scripts/download_lightning.py
if ($LASTEXITCODE -ne 0) { throw 'Lightning LoRA download/verification failed. Rerun to resume.' }
Write-Host 'ComfyUI and SDXL ready. Run run_local_cpu.bat.'
