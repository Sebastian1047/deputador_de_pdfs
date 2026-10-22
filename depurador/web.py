"""Servidor web interno Flask + Waitress. No subir credenciales ni datos a GitHub."""
from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import secrets
import threading
import time
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .core import Campo, leer_campos, procesar
from .proveedores import GmailMensajeSeleccionado, GmailReader, GoogleSheetsWriter, crear_servicios_google, crear_servicio_google_sheets
from .outlook import OutlookMensajeSeleccionado, OutlookReader, crear_cliente_outlook
from .excel_online import ExcelOnlineWriter, GraphExcelFile, crear_excel_desde_onedrive
from .gmail_personal import crear_servicio_gmail_personal
from .oauth_web import iniciar_oauth, completar_oauth
from .google_drive_sheet import COLUMNAS as COLUMNAS_SOLE, GoogleSheetsCreditosWriter
from .sole_pdf import extraer_credito_sole

LOG = logging.getLogger(__name__)
CONSULTA = "has:attachment filename:pdf newer_than:30d"


def _reglas(ruta: str):
    with Path(ruta).open(encoding="utf-8") as archivo:
        datos = json.load(archivo)
    if datos.get("formato") == "creditos_sole":
        columnas = [campo.get("nombre") for campo in datos.get("campos", [])]
        if columnas != list(COLUMNAS_SOLE):
            raise ValueError("El esquema SOLE requiere exactamente las siete columnas")
        return [Campo(nombre, r"(?s).+", True) for nombre in columnas]
    return leer_campos(datos)


def create_app(config: dict | None = None, service_factory=None) -> Flask:
    """La inyección de servicios permite pruebas locales sin acceder a Gmail."""
    app = Flask(__name__, template_folder="web_templates", static_folder="web_static")
    app.config.update(
        SECRET_KEY=os.getenv("WEB_SECRET_KEY", ""),
        ADMIN_USER=os.getenv("WEB_ADMIN_USER", "administrador"),
        ADMIN_PASSWORD_HASH=os.getenv("WEB_PASSWORD_HASH", ""),
        ADMIN_PASSWORD=os.getenv("WEB_ADMIN_PASSWORD", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("WEB_SECURE_COOKIES", "true").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=16 * 1024,
        GMAIL_QUERY=os.getenv("GMAIL_QUERY") or CONSULTA,
        GMAIL_TOKEN_FILE=os.getenv("GMAIL_TOKEN_FILE") or "",
        GMAIL_OAUTH_CLIENT_FILE=os.getenv("GMAIL_OAUTH_CLIENT_FILE") or "",
        GMAIL_OAUTH_CLIENT_JSON=os.getenv("GMAIL_OAUTH_CLIENT_JSON") or "",
        GMAIL_REDIRECT_URI=os.getenv("GMAIL_REDIRECT_URI") or "",
        GMAIL_EXPECTED_EMAIL=os.getenv("GMAIL_EXPECTED_EMAIL") or "",
        MAIL_PROVIDER=(os.getenv("MAIL_PROVIDER") or "outlook").lower(),
        TABLE_PROVIDER=(os.getenv("TABLE_PROVIDER") or "excel_online").lower(),
        MS_EXCEL_DRIVE_ID=os.getenv("MS_EXCEL_DRIVE_ID") or "",
        MS_EXCEL_ITEM_ID=os.getenv("MS_EXCEL_ITEM_ID") or "",
        MS_EXCEL_SHEET=os.getenv("MS_EXCEL_SHEET") or "Registros",
        MS_ONEDRIVE_OWNER=os.getenv("MS_ONEDRIVE_OWNER") or "",
        MS_ONEDRIVE_PATH=os.getenv("MS_ONEDRIVE_PATH") or "",
        MAILBOX=os.getenv("MS_MAILBOX") or "",
        OUTLOOK_QUERY=os.getenv("OUTLOOK_QUERY") or "hasAttachments:true",
        MAX_EMAILS=min(250, max(1, int(os.getenv("MAX_EMAILS") or "100"))),
        GOOGLE_SPREADSHEET_ID=os.getenv("GOOGLE_SPREADSHEET_ID", ""),
        GOOGLE_SHEET_TAB=os.getenv("GOOGLE_SHEET_TAB") or "Registros",
        GOOGLE_SHEETS_TEMPLATE=os.getenv("GOOGLE_SHEETS_TEMPLATE") or "",
        PDF_FIELDS_FILE=os.getenv("PDF_FIELDS_FILE") or str(
            Path(__file__).resolve().parent.parent / "config" / "campos.json"
        ),
    )
    if config:
        app.config.update(config)
    # En un servicio cloud, el password puede ser un secreto de entorno.
    # Nunca guardar contraseñas sin cifrar en el repositorio.
    if not app.config["ADMIN_PASSWORD_HASH"] and app.config["ADMIN_PASSWORD"]:
        if len(app.config["ADMIN_PASSWORD"]) < 12:
            raise RuntimeError("WEB_ADMIN_PASSWORD debe tener al menos 12 caracteres")
        app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash(app.config["ADMIN_PASSWORD"])
    app.config.pop("ADMIN_PASSWORD", None)

    if not app.config.get("TESTING"):
        if len(app.config["SECRET_KEY"]) < 32 or not app.config["ADMIN_PASSWORD_HASH"]:
            raise RuntimeError(
                "Configure WEB_SECRET_KEY y WEB_PASSWORD_HASH o WEB_ADMIN_PASSWORD"
            )
    if app.config["MAIL_PROVIDER"] not in ("outlook", "gmail"):
        raise ValueError("MAIL_PROVIDER debe ser outlook o gmail")
    if app.config["TABLE_PROVIDER"] not in ("excel_online", "google_sheets"):
        raise ValueError("TABLE_PROVIDER debe ser excel_online o google_sheets")
    def servicio_correo():
        """Buscar en Gmail personal sin necesitar todavía los permisos de OneDrive."""
        if service_factory:
            return service_factory()[0]
        if app.config["MAIL_PROVIDER"] == "gmail":
            if app.config["GMAIL_TOKEN_FILE"]:
                esperado = app.config["GMAIL_EXPECTED_EMAIL"]
                if esperado:
                    return crear_servicio_gmail_personal(app.config["GMAIL_TOKEN_FILE"], esperado)
                return crear_servicio_gmail_personal(app.config["GMAIL_TOKEN_FILE"])
            # Mantener el conector heredado Gmail + Sheets para desarrollo.
            if app.config["TABLE_PROVIDER"] == "google_sheets":
                return crear_servicios_google()[0]
            raise RuntimeError("Gmail no está autorizado: configure GMAIL_TOKEN_FILE")
        return crear_cliente_outlook()

    def servicio_destino():
        if service_factory:
            return service_factory()[1]
        if app.config["TABLE_PROVIDER"] == "excel_online":
            from .outlook import crear_cliente_microsoft
            return crear_cliente_microsoft()
        return crear_servicio_google_sheets()

    def nuevo_lector(cliente, filtro, cantidad):
        if app.config["MAIL_PROVIDER"] == "outlook":
            return OutlookReader(cliente, app.config["MAILBOX"], filtro, cantidad)
        return GmailReader(cliente, filtro, cantidad)
    cache: dict[str, dict] = {}
    estados: dict[str, dict] = {}
    mutex = threading.Lock()
    candado_proceso = threading.Lock()
    intentos: dict[str, list[float]] = {}
    candado_intentos = threading.Lock()

    def _oauth_origen():
        return ("json:" + app.config["GMAIL_OAUTH_CLIENT_JSON"]
                if app.config["GMAIL_OAUTH_CLIENT_JSON"]
                else app.config["GMAIL_OAUTH_CLIENT_FILE"])

    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(32)
        return session["_csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.after_request
    def cabeceras(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    @app.before_request
    def verificar_csrf():
        if request.method == "POST":
            esperado = session.get("_csrf", "")
            recibido = request.form.get("_csrf", "")
            if not esperado or not hmac.compare_digest(esperado, recibido):
                abort(400, description="Solicitud inválida, recargue la página")

    def requiere_login(view):
        @wraps(view)
        def ejecutar(*args, **kwargs):
            if not session.get("autenticado") or not session.get("sid"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return ejecutar

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("autenticado"):
            return redirect(url_for("inicio"))
        if request.method == "POST":
            ip = request.remote_addr or "-"
            ahora = time.monotonic()
            with candado_intentos:
                recientes = [v for v in intentos.get(ip, []) if ahora - v < 300]
                bloqueado = len(recientes) >= 5
                if not bloqueado:
                    recientes.append(ahora)
                intentos[ip] = recientes
            if bloqueado:
                flash("Demasiados intentos. Vuelva a intentar más tarde.", "error")
            else:
                usuario = request.form.get("usuario", "")
                clave = request.form.get("clave", "")
                ok_usuario = hmac.compare_digest(usuario, app.config["ADMIN_USER"])
                hash_clave = app.config["ADMIN_PASSWORD_HASH"]
                ok_clave = bool(hash_clave) and check_password_hash(hash_clave, clave)
                if ok_usuario and ok_clave:
                    with candado_intentos:
                        intentos.pop(ip, None)
                    session.clear()
                    session["autenticado"] = True
                    session["sid"] = secrets.token_urlsafe(24)
                    session.permanent = True
                    csrf_token()
                    return redirect(url_for("inicio"))
                flash("Usuario o contraseña incorrectos.", "error")
        return render_template("login.html")

    def seleccion_actual(sid: str):
        with mutex:
            valor = cache.get(sid)
            if valor and valor["vence"] > time.monotonic():
                return valor
            cache.pop(sid, None)
            return None

    @app.get("/")
    @requiere_login
    def inicio():
        sid = session["sid"]
        seleccion = seleccion_actual(sid)
        with mutex:
            estado = dict(estados.get(sid, {"estado": "pendiente"}))
        return render_template(
            "inicio.html",
            correos=seleccion["correos"] if seleccion else [],
            filtro=seleccion["filtro"] if seleccion else (
                app.config["OUTLOOK_QUERY"] if app.config["MAIL_PROVIDER"] == "outlook"
                else app.config["GMAIL_QUERY"]
            ),
            proveedor="Outlook empresarial" if app.config["MAIL_PROVIDER"] == "outlook" else "Gmail",
            estado=estado,
            configurado=(bool((app.config["MS_ONEDRIVE_OWNER"] and app.config["MS_ONEDRIVE_PATH"]) or (app.config["MS_EXCEL_DRIVE_ID"] and app.config["MS_EXCEL_ITEM_ID"]))
                         if app.config["TABLE_PROVIDER"] == "excel_online"
                         else bool(app.config["GOOGLE_SPREADSHEET_ID"])),
            destino_nombre=("Excel Online" if app.config["TABLE_PROVIDER"] == "excel_online"
                            else "Google Sheets"),
            gmail_modo=app.config["MAIL_PROVIDER"] == "gmail",
            gmail_oauth_preparado=bool(
                (app.config["GMAIL_OAUTH_CLIENT_FILE"] or app.config["GMAIL_OAUTH_CLIENT_JSON"])
                and app.config["GMAIL_REDIRECT_URI"]
                and app.config["GMAIL_TOKEN_FILE"]
                and app.config["GMAIL_EXPECTED_EMAIL"]
            ),
        )

    @app.post("/oauth/google/conectar")
    @requiere_login
    def vincular_gmail_web():
        """Solo el administrador autenticado inicia OAuth desde el panel privado."""
        if app.config["MAIL_PROVIDER"] != "gmail":
            abort(404)
        if not all((
            (app.config["GMAIL_OAUTH_CLIENT_FILE"] or app.config["GMAIL_OAUTH_CLIENT_JSON"]), app.config["GMAIL_REDIRECT_URI"],
            app.config["GMAIL_TOKEN_FILE"], app.config["GMAIL_EXPECTED_EMAIL"],
        )):
            flash("Pendiente configurar OAuth web en el servidor.", "error")
            return redirect(url_for("inicio"))
        try:
            url, estado = iniciar_oauth(
                _oauth_origen(), app.config["GMAIL_REDIRECT_URI"]
            )
            session["gmail_oauth_state"] = estado
            session["gmail_oauth_inicio"] = time.time()
            return redirect(url, code=303)
        except (OSError, ValueError, RuntimeError) as exc:
            LOG.warning("No se pudo iniciar la autorización Gmail: %s", type(exc).__name__)
            flash("No fue posible iniciar la autorización. Revise OAuth en Windows Server.", "error")
            return redirect(url_for("inicio"))

    @app.get("/oauth/google/callback")
    @requiere_login
    def retorno_gmail_web():
        """Google devuelve el código al servidor, nunca a GitHub Pages."""
        if app.config["MAIL_PROVIDER"] != "gmail":
            abort(404)
        esperado = session.pop("gmail_oauth_state", None)
        iniciado = session.pop("gmail_oauth_inicio", 0)
        recibido = request.args.get("state", "")
        if (
            not esperado or not recibido or not hmac.compare_digest(esperado, recibido)
            or time.time() - iniciado > 600 or time.time() < iniciado
        ):
            abort(400, description="Estado de autorización inválido o vencido")
        if request.args.get("error"):
            flash("Se canceló o rechazó la autorización de Gmail.", "error")
            return redirect(url_for("inicio"))
        codigo = request.args.get("code", "")
        if not codigo:
            abort(400, description="Falta el código de autorización")
        try:
            completar_oauth(
                _oauth_origen(),
                app.config["GMAIL_REDIRECT_URI"],
                esperado, codigo,
                app.config["GMAIL_TOKEN_FILE"],
                app.config["GMAIL_EXPECTED_EMAIL"],
            )
            flash("Gmail autorizado correctamente. Puede buscar correos con PDF.", "exito")
        except (OSError, ValueError, RuntimeError, PermissionError) as exc:
            LOG.warning("Fallo de autorización Google: %s", type(exc).__name__)
            flash("La vinculación de Gmail no se completó. Revise configuración y cuenta.", "error")
        return redirect(url_for("inicio"))

    @app.post("/buscar")
    @requiere_login
    def buscar():
        filtro = (request.form.get("filtro") or "").strip()
        if not filtro or len(filtro) > 500:
            flash("Introduzca un filtro válido (máximo 500 caracteres).", "error")
            return redirect(url_for("inicio"))
        sid = session["sid"]
        with mutex:
            cache.pop(sid, None)
        try:
            correo_cliente = servicio_correo()
            correos = nuevo_lector(
                correo_cliente, filtro, app.config["MAX_EMAILS"]
            ).listar_correos()
            # En memoria, vinculados a la sesión; no se almacenan correos en disco.
            with mutex:
                cache[sid] = {
                    "correos": [
                        {"id": c.id, "fecha": c.fecha, "remitente": c.remitente,
                         "asunto": c.asunto, "pdf": c.cantidad_pdf}
                        for c in correos
                    ],
                    "filtro": filtro,
                    "vence": time.monotonic() + 900,
                }
            if not correos:
                flash("No se encontraron correos con PDF.", "info")
        except Exception as exc:
            LOG.warning("Fallo en búsqueda de correo: %s", type(exc).__name__)
            flash("No fue posible consultar el correo. Revise conexión y permisos.", "error")
        return redirect(url_for("inicio"))

    def ejecutar_proceso(sid: str, id_correo: str):
        try:
            campos = _reglas(app.config["PDF_FIELDS_FILE"])
            cliente = servicio_correo()
            destino_cliente = servicio_destino()
            lector = nuevo_lector(cliente, "", app.config["MAX_EMAILS"])
            if app.config["MAIL_PROVIDER"] == "outlook":
                origen = OutlookMensajeSeleccionado(lector, id_correo)
            else:
                origen = GmailMensajeSeleccionado(lector, id_correo)
            if app.config["TABLE_PROVIDER"] == "excel_online":
                if app.config["MS_ONEDRIVE_OWNER"] and app.config["MS_ONEDRIVE_PATH"]:
                    destino = crear_excel_desde_onedrive(
                        destino_cliente,
                        app.config["MS_ONEDRIVE_OWNER"], app.config["MS_ONEDRIVE_PATH"],
                        app.config["MS_EXCEL_SHEET"],
                    )
                else:
                    archivo = GraphExcelFile(
                        destino_cliente, app.config["MS_EXCEL_DRIVE_ID"], app.config["MS_EXCEL_ITEM_ID"]
                    )
                    destino = ExcelOnlineWriter(archivo, app.config["MS_EXCEL_SHEET"])
            else:
                if app.config["GOOGLE_SHEETS_TEMPLATE"] == "creditos_sole":
                    destino = GoogleSheetsCreditosWriter(
                        destino_cliente, app.config["GOOGLE_SPREADSHEET_ID"],
                        app.config["GOOGLE_SHEET_TAB"]
                    )
                else:
                    destino = GoogleSheetsWriter(
                        destino_cliente, app.config["GOOGLE_SPREADSHEET_ID"],
                        app.config["GOOGLE_SHEET_TAB"]
                    )
            extractor = (
                extraer_credito_sole
                if app.config["TABLE_PROVIDER"] == "google_sheets"
                and app.config["GOOGLE_SHEETS_TEMPLATE"] == "creditos_sole"
                else None
            )
            resumen = procesar(origen, destino, campos, extractor=extractor)
            if app.config["TABLE_PROVIDER"] == "excel_online":
                destino.finalizar()  # Solo se reporta éxito si el Excel se guardó correctamente.
            with mutex:
                estados[sid] = {
                    "estado": "terminado" if not resumen["errores"] else "parcial",
                    "resumen": resumen,
                }
        except Exception as exc:
            LOG.warning("Fallo al procesar correo seleccionado: %s", type(exc).__name__)
            with mutex:
                estados[sid] = {"estado": "error"}
        finally:
            candado_proceso.release()

    @app.post("/procesar")
    @requiere_login
    def procesar_seleccionado():
        sid = session["sid"]
        id_correo = request.form.get("mensaje_id", "")
        actual = seleccion_actual(sid)
        if not actual or id_correo not in {v["id"] for v in actual["correos"]}:
            abort(400, description="Seleccione primero un correo de la lista vigente")
        if app.config["TABLE_PROVIDER"] == "excel_online":
            configurado = bool((app.config["MS_ONEDRIVE_OWNER"] and app.config["MS_ONEDRIVE_PATH"]) or (app.config["MS_EXCEL_DRIVE_ID"] and app.config["MS_EXCEL_ITEM_ID"]))
        else:
            configurado = bool(app.config["GOOGLE_SPREADSHEET_ID"])
        if not configurado:
            flash("Falta configurar el Excel Online de destino en el servidor.", "error")
            return redirect(url_for("inicio"))
        try:
            if not _reglas(app.config["PDF_FIELDS_FILE"]):
                raise ValueError("Sin reglas")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            flash("Falta configurar los campos de extracción con un PDF de ejemplo.", "error")
            return redirect(url_for("inicio"))
        if not candado_proceso.acquire(blocking=False):
            flash("Ya existe un procesamiento activo. Espere a que termine.", "error")
            return redirect(url_for("inicio"))
        with mutex:
            estados[sid] = {"estado": "procesando"}
        try:
            hilo = threading.Thread(target=ejecutar_proceso, args=(sid, id_correo), daemon=True)
            hilo.start()
        except Exception:
            candado_proceso.release()
            with mutex:
                estados[sid] = {"estado": "error"}
            raise
        return redirect(url_for("inicio"))

    @app.post("/salir")
    @requiere_login
    def salir():
        sid = session["sid"]
        with mutex:
            cache.pop(sid, None)
            estados.pop(sid, None)
        session.clear()
        return redirect(url_for("login"))

    return app


def main():
    parser = argparse.ArgumentParser(description="Servidor local Depurador PDF")
    parser.add_argument("--hash-password", action="store_true",
                        help="Generar hash de contraseña sin guardarla en el repositorio")
    args = parser.parse_args()
    if args.hash_password:
        from getpass import getpass
        contrasena = getpass("Contraseña de acceso (no se mostrará): ")
        if len(contrasena) < 12:
            raise SystemExit("Utilice una contraseña de al menos 12 caracteres")
        print(generate_password_hash(contrasena))
        return

    from waitress import serve
    app = create_app()
    host = os.environ.get("WEB_HOST") or "127.0.0.1"
    puerto = int(os.environ.get("WEB_PORT") or "8080")
    if not 1 <= puerto <= 65535:
        raise ValueError("Puerto inválido")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    serve(app, host=host, port=puerto, threads=4)


if __name__ == "__main__":
    main()
