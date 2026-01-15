"""Unit tests for the reference type computed tag plugins."""

from __future__ import annotations

import pytest

from app.domain.models import GroundTruthItem, Reference
from app.plugins.computed_tags.reference_type import (
    ReferenceTypeArticlePlugin,
    ReferenceTypeHelpcenterPlugin,
    _is_article_url,
    _is_helpcenter_url,
)


class TestUrlPatternDetection:
    """Tests for URL pattern detection helpers."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://docs.example.com/support/article/CS431120", True),
            ("https://docs.example.com/en/support/article/cs999999", True),  # Case insensitive
            ("https://docs.example.com/support/page", False),
            ("https://support.example.com/help/product/page.html", False),
        ],
    )
    def test_article_url_detection(self, url, expected):
        """Article URLs contain CS# pattern."""
        assert _is_article_url(url) == expected

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://support.example.com/help/product/page.html", True),
            ("https://SUPPORT.EXAMPLE.COM/help/page.html", True),  # Case insensitive
            ("https://docs.example.com/support/article/CS431120", False),
            ("https://example.com/other", False),
        ],
    )
    def test_helpcenter_url_detection(self, url, expected):
        """Helpcenter URLs contain /help in the path."""
        assert _is_helpcenter_url(url) == expected


class TestReferenceTypePlugins:
    """Tests for reference type plugins."""

    def test_no_refs_gets_no_tags(self):
        """Item with no refs should get neither tag."""
        item = GroundTruthItem(
            id="test-no-refs",
            datasetName="test-dataset",
            synthQuestion="Question",
        )
        assert ReferenceTypeArticlePlugin().compute(item) is None
        assert ReferenceTypeHelpcenterPlugin().compute(item) is None

    def test_item_can_have_both_tags(self):
        """Item with both reference types should get both tags."""
        item = GroundTruthItem(
            id="test-both",
            datasetName="test-dataset",
            synthQuestion="Question",
            refs=[
                Reference(url="https://docs.example.com/support/article/CS431120"),
                Reference(url="https://support.example.com/help/product/page.html"),
            ],
        )
        assert ReferenceTypeArticlePlugin().compute(item) == "reference_type:article"
        assert ReferenceTypeHelpcenterPlugin().compute(item) == "reference_type:helpcenter"

    def test_type_field_is_ignored(self):
        """Only URL matters, not the type field on Reference."""
        item = GroundTruthItem(
            id="test-type-ignored",
            datasetName="test-dataset",
            synthQuestion="Question",
            refs=[Reference(url="https://example.com/page", type="article")],
        )
        # URL doesn't match article pattern, so no tag even though type="article"
        assert ReferenceTypeArticlePlugin().compute(item) is None
