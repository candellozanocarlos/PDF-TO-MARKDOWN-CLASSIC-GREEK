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


class DependencyDialog(ctk.CTkToplevel):
    """
    Shown when Tesseract and/or Poppler cannot be located. Aimed at
    non-technical users who downloaded the packaged app and should never
    need to open a terminal/PowerShell window:

      - macOS: a single "Instalar automáticamente" button installs
        whatever is missing. If Homebrew itself is not present, it is
        installed first (macOS shows its own native administrator
        password dialog for the one step that needs it), and then
        Tesseract/Poppler are installed right after, in the same click.
      - Windows: the same button runs 'winget install' for Tesseract and
        Poppler with --scope user, which does not need the UAC
        administrator prompt. winget itself ships with Windows 10/11, so
        no separate installer-of-an-installer step is needed here.
      - Linux, or Windows without winget (rare, very old systems): shows
        the manual instructions already produced by
        config.check_external_dependencies().
    """

    def __init__(self, parent, warnings: list[str], on_ready: Callable[[], None]) -> None:
        super().__init__(parent)
        self.title("Faltan programas necesarios")
        self.geometry("560x440")
        self.minsize(520, 400)
        self.on_ready = on_ready
        self._result_queue: "queue.Queue[str]" = queue.Queue()
        self._installing = False

        ctk.CTkLabel(
            self, text="⚠️  Faltan programas externos",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(18, 6))

        ctk.CTkLabel(
            self, text="\n\n".join(warnings), justify="left", wraplength=510,
            text_color=WARNING_TEXT_COLOR,
        ).pack(anchor="w", padx=20, pady=(0, 14))

        self.log_box = ctk.CTkTextbox(self, height=150, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=20, pady=(0, 18))

        self.install_button: Optional[ctk.CTkButton] = None
        if sys.platform == "darwin":
            label = (
                "🍺  Instalar automáticamente" if config.homebrew_available()
                else "🍺  Instalar Homebrew y continuar"
            )
            self.install_button = ctk.CTkButton(button_row, text=label, command=self._start_install)
            self.install_button.pack(side="left")
        elif os.name == "nt" and config.winget_available():
            self.install_button = ctk.CTkButton(
                button_row, text="🪟  Instalar automáticamente", command=self._start_install,
            )
            self.install_button.pack(side="left")

        ctk.CTkButton(
            button_row, text="Cerrar", fg_color=SECONDARY_TEXT_COLOR,
            hover_color="#6E5540", command=self.destroy,
        ).pack(side="right")

        self.after(150, self._poll_queue)
        self.transient(parent)
        self.grab_set()

    def _log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _start_install(self) -> None:
        if self._installing or self.install_button is None:
            return
        self._installing = True
        self.install_button.configure(state="disabled", text="Instalando...")
        threading.Thread(target=self._run_install, daemon=True).start()

    def _run_install(self) -> None:
        if sys.platform == "darwin":
            self._run_install_macos()
        elif os.name == "nt":
            self._run_install_windows()

    def _run_install_macos(self) -> None:
        # Stage 1: Homebrew itself, only if it is not already there. May
        # show macOS's native administrator-password dialog once.
        if not config.homebrew_available():
            success, message = config.install_homebrew(on_output=self._result_queue.put)
            if not success:
                self._result_queue.put(f"__DONE__FAIL::{message}")
                return
            self._result_queue.put(f"__LOG__✅ {message}")

        # Stage 2: Tesseract / Poppler via 'brew install'.
        packages = config.missing_homebrew_packages()
        if packages:
            self._result_queue.put(f"__LOG__Instalando con Homebrew: {', '.join(packages)}")
            self._result_queue.put("__LOG__Puede tardar varios minutos. No cierres esta ventana.\n")
            success, message = config.install_homebrew_packages(packages, on_output=self._result_queue.put)
        else:
            success, message = True, "No faltaba nada más por instalar."

        status = "OK" if success else "FAIL"
        self._result_queue.put(f"__DONE__{status}::{message}")

    def _run_install_windows(self) -> None:
        packages = config.missing_winget_packages()
        if not packages:
            self._result_queue.put("__DONE__OK::No faltaba nada más por instalar.")
            return
        self._result_queue.put(f"__LOG__Instalando con winget: {', '.join(packages)}")
        self._result_queue.put("__LOG__Puede tardar varios minutos. No cierres esta ventana.\n")
        success, message = config.install_winget_packages(packages, on_output=self._result_queue.put)
        status = "OK" if success else "FAIL"
        self._result_queue.put(f"__DONE__{status}::{message}")

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._result_queue.get_nowait()
                if item.startswith("__LOG__"):
                    self._log(item[len("__LOG__"):])
                elif item.startswith("__DONE__"):
                    status_part, _, message = item.partition("::")
                    success = status_part.endswith("OK")
                    self._log(("\n✅ " if success else "\n❌ ") + message)
                    self._installing = False
                    if success and not config.check_external_dependencies():
                        self._log("Todo listo. Continuando con la conversión...")
                        self.after(1200, self._finish)
                    elif self.install_button is not None:
                        current_text = self.install_button.cget("text")
                        retry_text = current_text.split("  ", 1)[0] + "  Reintentar instalación"
                        self.install_button.configure(state="normal", text=retry_text)
                else:
                    self._log(item)
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(150, self._poll_queue)

    def _finish(self) -> None:
        self.destroy()
        self.on_ready()


def ensure_dependencies(parent, on_ready: Callable[[], None]) -> None:
    """
    Checks that Tesseract and Poppler can be located. If so, calls
    on_ready() right away. Otherwise opens DependencyDialog, which will
    call on_ready() itself once the missing programs have been installed
    (macOS + Homebrew case) — the caller does not need to retry anything.
    """
    warnings = config.check_external_dependencies()
    if not warnings:
        on_ready()
        return
    DependencyDialog(parent, warnings, on_ready)


def get_lang_string(variables: dict[str, ctk.BooleanVar]) -> Optional[str]:
    """
    Converts the checked boxes into the language string Tesseract expects
    (e.g. "grc+eng+fra"). Returns None if none is checked, so the GUI can
    warn instead of launching OCR without a language.
    """
    order = [code for code, _ in TESSERACT_LANGUAGES]
    selected = [c for c in order if variables[c].get()]
    return "+".join(selected) if selected else None
