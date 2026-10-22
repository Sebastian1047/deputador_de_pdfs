"""Autorización inicial de Gmail personal para el servidor web privado.

Ejecutar la autorización una sola vez desde una sesión interactiva con navegador
en el equipo autorizado (por ejemplo, una sesión de escritorio remoto en Windows
Server). El token contiene información sensible y jamás debe subir a GitHub.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SCOPES = [GMAIL_SCOPE]


def _token_path(value: str | os.PathLike[str]) -> Path:
    if not value:
        raise ValueError("Configure GMAIL_TOKEN_FILE con ruta absoluta y protegida")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("GMAIL_TOKEN_FILE debe ser una ruta absoluta")
    return path


def _verificar_archivo(path: Path):
    if not path.is_file():
        raise FileNotFoundError("No existe el archivo de autorización Gmail en el servidor")
    if path.stat().st_size > 32 * 1024:
        raise ValueError("El archivo del token Gmail supera el tamaño permitido")


def cargar_credenciales(ruta_token: str | os.PathLike[str]):
    """Carga un token previamente autorizado sin solicitar nuevos permisos."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token = _token_path(ruta_token)
    _verificar_archivo(token)
    config = json.loads(token.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Archivo de credenciales Gmail no válido")
    if not config.get("refresh_token"):
        raise RuntimeError("La autorización de Gmail debe incluir token de renovación")
    scopes = set(config.get("scopes") or [])
    if GMAIL_SCOPE not in scopes:
        raise ValueError("El token debe tener permiso gmail.readonly")
    if any(s != GMAIL_SCOPE for s in scopes):
        raise ValueError("Use un token Gmail solo de lectura, sin permisos adicionales")
    credenciales = Credentials.from_authorized_user_info(config, scopes=GMAIL_SCOPES)
    if not credenciales.valid and credenciales.refresh_token:
        credenciales.refresh(Request())
    if not credenciales.valid:
        raise RuntimeError("Debe renovar la autorización de Gmail")
    return credenciales


def crear_servicio_gmail_personal(ruta_token: str | os.PathLike[str]):
    """Devuelve la API Gmail autenticada sin requerir credenciales Microsoft."""
    from googleapiclient.discovery import build

    credenciales = cargar_credenciales(ruta_token)
    return build("gmail", "v1", credentials=credenciales, cache_discovery=False)


def autorizar_gmail(ruta_oauth: str | os.PathLike[str],
                    ruta_token: str | os.PathLike[str]) -> Path:
    """Pide consentimiento en navegador local y guarda un refresh token seguro."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    oauth_file = Path(ruta_oauth).expanduser()
    if not oauth_file.is_absolute() or not oauth_file.is_file():
        raise FileNotFoundError("Indique la ruta absoluta del OAuth JSON descargado de Google")
    if oauth_file.stat().st_size > 64 * 1024:
        raise ValueError("Archivo OAuth JSON demasiado grande")
    meta = json.loads(oauth_file.read_text(encoding="utf-8"))
    if "installed" not in meta or "web" in meta:
        raise ValueError("Descargue un OAuth Client ID de tipo 'Desktop app' para la autorización local")
    ruta = _token_path(ruta_token)
    if ruta.exists():
        raise FileExistsError(
            "Ya hay un token Gmail. Para cambiar cuenta, archive/elimine el token con ayuda de TI"
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(oauth_file), GMAIL_SCOPES)
    credenciales = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
    )
    if not credenciales.valid or not credenciales.refresh_token:
        raise RuntimeError("Gmail no entregó una autorización válida con acceso sin conexión")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Creación exclusiva: evita sobrescribir una autorización que otro proceso creó.
        with ruta.open("x", encoding="utf-8") as handle:
            handle.write(credenciales.to_json())
        if os.name == "nt":
            # Restricción ACL con cuenta de servicio: responsabilidad de TI.
            pass
        else:
            ruta.chmod(0o600)
    except Exception:
        # Si hubo un error al guardar, no revelar el token en el registro.
        raise
    return ruta


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vincular Gmail personal mediante OAuth (solo lectura)"
    )
    parser.add_argument("--authorize", action="store_true", help="Abrir Google para autorizar")
    parser.add_argument("--credentials", help="Ruta absoluta a client_secret_*.json")
    parser.add_argument("--token", default=os.getenv("GMAIL_TOKEN_FILE"),
                        help="Ruta absoluta del token privado en Windows Server")
    args = parser.parse_args()
    if not args.authorize or not args.credentials or not args.token:
        parser.error("Utilice --authorize --credentials RUTA_JSON --token RUTA_TOKEN")
    ruta = autorizar_gmail(args.credentials, args.token)
    print("Gmail personal autorizado correctamente; token guardado en el equipo indicado.")
    print("Ubicación del token:", ruta)
    print("No envíe este archivo ni lo suba a repositorios públicos.")


if __name__ == "__main__":
    main()
