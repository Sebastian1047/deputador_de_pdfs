"""Salida a la plantilla Creditos SOLE convertida a Google Sheets.

Los datos históricos permanecen intactos. Las nuevas filas se agregan a
DETALLE DEVOLUCION y las claves PDF a una hoja técnica oculta en una sola
operación de Google Sheets (batchUpdate), para evitar marcas incoherentes.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Sequence

from .core import Campo

COLUMNAS = (
    "VARIEDAD", "CAT", "FINCA", "RM", "TOTAL", "QC Inspection", "MES",
)
CONTROL = "_CONTROL_PDF"


def _a1(name: str, interval: str) -> str:
    return "'" + name.replace("'", "''") + "'!" + interval


def _numero(raw: str, indice: int) -> dict:
    value = str(raw).strip()
    if not value:
        return {"stringValue": ""}
    # Aceptar separador decimal latino sin transformar separadores arbitrarios.
    if not re.fullmatch(r"-?\d+(?:[.,]\d+)?", value):
        raise ValueError("Un campo numérico de la plantilla no es válido")
    try:
        decimal = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Número de la plantilla inválido") from exc
    if not decimal.is_finite():
        raise ValueError("Número no finito")
    if indice in (3, 5, 6) and decimal != int(decimal):
        raise ValueError("RM, QC Inspection y MES deben ser números enteros")
    if indice == 6 and not 1 <= decimal <= 12:
        raise ValueError("MES debe estar entre 1 y 12")
    if indice == 5 and not 0 <= decimal < 10**15:
        raise ValueError("QC Inspection fuera de rango")
    return {"numberValue": float(decimal)}


class GoogleSheetsCreditosWriter:
    """Agregar filas en el mismo orden de las 7 columnas del Excel original."""

    def __init__(self, service, spreadsheet_id: str, tab: str = "DETALLE DEVOLUCION"):
        if not spreadsheet_id:
            raise ValueError("Configure GOOGLE_SPREADSHEET_ID")
        self.service = service
        self.spreadsheet_id = spreadsheet_id
        self.tab = tab
        self.values = service.spreadsheets().values()
        self.sheet_id = None
        self.control_id = None
        self.creditos_existentes: set[str] = set()

    def claves_existentes(self, campos: Sequence[Campo]) -> set[str]:
        if [campo.nombre.strip().casefold() for campo in campos] != [
            col.casefold() for col in COLUMNAS
        ]:
            raise ValueError(
                "Los nombres y el orden de config/campos.json deben corresponder "
                "a las 7 columnas de DETALLE DEVOLUCION"
            )
        info = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id,
            fields="sheets(properties(sheetId,title))",
        ).execute()
        tabs = {entry["properties"]["title"]: entry["properties"]["sheetId"]
                for entry in info.get("sheets", [])}
        if self.tab not in tabs:
            raise ValueError("No existe la pestaña DETALLE DEVOLUCION en Google Sheets")
        self.sheet_id = tabs[self.tab]
        encabezados = self.values.get(
            spreadsheetId=self.spreadsheet_id, range=_a1(self.tab, "A1:G1")
        ).execute().get("values", [[]])
        if not encabezados or [str(c).strip().casefold() for c in encabezados[0]] != [
            c.casefold() for c in COLUMNAS
        ]:
            raise ValueError("La plantilla de destino tiene columnas diferentes al Excel original")
        # Revisar el histórico por número QC; los registros previos a la
        # aplicación no tienen claves de PDF en la pestaña técnica.
        historicos = self.values.get(
            spreadsheetId=self.spreadsheet_id, range=_a1(self.tab, "F2:F")
        ).execute().get("values", [])
        self.creditos_existentes = {
            str(fila[0]).strip() for fila in historicos if fila and fila[0] != ""
        }
        self.control_id = tabs.get(CONTROL)
        if self.control_id is None:
            creado = self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": CONTROL, "hidden": True}}}]},
            ).execute()
            self.control_id = creado["replies"][0]["addSheet"]["properties"]["sheetId"]
            self.values.update(
                spreadsheetId=self.spreadsheet_id, range=_a1(CONTROL, "A1:B1"),
                valueInputOption="RAW",
                body={"values": [["document_key", "processed_utc"]]},
            ).execute()
        claves = self.values.get(
            spreadsheetId=self.spreadsheet_id, range=_a1(CONTROL, "A2:A")
        ).execute().get("values", [])
        return {str(row[0]) for row in claves if row}

    def es_registro_historico(self, datos: Sequence[str]) -> bool:
        if len(datos) != len(COLUMNAS):
            raise ValueError("No coinciden las 7 columnas de la plantilla")
        return str(datos[5]).strip() in self.creditos_existentes

    def agregar(self, clave: str, fecha_utc: str, datos: Sequence[str]) -> None:
        if self.sheet_id is None or self.control_id is None:
            raise RuntimeError("Debe verificar encabezados y duplicados antes de escribir")
        if len(datos) != len(COLUMNAS):
            raise ValueError("La plantilla necesita 7 valores por PDF")
        if self.es_registro_historico(datos):
            raise ValueError("Crédito QC ya existente; no duplicar")
        celdas = []
        for i, value in enumerate(datos):
            if i in (3, 4, 5, 6):
                user_value = _numero(value, i)
            else:
                # stringValue evita la ejecución de fórmulas incrustadas en PDF.
                user_value = {"stringValue": str(value).strip()}
            celdas.append({"userEnteredValue": user_value})
        requests = [
            {"appendCells": {
                "sheetId": self.sheet_id,
                "rows": [{"values": celdas}],
                "fields": "userEnteredValue",
            }},
            {"appendCells": {
                "sheetId": self.control_id,
                "rows": [{"values": [
                    {"userEnteredValue": {"stringValue": str(clave)}},
                    {"userEnteredValue": {"stringValue": str(fecha_utc)}},
                ]}],
                "fields": "userEnteredValue",
            }},
        ]
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id, body={"requests": requests}
        ).execute()
        self.creditos_existentes.add(str(datos[5]).strip())
