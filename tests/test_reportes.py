"""Informes por año/mes y exportación PNG: pruebas sin acceso a datos reales."""
from decimal import Decimal
from io import BytesIO

import pytest
from PIL import Image

from depurador.reportes import crear_imagen_resumen, leer_reporte_sole, numero_es
from depurador import web
from test_web import entorno, iniciar_sesion


class Query:
    def __init__(self, content):
        self.content = content

    def execute(self):
        return self.content


class FakeSheets:
    def __init__(self):
        self.calls = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        self.calls.append(kwargs)
        if "fields" in kwargs:
            return Query({"sheets": [
                {"properties": {"title": "DETALLE DEVOLUCION"}},
                {"properties": {"title": "_CONTROL_PDF"}},
            ]})
        if kwargs["range"] == "'DETALLE DEVOLUCION'!A1:G":
            return Query({"values": [
                ["VARIEDAD", "CAT", "FINCA", "RM", "TOTAL", "QC Inspection", "MES"],
                ["Pom histórico", "PO", "JN", 12, 16.85, 34261, 9],
                ["Mums histórico", "SP", "JN", 9, 25.4, 34444, 9],
                ["Mums marzo", "CR", "JN", 3, 8.70, 34445, 3],
                ["Pom otro año", "PO", "JN", 4, 30, 34261, 9],
            ]})
        if kwargs["range"] == "'_CONTROL_PDF'!C2:D":
            return Query({"values": [
                [34261, 2027],
            ]})
        raise AssertionError(kwargs)


def test_consulta_anio_2026_mantiene_historico_y_mes_correcto():
    service = FakeSheets()
    result = leer_reporte_sole(service, "fake-spreadsheet", "DETALLE DEVOLUCION", 2026, 9)
    assert result["cantidad"] == 2
    assert result["total"] == Decimal("42.25")
    assert {x["qc"] for x in result["registros"]} == {"34261", "34444"}
    assert result["resumen"] == [
        {"cat": "PO", "total": Decimal("16.85")},
        {"cat": "CR", "total": Decimal("0")},
        {"cat": "SP", "total": Decimal("25.4")},
    ]
    assert len(service.calls) == 3
    assert all("spreadsheetId" in c for c in service.calls)


def test_consulta_2027_distingue_qc_reutilizado_en_otro_anio(monkeypatch):
    import depurador.reportes as rp
    monkeypatch.setattr(rp, "validar_periodo", lambda anio, mes: None)
    result = leer_reporte_sole(FakeSheets(), "fake-spreadsheet", "DETALLE DEVOLUCION", 2027, 9)
    assert result["cantidad"] == 1
    assert result["total"] == Decimal("30")
    assert result["registros"][0]["qc"] == "34261"


def test_numero_regional_y_png_corporativo_legible():
    assert numero_es("1919.94") == "1.919,94"
    assert numero_es("11,23") == "11,23"
    report = {
        "nombre_mes": "Septiembre",
        "anio": 2026,
        "cantidad": 39,
        "resumen": [
            {"cat": "PO", "total": Decimal("1919.94")},
            {"cat": "CR", "total": Decimal("11.23")},
            {"cat": "SP", "total": Decimal("79.06")},
        ],
        "total": Decimal("2010.23"),
    }
    png = crear_imagen_resumen(report)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    im = Image.open(BytesIO(png))
    assert im.size == (1440, 1020)


def test_informe_web_solo_autenticado_y_con_tabs_y_descarga(entorno, monkeypatch):
    app, client, _ = entorno
    app.config["GOOGLE_SHEETS_TEMPLATE"] = "creditos_sole"
    app.config["GOOGLE_SHEET_TAB"] = "DETALLE DEVOLUCION"
    assert client.get("/informes/resumen.png?anio=2026&mes=9").status_code == 302
    monkeypatch.setattr(web, "servicio_destino", None, raising=False) if False else None
    # create_app tiene una fábrica de servicios; su segunda instancia falsa
    # se sustituye directamente con FakeSheets para estas pruebas.
    fake = FakeSheets()
    from depurador import web as web_module
    # La app fue creada con service_factory: cambiar la referencia dentro de
    # create_app no es público, por lo que se vuelve a crear una app con fakes.
    from werkzeug.security import generate_password_hash
    app = web_module.create_app({
        "TESTING": True, "SECRET_KEY": "t" * 48,
        "ADMIN_USER": "analista",
        "ADMIN_PASSWORD_HASH": generate_password_hash("contrasena-muy-segura"),
        "SESSION_COOKIE_SECURE": False,
        "MAIL_PROVIDER": "gmail",
        "TABLE_PROVIDER": "google_sheets",
        "GOOGLE_SHEETS_TEMPLATE": "creditos_sole",
        "GOOGLE_SPREADSHEET_ID": "hoja-de-prueba",
        "GOOGLE_SHEET_TAB": "DETALLE DEVOLUCION",
    }, service_factory=lambda: (object(), fake))
    client = app.test_client()
    iniciar_sesion(client)
    detail = client.get("/?anio=2026&mes=9&vista=detalle")
    assert detail.status_code == 200
    assert "Detalle del mes" in detail.text and "Suma total del mes" in detail.text
    assert "Pom histórico" in detail.text
    assert "Mums marzo" not in detail.text
    report = client.get("/?anio=2026&mes=9&vista=resumen")
    assert "42,25" in report.text
    assert "Descargar imagen PNG" in report.text
    png = client.get("/informes/resumen.png?anio=2026&mes=9")
    assert png.status_code == 200
    assert png.mimetype == "image/png"
    assert "attachment" in png.headers["Content-Disposition"]
    assert "Septiembre_2026.png" in png.headers["Content-Disposition"]
    assert png.data.startswith(b"\x89PNG")
    assert client.get("/informes/resumen.png?anio=2001&mes=9").status_code == 400
