from __future__ import annotations

import pytest

from typing import Any

from app.exports.registry import (
    ExportFormatter,
    ExportFormatterRegistry,
    ExportProcessor,
    ExportProcessorRegistry,
    parse_processor_order,
)


class ExampleProcessor(ExportProcessor):
    @property
    def name(self) -> str:
        return "merge_tags"

    def process(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return list(docs)


class OtherProcessor(ExportProcessor):
    @property
    def name(self) -> str:
        return "other"

    def process(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return list(docs)


class ExampleFormatter(ExportFormatter):
    @property
    def format_name(self) -> str:
        return "json_items"

    def format(self, docs: list[dict[str, Any]]) -> str:
        return "[]"


class OtherFormatter(ExportFormatter):
    @property
    def format_name(self) -> str:
        return "json_snapshot_payload"

    def format(self, docs: list[dict[str, Any]]) -> str:
        return "{}"


def test_processor_registry_rejects_duplicates() -> None:
    registry = ExportProcessorRegistry()
    registry.register(ExampleProcessor())
    with pytest.raises(ValueError, match="Duplicate export processor"):
        registry.register(ExampleProcessor())


def test_processor_registry_rejects_unknown() -> None:
    registry = ExportProcessorRegistry()
    with pytest.raises(ValueError, match="Unknown export processor"):
        registry.get("missing")


def test_formatter_registry_rejects_duplicates() -> None:
    registry = ExportFormatterRegistry()
    registry.register(ExampleFormatter())
    with pytest.raises(ValueError, match="Duplicate export formatter"):
        registry.register(ExampleFormatter())


def test_formatter_registry_rejects_unknown() -> None:
    registry = ExportFormatterRegistry()
    with pytest.raises(ValueError, match="Unknown export format"):
        registry.create("missing")


def test_parse_processor_order_is_whitespace_tolerant() -> None:
    value = " merge_tags , other ,,  "
    assert parse_processor_order(value) == ["merge_tags", "other"]


def test_resolve_chain_prefers_request_override() -> None:
    registry = ExportProcessorRegistry()
    registry.register(ExampleProcessor())
    registry.register(OtherProcessor())
    resolved = registry.resolve_chain(["other"], ["merge_tags"])
    assert [p.name for p in resolved] == ["other"]


def test_resolve_chain_uses_default_order_when_missing() -> None:
    registry = ExportProcessorRegistry()
    registry.register(ExampleProcessor())
    registry.register(OtherProcessor())
    resolved = registry.resolve_chain(None, ["merge_tags", "other"])
    assert [p.name for p in resolved] == ["merge_tags", "other"]
