"""OAuth web Gmail: el servidor recibe el callback; no se ejecuta en GitHub Pages.

No publica secretos ni tokens. Usa la ruta y URI configurados por el operador del
Windows Server, nunca datos suministrados por un cliente HTTP.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from .gmail_personal import GMAIL_SCOPES, GMAIL_SCOPE, _token_path, validar_cuenta_gmail


def validar_uri_retorno(uri: str) -> str:
    """Exigir URI exacta del callback, HTTPS salvo localhost en desarrollo."""
    if not isinstance(uri, str) or len(uri) > 1024:
        raise ValueError("GMAIL_REDIRECT_URI no es válida")
    parsed = urlsplit(uri)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if (
        not parsed.hostname or parsed.username or parsed.password
        or parsed.query or parsed.fragment
        or parsed.path != "/oauth/google/callback"
        or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))
    ):
        raise ValueError("GMAIL_REDIRECT_URI debe ser HTTPS y terminar en /oauth/google/callback")
    return uri


def crear_flujo_web(cliente_json: str, uri_retorno: str, state: str | None = None,
                    code_verifier: str | None = None):
    """Leer un cliente OAuth tipo web ubicado fuera del repositorio público."""
    from google_auth_oauthlib.flow import Flow

    uri = validar_uri_retorno(uri_retorno)
    if cliente_json.startswith("json:"):
        # Secreto suministrado por la configuración privada del proveedor cloud.
        raw = cliente_json[5:]
        if len(raw) > 64 * 1024:
            raise ValueError("El JSON de OAuth excede el tamaño permitido")
        configuracion = json.loads(raw)
    else:
        archivo = Path(cliente_json).expanduser()
        if not archivo.is_absolute() or not archivo.is_file():
            raise FileNotFoundError("Configure GMAIL_OAUTH_CLIENT_FILE como archivo privado absoluto")
        if archivo.stat().st_size > 64 * 1024:
            raise ValueError("El JSON de OAuth excede el tamaño permitido")
        configuracion = json.loads(archivo.read_text(encoding="utf-8"))
    if not isinstance(configuracion, dict) or "web" not in configuracion or "installed" in configuracion:
        raise ValueError("Las credenciales deben ser de tipo Aplicación web")
    flujo = Flow.from_client_config(
        configuracion, scopes=GMAIL_SCOPES, state=state,
        code_verifier=code_verifier,
    )
    flujo.redirect_uri = uri
    return flujo


def iniciar_oauth(cliente_json: str, uri_retorno: str) -> tuple[str, str, str]:
    flujo = crear_flujo_web(cliente_json, uri_retorno)
    url, estado = flujo.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="false"
    )
    # PKCE exige que el código verificador usado al iniciar se preserve para
    # el callback. La ruta Flask lo guarda en cookie de sesión HttpOnly/Secure.
    if not flujo.code_verifier:
        raise RuntimeError("No fue posible iniciar PKCE con Google")
    return url, estado, flujo.code_verifier


def completar_oauth(cliente_json: str, uri_retorno: str, estado: str,
                    codigo: str, token_file: str, correo_esperado: str,
                    code_verifier: str) -> None:
    """Intercambiar código, verificar cuenta y guardar token solo en servidor."""
    from googleapiclient.discovery import build

    if not estado or not codigo or len(codigo) > 4096:
        raise ValueError("Respuesta OAuth no válida")
    if not isinstance(code_verifier, str) or not re.fullmatch(
        r"[A-Za-z0-9._~-]{43,128}", code_verifier
    ):
        raise ValueError("Código de verificación OAuth inválido")
    if not correo_esperado:
        raise ValueError("Configure GMAIL_EXPECTED_EMAIL antes de autorizar")
    ruta = _token_path(token_file)
    if ruta.exists():
        raise FileExistsError("Ya existe un token Gmail. TI debe retirarlo antes de renovar")
    flujo = crear_flujo_web(
        cliente_json, uri_retorno, state=estado, code_verifier=code_verifier
    )
    flujo.fetch_token(code=codigo)
    credenciales = flujo.credentials
    if not credenciales.valid or not credenciales.refresh_token:
        raise RuntimeError("Google no entregó credenciales de acceso sin conexión")
    if set(credenciales.scopes or []) != {GMAIL_SCOPE}:
        raise PermissionError("Los permisos autorizados no corresponden a Gmail de solo lectura")
    servicio = build("gmail", "v1", credentials=credenciales, cache_discovery=False)
    validar_cuenta_gmail(servicio, correo_esperado)
    contenido = credenciales.to_json()
    if len(contenido) > 32 * 1024:
        raise ValueError("Token de autorización demasiado grande")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # En Windows Server TI debe proteger el directorio mediante ACL NTFS.
    descriptor = os.open(str(ruta), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destino:
            destino.write(contenido)
    except Exception:
        # La aplicación no registra secretos aunque haya errores de escritura.
        try:
            ruta.unlink(missing_ok=True)
        except OSError:
            pass
        raise
