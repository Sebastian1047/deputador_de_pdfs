"""Acceso de solo lectura a Gmail y lectura de PDF adjuntos en memoria.

Configuración local:
- Colocar el archivo OAuth de Google Cloud como credentials.json en la raíz.
- Ejecutar la aplicación y autorizar el acceso en el navegador.
- token.json se genera localmente y NO debe subirse a GitHub.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRET_FILE = ROOT / "credentials.json"
TOKEN_FILE = ROOT / "token.json"


def get_gmail_service():
    """Autoriza al usuario y devuelve el cliente de Gmail API."""
    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError(
            "No se encontró credentials.json. Configura un cliente OAuth "
            "en Google Cloud y coloca el archivo en la raíz del proyecto."
        )

    credentials = None
    if TOKEN_FILE.exists():
        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE), SCOPES
        )

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE), SCOPES
            )
            credentials = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _walk_parts(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Recorre las partes MIME de un correo, incluidas las anidadas."""
    for part in payload.get("parts", []):
        yield part
        yield from _walk_parts(part)


def find_pdf_attachments(service, query: str = "has:attachment filename:pdf",
                         max_messages: int = 100) -> list[dict[str, Any]]:
    """Lista los PDF adjuntos de los correos que coinciden con una búsqueda.

    Devuelve metadatos y el ID del adjunto; todavía no descarga ni procesa
    el contenido. max_messages limita los mensajes revisados en esta llamada.
    """
    response = service.users().messages().list(
        userId="me", q=query, maxResults=min(max_messages, 500)
    ).execute()

    found: list[dict[str, Any]] = []
    for message_ref in response.get("messages", []):
        message = service.users().messages().get(
            userId="me", id=message_ref["id"], format="full"
        ).execute()
        for part in _walk_parts(message.get("payload", {})):
            filename = part.get("filename", "")
            body = part.get("body", {})
            if filename.lower().endswith(".pdf") and body.get("attachmentId"):
                found.append({
                    "message_id": message["id"],
                    "attachment_id": body["attachmentId"],
                    "filename": filename,
                    "mime_type": part.get("mimeType", "application/pdf"),
                })
    return found


def read_attachment_bytes(service, message_id: str, attachment_id: str) -> bytes:
    """Lee el contenido de un adjunto en memoria; no crea un archivo PDF."""
    attachment = service.users().messages().attachments().get(
        userId="me", messageId=message_id, id=attachment_id
    ).execute()
    data = attachment.get("data", "")
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
