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

Digital PDFs: by default, pages that already contain a usable text layer
are read directly (much more accurate than OCR for Greek); only scanned
pages, or pages with a broken text layer, are OCR'd. Use --force-ocr to
OCR every page.

The resulting .md is saved in the output folder and opened automatically
on Windows (use --no-open to disable this).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pdfplumber
import pytesseract
from pdf2image import convert_from_path

import config  # noqa: F401  (applies TESSERACT_CMD on import)
import ocr_postprocess
import text_layer
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
        "--force-ocr", action="store_true",
        help="OCR every page, even if the PDF has a usable text layer.",
    )
    parser.add_argument(
        "--corpus-rules", action="store_true",
        help="Also apply the corrections learned from the author's own corpus "
             "(Dodona lamellae and related literature). Off by default; can also "
             "be enabled with the environment variable PDF2MD_CORPUS_RULES=1.",
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
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as exc:  # Not critical: the file is already saved.
        print(f"[warning] Could not open the file automatically: {exc}")


def main() -> None:
    args = build_parser().parse_args()
    if args.corpus_rules:
        # Read by every fix_text() call, including the table cells.
        os.environ[ocr_postprocess.CORPUS_RULES_ENV] = "1"
    requested_languages = args.lang.split("+")
    warnings = config.check_external_dependencies(languages=requested_languages)
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
    with pdfplumber.open(str(args.pdf)) as pdf:
        total_pages = len(pdf.pages)
    if args.pages:
        if args.pages[0] > total_pages:
            print(
                f"[error] --pages starts at page {args.pages[0]}, but the PDF "
                f"only has {total_pages} page(s).",
                file=sys.stderr,
            )
            sys.exit(1)
        first_page, last_page = args.pages[0], min(args.pages[1], total_pages)
        suffix = f"_pp{args.pages[0]}-{args.pages[1]}"
    else:
        first_page, last_page = 1, total_pages

    tables_suffix = "_tables" if args.tables else ""
    output_path = args.output_dir / f"{args.pdf.stem}{suffix}{tables_suffix}.md"

    text_pages: dict[int, str] = {}
    if not args.force_ocr:
        text_pages = text_layer.extract_pages(str(args.pdf), first_page, last_page)
        print(f"Text layer used for {len(text_pages)} of {last_page - first_page + 1} page(s).")

    def rasterize(first: int, last: int) -> list:
        try:
            return convert_from_path(str(args.pdf), first_page=first, last_page=last, **convert_kwargs)
        except Exception as exc:
            print(
                f"[error] Failed to convert the PDF to images. Check that Poppler "
                f"is installed and accessible (see config.py). Detail: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Tables need every page image up front; otherwise pages are rasterized
    # one at a time, only when OCR is actually required (keeps RAM flat on big books).
    images: dict[int, object] = {}
    tables_by_page: dict[int, list[str]] = {}
    if args.tables:
        from pdf_table_extractor import extract_tables, detect_pdf_type, insert_tables_into_text

        print("Converting PDF to images...")
        all_images = rasterize(first_page, last_page)
        images = {first_page + i: img for i, img in enumerate(all_images)}
        print("Extracting tables...")
        pdf_type = detect_pdf_type(str(args.pdf))
        tables_by_page = extract_tables(
            str(args.pdf), pdf_type=pdf_type, images=all_images, lang=args.lang,
            apply_postprocessing=True,
        )

        insert_tables = insert_tables_into_text

    print(f"Processing {last_page - first_page + 1} page(s)...")
    full_text = ""
    for page_number in range(first_page, last_page + 1):
        if page_number in text_pages:
            print(f"  Page {page_number} (text layer)...")
            corrected_text = text_pages[page_number]
        else:
            print(f"  Page {page_number} (OCR)...")
            page = images[page_number] if page_number in images else rasterize(page_number, page_number)[0]
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
