"""
PDF_a_Markdown_GUI.py
----------------------
Aplicación de escritorio (sin terminal, sin Python visible) para convertir
un PDF con texto en griego clásico a un archivo Markdown.

Pensada para compañeros sin conocimientos de informática: se elige el PDF,
se elige dónde guardar, se pulsa "Convertir" y ya está.

Esta versión NO extrae tablas (para eso existe la aplicación hermana
`PDF_a_Markdown_con_Tablas_GUI.py`), lo que la hace más rápida y sencilla
para documentos que son solo texto corrido.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from gui_common import (
    COLOR_TEXTO_SECUNDARIO,
    MotorConversion,
    abrir_archivo,
    abrir_carpeta,
    crear_selector_archivo,
    crear_selector_carpeta,
    crear_selector_idiomas,
    obtener_lang_string,
)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF a Markdown — Griego clásico")
        self.geometry("680x700")
        self.minsize(600, 620)

        self.motor = MotorConversion()
        self.ultimo_output: Path | None = None

        self.var_pdf = ctk.StringVar()
        self.var_output_dir = ctk.StringVar(value=str(Path.home() / "Documents" / "markdown"))
        self.var_rango_activo = ctk.BooleanVar(value=False)
        self.var_pag_inicio = ctk.StringVar()
        self.var_pag_fin = ctk.StringVar()

        self._construir_ui()
        self.after(150, self._consumir_cola)

    # ------------------------------------------------------------------ UI
    def _construir_ui(self) -> None:
        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=26, pady=22)

        # --- Cabecera ---
        cabecera = ctk.CTkFrame(contenedor, corner_radius=14)
        cabecera.pack(fill="x", pady=(0, 18))
        ctk.CTkLabel(
            cabecera, text="📜  PDF a Markdown",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(14, 2))
        ctk.CTkLabel(
            cabecera,
            text="Griego clásico y otros idiomas académicos, con corrección automática de OCR.",
            text_color=COLOR_TEXTO_SECUNDARIO,
        ).pack(anchor="w", padx=18, pady=(0, 14))

        # --- Tarjeta de configuración ---
        tarjeta = ctk.CTkFrame(contenedor, corner_radius=14)
        tarjeta.pack(fill="x", pady=(0, 16))
        interior = ctk.CTkFrame(tarjeta, fg_color="transparent")
        interior.pack(fill="x", padx=18, pady=16)

        crear_selector_archivo(
            interior,
            "1.  Selecciona el PDF",
            self.var_pdf,
            filetypes=[("Archivos PDF", "*.pdf")],
        ).pack(fill="x", pady=(0, 16))

        crear_selector_carpeta(
            interior, "2.  Carpeta donde guardar el .md", self.var_output_dir
        ).pack(fill="x", pady=(0, 16))

        frame_idiomas, self.vars_idiomas = crear_selector_idiomas(interior)
        frame_idiomas.pack(fill="x", pady=(0, 16))

        # Rango de páginas opcional
        ctk.CTkCheckBox(
            interior, text="Convertir solo un rango de páginas",
            variable=self.var_rango_activo, command=self._alternar_rango,
        ).pack(anchor="w", pady=(0, 6))

        self.fila_paginas = ctk.CTkFrame(interior, fg_color="transparent")
        self.fila_paginas.pack(fill="x")
        ctk.CTkLabel(self.fila_paginas, text="Desde página:").pack(side="left")
        self.entry_inicio = ctk.CTkEntry(self.fila_paginas, textvariable=self.var_pag_inicio, width=70, state="disabled")
        self.entry_inicio.pack(side="left", padx=(6, 18))
        ctk.CTkLabel(self.fila_paginas, text="Hasta página:").pack(side="left")
        self.entry_fin = ctk.CTkEntry(self.fila_paginas, textvariable=self.var_pag_fin, width=70, state="disabled")
        self.entry_fin.pack(side="left", padx=(6, 0))

        # --- Botón de conversión ---
        self.boton_convertir = ctk.CTkButton(
            contenedor, text="✨  Convertir a Markdown", height=46,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_convertir,
        )
        self.boton_convertir.pack(fill="x", pady=(0, 14))

        self.barra_progreso = ctk.CTkProgressBar(contenedor, height=10)
        self.barra_progreso.set(0)
        self.barra_progreso.pack(fill="x", pady=(0, 12))

        # --- Registro ---
        ctk.CTkLabel(contenedor, text="Registro de la conversión", anchor="w",
                     font=ctk.CTkFont(weight="bold")).pack(fill="x")
        self.caja_log = ctk.CTkTextbox(contenedor, height=170, state="disabled")
        self.caja_log.pack(fill="both", expand=True, pady=(6, 14))

        self.fila_final = ctk.CTkFrame(contenedor, fg_color="transparent")
        self.fila_final.pack(fill="x")
        self.boton_abrir = ctk.CTkButton(
            self.fila_final, text="📄  Abrir el .md generado", state="disabled",
            command=self._abrir_resultado,
        )
        self.boton_abrir.pack(side="left")
        self.boton_carpeta = ctk.CTkButton(
            self.fila_final, text="📂  Abrir carpeta", state="disabled",
            command=self._abrir_carpeta, fg_color="#8A6D4E", hover_color="#6E5540",
        )
        self.boton_carpeta.pack(side="left", padx=(10, 0))

    def _alternar_rango(self) -> None:
        estado = "normal" if self.var_rango_activo.get() else "disabled"
        self.entry_inicio.configure(state=estado)
        self.entry_fin.configure(state=estado)

    # -------------------------------------------------------------- lógica
    def _log(self, texto: str) -> None:
        self.caja_log.configure(state="normal")
        self.caja_log.insert("end", texto + "\n")
        self.caja_log.see("end")
        self.caja_log.configure(state="disabled")

    def _on_convertir(self) -> None:
        if self.motor.en_curso():
            return

        pdf_path = self.var_pdf.get().strip()
        output_dir = self.var_output_dir.get().strip()

        if not pdf_path:
            self._log("⚠ Selecciona primero un archivo PDF.")
            return
        if not Path(pdf_path).is_file():
            self._log("⚠ El archivo PDF seleccionado no existe.")
            return
        if not output_dir:
            self._log("⚠ Indica una carpeta de salida.")
            return

        lang = obtener_lang_string(self.vars_idiomas)
        if lang is None:
            self._log("⚠ Marca al menos un idioma antes de convertir.")
            return

        pagina_inicio = pagina_fin = None
        if self.var_rango_activo.get():
            try:
                pagina_inicio = int(self.var_pag_inicio.get())
                pagina_fin = int(self.var_pag_fin.get())
                if pagina_inicio < 1 or pagina_fin < pagina_inicio:
                    raise ValueError
            except ValueError:
                self._log("⚠ El rango de páginas no es válido (revisa 'Desde' y 'Hasta').")
                return

        self.caja_log.configure(state="normal")
        self.caja_log.delete("1.0", "end")
        self.caja_log.configure(state="disabled")
        self.barra_progreso.set(0)
        self.boton_convertir.configure(state="disabled", text="Convirtiendo...")
        self.boton_abrir.configure(state="disabled")
        self.boton_carpeta.configure(state="disabled")

        self.motor.iniciar(
            pdf_path=Path(pdf_path),
            output_dir=Path(output_dir),
            lang=lang,
            con_tablas=False,
            pagina_inicio=pagina_inicio,
            pagina_fin=pagina_fin,
        )

    def _consumir_cola(self) -> None:
        try:
            while True:
                mensaje = self.motor.cola.get_nowait()
                tipo = mensaje[0]

                if tipo == "log":
                    self._log(mensaje[1])
                elif tipo == "progreso":
                    actual, total = mensaje[1], mensaje[2]
                    self.barra_progreso.set(actual / total if total else 0)
                elif tipo == "hecho":
                    ruta = Path(mensaje[1])
                    self.ultimo_output = ruta
                    self._log(f"\n✅ Conversión terminada.\nArchivo guardado en:\n{ruta}")
                    self.boton_convertir.configure(state="normal", text="✨  Convertir a Markdown")
                    self.boton_abrir.configure(state="normal")
                    self.boton_carpeta.configure(state="normal")
                    self.barra_progreso.set(1)
                elif tipo == "error":
                    self._log(f"\n❌ Ha ocurrido un error:\n{mensaje[1]}")
                    self.boton_convertir.configure(state="normal", text="✨  Convertir a Markdown")
        except Exception:
            pass
        finally:
            self.after(150, self._consumir_cola)

    def _abrir_resultado(self) -> None:
        if self.ultimo_output:
            abrir_archivo(self.ultimo_output)

    def _abrir_carpeta(self) -> None:
        if self.ultimo_output:
            abrir_carpeta(self.ultimo_output.parent)


if __name__ == "__main__":
    app = App()
    app.mainloop()
