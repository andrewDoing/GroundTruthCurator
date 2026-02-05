#!/usr/bin/env bash
#
# deploy-demo-infra.sh
# Deploy infra (Cosmos + Container Apps env) and configure Container App + Easy Auth.
#
## Required Environment Variables (unless provided via flags):
# RESOURCE_GROUP          - Azure resource group name
# CONTAINER_APP_NAME      - Container App name
# CONTAINER_IMAGE         - Container image (registry/image:tag)
# AUTH_CLIENT_ID          - Entra app client ID for Easy Auth
# TENANT_ID               - Entra tenant ID for Easy Auth
#
## Optional Environment Variables:
# ENV_FILE                - Path to .env file to source
# DEPLOYMENT_NAME         - Deployment name for infra
# BICEP_FILE              - Path to main.bicep
# PARAMS_FILE             - Path to main.bicepparam
# RESOURCE_PREFIX         - Name prefix (if not in params file)
# DEPLOY_ENVIRONMENT      - Environment name (if not in params file)
# LOCATION                - Azure location (if not in params file)
# COSMOS_DB_NAME           - Cosmos SQL database name (if not in params file)
# REGISTRY_SERVER         - Container registry server (optional)
# REGISTRY_IDENTITY       - Managed identity for registry access (optional)
# WORKLOAD_PROFILE_NAME   - Container Apps workload profile name (optional)
# CONTAINER_CPU           - Container CPU (default: 0.5)
# CONTAINER_MEMORY        - Container memory (default: 1.0Gi)
# GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS - CSV of paths excluded from Easy Auth
# COSMOS_INDEXING_POLICY  - Indexing policy JSON path (default: backend/scripts/indexing-policy.json)
# SET_COSMOS_KEY          - true|false (default: false)
# COSMOS_MAX_THROUGHPUT   - Autoscale max throughput for containers (default: 1000)

set -euo pipefail

if [[ -z "${BASH_VERSION:-}" ]]; then
  echo "This script requires bash. Run: bash $0 ..." >&2
  exit 1
fi

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  -g, --resource-group NAME     Azure resource group name
  -n, --container-app NAME       Container App name
  -i, --image IMAGE              Container image (registry/image:tag)
  --auth-client-id ID            Entra app client ID for Easy Auth
  --tenant-id ID                 Entra tenant ID for Easy Auth
  --env-file PATH                Path to .env file to source
  --bicep-file PATH              Bicep file (default: infra/main.bicep)
  --params-file PATH             Bicep params file (default: infra/main.bicepparam if present)
  --deployment-name NAME         ARM deployment name (default: gtc-demo-infra)
  --location NAME                Azure location (override)
  --prefix NAME                  Resource prefix (override)
  --environment NAME             Environment name (override)
  --cosmos-db-name NAME          Cosmos SQL database name (override)
  --registry-server NAME         Container registry server (optional)
  --registry-identity ID         Managed identity for registry access (optional)
  --workload-profile NAME        Container Apps workload profile name
  --container-cpu CPU            Container CPU (default: 0.5)
  --container-memory MEMORY      Container memory (default: 1.0Gi)
  --allow-anon-paths CSV         Easy Auth excluded paths
  --cosmos-indexing-policy PATH  Cosmos indexing policy JSON
  --no-cosmos-key                Do not set GTC_COSMOS_KEY in the app env
  -h, --help                     Show this help and exit

Notes:
  - The script deploys infra via Bicep and configures the Container App via az CLI.
  - Easy Auth is enabled at the Container App level using the provided client/tenant.
  - Cosmos containers are created with the Python container manager (HPK-safe).
EOF
}

err() {
  printf "ERROR: %s\n" "$1" >&2
  exit 1
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" &>/dev/null; then
    err "'$cmd' command is required but not installed"
  fi
}

RESOURCE_GROUP="${RESOURCE_GROUP:-}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-}"
CONTAINER_IMAGE="${CONTAINER_IMAGE:-}"
AUTH_CLIENT_ID="${AUTH_CLIENT_ID:-}"
TENANT_ID="${TENANT_ID:-}"
ENV_FILE="${ENV_FILE:-}"
BICEP_FILE="${BICEP_FILE:-infra/main.bicep}"
PARAMS_FILE="${PARAMS_FILE:-}"
DEPLOYMENT_NAME="${DEPLOYMENT_NAME:-gtc-demo-infra}"
LOCATION="${LOCATION:-}"
RESOURCE_PREFIX="${RESOURCE_PREFIX:-}"
DEPLOY_ENVIRONMENT="${DEPLOY_ENVIRONMENT:-}"
COSMOS_DB_NAME="${COSMOS_DB_NAME:-}"
REGISTRY_SERVER="${REGISTRY_SERVER:-}"
REGISTRY_IDENTITY="${REGISTRY_IDENTITY:-}"
WORKLOAD_PROFILE_NAME="${WORKLOAD_PROFILE_NAME:-}"
CONTAINER_CPU="${CONTAINER_CPU:-0.5}"
CONTAINER_MEMORY="${CONTAINER_MEMORY:-1.0Gi}"
ALLOW_ANON_PATHS="${GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS:-}"
COSMOS_INDEXING_POLICY="${COSMOS_INDEXING_POLICY:-backend/scripts/indexing-policy.json}"
SET_COSMOS_KEY="${SET_COSMOS_KEY:-false}"
COSMOS_MAX_THROUGHPUT="${COSMOS_MAX_THROUGHPUT:-1000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -g|--resource-group)
      RESOURCE_GROUP="$2"; shift 2 ;;
    -n|--container-app)
      CONTAINER_APP_NAME="$2"; shift 2 ;;
    -i|--image)
      CONTAINER_IMAGE="$2"; shift 2 ;;
    --auth-client-id)
      AUTH_CLIENT_ID="$2"; shift 2 ;;
    --tenant-id)
      TENANT_ID="$2"; shift 2 ;;
    --env-file)
      ENV_FILE="$2"; shift 2 ;;
    --bicep-file)
      BICEP_FILE="$2"; shift 2 ;;
    --params-file)
      PARAMS_FILE="$2"; shift 2 ;;
    --deployment-name)
      DEPLOYMENT_NAME="$2"; shift 2 ;;
    --location)
      LOCATION="$2"; shift 2 ;;
    --prefix)
      RESOURCE_PREFIX="$2"; shift 2 ;;
    --environment)
      DEPLOY_ENVIRONMENT="$2"; shift 2 ;;
    --cosmos-db-name)
      COSMOS_DB_NAME="$2"; shift 2 ;;
    --registry-server)
      REGISTRY_SERVER="$2"; shift 2 ;;
    --registry-identity)
      REGISTRY_IDENTITY="$2"; shift 2 ;;
    --workload-profile)
      WORKLOAD_PROFILE_NAME="$2"; shift 2 ;;
    --container-cpu)
      CONTAINER_CPU="$2"; shift 2 ;;
    --container-memory)
      CONTAINER_MEMORY="$2"; shift 2 ;;
    --allow-anon-paths)
      ALLOW_ANON_PATHS="$2"; shift 2 ;;
    --cosmos-indexing-policy)
      COSMOS_INDEXING_POLICY="$2"; shift 2 ;;
    --no-cosmos-key)
      SET_COSMOS_KEY="false"; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -n "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    err "Env file not found: $ENV_FILE"
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

RESOURCE_GROUP="${RESOURCE_GROUP:-}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-}"
CONTAINER_IMAGE="${CONTAINER_IMAGE:-}"
AUTH_CLIENT_ID="${AUTH_CLIENT_ID:-}"
TENANT_ID="${TENANT_ID:-}"
LOCATION="${LOCATION:-}"
RESOURCE_PREFIX="${RESOURCE_PREFIX:-}"
DEPLOY_ENVIRONMENT="${DEPLOY_ENVIRONMENT:-}"
COSMOS_DB_NAME="${COSMOS_DB_NAME:-}"
REGISTRY_SERVER="${REGISTRY_SERVER:-}"
REGISTRY_IDENTITY="${REGISTRY_IDENTITY:-}"
WORKLOAD_PROFILE_NAME="${WORKLOAD_PROFILE_NAME:-}"
CONTAINER_CPU="${CONTAINER_CPU:-0.5}"
CONTAINER_MEMORY="${CONTAINER_MEMORY:-1.0Gi}"
ALLOW_ANON_PATHS="${GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS:-$ALLOW_ANON_PATHS}"
COSMOS_INDEXING_POLICY="${COSMOS_INDEXING_POLICY:-backend/scripts/indexing-policy.json}"
SET_COSMOS_KEY="${SET_COSMOS_KEY:-true}"
COSMOS_MAX_THROUGHPUT="${COSMOS_MAX_THROUGHPUT:-1000}"

require_cmd az
if ! command -v uv &>/dev/null && ! command -v python &>/dev/null; then
  err "Python is required but not installed."
fi

if [[ -z "$RESOURCE_GROUP" ]]; then
  err "Resource group is required (--resource-group or RESOURCE_GROUP)."
fi
if [[ -z "$CONTAINER_APP_NAME" ]]; then
  err "Container App name is required (--container-app or CONTAINER_APP_NAME)."
fi
if [[ -z "$CONTAINER_IMAGE" ]]; then
  err "Container image is required (--image or CONTAINER_IMAGE)."
fi
if [[ -z "$AUTH_CLIENT_ID" ]]; then
  err "Easy Auth client ID is required (--auth-client-id or AUTH_CLIENT_ID)."
fi
if [[ -z "$TENANT_ID" ]]; then
  err "Tenant ID is required (--tenant-id or TENANT_ID)."
fi

if [[ -z "$PARAMS_FILE" && -f "infra/main.bicepparam" ]]; then
  PARAMS_FILE="infra/main.bicepparam"
fi

if [[ -z "$PARAMS_FILE" ]]; then
  if [[ -z "$LOCATION" || -z "$RESOURCE_PREFIX" || -z "$DEPLOY_ENVIRONMENT" || -z "$COSMOS_DB_NAME" ]]; then
    err "When no params file is used, --location, --prefix, --environment, and --cosmos-db-name are required."
  fi
fi

if [[ ! -f "$BICEP_FILE" ]]; then
  err "Bicep file not found: $BICEP_FILE"
fi

if [[ -n "$PARAMS_FILE" && ! -f "$PARAMS_FILE" ]]; then
  err "Params file not found: $PARAMS_FILE"
fi

if [[ ! -f "$COSMOS_INDEXING_POLICY" ]]; then
  err "Indexing policy file not found: $COSMOS_INDEXING_POLICY"
fi

if ! az account show --output none &>/dev/null; then
  err "Azure CLI not logged in. Run: az login"
fi

az extension add --name containerapp --upgrade

params_args=()
if [[ -n "$PARAMS_FILE" ]]; then
  params_args+=(--parameters "@$PARAMS_FILE")
fi
if [[ -n "$LOCATION" ]]; then
  params_args+=(--parameters location="$LOCATION")
fi
if [[ -n "$RESOURCE_PREFIX" ]]; then
  params_args+=(--parameters resourcePrefix="$RESOURCE_PREFIX")
fi
if [[ -n "$DEPLOY_ENVIRONMENT" ]]; then
  params_args+=(--parameters environment="$DEPLOY_ENVIRONMENT")
fi
if [[ -n "$COSMOS_DB_NAME" ]]; then
  params_args+=(--parameters cosmosDatabaseName="$COSMOS_DB_NAME")
fi

az deployment group create \
  --name "$DEPLOYMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$BICEP_FILE" \
  "${params_args[@]}"

cosmos_account_name=$(az deployment group show \
  --name "$DEPLOYMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.outputs.cosmosAccountName.value" \
  --output tsv)
cosmos_endpoint=$(az deployment group show \
  --name "$DEPLOYMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.outputs.cosmosAccountEndpoint.value" \
  --output tsv)
cosmos_db_name=$(az deployment group show \
  --name "$DEPLOYMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.outputs.cosmosDatabaseName.value" \
  --output tsv)
container_env_name=$(az deployment group show \
  --name "$DEPLOYMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.outputs.containerAppsEnvironmentName.value" \
  --output tsv)
managed_identity_id=$(az deployment group show \
  --name "$DEPLOYMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.outputs.managedIdentityId.value" \
  --output tsv)
managed_identity_client_id=$(az deployment group show \
  --name "$DEPLOYMENT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.outputs.managedIdentityClientId.value" \
  --output tsv)

if [[ -z "$cosmos_account_name" || -z "$cosmos_endpoint" || -z "$cosmos_db_name" ]]; then
  err "Failed to read Cosmos outputs from deployment."
fi
if [[ -z "$container_env_name" ]]; then
  err "Failed to read Container Apps environment name from deployment."
fi
if [[ -z "$managed_identity_id" || -z "$managed_identity_client_id" ]]; then
  err "Failed to read managed identity outputs from deployment."
fi

export GTC_COSMOS_ENDPOINT="${GTC_COSMOS_ENDPOINT:-$cosmos_endpoint}"
export GTC_COSMOS_DB_NAME="${GTC_COSMOS_DB_NAME:-$cosmos_db_name}"
export GTC_COSMOS_CONTAINER_GT="${GTC_COSMOS_CONTAINER_GT:-ground_truth}"
export GTC_COSMOS_CONTAINER_ASSIGNMENTS="${GTC_COSMOS_CONTAINER_ASSIGNMENTS:-assignments}"
export GTC_COSMOS_CONTAINER_TAGS="${GTC_COSMOS_CONTAINER_TAGS:-tags}"
export GTC_COSMOS_CONTAINER_TAG_DEFINITIONS="${GTC_COSMOS_CONTAINER_TAG_DEFINITIONS:-tag_definitions}"
export GTC_REPO_BACKEND="${GTC_REPO_BACKEND:-cosmos}"
export GTC_EZAUTH_ENABLED="${GTC_EZAUTH_ENABLED:-true}"

if [[ -z "${AZURE_CLIENT_ID:-}" ]]; then
  export AZURE_CLIENT_ID="$managed_identity_client_id"
fi

if [[ -z "$ALLOW_ANON_PATHS" ]]; then
  ALLOW_ANON_PATHS="/healthz,/metrics"
fi
export GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS="$ALLOW_ANON_PATHS"

if [[ "$SET_COSMOS_KEY" == "true" && -z "${GTC_COSMOS_KEY:-}" ]]; then
  cosmos_key=$(az cosmosdb keys list \
    --name "$cosmos_account_name" \
    --resource-group "$RESOURCE_GROUP" \
    --query primaryMasterKey \
    --output tsv)
  if [[ -z "$cosmos_key" ]]; then
    err "Failed to fetch Cosmos DB account key."
  fi
  export GTC_COSMOS_KEY="$cosmos_key"
fi

env_vars=()
while IFS='=' read -r key value; do
  env_vars+=("${key}=${value}")
done < <(env | grep -E '^(GTC_|APPLICATIONINSIGHTS_|AZURE_CLIENT_ID|HEALTHCHECK_)')

create_cmd=(
  az containerapp create
  --name "$CONTAINER_APP_NAME"
  --resource-group "$RESOURCE_GROUP"
  --environment "$container_env_name"
  --image "$CONTAINER_IMAGE"
  --ingress external
  --target-port 8080
  --min-replicas 1
  --max-replicas 1
  --cpu "$CONTAINER_CPU"
  --memory "$CONTAINER_MEMORY"
)

if [[ -n "$REGISTRY_SERVER" ]]; then
  create_cmd+=(--registry-server "$REGISTRY_SERVER")
fi
if [[ -n "$REGISTRY_IDENTITY" ]]; then
  create_cmd+=(--registry-identity "$REGISTRY_IDENTITY")
fi
if [[ -n "$WORKLOAD_PROFILE_NAME" ]]; then
  create_cmd+=(--workload-profile-name "$WORKLOAD_PROFILE_NAME")
fi
if (( ${#env_vars[@]} > 0 )); then
  create_cmd+=(--env-vars "${env_vars[@]}")
fi

if az containerapp show --name "$CONTAINER_APP_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  update_cmd=(
    az containerapp update
    --name "$CONTAINER_APP_NAME"
    --resource-group "$RESOURCE_GROUP"
    --image "$CONTAINER_IMAGE"
    --ingress external
    --target-port 8080
    --min-replicas 1
    --max-replicas 1
  )
  if [[ -n "$WORKLOAD_PROFILE_NAME" ]]; then
    update_cmd+=(--workload-profile-name "$WORKLOAD_PROFILE_NAME")
  fi
  if (( ${#env_vars[@]} > 0 )); then
    update_cmd+=(--set-env-vars "${env_vars[@]}")
  fi
  "${update_cmd[@]}"
else
  "${create_cmd[@]}"
fi

az containerapp identity assign \
  --name "$CONTAINER_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --user-assigned "$managed_identity_id"

az containerapp revision set-mode \
  --name "$CONTAINER_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --mode single

az containerapp auth update \
  --name "$CONTAINER_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --enabled true \
  --unauthenticated-client-action RedirectToLoginPage \
  --excluded-paths "$GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS" \
  --yes

az containerapp auth microsoft update \
  --name "$CONTAINER_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --client-id "$AUTH_CLIENT_ID" \
  --tenant-id "$TENANT_ID"

RUNNER=()
if command -v uv &>/dev/null; then
  RUNNER=("uv" "run" "python")
elif command -v python3 &>/dev/null; then
  RUNNER=("python3")
else
  RUNNER=("python")
fi

"${RUNNER[@]}" backend/scripts/cosmos_container_manager.py \
  --endpoint "$GTC_COSMOS_ENDPOINT" \
  --use-aad \
  --db "$GTC_COSMOS_DB_NAME" \
  --gt-container "$GTC_COSMOS_CONTAINER_GT" \
  --assignments-container "$GTC_COSMOS_CONTAINER_ASSIGNMENTS" \
  --tags-container "$GTC_COSMOS_CONTAINER_TAGS" \
  --tag-definitions-container "$GTC_COSMOS_CONTAINER_TAG_DEFINITIONS" \
  --indexing-policy "$COSMOS_INDEXING_POLICY" \
  --max-throughput "$COSMOS_MAX_THROUGHPUT"
