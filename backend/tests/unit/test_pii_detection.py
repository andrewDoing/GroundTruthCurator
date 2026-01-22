"""Unit tests for PII detection service.

Tests cover:
- Email detection patterns
- US phone number detection patterns
- Masking behavior
- Snippet generation
- Field scanning for GroundTruthItem
- Bulk scanning
- Edge cases
"""

import pytest

from app.services.pii_service import (
    PIIWarning,
    scan_text_for_pii,
    scan_item_for_pii,
    scan_bulk_items_for_pii,
    _mask_match,
    _create_snippet,
    EMAIL_PATTERN,
    PHONE_PATTERN,
)
from app.domain.models import GroundTruthItem, HistoryItem
from app.domain.enums import HistoryItemRole


class TestEmailDetection:
    """Tests for email address detection."""

    @pytest.mark.parametrize(
        "email",
        [
            "user@example.com",
            "test.user@domain.org",
            "name+tag@company.co.uk",
            "UPPERCASE@DOMAIN.COM",
            "user123@test-domain.net",
            "a@b.co",  # Minimal valid email
        ],
    )
    def test_detects_valid_emails(self, email: str):
        """Should detect various valid email formats."""
        warnings = scan_text_for_pii(f"Contact me at {email} please", "field", "item-1")
        assert len(warnings) == 1
        assert warnings[0].pattern_type == "email"
        assert warnings[0].item_id == "item-1"
        assert warnings[0].field == "field"

    @pytest.mark.parametrize(
        "text",
        [
            "No email here",
            "user@",
            "@domain.com",
            "user@domain",  # No TLD
            "not an email",
        ],
    )
    def test_ignores_invalid_patterns(self, text: str):
        """Should not flag invalid email patterns."""
        warnings = scan_text_for_pii(text, "field", "item-1")
        assert len(warnings) == 0

    def test_detects_multiple_emails_in_text(self):
        """Should detect multiple emails in the same text."""
        text = "Contact alice@example.com or bob@company.org for support"
        warnings = scan_text_for_pii(text, "field", "item-1")
        assert len(warnings) == 2
        assert all(w.pattern_type == "email" for w in warnings)


class TestPhoneDetection:
    """Tests for US phone number detection."""

    @pytest.mark.parametrize(
        "phone",
        [
            "(555) 123-4567",
            "555-123-4567",
            "555.123.4567",
            "555 123 4567",
            "+1 555 123 4567",
            "+1-555-123-4567",
            "1-555-123-4567",
            "5551234567",
        ],
    )
    def test_detects_valid_phone_formats(self, phone: str):
        """Should detect various US phone number formats."""
        warnings = scan_text_for_pii(f"Call us at {phone} today", "field", "item-1")
        assert len(warnings) == 1
        assert warnings[0].pattern_type == "phone"

    @pytest.mark.parametrize(
        "text",
        [
            "No phone here",
            "123-456",  # Too short
            "12-345-6789",  # Wrong format
            "Call 911 for emergency",  # 3 digits
        ],
    )
    def test_ignores_invalid_patterns(self, text: str):
        """Should not flag invalid phone patterns."""
        warnings = scan_text_for_pii(text, "field", "item-1")
        assert len(warnings) == 0

    def test_detects_multiple_phones_in_text(self):
        """Should detect multiple phone numbers in the same text."""
        text = "Call (555) 123-4567 or 555-987-6543 for support"
        warnings = scan_text_for_pii(text, "field", "item-1")
        assert len(warnings) == 2
        assert all(w.pattern_type == "phone" for w in warnings)


class TestMasking:
    """Tests for PII masking behavior."""

    def test_masks_email_preserving_structure(self):
        """Email masking should preserve basic structure."""
        masked = _mask_match("user@example.com", "email")
        assert "@" in masked
        assert "." in masked
        assert "user" not in masked.lower()
        # First char of local part preserved
        assert masked.startswith("u")

    def test_masks_phone_preserving_structure(self):
        """Phone masking should preserve formatting."""
        masked = _mask_match("(555) 123-4567", "phone")
        assert "(" in masked
        assert ")" in masked
        assert "-" in masked
        # First digit preserved
        assert masked[1] == "5"
        # Other digits masked
        assert "*" in masked


class TestSnippetGeneration:
    """Tests for context snippet generation."""

    def test_creates_snippet_with_context(self):
        """Should create snippet with surrounding context."""
        text = "Please contact user@example.com for more information about your order"
        snippet = _create_snippet(text, 15, 31, "[MASKED]", context_chars=10)
        assert "contact" in snippet or "..." in snippet
        assert "[MASKED]" in snippet

    def test_handles_match_at_start(self):
        """Should handle PII at the start of text."""
        text = "user@example.com is our contact"
        snippet = _create_snippet(text, 0, 16, "[MASKED]", context_chars=10)
        assert "[MASKED]" in snippet

    def test_handles_match_at_end(self):
        """Should handle PII at the end of text."""
        text = "Contact us at user@example.com"
        snippet = _create_snippet(text, 14, 30, "[MASKED]", context_chars=10)
        assert "[MASKED]" in snippet


class TestGroundTruthItemScanning:
    """Tests for scanning GroundTruthItem fields."""

    def test_scans_synth_question(self):
        """Should detect PII in synthQuestion field."""
        item = GroundTruthItem(
            id="test-1",
            datasetName="test-dataset",
            synth_question="Contact alice@example.com for help",
        )
        warnings = scan_item_for_pii(item)
        assert len(warnings) == 1
        assert warnings[0].field == "synthQuestion"

    def test_scans_edited_question(self):
        """Should detect PII in editedQuestion field."""
        item = GroundTruthItem(
            id="test-1",
            datasetName="test-dataset",
            synth_question="Original question",
            edited_question="Contact support@company.org for assistance",
        )
        warnings = scan_item_for_pii(item)
        assert len(warnings) == 1
        assert warnings[0].field == "editedQuestion"

    def test_scans_answer(self):
        """Should detect PII in answer field."""
        item = GroundTruthItem(
            id="test-1",
            datasetName="test-dataset",
            synth_question="What is the contact?",
            answer="Call us at (555) 123-4567",
        )
        warnings = scan_item_for_pii(item)
        assert len(warnings) == 1
        assert warnings[0].field == "answer"

    def test_scans_comment(self):
        """Should detect PII in comment field."""
        item = GroundTruthItem(
            id="test-1",
            datasetName="test-dataset",
            synth_question="A question",
            comment="Reviewed by john@internal.com",
        )
        warnings = scan_item_for_pii(item)
        assert len(warnings) == 1
        assert warnings[0].field == "comment"

    def test_scans_history_messages(self):
        """Should detect PII in history messages."""
        item = GroundTruthItem(
            id="test-1",
            datasetName="test-dataset",
            synth_question="A question",
            history=[
                HistoryItem(role=HistoryItemRole.user, msg="Contact alice@example.com"),
                HistoryItem(role=HistoryItemRole.assistant, msg="Sure, I'll help you"),
                HistoryItem(role=HistoryItemRole.user, msg="Call me at 555-123-4567"),
            ],
        )
        warnings = scan_item_for_pii(item)
        assert len(warnings) == 2
        # Check field names include index
        fields = {w.field for w in warnings}
        assert "history[0].msg" in fields
        assert "history[2].msg" in fields

    def test_returns_empty_for_clean_item(self):
        """Should return empty list for item without PII."""
        item = GroundTruthItem(
            id="test-1",
            datasetName="test-dataset",
            synth_question="What is the weather like today?",
            answer="The weather is sunny and warm.",
        )
        warnings = scan_item_for_pii(item)
        assert len(warnings) == 0


class TestBulkScanning:
    """Tests for bulk item scanning."""

    def test_scans_multiple_items(self):
        """Should scan all items and aggregate warnings."""
        items = [
            GroundTruthItem(
                id="item-1",
                datasetName="test-dataset",
                synth_question="Contact alice@example.com",
            ),
            GroundTruthItem(
                id="item-2",
                datasetName="test-dataset",
                synth_question="No PII here",
            ),
            GroundTruthItem(
                id="item-3",
                datasetName="test-dataset",
                synth_question="Call (555) 123-4567",
            ),
        ]
        warnings = scan_bulk_items_for_pii(items)
        assert len(warnings) == 2
        item_ids = {w.item_id for w in warnings}
        assert "item-1" in item_ids
        assert "item-3" in item_ids

    def test_handles_empty_list(self):
        """Should return empty list for empty input."""
        warnings = scan_bulk_items_for_pii([])
        assert len(warnings) == 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_handles_empty_text(self):
        """Should handle empty/None text gracefully."""
        warnings = scan_text_for_pii("", "field", "item-1")
        assert len(warnings) == 0

        warnings = scan_text_for_pii(None, "field", "item-1")  # type: ignore
        assert len(warnings) == 0

    def test_handles_item_without_id(self):
        """Should handle item with missing/blank ID."""
        item = GroundTruthItem(
            id="",
            datasetName="test-dataset",
            synth_question="Contact user@example.com",
        )
        # Need to set id after construction since blank is usually generated
        item.id = ""
        warnings = scan_item_for_pii(item)
        assert len(warnings) == 1
        assert warnings[0].item_id == "(no ID)"

    def test_mixed_pii_types_in_single_field(self):
        """Should detect multiple PII types in the same field."""
        text = "Email alice@example.com or call (555) 123-4567"
        warnings = scan_text_for_pii(text, "field", "item-1")
        assert len(warnings) == 2
        types = {w.pattern_type for w in warnings}
        assert "email" in types
        assert "phone" in types

    def test_warning_model_serialization(self):
        """PIIWarning should serialize correctly."""
        warning = PIIWarning(
            item_id="test-1",
            field="synthQuestion",
            pattern_type="email",
            snippet="...[u***@e***e.com]...",
            position=10,
        )
        data = warning.model_dump()
        assert data["item_id"] == "test-1"
        assert data["field"] == "synthQuestion"
        assert data["pattern_type"] == "email"
        assert data["snippet"] == "...[u***@e***e.com]..."
        assert data["position"] == 10
