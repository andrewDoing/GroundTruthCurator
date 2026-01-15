"""
Unit tests for Unicode character normalization for Cosmos DB emulator.
Validates that the _normalize_unicode_for_cosmos function correctly replaces
problematic Unicode characters with ASCII equivalents.
"""

import pytest
from unittest.mock import patch

from app.adapters.repos.cosmos_repo import _normalize_unicode_for_cosmos


@pytest.fixture
def mock_enabled_setting():
    """Fixture to enable Unicode normalization for tests."""
    with patch("app.adapters.repos.cosmos_repo.settings") as mock_settings:
        mock_settings.COSMOS_DISABLE_UNICODE_ESCAPE = True
        yield mock_settings


@pytest.fixture
def mock_disabled_setting():
    """Fixture to disable Unicode normalization for tests."""
    with patch("app.adapters.repos.cosmos_repo.settings") as mock_settings:
        mock_settings.COSMOS_DISABLE_UNICODE_ESCAPE = False
        yield mock_settings


def test_smart_quotes(mock_enabled_setting):
    """Test that smart quotes are replaced with regular quotes."""
    input_text = "She said \u201chello\u201d and \u2018goodbye\u2019"
    expected = "She said \"hello\" and 'goodbye'"
    result = _normalize_unicode_for_cosmos(input_text)
    assert result == expected


def test_dashes(mock_enabled_setting):
    """Test that em and en dashes are replaced with hyphens."""
    input_text = "Range: 1\u201310 and summary\u2014conclusion"
    expected = "Range: 1-10 and summary--conclusion"
    result = _normalize_unicode_for_cosmos(input_text)
    assert result == expected


def test_ellipsis(mock_enabled_setting):
    """Test that ellipsis is replaced with three periods."""
    input_text = "Wait\u2026 what?"
    expected = "Wait... what?"
    result = _normalize_unicode_for_cosmos(input_text)
    assert result == expected


def test_nested_structure(mock_enabled_setting):
    """Test that normalization works recursively on nested structures."""
    input_data = {
        "question": "What\u2019s the \u201cbest\u201d approach?",
        "history": [
            {"role": "user", "content": "Tell me about this product\u2019s features\u2026"},
            {"role": "assistant", "content": "Here\u2019s what I know\u2014it\u2019s great!"},
        ],
        "refs": [{"title": "Article: \u201cIntroduction\u201d", "url": "https://example.com"}],
    }

    result = _normalize_unicode_for_cosmos(input_data)

    assert result["question"] == 'What\'s the "best" approach?'
    assert result["history"][0]["content"] == "Tell me about this product's features..."
    assert result["history"][1]["content"] == "Here's what I know--it's great!"
    assert result["refs"][0]["title"] == 'Article: "Introduction"'


def test_preserves_other_unicode(mock_enabled_setting):
    """Test that other Unicode (emojis, accents, non-Latin) are preserved."""
    input_text = "café, résumé, 你好, 😀🎉 product®"
    result = _normalize_unicode_for_cosmos(input_text)
    # Should preserve these characters since they're not in the replacement dict
    assert "café" in result
    assert "résumé" in result
    assert "你好" in result
    # Emojis should be preserved (not in replacement dict)
    assert "😀" in result or "🎉" in result


def test_disabled_flag(mock_disabled_setting):
    """Test that normalization is skipped when flag is False."""
    input_text = "She said \u201chello\u201d"
    result = _normalize_unicode_for_cosmos(input_text)

    # Should return unchanged when disabled
    assert result == input_text


def test_returns_non_string_types_unchanged(mock_enabled_setting):
    """Test that non-string types are returned unchanged."""
    # Numbers
    assert _normalize_unicode_for_cosmos(42) == 42
    assert _normalize_unicode_for_cosmos(3.14) == 3.14

    # Booleans and None
    assert _normalize_unicode_for_cosmos(True) is True
    assert _normalize_unicode_for_cosmos(False) is False
    assert _normalize_unicode_for_cosmos(None) is None


def test_empty_structures(mock_enabled_setting):
    """Test handling of empty strings, lists, and dicts."""
    assert _normalize_unicode_for_cosmos("") == ""
    assert _normalize_unicode_for_cosmos([]) == []
    assert _normalize_unicode_for_cosmos({}) == {}
