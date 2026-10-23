"""Informes de créditos SOLE consultados directamente desde Google Sheets.

No modifica hojas ni depende de los filtros de una tabla dinámica. La plantilla
histórica tiene MES pero no año: se interpreta como 2026, el año de origen del
libro. Los nuevos PDF guardan además el año en _CONTROL_PDF (columna D).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO

from .google_drive_sheet import COLUMNAS, CONTROL, _a1
from .filtros_creditos import MESES

CATEGORIAS = ("PO", "CR", "SP")
ANIO_HISTORICO = 2026


def validar_periodo(anio: int, mes: int):
    from .filtros_creditos import anos_disponibles

    if anio not in anos_disponibles() or not 1 <= mes <= 12:
        raise ValueError("Seleccione un año y un mes válidos")


def _decimal(value) -> Decimal:
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return Decimal("0")
    # Google Sheets UNFORMATTED_VALUE devuelve números como int/float; cubrir
    # también hojas cuyos valores fueron importados como textos regionales.
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
        if not number.is_finite():
            raise InvalidOperation
        return number
    except InvalidOperation as exc:
        raise ValueError("Valor numérico inválido en Google Sheets") from exc


def numero_es(value: Decimal | int | float | str) -> str:
    amount = _decimal(value).quantize(Decimal("0.01"))
    s = f"{amount:,.2f}"
    return s.replace(",", "@").replace(".", ",").replace("@", ".")


def leer_reporte_sole(servicio, spreadsheet_id: str, tab: str,
                     anio: int, mes: int, anio_historico: int = ANIO_HISTORICO) -> dict:
    """Devuelve detalle/resumen del mes solicitado, sin mutaciones en Drive."""
    validar_periodo(anio, mes)
    sheets = servicio.spreadsheets()
    properties = sheets.get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(title))",
    ).execute()
    titles = {s["properties"]["title"] for s in properties.get("sheets", [])}
    if tab not in titles:
        raise ValueError("No existe la pestaña de detalle")
    raw = sheets.values().get(
        spreadsheetId=spreadsheet_id, range=_a1(tab, "A1:G"),
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute().get("values", [])
    if not raw or [str(v).strip().casefold() for v in raw[0]] != [
        c.casefold() for c in COLUMNAS
    ]:
        raise ValueError("Los encabezados de la hoja no son los esperados")

    data = [list(row) for row in raw[1:]]
    # Índice en el archivo de control. El año del crédito se toma de Credit
    # Date, NO de la fecha de llegada del correo ni de la fecha de importación.
    explicit: dict[str, list[int]] = defaultdict(list)
    if CONTROL in titles:
        indexed = sheets.values().get(
            spreadsheetId=spreadsheet_id, range=_a1(CONTROL, "C2:D"),
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute().get("values", [])
        for row in indexed:
            if len(row) >= 2 and str(row[0]).strip() and str(row[1]).strip():
                try:
                    year = int(row[1])
                except (ValueError, TypeError, OverflowError):
                    continue
                if 2000 <= year <= 2100:
                    explicit[str(row[0]).strip()].append(year)

    # Si un QC se reutiliza entre años, asignar las anotaciones más recientes
    # a las últimas filas, conservando 2026 para el histórico sin metadatos.
    years = [anio_historico] * len(data)
    positions: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(data):
        if len(row) > 5 and str(row[5]).strip():
            positions[str(row[5]).strip()].append(i)
    for qc, annotations in explicit.items():
        for pos, year in zip(reversed(positions.get(qc, [])), reversed(annotations)):
            years[pos] = year

    registros = []
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    total_general = Decimal("0")
    for i, row in enumerate(data):
        if not row or not any(str(c).strip() for c in row):
            continue
        row = (row + [""] * len(COLUMNAS))[:len(COLUMNAS)]
        try:
            mes_fila = int(row[6])
        except (ValueError, TypeError, OverflowError):
            continue
        if mes_fila != mes or years[i] != anio:
            continue
        valor = _decimal(row[4])
        categoria = str(row[1]).strip().upper()
        totals[categoria] += valor
        total_general += valor
        registros.append({
            "variedad": str(row[0]),
            "cat": categoria,
            "finca": str(row[2]),
            "rm": str(row[3]),
            "total": valor,
            "qc": str(row[5]),
            "mes": mes_fila,
        })
    categories = list(CATEGORIAS) + sorted(set(totals).difference(CATEGORIAS))
    resumen = [{"cat": cat, "total": totals[cat]} for cat in categories]
    return {
        "anio": anio, "mes": mes, "nombre_mes": MESES[mes - 1].capitalize(),
        "registros": registros, "resumen": resumen, "total": total_general,
        "cantidad": len(registros),
        "anio_historico": anio_historico,
    }


def crear_imagen_resumen(reporte: dict) -> bytes:
    """PNG de alta resolución, descargable para correo sin datos secretos."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1440, 1020
    img = Image.new("RGB", (W, H), "#f2f6f3")
    dr = ImageDraw.Draw(img)

    def font(size, bold=False):
        file = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        try:
            return ImageFont.truetype(file, size)
        except (OSError, ValueError):
            return ImageFont.load_default()

    def right(text, x, y, fnt, fill):
        width = dr.textbbox((0, 0), text, font=fnt)[2]
        dr.text((x-width, y), text, font=fnt, fill=fill)

    dr.rounded_rectangle((64, 55, 1376, 963), radius=32, fill="#ffffff")
    dr.rounded_rectangle((64, 55, 1376, 346), radius=32, fill="#0e503a")
    # Cubrir esquinas inferiores redondas del bloque verde, dejando borde recto
    dr.rectangle((64, 308, 1376, 346), fill="#0e503a")
    dr.rounded_rectangle((111, 103, 358, 155), radius=14, fill="#287456")
    dr.text((135, 113), "INFORME DE CRÉDITOS", font=font(22, True), fill="#e7f8ef")
    dr.text((110, 186), "Resumen Créditos SOLE", font=font(59, True), fill="white")
    dr.text((113, 277), f"{reporte['nombre_mes']} {reporte['anio']}",
            font=font(37), fill="#d7ebdf")
    dr.text((112, 389), "CATEGORÍA", font=font(23, True), fill="#557463")
    right("SUMA DE TOTAL", 1317, 389, font(23, True), "#557463")
    dr.line((111, 437, 1318, 437), fill="#e0eae3", width=3)
    y = 465
    for item in reporte["resumen"]:
        dr.text((115, y), item["cat"], font=font(34, True), fill="#214735")
        right(numero_es(item["total"]), 1314, y, font(34), "#214735")
        dr.line((111, y + 68, 1318, y + 68), fill="#ecf2ee", width=2)
        y += 100

    dr.rounded_rectangle((109, 800, 1320, 901), radius=18, fill="#e1f2e7")
    dr.text((135, 825), "TOTAL GENERAL", font=font(30, True), fill="#14563d")
    right(numero_es(reporte["total"]), 1295, 819, font(43, True), "#0e503a")
    dr.text((112, 926), f"{reporte['cantidad']} créditos registrados en el período",
            font=font(19), fill="#6a8376")
    output = BytesIO()
    img.save(output, format="PNG", optimize=True)
    return output.getvalue()
