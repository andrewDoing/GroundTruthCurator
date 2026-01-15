from app.domain.models import DatasetCurationInstructions


def test_curation_model_aliases_and_etag_serialization():
    doc = DatasetCurationInstructions(
        id="curation-instructions|ds1",
        datasetName="ds1",
        instructions="Hello world",
    )
    # ETag default None but serialized as _etag alias when present
    data = doc.model_dump(mode="json", by_alias=True)
    assert data["id"] == "curation-instructions|ds1"
    assert data["datasetName"] == "ds1"
    assert data["docType"] == "curation-instructions"
    assert data["schemaVersion"] == "v1"
    # Set etag and ensure alias mapping
    doc.etag = "abc123"
    data = doc.model_dump(mode="json", by_alias=True)
    assert data["_etag"] == "abc123"
