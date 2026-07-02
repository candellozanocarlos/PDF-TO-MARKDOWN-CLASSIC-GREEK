#!/bin/bash
# setup_mac.sh
# ---------------------------------------------------------------------------
# Instalación automática en macOS para PDF-TO-MARKDOWN-CLASSIC-GREEK.
#
# Qué hace, en orden:
#   1. Comprueba que Homebrew está instalado (si no, avisa cómo instalarlo).
#   2. Instala Tesseract OCR (con los paquetes de idioma) y Poppler.
#   3. Instala Python 3.13 de Homebrew (el de las Command Line Tools de
#      Apple da problemas con las ventanas de la interfaz gráfica).
#   4. Instala python-tk@3.13 (necesario para que la interfaz no salga
#      en blanco).
#   5. Crea un entorno virtual (venv) dentro del proyecto e instala las
#      dependencias de requirements.txt en él.
#
# Uso: desde la carpeta del proyecto, en Terminal:
#   chmod +x setup_mac.sh
#   ./setup_mac.sh
# ---------------------------------------------------------------------------

set -e

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROYECTO"

echo "📂 Carpeta del proyecto: $PROYECTO"
echo ""

# --- 1. Homebrew ------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
    echo "❌ No se ha encontrado Homebrew."
    echo "   Instálalo primero desde https://brew.sh y vuelve a ejecutar este script."
    exit 1
fi
echo "✅ Homebrew encontrado en: $(command -v brew)"

# --- 2. Tesseract y Poppler ---------------------------------------------------
echo ""
echo "🔍 Comprobando Tesseract OCR..."
if ! brew list tesseract >/dev/null 2>&1; then
    echo "   Instalando tesseract y tesseract-lang (incluye griego, alemán, etc.)..."
    brew install tesseract tesseract-lang
else
    echo "✅ Tesseract ya está instalado."
fi

echo ""
echo "🔍 Comprobando Poppler..."
if ! brew list poppler >/dev/null 2>&1; then
    echo "   Instalando poppler..."
    brew install poppler
else
    echo "✅ Poppler ya está instalado."
fi

# --- 3. Python 3.13 de Homebrew ---------------------------------------------
echo ""
echo "🔍 Comprobando Python 3.13 de Homebrew..."
if ! brew list python@3.13 >/dev/null 2>&1; then
    echo "   Instalando python@3.13..."
    brew install python@3.13
else
    echo "✅ python@3.13 ya está instalado."
fi

PYTHON_BIN="$(brew --prefix)/bin/python3.13"
if [ ! -x "$PYTHON_BIN" ]; then
    echo "❌ No se ha encontrado $PYTHON_BIN tras la instalación."
    echo "   Revisa la salida de 'brew install python@3.13' más arriba."
    exit 1
fi
echo "✅ Usando Python de Homebrew: $PYTHON_BIN"

# --- 4. python-tk ------------------------------------------------------------
echo ""
echo "🔍 Comprobando python-tk@3.13 (necesario para la interfaz gráfica)..."
if ! brew list python-tk@3.13 >/dev/null 2>&1; then
    echo "   Instalando python-tk@3.13..."
    brew install python-tk@3.13
else
    echo "✅ python-tk@3.13 ya está instalado."
fi

# --- 5. Entorno virtual + dependencias ---------------------------------------
echo ""
if [ ! -d "venv" ]; then
    echo "🐍 Creando entorno virtual en ./venv ..."
    "$PYTHON_BIN" -m venv venv
else
    echo "✅ El entorno virtual ./venv ya existe."
fi

echo "📦 Instalando dependencias del proyecto en el entorno virtual..."
"$PROYECTO/venv/bin/python" -m pip install --upgrade pip >/dev/null
"$PROYECTO/venv/bin/python" -m pip install -r requirements.txt

echo ""
echo "🎉 Instalación completada."
echo ""
echo "   Ya puedes abrir la app haciendo doble clic en:"
echo "     - Abrir_PDF_a_Markdown.command"
echo "     - Abrir_PDF_a_Markdown_con_Tablas.command"
echo ""
echo "   (la primera vez, clic derecho -> Abrir, para saltar el aviso de macOS"
echo "    sobre desarrollador no identificado)"
