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
cd backend
uv run uvicorn app.main:app --reload

# Start frontend (in another terminal)
cd frontend
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
uv run pytest tests/unit/ -v

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
