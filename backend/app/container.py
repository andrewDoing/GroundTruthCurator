from __future__ import annotations

import logging
from typing import cast, Any

from app.core.config import settings
from app.adapters.repos.base import GroundTruthRepo
from app.services.assignment_service import AssignmentService
from app.services.search_service import SearchService
from app.services.snapshot_service import SnapshotService
from app.services.curation_service import CurationService
from app.adapters.repos.tags_repo import CosmosTagsRepo
from app.services.tag_registry_service import TagRegistryService
from app.exports.formatters.json_items import JsonItemsFormatter
from app.exports.formatters.json_snapshot_payload import JsonSnapshotPayloadFormatter
from app.exports.pipeline import ExportPipeline
from app.exports.processors.merge_tags import MergeTagsProcessor
from app.exports.registry import (
    ExportFormatterRegistry,
    ExportProcessorRegistry,
    parse_processor_order,
)
from app.exports.storage.base import ExportStorage
from app.exports.storage.blob import BlobExportStorage
from app.exports.storage.local import LocalExportStorage
from app.plugins.pack_registry import get_default_pack_registry
from app.plugins.base import PluginPackRegistry
from app.adapters.repos.memory_repo import InMemoryGroundTruthRepo
from app.adapters.search.demo_search import DemoSearchAdapter
from app.demo_seed import DEMO_CURATION_INSTRUCTIONS, build_demo_items


logger = logging.getLogger("gtc.container")


class InMemoryTagsRepo:
    def __init__(self) -> None:
        self.tags: list[str] = []

    async def get_global_tags(self) -> list[str]:
        return list(self.tags)

    async def save_global_tags(self, tags: list[str]) -> list[str]:
        self.tags = sorted(set(tags))
        return list(self.tags)

    async def upsert_add(self, tags_to_add: list[str]) -> list[str]:
        return await self.save_global_tags([*self.tags, *tags_to_add])

    async def upsert_remove(self, tags_to_remove: list[str]) -> list[str]:
        remove = {str(tag) for tag in tags_to_remove}
        self.tags = [tag for tag in self.tags if tag not in remove]
        return list(self.tags)


class Container:
    # Class-level annotations so static checkers understand intended types
    repo: GroundTruthRepo
    assignment_service: AssignmentService
    search_service: SearchService
    snapshot_service: SnapshotService
    curation_service: CurationService
    tag_registry_service: TagRegistryService
    tags_repo: CosmosTagsRepo
    tag_definitions_repo: Any  # CosmosTagDefinitionsRepo
    export_pipeline: ExportPipeline
    export_processor_registry: ExportProcessorRegistry
    export_formatter_registry: ExportFormatterRegistry
    export_storage: ExportStorage
    export_default_processor_order: list[str]
    plugin_pack_registry: PluginPackRegistry

    def __init__(self) -> None:
        # Lazily initialize repo and services. Tests and app lifespan will call
        # init_cosmos_repo() to create an instance bound to the current event loop.
        self.repo = cast(GroundTruthRepo, None)
        self.assignment_service = cast(AssignmentService, None)
        # Provide a no-op search service by default to avoid None checks
        self.search_service = SearchService()
        self.snapshot_service = cast(SnapshotService, None)
        self.curation_service = cast(CurationService, None)
        self.tags_repo = cast(CosmosTagsRepo, None)
        self.tag_definitions_repo = cast(Any, None)
        self.tag_registry_service = cast(TagRegistryService, None)
        self.export_storage = self._build_export_storage()
        self.export_processor_registry = self._build_export_processor_registry()
        self.export_formatter_registry = self._build_export_formatter_registry()
        self.export_pipeline = ExportPipeline(self.export_storage)
        self.export_default_processor_order = parse_processor_order(settings.EXPORT_PROCESSOR_ORDER)
        # Plugin-pack registry — lazily populated on first use (startup_cosmos
        # calls validate_all() to ensure all packs pass their startup checks).
        self.plugin_pack_registry = get_default_pack_registry()

    def _build_default_credential(self) -> Any:
        """Create a DefaultAzureCredential for runtime use.

        Keep simple, rely on standard environment and managed identity when available.
        """
        try:
            from azure.identity.aio import DefaultAzureCredential
        except Exception as e:
            raise RuntimeError(f"azure-identity not installed: {e}")
        # Exclude shared cache for server scenarios to keep minimal surface
        return DefaultAzureCredential(exclude_shared_token_cache_credential=True)

    def _build_export_storage(self) -> ExportStorage:
        if settings.EXPORT_STORAGE_BACKEND == "blob":
            if not settings.EXPORT_BLOB_ACCOUNT_URL or not settings.EXPORT_BLOB_CONTAINER:
                raise RuntimeError(
                    "EXPORT_BLOB_ACCOUNT_URL and EXPORT_BLOB_CONTAINER are required when "
                    "EXPORT_STORAGE_BACKEND is 'blob'"
                )
            return BlobExportStorage(
                account_url=settings.EXPORT_BLOB_ACCOUNT_URL,
                container_name=settings.EXPORT_BLOB_CONTAINER,
            )
        return LocalExportStorage(base_dir=".")

    def _build_export_processor_registry(self) -> ExportProcessorRegistry:
        registry = ExportProcessorRegistry()
        registry.register(MergeTagsProcessor())
        return registry

    def _build_export_formatter_registry(self) -> ExportFormatterRegistry:
        registry = ExportFormatterRegistry()
        registry.register(JsonItemsFormatter())
        registry.register_factory(
            "json_snapshot_payload",
            lambda snapshot_at, filters=None: JsonSnapshotPayloadFormatter(
                snapshot_at=snapshot_at,
                filters=filters,
            ),
        )
        return registry

    def _build_snapshot_service(self, repo: GroundTruthRepo) -> SnapshotService:
        return SnapshotService(
            repo,
            export_pipeline=self.export_pipeline,
            processor_registry=self.export_processor_registry,
            formatter_registry=self.export_formatter_registry,
            default_processor_order=self.export_default_processor_order,
            plugin_export_transforms=self.plugin_pack_registry.collect_export_transforms(),
        )

    def init_cosmos_repo(self, db_name: str | None = None) -> None:
        """Create a Cosmos repo instance and wire services.

        If db_name is provided, override the configured DB name (useful for
        per-test databases). This does not perform any async initialization; the
        caller should await repo._init() or rely on app lifespan to initialize.
        """
        try:
            from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo
        except Exception as e:
            raise RuntimeError(f"Cosmos SDK not available; install azure-cosmos. Error: {e}")
        if not settings.COSMOS_ENDPOINT:
            raise RuntimeError("COSMOS_ENDPOINT must be set for Cosmos backend")

        effective_db = db_name or settings.COSMOS_DB_NAME
        credential = None

        # Guardrails and logging: Emulator and non-TLS endpoints should use key auth
        endpoint_lower = (settings.COSMOS_ENDPOINT or "").lower()
        emulator_flag = bool(getattr(settings, "USE_COSMOS_EMULATOR", False))
        use_emulator_or_non_tls = endpoint_lower.startswith("http://") or emulator_flag

        if not use_emulator_or_non_tls and not settings.COSMOS_KEY:
            # Use DefaultAzureCredential when not using emulator and no key provided
            credential = self._build_default_credential()
        elif not settings.COSMOS_KEY and use_emulator_or_non_tls:
            raise RuntimeError("COSMOS_KEY missing for emulator/non-TLS endpoint")

        self.repo = CosmosGroundTruthRepo(
            endpoint=settings.COSMOS_ENDPOINT,
            key=settings.COSMOS_KEY.get_secret_value() if settings.COSMOS_KEY else None,
            db_name=effective_db,
            gt_container_name=settings.COSMOS_CONTAINER_GT,
            assignments_container_name=settings.COSMOS_CONTAINER_ASSIGNMENTS,
            connection_verify=settings.COSMOS_CONNECTION_VERIFY,
            test_mode=settings.COSMOS_TEST_MODE,
            credential=credential,
        )
        logger.info(
            "Using CosmosGroundTruthRepo (endpoint=%s, db=%s, container=%s)",
            settings.COSMOS_ENDPOINT,
            effective_db,
            settings.COSMOS_CONTAINER_GT,
        )
        logger.debug(
            "Cosmos auth mode: %s",
            "DefaultAzureCredential (AAD)" if credential is not None else "Key (account/emulator)",
        )

        # Recreate services to point at the new repo instance
        self.assignment_service = AssignmentService(self.repo)
        # Keep existing search service (may already be wired with adapter)
        self.search_service = self.search_service or SearchService()
        self.snapshot_service = self._build_snapshot_service(self.repo)
        self.curation_service = CurationService(self.repo)
        # Initialize tags repo and service (shares the same Cosmos account/db)
        self.tags_repo = CosmosTagsRepo(
            endpoint=settings.COSMOS_ENDPOINT,
            key=settings.COSMOS_KEY.get_secret_value() if settings.COSMOS_KEY else None,
            db_name=effective_db,
            container_name=settings.COSMOS_CONTAINER_TAGS,
            connection_verify=settings.COSMOS_CONNECTION_VERIFY,
            credential=credential,
        )
        self.tag_registry_service = TagRegistryService(self.tags_repo)

        # Initialize tag definitions repo
        from app.adapters.repos.tag_definitions_repo import CosmosTagDefinitionsRepo

        self.tag_definitions_repo = CosmosTagDefinitionsRepo(
            endpoint=settings.COSMOS_ENDPOINT,
            key=settings.COSMOS_KEY.get_secret_value() if settings.COSMOS_KEY else None,
            db_name=effective_db,
            container_name=settings.COSMOS_CONTAINER_TAG_DEFINITIONS,
            connection_verify=settings.COSMOS_CONNECTION_VERIFY,
            credential=credential,
        )

    def init_memory_repo(self, *, enable_demo_data: bool = False) -> None:
        demo_items = build_demo_items(settings.DEMO_USER_ID) if enable_demo_data else []
        demo_instructions = DEMO_CURATION_INSTRUCTIONS if enable_demo_data else []
        self.repo = InMemoryGroundTruthRepo(
            items=demo_items,
            curation_instructions=demo_instructions,
        )
        self.assignment_service = AssignmentService(self.repo)
        self.snapshot_service = self._build_snapshot_service(self.repo)
        self.curation_service = CurationService(self.repo)
        self.tags_repo = cast(CosmosTagsRepo, InMemoryTagsRepo())
        self.tag_registry_service = TagRegistryService(self.tags_repo)
        self.tag_definitions_repo = cast(Any, None)
        self.search_service = (
            SearchService(DemoSearchAdapter(demo_items)) if enable_demo_data else SearchService()
        )
        logger.info(
            "Using InMemoryGroundTruthRepo (demo_mode=%s, items=%s)",
            enable_demo_data,
            len(demo_items),
        )

    async def startup_cosmos(self, db_name: str | None = None) -> None:
        """Initialize and validate Cosmos repos and services.

        This is the main entry point for Cosmos backend startup. It:
        1. Creates repo instances via init_cosmos_repo()
        2. Initializes async clients (binds to current event loop)
        3. Validates that database and containers exist

        Args:
            db_name: Optional database name override (for per-test databases)

        Raises:
            RuntimeError: If containers don't exist (with guidance on how to fix)
        """
        from app.adapters.repos.cosmos_repo import CosmosGroundTruthRepo

        # Step 1: Create repo instances
        self.init_cosmos_repo(db_name)

        # Step 2: Initialize async clients
        # At this point self.repo is guaranteed to be CosmosGroundTruthRepo
        assert isinstance(self.repo, CosmosGroundTruthRepo)
        logger.info("Initializing Cosmos repository...")
        await self.repo._init()

        logger.info("Initializing tags repository...")
        await self.tags_repo._init()

        logger.info("Initializing tag definitions repository...")
        await self.tag_definitions_repo._init()

        # Step 3: Validate containers exist
        logger.info("Validating Cosmos DB containers...")
        await self.repo.validate_containers()
        await self.tags_repo.validate_container()
        await self.tag_definitions_repo.validate_container()
        logger.info("Cosmos DB validation passed.")

        # Step 4: Run plugin-pack startup validation so misconfigured packs
        # fail here with an actionable error rather than silently at runtime.
        logger.info("Running plugin-pack startup validation...")
        self.plugin_pack_registry.validate_all()
        logger.info(
            "Plugin-pack validation passed. Registered packs: %s",
            self.plugin_pack_registry.names(),
        )

    def init_search(self) -> None:
        """Configure search adapter if Azure Search settings are present."""
        from app.adapters.search.azure_ai_search import AzureAISearchAdapter

        if (
            settings.REPO_BACKEND == "memory"
            and settings.DEMO_MODE
            and getattr(self.search_service, "adapter", None) is not None
        ):
            logger.info("Using demo search adapter for memory-backed demo mode")
            return

        if settings.AZ_SEARCH_ENDPOINT and settings.AZ_SEARCH_INDEX:
            token_cred = None
            if not settings.AZ_SEARCH_KEY:
                # Use DefaultAzureCredential when no key provided
                token_cred = self._build_default_credential()
            adapter = AzureAISearchAdapter(
                endpoint=settings.AZ_SEARCH_ENDPOINT,
                index_name=settings.AZ_SEARCH_INDEX,
                api_version=settings.AZ_SEARCH_API_VERSION,
                api_key=settings.AZ_SEARCH_KEY.get_secret_value()
                if settings.AZ_SEARCH_KEY
                else None,
                token_credential=token_cred,
            )
            # Replace or create service with adapter-wired instance
            self.search_service = SearchService(adapter)
            logger.info(
                "Using AzureAISearchAdapter (endpoint=%s, index=%s)",
                settings.AZ_SEARCH_ENDPOINT,
                settings.AZ_SEARCH_INDEX,
            )
        else:
            # Keep default no-op search service to satisfy consumers and typing
            self.search_service = self.search_service or SearchService()
            logger.info("Search adapter not configured; using no-op SearchService")


container = Container()
