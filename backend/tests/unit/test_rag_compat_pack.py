"""Unit tests for RagCompatPack plugin contracts and migration helpers.

Core-generic behavior stays covered elsewhere. This file focuses on:
- runtime-backed pack registration and registry presence
- stable helper contracts for retrieval/reference ownership
- compat-migration helpers that still project legacy payloads while the shim exists
"""

from __future__ import annotations

import pytest

from app.domain.models import AgenticGroundTruthEntry, Reference
from app.plugins.packs.rag_compat import RagCompatPack, _RAG_COMPAT_KIND
from app.plugins.pack_registry import (
    get_default_pack_registry,
    reset_default_pack_registry,
)


# ---------------------------------------------------------------------------
# validate_registration
# ---------------------------------------------------------------------------


def test_validate_registration_passes():
    """RagCompatPack registers successfully when constants are in sync."""
    pack = RagCompatPack()
    pack.validate_registration()  # should not raise


def test_validate_registration_name_matches_host_model_constant():
    """The pack name must equal AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN."""
    from app.domain.models import AgenticGroundTruthEntry

    pack = RagCompatPack()
    assert pack.name == AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN


def test_validate_registration_kind_constant_correct():
    """_RAG_COMPAT_KIND must match the host model constant."""
    from app.domain.models import AgenticGroundTruthEntry

    assert _RAG_COMPAT_KIND == AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN


def test_validate_registration_fails_on_constant_mismatch(monkeypatch: pytest.MonkeyPatch):
    """validate_registration() must raise ValueError if constants diverge."""
    pack = RagCompatPack()
    # Simulate a rename of the host-model constant
    monkeypatch.setattr(AgenticGroundTruthEntry, "_RAG_COMPAT_PLUGIN", "rag-v2")
    with pytest.raises(ValueError, match="does not match"):
        pack.validate_registration()


# ---------------------------------------------------------------------------
# Plugin-contract: approval hooks
# ---------------------------------------------------------------------------


def _generic_item() -> AgenticGroundTruthEntry:
    return AgenticGroundTruthEntry(
        id="gen-001",
        datasetName="generic-dataset",
        history=[
            {"role": "user", "msg": "What is 2+2?"},
            {"role": "assistant", "msg": "4"},
        ],
    )


def _rag_item() -> AgenticGroundTruthEntry:
    return AgenticGroundTruthEntry.model_validate(
        {
            "id": "rag-001",
            "datasetName": "rag-dataset",
            "synthQuestion": "What is retrieval?",
            "answer": "Retrieval is finding relevant docs.",
            "refs": [{"url": "https://example.com/doc"}],
        }
    )


def test_collect_approval_errors_generic_item_empty():
    pack = RagCompatPack()
    item = _generic_item()
    assert pack.collect_approval_errors(item) == []


def test_collect_approval_errors_rag_item_empty():
    """RAG items currently produce no additional pack-level errors."""
    pack = RagCompatPack()
    item = _rag_item()
    assert pack.collect_approval_errors(item) == []


# ---------------------------------------------------------------------------
# Plugin-contract: helper accessors
# ---------------------------------------------------------------------------


def test_rag_compat_data_empty_for_generic_item():
    pack = RagCompatPack()
    item = _generic_item()
    assert pack.rag_compat_data(item) == {}


def test_rag_compat_data_populated_for_rag_item():
    pack = RagCompatPack()
    item = _rag_item()
    data = pack.rag_compat_data(item)
    # The model_validator moves synthQuestion, answer, refs into rag-compat plugin data
    assert data  # non-empty


def test_rag_compat_data_contains_synth_question():
    pack = RagCompatPack()
    item = _rag_item()
    data = pack.rag_compat_data(item)
    assert "synthQuestion" in data
    assert data["synthQuestion"] == "What is retrieval?"


# ---------------------------------------------------------------------------
# refs_from_item accessor
# ---------------------------------------------------------------------------


def test_refs_from_item_empty_for_generic_item():
    pack = RagCompatPack()
    item = _generic_item()
    assert pack.refs_from_item(item) == []


def test_refs_from_item_populated_for_rag_item():
    pack = RagCompatPack()
    item = _rag_item()
    refs = pack.refs_from_item(item)
    assert len(refs) == 1
    assert isinstance(refs[0], Reference)
    assert refs[0].url == "https://example.com/doc"


def test_refs_from_item_flattens_per_call_retrieval_state():
    pack = RagCompatPack()
    item = AgenticGroundTruthEntry.model_validate(
        {
            "id": "rag-002",
            "datasetName": "rag-dataset",
            "toolCalls": [{"id": "tc-1", "name": "search", "callType": "tool", "stepNumber": 2}],
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "data": {
                        "retrievals": {
                            "tc-1": {
                                "candidates": [
                                    {
                                        "url": "https://example.com/candidate",
                                        "title": "Candidate",
                                        "chunk": "retrieved chunk",
                                    }
                                ]
                            }
                        }
                    },
                }
            },
        }
    )

    refs = pack.refs_from_item(item)
    assert len(refs) == 1
    assert refs[0].url == "https://example.com/candidate"
    assert refs[0].content == "retrieved chunk"
    assert refs[0].messageIndex == 2


# ---------------------------------------------------------------------------
# Plugin-contract: reference ownership helpers
# ---------------------------------------------------------------------------


def test_attach_reference_adds_to_rag_item():
    pack = RagCompatPack()
    item = _rag_item()
    initial_count = len(pack.refs_from_item(item))
    new_ref = Reference(url="https://newdoc.example.com/page")
    result = pack.attach_reference(item, new_ref)
    assert result is item  # mutated in-place
    assert len(pack.refs_from_item(item)) == initial_count + 1
    urls = [r.url for r in pack.refs_from_item(item)]
    assert "https://newdoc.example.com/page" in urls


def test_attach_reference_works_on_generic_item():
    pack = RagCompatPack()
    item = _generic_item()
    new_ref = Reference(url="https://docs.example.com/a")
    pack.attach_reference(item, new_ref)
    # The ref is written to rag-compat plugin payload via the setter
    refs = pack.refs_from_item(item)
    assert len(refs) == 1
    assert refs[0].url == "https://docs.example.com/a"


def test_detach_reference_removes_by_url():
    pack = RagCompatPack()
    item = _rag_item()
    target_url = "https://example.com/doc"
    assert any(r.url == target_url for r in pack.refs_from_item(item))

    result = pack.detach_reference(item, target_url)
    assert result is item
    assert not any(r.url == target_url for r in pack.refs_from_item(item))


def test_detach_reference_nonexistent_url_is_noop():
    pack = RagCompatPack()
    item = _rag_item()
    before = len(pack.refs_from_item(item))
    pack.detach_reference(item, "https://nonexistent.example.com")
    assert len(pack.refs_from_item(item)) == before


def test_replace_references_clears_per_call_retrieval_state():
    pack = RagCompatPack()
    item = AgenticGroundTruthEntry.model_validate(
        {
            "id": "rag-003",
            "datasetName": "rag-dataset",
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "data": {
                        "retrievals": {
                            "tc-1": {
                                "candidates": [{"url": "https://example.com/old"}]
                            }
                        }
                    },
                }
            },
        }
    )

    pack.replace_references(item, [Reference(url="https://example.com/new")])

    assert pack.has_per_call_state(item) is False
    refs = pack.refs_from_item(item)
    assert len(refs) == 1
    assert refs[0].url == "https://example.com/new"


def test_export_transform_projects_retrieval_candidates_to_refs():
    pack = RagCompatPack()
    transform = pack.get_export_transforms()[0].transform

    projected = transform(
        {
            "id": "rag-004",
            "datasetName": "rag-dataset",
            "toolCalls": [{"id": "tc-1", "stepNumber": 1}],
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "data": {
                        "retrievals": {
                            "tc-1": {
                                "candidates": [
                                    {
                                        "url": "https://example.com/exported",
                                        "title": "Exported",
                                        "chunk": "retrieved chunk",
                                    }
                                ]
                            }
                        }
                    },
                }
            },
        }
    )

    assert projected["totalReferences"] == 1
    assert projected["refs"][0]["url"] == "https://example.com/exported"
    assert projected["refs"][0]["messageIndex"] == 1


# ---------------------------------------------------------------------------
# Runtime-backed registry seam
# ---------------------------------------------------------------------------


def test_default_pack_registry_contains_rag_compat():
    reset_default_pack_registry()
    try:
        registry = get_default_pack_registry()
        assert "rag-compat" in registry.names()
    finally:
        reset_default_pack_registry()


def test_default_pack_registry_validates_without_error():
    reset_default_pack_registry()
    try:
        registry = get_default_pack_registry()
        registry.validate_all()  # should not raise
    finally:
        reset_default_pack_registry()


def test_default_pack_registry_singleton_stable():
    reset_default_pack_registry()
    try:
        r1 = get_default_pack_registry()
        r2 = get_default_pack_registry()
        assert r1 is r2
    finally:
        reset_default_pack_registry()
