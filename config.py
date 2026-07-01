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

Uso en Linux/macOS, si necesitas forzar una ruta concreta:

    export TESSERACT_CMD=/usr/bin/tesseract
    export POPPLER_PATH=/usr/bin

Nota sobre macOS y las apps empaquetadas (PyInstaller / doble clic desde
Finder): una app abierta con doble clic NO hereda el PATH que tiene tu
Terminal (el que configura Homebrew en tu .zshrc/.bash_profile). Por eso
"brew install tesseract poppler" deja los programas instalados y
funcionando perfectamente desde la Terminal, pero la app igualmente no los
encuentra si solo confiamos en el PATH. Para evitarlo, además del PATH,
también se buscan explícitamente las rutas de instalación típicas de
Homebrew (Apple Silicon y Intel) y MacPorts.

Si no se definen variables de entorno ni se encuentra nada en esas rutas,
se usan los valores por defecto de abajo (los del equipo original de
desarrollo en Windows). Edítalos aquí si prefieres no usar variables de
entorno, pero entonces evita subir tus rutas personales a un repositorio
público.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import pytesseract

# ---------------------------------------------------------------------------
# Rutas configurables
# ---------------------------------------------------------------------------

DEFAULT_TESSERACT_CMD_WINDOWS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
DEFAULT_POPPLER_PATH_WINDOWS = r"C:\poppler\Library\bin"

# Carpetas donde Homebrew/MacPorts suelen dejar sus binarios en macOS.
# /opt/homebrew/bin  -> Homebrew en Mac con chip Apple (M1/M2/M3...)
# /usr/local/bin      -> Homebrew en Mac con chip Intel
# /opt/local/bin       -> MacPorts
CARPETAS_MACOS_CANDIDATAS = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]


def _buscar_ejecutable(nombre: str) -> Optional[str]:
    """
    Busca un ejecutable por nombre en, por este orden: el PATH heredado del
    proceso (shutil.which), y en macOS además en las rutas típicas de
    Homebrew/MacPorts (que un proceso lanzado con doble clic desde Finder
    no ve, aunque estén perfectamente instaladas).
    """
    encontrado = shutil.which(nombre)
    if encontrado:
        return encontrado
    if sys.platform == "darwin":
        for carpeta in CARPETAS_MACOS_CANDIDATAS:
            candidato = Path(carpeta) / nombre
            if candidato.is_file():
                return str(candidato)
    return None


TESSERACT_CMD = os.environ.get("TESSERACT_CMD") or (
    DEFAULT_TESSERACT_CMD_WINDOWS if os.name == "nt" else (_buscar_ejecutable("tesseract") or "tesseract")
)

if os.environ.get("POPPLER_PATH"):
    POPPLER_PATH = os.environ["POPPLER_PATH"]
elif os.name == "nt":
    POPPLER_PATH = DEFAULT_POPPLER_PATH_WINDOWS
else:
    # En Linux/macOS, deducimos la carpeta a partir de dónde se encontró
    # pdftoppm (PATH normal, o las rutas de Homebrew/MacPorts de arriba).
    _pdftoppm = _buscar_ejecutable("pdftoppm")
    POPPLER_PATH = str(Path(_pdftoppm).parent) if _pdftoppm else None

# Aplica la ruta de Tesseract una única vez, para todo el proyecto.
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def _localizar_poppler() -> Optional[str]:
    """
    Devuelve la ruta al ejecutable 'pdftoppm' de Poppler (el que usa
    pdf2image), buscando primero en POPPLER_PATH y si no mediante
    _buscar_ejecutable() (PATH + rutas típicas de Homebrew/MacPorts en
    macOS). None si no se encuentra en ningún sitio.
    """
    nombre = "pdftoppm.exe" if os.name == "nt" else "pdftoppm"
    if POPPLER_PATH:
        candidato = os.path.join(POPPLER_PATH, nombre)
        if os.path.isfile(candidato):
            return candidato
    return _buscar_ejecutable(nombre)


def verificar_dependencias_externas() -> list[str]:
    """
    Comprueba que Tesseract y Poppler están localizables. Devuelve una lista
    de mensajes de aviso (vacía si todo está en orden).

    Importante: esta función NO imprime nada por su cuenta. En las
    aplicaciones de escritorio empaquetadas con PyInstaller en modo
    --windowed no hay consola visible, así que un aviso impreso por
    print()/stderr se pierde sin que nadie lo vea. Quien llame a esta
    función debe mostrar los mensajes devueltos por su propia interfaz
    (log de la GUI, print() en el caso del CLI, etc.).
    """
    avisos: list[str] = []

    if not shutil.which(TESSERACT_CMD) and not os.path.isfile(TESSERACT_CMD):
        if sys.platform == "darwin":
            instrucciones = "Instálalo con Homebrew: brew install tesseract tesseract-lang"
        elif os.name == "nt":
            instrucciones = (
                "Instálalo desde https://github.com/UB-Mannheim/tesseract/wiki "
                "y define la variable de entorno TESSERACT_CMD con la ruta al .exe"
            )
        else:
            instrucciones = "Instálalo con el gestor de paquetes de tu sistema (p. ej. apt install tesseract-ocr)"
        avisos.append(
            f"No se encuentra Tesseract OCR (ruta probada: '{TESSERACT_CMD}'). {instrucciones}"
        )

    if _localizar_poppler() is None:
        if sys.platform == "darwin":
            instrucciones = "Instálalo con Homebrew: brew install poppler"
        elif os.name == "nt":
            instrucciones = (
                "Descárgalo de https://github.com/oschwartz10612/poppler-windows/releases "
                "y define la variable de entorno POPPLER_PATH con la carpeta 'bin' descomprimida"
            )
        else:
            instrucciones = "Instálalo con el gestor de paquetes de tu sistema (p. ej. apt install poppler-utils)"
        avisos.append(f"No se encuentra Poppler (necesario para leer el PDF). {instrucciones}")

    return avisos
