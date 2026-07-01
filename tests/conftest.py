"""
conftest.py
-----------
Shared pytest configuration and fixtures for the test suite.

The project's modules (config.py, ocr_postprocess.py, etc.) live at the
repository root, not inside a package, so this file adds the repo root to
sys.path before any test module tries to import them.
"""

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_pdf_path() -> Path:
    """
    Path to a small 3-page sample PDF used across tests:
      - page 1: plain text, no table, no caption.
      - page 2: text + a real 4x3 table with an explicit "Table 1" caption,
        plus a "Figure 1" caption (which must NOT trigger table extraction).
      - page 3: only a "Figure 2" caption, no table at all.

    It is a "digital" PDF (selectable text), generated once with reportlab
    and committed to the repository as a small binary fixture, so the test
    suite does not need reportlab as a dependency to run.
    """
    path = FIXTURES_DIR / "sample_with_table.pdf"
    assert path.is_file(), f"Missing fixture: {path}"
    return path


def tesseract_available() -> bool:
    """True if a usable Tesseract binary can be located on this machine."""
    try:
        import config  # noqa: WPS433 (local import to avoid import cost when unused)
        return bool(shutil.which(config.TESSERACT_CMD) or Path(config.TESSERACT_CMD).is_file())
    except Exception:
        return False


def poppler_available() -> bool:
    """True if a usable Poppler (pdftoppm) can be located on this machine."""
    try:
        import config  # noqa: WPS433
        return config._locate_poppler() is not None  # noqa: SLF001 (test-only introspection)
    except Exception:
        return False


requires_tesseract = pytest.mark.skipif(
    not tesseract_available(), reason="Tesseract OCR is not installed/found on this machine"
)
requires_poppler = pytest.mark.skipif(
    not poppler_available(), reason="Poppler is not installed/found on this machine"
)
