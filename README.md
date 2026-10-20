# Depurador de PDF · Python (v0.3.0)

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
pytest -q
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


## Versión de escritorio Windows — v0.3.0

La aplicación de escritorio con Tkinter utiliza el mismo motor Python que la versión web. Tiene botones para probar con PDF ficticio, conectar Gmail/Sheets, buscar correos que tienen PDF, seleccionar un único mensaje de la lista, editar las reglas y procesar solamente los adjuntos de ese correo.

### Obtener el ejecutable (.exe) desde GitHub

1. Abra https://github.com/Sebastian1047/deputador_de_pdfs/actions/workflows/escritorio.yml
2. Seleccione una ejecución exitosa (o lance Run workflow).
3. Descargue el artefacto llamado DepuradorPDF-Windows y descomprima el archivo ZIP.
4. Ejecute DepuradorPDF.exe en Windows. No necesita instalar Python.

También puede iniciar la ventana desde el código fuente con:

    pip install -r requirements-desktop.txt
    python -m depurador.escritorio

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
