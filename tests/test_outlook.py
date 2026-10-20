"""Microsoft Graph simulado: no solicita accesos reales."""
from urllib.parse import unquote

import pytest

from depurador.outlook import GRAPH, GraphClient, OutlookMensajeSeleccionado, OutlookReader


class ClienteSimulado:
    def __init__(self):
        self.solicitudes = []

    def get(self, url, params=None, raw=False):
        self.solicitudes.append((url, params, raw))
        ruta = unquote(url)
        if ruta.endswith("/attachments/a-1/$value"):
            assert raw
            return b"%PDF-1.7 primer pdf"
        if ruta.endswith("/attachments/b-1/$value"):
            assert raw
            return b"%PDF-1.7 segundo pdf"
        if ruta.endswith("/attachments"):
            if "m-1" in ruta:
                return {"value": [
                    {"id": "a-1", "name": "informe.PDF", "@odata.type": "#microsoft.graph.fileAttachment",
                     "size": 100, "isInline": False},
                    {"id": "a-2", "name": "logo.png", "@odata.type": "#microsoft.graph.fileAttachment",
                     "size": 30, "isInline": True},
                    {"id": "a-3", "name": "externo.pdf", "@odata.type": "#microsoft.graph.referenceAttachment"},
                ]}
            if "m-2" in ruta:
                return {"value": [{"id": "b-1", "name": "otro.pdf",
                                   "@odata.type": "#microsoft.graph.fileAttachment", "size": 100}]}
        if ruta.endswith("/messages"):
            return {"value": [
                {"id": "m-1", "subject": "Reporte de cosecha",
                 "receivedDateTime": "2026-10-20T08:00:00Z",
                 "from": {"emailAddress": {"address": "proveedor@empresa.com"}},
                 "hasAttachments": True},
                {"id": "m-2", "subject": "Otro correo",
                 "receivedDateTime": "2026-10-19T08:00:00Z",
                 "from": {"emailAddress": {"address": "otro@empresa.com"}},
                 "hasAttachments": True},
            ]}
        raise AssertionError("Ruta no esperada: " + url)


def test_lista_outlook_sin_bajar_pdf():
    falso = ClienteSimulado()
    lector = OutlookReader(falso, "reportes@empresa.com", "from:proveedor@empresa.com")
    correos = lector.listar_correos()
    assert len(correos) == 2
    assert correos[0].cantidad_pdf == 1
    assert correos[0].asunto == "Reporte de cosecha"
    assert not any(raw for _, _, raw in falso.solicitudes)
    assert falso.solicitudes[0][1]["$search"] == '"from:proveedor@empresa.com"'


def test_solo_procesa_id_microsoft_elegido():
    falso = ClienteSimulado()
    lector = OutlookReader(falso, "reportes@empresa.com")
    seleccionado = OutlookMensajeSeleccionado(lector, "m-2")
    lista = list(seleccionado.adjuntos_pdf())
    assert len(lista) == 1
    assert lista[0].clave == "outlook:reportes@empresa.com:m-2:b-1"
    assert lista[0].contenido.startswith(b"%PDF")
    assert not any("/m-1/" in url for url, _, _ in falso.solicitudes)
    assert not any(url.endswith("/messages") for url, _, _ in falso.solicitudes)


def test_outlook_acepta_ids_opacos_que_tienen_simbolos():
    class Simulado:
        def get(self, url, params=None, raw=False):
            assert "AB%2B%2F%3D" in url
            return {"value": []}
    lector = OutlookReader(Simulado(), "buzon@empresa.com")
    assert list(lector.adjuntos_pdf("AB+/=")) == []


def test_no_permite_paginacion_fuera_del_buzon():
    class Simulado:
        def get(self, url, params=None, raw=False):
            return {"value": [{"id": "m-1", "hasAttachments": False}],
                    "@odata.nextLink": GRAPH + "/users/otro@empresa.com/messages"}
    lector = OutlookReader(Simulado(), "buzon@empresa.com")
    with pytest.raises(ValueError, match="autorizada"):
        lector.listar_correos()


def test_no_permite_redireccion_del_token_a_otro_dominio():
    cliente = GraphClient.__new__(GraphClient)
    cliente.auth = type("Auth", (), {
        "acquire_token_for_client": lambda self, scopes: {"access_token": "falso"}
    })()
    class NoEnviar:
        def get(self, url, **kwargs):
            raise AssertionError("No enviar tokens al dominio ajeno")
    cliente.http = NoEnviar()
    with pytest.raises(ValueError, match="permitida"):
        cliente.get("https://sitio-falso.example/v1.0/users/buzon/messages")


def test_limite_de_tamano_por_adjunto():
    class Simulado:
        def get(self, url, params=None, raw=False):
            return {"value": [{"id": "uno", "name": "muy-grande.pdf",
                                "size": 100 * 1024 * 1024}]}
    lector = OutlookReader(Simulado(), "reportes@empresa.com")
    with pytest.raises(ValueError, match="demasiado grande"):
        list(lector.adjuntos_pdf("mensaje"))
