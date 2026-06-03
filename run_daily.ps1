# Wrapper invoked by the scheduled task for daily generation.
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Environment variables to keep XTTS (voice clone) stable
$env:COQUI_TOS_AGREED = "1"
$env:OMP_NUM_THREADS = "2"
$env:PYTHONIOENCODING = "utf-8"

# Use the venv python if present
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) { $python = $venvPython } else { $python = "python" }

# Keep a log
$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir ("run-" + (Get-Date -Format "yyyyMMdd") + ".log")

"=== $(Get-Date -Format s) start ===" | Out-File -FilePath $log -Append -Encoding utf8
& $python -X utf8 -u -m src.main *>> $log
"=== $(Get-Date -Format s) end (exit $LASTEXITCODE) ===" | Out-File -FilePath $log -Append -Encoding utf8
