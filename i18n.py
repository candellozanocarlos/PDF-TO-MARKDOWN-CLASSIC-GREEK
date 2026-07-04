"""
i18n.py
-------
Minimal translation layer for the desktop apps' user-visible text (window
titles, buttons, log messages, dialog text). Two languages are supported:
Spanish ("es", the default, matching the original audience of these apps)
and English ("en").

Usage:
    import i18n
    i18n.set_language("en")   # call this BEFORE building the GUI
    ...
    self.title(i18n._("app_title_basic"))
    self._log(i18n._("log_page_processing", n=page_number))

The language can also be picked up from the APP_LANG environment variable
(set by the English entry-point scripts, e.g. PDF_to_Markdown_GUI.py,
before importing the shared App class), so PyInstaller can build a
separate English .exe/.app from the same underlying code.
"""

from __future__ import annotations

import os

_LANG = os.environ.get("APP_LANG", "es")
if _LANG not in ("es", "en"):
    _LANG = "es"


def set_language(lang: str) -> None:
    global _LANG
    if lang not in ("es", "en"):
        raise ValueError(f"Unsupported language: {lang!r} (use 'es' or 'en')")
    _LANG = lang


def get_language() -> str:
    return _LANG


STRINGS: dict[str, dict[str, str]] = {
    # --- Tesseract language names (language selector checkboxes) ---
    "lang_grc": {"es": "Griego clásico", "en": "Classical Greek"},
    "lang_eng": {"es": "Inglés", "en": "English"},
    "lang_fra": {"es": "Francés", "en": "French"},
    "lang_deu": {"es": "Alemán", "en": "German"},
    "lang_ita": {"es": "Italiano", "en": "Italian"},
    "lang_spa": {"es": "Español", "en": "Spanish"},
    "lang_lat": {"es": "Latín", "en": "Latin"},

    # --- App windows: titles, headers ---
    "app_title_basic": {"es": "PDF a Markdown — Griego clásico", "en": "PDF to Markdown — Classical Greek"},
    "app_title_tables": {"es": "PDF a Markdown — Griego clásico (con tablas)", "en": "PDF to Markdown — Classical Greek (with tables)"},
    "app_header_basic": {"es": "📜  PDF a Markdown", "en": "📜  PDF to Markdown"},
    "app_header_tables": {"es": "📊  PDF a Markdown  ·  con tablas", "en": "📊  PDF to Markdown  ·  with tables"},
    "app_subtitle_basic": {
        "es": "Griego clásico y otros idiomas académicos, con corrección automática de OCR.",
        "en": "Classical Greek and other academic languages, with automatic OCR correction.",
    },
    "app_subtitle_tables": {
        "es": "Extrae también las tablas del documento con detección estricta:\n"
              "solo se extraen tablas con pie explícito y rejilla real (evita falsos positivos).",
        "en": "Also extracts the document's tables with strict detection:\n"
              "only tables with an explicit caption and a real grid are extracted (avoids false positives).",
    },

    # --- Form labels ---
    "label_select_pdf": {"es": "1.  Selecciona el PDF", "en": "1.  Select the PDF"},
    "label_output_folder": {"es": "2.  Carpeta donde guardar el .md", "en": "2.  Folder to save the .md in"},
    "filetype_pdf": {"es": "Archivos PDF", "en": "PDF files"},
    "browse_button": {"es": "Examinar...", "en": "Browse..."},
    "languages_label": {"es": "Idiomas del documento (marca todos los que aparezcan)", "en": "Document languages (check all that appear)"},
    "page_range_checkbox": {"es": "Convertir solo un rango de páginas", "en": "Convert only a range of pages"},
    "page_range_from": {"es": "Desde página:", "en": "From page:"},
    "page_range_to": {"es": "Hasta página:", "en": "To page:"},

    # --- Buttons ---
    "convert_button_basic": {"es": "✨  Convertir a Markdown", "en": "✨  Convert to Markdown"},
    "convert_button_tables": {"es": "✨  Convertir a Markdown (con tablas)", "en": "✨  Convert to Markdown (with tables)"},
    "converting_button": {"es": "Convirtiendo...", "en": "Converting..."},
    "open_file_button": {"es": "📄  Abrir el .md generado", "en": "📄  Open the generated .md"},
    "open_folder_button": {"es": "📂  Abrir carpeta", "en": "📂  Open folder"},

    # --- Log / conversion messages ---
    "log_title": {"es": "Registro de la conversión", "en": "Conversion log"},
    "log_checking_deps": {"es": "Comprobando dependencias externas (Tesseract, Poppler)...", "en": "Checking external dependencies (Tesseract, Poppler)..."},
    "log_missing_deps_error": {
        "es": "Faltan programas externos necesarios (ver avisos arriba). "
              "Instálalos y vuelve a intentarlo; esta aplicación no puede "
              "convertir el PDF sin ellos.",
        "en": "Required external programs are missing (see warnings above). "
              "Install them and try again; this application cannot "
              "convert the PDF without them.",
    },
    "log_converting_to_images": {"es": "Convirtiendo PDF a imágenes...", "en": "Converting PDF to images..."},
    "log_analyzing_pdf_type": {"es": "Analizando tipo de PDF (digital / escaneado)...", "en": "Analyzing PDF type (digital / scanned)..."},
    "log_pdf_type_detected": {"es": "Tipo detectado: {pdf_type}.", "en": "Type detected: {pdf_type}."},
    "log_searching_tables": {"es": "Buscando tablas (modo estricto)...", "en": "Searching for tables (strict mode)..."},
    "log_no_tables_found": {
        "es": "No se ha detectado ninguna tabla que cumpla los criterios "
              "estrictos (pie de tabla + rejilla de al menos 3x2 celdas "
              "con contenido). Si esperabas encontrar alguna, revisa que "
              "tenga un pie del tipo 'Table 1', 'Tabla 1', etc.",
        "en": "No table meeting the strict criteria was detected "
              "(table caption + a grid of at least 3x2 cells with "
              "content). If you expected to find one, check that it "
              "has a caption like 'Table 1', 'Tabla 1', etc.",
    },
    "log_processing_ocr": {"es": "Procesando {n} página(s) con OCR...", "en": "Processing {n} page(s) with OCR..."},
    "log_page_processing": {"es": "  Página {n}...", "en": "  Page {n}..."},
    "output_page_separator": {"es": "--- Página {n} ---", "en": "--- Page {n} ---"},
    "log_conversion_cancelled": {"es": "Conversión cancelada por el usuario.", "en": "Conversion cancelled by the user."},
    "log_conversion_done": {"es": "\n✅ Conversión terminada.\nArchivo guardado en:\n{path}", "en": "\n✅ Conversion finished.\nFile saved to:\n{path}"},
    "log_error_header": {"es": "\n❌ Ha ocurrido un error:\n{error}", "en": "\n❌ An error occurred:\n{error}"},
    "output_suffix_tables": {"es": "_tablas", "en": "_tables"},

    # --- Inline validation warnings ---
    "warn_select_pdf_first": {"es": "⚠ Selecciona primero un archivo PDF.", "en": "⚠ Select a PDF file first."},
    "warn_pdf_not_found": {"es": "⚠ El archivo PDF seleccionado no existe.", "en": "⚠ The selected PDF file does not exist."},
    "warn_set_output_folder": {"es": "⚠ Indica una carpeta de salida.", "en": "⚠ Specify an output folder."},
    "warn_select_language": {"es": "⚠ Marca al menos un idioma antes de convertir.", "en": "⚠ Check at least one language before converting."},
    "warn_invalid_page_range": {
        "es": "⚠ El rango de páginas no es válido (revisa 'Desde' y 'Hasta').",
        "en": "⚠ The page range is not valid (check 'From' and 'To').",
    },

    # --- Table summary panel (tables app only) ---
    "tables_summary_none_yet": {"es": "📋  Todavía no se ha buscado ninguna tabla.", "en": "📋  No table search has been done yet."},
    "tables_summary_searching": {"es": "🔍  Buscando tablas...", "en": "🔍  Searching for tables..."},
    "tables_summary_zero": {
        "es": "📋  0 tablas encontradas (con los criterios estrictos de detección).",
        "en": "📋  0 tables found (under the strict detection criteria).",
    },
    "tables_summary_found": {
        "es": "📋  {total} tabla(s) encontrada(s) en la(s) página(s): {pages}",
        "en": "📋  {total} table(s) found on page(s): {pages}",
    },

    # --- Dependency dialog (config.py + gui_common.py) ---
    "dep_dialog_title": {"es": "Faltan programas necesarios", "en": "Required programs are missing"},
    "dep_dialog_header": {"es": "⚠️  Faltan programas externos", "en": "⚠️  External programs are missing"},
    "dep_close_button": {"es": "Cerrar", "en": "Close"},
    "dep_install_button_mac_auto": {"es": "🍺  Instalar automáticamente", "en": "🍺  Install automatically"},
    "dep_install_button_mac_homebrew": {"es": "🍺  Instalar Homebrew y continuar", "en": "🍺  Install Homebrew and continue"},
    "dep_install_button_win_auto": {"es": "🪟  Instalar automáticamente", "en": "🪟  Install automatically"},
    "dep_installing_button": {"es": "Instalando...", "en": "Installing..."},
    "dep_retry_install": {"es": "Reintentar instalación", "en": "Retry installation"},
    "dep_everything_ready": {"es": "Todo listo. Continuando con la conversión...", "en": "Everything is ready. Continuing with the conversion..."},

    # --- config.py: dependency check messages ---
    "dep_tesseract_not_found": {
        "es": "No se encuentra Tesseract OCR (ruta probada: '{path}'). {instructions}",
        "en": "Tesseract OCR was not found (path tried: '{path}'). {instructions}",
    },
    "dep_poppler_not_found": {
        "es": "No se encuentra Poppler (necesario para leer el PDF). {instructions}",
        "en": "Poppler was not found (needed to read the PDF). {instructions}",
    },
    "dep_tessdata_missing": {
        "es": "Faltan paquetes de idioma de Tesseract: {langs}. Sin ellos, el OCR en esos idiomas fallará al convertir.",
        "en": "Tesseract language packs are missing: {langs}. Without them, OCR in those languages will fail when converting.",
    },
    "instr_tesseract_mac": {"es": "Instálalo con Homebrew: brew install tesseract tesseract-lang", "en": "Install it with Homebrew: brew install tesseract tesseract-lang"},
    "instr_tesseract_win": {
        "es": "Instálalo desde https://github.com/UB-Mannheim/tesseract/wiki y define la variable de entorno TESSERACT_CMD con la ruta al .exe",
        "en": "Install it from https://github.com/UB-Mannheim/tesseract/wiki and set the TESSERACT_CMD environment variable to the .exe path",
    },
    "instr_tesseract_linux": {
        "es": "Instálalo con el gestor de paquetes de tu sistema (p. ej. apt install tesseract-ocr)",
        "en": "Install it with your system's package manager (e.g. apt install tesseract-ocr)",
    },
    "instr_poppler_mac": {"es": "Instálalo con Homebrew: brew install poppler", "en": "Install it with Homebrew: brew install poppler"},
    "instr_poppler_win": {
        "es": "Descárgalo de https://github.com/oschwartz10612/poppler-windows/releases y define la variable de entorno POPPLER_PATH con la carpeta 'bin' descomprimida",
        "en": "Download it from https://github.com/oschwartz10612/poppler-windows/releases and set the POPPLER_PATH environment variable to the unzipped 'bin' folder",
    },
    "instr_poppler_linux": {
        "es": "Instálalo con el gestor de paquetes de tu sistema (p. ej. apt install poppler-utils)",
        "en": "Install it with your system's package manager (e.g. apt install poppler-utils)",
    },

    # --- config.py: Homebrew (macOS) install flow ---
    "homebrew_macos_only": {"es": "La instalación automática de Homebrew solo está disponible en macOS.", "en": "Automatic Homebrew installation is only available on macOS."},
    "homebrew_need_admin": {"es": "Se necesita permiso de administrador para preparar Homebrew.", "en": "Administrator permission is needed to prepare Homebrew."},
    "homebrew_password_prompt": {"es": "macOS te pedirá tu contraseña en un momento (diálogo del sistema).", "en": "macOS will ask for your password in a moment (system dialog)."},
    "homebrew_admin_request_failed": {"es": "No se pudo pedir permisos de administrador: {exc}", "en": "Could not request administrator permissions: {exc}"},
    "homebrew_install_cancelled": {"es": "Instalación cancelada (se rechazó la solicitud de contraseña).", "en": "Installation cancelled (the password request was declined)."},
    "homebrew_prep_failed": {"es": "No se pudo preparar Homebrew: {stderr}", "en": "Could not prepare Homebrew: {stderr}"},
    "homebrew_permissions_granted": {"es": "Permisos concedidos.", "en": "Permissions granted."},
    "homebrew_downloading": {"es": "Descargando e instalando Homebrew (puede tardar varios minutos)...", "en": "Downloading and installing Homebrew (this can take several minutes)..."},
    "homebrew_install_error": {"es": "Error al instalar Homebrew: {exc}", "en": "Error installing Homebrew: {exc}"},
    "homebrew_install_failed_code": {"es": "El instalador de Homebrew terminó con un error (código {code}).", "en": "The Homebrew installer exited with an error (code {code})."},
    "homebrew_not_found_after_install": {
        "es": "Homebrew parece haberse instalado, pero no se encuentra su ejecutable. Cierra y vuelve a abrir esta aplicación.",
        "en": "Homebrew appears to have been installed, but its executable cannot be found. Close and reopen this application.",
    },
    "homebrew_installed_ok": {"es": "Homebrew instalado correctamente.", "en": "Homebrew installed successfully."},
    "homebrew_not_found": {"es": "No se ha encontrado Homebrew en este equipo.", "en": "Homebrew was not found on this computer."},
    "nothing_to_install": {"es": "No hay nada que instalar.", "en": "There is nothing to install."},
    "homebrew_packages_install_error": {"es": "Error al ejecutar Homebrew: {exc}", "en": "Error running Homebrew: {exc}"},
    "install_ok": {"es": "Instalación completada correctamente.", "en": "Installation completed successfully."},
    "homebrew_install_failed": {"es": "'brew install' terminó con un error (código {code}).", "en": "'brew install' exited with an error (code {code})."},
    "nothing_else_to_install": {"es": "No faltaba nada más por instalar.", "en": "Nothing else needed to be installed."},

    # --- config.py: winget (Windows) install flow ---
    "winget_not_found": {"es": "No se ha encontrado winget en este equipo.", "en": "winget was not found on this computer."},
    "winget_no_user_scope_retry": {
        "es": "⚠ {package} no tiene instalador para 'solo mi usuario'; reintentando para todo el equipo (puede pedir permiso de administrador)...",
        "en": "⚠ {package} has no 'current user only' installer; retrying for the whole machine (may ask for administrator permission)...",
    },
    "winget_already_present": {"es": "✅ {package} ya estaba instalado y disponible, se continúa.", "en": "✅ {package} was already installed and available, continuing."},
    "winget_package_failed_code": {"es": "⚠ {package} terminó con código {code}.", "en": "⚠ {package} exited with code {code}."},
    "winget_install_error": {"es": "⚠ Error instalando {package}: {exc}", "en": "⚠ Error installing {package}: {exc}"},
    "winget_some_failed": {"es": "Alguno de los programas no se pudo instalar (revisa el registro de arriba).", "en": "Some of the programs could not be installed (check the log above)."},

    # --- DependencyDialog: install progress lines ---
    "installing_with_homebrew": {"es": "Instalando con Homebrew: {packages}", "en": "Installing with Homebrew: {packages}"},
    "installing_with_winget": {"es": "Instalando con winget: {packages}", "en": "Installing with winget: {packages}"},
    "installing_package": {"es": "Instalando {package}...", "en": "Installing {package}..."},
    "may_take_minutes": {"es": "Puede tardar varios minutos. No cierres esta ventana.\n", "en": "This can take several minutes. Do not close this window.\n"},

    # --- config.py: Tesseract language pack download (Windows only) ---
    "tessdata_checking": {"es": "Comprobando paquetes de idioma de Tesseract...", "en": "Checking Tesseract language packs..."},
    "tessdata_downloading": {"es": "Descargando paquete de idioma: {lang}...", "en": "Downloading language pack: {lang}..."},
    "tessdata_download_error": {"es": "Error descargando el paquete de idioma '{lang}': {exc}", "en": "Error downloading the '{lang}' language pack: {exc}"},
    "tessdata_dir_not_found": {
        "es": "No se ha encontrado la carpeta 'tessdata' de Tesseract; no se pueden instalar paquetes de idioma.",
        "en": "Tesseract's 'tessdata' folder was not found; language packs cannot be installed.",
    },
    "tessdata_need_admin": {
        "es": "Se necesita permiso de administrador para copiar los paquetes de idioma a Tesseract.",
        "en": "Administrator permission is needed to copy the language packs into Tesseract.",
    },
    "tessdata_copy_failed": {"es": "No se pudieron copiar los paquetes de idioma: {exc}", "en": "Could not copy the language packs: {exc}"},
    "tessdata_install_ok": {"es": "Paquetes de idioma instalados correctamente.", "en": "Language packs installed successfully."},
}


def _(key: str, **kwargs: object) -> str:
    """Returns the translated string for `key` in the current language,
    formatted with any keyword arguments given."""
    try:
        template = STRINGS[key][_LANG]
    except KeyError:
        # Missing translation: fail loudly during development rather than
        # silently showing a raw key to the user.
        raise KeyError(f"No translation for key {key!r} (lang={_LANG!r})") from None
    return template.format(**kwargs) if kwargs else template
