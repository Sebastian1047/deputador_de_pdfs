"""Pruebas sin conexión: selección inequívoca de un solo correo de Gmail."""
import base64

import fitz
import pytest

from depurador.core import Campo, procesar
from depurador.proveedores import GmailMensajeSeleccionado, GmailReader


def pdf_ejemplo(numero: int) -> bytes:
    documento = fitz.open()
    hoja = documento.new_page()
    hoja.insert_text((40, 80), f"Documento: {numero}")
    contenido = documento.tobytes()
    documento.close()
    return contenido


def contenido_base64(contenido: bytes) -> str:
    return base64.urlsafe_b64encode(contenido).decode("ascii").rstrip("=")


def correo(id, numero, cantidad=1, con_pdf=True):
    partes = []
    for i in range(cantidad):
        partes.append({
            "filename": f"reporte-{numero}-{i}.pdf" if con_pdf else f"nota-{i}.txt",
            "partId": str(i + 1),
            "mimeType": "application/pdf" if con_pdf else "text/plain",
            "body": {"attachmentId": f"adjunto-{id}-{i}"},
        })
    return {
        "id": id,
        "internalDate": "1780000000000",
        "payload": {
            "headers": [
                {"name": "From", "value": f"Remitente {id} <test@example.com>"},
                {"name": "Subject", "value": f"Reporte {numero}"},
            ],
            "mimeType": "multipart/mixed",
            "parts": partes,
        },
    }


class Respuesta:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self.data


class MensajesFalsos:
    def __init__(self, correos):
        self.correos = correos
        self.buscados = []
        self.abiertos = []
        self.adjuntos_solicitados = []
        self._numero = {
            "aaa": 101,
            "bbb": 202,
            "ccc": 303,
        }

    def list(self, **kwargs):
        self.buscados.append(kwargs)
        return Respuesta({"messages": [{"id": id} for id in self.correos]})

    def get(self, **kwargs):
        self.abiertos.append(kwargs["id"])
        return Respuesta(self.correos[kwargs["id"]])

    def attachments(self):
        return self

    def get_attachment_not_used(self, **kwargs):
        raise AssertionError("No debería descargar adjuntos durante la búsqueda")


class AdjuntosFalsos:
    def __init__(self, servicio):
        self.servicio = servicio

    def get(self, **kwargs):
        self.servicio.adjuntos_solicitados.append(kwargs)
        numero = self.servicio._numero[kwargs["messageId"]]
        return Respuesta({"data": contenido_base64(pdf_ejemplo(numero))})


class ServicioFalso:
    def __init__(self, correos):
        self.mensajes = MensajesFalsos(correos)
        # methods chained by GmailReader: servicio.users().messages().attachments().get()
        self.adjuntos = AdjuntosFalsos(self.mensajes)

    def users(self):
        return self

    def messages(self):
        return self.mensajes


def preparar(monkeypatch, con_tercero=False):
    correos = {
        "aaa": correo("aaa", 101, cantidad=2),
        "bbb": correo("bbb", 202, cantidad=1),
    }
    if con_tercero:
        correos["ccc"] = correo("ccc", 303, con_pdf=False)
    servicio = ServicioFalso(correos)
    monkeypatch.setattr(servicio.mensajes, "attachments", lambda: servicio.adjuntos)
    return servicio


def test_buscar_lista_sin_descargar_archivos(monkeypatch):
    servicio = preparar(monkeypatch, con_tercero=True)
    lector = GmailReader(servicio, "filename:pdf", max_correos=15)

    resultados = lector.listar_correos()

    assert len(resultados) == 2
    assert [item.id for item in resultados] == ["aaa", "bbb"]
    assert [item.cantidad_pdf for item in resultados] == [2, 1]
    assert resultados[0].asunto == "Reporte 101"
    assert "Remitente aaa" in resultados[0].remitente
    assert resultados[0].fecha
    assert servicio.mensajes.buscados[0]["q"] == "filename:pdf"
    assert servicio.mensajes.adjuntos_solicitados == []


def test_solo_descarga_y_procesa_el_correo_elegido(monkeypatch):
    servicio = preparar(monkeypatch)
    lector = GmailReader(servicio, "filename:pdf")
    seleccionado = GmailMensajeSeleccionado(lector, "bbb")
    class Tabla:
        def __init__(self):
            self.filas = []
        def claves_existentes(self, campos):
            return set()
        def agregar(self, clave, fecha, datos):
            self.filas.append((clave, datos))
    tabla = Tabla()
    resumen = procesar(
        seleccionado, tabla,
        [Campo("numero", r"Documento:\s*(\d+)", True)]
    )
    assert resumen == {"encontrados": 1, "agregados": 1, "duplicados": 0, "errores": 0}
    assert len(tabla.filas) == 1
    assert tabla.filas[0][0] == "gmail:bbb:1"
    assert tabla.filas[0][1] == ["202"]
    assert servicio.mensajes.buscados == []
    assert servicio.mensajes.abiertos == ["bbb"]
    assert {obj["messageId"] for obj in servicio.mensajes.adjuntos_solicitados} == {"bbb"}


def test_rechaza_identificador_invalido(monkeypatch):
    servicio = preparar(monkeypatch)
    lector = GmailReader(servicio, "filename:pdf")
    with pytest.raises(ValueError, match="válido"):
        GmailMensajeSeleccionado(lector, "bbb OR aaa")
    assert servicio.mensajes.buscados == []
    assert servicio.mensajes.abiertos == []
