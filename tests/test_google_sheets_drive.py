"""Conexión Google Sheets en Drive sin permisos de Gmail ni Drive completos."""
import json
from unittest.mock import MagicMock

import pytest

from depurador.proveedores import crear_servicio_google_sheets


def test_conector_sheets_usa_cuenta_servicio_y_permisos_solo_sheets(monkeypatch):
    import google.oauth2.service_account as sa
    import googleapiclient.discovery as disc
    data = {
        "type": "service_account",
        "client_email": "lector-escritor@example-project.iam.gserviceaccount.com",
        "private_key": "FAKE_TEST_KEY",
    }
    monkeypatch.setenv("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON", json.dumps(data))
    cred = object()
    calls = []

    def load(data_loaded, scopes):
        assert data_loaded == data
        assert scopes == ["https://www.googleapis.com/auth/spreadsheets"]
        calls.append("service_account")
        return cred

    monkeypatch.setattr(sa.Credentials, "from_service_account_info", load)
    fake = MagicMock()
    monkeypatch.setattr(
        disc, "build",
        lambda name, version, credentials, cache_discovery: (
            calls.append(("build", name, version, credentials is cred)),
            fake
        )[-1]
    )
    assert crear_servicio_google_sheets() is fake
    assert calls == ["service_account", ("build", "sheets", "v4", True)]


def test_conector_sheets_rechaza_json_cuenta_incorrecta(monkeypatch):
    monkeypatch.setenv(
        "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON",
        json.dumps({"type": "authorized_user", "refresh_token": "fake"}),
    )
    with pytest.raises(ValueError, match="cuenta de servicio"):
        crear_servicio_google_sheets()
