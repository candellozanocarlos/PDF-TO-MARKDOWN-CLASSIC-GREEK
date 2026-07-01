"""
tests/test_pdf_to_markdown.py
-------------------------------
Tests for pdf_to_markdown.py: CLI argument parsing, and a full end-to-end
run against the sample fixture PDF (skipped automatically if Tesseract or
Poppler are not available on the machine running the tests).
"""

import argparse

import pytest

import pdf_to_markdown as ptm
from conftest import requires_poppler, requires_tesseract


class TestParsePageRange:
    def test_valid_range(self):
        assert ptm.parse_page_range("79-130") == (79, 130)

    def test_single_page_range(self):
        assert ptm.parse_page_range("5-5") == (5, 5)

    def test_missing_dash_raises(self):
        with pytest.raises(argparse.ArgumentTypeError):
            ptm.parse_page_range("79")

    def test_non_numeric_raises(self):
        with pytest.raises(argparse.ArgumentTypeError):
            ptm.parse_page_range("a-b")

    def test_end_before_start_raises(self):
        with pytest.raises(argparse.ArgumentTypeError):
            ptm.parse_page_range("130-79")

    def test_zero_start_raises(self):
        with pytest.raises(argparse.ArgumentTypeError):
            ptm.parse_page_range("0-10")


class TestArgumentParser:
    def test_requires_pdf_positional_argument(self):
        parser = ptm.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_defaults(self):
        parser = ptm.build_parser()
        args = parser.parse_args(["input.pdf"])
        assert args.lang == "eng+grc"
        assert args.dpi == 300
        assert args.tables is False
        assert args.no_open is False
        assert args.pages is None

    def test_tables_flag(self):
        parser = ptm.build_parser()
        args = parser.parse_args(["input.pdf", "--tables"])
        assert args.tables is True

    def test_pages_flag(self):
        parser = ptm.build_parser()
        args = parser.parse_args(["input.pdf", "--pages", "10-20"])
        assert args.pages == (10, 20)


@requires_tesseract
@requires_poppler
class TestEndToEnd:
    def test_full_conversion_produces_expected_output(self, sample_pdf_path, tmp_path, monkeypatch):
        output_dir = tmp_path / "markdown"
        monkeypatch.setattr(
            "sys.argv",
            [
                "pdf_to_markdown.py", str(sample_pdf_path),
                "-o", str(output_dir), "--lang", "eng",
                "--tables", "--no-open", "-q",
            ],
        )

        ptm.main()

        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) == 1

        content = output_files[0].read_text(encoding="utf-8")
        assert "--- Page 1 ---" in content
        assert "--- Page 2 ---" in content
        assert "--- Page 3 ---" in content
        assert "Table 1. Sample data" in content
        assert "Anna" in content and "30" in content

