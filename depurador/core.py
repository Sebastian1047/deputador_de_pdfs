"""Reglas de extracción y orquestación independientes del proveedor."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping, Protocol, Sequence

import fitz

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdjuntoPDF:
    clave: str
    contenido: bytes


@dataclass(frozen=True)
class Campo:
    nombre: str
    patron: str
    obligatorio: bool = False


class LectorCorreo(Protocol):
    def adjuntos_pdf(self) -> Iterable[AdjuntoPDF]: ...


class EscritorTabla(Protocol):
    def claves_existentes(self, campos: Sequence[Campo]) -> set[str]: ...
    def agregar(self, clave: str, fecha_utc: str, datos: Sequence[str]) -> None: ...


def leer_campos(config: Mapping) -> list[Campo]:
    resultado = []
    nombres = set()
    for item in config.get("campos", []):
        nombre = item["nombre"].strip()
        patron = item["patron"]
        if not nombre or nombre in nombres:
            raise ValueError("Los nombres de campos deben ser únicos y no vacíos")
        if not isinstance(patron, str) or not patron.strip():
            raise ValueError("Cada campo necesita un patrón de extracción")
        re.compile(patron)
        resultado.append(Campo(nombre, patron, bool(item.get("obligatorio", False))))
        nombres.add(nombre)
    return resultado


def extraer_datos(contenido: bytes, campos: Sequence[Campo]) -> list[str]:
    """Procesa bytes en memoria: no guarda el PDF en el disco."""
    with fitz.open(stream=contenido, filetype="pdf") as pdf:
        texto = "\n".join(pagina.get_text(sort=True) for pagina in pdf)
    if not texto.strip():
        raise ValueError("PDF sin texto extraíble; requerirá OCR")
    salida = []
    for campo in campos:
        encontrado = re.search(campo.patron, texto, flags=re.IGNORECASE | re.MULTILINE)
        if encontrado:
            valor = encontrado.group(1) if encontrado.lastindex else encontrado.group(0)
            salida.append(" ".join(valor.strip().split()))
        elif campo.obligatorio:
            raise ValueError("No se pudo extraer un campo obligatorio: " + campo.nombre)
        else:
            salida.append("")
    return salida


def procesar(correo: LectorCorreo, tabla: EscritorTabla, campos: Sequence[Campo],
            extractor: Callable[[bytes, Sequence[Campo]], list[str]] | None = None) -> dict[str, int]:
    if not campos:
        raise ValueError("Configure los campos de extracción antes de procesar correos reales")
    conocidas = tabla.claves_existentes(campos)
    resumen = {"encontrados": 0, "agregados": 0, "duplicados": 0, "errores": 0}
    for adjunto in correo.adjuntos_pdf():
        resumen["encontrados"] += 1
        if adjunto.clave in conocidas:
            resumen["duplicados"] += 1
            continue
        try:
            valores = (extractor or extraer_datos)(adjunto.contenido, campos)
            # La plantilla histórica ya tiene QC Inspection, pero carece de
            # document_key. Evitar importar de nuevo un crédito ya registrado.
            if hasattr(tabla, "es_registro_historico") and tabla.es_registro_historico(valores):
                resumen["duplicados"] += 1
                continue
            fecha = datetime.now(timezone.utc).isoformat(timespec="seconds")
            tabla.agregar(adjunto.clave, fecha, valores)
            conocidas.add(adjunto.clave)
            resumen["agregados"] += 1
        except Exception as error:
            # Nunca registrar nombres, texto de PDF ni credenciales en logs públicos.
            resumen["errores"] += 1
            LOG.warning("Un documento no pudo procesarse (%s)", type(error).__name__)
    return resumen
