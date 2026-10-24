# Instalación web provisional en PC Windows — Gmail + Google Sheets

## Objetivo y alcance

Este procedimiento deja funcionando la MISMA aplicación Python/Flask/Waitress que utiliza Render, pero ejecutándose en un PC Windows, antes de pasar a Windows Server. El destino SIGUE siendo una hoja nativa de Google Sheets almacenada en Google Drive. NO se guarda el Excel en el disco local, NO se sustituyen los proveedores por Microsoft y NO se modifican el extractor de PDF, el control de duplicados, la consulta mensual ni la generación del PNG.

La primera etapa es una prueba segura en http://localhost:8080/ desde el navegador del MISMO PC. Las personas de otros equipos todavía NO tienen acceso: para usarse en LAN o desde móviles, TI debe publicar una dirección HTTPS mediante un proxy (por ejemplo, IIS), con control de acceso y certificado adecuado.

## 1. Requisitos

- PC con Windows 10/11 autorizado para ejecutar Python y la aplicación.
- Python 3.12, Git y PowerShell 5.1 o posterior.
- Acceso saliente a Google APIs (Gmail y Sheets) e inicio de sesión de Google.
- Credenciales OAuth de tipo **Aplicación web** del proyecto Google Cloud existente.
- Archivo JSON PRIVADO de la cuenta de servicio que ya tiene permiso Editor en una COPIA de Google Sheets, no en el libro original.
- Usuario/contraseña definidos para el panel web. No utilizar contraseñas compartidas.
- Respaldar primero el contenido de la hoja de pruebas y **no** procesar simultáneamente el mismo correo desde Render y desde su PC.

Si TI no autoriza ejecutar Python en su estación de trabajo, NO omitir controles de seguridad; solicitar un equipo o VM de pruebas aprobado.

## 2. Obtener el proyecto

Abra PowerShell y clone el repositorio, sin guardar secretos en él:

    git clone https://github.com/Sebastian1047/deputador_de_pdfs.git
    cd deputador_de_pdfs

Ejecute el instalador incluido en la versión local:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\Instalar-PC.ps1

El instalador crea .venv, instala requirements-web.txt, ejecuta pytest y coloca una configuración de ejemplo FUERA del repositorio, en:

    %LOCALAPPDATA%\DepuradorPDF\config.local.ps1

Si el archivo privado ya existe, NO lo sobrescribe. El instalador genera una WEB_SECRET_KEY aleatoria de uso local. El hecho de instalar no autoriza Gmail ni conecta Sheets automáticamente.

## 3. Proteger y colocar las credenciales privadas

En la MISMA carpeta %LOCALAPPDATA%\DepuradorPDF, con permisos limitados a su cuenta Windows, coloque:

    oauth_web.json                  (cliente OAuth WEB descargado de Google Cloud)
    sheets_service_account.json     (clave JSON de cuenta de servicio Sheets)
    token_gmail.json                (se crea tras autorizar Gmail, NO copiar de GitHub)

Abra la configuración privada config.local.ps1 y complete sin compartir su contenido:

- GOOGLE_SPREADSHEET_ID: ID de la COPIA de Google Sheets, no el original.
- GMAIL_EXPECTED_EMAIL: la única cuenta Gmail autorizada a leer.
- WEB_PASSWORD_HASH: hash generado con el comando indicado abajo.
- Compruebe las rutas a los dos JSON y la pestaña DETALLE DEVOLUCION.
- Mantenga en la prueba inicial WEB_HOST=127.0.0.1, WEB_PORT=8080, WEB_SECURE_COOKIES=false y GMAIL_REDIRECT_URI=http://localhost:8080/oauth/google/callback.

Genere el hash sin guardar su contraseña en GitHub:

    .\.venv\Scripts\python.exe -m depurador.web --hash-password

El programa solicita una contraseña de al menos 12 caracteres y devuelve un HASH para pegar en WEB_PASSWORD_HASH del archivo privado. No utilice directamente la contraseña como valor del hash.

**Seguridad:** nunca enviar por chat ni subir a GitHub los archivos JSON, tokens, contraseñas o el contenido de config.local.ps1. La carpeta LocalAppData es privada por perfil en un Windows correctamente configurado; confirme ACL y políticas de la empresa. Para producción TI debe usar un gestor de secretos o ACL de cuenta de servicio.

## 4. Autorizar el retorno de Gmail para localhost

En Google Cloud > Google Auth Platform > Clientes > cliente OAuth de tipo Aplicación web, agregue como URI de redireccionamiento autorizado, **además de la URI de Render existente**:

    http://localhost:8080/oauth/google/callback

La coincidencia debe ser EXACTA. Google permite HTTP para localhost en pruebas de aplicaciones web, pero no para IP privadas o accesos de la LAN.

Referencias: https://developers.google.com/identity/protocols/oauth2/web-server

## 5. Iniciar la aplicación en su computador

Desde la carpeta del repositorio ejecute:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\Iniciar-PC.ps1

El script carga la configuración desde LocalAppData SOLO para ese proceso y transmite el JSON de la cuenta de servicio como variable de entorno al proceso Python, sin subirlo al repositorio. Abra:

    http://localhost:8080/

1. Entre con usuario y contraseña del panel.
2. Pulse **Autorizar Gmail con Google** y conceda acceso de solo lectura desde la cuenta esperada (si todavía no hay token local).
3. Seleccione año y mes del crédito en **1. Buscar correos con PDF**, y pulse Buscar correos.
4. Pulse **Verificar Google Sheets (solo lectura)**. Esta comprobación habilita Procesar todos por 15 minutos si se valida el archivo y sus 7 columnas.
5. Para una prueba de escritura controlada, use exclusivamente una copia aprobada de Google Sheets. **Procesar todos** importa el correo completo; si ya están registrados los QC, pueden aparecer como duplicados.
6. Revise la sección 4, luego **5. Consultar créditos por período** y la imagen PNG del resumen.

No borre filas ni datos de la hoja de producción solo para hacer pruebas.

## 6. Por qué NO habilitamos todavía a otros computadores de la red

El servidor local escucha solo en 127.0.0.1. Si se cambia a 0.0.0.0 y otros usuarios ingresan mediante HTTP, circularían sesiones y credenciales sin HTTPS y el retorno OAuth no puede usar una dirección IP privada. No recomendamos abrir el puerto 8080 directamente en la LAN ni desactivar medidas de seguridad para que funcione.

Para uso multiusuario, TI debe preparar un DNS con URL HTTPS accesible desde la LAN/VPN y un proxy inverso (IIS/ARR u otro aprobado), dejando Waitress en 127.0.0.1. Configurar WEB_SECURE_COOKIES=true y la URI HTTPS exacta en Google Cloud; validar la cabecera Host y la cadena de proxies según los controles del entorno. El usuario final entra con su navegador, sin Python. Las sesiones y el trabajo concurrente requieren pruebas con usuarios reales.

## 7. Migración a Windows Server sin reprogramar

La migración del ESCENARIO Gmail + Google Sheets no exige reescribir los módulos de correos, PDF, Sheets, informes ni controles de duplicado.

1. Instalar Python 3.12, dependencias y ejecutar pruebas en Windows Server con la misma rama main.
2. Preparar carpeta PRIVADA de secretos para la cuenta del servicio Windows, con ACL, y transferir o volver a emitir credenciales de manera segura. Es posible que deba autorizar Gmail nuevamente; no copiar tokens sin autorización de TI.
3. Configurar variables del nuevo equipo: WEB_HOST=127.0.0.1; WEB_PORT=8080; WEB_SECURE_COOKIES=true; WEB_SECRET_KEY segura; WEB_PASSWORD_HASH; GOOGLE_SPREADSHEET_ID; claves de Google, GMAIL_TOKEN_FILE y GMAIL_EXPECTED_EMAIL.
4. Registrar URL HTTPS definitiva terminada en /oauth/google/callback en el mismo cliente OAuth Web y ajustar GMAIL_REDIRECT_URI.
5. Publicar IIS como proxy inverso con HTTPS, servicio Windows con cuenta de mínimos privilegios, firewall, supervisión, backups y acceso LAN/VPN, según TI.
6. Verificar Google Sheets, buscar correos e iniciar una importación controlada antes de entregar a usuarios.

El directorio LOCALAPPDATA de la estación y el del servicio en Windows Server serán diferentes: hay que transferir configuración PRIVADA o recrearla, no copiar literalmente rutas absolutas. La hoja Google Sheets y el código se mantienen. El cambio de URL y OAuth es configuración, NO un cambio sustancial al código.

## 8. Riesgos y limitaciones importantes

- Google OAuth en estado de pruebas puede necesitar nueva autorización, y los tokens pueden caducar.
- Si el PC se apaga, entra en suspensión o pierde Internet, la web local deja de responder; Windows Server se configura para servicio continuo.
- No ejecutar la misma importación a la misma hoja simultáneamente desde PC, Render y Windows Server: evaluar concurrencia y bloqueos si se operará en paralelo.
- Mantener datos empresariales y credenciales conforme a las políticas de TI. No poner información de créditos en GitHub.
- Los pasos de los scripts están diseñados para PowerShell/Windows y deben verificarse en el PC concreto; ejecutar instalación de software solamente si lo permite TI.
- Los módulos Outlook y OneDrive existen como alternativa, pero esta ruta provisional no los utiliza.
