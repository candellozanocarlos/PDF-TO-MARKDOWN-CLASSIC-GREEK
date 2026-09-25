"""Tests for text_layer.is_usable (text-layer vs OCR decision)."""

import text_layer


def test_real_greek_text_is_usable():
    text = "5. Vocalism ἱαρός: hιαρᾶς (ΧΕΔ 487Α.2, 5th?), hιαρόν (ΧΕΔ 1108A.5, m5th?), " * 3
    assert text_layer.is_usable(text)


def test_legacy_greek_font_is_rejected():
    text = "°ÂÓÈÎ¿, ÔÈ ÚÔÛÎ˘ÓËÙ¤˜ ¤Î·Ó·Ó ÙËÓ ÂÚÒÙËÛË ÛÙË ‰È¿ÏÂÎÙfi ÙÔ˘˜. " * 3
    assert not text_layer.is_usable(text)


def test_spanish_with_inverted_marks_is_usable():
    text = "¿Qué dice la inscripción? ¡Nada! Según Méndez Dosuna, el dórico noroccidental. " * 3
    assert text_layer.is_usable(text)


def test_near_empty_page_is_rejected():
    assert not text_layer.is_usable("  12  ")


def test_clean_fixes_greek_capitals_in_latin_words():
    assert text_layer.clean("Τhe view of Μéndez Dosuna (Βoston)") == "The view of Méndez Dosuna (Boston)"
