# Quality Verification

This folder contains a quality verification module for the OCR pipeline,
adapted specifically to polytonic Greek. It complements the main
conversion pipeline by measuring how accurate a given OCR run is against
a manually corrected reference sample, rather than relying only on visual
inspection.

## Why a separate module

Generic PDF-to-Markdown quality checks (character counts, global text
similarity) are built with modern Latin-alphabet text in mind. Polytonic
Greek OCR noise behaves differently: it rarely drops entire letters, but
frequently loses or confuses breathings, accents, and the iota subscript.
A single global similarity score would penalize a text with correct
letters but faulty accentuation the same way it penalizes a text with
actually misrecognized letters. This module keeps those two failure modes
separate, so that a report can distinguish between them.

## Files

- `quality_verifier_greek.py`: core comparison logic. Given a reference
  text and an OCR text, it returns base-letter similarity, diacritic
  accuracy, and basic content counts (characters, words), each against
  its own configurable threshold.
- `batch_quality_check.py`: batch runner. Compares every OCR page against
  its matching reference page (by filename) and writes one JSON report
  per page, plus an aggregate `batch_summary.json`.
- `reference_pages/`: manually corrected transcriptions used as ground
  truth. Not generated automatically, built once and reused across runs.
- `reports/`: generated output (ignored by git, see below).

## Building the reference set

The reference sample does not need to cover the whole corpus, a
representative subset is usually enough to catch regressions. A practical
approach:

1. Pick 10 to 20 pages spanning different sources, print quality, and
   dialectal variants in the DVC corpus.
2. Run the current OCR pipeline on those pages to get a first draft.
3. Correct that draft by hand (breathings, accents, iota subscript, any
   misrecognized letters) using the original PDF as ground truth.
4. Save each corrected page in `reference_pages/` with the same filename
   used by the OCR output (for example, `page_001.md`).

Once this set exists, it should stay fixed. Comparing future pipeline
changes against the same reference pages is what makes results
comparable over time.

## Running the batch check

```bash
python batch_quality_check.py --ocr <ocr_folder> --reference reference_pages --output reports
```

Thresholds can be adjusted without touching the code:

```bash
python batch_quality_check.py --ocr <ocr_folder> --reference reference_pages --output reports --min-base-similarity 92 --min-diacritic-accuracy 65
```

## Git tracking

- Track: `quality_verifier_greek.py`, `batch_quality_check.py`,
  `reference_pages/`, this `README.md`.
- Do not track: `reports/`, since it is regenerated on every run. Add a
  `verification/reports/` entry to `.gitignore`.
