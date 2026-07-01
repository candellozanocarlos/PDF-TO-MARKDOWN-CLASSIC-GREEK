"""
gui_common.py
-------------
Logic and components shared by the two desktop applications:

  - PDF_a_Markdown_GUI.py            (text conversion, no tables)
  - PDF_a_Markdown_con_Tablas_GUI.py (text conversion + table extraction)

Centralized here so both GUIs reuse exactly the same conversion engine
(pdf_to_markdown / ocr_postprocess / pdf_table_extractor) and do not
diverge over time.

Note on language: identifiers, comments, and docstrings in this file are
in English, but the strings actually displayed inside the GUI windows
(log messages, button labels, checkbox text) are intentionally kept in
Spanish, since the desktop apps are aimed at non-technical, Spanish-
speaking colleagues.
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
from ocr_postprocess import fix_text

TESSERACT_LANGUAGES: list[tuple[str, str]] = [
    ("grc", "Griego clásico"),
    ("eng", "Inglés"),
    ("fra", "Francés"),
    ("deu", "Alemán"),
    ("ita", "Italiano"),
    ("spa", "Español"),
    ("lat", "Latín"),
]

DEFAULT_LANGUAGES = ("grc", "eng")

def _resource_path(name: str) -> Path:
    """
    Locates a resource file (such as tema_calido.json) both when the
    program runs as a normal script and when it has been packaged with
    PyInstaller in --onefile mode (where resources are extracted to a
    temporary folder given by sys._MEIPASS, and Path(__file__).parent no
    longer points to the project folder).
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / name


ctk.set_appearance_mode("light")
ctk.set_default_color_theme(str(_resource_path("tema_calido.json")))

# Warm palette, for the few places where a color is set by hand (warning
# panels, secondary text) instead of letting the CustomTkinter theme
# resolve it.
SECONDARY_TEXT_COLOR = "#8A6D4E"
WARNING_PANEL_COLOR = "#EAD6AE"
WARNING_TEXT_COLOR = "#8C4E17"


def open_file(path: Path) -> None:
    """Opens the file with the system's default application."""
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass


def open_folder(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass


class ConversionInProgress(Exception):
    """Internal signal used to cleanly cancel a running conversion."""


class ConversionEngine:
    """
    Runs the PDF -> Markdown conversion on a separate thread, so as not to
    freeze the interface, and communicates progress through a message
    queue that the main window polls periodically with `after()`.

    Messages put on the queue (tuples):
        ("log", text)
        ("progress", current_page, total_pages)
        ("table_found", page_num, num_tables)
        ("done", output_path)
        ("error", error_text)
    """

    def __init__(self) -> None:
        self.queue: "queue.Queue[tuple]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        pdf_path: Path,
        output_dir: Path,
        lang: str,
        with_tables: bool,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        dpi: int = 300,
    ) -> None:
        if self.is_running():
            return
        self._cancelled.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(pdf_path, output_dir, lang, with_tables, start_page, end_page, dpi),
            daemon=True,
        )
        self._thread.start()

    def _run(
        self,
        pdf_path: Path,
        output_dir: Path,
        lang: str,
        with_tables: bool,
        start_page: Optional[int],
        end_page: Optional[int],
        dpi: int,
    ) -> None:
        try:
            self.queue.put(("log", "Comprobando dependencias externas (Tesseract, Poppler)..."))
            warnings = config.check_external_dependencies()
            if warnings:
                for warning in warnings:
                    self.queue.put(("log", f"⚠ {warning}"))
                self.queue.put((
                    "error",
                    "Faltan programas externos necesarios (ver avisos arriba). "
                    "Instálalos y vuelve a intentarlo; esta aplicación no puede "
                    "convertir el PDF sin ellos.",
                ))
                return

            output_dir.mkdir(parents=True, exist_ok=True)

            convert_kwargs = {"dpi": dpi, "poppler_path": config.POPPLER_PATH}
            if start_page and end_page:
                convert_kwargs["first_page"] = start_page
                convert_kwargs["last_page"] = end_page
                first_page = start_page
                suffix = f"_pp{start_page}-{end_page}"
            else:
                first_page = 1
                suffix = ""

            self.queue.put(("log", "Convirtiendo PDF a imágenes..."))
            pages = convert_from_path(str(pdf_path), **convert_kwargs)
            self._check_cancelled()

            tables_by_page: dict[int, list[str]] = {}
            insert_tables = None
            if with_tables:
                from pdf_table_extractor import (
                    extract_tables, detect_pdf_type,
                    insert_tables_into_text,
                )

                self.queue.put(("log", "Analizando tipo de PDF (digital / escaneado)..."))
                pdf_type = detect_pdf_type(str(pdf_path))
                self.queue.put(("log", f"Tipo detectado: {pdf_type}."))
                self.queue.put(("log", "Buscando tablas (modo estricto)..."))
                tables_by_page = extract_tables(
                    str(pdf_path), pdf_type=pdf_type, images=pages, lang=lang,
                    apply_postprocessing=True,
                )
                total_tables = sum(len(v) for v in tables_by_page.values())
                if total_tables == 0:
                    self.queue.put((
                        "log",
                        "No se ha detectado ninguna tabla que cumpla los criterios "
                        "estrictos (pie de tabla + rejilla de al menos 3x2 celdas "
                        "con contenido). Si esperabas encontrar alguna, revisa que "
                        "tenga un pie del tipo 'Table 1', 'Tabla 1', etc.",
                    ))
                else:
                    for page_num, tables in sorted(tables_by_page.items()):
                        self.queue.put(("table_found", page_num, len(tables)))

                insert_tables = insert_tables_into_text

            self.queue.put(("log", f"Procesando {len(pages)} página(s) con OCR..."))
            full_text = ""
            for i, page in enumerate(pages):
                self._check_cancelled()
                page_number = first_page + i
                self.queue.put(("progress", i + 1, len(pages)))
                self.queue.put(("log", f"  Página {page_number}..."))

                raw_text = pytesseract.image_to_string(page, lang=lang, config="--psm 3")
                corrected_text = fix_text(raw_text, verbose=False)

                if with_tables and page_number in tables_by_page and insert_tables:
                    corrected_text = insert_tables(
                        corrected_text, tables_by_page[page_number]
                    )

                full_text += f"\n\n--- Página {page_number} ---\n\n{corrected_text}"

            tables_suffix = "_tablas" if with_tables else ""
            output_path = output_dir / f"{pdf_path.stem}{suffix}{tables_suffix}.md"
            output_path.write_text(full_text, encoding="utf-8")

            self.queue.put(("done", str(output_path)))

        except ConversionInProgress:
            self.queue.put(("log", "Conversión cancelada por el usuario."))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", f"{exc}\n\n{traceback.format_exc(limit=3)}"))

    def _check_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise ConversionInProgress()


def create_file_selector(
    parent,
    label_text: str,
    variable: ctk.StringVar,
    filetypes: list[tuple[str, str]],
    on_change: Optional[Callable[[str], None]] = None,
) -> ctk.CTkFrame:
    """Creates a row with label + read-only text field + 'Browse' button."""
    from tkinter import filedialog

    frame = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(frame, text=label_text, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
        fill="x", pady=(0, 4)
    )

    row = ctk.CTkFrame(frame, fg_color="transparent")
    row.pack(fill="x")

    entry = ctk.CTkEntry(row, textvariable=variable, state="readonly")
    entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    def _browse():
        path = filedialog.askopenfilename(title=label_text, filetypes=filetypes)
        if path:
            variable.set(path)
            if on_change:
                on_change(path)

    ctk.CTkButton(row, text="Examinar...", width=110, command=_browse).pack(side="left")

    return frame


def create_folder_selector(
    parent, label_text: str, variable: ctk.StringVar
) -> ctk.CTkFrame:
    from tkinter import filedialog

    frame = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(frame, text=label_text, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
        fill="x", pady=(0, 4)
    )

    row = ctk.CTkFrame(frame, fg_color="transparent")
    row.pack(fill="x")

    entry = ctk.CTkEntry(row, textvariable=variable, state="readonly")
    entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    def _browse():
        path = filedialog.askdirectory(title=label_text)
        if path:
            variable.set(path)

    ctk.CTkButton(row, text="Examinar...", width=110, command=_browse).pack(side="left")

    return frame


def create_language_selector(
    parent, default_checked: tuple[str, ...] = DEFAULT_LANGUAGES
) -> tuple[ctk.CTkFrame, dict[str, ctk.BooleanVar]]:
    """
    Creates a panel with an independent checkbox per language (instead of
    a dropdown with prefixed combinations), so they can be freely checked
    and unchecked according to which languages actually appear in the PDF.

    Returns (frame, variables), where `variables` is a dictionary
    {tesseract_code: BooleanVar} that is queried with get_lang_string().
    """
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(
        frame, text="Idiomas del documento (marca todos los que aparezcan)",
        anchor="w", font=ctk.CTkFont(weight="bold"),
    ).pack(fill="x", pady=(0, 6))

    grid = ctk.CTkFrame(frame, fg_color="transparent")
    grid.pack(fill="x")

    variables: dict[str, ctk.BooleanVar] = {}
    columns = 3
    for i, (code, name) in enumerate(TESSERACT_LANGUAGES):
        var = ctk.BooleanVar(value=(code in default_checked))
        variables[code] = var
        ctk.CTkCheckBox(grid, text=name, variable=var).grid(
            row=i // columns, column=i % columns, sticky="w", padx=(0, 18), pady=5
        )

    return frame, variables


def get_lang_string(variables: dict[str, ctk.BooleanVar]) -> Optional[str]:
    """
    Converts the checked boxes into the language string Tesseract expects
    (e.g. "grc+eng+fra"). Returns None if none is checked, so the GUI can
    warn instead of launching OCR without a language.
    """
    order = [code for code, _ in TESSERACT_LANGUAGES]
    selected = [c for c in order if variables[c].get()]
    return "+".join(selected) if selected else None
