Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".\.venv\Scripts\python.exe")) { throw "Virtual environment not found. Run scripts\setup_windows.ps1 first." }
Push-Location backend
try { & ..\.venv\Scripts\python.exe -m alembic upgrade head; & ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload }
finally { Pop-Location }
