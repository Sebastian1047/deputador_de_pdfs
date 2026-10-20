"""Preferencias locales de escritorio; NO contiene tokens de acceso."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .core import leer_campos


def directorio_usuario() -> Path:
    if os.name == "nt":
        raiz = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return raiz / "DepuradorPDF"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "depurador-pdf"


PREFERENCIAS = {
    "consulta": "has:attachment filename:pdf newer_than:30d",
    "hoja_id": "",
    "pestana": "Registros",
    "oauth_json": "",
    "max_correos": 250,
}


def cargar_preferencias(carpeta: Path | None = None) -> dict:
    carpeta = carpeta or directorio_usuario()
    ubicacion = carpeta / "preferencias.json"
    if not ubicacion.exists():
        return dict(PREFERENCIAS)
    datos = json.loads(ubicacion.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        raise ValueError("Preferencias inválidas")
    return {**PREFERENCIAS, **{k: v for k, v in datos.items() if k in PREFERENCIAS}}


def guardar_preferencias(datos: dict, carpeta: Path | None = None) -> None:
    carpeta = carpeta or directorio_usuario()
    carpeta.mkdir(parents=True, exist_ok=True)
    valores = {k: datos[k] for k in PREFERENCIAS if k in datos}
    (carpeta / "preferencias.json").write_text(
        json.dumps(valores, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def cargar_reglas(carpeta: Path | None = None) -> str:
    carpeta = carpeta or directorio_usuario()
    ruta = carpeta / "campos.json"
    if not ruta.exists():
        return '{\n  "campos": []\n}\n'
    return ruta.read_text(encoding="utf-8")


def validar_reglas(contenido: str):
    datos = json.loads(contenido)
    if not isinstance(datos, dict) or not isinstance(datos.get("campos"), list):
        raise ValueError('Las reglas deben contener una lista llamada "campos"')
    return leer_campos(datos)


def guardar_reglas(contenido: str, carpeta: Path | None = None) -> None:
    validar_reglas(contenido)
    carpeta = carpeta or directorio_usuario()
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "campos.json").write_text(contenido, encoding="utf-8")
