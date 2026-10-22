"""Pruebas de plantilla histórica SOLE sin consultar Google ni PDF reales."""
from types import SimpleNamespace

import pytest

from depurador.core import Campo
from depurador.google_drive_sheet import COLUMNAS, CONTROL, GoogleSheetsCreditosWriter, _numero


class Peticion:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class SheetsFake:
    def __init__(self, control_exists=False):
        self.control_exists = control_exists
        self.calls = []
        self.rows = [
            ["VARIEDAD", "CAT", "FINCA", "RM", "TOTAL", "QC Inspection ", "MES"],
        ]

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        if "fields" in kwargs:
            properties = [
                {"properties": {"title": "DETALLE DEVOLUCION", "sheetId": 111}}
            ]
            if self.control_exists:
                properties.append({"properties": {"title": CONTROL, "sheetId": 222}})
            return Peticion({"sheets": properties})
        if kwargs["range"] == "'DETALLE DEVOLUCION'!A1:G1":
            return Peticion({"values": self.rows})
        if kwargs["range"] == "'_CONTROL_PDF'!A2:A":
            return Peticion({"values": [["gmail:id-antiguo:1"]]})
        raise AssertionError("Rango inesperado")

    def batchUpdate(self, **kwargs):
        self.calls.append(("batchUpdate", kwargs))
        if kwargs["body"]["requests"][0].get("addSheet"):
            return Peticion({"replies": [{"addSheet": {"properties": {"sheetId": 222}}}]})
        return Peticion({"replies": [{}] * len(kwargs["body"]["requests"])})

    def update(self, **kwargs):
        self.calls.append(("update", kwargs))
        return Peticion({"updatedRows": 1})


def fields():
    return [Campo(c, r"(.*)") for c in COLUMNAS]


def test_plantilla_verifica_encabezados_y_conserva_historico():
    service = SheetsFake()
    writer = GoogleSheetsCreditosWriter(service, "fake-spreadsheet-id")
    assert writer.claves_existentes(fields()) == {"gmail:id-antiguo:1"}
    assert writer.sheet_id == 111 and writer.control_id == 222
    creates = [call for typ, call in service.calls if typ == "batchUpdate"]
    assert len(creates) == 1
    assert creates[0]["body"]["requests"] == [{
        "addSheet": {"properties": {"title": CONTROL, "hidden": True}}
    }]
    # Ninguna escritura ni limpieza en la pestaña histórica.
    writes = [c for t, c in service.calls if t == "update"]
    assert all("DETALLE DEVOLUCION" not in item["range"] for item in writes)


def test_append_plantilla_y_deduplicacion_es_atomica():
    service = SheetsFake(control_exists=True)
    writer = GoogleSheetsCreditosWriter(service, "fake-id")
    writer.claves_existentes(fields())
    writer.agregar("gmail:nuevo:1", "2026-10-22T18:00:00Z", [
        "=UNSAFE", "PO", "JN", "12", "16,26", "31409", "3"
    ])
    calls = [arg for name, arg in service.calls if name == "batchUpdate"]
    assert len(calls) == 1
    requests = calls[0]["body"]["requests"]
    assert len(requests) == 2
    assert requests[0]["appendCells"]["sheetId"] == 111
    assert requests[1]["appendCells"]["sheetId"] == 222
    row = requests[0]["appendCells"]["rows"][0]["values"]
    assert row[0]["userEnteredValue"] == {"stringValue": "=UNSAFE"}
    assert row[3]["userEnteredValue"] == {"numberValue": 12.0}
    assert row[4]["userEnteredValue"] == {"numberValue": 16.26}
    assert row[5]["userEnteredValue"] == {"numberValue": 31409.0}
    assert row[6]["userEnteredValue"] == {"numberValue": 3.0}
    assert requests[1]["appendCells"]["rows"][0]["values"][0]["userEnteredValue"] == {
        "stringValue": "gmail:nuevo:1"
    }


def test_template_rejects_incorrect_columns_before_any_mutation():
    service = SheetsFake()
    writer = GoogleSheetsCreditosWriter(service, "fake-id")
    with pytest.raises(ValueError, match="7 columnas"):
        writer.claves_existentes([Campo("a", "(.*)")])
    assert service.calls == []


def test_template_rejects_invalid_month_and_injected_numeric():
    with pytest.raises(ValueError, match="MES"):
        _numero("13", 6)
    with pytest.raises(ValueError, match="campo numérico"):
        _numero("=HYPERLINK('example')", 4)
    with pytest.raises(ValueError, match="números enteros"):
        _numero("3.25", 3)
