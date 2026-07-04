"""
ocr_postprocess.py
-------------------
OCR text post-processing for multilingual academic texts with Ancient
Greek (Tesseract grc+fra+deu+eng+spa).

Usage:
    from ocr_postprocess import fix_text

    clean_text = fix_text(raw_text)
    clean_text = fix_text(raw_text, verbose=True)

The rules are organized into sections and are easy to extend. To add a
new pattern, just add an entry to the corresponding dictionary or a tuple
to the corresponding rule list.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------
# Greek constants
# ---------------------------------------------------------------------------

GREEK_CHAR = r"[Ͱ-Ͽἀ-῿]"

# Captures Greek runs including interleaved Leiden brackets (ἀγαθ[ο]ῦ).
# Allows one bracket character between two Greek sequences so as not to
# break epigraphic words with gaps in the middle.
GREEK_RUN_RE = re.compile(
    r"[Ͱ-Ͽἀ-῿]+"
    r"(?:[\[\](){}⟨⟩][Ͱ-Ͽἀ-῿]+)*"
)

# Punctuation recognized after a final sigma
_SIGMA_FINAL_LOOKAHEAD = r"""[\s,\.·;:\!\?\)\]\}»'"··]|$"""

# Frequent particles / monosyllables: do not merge with the following word
GREEK_STOPWORDS = frozenset({
    "καὶ", "καί", "οὐ", "οὐκ", "οὐχ", "μὴ", "μή", "δὲ", "δέ", "γὰρ", "γάρ",
    "ἐν", "εἰ", "ὡς", "μὲν", "μέν", "ἡ", "ὁ", "οἱ", "αἱ", "τὰ", "τὸ", "τῇ",
    "τῷ", "ἐκ", "πρὸς", "πρὸ", "ἀπὸ", "μετὰ", "κατὰ", "παρὰ", "ὑπὸ", "ὑπὲρ",
    "ἀλλὰ", "ἄρα", "οὖν", "ἔτι", "οὐδὲ", "εἰς", "ἄν", "τε", "γε", "τι", "τις",
    "ἂν", "ἃν", "ὅτι", "ὅτε", "ὅπερ", "ὅπως", "ὅστις", "ὅσον", "ὅσοι",
})

# Latin uppercase homoglyphs → Greek in epigraphic notation <...>
# Extended: G→Γ, L→Λ, S→Σ, V→Υ compared to the previous version
EPIGRAPHIC_LATIN_TO_GREEK = {
    "A": "Α", "B": "Β", "D": "Δ", "E": "Ε", "F": "Φ",
    "G": "Γ", "H": "Η", "I": "Ι", "K": "Κ", "L": "Λ",
    "M": "Μ", "N": "Ν", "O": "Ο", "P": "Ρ", "Q": "Ω",
    "S": "Σ", "T": "Τ", "V": "Υ", "X": "Χ", "Y": "Υ", "Z": "Ζ",
}

# Latin lowercase letters visually similar to Greek ones.
# Applied ONLY when the letter is surrounded by Greek characters.
LATIN_TO_GREEK_IN_RUN = {
    "a": "α", "b": "β", "e": "ε", "i": "ι", "k": "κ",
    "n": "ν", "o": "ο", "p": "ρ", "r": "ρ", "t": "τ",
    "u": "υ", "v": "ν", "w": "ω", "x": "χ",
}

# Fixed lookbehind/lookahead (one Greek character) → substitution without consuming context
_LATIN_IN_GREEK_CTX_RE = re.compile(
    r"(?<=[Ͱ-Ͽἀ-῿])([a-z])(?=[Ͱ-Ͽἀ-῿])"
)

# ---------------------------------------------------------------------------
# 1. SINGLE-CHARACTER SUBSTITUTIONS
#    Systematic, context-independent OCR errors.
# ---------------------------------------------------------------------------

CHAR_REPLACEMENTS = {
    # Misrecognized typographic quotes (Windows-1252 → Unicode)
    "\x93": "“",
    "\x94": "”",
    "\x91": "‘",
    "\x92": "’",
    "\x85": "...",
    "\x96": "–",   # en-dash
    "\x97": "—",   # em-dash

    # Leftover control characters
    "\x0c": "\n",       # form feed
    "\r\n": "\n",
    "\r": "\n",

    # Special spaces → normal space
    " ": " ",  # non-breaking space (was a plain space by mistake, a no-op)
    "​": "",       # zero-width space
    "‌": "",       # zero-width non-joiner
    "﻿": "",       # BOM

    # Poorly segmented Latin ligatures (common in old PDFs)
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬆ": "st",
}

# ---------------------------------------------------------------------------
# 2. GENERAL RULES (whole text)
# ---------------------------------------------------------------------------

REGEX_RULES_GENERAL = [


    # --- Pagination and header artifacts ---

    (re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE),
     "",
     "Removes lines that are only a page number"),

    # --- End-of-line hyphens (syllabic division from the original) ---

    (re.compile(r"(\w)-\n(\w)", re.UNICODE),
     r"\1\2",
     "Rejoins words split by an end-of-line hyphen"),

    (re.compile(r"(\w)- \n(\w)", re.UNICODE),
     r"\1\2",
     "Rejoins words split by an end-of-line hyphen+space"),

    # --- Spurious spaces ---

    (re.compile(r" {2,}"),
     " ",
     "Collapses multiple spaces"),

    (re.compile(r" ([,\.\!\?\:\;])(?!\s*\n)"),
     r"\1",
     "Removes space before punctuation"),

    (re.compile(r"\n{3,}"),
     "\n\n",
     "Collapses multiple blank lines"),

    # --- Numeric confusions in Latin-script context ---

    (re.compile(
        r"(?<=[a-záéíóúàèìòùäëïöüâêîôûæœ])1(?=[a-záéíóúàèìòùäëïöüâêîôûæœ])",
        re.IGNORECASE | re.UNICODE,
    ),
     "l",
     "1 between Latin letters → l"),

    (re.compile(
        r"(?<=[a-záéíóúàèìòùäëïöüâêîôûæœ])0(?=[a-záéíóúàèìòùäëïöüâêîôûæœ])",
        re.IGNORECASE | re.UNICODE,
    ),
     "o",
     "0 between Latin letters → o"),

    # --- Tesseract multi-character confusions in Greek context ---
    # Applied here (before segmentation) because the characters involved
    # are Latin and would break the Greek run if not handled first.

    (re.compile(rf"(?<={GREEK_CHAR})ij|ij(?={GREEK_CHAR})"),
     "η",
     "ij in Greek context → η"),

    (re.compile(rf"(?<={GREEK_CHAR})rj|rj(?={GREEK_CHAR})"),
     "η",
     "rj in Greek context → η"),

    (re.compile(rf"(?<={GREEK_CHAR})cp|cp(?={GREEK_CHAR})"),
     "φ",
     "cp in Greek context → φ"),

    (re.compile(rf"(?<={GREEK_CHAR})<p|<p(?={GREEK_CHAR})"),
     "φ",
     "<p in Greek context → φ"),

    (re.compile(rf"(?<={GREEK_CHAR})©|©(?={GREEK_CHAR})"),
     "θ",
     "© in Greek context → θ (theta)"),

    # Also applied here rather than in REGEX_RULES_GREEK: ';' and the loose
    # breathing mark are not bracket characters that GREEK_RUN_RE allows
    # inside a run, so a Greek block gets segmented right before/after
    # them and REGEX_RULES_GREEK (block-scoped) would never see Greek
    # characters on both sides.

    (re.compile(rf"(?<={GREEK_CHAR});(?={GREEK_CHAR})"),
     "",
     "Spurious ; inside a Greek word"),

    (re.compile(rf"(?<={GREEK_CHAR})[̓̔''](?={GREEK_CHAR})"),
     "",
     "Loose breathing mark or apostrophe inside a word"),

    # --- Bibliographic references ---

    (re.compile(r"\bp p\.\s*(\d)"),
     r"pp. \1",
     "Fixes 'p p.' → 'pp.'"),

    (re.compile(r"\bI bid\b", re.IGNORECASE),
     "Ibid",
     "Fixes 'I bid' → 'Ibid'"),

    (re.compile(r"\bop\s*\.\s*cit\s*\."),
     "op. cit.",
     "Normalizes 'op. cit.'"),

    # --- Column and table artifacts ---

    (re.compile(r"\t+"),
     " ",
     "Converts tabs into spaces"),

    (re.compile(r"^\s*[-=\*]{3,}\s*$", re.MULTILINE),
     "",
     "Removes column separator lines"),

    # --- Section sign (§) OCR confusions (common in academic PDFs) ---
    # $$ and $ before a digit are almost never legitimate in philological texts.

    (re.compile(r"\$\$\s*(?=\d)"),
     "§§ ",
     "$$ before digit → §§ (section sign double)"),

    (re.compile(r"\$\s*(?=\d)"),
     "§",
     "$ before digit → § (section sign)"),

    # --- French academic spelling ---

    (re.compile(r"«\s+"),
     "« ",
     "Normalizes the space after «"),

    (re.compile(r"\s+»"),
     " »",
     "Normalizes the space before »"),

    # --- Phonetic (IPA) notation ---

    (re.compile(r"/9:/"),
     "/ɔː/",
     "/9:/ → /ɔː/ (IPA)"),

    (re.compile(r"\[9:\]"),
     "[ɔː]",
     "[9:] → [ɔː] (IPA)"),

    (re.compile(r'/"([a-zA-Zɑ-ɿʀ-ʿ])'),
     r"/ʰ\1",
     '/" → /ʰ (IPA aspirated)'),
]

# ---------------------------------------------------------------------------
# 2b. CORPUS-SPECIFIC RULES
# Automatically generated by ocr_ml_detector.py (an internal tool, not
# included in this repository) from errors observed in specific documents
# already processed. They are kept separate from REGEX_RULES_GENERAL
# because they are ad hoc corrections (proper nouns, very specific word
# fragments) that do not make sense to apply to a brand-new PDF. Enable
# They are applied by default. Pass include_corpus_specific=False to
# disable them when processing a document outside this corpus.
# ---------------------------------------------------------------------------

REGEX_RULES_CORPUS_SPECIFIC = [
    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Ilioaı", re.IGNORECASE | re.UNICODE),
     "llioaı",
     "Il→ll at word start (Ileno→lleno, Ilama→llama)"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Ηellenistic", re.IGNORECASE | re.UNICODE),
     "Ηellenιstιc",
     "Mixed Greek+Latin script: 'i'→'ι'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"AAλοιρ", re.IGNORECASE | re.UNICODE),
     "ΑΑλοιρ",
     "Mixed Greek+Latin script: 'A'→'Α'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"önnoσίων", re.IGNORECASE | re.UNICODE),
     "önnοσίων",
     "Mixed Greek+Latin script: 'o'→'ο'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"ἐξetvat", re.IGNORECASE | re.UNICODE),
     "ἐξetνat",
     "Mixed Greek+Latin script: 'v'→'ν'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"xeoάσθο", re.IGNORECASE | re.UNICODE),
     "xeοάσθο",
     "Mixed Greek+Latin script: 'o'→'ο'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"duyaδεύαντι", re.IGNORECASE | re.UNICODE),
     "dυyaδεύαντι",
     "Mixed Greek+Latin script: 'u'→'υ'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"ΙN", re.IGNORECASE | re.UNICODE),
     "ΙΝ",
     "Mixed Greek+Latin script: 'N'→'Ν'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Develἢ", re.IGNORECASE | re.UNICODE),
     "Deνelἢ",
     "Mixed Greek+Latin script: 'v'→'ν'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"SUMMARΥ", re.IGNORECASE | re.UNICODE),
     "SUΜΜΑRΥ",
     "Mixed Greek+Latin script: 'M'→'Μ' 'A'→'Α'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Agteptρίαν", re.IGNORECASE | re.UNICODE),
     "Αgteρtρίαν",
     "Mixed Greek+Latin script: 'A'→'Α' 'p'→'ρ'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"φαAvgöv", re.IGNORECASE | re.UNICODE),
     "φαΑνgöν",
     "Mixed Greek+Latin script: 'A'→'Α' 'v'→'ν'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"XQEOTEQκαὶ", re.IGNORECASE | re.UNICODE),
     "ΧQΕΟΤΕQκαὶ",
     "Mixed Greek+Latin script: 'X'→'Χ' 'E'→'Ε' 'O'→'Ο' 'T'→'Τ'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Zußagiται", re.IGNORECASE | re.UNICODE),
     "Ζυßagιται",
     "Mixed Greek+Latin script: 'Z'→'Ζ' 'u'→'υ' 'i'→'ι'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Εéveoc", re.IGNORECASE | re.UNICODE),
     "Εéνeοc",
     "Mixed Greek+Latin script: 'v'→'ν' 'o'→'ο'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"SENSΕ", re.IGNORECASE | re.UNICODE),
     "SΕΝSΕ",
     "Mixed Greek+Latin script: 'E'→'Ε' 'N'→'Ν'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"BRΟAD", re.IGNORECASE | re.UNICODE),
     "ΒRΟΑD",
     "Mixed Greek+Latin script: 'B'→'Β' 'A'→'Α'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"TΗE", re.IGNORECASE | re.UNICODE),
     "ΤΗΕ",
     "Mixed Greek+Latin script: 'T'→'Τ' 'E'→'Ε'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Ηesychios", re.IGNORECASE | re.UNICODE),
     "Ηesychιοs",
     "Mixed Greek+Latin script: 'i'→'ι' 'o'→'ο'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"BeiAoμαι", re.IGNORECASE | re.UNICODE),
     "ΒeιΑομαι",
     "Mixed Greek+Latin script: 'B'→'Β' 'i'→'ι' 'A'→'Α' 'o'→'ο'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"PöAoμαι", re.IGNORECASE | re.UNICODE),
     "ΡöΑομαι",
     "Mixed Greek+Latin script: 'P'→'Ρ' 'A'→'Α' 'o'→'ο'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"CΥPRΙΟT", re.IGNORECASE | re.UNICODE),
     "CΥΡRΙΟΤ",
     "Mixed Greek+Latin script: 'P'→'Ρ' 'T'→'Τ'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"NOΝΟΥΣ", re.IGNORECASE | re.UNICODE),
     "ΝΟΝΟΥΣ",
     "Mixed Greek+Latin script: 'N'→'Ν' 'O'→'Ο'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"CΥPRIΟT", re.IGNORECASE | re.UNICODE),
     "CΥΡRΙΟΤ",
     "Mixed Greek+Latin script: 'P'→'Ρ' 'I'→'Ι' 'T'→'Τ'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"MYCENAΕAN", re.IGNORECASE | re.UNICODE),
     "ΜYCΕΝΑΕΑΝ",
     "Mixed Greek+Latin script: 'M'→'Μ' 'E'→'Ε' 'N'→'Ν' 'A'→'Α'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Ηomeric", re.IGNORECASE | re.UNICODE),
     "Ηοmerιc",
     "Mixed Greek+Latin script: 'o'→'ο' 'i'→'ι'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Ιonic", re.IGNORECASE | re.UNICODE),
     "Ιοnιc",
     "Mixed Greek+Latin script: 'o'→'ο' 'i'→'ι'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"Εuboean", re.IGNORECASE | re.UNICODE),
     "Ευbοean",
     "Mixed Greek+Latin script: 'u'→'υ' 'o'→'ο'"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"ovvavφότεροι", re.IGNORECASE | re.UNICODE),
     "ovvaνφότεροι",
     "Latin v→ν (nu) adjacent to Greek"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"κἐλευλύvıa", re.IGNORECASE | re.UNICODE),
     "κἐλευλύνıa",
     "Latin v→ν (nu) adjacent to Greek"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"ivbooßievεἰ", re.IGNORECASE | re.UNICODE),
     "ivbooßieνεἰ",
     "Latin v→ν (nu) adjacent to Greek"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"acentuaci6n", re.IGNORECASE | re.UNICODE),
     "acentuación",
     "Spanish ci6n→ción (noun ending; text being corrected is Spanish)"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"absorci6n", re.IGNORECASE | re.UNICODE),
     "absorción",
     "Spanish ci6n→ción (noun ending; text being corrected is Spanish)"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"pronunciaci6n", re.IGNORECASE | re.UNICODE),
     "pronunciación",
     "Spanish ci6n→ción (noun ending; text being corrected is Spanish)"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"‘espafiol’", re.IGNORECASE | re.UNICODE),
     "‘español’",
     "Spanish espafiol→español"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"formulaci6n", re.IGNORECASE | re.UNICODE),
     "formulación",
     "Spanish ci6n→ción (noun ending; text being corrected is Spanish)"),


    # Automatically detected by ocr_ml_detector.py
    (re.compile(r"relaci6n", re.IGNORECASE | re.UNICODE),
     "relación",
     "Spanish ci6n→ción (noun ending; text being corrected is Spanish)"),

    # --- Brill journal running footer artifacts ---
    # The footer of Brill PDFs (MNEMOSYNE, Glotta, etc.) is OCR'd with
    # systematic errors.  These are safe to apply to any Brill corpus.

    (re.compile(r"MNEMOSYNE\s*\(22h\)\s*1526\s*,?\s*4\.17-41a0", re.IGNORECASE),
     "MNEMOSYNE (2021) 1-26",
     "Brill footer: (22h) 1526, 4.17-41a0 → (2021) 1-26"),

    (re.compile(r"\bomnioaded\b", re.IGNORECASE),
     "Downloaded",
     "omnioaded → Downloaded (Brill OCR artifact)"),

    (re.compile(r"omnioaded\s+from\s+ΒΗ\s+com(?=\d)"),
     "Downloaded from Brill.com",
     "'omnioaded from ΒΗ com' → 'Downloaded from Brill.com'"),

    (re.compile(r"\bjed\s+from\s+Brill\.com"),
     "Downloaded from Brill.com",
     "Truncated 'jed from Brill.com' → 'Downloaded from Brill.com'"),

    # --- LOD abbreviation (Les lamelles oraculaires de Dodone, Lhôte 2006) ---
    # The capital L of "LOD" is read as "[Γ" or "[Ο" depending on the font.

    (re.compile(r"\[ΓΟ\b"),
     "LOD",
     "[ΓΟ → LOD (Les lamelles oraculaires de Dodone, abbreviation)"),

    (re.compile(r"\[ΟΡ\b"),
     "LOD",
     "[ΟΡ → LOD (LOD abbreviation OCR error)"),

    # --- French words misread as Greek ---

    (re.compile(r"\bὕπο\s+liste\b"),
     "Une liste",
     "ὕπο liste → Une liste (French 'Une' OCR'd as Greek)"),

    # --- Section sign ὃ (omicron with psili+varia) before a digit ---
    # In Brill PDFs, ὃ immediately before an integer always represents §.
    # The true Greek article ὃ never precedes a bare numeral in these texts.

    (re.compile(r"\bὃ\s+(?=\d)"),
     "§ ",
     "ὃ before digit → § (section sign OCR error in Brill PDFs)"),

    # -----------------------------------------------------------------------
    # OCR fixes from Alonso Déniz 2022 (Mnemosyne 2021, Brill)
    # Diplomatic text and apparatus criticus of the L2 lead tablet
    # (Apollonia d'Illyrie, hymne à Asclépios, SEG 65 397)
    # -----------------------------------------------------------------------

    # L2 verse 1: ΗΙΛΑΟΝ in epigraphic mixed font
    (re.compile(r"\bhiAdov\b"),
     "hιλάο̄ν",
     "hiAdov → hιλάο̄ν (L2 diplomatic text, epigraphic form of ἱλάων)"),

    # Apparatus v.1-2: Cabanes reading (backslash is literal in source)
    (re.compile(r"ht\\aov\s+Cabanes"),
     "hίλαον Cabanes",
     r"ht\aov Cabanes → hίλαον Cabanes (apparatus criticus)"),

    # Apparatus v.1-2: Lhôte reading with Leiden angle brackets
    (re.compile(r"hlAao\(ç\)\s+Lhôte"),
     "hίλαο⟨ς⟩ Lhôte",
     "hlAao(ç) Lhôte → hίλαο⟨ς⟩ Lhôte (apparatus criticus)"),

    # Apparatus v.1: [ἵλα]ος A — the ἵ was swallowed by the OCR
    (re.compile(r"\[λα\]ος A"),
     "[ἵλα]ος A",
     "[λα]ος A → [ἵλα]ος A (ἵ lost in OCR)"),

    # Apparatus v.3: Lhôte reading [ἰε̄̀ (sic) ο̄̓]
    (re.compile(r"\[lé\s+\(sic\)\s+ὁ\]"),
     "[ἰε̄̀ (sic) ο̄̓]",
     "[lé (sic) ὁ] → [ἰε̄̀ (sic) ο̄̓] (apparatus criticus v.3, Lhôte)"),

    # Apparatus v.3: Dion reading (ἰὲ ὦ ἰὲ ὦ ἰὲ D)
    (re.compile(r"lédlédièD"),
     "ἰὲ ὦ ἰὲ ὦ ἰὲ D",
     "lédlédièD → ἰὲ ὦ ἰὲ ὦ ἰὲ D (apparatus criticus, Dion reading)"),

    # Apparatus v.4: combined block ἁ[μᾶς] Cabanes, ἁ[μέ] Lhôte
    # The & is a mangled ἁ; [uäç] is [μᾶς]; d[pé] is ἁ[μέ]
    (re.compile(r"4\.\s*&\s*\[uäç\]\s+Cabanes,\s+d\[pé\]\s+Lhôte"),
     "4. ἁ[μᾶς] Cabanes, ἁ[μέ] Lhôte",
     "4.&[uäç] Cabanes, d[pé] Lhôte → 4. ἁ[μᾶς] Cabanes, ἁ[μέ] Lhôte"),

    # Apparatus v.4: EPD reading ἡμᾶς E P D
    (re.compile(r"hpuäçEPD"),
     "ἡμᾶς E P D",
     "hpuäçEPD → ἡμᾶς E P D (apparatus criticus, E P D reading)"),

    # L1 line 3: prophetess title hα μάντις (Dodona)
    (re.compile(r"Βα\s+pavris"),
     "hα μάντις",
     "Βα pavris → hα μάντις (L1 l.3, title of the Dodona prophetess)"),

    # CEG 396.3 (Metapontum, ca. 500 BC): ϝάναξ Hε̄́ρακλες
    (re.compile(r"FavaË\s+Héponches"),
     "ϝάναξ Hε̄́ρακλες",
     "FavaË Héponches → ϝάναξ Hε̄́ρακλες (CEG 396.3, Metapontum)"),

    # CEG 396.3: ἀγαθάν (last word of the cited line)
    (re.compile(r"\bdyaodv\b"),
     "ἀγαθάν",
     "dyaodv → ἀγαθάν (CEG 396.3, Metapontum)"),

    # Footnote 68: scholion reference (= and CÉ.XIL6 both garbled)
    (re.compile(r"=\s*CÉ\.XIL6\.414b-cE\.?"),
     "Cf. Σ Il. 6.414b-c E.",
     "= CÉ.XIL6.414b-cE. → Cf. Σ Il. 6.414b-c E. (scholion reference, fn.68)"),

    # Footnote 71: Εἰ (Greek εἰ) used for Latin 'Cf.' + Ἀλχ→Ἀλκ (χ/κ OCR confusion)
    (re.compile(r"Εἰ\s+Ἀλχίμου"),
     "Cf. Ἀλκίμου",
     "Εἰ Ἀλχίμου → Cf. Ἀλκίμου (fn.71: Εἰ=Cf., χ→κ)"),

    # Footnote 71: Todôv → ποδο̃ν (genitive plural, IG 9.12.4 874)
    (re.compile(r"\bTodôv\b"),
     "ποδο̃ν",
     "Todôv → ποδο̃ν (fn.71, IG 9.12.4 874.3)"),
]

# ---------------------------------------------------------------------------
# 3. GREEK RULES (only blocks containing Greek characters)
# ---------------------------------------------------------------------------

REGEX_RULES_GREEK = [

    # Final sigma: σ → ς before space, punctuation, or end of line
    (re.compile(
        rf"σ(?={_SIGMA_FINAL_LOOKAHEAD})",
        re.MULTILINE | re.UNICODE,
    ),
     "ς",
     "σ before space/punctuation → ς (final sigma)"),

    # Documented Tesseract grc confusions
    (re.compile(r"\(ρ"),  "φ",  "(ρ → φ"),
    (re.compile(r"cp"),   "φ",  "cp → φ inside a Greek block"),
    (re.compile(r"<p"),   "φ",  "<p → φ inside a Greek block"),
]

# Alias for compatibility with external code
REGEX_RULES = REGEX_RULES_GENERAL + REGEX_RULES_CORPUS_SPECIFIC + REGEX_RULES_GREEK

# ---------------------------------------------------------------------------
# 4. FULL-WORD SUBSTITUTIONS (Latin-script / academic context)
# ---------------------------------------------------------------------------

WORD_REPLACEMENTS = {
    "lhéte": "Lhôte",
    "dopdonna": "dodona",
    "fiir": "für",
    "lingiiista": "lingüista",
    "geminaciOn": "geminación",
    "sefiala": "señala",
    "preposiciOn": "preposición",
    "sefialé": "señalé",
    "oraciOn": "oración",
    "negaciOn": "negación",
    "variaciOn": "variación",
    "entonaciOn": "entonación",
    "formulaciOn": "formulación",
    "pequenios": "pequeños",
    "afios": "años",
    "lingiistas": "lingüistas",
    "acentuaciOn": "acentuación",
    "lingiiisticos": "lingüisticos",
    "Filologia": "Filología",
    "Lingiiistica": "lingüística",
    "Zeitschrifi": "Zeitschrift",
    "Zeitschnft":  "Zeitschrift",
    "G1otta":      "Glotta",
    "Hespena":     "Hesperia",
    "Mnemosvne":   "Mnemosyne",
    "ibid":        "ibid.",
    "Ibid":        "Ibid.",
    "epigratia":   "epigrafía",
    "epigrafia":   "epigrafía",
    "fonologia":   "fonología",
    "morfologa":   "morfología",
    "inscnpcion":  "inscripción",
    "inscripcion": "inscripción",
}

# Patterns compiled once when the module loads (avoids recompiling on every call)
# For entries that just append a trailing period (e.g. "ibid" -> "ibid."), a
# negative lookahead skips the match when that period is already there, so
# an already-correct "Ibid." in the source is not turned into "Ibid..".
_WORD_PATTERNS = [
    (
        re.compile(
            r"\b" + re.escape(error) + r"\b" + (r"(?!\.)" if correct == error + "." else ""),
            re.UNICODE,
        ),
        correct,
    )
    for error, correct in WORD_REPLACEMENTS.items()
]

# ---------------------------------------------------------------------------
# 5. HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def _apply_char_replacements(text: str) -> str:
    for original, replacement in CHAR_REPLACEMENTS.items():
        text = text.replace(original, replacement)
    return text


def _apply_regex_rules(text: str, rules: list) -> str:
    for pattern, replacement, _description in rules:
        text = pattern.sub(replacement, text)
    return text


def _apply_word_replacements(text: str) -> str:
    for pattern, correct in _WORD_PATTERNS:
        text = pattern.sub(correct, text)
    return text


def _normalize_unicode(text: str) -> str:
    """Normalizes to NFC (canonical composed form), standard for polytonic Greek."""
    return unicodedata.normalize("NFC", text)


def _clean_leiden_notation(text: str) -> str:
    """
    Removes spurious spaces that the OCR introduces inside Leiden
    epigraphic notation brackets: [ ] ( ) { } ⟨ ⟩
    Example: '[ ἀγαθ οῦ ]' → '[ἀγαθοῦ]'
    """
    for opening, closing in [("\\[", "\\]"), ("\\(", "\\)"), ("\\{", "\\}"), ("⟨", "⟩")]:
        text = re.sub(opening + r"\s+", opening.replace("\\", ""), text)
        text = re.sub(r"\s+" + closing, closing.replace("\\", ""), text)
    return text


def _replace_latin_in_greek_context(text: str) -> str:
    """
    Replaces lowercase Latin letters located between two Greek characters
    with their visually equivalent Greek letter (α, ε, ν, ο, ρ…).
    Only acts when the Latin letter is flanked by Greek Unicode, which
    guarantees that the context is a Greek block and not Latin text.
    """
    return _LATIN_IN_GREEK_CTX_RE.sub(
        lambda m: LATIN_TO_GREEK_IN_RUN.get(m.group(1), m.group(1)),
        text,
    )


def _fix_epigraphic_notation(text: str) -> str:
    """Converts Latin uppercase homoglyphs inside <...> to Greek."""
    def _replace(match: re.Match) -> str:
        content = match.group(1)
        for latin, greek in EPIGRAPHIC_LATIN_TO_GREEK.items():
            content = content.replace(latin, greek)
        return f"<{content}>"
    return re.sub(r"<([^>]+)>", _replace, text)


def _join_intra_word_greek_spaces(text: str, max_iterations: int = 5) -> str:
    """
    Joins spurious OCR spaces between adjacent Greek fragments.
    Does not join if both fragments have >= 4 characters (they are likely
    complete separate words, not fragments of the same word).
    """
    pattern = re.compile(rf"([Ͱ-Ͽἀ-῿]+) ([Ͱ-Ͽἀ-῿]+)")

    def _maybe_join(match: re.Match) -> str:
        left, right = match.group(1), match.group(2)
        if left in GREEK_STOPWORDS or right in GREEK_STOPWORDS:
            return match.group(0)
        # Both fragments are long → likely distinct words
        if len(left) >= 4 and len(right) >= 4:
            return match.group(0)
        return left + right

    for _ in range(max_iterations):
        new_text = pattern.sub(_maybe_join, text)
        if new_text == text:
            break
        text = new_text
    return text


def _process_greek_block(text: str) -> str:
    """Applies Greek-specific corrections to an already segmented block."""
    text = _apply_regex_rules(text, REGEX_RULES_GREEK)
    text = _join_intra_word_greek_spaces(text)
    return text


def _segment_and_process(text: str, apply_greek: bool = True) -> str:
    """
    Walks through the text in a single pass, applying:
    - To Greek blocks: Greek rules (if apply_greek=True).
    - To non-Greek blocks: Latin lexical substitutions.
    Merges the two previous passes (_segment_and_process_greek and
    _process_non_greek_blocks) into a single loop.
    """
    parts = []
    last_end = 0
    for match in GREEK_RUN_RE.finditer(text):
        if match.start() > last_end:
            parts.append(_apply_word_replacements(text[last_end:match.start()]))
        block = match.group(0)
        parts.append(_process_greek_block(block) if apply_greek else block)
        last_end = match.end()
    if last_end < len(text):
        parts.append(_apply_word_replacements(text[last_end:]))
    return "".join(parts)


# ---------------------------------------------------------------------------
# 6. MAIN FUNCTION
# ---------------------------------------------------------------------------

def fix_text(
    text: str,
    verbose: bool = False,
    mode: str = "full",
    include_corpus_specific: bool = True,
) -> str:
    """
    Applies the full OCR post-processing pipeline to the text.

    Parameters
    ----------
    text    : str  — Raw text returned by pytesseract.
    verbose : bool — If True, prints character-count statistics.
    mode    : str
        - "full" (default): general rules + Greek + epigraphy.
        - "general": only general and epigraphic rules (no Greek corrections).
        - "greek": explicit alias for "full".
    include_corpus_specific : bool
        If True (default), also applies REGEX_RULES_CORPUS_SPECIFIC (ad hoc
        corrections learned from specific documents already processed).
        Pass False only if you are processing a document outside this corpus
        and the corpus-specific patterns could produce false positives.

    Returns
    -------
    str — Corrected text.
    """
    if mode not in ("full", "general", "greek"):
        raise ValueError(f"invalid mode: {mode!r}. Use 'full', 'general', or 'greek'.")

    if verbose:
        print(f"    [postproc] Characters before: {len(text)}")

    text = _normalize_unicode(text)
    text = _apply_char_replacements(text)
    text = _clean_leiden_notation(text)                 # before segmentation
    text = _replace_latin_in_greek_context(text)         # before segmentation
    text = _apply_regex_rules(text, REGEX_RULES_GENERAL)
    if include_corpus_specific:
        text = _apply_regex_rules(text, REGEX_RULES_CORPUS_SPECIFIC)
    text = _fix_epigraphic_notation(text)
    text = _segment_and_process(text, apply_greek=(mode in ("full", "greek")))
    text = text.strip()

    if verbose:
        print(f"    [postproc] Characters after: {len(text)}")

    return text
