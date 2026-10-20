# Depurador de PDF · v0.5.2

**Aplicación web Python para Windows Server**. El usuario inicia sesión en el navegador de la empresa, busca correos en Outlook empresarial, escoge un correo específico, procesa sus PDF adjuntos **en memoria** y agrega datos a **Excel Online** en Microsoft 365.

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
