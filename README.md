# Depurador de PDF · Python (v0.4.0)

Aplicación para extraer campos de muchos PDF adjuntos a mensajes de correo, **sin descargarlos manualmente**, y escribir los resultados en una hoja de cálculo en la nube. El proyecto usa inicialmente **Gmail + Google Sheets (en Drive)**, con adaptadores para reemplazarlos luego por las herramientas del cliente.

## Estado actual

- ✅ Código Python, lectura de archivos adjuntos en memoria, extracción de texto y campos regex.
- ✅ Actualización de Google Sheets sin registros repetidos, usando una clave por adjunto.
- ✅ Pruebas y demo 100 % local con datos inventados; GitHub Actions de validación.
- ✅ Ejecución manual y programación opcional de GitHub Actions.
- ✅ Panel público de información (docs/index.html), sin datos de clientes.
- ⏳ Configurar credenciales OAuth, ID de la hoja y reglas con un PDF real.
- ⏳ Si los PDF son escaneos, agregar OCR.
- ⏳ Nuevos conectores (Outlook, Microsoft 365/OneDrive, otras herramientas del cliente).

## Ejecución sin credenciales

Se necesita Python 3.11+.

```bash
pip install -r requirements.txt
python -m pytest -q
python -m depurador --demo
```

La demo genera un PDF de ejemplo **en memoria**, extrae tres valores y simula una fila. No accede a Gmail ni Drive.

## Configuración para Gmail y Drive

1. En Google Cloud crear un proyecto; habilitar **Gmail API** y **Google Sheets API**.
2. Configurar consentimiento OAuth 2.0 para la cuenta autorizada. Conceder solamente los ámbitos `gmail.readonly` y `spreadsheets`. Obtener un **refresh token** con consentimiento del dueño de la cuenta y acceso sin conexión; puede requerir verificación/publicación de la aplicación en Google según el caso. No publicar credenciales en GitHub.
3. Crear en Google Drive una **hoja nativa de Google Sheets** con una pestaña llamada `Registros`. Copiar el ID de la URL. **Importante:** un Excel `.xlsx` alojado en Drive no es lo mismo que una hoja nativa; debe convertirse o añadirse otro adaptador.
4. Ajustar `config/campos.json` con las columnas necesarias según un PDF auténtico. `config/campos.ejemplo.json` muestra el formato de patrones de demostración, no los campos reales.
5. GitHub → Settings → Secrets and variables → Actions → **Secrets**:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`
6. En **Variables**:
   - `GOOGLE_SPREADSHEET_ID`: ID de la hoja nativa en Drive.
   - `GOOGLE_SHEET_TAB`: `Registros`.
   - `GMAIL_QUERY`: por ejemplo `has:attachment filename:pdf newer_than:30d`, idealmente añadir remitente/etiqueta específica.
   - `PROCESAMIENTO_ACTIVO`: `true` **solo** después de probar.
7. Ir a Actions → **Procesar PDF del correo** → Run workflow. Por defecto, las ejecuciones programadas se omiten si no está activa la variable `PROCESAMIENTO_ACTIVO`. El horario de ejemplo es 13:17 y 19:17 UTC; ajustarlo con el cliente.
8. Se agregan columnas `document_key` y `processed_utc` para evitar duplicados. Las demás columnas corresponden a los campos configurados. Una vez creada la tabla, no cambiar nombres/orden sin una migración.

**Atención:** GitHub Actions puede retrasar ejecuciones programadas, y GitHub deshabilita automáticamente las programaciones en repositorios públicos sin actividad por 60 días. No garantiza procesamiento inmediato.

## Seguridad

El repositorio es **público**. No subir ni registrar correos, PDF reales, información personal, tokens, credenciales ni hojas con datos del cliente. El flujo mantiene el contenido del PDF en RAM durante la ejecución y solo escribe los valores extraídos en el destino autorizado. Evitar publicar datos reales por GitHub Pages o en logs de Actions. Los datos deben alojarse en la cuenta que el cliente autorice.

## Arquitectura

```text
GmailReader ---\
                → core.procesar() → GoogleSheetsWriter
OtroReader ----/                   ↘ OtroWriter (posterior)
                ↳ extracción PDF y reglas en config/campos.json
```

Para cambiar el correo/tabla se implementan nuevos adaptadores y se actualiza la selección del proveedor: el motor `core.py` se mantiene. No hay servidor Python permanente; GitHub Pages es solo una interfaz estática y GitHub Actions ejecuta Python cuando corresponda.

## Límites de esta primera versión

- Reglas de extracción aún no definidas: necesitamos un PDF de ejemplo (puede ser anonimizado) y los nombres de las columnas de destino.
- Los documentos deben contener texto seleccionable. El OCR para imágenes escaneadas se agregará si es necesario.
- La idempotencia usa la clave `document_key` de cada adjunto en Sheets; no elimina duplicados si se reenvía el mismo PDF como adjunto de otro mensaje.
- El procesamiento depende de OAuth/consentimiento real, límites de APIs y permisos de acceso. No se ha ejecutado una integración real.
- Esta página web no ejecuta Python desde el navegador ni muestra datos privados; para una consola operativa con autenticación habrá que definir un backend o servicio compatible.


## Versión de escritorio Windows — v0.3.2

La aplicación de escritorio con Tkinter utiliza el mismo motor Python que la versión web. Tiene botones para probar con PDF ficticio, conectar Gmail/Sheets, buscar correos que tienen PDF, seleccionar un único mensaje de la lista, editar las reglas y procesar solamente los adjuntos de ese correo.

### Abrir en cualquier portátil Windows SIN instalar nada

La versión de escritorio es **portable**: un único archivo `DepuradorPDF.exe` que incorpora Python y las bibliotecas utilizadas. **No requiere instalar Python, ejecutar comandos ni abrir el navegador para mostrar la ventana.** La primera vez, para trabajar con Gmail real, sí se debe autorizar Google y configurar el destino y los campos.

1. Abra https://github.com/Sebastian1047/deputador_de_pdfs/actions/workflows/escritorio.yml
2. Abra una compilación **exitosa** del flujo *Compilar escritorio Windows portable*.
3. Descargue el artefacto `DepuradorPDF-Portable-Windows` (GitHub lo entrega en un archivo ZIP).
4. Extraiga su contenido en una carpeta del portátil y haga **doble clic en `DepuradorPDF.exe`**. No hay asistente ni instalador. El ZIP incluye `LEEME.txt`.
5. La aplicación se abre incluso sin cuenta Google. **Probar sin conexión** ejecuta una prueba con un PDF ficticio.

Para desarrollar desde el código fuente (no es necesario para usuarios del EXE):

    pip install -r requirements-desktop.txt
    python -m depurador.escritorio

La compilación y las pruebas de Windows se ejecutan en los servidores de GitHub, no en el portátil del usuario. El ejecutable incluye una autoprueba interna del motor PDF para comprobar el empaquetado antes de publicar el artefacto. No se firma digitalmente, por lo que Windows podría advertir sobre aplicaciones no reconocidas; no es preciso desactivar antivirus ni protecciones de Windows.

### Configuración en el portátil

1. Pulse **Probar sin conexión**. El sistema crea un PDF ficticio en memoria y simula una fila.
2. Para conectarse a Gmail/Google Sheets reales, cree un proyecto Google Cloud, habilite Gmail API y Google Sheets API, y descargue un archivo OAuth Client ID de tipo **Desktop app** (JSON). Nunca lo suba a GitHub.
3. Pulse **Elegir JSON** y **Conectar Google**. El navegador pedirá consentimiento del usuario autorizado.
4. Ingrese ID o URL de Google Sheets, nombre de pestaña y consulta Gmail.
5. En **Campos de los PDF**, edite/importa reglas JSON según el documento real que vamos a estudiar.
6. Regrese a **1. Seleccionar correo** y use el buscador de Gmail (remitente, asunto, fecha, etc.). Pulse **Buscar correos**. Se muestran fecha, remitente, asunto y cantidad de archivos PDF por mensaje.
7. Haga clic en **un solo correo** de la lista. El botón **Procesar correo seleccionado** se habilita únicamente cuando existe una selección válida. Confirme antes de guardar filas en Google Sheets.
8. Se descargan los adjuntos del mensaje elegido únicamente a memoria RAM (no a carpetas) y se envían los campos extraídos a la hoja. Ningún otro mensaje es procesado en este modo.
9. Si cambia el filtro, debe hacer una nueva búsqueda y selección. No se permite procesar toda la bandeja desde el botón de escritorio; se repiten los pasos para otro correo.

Nota: la versión web mediante GitHub Actions conserva su procesamiento automático por consulta, sin necesidad de selección manual. Se previenen registros repetidos cuando vuelve a elegir el mismo adjunto, mediante la clave de Gmail en la hoja.

Las preferencias y reglas se guardan en el perfil local de usuario: %APPDATA%\DepuradorPDF en Windows. El token de Google se guarda por separado como token_google.json en esa misma carpeta. No se almacena en el código ni el ejecutable. Proteja el perfil del equipo. Hace falta conexión a Internet para procesar correo y escribir en Google Sheets.

**Limitaciones:** se necesita un PDF de ejemplo para definir las reglas, y credenciales OAuth válidas para comprobar la integración real. La aplicación web alojada con GitHub Pages muestra un panel informativo, pero es GitHub Actions quien ejecuta el código privado en la nube. Hay que habilitar Pages en Settings > Pages desde /docs para publicar ese panel. Evitar iniciar web y escritorio al mismo tiempo contra la misma hoja hasta añadir un bloqueo de concurrencia. PyInstaller genera el EXE en un runner de Windows. El EXE no está firmado digitalmente y puede requerir aprobación por políticas de seguridad del equipo.

Cuando el cliente elija otros proveedores (por ejemplo Outlook y Microsoft Excel en OneDrive), se podrán escribir nuevos conectores conservando depurador/core.py y las reglas de extracción. Una hoja Google Sheets alojada en Drive no es lo mismo que un archivo Excel .xlsx.


## Aplicación web en el servidor LOCAL de la empresa — versión 0.4.0

**Nueva arquitectura:** GitHub conserva el código, pero ya **no procesa correos ni PDF mediante GitHub Actions**. La empresa ejecutará su propio servidor Python con Flask y Waitress. **La versión escritorio está en pausa**: el código permanece, pero no se compila automáticamente en cada push.

### Características del panel interno

- Acceso por usuario y contraseña con contraseñas almacenadas como hash, sesión de 8 horas, protección CSRF y bloqueo temporal de intentos fallidos.
- Busca mensajes Gmail por filtro configurable y muestra fecha, remitente, asunto y cantidad de PDF sin descargar adjuntos.
- El usuario pulsa **Procesar** en la fila del correo específico que desea. La selección solo es válida si el correo pertenece a la lista consultada de su sesión.
- Extrae datos de todos los PDF de ese mensaje **en memoria**, evita duplicados por clave de adjunto e inserta registros en Google Sheets. No modifica ni elimina mensajes Gmail.
- Procesa en segundo plano, con un solo trabajo simultáneo y resumen de PDF procesados, repetidos y fallidos. El resumen es temporal (solo vive en memoria mientras funcione el servicio).

### Preparación en el servidor corporativo

Requisitos: Python 3.11+ y permiso de TI para instalar dependencias y mantener un servicio ejecutándose en el servidor. Puede utilizarse Windows Server o Linux. La ruta de instalación debe ser accesible únicamente a TI. No hay obligación de instalar software en cada portátil: los usuarios ingresan desde su navegador a la dirección interna autorizada.

1. Obtener el proyecto mediante clonación o un ZIP de la rama main y entrar a su carpeta.
2. Crear un entorno virtual Python en el servidor y ejecutar:

       python -m pip install -r requirements-web.txt
       python -m pytest -q

3. Generar una contraseña robusta (mínimo 12 caracteres) para el administrador:

       python -m depurador.web --hash-password

   El comando pide la contraseña sin mostrarla y devuelve un hash. **No guardar la contraseña ni el hash en GitHub.**
4. Configurar las siguientes variables de entorno **en el servidor**, gestionadas por TI:

   | Variable | Uso |
   | --- | --- |
   | WEB_SECRET_KEY | Valor aleatorio de 32 caracteres o más, secreto |
   | WEB_ADMIN_USER | Nombre del usuario autorizado |
   | WEB_PASSWORD_HASH | Resultado del comando anterior |
   | GOOGLE_CLIENT_ID | ID OAuth del proyecto autorizado |
   | GOOGLE_CLIENT_SECRET | Secreto OAuth del proyecto autorizado |
   | GOOGLE_REFRESH_TOKEN | Token de renovación con consentimiento del dueño |
   | GOOGLE_SPREADSHEET_ID | ID de hoja **nativa** Google Sheets |
   | GOOGLE_SHEET_TAB | Pestaña (por defecto Registros) |
   | GMAIL_QUERY | Filtro predeterminado, por ejemplo remitente y PDF |
   | PDF_FIELDS_FILE | Ruta absoluta al JSON de campos (opcional; por defecto config/campos.json) |
   | WEB_HOST | Por defecto 127.0.0.1 (solo loopback) |
   | WEB_PORT | Por defecto 8080 |
   | WEB_SECURE_COOKIES | true para HTTPS (por defecto) |

5. Configurar **config/campos.json** con los campos reales cuando tengamos un PDF de ejemplo. El archivo actualmente está vacío a propósito; evita escribir datos equivocados.
6. Iniciar el servidor con:

       python -m depurador.web

   El proceso debe permanecer activo. Para producción, TI debe configurarlo como servicio de Windows o systemd en Linux, con reinicio automático, usuario de mínimos privilegios y registros adecuados.
7. TI debe instalar y configurar **un proxy inverso con HTTPS** (por ejemplo IIS, Nginx o Caddy), protegido por red corporativa/VPN, que reenvíe al servidor en 127.0.0.1:8080. No publicar Waitress directamente a Internet ni operar credenciales sobre HTTP. Mantener WEB_SECURE_COOKIES=true en HTTPS. Evitar enviar tráfico del cliente por páginas públicas de GitHub.
8. Desde un navegador autorizado en la red de la empresa abrir la dirección interna definida por TI, iniciar sesión, buscar, elegir un correo y pulsar Procesar.

**Prueba local sin proxy:** solo para TI, en el mismo servidor y sin exponer a la LAN, se puede usar WEB_SECURE_COOKIES=false con WEB_HOST=127.0.0.1 y http://127.0.0.1:8080. **Nunca** usar HTTP para acceso remoto con credenciales reales.

### Seguridad, límites y tareas pendientes

- Los datos del correo se muestran únicamente tras autenticar. Las listas quedan en RAM por 15 minutos; jamás en GitHub ni en GitHub Pages.
- El proyecto y los workflows de CI permanecen públicos: **no subir PDF reales, secretos, archivos de datos ni información identificable**. Los PDF no se guardan en el servidor, se procesan en memoria. El servidor necesita conexión **saliente** a las APIs autorizadas de Google; estar alojado en la LAN no elimina esa dependencia.
- Las cuentas, políticas OAuth, configuración de proxy HTTPS, copias de seguridad y permisos de empresa requieren acompañamiento del equipo de TI.
- Para uso con más de un usuario concurrente, se recomienda posteriormente añadir autenticación corporativa (SSO/AD) y persistencia segura de procesos. En la fase actual hay un único usuario administrador y un proceso Python que admite varias peticiones.
- El mecanismo de deduplicación sigue basado en el ID de adjunto Gmail: si reenvían el mismo PDF como un nuevo mensaje, podría repetirse.
- Si algún documento es escaneado (imagen), hará falta OCR. Necesitamos un PDF de ejemplo anonimizado y las columnas objetivo.
- La herramienta de escritorio no fue eliminada; simplemente quedó en pausa. El workflow de escritorio solo corre si TI/desarrollo lo inicia manualmente.
