$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot 'BackEnd')
try {
    if (!(Test-Path '.env')) { throw 'Configura BackEnd/.env siguiendo README.md.' }
    if (!(Test-Path '.venv/Scripts/python.exe')) { throw 'Ejecuta setup-local.ps1 primero.' }
    & .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8015 --reload
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar el backend.' }
} finally { Pop-Location }
