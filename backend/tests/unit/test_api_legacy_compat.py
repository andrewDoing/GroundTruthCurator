from app.api.v1._legacy_compat import apply_legacy_compat_fields
from app.domain.models import AgenticGroundTruthEntry


def test_apply_legacy_compat_fields_resets_total_references_on_refs_update() -> None:
    item = AgenticGroundTruthEntry(
        id="test-1",
        datasetName="test",
        totalReferences=7,
        refs=[{"url": "https://existing.example"}],
    )

    apply_legacy_compat_fields(
        item,
        {"refs": [{"url": "https://updated.example"}, {"url": "https://updated-2.example"}]},
    )

    assert len(item.refs) == 2
    assert item.totalReferences == 0
