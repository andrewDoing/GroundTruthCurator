# Ground Truth Curator

A platform for subject-matter experts to create and maintain high-quality ground truth datasets for agent evaluation and model accuracy measurement.

## Quick Start

See the [documentation](https://andrewvineyard.github.io/GroundTruthCurator/) for complete guides.

### Installation

```bash
# Backend
cd backend
uv sync

# Frontend
cd frontend
npm install
```

### Running Locally

```bash
# Start backend
make -f Makefile.harness backend

# Start frontend (in another terminal)
make -f Makefile.harness frontend

# Or run both from one terminal
make -f Makefile.harness dev

# Or run both in the background
make -f Makefile.harness dev-up
make -f Makefile.harness dev-down
```

These targets wrap the existing local dev commands in `backend/` and `frontend/`. Use `dev` for a foreground session, or `dev-up` / `dev-down` when an agent or developer wants background-managed servers with logs in `.harness/dev/`.

To start the background demo stack with seeded demo data and a stable local identity, run:

```bash
VITE_DEMO_MODE=true VITE_DEV_USER_ID=demo-user make dev-up
```

This enables the demo UI flow, seeds the backend memory repo with demo items, and uses `demo-user` for assignment-aware API calls. Stop it later with `make dev-down`.

### Running Tests

```bash
# Backend tests
cd backend
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v

# Frontend tests
cd frontend
npm test -- --run
```

## Documentation

Full documentation is available at [https://andrewvineyard.github.io/GroundTruthCurator/](https://andrewvineyard.github.io/GroundTruthCurator/)

To build documentation locally:

```bash
cd backend
uv run mkdocs serve -f ../mkdocs.yml
```

Then open http://localhost:8000

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

[License information to be added]
