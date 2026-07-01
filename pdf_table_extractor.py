"""
pdf_table_extractor.py
-----------------------
Table extraction for two types of PDF:
  - Digital (selectable text): pdfplumber detects the structure directly.
  - Scanned (image): OpenCV locates the cells, Tesseract reads them one by one.

Quick usage:
    from pdf_table_extractor import extract_tables, detect_pdf_type

    pdf_type = detect_pdf_type("article.pdf")            # "digital" or "scanned"
    tables = extract_tables("article.pdf", images)        # {page_num: [md, ...]}
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pdfplumber
import pytesseract
from PIL import Image

import config  # noqa: F401  (applies TESSERACT_CMD on import; avoids duplicating the path here)
from ocr_postprocess import fix_text

# Matches a cell that is only a number (with or without decimals). These
# cells must NOT go through the general fix_text() pipeline, because it
# includes a rule meant to remove stray page numbers (pattern
# "^\s*\d{1,4}\s*$") which, applied to a cell's content, would delete any
# purely numeric table data (ages, years, quantities...). That context
# (running page text vs. an isolated cell) is exactly the difference the
# rule cannot tell apart on its own.
_NUMBER_ONLY_CELL = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*$")


def _fix_cell(text: Optional[str]) -> str:
    """Applies fix_text() to a cell, unless it is an isolated number."""
    if not text:
        return ""
    if _NUMBER_ONLY_CELL.match(text):
        return text.strip()
    return fix_text(text)

# ---------------------------------------------------------------------------
# TABLE caption pattern (multilingual). A table is only searched for if the
# page contains one of these captions. Figure captions ("Figure", "Fig.",
# "Abb.", "Tav.") are deliberately excluded: a figure is not a table, and
# including them caused false positives (the extractor would try to read a
# table on pages that actually contained a map or a photograph).
# ---------------------------------------------------------------------------
CAPTION_RE = re.compile(
    r"^\s*(?:Table|Tab\.?|Tabla|Cuadro|Tableau)\s*\.?\s*\d+",
    re.IGNORECASE | re.MULTILINE,
)

# Figure caption pattern, kept separate in case it is needed in the future
# for a standalone figure extractor. Not used in this module.
CAPTION_RE_FIGURE = re.compile(
    r"^\s*(?:Figure|Fig\.?|Abbildung|Abb\.?|Tav\.?)\s*\.?\s*\d+",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Shared utility: list-of-lists → Markdown table
# ---------------------------------------------------------------------------

def _table_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    # Normalize cells
    rows = [[str(c or "").strip() for c in row] for row in rows]
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]

    widths = [max(len(r[c]) for r in rows) or 1 for c in range(ncols)]

    def _row_md(row: list[str]) -> str:
        return "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(row)) + " |"

    sep = "| " + " | ".join("-" * a for a in widths) + " |"
    return "\n".join([_row_md(rows[0]), sep] + [_row_md(r) for r in rows[1:]])


# ---------------------------------------------------------------------------
# Automatic PDF type detection
# ---------------------------------------------------------------------------

def detect_pdf_type(pdf_path: str, char_threshold: int = 80) -> str:
    """
    Reads the text of the first page with pdfplumber.
    If it gets at least `char_threshold` characters, the PDF is digital;
    otherwise, it is scanned (the pages are images).
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    pdf_type = "digital" if len(text.strip()) >= char_threshold else "scanned"
    print(f"[table_extractor] Detected type: {pdf_type}  "
          f"({len(text.strip())} characters on page 1)")
    return pdf_type


# ===========================================================================
# FLOW 1 — DIGITAL PDF (pdfplumber)
# ===========================================================================

def extract_tables_digital(
    pdf_path: str,
    pages: Optional[list[int]] = None,
    apply_postprocessing: bool = True,
) -> dict[int, list[str]]:
    """
    Extracts tables from a PDF with selectable text.

    Parameters
    ----------
    pdf_path             : path to the PDF.
    pages                : list of 0-based indices; None = whole document.
    apply_postprocessing : passes each cell through fix_text().

    Returns
    -------
    {page_num_1based: [markdown_table, ...]}
    """
    result: dict[int, list[str]] = {}

    # Explicit borders — the only active strategy (text-alignment detection
    # produced too many false positives in lists, bibliographies, and
    # column text).
    line_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 5,
        "join_tolerance": 3,
        "edge_min_length": 30,
        "min_words_vertical": 1,
        "min_words_horizontal": 1,
    }

    def _is_real_table(table: list) -> bool:
        """
        Discards structures that are not real tables. Criteria (all must
        be met):
          - At least 3 rows and at least 2 columns in the most common row.
          - >= 75% of rows have that same number of columns (was 60%; 60%
            let irregular boxes slip through).
          - >= 50% of cells have non-empty content (discards grids of
            detected lines over a mostly blank area, e.g. a page margin or
            a decorative box).
        """
        if not table or len(table) < 3:
            return False
        n_cols = [len(row) for row in table]
        if max(n_cols) < 2:
            return False
        mode_ncols = max(set(n_cols), key=n_cols.count)
        if mode_ncols < 2:
            return False
        consistency = sum(1 for n in n_cols if n == mode_ncols) / len(table)
        if consistency < 0.75:
            return False
        total_cells = sum(len(row) for row in table)
        non_empty_cells = sum(
            1 for row in table for c in row if c and str(c).strip()
        )
        return total_cells > 0 and (non_empty_cells / total_cells) >= 0.5

    with pdfplumber.open(pdf_path) as pdf:
        indices = list(pages) if pages is not None else list(range(len(pdf.pages)))

        # Pre-scan: pages with their own caption + the following page
        # (the caption may sit above the table, at the end of the previous page)
        has_table: set[int] = set()
        for i in indices:
            text = pdf.pages[i].extract_text() or ""
            if CAPTION_RE.search(text):
                has_table.add(i)        # caption on the same page
                has_table.add(i + 1)    # table may start on the next page

        for i in indices:
            if i not in has_table:
                continue

            page = pdf.pages[i]
            tables = page.extract_tables(table_settings=line_settings)

            markdown_tables = []
            for table in tables:
                if not _is_real_table(table):
                    continue
                if apply_postprocessing:
                    table = [
                        [_fix_cell(c) for c in row]
                        for row in table
                    ]
                md = _table_to_markdown(table)
                if md:
                    markdown_tables.append(md)

            if markdown_tables:
                page_number = i + 1
                result[page_number] = markdown_tables
                print(f"[table_extractor] Page {page_number}: {len(markdown_tables)} table(s) extracted")

    return result


# ===========================================================================
# FLOW 2 — SCANNED PDF (OpenCV + Tesseract)
# ===========================================================================

# ── 2a. Image pre-processing ─────────────────────────────────────────────

def _preprocess(img_gray: np.ndarray) -> np.ndarray:
    """Otsu binarization + speckle noise removal."""
    _, bin_inv = cv2.threshold(img_gray, 0, 255,
                               cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(bin_inv, cv2.MORPH_OPEN, kernel)
    return cv2.bitwise_not(cleaned)


# ── 2b. Table region detection ───────────────────────────────────────────

def _split_lines(img_gray: np.ndarray):
    """
    Returns (h_lines, v_lines) as binary masks.
    Large kernels (>= 1/4 of the dimension) so that only real table
    borders pass through, not underlines or short separators.
    """
    h, w = img_gray.shape
    _, binary = cv2.threshold(img_gray, 0, 255,
                               cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 4, 60), 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k_h)

    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 4, 60)))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k_v)

    return h_lines, v_lines


def _table_bbox(img_gray: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    """
    Returns (x, y, w, h) of the table, or None if there is no table.

    Strategy: a real table has intersections between horizontal and
    vertical lines. We look for the contour of the line area that
    contains the most intersections. We require:
      - At least 9 intersections (equivalent to a minimum 3x3 cell grid;
        previously 4 were accepted, i.e. a plain 2x2, which was too
        permissive and easy to confuse with a box or a logo with a frame).
      - The bbox area must be at least 2% of the full image, to discard
        small boxes (stamps, framed headers, icons) that are not data
        tables.
    """
    h_total, w_total = img_gray.shape
    h_lines, v_lines = _split_lines(img_gray)

    # Pixels where a horizontal line AND a vertical line coincide → intersections
    intersections = cv2.bitwise_and(h_lines, v_lines)
    if cv2.countNonZero(intersections) < 9:
        return None

    # A plain box/frame (with no internal lines) also has 2 horizontal
    # components (top + bottom border) and 2 vertical ones (left + right
    # border), so a ">= 2" threshold does not distinguish it from a real
    # table. The minimum accepted grid is 3 rows x 2 columns, which
    # requires 4 horizontal lines (borders + 2 internal dividers) and 3
    # vertical lines (borders + 1 internal divider); we require exactly
    # that as a minimum.
    n_h = cv2.connectedComponents(h_lines)[0] - 1  # -1: discounts the background
    n_v = cv2.connectedComponents(v_lines)[0] - 1
    if n_h < 4 or n_v < 3:
        return None

    # Full line mask; dilate to connect the borders of each cell
    mask = cv2.add(h_lines, v_lines)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.dilate(mask, k, iterations=3)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Pick the contour whose interior contains the most intersections
    best_bbox = None
    best_n = 0
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        n = cv2.countNonZero(intersections[y:y+ch, x:x+cw])
        if n > best_n:
            best_n = n
            best_bbox = (x, y, cw, ch)

    if best_bbox is None or best_n < 9:
        return None

    _, _, bw, bh = best_bbox
    area_rel = (bw * bh) / (w_total * h_total)
    if area_rel < 0.02:
        return None

    return best_bbox


# ── 2c. Cell detection and grouping ──────────────────────────────────────

def _line_positions(line_mask: np.ndarray, axis: str) -> list[int]:
    """
    Locates the position (center coordinate) of each table line within a
    binary mask of horizontal or vertical lines.

    Requires the line to cover at least 60% of the perpendicular dimension
    to be counted as a real grid line (a short noise stroke, or a loose
    underline, does not reach that threshold and is discarded).

    Parameters
    ----------
    axis : 'h' for horizontal lines (Y positions are returned),
           'v' for vertical lines (X positions are returned).
    """
    if axis == "h":
        profile = (line_mask > 0).sum(axis=1)  # number of line pixels per row
        perpendicular_dim = line_mask.shape[1]
    else:
        profile = (line_mask > 0).sum(axis=0)  # number of line pixels per column
        perpendicular_dim = line_mask.shape[0]

    threshold = perpendicular_dim * 0.6
    active = profile >= threshold

    positions = []
    in_run = False
    start = 0
    for i, val in enumerate(active):
        if val and not in_run:
            in_run, start = True, i
        elif not val and in_run:
            in_run = False
            positions.append((start + i - 1) // 2)
    if in_run:
        positions.append((start + len(active) - 1) // 2)

    return positions


def _detect_cells(roi: np.ndarray) -> list[tuple[int, int, int, int]]:
    """
    Reconstructs the table grid from the actual positions of the
    horizontal and vertical lines, and returns each cell as (x, y, w, h),
    ordered by row and then by column.

    This method (based on the line profile, not on contours) is more
    robust than locating "gaps" between lines via contours: it does not
    depend on the grid being perfectly closed at the crop's border pixels,
    which is a common source of failures with OpenCV when the table
    occupies the crop right up to its edge.
    """
    h, w = roi.shape
    h_lines, v_lines = _split_lines(roi)

    ys = _line_positions(h_lines, "h")
    xs = _line_positions(v_lines, "v")

    margin = 3    # avoids capturing the line pixels themselves in the cell crop
    min_side = 10  # cells narrower than this are considered noise, not data

    cells: list[tuple[int, int, int, int]] = []
    for i in range(len(ys) - 1):
        y1, y2 = ys[i], ys[i + 1]
        if (y2 - y1) < min_side:
            continue
        for j in range(len(xs) - 1):
            x1, x2 = xs[j], xs[j + 1]
            if (x2 - x1) < min_side:
                continue
            cx, cy = x1 + margin, y1 + margin
            cw, ch = max((x2 - x1) - 2 * margin, 1), max((y2 - y1) - 2 * margin, 1)
            cells.append((cx, cy, cw, ch))

    return cells


def _group_rows(cells: list[tuple], tolerance_pct: float = 0.025,
                roi_height: int = 100) -> list[list[tuple]]:
    """Groups cells into rows using a tolerance relative to the ROI height."""
    if not cells:
        return []
    tolerance = max(int(roi_height * tolerance_pct), 8)
    rows: list[list[tuple]] = []
    current_row = [cells[0]]
    y_ref = cells[0][1]

    for cell in cells[1:]:
        if abs(cell[1] - y_ref) <= tolerance:
            current_row.append(cell)
        else:
            rows.append(sorted(current_row, key=lambda c: c[0]))
            current_row = [cell]
            y_ref = cell[1]
    rows.append(sorted(current_row, key=lambda c: c[0]))
    return rows


def _is_valid_grid(rows: list[list]) -> bool:
    """
    Checks that the rows form a coherent grid. All must be met:
    - At least 3 rows and 2 columns (was 2 rows: a 2xN grid is too easy to
      produce from OCR noise or poorly detected lines).
    - >= 80% of rows have the same number of columns (was 70%).
    """
    if len(rows) < 3:
        return False
    n_cols = [len(r) for r in rows]
    if max(n_cols) < 2:
        return False
    mode_ncols = max(set(n_cols), key=n_cols.count)
    if mode_ncols < 2:
        return False
    return sum(1 for n in n_cols if n == mode_ncols) >= max(2, len(rows) * 0.8)


# ── 2d. Single-cell OCR ───────────────────────────────────────────────────

def _ocr_cell(crop: np.ndarray, lang: str) -> str:
    """OCR of a cell with PSM 7 (single line) or PSM 6 if multi-line."""
    height = crop.shape[0]
    # Padding so Tesseract does not cut off border characters
    padded = cv2.copyMakeBorder(crop, 6, 6, 6, 6,
                                cv2.BORDER_CONSTANT, value=255)
    pil_img = Image.fromarray(padded)

    psm = "7" if height < 60 else "6"
    tess_config = f"--psm {psm} -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(pil_img, lang=lang, config=tess_config)
    return text.strip()


# ── 2e. Full pipeline for one image ──────────────────────────────────────

def extract_table_from_image(
    pil_image: Image.Image,
    lang: str = "grc+eng",
    apply_postprocessing: bool = True,
    previous_page_text: Optional[str] = None,
    _page_text: Optional[str] = None,
) -> Optional[str]:
    """
    Detects and extracts the table from a PIL image (one scanned page).

    Returns the table in Markdown format, or None if no table is detected.
    `_page_text` allows reusing OCR that has already been performed
    externally.
    """
    # Step 0: check for a caption (on this page or the previous one).
    page_text = _page_text or pytesseract.image_to_string(
        pil_image, lang=lang, config="--psm 3"
    )
    has_caption = CAPTION_RE.search(page_text) or (
        previous_page_text and CAPTION_RE.search(previous_page_text)
    )
    if not has_caption:
        return None

    img_gray = np.array(pil_image.convert("L"))
    processed_img = _preprocess(img_gray)

    bbox = _table_bbox(processed_img)
    if bbox is None:
        return None

    x, y, w, h = bbox
    roi = processed_img[y:y+h, x:x+w]

    cells = _detect_cells(roi)
    if len(cells) < 6:  # was 4; the minimum valid grid is now 3 rows x 2 cols = 6
        return None

    rows = _group_rows(cells, roi_height=h)
    if not _is_valid_grid(rows):
        return None

    data: list[list[str]] = []
    for row in rows:
        row_texts = []
        for (cx, cy, cw, ch) in row:
            crop = roi[cy:cy+ch, cx:cx+cw]
            text = _ocr_cell(crop, lang=lang)
            if apply_postprocessing:
                text = _fix_cell(text)
            row_texts.append(text)
        data.append(row_texts)

    if not data:
        return None

    # Final check: if, after OCR, most cells are empty, what was detected
    # was probably not a real data table (it could have been a decorative
    # box or a framed figure), so it is discarded.
    total_cells = sum(len(r) for r in data)
    cells_with_text = sum(1 for r in data for c in r if c.strip())
    if total_cells == 0 or (cells_with_text / total_cells) < 0.5:
        return None

    return _table_to_markdown(data)


def extract_tables_scanned(
    images: list[Image.Image],
    lang: str = "grc+eng",
    apply_postprocessing: bool = True,
    first_page: int = 1,
) -> dict[int, list[str]]:
    """
    Extracts tables from a list of PIL images (already converted pages).

    Parameters
    ----------
    images                : pages as PIL.Image (from convert_from_path/bytes).
    lang                  : Tesseract languages, format 'grc+eng'.
    apply_postprocessing  : passes each cell through fix_text().
    first_page            : the real page number of images[0] (for reporting).

    Returns
    -------
    {page_num_1based: [markdown_table, ...]}
    """
    result: dict[int, list[str]] = {}
    previous_text: Optional[str] = None

    for i, img in enumerate(images):
        page_number = first_page + i

        # Quick OCR of this page (reused as previous_text for the next one)
        page_text = pytesseract.image_to_string(img, lang=lang, config="--psm 3")

        has_caption = CAPTION_RE.search(page_text) or (
            previous_text and CAPTION_RE.search(previous_text)
        )

        if has_caption:
            table_md = extract_table_from_image(
                img,
                lang=lang,
                apply_postprocessing=apply_postprocessing,
                previous_page_text=previous_text,
                _page_text=page_text,   # avoids repeating the OCR inside
            )
            if table_md:
                result[page_number] = [table_md]
                print(f"[table_extractor] Page {page_number}: table extracted "
                      f"({table_md.count(chr(10))+1} rows)")
            else:
                print(f"[table_extractor] Page {page_number}: caption without a visible table")
        else:
            print(f"[table_extractor] Page {page_number}: no caption, skipped")

        previous_text = page_text

    return result


# ===========================================================================
# MAIN ROUTER
# ===========================================================================

def extract_tables(
    pdf_path: str,
    pdf_type: str,
    images: Optional[list[Image.Image]] = None,
    lang: str = "grc+eng",
    apply_postprocessing: bool = True,
) -> dict[int, list[str]]:
    """
    Single entry point.

    Parameters
    ----------
    pdf_path              : path to the original PDF (always required).
    pdf_type               : "digital" (selectable text) or "scanned" (images).
    images                : pages as PIL.Image; required if pdf_type="scanned".
    lang                   : Tesseract languages (scanned flow only).
    apply_postprocessing   : applies fix_text() to each cell.

    Returns
    -------
    {page_num: [markdown_table, ...]}
    """
    if pdf_type not in ("digital", "scanned"):
        raise ValueError(f"pdf_type must be 'digital' or 'scanned', not {pdf_type!r}")

    if pdf_type == "digital":
        return extract_tables_digital(pdf_path,
                                       apply_postprocessing=apply_postprocessing)
    else:
        if images is None:
            raise ValueError(
                "For scanned PDFs pass 'images' "
                "(a list of PIL images obtained with convert_from_path)."
            )
        return extract_tables_scanned(images, lang=lang,
                                       apply_postprocessing=apply_postprocessing)


# ===========================================================================
# Inserting tables into the text (shared by pdf_to_markdown.py and the GUIs)
# ===========================================================================

def insert_tables_into_text(text: str, tables_md: list[str]) -> str:
    """
    Inserts each Markdown table right after the full LINE that contains
    its caption (not just after the number), so as not to split the table
    caption sentence in half (e.g. "Table 1. Sample data" should not end
    up cut between "Table 1" and ". Sample data").
    """
    if not tables_md:
        return text
    matches = list(CAPTION_RE.finditer(text))
    if not matches:
        return text

    parts, prev_end = [], 0
    for i, m in enumerate(matches):
        line_end = text.find("\n", m.end())
        line_end = len(text) if line_end == -1 else line_end
        parts.append(text[prev_end:line_end])
        if i < len(tables_md):
            parts.append(f"\n\n{tables_md[i]}\n")
        prev_end = line_end
    parts.append(text[prev_end:])
    return "".join(parts)


# ===========================================================================
# Result formatting for embedding into Markdown
# ===========================================================================

def tables_to_text(result: dict[int, list[str]]) -> str:
    """
    Converts the dict {page_num: [md, ...]} into a block of Markdown text
    ready to insert into the output document.
    """
    parts = []
    for page_num, tables in sorted(result.items()):
        for j, table in enumerate(tables, 1):
            title = f"### Table {j} — Page {page_num}"
            parts.append(f"{title}\n\n{table}")
    return "\n\n---\n\n".join(parts)
