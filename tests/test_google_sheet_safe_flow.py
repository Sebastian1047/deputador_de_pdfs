"""La verificación de la hoja nunca escribe y la prueba procesa solo un PDF."""
from types import SimpleNamespace
from threading import Event
import re

from depurador.google_sheet_checks import comprobar_hoja_creditos
from depurador import web
from test_web import entorno, iniciar_sesion


class Request:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class Service:
    def __init__(self, headers=None, authorized=True):
        self.headers = headers or [
            "VARIEDAD", "CAT", "FINCA", "RM", "TOTAL", "QC Inspection", "MES"
        ]
        self.authorized = authorized
        self.calls = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        self.calls.append(kwargs)
        if not self.authorized:
            raise PermissionError("No access to the sheet")
        if kwargs.get("fields"):
            return Request({"sheets": [{"properties": {"sheetId": 10, "title": "DETALLE DEVOLUCION"}}]})
        return Request({"values": [self.headers]})


def test_read_only_check_does_not_modify_sheet():
    service = Service()
    comprobar_hoja_creditos(service, "TEST-SHEET-ID")
    assert len(service.calls) == 2
    assert all(call["spreadsheetId"] == "TEST-SHEET-ID" for call in service.calls)
    assert service.calls[1]["range"] == "'DETALLE DEVOLUCION'!A1:G1"


def test_read_only_check_fails_wrong_columns():
    import pytest
    service = Service(headers=["INFORMACION EQUIVOCADA"])
    with pytest.raises(ValueError, match="columnas"):
        comprobar_hoja_creditos(service, "TEST-SHEET-ID")


def test_safe_web_flow_uses_explicit_verification_and_single_pdf(entorno, monkeypatch):
    app, client, _ = entorno
    app.config["GOOGLE_SHEETS_TEMPLATE"] = "creditos_sole"
    app.config["GOOGLE_SHEET_TAB"] = "DETALLE DEVOLUCION"
    called = []
    finished = Event()
    monkeypatch.setattr(
        web, "comprobar_hoja_creditos", lambda *args: called.append("verified")
    )

    class DummyReader:
        def __init__(self, *args): pass

        def listar_correos(self):
            return [SimpleNamespace(
                id="mensaje1", fecha="23/10/2026", remitente="Ficticio",
                asunto="CREDITOS SEPTIEMBRE", cantidad_pdf=39
            )]

        def adjuntos_pdf(self, mensaje_id=None):
            for i in range(39):
                yield SimpleNamespace(clave=f"falso:{i}", contenido=b"%PDF-simulado")

    def fake_procesar(origen, destino, campos, extractor=None):
        items = list(origen.adjuntos_pdf())
        called.append(("processed", len(items)))
        finished.set()
        return {"encontrados": len(items), "agregados": len(items),
                "duplicados": 0, "errores": 0}

    monkeypatch.setattr(web, "GmailReader", DummyReader)
    monkeypatch.setattr(web, "GoogleSheetsCreditosWriter", lambda *args: object())
    monkeypatch.setattr(web, "procesar", fake_procesar)

    # Fixture has generic extraction rules, but test only the HTTP safety gate.
    import json
    from pathlib import Path
    f = Path(app.config["PDF_FIELDS_FILE"])
    f.write_text(json.dumps({
        "formato": "creditos_sole",
        "campos": [{"nombre": c} for c in [
            "VARIEDAD", "CAT", "FINCA", "RM", "TOTAL", "QC Inspection", "MES"
        ]]
    }), encoding="utf-8")

    token = iniciar_sesion(client)
    client.post("/buscar", data={"_csrf": token, "filtro": "filename:pdf"})
    assert "Probar 1 PDF" in client.get("/").text
    assert client.post("/procesar", data={
        "_csrf": token, "mensaje_id": "mensaje1", "modo": "uno"
    }).status_code == 302
    assert "Primero use" in client.get("/").text
    assert "processed" not in called

    resp = client.post("/verificar-destino", data={"_csrf": token})
    assert resp.status_code == 302
    assert "verified" in called
    assert "Google Sheets verificado" in client.get("/").text

    assert client.post("/procesar", data={
        "_csrf": token, "mensaje_id": "mensaje1", "modo": "uno"
    }).status_code == 302
    assert finished.wait(3)
    assert ("processed", 1) in called
