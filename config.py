r"""
config.py
---------
Configuración centralizada de rutas externas (Tesseract, Poppler).

En vez de escribir estas rutas dentro de cada script, se leen aquí desde
variables de entorno. Así, para usar el proyecto en otro equipo basta con
definir las variables antes de ejecutar (o crear un archivo `.env`), sin
tocar ningún archivo .py.

Uso en Windows (PowerShell), antes de ejecutar el script:

    $env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    $env:POPPLER_PATH  = "C:\poppler\Library\bin"

Uso en Linux/macOS (donde Tesseract y Poppler suelen estar ya en el PATH):

    export TESSERACT_CMD=/usr/bin/tesseract
    export POPPLER_PATH=/usr/bin

Si no se definen, se usan los valores por defecto de abajo (los del equipo
original de desarrollo en Windows). Edítalos aquí si prefieres no usar
variables de entorno, pero entonces evita subir tus rutas personales a un
repositorio público.
"""

from __future__ import annotations

import os
import shutil
import sys

import pytesseract

# ---------------------------------------------------------------------------
# Rutas configurables
# ---------------------------------------------------------------------------

DEFAULT_TESSERACT_CMD_WINDOWS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
DEFAULT_POPPLER_PATH_WINDOWS = r"C:\poppler\Library\bin"

TESSERACT_CMD = os.environ.get("TESSERACT_CMD") or (
    DEFAULT_TESSERACT_CMD_WINDOWS if os.name == "nt" else (shutil.which("tesseract") or "tesseract")
)

# En Linux/macOS, pdf2image usa Poppler desde el PATH si POPPLER_PATH es None.
POPPLER_PATH = os.environ.get("POPPLER_PATH") or (
    DEFAULT_POPPLER_PATH_WINDOWS if os.name == "nt" else None
)

# Aplica la ruta de Tesseract una única vez, para todo el proyecto.
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def verificar_dependencias_externas() -> None:
    """Comprueba que Tesseract está localizable y avisa con un mensaje claro
    si no lo está, en vez de dejar que falle más adelante con un error críptico."""
    if not shutil.which(TESSERACT_CMD) and not os.path.isfile(TESSERACT_CMD):
        print(
            f"[config] AVISO: no se encuentra el ejecutable de Tesseract en "
            f"'{TESSERACT_CMD}'. Define la variable de entorno TESSERACT_CMD "
            f"o instala Tesseract OCR.",
            file=sys.stderr,
        )
