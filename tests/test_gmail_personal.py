"""Gmail personal en la web Windows Server: pruebas sin acceso a cuentas reales."""
import json
import re
from types import SimpleNamespace

import pytest
from werkzeug.security import generate_password_hash

from depurador import web
from depurador.gmail_personal import GMAIL_SCOPE, _token_path, cargar_credenciales


def test_gmail_personal_acepta_excel_online_sin_exigir_outlook(tmp_path, monkeypatch):
    archivo = tmp_path / "token_gmail.json"
    monkeypatch.setattr(web, "crear_servicio_gmail_personal", lambda path: ("GMAIL_FICTICIO", path))

    class FakeReader:
        def __init__(self, servicio, filtro, cantidad):
            assert servicio[0] == "GMAIL_FICTICIO"
            assert filtro == "filename:pdf"
            assert cantidad > 0

        def listar_correos(self):
            return [SimpleNamespace(
                id="id_gmail_123", fecha="22/10/2026", remitente="proveedor@example.com",
                asunto="PDF recibidos", cantidad_pdf=40
            )]

    monkeypatch.setattr(web, "GmailReader", FakeReader)

    app = web.create_app({
        "TESTING": True,
        "SECRET_KEY": "s" * 48,
        "ADMIN_USER": "usuario",
        "ADMIN_PASSWORD_HASH": generate_password_hash("contrasena-segura"),
        "MAIL_PROVIDER": "gmail",
        "TABLE_PROVIDER": "excel_online",
        "GMAIL_TOKEN_FILE": str(archivo),
        "GOOGLE_SPREADSHEET_ID": "",
        "MS_EXCEL_DRIVE_ID": "",
        "MS_EXCEL_ITEM_ID": "",
        "SESSION_COOKIE_SECURE": False,
    })
    client = app.test_client()
    html = client.get("/login").data
    csrf = re.search(rb'name="_csrf" value="([^"]+)"', html).group(1).decode()
    client.post("/login", data={
        "_csrf": csrf, "usuario": "usuario", "clave": "contrasena-segura"
    })
    home = client.get("/")
    csrf = re.search(rb'name="_csrf" value="([^"]+)"', home.data).group(1).decode()
    r = client.post("/buscar", data={"_csrf": csrf, "filtro": "filename:pdf"})
    assert r.status_code == 302
    assert "PDF recibidos" in client.get("/").text
    # Aunque hay Gmail real, Excel empresarial aún no permite guardar.
    guardado = client.post("/procesar", data={
        "_csrf": csrf, "mensaje_id": "id_gmail_123"
    })
    assert guardado.status_code == 302
    assert "Falta configurar" in client.get("/").text


def test_token_personal_exige_ruta_absoluta(tmp_path):
    with pytest.raises(ValueError, match="absoluta"):
        _token_path("secretos/token.json")
    assert _token_path(str(tmp_path / "token.json")).is_absolute()


def test_token_solo_lectura_rechaza_scope_extra(tmp_path):
    archivo = tmp_path / "token.json"
    archivo.write_text(json.dumps({
        "refresh_token": "TOKEN_FICTICIO",
        "scopes": [GMAIL_SCOPE, "https://www.googleapis.com/auth/gmail.modify"],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="solo de lectura"):
        cargar_credenciales(str(archivo))


def test_token_solo_lectura_rechaza_token_sin_refresh(tmp_path):
    archivo = tmp_path / "token.json"
    archivo.write_text(json.dumps({
        "refresh_token": "", "scopes": [GMAIL_SCOPE]
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="renovación"):
        cargar_credenciales(str(archivo))



def test_validacion_gmail_permite_la_cuenta_exacta_sin_distinguir_mayusculas():
    from depurador.gmail_personal import validar_cuenta_gmail

    class Get:
        def execute(self):
            return {"emailAddress": "PRUEBAS@EXAMPLE.COM"}
    class Users:
        def getProfile(self, userId):
            assert userId == "me"
            return Get()
    class Gmail:
        def users(self):
            return Users()
    validar_cuenta_gmail(Gmail(), "pruebas@example.com")


def test_validacion_gmail_rechaza_cuenta_incorrecta_sin_revelar_identidad():
    from depurador.gmail_personal import validar_cuenta_gmail

    class Get:
        def execute(self):
            return {"emailAddress": "otra@example.com"}
    class Users:
        def getProfile(self, userId):
            return Get()
    class Gmail:
        def users(self):
            return Users()
    with pytest.raises(PermissionError, match="no coincide") as error:
        validar_cuenta_gmail(Gmail(), "pruebas@example.com")
    assert "otra@example.com" not in str(error.value)
    assert "pruebas@example.com" not in str(error.value)


def test_servidor_transmite_solo_la_cuenta_esperada_al_conector(tmp_path, monkeypatch):
    configuraciones = []
    monkeypatch.setattr(
        web, "crear_servicio_gmail_personal",
        lambda ruta, esperado: configuraciones.append((ruta, esperado)) or "GMAIL_FICTICIO"
    )
    app = web.create_app({
        "TESTING": True,
        "SECRET_KEY": "x" * 48,
        "MAIL_PROVIDER": "gmail",
        "TABLE_PROVIDER": "excel_online",
        "GMAIL_TOKEN_FILE": str(tmp_path / "token.json"),
        "GMAIL_EXPECTED_EMAIL": "pruebas@example.com",
    })
    # Para ejercitar el flujo protegido, usar rutas de la misma manera que la interfaz.
    # No es necesario conectarse a Google ni proporcionar credenciales reales.
    from werkzeug.security import generate_password_hash
    app.config["ADMIN_USER"] = "analista"
    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("contrasena-segura")
    app.config["SESSION_COOKIE_SECURE"] = False
    client = app.test_client()
    html = client.get("/login").data
    csrf = re.search(rb'name="_csrf" value="([^"]+)"', html).group(1).decode()
    client.post("/login", data={
        "_csrf": csrf, "usuario": "analista", "clave": "contrasena-segura"
    })
    html = client.get("/").data
    csrf = re.search(rb'name="_csrf" value="([^"]+)"', html).group(1).decode()
    # GmailReader real no puede consultar datos ficticios, pero el servicio se llamó y se validó.
    client.post("/buscar", data={"_csrf": csrf, "filtro": "filename:pdf"})
    assert configuraciones == [(str(tmp_path / "token.json"), "pruebas@example.com")]
