# Desplegar la aplicación web en Render Free (pruebas)

**Estado de este proyecto:** el código y `render.yaml` están preparados, pero **todavía no existe una instancia Render creada ni una URL pública verificada**. Para crearla es necesario autorizar el acceso a la cuenta Render y vincular el repositorio GitHub. Nunca revelar claves ni tokens en el chat o en GitHub.

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

## Paso 3: análisis de PDF y Excel Online

Para procesar datos reales no basta con tener Gmail conectado:
1. Definir `config/campos.json` con los nombres y patrones a extraer de una muestra de PDF anonimizada.
2. Autorizar por separado el acceso al Excel empresarial de Microsoft 365 / OneDrive.
3. Trabajar primero sobre una copia del libro Excel sin datos sensibles y verificar que se mantengan fórmulas/estilos y que no haya ediciones concurrentes.
4. Para un entorno corporativo definitivo, usar Windows Server autorizado o una infraestructura de nube aprobada con un **almacén de secretos duradero**, auditoría, controles de acceso y respaldo.

**No conectar OneDrive empresarial real ni procesar información empresarial confidencial en Render Free sin permiso expreso del cliente y de TI.**

## Verificación y enlaces

- Código: https://github.com/Sebastian1047/deputador_de_pdfs
- Blueprint: `render.yaml` en rama `main`
- Dashboard: https://dashboard.render.com/
- Documentación oficial: https://render.com/docs/infrastructure-as-code
