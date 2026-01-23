# Contributing to Ground Truth Curator

Thank you for your interest in contributing to Ground Truth Curator! This guide will help you get started.

## Code of Conduct

Please be respectful and constructive in all interactions with the project community.

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- uv package manager
- Jujutsu (jj) for version control (recommended)

### Getting Started

1. **Clone the repository**:
   ```bash
   jj clone https://github.com/andrewvineyard/GroundTruthCurator.git
   cd GroundTruthCurator
   ```

2. **Install dependencies**:
   ```bash
   # Backend
   cd backend
   uv sync
   
   # Frontend
   cd ../frontend
   npm install
   ```

3. **Run tests**:
   ```bash
   # Backend tests
   cd backend
   uv run pytest tests/unit/ -v
   
   # Frontend tests
   cd frontend
   npm test -- --run
   ```

## Version Control Workflow (Jujutsu)

This repository uses [Jujutsu (jj)](https://martinvonz.github.io/jj/) for version control.

### Before Making Changes

1. Check if the current commit is empty:
   ```bash
   jj log --no-pager --limit 1
   ```

2. If empty, set a descriptive commit message:
   ```bash
   jj describe -m "initial commit description"
   ```

3. If not empty, create a new commit:
   ```bash
   jj new -m "description of the change"
   ```

### Making Changes

- Make your code changes
- Use `jj status` to review uncommitted changes
- Use `jj diff --no-pager` to see what has changed

### After Completing Changes

1. Update the commit description if needed:
   ```bash
   jj describe -m "final description of changes"
   ```

2. The maintainer will advance the main bookmark after review

## Commit Message Guidelines

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test changes
- `refactor`: Code refactoring
- `chore`: Maintenance tasks

Examples:
```
feat(api): add keyword search to ground truths endpoint
fix(frontend): prevent Space key from closing modals
docs: update installation guide with Docker instructions
test(backend): add tests for PII detection service
```

## Testing Guidelines

### Backend Testing

Run all tests:
```bash
cd backend
uv run pytest tests/unit/ -v
```

Run specific test file:
```bash
uv run pytest tests/unit/test_dos_prevention.py -v
```

Run tests matching keyword:
```bash
uv run pytest tests/unit/ -k "bulk" -v
```

Type checking:
```bash
uv run ty check app/api/v1/ground_truths.py
```

### Frontend Testing

Run tests:
```bash
cd frontend
npm test -- --run
```

Type checking:
```bash
npm run typecheck
```

Build verification:
```bash
npm run build
```

## Code Quality Standards

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints for function signatures
- Document complex logic with concise comments
- Keep functions focused and testable
- Use dependency injection where appropriate

### TypeScript (Frontend)

- Use TypeScript strict mode
- Define interfaces for all data structures
- Use functional components with hooks
- Follow React best practices
- Keep components small and focused

## Pull Request Process

1. **Create a branch**: Use Jujutsu to create a new change
2. **Make changes**: Implement your feature or fix
3. **Test thoroughly**: Ensure all tests pass
4. **Update documentation**: Add or update relevant docs
5. **Submit PR**: Create a pull request with clear description
6. **Address feedback**: Respond to review comments

## Project Structure

```
GroundTruthCurator/
├── backend/          # FastAPI backend
│   ├── app/          # Application code
│   │   ├── api/      # API endpoints
│   │   ├── services/ # Business logic
│   │   ├── adapters/ # External integrations
│   │   └── domain/   # Domain models
│   └── tests/        # Tests
│       ├── unit/     # Unit tests
│       └── integration/ # Integration tests
├── frontend/         # React frontend
│   ├── src/          # Source code
│   │   ├── components/ # React components
│   │   ├── hooks/    # Custom hooks
│   │   ├── services/ # API clients
│   │   └── utils/    # Utilities
│   └── tests/        # Tests
└── docs/             # Documentation
```

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/andrewvineyard/GroundTruthCurator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/andrewvineyard/GroundTruthCurator/discussions)

## Areas for Contribution

### High Priority
- Documentation improvements
- Test coverage expansion
- Performance optimization
- Accessibility improvements

### Features
- See [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) for planned features
- Check GitHub Issues for feature requests

### Bug Fixes
- Check GitHub Issues for reported bugs
- Submit fixes with test cases

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
