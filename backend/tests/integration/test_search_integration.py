from __future__ import annotations

from typing import cast

import pytest
from httpx import AsyncClient
from app.container import container
from app.adapters.search.azure_ai_search import AzureAISearchAdapter
from app.core.config import settings


@pytest.mark.requires_search
@pytest.mark.anyio
async def test_search_hits_real_service(async_client: AsyncClient, user_headers: dict[str, str]):
    # Ensure search is configured; otherwise skip this integration test gracefully
    if not (settings.AZ_SEARCH_ENDPOINT and settings.AZ_SEARCH_INDEX):
        pytest.skip("Azure Search not configured; set GTC_ENV_FILE=environments/sample.env")

    # Skip if no default Azure credential is available (prevents noisy auth failures)
    try:
        from azure.identity import DefaultAzureCredential, CredentialUnavailableError  # type: ignore
        from azure.core.exceptions import ClientAuthenticationError  # type: ignore

        credential = DefaultAzureCredential(
            exclude_interactive_browser_credential=True
        )  # avoid hanging waiting for browser/device flow in CI
        try:
            # Lightweight token request to confirm a usable credential chain exists.
            # Azure Search uses https://search.azure.com/.default scope.
            credential.get_token("https://search.azure.com/.default")  # type: ignore[no-untyped-call]
        except CredentialUnavailableError:
            pytest.skip("No default Azure credential available for Azure Search integration test")
        except ClientAuthenticationError:
            # Azure CLI installed but not logged in (or token acquisition failed) -> treat as infra gap, not a test failure.
            pytest.skip(
                "Azure credential chain present but authentication failed (e.g., az not logged in)"
            )
        except Exception:
            # Any other exception means credentials were found but may be invalid; let the test proceed to surface a real service/adapter issue.
            pass
    except ImportError:
        pytest.skip("azure.identity not installed; skipping Azure Search integration test")
    svc = container.search_service
    if getattr(svc, "adapter", None) is None:
        pytest.skip("Search adapter is not configured; app not wired for Azure Search")
    assert isinstance(svc.adapter, AzureAISearchAdapter), (
        "Search adapter is not AzureAISearchAdapter"
    )
    # This test calls the actual /v1/search endpoint which in turn hits the configured Azure AI Search.
    # Integration env must provide AZ_SEARCH_* settings via environments/sample.env.
    r = await async_client.get("/v1/search", params={"q": "*", "top": 2}, headers=user_headers)
    assert r.status_code == 200
    body = cast(dict[str, object], r.json())
    assert isinstance(body, dict)
    assert "results" in body and isinstance(body["results"], list)
    results = cast(list[dict[str, object]], body["results"])  # type: ignore[assignment]
    assert all(set(x.keys()) >= {"url"} for x in results)
    assert all(set(x.keys()) >= {"title"} for x in results)
    assert all(set(x.keys()) >= {"chunk"} for x in results)
