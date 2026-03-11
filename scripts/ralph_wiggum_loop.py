#!/usr/bin/env python3

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REVIEW_GATE_JSON_START = "<!-- REVIEW_GATE_JSON_START -->"
REVIEW_GATE_JSON_END = "<!-- REVIEW_GATE_JSON_END -->"
PHASE_PATTERN = re.compile(
    r"^### \[(?P<checked>[ xX])\] Implementation Phase (?P<number>\d+): (?P<title>.+)$",
    re.MULTILINE,
)
FRONTMATTER_PATTERN = re.compile(r"\A---\n(?P<frontmatter>.*?)\n---\n", re.DOTALL)
CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True)
class Phase:
    number: int
    title: str
    checked: bool


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Ralph Wiggum implementor/reviewer loop with Copilot CLI and "
            "advance to the next phase only when all review items are addressed."
        )
    )
    parser.add_argument("--plan", required=True, help="Path to the plan instructions markdown file.")
    parser.add_argument("--phase", type=int, help="Implementation phase number to run. Defaults to loop state or first unchecked phase.")
    parser.add_argument("--date", help="Date folder to use for review artifacts in YYYY-MM-DD format. Defaults to current UTC date.")
    parser.add_argument("--copilot-bin", default="copilot", help="Copilot CLI binary to invoke.")
    parser.add_argument("--model", default="gpt-5.4", help="Copilot model to use.")
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        choices=["low", "medium", "high", "xhigh"],
        help="Copilot reasoning effort level.",
    )
    parser.add_argument("--implementor-agent", default="task-implementor", help="Copilot custom agent for the implementation pass.")
    parser.add_argument("--reviewer-agent", default="task-reviewer", help="Copilot custom agent for the review pass.")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum implementor/reviewer iterations to run for a phase before exiting blocked.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the computed workflow without invoking Copilot.")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    raise SystemExit(f"Could not find repository root above {start}")


def parse_frontmatter(plan_text: str) -> dict[str, str]:
    match = FRONTMATTER_PATTERN.match(plan_text)
    if not match:
        return {}

    frontmatter: dict[str, str] = {}
    for raw_line in match.group("frontmatter").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")
    return frontmatter


def parse_phases(plan_text: str) -> list[Phase]:
    phases: list[Phase] = []
    for match in PHASE_PATTERN.finditer(plan_text):
        phases.append(
            Phase(
                number=int(match.group("number")),
                title=match.group("title").strip(),
                checked=match.group("checked").lower() == "x",
            )
        )
    if not phases:
        raise SystemExit("No implementation phases were found in the plan file.")
    return phases


def derive_plan_slug(plan_path: Path) -> str:
    suffix = "-plan.instructions.md"
    if plan_path.name.endswith(suffix):
        return plan_path.name[: -len(suffix)]
    return plan_path.stem


def resolve_changes_path(repo_root: Path, frontmatter: dict[str, str], date_folder: str, slug: str) -> Path:
    apply_to = frontmatter.get("applyTo")
    if apply_to:
        return repo_root / apply_to
    return repo_root / ".copilot-tracking" / "changes" / date_folder / f"{slug}-changes.md"


def build_review_path(repo_root: Path, date_folder: str, slug: str, phase_number: int) -> Path:
    return repo_root / ".copilot-tracking" / "reviews" / "rpi" / date_folder / f"{slug}-plan-{phase_number:03d}-validation.md"


def build_status_path(review_path: Path) -> Path:
    return review_path.with_suffix(".status.json")


def build_loop_state_path(repo_root: Path, slug: str) -> Path:
    return repo_root / ".copilot-tracking" / "prd-sessions" / f"{slug}.implementation-loop.state.json"


def make_relative(path: Path, repo_root: Path) -> str:
    return str(path.relative_to(repo_root))


def load_loop_state(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(read_text(path))


def find_phase_by_number(phases: list[Phase], number: int) -> Phase | None:
    return next((phase for phase in phases if phase.number == number), None)


def select_phase(phases: list[Phase], requested_phase: int | None, loop_state: dict) -> Phase:
    if requested_phase is not None:
        phase = find_phase_by_number(phases, requested_phase)
        if phase is not None:
            return phase
        raise SystemExit(f"Phase {requested_phase} was not found in the plan file.")

    state_phase = loop_state.get("currentPhase")
    if isinstance(state_phase, int):
        phase = find_phase_by_number(phases, state_phase)
        if phase is not None:
            return phase

    if loop_state.get("loopStatus") == "complete":
        raise SystemExit("Every plan phase is already marked complete.")

    phase = next((phase for phase in phases if not phase.checked), None)
    if phase is not None:
        return phase

    raise SystemExit("Every plan phase is already marked complete.")


def next_phase(phases: list[Phase], current_number: int) -> Phase | None:
    return next((phase for phase in phases if phase.number > current_number), None)


def unresolved_review_items(loop_state: dict, phase_number: int) -> list[dict]:
    state_phase = loop_state.get("lastReviewedPhase")
    items = loop_state.get("openReviewItems", [])
    if state_phase == phase_number and isinstance(items, list):
        return items
    return []


def implementor_prompt(
    repo_root: Path,
    plan_path: Path,
    changes_path: Path,
    phase: Phase,
    prior_open_items: list[dict],
    iteration: int,
    max_iterations: int,
) -> str:
    unresolved_items = json.dumps(prior_open_items, indent=2) if prior_open_items else "[]"
    return f"""You are the task-implementor for implementation phase {phase.number}: {phase.title}.

Repository root: {repo_root}
Plan file: {make_relative(plan_path, repo_root)}
Changes log path: {make_relative(changes_path, repo_root)}
Loop iteration: {iteration} of {max_iterations}

Primary instructions:
1. Implement only the current phase from the plan.
2. If the unresolved review items list below is non-empty, address every one of those items before doing any new work for this phase.
3. Update the changes log at the path above so it reflects the implementation you actually made.
4. Run the validation commands listed for this phase and fix any issues introduced by your changes.
5. Do not advance the implementation phase state yourself.

Unresolved review items to address first:
{unresolved_items}

Keep stable review-item IDs if you are clearly addressing prior reviewer findings. Avoid unrelated files and preserve existing repository conventions.
"""


def reviewer_prompt(
    repo_root: Path,
    plan_path: Path,
    changes_path: Path,
    review_path: Path,
    phase: Phase,
    prior_open_items: list[dict],
    iteration: int,
    max_iterations: int,
) -> str:
    prior_items = json.dumps(prior_open_items, indent=2) if prior_open_items else "[]"
    return f"""You are the task-reviewer for implementation phase {phase.number}: {phase.title}.

Repository root: {repo_root}
Plan file: {make_relative(plan_path, repo_root)}
Changes log path: {make_relative(changes_path, repo_root)}
Write the review output to: {make_relative(review_path, repo_root)}
Loop iteration: {iteration} of {max_iterations}

Review instructions:
1. Review the current phase implementation against the plan, the changes log, and any relevant validation results.
2. Overwrite the target review file with your full review.
3. Reuse stable IDs for still-relevant prior review items whenever possible.
4. If an item is fully fixed, keep it in the JSON block with status "addressed". If it remains a problem, use status "open".
5. If any review item remains open, the overall review status must be "changes_requested" and all_review_items_addressed must be false.
6. If every review item is addressed, the overall review status must be "approved" and all_review_items_addressed must be true.

Prior open review items:
{prior_items}

At the end of the markdown file, include this exact machine-readable block:
{REVIEW_GATE_JSON_START}
```json
{{
  "phase": {phase.number},
  "status": "approved",
  "all_review_items_addressed": true,
  "review_items": [
    {{
      "id": "R-001",
      "severity": "major",
      "status": "addressed",
      "summary": "Brief finding summary",
      "evidence": "Brief evidence or validation reference"
    }}
  ]
}}
```
{REVIEW_GATE_JSON_END}

The loop will gate phase progression from that JSON block, so it must be present and accurate.
"""


def run_copilot(
    copilot_bin: str,
    repo_root: Path,
    agent: str,
    model: str,
    reasoning_effort: str,
    prompt: str,
) -> None:
    if shutil.which(copilot_bin) is None:
        raise SystemExit(f"Copilot CLI binary not found: {copilot_bin}")

    command = [
        copilot_bin,
        "--model",
        model,
        "--reasoning-effort",
        reasoning_effort,
        "--agent",
        agent,
        "--add-dir",
        str(repo_root),
        "--allow-all-tools",
        "--no-ask-user",
        "-p",
        prompt,
    ]
    print(f"$ {' '.join(command[:10])} ...", flush=True)
    completed = subprocess.run(command, cwd=repo_root, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def parse_review_gate(review_path: Path) -> dict:
    review_text = read_text(review_path)
    start = review_text.find(REVIEW_GATE_JSON_START)
    end = review_text.find(REVIEW_GATE_JSON_END)
    if start == -1 or end == -1 or end <= start:
        raise SystemExit(
            f"{review_path} does not contain the required review gate JSON block."
        )

    json_block = review_text[start + len(REVIEW_GATE_JSON_START) : end].strip()
    json_block = CODE_FENCE_PATTERN.sub("", json_block).strip()
    payload = json.loads(json_block)

    if not isinstance(payload.get("review_items"), list):
        raise SystemExit("Review gate JSON must contain a review_items array.")

    return payload


def compute_gate_result(payload: dict) -> tuple[bool, list[dict]]:
    open_items: list[dict] = []
    for item in payload["review_items"]:
        if not isinstance(item, dict):
            raise SystemExit("Each review item must be a JSON object.")
        status = item.get("status")
        if status not in {"open", "addressed"}:
            raise SystemExit("Review item status must be either 'open' or 'addressed'.")
        if status == "open":
            open_items.append(item)

    review_status = payload.get("status")
    if review_status not in {"approved", "changes_requested"}:
        raise SystemExit("Review gate JSON status must be either 'approved' or 'changes_requested'.")

    all_addressed = bool(payload.get("all_review_items_addressed"))
    approved = review_status == "approved"
    if all_addressed and open_items:
        raise SystemExit("Review gate JSON says all items are addressed, but open items remain.")
    if approved and open_items:
        raise SystemExit("Review gate JSON says approved, but open items remain.")
    if approved and not all_addressed:
        raise SystemExit("Review gate JSON says approved, but all_review_items_addressed is false.")
    if review_status == "changes_requested" and all_addressed:
        raise SystemExit("Review gate JSON says changes_requested, but all_review_items_addressed is true.")
    if review_status == "changes_requested" and not open_items:
        raise SystemExit("Review gate JSON says changes_requested, but no open items remain.")
    return all_addressed and approved and not open_items, open_items


def review_requires_changes(payload: dict, open_items: list[dict]) -> bool:
    return payload.get("status") == "changes_requested" or bool(open_items)


def update_loop_state(
    state_path: Path,
    repo_root: Path,
    plan_path: Path,
    changes_path: Path,
    review_path: Path,
    status_path: Path,
    phase: Phase,
    upcoming_phase: Phase | None,
    gate_passed: bool,
    open_items: list[dict],
    iteration: int,
    args: argparse.Namespace,
) -> None:
    previous_state = load_loop_state(state_path)
    phase_history = previous_state.get("phaseHistory", [])
    if not isinstance(phase_history, list):
        phase_history = []

    history_entry = {
        "phase": phase.number,
        "title": phase.title,
        "timestamp": utc_now_iso(),
        "iteration": iteration,
        "result": "approved" if gate_passed else "blocked",
        "reviewFile": make_relative(review_path, repo_root),
        "reviewStatusFile": make_relative(status_path, repo_root),
        "openReviewItemCount": len(open_items),
    }
    phase_history.append(history_entry)

    state_payload = {
        "planFile": make_relative(plan_path, repo_root),
        "changesFile": make_relative(changes_path, repo_root),
        "lastRunAt": utc_now_iso(),
        "model": args.model,
        "reasoningEffort": args.reasoning_effort,
        "implementorAgent": args.implementor_agent,
        "reviewerAgent": args.reviewer_agent,
        "lastReviewedPhase": phase.number,
        "lastReviewedPhaseTitle": phase.title,
        "lastReviewFile": make_relative(review_path, repo_root),
        "lastReviewStatusFile": make_relative(status_path, repo_root),
        "allReviewItemsAddressed": gate_passed,
        "openReviewItems": open_items,
        "lastCompletedIteration": iteration,
        "maxIterations": args.max_iterations,
        "phaseHistory": phase_history,
    }

    if gate_passed and upcoming_phase is not None:
        state_payload["currentPhase"] = upcoming_phase.number
        state_payload["currentPhaseTitle"] = upcoming_phase.title
        state_payload["loopStatus"] = "ready_for_next_phase"
    elif gate_passed:
        state_payload["currentPhase"] = None
        state_payload["currentPhaseTitle"] = None
        state_payload["loopStatus"] = "complete"
    else:
        state_payload["currentPhase"] = phase.number
        state_payload["currentPhaseTitle"] = phase.title
        state_payload["loopStatus"] = "blocked_on_review"

    write_json(state_path, state_payload)


def run_phase_loop(
    args: argparse.Namespace,
    repo_root: Path,
    plan_path: Path,
    changes_path: Path,
    review_path: Path,
    status_path: Path,
    loop_state_path: Path,
    phase: Phase,
    upcoming_phase: Phase | None,
    prior_open_items: list[dict],
) -> tuple[bool, list[dict], int]:
    current_open_items = prior_open_items

    for iteration in range(1, args.max_iterations + 1):
        print(
            f"Loop iteration {iteration}/{args.max_iterations} for phase {phase.number}: {phase.title}",
            flush=True,
        )
        print(f"Running implementor for phase {phase.number}: {phase.title}", flush=True)
        run_copilot(
            copilot_bin=args.copilot_bin,
            repo_root=repo_root,
            agent=args.implementor_agent,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            prompt=implementor_prompt(
                repo_root=repo_root,
                plan_path=plan_path,
                changes_path=changes_path,
                phase=phase,
                prior_open_items=current_open_items,
                iteration=iteration,
                max_iterations=args.max_iterations,
            ),
        )

        print(f"Running reviewer for phase {phase.number}: {phase.title}", flush=True)
        run_copilot(
            copilot_bin=args.copilot_bin,
            repo_root=repo_root,
            agent=args.reviewer_agent,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            prompt=reviewer_prompt(
                repo_root=repo_root,
                plan_path=plan_path,
                changes_path=changes_path,
                review_path=review_path,
                phase=phase,
                prior_open_items=current_open_items,
                iteration=iteration,
                max_iterations=args.max_iterations,
            ),
        )

        if not review_path.exists():
            raise SystemExit(f"Reviewer did not create the expected review file: {review_path}")

        review_payload = parse_review_gate(review_path)
        gate_passed, open_items = compute_gate_result(review_payload)
        write_json(status_path, review_payload)
        update_loop_state(
            state_path=loop_state_path,
            repo_root=repo_root,
            plan_path=plan_path,
            changes_path=changes_path,
            review_path=review_path,
            status_path=status_path,
            phase=phase,
            upcoming_phase=upcoming_phase,
            gate_passed=gate_passed,
            open_items=open_items,
            iteration=iteration,
            args=args,
        )

        if not review_requires_changes(review_payload, open_items):
            return True, open_items, iteration

        if iteration == args.max_iterations:
            return False, open_items, iteration

        print(
            f"Review requested changes for phase {phase.number}. "
            f"Re-running implementor with {len(open_items)} open review item(s).",
            flush=True,
        )
        current_open_items = open_items

    raise AssertionError("run_phase_loop exhausted without returning")


def main() -> None:
    args = parse_args()
    if args.max_iterations < 1:
        raise SystemExit("--max-iterations must be at least 1.")

    plan_path = Path(args.plan).resolve()
    if not plan_path.exists():
        raise SystemExit(f"Plan file not found: {plan_path}")

    repo_root = find_repo_root(plan_path.parent)
    plan_text = read_text(plan_path)
    frontmatter = parse_frontmatter(plan_text)
    phases = parse_phases(plan_text)
    slug = derive_plan_slug(plan_path)
    date_folder = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    changes_path = resolve_changes_path(repo_root, frontmatter, date_folder, slug)
    loop_state_path = build_loop_state_path(repo_root, slug)
    loop_state = load_loop_state(loop_state_path)
    phase = select_phase(phases, args.phase, loop_state)
    review_path = build_review_path(repo_root, date_folder, slug, phase.number)
    status_path = build_status_path(review_path)
    upcoming_phase = next_phase(phases, phase.number)
    prior_open_items = unresolved_review_items(loop_state, phase.number)

    if args.dry_run:
        print("Ralph Wiggum loop dry run")
        print(f"repo_root: {repo_root}")
        print(f"phase: {phase.number} - {phase.title}")
        print(f"plan: {make_relative(plan_path, repo_root)}")
        print(f"changes: {make_relative(changes_path, repo_root)}")
        print(f"review: {make_relative(review_path, repo_root)}")
        print(f"state: {make_relative(loop_state_path, repo_root)}")
        print(f"max_iterations: {args.max_iterations}")
        print(f"prior_open_review_items: {len(prior_open_items)}")
        return

    review_path.parent.mkdir(parents=True, exist_ok=True)
    loop_state_path.parent.mkdir(parents=True, exist_ok=True)

    gate_passed, open_items, completed_iteration = run_phase_loop(
        args=args,
        repo_root=repo_root,
        plan_path=plan_path,
        changes_path=changes_path,
        review_path=review_path,
        status_path=status_path,
        loop_state_path=loop_state_path,
        phase=phase,
        upcoming_phase=upcoming_phase,
        prior_open_items=prior_open_items,
    )

    if gate_passed and upcoming_phase is not None:
        print(
            f"Phase {phase.number} approved after {completed_iteration} iteration(s). "
            f"Moving to phase {upcoming_phase.number}: {upcoming_phase.title}",
            flush=True,
        )
        return

    if gate_passed:
        print(
            f"Phase {phase.number} approved after {completed_iteration} iteration(s). "
            "All implementation phases are complete.",
            flush=True,
        )
        return

    print(
        f"Phase {phase.number} hit the max iteration limit ({args.max_iterations}). "
        f"{len(open_items)} review item(s) still need to be addressed.",
        flush=True,
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
