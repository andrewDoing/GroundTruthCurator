"""PII detection service for ground truth items during bulk import.

This service scans text fields for potential personally identifiable information (PII)
and returns warnings. PII detection is informational only - it does not block imports.

Phase 1 (MVP): Email addresses, US phone numbers
Phase 2 (Future): SSN, credit cards, names via Microsoft Presidio
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from pydantic import BaseModel, Field

from app.domain.models import GroundTruthItem


class PIIWarning(BaseModel):
    """Warning about potential PII detected in a ground truth item."""

    item_id: str = Field(description="Item identifier")
    field: str = Field(
        description="Field name where PII was detected (e.g., 'synthQuestion', 'history[2].msg')"
    )
    pattern_type: str = Field(description="Type of PII detected ('email' or 'phone')")
    snippet: str = Field(description="Masked context snippet showing the detected PII")
    position: int = Field(description="Character position where the PII was found")


@dataclass(frozen=True)
class PIIPattern:
    """Configuration for a PII detection pattern."""

    name: str
    pattern: re.Pattern[str]
    # How many characters of context to show around the match
    context_chars: int = 20


# Phase 1 PII patterns
# Email pattern: user@domain.tld with ≥95% precision target
EMAIL_PATTERN = PIIPattern(
    name="email",
    pattern=re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE),
)

# US Phone pattern: Multiple formats including (555) 123-4567, 555-123-4567, +1 555 123 4567
PHONE_PATTERN = PIIPattern(
    name="phone",
    pattern=re.compile(r"(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}"),
)

# All patterns to check (Phase 1)
PII_PATTERNS: list[PIIPattern] = [EMAIL_PATTERN, PHONE_PATTERN]


def _mask_match(match_text: str, pattern_type: str) -> str:
    """Mask detected PII while preserving context.

    Examples:
        email: "user@example.com" -> "u***@e***e.com"
        phone: "(555) 123-4567" -> "(5**) ***-****"
    """
    if pattern_type == "email":
        # Mask email while preserving structure
        parts = match_text.split("@")
        if len(parts) == 2:
            local, domain = parts
            masked_local = local[0] + "***" if local else "***"
            domain_parts = domain.rsplit(".", 1)
            if len(domain_parts) == 2:
                domain_name, tld = domain_parts
                masked_domain = (
                    domain_name[0] + "***" + domain_name[-1] if len(domain_name) > 1 else "***"
                )
                return f"{masked_local}@{masked_domain}.{tld}"
            return f"{masked_local}@***"
        return "***@***"
    elif pattern_type == "phone":
        # Mask phone number digits while preserving formatting
        result = []
        digit_count = 0
        for char in match_text:
            if char.isdigit():
                # Keep first digit, mask the rest
                if digit_count == 0:
                    result.append(char)
                else:
                    result.append("*")
                digit_count += 1
            else:
                result.append(char)
        return "".join(result)
    return "***"


def _create_snippet(
    text: str, match_start: int, match_end: int, masked_match: str, context_chars: int = 20
) -> str:
    """Create a snippet with masked PII and surrounding context.

    Returns a string like: "...context [MASKED_PII] context..."
    """
    # Get context before
    before_start = max(0, match_start - context_chars)
    before = text[before_start:match_start]
    if before_start > 0:
        before = "..." + before.lstrip()

    # Get context after
    after_end = min(len(text), match_end + context_chars)
    after = text[match_end:after_end]
    if after_end < len(text):
        after = after.rstrip() + "..."

    return f"{before}[{masked_match}]{after}"


def scan_text_for_pii(text: str, field_name: str, item_id: str) -> list[PIIWarning]:
    """Scan a single text field for PII patterns.

    Args:
        text: The text content to scan
        field_name: Name of the field (for reporting)
        item_id: ID of the item containing this field

    Returns:
        List of PIIWarning objects for detected PII
    """
    if not text:
        return []

    warnings: list[PIIWarning] = []

    for pii_pattern in PII_PATTERNS:
        for match in pii_pattern.pattern.finditer(text):
            match_text = match.group(0)
            masked = _mask_match(match_text, pii_pattern.name)
            snippet = _create_snippet(
                text,
                match.start(),
                match.end(),
                masked,
                pii_pattern.context_chars,
            )
            warnings.append(
                PIIWarning(
                    item_id=item_id,
                    field=field_name,
                    pattern_type=pii_pattern.name,
                    snippet=snippet,
                    position=match.start(),
                )
            )

    return warnings


def scan_item_for_pii(item: GroundTruthItem) -> list[PIIWarning]:
    """Scan a ground truth item for PII in all relevant fields.

    Phase 1 scans:
    - synth_question
    - edited_question
    - answer
    - comment
    - history[].msg

    Args:
        item: The ground truth item to scan

    Returns:
        List of PIIWarning objects for all detected PII
    """
    item_id = item.id or "(no ID)"
    warnings: list[PIIWarning] = []

    # Scan primary text fields
    if item.synth_question:
        warnings.extend(scan_text_for_pii(item.synth_question, "synthQuestion", item_id))

    if item.edited_question:
        warnings.extend(scan_text_for_pii(item.edited_question, "editedQuestion", item_id))

    if item.answer:
        warnings.extend(scan_text_for_pii(item.answer, "answer", item_id))

    if item.comment:
        warnings.extend(scan_text_for_pii(item.comment, "comment", item_id))

    # Scan history messages
    if item.history:
        for idx, turn in enumerate(item.history):
            if turn.msg:
                warnings.extend(scan_text_for_pii(turn.msg, f"history[{idx}].msg", item_id))

    return warnings


def scan_bulk_items_for_pii(items: Sequence[GroundTruthItem]) -> list[PIIWarning]:
    """Scan multiple ground truth items for PII.

    This is the main entry point for bulk import PII detection.

    Args:
        items: List of ground truth items to scan

    Returns:
        List of PIIWarning objects for all detected PII across all items
    """
    all_warnings: list[PIIWarning] = []

    for item in items:
        warnings = scan_item_for_pii(item)
        all_warnings.extend(warnings)

    return all_warnings
