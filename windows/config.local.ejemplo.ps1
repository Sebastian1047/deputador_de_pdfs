# Copie este EJEMPLO solo al directorio PRIVADO indicado por Instalar-PC.ps1.
# Este archivo de ejemplo NO contiene credenciales reales.
# El instalador sustituye automaticamente __CLAVE_ALEATORIA_AUTOGENERADA__.
$env:MAIL_PROVIDER = "gmail"
$env:TABLE_PROVIDER = "google_sheets"
$env:GOOGLE_SHEETS_TEMPLATE = "creditos_sole"
$env:GOOGLE_SHEET_TAB = "DETALLE DEVOLUCION"
$env:GOOGLE_SHEETS_HISTORICAL_YEAR = "2026"
$env:GOOGLE_SPREADSHEET_ID = "__ID_DE_HOJA_DE_PRUEBAS__"

# Credenciales privadas: no compartir, no copiar en GitHub ni chats.
$env:GMAIL_EXPECTED_EMAIL = "__CUENTA_GMAIL_AUTORIZADA__"
$env:GMAIL_OAUTH_CLIENT_FILE = Join-Path $PSScriptRoot "oauth_web.json"
$env:GMAIL_TOKEN_FILE = Join-Path $PSScriptRoot "token_gmail.json"
$env:GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE = Join-Path $PSScriptRoot "sheets_service_account.json"

# Para la PRUEBA LOCAL, navegador y Python se ejecutan en el MISMO PC.
# Esta URI debe registrarse adicionalmente en Google Cloud -> Cliente OAuth Web.
$env:GMAIL_REDIRECT_URI = "http://localhost:8080/oauth/google/callback"
$env:WEB_HOST = "127.0.0.1"
$env:WEB_PORT = "8080"
$env:WEB_SECURE_COOKIES = "false"   # SOLO localhost: no usar HTTP en LAN.

# Clave privada generada por el instalador y hash de su contrasena.
$env:WEB_SECRET_KEY = "__CLAVE_ALEATORIA_AUTOGENERADA__"
$env:WEB_ADMIN_USER = "administrador"
# Mantenga COMILLAS SIMPLES al pegar el hash: contiene caracteres $.
$env:WEB_PASSWORD_HASH = '__HASH_GENERADO_EN_SU_PC__'
