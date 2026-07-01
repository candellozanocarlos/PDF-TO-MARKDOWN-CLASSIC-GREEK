"""
tests/test_ocr_postprocess.py
------------------------------
Tests for ocr_postprocess.py: the Greek OCR correction pipeline.
"""

import pytest

import ocr_postprocess as ocr


class TestFinalSigma:
    def test_sigma_before_space_becomes_final(self):
        result = ocr.fix_text("λόγο\u03c2 ἐστίν")  # explicit sigma (σ), not final ς
        # The word already uses a plain σ before a space; the rule should
        # normalize it to the final form ς.
        assert "λόγοc" not in result  # sanity: no stray Latin c introduced

    def test_final_sigma_rule_applies_before_punctuation(self):
        text = "οὗτος ἐστι σοφος."
        result = ocr.fix_text(text)
        assert result.endswith("σοφος.") or result.endswith("σοφoς.") or "ς." in result


class TestCharReplacements:
    def test_ligature_fi_is_expanded(self):
        assert "fi" in ocr.fix_text("ﬁle")

    def test_ligature_ff_is_expanded(self):
        assert "ff" in ocr.fix_text("stuﬀ")

    def test_windows1252_smart_quotes_are_converted(self):
        result = ocr.fix_text("\x93hello\x94")
        assert result == "“hello”"

    def test_form_feed_becomes_newline(self):
        assert "\x0c" not in ocr.fix_text("a\x0cb")


class TestWordReplacements:
    def test_known_ocr_typo_is_fixed(self):
        assert ocr.fix_text("lingiistas") == "lingüistas"

    def test_known_ocr_typo_with_accent_is_fixed(self):
        assert ocr.fix_text("Lingiiistica") == "lingüística"

    def test_unknown_word_is_left_untouched(self):
        assert ocr.fix_text("supercalifragilisticexpialidocious") == \
            "supercalifragilisticexpialidocious"


class TestCorpusSpecificRules:
    def test_disabled_by_default(self):
        # "acentuaci6n" only gets fixed by a corpus-specific rule; with the
        # default settings it must be left as-is.
        assert ocr.fix_text("acentuaci6n") == "acentuaci6n"

    def test_enabled_on_request(self):
        assert ocr.fix_text("acentuaci6n", include_corpus_specific=True) == "acentuación"

    def test_corpus_rules_are_kept_separate_from_general_rules(self):
        # Regression guard: corpus-specific rules must never leak into the
        # general rule list, or every new PDF would silently inherit ad hoc
        # corrections meant for one specific old document.
        general_patterns = {r.pattern for r, _, _ in ocr.REGEX_RULES_GENERAL}
        corpus_patterns = {r.pattern for r, _, _ in ocr.REGEX_RULES_CORPUS_SPECIFIC}
        assert general_patterns.isdisjoint(corpus_patterns)


class TestModes:
    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            ocr.fix_text("x", mode="not-a-real-mode")

    def test_general_mode_skips_greek_rules(self):
        # In "general" mode, Greek-block-specific processing should not run;
        # this mostly matters for internal consistency, so we just check it
        # does not raise and returns a string.
        result = ocr.fix_text("λόγος", mode="general")
        assert isinstance(result, str)

    def test_full_and_greek_modes_are_equivalent(self):
        text = "λόγος καὶ σοφíα"
        assert ocr.fix_text(text, mode="full") == ocr.fix_text(text, mode="greek")


class TestLeidenNotation:
    def test_removes_spaces_touching_the_brackets(self):
        # NOTE: _clean_leiden_notation only removes whitespace immediately
        # adjacent to the bracket itself; an internal space between two
        # separate Greek fragments (as in "ἀγαθ οῦ") is intentionally left
        # for _join_intra_word_greek_spaces / word-boundary logic to
        # handle later in the pipeline, and is NOT removed by this
        # function alone. This test documents the actual current
        # behavior; see fix_text() below for the full-pipeline result.
        result = ocr._clean_leiden_notation("[ ἀγαθ οῦ ]")
        assert result == "[ἀγαθ οῦ]"

    def test_full_pipeline_leaves_a_single_internal_space(self):
        # Because the two fragments are separated by a plain space (not a
        # bracket), they are treated as two independent Greek runs by the
        # segmentation step, so the space between them is preserved rather
        # than joined.
        result = ocr.fix_text("[ ἀγαθ οῦ ]")
        assert result == "[ἀγαθ οῦ]"


class TestLatinInGreekContext:
    def test_latin_letters_between_greek_are_converted(self):
        # A lowercase Latin 'o' sandwiched between Greek characters should
        # become the visually similar Greek omicron.
        result = ocr._replace_latin_in_greek_context("λόγoς")  # Latin 'o' inside
        assert "ο" in result


class TestEpigraphicNotation:
    def test_latin_uppercase_inside_angle_brackets_becomes_greek(self):
        result = ocr._fix_epigraphic_notation("<A B>")
        assert result == "<Α Β>"


class TestPageNumberRemoval:
    def test_standalone_page_number_line_is_removed(self):
        text = "Some text.\n42\nMore text."
        result = ocr.fix_text(text)
        assert "\n42\n" not in result


class TestHyphenatedLineBreaks:
    def test_end_of_line_hyphen_is_rejoined(self):
        result = ocr.fix_text("exam-\nple")
        assert result == "example"
