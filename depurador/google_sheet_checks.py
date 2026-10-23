"""Comprobación de destino Google Sheets sin modificar el archivo."""
from __future__ import annotations

from .google_drive_sheet import COLUMNAS, _a1


def comprobar_hoja_creditos(service, spreadsheet_id: str,
                           nombre_hoja: str = "DETALLE DEVOLUCION") -> None:
    """Verifica acceso y columnas; no crea pestañas, filas ni controles."""
    if not spreadsheet_id or not nombre_hoja:
        raise ValueError("Falta identificar la hoja de destino")
    sheets = service.spreadsheets()
    metadata = sheets.get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(title,sheetId))",
    ).execute()
    titles = {
        sheet["properties"]["title"] for sheet in metadata.get("sheets", [])
    }
    if nombre_hoja not in titles:
        raise ValueError("No existe la pestaña esperada en el destino")
    response = sheets.values().get(
        spreadsheetId=spreadsheet_id,
        range=_a1(nombre_hoja, "A1:G1"),
    ).execute()
    encabezados = response.get("values", [[]])
    expected = [c.strip().casefold() for c in COLUMNAS]
    actual = [str(c).strip().casefold() for c in encabezados[0]] if encabezados else []
    if actual != expected:
        raise ValueError("Las siete columnas del destino no coinciden")
