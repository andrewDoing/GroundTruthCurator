from __future__ import annotations

from app.exports.processors.merge_tags import MergeTagsProcessor


def test_merge_tags_unions_and_sorts() -> None:
    processor = MergeTagsProcessor()
    docs = [
        {
            "id": "1",
            "manualTags": ["b", "a"],
            "computedTags": ["c", "b"],
        }
    ]
    result = processor.process(docs)
    assert result[0]["tags"] == ["a", "b", "c"]
    assert result[0]["manualTags"] == ["b", "a"]
    assert result[0]["computedTags"] == ["c", "b"]
