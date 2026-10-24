"""Verificar que las recetas públicas de Windows jamás incluyan secretos ni abran LAN."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lanzador_local_restringido_a_loopback():
    launcher = (ROOT / "windows" / "Iniciar-PC.ps1").read_text(encoding="utf-8")
    template = (ROOT / "windows" / "config.local.ejemplo.ps1").read_text(encoding="utf-8")
    assert '127.0.0.1' in template
    assert 'WEB_SECURE_COOKIES = "false"' in template
    assert "http://localhost:8080/oauth/google/callback" in template
    assert '127.0.0.1' in launcher
    assert 'WEB_SECURE_COOKIES' in launcher
    assert 'ConvertFrom-Json' in launcher
    assert 'sheets_service_account.json' in template


def test_instalador_no_sobrescribe_config_privada_y_valida_pruebas():
    script = (ROOT / "windows" / "Instalar-PC.ps1").read_text(encoding="utf-8")
    assert "pip install -r requirements-web.txt" in script
    assert "pytest -q" in script
    assert "LOCALAPPDATA" in script
    assert 'if (-not (Test-Path -LiteralPath $config))' in script
    assert "RandomNumberGenerator" in script
    assert not (ROOT / "windows" / "config.local.ps1").exists()
