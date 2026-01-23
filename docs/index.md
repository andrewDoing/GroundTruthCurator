# Ground Truth Curator

Welcome to the Ground Truth Curator documentation. This platform accelerates and simplifies how subject-matter experts (SMEs) create and maintain high-quality ground truth datasets for agent evaluation and model accuracy measurement.

## What is Ground Truth Curator?

Ground Truth Curator is a web-based platform that enables:

- **Faster Curation**: Guided flows and inline validation reduce back-and-forth and rework
- **Higher Quality**: Standardized tagging ensures comparable examples across teams
- **Broader Coverage**: Targeted assignment and progress visibility help close coverage gaps
- **Trustworthy Metrics**: Ground truth enables repeatable offline evaluations and release gates

## Key Features

### For SMEs (Curators)
- **Interactive Editor**: Edit and refine question-answer pairs with multi-turn support
- **Reference Management**: Link and track source materials for each ground truth item
- **Tag System**: Categorize items with standardized tags for filtering and analysis
- **Assignment Workflow**: Self-assign items for review and track your progress

### For Administrators
- **Bulk Import**: Upload batches of ground truth items from CSV or JSON
- **Role-Based Access**: Control who can review, approve, or manage content
- **Export Snapshots**: Generate versioned datasets for evaluation pipelines
- **Analytics**: Track curation progress and coverage metrics

### For Developers
- **RESTful API**: Comprehensive API for integration with evaluation systems
- **Repository Pattern**: Clean separation between business logic and data storage
- **Extensible**: Plugin architecture for custom validation and processing

## Quick Links

- [Installation Guide](getting-started/installation.md)
- [SME Workflow Guide](guides/sme-workflow.md)
- [API Reference](api/index.md)
- [Contributing](development/contributing.md)

## Business Value

Ground truth datasets are the backbone for measuring accuracy of agent solutions. By making curation faster and more consistent, Ground Truth Curator:

- **Reduces cycle time** for producing trusted evaluation data by 2-4x
- **Decreases rework** by 30-50% through standardized templates and inline checks
- **Increases coverage** of real-world scenarios by 2x
- **Enables objective** release decisions based on repeatable accuracy metrics

[Read more about business value &rarr;](business/value.md)

## Architecture Overview

```
┌─────────────┐
│   Frontend  │  React + TypeScript
│   (Vite)    │  Material-UI components
└──────┬──────┘
       │ REST API
┌──────┴──────┐
│   Backend   │  FastAPI + Python
│  (FastAPI)  │  Service-oriented architecture
└──────┬──────┘
       │
┌──────┴──────┐
│  Cosmos DB  │  Document storage
│   or Mock   │  ETag-based concurrency
└─────────────┘
```

[Learn more about architecture &rarr;](architecture/index.md)

## Getting Started

1. **[Install](getting-started/installation.md)** the backend and frontend
2. **[Configure](getting-started/configuration.md)** your environment
3. **[Follow the quickstart](getting-started/quickstart.md)** to create your first ground truth item
4. **[Read the SME guide](guides/sme-workflow.md)** to learn the curation workflow

## Support

- **Issues**: [GitHub Issues](https://github.com/andrewvineyard/GroundTruthCurator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/andrewvineyard/GroundTruthCurator/discussions)
- **Contributing**: See our [contributing guide](development/contributing.md)

## License

[License information to be added]
