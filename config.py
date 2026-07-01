r"""
config.py
---------
Centralized configuration of external tool paths (Tesseract, Poppler).

Instead of hardcoding these paths inside every script, they are read here
from environment variables. This way, using the project on another machine
only requires setting the variables before running (or creating an `.env`
file), without touching any .py file.

Usage on Windows (PowerShell), before running the script:

    $env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    $env:POPPLER_PATH  = "C:\poppler\Library\bin"

Usage on Linux/macOS, if you need to force a specific path:

    export TESSERACT_CMD=/usr/bin/tesseract
    export POPPLER_PATH=/usr/bin

Note about macOS and packaged apps (PyInstaller / double-click from
Finder): an app opened by double-clicking does NOT inherit the PATH that
your Terminal has (the one Homebrew configures in your .zshrc/.bash_profile).
That is why "brew install tesseract poppler" leaves the programs installed
and working perfectly from the Terminal, yet the app still cannot find them
if we only rely on PATH. To avoid this, in addition to PATH, the typical
Homebrew (Apple Silicon and Intel) and MacPorts installation directories
are also searched explicitly.

If no environment variables are set and nothing is found in those
directories, the defaults below are used (the ones from the original
development machine, on Windows). Edit them here if you prefer not to use
environment variables, but then avoid pushing your personal paths to a
public repository.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import pytesseract

# ---------------------------------------------------------------------------
# Configurable paths
# ---------------------------------------------------------------------------

DEFAULT_TESSERACT_CMD_WINDOWS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
DEFAULT_POPPLER_PATH_WINDOWS = r"C:\poppler\Library\bin"

# Directories where Homebrew/MacPorts typically install their binaries on
# macOS.
# /opt/homebrew/bin  -> Homebrew on Apple silicon Macs (M1/M2/M3...)
# /usr/local/bin      -> Homebrew on Intel Macs
# /opt/local/bin       -> MacPorts
CANDIDATE_MACOS_DIRECTORIES = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]


def _find_executable(name: str) -> Optional[str]:
    """
    Looks up an executable by name, in this order: the process's inherited
    PATH (shutil.which), and on macOS also the typical Homebrew/MacPorts
    directories (which a process launched by double-clicking from Finder
    does not see, even if the tool is perfectly installed).
    """
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == "darwin":
        for directory in CANDIDATE_MACOS_DIRECTORIES:
            candidate = Path(directory) / name
            if candidate.is_file():
                return str(candidate)
    return None


TESSERACT_CMD = os.environ.get("TESSERACT_CMD") or (
    DEFAULT_TESSERACT_CMD_WINDOWS if os.name == "nt" else (_find_executable("tesseract") or "tesseract")
)

if os.environ.get("POPPLER_PATH"):
    POPPLER_PATH = os.environ["POPPLER_PATH"]
elif os.name == "nt":
    POPPLER_PATH = DEFAULT_POPPLER_PATH_WINDOWS
else:
    # On Linux/macOS, derive the directory from wherever pdftoppm was found
    # (normal PATH, or the Homebrew/MacPorts directories above).
    _pdftoppm = _find_executable("pdftoppm")
    POPPLER_PATH = str(Path(_pdftoppm).parent) if _pdftoppm else None

# Apply the Tesseract path once, for the whole project.
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def _locate_poppler() -> Optional[str]:
    """
    Returns the path to Poppler's 'pdftoppm' executable (the one pdf2image
    uses), looking first in POPPLER_PATH and otherwise via
    _find_executable() (PATH + typical Homebrew/MacPorts directories on
    macOS). None if it cannot be found anywhere.
    """
    name = "pdftoppm.exe" if os.name == "nt" else "pdftoppm"
    if POPPLER_PATH:
        candidate = os.path.join(POPPLER_PATH, name)
        if os.path.isfile(candidate):
            return candidate
    return _find_executable(name)


def check_external_dependencies() -> list[str]:
    """
    Checks that Tesseract and Poppler can be located. Returns a list of
    warning messages (empty if everything is in order).

    Important: this function does NOT print anything on its own. Desktop
    applications packaged with PyInstaller in --windowed mode have no
    visible console, so a warning printed via print()/stderr is lost
    without anyone seeing it. Whoever calls this function must display the
    returned messages through its own interface (GUI log, print() for the
    CLI, etc.).

    Note: the warning strings below are intentionally kept in Spanish, since
    they are shown as-is in the desktop apps' log window, which is aimed at
    Spanish-speaking, non-technical users.
    """
    warnings: list[str] = []

    if not shutil.which(TESSERACT_CMD) and not os.path.isfile(TESSERACT_CMD):
        if sys.platform == "darwin":
            instructions = "Instálalo con Homebrew: brew install tesseract tesseract-lang"
        elif os.name == "nt":
            instructions = (
                "Instálalo desde https://github.com/UB-Mannheim/tesseract/wiki "
                "y define la variable de entorno TESSERACT_CMD con la ruta al .exe"
            )
        else:
            instructions = "Instálalo con el gestor de paquetes de tu sistema (p. ej. apt install tesseract-ocr)"
        warnings.append(
            f"No se encuentra Tesseract OCR (ruta probada: '{TESSERACT_CMD}'). {instructions}"
        )

    if _locate_poppler() is None:
        if sys.platform == "darwin":
            instructions = "Instálalo con Homebrew: brew install poppler"
        elif os.name == "nt":
            instructions = (
                "Descárgalo de https://github.com/oschwartz10612/poppler-windows/releases "
                "y define la variable de entorno POPPLER_PATH con la carpeta 'bin' descomprimida"
            )
        else:
            instructions = "Instálalo con el gestor de paquetes de tu sistema (p. ej. apt install poppler-utils)"
        warnings.append(f"No se encuentra Poppler (necesario para leer el PDF). {instructions}")

    return warnings
