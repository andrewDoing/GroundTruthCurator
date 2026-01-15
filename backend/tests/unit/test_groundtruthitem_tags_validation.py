import pytest

from app.domain.models import GroundTruthItem


BASE = dict(id="id1", datasetName="ds", synthQuestion="What is this product?")


def make_item(**overrides):
    data = {**BASE, **overrides}
    # Allow both field names and aliases; Pydantic config handles this
    return GroundTruthItem(**data)


def test_model_accepts_valid_tag_set():
    it = make_item(manualTags=["source:sme", "topic:general"])
    assert it.tags == ["source:sme", "topic:general"]


def test_model_allows_unknown_group():
    it = make_item(manualTags=["unknown:foo"])
    assert it.tags == ["unknown:foo"]


def test_model_enforces_exclusive_groups():
    with pytest.raises(Exception):
        make_item(manualTags=["source:sme", "source:user"])


def test_model_allows_multiple_topics():
    it = make_item(manualTags=["topic:general", "topic:simulation"])
    assert it.tags == ["topic:general", "topic:simulation"]
