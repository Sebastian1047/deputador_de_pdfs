# Depurador de PDF · v0.7.2

**Aplicación web Python para navegador (Render o Windows Server)**. Para las próximas pruebas, busca mensajes en Gmail personal, permite seleccionar un correo, extrae información de sus PDF adjuntos **en memoria** y agrega filas a una **hoja nativa de Google Sheets guardada en Google Drive**. La integración con Outlook y OneDrive se conserva solo como alternativa heredada.

## Estado del desarrollo

- Conector Microsoft Graph para Microsoft 365 / Exchange Online (lectura solamente).
- Conector Excel Online para libros **.xlsx** en OneDrive para Empresas o SharePoint: una carga en memoria y una escritura por correo seleccionado.
- Manejo de claves únicas para evitar procesar el mismo adjunto dos veces, verificación de versión eTag y protección contra sobrescritura cuando el Excel cambie.
- Flask/Waitress para Windows Server, login, búsqueda y procesamiento manual seguro.
- Pruebas automáticas con datos simulados. **Pendiente** integración con credenciales reales y un PDF de referencia.
- La aplicación de escritorio permanece en pausa y no se compila automáticamente.
- GitHub conserva solo código y pruebas, **no ejecuta los PDF del cliente**.

## Instrucciones Windows Server y Microsoft 365

[Guía de despliegue, permisos y seguridad](docs/INSTALACION_WINDOWS_SERVER.md)

Con Python 3.12 y permisos de TI en el servidor:

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m depurador.web --hash-password

Una vez configurados los secretos en variables de entorno del servicio y el archivo config/campos.json:

    .\.venv\Scripts\python.exe -m depurador.web

TI publica la interfaz **solo en la intranet con IIS y HTTPS**. Los usuarios no instalan nada en sus portátiles.

### No publicado todavía

El servidor del cliente no se ha configurado. Falta confirmar si Outlook utiliza Exchange Online y dónde se guarda exactamente el Excel (.xlsx): OneDrive o SharePoint. También necesitamos un PDF anonimizado para definir los campos y una prueba con una copia del libro real.

**Limitación de Excel Online:** la API de Microsoft Graph para agregar filas directamente a un libro no admite permisos exclusivos de aplicación; el conector actual descarga y sustituye un .xlsx completo tras verificar versión, por lo que no debe utilizarse con libros complejos o en edición simultánea sin pruebas. Se conservan Gmail y Google Sheets solo como conectores alternativos de desarrollo, sin ser el destino principal.


**OneDrive empresarial:** puede configurarse el propietario (`MS_ONEDRIVE_OWNER`) y la ruta relativa (`MS_ONEDRIVE_PATH`) del `.xlsx`. Si TI ya conoce los identificadores, sigue disponible `MS_EXCEL_DRIVE_ID` y `MS_EXCEL_ITEM_ID`. Consulte la guía de Windows Server para requisitos y seguridad.


## Vista demostrativa desde el navegador (v0.5.2)

La ruta `docs/index.html` contiene una **demo interactiva, independiente del servidor**: lista correos ficticios, permite buscar y seleccionar uno, simula el procesamiento de PDF y muestra filas de ejemplo como si se hubieran registrado en Excel Online. **No consulta Outlook, no descarga PDF reales y no escribe en OneDrive**.

- Vista provisional desde los archivos de GitHub (a través de un visualizador HTML externo): https://raw.githack.com/Sebastian1047/deputador_de_pdfs/main/docs/index.html
- El visualizador externo puede mostrar una pantalla de confirmación. No coloque datos privados en esa página: es una demo pública.
- Enlace oficial previsto de GitHub Pages, cuando esté habilitado: https://sebastian1047.github.io/deputador_de_pdfs/

Para activar la URL oficial, un administrador del repositorio debe ir a **GitHub → Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main → Folder: /docs → Save**. Puede tardar unos minutos en publicar.

**Importante:** GitHub Pages y el visualizador externo sirven solo archivos estáticos. La aplicación web que realmente lee Outlook y edita Excel se ejecutará en **Windows Server interno** y no se expone a Internet desde GitHub.


## Gmail personal para pruebas (v0.6.0)

Ya se permite usar Gmail personal como fuente de PDF y Excel Online como destino empresarial, con autorización independiente para cada sistema. El panel puede buscar y seleccionar correos de Gmail sin necesidad de configurar los permisos de OneDrive. El botón de procesar permanece bloqueado hasta configurar Excel y las reglas de extracción.

Manual de autorización de Gmail en el servidor: docs/CONECTAR_GMAIL_PERSONAL.md

Nunca compartir contraseña, token ni credenciales JSON en GitHub o ChatGPT. La versión pública de demostración no se conecta a Gmail real.


**Protección adicional para Gmail personal:** configure en el Windows Server la variable privada `GMAIL_EXPECTED_EMAIL` con la dirección del buzón que realmente recibe los PDF. El sistema verifica que la cuenta autorizada por OAuth coincide antes de listar mensajes, sin guardar esa dirección en el repositorio.


## OAuth web de Gmail listo para despliegue (v0.6.2)

El repositorio incluye las rutas de servidor `POST /oauth/google/conectar` y `GET /oauth/google/callback`, con sesión autenticada, protección CSRF, estado OAuth de 10 minutos, verificación de la cuenta Gmail esperada y guardado privado del refresh token. El panel mostrará un botón **Autorizar Gmail con Google** cuando estén configurados el cliente OAuth y la dirección HTTPS del servidor.

**Mientras el proyecto solo esté en GitHub no se puede finalizar OAuth ni consultar el buzón real desde GitHub Pages.** No registrar una dirección de GitHub Pages como redirect URI; es una página estática pública. El servidor con Flask debe estar disponible en una URL HTTPS segura y previamente autorizada en Google Cloud. Para pruebas locales únicamente, Google permite `http://localhost`.

Guía: [OAuth Gmail desde la aplicación web](docs/OAUTH_GMAIL_WEB.md).

La credencial elegida en Google Cloud debe ser del tipo **Aplicación web** (no la de aplicación de escritorio usada por el flujo local opcional anterior). No almacenar el secreto OAuth, tokens ni PDFs de usuarios en el repositorio público.


## Hosting web gratuito para pruebas (Render Free)

Se añadió `render.yaml` para crear **un servicio web Python real, no GitHub Pages**. El plan Free permite abrir el panel en celular o computador tras conectar Render a GitHub y crear el servicio. **Todavía no se ha desplegado una URL** porque hace falta que el propietario conecte su cuenta Render. La aplicación requiere contraseña fuerte, configurada exclusivamente como secreto Render, y ofrece `/health` para comprobación.

Consulte [Cómo desplegar en Render](docs/DESPLIEGUE_RENDER.md). **Solo para desarrollo sin datos sensibles:** Render Free suspende el servicio y borra los tokens guardados localmente en cada suspensión/reinicio. Nunca subir JSON OAuth ni tokens a GitHub. La conexión permanente de Gmail y la información confidencial requerirán almacenamiento duradero y entorno aprobado.

## Google Drive como destino de pruebas (v0.7.2)

**Configuración Render actual:** `MAIL_PROVIDER=gmail` y `TABLE_PROVIDER=google_sheets`. Este flujo alimenta una **hoja nativa de Google Sheets alojada en Google Drive**; NO actualiza directamente un Excel `.xlsx` almacenado en Google Drive. Para ese segundo formato se requiere otra implementación.

Para editar una hoja de prueba ya existente:
1. Habilitar **Google Sheets API** en el mismo proyecto Google Cloud.
2. Crear una cuenta de servicio de Google Cloud con acceso mínimo y generar una clave JSON de prueba si la política organizacional lo permite.
3. Compartir **solo la hoja específica de Google Drive** con el correo de la cuenta de servicio y permiso **Editor**.
4. En **Render → Environment**, guardar `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` con el contenido del JSON y `GOOGLE_SPREADSHEET_ID` con el identificador de la URL del documento. `GOOGLE_SHEET_TAB` inicialmente es `Registros`.
5. Mantener aparte la autorización OAuth de Gmail: `gmail.readonly` no permite editar Sheets. La cuenta de servicio no puede leer el Gmail del usuario.
6. Definir `config/campos.json` según un PDF anonimizado antes de activar el procesamiento real.

No colocar JSON de cuentas de servicio, tokens ni datos privados en GitHub, capturas ni mensajes de chat. Consulte [paso a paso en Render](docs/DESPLIEGUE_RENDER.md).
