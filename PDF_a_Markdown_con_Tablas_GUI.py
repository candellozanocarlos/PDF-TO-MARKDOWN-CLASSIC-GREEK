"""
PDF_a_Markdown_con_Tablas_GUI.py
----------------------------------
Igual que PDF_a_Markdown_GUI.py, pero además extrae las tablas del documento
(digital o escaneado) y las inserta en el Markdown junto a su pie ("Table 1",
"Tabla 1"...).

La detección de tablas es deliberadamente ESTRICTA para evitar falsos
positivos (recuadros decorativos, figuras, cabeceras con marco). Una
estructura solo se considera tabla si cumple TODO lo siguiente:

  - La página contiene un pie explícito de tabla (no de figura): "Table 1",
    "Tabla 1", "Tab. 1", "Cuadro 1", "Tableau 1"...
  - La rejilla tiene al menos 3 filas y 2 columnas (PDF digital: además,
    al menos un 75 % de las filas deben compartir el mismo número de
    columnas).
  - Al menos la mitad de las celdas contienen texto real tras el OCR
    (descarta recuadros vacíos o mal detectados).

Por eso, si un documento no tiene tablas "de verdad", esta aplicación no
inventará ninguna: es normal y esperable ver "0 tablas encontradas" en
documentos que son solo texto corrido con figuras.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from gui_common import (
    IDIOMAS_DISPONIBLES,
    MotorConversion,
    abrir_archivo,
    abrir_carpeta,
    crear_selector_archivo,
    crear_selector_carpeta,
)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF a Markdown — Griego clásico (con tablas)")
        self.geometry("640x700")
        self.minsize(560, 620)

        self.motor = MotorConversion()
        self.ultimo_output: Path | None = None
        self.tablas_encontradas: list[tuple[int, int]] = []  # (num_pagina, n_tablas)

        self.var_pdf = ctk.StringVar()
        self.var_output_dir = ctk.StringVar(value=str(Path.home() / "Documents" / "markdown"))
        self.var_idioma = ctk.StringVar(value=list(IDIOMAS_DISPONIBLES.keys())[0])
        self.var_rango_activo = ctk.BooleanVar(value=False)
        self.var_pag_inicio = ctk.StringVar()
        self.var_pag_fin = ctk.StringVar()

        self._construir_ui()
        self.after(150, self._consumir_cola)

    # ------------------------------------------------------------------ UI
    def _construir_ui(self) -> None:
        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            contenedor,
            text="Convertir PDF a Markdown (con tablas)",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            contenedor,
            text="Extrae también las tablas del documento. Detección estricta:\n"
                 "solo se extraen tablas con pie explícito y rejilla real (evita falsos positivos).",
            text_color="gray40", justify="left",
        ).pack(anchor="w", pady=(0, 16))

        crear_selector_archivo(
            contenedor,
            "1. Selecciona el PDF",
            self.var_pdf,
            filetypes=[("Archivos PDF", "*.pdf")],
        ).pack(fill="x", pady=(0, 14))

        crear_selector_carpeta(
            contenedor, "2. Carpeta donde guardar el .md", self.var_output_dir
        ).pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            contenedor, text="3. Idioma del documento", anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).pack(fill="x", pady=(0, 4))
        ctk.CTkOptionMenu(
            contenedor, variable=self.var_idioma, values=list(IDIOMAS_DISPONIBLES.keys())
        ).pack(fill="x", pady=(0, 14))

        # Rango de páginas opcional
        fila_rango = ctk.CTkFrame(contenedor, fg_color="transparent")
        fila_rango.pack(fill="x", pady=(0, 14))
        ctk.CTkCheckBox(
            fila_rango, text="Convertir solo un rango de páginas",
            variable=self.var_rango_activo, command=self._alternar_rango,
        ).pack(anchor="w", pady=(0, 6))

        self.fila_paginas = ctk.CTkFrame(fila_rango, fg_color="transparent")
        self.fila_paginas.pack(fill="x")
        ctk.CTkLabel(self.fila_paginas, text="Desde página:").pack(side="left")
        self.entry_inicio = ctk.CTkEntry(self.fila_paginas, textvariable=self.var_pag_inicio, width=70, state="disabled")
        self.entry_inicio.pack(side="left", padx=(6, 18))
        ctk.CTkLabel(self.fila_paginas, text="Hasta página:").pack(side="left")
        self.entry_fin = ctk.CTkEntry(self.fila_paginas, textvariable=self.var_pag_fin, width=70, state="disabled")
        self.entry_fin.pack(side="left", padx=(6, 0))

        # Botón de conversión
        self.boton_convertir = ctk.CTkButton(
            contenedor, text="Convertir a Markdown (con tablas)", height=42,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_convertir,
        )
        self.boton_convertir.pack(fill="x", pady=(6, 10))

        self.barra_progreso = ctk.CTkProgressBar(contenedor)
        self.barra_progreso.set(0)
        self.barra_progreso.pack(fill="x", pady=(0, 10))

        # Panel de resumen de tablas
        self.panel_tablas = ctk.CTkFrame(contenedor, fg_color=("gray90", "gray20"))
        self.panel_tablas.pack(fill="x", pady=(0, 10))
        self.label_resumen_tablas = ctk.CTkLabel(
            self.panel_tablas, text="Todavía no se ha buscado ninguna tabla.",
            anchor="w", justify="left",
        )
        self.label_resumen_tablas.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(contenedor, text="Registro de la conversión:", anchor="w").pack(fill="x")
        self.caja_log = ctk.CTkTextbox(contenedor, height=150, state="disabled")
        self.caja_log.pack(fill="both", expand=True, pady=(4, 10))

        self.fila_final = ctk.CTkFrame(contenedor, fg_color="transparent")
        self.fila_final.pack(fill="x")
        self.boton_abrir = ctk.CTkButton(
            self.fila_final, text="Abrir el .md generado", state="disabled",
            command=self._abrir_resultado,
        )
        self.boton_abrir.pack(side="left")
        self.boton_carpeta = ctk.CTkButton(
            self.fila_final, text="Abrir carpeta", state="disabled",
            command=self._abrir_carpeta, fg_color="gray50", hover_color="gray40",
        )
        self.boton_carpeta.pack(side="left", padx=(8, 0))

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

        lang = IDIOMAS_DISPONIBLES[self.var_idioma.get()]

        self.caja_log.configure(state="normal")
        self.caja_log.delete("1.0", "end")
        self.caja_log.configure(state="disabled")
        self.barra_progreso.set(0)
        self.tablas_encontradas = []
        self.label_resumen_tablas.configure(text="Buscando tablas...")
        self.boton_convertir.configure(state="disabled", text="Convirtiendo...")
        self.boton_abrir.configure(state="disabled")
        self.boton_carpeta.configure(state="disabled")

        self.motor.iniciar(
            pdf_path=Path(pdf_path),
            output_dir=Path(output_dir),
            lang=lang,
            con_tablas=True,
            pagina_inicio=pagina_inicio,
            pagina_fin=pagina_fin,
        )

    def _actualizar_resumen_tablas(self) -> None:
        if not self.tablas_encontradas:
            self.label_resumen_tablas.configure(
                text="0 tablas encontradas (con los criterios estrictos de detección)."
            )
            return
        total = sum(n for _, n in self.tablas_encontradas)
        paginas = ", ".join(str(p) for p, _ in sorted(self.tablas_encontradas))
        self.label_resumen_tablas.configure(
            text=f"{total} tabla(s) encontrada(s) en la(s) página(s): {paginas}"
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
                elif tipo == "tabla_encontrada":
                    num_pag, n_tablas = mensaje[1], mensaje[2]
                    self.tablas_encontradas.append((num_pag, n_tablas))
                    self._actualizar_resumen_tablas()
                elif tipo == "hecho":
                    ruta = Path(mensaje[1])
                    self.ultimo_output = ruta
                    self._actualizar_resumen_tablas()
                    self._log(f"\n✅ Conversión terminada.\nArchivo guardado en:\n{ruta}")
                    self.boton_convertir.configure(state="normal", text="Convertir a Markdown (con tablas)")
                    self.boton_abrir.configure(state="normal")
                    self.boton_carpeta.configure(state="normal")
                    self.barra_progreso.set(1)
                elif tipo == "error":
                    self._log(f"\n❌ Ha ocurrido un error:\n{mensaje[1]}")
                    self.boton_convertir.configure(state="normal", text="Convertir a Markdown (con tablas)")
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
