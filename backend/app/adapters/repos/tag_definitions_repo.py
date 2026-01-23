from __future__ import annotations

from typing import Any, Protocol
import asyncio
from datetime import datetime, timezone

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

from app.domain.models import TagDefinition


class TagDefinitionsRepo(Protocol):
    async def get_definition(self, tag_key: str) -> TagDefinition | None: ...
    async def list_all(self) -> list[TagDefinition]: ...
    async def upsert(self, definition: TagDefinition) -> TagDefinition: ...
    async def delete(self, tag_key: str) -> None: ...


class CosmosTagDefinitionsRepo:
    """Cosmos adapter for storing custom tag definitions.

    Container partition key: /tag_key
    Document id: same as tag_key for simple 1:1 mapping
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
        self._db = self._client.get_database_client(self._db_name)
        self._container = self._db.get_container_client(self._container_name)

    async def _ensure(self) -> None:
        if self._client is None or self._container is None:
            await self._init()

    async def validate_container(self) -> None:
        """Validate that the database and tag_definitions container exist.

        Raises:
            RuntimeError: If database or container doesn't exist with guidance on how to fix.
        """
        await self._ensure()
        assert self._db is not None
        assert self._container is not None

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
                f"    --gt-container --assignments-container --tags-container --tag-definitions-container\n"
            )

        try:
            await self._container.read()
        except CosmosResourceNotFoundError:
            raise RuntimeError(
                f"Cosmos DB tag_definitions container '{self._container_name}' does not exist. "
                f"Run the container initialization script first:\n\n"
                f"  uv run python scripts/cosmos_container_manager.py \\ \n"
                f"    --endpoint {self._endpoint} \\ \n"
                f"    --key <your-key> --no-verify \\ \n"
                f"    --db {self._db_name} \\ \n"
                f"    --gt-container --assignments-container --tags-container --tag-definitions-container\n"
            )

    async def get_definition(self, tag_key: str) -> TagDefinition | None:
        """Retrieve a tag definition by tag_key.

        Args:
            tag_key: The tag key (e.g., "source:custom_value")

        Returns:
            TagDefinition if found, None otherwise
        """
        await self._ensure()
        try:
            assert self._container is not None
            doc = await self._container.read_item(item=tag_key, partition_key=tag_key)  # type: ignore
            return TagDefinition.model_validate(doc)
        except CosmosHttpResponseError as e:
            if getattr(e, "status_code", None) == 404:
                return None
            raise

    async def list_all(self) -> list[TagDefinition]:
        """List all custom tag definitions.

        Returns:
            List of TagDefinition objects
        """
        await self._ensure()
        assert self._container is not None

        query = "SELECT * FROM c WHERE c.docType = 'tag-definition'"
        items = []

        async for item in self._container.query_items(
            query=query, enable_scan_in_query=True
        ):  # type: ignore
            try:
                items.append(TagDefinition.model_validate(item))
            except Exception:
                # Skip malformed items
                continue

        return items

    async def upsert(self, definition: TagDefinition) -> TagDefinition:
        """Create or update a tag definition.

        Args:
            definition: The tag definition to store

        Returns:
            The stored TagDefinition with updated timestamp
        """
        await self._ensure()

        # Ensure id matches tag_key
        definition.id = definition.tag_key
        # Update timestamp
        definition.updated_at = datetime.now(timezone.utc)

        body = definition.model_dump(by_alias=True)
        # Add partition key field for Cosmos
        body["tag_key"] = definition.tag_key

        assert self._container is not None
        result = await self._container.upsert_item(body)  # type: ignore
        return TagDefinition.model_validate(result)

    async def delete(self, tag_key: str) -> None:
        """Delete a tag definition by tag_key.

        Args:
            tag_key: The tag key to delete

        Raises:
            CosmosResourceNotFoundError: If the tag definition doesn't exist
        """
        await self._ensure()
        assert self._container is not None
        await self._container.delete_item(item=tag_key, partition_key=tag_key)  # type: ignore
