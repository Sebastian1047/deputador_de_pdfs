"""Selector año/mes genera consultas Gmail sin mezclar años ni reenvíos tardíos."""
from datetime import date
from types import SimpleNamespace

import pytest

from depurador.filtros_creditos import (
    MESES, anos_disponibles, consulta_creditos, periodo_predeterminado,
)
from depurador import web
from test_web import entorno, iniciar_sesion


def test_septiembre_2026_incluye_octubre_2026_no_2025():
    query = consulta_creditos(2026, 9, date(2026, 10, 23))
    assert query == (
        'subject:"CREDITOS SEPTIEMBRE JN" has:attachment filename:pdf '
        'after:2026/09/01 before:2026/11/01'
    )
    assert "2025/" not in query
    assert "2027/" not in query
    assert len(MESES) == 12


def test_diciembre_admite_enero_siguiente_ano_sin_otros_periodos():
    assert consulta_creditos(2025, 12, date(2026, 10, 23)) == (
        'subject:"CREDITOS DICIEMBRE JN" has:attachment filename:pdf '
        'after:2025/12/01 before:2026/02/01'
    )


def test_predeterminado_mes_anterior_incluye_cambio_de_ano():
    assert periodo_predeterminado(date(2026, 10, 23)) == (2026, 9)
    assert periodo_predeterminado(date(2027, 1, 7)) == (2026, 12)
    assert anos_disponibles(date(2026, 10, 23)) == (
        2026, 2025, 2024, 2023, 2022, 2021
    )


@pytest.mark.parametrize("year,month", [
    ("2026 after:2010/01/01", "9"),
    ("2026", "13"),
    ("2026", "0"),
    ("2026", "septiembre"),
    ("1999", "9"),
    ("2027", "9"),
    ("2020", "9"),
])
def test_datos_invalidos_no_forman_consulta(year, month):
    with pytest.raises(ValueError):
        consulta_creditos(year, month, date(2026, 10, 23))


def test_web_gmail_sole_usa_anio_y_mes_y_conserva_seleccion(entorno, monkeypatch):
    app, client, _ = entorno
    app.config["GOOGLE_SHEETS_TEMPLATE"] = "creditos_sole"
    usadas = []

    class Reader:
        def __init__(self, service, filtro, cantidad):
            usadas.append(filtro)

        def listar_correos(self):
            return [SimpleNamespace(
                id="email_creditos", fecha="22/10/2026 17:18",
                remitente="Correo de pruebas", asunto="Fwd: CREDITOS SEPTIEMBRE JN",
                cantidad_pdf=39
            )]

    monkeypatch.setattr(web, "GmailReader", Reader)
    csrf = iniciar_sesion(client)
    html = client.get("/").text
    assert 'name="anio"' in html and 'name="mes"' in html
    assert 'name="filtro"' not in html

    result = client.post("/buscar", data={
        "_csrf": csrf, "anio": "2026", "mes": "9"
    })
    assert result.status_code == 302
    assert usadas == [consulta_creditos(2026, 9)]
    home = client.get("/").text
    assert "Fwd: CREDITOS SEPTIEMBRE JN" in home
    assert '<option value="2026" selected>' in home
    assert '<option value="9" selected>' in home

    # Si el usuario envía campos ajenos no debe poder insertar búsquedas amplias.
    client.post("/buscar", data={
        "_csrf": csrf, "anio": "2026", "mes": "13",
        "filtro": "after:1990/01/01"
    })
    assert len(usadas) == 1
    assert "Seleccione un año y mes válidos" in client.get("/").text
