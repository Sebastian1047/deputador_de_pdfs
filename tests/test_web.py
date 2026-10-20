"""Pruebas HTTP sin credenciales ni tráfico real a Google."""
import json
import re
import threading
from types import SimpleNamespace

import pytest
from werkzeug.security import generate_password_hash

from depurador import web


class ServiciosFalsos:
    def __call__(self):
        return object(), object()


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    reglas = tmp_path / "campos.json"
    reglas.write_text(json.dumps({
        "campos": [{"nombre": "identificador", "patron": r"Documento:\s*(\d+)", "obligatorio": True}]
    }), encoding="utf-8")
    app = web.create_app({
        "TESTING": True,
        "SECRET_KEY": "x" * 48,
        "ADMIN_USER": "analista",
        "ADMIN_PASSWORD_HASH": generate_password_hash("contrasena-muy-segura"),
        "SESSION_COOKIE_SECURE": False,
        "PDF_FIELDS_FILE": str(reglas),
        "GOOGLE_SPREADSHEET_ID": "spreadsheet-demo",
    }, service_factory=ServiciosFalsos())
    return app, app.test_client(), monkeypatch


def csrf(respuesta):
    encontrado = re.search(rb'name="_csrf" value="([^"]+)"', respuesta.data)
    assert encontrado
    return encontrado.group(1).decode()


def iniciar_sesion(client):
    token = csrf(client.get("/login"))
    r = client.post("/login", data={
        "_csrf": token, "usuario": "analista", "clave": "contrasena-muy-segura",
    })
    assert r.status_code == 302
    return csrf(client.get("/"))


def test_sin_login_no_accede_al_panel(entorno):
    _, client, _ = entorno
    assert client.get("/").status_code == 302
    assert "Iniciar sesión" in client.get("/login").text


def test_login_tiene_csrf_y_responde_a_credenciales(entorno):
    _, client, _ = entorno
    assert client.post("/login", data={"usuario": "analista", "clave": "x"}).status_code == 400
    token = csrf(client.get("/login"))
    assert client.post("/login", data={
        "_csrf": token, "usuario": "analista", "clave": "incorrecta"
    }).status_code == 200
    token = iniciar_sesion(client)
    assert token
    assert client.get("/").status_code == 200


def test_no_procesa_mensaje_que_no_fue_seleccionado(entorno):
    _, client, _ = entorno
    token = iniciar_sesion(client)
    respuesta = client.post("/procesar", data={"_csrf": token, "mensaje_id": "inventado"})
    assert respuesta.status_code == 400


def test_busca_y_procesa_solo_el_correo_de_la_lista(entorno):
    app, client, monkeypatch = entorno
    fin = threading.Event()
    usados = []

    class FakeReader:
        def __init__(self, service, filtro, cantidad=100):
            self.filtro = filtro
        def listar_correos(self):
            return [
                SimpleNamespace(id="aaaa1", fecha="20/10/2026", remitente="A",
                                asunto="Informe A", cantidad_pdf=40),
                SimpleNamespace(id="bbbb2", fecha="19/10/2026", remitente="B",
                                asunto="Informe B", cantidad_pdf=1),
            ]

    class FakeWriter:
        def __init__(self, *args):
            pass

    def fake_procesar(origen, destino, campos):
        usados.append(origen.mensaje_id)
        fin.set()
        return {"encontrados": 1, "agregados": 1, "duplicados": 0, "errores": 0}

    monkeypatch.setattr(web, "GmailReader", FakeReader)
    monkeypatch.setattr(web, "GoogleSheetsWriter", FakeWriter)
    monkeypatch.setattr(web, "procesar", fake_procesar)
    token = iniciar_sesion(client)
    assert client.post("/buscar", data={
        "_csrf": token, "filtro": "from:proveedor@example.com"
    }).status_code == 302
    pagina = client.get("/")
    assert "Informe A" in pagina.text and "Informe B" in pagina.text
    assert client.post("/procesar", data={
        "_csrf": token, "mensaje_id": "no-autorizado"
    }).status_code == 400
    assert client.post("/procesar", data={
        "_csrf": token, "mensaje_id": "bbbb2"
    }).status_code == 302
    assert fin.wait(3)
    assert usados == ["bbbb2"]
    assert "Agregados" in client.get("/").text


def test_sin_campos_reales_no_procesa(entorno, tmp_path, monkeypatch):
    app, client, _ = entorno
    token = iniciar_sesion(client)

    class FakeReader:
        def __init__(self, *args):
            pass
        def listar_correos(self):
            return [SimpleNamespace(id="aaaa1", fecha="hoy", remitente="A",
                                    asunto="Prueba", cantidad_pdf=40)]

    monkeypatch.setattr(web, "GmailReader", FakeReader)
    client.post("/buscar", data={"_csrf": token, "filtro": "filename:pdf"})
    vacio = tmp_path / "sin_campos.json"
    vacio.write_text('{"campos":[]}', encoding="utf-8")
    app.config["PDF_FIELDS_FILE"] = str(vacio)
    assert client.post("/procesar", data={
        "_csrf": token, "mensaje_id": "aaaa1"
    }).status_code == 302
    assert "Falta configurar los campos" in client.get("/").text
