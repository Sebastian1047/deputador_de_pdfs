# Autorizar Gmail personal (solo lectura) para el servidor Windows

Esta integración se usa cuando los PDF llegan a una cuenta @gmail.com personal.
**No se requiere un administrador Google Workspace**. La persona propietaria
inicia sesión en Google y acepta el permiso de Gmail de solo lectura.

La aplicación operativa seguirá funcionando en el Windows Server de la empresa.
Por tanto, la **instalación del servicio en el servidor** sí requiere la
aprobación y participación del área de TI correspondiente.

## Primero: configurar Google Cloud

1. Abrir https://console.cloud.google.com/ con una cuenta que pueda administrar un proyecto.
2. Crear un proyecto, por ejemplo "Depurador PDF Pruebas".
3. Habilitar **Gmail API** desde APIs y servicios.
4. Configurar Google Auth Platform: Branding y Audience **External** (no Internal, ya que es un Gmail personal).
5. Para pruebas con estado **Testing**, agregar el Gmail real como usuario de prueba.
6. En Data Access agregar únicamente https://www.googleapis.com/auth/gmail.readonly
7. En Clients crear un OAuth Client ID tipo **Desktop app** para autorización inicial en un equipo con navegador.
8. Descargar el JSON del cliente OAuth a una carpeta privada; **no subir a GitHub**.

Gmail readonly es un alcance **restringido**. En OAuth Testing los
refresh tokens normalmente vencen a los siete días. Google puede exigir
verificación para operaciones fuera de un entorno de prueba; no debe asumirse
funcionamiento indefinido sin cumplir la política aplicable.

Guías oficiales:
https://developers.google.com/workspace/gmail/api/quickstart/python
https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification

## Segundo: vincular Gmail desde un equipo autorizado

Requisitos: Python 3.12 con las dependencias del proyecto, navegador disponible
en la misma máquina desde la que se ejecuta el comando. Por ejemplo,
Windows Server durante una sesión interactiva autorizada por TI.

Dentro de la carpeta del repositorio, ejecutar PowerShell:

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-web.txt

La autorización se inicia con el siguiente comando. Las rutas son ejemplos:
TI debe ajustar los permisos de la carpeta para que solo puedan acceder a ella
el usuario autorizador y la cuenta de servicio aprobada.

    .\.venv\Scripts\python.exe -m depurador.gmail_personal --authorize --credentials "C:\ProgramData\DepuradorPDF\secrets\client_secret_google.json" --token "C:\ProgramData\DepuradorPDF\secrets\token_gmail.json"

Se abrirá el navegador de ese mismo equipo. La persona inicia sesión en el
Gmail que recibe PDF y acepta permiso de lectura. No introducir contraseñas en
la aplicación. El token queda en la carpeta privada del servidor. Este token
es sensible, no enviarlo por chat/correo ni subirlo al repositorio.

## Tercero: variables del servidor web

    MAIL_PROVIDER=gmail
    TABLE_PROVIDER=excel_online
    GMAIL_TOKEN_FILE=C:\ProgramData\DepuradorPDF\secrets\token_gmail.json
    GMAIL_QUERY=has:attachment filename:pdf newer_than:30d

El panel web consultará Gmail para listar mensajes y permitirá elegir uno.
Esto funciona **sin autorización de Microsoft 365**. Sin embargo, para guardar
en Excel Online del cliente sí se necesitan además los permisos de Microsoft
para OneDrive empresarial y un Excel .xlsx de prueba.

Para esa segunda conexión consultar INSTALACION_WINDOWS_SERVER.md.

## Qué comprobar primero

1. Login web en Windows Server y búsqueda de correos Gmail. La aplicación debe
mostrar fecha, remitente, asunto y cantidad de PDF del mensaje elegido.
2. No activar procesamiento real hasta obtener un PDF de ejemplo anonimizado y
definir las columnas exactas.
3. Conectar Microsoft 365 solo cuando TI haya aprobado el acceso al Excel.
4. Probar la escritura con una **copia de prueba** del archivo real antes de
trabajar sobre documentos empresariales.

La demo pública de GitHub es únicamente ilustrativa. No autoriza Gmail, no
descarga PDF y no escribe en Excel.
