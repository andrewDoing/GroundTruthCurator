"""Unit tests for the dataset computed tag plugin."""

from __future__ import annotations

import pytest

from app.plugins.computed_tags.dataset import DatasetPlugin
from tests.test_helpers import make_test_entry


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
        item = make_test_entry(id="test-id", dataset_name=dataset_name)
        assert plugin.compute(item) == expected_tag
