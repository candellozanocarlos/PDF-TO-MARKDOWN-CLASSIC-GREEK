"""
text_layer.py
-------------
Reads the embedded text layer of digital (born-digital) PDFs.

For PDFs that already contain real text, the text layer is far more
accurate than OCR: it keeps short Greek words, sub-dots, macrons, Leiden
brackets, question marks in dates, etc. OCR is only needed for scanned
pages, or for pages whose text layer is unusable (e.g. old Greek fonts
without a Unicode mapping, which extract as "¶·Ú·ÙËÚ‹ÛÂÈ˜").
"""

from __future__ import annotations

import unicodedata

import pdfplumber

import ocr_postprocess

# Characters typical of legacy Greek fonts extracted without a ToUnicode map.
# (¿ and ¡ are deliberately excluded: they are normal in Spanish.)
_LEGACY_FONT_CHARS = set("˘˜‹›‰¤™∂√∞ª¶ˆ¢ø∏ı")
MIN_CHARS = 100          # below this, the page is treated as scanned/blank
MAX_SUSPICIOUS = 0.01    # max share of legacy-font or private-use characters


def is_usable(text: str) -> bool:
    """True if a page's text layer looks like real, readable text."""
    chars = [c for c in text if not c.isspace()]
    if len(chars) < MIN_CHARS:
        return False
    suspicious = sum(
        1 for c in chars
        if c in _LEGACY_FONT_CHARS or "\ue000" <= c <= "\uf8ff" or c == "\ufffd"
    )
    return suspicious / len(chars) <= MAX_SUSPICIOUS


def clean(text: str) -> str:
    """Minimal cleanup for text-layer pages (no OCR rules): NFC + Greek capital
    homoglyphs at the start of Latin words ('Τhe', 'Μéndez'), which some
    publisher PDFs embed."""
    text = unicodedata.normalize("NFC", text)
    return ocr_postprocess.fix_greek_capitals_in_latin_words(text)


def extract_pages(pdf_path: str, first_page: int, last_page: int | None) -> dict[int, str]:
    """
    Returns {page_number: text} (1-based) for the pages whose text layer is
    usable. Pages missing from the result must be OCR'd.
    """
    usable: dict[int, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        last = min(last_page or len(pdf.pages), len(pdf.pages))
        for number in range(first_page, last + 1):
            text = pdf.pages[number - 1].extract_text() or ""
            if is_usable(text):
                usable[number] = clean(text).strip()
    return usable
