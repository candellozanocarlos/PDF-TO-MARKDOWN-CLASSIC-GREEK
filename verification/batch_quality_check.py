"""
batch_quality_check.py

Integrates the polytonic Greek quality verifier (quality_verifier_greek.py)
into a batch workflow, designed to fit the logic of
PDF-TO-MARKDOWN-CLASSIC-GREEK: for each page processed by the OCR, the
result is compared against a manually corrected reference transcription,
and an individual JSON report is generated, plus an aggregate summary for
the whole batch.

Folder structure expected by this script (feel free to rename):

    input/
        ocr/            -> pages produced by your OCR (page_001.md, page_002.md, ...)
        reference/      -> manually corrected pages, with the same filename
    output/
        reports/        -> JSON reports are written here (created if missing)

Only pages whose filename matches in both folders are compared. Pages
without a reference are skipped and reported on the console, since there
is no point generating a score without a text to compare against.

Usage:

    python batch_quality_check.py --ocr input/ocr --reference input/reference --output output/reports
"""

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Dict, List

from quality_verifier_greek import verify_greek_conversion, GreekQualityThresholds


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def process_batch(
    ocr_folder: Path,
    reference_folder: Path,
    output_folder: Path,
    thresholds: GreekQualityThresholds,
) -> Dict:
    """
    Walks through the pages in the OCR folder, looks up their counterpart
    in the reference folder (by filename) and generates an individual
    report for each matching pair. Also returns an aggregate summary for
    the whole batch.
    """
    output_folder.mkdir(parents=True, exist_ok=True)

    ocr_files = sorted(ocr_folder.glob("*"))
    reports: List[Dict] = []
    skipped: List[str] = []

    for ocr_file in ocr_files:
        if not ocr_file.is_file():
            continue

        reference_file = reference_folder / ocr_file.name
        if not reference_file.exists():
            skipped.append(ocr_file.name)
            continue

        ocr_text = read_text(ocr_file)
        reference_text = read_text(reference_file)

        report = verify_greek_conversion(reference_text, ocr_text, thresholds)
        report["page"] = ocr_file.name

        report_path = output_folder / f"{ocr_file.stem}_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        reports.append(report)

    summary = build_summary(reports, skipped)

    summary_path = output_folder / "batch_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return summary


def build_summary(reports: List[Dict], skipped: List[str]) -> Dict:
    """
    Computes batch-wide averages (base-letter similarity, diacritic
    accuracy) and counts how many pages passed or failed verification.
    Gives an at-a-glance view of the overall state of a conversion batch,
    without having to open every individual report.
    """
    if not reports:
        return {
            "pages_evaluated": 0,
            "pages_skipped_no_reference": skipped,
            "mean_base_letter_similarity_pct": None,
            "mean_diacritic_accuracy_pct": None,
            "pages_passed": 0,
            "pages_with_errors": 0,
        }

    base_similarities = [r["metrics"]["base_letter_similarity_pct"] for r in reports]

    diacritic_accuracies = [
        r["metrics"]["diacritic_integrity"]["diacritic_accuracy_pct"]
        for r in reports
        if r["metrics"]["diacritic_integrity"]["diacritic_accuracy_pct"] is not None
    ]

    passed = sum(1 for r in reports if r["passed"])

    return {
        "pages_evaluated": len(reports),
        "pages_skipped_no_reference": skipped,
        "mean_base_letter_similarity_pct": round(mean(base_similarities), 2),
        "mean_diacritic_accuracy_pct": (
            round(mean(diacritic_accuracies), 2) if diacritic_accuracies else None
        ),
        "pages_passed": passed,
        "pages_with_errors": len(reports) - passed,
        "pages_with_warnings": sum(1 for r in reports if r["warnings"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verifies the quality of a batch of polytonic Greek OCR pages."
    )
    parser.add_argument("--ocr", required=True, type=Path, help="Folder with OCR pages")
    parser.add_argument(
        "--reference", required=True, type=Path, help="Folder with reference pages"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="Folder where reports are written"
    )
    parser.add_argument(
        "--min-base-similarity",
        type=float,
        default=90.0,
        help="Minimum base-letter similarity threshold (default: 90)",
    )
    parser.add_argument(
        "--min-diacritic-accuracy",
        type=float,
        default=70.0,
        help="Minimum diacritic accuracy threshold (default: 70)",
    )
    args = parser.parse_args()

    thresholds = GreekQualityThresholds(
        min_base_similarity_pct=args.min_base_similarity,
        min_diacritic_accuracy_pct=args.min_diacritic_accuracy,
    )

    summary = process_batch(args.ocr, args.reference, args.output, thresholds)

    print("Batch summary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
