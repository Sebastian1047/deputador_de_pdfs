"""Pruebas básicas del despliegue Render sin datos ni cuentas reales."""
import os
import re
import json

from depurador.web import create_app
from depurador.oauth_web import crear_flujo_web


def test_web_publica_healthcheck_sin_autenticacion(monkeypatch):
    monkeypatch.setenv("WEB_SECRET_KEY", "s" * 48)
    monkeypatch.setenv("WEB_ADMIN_PASSWORD", "una-contrasena-de-pruebas")
    monkeypatch.delenv("WEB_PASSWORD_HASH", raising=False)
    app = create_app({
        "MAIL_PROVIDER": "gmail", "TABLE_PROVIDER": "excel_online",
        "SESSION_COOKIE_SECURE": False,
    })
    assert "ADMIN_PASSWORD" not in app.config
    cliente = app.test_client()
    assert cliente.get("/health").json == {"status": "ok"}
    assert cliente.get("/").status_code == 302
    html = cliente.get("/login").data
    csrf = re.search(rb'name="_csrf" value="([^"]+)"', html).group(1).decode()
    resultado = cliente.post("/login", data={
        "_csrf": csrf, "usuario": "administrador",
        "clave": "una-contrasena-de-pruebas",
    })
    assert resultado.status_code == 302
    assert cliente.get("/").status_code == 200


def test_web_rechaza_password_corto_en_nube(monkeypatch):
    import pytest
    monkeypatch.setenv("WEB_SECRET_KEY", "s" * 48)
    monkeypatch.setenv("WEB_ADMIN_PASSWORD", "corta")
    monkeypatch.delenv("WEB_PASSWORD_HASH", raising=False)
    with pytest.raises(RuntimeError, match="12 caracteres"):
        create_app()


def test_oauth_cliente_web_puede_configurarse_por_secreto_de_entorno():
    fake = {
        "web": {
            "client_id": "fake-client-id.apps.googleusercontent.com",
            "client_secret": "fake-private-value",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["https://ejemplo.onrender.com/oauth/google/callback"],
        }
    }
    flujo = crear_flujo_web(
        "json:" + json.dumps(fake),
        "https://ejemplo.onrender.com/oauth/google/callback",
    )
    assert flujo.redirect_uri == "https://ejemplo.onrender.com/oauth/google/callback"


def test_blueprint_no_incluye_secreto_real():
    from pathlib import Path
    texto = Path("render.yaml").read_text(encoding="utf-8")
    assert "plan: free" in texto
    assert "WEB_SECRET_KEY" in texto and "generateValue: true" in texto
    assert "WEB_ADMIN_PASSWORD" in texto and "sync: false" in texto
    assert "MAIL_PROVIDER" in texto and "value: gmail" in texto
    assert "/health" in texto
