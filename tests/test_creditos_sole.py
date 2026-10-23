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
        if kwargs["range"] == "'_CONTROL_PDF'!C2:D":
            return Peticion({"values": []})
        if kwargs["range"] == "'DETALLE DEVOLUCION'!F2:F":
            return Peticion({"values": [["31409"]]})
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
    assert writer.claves_existentes(fields()) == set()
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
        "=UNSAFE", "PO", "JN", "12", "16,26", "98765", "3"
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
    assert row[5]["userEnteredValue"] == {"numberValue": 98765.0}
    assert row[6]["userEnteredValue"] == {"numberValue": 3.0}
    assert requests[1]["appendCells"]["rows"][0]["values"][0]["userEnteredValue"] == {
        "stringValue": "gmail:nuevo:1"
    }
    assert writer.es_registro_historico(["=UNSAFE", "PO", "JN", "12", "16,26", "98765", "3"])


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



def test_plantilla_bloquea_credito_ya_en_historico():
    service = SheetsFake()
    writer = GoogleSheetsCreditosWriter(service, "fake-id")
    writer.claves_existentes(fields())
    assert writer.es_registro_historico(["Pom Green Daisy", "PO", "JN", "12", "15", "31409", "1"])
    with pytest.raises(ValueError, match="ya existente"):
        writer.agregar("gmail:nuevo:1", "2026-10-22T18:00:00Z", [
            "Pom Green Daisy", "PO", "JN", "12", "15", "31409", "1"
        ])
    assert not any(
        call["body"]["requests"][0].get("appendCells")
        for typ, call in service.calls if typ == "batchUpdate"
    )


def test_plantilla_registra_anio_sin_anadir_columna_visible():
    service = SheetsFake(control_exists=True)
    writer = GoogleSheetsCreditosWriter(service, "fake-id")
    writer.claves_existentes(fields())
    writer.anio_credito_actual = 2027
    writer.agregar("gmail:2027:1", "2027-02-01T12:00:00Z", [
        "Pom Ficticio", "PO", "JN", "12", "23.50", "31409", "1"
    ])
    writes = [arg for typ, arg in service.calls if typ == "batchUpdate"]
    assert len(writes) == 1
    rows = writes[0]["body"]["requests"]
    assert len(rows[0]["appendCells"]["rows"][0]["values"]) == 7
    technical = rows[1]["appendCells"]["rows"][0]["values"]
    assert len(technical) == 4
    assert technical[2]["userEnteredValue"]["stringValue"] == "31409"
    assert technical[3]["userEnteredValue"]["numberValue"] == 2027
    assert writer.es_registro_historico(["Pom Ficticio", "PO", "JN", "12", "23.50", "31409", "1"])



def test_borrado_visible_ignora_claves_obsoletas_de_control():
    """El PDF puede reimportarse si el usuario borró el QC de DETALLE DEVOLUCION."""
    class HojaVaciada(SheetsFake):
        def get(self, **kwargs):
            if kwargs.get("range") == "'DETALLE DEVOLUCION'!F2:F":
                self.calls.append(("get", kwargs))
                return Peticion({"values": []})
            if kwargs.get("range") == "'_CONTROL_PDF'!C2:D":
                self.calls.append(("get", kwargs))
                return Peticion({"values": [["31409", 2026]]})
            return super().get(**kwargs)

    from depurador.core import AdjuntoPDF, procesar
    service = HojaVaciada(control_exists=True)
    destino = GoogleSheetsCreditosWriter(service, "fake-id")

    # Generar 39 contenidos con números QC distintos, pero todas las claves
    # documentales figuran en el control histórico y ya no en la hoja visible.
    class LoteReal:
        def adjuntos_pdf(self):
            for index in range(39):
                yield AdjuntoPDF(f"gmail:correo:archivo-{index}", f"%PDF-{index}".encode())

    def extraer(documento, campos):
        indice = int(documento.split(b"-")[-1])
        return ["Pom Ficticio", "PO", "JN", "2", "3,20", str(31409 + indice), "9"]

    resultado = procesar(LoteReal(), destino, fields(), extractor=extraer)
    assert resultado == {"encontrados": 39, "agregados": 39, "duplicados": 0, "errores": 0}
    assert len([c for t, c in service.calls if t == "batchUpdate"]) == 39


def test_claves_viejas_no_impiden_bloquear_duplicados_que_siguen_en_detalle():
    from depurador.core import AdjuntoPDF, procesar

    service = SheetsFake(control_exists=True)
    destino = GoogleSheetsCreditosWriter(service, "fake-id")

    class Correo:
        def adjuntos_pdf(self):
            yield AdjuntoPDF("gmail:id-antiguo:1", b"fake")

    resultado = procesar(
        Correo(), destino, fields(),
        extractor=lambda contenido, campos: [
            "Pom Ficticio", "PO", "JN", "12", "16.85", "31409", "1"
        ],
    )
    assert resultado == {"encontrados": 1, "agregados": 0, "duplicados": 1, "errores": 0}
    assert not any(
        call["body"]["requests"][0].get("appendCells")
        for typ, call in service.calls if typ == "batchUpdate"
    )


def test_control_obsoleto_2027_no_ensucia_periodo_sin_qc_visible():
    class HojaVaciada(SheetsFake):
        def get(self, **kwargs):
            if kwargs.get("range") == "'DETALLE DEVOLUCION'!F2:F":
                self.calls.append(("get", kwargs))
                return Peticion({"values": []})
            if kwargs.get("range") == "'_CONTROL_PDF'!C2:D":
                self.calls.append(("get", kwargs))
                return Peticion({"values": [["31409", 2027]]})
            return super().get(**kwargs)

    writer = GoogleSheetsCreditosWriter(HojaVaciada(control_exists=True), "fake-id")
    assert writer.claves_existentes(fields()) == set()
    assert not writer.es_registro_historico([
        "Pom Ficticio", "PO", "JN", "12", "16.85", "31409", "1"
    ])
