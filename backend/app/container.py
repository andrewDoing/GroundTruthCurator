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
from app.adapters.gtc_inference_adapter import GTCInferenceAdapter
from app.services.chat_service import ChatService
from app.adapters.agent_steps_store import AgentStepsStore
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


logger = logging.getLogger("gtc.container")


class Container:
    # Class-level annotations so static checkers understand intended types
    repo: GroundTruthRepo
    assignment_service: AssignmentService
    search_service: SearchService
    snapshot_service: SnapshotService
    curation_service: CurationService
    tag_registry_service: TagRegistryService
    tags_repo: CosmosTagsRepo
    inference_service: GTCInferenceAdapter | None
    chat_service: ChatService
    agent_steps_store: AgentStepsStore | None
    export_pipeline: ExportPipeline
    export_processor_registry: ExportProcessorRegistry
    export_formatter_registry: ExportFormatterRegistry
    export_storage: ExportStorage
    export_default_processor_order: list[str]

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
        self.tag_registry_service = cast(TagRegistryService, None)
        self.inference_service = None  # Lazily initialized by init_chat()
        self.agent_steps_store = cast(AgentStepsStore | None, None)
        self.export_storage = self._build_export_storage()
        self.export_processor_registry = self._build_export_processor_registry()
        self.export_formatter_registry = self._build_export_formatter_registry()
        self.export_pipeline = ExportPipeline(self.export_storage)
        self.export_default_processor_order = parse_processor_order(settings.EXPORT_PROCESSOR_ORDER)
        self.chat_service = ChatService(
            inference_service=None,
            steps_store=self.agent_steps_store,
            store_steps=settings.STORE_AGENT_STEPS,
        )

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
        self.snapshot_service = SnapshotService(
            self.repo,
            export_pipeline=self.export_pipeline,
            processor_registry=self.export_processor_registry,
            formatter_registry=self.export_formatter_registry,
            default_processor_order=self.export_default_processor_order,
        )
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

        # Step 3: Validate containers exist
        logger.info("Validating Cosmos DB containers...")
        await self.repo.validate_containers()
        await self.tags_repo.validate_container()
        logger.info("Cosmos DB validation passed.")

    def init_search(self) -> None:
        """Configure search adapter if Azure Search settings are present."""
        from app.adapters.search.azure_ai_search import AzureAISearchAdapter

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

    def _build_sync_default_credential(self) -> Any:
        """Create a sync DefaultAzureCredential for runtime use.
        Used for GTCInferenceAdapter which requires sync credentials.
        """
        try:
            from azure.identity import DefaultAzureCredential
        except Exception as e:
            raise RuntimeError(f"azure-identity not installed: {e}")
        # Exclude shared cache for server scenarios to keep minimal surface
        return DefaultAzureCredential(exclude_shared_token_cache_credential=True)

    def init_chat(self) -> None:
        """Configure chat inference service and chat service.

        Validates that retrieval configuration is present when agent is configured.
        Uses managed identity for both agent auth and retrieval token minting.
        """
        project_endpoint = settings.AZURE_AI_PROJECT_ENDPOINT
        agent_id = settings.AZURE_AI_AGENT_ID
        retrieval_url = settings.RETRIEVAL_URL
        permissions_scope = settings.RETRIEVAL_PERMISSIONS_SCOPE

        # Only build the inference service when fully configured.
        if not project_endpoint or not agent_id:
            self.inference_service = None
        elif not retrieval_url or not permissions_scope:
            logger.error(
                "Agent is configured but retrieval settings missing. "
                "Set GTC_RETRIEVAL_URL and GTC_RETRIEVAL_PERMISSIONS_SCOPE."
            )
            # Mark as not configured so we fail at runtime with 502
            self.inference_service = None
        else:
            # Use sync DefaultAzureCredential for GTCInferenceAdapter
            # (reused for both agent auth and retrieval token minting)
            credential = self._build_sync_default_credential()

            self.inference_service = GTCInferenceAdapter(
                project_endpoint=project_endpoint,
                agent_id=agent_id,
                retrieval_url=retrieval_url,
                permissions_scope=permissions_scope,
                timeout_seconds=settings.RETRIEVAL_TIMEOUT_SECONDS,
                credential=credential,
            )

        # Reuse any existing steps store instance (may be configured elsewhere)
        store = getattr(self, "agent_steps_store", None)
        self.chat_service = ChatService(
            inference_service=self.inference_service,
            steps_store=store,
            store_steps=settings.STORE_AGENT_STEPS and bool(store),
        )

        if not settings.CHAT_ENABLED:
            self.chat_service.set_store_steps(False)
            logger.info("Chat service disabled via settings")
        elif not self.inference_service:
            logger.info("Chat service running in mock mode (agent not configured)")
        else:
            logger.info(
                "Chat service configured with Azure AI Project (endpoint=%s, agent=%s)",
                settings.AZURE_AI_PROJECT_ENDPOINT,
                settings.AZURE_AI_AGENT_ID,
            )


container = Container()
