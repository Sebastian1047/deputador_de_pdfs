"""Extractor de reportes QC Inspection de Sole Farms.

Reconoce los campos impresos de la página de crédito sin analizar fotografías.
Ante proveedores, categorías o formatos desconocidos, rechaza la fila en lugar
de escribir datos inventados.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import fitz

COLUMNAS = ("VARIEDAD", "CAT", "FINCA", "RM", "TOTAL", "QC Inspection", "MES")


def _capturar(texto: str, patron: str, etiqueta: str) -> re.Match:
    resultado = re.search(patron, texto, flags=re.IGNORECASE | re.MULTILINE)
    if not resultado:
        raise ValueError(f"Falta o no se reconoce el dato obligatorio: {etiqueta}")
    return resultado


def _categoria(producto: str) -> str:
    primera = producto.split(maxsplit=1)[0].casefold()
    if primera == "pom":
        return "PO"
    if primera in {"mums", "mum"}:
        if re.search(r"\bspider\b", producto, flags=re.IGNORECASE):
            return "SP"
        if re.search(r"\bcremon\b", producto, flags=re.IGNORECASE):
            return "CR"
    raise ValueError("No se reconoce la categoría del producto")


def extraer_credito_sole(contenido: bytes, campos=None, *,
                        incluir_anio: bool = False):
    """Extraer las siete columnas y opcionalmente el año de Credit Date."""
    if not contenido.startswith(b"%PDF"):
        raise ValueError("Adjunto no es un PDF válido")
    if campos is not None and [c.nombre.strip().casefold() for c in campos] != [
        c.casefold() for c in COLUMNAS
    ]:
        raise ValueError("Los campos de configuración no corresponden a Créditos SOLE")
    with fitz.open(stream=contenido, filetype="pdf") as documento:
        if len(documento) < 1 or len(documento) > 30:
            raise ValueError("Número de páginas PDF fuera del rango permitido")
        texto = "\n".join(pagina.get_text(sort=True) for pagina in documento)
    if not texto.strip():
        raise ValueError("PDF sin texto extraíble; requiere revisión u OCR")

    credito = _capturar(
        texto, r"^\s*Credit\s*#\s*(\d{1,12})\s*$", "Credit #"
    ).group(1)
    producto_proveedor = _capturar(
        texto, r"^\s*Product:\s*(.*?)\s+Vendor:\s*([^\r\n]+)",
        "Product / Vendor",
    )
    producto = producto_proveedor.group(1).strip()
    proveedor = producto_proveedor.group(2).strip()
    if not producto or len(producto) > 250:
        raise ValueError("Producto vacío o demasiado largo")
    finca = proveedor.split("-", 1)[0].strip().upper()
    if finca != "JN":
        raise ValueError("La finca del PDF no coincide con la plantilla JN")

    cantidad = _capturar(
        texto,
        r"^\s*Credit Quantity:\s*(\d+)\s+(?:Bunch(?:es)?|Bchs?)(?:\b|\s)",
        "Credit Quantity",
    ).group(1)
    total = _capturar(
        texto, r"\bTotal Credit:\s*\$\s*([0-9][0-9,.]*)\b", "Total Credit"
    ).group(1)
    if "," in total and "." in total:
        total = total.replace(",", "")
    elif "," in total:
        total = total.replace(",", ".")
    try:
        importe = Decimal(total)
    except InvalidOperation as error:
        raise ValueError("Total Credit no es numérico") from error
    if not importe.is_finite() or importe < 0:
        raise ValueError("Total Credit inválido")

    fecha = _capturar(
        texto,
        r"^\s*Credit Date\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})\b",
        "Credit Date",
    ).group(1)
    fecha_credito = datetime.strptime(fecha, "%m/%d/%Y")
    datos = [
        producto, _categoria(producto), finca, str(int(cantidad)),
        str(importe), str(int(credito)), str(fecha_credito.month),
    ]
    return (datos, fecha_credito.year) if incluir_anio else datos
