"""
PDF_to_Markdown_with_Tables_GUI.py
------------------------------------
English entry point for the table-extracting desktop app. Thin wrapper,
same idea as PDF_to_Markdown_GUI.py: switches the shared UI strings to
English before the window is built, then reuses the exact same App class
and conversion logic as PDF_a_Markdown_con_Tablas_GUI.py (the Spanish
entry point).
"""

from __future__ import annotations

import i18n

i18n.set_language("en")

from PDF_a_Markdown_con_Tablas_GUI import App  # noqa: E402  (must come after set_language)

if __name__ == "__main__":
    app = App()
    app.mainloop()
