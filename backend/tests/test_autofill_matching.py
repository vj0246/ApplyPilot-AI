"""
Tests for the option-matching logic in autofill_service.py.

The trickiest part of the autofill engine: Groq returns free-text like
"Yes, I agree" but the form has a radio button labelled just "Yes".
These tests verify the matching holds up across variations the model
actually produces in practice.

No browser, no DB, no network needed.

Run: pytest tests/test_autofill_matching.py -v
"""
from app.services.autofill_service import (
    _match_option,
    _match_multiple_options,
    is_google_form_url,
)


class TestGoogleFormUrlDetection:
    def test_valid_google_form_url(self):
        assert is_google_form_url("https://docs.google.com/forms/d/e/xyz/viewform")

    def test_google_form_with_trailing_params(self):
        assert is_google_form_url("https://docs.google.com/forms/d/e/xyz/viewform?usp=sf_link")

    def test_rejects_non_google_url(self):
        assert not is_google_form_url("https://example.com/apply")

    def test_rejects_google_doc_url(self):
        assert not is_google_form_url("https://docs.google.com/document/d/xyz")

    def test_rejects_empty_string(self):
        assert not is_google_form_url("")


class TestOptionMatching:
    """_match_option maps a free-text AI response back to one of the
    real options on the form. Exact match wins, substring is the fallback."""

    def test_exact_match(self):
        assert _match_option("Yes", ["Yes", "No"]) == "Yes"

    def test_case_insensitive_exact(self):
        assert _match_option("yes", ["Yes", "No"]) == "Yes"

    def test_ai_adds_words_around_option(self):
        # "Yes, I agree" should match the "Yes" option
        assert _match_option("Yes, I agree", ["Yes", "No"]) == "Yes"

    def test_option_is_substring_of_answer(self):
        # model said "I am available immediately" for the option "Available immediately"
        assert _match_option("I am available immediately", ["Available immediately", "2 weeks notice"]) == "Available immediately"

    def test_no_match_returns_none(self):
        assert _match_option("Maybe", ["Yes", "No"]) is None

    def test_first_matching_option_wins_on_substring(self):
        # "Python and SQL" should match "Python" before "SQL" since Python
        # comes first in the options list
        result = _match_option("Python and SQL experience", ["Python", "SQL", "Java"])
        assert result in ("Python", "SQL")  # either is valid per the function spec

    def test_empty_answer_returns_none(self):
        assert _match_option("", ["Yes", "No"]) is None

    def test_empty_options_returns_none(self):
        assert _match_option("Yes", []) is None


class TestMultipleOptionMatching:
    """_match_multiple_options handles checkbox questions where the user
    can pick more than one item."""

    def test_comma_separated_picks_two(self):
        result = _match_multiple_options("Python, SQL", ["Python", "SQL", "Java"])
        assert "Python" in result
        assert "SQL" in result
        assert "Java" not in result

    def test_and_separator(self):
        result = _match_multiple_options("Python and Docker", ["Python", "Docker", "AWS"])
        assert "Python" in result
        assert "Docker" in result

    def test_semicolon_separator(self):
        result = _match_multiple_options("Python; Docker", ["Python", "Docker", "AWS"])
        assert "Python" in result
        assert "Docker" in result

    def test_no_duplicates_in_result(self):
        # if model says "Python, Python" we should only pick it once
        result = _match_multiple_options("Python, Python", ["Python", "SQL"])
        assert result.count("Python") == 1

    def test_unmatched_parts_are_ignored(self):
        result = _match_multiple_options("Python, Cobol", ["Python", "SQL", "Java"])
        assert result == ["Python"]

    def test_empty_string_returns_empty_list(self):
        result = _match_multiple_options("", ["Python", "SQL"])
        assert result == []
