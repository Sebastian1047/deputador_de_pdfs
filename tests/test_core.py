import fitz
import pytest

from depurador.core import AdjuntoPDF, Campo, extraer_datos, leer_campos, procesar
from depurador.proveedores import _decodificar, _partes_recursivas


def crear_pdf(texto):
    doc = fitz.open()
    pagina = doc.new_page()
    pagina.insert_text((40, 80), texto)
    resultado = doc.tobytes()
    doc.close()
    return resultado


def test_extrae_campos_de_pdf_en_memoria():
    pdf = crear_pdf("Documento: X-123\nFecha: 20/10/2026")
    campos = leer_campos({"campos": [
        {"nombre": "numero", "patron": r"Documento:\s*([A-Z0-9-]+)", "obligatorio": True},
        {"nombre": "fecha", "patron": r"Fecha:\s*(\d{2}/\d{2}/\d{4})"},
    ]})
    assert extraer_datos(pdf, campos) == ["X-123", "20/10/2026"]


def test_campo_obligatorio_ausente_produce_error():
    with pytest.raises(ValueError, match="obligatorio"):
        extraer_datos(crear_pdf("Sin numero"), [Campo("numero", r"Número:\s*(\d+)", True)])


def test_evita_registros_duplicados_y_permite_reintento():
    contenido = crear_pdf("Documento: 100")
    class Correo:
        def adjuntos_pdf(self):
            yield AdjuntoPDF("clave-1", contenido)
            yield AdjuntoPDF("clave-1", contenido)
    class Tabla:
        def __init__(self):
            self.claves = set()
            self.filas = []
        def claves_existentes(self, campos):
            return self.claves.copy()
        def agregar(self, clave, fecha, valores):
            self.filas.append(valores)
            self.claves.add(clave)
    tabla = Tabla()
    regla = [Campo("documento", r"Documento:\s*(\d+)", True)]
    assert procesar(Correo(), tabla, regla) == {
        "encontrados": 2, "agregados": 1, "duplicados": 1, "errores": 0
    }
    assert procesar(Correo(), tabla, regla)["agregados"] == 0
    assert tabla.filas == [["100"]]


def test_decodifica_base64url_y_recursividad():
    assert _decodificar("JVBERi0") == b"%PDF-"
    partes = {"parts": [
        {"filename": "a.pdf"}, {"parts": [{"filename": "b.pdf"}]}
    ]}
    assert [x["filename"] for x in _partes_recursivas(partes)] == ["a.pdf", "b.pdf"]


def test_conflicto_en_nombres_de_campos():
    with pytest.raises(ValueError, match="únicos"):
        leer_campos({"campos": [
            {"nombre": "uno", "patron": "x"},
            {"nombre": "uno", "patron": "y"},
        ]})
