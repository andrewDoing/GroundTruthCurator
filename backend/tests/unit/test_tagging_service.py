import pytest

from app.services.tagging_service import (
    normalize_tag,
    parse_tag,
    validate_tags,
)
from app.domain.tags import TAG_SCHEMA


def test_normalize_tag_trims_and_lowercases():
    assert normalize_tag("  Source : SME  ") == "source:sme"


def test_parse_tag_rejects_malformed():
    with pytest.raises(ValueError):
        parse_tag("no-sep")


def test_validate_tags_allows_unknown_group():
    # With relaxed validation, unknown group is allowed as long as format is valid
    assert validate_tags(["unknown:foo"]) == ["unknown:foo"]


def test_validate_tags_allows_unknown_value_in_known_group():
    # With relaxed validation, unknown value in a known group is allowed, but
    # exclusivity/dependency rules still apply when relevant
    assert validate_tags(["source:experimental"]) == ["source:experimental"]


def test_mutual_exclusivity_allows_single_source_only():
    with pytest.raises(ValueError) as e:
        validate_tags(["source:sme", "source:synthetic"])
    assert "Group 'source' is exclusive" in str(e.value)


def test_multi_select_topic_allows_multiple():
    tags = validate_tags(["topic:general", "topic:simulation"])
    assert tags == ["topic:general", "topic:simulation"]


def test_dedup_and_sort_is_deterministic():
    tags = validate_tags(["Topic:General", "topic:general", "source:sme"])
    assert tags == ["source:sme", "topic:general"]


def test_schema_registry_exposes_expected_groups():
    assert "source" in TAG_SCHEMA
    assert "sme" in TAG_SCHEMA["source"].values


def test_rules_are_applied_in_validation():
    with pytest.raises(ValueError):
        validate_tags(["source:sme", "source:other"])  # exclusivity rule
