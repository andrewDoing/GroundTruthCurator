"""Unit tests for legacy retrieval compatibility normalization."""

from __future__ import annotations

from app.domain.models import AgenticGroundTruthEntry, Reference
from app.plugins.packs.rag_compat import RagCompatPack


class TestLegacyRetrievalCompatibility:
    def test_refs_from_item_flattens_legacy_retrieval_candidates(self):
        pack = RagCompatPack()
        item = AgenticGroundTruthEntry.model_validate(
            {
                "id": "test-item",
                "datasetName": "ds",
                "history": [
                    {"role": "user", "msg": "hi"},
                    {"role": "assistant", "msg": "hello"},
                ],
                "toolCalls": [
                    {"id": "tc-1", "name": "search", "callType": "tool", "stepNumber": 1}
                ],
                "plugins": {
                    "rag-compat": {
                        "kind": "rag-compat",
                        "version": "1.0",
                        "data": {
                            "retrievals": {
                                "tc-1": {
                                    "candidates": [
                                        {"url": "https://a.com", "title": "A", "chunk": "chunk-a"},
                                        {"url": "https://b.com", "title": "B", "chunk": "chunk-b"},
                                    ]
                                }
                            }
                        },
                    }
                },
            }
        )

        refs = pack.refs_from_item(item)
        assert [ref.url for ref in refs] == ["https://a.com", "https://b.com"]
        assert [ref.messageIndex for ref in refs] == [1, 1]

    def test_replace_references_rewrites_payload_to_owned_references(self):
        pack = RagCompatPack()
        item = AgenticGroundTruthEntry.model_validate(
            {
                "id": "test-item",
                "datasetName": "ds",
                "plugins": {
                    "rag-compat": {
                        "kind": "rag-compat",
                        "version": "1.0",
                        "data": {
                            "retrievals": {"tc-1": {"candidates": [{"url": "https://legacy.com"}]}}
                        },
                    }
                },
            }
        )

        pack.replace_references(item, [Reference(url="https://normalized.com")])

        assert item.plugins["rag-compat"].data == {
            "references": [{"url": "https://normalized.com", "bonus": False}]
        }
