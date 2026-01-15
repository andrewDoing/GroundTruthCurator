#!/usr/bin/env python3
from __future__ import annotations

"""Convert Jira CSV export to a simplified PRD JSON list.

Usage:
  python3 scripts/jira_to_prd.py --input Jira.csv --output prd.json
"""

import argparse
import csv
import json
import sys
from pathlib import Path

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_ERROR = 2


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(description="Convert Jira CSV export to PRD JSON")
    parser.add_argument("--input", type=Path, default=Path("Jira.csv"))
    parser.add_argument("--output", type=Path, default=Path("prd.json"))
    return parser


def normalize_status(raw: str) -> str:
    """Map Jira statuses to: not started | in progress | done."""
    done = {"done", "closed", "resolved", "complete", "completed"}
    in_progress = {"in progress", "doing", "in review", "review", "qa", "testing", "blocked"}
    not_started = {"to do", "todo", "backlog", "open", "new"}

    status = (raw or "").strip().lower()

    if status in done:
        return "done"
    if status in in_progress:
        return "in progress"
    if status in not_started:
        return "not started"

    # Heuristic fallbacks for common Jira workflows.
    if any(token in status for token in ("done", "close", "resolve")):
        return "done"
    if any(token in status for token in ("progress", "review", "qa", "test")):
        return "in progress"
    if any(token in status for token in ("to do", "backlog", "open")):
        return "not started"

    return "not started"


def clean_text(value: str | None) -> str:
    """Trim text while preserving internal newlines."""
    return (value or "").strip()


def run(input_path: Path, output_path: Path) -> int:
    """Read Jira CSV and write simplified PRD JSON."""
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return EXIT_ERROR

    items: list[dict[str, str]] = []
    with input_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required_cols = {"Issue key", "Summary", "Description", "Status"}
        missing = required_cols - set(reader.fieldnames or [])
        if missing:
            print(f"Error: missing expected columns: {sorted(missing)}", file=sys.stderr)
            return EXIT_ERROR

        for row in reader:
            issue_key = clean_text(row.get("Issue key"))
            if not issue_key:
                continue

            items.append(
                {
                    "issue": issue_key,
                    "title": clean_text(row.get("Summary")),
                    "description": clean_text(row.get("Description")),
                    "status": normalize_status(row.get("Status", "")),
                }
            )

    output_path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Basic validation.
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        print("Error: output JSON is not a list", file=sys.stderr)
        return EXIT_FAILURE
    return EXIT_SUCCESS


def main() -> int:
    """Main entry point with error handling."""
    try:
        args = create_parser().parse_args()
        return run(args.input, args.output)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except BrokenPipeError:
        sys.stderr.close()
        return EXIT_FAILURE
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
