"""
tests/test_pdf_table_extractor.py
-----------------------------------
Tests for pdf_table_extractor.py: strict table detection, for both the
digital (pdfplumber) and scanned (OpenCV) flows.

Some tests reproduce the exact synthetic scenarios used during
development to catch two real regressions found along the way:
  - A contour-hierarchy bug that made _detect_cells() find zero cells on
    a clean-lined table (fixed by switching to line-position-based grid
    reconstruction).
  - fix_text()'s "remove standalone page number" rule deleting purely
    numeric table cells (fixed with a dedicated _fix_cell() wrapper).
"""

import cv2
import numpy as np
import pytest

import pdf_table_extractor as pte


# ---------------------------------------------------------------------------
# Synthetic image helpers
# ---------------------------------------------------------------------------

def make_real_table(rows=4, cols=3, cell_w=100, cell_h=60, margin=40):
    """A clean grayscale image of a ruled table with `rows` x `cols` cells."""
    w = cols * cell_w + 2 * margin
    h = rows * cell_h + 2 * margin
    img = np.full((h, w), 255, dtype=np.uint8)
    for i in range(rows + 1):
        y = margin + i * cell_h
        cv2.line(img, (margin, y), (w - margin, y), 0, 2)
    for j in range(cols + 1):
        x = margin + j * cell_w
        cv2.line(img, (x, margin), (x, h - margin), 0, 2)
    return img


def make_decorative_box():
    """A plain rectangle with no internal grid lines: must never be a table."""
    w, h = 300, 200
    img = np.full((h, w), 255, dtype=np.uint8)
    cv2.rectangle(img, (30, 30), (w - 30, h - 30), 0, 3)
    return img


# ---------------------------------------------------------------------------
# CAPTION_RE: tables vs. figures
# ---------------------------------------------------------------------------

class TestCaptionPattern:
    @pytest.mark.parametrize("caption", [
        "Table 1", "Table 1.", "Tab. 2", "Tabla 3", "Cuadro 4", "Tableau 5",
    ])
    def test_table_captions_match(self, caption):
        assert pte.CAPTION_RE.search(caption)

    @pytest.mark.parametrize("caption", [
        "Figure 1", "Fig. 2", "Abbildung 3", "Abb. 4", "Tav. 5",
    ])
    def test_figure_captions_do_not_match(self, caption):
        # Regression guard: figure captions must never trigger table
        # extraction (this was a real bug found during development).
        assert pte.CAPTION_RE.search(caption) is None


# ---------------------------------------------------------------------------
# Grid geometry: real tables vs. false positives
# ---------------------------------------------------------------------------

class TestGridDetection:
    def test_real_4x3_table_is_detected(self):
        img = make_real_table(rows=4, cols=3)
        proc = pte._preprocess(img)
        bbox = pte._table_bbox(proc)
        assert bbox is not None

        x, y, w, h = bbox
        roi = proc[y:y + h, x:x + w]
        cells = pte._detect_cells(roi)
        # Regression guard: an earlier contour-based implementation found
        # ZERO cells here even though the bbox was detected correctly.
        assert len(cells) == 12  # 4 rows x 3 cols

        rows = pte._group_rows(cells, roi_height=h)
        assert len(rows) == 4
        assert pte._is_valid_grid(rows)

    def test_larger_table_is_detected(self):
        img = make_real_table(rows=6, cols=4)
        proc = pte._preprocess(img)
        bbox = pte._table_bbox(proc)
        assert bbox is not None
        x, y, w, h = bbox
        roi = proc[y:y + h, x:x + w]
        cells = pte._detect_cells(roi)
        assert len(cells) == 24  # 6 rows x 4 cols

    def test_decorative_box_is_rejected(self):
        img = make_decorative_box()
        proc = pte._preprocess(img)
        assert pte._table_bbox(proc) is None

    def test_grid_too_small_is_rejected(self):
        # Minimum accepted grid is 3 rows x 2 cols; a 2x2 grid must fail.
        img = make_real_table(rows=2, cols=2)
        proc = pte._preprocess(img)
        assert pte._table_bbox(proc) is None

    def test_is_valid_grid_requires_at_least_three_rows(self):
        two_rows = [[(0, 0, 10, 10), (20, 0, 10, 10)],
                    [(0, 20, 10, 10), (20, 20, 10, 10)]]
        assert pte._is_valid_grid(two_rows) is False

    def test_is_valid_grid_accepts_consistent_rows(self):
        rows = [[(0, 0, 10, 10), (20, 0, 10, 10)],
                [(0, 20, 10, 10), (20, 20, 10, 10)],
                [(0, 40, 10, 10), (20, 40, 10, 10)]]
        assert pte._is_valid_grid(rows) is True


# ---------------------------------------------------------------------------
# _fix_cell(): numeric cells must survive post-processing
# ---------------------------------------------------------------------------

class TestFixCell:
    def test_pure_number_cell_is_kept_verbatim(self):
        # Regression guard: fix_text()'s "remove standalone page number"
        # rule used to delete numeric-only table cells such as ages.
        assert pte._fix_cell("30") == "30"

    def test_decimal_number_cell_is_kept(self):
        assert pte._fix_cell("3.14") == "3.14"

    def test_empty_cell_returns_empty_string(self):
        assert pte._fix_cell(None) == ""
        assert pte._fix_cell("") == ""

    def test_non_numeric_cell_still_goes_through_fix_text(self):
        assert pte._fix_cell("lingiistas") == "lingüistas"


# ---------------------------------------------------------------------------
# _table_to_markdown(): formatting
# ---------------------------------------------------------------------------

class TestTableToMarkdown:
    def test_basic_table_formatting(self):
        rows = [["Name", "Age"], ["Anna", "30"]]
        md = pte._table_to_markdown(rows)
        lines = md.splitlines()
        assert lines[0].startswith("| Name")
        assert lines[1].startswith("| ----")
        assert "Anna" in lines[2]

    def test_empty_table_returns_empty_string(self):
        assert pte._table_to_markdown([]) == ""


# ---------------------------------------------------------------------------
# insert_tables_into_text(): caption line must stay intact
# ---------------------------------------------------------------------------

class TestInsertTablesIntoText:
    def test_caption_sentence_is_not_split(self):
        # Regression guard: an earlier version inserted the table right
        # after the caption's number, splitting "Table 1. Sample data"
        # into "Table 1" ... "| table |" ... ". Sample data".
        text = "Intro text.\n\nTable 1. Sample data\n\nMore text after."
        result = pte.insert_tables_into_text(text, ["| a | b |\n| - | - |\n| 1 | 2 |"])
        assert "Table 1. Sample data" in result
        assert ". Sample data" not in result.split("Table 1. Sample data")[1][:5]

    def test_no_tables_returns_text_unchanged(self):
        text = "Table 1. Some caption"
        assert pte.insert_tables_into_text(text, []) == text

    def test_no_caption_returns_text_unchanged(self):
        text = "No captions here at all."
        assert pte.insert_tables_into_text(text, ["| a |\n| - |\n| 1 |"]) == text


# ---------------------------------------------------------------------------
# End-to-end digital-PDF flow (pdfplumber only, no external binaries needed)
# ---------------------------------------------------------------------------

class TestDigitalPdfEndToEnd:
    def test_detects_digital_type(self, sample_pdf_path):
        assert pte.detect_pdf_type(str(sample_pdf_path)) == "digital"

    def test_extracts_exactly_the_real_table(self, sample_pdf_path):
        result = pte.extract_tables_digital(str(sample_pdf_path))
        # The table lives on page 2 (1-based); pages 1 and 3 have no real
        # table (page 3 has only a figure caption).
        assert list(result.keys()) == [2]
        assert len(result[2]) == 1

    def test_table_content_is_correct(self, sample_pdf_path):
        result = pte.extract_tables_digital(str(sample_pdf_path))
        md = result[2][0]
        assert "Name" in md and "Age" in md and "City" in md
        assert "Anna" in md and "30" in md  # numeric cell must survive

    def test_figure_only_page_yields_no_table(self, sample_pdf_path):
        result = pte.extract_tables_digital(str(sample_pdf_path))
        assert 3 not in result

    def test_router_dispatches_to_digital_flow(self, sample_pdf_path):
        result = pte.extract_tables(str(sample_pdf_path), pdf_type="digital")
        assert 2 in result

    def test_router_rejects_invalid_type(self, sample_pdf_path):
        with pytest.raises(ValueError):
            pte.extract_tables(str(sample_pdf_path), pdf_type="not-a-type")

    def test_router_requires_images_for_scanned_type(self):
        with pytest.raises(ValueError):
            pte.extract_tables("irrelevant.pdf", pdf_type="scanned", images=None)
