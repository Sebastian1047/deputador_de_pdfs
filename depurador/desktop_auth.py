"""OAuth para aplicaciones instaladas. El navegador autoriza, el token queda SOLO en el equipo."""
from __future__ import annotations

import os
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]


def autenticar(oauth_json: str, archivo_token: Path, cambiar_cuenta: bool = False):
    """Retorna credenciales autorizadas. No incorpora secretos en el ejecutable."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    cliente = Path(oauth_json).expanduser()
    if not cliente.is_file():
        raise FileNotFoundError("Seleccione el archivo OAuth JSON de Google Cloud")
    credenciales = None
    if archivo_token.exists() and not cambiar_cuenta:
        credenciales = Credentials.from_authorized_user_file(str(archivo_token), SCOPES)
        if credenciales and credenciales.expired and credenciales.refresh_token:
            credenciales.refresh(Request())
    if not credenciales or not credenciales.valid:
        flujo = InstalledAppFlow.from_client_secrets_file(str(cliente), SCOPES)
        credenciales = flujo.run_local_server(
            host="localhost",
            port=0,
            open_browser=True,
            access_type="offline",
            prompt="consent",
        )
    if not credenciales.valid:
        raise RuntimeError("No se pudo completar la autorización de Google")
    archivo_token.parent.mkdir(parents=True, exist_ok=True)
    archivo_token.write_text(credenciales.to_json(), encoding="utf-8")
    if os.name != "nt":
        archivo_token.chmod(0o600)
    return credenciales


def servicios(credenciales):
    from googleapiclient.discovery import build

    return (
        build("gmail", "v1", credentials=credenciales, cache_discovery=False),
        build("sheets", "v4", credentials=credenciales, cache_discovery=False),
    )
