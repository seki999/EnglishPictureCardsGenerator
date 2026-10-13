$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.runtime\comfy-venv\Scripts\python.exe'
$comfyDirectory = Join-Path $PSScriptRoot '.runtime\ComfyUI'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'ComfyUI environment missing. Run setup_comfyui.ps1 first.'
}
try {
    $null = Invoke-RestMethod 'http://127.0.0.1:8188/system_stats' -TimeoutSec 2
    Write-Host 'ComfyUI is already running on port 8188.'
    exit 0
} catch {}
New-Item -ItemType Directory -Path 'logs' -Force | Out-Null
$env:PYTHONUTF8 = '1'
$env:OMP_NUM_THREADS = '8'
$env:MKL_NUM_THREADS = '8'
$process = Start-Process -FilePath $pythonPath -ArgumentList @('main.py', '--cpu', '--listen', '127.0.0.1', '--port', '8188', '--disable-all-custom-nodes', '--offline', '--disable-auto-launch') -WorkingDirectory $comfyDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'logs\comfyui.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'logs\comfyui.stderr.log') -PassThru
$process.Id | Set-Content -LiteralPath '.runtime\comfyui.pid'
Write-Host "Starting ComfyUI CPU mode (PID $($process.Id))..."
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    if ($process.HasExited) { throw 'ComfyUI exited. Inspect logs/comfyui.stderr.log.' }
    try {
        $null = Invoke-RestMethod 'http://127.0.0.1:8188/system_stats' -TimeoutSec 2
        Write-Host 'ComfyUI ready: http://127.0.0.1:8188'
        exit 0
    } catch {}
    Start-Sleep -Seconds 2
}
throw 'ComfyUI startup timed out. Inspect logs/comfyui.stderr.log.'
