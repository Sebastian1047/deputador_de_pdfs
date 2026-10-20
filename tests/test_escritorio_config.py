import json

import pytest

from depurador.desktop_config import (
    cargar_preferencias,
    cargar_reglas,
    guardar_preferencias,
    guardar_reglas,
    validar_reglas,
)


def test_preferencias_no_guardan_campos_ajenos_ni_tokens(tmp_path):
    guardar_preferencias(
        {
            "consulta": "from:remitente@example.com has:attachment",
            "hoja_id": "abc",
            "refresh_token": "PROHIBIDO",
        }, tmp_path
    )
    contenido = (tmp_path / "preferencias.json").read_text()
    assert "PROHIBIDO" not in contenido
    assert cargar_preferencias(tmp_path)["hoja_id"] == "abc"
    assert cargar_preferencias(tmp_path)["pestana"] == "Registros"


def test_campos_desde_la_misma_configuracion_del_motor(tmp_path):
    assert validar_reglas(cargar_reglas(tmp_path)) == []
    ejemplo = {"campos": [{"nombre": "numero", "patron": r"Nº:\s*(\d+)", "obligatorio": True}]}
    guardar_reglas(json.dumps(ejemplo), tmp_path)
    assert validar_reglas(cargar_reglas(tmp_path))[0].nombre == "numero"


@pytest.mark.parametrize("contenido", ["{", "[]", '{"campos": 7}'])
def test_campos_invalidos_no_se_guardan(tmp_path, contenido):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        guardar_reglas(contenido, tmp_path)
    assert not (tmp_path / "campos.json").exists()
