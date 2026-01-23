from __future__ import annotations
from typing import Optional, Any
import asyncio
from datetime import datetime, timezone
import os
from uuid import UUID, uuid4
import random
import logging
import math
import re
import unicodedata
import time
import json

from fastapi import HTTPException
from app.core.config import settings

from azure.cosmos.aio import CosmosClient, DatabaseProxy, ContainerProxy
from azure.cosmos import ConsistencyLevel, documents as cosmos_documents
from azure.core import MatchConditions
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

from app.adapters.repos.base import GroundTruthRepo
from app.domain.models import (
    GroundTruthItem,
    Stats,
    AssignmentDocument,
    DatasetCurationInstructions,
    BulkImportResult,
    PaginationMetadata,
)
from app.domain.enums import GroundTruthStatus, SortField, SortOrder
from app.core.config import get_sampling_allocation


_SMART_PUNCT_REPLACEMENTS: dict[str, str] = {
    "\u201c": '"',  # Left double quotation mark
    "\u201d": '"',  # Right double quotation mark
    "\u2018": "'",  # Left single quotation mark
    "\u2019": "'",  # Right single quotation mark
    "\u2013": "-",  # En dash
    "\u2014": "--",  # Em dash
    "\u2026": "...",  # Horizontal ellipsis
}

_INVALID_ESCAPE_PATTERN = re.compile(r"\\(?![\"\\/bfnrt]|u[0-9a-fA-F]{4})")
_BACKSLASH_SENTINEL = "{{BACKSLASH}}"  # ASCII-safe placeholder
_CONTROL_CHAR_TRANSLATION = {
    **{ord(ch): "" for ch in ("\u200b", "\ufeff")},  # zero-width space & BOM
    **{ord(ch): " " for ch in (chr(i) for i in range(32)) if ch not in ("\n", "\r", "\t")},
    ord("\u007f"): " ",
}

# Cosmos DB SELECT clause for most GroundTruthItem fields used in several functions
# list_gt_paginated, _list_gt_paginated_with_emulator, list_gt_by_dataset
SELECT_CLAUSE_C = (
    "SELECT c.id, c.datasetName, c.bucket, c.status, c.docType, c.schemaVersion, "
    "c.curationInstructions, c.synthQuestion, c.editedQuestion, c.answer, c.refs, c.tags, c.manualTags, c.computedTags, c.comment, "
    "c.history, "
    "c.contextUsedForGeneration, c.contextSource, c.modelUsedForGeneration, "
    "c.semanticClusterNumber, c.weight, c.samplingBucket, c.questionLength, "
    "c.assignedTo, c.assignedAt, c.totalReferences, c.updatedAt, c.updatedBy, c.reviewedAt, c._etag "
)


class SortSecurityError(ValueError):
    """Raised when sort parameters fail security validation."""

    pass


def _base64_encode_refs_content(refs_list: list) -> list:
    """
    Base64-encode 'content' fields within refs array items.
    This works around Cosmos emulator bugs that reject certain character sequences.
    """
    import base64

    result = []
    for ref in refs_list:
        if isinstance(ref, dict):
            ref_copy = ref.copy()
            # Only encode content field if it's a non-empty string and not already encoded
            if (
                "content" in ref_copy
                and isinstance(ref_copy["content"], str)
                and ref_copy["content"]
                and not ref_copy.get("_contentEncoded")
            ):
                content_bytes = ref_copy["content"].encode("utf-8")
                ref_copy["content"] = base64.b64encode(content_bytes).decode("ascii")
                ref_copy["_contentEncoded"] = True
            result.append(ref_copy)
        else:
            result.append(ref)
    return result


def _base64_decode_refs_content(refs_list: list) -> list:
    """Reverse Base64 encoding of 'content' fields in refs array."""
    import base64

    result = []
    for ref in refs_list:
        if isinstance(ref, dict):
            ref_copy = ref.copy()
            # Decode if marked as encoded
            if ref_copy.get("_contentEncoded") and "content" in ref_copy:
                try:
                    content_bytes = base64.b64decode(ref_copy["content"])
                    ref_copy["content"] = content_bytes.decode("utf-8")
                    del ref_copy["_contentEncoded"]
                except Exception:
                    pass  # If decode fails, leave as-is
            result.append(ref_copy)
        else:
            result.append(ref)
    return result


def _sanitize_string_for_cosmos(value: str) -> str:
    """Normalize and sanitize strings so Cosmos emulator accepts them."""

    normalized = unicodedata.normalize("NFKC", value)
    if not normalized:
        return normalized

    # Strip problematic control characters and zero-width markers
    cleaned = normalized.translate(_CONTROL_CHAR_TRANSLATION)

    # Replace smart punctuation with ASCII fallbacks
    for old, new in _SMART_PUNCT_REPLACEMENTS.items():
        if old in cleaned:
            cleaned = cleaned.replace(old, new)

    if "\\" not in cleaned:
        return cleaned

    # Replace backslashes that would yield invalid JSON escape sequences with ASCII placeholder.
    return _INVALID_ESCAPE_PATTERN.sub(_BACKSLASH_SENTINEL, cleaned)


def _normalize_unicode_for_cosmos(obj: Any) -> Any:
    """
    Recursively sanitize strings to work around Cosmos emulator Unicode bugs.
    Also Base64-encodes 'content' fields in 'refs' arrays as a workaround.
    """

    if not settings.COSMOS_DISABLE_UNICODE_ESCAPE:
        return obj

    if isinstance(obj, str):
        return _sanitize_string_for_cosmos(obj)
    if isinstance(obj, dict):
        normalized = {}
        for k, v in obj.items():
            # Special handling for 'refs' array - encode content fields
            if k == "refs" and isinstance(v, list):
                # First normalize the refs
                normalized_refs = [_normalize_unicode_for_cosmos(item) for item in v]
                # Then Base64-encode content fields in refs
                normalized[k] = _base64_encode_refs_content(normalized_refs)
            else:
                normalized[k] = _normalize_unicode_for_cosmos(v)
        return normalized
    if isinstance(obj, list):
        return [_normalize_unicode_for_cosmos(item) for item in obj]
    return obj


def _restore_unicode_from_cosmos(obj: Any) -> Any:
    """
    Reverse emulator-only sanitization markers after fetching documents.
    Also Base64-decodes 'content' fields in 'refs' arrays.
    """

    if not settings.COSMOS_DISABLE_UNICODE_ESCAPE:
        return obj

    if isinstance(obj, str):
        if _BACKSLASH_SENTINEL in obj:
            return obj.replace(_BACKSLASH_SENTINEL, "\\")
        return obj
    if isinstance(obj, dict):
        restored = {}
        for k, v in obj.items():
            # Special handling for 'refs' array - decode content fields
            if k == "refs" and isinstance(v, list):
                # First decode Base64-encoded content fields
                decoded_refs = _base64_decode_refs_content(v)
                # Then restore backslash sentinels
                restored[k] = [_restore_unicode_from_cosmos(item) for item in decoded_refs]
            else:
                restored[k] = _restore_unicode_from_cosmos(v)
        return restored
    if isinstance(obj, list):
        return [_restore_unicode_from_cosmos(item) for item in obj]
    return obj


class CosmosGroundTruthRepo(GroundTruthRepo):
    """
    Cosmos DB (SQL API) implementation of GroundTruthRepo using async SDK.

    Partition key strategy: MultiHash hierarchical key on [/datasetName, /bucket].
    The `bucket` field is a UUID and is stored as its string representation in documents
    and when passed as the partition key value.
    """

    def __init__(
        self,
        endpoint: str,
        key: str | None,
        db_name: str,
        gt_container_name: str,
        assignments_container_name: str,
        connection_verify: bool | str | None = None,
        test_mode: bool = False,
        credential: Any | None = None,
    ):
        # Defer CosmosClient creation to _init so the underlying aiohttp session binds
        # to the event loop of the running app (avoids cross-loop RuntimeError in tests).
        self._endpoint = endpoint
        self._key = key
        self._credential = credential
        self._connection_verify = connection_verify
        self._client: CosmosClient | None = None
        self._db_name = db_name
        self._gt_container_name = gt_container_name
        self._assignments_container_name = assignments_container_name
        self._test_mode = test_mode
        self._db: DatabaseProxy | None = None
        self._gt_container: ContainerProxy | None = None
        self._assignments_container: ContainerProxy | None = None
        # Track the event loop on which the aiohttp client/session was created to
        # guard against cross-loop usage during tests.
        self._loop: asyncio.AbstractEventLoop | None = None  # set in _init on first use
        self._logger = logging.getLogger(__name__)

    def _build_connection_policy(self) -> cosmos_documents.ConnectionPolicy:
        policy = cosmos_documents.ConnectionPolicy()
        if settings.COSMOS_MAX_CONNECTION_POOL_SIZE > 0:
            setattr(policy, "MaxConnectionPoolSize", int(settings.COSMOS_MAX_CONNECTION_POOL_SIZE))
        if settings.COSMOS_REQUEST_TIMEOUT > 0:
            policy.RequestTimeout = int(settings.COSMOS_REQUEST_TIMEOUT)
        policy.EnableEndpointDiscovery = bool(settings.COSMOS_ENABLE_ENDPOINT_DISCOVERY)
        retry_cls = getattr(cosmos_documents, "RetryOptions", None)
        if retry_cls is None:
            self._logger.warning("Cosmos RetryOptions unavailable; using SDK defaults")
            return policy
        retry_kwargs: dict[str, Any] = {}
        if settings.COSMOS_RETRY_TOTAL_ATTEMPTS > 0:
            retry_kwargs["max_retry_attempt_count"] = int(settings.COSMOS_RETRY_TOTAL_ATTEMPTS)
        if settings.COSMOS_RETRY_FIXED_INTERVAL > 0:
            retry_kwargs["fixed_retry_interval_in_milliseconds"] = int(
                settings.COSMOS_RETRY_FIXED_INTERVAL * 1000
            )
        retry = retry_cls(**retry_kwargs)
        policy.RetryOptions = retry
        return policy

    async def _init(self):
        # Ensure database exists
        if self._client is None:
            # connection_verify can be False for emulator self-signed cert, True/str for real certs/CA bundle
            policy = self._build_connection_policy()

            if self._key is not None:
                self._client = CosmosClient(
                    url=self._endpoint,
                    credential=self._key,
                    connection_verify=self._connection_verify,
                    connection_policy=policy,
                    consistency_level=ConsistencyLevel.Session,
                )
            elif self._credential is not None:
                # Prefer AAD credential when provided (Managed Identity)
                self._client = CosmosClient(
                    url=self._endpoint,
                    credential=self._credential,
                    connection_verify=self._connection_verify,
                    connection_policy=policy,
                    consistency_level=ConsistencyLevel.Session,
                )
            else:
                # Fallback to key-based auth (emulator/local dev)
                raise ValueError("Either key or credential must be provided for CosmosClient")
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # Fallback if called outside of a running loop
                self._loop = None
        # Get database client (database is created by infrastructure/test fixtures)
        self._db = self._client.get_database_client(self._db_name)

        # Get container clients (containers are created by infrastructure/test fixtures)
        self._gt_container = self._db.get_container_client(self._gt_container_name)
        self._assignments_container = self._db.get_container_client(
            self._assignments_container_name
        )

    async def validate_containers(self) -> None:
        """Validate that the database and required containers exist.

        Raises:
            RuntimeError: If database or containers don't exist with guidance on how to fix.
        """
        if self._client is None:
            await self._init()

        assert self._db is not None
        assert self._gt_container is not None
        assert self._assignments_container is not None

        missing: list[str] = []

        # Check database exists
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

        # Check ground truth container
        try:
            await self._gt_container.read()
        except CosmosResourceNotFoundError:
            missing.append(self._gt_container_name)

        # Check assignments container
        try:
            await self._assignments_container.read()
        except CosmosResourceNotFoundError:
            missing.append(self._assignments_container_name)

        if missing:
            raise RuntimeError(
                f"Cosmos DB containers not found: {', '.join(missing)}. "
                f"Run the container initialization script first:\n\n"
                f"  uv run python scripts/cosmos_container_manager.py \\ \n"
                f"    --endpoint {self._endpoint} \\ \n"
                f"    --key <your-key> --no-verify \\ \n"
                f"    --db {self._db_name} \\ \n"
                f"    --gt-container --assignments-container --tags-container\n"
            )

        self._logger.info(
            "Cosmos DB validation passed: database=%s, containers=%s",
            self._db_name,
            [self._gt_container_name, self._assignments_container_name],
        )

    @staticmethod
    def _ensure_utf8_strings(obj: Any) -> Any:
        """
        Normalize Unicode characters to work around Cosmos emulator bugs.
        When COSMOS_DISABLE_UNICODE_ESCAPE is True, replaces smart quotes, em dashes,
        and other problematic Unicode with ASCII equivalents.

        This prevents "unsupported unicode escape sequences" errors with the emulator.
        """
        return _normalize_unicode_for_cosmos(obj)

    @staticmethod
    def _is_invalid_json_payload_error(error: Exception) -> bool:
        message = getattr(error, "message", None) or str(error) or ""
        return "invalid input syntax for type json" in message.lower()

    @staticmethod
    def _sanitize_doc_for_emulator_retry(doc: dict[str, Any]) -> dict[str, Any]:
        sanitized = CosmosGroundTruthRepo._ensure_utf8_strings(doc)
        try:
            return json.loads(json.dumps(sanitized, ensure_ascii=True))
        except Exception:
            return sanitized

    @staticmethod
    def _compute_total_references(item: GroundTruthItem) -> int:
        """Calculate total reference count from item.refs and item.history[].refs.

        Replicates the logic from the original computed field.
        """
        # Count refs in all history turns
        history_refs = sum(len(turn.refs or []) for turn in (item.history or []))
        # if no turn ref (history_refs =0), then return the item refs if any
        if history_refs == 0:
            return len(item.refs or [])
        return history_refs

    def _to_doc(self, item: GroundTruthItem) -> dict[str, Any]:
        # Check if the doc has dataset and bucket fields, since they make the PK
        if not item.datasetName:
            self._logger.error(f"Document missing datasetName: {item!r}")
            raise ValueError("Document must have datasetName")

        # Calculate totalReferences and update the item object
        calculated_total_refs = CosmosGroundTruthRepo._compute_total_references(item)
        item.totalReferences = calculated_total_refs

        # Dump in JSON mode so datetimes/enums are serialized to strings
        d = item.model_dump(mode="json", by_alias=True)
        if d.get("bucket") is not None:
            d["bucket"] = str(d["bucket"])  # store UUID as string
        # Ensure updatedAt present as ISO string
        if "updatedAt" not in d or d["updatedAt"] is None:
            d["updatedAt"] = datetime.now(timezone.utc).isoformat()

        # Ensure totalReferences is set correctly (should already be from model_dump above)
        d["totalReferences"] = calculated_total_refs

        return d

    @staticmethod
    def _from_doc(doc: dict[str, Any]) -> GroundTruthItem:
        # Normalize doc before validation
        normalized_doc = (
            _restore_unicode_from_cosmos(doc) if settings.COSMOS_DISABLE_UNICODE_ESCAPE else doc
        )

        # Convert None to [] for history field (legacy data compatibility)
        if normalized_doc.get("history") is None:
            normalized_doc["history"] = []

        # Pydantic will parse aliases automatically
        item = GroundTruthItem.model_validate(normalized_doc)

        return item

    async def _ensure_initialized(self) -> None:
        """Lazy-initialize the client/containers on first use.

        This does not attempt to handle event-loop rebinding; tests are
        responsible for creating and using the repo on a single loop per test.
        """
        if (
            self._client is None
            or self._gt_container is None
            or self._assignments_container is None
        ):
            await self._init()

    async def import_bulk_gt(
        self, items: list[GroundTruthItem], buckets: int | None = None
    ) -> BulkImportResult:
        await self._ensure_initialized()
        # Assign UUID buckets per dataset for items missing bucket
        default_buckets = int(os.getenv("GTC_IMPORT_BUCKETS_DEFAULT", "5"))
        n = buckets if buckets is not None else default_buckets
        n = max(1, min(50, int(n)))

        from collections import defaultdict

        idxs_by_ds: dict[str, list[int]] = defaultdict(list)
        for idx, it in enumerate(items):
            if it.bucket is None:
                idxs_by_ds[it.datasetName].append(idx)

        for _ds, idxs in idxs_by_ds.items():
            count = len(idxs)
            k = max(1, min(n, count))
            buckets_for_ds = [uuid4() for _ in range(k)]
            for i, item_idx in enumerate(idxs):
                items[item_idx].bucket = buckets_for_ds[i % k]

        # sequential create to keep simple and clear errors
        gt = self._gt_container
        assert gt is not None
        success = 0
        errors: list[str] = []
        for it in items:
            doc = self._to_doc(it)

            # Apply UTF-8 fix when using Cosmos emulator
            if settings.COSMOS_DISABLE_UNICODE_ESCAPE:
                doc = CosmosGroundTruthRepo._ensure_utf8_strings(doc)

            try:
                await gt.create_item(doc)  # type: ignore
                success += 1
            except CosmosHttpResponseError as e:
                status = getattr(e, "status_code", None)
                if status == 409:
                    # Duplicate; report but continue others
                    article_num = (
                        doc.get("refs", [{}])[0].get("url", "unknown")
                        if doc.get("refs")
                        else "unknown"
                    )
                    errors.append(
                        f"exists (article: {article_num}, id: {doc.get('id', 'unknown')})"
                    )
                else:
                    article_num = (
                        doc.get("refs", [{}])[0].get("url", "unknown")
                        if doc.get("refs")
                        else "unknown"
                    )
                    errors.append(
                        f"create_failed (article: {article_num}, id: {doc.get('id', 'unknown')}): {getattr(e, 'message', str(e))}"
                    )
        return BulkImportResult(imported=success, errors=errors)

    async def list_all_gt(
        self, status: Optional[GroundTruthStatus] = None
    ) -> list[GroundTruthItem]:
        await self._ensure_initialized()
        # Cross-partition scan for all GT items; filter by status if provided
        status_filter = ""
        params: list[dict[str, Any]] = []
        if status is not None:
            status_filter = " WHERE c.status = @status"
            params.append({"name": "@status", "value": status.value})
        query = f"SELECT * FROM c{status_filter}"
        items: list[GroundTruthItem] = []
        gt = self._gt_container
        assert gt is not None
        it = gt.query_items(query=query, parameters=params, enable_scan_in_query=True)  # type: ignore
        async for doc in it:  # type: ignore
            items.append(self._from_doc(doc))
        return items

    def _build_query_filter(
        self,
        status: GroundTruthStatus | None,
        dataset: str | None,
        tags: list[str] | None,
        item_id: str | None = None,
        ref_url: str | None = None,
        *,
        include_tags: bool = True,
        include_ref_url: bool = True,
    ) -> tuple[str, list[dict[str, Any]]]:
        clauses: list[str] = ["c.docType = 'ground-truth-item'"]
        params: list[dict[str, Any]] = []

        if status is not None:
            status_value = status.value if isinstance(status, GroundTruthStatus) else str(status)
            clauses.append("c.status = @status")
            # Cosmos SQL expects parameter values to be JSON scalars; ensure plain string.
            params.append({"name": "@status", "value": str(status_value)})

        if dataset:
            clauses.append("c.datasetName = @dataset")
            params.append({"name": "@dataset", "value": dataset})

        if item_id:
            # Use simple STARTSWITH() for case-sensitive search
            # Note: Cosmos DB emulator doesn't support nested functions like STARTSWITH(LOWER(c.id), ...)
            # In production Azure Cosmos DB, use STARTSWITH(LOWER(c.id), @searchId) for case-insensitive
            # For now, search is case-sensitive to work with emulator
            clauses.append("STARTSWITH(c.id, @searchId)")
            params.append({"name": "@searchId", "value": item_id})

        if include_tags and tags:
            normalized = [tag for tag in (tag.strip() for tag in tags) if tag]
            for idx, tag in enumerate(normalized):
                pname = f"@tag{idx}"
                # Search across manualTags and computedTags
                clauses.append(
                    f"(ARRAY_CONTAINS(c.manualTags, {pname}) OR "
                    f"ARRAY_CONTAINS(c.computedTags, {pname}))"
                )
                params.append({"name": pname, "value": tag})

        # Ref URL filtering only if not using the Cosmos Emulator as it does not support EXISTS
        # include_ref_url set to True when Comsomus Emulator is not used
        if include_ref_url and ref_url:
            clauses.append(
                "(EXISTS(SELECT VALUE r FROM r IN c.refs WHERE CONTAINS(r.url, @refUrl)) "
                "OR EXISTS(SELECT VALUE h FROM h IN c.history "
                "WHERE EXISTS(SELECT VALUE r FROM r IN h.refs WHERE CONTAINS(r.url, @refUrl))))"
            )
            params.append({"name": "@refUrl", "value": ref_url})

        where_clause = " WHERE " + " AND ".join(clauses) if clauses else ""
        return where_clause, params

    def _resolve_sort(
        self,
        sort_by: SortField | str | None,
        sort_order: SortOrder | str | None,
    ) -> tuple[SortField, SortOrder]:
        field = SortField.reviewed_at
        if isinstance(sort_by, SortField):
            field = sort_by
        elif isinstance(sort_by, str):
            try:
                field = SortField(sort_by)
            except ValueError:
                field = SortField.reviewed_at

        direction = SortOrder.desc
        if isinstance(sort_order, SortOrder):
            direction = sort_order
        elif isinstance(sort_order, str):
            try:
                direction = SortOrder(sort_order)
            except ValueError:
                direction = SortOrder.desc

        return field, direction

    @staticmethod
    def _sort_key(item: GroundTruthItem, field: SortField) -> tuple[Any, ...]:
        if field == SortField.id:
            return (item.id or "",)

        if field == SortField.updated_at:
            return (
                item.updated_at
                if item.updated_at is not None
                else datetime(1970, 1, 1, tzinfo=timezone.utc),
                item.id,
            )

        if field == SortField.has_answer:
            has_answer = 1 if item.answer and item.answer.strip() else 0
            reference_time = (
                item.reviewed_at or item.updated_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
            )
            return (has_answer, reference_time, item.id)

        if field == SortField.totalReferences:
            return (item.totalReferences, item.id)

        reference_time = (
            item.reviewed_at or item.updated_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
        )
        return (reference_time, item.id)

    def is_cosmos_emulator_in_use(self) -> bool:
        """Detect if Cosmos DB emulator is in use based on endpoint URL."""
        return "localhost" in self._endpoint or "127.0.0.1" in self._endpoint

    @staticmethod
    def _item_matches_keyword(item: GroundTruthItem, keyword: str) -> bool:
        """Check if item matches keyword search (case-insensitive substring match).

        Searches across:
        - synth_question and edited_question fields
        - answer field
        - history[*].msg content (all turns)
        """
        if not keyword:
            return True

        search_term = keyword.lower()

        # Search question fields
        if item.synth_question and search_term in item.synth_question.lower():
            return True
        if item.edited_question and search_term in item.edited_question.lower():
            return True

        # Search answer field
        if item.answer and search_term in item.answer.lower():
            return True

        # Search history messages
        if item.history:
            for turn in item.history:
                if turn.msg and search_term in turn.msg.lower():
                    return True

        return False

    # Security: Comprehensive input validation and parameterization
    def _build_secure_sort_clause(self, sort_field: SortField, sort_direction: SortOrder) -> str:
        """Build secure ORDER BY clause with validation and parameterization."""

        # Security: Safe field mapping (no user input)
        # TODO: revisit the mapping SortField.has_answer: "c.reviewedAt"
        secure_field_map = {
            SortField.id: "c.id",
            SortField.updated_at: "c.updatedAt",
            SortField.reviewed_at: "c.reviewedAt",
            SortField.has_answer: "c.reviewedAt",
            SortField.totalReferences: "c.totalReferences",
        }

        # Security: Safe direction mapping (no user input)
        secure_direction_map = {SortOrder.desc: "DESC", SortOrder.asc: "ASC"}

        column_name = secure_field_map[sort_field]
        direction_sql = secure_direction_map[sort_direction]

        # Security: Use parameterized construction
        order_by_clause = f" ORDER BY {column_name} {direction_sql}"

        # Add secondary sort for stable pagination
        if sort_field != SortField.id:
            order_by_clause += ", c.id ASC"

        # Security: Log sort operations for monitoring
        self._logger.debug(
            f"security.sort_clause_built - field: {sort_field.value}, direction: {sort_direction.value}, column: {column_name}"
        )

        return order_by_clause

    async def list_gt_paginated(
        self,
        status: Optional[GroundTruthStatus] = None,
        dataset: str | None = None,
        tags: list[str] | None = None,
        item_id: str | None = None,
        ref_url: str | None = None,
        keyword: str | None = None,
        sort_by: SortField | None = None,
        sort_order: SortOrder | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> tuple[list[GroundTruthItem], PaginationMetadata]:
        await self._ensure_initialized()

        safe_limit = max(settings.PAGINATION_MIN_LIMIT, min(limit, settings.PAGINATION_MAX_LIMIT))
        safe_page = max(1, page)
        offset = (safe_page - 1) * safe_limit

        normalized_tags = [tag for tag in (tag.strip() for tag in (tags or [])) if tag]

        # For queries with tags, we need to filter in-memory since ARRAY_CONTAINS
        # doesn't work well with ORDER BY in Cosmos DB
        # Also use in-memory filtering for ref_url if Cosmos emultor is used since EXISTS is not supported by emulator
        # Keyword search also requires in-memory filtering (no full-text index)

        if normalized_tags or ref_url or keyword:
            # Always use in-memory filtering path for these filters
            # (Cosmos emulator has limitations, and keyword search needs in-memory filtering regardless)
            return await self._list_gt_paginated_with_emulator(
                status,
                dataset,
                normalized_tags,
                item_id,
                ref_url,
                keyword,
                sort_by,
                sort_order,
                safe_page,
                safe_limit,
            )
        sort_field, sort_direction = self._resolve_sort(sort_by, sort_order)

        self._logger.debug("Using direct Cosmos DB query for pagination without Cosmos Emulator")
        where_clause, filter_params = self._build_query_filter(
            status,
            dataset,
            normalized_tags,
            item_id,
            ref_url,
            include_tags=True,
            include_ref_url=True,
        )

        # Build ORDER BY clause
        try:
            order_by_clause = self._build_secure_sort_clause(sort_field, sort_direction)
        except SortSecurityError as e:
            self._logger.error(f"Security validation failed in sort clause: {e}")
            raise HTTPException(status_code=400, detail="Invalid sort parameters")

        # Build query with ORDER BY and OFFSET/LIMIT
        query = (
            f"{SELECT_CLAUSE_C} "
            "FROM c"
            f"{where_clause}"
            f"{order_by_clause} "
            f"OFFSET {offset} LIMIT {safe_limit}"
        )

        # Security: Log query construction for audit
        self._logger.info(
            "security.database_query_executed",
            extra={
                "query_type": "paginated_sort",
                "sort_field": sort_field.value,
                "parameters_count": len(filter_params),
            },
        )

        gt = self._gt_container
        assert gt is not None

        items: list[GroundTruthItem] = []
        it = gt.query_items(  # type: ignore
            query=query,
            parameters=filter_params,
            enable_scan_in_query=True,
        )
        async for doc in it:  # type: ignore
            items.append(self._from_doc(doc))

        # Get total count for pagination metadata
        total = await self._get_filtered_count(status, dataset, normalized_tags, item_id)
        total_pages = math.ceil(total / safe_limit) if total > 0 else 0

        pagination = PaginationMetadata(
            page=safe_page,
            limit=safe_limit,
            total=total,
            totalPages=total_pages,
            hasNext=safe_page < total_pages,
            hasPrev=safe_page > 1 and total > 0,
        )

        return items, pagination

    async def _list_gt_paginated_with_emulator(
        self,
        status: Optional[GroundTruthStatus],
        dataset: str | None,
        tags: list[str],
        item_id: str | None,
        ref_url: str | None,
        keyword: str | None,
        sort_by: SortField | None,
        sort_order: SortOrder | None,
        page: int,
        limit: int,
    ) -> tuple[list[GroundTruthItem], PaginationMetadata]:
        """Handle pagination for queries with tag and url_ref filters (requires in-memory filtering).

        Note: Due to Cosmos DB limitations with ARRAY_CONTAINS + ORDER BY, tag filtering
        requires fetching more items than requested and filtering in-memory. This method
        includes safeguards against memory exhaustion.

        Due to Cosmos DB emulator limitations with EXISTS sql clause, ref_url filtering is also done in-memory.
        """
        start_index = (page - 1) * limit

        # Use SQL tag filtering to reduce data transfer
        # Note: Cosmos DB emulator doesn't support multiple ARRAY_CONTAINS without composite indexes
        # so we filter in-memory instead (include_tags=False)
        where_clause, filter_params = self._build_query_filter(
            status,
            dataset,
            tags,
            item_id,
            ref_url,
            include_tags=False,  # Disable SQL-level tag filtering - filter in-memory instead
            include_ref_url=False,  # Disable ref_url filtering for emulator
        )

        sort_field, sort_direction = self._resolve_sort(sort_by, sort_order)

        query = f"{SELECT_CLAUSE_C}FROM c{where_clause}"

        gt = self._gt_container
        assert gt is not None

        # Memory safeguard: limit maximum items to fetch to prevent DoS
        MAX_ITEMS_TO_FETCH = settings.PAGINATION_TAG_FETCH_MAX

        raw_items: list[GroundTruthItem] = []
        it = gt.query_items(  # type: ignore
            query=query,
            parameters=filter_params,
            enable_scan_in_query=True,
            max_item_count=MAX_ITEMS_TO_FETCH,
        )

        items_fetched = 0
        async for doc in it:  # type: ignore
            raw_items.append(self._from_doc(doc))
            items_fetched += 1
            # Enforce memory limit to prevent resource exhaustion
            if items_fetched >= MAX_ITEMS_TO_FETCH:
                self._logger.warning(
                    "repo.list_gt_paginated_with_tags.max_items_reached",
                    extra={
                        "max_items": MAX_ITEMS_TO_FETCH,
                        "tags": tags,
                        "status": status.value if status else None,
                        "dataset": dataset,
                    },
                )
                break

        # Filter tags in-memory since SQL-level filtering is disabled
        # to avoid Cosmos DB emulator issues with multiple ARRAY_CONTAINS
        self._logger.debug(
            "Filtering tags and ref_url in-memory due to Cosmos DB emulator limitations"
        )
        if tags:
            filtered_items_tag: list[GroundTruthItem] = []
            tags_set = set(tags)
            for item in raw_items:
                if item.tags and tags_set.issubset(set(item.tags)):
                    filtered_items_tag.append(item)
            raw_items = filtered_items_tag

        # Filter by ref_url in-memory (EXISTS not supported by Cosmos DB emulator)
        if ref_url:
            start = time.time()
            filtered_items_ref: list[GroundTruthItem] = []
            total_refs_checked = 0

            for item in raw_items:
                # Check item-level refs
                has_match = any(ref_url in ref.url for ref in item.refs)
                total_refs_checked += len(item.refs)

                # Check history-level refs if no match yet
                if not has_match and item.history:
                    for turn in item.history:
                        if turn.refs:
                            total_refs_checked += len(turn.refs)
                            if any(ref_url in ref.url for ref in turn.refs):
                                has_match = True
                                break
                if has_match:
                    filtered_items_ref.append(item)

            elapsed = time.time() - start
            self._logger.info(
                "repo.ref_url_filter.performance"
                f"items_checked: {len(raw_items)}, "
                f"items_matched: {len(filtered_items_ref)}, "
                f"refs_checked: {total_refs_checked}, "
                f"elapsed_ms: {elapsed * 1000}, "
                f"ref_url_length: {len(ref_url)}, "
            )
            raw_items = filtered_items_ref

        # Filter by keyword in-memory (case-insensitive substring match)
        if keyword:
            start = time.time()
            filtered_items_keyword: list[GroundTruthItem] = []

            for item in raw_items:
                if self._item_matches_keyword(item, keyword):
                    filtered_items_keyword.append(item)

            elapsed = time.time() - start
            self._logger.info(
                "repo.keyword_filter.performance"
                f"items_checked: {len(raw_items)}, "
                f"items_matched: {len(filtered_items_keyword)}, "
                f"elapsed_ms: {elapsed * 1000}, "
                f"keyword_length: {len(keyword)}, "
            )
            raw_items = filtered_items_keyword

        # Sort in-memory (required since ORDER BY conflicts with ARRAY_CONTAINS in Cosmos DB)
        reverse_sort = sort_direction == SortOrder.desc
        raw_items.sort(key=lambda item: self._sort_key(item, sort_field), reverse=reverse_sort)

        total = len(raw_items)
        total_pages = math.ceil(total / limit) if total > 0 else 0
        end_index = start_index + limit
        items = raw_items[start_index:end_index] if start_index < total else []

        pagination = PaginationMetadata(
            page=page,
            limit=limit,
            total=total,
            totalPages=total_pages,
            hasNext=end_index < total,
            hasPrev=page > 1 and total > 0,
        )

        return items, pagination

    async def _get_filtered_count(
        self,
        status: Optional[GroundTruthStatus],
        dataset: str | None,
        tags: list[str] | None,
        item_id: str | None = None,
    ) -> int:
        """Get total count of items matching the filter criteria."""
        # For queries with tags, check if we should use SQL filtering or in-memory filtering
        if tags:
            if self.is_cosmos_emulator_in_use():
                # Use in-memory filtering for emulator (same as _list_gt_paginated_with_emulator)
                where_clause, filter_params = self._build_query_filter(
                    status,
                    dataset,
                    None,  # Don't include tags in SQL query for emulator
                    item_id,
                    include_tags=False,
                )

                # Select tag fields for in-memory filtering
                query = f"SELECT c.manualTags, c.computedTags FROM c{where_clause}"

                gt = self._gt_container
                assert gt is not None

                it = gt.query_items(  # type: ignore
                    query=query,
                    parameters=filter_params,
                    enable_scan_in_query=True,
                )

                count = 0
                tags_set = set(tags)
                async for doc in it:  # type: ignore
                    # Merge manualTags and computedTags for filtering
                    manual = set(doc.get("manualTags") or [])
                    computed = set(doc.get("computedTags") or [])
                    all_tags = manual | computed
                    if all_tags and tags_set.issubset(all_tags):
                        count += 1
                return count
            else:
                # Use SQL-based counting for real Cosmos DB
                where_clause, filter_params = self._build_query_filter(
                    status,
                    dataset,
                    tags,
                    item_id,
                    include_tags=True,
                )

                # Use SELECT VALUE COUNT(1) with tag filters for consistency with main query
                query = f"SELECT VALUE COUNT(1) FROM c{where_clause}"

                gt = self._gt_container
                assert gt is not None

                it = gt.query_items(  # type: ignore
                    query=query,
                    parameters=filter_params,
                    enable_scan_in_query=True,
                )

                # The query returns a single scalar value
                async for result in it:  # type: ignore
                    if isinstance(result, dict):
                        for k in ("$1", "count"):
                            if k in result:
                                val = result.get(k)
                                return int(val) if val is not None else 0
                        return 0
                    return int(result) if result is not None else 0
                return 0

        # For non-tag queries, use SELECT VALUE COUNT(1) which returns a scalar per Cosmos DB docs.
        # The docs (COUNT aggregate examples) show SELECT VALUE COUNT(1) as the canonical
        # pattern for counting items. Using the VALUE form also avoids the "NonValueAggregate"
        # query plan feature that triggered the original production error with SELECT COUNT(1) AS count.
        where_clause, filter_params = self._build_query_filter(
            status,
            dataset,
            None,
            item_id,
            include_tags=False,
        )
        # Returns a single scalar value (e.g., [42])
        query = f"SELECT VALUE COUNT(1) FROM c{where_clause}"

        gt = self._gt_container
        assert gt is not None

        it = gt.query_items(  # type: ignore
            query=query,
            parameters=filter_params,
            enable_scan_in_query=True,
        )

        async for result in it:  # type: ignore
            # Result is a scalar integer (VALUE projection). Some emulator / older SDK
            # combinations have been observed to return a dict like {"$1": n}; handle defensively.
            if isinstance(result, dict):
                # Fallback keys sometimes observed: "$1", "count"
                for k in ("$1", "count"):
                    if k in result:
                        val = result.get(k)
                        return int(val) if val is not None else 0
                return 0
            return int(result) if result is not None else 0

        return 0

    async def list_gt_by_dataset(
        self, dataset: str, status: Optional[GroundTruthStatus] = None
    ) -> list[GroundTruthItem]:
        await self._ensure_initialized()
        # Query across all buckets for this dataset by filtering datasetName
        status_filter = ""
        params: list[dict[str, Any]] = [{"name": "@ds", "value": dataset}]
        if status is not None:
            status_filter = " AND c.status = @status"
            params.append({"name": "@status", "value": status.value})

        query = (
            f"{SELECT_CLAUSE_C} "
            "FROM c WHERE c.datasetName = @ds AND (NOT IS_DEFINED(c.docType) OR c.docType != 'curation-instructions')"
            + status_filter
        )
        items: list[GroundTruthItem] = []
        gt = self._gt_container
        assert gt is not None
        it = gt.query_items(query=query, parameters=params, enable_scan_in_query=True)  # type: ignore
        async for doc in it:  # type: ignore
            items.append(self._from_doc(doc))

        return items

    async def get_gt(self, dataset: str, bucket: UUID, item_id: str) -> GroundTruthItem | None:
        await self._ensure_initialized()
        # dataset and bucket comprise the hierarchical partition key
        try:
            gt = self._gt_container
            assert gt is not None
            it = await gt.read_item(item=item_id, partition_key=[dataset, str(bucket)])  # type: ignore
            return self._from_doc(it)
        except CosmosHttpResponseError as e:
            if getattr(e, "status_code", None) == 404:
                return None
            raise

    # Curation instructions helpers
    @staticmethod
    def _to_curation_doc(doc: DatasetCurationInstructions) -> dict[str, Any]:
        d = doc.model_dump(mode="json", by_alias=True)
        if "updatedAt" not in d or d["updatedAt"] is None:
            d["updatedAt"] = datetime.now(timezone.utc).isoformat()

        return d

    @staticmethod
    def _from_curation_doc(d: dict[str, Any]) -> DatasetCurationInstructions:
        if settings.COSMOS_DISABLE_UNICODE_ESCAPE:
            d = _restore_unicode_from_cosmos(d)
        return DatasetCurationInstructions.model_validate(d)

    def _curation_id(self, dataset: str) -> str:
        return f"curation-instructions|{dataset}"

    async def get_curation_instructions(self, dataset: str) -> DatasetCurationInstructions | None:
        await self._ensure_initialized()
        try:
            res = await self._gt_container.read_item(  # type: ignore
                item=self._curation_id(dataset),
                partition_key=[dataset, "00000000-0000-0000-0000-000000000000"],
            )
            return self._from_curation_doc(res)
        except CosmosHttpResponseError as e:
            if getattr(e, "status_code", None) == 404:
                return None
            raise

    async def upsert_curation_instructions(
        self, doc: DatasetCurationInstructions
    ) -> DatasetCurationInstructions:
        await self._ensure_initialized()
        # Ensure identity fields
        doc.id = self._curation_id(doc.datasetName)
        body = self._to_curation_doc(doc)
        body["updatedAt"] = datetime.now(timezone.utc).isoformat()

        # Apply UTF-8 fix after all modifications
        if settings.COSMOS_DISABLE_UNICODE_ESCAPE:
            body = CosmosGroundTruthRepo._ensure_utf8_strings(body)

        try:
            gt = self._gt_container
            assert gt is not None
            if doc.etag:
                res = await gt.replace_item(  # type: ignore
                    item=doc.id,
                    body=body,
                    etag=doc.etag,
                    match_condition=MatchConditions.IfNotModified,
                )
            else:
                # Try create first so PUT without etag creates if missing
                try:
                    res = await gt.create_item(body)  # type: ignore
                except CosmosHttpResponseError as e:
                    if getattr(e, "status_code", None) == 409:
                        # Already exists -> upsert/replace without etag
                        res = await gt.upsert_item(body)  # type: ignore
                    else:
                        raise
            return self._from_curation_doc(res)
        except CosmosHttpResponseError as e:
            if getattr(e, "status_code", None) == 412:
                raise ValueError("etag_mismatch")
            raise

    async def upsert_gt(self, item: GroundTruthItem) -> GroundTruthItem:
        await self._ensure_initialized()

        doc = self._to_doc(item)
        # Concurrency: if etag provided, use conditional replace; otherwise upsert
        now = datetime.now(timezone.utc)
        doc["updatedAt"] = now.isoformat()

        # Apply UTF-8 fix after all modifications
        if settings.COSMOS_DISABLE_UNICODE_ESCAPE:
            doc = CosmosGroundTruthRepo._ensure_utf8_strings(doc)

        gt = self._gt_container
        assert gt is not None

        if item.etag:
            # use conditional replace with ETag and match condition
            # Retry logic for intermittent Cosmos DB emulator "jsonb type as object key" errors
            max_retries = 3
            res = None
            sanitized_retry_applied = False
            for attempt in range(max_retries):
                try:
                    res = await gt.replace_item(
                        item=item.id,
                        body=doc,
                        etag=item.etag,
                        match_condition=MatchConditions.IfNotModified,
                    )
                    break  # Success, exit retry loop
                except CosmosHttpResponseError as e:
                    status = getattr(e, "status_code", None)
                    if status == 412:
                        # ETag mismatch -> propagate for API to return 412
                        raise ValueError("etag_mismatch")
                    elif status == 404:
                        # Create if not found (should be rare)
                        res = await gt.create_item(doc)  # type: ignore
                        break  # Success, exit retry loop
                    else:
                        if (
                            self.is_cosmos_emulator_in_use()
                            and not sanitized_retry_applied
                            and CosmosGroundTruthRepo._is_invalid_json_payload_error(e)
                        ):
                            sanitized_retry_applied = True
                            doc = CosmosGroundTruthRepo._sanitize_doc_for_emulator_retry(doc)
                            self._logger.warning(
                                "cosmos_emulator.retry_invalid_json",
                                extra={"item_id": item.id, "attempt": attempt + 1},
                            )
                            continue
                        error_msg = str(e)
                        is_jsonb_error = (
                            "unexpected jsonb type as object key" in error_msg
                            or "unknown type of jsonb container" in error_msg
                        )
                        if (
                            attempt < max_retries - 1
                            and is_jsonb_error
                            and self.is_cosmos_emulator_in_use()
                        ):
                            # This is a known intermittent emulator bug, retry after a short delay
                            logging.warning(
                                f"Cosmos emulator jsonb error on attempt {attempt + 1} "
                                f"for item {item.id}, retrying... Error: {error_msg}"
                            )
                            await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            # Not a retryable error or max retries exceeded
                            raise
        else:
            # Retry logic for upsert operations as well
            max_retries = 3
            res = None
            sanitized_retry_applied = False
            for attempt in range(max_retries):
                try:
                    res = await gt.upsert_item(doc)  # type: ignore
                    break  # Success, exit retry loop
                except CosmosHttpResponseError as e:
                    if (
                        self.is_cosmos_emulator_in_use()
                        and not sanitized_retry_applied
                        and CosmosGroundTruthRepo._is_invalid_json_payload_error(e)
                    ):
                        sanitized_retry_applied = True
                        doc = CosmosGroundTruthRepo._sanitize_doc_for_emulator_retry(doc)
                        self._logger.warning(
                            "cosmos_emulator.retry_invalid_json",
                            extra={"item_id": item.id, "attempt": attempt + 1},
                        )
                        continue
                    error_msg = str(e)
                    is_jsonb_error = (
                        "unexpected jsonb type as object key" in error_msg
                        or "unknown type of jsonb container" in error_msg
                    )
                    if (
                        attempt < max_retries - 1
                        and is_jsonb_error
                        and self.is_cosmos_emulator_in_use()
                    ):
                        # This is a known intermittent emulator bug, retry after a short delay
                        logging.warning(
                            f"Cosmos emulator jsonb error on attempt {attempt + 1} "
                            f"for upsert item {item.id}, retrying... Error: {error_msg}"
                        )
                        await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        # Not a retryable error or max retries exceeded
                        raise

        assert res is not None, "res should be assigned by either replace_item or upsert_item"
        return self._from_doc(res)

    async def soft_delete_gt(self, dataset: str, bucket: UUID, item_id: str) -> None:
        # Implement as soft delete: set status=deleted
        it = await self.get_gt(dataset, bucket, item_id)
        if not it:
            return
        it.status = GroundTruthStatus.deleted
        await self.upsert_gt(it)

    async def delete_dataset(self, dataset: str) -> None:
        await self._ensure_initialized()
        # hard-delete all items in dataset
        items = await self.list_gt_by_dataset(dataset)
        gt = self._gt_container
        assert gt is not None
        for it in items:
            # Retry logic for intermittent Cosmos DB emulator "jsonb type as object key" errors
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await gt.delete_item(item=it.id, partition_key=[dataset, str(it.bucket)])
                    break  # Success, move to next item
                except CosmosResourceNotFoundError:
                    # Item already deleted - this is expected and not an error
                    logging.debug(f"Item {it.id} already deleted, skipping")
                    break
                except Exception as e:
                    error_msg = str(e)
                    is_jsonb_error = (
                        "unexpected jsonb type as object key" in error_msg
                        or "unknown type of jsonb container" in error_msg
                    )
                    is_http_format_error = "Expected HTTP" in error_msg
                    # Only retry for known emulator issues, otherwise re-raise original exception type
                    if (
                        attempt < max_retries - 1
                        and (is_jsonb_error or is_http_format_error)
                        and self.is_cosmos_emulator_in_use()
                    ):
                        # These are known intermittent emulator bugs, retry after a short delay
                        error_type = "jsonb" if is_jsonb_error else "HTTP format"
                        logging.warning(
                            f"Cosmos emulator {error_type} error on attempt {attempt + 1} "
                            f"for item {it.id}, retrying... Error: {error_msg}"
                        )
                        import asyncio

                        await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        # Not a retryable error or max retries exceeded - re-raise as original type
                        if isinstance(e, CosmosHttpResponseError):
                            raise
                        else:
                            # For non-Cosmos errors, log and re-raise
                            logging.error(f"Unexpected error deleting item {it.id}: {e}")
                            raise

        # Delete curation instructions for this dataset
        curation_id = self._curation_id(dataset)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await gt.delete_item(
                    item=curation_id,
                    partition_key=[dataset, "00000000-0000-0000-0000-000000000000"],
                )
                logging.info(f"Deleted curation instructions for dataset: {dataset}")
                break
            except CosmosHttpResponseError as e:
                if getattr(e, "status_code", None) == 404:
                    # Curation instructions don't exist, that's fine
                    logging.debug(f"No curation instructions found for dataset: {dataset}")
                    break
                elif attempt < max_retries - 1 and "Expected HTTP" in str(e):
                    # Retry on HTTP format errors (CI emulator issue)
                    logging.warning(
                        f"HTTP format error deleting curation instructions (attempt {attempt + 1}): {e}"
                    )
                    import asyncio

                    await asyncio.sleep(0.2 * (attempt + 1))
                    continue
                else:
                    logging.error(
                        f"Failed to delete curation instructions for dataset {dataset}: {e}"
                    )
                    raise

    async def stats(self) -> Stats:
        await self._ensure_initialized()
        # Count by status. Simpler and broadly compatible across emulator/SDK versions.
        draft = approved = deleted = 0
        gt = self._gt_container
        assert gt is not None
        it = gt.query_items(
            query="SELECT c.status FROM c",
            parameters=[],
            enable_scan_in_query=True,
        )  # type: ignore
        async for doc in it:  # type: ignore
            s = doc.get("status")
            if s == GroundTruthStatus.draft.value:
                draft += 1
            elif s == GroundTruthStatus.approved.value:
                approved += 1
            elif s == GroundTruthStatus.deleted.value:
                deleted += 1
        return Stats(draft=draft, approved=approved, deleted=deleted)

    async def list_datasets(self) -> list[str]:
        await self._ensure_initialized()
        gt = self._gt_container
        assert gt is not None
        query = (
            "SELECT DISTINCT VALUE c.datasetName "
            "FROM c WHERE c.docType = 'ground-truth-item' ORDER BY c.datasetName"
        )
        names: list[str] = []
        seen: set[str] = set()
        it = gt.query_items(  # type: ignore
            query=query,
            parameters=[],
            enable_scan_in_query=True,
        )
        async for raw in it:  # type: ignore
            if not isinstance(raw, str):
                continue
            name = raw.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            names.append(name)
        return names

    async def list_unassigned(self, limit: int) -> list[GroundTruthItem]:
        await self._ensure_initialized()
        if limit <= 0:
            return []
        # Global unassigned/skipped query, capped by limit
        query = (
            "SELECT * FROM c "
            "WHERE c.docType = 'ground-truth-item' AND ("
            "(c.status = 'draft' AND (NOT IS_DEFINED(c.assignedTo) OR IS_NULL(c.assignedTo) OR c.assignedTo = '')) "
            "OR c.status = 'skipped'"
            ")"
        )
        gt = self._gt_container
        assert gt is not None
        it = gt.query_items(  # type: ignore
            query=query,
            parameters=[],
            enable_scan_in_query=True,
            max_item_count=min(limit, 200),
        )
        res: list[GroundTruthItem] = []
        async for doc in it:  # type: ignore
            res.append(self._from_doc(doc))
            if len(res) >= limit:
                break
        self._logger.debug("repo.list_unassigned", extra={"limit": limit, "count": len(res)})
        return res

    # flow:
    # sample unassigned to get a set of potential items to assign
    # try to assign them, concurrent requests could also be trying to do this so we need to match on the etag when we update assignedTo
    # we need to add these newly assigned docs into the assignments container with the relevant subset of fields and a link back to the ground truth item.
    async def sample_unassigned(
        self, user_id: str, limit: int, exclude_ids: list[str] | None = None
    ) -> list[GroundTruthItem]:
        await self._ensure_initialized()
        if limit <= 0:
            self._logger.warning(
                "repo.sample_unassigned.invalid_limit",
                extra={"limit": limit},
            )
            return []

        # 1) Include already assigned items first
        self._logger.debug(
            "repo.sample_unassigned.start",
            extra={
                "limit": limit,
                "exclude_count": len(exclude_ids) if exclude_ids else 0,
            },
        )
        results: list[GroundTruthItem] = await self.list_assigned(user_id)
        seen_ids: set[str] = {it.id for it in results}
        # Add caller-provided excludes
        if exclude_ids:
            seen_ids.update(exclude_ids)
        self._logger.debug(
            "repo.sample_unassigned.already_assigned",
            extra={"count": len(results)},
        )
        if len(results) >= limit:
            self._logger.debug(
                "repo.sample_unassigned.already_assigned_satisfies",
                extra={"count": len(results), "limit": limit},
            )
            return results[:limit]

        remaining = limit - len(results)
        # 2) Read allocation config
        weights = get_sampling_allocation()
        self._logger.debug(
            "repo.sample_unassigned.weights_config",
            extra={"weights": weights, "has_weights": bool(weights)},
        )
        if not weights:
            # No allocation configured -> simple global fill of unassigned/skipped
            self._logger.debug(
                "repo.sample_unassigned.no_weights_global_query",
                extra={"remaining": remaining},
            )
            more = await self._query_unassigned_global_excluding_user(
                user_id, remaining, exclude_ids=list(seen_ids)
            )
            self._logger.debug(
                "repo.sample_unassigned.global_fill",
                extra={"remaining": remaining, "candidates": len(more)},
            )
            # Shuffle to reduce any cross-partition bias from Cosmos
            random.shuffle(more)
            for it in more:
                if it.id not in seen_ids:
                    results.append(it)
                    seen_ids.add(it.id)
                    if len(results) >= limit:
                        break
            self._logger.debug(
                "repo.sample_unassigned.global_fill_complete",
                extra={"final_count": len(results), "limit": limit},
            )
            return results[:limit]

        # 3) Compute quotas using largest remainder method
        quotas = self._compute_quotas(weights, remaining)
        self._logger.debug(
            "repo.sample_unassigned.quotas",
            extra={"remaining": remaining, "quotas": quotas},
        )

        # 4) Query each dataset up to its quota (single pass)
        per_dataset_results: dict[str, list[GroundTruthItem]] = {}
        for ds, q in quotas.items():
            if q <= 0:
                self._logger.debug(
                    "repo.sample_unassigned.skip_zero_quota",
                    extra={"dataset": ds, "quota": q},
                )
                continue
            items = await self._query_unassigned_by_selector(
                ds, user_id, q, exclude_ids=list(seen_ids)
            )
            self._logger.debug(
                "repo.sample_unassigned.dataset_candidates",
                extra={"dataset": ds, "quota": q, "candidates": len(items)},
            )
            # Shuffle each bucket to de-bias ordering
            random.shuffle(items)
            per_dataset_results[ds] = items

        # 5) Round-robin interleave by weight order until limit reached or supply exhausted
        order = [ds for ds, _w in sorted(weights.items(), key=lambda kv: kv[1], reverse=True)]
        to_take = limit - len(results)
        self._logger.debug(
            "repo.sample_unassigned.round_robin_start",
            extra={"to_take": to_take, "dataset_order": order},
        )
        while to_take > 0:
            progressed = False
            for ds in order:
                if to_take <= 0:
                    break
                lst = per_dataset_results.get(ds, [])
                while lst and lst[0].id in seen_ids:
                    lst.pop(0)
                if lst:
                    it = lst.pop(0)
                    results.append(it)
                    seen_ids.add(it.id)
                    to_take -= 1
                    progressed = True
            if not progressed:
                self._logger.debug(
                    "repo.sample_unassigned.round_robin_exhausted",
                    extra={"collected": len(results), "limit": limit},
                )
                break

        self._logger.debug(
            "repo.sample_unassigned.round_robin_complete",
            extra={"collected": len(results), "limit": limit},
        )
        if len(results) >= limit:
            return results[:limit]

        # 6) Final global fill if still short (single pass)
        remaining_needed = max(0, limit - len(results))
        if remaining_needed > 0:
            self._logger.debug(
                "repo.sample_unassigned.global_fill_tail_start",
                extra={"remaining_needed": remaining_needed},
            )
            more = await self._query_unassigned_global_excluding_user(
                user_id, remaining_needed, exclude_ids=list(seen_ids)
            )
            self._logger.debug(
                "repo.sample_unassigned.global_fill_tail",
                extra={"remaining": remaining_needed, "candidates": len(more)},
            )
            random.shuffle(more)
            for it in more:
                if it.id not in seen_ids:
                    results.append(it)
                    seen_ids.add(it.id)
                    if len(results) >= limit:
                        break

        final = results[:limit]
        self._logger.debug(
            "repo.sample_unassigned.done",
            extra={"limit": limit, "return_count": len(final)},
        )
        return final

    async def _query_unassigned_by_selector(
        self, dataset_prefix: str, user_id: str, take: int, exclude_ids: list[str] | None = None
    ) -> list[GroundTruthItem]:
        if take <= 0:
            return []
        await self._ensure_initialized()
        # Treat dataset selector as a prefix for grouping, e.g., "dsA" matches "dsA-*"
        exclude_params: list[dict[str, Any]] = []
        exclude_clause = ""
        if exclude_ids:
            # Build a conjunction of c.id != @e0 AND c.id != @e1 ... to avoid unsupported ARRAY_CONTAINS on emulator
            parts: list[str] = []
            for idx, val in enumerate(exclude_ids[:200]):
                pname = f"@e{idx}"
                parts.append(f"c.id != {pname}")
                exclude_params.append({"name": pname, "value": val})
            if parts:
                exclude_clause = " AND " + " AND ".join(parts)
        query = (
            "SELECT * FROM c "
            "WHERE c.docType = 'ground-truth-item' AND STARTSWITH(c.datasetName, @prefix) AND ("
            "(c.status = 'draft' AND (NOT IS_DEFINED(c.assignedTo) OR IS_NULL(c.assignedTo) OR c.assignedTo = '')) "
            "OR (c.status = 'skipped' AND c.assignedTo != @user_id)"
            ")" + exclude_clause
        )
        gt = self._gt_container
        assert gt is not None
        params: list[dict[str, Any]] = [
            {"name": "@prefix", "value": dataset_prefix},
            {"name": "@user_id", "value": user_id},
        ]
        params.extend(exclude_params)
        self._logger.debug(
            "repo.query_unassigned_by_selector.start",
            extra={
                "dataset_prefix": dataset_prefix,
                "take": take,
                "exclude_count": len(exclude_ids) if exclude_ids else 0,
            },
        )
        it = gt.query_items(  # type: ignore
            query=query,
            parameters=params,
            enable_scan_in_query=True,
            max_item_count=min(take, 200),
        )
        res: list[GroundTruthItem] = []
        async for doc in it:  # type: ignore
            res.append(self._from_doc(doc))
            if len(res) >= take:
                break
        self._logger.debug(
            "repo.query_unassigned_by_selector.complete",
            extra={
                "dataset_prefix": dataset_prefix,
                "take": take,
                "count": len(res),
            },
        )
        return res

    async def _query_unassigned_global_excluding_user(
        self, user_id: str, take: int, exclude_ids: list[str] | None = None
    ) -> list[GroundTruthItem]:
        if take <= 0:
            return []
        await self._ensure_initialized()
        exclude_params: list[dict[str, Any]] = []
        exclude_clause = ""
        if exclude_ids:
            parts: list[str] = []
            for idx, val in enumerate(exclude_ids[:200]):
                pname = f"@e{idx}"
                parts.append(f"c.id != {pname}")
                exclude_params.append({"name": pname, "value": val})
            if parts:
                exclude_clause = " AND " + " AND ".join(parts)
        query = (
            "SELECT * FROM c "
            "WHERE c.docType = 'ground-truth-item' AND ("
            "(c.status = 'draft' AND (NOT IS_DEFINED(c.assignedTo) OR IS_NULL(c.assignedTo) OR c.assignedTo = '')) "
            "OR (c.status = 'skipped' AND c.assignedTo != @user_id)"
            ")" + exclude_clause
        )
        gt = self._gt_container
        assert gt is not None
        params: list[dict[str, Any]] = [{"name": "@user_id", "value": user_id}]
        params.extend(exclude_params)
        self._logger.debug(
            "repo.query_unassigned_global.start",
            extra={
                "take": take,
                "exclude_count": len(exclude_ids) if exclude_ids else 0,
            },
        )
        it = gt.query_items(  # type: ignore
            query=query,
            parameters=params,
            enable_scan_in_query=True,
            max_item_count=min(take, 200),
        )
        res: list[GroundTruthItem] = []
        async for doc in it:  # type: ignore
            res.append(self._from_doc(doc))
            if len(res) >= take:
                break
        self._logger.debug(
            "repo.query_unassigned_global.complete",
            extra={"take": take, "count": len(res)},
        )
        return res

    def _compute_quotas(self, weights: dict[str, float], k: int) -> dict[str, int]:
        """Largest remainder method to convert weights to integer quotas summing to k."""
        if k <= 0 or not weights:
            return {ds: 0 for ds in weights}
        # Normalize weights just in case
        total = sum(w for w in weights.values() if w > 0)
        if total <= 0:
            return {ds: 0 for ds in weights}
        normalized = {ds: (w / total) for ds, w in weights.items() if w > 0}
        # Floor allocations and track remainders
        floors: dict[str, int] = {}
        remainders: list[tuple[str, float]] = []
        allocated = 0
        for ds, w in normalized.items():
            raw = w * k
            fl = int(raw // 1)
            floors[ds] = fl
            allocated += fl
            remainders.append((ds, raw - fl))
        remaining = max(0, k - allocated)
        if remaining > 0:
            # Distribute remaining to largest remainders; stable sort by remainder desc then name
            remainders.sort(key=lambda t: (t[1], t[0]), reverse=True)
            for i in range(remaining):
                ds = remainders[i % len(remainders)][0]
                floors[ds] += 1
        return floors

    async def assign_to(self, item_id: str, user_id: str) -> bool:
        await self._ensure_initialized()

        # State-agnostic assignment: caller is responsible for validating state before calling
        # For MultiHash PK [/datasetName, /bucket], pass both PK values in order.

        # Validate user_id: reject if it contains characters that could break SQL escaping
        # Allow only alphanumeric, @, ., -, and _ (common in email addresses and user IDs)
        if not re.match(r"^[a-zA-Z0-9@.\-_]+$", user_id):
            self._logger.warning(
                f"repo.assign_to.invalid_user_id - user_id={user_id}, reason=contains_invalid_characters_or_whitespace"
            )
            return False

        # Use different approaches for emulator vs production Cosmos DB
        if self.is_cosmos_emulator_in_use():
            return await self._assign_to_with_read_modify_replace(item_id, user_id)
        else:
            return await self._assign_to_with_patch(item_id, user_id)

    async def _assign_to_with_patch(self, item_id: str, user_id: str) -> bool:
        """Use patch operations for production Cosmos DB (optimal performance)."""
        # First, get partition key by querying for dataset and bucket
        query = "SELECT TOP 1 c.datasetName, c.bucket FROM c WHERE c.id = @id"
        gt = self._gt_container
        assert gt is not None
        it = gt.query_items(  # type: ignore
            query=query,
            parameters=[{"name": "@id", "value": item_id}],
            enable_scan_in_query=True,
        )

        partition_info: dict[str, Any] | None = None
        async for d in it:  # type: ignore
            partition_info = d
            break

        if not partition_info:
            self._logger.warning(f"repo.assign_to.item_not_found - item_id={item_id}")
            return False

        ds = partition_info.get("datasetName")
        bucket = partition_info.get("bucket")
        partition_key = [ds, str(bucket)]

        # Use patch operations with filter_predicate for atomic conditional update
        # Note: Cosmos DB patch_item filter_predicate does NOT support parameterized queries
        # We must escape the user_id for safe string interpolation
        now = datetime.now(timezone.utc).isoformat()

        # Build filter predicate for conditional assignment
        # Only assign if item is unassigned, empty assigned, already assigned to this user, or not in draft state
        filter_predicate = (
            f"FROM c WHERE (c.assignedTo = null OR c.assignedTo = '' "
            f"OR c.assignedTo = '{user_id}' OR c.status != 'draft')"
        )

        patch_operations = [
            {"op": "set", "path": "/assignedTo", "value": user_id},
            {"op": "set", "path": "/assignedAt", "value": now},
            {"op": "set", "path": "/status", "value": GroundTruthStatus.draft.value},
            {"op": "set", "path": "/updatedAt", "value": now},
        ]

        try:
            await gt.patch_item(
                item=item_id,
                partition_key=partition_key,
                patch_operations=patch_operations,
                filter_predicate=filter_predicate,
            )

            self._logger.info(
                f"repo.assign_to.success - item_id={item_id}, dataset={ds}, user_id={user_id}, method=patch"
            )
            return True
        except CosmosHttpResponseError as e:
            if getattr(e, "status_code", None) == 412:  # Precondition failed
                self._logger.info(
                    f"repo.assign_to.assignment_rejected - item_id={item_id}, user_id={user_id}, "
                    f"reason=filter_predicate_failed"
                )
                return False
            else:
                self._logger.error(
                    f"repo.assign_to.patch_error - item_id={item_id}, user_id={user_id}, dataset={ds}, "
                    f"error_type={type(e).__name__}, error='{str(e)}', status_code={getattr(e, 'status_code', None)}"
                )
                return False
        except Exception as e:
            self._logger.error(
                f"repo.assign_to.unexpected_error - item_id={item_id}, user_id={user_id}, dataset={ds}, "
                f"error_type={type(e).__name__}, error='{str(e)}'"
            )
            return False

    async def _assign_to_with_read_modify_replace(self, item_id: str, user_id: str) -> bool:
        """Use read-modify-replace for emulator compatibility."""
        # Select all fields to preserve complete document structure for replace_item
        query = "SELECT TOP 1 * FROM c WHERE c.id = @id"
        gt = self._gt_container
        assert gt is not None
        it = gt.query_items(  # type: ignore
            query=query,
            parameters=[{"name": "@id", "value": item_id}],
            enable_scan_in_query=True,
        )
        doc: dict[str, Any] | None = None
        async for d in it:  # type: ignore
            doc = d
            break

        if not doc:
            self._logger.warning(f"repo.assign_to.item_not_found - item_id={item_id}")
            return False

        ds = doc.get("datasetName")
        bucket = doc.get("bucket")
        partition_key = [ds, str(bucket)]

        try:
            # Apply the same conditional logic that would be in filter_predicate
            current_assigned_to = doc.get("assignedTo")
            current_status = doc.get("status")

            # Check assignment conditions (same logic as filter_predicate)
            can_assign = (
                not current_assigned_to  # Not assigned
                or current_assigned_to == ""  # Empty assignment
                or current_assigned_to == user_id  # Already assigned to this user
                or current_status != GroundTruthStatus.draft.value  # Not in draft state
            )

            if not can_assign:
                self._logger.info(
                    f"repo.assign_to.assignment_rejected - item_id={item_id}, current_assigned_to={current_assigned_to}, "
                    f"current_status={current_status}, reason=already_assigned_to_other_user"
                )
                return False

            # Update the item with assignment details
            now = datetime.now(timezone.utc).isoformat()
            updated_item = {
                **doc,
                "assignedTo": user_id,
                "assignedAt": now,
                "status": GroundTruthStatus.draft.value,
                "updatedAt": now,
            }

            # Use replace_item without etag since query result may not include it
            # The conditional logic above provides the race condition protection
            await gt.replace_item(
                item=item_id,
                body=updated_item,
            )

            self._logger.info(
                f"repo.assign_to.success - item_id={item_id}, dataset={ds}, user_id={user_id}, method=read_modify_replace"
            )
            return True
        except Exception as e:
            self._logger.error(
                f"repo.assign_to.conflict_or_error - item_id={item_id}, user_id={user_id}, dataset={ds}, "
                f"error_type={type(e).__name__}, error='{str(e)}', status_code={getattr(e, 'status_code', None)}, "
                f"partition_key={partition_key}, method=read_modify_replace"
            )
            return False

    async def list_assigned(self, user_id: str) -> list[GroundTruthItem]:
        await self._ensure_initialized()
        query = "SELECT * FROM c WHERE c.assignedTo = @u AND c.status = 'draft'"
        gt = self._gt_container
        assert gt is not None
        it = gt.query_items(
            query=query,
            parameters=[{"name": "@u", "value": user_id}],
            enable_scan_in_query=True,
        )  # type: ignore
        items: list[GroundTruthItem] = []
        async for doc in it:  # type: ignore
            items.append(self._from_doc(doc))
        self._logger.debug("repo.list_assigned", extra={"count": len(items)})
        return items

    # Assignment documents APIs (assignments container)
    async def upsert_assignment_doc(self, user_id: str, gt: GroundTruthItem) -> AssignmentDocument:
        await self._ensure_initialized()
        doc_id = f"{gt.datasetName}|{str(gt.bucket)}|{gt.id}"
        ad = AssignmentDocument(
            id=doc_id,
            pk=f"sme:{user_id}",
            ground_truth_id=gt.id,
            datasetName=gt.datasetName,
            bucket=(
                gt.bucket if gt.bucket is not None else UUID("00000000-0000-0000-0000-000000000000")
            ),
        )
        body = ad.model_dump(mode="json", by_alias=True)

        # When using Cosmos emulator locally, ensure UTF-8 characters are preserved
        if settings.COSMOS_DISABLE_UNICODE_ESCAPE:
            body = CosmosGroundTruthRepo._ensure_utf8_strings(body)

        ac = self._assignments_container
        assert ac is not None
        res = await ac.upsert_item(body)  # type: ignore
        return AssignmentDocument.model_validate(res)

    async def list_assignments_by_user(self, user_id: str) -> list[AssignmentDocument]:
        await self._ensure_initialized()
        query = "SELECT * FROM c WHERE c.pk = @pk"
        ac = self._assignments_container
        assert ac is not None
        it = ac.query_items(
            query=query,
            parameters=[{"name": "@pk", "value": f"sme:{user_id}"}],
            enable_scan_in_query=False,
        )  # type: ignore
        res: list[AssignmentDocument] = []
        async for doc in it:  # type: ignore
            if settings.COSMOS_DISABLE_UNICODE_ESCAPE:
                doc = _restore_unicode_from_cosmos(doc)
            res.append(AssignmentDocument.model_validate(doc))
        return res

    async def get_assignment_by_gt(
        self, user_id: str, ground_truth_id: str
    ) -> AssignmentDocument | None:
        await self._ensure_initialized()
        query = "SELECT TOP 1 * FROM c WHERE c.pk = @pk AND c.ground_truth_id = @gtid"
        ac = self._assignments_container
        assert ac is not None
        it = ac.query_items(
            query=query,
            parameters=[
                {"name": "@pk", "value": f"sme:{user_id}"},
                {"name": "@gtid", "value": ground_truth_id},
            ],
            enable_scan_in_query=False,
        )  # type: ignore
        async for doc in it:  # type: ignore
            if settings.COSMOS_DISABLE_UNICODE_ESCAPE:
                doc = _restore_unicode_from_cosmos(doc)
            return AssignmentDocument.model_validate(doc)
        return None

    async def delete_assignment_doc(
        self, user_id: str, dataset: str, bucket: UUID, ground_truth_id: str
    ) -> bool:
        """Delete an assignment document from the assignments container.

        Returns True if deleted successfully, False if not found.
        """
        await self._ensure_initialized()
        pk = f"sme:{user_id}"
        item_id = f"{dataset}|{str(bucket)}|{ground_truth_id}"
        ac = self._assignments_container
        assert ac is not None
        try:
            await ac.delete_item(item=item_id, partition_key=pk)
            self._logger.debug(f"Deleted assignment document: {item_id}")
            return True
        except CosmosResourceNotFoundError:
            # Assignment already deleted or never existed - this is OK
            self._logger.debug(f"Assignment {item_id} already deleted or not found")
            return False
        except Exception as e:
            self._logger.error(f"Failed to delete assignment for item {item_id}: {e}")
            raise
