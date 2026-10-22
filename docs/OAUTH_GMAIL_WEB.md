# OAuth Gmail para la aplicación web (celular y computador)

**Estado:** Código preparado en la rama main. Todavía no hay aplicación en Windows Server ni dirección HTTPS asignada. Por tanto, Google Cloud debe conservar el cliente OAuth web creado, pero **sin URL de retorno inventada**. GitHub Pages solo puede mostrar una demo con datos ficticios.

## Lo que ya se hizo

- Gmail API está habilitada en el proyecto de Google Cloud.
- La pantalla de consentimiento está configurada con tipo External, usuario de prueba y alcance de solo lectura gmail.readonly.
- Existe un cliente OAuth de tipo **Aplicación web**. Conservar su JSON secreto en una carpeta privada; no compartir secretos ni tokens.
- El repositorio ya incluye POST /oauth/google/conectar y GET /oauth/google/callback en Flask. Solo un usuario del panel web autenticado puede iniciar autorización.
- Antes de guardar la autorización, la app comprueba que el correo autorizado coincide con GMAIL_EXPECTED_EMAIL. Ese dato se fija exclusivamente en la configuración privada de Windows Server.

## Cuando se disponga de Windows Server y HTTPS

1. TI autorizará el despliegue Python/Waitress en Windows Server con IIS de proxy inverso HTTPS.
2. Definir un dominio HTTPS que sea accesible desde el navegador en los dispositivos permitidos (LAN o VPN, incluido móvil). Para producción Google requiere HTTPS y un nombre de dominio válido; no usar una IP interna como URI de redirección.
3. La URI de redirección real debe terminar **exactamente** en:
   
       /oauth/google/callback

   Ejemplo solamente (NO copiar si no es un dominio propio):

       https://depurador.ejemplo.com/oauth/google/callback

4. En **Google Cloud → Google Auth Platform → Clientes → Depurador PDF JN - Web**, editar el cliente OAuth. En **URIs de redireccionamiento autorizados**, agregar la URI HTTPS exacta del servidor. **Orígenes autorizados de JavaScript** pueden quedar vacíos: la app usa intercambio de códigos en Python.
5. TI descargará el JSON de tipo web en una carpeta restringida del Windows Server. El secreto NO se agrega en código, documentos públicos, páginas estáticas ni chats.
6. Configurar de forma privada en el servidor estas variables:

       MAIL_PROVIDER=gmail
       TABLE_PROVIDER=excel_online
       GMAIL_OAUTH_CLIENT_FILE=C:\ProgramData\DepuradorPDF\secrets\oauth_web.json
       GMAIL_REDIRECT_URI=https://depurador.ejemplo.com/oauth/google/callback
       GMAIL_EXPECTED_EMAIL=<correo de Gmail autorizado>
       GMAIL_TOKEN_FILE=C:\ProgramData\DepuradorPDF\secrets\token_gmail.json

   La URI es ilustrativa. Debe reemplazarse con la que TI configure y que se registrará exactamente igual en Google Cloud. GMAIL_EXPECTED_EMAIL se define allí, no en el código público.
7. Al entrar al panel web privado con usuario y contraseña, aparecerá el botón **Autorizar Gmail con Google**. Su propietario hará clic, iniciará sesión directamente en Google, concederá acceso de solo lectura y regresará a la aplicación.
8. El callback comprobará el estado de seguridad (máximo 10 minutos), la cuenta autorizada y el alcance solicitado. Guardará el token con exclusividad en la carpeta privada. Para renovar un token anterior, TI deberá retirarlo de manera controlada antes de repetir el flujo.
9. El botón **Buscar correos** podrá listar los mensajes Gmail que incluyan PDF. Para agregar registros al Excel Online del cliente habrá que autorizar por separado Microsoft Graph y validar las columnas a partir de un PDF de ejemplo.

### Desarrollo local sin Windows Server

Si se ejecuta un servidor Python de pruebas autorizado en el propio equipo que tiene el navegador, Google permite un redireccionamiento local, por ejemplo:

    http://localhost:8080/oauth/google/callback

Este valor también debe añadirse al cliente OAuth web en Google Cloud y usarse como GMAIL_REDIRECT_URI. Es una excepción **solo para localhost**. No sirve como dirección para usuarios en otros computadores o celulares, y **no funciona desde GitHub Pages**.

## Seguridad y limitaciones

- OAuth de Google utiliza token de acceso limitado a gmail.readonly; jamás pide la contraseña en el panel.
- El archivo OAuth del cliente web y el token resultante no deben ubicarse dentro de la raíz pública del repositorio ni compartirse.
- Un token de renovación de Gmail con app externa en estado Testing puede caducar tras aproximadamente 7 días. No se debe prometer que funcionará indefinidamente sin atender los requisitos de publicación y verificación de Google.
- No habilitar OAuth en sitios públicos estáticos ni exponer la aplicación Python en Internet sin controles, TLS, gestión de secretos y supervisión de TI.
- El servidor podrá atender navegadores en móviles y computadores mediante la misma interfaz; las personas no tienen que instalar Python en sus dispositivos.
- **El correo Gmail real y sus PDF siguen sin haberse conectado o consultado**. El código ha sido probado solamente con servicios ficticios.

Documentación oficial: https://developers.google.com/identity/protocols/oauth2/web-server
