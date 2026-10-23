# Desplegar la aplicación web en Render Free (pruebas)

**Estado de este proyecto:** el código y `render.yaml` están preparados para Gmail + Google Sheets, pero **todavía no existe una instancia Render creada ni una URL pública verificada**. Para crearla es necesario autorizar el acceso a la cuenta Render y vincular el repositorio GitHub. Nunca revelar claves ni tokens en el chat o en GitHub.

## Qué ofrece Render Free

Un **Web Service** Python real con HTTPS (dominio `*.onrender.com`) que puede abrirse desde navegador en celular/computador. No es GitHub Pages: Render sí ejecuta el servidor Python Flask/Waitress. El plan Free se usa **solo para desarrollo/demostraciones sin datos reales sensibles**.

Límites importantes comprobados en documentación de Render:
- Se suspende a los **15 minutos** sin solicitudes; el primer arranque siguiente puede tardar alrededor de un minuto.
- Tiene un **sistema de archivos efímero**. Toda autorización Gmail recibida y guardada en un archivo local (incluido `/tmp/depurador-pdf/token_gmail.json`) se **pierde al reiniciar, suspender o volver a desplegar**. Será necesario volver a autorizar Gmail.
- El plan Free no permite discos persistentes. La opción Free de Postgres **vence a los 30 días**; no se ha incluido como almacén de tokens.
- La potencia y memoria son limitadas. Un correo con 40 PDF puede requerir más recursos que el plan gratuito.
- Para datos personales o empresariales, consultar primero sus políticas de protección de datos, consentimiento y el acuerdo del servicio, además de las verificaciones requeridas por Google para `gmail.readonly`.

Fuente: https://render.com/docs/free

## Paso 1: crear servicio desde GitHub

1. Entrar a https://dashboard.render.com/ e iniciar sesión o crear la cuenta del responsable del proyecto.
2. Conectar GitHub cuando lo solicite Render. Autorizar solamente el repositorio necesario.
3. Crear un recurso **New → Blueprint** desde el repositorio `Sebastian1047/deputador_de_pdfs`, rama `main`.
4. Render encontrará el archivo `render.yaml` e identificará un **Web Service / Python / Free**.
5. Render solicitará `WEB_ADMIN_PASSWORD`. Crear una **contraseña nueva y robusta de 12+ caracteres**, exclusiva del panel web. Guardarla en el administrador de contraseñas autorizado; solo introducirla en el formulario privado de Render. El usuario inicial del panel será `administrador`.
6. Completar la creación. Render ejecutará `pip install -r requirements-web.txt` y `python -m depurador.web`.
7. Cuando termine, el panel mostrará la dirección web exacta de su servicio, por ejemplo `https://NOMBRE-QUE-ASIGNE-RENDER.onrender.com`. El ejemplo no es un enlace creado.
8. Verificar que `/health` muestra únicamente `{"status":"ok"}`. Abrir `/` y comprobar el inicio de sesión.

El despliegue automático por cambios de GitHub está desactivado en el Blueprint para no provocar reinicios innecesarios. Puede iniciarse manualmente desde Render si se actualiza la aplicación.

## Paso 2: autorizar Gmail desde Render (solo si el uso está aprobado)

Cuando la URL HTTPS real ya exista, abrir Google Cloud → Google Auth Platform → Clientes → aplicación OAuth web creada anteriormente.

Agregar en **URIs de redireccionamiento autorizados** la dirección exacta:

    https://NOMBRE-REAL.onrender.com/oauth/google/callback

**No copiar ejemplos con dominios ajenos.** La dirección debe coincidir letra por letra con la que tiene el servicio.

En Render → Servicio → Environment, agregar como **secretos privados** (no `render.yaml`):

- `GMAIL_OAUTH_CLIENT_JSON`: **contenido completo** del archivo JSON del cliente OAuth de tipo Aplicación web descargado de Google. No pegarlo en GitHub ni enviarlo al chat.
- `GMAIL_REDIRECT_URI`: la dirección de callback HTTPS real del paso anterior.
- `GMAIL_EXPECTED_EMAIL`: la dirección Gmail exacta que debe leer la aplicación (se configura solo en Render).
- Ya incluye `GMAIL_TOKEN_FILE=/tmp/depurador-pdf/token_gmail.json` como almacenamiento **temporal**, que se pierde cuando Render detiene/reinicia el servicio.

Una vez guardadas las variables, iniciar sesión en la web de Render y pulsar **Autorizar Gmail con Google**. El propietario inicia sesión directamente en Google y acepta **solo lectura** de Gmail. Al regresar, el botón **Buscar correos** podrá consultar Gmail cuando el permiso esté vigente.

**Advertencia importante:** en Render Free el token guardado se perderá al suspenderse el servicio después de 15 minutos sin actividad y al reiniciarse. No es apto para una conexión Gmail permanente. No emplear datos reales sensibles en un servicio gratuito sin autorización y controles adecuados.

## Paso 3: extracción PDF y destino Google Sheets en Drive

Para las próximas pruebas el origen será Gmail y el destino una hoja nativa de **Google Sheets**, almacenada en Google Drive:

1. Subir el Excel original a Drive, abrirlo y elegir **Archivo → Guardar como Hojas de cálculo de Google**. Se crearán dos archivos; conservar intacto el Excel original. Comprobar ambas pestañas, encabezados y el resumen. [Guía específica](PLANTILLA_CREDITOS_SOLE.md).
2. En Google Cloud, proyecto **Procesador PDF JN**, habilitar **Google Sheets API** además de Gmail API.
3. Crear una **cuenta de servicio** solo para Sheets y una clave JSON de prueba, si Google Cloud permite generar claves. El `client_email` de esa cuenta termina normalmente en `.iam.gserviceaccount.com`. No compartir la clave JSON en GitHub ni en el chat.
4. En Google Drive, abrir una **hoja nativa de Google Sheets** de prueba, pulsar **Compartir**, agregar el `client_email` de la cuenta de servicio con permiso Editor. Compartir solo ese archivo. En organizaciones, la política de compartición externa puede impedirlo.
5. Copiar el identificador de la URL de la hoja. Para `https://docs.google.com/spreadsheets/d/ID_DEL_DOCUMENTO/edit`, el ID es únicamente `ID_DEL_DOCUMENTO`.
6. En Render → Servicio → Environment configurar de forma privada:
   - `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` = contenido completo del JSON de cuenta de servicio (Render no debe copiarlo al repositorio).
   - `GOOGLE_SPREADSHEET_ID` = ID del documento de Google Sheets.
   - `GOOGLE_SHEET_TAB` = `DETALLE DEVOLUCION` (ya viene del Excel original).
   - `TABLE_PROVIDER` = `google_sheets` (el Blueprint ya lo configura).
   - `GOOGLE_SHEETS_TEMPLATE` = `creditos_sole` (el Blueprint lo configura automáticamente).
7. `config/campos.json` ya incluye el formato `creditos_sole` y las siete columnas extraídas del PDF de muestra. El lector verifica números QC en la hoja histórica antes de escribir; la hoja técnica `_CONTROL_PDF` controla documentos procesados con posterioridad.
8. Probar solamente un correo con PDF ficticios y una copia de la hoja. Comprobar que los datos se anexen una vez y que la deduplicación funcione.

No se requiere autorizar una segunda vez el Gmail para que la cuenta de servicio trabaje con Google Sheets. La aplicación conecta **dos identidades independientes** (Gmail OAuth solo lectura y cuenta de servicio con acceso a la hoja compartida). Esto evita otorgar permiso amplio sobre todo Google Drive.

**Atención:** si el destino es un Excel `.xlsx` subido a Google Drive (en lugar de una hoja nativa de Google Sheets), esta integración no será compatible y habrá que implementar otra ruta de escritura. No transformar el Excel sin autorización del dueño.

En Render Free el token Gmail guardado en disco es efímero; puede desaparecer al reiniciarse la instancia. No usar documentos reales sensibles en un plan de pruebas sin aprobación. Para producción, usar alojamiento aprobado, almacenamiento de tokens seguro y persistente, auditoría y respaldos.

**No conectar carpetas privadas de Google Drive ni procesar información empresarial confidencial en Render Free sin permiso expreso del cliente y de TI.**

## Verificación y enlaces

- Código: https://github.com/Sebastian1047/deputador_de_pdfs
- Blueprint: `render.yaml` en rama `main`
- Dashboard: https://dashboard.render.com/
- Documentación oficial: https://render.com/docs/infrastructure-as-code


## Verificación segura previa a importación (v0.8.3)

Después de guardar las variables de la hoja en Render, haga un despliegue manual del commit actualizado. En el panel autenticado:

1. Use **Verificar Google Sheets (solo lectura)**. Esta acción prueba permisos de consulta y esquema, pero no guarda nada en la hoja de Drive.
2. Busque el correo con 39 adjuntos.
3. Use **Probar 1 PDF** en **solo un mensaje**; puede guardar una única fila nueva en el archivo de pruebas. Si el documento ya está en el histórico, registrará un duplicado y no escribirá filas.
4. Compare la fila nueva con el PDF original y compruebe si el resumen `SUMA TOTAL` incluye el dato.
5. Solo después de validar, considere **Procesar todos**. El envío completo podría contener PDF de formatos diferentes y el contador de errores indica cuáles no pudieron incorporarse (sin registrar sus datos privados en logs).

El flujo de prueba no puede demostrar escritura en Google Sheets sin ejecutar la importación de un documento; la validación previa es estrictamente de lectura.

## Seleccionar año y mes en la aplicación (v0.8.4)

En **1. Buscar correos con PDF** seleccione el **año** y el **mes** del crédito (por defecto el mes anterior). Pulse **Buscar correos**. La aplicación genera internamente `subject:"CREDITOS SEPTIEMBRE JN"` o el mes elegido, además de `has:attachment filename:pdf` y un intervalo desde el primer día del mes hasta el primer día de dos meses después. Esto contempla informes enviados en el mes siguiente sin mostrar el año equivalente anterior. Ejemplo: **Septiembre de 2026** consulta mensajes recibidos en septiembre/octubre de 2026; **Diciembre de 2026** incluye enero de 2027.

Los botones **Verificar Google Sheets**, **Probar 1 PDF** y **Procesar todos** conservan su comportamiento actual; no cambie las variables de entorno ni el JSON OAuth al desplegar esta actualización.
