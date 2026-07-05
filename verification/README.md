# Quality Verification

This folder contains a quality verification module for the OCR pipeline,
adapted specifically to polytonic Greek. It complements the main
conversion pipeline by measuring how accurate a given OCR run is against
a manually corrected reference sample, rather than relying only on visual
inspection.

The pipeline targets two rather different kinds of source material:
epigraphic corpora (the Dodona DVC lamellae, single short inscriptions
per page) and academic articles or books (journal papers, book chapters,
with running prose, footnotes, and bibliography). Each kind has its own
implications for how the reference set should be built and which metric
in the report matters most, see "Choosing a reference strategy" below.

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
  text and an OCR text, it returns base-letter similarity (ordered),
  diacritic accuracy, order-independent word overlap, and basic content
  counts (characters, words), each against its own configurable
  threshold.
- `batch_quality_check.py`: batch runner. Compares every OCR page against
  its matching reference page (by filename) and writes one JSON report
  per page, plus an aggregate `batch_summary.json`.
- `reference_pages/`: manually corrected transcriptions used as ground
  truth. Not generated automatically, built once and reused across runs.
- `reports/`: generated output (ignored by git, see below).
- `fix_cardo_pua_greek.py`: helper for building reference text out of a
  `.docx` (an already-written article or book chapter), rather than
  transcribing an OCR draft by hand. Fixes legacy Cardo-font Private Use
  Area characters (epsilon/omicron with circumflex) and inlines
  footnote/endnote text at their citation mark, see below.

## Choosing a reference strategy

**Epigraphic corpus (DVC lamellae).** Each page is a short, self-
contained inscription. Build the reference by running the OCR once,
correcting the draft by hand against the original image, and saving it
under the same filename as the OCR output. Reading order is not an
issue here, a page's transcription is inherently short and linear, so
`base_letter_similarity_pct` and `diacritic_accuracy_pct` are reliable
on their own.

**Academic articles and books.** Here the reference text is usually
already available and correct, the article or chapter itself, so
`fix_cardo_pua_greek.py` can build the reference directly from the
`.docx` instead of correcting an OCR draft from scratch. The catch is
footnotes: a `.docx` stores footnote text separately from the body
(`word/footnotes.xml`, not `word/document.xml`), cited inline at a single
point, whereas a printed page (and therefore the OCR reading it) always
pushes footnote text down to the bottom of that page, after the rest of
the body text on it. `fix_cardo_pua_greek.py` reinserts each footnote at
its citation mark, which is closer to the truth than leaving it out or
appending every note in one block at the very end, but it still will not
match the OCR's reading order exactly whenever a footnote is cited
mid-page rather than at the page's last line.

This means that, for whole articles or book chapters, `word_overlap_pct`
(order-independent) is the metric to trust first. A low
`base_letter_similarity_pct` alongside a high `word_overlap_pct` usually
means the content matches but the reading order does not, not that the
OCR is misreading letters. Only treat `base_letter_similarity_pct` as
the primary signal once both texts are already known to follow the same
order, which in practice means single pages (as in the epigraphic
workflow above), not multi-page documents with footnotes reinserted out
of print order.

## Building the reference set

**For the epigraphic corpus:**

1. Pick 10 to 20 pages spanning different sources, print quality, and
   dialectal variants in the DVC corpus.
2. Run the current OCR pipeline on those pages to get a first draft.
3. Correct that draft by hand (breathings, accents, iota subscript, any
   misrecognized letters) using the original PDF as ground truth.
4. Save each corrected page in `reference_pages/` with the same filename
   used by the OCR output (for example, `page_001.md`).

**For an academic article or book chapter you already have as a `.docx`:**

1. Run the current OCR pipeline on the matching PDF to get `articulo.md`
   (or however the OCR names its output).
2. Build the reference straight from the source document:
   `python fix_cardo_pua_greek.py articulo.docx verification/reference_pages/articulo.md`
   (match the extension of the OCR output, not `.txt`, so
   `batch_quality_check.py` can pair the two files by filename).
3. Run the batch check and read `word_overlap_pct` first.

Once a reference set exists, it should stay fixed. Comparing future
pipeline changes against the same reference pages is what makes results
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
  `fix_cardo_pua_greek.py`, `reference_pages/`, this `README.md`.
- Do not track: `reports/`, since it is regenerated on every run. Add a
  `verification/reports/` entry to `.gitignore`.
