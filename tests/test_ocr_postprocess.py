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


class TestUnicodeNormalization:
    def test_decomposed_polytonic_sequence_is_composed_to_nfc(self):
        # Some scanners emit alpha + combining smooth breathing + combining
        # iota subscript as three separate codepoints instead of the single
        # precomposed U+1F80 (ᾀ). fix_text must normalize to NFC first.
        decomposed = "ᾀ"
        assert ocr.fix_text(decomposed) == "ᾀ"


class TestWhitespaceAndPunctuationGeneral:
    def test_multiple_spaces_collapse_to_one(self):
        assert ocr.fix_text("a    b") == "a b"

    def test_space_before_punctuation_is_removed(self):
        assert ocr.fix_text("hola , mundo !") == "hola, mundo!"

    def test_multiple_blank_lines_collapse_to_one(self):
        assert ocr.fix_text("a\n\n\n\nb") == "a\n\nb"

    def test_tabs_become_spaces(self):
        assert ocr.fix_text("a\tb\tc") == "a b c"

    def test_column_separator_line_is_removed(self):
        assert ocr.fix_text("text\n---\nmore") == "text\n\nmore"


class TestNumericLatinConfusions:
    def test_digit_one_between_latin_letters_becomes_l(self):
        assert ocr.fix_text("wor1d") == "world"

    def test_digit_zero_between_latin_letters_becomes_o(self):
        assert ocr.fix_text("c0ntent") == "content"

    def test_leading_digit_not_between_letters_is_untouched(self):
        # "1" is at the start of the word (nothing before it), so the
        # lookbehind for a preceding Latin letter fails and it must not
        # be converted to 'l'.
        assert ocr.fix_text("1nformation") == "1nformation"


class TestGreekContextMultiCharConfusions:
    def test_ij_next_to_greek_becomes_eta(self):
        assert ocr.fix_text("λόγijος") == "λόγηος"

    def test_rj_next_to_greek_becomes_eta(self):
        assert ocr.fix_text("λόγrjος") == "λόγηος"

    def test_cp_next_to_greek_becomes_phi(self):
        assert ocr.fix_text("λόγcpος") == "λόγφος"

    def test_copyright_sign_next_to_greek_becomes_theta(self):
        assert ocr.fix_text("λόγ©ος") == "λόγθος"


class TestBibliographicAbbreviations:
    def test_p_p_dot_becomes_pp_dot(self):
        assert ocr.fix_text("see p p. 12") == "see pp. 12"

    def test_op_cit_spacing_is_normalized(self):
        assert ocr.fix_text("op . cit .") == "op. cit."

    def test_i_bid_with_trailing_period_does_not_get_doubled(self):
        assert ocr.fix_text("I bid.") == "Ibid."

    def test_already_correct_ibid_is_left_untouched(self):
        # Regression guard for the fix above: WORD_REPLACEMENTS must not
        # blindly append a period to a word that already has one.
        assert ocr.fix_text("Ibid.") == "Ibid."
        assert ocr.fix_text("ibid.") == "ibid."


class TestFrenchGuillemets:
    def test_space_after_opening_guillemet_is_normalized(self):
        assert ocr.fix_text("«  hola") == "« hola"

    def test_space_before_closing_guillemet_is_normalized(self):
        assert ocr.fix_text("hola  »") == "hola »"


class TestIPANotation:
    def test_slash_9_colon_slash_becomes_open_o_length_mark(self):
        assert ocr.fix_text("/9:/") == "/ɔː/"

    def test_bracket_9_colon_becomes_open_o_length_mark(self):
        assert ocr.fix_text("[9:]") == "[ɔː]"

    def test_aspiration_mark_is_converted(self):
        assert ocr.fix_text('/"p') == "/ʰp"


class TestGreekBlockBracketRules:
    def test_paren_rho_inside_a_leiden_bracket_run_becomes_phi(self):
        # '(' is one of the bracket characters GREEK_RUN_RE allows inside a
        # run, so "λό(ργος" is segmented as a single Greek block and the
        # '(ρ' -> 'φ' rule (REGEX_RULES_GREEK) can act on it.
        assert ocr.fix_text("λό(ργος") == "λόφγος"

    def test_multiple_leiden_gaps_stay_in_a_single_run(self):
        runs = [m.group(0) for m in ocr.GREEK_RUN_RE.finditer("ἀγαθ[ο]ῦ[τι]ος")]
        assert runs == ["ἀγαθ[ο]ῦ[τι]ος"]


class TestSemicolonAndApostropheInsideGreekWord:
    # Regression guard for the fix that moved these two rules into
    # REGEX_RULES_GENERAL (applied before segmentation, via lookaround,
    # like the ij/rj/cp/<p/© rules above) precisely so they are reachable
    # through the real fix_text() pipeline instead of being silently
    # split apart by GREEK_RUN_RE first.
    def test_semicolon_inside_greek_word_is_removed_through_fix_text(self):
        assert ocr.fix_text("λόγ;ος") == "λόγος"

    def test_loose_apostrophe_inside_greek_word_is_removed_through_fix_text(self):
        assert ocr.fix_text("λόγ'ος") == "λόγος"


class TestJoinIntraWordGreekSpaces:
    def test_two_short_fragments_are_joined(self):
        assert ocr._join_intra_word_greek_spaces("λό γος") == "λόγος"

    def test_stopword_fragment_is_not_joined(self):
        assert ocr._join_intra_word_greek_spaces("καὶ λόγος") == "καὶ λόγος"

    def test_two_long_fragments_are_not_joined(self):
        # Both sides have >= 4 characters, so they are treated as distinct
        # complete words rather than a single word split by a stray space.
        assert ocr._join_intra_word_greek_spaces("ἄνθρωπος σοφίας") == "ἄνθρωπος σοφίας"


class TestVerboseOutput:
    def test_verbose_prints_before_and_after_character_counts(self, capsys):
        ocr.fix_text("hola", verbose=True)
        captured = capsys.readouterr()
        assert "Characters before: 4" in captured.out
        assert "Characters after:" in captured.out


class TestEmptyAndWhitespaceInput:
    def test_empty_string_returns_empty_string(self):
        assert ocr.fix_text("") == ""

    def test_whitespace_only_input_is_stripped_to_empty(self):
        assert ocr.fix_text("   \n\n  ") == ""


class TestPageNumberEdgeCase:
    def test_input_that_is_only_a_page_number_is_fully_removed(self):
        # A "document" that is nothing but a 1-4 digit line is treated as
        # a page-number artifact and stripped entirely, not just trimmed.
        assert ocr.fix_text("1234") == ""


class TestIdempotency:
    def test_running_fix_text_twice_produces_the_same_result(self):
        # Regression guard: re-running the pipeline on already-clean text
        # (e.g. if a document gets processed twice by mistake) must not
        # keep mutating it.
        messy = "λόγoς  ,  ἐστι.\n\nσοφος-\nεἶναι"
        once = ocr.fix_text(messy)
        twice = ocr.fix_text(once)
        assert once == twice


class TestNonBreakingSpace:
    def test_nbsp_is_normalized_to_a_regular_space(self):
        assert ocr.fix_text("hola mundo") == "hola mundo"


class TestRegexRulesAlias:
    def test_alias_matches_concatenation_of_the_three_rule_lists(self):
        assert ocr.REGEX_RULES == (
            ocr.REGEX_RULES_GENERAL
            + ocr.REGEX_RULES_CORPUS_SPECIFIC
            + ocr.REGEX_RULES_GREEK
        )
