# Pre-Commit Quality Checks

This document describes the available code quality checks and how to run them before committing changes.

## Quick Start

Run all pre-commit checks manually:

```bash
cd frontend
npm run pre-commit
```

This command runs:
1. **Linting**: `biome check` (code style and quality)
2. **Type checking**: `tsc -b` (TypeScript type safety)

## Available Commands

### Linting

```bash
# Check for linting issues (no changes)
npm run lint:check

# Check and auto-fix linting issues
npm run lint
```

### Type Checking

```bash
# Run TypeScript type checker
npm run typecheck
```

### Pre-Commit (Combined)

```bash
# Run all checks (linting + type checking)
npm run pre-commit
```

## Setting Up Automatic Git Hooks (Optional)

Since this repository uses Jujutsu (jj) for version control, which doesn't yet support native hooks, you can optionally set up git hooks manually if you also use git commands.

### Option 1: Manual Hook Installation

Create a git pre-commit hook:

```bash
cd frontend
cat > ../.git/hooks/pre-commit << 'EOF'
#!/bin/sh
# Pre-commit hook for frontend code quality

echo "Running pre-commit checks..."
cd frontend && npm run pre-commit

if [ $? -ne 0 ]; then
  echo "❌ Pre-commit checks failed. Please fix errors before committing."
  exit 1
fi

echo "✅ Pre-commit checks passed!"
EOF

chmod +x ../.git/hooks/pre-commit
```

### Option 2: Using Husky (Advanced)

If you prefer a more robust solution, install Husky:

```bash
npm install --save-dev husky
npx husky init
echo "cd frontend && npm run pre-commit" > .husky/pre-commit
```

**Note**: Husky hooks only work with git commands, not jj commands.

## CI Integration

The pre-commit checks are also run in the CI pipeline to ensure code quality. See `.github/workflows/gtc-ci.yml` for the CI configuration.

## Troubleshooting

### Linting Errors

If you encounter linting errors:

```bash
# Auto-fix most issues
npm run lint

# Or manually review and fix
npm run lint:check
```

### Type Errors

If you encounter type errors:

```bash
# Review the errors
npm run typecheck

# Fix the issues in your code editor
# Most IDEs show TypeScript errors inline
```

### Skipping Hooks (Not Recommended)

If you absolutely need to bypass pre-commit checks (not recommended):

```bash
# Git only
git commit --no-verify

# For jj, just commit normally (no hooks active)
jj describe -m "your message"
```

## Best Practices

1. **Run checks before committing**: Get into the habit of running `npm run pre-commit` before committing
2. **Fix issues incrementally**: Don't let linting/type errors accumulate
3. **Use IDE integration**: Configure your editor to show Biome and TypeScript errors in real-time
4. **Keep commits focused**: Small, focused commits are easier to review and validate

## Related Documentation

- [Biome Documentation](https://biomejs.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Jujutsu Documentation](https://martinvonz.github.io/jj/)
