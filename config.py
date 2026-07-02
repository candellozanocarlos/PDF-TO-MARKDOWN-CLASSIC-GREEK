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
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

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


# ---------------------------------------------------------------------------
# Automatic installation via Homebrew (macOS only)
# ---------------------------------------------------------------------------
# The goal is that a non-technical person who downloads the packaged .app
# and double-clicks it never has to open the Terminal, even on a brand
# new Mac that does not have Homebrew yet:
#
#   - Tesseract/Poppler missing but Homebrew present: 'brew install' runs
#     directly (see install_homebrew_packages below).
#   - Homebrew itself missing: install_homebrew() below installs it too,
#     using macOS's native administrator-password dialog (via osascript)
#     only for the single step that truly requires root (creating and
#     taking ownership of the Homebrew prefix directory). The official
#     Homebrew installer script is then run as the normal, non-root user,
#     exactly as it requires (it refuses to run as root/EUID 0), so it
#     never needs its own sudo prompt inside a non-interactive GUI
#     process.

def homebrew_available() -> bool:
    """True on macOS if the 'brew' executable can be located."""
    return sys.platform == "darwin" and _find_executable("brew") is not None


def missing_homebrew_packages() -> list[str]:
    """
    Returns the Homebrew formula names that still need to be installed,
    for whichever of Tesseract/Poppler cannot currently be found.
    """
    packages: list[str] = []
    if _find_executable("tesseract") is None:
        packages.extend(["tesseract", "tesseract-lang"])
    if _locate_poppler() is None:
        packages.append("poppler")
    return packages


def _homebrew_prefix() -> str:
    """Where Homebrew installs itself: /opt/homebrew on Apple Silicon,
    /usr/local on Intel Macs."""
    try:
        machine = subprocess.run(
            ["uname", "-m"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        machine = ""
    return "/opt/homebrew" if machine == "arm64" else "/usr/local"


def install_homebrew(on_output: Callable[[str], None]) -> tuple[bool, str]:
    """
    Installs Homebrew itself on macOS without sending the user to
    Terminal. Returns (success, message).
    """
    if sys.platform != "darwin":
        return False, "La instalación automática de Homebrew solo está disponible en macOS."

    prefix = _homebrew_prefix()
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""

    if not os.path.isdir(prefix) or not os.access(prefix, os.W_OK):
        on_output(f"Se necesita permiso de administrador para crear {prefix}.")
        on_output("macOS te pedirá tu contraseña en un momento (diálogo del sistema).")
        prep_script = f"mkdir -p '{prefix}' && chown -R '{user}':admin '{prefix}'"
        applescript = f'do shell script "{prep_script}" with administrator privileges'
        try:
            result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
        except Exception as exc:  # noqa: BLE001
            return False, f"No se pudo pedir permisos de administrador: {exc}"
        if result.returncode != 0:
            if "User canceled" in (result.stderr or ""):
                return False, "Instalación cancelada (se rechazó la solicitud de contraseña)."
            return False, f"No se pudo preparar {prefix}: {result.stderr.strip()}"
        on_output(f"Permisos concedidos. {prefix} está listo.")

    on_output("Descargando e instalando Homebrew (puede tardar varios minutos)...")
    env = dict(os.environ)
    env["NONINTERACTIVE"] = "1"  # Homebrew's installer must NOT run as root; this
                                  # just skips its own interactive confirmation prompts.
    install_command = (
        '/bin/bash -c "$(curl -fsSL '
        'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    )
    try:
        process = subprocess.Popen(
            ["/bin/bash", "-c", install_command],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=env,
        )
        assert process.stdout is not None
        for line in process.stdout:
            on_output(line.rstrip())
        process.wait()
    except Exception as exc:  # noqa: BLE001
        return False, f"Error al instalar Homebrew: {exc}"

    if process.returncode != 0:
        return False, f"El instalador de Homebrew terminó con un error (código {process.returncode})."

    if _find_executable("brew") is None:
        return False, (
            "Homebrew parece haberse instalado, pero no se encuentra su ejecutable. "
            "Cierra y vuelve a abrir esta aplicación."
        )

    return True, "Homebrew instalado correctamente."


def install_homebrew_packages(
    packages: list[str], on_output: Callable[[str], None]
) -> tuple[bool, str]:
    """
    Runs 'brew install <packages>', streaming each output line to
    on_output as it arrives (meant to feed a live log box in the GUI).
    Returns (success, message).
    """
    brew = _find_executable("brew")
    if not brew:
        return False, "No se ha encontrado Homebrew en este equipo."
    if not packages:
        return True, "No hay nada que instalar."
    try:
        process = subprocess.Popen(
            [brew, "install", *packages],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            on_output(line.rstrip())
        process.wait()
        if process.returncode == 0:
            return True, "Instalación completada correctamente."
        return False, f"'brew install' terminó con un error (código {process.returncode})."
    except Exception as exc:  # noqa: BLE001
        return False, f"Error al ejecutar Homebrew: {exc}"
