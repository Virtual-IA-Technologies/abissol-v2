$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot 'BackEnd')
try {
    if (!(Test-Path '.venv/Scripts/python.exe')) {
        & py -3.14 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Se requiere Python 3.14.' }
    }
    & .\.venv\Scripts\python.exe -m pip install -r requirements-core.txt
    if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación Python.' }
    if (!(Test-Path '.env')) {
        Copy-Item '.env.example' '.env'
        & .\.venv\Scripts\python.exe -c "from pathlib import Path; import secrets; p=Path('.env'); p.write_text(p.read_text().replace('SECRET_KEY=', 'SECRET_KEY='+secrets.token_urlsafe(48)), encoding='utf-8')"
        if ($LASTEXITCODE -ne 0) { throw 'Falló la generación de configuración.' }
    }
} finally { Pop-Location }
Push-Location (Join-Path $PSScriptRoot 'FrontEnd/frontend-app')
try {
    & npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación React.' }
} finally { Pop-Location }
Write-Host 'Dependencias listas. Configura MariaDB en BackEnd/.env y sigue los pasos de migración y cuenta inicial del README.'
