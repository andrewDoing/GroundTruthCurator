---
title: Demo deployment guide
description: Steps to deploy Ground Truth Curator to Azure for a hands-on demo.
author: Ground Truth Curator Team
ms.date: 2026-02-03
ms.topic: how-to
keywords:
  - demo
  - azure container apps
  - cosmos db
  - deployment
estimated_reading_time: 8
---

## Overview

This guide walks you through a demo deployment that uses Azure Container Apps and Azure Cosmos DB. It assumes you will run without Easy Auth initially and enable it later when you have an Entra app registration.

> [!IMPORTANT]
> Running without Easy Auth is not secure for public internet access. Use internal ingress or restrict access when you run in dev auth mode.

## Prerequisites

* Azure CLI logged in to the target subscription
* Azure role that can create resource groups, Container Apps, Cosmos DB, and ACR
* Docker or compatible container build tool
* Python and uv for backend scripts

## Step 1: Deploy shared infrastructure

Deploy the Cosmos DB account and the Container Apps environment.

```bash
az deployment group create \
  --resource-group <resource-group> \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam
```

## Step 2: Create a container registry

```bash
az acr create \
  --name <acr-name> \
  --resource-group <resource-group> \
  --location <location> \
  --sku Basic
```

## Step 3: Build and push the backend image

1. Log in to ACR:

   ```bash
   az acr login --name <acr-name>
   ```

2. Build and push the image:

   ```bash
   docker build -t <acr-name>.azurecr.io/gtc-backend:demo -f backend/Dockerfile .
   docker push <acr-name>.azurecr.io/gtc-backend:demo
   ```

## Step 4: Create Cosmos containers

Initialize the default containers using Azure AD authentication.

```bash
cd backend
uv run python scripts/cosmos_container_manager.py \
  --endpoint https://<cosmos-account>.documents.azure.com:443/ \
  --use-aad \
  --db <cosmos-db-name> \
  --gt-container \
  --assignments-container \
  --tags-container \
  --tag-definitions-container \
  --indexing-policy scripts/indexing-policy.json
```

## Step 5: Create the Container App

Create the app first. Replace the placeholders.

```bash
az containerapp create \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --environment <container-apps-env-name> \
  --image <acr-name>.azurecr.io/gtc-backend:demo \
  --ingress external \
  --target-port 8080 \
  --min-replicas 1 \
  --max-replicas 1
```

## Step 6: Configure Easy Auth before app settings

Follow [docs/operations/easy-auth-setup.md](docs/operations/easy-auth-setup.md) once the app exists. Apply Easy Auth first so you can align auth configuration before setting runtime variables.

### Create the Entra app registration

1. Create an app registration in the Azure portal or via CLI:

   ```bash
   az ad app create --display-name "GTC Demo"
   ```

2. Note the **Application (client) ID** from the output.

3. **Enable ID token implicit grant** (required for Easy Auth):

   ```bash
   # Using the Application (client) ID
   az ad app update --id <APP_CLIENT_ID> --enable-id-token-issuance true
   ```

   Or via the portal: **Entra ID** → **App registrations** → **GTC Demo** → **Authentication** → check **ID tokens (used for implicit and hybrid flows)** → **Save**.

4. Add a redirect URI for the Container App callback:

   ```bash
   az ad app update --id <APP_CLIENT_ID> \
     --web-redirect-uris "https://<container-app-fqdn>/.auth/login/aad/callback"
   ```

5. Create a client secret:

   ```bash
   az ad app credential reset --id <APP_CLIENT_ID> --append
   ```

   Save the generated password—you will need it for Easy Auth configuration.

6. Create the Enterprise App (service principal) and allow all users:

   ```bash
   az ad sp create --id <APP_CLIENT_ID>
   az ad sp update --id <APP_CLIENT_ID> --set appRoleAssignmentRequired=false
   ```

### Configure Easy Auth on Container Apps

```bash
az containerapp auth microsoft update \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --client-id <APP_CLIENT_ID> \
  --client-secret <CLIENT_SECRET> \
  --issuer https://login.microsoftonline.com/<TENANT_ID>/v2.0 \
  --yes
```

> [!NOTE]
> If you see error `AADSTS700054: response_type 'id_token' is not enabled`, you need to enable the ID token implicit grant as shown in step 3 above.

## Step 7: Set environment variables

Set required environment variables for Cosmos and the auth mode you configured:

```bash
az containerapp update \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --set-env-vars \
  GTC_REPO_BACKEND=cosmos \
  GTC_COSMOS_ENDPOINT=https://<cosmos-account>.documents.azure.com:443/ \
  GTC_COSMOS_DB_NAME=<cosmos-db-name> \
  GTC_COSMOS_CONTAINER_GT=ground_truth \
  GTC_COSMOS_CONTAINER_ASSIGNMENTS=assignments \
  GTC_COSMOS_CONTAINER_TAGS=tags \
  GTC_COSMOS_CONTAINER_TAG_DEFINITIONS=tag_definitions \
  GTC_EZAUTH_ENABLED=false \
  GTC_AUTH_MODE=dev
```

> [!NOTE]
> In dev auth mode, the API trusts the `X-User-Id` header. Use a gateway or internal access for demos.

## Step 8: Validate the demo

1. Get the app FQDN:

   ```bash
   az containerapp show \
     --name <container-app-name> \
     --resource-group <resource-group> \
     --query properties.configuration.ingress.fqdn \
     --output tsv
   ```

2. Call the health endpoint:

   ```bash
   curl -i https://<container-app-fqdn>/healthz
   ```

3. Call the API with a demo user header:

   ```bash
   curl -i \
     -H "X-User-Id: demo-user" \
     https://<container-app-fqdn>/v1/healthz
   ```

## Cleanup

```bash
az group delete --name <resource-group> --yes --no-wait
```
