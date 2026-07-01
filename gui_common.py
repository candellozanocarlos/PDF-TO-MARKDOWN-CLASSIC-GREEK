"""
gui_common.py
-------------
Lógica y componentes compartidos por las dos aplicaciones de escritorio:

  - PDF_a_Markdown_GUI.py            (conversión de texto, sin tablas)
  - PDF_a_Markdown_con_Tablas_GUI.py (conversión de texto + extracción de tablas)

Se centraliza aquí para que ambas GUIs reutilicen exactamente el mismo motor
de conversión (pdf_to_markdown / ocr_postprocess_mejorado / pdf_table_extractor)
y no diverjan con el tiempo.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
import pytesseract
from pdf2image import convert_from_path

import config
from ocr_postprocess_mejorado import corregir_texto

IDIOMAS_DISPONIBLES = {
    "Griego clásico + inglés (recomendado)": "grc+eng",
    "Solo griego clásico": "grc",
    "Griego clásico + inglés + francés": "grc+eng+fra",
    "Griego clásico + inglés + alemán": "grc+eng+deu",
    "Griego clásico + inglés + italiano": "grc+eng+ita",
    "Solo inglés": "eng",
}

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def abrir_archivo(ruta: Path) -> None:
    """Abre el archivo con la aplicación por defecto del sistema."""
    try:
        if os.name == "nt":
            os.startfile(ruta)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{ruta}"')
        else:
            os.system(f'xdg-open "{ruta}"')
    except Exception:
        pass


def abrir_carpeta(ruta: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(ruta)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{ruta}"')
        else:
            os.system(f'xdg-open "{ruta}"')
    except Exception:
        pass


class ConversionEnCurso(Exception):
    """Señal interna para cancelar limpiamente una conversión en curso."""


class MotorConversion:
    """
    Ejecuta la conversión PDF -> Markdown en un hilo aparte, para no congelar
    la interfaz, y comunica el progreso mediante una cola de mensajes que la
    ventana principal consume periódicamente con `after()`.

    Mensajes puestos en la cola (tuplas):
        ("log", texto)
        ("progreso", pagina_actual, total_paginas)
        ("tabla_encontrada", num_pagina, num_tablas)
        ("hecho", ruta_salida)
        ("error", texto_error)
    """

    def __init__(self) -> None:
        self.cola: "queue.Queue[tuple]" = queue.Queue()
        self._hilo: Optional[threading.Thread] = None
        self._cancelado = threading.Event()

    def cancelar(self) -> None:
        self._cancelado.set()

    def en_curso(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(
        self,
        pdf_path: Path,
        output_dir: Path,
        lang: str,
        con_tablas: bool,
        pagina_inicio: Optional[int] = None,
        pagina_fin: Optional[int] = None,
        dpi: int = 300,
    ) -> None:
        if self.en_curso():
            return
        self._cancelado.clear()
        self._hilo = threading.Thread(
            target=self._ejecutar,
            args=(pdf_path, output_dir, lang, con_tablas, pagina_inicio, pagina_fin, dpi),
            daemon=True,
        )
        self._hilo.start()

    def _ejecutar(
        self,
        pdf_path: Path,
        output_dir: Path,
        lang: str,
        con_tablas: bool,
        pagina_inicio: Optional[int],
        pagina_fin: Optional[int],
        dpi: int,
    ) -> None:
        try:
            self.cola.put(("log", f"Comprobando dependencias..."))
            config.verificar_dependencias_externas()

            output_dir.mkdir(parents=True, exist_ok=True)

            kwargs_convert = {"dpi": dpi, "poppler_path": config.POPPLER_PATH}
            if pagina_inicio and pagina_fin:
                kwargs_convert["first_page"] = pagina_inicio
                kwargs_convert["last_page"] = pagina_fin
                primera = pagina_inicio
                sufijo = f"_pp{pagina_inicio}-{pagina_fin}"
            else:
                primera = 1
                sufijo = ""

            self.cola.put(("log", "Convirtiendo PDF a imágenes..."))
            pages = convert_from_path(str(pdf_path), **kwargs_convert)
            self._comprobar_cancelacion()

            tablas_por_pagina: dict[int, list[str]] = {}
            insertar_tablas = None
            if con_tablas:
                from pdf_table_extractor import (
                    extraer_tablas, detectar_tipo_pdf,
                    insertar_tablas_en_texto,
                )

                self.cola.put(("log", "Analizando tipo de PDF (digital / escaneado)..."))
                tipo_pdf = detectar_tipo_pdf(str(pdf_path))
                self.cola.put(("log", f"Tipo detectado: {tipo_pdf}."))
                self.cola.put(("log", "Buscando tablas (modo estricto)..."))
                tablas_por_pagina = extraer_tablas(
                    str(pdf_path), tipo=tipo_pdf, imagenes=pages, lang=lang,
                    aplicar_postproc=True,
                )
                total_tablas = sum(len(v) for v in tablas_por_pagina.values())
                if total_tablas == 0:
                    self.cola.put((
                        "log",
                        "No se ha detectado ninguna tabla que cumpla los criterios "
                        "estrictos (pie de tabla + rejilla de al menos 3x2 celdas "
                        "con contenido). Si esperabas encontrar alguna, revisa que "
                        "tenga un pie del tipo 'Table 1', 'Tabla 1', etc.",
                    ))
                else:
                    for num_pag, tablas in sorted(tablas_por_pagina.items()):
                        self.cola.put(("tabla_encontrada", num_pag, len(tablas)))

                insertar_tablas = insertar_tablas_en_texto

            self.cola.put(("log", f"Procesando {len(pages)} página(s) con OCR..."))
            texto_completo = ""
            for i, page in enumerate(pages):
                self._comprobar_cancelacion()
                num_pagina = primera + i
                self.cola.put(("progreso", i + 1, len(pages)))
                self.cola.put(("log", f"  Página {num_pagina}..."))

                texto_bruto = pytesseract.image_to_string(page, lang=lang, config="--psm 3")
                texto_corregido = corregir_texto(texto_bruto, verbose=False)

                if con_tablas and num_pagina in tablas_por_pagina and insertar_tablas:
                    texto_corregido = insertar_tablas(
                        texto_corregido, tablas_por_pagina[num_pagina]
                    )

                texto_completo += f"\n\n--- Página {num_pagina} ---\n\n{texto_corregido}"

            sufijo_tablas = "_tablas" if con_tablas else ""
            output_path = output_dir / f"{pdf_path.stem}{sufijo}{sufijo_tablas}.md"
            output_path.write_text(texto_completo, encoding="utf-8")

            self.cola.put(("hecho", str(output_path)))

        except ConversionEnCurso:
            self.cola.put(("log", "Conversión cancelada por el usuario."))
        except Exception as exc:  # noqa: BLE001
            self.cola.put(("error", f"{exc}\n\n{traceback.format_exc(limit=3)}"))

    def _comprobar_cancelacion(self) -> None:
        if self._cancelado.is_set():
            raise ConversionEnCurso()


def crear_selector_archivo(
    parent,
    label_texto: str,
    variable: ctk.StringVar,
    filetypes: list[tuple[str, str]],
    on_change: Optional[Callable[[str], None]] = None,
) -> ctk.CTkFrame:
    """Crea una fila con etiqueta + campo de texto (solo lectura) + botón 'Examinar'."""
    from tkinter import filedialog

    frame = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(frame, text=label_texto, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
        fill="x", pady=(0, 4)
    )

    fila = ctk.CTkFrame(frame, fg_color="transparent")
    fila.pack(fill="x")

    entrada = ctk.CTkEntry(fila, textvariable=variable, state="readonly")
    entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))

    def _examinar():
        ruta = filedialog.askopenfilename(title=label_texto, filetypes=filetypes)
        if ruta:
            variable.set(ruta)
            if on_change:
                on_change(ruta)

    ctk.CTkButton(fila, text="Examinar...", width=110, command=_examinar).pack(side="left")

    return frame


def crear_selector_carpeta(
    parent, label_texto: str, variable: ctk.StringVar
) -> ctk.CTkFrame:
    from tkinter import filedialog

    frame = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(frame, text=label_texto, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
        fill="x", pady=(0, 4)
    )

    fila = ctk.CTkFrame(frame, fg_color="transparent")
    fila.pack(fill="x")

    entrada = ctk.CTkEntry(fila, textvariable=variable, state="readonly")
    entrada.pack(side="left", fill="x", expand=True, padx=(0, 8))

    def _examinar():
        ruta = filedialog.askdirectory(title=label_texto)
        if ruta:
            variable.set(ruta)

    ctk.CTkButton(fila, text="Examinar...", width=110, command=_examinar).pack(side="left")

    return frame
