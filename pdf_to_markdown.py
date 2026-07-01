"""
pdf_to_markdown.py
-------------------
Convierte un PDF (griego clásico + otros idiomas) a Markdown mediante OCR,
con corrección automática de errores típicos del OCR en griego.

Sustituye a los tres scripts originales (PDF_TO_MARKDOWN.py,
PDF_TO_MARKDOWN_PAGES.py, PDF_TO_MARKDOWN_TABLES.py), que compartían casi
todo el código. Ahora es un único script parametrizable por línea de
comandos.

Ejemplos de uso
----------------
Documento completo:

    python pdf_to_markdown.py "articulo.pdf" -o ./markdown --lang eng+grc

Solo un rango de páginas:

    python pdf_to_markdown.py "libro.pdf" -o ./markdown --lang grc+eng+fra \
        --paginas 79-130

Con extracción de tablas (detecta automáticamente si el PDF es digital o
escaneado):

    python pdf_to_markdown.py "articulo.pdf" -o ./markdown --tablas

El .md resultante se guarda en la carpeta de salida y se abre
automáticamente si estás en Windows (usa --no-abrir para desactivarlo).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

import config  # noqa: F401  (aplica TESSERACT_CMD al importarse)
from ocr_postprocess_mejorado import corregir_texto


def parse_rango_paginas(valor: str) -> tuple[int, int]:
    """Convierte 'INICIO-FIN' en (inicio, fin), validando el formato."""
    try:
        inicio_str, fin_str = valor.split("-")
        inicio, fin = int(inicio_str), int(fin_str)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--paginas debe tener el formato INICIO-FIN (ej. 79-130), recibido: {valor!r}"
        ) from exc
    if inicio < 1 or fin < inicio:
        raise argparse.ArgumentTypeError(
            f"Rango de páginas inválido: {valor!r} (INICIO debe ser >=1 y FIN >= INICIO)"
        )
    return inicio, fin


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convierte un PDF con griego clásico (y otros idiomas) a Markdown vía OCR.",
    )
    parser.add_argument("pdf", type=Path, help="Ruta al PDF de entrada.")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("./markdown"),
        help="Carpeta de salida para el .md (se crea si no existe). Por defecto: ./markdown",
    )
    parser.add_argument(
        "--lang", default="eng+grc",
        help="Idiomas para Tesseract, formato 'eng+grc' (ver `tesseract --list-langs`). "
             "Por defecto: eng+grc",
    )
    parser.add_argument(
        "--paginas", type=parse_rango_paginas, metavar="INICIO-FIN",
        help="Procesar solo un rango de páginas, ej. --paginas 79-130. "
             "Si se omite, se procesa el documento completo.",
    )
    parser.add_argument(
        "--tablas", action="store_true",
        help="Además del texto, extrae tablas (detecta automáticamente si el PDF "
             "es digital o escaneado) y las inserta junto a su caption.",
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="Resolución (ppp) para convertir el PDF a imágenes. Por defecto: 300.",
    )
    parser.add_argument(
        "--no-abrir", action="store_true",
        help="No abrir automáticamente el .md resultante al terminar.",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="No mostrar el detalle de correcciones de corregir_texto() por página.",
    )
    return parser


def abrir_archivo(ruta: Path) -> None:
    """Abre el archivo con la aplicación por defecto del sistema, si es posible."""
    try:
        if os.name == "nt":
            os.startfile(ruta)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{ruta}"')
        else:
            os.system(f'xdg-open "{ruta}"')
    except Exception as exc:  # No es crítico: el archivo ya está guardado.
        print(f"[aviso] No se pudo abrir el archivo automáticamente: {exc}")


def main() -> None:
    args = construir_parser().parse_args()
    config.verificar_dependencias_externas()

    if not args.pdf.is_file():
        print(f"[error] No se encuentra el PDF: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    sufijo = ""
    kwargs_convert = {"dpi": args.dpi, "poppler_path": config.POPPLER_PATH}
    if args.paginas:
        inicio, fin = args.paginas
        kwargs_convert["first_page"] = inicio
        kwargs_convert["last_page"] = fin
        sufijo = f"_pp{inicio}-{fin}"
    else:
        inicio = 1

    sufijo_tablas = "_tablas" if args.tablas else ""
    output_path = args.output_dir / f"{args.pdf.stem}{sufijo}{sufijo_tablas}.md"

    print("Convirtiendo PDF a imágenes...")
    try:
        pages = convert_from_path(str(args.pdf), **kwargs_convert)
    except Exception as exc:
        print(
            f"[error] Fallo al convertir el PDF a imágenes. Comprueba que Poppler "
            f"está instalado y accesible (ver config.py). Detalle: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    tablas_por_pagina: dict[int, list[str]] = {}
    if args.tablas:
        from pdf_table_extractor import extraer_tablas, detectar_tipo_pdf, CAPTION_RE

        print("Extrayendo tablas...")
        tipo_pdf = detectar_tipo_pdf(str(args.pdf))
        tablas_por_pagina = extraer_tablas(
            str(args.pdf), tipo=tipo_pdf, imagenes=pages, lang=args.lang,
            aplicar_postproc=True,
        )

        def insertar_tablas_junto_a_caption(texto: str, tablas_md: list[str]) -> str:
            """Inserta cada tabla markdown justo después de su caption en el texto OCR."""
            if not tablas_md:
                return texto
            matches = list(CAPTION_RE.finditer(texto))
            if not matches:
                return texto
            partes, prev_end = [], 0
            for i, m in enumerate(matches):
                partes.append(texto[prev_end:m.end()])
                if i < len(tablas_md):
                    partes.append(f"\n\n{tablas_md[i]}\n")
                prev_end = m.end()
            partes.append(texto[prev_end:])
            return "".join(partes)

    print(f"Procesando {len(pages)} páginas...")
    texto_completo = ""
    for i, page in enumerate(pages):
        num_pagina = inicio + i
        print(f"  Página {num_pagina}...")
        texto_bruto = pytesseract.image_to_string(page, lang=args.lang, config="--psm 3")
        texto_corregido = corregir_texto(texto_bruto, verbose=not args.quiet)
        if args.tablas and num_pagina in tablas_por_pagina:
            texto_corregido = insertar_tablas_junto_a_caption(
                texto_corregido, tablas_por_pagina[num_pagina]
            )
        texto_completo += f"\n\n--- Página {num_pagina} ---\n\n{texto_corregido}"

    output_path.write_text(texto_completo, encoding="utf-8")
    print(f"Listo. Archivo guardado en:\n{output_path}")

    if not args.no_abrir:
        abrir_archivo(output_path)


if __name__ == "__main__":
    main()
