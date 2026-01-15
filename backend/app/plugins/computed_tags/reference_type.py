"""Computed tag plugins for reference type classification.

This module provides plugins that tag documents based on the types
of references they contain (article vs helpcenter).

Reference types are derived from URL patterns:
- Article: URLs containing a CS# pattern (e.g., CS431120)
  Example: https://docs.example.com/support/article/CS431120
- Helpcenter: URLs containing /help in path
  Example: https://support.example.com/help/product/page.html
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.plugins.base import ComputedTagPlugin

if TYPE_CHECKING:
    from app.domain.models import GroundTruthItem, Reference

# Pattern for article references: CS followed by digits (e.g., CS431120)
_ARTICLE_PATTERN = re.compile(r"CS\d+", re.IGNORECASE)


def _is_article_url(url: str) -> bool:
    """Check if a URL is an article reference.

    Article URLs contain a CS# pattern (e.g., CS431120).

    Args:
        url: The URL to check.

    Returns:
        True if the URL matches the article pattern.
    """
    return bool(_ARTICLE_PATTERN.search(url))


def _is_helpcenter_url(url: str) -> bool:
    """Check if a URL is a helpcenter reference.

    Helpcenter URLs contain '/help' in the path.

    Args:
        url: The URL to check.

    Returns:
        True if the URL contains '/help'.
    """
    return "/help" in url.lower()


def _get_all_references(doc: GroundTruthItem) -> list[Reference]:
    """Get all references from a document, including those in history turns.

    Args:
        doc: The GroundTruthItem to evaluate.

    Returns:
        A list of all Reference objects from the document.
    """
    refs: list[Reference] = list(doc.refs or [])

    # Also gather refs from history turns
    if doc.history:
        for turn in doc.history:
            if turn.refs:
                refs.extend(turn.refs)

    return refs


def _has_article_reference(doc: GroundTruthItem) -> bool:
    """Check if document has at least one article reference.

    Args:
        doc: The GroundTruthItem to evaluate.

    Returns:
        True if at least one reference URL matches the article pattern.
    """
    refs = _get_all_references(doc)
    return any(_is_article_url(ref.url) for ref in refs)


def _has_helpcenter_reference(doc: GroundTruthItem) -> bool:
    """Check if document has at least one helpcenter reference.

    Args:
        doc: The GroundTruthItem to evaluate.

    Returns:
        True if at least one reference URL contains '/help'.
    """
    refs = _get_all_references(doc)
    return any(_is_helpcenter_url(ref.url) for ref in refs)


class ReferenceTypeArticlePlugin(ComputedTagPlugin):
    """Tags documents that contain an article reference.

    Applies the 'reference_type:article' tag if the document has at least
    one reference URL containing a CS# pattern (e.g., CS431120).
    """

    @property
    def tag_key(self) -> str:
        return "reference_type:article"

    def compute(self, doc: GroundTruthItem) -> str | None:
        return self.tag_key if _has_article_reference(doc) else None


class ReferenceTypeHelpcenterPlugin(ComputedTagPlugin):
    """Tags documents that contain a helpcenter reference.

    Applies the 'reference_type:helpcenter' tag if the document has at least
    one reference URL containing '/help' in the path.
    """

    @property
    def tag_key(self) -> str:
        return "reference_type:helpcenter"

    def compute(self, doc: GroundTruthItem) -> str | None:
        return self.tag_key if _has_helpcenter_reference(doc) else None
