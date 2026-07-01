"""
pdf_to_markdown.py
-------------------
Converts a PDF (classical Greek + other languages) to Markdown via OCR,
with automatic correction of typical Greek OCR errors.

Replaces the three original scripts (PDF_TO_MARKDOWN.py,
PDF_TO_MARKDOWN_PAGES.py, PDF_TO_MARKDOWN_TABLES.py), which shared almost
all of their code. It is now a single script configurable from the command
line.

Usage examples
---------------
Full document:

    python pdf_to_markdown.py "article.pdf" -o ./markdown --lang eng+grc

Only a page range:

    python pdf_to_markdown.py "book.pdf" -o ./markdown --lang grc+eng+fra \
        --pages 79-130

With table extraction (automatically detects whether the PDF is digital or
scanned):

    python pdf_to_markdown.py "article.pdf" -o ./markdown --tables

The resulting .md is saved in the output folder and opened automatically
on Windows (use --no-open to disable this).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

import config  # noqa: F401  (applies TESSERACT_CMD on import)
from ocr_postprocess import fix_text


def parse_page_range(value: str) -> tuple[int, int]:
    """Converts 'START-END' into (start, end), validating the format."""
    try:
        start_str, end_str = value.split("-")
        start, end = int(start_str), int(end_str)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--pages must use the format START-END (e.g. 79-130), got: {value!r}"
        ) from exc
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError(
            f"Invalid page range: {value!r} (START must be >=1 and END >= START)"
        )
    return start, end


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Converts a PDF with classical Greek (and other languages) to Markdown via OCR.",
    )
    parser.add_argument("pdf", type=Path, help="Path to the input PDF.")
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=Path("./markdown"),
        help="Output folder for the .md file (created if it does not exist). Default: ./markdown",
    )
    parser.add_argument(
        "--lang", default="eng+grc",
        help="Languages for Tesseract, format 'eng+grc' (see `tesseract --list-langs`). "
             "Default: eng+grc",
    )
    parser.add_argument(
        "--pages", type=parse_page_range, metavar="START-END",
        help="Process only a range of pages, e.g. --pages 79-130. "
             "If omitted, the full document is processed.",
    )
    parser.add_argument(
        "--tables", action="store_true",
        help="In addition to the text, extract tables (automatically detects "
             "whether the PDF is digital or scanned) and insert them next to their caption.",
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="Resolution (dpi) used to convert the PDF into images. Default: 300.",
    )
    parser.add_argument(
        "--no-open", action="store_true",
        help="Do not automatically open the resulting .md file when done.",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Do not show the per-page correction details from fix_text().",
    )
    return parser


def open_file(path: Path) -> None:
    """Opens the file with the system's default application, if possible."""
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as exc:  # Not critical: the file is already saved.
        print(f"[warning] Could not open the file automatically: {exc}")


def main() -> None:
    args = build_parser().parse_args()
    warnings = config.check_external_dependencies()
    for warning in warnings:
        print(f"[error] {warning}", file=sys.stderr)
    if warnings:
        print(
            "\nMissing required external programs. Install them and try again.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.pdf.is_file():
        print(f"[error] PDF not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    suffix = ""
    convert_kwargs = {"dpi": args.dpi, "poppler_path": config.POPPLER_PATH}
    if args.pages:
        start, end = args.pages
        convert_kwargs["first_page"] = start
        convert_kwargs["last_page"] = end
        suffix = f"_pp{start}-{end}"
        first_page = start
    else:
        first_page = 1

    tables_suffix = "_tables" if args.tables else ""
    output_path = args.output_dir / f"{args.pdf.stem}{suffix}{tables_suffix}.md"

    print("Converting PDF to images...")
    try:
        pages = convert_from_path(str(args.pdf), **convert_kwargs)
    except Exception as exc:
        print(
            f"[error] Failed to convert the PDF to images. Check that Poppler "
            f"is installed and accessible (see config.py). Detail: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    tables_by_page: dict[int, list[str]] = {}
    if args.tables:
        from pdf_table_extractor import extract_tables, detect_pdf_type, insert_tables_into_text

        print("Extracting tables...")
        pdf_type = detect_pdf_type(str(args.pdf))
        tables_by_page = extract_tables(
            str(args.pdf), pdf_type=pdf_type, images=pages, lang=args.lang,
            apply_postprocessing=True,
        )

        insert_tables = insert_tables_into_text

    print(f"Processing {len(pages)} page(s)...")
    full_text = ""
    for i, page in enumerate(pages):
        page_number = first_page + i
        print(f"  Page {page_number}...")
        raw_text = pytesseract.image_to_string(page, lang=args.lang, config="--psm 3")
        corrected_text = fix_text(raw_text, verbose=not args.quiet)
        if args.tables and page_number in tables_by_page:
            corrected_text = insert_tables(
                corrected_text, tables_by_page[page_number]
            )
        full_text += f"\n\n--- Page {page_number} ---\n\n{corrected_text}"

    output_path.write_text(full_text, encoding="utf-8")
    print(f"Done. File saved to:\n{output_path}")

    if not args.no_open:
        open_file(output_path)


if __name__ == "__main__":
    main()
