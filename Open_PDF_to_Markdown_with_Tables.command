#!/bin/bash
# Launcher for PDF to Markdown with Tables (English).
# Double-click to open the app using the project's virtual environment.
# If the virtual environment does not exist yet, run setup_mac.sh first.

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROYECTO"

if [ ! -x "venv/bin/python" ]; then
    echo "Virtual environment not found (./venv)."
    echo "Run setup_mac.sh first (double-click it, or './setup_mac.sh' in Terminal)."
    read -p "Press Enter to close..."
    exit 1
fi

venv/bin/python PDF_to_Markdown_with_Tables_GUI.py

if [ $? -ne 0 ]; then
    echo ""
    echo "The application closed with an error (see above)."
    read -p "Press Enter to close this window..."
fi
