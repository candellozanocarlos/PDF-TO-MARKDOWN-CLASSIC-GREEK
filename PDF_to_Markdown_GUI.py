"""
PDF_to_Markdown_GUI.py
-----------------------
English entry point for the basic (no tables) desktop app. This is a
thin wrapper: it switches the shared UI strings to English before the
window is built, then reuses the exact same App class and conversion
logic as PDF_a_Markdown_GUI.py (the Spanish entry point), so both
language variants stay in sync automatically instead of drifting apart
as two separate copies of the code.
"""

from __future__ import annotations

import i18n

i18n.set_language("en")

from PDF_a_Markdown_GUI import App  # noqa: E402  (must come after set_language)

if __name__ == "__main__":
    app = App()
    app.mainloop()
