"""Búsqueda mensual segura de créditos JN en Gmail.

El asunto identifica el mes del crédito, pero los mensajes pueden llegar el
mes siguiente. Por ello no se filtra solamente por el mes de recepción.
"""
from __future__ import annotations

from datetime import date, timedelta

MESES = (
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
)


def periodo_predeterminado(hoy: date | None = None) -> tuple[int, int]:
    """Sugerir el mes anterior, ya que los PDFs suelen enviarse el siguiente."""
    hoy = hoy or date.today()
    previo = hoy.replace(day=1) - timedelta(days=1)
    return previo.year, previo.month


def anos_disponibles(hoy: date | None = None) -> tuple[int, ...]:
    """Ofrecer el año actual y cinco anteriores sin recurrir a años futuros."""
    actual = (hoy or date.today()).year
    return tuple(range(actual, max(actual - 6, 2019), -1))


def consulta_creditos(anio: int | str, mes: int | str,
                      hoy: date | None = None) -> str:
    """Generar consulta Gmail sin interpolar texto arbitrario del formulario.

    Limitar recepción al mes del crédito y el mes siguiente. Así SEPTIEMBRE
    2026 puede llegar en OCTUBRE 2026, y DICIEMBRE puede llegar en ENERO
    del año posterior, sin mezclar envíos de otros años.
    """
    try:
        year = int(anio)
        month = int(mes)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Seleccione un año y un mes válidos") from exc
    if str(anio) != str(year) or str(mes) != str(month):
        raise ValueError("Los valores de año y mes deben ser numéricos")
    if year not in anos_disponibles(hoy) or not 1 <= month <= 12:
        raise ValueError("Seleccione un año y un mes disponibles")
    # Desde el día 1 del mes elegido hasta el día 1 de dos meses después.
    # End date exclusiva, como en el buscador de Gmail.
    upper_month_zero = month + 1
    last_year = year + upper_month_zero // 12
    last_month = upper_month_zero % 12 + 1
    return (
        f'subject:"CREDITOS {MESES[month - 1]} JN" '
        f'has:attachment filename:pdf '
        f'after:{year:04d}/{month:02d}/01 '
        f'before:{last_year:04d}/{last_month:02d}/01'
    )
