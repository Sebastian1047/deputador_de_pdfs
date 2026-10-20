"""Aplicación de escritorio Tkinter: mismo motor de extracción de la versión web."""
from __future__ import annotations

import json
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import AdjuntoPDF, Campo, procesar
from .desktop_auth import autenticar, servicios
from .desktop_config import (
    cargar_preferencias,
    cargar_reglas,
    directorio_usuario,
    guardar_preferencias,
    guardar_reglas,
    validar_reglas,
)
from .proveedores import GmailReader, GoogleSheetsWriter

FONDO = "#f2f7f4"
VERDE = "#145b43"
TEXTO = "#173d2e"
SUAVE = "#5c7369"


def _id_hoja(entrada: str) -> str:
    entrada = entrada.strip()
    encontrado = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", entrada)
    return encontrado.group(1) if encontrado else entrada


def _prueba_local() -> tuple[dict[str, int], str]:
    """Prueba el motor real en memoria sin Gmail, Drive ni credenciales."""
    import fitz

    documento = fitz.open()
    pagina = documento.new_page()
    pagina.insert_text((50, 85), "Documento: DEMO-001\nFecha: 20/10/2026\nTotal: 125")
    pdf = documento.tobytes()
    documento.close()

    class CorreoPrueba:
        def adjuntos_pdf(self):
            yield AdjuntoPDF("demo:1", pdf)

    class TablaPrueba:
        def __init__(self):
            self.filas = []
        def claves_existentes(self, campos):
            return set()
        def agregar(self, clave, fecha_utc, valores):
            self.filas.append(valores)

    campos = [
        Campo("documento", r"Documento:\s*([A-Z0-9-]+)", True),
        Campo("fecha", r"Fecha:\s*(\d{2}/\d{2}/\d{4})", True),
        Campo("total", r"Total:\s*(\d+)", True),
    ]
    tabla = TablaPrueba()
    resultado = procesar(CorreoPrueba(), tabla, campos)
    return resultado, "Ejemplo extraído: Documento=DEMO-001; Fecha=20/10/2026; Total=125."


class Escritorio:
    def __init__(self, ventana: tk.Tk):
        self.ventana = ventana
        self.ventana.title("Depurador de PDF — Escritorio 0.2.0")
        self.ventana.geometry("870x680")
        self.ventana.minsize(720, 590)
        self.ventana.configure(background=FONDO)
        self.eventos: queue.Queue = queue.Queue()
        self.ocupado = False
        self.carpeta = directorio_usuario()
        self.preferencias = cargar_preferencias(self.carpeta)
        self._construir()
        self.ventana.after(150, self._escuchar)

    def _construir(self):
        tema = ttk.Style(self.ventana)
        tema.theme_use("clam")
        tema.configure("TNotebook", background=FONDO, borderwidth=0)
        tema.configure("TNotebook.Tab", padding=(20, 12), font=("Segoe UI", 10))
        tema.map("TNotebook.Tab", background=[("selected", "#d5eddf")])
        tema.configure("TEntry", padding=6)
        tema.configure("TButton", padding=(12, 9), font=("Segoe UI", 10))
        tema.configure("Accent.TButton", foreground="white", background=VERDE)
        tema.map("Accent.TButton", background=[("active", "#1e7556")])
        tema.configure("TLabel", background=FONDO, foreground=TEXTO, font=("Segoe UI", 10))

        barra = tk.Frame(self.ventana, bg=VERDE, height=98)
        barra.pack(fill="x")
        tk.Label(
            barra, text="Depurador de PDF", font=("Segoe UI", 22, "bold"),
            bg=VERDE, fg="white"
        ).pack(anchor="w", padx=26, pady=(15, 0))
        tk.Label(
            barra, text="Gmail  →  Extracción Python  →  Google Sheets",
            bg=VERDE, fg="#c8e7d8", font=("Segoe UI", 10)
        ).pack(anchor="w", padx=28, pady=(1, 13))

        base = tk.Frame(self.ventana, bg=FONDO)
        base.pack(fill="both", expand=True, padx=23, pady=18)
        pestanas = ttk.Notebook(base)
        pestanas.pack(fill="both", expand=True)
        ejecucion = ttk.Frame(pestanas)
        reglas = ttk.Frame(pestanas)
        pestanas.add(ejecucion, text="Operación y conexiones")
        pestanas.add(reglas, text="Campos de los PDF")
        for panel in (ejecucion, reglas):
            panel.configure(padding=18)

        self.consulta = tk.StringVar(value=self.preferencias["consulta"])
        self.hoja = tk.StringVar(value=self.preferencias["hoja_id"])
        self.pestana = tk.StringVar(value=self.preferencias["pestana"])
        self.json_cliente = tk.StringVar(value=self.preferencias["oauth_json"])
        self.cantidad = tk.StringVar(value=str(self.preferencias["max_correos"]))
        self.estado = tk.StringVar(value="Listo para probar con datos ficticios.")

        self._campo(ejecucion, "Filtro de Gmail", self.consulta, 0)
        self._campo(ejecucion, "ID o URL de Google Sheets (Drive)", self.hoja, 1)
        self._campo(ejecucion, "Nombre de la pestaña del documento", self.pestana, 2)

        ttk.Label(ejecucion, text="Archivo OAuth de Google Cloud (JSON)").grid(
            row=3, column=0, sticky="w", pady=(9, 2)
        )
        archivo = ttk.Frame(ejecucion)
        archivo.grid(row=4, column=0, sticky="ew")
        ttk.Entry(archivo, textvariable=self.json_cliente).pack(side="left", fill="x", expand=True)
        ttk.Button(archivo, text="Elegir JSON", command=self._buscar_json).pack(side="left", padx=(8, 0))
        self._campo(ejecucion, "Máximo de correos por ejecución", self.cantidad, 5)

        operaciones = ttk.Frame(ejecucion)
        operaciones.grid(row=7, column=0, sticky="ew", pady=(17, 5))
        self.boton_demo = ttk.Button(
            operaciones, text="Probar sin conexión", command=lambda: self._iniciar("demo")
        )
        self.boton_demo.pack(side="left", padx=(0, 7))
        self.boton_conectar = ttk.Button(
            operaciones, text="Conectar Google", command=lambda: self._iniciar("conectar")
        )
        self.boton_conectar.pack(side="left", padx=(0, 7))
        self.boton_procesar = ttk.Button(
            operaciones, text="Procesar ahora", style="Accent.TButton",
            command=lambda: self._iniciar("procesar")
        )
        self.boton_procesar.pack(side="left")

        estado = ttk.Label(ejecucion, textvariable=self.estado, foreground=SUAVE, wraplength=730)
        estado.grid(row=8, column=0, sticky="w", pady=(9, 8))
        self.salida = tk.Text(
            ejecucion, height=7, state="disabled", relief="flat",
            bg="#e6f0e9", fg=TEXTO, font=("Consolas", 10),
            padx=12, pady=10, wrap="word"
        )
        self.salida.grid(row=9, column=0, sticky="nsew")
        ejecucion.columnconfigure(0, weight=1)
        ejecucion.rowconfigure(9, weight=1)
        ttk.Label(ejecucion, text="Los PDF se leen en memoria; no se descargan a carpetas.").grid(
            row=10, column=0, sticky="w", pady=(9, 0)
        )

        ttk.Label(
            reglas, text="Configure los datos que se extraerán de cada documento.",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        ttk.Label(
            reglas, text="Una regla por campo: nombre, patrón de extracción y si es obligatorio.",
            foreground=SUAVE
        ).pack(anchor="w", pady=(6, 9))
        self.editor = tk.Text(reglas, font=("Consolas", 11), bg="#fff",
                              fg=TEXTO, relief="solid", bd=1, wrap="none")
        self.editor.pack(fill="both", expand=True)
        self.editor.insert("1.0", cargar_reglas(self.carpeta))
        fila = ttk.Frame(reglas)
        fila.pack(fill="x", pady=(12, 2))
        ttk.Button(fila, text="Importar JSON", command=self._importar_reglas).pack(side="left")
        ttk.Button(fila, text="Guardar campos", style="Accent.TButton",
                   command=lambda: self._guardar(mostrar=True)).pack(side="right")
        ttk.Label(
            reglas, text='Ejemplo: {"campos":[{"nombre":"numero","patron":"Documento: ([0-9]+)","obligatorio":true}]}',
            foreground=SUAVE, wraplength=760
        ).pack(anchor="w", pady=(8, 0))

    def _campo(self, marco, etiqueta, variable, fila):
        # Las filas se numeran explícitamente para mantener alineadas las entradas.
        ttk.Label(marco, text=etiqueta).grid(
            row=fila * 2 if fila <= 2 else fila + 1,
            column=0, sticky="w", pady=(8, 2)
        )
        ttk.Entry(marco, textvariable=variable).grid(
            row=fila * 2 + 1 if fila <= 2 else fila + 2,
            column=0, sticky="ew"
        )

    def _buscar_json(self):
        ruta = filedialog.askopenfilename(
            title="Credenciales OAuth para aplicación de escritorio",
            filetypes=[("Archivos JSON", "*.json")]
        )
        if ruta:
            self.json_cliente.set(ruta)

    def _importar_reglas(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar reglas", filetypes=[("JSON", "*.json")]
        )
        if ruta:
            try:
                texto = Path(ruta).read_text(encoding="utf-8")
                validar_reglas(texto)
            except (OSError, ValueError, json.JSONDecodeError):
                messagebox.showerror("Reglas inválidas", "El archivo no contiene reglas válidas.")
                return
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", texto)

    def _guardar(self, mostrar=False) -> bool:
        try:
            cantidad = int(self.cantidad.get().strip())
            if not 1 <= cantidad <= 500:
                raise ValueError("El máximo de correos debe estar entre 1 y 500")
            if not self.pestana.get().strip():
                raise ValueError("Escriba el nombre de la pestaña de destino")
            reglas = self.editor.get("1.0", "end-1c")
            validar_reglas(reglas)
            preferencias = {
                "consulta": self.consulta.get().strip(),
                "hoja_id": _id_hoja(self.hoja.get()),
                "pestana": self.pestana.get().strip(),
                "oauth_json": self.json_cliente.get().strip(),
                "max_correos": cantidad,
            }
            guardar_preferencias(preferencias, self.carpeta)
            guardar_reglas(reglas, self.carpeta)
            if mostrar:
                self.estado.set("Preferencias y campos guardados únicamente en este equipo.")
            return True
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Revisar configuración", str(error))
            return False

    def _iniciar(self, operacion: str):
        if self.ocupado or not self._guardar():
            return
        if operacion == "procesar":
            if not self.hoja.get().strip():
                messagebox.showwarning("Falta Google Sheets", "Introduzca el ID de la hoja de destino.")
                return
            if not validar_reglas(self.editor.get("1.0", "end-1c")):
                messagebox.showwarning("Faltan campos", "Configure los campos con un PDF de ejemplo.")
                return
        if operacion != "demo" and not self.json_cliente.get().strip():
            messagebox.showwarning(
                "Faltan credenciales", "Seleccione el JSON OAuth de escritorio de Google Cloud."
            )
            return
        self.ocupado = True
        for boton in (self.boton_demo, self.boton_conectar, self.boton_procesar):
            boton.configure(state="disabled")
        self.estado.set("Ejecutando " + ("prueba local..." if operacion == "demo" else "operación..."))
        parametros = {
            "consulta": self.consulta.get().strip(),
            "id": _id_hoja(self.hoja.get()),
            "pestana": self.pestana.get().strip(),
            "json": self.json_cliente.get().strip(),
            "max": int(self.cantidad.get()),
            "reglas": self.editor.get("1.0", "end-1c"),
        }
        threading.Thread(
            target=self._trabajo, args=(operacion, parametros), daemon=True
        ).start()

    def _trabajo(self, operacion: str, config: dict):
        try:
            if operacion == "demo":
                resultado, detalle = _prueba_local()
            else:
                credenciales = autenticar(
                    config["json"], self.carpeta / "token_google.json"
                )
                if operacion == "conectar":
                    resultado, detalle = None, "Cuenta de Google autorizada en este portátil."
                else:
                    gmail, sheets = servicios(credenciales)
                    lector = GmailReader(gmail, config["consulta"], config["max"])
                    destino = GoogleSheetsWriter(sheets, config["id"], config["pestana"])
                    resultado = procesar(
                        lector, destino, validar_reglas(config["reglas"])
                    )
                    detalle = "Lectura de Gmail y actualización de Google Sheets finalizadas."
            self.eventos.put(("ok", resultado, detalle))
        except Exception as error:
            # No mostrar respuestas de Google: podrían contener datos privados.
            tipo = type(error).__name__
            self.eventos.put(("error", tipo, "Revise permisos, conexión y configuración de Google."))

    def _escuchar(self):
        try:
            while True:
                tipo, datos, detalle = self.eventos.get_nowait()
                self.ocupado = False
                for boton in (self.boton_demo, self.boton_conectar, self.boton_procesar):
                    boton.configure(state="normal")
                if tipo == "error":
                    self.estado.set("La operación no pudo completarse.")
                    self._anotar("Error: " + datos + ". " + detalle)
                else:
                    self.estado.set("Operación finalizada correctamente.")
                    if datos:
                        self._anotar(
                            f"PDF: {datos['encontrados']} | Agregados: {datos['agregados']} | "
                            f"Duplicados: {datos['duplicados']} | Errores: {datos['errores']}"
                        )
                        if datos["errores"]:
                            self.estado.set("Procesamiento terminado con documentos pendientes de revisión.")
                    self._anotar(detalle)
        except queue.Empty:
            pass
        self.ventana.after(150, self._escuchar)

    def _anotar(self, mensaje: str):
        self.salida.configure(state="normal")
        self.salida.insert("end", mensaje + "\n")
        self.salida.see("end")
        self.salida.configure(state="disabled")


def main():
    ventana = tk.Tk()
    Escritorio(ventana)
    ventana.mainloop()


if __name__ == "__main__":
    main()
