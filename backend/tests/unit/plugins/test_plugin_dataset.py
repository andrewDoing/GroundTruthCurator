"""Unit tests for the dataset computed tag plugin."""

from __future__ import annotations

import pytest

from app.domain.models import GroundTruthItem
from app.plugins.computed_tags.dataset import DatasetPlugin


class TestDatasetPlugin:
    """Tests for the DatasetPlugin."""

    def test_tag_key_is_dynamic_placeholder(self):
        """Plugin uses _dynamic placeholder since actual tag varies."""
        plugin = DatasetPlugin()
        assert plugin.tag_key == "dataset:_dynamic"

    @pytest.mark.parametrize(
        "dataset_name,expected_tag",
        [
            ("simple", "dataset:simple"),
            ("with-dashes", "dataset:with-dashes"),
            ("with_underscores", "dataset:with_underscores"),
            ("CamelCase", "dataset:CamelCase"),
            ("version.1.0", "dataset:version.1.0"),
            ("support-tickets", "dataset:support-tickets"),
        ],
    )
    def test_compute_returns_dataset_prefixed_tag(self, dataset_name, expected_tag):
        """compute() returns 'dataset:' prefix with the dataset name."""
        plugin = DatasetPlugin()
        item = GroundTruthItem(
            id="test-id",
            datasetName=dataset_name,
            synthQuestion="Question",
        )
        assert plugin.compute(item) == expected_tag
