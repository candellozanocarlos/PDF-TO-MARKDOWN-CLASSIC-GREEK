#!/bin/bash
# Lanzador de PDF a Markdown (GUI básica).
# Doble clic para abrir la app usando el entorno virtual del proyecto.
# Si el entorno virtual no existe todavía, ejecuta primero setup_mac.sh.

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROYECTO"

if [ ! -x "venv/bin/python" ]; then
    echo "No se encuentra el entorno virtual (./venv)."
    echo "Ejecuta primero setup_mac.sh (doble clic o './setup_mac.sh' en Terminal)."
    read -p "Pulsa Enter para cerrar..."
    exit 1
fi

venv/bin/python PDF_a_Markdown_GUI.py

if [ $? -ne 0 ]; then
    echo ""
    echo "La aplicación se cerró con un error (ver arriba)."
    read -p "Pulsa Enter para cerrar esta ventana..."
fi
