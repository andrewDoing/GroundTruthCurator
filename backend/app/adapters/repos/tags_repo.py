from __future__ import annotations

from typing import Any, Iterable, Protocol
import asyncio

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError


class TagsRepo(Protocol):
    async def get_global_tags(self) -> list[str]: ...
    async def save_global_tags(self, tags: list[str]) -> list[str]: ...
    async def upsert_add(self, tags_to_add: Iterable[str]) -> list[str]: ...
    async def upsert_remove(self, tags_to_remove: Iterable[str]) -> list[str]: ...


class CosmosTagsRepo:
    """Minimal Cosmos adapter storing a single global tags document in its own container.

    Container partition key: /pk with a single logical partition value "global".
    Document id: "tags|global" with shape:
        { id, docType: "tags", pk: "global", tags: ["group:value", ...] }
    """

    def __init__(
        self,
        endpoint: str,
        key: str | None,
        db_name: str,
        container_name: str,
        connection_verify: bool | str | None = None,
        credential: Any | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._key = key
        self._credential = credential
        self._db_name = db_name
        self._container_name = container_name
        self._connection_verify = connection_verify
        self._client: CosmosClient | None = None
        # Use Any to avoid hard dependency on azure SDK typing details while keeping mypy happy
        self._db: Any = None
        self._container: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def _init(self) -> None:
        if self._client is None:
            if self._credential is not None:
                self._client = CosmosClient(
                    self._endpoint,
                    credential=self._credential,
                    connection_verify=self._connection_verify,
                )
            else:
                assert self._key is not None
                self._client = CosmosClient(
                    self._endpoint, self._key, connection_verify=self._connection_verify
                )
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = None
        # Get database client (database is created by infrastructure/test fixtures)
        self._db = self._client.get_database_client(self._db_name)
        # Get container client (container is created by infrastructure/test fixtures)
        self._container = self._db.get_container_client(self._container_name)

    async def _ensure(self) -> None:
        if self._client is None or self._container is None:
            await self._init()

    async def validate_container(self) -> None:
        """Validate that the database and tags container exist.

        Raises:
            RuntimeError: If database or container doesn't exist with guidance on how to fix.
        """
        await self._ensure()
        assert self._db is not None
        assert self._container is not None

        # Verify database exists (provides clearer error if missing)
        try:
            await self._db.read()
        except CosmosResourceNotFoundError:
            raise RuntimeError(
                f"Cosmos DB database '{self._db_name}' does not exist. "
                f"Run the container initialization script first:\n\n"
                f"  uv run python scripts/cosmos_container_manager.py \\ \n"
                f"    --endpoint {self._endpoint} \\ \n"
                f"    --key <your-key> --no-verify \\ \n"
                f"    --db {self._db_name} \\ \n"
                f"    --gt-container --assignments-container --tags-container\n"
            )

        try:
            await self._container.read()
        except CosmosResourceNotFoundError:
            raise RuntimeError(
                f"Cosmos DB tags container '{self._container_name}' does not exist. "
                f"Run the container initialization script first:\n\n"
                f"  uv run python scripts/cosmos_container_manager.py \\ \n"
                f"    --endpoint {self._endpoint} \\ \n"
                f"    --key <your-key> --no-verify \\ \n"
                f"    --db {self._db_name} \\ \n"
                f"    --gt-container --assignments-container --tags-container\n"
            )

    @property
    def _doc_id(self) -> str:
        return "tags|global"

    @property
    def _pk(self) -> str:
        return "global"

    async def get_global_tags(self) -> list[str]:
        await self._ensure()
        try:
            assert self._container is not None
            doc = await self._container.read_item(item=self._doc_id, partition_key=self._pk)  # type: ignore
            arr = doc.get("tags") or []
            if isinstance(arr, list):
                return [str(t) for t in arr]
            return []
        except CosmosHttpResponseError as e:
            if getattr(e, "status_code", None) == 404:
                return []
            raise

    async def save_global_tags(self, tags: list[str]) -> list[str]:
        await self._ensure()
        body: dict[str, Any] = {
            "id": self._doc_id,
            "docType": "tags",
            "pk": self._pk,
            "tags": list(tags),
        }
        assert self._container is not None
        await self._container.upsert_item(body)  # type: ignore
        return list(tags)

    async def upsert_add(self, tags_to_add: Iterable[str]) -> list[str]:
        current = set(await self.get_global_tags())
        for t in tags_to_add:
            current.add(str(t))
        res = sorted(current)
        return await self.save_global_tags(res)

    async def upsert_remove(self, tags_to_remove: Iterable[str]) -> list[str]:
        current = set(await self.get_global_tags())
        remove = {str(t) for t in tags_to_remove}
        res = sorted(current - remove)
        return await self.save_global_tags(res)
