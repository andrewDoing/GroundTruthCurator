#!/usr/bin/env python3
"""
Export OpenAPI schema from the FastAPI application.

This script generates the OpenAPI JSON specification and writes it to the
frontend directory so the frontend can generate TypeScript types without
requiring a running backend server.

Usage:
    uv run python scripts/export_openapi.py

The script outputs to ../frontend/src/api/openapi.json by default.
"""

import json
import sys
import subprocess
from pathlib import Path

# Ensure the app module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


def format_with_biome(output_path: Path) -> None:
    """Run Biome formatter on the generated OpenAPI file."""
    cmd = ["npx", "--yes", "biome", "format", str(output_path), "--write"]
    try:
        subprocess.run(cmd, cwd=output_path.parent.parent.parent, check=True)
    except FileNotFoundError:
        print("Biome not available (npx missing); leaving raw JSON.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Biome formatting failed") from exc


def export_openapi(output_path: Path | None = None) -> Path:
    """Export the OpenAPI schema to a JSON file.

    Args:
        output_path: Optional path to write the schema. Defaults to
                     ../frontend/src/api/openapi.json relative to backend.

    Returns:
        The path where the schema was written.
    """
    if output_path is None:
        # Default: frontend/src/api/openapi.json relative to this script
        backend_dir = Path(__file__).resolve().parent.parent
        output_path = backend_dir.parent / "frontend" / "src" / "api" / "openapi.json"

    # Get the OpenAPI schema from FastAPI
    openapi_schema = app.openapi()

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write with consistent formatting for reproducible diffs
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, sort_keys=False)
        f.write("\n")  # Trailing newline for POSIX compliance

    format_with_biome(output_path)
    return output_path


def main() -> None:
    """CLI entrypoint."""
    output = None
    if len(sys.argv) > 1:
        output = Path(sys.argv[1])

    result_path = export_openapi(output)
    print(f"OpenAPI schema exported to: {result_path}")


if __name__ == "__main__":
    main()
