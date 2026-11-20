Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw "Python launcher (py) was not found. Install Python 3.11 first." }
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Write-Host "Environment ready. Activate with .\.venv\Scripts\Activate.ps1"
