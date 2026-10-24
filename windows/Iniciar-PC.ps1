#Requires -Version 5.1
# Solo inicio para el navegador del MISMO PC (localhost).
# No expone el servicio en la red; la publicacion LAN requiere IIS/HTTPS.
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
$private = Join-Path $env:LOCALAPPDATA "DepuradorPDF"
$config = Join-Path $private "config.local.ps1"
if (-not (Test-Path -LiteralPath $python)) { throw "Ejecute primero windows\Instalar-PC.ps1" }
if (-not (Test-Path -LiteralPath $config)) { throw "Falta configuracion privada: $config" }
. $config
$required = @("GOOGLE_SPREADSHEET_ID", "GMAIL_EXPECTED_EMAIL", "GMAIL_REDIRECT_URI",
              "WEB_SECRET_KEY", "WEB_PASSWORD_HASH", "GMAIL_OAUTH_CLIENT_FILE", "GMAIL_TOKEN_FILE")
foreach ($key in $required) {
    $value = [Environment]::GetEnvironmentVariable($key, "Process")
    if ([string]::IsNullOrWhiteSpace($value) -or $value.StartsWith("__")) {
        throw "Complete '$key' en su archivo config.local.ps1 privado antes de iniciar."
    }
}
if ($env:WEB_HOST -ne "127.0.0.1" -or $env:WEB_PORT -ne "8080" -or
    $env:WEB_SECURE_COOKIES -ne "false" -or
    $env:GMAIL_REDIRECT_URI -ne "http://localhost:8080/oauth/google/callback") {
    throw "Este iniciador es solo para localhost. Para LAN use un proxy HTTPS aprobado por TI."
}
if (-not (Test-Path -LiteralPath $env:GMAIL_OAUTH_CLIENT_FILE)) {
    throw "Falta el JSON OAuth WEB privado en la ruta configurada."
}
if ([string]::IsNullOrWhiteSpace($env:GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE) -or
    -not (Test-Path -LiteralPath $env:GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE)) {
    throw "Falta el JSON PRIVADO de la cuenta de servicio de Google Sheets."
}
$env:GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON = [System.IO.File]::ReadAllText(
    $env:GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE)
try {
    $json = $env:GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON | ConvertFrom-Json
    if ($json.type -ne "service_account") { throw "El JSON no es una cuenta de servicio." }
} catch {
    throw "No se pudo leer la cuenta de servicio de Google Sheets. Revise el JSON PRIVADO."
}
Push-Location $repo
try {
    Write-Host "Aplicacion local: http://localhost:8080/" -ForegroundColor Green
    Write-Host "Pulse Ctrl+C para detener. No exponga el puerto 8080 en su LAN." -ForegroundColor Yellow
    & $python -m depurador.web
    if ($LASTEXITCODE -ne 0) { throw "El servidor se cerro con error." }
} finally {
    Remove-Item Env:GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON -ErrorAction SilentlyContinue
    Pop-Location
}
