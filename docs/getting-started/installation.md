# Installation

This guide walks through installing Ground Truth Curator on your local machine.

## Backend Installation

### Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) package manager

### Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/andrewvineyard/GroundTruthCurator.git
   cd GroundTruthCurator
   ```

2. **Install backend dependencies**:
   ```bash
   cd backend
   uv sync
   ```

3. **Verify installation**:
   ```bash
   uv run pytest tests/unit/ -v
   ```

   All tests should pass.

## Frontend Installation

### Prerequisites

- Node.js 18 or later
- npm

### Steps

1. **Install frontend dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Verify installation**:
   ```bash
   npm test -- --run
   npm run typecheck
   npm run build
   ```

   All commands should complete successfully.

## Docker Installation (Optional)

Docker support is planned for future releases.

## Next Steps

- [Configure your environment](configuration.md)
- [Run the quickstart](quickstart.md)
