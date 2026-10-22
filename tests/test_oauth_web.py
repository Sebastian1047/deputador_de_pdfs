"""OAuth Gmail web: prueba de inicio, callback, estado y rutas sin conexiones reales."""
import json
import re

import pytest
from werkzeug.security import generate_password_hash

from depurador import web
from depurador.oauth_web import validar_uri_retorno, crear_flujo_web


def app_cliente(tmp_path):
    app = web.create_app({
        "TESTING": True,
        "SECRET_KEY": "w" * 48,
        "ADMIN_USER": "admin",
        "ADMIN_PASSWORD_HASH": generate_password_hash("contrasena-larga-segura"),
        "MAIL_PROVIDER": "gmail",
        "TABLE_PROVIDER": "excel_online",
        "SESSION_COOKIE_SECURE": False,
        "GMAIL_OAUTH_CLIENT_FILE": str(tmp_path / "client_google.json"),
        "GMAIL_REDIRECT_URI": "https://mi-dominio.example/oauth/google/callback",
        "GMAIL_TOKEN_FILE": str(tmp_path / "token_gmail.json"),
        "GMAIL_EXPECTED_EMAIL": "pruebas@example.com",
    })
    cliente = app.test_client()
    html = cliente.get("/login").data
    csrf = re.search(rb'name="_csrf" value="([^"]+)"', html).group(1).decode()
    login = cliente.post("/login", data={
        "_csrf": csrf, "usuario": "admin", "clave": "contrasena-larga-segura"
    })
    assert login.status_code == 302
    html = cliente.get("/").data
    csrf = re.search(rb'name="_csrf" value="([^"]+)"', html).group(1).decode()
    return app, cliente, csrf


def test_oauth_web_exige_sesion_y_csrf(tmp_path):
    _, client, token = app_cliente(tmp_path)
    sin_csrf = client.post("/oauth/google/conectar")
    assert sin_csrf.status_code == 400
    # Logout y comprobar que no permite vincular sin sesión.
    client.post("/salir", data={"_csrf": token})
    nueva = client.get("/oauth/google/callback?state=falso&code=falso")
    assert nueva.status_code == 302
    assert "/login" in nueva.headers["Location"]


def test_oauth_web_inicia_y_verifica_estado_de_google(tmp_path, monkeypatch):
    _, cliente, csrf = app_cliente(tmp_path)
    llamadas = []
    monkeypatch.setattr(
        web, "iniciar_oauth",
        lambda client_file, uri: (
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=ejemplo", "ESTADO_SEGURO"
        ),
    )
    monkeypatch.setattr(
        web, "completar_oauth",
        lambda *args: llamadas.append(args),
    )
    inicio = cliente.post("/oauth/google/conectar", data={"_csrf": csrf})
    assert inicio.status_code == 303
    assert inicio.headers["Location"].startswith("https://accounts.google.com/")
    with cliente.session_transaction() as session:
        assert session["gmail_oauth_state"] == "ESTADO_SEGURO"
    incorrecto = cliente.get("/oauth/google/callback?state=OTRO&code=prueba")
    assert incorrecto.status_code == 400
    assert not llamadas
    inicio = cliente.post("/oauth/google/conectar", data={"_csrf": csrf})
    correcto = cliente.get("/oauth/google/callback?state=ESTADO_SEGURO&code=CODIGO_PRUEBA")
    assert correcto.status_code == 302
    assert len(llamadas) == 1
    assert llamadas[0][2] == "ESTADO_SEGURO"
    assert llamadas[0][3] == "CODIGO_PRUEBA"
    assert llamadas[0][5] == "pruebas@example.com"
    repetido = cliente.get("/oauth/google/callback?state=ESTADO_SEGURO&code=CODIGO_PRUEBA")
    assert repetido.status_code == 400
    assert "autorizado correctamente" in cliente.get("/").text


def test_oauth_web_rechaza_respuesta_google_vencida(tmp_path, monkeypatch):
    _, cliente, csrf = app_cliente(tmp_path)
    monkeypatch.setattr(
        web, "iniciar_oauth",
        lambda a, b: ("https://accounts.google.com/o/oauth2/v2/auth", "ESTADO"),
    )
    cliente.post("/oauth/google/conectar", data={"_csrf": csrf})
    with cliente.session_transaction() as session:
        session["gmail_oauth_inicio"] = 1
    assert cliente.get("/oauth/google/callback?state=ESTADO&code=prueba").status_code == 400


@pytest.mark.parametrize("uri", [
    "http://mi-dominio.example/oauth/google/callback",
    "https://mi-dominio.example/callback",
    "https://usuario:clave@mi-dominio.example/oauth/google/callback",
    "https://mi-dominio.example/oauth/google/callback?token=foo",
    "https://mi-dominio.example/oauth/google/callback#fragmento",
    "",
])
def test_retorno_web_rechaza_uri_no_aprobada(uri):
    with pytest.raises(ValueError, match="GMAIL_REDIRECT_URI"):
        validar_uri_retorno(uri)


def test_retorno_web_permite_https_y_localhost_desarrollo():
    assert validar_uri_retorno("https://app.ejemplo.com/oauth/google/callback")
    assert validar_uri_retorno("http://localhost:8080/oauth/google/callback")


def test_oauth_web_requiere_json_cliente_web(tmp_path):
    archivo = tmp_path / "json.json"
    archivo.write_text(json.dumps({"installed": {"client_id": "ficticio"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Aplicación web"):
        crear_flujo_web(str(archivo), "https://app.ejemplo.com/oauth/google/callback")
