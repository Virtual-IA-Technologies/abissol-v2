$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot 'FrontEnd/frontend-app')
try {
    & npm.cmd run dev
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar el frontend.' }
} finally { Pop-Location }
