"""Unit tests for RagCompatPack plugin contracts and reference ownership."""

from __future__ import annotations

import pytest

from app.domain.models import AgenticGroundTruthEntry, Reference
from app.plugins.pack_registry import get_default_pack_registry, reset_default_pack_registry
from app.plugins.packs.rag_compat import RagCompatPack, _RAG_COMPAT_KIND


def test_validate_registration_passes():
    pack = RagCompatPack()
    pack.validate_registration()


def test_validate_registration_name_matches_host_model_constant():
    from app.domain.models import AgenticGroundTruthEntry

    pack = RagCompatPack()
    assert pack.name == AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN


def test_validate_registration_kind_constant_correct():
    from app.domain.models import AgenticGroundTruthEntry

    assert _RAG_COMPAT_KIND == AgenticGroundTruthEntry._RAG_COMPAT_PLUGIN


def test_validate_registration_fails_on_constant_mismatch(monkeypatch: pytest.MonkeyPatch):
    pack = RagCompatPack()
    monkeypatch.setattr(AgenticGroundTruthEntry, "_RAG_COMPAT_PLUGIN", "rag-v2")
    with pytest.raises(ValueError, match="does not match"):
        pack.validate_registration()


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
            "history": [
                {"role": "user", "msg": "What is retrieval?"},
                {"role": "assistant", "msg": "Retrieval is finding relevant docs."},
            ],
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "version": "1.0",
                    "data": {
                        "references": [{"url": "https://example.com/doc"}],
                    },
                }
            },
        }
    )


def test_collect_approval_errors_are_empty():
    pack = RagCompatPack()
    assert pack.collect_approval_errors(_generic_item()) == []
    assert pack.collect_approval_errors(_rag_item()) == []


def test_rag_compat_data_empty_for_generic_item():
    pack = RagCompatPack()
    assert pack.rag_compat_data(_generic_item()) == {}


def test_rag_compat_data_contains_only_references_for_owned_payload():
    pack = RagCompatPack()
    data = pack.rag_compat_data(_rag_item())
    assert list(data.keys()) == ["references"]


def test_refs_from_item_empty_for_generic_item():
    pack = RagCompatPack()
    assert pack.refs_from_item(_generic_item()) == []


def test_refs_from_item_reads_owned_references():
    pack = RagCompatPack()
    refs = pack.refs_from_item(_rag_item())
    assert len(refs) == 1
    assert isinstance(refs[0], Reference)
    assert refs[0].url == "https://example.com/doc"


def test_get_search_documents_includes_stable_id():
    pack = RagCompatPack()
    docs = pack.get_search_documents(_rag_item())
    assert len(docs) == 1
    assert docs[0]["id"] == "rag-001:ref:0"
    assert docs[0]["url"] == "https://example.com/doc"


def test_refs_from_item_reads_legacy_retrieval_payloads():
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


def test_attach_reference_adds_to_rag_item():
    pack = RagCompatPack()
    item = _rag_item()
    initial_count = len(pack.refs_from_item(item))
    new_ref = Reference(url="https://newdoc.example.com/page")
    result = pack.attach_reference(item, new_ref)
    assert result is item
    assert len(pack.refs_from_item(item)) == initial_count + 1


def test_attach_reference_writes_owned_references_key():
    pack = RagCompatPack()
    item = _generic_item()
    pack.attach_reference(item, Reference(url="https://docs.example.com/a"))
    assert item.plugins["rag-compat"].data == {
        "references": [{"url": "https://docs.example.com/a", "bonus": False}]
    }


def test_detach_reference_removes_by_url():
    pack = RagCompatPack()
    item = _rag_item()
    result = pack.detach_reference(item, "https://example.com/doc")
    assert result is item
    assert pack.refs_from_item(item) == []


def test_replace_references_clears_legacy_fields():
    pack = RagCompatPack()
    item = AgenticGroundTruthEntry.model_validate(
        {
            "id": "rag-003",
            "datasetName": "rag-dataset",
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "data": {
                        "refs": [{"url": "https://example.com/old"}],
                        "retrievals": {
                            "tc-1": {"candidates": [{"url": "https://example.com/legacy"}]}
                        },
                        "totalReferences": 2,
                        "synthQuestion": "legacy",
                    },
                }
            },
        }
    )

    pack.replace_references(item, [Reference(url="https://example.com/new")])

    assert item.plugins["rag-compat"].data == {
        "references": [{"url": "https://example.com/new", "bonus": False}]
    }


def test_import_transform_normalizes_legacy_fields_to_history_and_references():
    pack = RagCompatPack()
    transform = pack.get_import_transforms()[0].transform

    normalized = transform(
        {
            "id": "legacy-001",
            "datasetName": "rag-dataset",
            "editedQuestion": "What is retrieval?",
            "answer": "Retrieval finds relevant docs.",
            "refs": [{"url": "https://example.com/doc"}],
        }
    )

    assert normalized["history"] == [
        {"role": "user", "msg": "What is retrieval?"},
        {"role": "assistant", "msg": "Retrieval finds relevant docs."},
    ]
    assert normalized["plugins"]["rag-compat"]["data"] == {
        "references": [{"url": "https://example.com/doc", "bonus": False}]
    }


def test_export_transform_projects_references_and_count():
    pack = RagCompatPack()
    transform = pack.get_export_transforms()[0].transform

    projected = transform(
        {
            "id": "rag-004",
            "datasetName": "rag-dataset",
            "plugins": {
                "rag-compat": {
                    "kind": "rag-compat",
                    "data": {"references": [{"url": "https://example.com/exported"}]},
                }
            },
        }
    )

    assert projected["totalReferences"] == 1
    assert projected["references"][0]["url"] == "https://example.com/exported"


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
        registry.validate_all()
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
