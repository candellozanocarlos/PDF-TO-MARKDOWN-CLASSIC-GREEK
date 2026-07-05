"""
fix_cardo_pua_greek.py

Converts legacy Cardo-font Private Use Area (PUA) characters for
epsilon-with-circumflex and omicron-with-circumflex into the Unicode-
recommended combining sequence (base vowel + U+0342 COMBINING GREEK
PERISPOMENI), and exports the result as clean UTF-8 plain text.

Background: standard Greek never puts a circumflex on epsilon or omicron
(only on vowels long by nature: alpha, eta, iota, omega, upsilon), so
Unicode never defined a precomposed codepoint for these dialectal signs.
Several classicist fonts (Cardo among them) agreed on private codepoints
to display them, but those codepoints only render correctly with that
exact font installed. Once copied elsewhere (a .txt file, this chat,
another editor), they disappear because no other font maps anything to
those codepoints.

Known Cardo PUA mappings handled here:
    U+E1B0 -> epsilon + circumflex   (rendered as ε + U+0342)
    U+E1C3 -> omicron + circumflex   (rendered as ο + U+0342)

If your document uses uppercase variants or other dialectal PUA glyphs,
add them to PUA_MAP below once you confirm their meaning.

Footnotes and endnotes: a .docx stores footnote and endnote text in
separate XML parts (word/footnotes.xml, word/endnotes.xml), not inside
word/document.xml where the main body lives. A page image read by OCR
does not make that distinction, since footnotes are simply more visible
text at the bottom of the page. Appending all notes in a single block
after the body text preserves their content but not their position,
which breaks the sequence-alignment similarity score on long documents
(matching a block that has moved far from its original position is much
harder than matching one still roughly in place). Instead, this script
replaces each footnote/endnote reference marker inside the body with the
actual note text, right where it was cited, which keeps the overall
reading order close to what OCR encounters page by page.

Usage:

    python fix_cardo_pua_greek.py input.docx output.txt
"""

import argparse
import html
import re
import zipfile
from pathlib import Path

COMBINING_PERISPOMENI = "\u0342"

# Confirmed Cardo PUA codepoints -> base letter to combine with the
# perispomeni. Extend this table if other dialectal signs turn up.
PUA_MAP = {
    "\ue1b0": "\u03b5" + COMBINING_PERISPOMENI,  # epsilon + circumflex
    "\ue1c3": "\u03bf" + COMBINING_PERISPOMENI,  # omicron + circumflex
}


FOOTNOTE_REFERENCE_PATTERN = re.compile(r'<w:footnoteReference[^>]*\bw:id="(-?\d+)"[^>]*/>')
ENDNOTE_REFERENCE_PATTERN = re.compile(r'<w:endnoteReference[^>]*\bw:id="(-?\d+)"[^>]*/>')
NOTE_BLOCK_PATTERN = re.compile(
    r'<w:(footnote|endnote)\b(?![Rr]eference)[^>]*\bw:id="(-?\d+)"[^>]*>(.*?)</w:\1>',
    re.DOTALL,
)


def extract_paragraphs_from_xml(xml_content: str) -> list:
    """
    Given the raw XML content of a .docx part (document.xml, footnotes.xml,
    endnotes.xml...), returns a list of paragraph strings, each one built
    from the text runs it contains, in reading order.
    """
    paragraphs = re.findall(r"<w:p[ >].*?</w:p>", xml_content, re.DOTALL)
    result = []
    for paragraph_xml in paragraphs:
        runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", paragraph_xml, re.DOTALL)
        paragraph_text = "".join(html.unescape(run) for run in runs)
        result.append(paragraph_text)
    return result


def build_note_map(xml_content: str) -> dict:
    """
    Parses a footnotes.xml or endnotes.xml part into {id: note_text}.
    Skips ids -1 and 0, which Word reserves for the internal separator
    and continuation-separator marks, not real authored notes.
    """
    note_map = {}
    for _, note_id, note_body in NOTE_BLOCK_PATTERN.findall(xml_content):
        if note_id in ("-1", "0"):
            continue
        paragraphs = extract_paragraphs_from_xml(note_body)
        note_map[note_id] = " ".join(p.strip() for p in paragraphs if p.strip())
    return note_map


def read_docx_part(docx_path: Path, part_name: str) -> str:
    """Returns the raw XML text of a .docx part, or '' if it does not exist."""
    with zipfile.ZipFile(docx_path) as archive:
        if part_name not in archive.namelist():
            return ""
        return archive.read(part_name).decode("utf-8")


def extract_full_text(docx_path: Path) -> list:
    """
    Returns the body paragraphs with every footnote/endnote reference
    marker replaced, in place, by the text of that note, so the overall
    reading order matches what an OCR pass over the printed pages would
    encounter (each note appearing close to where it was cited, not all
    clustered at the very end of the document).
    """
    body_xml = read_docx_part(docx_path, "word/document.xml")
    footnote_map = build_note_map(read_docx_part(docx_path, "word/footnotes.xml"))
    endnote_map = build_note_map(read_docx_part(docx_path, "word/endnotes.xml"))

    def replace_footnote(match: re.Match) -> str:
        text = footnote_map.get(match.group(1), "")
        return f"<w:t> [{html.escape(text)}] </w:t>" if text else ""

    def replace_endnote(match: re.Match) -> str:
        text = endnote_map.get(match.group(1), "")
        return f"<w:t> [{html.escape(text)}] </w:t>" if text else ""

    body_xml = FOOTNOTE_REFERENCE_PATTERN.sub(replace_footnote, body_xml)
    body_xml = ENDNOTE_REFERENCE_PATTERN.sub(replace_endnote, body_xml)

    return extract_paragraphs_from_xml(body_xml)


def fix_pua_characters(text: str) -> str:
    """Replaces every known PUA codepoint with its Unicode-correct sequence."""
    for pua_char, replacement in PUA_MAP.items():
        text = text.replace(pua_char, replacement)
    return text


def convert(docx_path: Path, output_path: Path) -> None:
    paragraphs = extract_full_text(docx_path)
    fixed_paragraphs = [fix_pua_characters(p) for p in paragraphs]
    full_text = "\n".join(fixed_paragraphs)
    output_path.write_text(full_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix Cardo PUA epsilon/omicron circumflex characters and export clean UTF-8 text."
    )
    parser.add_argument("docx_path", type=Path, help="Source .docx file")
    parser.add_argument("output_path", type=Path, help="Destination .txt file")
    args = parser.parse_args()

    convert(args.docx_path, args.output_path)
    print(f"Written: {args.output_path}")


if __name__ == "__main__":
    main()
