---
title: Set up Easy Auth for Azure Container Apps
description: Configure Microsoft Entra authentication for the Ground Truth Curator Container App.
author: Ground Truth Curator Team
ms.date: 2026-02-03
ms.topic: how-to
keywords:
  - azure container apps
  - easy auth
  - entra id
  - authentication
estimated_reading_time: 7
---

## Prerequisites

- Azure CLI logged in to the target subscription
- A deployed Container App with ingress enabled
- Permission to create Entra app registrations in the target tenant

## Collect tenant and app details

1. Get the tenant ID:

   ```bash
   az account show --query tenantId --output tsv
   ```

2. Get the Container App FQDN:

   ```bash
   az containerapp show \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --query properties.configuration.ingress.fqdn \
     --output tsv
   ```

3. Build the redirect URI:

   ```text
   https://<container-app-fqdn>/.auth/login/aad/callback
   ```

## Create the Entra app registration

Use the Azure portal or Azure CLI. The examples below use Azure CLI.

1. Create the app registration with the redirect URI:

   ```bash
   az ad app create \
     --display-name "GTC Demo" \
     --web-redirect-uris "https://<container-app-fqdn>/.auth/login/aad/callback"
   ```

2. Capture the `appId` from the output. This is your Easy Auth client ID.

> [!IMPORTANT]
> If you change the Container App FQDN, update the redirect URI in the app registration.

## Create a client secret

Easy Auth requires a client secret to complete the OAuth 2.0 authorization code flow. Without it, the middleware cannot exchange the authorization code for tokens and returns HTTP 401 to the browser.

1. Create a secret on the app registration:

   ```bash
   az ad app credential reset \
     --id <entra-app-client-id> \
     --display-name "EasyAuth" \
     --end-date "2027-01-01"
   ```

   > [!NOTE]
   > Some organizations enforce credential lifetime policies that limit secret
   > expiry (for example, a maximum of 7 days or 6 months). If the command
   > fails with a policy error, reduce `--end-date` to comply with the policy.

2. Copy the `password` value from the output. This is the client secret.

3. Store the secret in the Container App:

   ```bash
   az containerapp secret set \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --secrets microsoft-provider-authentication-secret=<client-secret-value>
   ```

4. Configure the Microsoft auth provider to use the secret:

   ```bash
   az containerapp auth microsoft update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --client-secret-name microsoft-provider-authentication-secret
   ```

## Enable Easy Auth on the Container App

1. Enable a system-assigned managed identity on the Container App (required for the token store):

   ```bash
   az containerapp identity assign \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --system-assigned
   ```

2. Enable auth and configure the Microsoft provider:

   ```bash
   az containerapp auth update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --enabled true \
     --unauthenticated-client-action RedirectToLoginPage \
     --excluded-paths "/healthz,/metrics" \
     --yes

   az containerapp auth microsoft update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --client-id <entra-app-client-id> \
     --tenant-id <entra-tenant-id>
   ```

3. Set app environment variables to align with Easy Auth:

   ```bash
   az containerapp update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --set-env-vars \
     GTC_EZAUTH_ENABLED=true \
     GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS="/healthz,/metrics"
   ```

4. Optional allowlist controls for production:

   ```bash
   az containerapp update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --set-env-vars \
     GTC_EZAUTH_ALLOWED_EMAIL_DOMAINS="example.com" \
     GTC_EZAUTH_ALLOWED_OBJECT_IDS="00000000-0000-0000-0000-000000000000"
   ```

## Configure the token store

Easy Auth uses a token store to persist authentication tokens across requests. Without a token store backed by Azure Blob Storage, the auth middleware cannot maintain session state and the OAuth flow fails silently, returning HTTP 401 to the browser.

1. Create a storage account (or reuse an existing one) and a blob container:

   ```bash
   az storage container create \
     --name <tokenstore-container-name> \
     --account-name <storage-account-name> \
     --auth-mode login
   ```

2. Get the system-assigned identity principal ID of the Container App:

   ```bash
   az containerapp show \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --query identity.principalId \
     --output tsv
   ```

3. Grant the Container App's system-assigned identity `Storage Blob Data Contributor` on the storage account:

   ```bash
   az role assignment create \
     --assignee <system-identity-principal-id> \
     --role "Storage Blob Data Contributor" \
     --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Storage/storageAccounts/<storage-account-name>"
   ```

   > [!IMPORTANT]
   > Without this role assignment, the auth middleware cannot write tokens to
   > blob storage and the OAuth flow silently fails with HTTP 401. RBAC
   > propagation can take 1 to 2 minutes after assignment.

4. Enable the blob-backed token store:

   ```bash
   az containerapp auth update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --token-store true \
     --sas-url-setting-name "" \
     --blob-container-uri "https://<storage-account-name>.blob.core.windows.net/<tokenstore-container-name>"
   ```

5. Create a new revision to pick up the changes:

   ```bash
   az containerapp update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --revision-suffix "auth-$(date +%s)"
   ```

## Validate the setup

1. Open the app URL in a browser. You should be redirected to Microsoft sign-in.
2. After sign-in, call the API:

   ```bash
   curl -i "https://<container-app-fqdn>/v1/healthz"
   ```

   Expect `200 OK` and a JSON response.

> [!NOTE]
> When Easy Auth is enabled, identity headers are injected by Azure Container Apps.
> The backend trusts those headers and does not parse tokens directly.

## Troubleshooting

- **401 when testing with curl**: This is expected. The Easy Auth middleware returns `HTTP 401` with a `WWW-Authenticate: Bearer` header containing the `authorization_uri`. Browsers follow the redirect flow automatically; curl does not. Use a browser or navigate to `/.auth/login/aad` to initiate login manually.
- **401 in the browser after deploying**: Verify all three of these are configured:
  1. A client secret exists on the Entra app registration and is stored as a Container App secret referenced by `--client-secret-name`.
  2. A blob-backed token store is enabled with a valid `--blob-container-uri`.
  3. The Container App's system-assigned identity has `Storage Blob Data Contributor` on the token store storage account. RBAC propagation can take 1 to 2 minutes.
- **Redirect loop**: Confirm the exact FQDN and redirect URI in the app registration match the Container App's ingress FQDN. The redirect URI must be `https://<fqdn>/.auth/login/aad/callback`.
- **Access still blocked after sign-in**: Check `GTC_EZAUTH_ALLOWED_EMAIL_DOMAINS` and `GTC_EZAUTH_ALLOWED_OBJECT_IDS`. If these are set, only matching users are allowed.
- **Client secret creation fails with policy error**: Some organizations enforce credential lifetime policies. Reduce the `--end-date` value on `az ad app credential reset` to comply (for example, 7 days or 6 months depending on the policy).
- **Auth config not taking effect**: After changing auth settings, create a new revision with `az containerapp update --revision-suffix <unique-suffix>` to ensure the auth middleware picks up the changes.
