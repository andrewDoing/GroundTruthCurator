from __future__ import annotations

import json
from typing import Any, AsyncIterator

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import ContentSettings

from app.exports.storage.base import ExportStorage


class BlobExportStorage(ExportStorage):
    def __init__(self, account_url: str, container_name: str) -> None:
        self._credential = DefaultAzureCredential()
        self._service_client = BlobServiceClient(account_url, credential=self._credential)
        self._container_client = self._service_client.get_container_client(container_name)

    async def write_json(self, key: str, obj: dict[str, Any]) -> None:
        payload = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        await self.write_bytes(key, payload, "application/json")

    async def write_bytes(self, key: str, data: bytes, content_type: str) -> None:
        blob_client = self._container_client.get_blob_client(key)
        await blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        blob_client = self._container_client.get_blob_client(key)
        downloader = await blob_client.download_blob()

        async def iterator() -> AsyncIterator[bytes]:
            async for chunk in downloader.chunks():
                yield chunk

        return iterator()

    async def list_prefix(self, prefix: str) -> list[str]:
        names: list[str] = []
        async for blob in self._container_client.list_blobs(name_starts_with=prefix):
            names.append(blob.name)
        return names

    async def close(self) -> None:
        await self._container_client.close()
        await self._service_client.close()
        await self._credential.close()
