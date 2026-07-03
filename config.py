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

import json
import os
import shlex
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

# Fixed directories where the Windows installers of Tesseract/Poppler are
# known to land by default.
CANDIDATE_WINDOWS_DIRECTORIES = [
    r"C:\Program Files\Tesseract-OCR",
    r"C:\poppler\Library\bin",
]


def _winget_search_roots() -> list[str]:
    """
    Where 'winget install' leaves things on Windows:
      - Portable-type packages get a symlink in the per-user "Links"
        directory (which winget also adds to PATH, but a process already
        running, like our app, does not see that PATH update until it is
        relaunched, hence checking the folder directly here too).
      - Everything winget installs (portable or not) lives somewhere
        under the "Packages" directory, one subfolder per package.
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return []
    base = os.path.join(local_appdata, "Microsoft", "WinGet")
    return [os.path.join(base, "Links"), os.path.join(base, "Packages")]


def _find_executable(name: str) -> Optional[str]:
    """
    Looks up an executable by name, in this order: the process's inherited
    PATH (shutil.which), and then platform-specific fallback directories
    that a process launched by double-clicking (Finder on macOS, Explorer
    on Windows) does not inherit in its PATH even when the tool is
    perfectly installed:
      - macOS: typical Homebrew/MacPorts directories.
      - Windows: the default Tesseract/Poppler install directories, plus
        wherever 'winget install' may have placed things.

    Note: both branches deliberately use os.path (not pathlib.Path), so
    each can be exercised in tests regardless of the host OS by
    monkeypatching sys.platform/os.name. pathlib.Path picks its Windows
    vs. Posix flavour from the real os.name at instantiation time (not
    from a monkeypatched one), so e.g. building a WindowsPath while
    running the test suite on a real Mac raises NotImplementedError; a
    macOS-branch test that only monkeypatches os.name to "nt" (to
    exercise the Windows branch) would otherwise crash inside this very
    macOS branch, since sys.platform is still genuinely "darwin" and
    this branch runs unconditionally first.
    """
    found = shutil.which(name)
    if found:
        return found

    if sys.platform == "darwin":
        for directory in CANDIDATE_MACOS_DIRECTORIES:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate

    elif os.name == "nt":
        for directory in CANDIDATE_WINDOWS_DIRECTORIES:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
        for root in _winget_search_roots():
            if not os.path.isdir(root):
                continue
            direct = os.path.join(root, name)
            if os.path.isfile(direct):
                return direct
            for dirpath, _dirnames, filenames in os.walk(root):
                if name in filenames:
                    return os.path.join(dirpath, name)

    return None


def refresh_paths() -> None:
    """
    (Re)computes TESSERACT_CMD and POPPLER_PATH from scratch. Called once
    when the module is first imported, and again after successfully
    installing Tesseract/Poppler (via Homebrew or winget), since a program
    that just got installed was obviously not found the first time around.
    """
    global TESSERACT_CMD, POPPLER_PATH

    TESSERACT_CMD = os.environ.get("TESSERACT_CMD") or (
        _find_executable("tesseract.exe" if os.name == "nt" else "tesseract")
        or (DEFAULT_TESSERACT_CMD_WINDOWS if os.name == "nt" else "tesseract")
    )

    if os.environ.get("POPPLER_PATH"):
        POPPLER_PATH = os.environ["POPPLER_PATH"]
    else:
        _pdftoppm = _find_executable("pdftoppm.exe" if os.name == "nt" else "pdftoppm")
        if _pdftoppm:
            POPPLER_PATH = str(Path(_pdftoppm).parent)
        elif os.name == "nt":
            POPPLER_PATH = DEFAULT_POPPLER_PATH_WINDOWS
        else:
            POPPLER_PATH = None

    # Apply the Tesseract path for the whole project.
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


TESSERACT_CMD: str
POPPLER_PATH: Optional[str]
refresh_paths()


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


# On Intel Macs, Homebrew's prefix is /usr/local, a directory that (unlike
# /opt/homebrew on Apple Silicon) already exists on a stock, untouched
# macOS install. Since Big Sur, macOS marks that top-level directory itself
# with SIP's "restricted" flag as part of the Signed System Volume, so
# 'chown /usr/local' fails with "Operation not permitted" even when run as
# root via an administrator-elevated shell. The fix, also used internally
# by Homebrew's own installer, is to never touch /usr/local itself and
# instead create/take ownership of only the specific subdirectories
# Homebrew actually needs to write into.
_HOMEBREW_INTEL_SUBDIRS = [
    "bin", "etc", "include", "lib", "sbin", "share", "var", "opt",
    "Cellar", "Caskroom", "Frameworks", "Homebrew",
    "share/zsh", "share/zsh/site-functions", "etc/bash_completion.d",
]


def install_homebrew(on_output: Callable[[str], None]) -> tuple[bool, str]:
    """
    Installs Homebrew itself on macOS without sending the user to
    Terminal. Returns (success, message).
    """
    if sys.platform != "darwin":
        return False, "La instalación automática de Homebrew solo está disponible en macOS."

    prefix = _homebrew_prefix()
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""

    if prefix == "/opt/homebrew":
        # Does not exist on a stock Mac, so it is safe (and necessary) to
        # create and chown it directly.
        targets = [prefix]
    else:
        targets = [os.path.join(prefix, sub) for sub in _HOMEBREW_INTEL_SUBDIRS]

    needs_prep = any(
        not os.path.isdir(target) or not os.access(target, os.W_OK) for target in targets
    )

    if needs_prep:
        on_output("Se necesita permiso de administrador para preparar Homebrew.")
        on_output("macOS te pedirá tu contraseña en un momento (diálogo del sistema).")
        quoted_targets = " ".join(shlex.quote(t) for t in targets)
        prep_script = (
            f"mkdir -p {quoted_targets} && chown -R {shlex.quote(user + ':admin')} {quoted_targets}"
        )
        # json.dumps produces a double-quoted string with \" and \\
        # escaped exactly the way AppleScript's string literal syntax
        # also expects, which is what "do shell script "..."" needs here.
        applescript = f"do shell script {json.dumps(prep_script)} with administrator privileges"
        try:
            result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True)
        except Exception as exc:  # noqa: BLE001
            return False, f"No se pudo pedir permisos de administrador: {exc}"
        if result.returncode != 0:
            if "User canceled" in (result.stderr or ""):
                return False, "Instalación cancelada (se rechazó la solicitud de contraseña)."
            return False, f"No se pudo preparar Homebrew: {result.stderr.strip()}"
        on_output("Permisos concedidos.")

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
            refresh_paths()
            return True, "Instalación completada correctamente."
        return False, f"'brew install' terminó con un error (código {process.returncode})."
    except Exception as exc:  # noqa: BLE001
        return False, f"Error al ejecutar Homebrew: {exc}"


# ---------------------------------------------------------------------------
# Automatic installation via winget (Windows only)
# ---------------------------------------------------------------------------
# winget (Windows Package Manager / "App Installer") ships pre-installed on
# Windows 11 and on Windows 10 systems kept up to date through the Microsoft
# Store, so it can be assumed present on the large majority of machines
# without asking the person to install anything extra first. Unlike
# Homebrew on macOS, winget installers can usually run fully silently
# without any extra administrator prompt handling on our side: '--silent'
# together with '--scope user' avoids the UAC elevation dialog for
# packages that offer a per-user installer, which covers Poppler and the
# VC++ Redistributable. Tesseract's own installer (UB-Mannheim's NSIS
# package) is only published machine-wide, so for that one specifically
# install_winget_packages() below falls back to installing without a
# forced scope, which does show the standard UAC prompt just for that
# package; there is no way around that without a different Tesseract
# distribution.

WINGET_PACKAGE_IDS = {
    "vcredist": "Microsoft.VCRedist.2015+.x64",
    "tesseract": "UB-Mannheim.TesseractOCR",
    "poppler": "oschwartz10612.Poppler",
}


def _vcredist_installed() -> bool:
    """
    True if the Visual C++ Redistributable (2015-2022) appears to be
    installed, checked via the presence of vcruntime140.dll in
    System32. This is the DLL that pdfinfo.exe/pdftoppm.exe (Poppler)
    and Tesseract need to even start; without it they fail with a
    generic Windows "VCRUNTIME140.dll was not found" dialog that has
    nothing to do with Poppler/Tesseract themselves. Most Windows
    machines already have it (many other programs install it as a side
    effect), but a truly clean system, such as Windows Sandbox, does
    not.
    """
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return os.path.isfile(os.path.join(system_root, "System32", "vcruntime140.dll"))


def winget_available() -> bool:
    """True on Windows if the 'winget' executable can be located."""
    return os.name == "nt" and shutil.which("winget") is not None


def missing_winget_packages() -> list[str]:
    """
    Returns the winget package IDs that still need to be installed:
    the Visual C++ Redistributable (a shared dependency both Tesseract
    and Poppler need just to launch), plus whichever of Tesseract/
    Poppler cannot currently be found. Listed in install order, since
    the redistributable has to be there before the other two are worth
    installing.
    """
    packages: list[str] = []
    if not _vcredist_installed():
        packages.append(WINGET_PACKAGE_IDS["vcredist"])
    if _find_executable("tesseract.exe") is None:
        packages.append(WINGET_PACKAGE_IDS["tesseract"])
    if _locate_poppler() is None:
        packages.append(WINGET_PACKAGE_IDS["poppler"])
    return packages


def install_winget_packages(
    packages: list[str], on_output: Callable[[str], None]
) -> tuple[bool, str]:
    """
    Runs 'winget install' for each package ID, streaming output live.
    Tries --scope user first, so it does not need the UAC administrator
    prompt when possible (this works fine for Poppler and the VC++
    Redistributable). Some packages, though, are only published with a
    machine-wide installer (Tesseract's UB-Mannheim NSIS installer is one
    of them): winget then fails with error 0x8A150010 ("no applicable
    installer found"), since it filtered out the only installer available
    for not matching the requested "user" scope. When that specific error
    is detected, the same package is retried without forcing a scope,
    letting winget fall back to its default (machine-wide) installer,
    which will show the standard UAC prompt for that one package only.
    Returns (success, message).
    """
    winget = shutil.which("winget")
    if not winget:
        return False, "No se ha encontrado winget en este equipo."
    if not packages:
        return True, "No hay nada que instalar."

    NO_APPLICABLE_INSTALLER_CODES = {"2316632080", "-1978335216", "0x8a150010"}

    def _run(package_id: str, use_user_scope: bool) -> tuple[bool, str]:
        args = [
            winget, "install", "--id", package_id, "--exact", "--silent",
            "--accept-package-agreements", "--accept-source-agreements",
        ]
        if use_user_scope:
            args[3:3] = ["--scope", "user"]
        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            on_output(line.rstrip())
        process.wait()
        return process.returncode == 0, str(process.returncode)

    all_ok = True
    for package_id in packages:
        on_output(f"Instalando {package_id}...")
        try:
            success, returncode = _run(package_id, use_user_scope=True)
            if not success and returncode in NO_APPLICABLE_INSTALLER_CODES:
                on_output(
                    f"⚠ {package_id} no tiene instalador para 'solo mi usuario'; "
                    "reintentando para todo el equipo (puede pedir permiso de administrador)..."
                )
                success, returncode = _run(package_id, use_user_scope=False)
            if not success:
                all_ok = False
                on_output(f"⚠ {package_id} terminó con código {returncode}.")
        except Exception as exc:  # noqa: BLE001
            all_ok = False
            on_output(f"⚠ Error instalando {package_id}: {exc}")

    refresh_paths()
    if all_ok:
        return True, "Instalación completada correctamente."
    return False, "Alguno de los programas no se pudo instalar (revisa el registro de arriba)."
