"""
quality_verifier_greek.py

Draft of a quality verifier for OCR conversions of polytonic Greek
(PDF -> Markdown), inspired by the approach used in PDF-to-Markdown-Converter
(chachojrl), but adapted to a problem specific to this language: typical
OCR noise in polytonic Greek rarely drops whole letters, it mostly confuses
or removes breathings, accents, and iota subscripts. For that reason, this
draft splits the comparison into two independent layers:

    1. Base-letter similarity (ignoring diacritics entirely).
    2. Diacritic accuracy (only over the characters whose base letter
       already matches between reference and hypothesis).

This way, a text with correct letters but faulty accentuation does not
receive the same penalty as a text with misrecognized letters, a
distinction that a plain global Levenshtein distance cannot make.

A fourth, order-independent layer (word overlap) is also included. It
compares which words appear in both texts, regardless of position. This
matters because reference texts assembled from a Word document (with
footnotes reinserted near their citation mark) will not always follow
the exact reading order an OCR pass over the printed pages produces
(footnotes always end up at the bottom of the page, not mid-sentence).
Long-range reordering like this can derail a strict sequence-alignment
score even when the actual content matches well, so word overlap is a
useful cross-check whenever the two texts being compared are not
guaranteed to be in identical order (e.g. whole articles rather than
single, already order-matched pages).

Basic usage:

    from quality_verifier_greek import verify_greek_conversion

    report = verify_greek_conversion(reference_text, ocr_text)
    print(report)

No external dependencies required (uses unicodedata and difflib, both
part of the Python standard library).
"""

import unicodedata
import difflib
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional


# ---------------------------------------------------------------------------
# Unicode normalization helpers
# ---------------------------------------------------------------------------

def decompose(text: str) -> str:
    """Decomposes text into NFD form (base letter + separate diacritics)."""
    return unicodedata.normalize("NFD", text)


def strip_diacritics(text: str) -> str:
    """Returns the text with all diacritics removed (base letters only)."""
    decomposed = decompose(text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def extract_diacritics_per_base(text: str) -> List[Tuple[str, frozenset]]:
    """
    Walks through the text and returns a list of (base_char, marks) tuples,
    where 'marks' is the set of combining diacritics attached to that
    letter (smooth/rough breathing, acute accent, iota subscript, etc.).
    """
    decomposed = decompose(text)
    result: List[Tuple[str, frozenset]] = []
    current_base: Optional[str] = None
    current_marks: set = set()

    for ch in decomposed:
        if unicodedata.combining(ch):
            current_marks.add(ch)
        else:
            if current_base is not None:
                result.append((current_base, frozenset(current_marks)))
            current_base = ch
            current_marks = set()

    if current_base is not None:
        result.append((current_base, frozenset(current_marks)))

    return result


# ---------------------------------------------------------------------------
# Layer 1: base-letter similarity
# ---------------------------------------------------------------------------

def base_similarity(reference: str, hypothesis: str) -> float:
    """
    Similarity (0-100) between the two strings, comparing base letters
    only, with diacritics stripped. Uses difflib.SequenceMatcher, which
    gives a result equivalent in spirit to a Levenshtein ratio, without
    depending on the python-Levenshtein package.
    """
    ref_base = strip_diacritics(reference)
    hyp_base = strip_diacritics(hypothesis)
    ratio = difflib.SequenceMatcher(None, ref_base, hyp_base).ratio()
    return ratio * 100


# ---------------------------------------------------------------------------
# Layer 2: diacritic accuracy
# ---------------------------------------------------------------------------

def diacritic_score(reference: str, hypothesis: str) -> Dict:
    """
    Aligns the base letters of reference and hypothesis (using the same
    SequenceMatcher logic) and, only over the stretches where the base
    letter matches exactly, checks whether the set of diacritics also
    matches. This is the key figure for knowing whether the OCR is
    dropping breathings or accents, independently of whether it gets the
    letters right.
    """
    ref_pairs = extract_diacritics_per_base(reference)
    hyp_pairs = extract_diacritics_per_base(hypothesis)
    ref_bases = [p[0] for p in ref_pairs]
    hyp_bases = [p[0] for p in hyp_pairs]

    matcher = difflib.SequenceMatcher(None, ref_bases, hyp_bases)
    matched_chars = 0
    exact_diacritic_matches = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                matched_chars += 1
                ref_marks = ref_pairs[i1 + offset][1]
                hyp_marks = hyp_pairs[j1 + offset][1]
                if ref_marks == hyp_marks:
                    exact_diacritic_matches += 1

    if matched_chars == 0:
        return {"matched_base_chars": 0, "diacritic_accuracy_pct": None}

    accuracy = (exact_diacritic_matches / matched_chars) * 100
    return {
        "matched_base_chars": matched_chars,
        "diacritic_accuracy_pct": round(accuracy, 2),
    }


# ---------------------------------------------------------------------------
# Layer 3: content counts (same idea as the original project)
# ---------------------------------------------------------------------------

def content_counts(reference: str, hypothesis: str) -> Dict:
    """Percentage differences in character and word counts between both texts."""
    ref_chars, hyp_chars = len(reference), len(hypothesis)
    char_diff = abs(ref_chars - hyp_chars) / max(ref_chars, 1) * 100

    ref_words, hyp_words = len(reference.split()), len(hypothesis.split())
    word_diff = abs(ref_words - hyp_words) / max(ref_words, 1) * 100

    return {
        "character_count_diff_pct": round(char_diff, 2),
        "word_count_diff_pct": round(word_diff, 2),
    }


# ---------------------------------------------------------------------------
# Layer 4: order-independent word overlap
# ---------------------------------------------------------------------------

def word_overlap(reference: str, hypothesis: str) -> float:
    """
    Dice coefficient (0-100) between the two texts' word multisets, with
    diacritics stripped and case ignored. Unlike base_similarity, this
    layer does not care where a word sits in the text, only whether it
    appears in both, so long-range reordering (e.g. a footnote reinserted
    near its citation mark instead of at the bottom of its printed page)
    does not by itself lower the score.
    """
    ref_words = strip_diacritics(reference).lower().split()
    hyp_words = strip_diacritics(hypothesis).lower().split()

    ref_counts = Counter(ref_words)
    hyp_counts = Counter(hyp_words)

    shared = sum((ref_counts & hyp_counts).values())
    total = sum(ref_counts.values()) + sum(hyp_counts.values())

    if total == 0:
        return 100.0

    return (2 * shared / total) * 100


# ---------------------------------------------------------------------------
# Configurable thresholds
# ---------------------------------------------------------------------------

@dataclass
class GreekQualityThresholds:
    max_char_diff_pct: float = 5.0
    max_word_diff_pct: float = 5.0
    min_base_similarity_pct: float = 90.0
    min_diacritic_accuracy_pct: float = 70.0  # deliberately more lenient
    min_word_overlap_pct: float = 85.0


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def verify_greek_conversion(
    reference: str,
    hypothesis: str,
    thresholds: Optional[GreekQualityThresholds] = None,
) -> Dict:
    """
    Compares a reference text (e.g. a manually reviewed transcription)
    with the OCR output, and returns a report with the same general shape
    as the one used by PDF-to-Markdown-Converter, but with the two layers
    for base letters and diacritics kept separate.
    """
    thresholds = thresholds or GreekQualityThresholds()

    content = content_counts(reference, hypothesis)
    base_sim = base_similarity(reference, hypothesis)
    diacritics = diacritic_score(reference, hypothesis)
    overlap = word_overlap(reference, hypothesis)

    warnings: List[str] = []
    errors: List[str] = []

    if content["character_count_diff_pct"] > thresholds.max_char_diff_pct:
        warnings.append(
            f"Character count differs by {content['character_count_diff_pct']}%, "
            f"above the threshold ({thresholds.max_char_diff_pct}%)."
        )

    if content["word_count_diff_pct"] > thresholds.max_word_diff_pct:
        warnings.append(
            f"Word count differs by {content['word_count_diff_pct']}%, "
            f"above the threshold ({thresholds.max_word_diff_pct}%)."
        )

    if base_sim < thresholds.min_base_similarity_pct:
        errors.append(
            f"Base-letter similarity is {round(base_sim, 2)}%, "
            f"below the threshold ({thresholds.min_base_similarity_pct}%). "
            "This indicates misrecognized letters, not just lost accentuation."
        )

    if (
        diacritics["diacritic_accuracy_pct"] is not None
        and diacritics["diacritic_accuracy_pct"] < thresholds.min_diacritic_accuracy_pct
    ):
        warnings.append(
            f"Diacritic accuracy is {diacritics['diacritic_accuracy_pct']}%, "
            f"below the threshold ({thresholds.min_diacritic_accuracy_pct}%). "
            "Check breathings, accents, and iota subscript."
        )

    if overlap < thresholds.min_word_overlap_pct:
        warnings.append(
            f"Order-independent word overlap is {round(overlap, 2)}%, "
            f"below the threshold ({thresholds.min_word_overlap_pct}%). "
            "If base-letter similarity is also low but this figure is high, "
            "the texts likely match in content but differ in order (e.g. "
            "footnote placement), rather than in actual OCR accuracy."
        )

    passed = len(errors) == 0

    return {
        "passed": passed,
        "metrics": {
            "content": content,
            "base_letter_similarity_pct": round(base_sim, 2),
            "diacritic_integrity": diacritics,
            "word_overlap_pct": round(overlap, 2),
        },
        "warnings": warnings,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Reference text (correct transcription)
    reference_text = "τύχη ἀγαθῇ· ὁ θεὸς ἔδωκε χρησμὸν περὶ τῆς τύχης."

    # Simulated OCR output with breathings/accents misrecognized,
    # but correct base letters
    ocr_diacritic_noise = "τυχη αγαθη ο θεος εδωκε χρησμον περι της τυχης."

    # Simulated OCR output with a misrecognized base letter (χ -> κ)
    ocr_letter_error = "τύχη ἀγαθῇ· ὁ θεὸς ἔδωκε κρησμὸν περὶ τῆς τύχης."

    print("--- Case 1: diacritic noise only ---")
    print(verify_greek_conversion(reference_text, ocr_diacritic_noise))

    print("\n--- Case 2: base-letter error ---")
    print(verify_greek_conversion(reference_text, ocr_letter_error))
