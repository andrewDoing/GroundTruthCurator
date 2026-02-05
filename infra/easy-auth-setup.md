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

* Azure CLI logged in to the target subscription
* A deployed Container App with ingress enabled
* Permission to create Entra app registrations in the target tenant

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

## Enable Easy Auth on the Container App

1. Enable auth and configure the Microsoft provider:

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

2. Set app environment variables to align with Easy Auth:

   ```bash
   az containerapp update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --set-env-vars \
     GTC_EZAUTH_ENABLED=true \
     GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS="/healthz,/metrics"
   ```

3. Optional allowlist controls for production:

   ```bash
   az containerapp update \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --set-env-vars \
     GTC_EZAUTH_ALLOWED_EMAIL_DOMAINS="example.com" \
     GTC_EZAUTH_ALLOWED_OBJECT_IDS="00000000-0000-0000-0000-000000000000"
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

* Redirect loop: confirm the exact FQDN and redirect URI in the app registration
* 401 after sign-in: verify `GTC_EZAUTH_ENABLED=true` and reapply the auth settings
* Access still blocked: check `GTC_EZAUTH_ALLOWED_EMAIL_DOMAINS` and `GTC_EZAUTH_ALLOWED_OBJECT_IDS`
