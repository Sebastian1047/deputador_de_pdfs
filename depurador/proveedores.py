"""Adaptadores intercambiables de entrada Gmail y salida Google Sheets."""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from .core import AdjuntoPDF, Campo


def _partes_recursivas(parte: dict) -> Iterable[dict]:
    if parte.get("parts"):
        for hijo in parte["parts"]:
            yield from _partes_recursivas(hijo)
    else:
        yield parte


def _decodificar(cadena: str) -> bytes:
    return base64.urlsafe_b64decode(cadena + "=" * (-len(cadena) % 4))


@dataclass(frozen=True)
class CorreoResumen:
    """Metadatos visibles solo en la aplicación local; no descarga adjuntos."""
    id: str
    fecha: str
    remitente: str
    asunto: str
    cantidad_pdf: int


def _es_pdf(parte: dict) -> bool:
    nombre = parte.get("filename", "")
    tipo = parte.get("mimeType", "")
    return nombre.lower().endswith(".pdf") or tipo == "application/pdf"


class GmailReader:
    def __init__(self, servicio, consulta: str, max_correos: int = 250):
        self.servicio = servicio
        self.consulta = consulta
        self.max_correos = max_correos

    def _referencias(self) -> Iterable[str]:
        """Buscar IDs sin descargar adjuntos, respetando el filtro y el límite."""
        mensajes = self.servicio.users().messages()
        vistos = 0
        pagina = None
        while vistos < self.max_correos:
            argumentos = {
                "userId": "me", "q": self.consulta,
                "maxResults": min(100, self.max_correos - vistos),
            }
            if pagina:
                argumentos["pageToken"] = pagina
            listado = mensajes.list(**argumentos).execute()
            referencias = listado.get("messages", [])
            if not referencias:
                break
            for referencia in referencias:
                vistos += 1
                yield referencia["id"]
            pagina = listado.get("nextPageToken")
            if not pagina:
                break

    def listar_correos(self) -> list[CorreoResumen]:
        """Mostrar mensajes con PDF en la bandeja, sin bajar ningún archivo."""
        mensajes = self.servicio.users().messages()
        resultado = []
        for identificador in self._referencias():
            mensaje = mensajes.get(userId="me", id=identificador, format="full").execute()
            payload = mensaje.get("payload", {})
            cantidad = sum(_es_pdf(parte) for parte in _partes_recursivas(payload))
            if not cantidad:
                continue
            cabeceras = {
                h.get("name", "").lower(): h.get("value", "")
                for h in payload.get("headers", [])
            }
            try:
                sello = int(mensaje.get("internalDate", 0)) / 1000
                fecha = datetime.fromtimestamp(sello, tz=timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
            except (OverflowError, OSError, TypeError, ValueError):
                fecha = "Sin fecha"
            resultado.append(CorreoResumen(
                id=identificador,
                fecha=fecha,
                remitente=cabeceras.get("from", "Desconocido")[:140],
                asunto=cabeceras.get("subject", "(Sin asunto)")[:250],
                cantidad_pdf=cantidad,
            ))
        return resultado

    def adjuntos_pdf(self, mensaje_id: str | None = None) -> Iterable[AdjuntoPDF]:
        """Si se entrega mensaje_id, procesa SOLO ese mensaje, nunca la búsqueda entera."""
        mensajes = self.servicio.users().messages()
        if mensaje_id is not None:
            if not re.fullmatch(r"[A-Za-z0-9]+", mensaje_id):
                raise ValueError("Identificador de Gmail inválido")
            identificadores = [mensaje_id]
        else:
            identificadores = self._referencias()

        for identificador in identificadores:
            detalle = mensajes.get(userId="me", id=identificador, format="full").execute()
            for indice, parte in enumerate(_partes_recursivas(detalle.get("payload", {}))):
                if not _es_pdf(parte):
                    continue
                cuerpo = parte.get("body", {})
                if cuerpo.get("data"):
                    datos = cuerpo["data"]
                elif cuerpo.get("attachmentId"):
                    respuesta = mensajes.attachments().get(
                        userId="me", messageId=identificador, id=cuerpo["attachmentId"]
                    ).execute()
                    datos = respuesta.get("data", "")
                else:
                    continue
                contenido = _decodificar(datos)
                if not contenido.startswith(b"%PDF"):
                    continue
                clave = f"gmail:{identificador}:{parte.get('partId', indice)}"
                yield AdjuntoPDF(clave=clave, contenido=contenido)


class GmailMensajeSeleccionado:
    """Fuente segura para la versión escritorio: un correo previamente elegido."""
    def __init__(self, lector: GmailReader, mensaje_id: str):
        if not re.fullmatch(r"[A-Za-z0-9]+", mensaje_id):
            raise ValueError("Seleccione un correo válido")
        self.lector = lector
        self.mensaje_id = mensaje_id

    def adjuntos_pdf(self) -> Iterable[AdjuntoPDF]:
        return self.lector.adjuntos_pdf(mensaje_id=self.mensaje_id)

class GoogleSheetsWriter:
    """Escribe en una hoja NATIVA de Google Sheets ubicada en Drive."""
    def __init__(self, servicio, id_hoja: str, pestana: str = "Registros"):
        self.servicio = servicio
        self.id_hoja = id_hoja
        self.pestana = pestana
        self.valores = servicio.spreadsheets().values()

    def _rango(self, intervalo: str) -> str:
        nombre = self.pestana.replace("'", "''")
        return f"'{nombre}'!{intervalo}"

    def claves_existentes(self, campos: Sequence[Campo]) -> set[str]:
        esperados = ["document_key", "processed_utc"] + [campo.nombre for campo in campos]
        respuesta = self.valores.get(
            spreadsheetId=self.id_hoja, range=self._rango("1:1")
        ).execute()
        existentes = respuesta.get("values", [])
        if not existentes:
            self.valores.update(
                spreadsheetId=self.id_hoja, range=self._rango("A1"),
                valueInputOption="RAW", body={"values": [esperados]}
            ).execute()
        elif existentes[0] != esperados:
            raise ValueError("Las columnas de la hoja no coinciden con config/campos.json")
        respuesta = self.valores.get(
            spreadsheetId=self.id_hoja, range=self._rango("A2:A")
        ).execute()
        return {fila[0] for fila in respuesta.get("values", []) if fila}

    def agregar(self, clave: str, fecha_utc: str, datos: Sequence[str]) -> None:
        # RAW evita que texto del PDF se interprete como fórmula.
        self.valores.append(
            spreadsheetId=self.id_hoja, range=self._rango("A1"),
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [[clave, fecha_utc, *datos]]},
        ).execute()


def crear_servicios_google():
    """OAuth de usuario: el token de renovación se configura como secreto."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    requeridas = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
    faltantes = [nombre for nombre in requeridas if not os.getenv(nombre)]
    if faltantes:
        raise RuntimeError("Faltan secretos de conexión Google: " + ", ".join(faltantes))
    credenciales = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )
    gmail = build("gmail", "v1", credentials=credenciales, cache_discovery=False)
    sheets = build("sheets", "v4", credentials=credenciales, cache_discovery=False)
    return gmail, sheets
