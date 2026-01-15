# Cosmos Container Manager

Unified Cosmos DB container initialization script supporting both Azure-deployed Cosmos DB (Azure AD auth) and local Cosmos Emulator (key auth).

## Features

- **Dual Authentication**: Azure AD (`DefaultAzureCredential`) or key-based authentication
- **Partition Key Support**: Simple (Hash) and hierarchical (MultiHash) partition keys
- **Bulk Initialization**: Create multiple containers from a JSON configuration file
- **Default Containers**: Quick shortcuts for Ground Truth Curator containers
- **Flexible Configuration**: Custom indexing policies and partition key configurations

## Installation

Ensure the required dependencies are installed:

```bash
pip install azure-cosmos azure-identity
```

Or install from the project's `pyproject.toml`:

```bash
cd GroundTruthCurator/backend
pip install -e .
```

## Usage

### One-Command Emulator Initialization

For local development, you can use the convenience wrapper script. It targets the Cosmos DB Emulator and creates the Ground Truth Curator database + containers (including the GT container HPK and indexing policy):

```bash
backend/scripts/emulator_init.sh
```

Defaults:

- Database: `gt-curator` (override with `--db` or `GTC_COSMOS_DB_NAME`)

Override names via env vars (mirrors the CD workflow variable names):

```bash
GTC_COSMOS_DB_NAME=gt-curator \
GTC_COSMOS_CONTAINER_GT=ground_truth \
GTC_COSMOS_CONTAINER_ASSIGNMENTS=assignments \
GTC_COSMOS_CONTAINER_TAGS=tags \
backend/scripts/emulator_init.sh
```

### Azure AD Authentication (Production)

For Azure-deployed Cosmos DB using Azure AD authentication:

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://myaccount.documents.azure.com:443/ \
    --use-aad \
    --db my-database \
    --gt-container \
    --assignments-container \
    --tags-container
```

### Key-Based Authentication (Emulator)

For local development with Cosmos Emulator:

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://localhost:8081 \
    --key "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==" \
    --no-verify \
    --db my-database \
    --gt-container \
    --assignments-container \
    --tags-container
```

### Custom Container with Simple Partition Key

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://localhost:8081 \
    --key "<key>" \
    --no-verify \
    --db my-database \
    --container users \
    --partition-key /userId
```

### Custom Container with Hierarchical Partition Key

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://localhost:8081 \
    --key "<key>" \
    --no-verify \
    --db my-database \
    --container sessions \
    --partition-paths /tenantId /userId /sessionId
```

### Bulk Initialization from JSON

Create a `containers.json` file:

```json
[
    {
        "name": "ground_truth",
        "partition_key_paths": ["/datasetName", "/bucket"],
        "partition_key_kind": "MultiHash",
        "indexing_policy_file": "scripts/indexing-policy.json"
    },
    {
        "name": "assignments",
        "partition_key_paths": ["/pk"],
        "partition_key_kind": "Hash"
    },
    {
        "name": "tags",
        "partition_key_paths": ["/pk"],
        "partition_key_kind": "Hash"
    }
]
```

Then run:

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://myaccount.documents.azure.com:443/ \
    --use-aad \
    --db my-database \
    --containers containers.json
```

### Custom Container Names

Override default container names:

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://localhost:8081 \
    --key "<key>" \
    --no-verify \
    --db my-database \
    --gt-container my_custom_gt \
    --assignments-container my_assignments \
    --tags-container my_tags
```

### With Custom Indexing Policy

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://localhost:8081 \
    --key "<key>" \
    --no-verify \
    --db my-database \
    --container mycontainer \
    --partition-key /pk \
    --indexing-policy path/to/custom-policy.json
```

## CLI Reference

### Authentication Options

| Option        | Description                                              |
| ------------  | -------------------------------------------------------- |
| `--endpoint`  | Cosmos DB endpoint URL (required)                        |
| `--key`       | Cosmos DB key for key-based authentication               |
| `--use-aad`   | Use Azure AD authentication (DefaultAzureCredential)     |
| `--no-verify` | Disable SSL verification (required for Cosmos Emulator)  |

### Database Options

| Option | Description                |
| ------ | -------------------------- |
| `--db` | Database name (required)   |

### Default Container Options

| Option                            | Description                                             |
| --------------------------------- | ------------------------------------------------------- |
| `--gt-container [NAME]`           | Create ground truth container (default: `ground_truth`) |
| `--assignments-container [NAME]`  | Create assignments container (default: `assignments`)   |
| `--tags-container [NAME]`         | Create tags container (default: `tags`)                 |

### Custom Container Options

| Option              | Description                                        |
| ------------------- | -------------------------------------------------- |
| `--container`       | Custom container name                              |
| `--partition-key`   | Single partition key path (e.g., `/pk`)            |
| `--partition-paths` | Multiple partition key paths for hierarchical keys |

### Bulk Configuration

| Option         | Description                                     |
| -------------- | ----------------------------------------------- |
| `--containers` | Path to JSON file with container configurations |

### Indexing Policy

| Option              | Description                       |
| ------------------- | --------------------------------- |
| `--indexing-policy` | Path to indexing policy JSON file |

## JSON Configuration Schema

When using `--containers` for bulk initialization:

```json
[
    {
        "name": "container-name",
        "partition_key_paths": ["/path1", "/path2"],
        "partition_key_kind": "Hash | MultiHash",
        "indexing_policy_file": "path/to/policy.json",
        "indexing_policy": { }
    }
]
```

| Field                  | Required | Description                       |
| ---------------------- | -------- | --------------------------------- |
| `name`                 | Yes      | Container name                    |
| `partition_key_paths`  | Yes      | Array of partition key paths      |
| `partition_key_kind`   | No       | `Hash` (default) or `MultiHash`   |
| `indexing_policy_file` | No       | Path to indexing policy JSON file |
| `indexing_policy`      | No       | Inline indexing policy object     |

**Note**: Provide either `indexing_policy_file` or `indexing_policy`, not both.

## Migration from Legacy Scripts

This script replaces the following legacy scripts:

- `cosmos_init.py` - Key-based auth for bulk container initialization
- `create_cosmos_container_mgt.py` - Azure AD auth using Management SDK

### Equivalent Commands

**Previous (cosmos_init.py)**:

```bash
python scripts/cosmos_init.py \
    --endpoint https://localhost:8081 \
    --key "<key>" \
    --db mydb \
    --gt-container ground_truth \
    --assignments-container assignments \
    --tags-container tags \
    --no-verify
```

**New (cosmos_container_manager.py)**:

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://localhost:8081 \
    --key "<key>" \
    --db mydb \
    --gt-container \
    --assignments-container \
    --tags-container \
    --no-verify
```

**Previous (create_cosmos_container_mgt.py)**:

```bash
python scripts/create_cosmos_container_mgt.py \
    --subscription-id <sub-id> \
    --resource-group <rg> \
    --account-name <account> \
    --database-name mydb \
    --container-name ground_truth
```

**New (cosmos_container_manager.py)**:

```bash
python scripts/cosmos_container_manager.py \
    --endpoint https://<account>.documents.azure.com:443/ \
    --use-aad \
    --db mydb \
    --gt-container
```
