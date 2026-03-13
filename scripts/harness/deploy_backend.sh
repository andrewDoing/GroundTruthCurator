#!/usr/bin/env bash

set -euo pipefail

err() {
  printf "ERROR: %s\n" "$1" >&2
  exit 1
}

missing_vars=()

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || err "'$cmd' command is required"
}

require_var() {
  local name="$1"
  [[ -n "${!name:-}" ]] || missing_vars+=("$name")
}

python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    echo python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    echo python
    return
  fi
  err "python3 or python is required"
}

require_cmd az

PYTHON_BIN="$(python_cmd)"

require_var AZURE_SUBSCRIPTION_ID
require_var AZURE_TENANT_ID
require_var RESOURCE_GROUP_NAME
require_var GROUND_TRUTH_CURATION_NAME
require_var USER_ASSIGNED_IDENTITY
require_var ENVIRONMENT_NAME
require_var AUTH_CLIENT_ID
require_var GT_COSMOS_DB_ACCOUNT
require_var GTC_COSMOS_DB_NAME

if [[ -z "${CONTAINER_IMAGE:-}" ]]; then
  require_var REGISTRY_PREFIX
  require_var TAG_NAME
fi

if (( ${#missing_vars[@]} > 0 )); then
  err "Missing required environment variables: ${missing_vars[*]}"
fi

GT_COSMOS_DB_RESOURCE_GROUP="${GT_COSMOS_DB_RESOURCE_GROUP:-$RESOURCE_GROUP_NAME}"
GT_COSMOS_DB_INDEXING_POLICY="${GT_COSMOS_DB_INDEXING_POLICY:-backend/scripts/indexing-policy.json}"
WORKLOAD_PROFILE_NAME="${WORKLOAD_PROFILE_NAME:-ai-apps}"
CONTAINER_CPU="${CONTAINER_CPU:-0.5}"
CONTAINER_MEMORY="${CONTAINER_MEMORY:-1.0Gi}"
CONTAINER_IMAGE="${CONTAINER_IMAGE:-${REGISTRY_PREFIX}.azurecr.io/gtc-backend:${TAG_NAME}}"
REGISTRY_SERVER="${REGISTRY_SERVER:-}"
if [[ -z "$REGISTRY_SERVER" && "$CONTAINER_IMAGE" == */* ]]; then
  REGISTRY_SERVER="${CONTAINER_IMAGE%%/*}"
fi
[[ -n "$REGISTRY_SERVER" ]] || err "Set REGISTRY_SERVER or provide CONTAINER_IMAGE with a registry hostname"
GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS="${GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS:-/healthz,/metrics}"
GTC_COSMOS_CONTAINER_GT="${GTC_COSMOS_CONTAINER_GT:-ground_truth}"
GTC_COSMOS_CONTAINER_ASSIGNMENTS="${GTC_COSMOS_CONTAINER_ASSIGNMENTS:-assignments}"
GTC_COSMOS_CONTAINER_TAGS="${GTC_COSMOS_CONTAINER_TAGS:-tags}"
GT_COSMOS_CONTAINER_GT_MAX_THROUGHPUT="${GT_COSMOS_CONTAINER_GT_MAX_THROUGHPUT:-1000}"
GT_COSMOS_CONTAINER_ASSIGNMENTS_MAX_THROUGHPUT="${GT_COSMOS_CONTAINER_ASSIGNMENTS_MAX_THROUGHPUT:-1000}"
GT_COSMOS_CONTAINER_TAGS_MAX_THROUGHPUT="${GT_COSMOS_CONTAINER_TAGS_MAX_THROUGHPUT:-1000}"
GTC_COSMOS_CONTAINER_TAG_DEFINITIONS="${GTC_COSMOS_CONTAINER_TAG_DEFINITIONS:-}"
GT_COSMOS_CONTAINER_TAG_DEFINITIONS_MAX_THROUGHPUT="${GT_COSMOS_CONTAINER_TAG_DEFINITIONS_MAX_THROUGHPUT:-$GT_COSMOS_CONTAINER_TAGS_MAX_THROUGHPUT}"

[[ -f "$GT_COSMOS_DB_INDEXING_POLICY" ]] || err "Indexing policy file not found: $GT_COSMOS_DB_INDEXING_POLICY"

az account show --output none >/dev/null 2>&1 || err "Azure CLI is not logged in"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az extension add --name containerapp --upgrade

printf 'Deploying image: %s\n' "$CONTAINER_IMAGE"
printf 'Container app: %s\n' "$GROUND_TRUTH_CURATION_NAME"
printf 'Resource group: %s\n' "$RESOURCE_GROUP_NAME"
printf 'Cosmos account: %s\n' "$GT_COSMOS_DB_ACCOUNT"

managed_identity_resource="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourcegroups/${RESOURCE_GROUP_NAME}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${USER_ASSIGNED_IDENTITY}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
env_yaml_file="$tmp_dir/env.yaml"
config_file="$tmp_dir/container-config.yaml"

"$PYTHON_BIN" - <<'PY' >"$env_yaml_file"
import json
import os

keys = []
for key in os.environ:
    if (
        key.startswith("GTC_")
        or key.startswith("APPLICATIONINSIGHTS_")
        or key == "AZURE_CLIENT_ID"
        or key.startswith("HEALTHCHECK_")
    ):
        keys.append(key)

for key in sorted(keys):
    print(f"                    - name: {key}")
    print(f"                      value: {json.dumps(os.environ[key])}")
PY

env_line="env: []"
env_block=""
if [[ -s "$env_yaml_file" ]]; then
  env_line="env:"
  env_block="$(cat "$env_yaml_file")"
fi

pip_install=("$PYTHON_BIN" -m pip install --disable-pip-version-check)
if "$PYTHON_BIN" -m pip help install 2>/dev/null | grep -q -- "--break-system-packages"; then
  pip_install+=(--break-system-packages)
fi

{
cat <<EOF
identity:
  type: UserAssigned
  userAssignedIdentities:
    "${managed_identity_resource}": {}
properties:
  workloadProfileName: ${WORKLOAD_PROFILE_NAME}
  configuration:
    ingress:
      external: true
      targetPort: 8080
  template:
    replicas:
      min: 1
      max: 1
    scale:
      rules: []
    containers:
      - name: ${GROUND_TRUTH_CURATION_NAME}
        image: ${CONTAINER_IMAGE}
        resources:
          cpu: ${CONTAINER_CPU}
          memory: ${CONTAINER_MEMORY}
        ${env_line}
EOF
if [[ -n "$env_block" ]]; then
  printf '%s\n' "$env_block"
fi
cat <<EOF
        probes:
          - type: Liveness
            httpGet:
              path: "/healthz"
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 60
            timeoutSeconds: 30
            successThreshold: 1
            failureThreshold: 3
          - type: Readiness
            httpGet:
              path: "/healthz"
              port: 8080
            initialDelaySeconds: 0
            periodSeconds: 10
            timeoutSeconds: 1
            successThreshold: 1
            failureThreshold: 3
EOF
} >"$config_file"

if az containerapp show --name "$GROUND_TRUTH_CURATION_NAME" --resource-group "$RESOURCE_GROUP_NAME" >/dev/null 2>&1; then
  az containerapp update \
    --name "$GROUND_TRUTH_CURATION_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --yaml "$config_file"
else
  az containerapp create \
    --name "$GROUND_TRUTH_CURATION_NAME" \
    --registry-identity system-environment \
    --registry-server "$REGISTRY_SERVER" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --environment "$ENVIRONMENT_NAME" \
    --image "$CONTAINER_IMAGE" \
    --workload-profile-name "$WORKLOAD_PROFILE_NAME" \
    --min-replicas 1 \
    --max-replicas 1 \
    --user-assigned "$managed_identity_resource"

  az containerapp update \
    --name "$GROUND_TRUTH_CURATION_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --yaml "$config_file"
fi

az containerapp update \
  --name "$GROUND_TRUTH_CURATION_NAME" \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --min-replicas 1 \
  --max-replicas 1

while IFS= read -r rule; do
  [[ -n "$rule" ]] || continue
  az containerapp update \
    --name "$GROUND_TRUTH_CURATION_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --remove-scale-rule "$rule"
done < <(
  az containerapp show \
    --name "$GROUND_TRUTH_CURATION_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "properties.template.scale.rules[].name" \
    --output tsv
)

az containerapp revision set-mode \
  --name "$GROUND_TRUTH_CURATION_NAME" \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --mode single

az containerapp auth update \
  --name "$GROUND_TRUTH_CURATION_NAME" \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --enabled true \
  --unauthenticated-client-action RedirectToLoginPage \
  --excluded-paths "$GTC_EZAUTH_ALLOW_ANONYMOUS_PATHS" \
  --yes

az containerapp auth microsoft update \
  --name "$GROUND_TRUTH_CURATION_NAME" \
  --resource-group "$RESOURCE_GROUP_NAME" \
  --client-id "$AUTH_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID"

if ! az cosmosdb sql database show \
  --account-name "$GT_COSMOS_DB_ACCOUNT" \
  --name "$GTC_COSMOS_DB_NAME" \
  --resource-group "$GT_COSMOS_DB_RESOURCE_GROUP" >/dev/null 2>&1; then
  az cosmosdb sql database create \
    --account-name "$GT_COSMOS_DB_ACCOUNT" \
    --name "$GTC_COSMOS_DB_NAME" \
    --resource-group "$GT_COSMOS_DB_RESOURCE_GROUP"
fi

if az cosmosdb sql container show \
  --account-name "$GT_COSMOS_DB_ACCOUNT" \
  --database-name "$GTC_COSMOS_DB_NAME" \
  --name "$GTC_COSMOS_CONTAINER_GT" \
  --resource-group "$GT_COSMOS_DB_RESOURCE_GROUP" >/dev/null 2>&1; then
  az cosmosdb sql container update \
    --account-name "$GT_COSMOS_DB_ACCOUNT" \
    --database-name "$GTC_COSMOS_DB_NAME" \
    --name "$GTC_COSMOS_CONTAINER_GT" \
    --resource-group "$GT_COSMOS_DB_RESOURCE_GROUP" \
    --idx "@${GT_COSMOS_DB_INDEXING_POLICY}"
else
  "${pip_install[@]}" azure-identity azure-cosmos
  "$PYTHON_BIN" backend/scripts/cosmos_container_manager.py \
    --endpoint "https://${GT_COSMOS_DB_ACCOUNT}.documents.azure.com:443/" \
    --use-aad \
    --db "$GTC_COSMOS_DB_NAME" \
    --gt-container "$GTC_COSMOS_CONTAINER_GT" \
    --indexing-policy "$GT_COSMOS_DB_INDEXING_POLICY" \
    --max-throughput "$GT_COSMOS_CONTAINER_GT_MAX_THROUGHPUT"
fi

az cosmosdb sql container throughput update \
  --account-name "$GT_COSMOS_DB_ACCOUNT" \
  --database-name "$GTC_COSMOS_DB_NAME" \
  --name "$GTC_COSMOS_CONTAINER_GT" \
  --resource-group "$GT_COSMOS_DB_RESOURCE_GROUP" \
  --max-throughput "$GT_COSMOS_CONTAINER_GT_MAX_THROUGHPUT"

ensure_simple_container() {
  local container_name="$1"
  local partition_key="$2"
  local max_throughput="$3"

  if ! az cosmosdb sql container show \
    --account-name "$GT_COSMOS_DB_ACCOUNT" \
    --database-name "$GTC_COSMOS_DB_NAME" \
    --name "$container_name" \
    --resource-group "$GT_COSMOS_DB_RESOURCE_GROUP" >/dev/null 2>&1; then
    az cosmosdb sql container create \
      --account-name "$GT_COSMOS_DB_ACCOUNT" \
      --database-name "$GTC_COSMOS_DB_NAME" \
      --name "$container_name" \
      --resource-group "$GT_COSMOS_DB_RESOURCE_GROUP" \
      --partition-key-path "$partition_key" \
      --max-throughput "$max_throughput"
  fi

  az cosmosdb sql container throughput update \
    --account-name "$GT_COSMOS_DB_ACCOUNT" \
    --database-name "$GTC_COSMOS_DB_NAME" \
    --name "$container_name" \
    --resource-group "$GT_COSMOS_DB_RESOURCE_GROUP" \
    --max-throughput "$max_throughput"
}

ensure_simple_container "$GTC_COSMOS_CONTAINER_ASSIGNMENTS" "/pk" "$GT_COSMOS_CONTAINER_ASSIGNMENTS_MAX_THROUGHPUT"
ensure_simple_container "$GTC_COSMOS_CONTAINER_TAGS" "/pk" "$GT_COSMOS_CONTAINER_TAGS_MAX_THROUGHPUT"

if [[ -n "$GTC_COSMOS_CONTAINER_TAG_DEFINITIONS" ]]; then
  ensure_simple_container \
    "$GTC_COSMOS_CONTAINER_TAG_DEFINITIONS" \
    "/tag_key" \
    "$GT_COSMOS_CONTAINER_TAG_DEFINITIONS_MAX_THROUGHPUT"
fi
