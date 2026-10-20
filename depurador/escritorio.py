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
from .proveedores import GmailMensajeSeleccionado, GmailReader, GoogleSheetsWriter

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
    """Permite buscar mensajes y procesar exclusivamente el correo seleccionado."""

    def __init__(self, ventana: tk.Tk):
        self.ventana = ventana
        self.ventana.title("Depurador de PDF — Escritorio 0.3.0")
        self.ventana.geometry("1020x740")
        self.ventana.minsize(810, 600)
        self.ventana.configure(background=FONDO)
        self.eventos: queue.Queue = queue.Queue()
        self.ocupado = False
        self.carpeta = directorio_usuario()
        self.preferencias = cargar_preferencias(self.carpeta)
        self.correos = {}
        self.correo_seleccionado = None
        self.filtro_buscado = None
        self._construir()
        self.ventana.after(150, self._escuchar)

    def _construir(self):
        tema = ttk.Style(self.ventana)
        tema.theme_use("clam")
        tema.configure("TNotebook", background=FONDO, borderwidth=0)
        tema.configure("TNotebook.Tab", padding=(19, 11), font=("Segoe UI", 10))
        tema.map("TNotebook.Tab", background=[("selected", "#d5eddf")])
        tema.configure("TEntry", padding=6)
        tema.configure("TButton", padding=(12, 9), font=("Segoe UI", 10))
        tema.configure("Accent.TButton", foreground="white", background=VERDE)
        tema.map("Accent.TButton", background=[("active", "#1e7556")])
        tema.configure("TLabel", background=FONDO, foreground=TEXTO, font=("Segoe UI", 10))
        tema.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        tema.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        barra = tk.Frame(self.ventana, bg=VERDE, height=86)
        barra.pack(fill="x")
        tk.Label(
            barra, text="Depurador de PDF", font=("Segoe UI", 21, "bold"),
            bg=VERDE, fg="white"
        ).pack(anchor="w", padx=26, pady=(12, 0))
        tk.Label(
            barra, text="Seleccione un correo de Gmail y envíe sus PDF a Google Sheets",
            bg=VERDE, fg="#c8e7d8", font=("Segoe UI", 10)
        ).pack(anchor="w", padx=28, pady=(0, 12))

        base = tk.Frame(self.ventana, bg=FONDO)
        base.pack(fill="both", expand=True, padx=20, pady=14)
        pestanas = ttk.Notebook(base)
        pestanas.pack(fill="both", expand=True)
        bandeja = ttk.Frame(pestanas, padding=14)
        conexiones = ttk.Frame(pestanas, padding=18)
        reglas = ttk.Frame(pestanas, padding=18)
        pestanas.add(bandeja, text="1. Seleccionar correo")
        pestanas.add(conexiones, text="2. Conexiones")
        pestanas.add(reglas, text="3. Campos de los PDF")

        self.consulta = tk.StringVar(value=self.preferencias["consulta"])
        self.hoja = tk.StringVar(value=self.preferencias["hoja_id"])
        self.pestana = tk.StringVar(value=self.preferencias["pestana"])
        self.json_cliente = tk.StringVar(value=self.preferencias["oauth_json"])
        self.cantidad = tk.StringVar(value=str(self.preferencias["max_correos"]))
        self.estado = tk.StringVar(value="Conecte Gmail y busque los correos con PDF.")
        self.seleccion_texto = tk.StringVar(value="Seleccione un correo de la lista para habilitar el procesamiento.")

        ttk.Label(
            bandeja, text="Busque los correos que contienen los PDF",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w")
        ttk.Label(
            bandeja, text="Puede filtrar por remitente, asunto, fecha y adjuntos utilizando la búsqueda de Gmail.",
            foreground=SUAVE
        ).pack(anchor="w", pady=(3, 9))
        fila_filtro = ttk.Frame(bandeja)
        fila_filtro.pack(fill="x")
        ttk.Entry(fila_filtro, textvariable=self.consulta).pack(side="left", expand=True, fill="x")
        self.boton_buscar = ttk.Button(
            fila_filtro, text="Buscar correos", style="Accent.TButton",
            command=lambda: self._iniciar("buscar")
        )
        self.boton_buscar.pack(side="left", padx=(8, 0))
        self.consulta.trace_add("write", self._filtro_cambiado)

        ttk.Label(
            bandeja, text="Resultados con PDF adjuntos — seleccione una fila",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", pady=(18, 7))
        tabla_contenedor = ttk.Frame(bandeja)
        tabla_contenedor.pack(fill="both", expand=True)
        self.tabla = ttk.Treeview(
            tabla_contenedor, columns=("fecha", "remitente", "asunto", "pdf"),
            show="headings", selectmode="browse", height=8
        )
        for key, label, ancho, stretch in (
            ("fecha", "Fecha", 138, False),
            ("remitente", "Remitente", 225, True),
            ("asunto", "Asunto", 380, True),
            ("pdf", "PDF", 60, False),
        ):
            self.tabla.heading(key, text=label)
            self.tabla.column(key, width=ancho, minwidth=50, stretch=stretch,
                              anchor="center" if key == "pdf" else "w")
        desplazamiento = ttk.Scrollbar(tabla_contenedor, orient="vertical",
                                       command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=desplazamiento.set)
        self.tabla.pack(side="left", fill="both", expand=True)
        desplazamiento.pack(side="right", fill="y")
        self.tabla.bind("<<TreeviewSelect>>", self._seleccionar_correo)

        ttk.Label(bandeja, textvariable=self.seleccion_texto,
                  foreground=SUAVE, wraplength=850).pack(anchor="w", pady=(9, 7))
        botones = ttk.Frame(bandeja)
        botones.pack(fill="x", pady=(2, 6))
        self.boton_demo = ttk.Button(
            botones, text="Probar sin conexión", command=lambda: self._iniciar("demo")
        )
        self.boton_demo.pack(side="left", padx=(0, 7))
        self.boton_procesar = ttk.Button(
            botones, text="Procesar correo seleccionado", style="Accent.TButton",
            command=lambda: self._iniciar("procesar"), state="disabled"
        )
        self.boton_procesar.pack(side="right")
        ttk.Label(bandeja, textvariable=self.estado, foreground=SUAVE,
                  wraplength=870).pack(anchor="w", pady=(3, 7))
        self.salida = tk.Text(
            bandeja, height=5, state="disabled", relief="flat",
            bg="#e6f0e9", fg=TEXTO, font=("Consolas", 10),
            padx=12, pady=9, wrap="word"
        )
        self.salida.pack(fill="x")
        ttk.Label(
            bandeja, text="Solo se procesan los PDF del correo seleccionado; ningún otro mensaje.",
            foreground=SUAVE
        ).pack(anchor="w", pady=(9, 0))

        self._campo(conexiones, "ID o URL de Google Sheets (Drive)", self.hoja, 0)
        self._campo(conexiones, "Nombre de la pestaña de destino", self.pestana, 2)
        ttk.Label(conexiones, text="Archivo OAuth de Google Cloud (JSON)").grid(
            row=4, column=0, sticky="w", pady=(10, 3)
        )
        archivo = ttk.Frame(conexiones)
        archivo.grid(row=5, column=0, sticky="ew")
        ttk.Entry(archivo, textvariable=self.json_cliente).pack(side="left", expand=True, fill="x")
        ttk.Button(archivo, text="Elegir JSON", command=self._buscar_json).pack(side="left", padx=(8, 0))
        self._campo(conexiones, "Máximo de correos a mostrar en la búsqueda", self.cantidad, 6)
        controles = ttk.Frame(conexiones)
        controles.grid(row=8, column=0, sticky="w", pady=(20, 0))
        self.boton_conectar = ttk.Button(
            controles, text="Conectar o cambiar cuenta Google", style="Accent.TButton",
            command=lambda: self._iniciar("conectar")
        )
        self.boton_conectar.pack(side="left")
        ttk.Button(
            controles, text="Guardar configuración",
            command=lambda: self._guardar(mostrar=True)
        ).pack(side="left", padx=(9, 0))
        ttk.Label(conexiones, foreground=SUAVE, wraplength=800,
                  text="Primero autorice su Gmail. Después regrese a «Seleccionar correo» "
                       "para buscar y escoger el mensaje exacto.").grid(
            row=9, column=0, sticky="w", pady=(16, 0)
        )
        conexiones.columnconfigure(0, weight=1)

        ttk.Label(
            reglas, text="Datos a extraer de cada PDF",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w")
        ttk.Label(
            reglas, text="Los campos se configuran una vez con un PDF de ejemplo.",
            foreground=SUAVE
        ).pack(anchor="w", pady=(4, 9))
        self.editor = tk.Text(reglas, font=("Consolas", 11), bg="white",
                              fg=TEXTO, relief="solid", bd=1, wrap="none")
        self.editor.pack(fill="both", expand=True)
        self.editor.insert("1.0", cargar_reglas(self.carpeta))
        fila = ttk.Frame(reglas)
        fila.pack(fill="x", pady=(11, 3))
        ttk.Button(fila, text="Importar JSON", command=self._importar_reglas).pack(side="left")
        ttk.Button(fila, text="Guardar campos", style="Accent.TButton",
                   command=lambda: self._guardar(mostrar=True)).pack(side="right")
        ttk.Label(
            reglas, foreground=SUAVE,
            text='Ejemplo: {"campos":[{"nombre":"numero","patron":"Documento: ([0-9]+)","obligatorio":true}]}',
            wraplength=820
        ).pack(anchor="w", pady=(8, 0))

    def _campo(self, marco, etiqueta, variable, fila):
        ttk.Label(marco, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=(9, 3))
        ttk.Entry(marco, textvariable=variable).grid(row=fila + 1, column=0, sticky="ew")

    def _limpiar_lista(self):
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        self.correos = {}
        self.correo_seleccionado = None
        self.filtro_buscado = None
        self.seleccion_texto.set("Seleccione un correo de la lista para habilitar el procesamiento.")
        self.boton_procesar.configure(state="disabled")

    def _filtro_cambiado(self, *_):
        self._limpiar_lista()
        self.estado.set("El filtro cambió. Pulse «Buscar correos» para actualizar la lista.")

    def _seleccionar_correo(self, _evento=None):
        seleccion = self.tabla.selection()
        identificador = seleccion[0] if seleccion else None
        if identificador not in self.correos or self.filtro_buscado != self.consulta.get().strip():
            self.correo_seleccionado = None
            self.boton_procesar.configure(state="disabled")
            return
        self.correo_seleccionado = identificador
        correo = self.correos[identificador]
        self.seleccion_texto.set(
            f"Seleccionado: {correo.asunto} — {correo.cantidad_pdf} PDF. "
            "Se procesará exclusivamente este correo."
        )
        self.boton_procesar.configure(state="disabled" if self.ocupado else "normal")

    def _buscar_json(self):
        ruta = filedialog.askopenfilename(
            title="Credenciales OAuth para aplicación de escritorio",
            filetypes=[("Archivos JSON", "*.json")]
        )
        if ruta:
            self.json_cliente.set(ruta)
            self._limpiar_lista()

    def _importar_reglas(self):
        ruta = filedialog.askopenfilename(title="Seleccionar reglas", filetypes=[("JSON", "*.json")])
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
                self.estado.set("Configuración guardada solo en este portátil.")
            return True
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Revisar configuración", str(error))
            return False

    def _iniciar(self, operacion: str):
        if self.ocupado or not self._guardar():
            return
        seleccionado = None
        if operacion == "procesar":
            seleccionado = self.correo_seleccionado
            if not seleccionado or seleccionado not in self.correos:
                messagebox.showwarning("Seleccione un correo", "Primero busque y seleccione un correo de la lista.")
                return
            if self.filtro_buscado != self.consulta.get().strip():
                self._limpiar_lista()
                messagebox.showwarning("Lista desactualizada", "Repita la búsqueda antes de procesar.")
                return
            if not self.hoja.get().strip():
                messagebox.showwarning("Falta Google Sheets", "Ingrese el ID de la hoja de destino.")
                return
            if not validar_reglas(self.editor.get("1.0", "end-1c")):
                messagebox.showwarning("Faltan campos", "Configure los campos con un PDF de ejemplo.")
                return
            correo = self.correos[seleccionado]
            if not messagebox.askyesno(
                "Confirmar procesamiento",
                f"¿Procesar solo el correo «{correo.asunto}» ({correo.cantidad_pdf} PDF)?\n\n"
                "Los datos nuevos se agregarán a Google Sheets.",
            ):
                return
        if operacion != "demo" and not self.json_cliente.get().strip():
            messagebox.showwarning(
                "Faltan credenciales", "Seleccione el archivo OAuth JSON de Google Cloud."
            )
            return
        self.ocupado = True
        for boton in (self.boton_demo, self.boton_conectar, self.boton_buscar, self.boton_procesar):
            boton.configure(state="disabled")
        self.estado.set(
            "Buscando correos..." if operacion == "buscar" else
            "Procesando PDF del correo seleccionado..." if operacion == "procesar" else
            "Ejecutando prueba local..." if operacion == "demo" else "Autorizando Google..."
        )
        parametros = {
            "consulta": self.consulta.get().strip(),
            "id": _id_hoja(self.hoja.get()),
            "pestana": self.pestana.get().strip(),
            "json": self.json_cliente.get().strip(),
            "max": int(self.cantidad.get()),
            "reglas": self.editor.get("1.0", "end-1c"),
            "seleccionado": seleccionado,
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
                    config["json"], self.carpeta / "token_google.json",
                    cambiar_cuenta=(operacion == "conectar"),
                )
                if operacion == "conectar":
                    self.eventos.put(("conectado", None, "Cuenta de Google autorizada. Busque los correos."))
                    return
                gmail, sheets = servicios(credenciales)
                lector = GmailReader(gmail, config["consulta"], config["max"])
                if operacion == "buscar":
                    correos = lector.listar_correos()
                    self.eventos.put(("lista", (config["consulta"], correos), ""))
                    return
                destino = GoogleSheetsWriter(sheets, config["id"], config["pestana"])
                origen = GmailMensajeSeleccionado(lector, config["seleccionado"])
                resultado = procesar(origen, destino, validar_reglas(config["reglas"]))
                detalle = "Solo se revisaron los adjuntos del mensaje seleccionado."
            self.eventos.put(("ok", resultado, detalle))
        except Exception as error:
            # Los mensajes de Google podrían incluir datos privados; solo exponer el tipo.
            self.eventos.put(
                ("error", type(error).__name__,
                 "Revise permisos, conexión, campos y configuración de Google.")
            )

    def _escuchar(self):
        try:
            while True:
                tipo, datos, detalle = self.eventos.get_nowait()
                self.ocupado = False
                for boton in (self.boton_demo, self.boton_conectar, self.boton_buscar):
                    boton.configure(state="normal")
                if tipo == "error":
                    self.estado.set("La operación no pudo completarse.")
                    self._anotar("Error: " + datos + ". " + detalle)
                elif tipo == "lista":
                    filtro, correos = datos
                    self._limpiar_lista()
                    if filtro != self.consulta.get().strip():
                        self.estado.set("El filtro cambió durante la búsqueda. Repita la consulta.")
                        continue
                    self.filtro_buscado = filtro
                    for correo in correos:
                        self.correos[correo.id] = correo
                        self.tabla.insert(
                            "", "end", iid=correo.id,
                            values=(correo.fecha, correo.remitente,
                                    correo.asunto, correo.cantidad_pdf)
                        )
                    self.estado.set(
                        f"Se encontraron {len(correos)} correos con PDF. Seleccione uno para procesar."
                        if correos else "No hay correos con PDF que coincidan con la búsqueda."
                    )
                elif tipo == "conectado":
                    self._limpiar_lista()
                    self.estado.set(detalle)
                    self._anotar("Cuenta de Google conectada. No se procesó ningún correo.")
                else:
                    self.estado.set("Operación finalizada correctamente.")
                    if datos is not None:
                        self._anotar(
                            f"PDF: {datos['encontrados']} | Agregados: {datos['agregados']} | "
                            f"Duplicados: {datos['duplicados']} | Errores: {datos['errores']}"
                        )
                        if datos["errores"]:
                            self.estado.set("Procesamiento finalizado con documentos pendientes de revisión.")
                    self._anotar(detalle)
                self.boton_procesar.configure(
                    state="normal" if self.correo_seleccionado in self.correos else "disabled"
                )
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
