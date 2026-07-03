"""
PDF_a_Markdown_GUI.py
----------------------
Desktop application (no terminal, no visible Python) to convert a PDF
with classical Greek text into a Markdown file.

Designed for colleagues with no computing background: pick the PDF,
pick where to save it, click "Convertir" ("Convert"), and that's it.

Note on language: the code (identifiers, comments) is in English, but the
text actually shown inside the window (labels, buttons, log messages) is
kept in Spanish, since this app is meant for non-technical, Spanish-
speaking colleagues.

This version does NOT extract tables (for that, see the sibling app
`PDF_a_Markdown_con_Tablas_GUI.py`), which makes it faster and simpler
for documents that are plain running text.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

import i18n
from gui_common import (
    SECONDARY_TEXT_COLOR,
    ConversionEngine,
    ensure_dependencies,
    open_file,
    open_folder,
    create_file_selector,
    create_folder_selector,
    create_language_selector,
    get_lang_string,
)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(i18n._("app_title_basic"))
        self.geometry("680x700")
        self.minsize(600, 620)

        self.engine = ConversionEngine()
        self.last_output: Path | None = None

        self.pdf_var = ctk.StringVar()
        self.output_dir_var = ctk.StringVar(value=str(Path.home() / "Documents" / "markdown"))
        self.page_range_active_var = ctk.BooleanVar(value=False)
        self.start_page_var = ctk.StringVar()
        self.end_page_var = ctk.StringVar()

        self._build_ui()
        self.after(150, self._poll_queue)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=26, pady=22)

        # --- Header ---
        header = ctk.CTkFrame(container, corner_radius=14)
        header.pack(fill="x", pady=(0, 18))
        ctk.CTkLabel(
            header, text=i18n._("app_header_basic"),
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(14, 2))
        ctk.CTkLabel(
            header,
            text=i18n._("app_subtitle_basic"),
            text_color=SECONDARY_TEXT_COLOR,
        ).pack(anchor="w", padx=18, pady=(0, 14))

        # --- Settings card ---
        card = ctk.CTkFrame(container, corner_radius=14)
        card.pack(fill="x", pady=(0, 16))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)

        create_file_selector(
            inner,
            i18n._("label_select_pdf"),
            self.pdf_var,
            filetypes=[(i18n._("filetype_pdf"), "*.pdf")],
        ).pack(fill="x", pady=(0, 16))

        create_folder_selector(
            inner, i18n._("label_output_folder"), self.output_dir_var
        ).pack(fill="x", pady=(0, 16))

        lang_frame, self.lang_vars = create_language_selector(inner)
        lang_frame.pack(fill="x", pady=(0, 16))

        # Optional page range
        ctk.CTkCheckBox(
            inner, text=i18n._("page_range_checkbox"),
            variable=self.page_range_active_var, command=self._toggle_page_range,
        ).pack(anchor="w", pady=(0, 6))

        self.page_range_row = ctk.CTkFrame(inner, fg_color="transparent")
        self.page_range_row.pack(fill="x")
        ctk.CTkLabel(self.page_range_row, text=i18n._("page_range_from")).pack(side="left")
        self.start_page_entry = ctk.CTkEntry(self.page_range_row, textvariable=self.start_page_var, width=70, state="disabled")
        self.start_page_entry.pack(side="left", padx=(6, 18))
        ctk.CTkLabel(self.page_range_row, text=i18n._("page_range_to")).pack(side="left")
        self.end_page_entry = ctk.CTkEntry(self.page_range_row, textvariable=self.end_page_var, width=70, state="disabled")
        self.end_page_entry.pack(side="left", padx=(6, 0))

        # --- Convert button ---
        self.convert_button = ctk.CTkButton(
            container, text=i18n._("convert_button_basic"), height=46,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_convert,
        )
        self.convert_button.pack(fill="x", pady=(0, 14))

        self.progress_bar = ctk.CTkProgressBar(container, height=10)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 12))

        # --- Log ---
        ctk.CTkLabel(container, text=i18n._("log_title"), anchor="w",
                     font=ctk.CTkFont(weight="bold")).pack(fill="x")
        self.log_box = ctk.CTkTextbox(container, height=170, state="disabled")
        self.log_box.pack(fill="both", expand=True, pady=(6, 14))

        self.bottom_row = ctk.CTkFrame(container, fg_color="transparent")
        self.bottom_row.pack(fill="x")
        self.open_file_button = ctk.CTkButton(
            self.bottom_row, text=i18n._("open_file_button"), state="disabled",
            command=self._open_result,
        )
        self.open_file_button.pack(side="left")
        self.open_folder_button = ctk.CTkButton(
            self.bottom_row, text=i18n._("open_folder_button"), state="disabled",
            command=self._open_output_folder, fg_color="#8A6D4E", hover_color="#6E5540",
        )
        self.open_folder_button.pack(side="left", padx=(10, 0))

    def _toggle_page_range(self) -> None:
        state = "normal" if self.page_range_active_var.get() else "disabled"
        self.start_page_entry.configure(state=state)
        self.end_page_entry.configure(state=state)

    # -------------------------------------------------------------- logic
    def _log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_convert(self) -> None:
        if self.engine.is_running():
            return

        pdf_path = self.pdf_var.get().strip()
        output_dir = self.output_dir_var.get().strip()

        if not pdf_path:
            self._log(i18n._("warn_select_pdf_first"))
            return
        if not Path(pdf_path).is_file():
            self._log(i18n._("warn_pdf_not_found"))
            return
        if not output_dir:
            self._log(i18n._("warn_set_output_folder"))
            return

        lang = get_lang_string(self.lang_vars)
        if lang is None:
            self._log(i18n._("warn_select_language"))
            return

        start_page = end_page = None
        if self.page_range_active_var.get():
            try:
                start_page = int(self.start_page_var.get())
                end_page = int(self.end_page_var.get())
                if start_page < 1 or end_page < start_page:
                    raise ValueError
            except ValueError:
                self._log(i18n._("warn_invalid_page_range"))
                return

        def _start_conversion() -> None:
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")
            self.progress_bar.set(0)
            self.convert_button.configure(state="disabled", text=i18n._("converting_button"))
            self.open_file_button.configure(state="disabled")
            self.open_folder_button.configure(state="disabled")

            self.engine.start(
                pdf_path=Path(pdf_path),
                output_dir=Path(output_dir),
                lang=lang,
                with_tables=False,
                start_page=start_page,
                end_page=end_page,
            )

        # If Tesseract/Poppler are missing, this opens a dialog offering to
        # install them automatically (macOS + Homebrew) instead of failing
        # outright; _start_conversion() runs once everything is ready.
        ensure_dependencies(self, _start_conversion)

    def _poll_queue(self) -> None:
        try:
            while True:
                message = self.engine.queue.get_nowait()
                msg_type = message[0]

                if msg_type == "log":
                    self._log(message[1])
                elif msg_type == "progress":
                    current, total = message[1], message[2]
                    self.progress_bar.set(current / total if total else 0)
                elif msg_type == "done":
                    path = Path(message[1])
                    self.last_output = path
                    self._log(i18n._("log_conversion_done", path=path))
                    self.convert_button.configure(state="normal", text=i18n._("convert_button_basic"))
                    self.open_file_button.configure(state="normal")
                    self.open_folder_button.configure(state="normal")
                    self.progress_bar.set(1)
                elif msg_type == "error":
                    self._log(i18n._("log_error_header", error=message[1]))
                    self.convert_button.configure(state="normal", text=i18n._("convert_button_basic"))
        except Exception:
            pass
        finally:
            self.after(150, self._poll_queue)

    def _open_result(self) -> None:
        if self.last_output:
            open_file(self.last_output)

    def _open_output_folder(self) -> None:
        if self.last_output:
            open_folder(self.last_output.parent)


if __name__ == "__main__":
    app = App()
    app.mainloop()
