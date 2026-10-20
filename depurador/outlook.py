"""Microsoft 365 / Exchange Online via Microsoft Graph (solo lectura de correos).

No funciona con Exchange local sin Graph. Las credenciales se guardan en Windows
Server, nunca en el código ni en los navegadores.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Iterable
from urllib.parse import quote, unquote, urlsplit

from .core import AdjuntoPDF
from .proveedores import CorreoResumen

GRAPH = "https://graph.microsoft.com/v1.0"
MAX_ADJUNTO_BYTES = 25 * 1024 * 1024


class GraphClient:
    """Autenticación app-only; requiere aprobación de TI en Microsoft Entra."""

    def __init__(self, tenant: str, client_id: str, client_secret: str, session=None):
        import msal
        import requests

        if not re.fullmatch(r"[A-Za-z0-9.-]{2,128}", tenant):
            raise ValueError("MS_TENANT_ID inválido")
        self.auth = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant}",
            client_credential=client_secret,
        )
        self.http = session or requests.Session()

    def get(self, url: str, params: dict | None = None, *, raw: bool = False):
        """Nunca enviar el token a dominios externos ni seguir redirecciones."""
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "graph.microsoft.com"
            or not parsed.path.startswith("/v1.0/users/")
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Dirección Microsoft Graph no permitida")
        resultado = self.auth.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        token = resultado.get("access_token")
        if not token:
            raise RuntimeError("Microsoft no autorizó la lectura del buzón")
        response = self.http.get(
            url,
            params=params,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/json" if not raw else "application/pdf"},
            timeout=(10, 90),
            allow_redirects=False,
        )
        # No incluir cuerpos del error: pueden contener detalles del tenant.
        if response.status_code != 200:
            raise RuntimeError(f"Solicitud Microsoft Graph falló (HTTP {response.status_code})")
        if raw:
            if len(response.content) > MAX_ADJUNTO_BYTES:
                raise ValueError("Adjunto supera el máximo permitido")
            return response.content
        return response.json()


class OutlookReader:
    """Enumerar correos con PDF y abrir solamente un mensaje elegido."""

    def __init__(self, client, mailbox: str, consulta: str = "", max_correos: int = 100):
        mailbox = mailbox.strip()
        if not mailbox or len(mailbox) > 254 or "/" in mailbox or "?" in mailbox:
            raise ValueError("Debe configurar MS_MAILBOX válido")
        self.client = client
        self.mailbox = mailbox
        self.base = f"{GRAPH}/users/{quote(mailbox, safe='')}/messages"
        self.consulta = consulta.strip()
        if len(self.consulta) > 500:
            raise ValueError("Filtro demasiado largo")
        self.max_correos = min(250, max(1, int(max_correos)))

    def _paginar(self, url: str, params: dict | None = None) -> Iterable[dict]:
        paginas = 0
        while url:
            parsed = urlsplit(url)
            # El buzón es fijo. Nunca seguir un nextLink a otro usuario ni dominio.
            ruta = unquote(parsed.path)
            prefijo = f"/v1.0/users/{self.mailbox}/messages"
            if (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
                or not (ruta == prefijo or ruta.startswith(prefijo + "/"))):
                raise ValueError("Paginación de Microsoft Graph no autorizada")
            respuesta = self.client.get(url, params=params)
            if not isinstance(respuesta, dict):
                raise ValueError("Respuesta inválida de Microsoft Graph")
            yield from respuesta.get("value", [])
            url = respuesta.get("@odata.nextLink")
            params = None  # nextLink conserva los parámetros de Graph
            paginas += 1
            if paginas >= 20 and url:
                raise ValueError("Se excedió el límite de paginación")

    def _adjuntos(self, mensaje_id: str) -> Iterable[dict]:
        url = f"{self.base}/{quote(mensaje_id, safe='')}/attachments"
        for item in self._paginar(url, {"$top": 100}):
            tipo = item.get("@odata.type", "#microsoft.graph.fileAttachment")
            if tipo != "#microsoft.graph.fileAttachment" or item.get("isInline"):
                continue
            nombre = str(item.get("name") or "")
            if nombre.lower().endswith(".pdf") or item.get("contentType") == "application/pdf":
                yield item

    def listar_correos(self) -> list[CorreoResumen]:
        # La búsqueda de Graph usa KQL: "from:...", "subject:..." o texto libre.
        # Sin filtro explícito se buscan mensajes con adjuntos.
        buscar = self.consulta or "hasAttachments:true"
        parametros = {
            "$search": '"' + buscar.replace('"', "") + '"',
            "$top": min(50, self.max_correos),
            "$select": "id,subject,from,receivedDateTime,hasAttachments",
        }
        resultado = []
        examinados = 0
        for item in self._paginar(self.base, parametros):
            if examinados >= self.max_correos:
                break
            examinados += 1
            if not item.get("hasAttachments"):
                continue
            mensaje_id = item.get("id")
            if not isinstance(mensaje_id, str) or not mensaje_id:
                continue
            cantidad = sum(1 for _ in self._adjuntos(mensaje_id))
            if not cantidad:
                continue
            remitente = (((item.get("from") or {}).get("emailAddress") or {})
                         .get("address") or "Desconocido")
            fecha_original = item.get("receivedDateTime") or ""
            try:
                fecha = datetime.fromisoformat(fecha_original.replace("Z", "+00:00"))
                fecha = fecha.astimezone().strftime("%d/%m/%Y %H:%M")
            except (TypeError, ValueError, OverflowError):
                fecha = "Sin fecha"
            resultado.append(CorreoResumen(
                id=mensaje_id,
                fecha=fecha,
                remitente=str(remitente)[:140],
                asunto=str(item.get("subject") or "(Sin asunto)")[:250],
                cantidad_pdf=cantidad,
            ))
        return resultado

    def adjuntos_pdf(self, mensaje_id: str) -> Iterable[AdjuntoPDF]:
        """Solo lee adjuntos del mensaje indicado, uno por uno, en memoria."""
        if not isinstance(mensaje_id, str) or not (1 <= len(mensaje_id) <= 1024):
            raise ValueError("Identificador de Outlook inválido")
        for adjunto in self._adjuntos(mensaje_id):
            if int(adjunto.get("size") or 0) > MAX_ADJUNTO_BYTES:
                raise ValueError("PDF demasiado grande para procesar")
            adjunto_id = adjunto.get("id")
            if not adjunto_id:
                continue
            url = (f"{self.base}/{quote(mensaje_id, safe='')}/attachments/"
                   f"{quote(adjunto_id, safe='')}/$value")
            contenido = self.client.get(url, raw=True)
            if not contenido.startswith(b"%PDF"):
                continue
            yield AdjuntoPDF(
                clave=f"outlook:{self.mailbox}:{mensaje_id}:{adjunto_id}",
                contenido=contenido,
            )


class OutlookMensajeSeleccionado:
    """Fuente que implementa el protocolo del motor Python compartido."""

    def __init__(self, lector: OutlookReader, mensaje_id: str):
        self.lector = lector
        self.mensaje_id = mensaje_id

    def adjuntos_pdf(self) -> Iterable[AdjuntoPDF]:
        return self.lector.adjuntos_pdf(self.mensaje_id)


def crear_cliente_outlook():
    requeridas = ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET", "MS_MAILBOX")
    faltan = [clave for clave in requeridas if not os.getenv(clave)]
    if faltan:
        raise RuntimeError("Faltan variables Outlook: " + ", ".join(faltan))
    return GraphClient(
        os.environ["MS_TENANT_ID"],
        os.environ["MS_CLIENT_ID"],
        os.environ["MS_CLIENT_SECRET"],
    )
