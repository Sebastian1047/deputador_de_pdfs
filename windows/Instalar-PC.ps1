#Requires -Version 5.1
# Instala únicamente el servidor web Python en el equipo Windows actual.
# Nunca descarga ni solicita secretos y no abre puertos en el firewall.
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
Push-Location $repo
try {
    Write-Host "Comprobando Python 3.12..." -ForegroundColor Cyan
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Instale Python 3.12 y habilite el comando py." }
    & $python -m pip install -r requirements-web.txt
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Las pruebas fallaron: no inicie el servidor." }

    $private = Join-Path $env:LOCALAPPDATA "DepuradorPDF"
    New-Item -ItemType Directory -Path $private -Force | Out-Null
    $config = Join-Path $private "config.local.ps1"
    if (-not (Test-Path -LiteralPath $config)) {
        $example = Join-Path $repo "windows\config.local.ejemplo.ps1"
        $content = [System.IO.File]::ReadAllText($example)
        $bytes = New-Object byte[] 48
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $key = [Convert]::ToBase64String($bytes)
        $content = $content.Replace("__CLAVE_ALEATORIA_AUTOGENERADA__", $key)
        [System.IO.File]::WriteAllText($config, $content, [System.Text.UTF8Encoding]::new($false))
        Write-Host "Plantilla PRIVADA creada en: $config" -ForegroundColor Green
    } else {
        Write-Host "Se conserva la configuracion privada existente: $config" -ForegroundColor Yellow
    }
    Write-Host "Instalacion comprobada. Antes de iniciar, complete su configuracion privada siguiendo docs/INSTALACION_PC_GMAIL_SHEETS.md" -ForegroundColor Green
    Write-Host "Para generar el hash de la contrasena: .\.venv\Scripts\python.exe -m depurador.web --hash-password"
} finally {
    Pop-Location
}
