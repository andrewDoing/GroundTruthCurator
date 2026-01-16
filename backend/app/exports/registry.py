from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class ExportProcessor(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def process(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform documents and return a new list."""
        pass


class ExportFormatter(ABC):
    @property
    @abstractmethod
    def format_name(self) -> str:
        pass

    @abstractmethod
    def format(self, docs: list[dict[str, Any]]) -> bytes | str:
        """Serialize documents to bytes or string."""
        pass


class ExportProcessorRegistry:
    def __init__(self) -> None:
        self._processors: dict[str, ExportProcessor] = {}

    def register(self, processor: ExportProcessor) -> None:
        name = processor.name
        if name in self._processors:
            raise ValueError(f"Duplicate export processor '{name}'")
        self._processors[name] = processor

    def get(self, name: str) -> ExportProcessor:
        processor = self._processors.get(name)
        if processor is None:
            raise ValueError(f"Unknown export processor '{name}'")
        return processor

    def resolve_chain(
        self, requested: list[str] | None, default_order: list[str] | None
    ) -> list[ExportProcessor]:
        names = requested if requested is not None else (default_order or [])
        return [self.get(name) for name in names]


class ExportFormatterRegistry:
    def __init__(self) -> None:
        self._formatters: dict[str, Callable[..., ExportFormatter]] = {}

    def register(self, formatter: ExportFormatter) -> None:
        name = formatter.format_name
        self.register_factory(name, lambda **_: formatter)

    def register_factory(self, name: str, factory: Callable[..., ExportFormatter]) -> None:
        if name in self._formatters:
            raise ValueError(f"Duplicate export formatter '{name}'")
        self._formatters[name] = factory

    def create(self, name: str, **kwargs: Any) -> ExportFormatter:
        factory = self._formatters.get(name)
        if factory is None:
            raise ValueError(f"Unknown export format '{name}'")
        return factory(**kwargs)


def parse_processor_order(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [part.strip() for part in value.split(",")]
    return [part for part in parts if part]
