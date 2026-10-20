"""Punto de entrada: python -m depurador [--demo]."""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from .core import AdjuntoPDF, Campo, extraer_datos, leer_campos, procesar


def _modo_demo() -> None:
    import fitz

    documento = fitz.open()
    pagina = documento.new_page()
    pagina.insert_text((60, 90), "Documento: EJEMPLO-001\nFecha: 20/10/2026\nTotal: 125")
    datos = documento.tobytes()
    documento.close()
    campos = [
        Campo("documento", r"Documento:\s*([A-Z0-9-]+)", True),
        Campo("fecha", r"Fecha:\s*(\d{2}/\d{2}/\d{4})", True),
        Campo("total", r"Total:\s*(\d+)", True),
    ]
    class BandejaEjemplo:
        def adjuntos_pdf(self):
            yield AdjuntoPDF("demo:1", datos)

    class TablaEjemplo:
        def __init__(self):
            self.registros = []
        def claves_existentes(self, campos):
            return set()
        def agregar(self, clave, fecha_utc, valores):
            self.registros.append([clave, fecha_utc, *valores])

    tabla = TablaEjemplo()
    resumen = procesar(BandejaEjemplo(), tabla, campos)
    print("PRUEBA SIN CONEXIONES: ", json.dumps(resumen, ensure_ascii=False))
    print("Fila simulada (datos ficticios):", tabla.registros[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrae campos de PDF recibidos por correo")
    parser.add_argument("--demo", action="store_true", help="Simular todo sin correo ni Drive")
    argumentos = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if argumentos.demo:
        _modo_demo()
        return

    from .proveedores import GmailReader, GoogleSheetsWriter, crear_servicios_google

    if os.getenv("EMAIL_PROVIDER", "gmail").lower() != "gmail":
        raise SystemExit("Proveedor de correo no implementado todavía")
    if os.getenv("TABLE_PROVIDER", "google_sheets").lower() != "google_sheets":
        raise SystemExit("Proveedor de tabla no implementado todavía")

    configuracion = json.loads(Path("config/campos.json").read_text(encoding="utf-8"))
    campos = leer_campos(configuracion)
    if not campos:
        raise SystemExit("Configure config/campos.json usando un PDF real antes de activar el proceso")
    identificador = os.getenv("GOOGLE_SPREADSHEET_ID")
    if not identificador:
        raise SystemExit("Falta GOOGLE_SPREADSHEET_ID")

    gmail, sheets = crear_servicios_google()
    correo = GmailReader(
        gmail,
        (os.getenv("GMAIL_QUERY") or "has:attachment filename:pdf newer_than:30d"),
        int(os.getenv("MAX_EMAILS", "250")),
    )
    tabla = GoogleSheetsWriter(sheets, identificador, (os.getenv("GOOGLE_SHEET_TAB") or "Registros"))
    resumen = procesar(correo, tabla, campos)
    print("RESUMEN:", json.dumps(resumen, ensure_ascii=False))
    if resumen["errores"]:
        raise SystemExit("Hubo documentos con errores; revise los patrones de extracción")


if __name__ == "__main__":
    main()
