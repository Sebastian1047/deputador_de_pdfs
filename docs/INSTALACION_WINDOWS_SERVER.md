# Windows Server + Outlook empresarial + Excel Online

## Estado

Aplicación Python Flask/Waitress para la intranet. Repositorio GitHub solo para código y pruebas; los datos y credenciales permanecen en el entorno del cliente. La edición real de Outlook/Excel no está conectada hasta que TI autorice Microsoft Graph y se definan columnas con un PDF de muestra. Escritorio en pausa.

## Arquitectura y almacenamiento

- Correo de entrada: Outlook empresarial de Microsoft 365 / Exchange Online, con permiso de solo lectura a un buzón autorizado.
- Aplicación: Python en Windows Server, con autenticación propia y HTTPS mediante IIS como proxy inverso.
- Destino: Excel Online en OneDrive empresarial o SharePoint, archivo formato .xlsx.
- Cada operación toma un mensaje elegido por la persona y procesa **únicamente sus PDF adjuntos**.
- No escribe PDF en disco. Para este conector Excel, el libro completo se descarga **temporalmente a memoria RAM**, se agrega una tanda de filas con openpyxl y se devuelve al almacenamiento autorizado. Esto no es la API de filas de Excel.
- La versión inicial es apta para un libro sencillo y una hoja de registros exclusiva; no usar con macros, características avanzadas no soportadas, vínculos complejos, colaboración intensiva o etiquetas de confidencialidad sin validar con TI.

### Por qué se utiliza descarga y subida del libro

Microsoft Graph /workbook/tables/.../rows/add **no admite permisos app-only**. Para que el servidor opere sin abrir sesión interactiva en cada ejecución se usa el API de archivos /drives/{driveId}/items/{itemId}/content con permisos de aplicación. Las operaciones de archivos sí admiten app-only con autorización de TI, pero requieren controlar la versión eTag para reducir el riesgo de sobrescritura accidental. El código comprueba el eTag inmediatamente antes de subir y transmite If-Match. Si Excel cambió, detiene la operación y requiere reintentar.

Fuentes oficiales:
- https://learn.microsoft.com/en-us/graph/api/tablerowcollection-add?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/driveitem-put-content?view=graph-rest-1.0

## Requisitos de TI: Microsoft 365

1. Confirmar que el cliente utiliza **Exchange Online**, no Exchange Server on-premises. El conector Microsoft Graph no sirve directamente para una instalación Exchange local.
2. Confirmar que el Excel está en **OneDrive para la Empresa o SharePoint**. Necesitamos el drive ID y el item ID de su archivo de registros, no usuario ni contraseña.
3. Registrar una aplicación Microsoft Entra y autorizar:
   - **Mail.Read** de tipo Application para leer correos. Restringir al buzón aprobado mediante Exchange Online Application RBAC. No conceder envío ni modificación de mensajes.
   - Permisos de lectura/escritura sobre el Excel (Microsoft Graph driveItem). Su documentación enumera permisos de aplicación Files.ReadWrite.All o Sites.ReadWrite.All. Son privilegios amplios; TI debe evaluar si puede aplicar permisos limitados al sitio/archivo mediante mecanismos admitidos en su tenant antes de producción.
   - El código de esta versión usa un client ID/secret para ambos accesos. Para producción, separar identidades o sustituir secreto por certificado cuando sea viable.
4. Mantener el client secret fuera del código y del repositorio. Registrar caducidad, rotación y auditoría. El servidor precisa HTTPS saliente a login.microsoftonline.com y graph.microsoft.com y a endpoints de descarga firmados SharePoint.
5. Escribir en una **copia del libro de pruebas** antes de operar sobre el definitivo. Microsoft no permite sustituir archivos con ciertas etiquetas de sensibilidad utilizando autenticación app-only.

## Instalación en Windows Server (cuando TI autorice)

Requiere Python 3.12 instalado solo en Windows Server; las estaciones de trabajo usan únicamente navegador web. En PowerShell dentro del repositorio, tras clonar main:

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m depurador.web --hash-password

El último comando genera un hash de contraseña a partir de una clave de mínimo 12 caracteres.

Variables de entorno bajo control de TI (nunca registrar sus valores en GitHub):

| Variable | Descripción |
| --- | --- |
| MAIL_PROVIDER | outlook |
| TABLE_PROVIDER | excel_online |
| MS_TENANT_ID | ID del tenant Microsoft |
| MS_CLIENT_ID | ID de la aplicación Entra |
| MS_CLIENT_SECRET | Secreto de la aplicación |
| MS_MAILBOX | Buzón autorizado, p. ej. reportes@empresa.com |
| MS_EXCEL_DRIVE_ID | Identificador drive de OneDrive empresarial o SharePoint |
| MS_EXCEL_ITEM_ID | Identificador item del archivo Excel .xlsx |
| MS_EXCEL_SHEET | Nombre de hoja de registros (por defecto Registros) |
| OUTLOOK_QUERY | Búsqueda inicial KQL, por defecto hasAttachments:true |
| WEB_SECRET_KEY | Cadena aleatoria privada de 32 caracteres o más |
| WEB_ADMIN_USER | Usuario para el panel |
| WEB_PASSWORD_HASH | Hash del password del panel |
| PDF_FIELDS_FILE | Ruta al JSON de patrones de extracción, por defecto config/campos.json |
| WEB_HOST | 127.0.0.1 (por defecto) |
| WEB_PORT | 8080 (por defecto) |
| WEB_SECURE_COOKIES | true al trabajar con HTTPS (por defecto) |

Ejecución en el servidor:

    .\.venv\Scripts\python.exe -m depurador.web

TI configura la ejecución como **servicio Windows** con una cuenta de mínimos privilegios, reinicio tras fallos y controles de acceso. IIS debe actuar como proxy inverso con **HTTPS**, certificado corporativo y acceso restringido a la LAN/VPN, reenviando a 127.0.0.1:8080. No abrir directamente el puerto Python al exterior.

## Archivo Excel de destino

1. Crear una copia de prueba del archivo, en OneDrive Empresarial o SharePoint.
2. Usar un archivo **.xlsx** (sin macros), preferiblemente dedicado a registros.
3. Crear una hoja llamada **Registros** (o nombre configurado).
4. La fila 1 debe tener columnas en este orden: document_key, processed_utc, y los campos que se acordarán a partir del PDF real. El sistema comprueba las cabeceras antes de editar.
5. El motor carga el libro, agrega únicamente los registros que no tengan la misma clave de adjunto y guarda el libro una sola vez por correo seleccionado. Actualiza el rango de la tabla de Excel de esa hoja o crea una tabla si no existe.
6. No ejecutar con un libro abierto en edición simultánea sin comprobar los conflictos. Si cambia la versión durante el procesamiento, el sistema informa error y no da la operación por completada.
7. Si el libro contiene tablas complejas, Power Query, macros, conexiones externas, comentarios o características de Excel avanzadas, revisar en una copia si openpyxl conserva todo lo necesario. Para esos libros sería preferible un conector con autorización delegada para la API de filas Excel.

## Operación

Entrar a la URL corporativa segura > acceder con usuario autorizado > buscar mensajes de Outlook > elegir el correo específico > presionar Procesar > ver encontrados, agregados, duplicados y errores. Cada acción solo procesa un mensaje y sus adjuntos, no la bandeja entera.

## Pendiente por confirmar

- Microsoft 365/Exchange Online frente a Exchange local.
- Si Excel está guardado en OneDrive Empresarial o SharePoint.
- Un PDF de ejemplo anonimizado y las columnas que desea extraer.
- Revisión de TI del acceso a Graph, de la seguridad del archivo y del despliegue IIS/Windows Server.

## Configuración simplificada para OneDrive empresarial (versión 0.5.1)

En lugar de buscar los IDs de drive e item, TI puede configurar la ruta del libro usando:

- `MS_ONEDRIVE_OWNER`: cuenta dueña del OneDrive empresarial, por ejemplo `informes@empresa.com`.
- `MS_ONEDRIVE_PATH`: ruta relativa al OneDrive de ese propietario, por ejemplo `Informes/2026/Reporte consolidado.xlsx`.
- `MS_EXCEL_SHEET`: pestaña de destino, por defecto `Registros`.

El servidor resuelve esos valores mediante `GET /users/{upn}/drive/root:/{ruta}:` para identificar el archivo y después utiliza la misma implementación de descarga, comparación de versión eTag y subida condicionada. Se pueden mantener alternativamente `MS_EXCEL_DRIVE_ID` y `MS_EXCEL_ITEM_ID` proporcionados por TI. Cuando ambas configuraciones existen, tiene prioridad propietario+ruta.

**Advertencia:** la dirección debe ser la del **propietario real** del OneDrive. Si el libro aparece solamente en «Compartido conmigo», la ruta del destinatario podría no resolver el documento. En ese caso TI debe obtener los IDs de la unidad y el archivo donde esté realmente almacenado. La empresa debe aprobar los permisos de Microsoft Graph y realizar pruebas en una copia del Excel, especialmente ante ediciones concurrentes, formatos avanzados y etiquetas de sensibilidad.
