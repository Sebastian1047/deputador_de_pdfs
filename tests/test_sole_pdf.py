"""Pruebas unitarias de reportes QC Inspection (documentos ficticios)."""
import json

import fitz
import pytest

from depurador.core import AdjuntoPDF, Campo, procesar
from depurador.sole_pdf import COLUMNAS, extraer_credito_sole
from depurador.web import _reglas


def pdf_sintetico(*, producto="Pom Green Cushion Ficticio",
                 proveedor="JN-Sitio Ejemplo", credito="98765",
                 cantidad="12", total="16.85", fecha="09/18/2026"):
    lineas = [
        f"Credit #            {credito}",
        f"Credit Date       {fecha}",
        "AWB             000-0000-0000",
        "Farm Ship Date   09/05/2026",
        "PO #          A12345",
        f"Product: {producto}     Vendor: {proveedor}",
        "Inspection Notes:",
        "Credit Information:",
        f"Credit Quantity:    {cantidad} Bunch",
        "Flower Credit: $ 12.00",
        "Freight Credit: $ 4.85",
        f"Total Credit:       $ {total}",
    ]
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((40, 55), "\n".join(lineas), fontsize=10, lineheight=1.35)
    other = pdf.new_page()
    other.insert_text((40, 55), "Images: fotos de prueba", fontsize=10)
    resultado = pdf.tobytes()
    pdf.close()
    return resultado


def campos():
    return [Campo(nombre, r"(?s).+", True) for nombre in COLUMNAS]


@pytest.mark.parametrize("producto,cat", [
    ("Pom Green Cushion Ficticio", "PO"),
    ("Mums White Spider Ficticio", "SP"),
    ("Mums Purple Cremon Ficticio", "CR"),
])
def test_extrae_siete_campos_reportes_multipagina(producto, cat):
    resultado = extraer_credito_sole(pdf_sintetico(producto=producto), campos())
    assert resultado == [producto, cat, "JN", "12", "16.85", "98765", "9"]


@pytest.mark.parametrize("cambio", [
    {"producto": "Unknown Green"},
    {"proveedor": "OTRA-Finca"},
    {"cantidad": "N/A"},
    {"total": "no tiene total"},
])
def test_no_agrega_campos_inventados(cambio):
    with pytest.raises(ValueError):
        extraer_credito_sole(pdf_sintetico(**cambio), campos())


def test_fecha_invalida_no_se_convierte_en_mes():
    with pytest.raises(ValueError):
        extraer_credito_sole(pdf_sintetico(fecha="13/35/2026"), campos())


def test_config_actual_se_sirve_sin_regex_ficticios():
    from pathlib import Path
    conf = Path("config/campos.json")
    data = json.loads(conf.read_text(encoding="utf-8"))
    assert data["formato"] == "creditos_sole"
    assert [x["nombre"] for x in data["campos"]] == list(COLUMNAS)
    assert [x.nombre for x in _reglas(str(conf))] == list(COLUMNAS)


def test_procesar_evitar_duplicados_historicos_por_credito():
    class Mail:
        def adjuntos_pdf(self):
            yield AdjuntoPDF("gmail:fake:1", pdf_sintetico())

    class Destination:
        def claves_existentes(self, fields):
            return set()

        def es_registro_historico(self, valores):
            return valores[5] == "98765"

        def agregar(self, *args):
            raise AssertionError("No debe escribirse un crédito histórico")
    result = procesar(Mail(), Destination(), campos(), extractor=extraer_credito_sole)
    assert result == {"encontrados": 1, "agregados": 0, "duplicados": 1, "errores": 0}


def test_extrae_anio_del_credit_date_sin_cambiar_siete_columnas():
    datos, anio = extraer_credito_sole(
        pdf_sintetico(fecha="01/17/2027"), campos(), incluir_anio=True
    )
    assert anio == 2027
    assert len(datos) == 7
    assert datos[6] == "1"
