from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path


def load_ralph_module():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "ralph_wiggum_loop.py"
    spec = importlib.util.spec_from_file_location("ralph_wiggum_loop", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ralph_wiggum_loop = load_ralph_module()


def make_args(*, phase: int | None, max_iterations: int = 7, committer_agent: str = "task-implementor") -> Namespace:
    return Namespace(
        phase=phase,
        max_iterations=max_iterations,
        committer_agent=committer_agent,
        copilot_bin="copilot",
        model="gpt-5.4",
        reasoning_effort="medium",
    )


def test_parse_args_uses_overnight_friendly_default_iterations(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["ralph_wiggum_loop.py", "--plan", "docs/example-plan.instructions.md"],
    )

    args = ralph_wiggum_loop.parse_args()

    assert args.max_iterations == ralph_wiggum_loop.DEFAULT_MAX_ITERATIONS
    assert args.reasoning_effort == "medium"


def test_implementor_prompt_references_learnings_handoff(tmp_path) -> None:
    phase = ralph_wiggum_loop.Phase(number=1, title="First", checked=False)

    prompt = ralph_wiggum_loop.implementor_prompt(
        repo_root=tmp_path,
        plan_path=tmp_path / "demo-plan.instructions.md",
        changes_path=tmp_path / "changes.md",
        learnings_path=tmp_path / "RALPH_LEARNINGS.md",
        phase=phase,
        prior_open_items=[],
        iteration=1,
        max_iterations=7,
    )

    assert "Learnings handoff path: RALPH_LEARNINGS.md" in prompt
    assert "Read the learnings handoff file before coding" in prompt
    assert "Commit your phase-specific implementation work before you finish this iteration" in prompt
    assert "ralph: phase 1 iteration 1 - First" in prompt


def test_committer_prompt_references_final_commit_requirements(tmp_path) -> None:
    phase = ralph_wiggum_loop.Phase(number=1, title="First", checked=False)

    prompt = ralph_wiggum_loop.committer_prompt(
        repo_root=tmp_path,
        plan_path=tmp_path / "demo-plan.instructions.md",
        changes_path=tmp_path / "changes.md",
        learnings_path=tmp_path / "RALPH_LEARNINGS.md",
        review_path=tmp_path / "review.md",
        phase=phase,
    )

    assert "Approved review file: review.md" in prompt
    assert "Create a final phase commit" in prompt
    assert "ralph: phase 1 - First" in prompt


def test_reviewer_prompt_references_learnings_handoff(tmp_path) -> None:
    phase = ralph_wiggum_loop.Phase(number=1, title="First", checked=False)

    prompt = ralph_wiggum_loop.reviewer_prompt(
        repo_root=tmp_path,
        plan_path=tmp_path / "demo-plan.instructions.md",
        changes_path=tmp_path / "changes.md",
        learnings_path=tmp_path / "RALPH_LEARNINGS.md",
        review_path=tmp_path / "review.md",
        phase=phase,
        prior_open_items=[],
        iteration=1,
        max_iterations=7,
    )

    assert "Learnings handoff path: RALPH_LEARNINGS.md" in prompt
    assert "Read the learnings handoff file before reviewing" in prompt


def test_run_selected_phases_auto_advances_until_complete(monkeypatch, tmp_path, capsys) -> None:
    phase_calls: list[int] = []
    commit_calls: list[int] = []

    def fake_run_phase_loop(**kwargs):
        phase_calls.append(kwargs["phase"].number)
        return True, [], 1

    def fake_run_phase_commit(**kwargs):
        commit_calls.append(kwargs["phase"].number)

    monkeypatch.setattr(ralph_wiggum_loop, "run_phase_loop", fake_run_phase_loop)
    monkeypatch.setattr(ralph_wiggum_loop, "run_phase_commit", fake_run_phase_commit)

    plan_path = tmp_path / "demo-plan.instructions.md"
    plan_path.write_text("", encoding="utf-8")
    phases = [
        ralph_wiggum_loop.Phase(number=1, title="First", checked=False),
        ralph_wiggum_loop.Phase(number=2, title="Second", checked=False),
    ]

    exit_code = ralph_wiggum_loop.run_selected_phases(
        args=make_args(phase=None),
        repo_root=tmp_path,
        plan_path=plan_path,
        changes_path=tmp_path / "changes.md",
        learnings_path=tmp_path / "RALPH_LEARNINGS.md",
        loop_state_path=tmp_path / "loop.state.json",
        phases=phases,
        starting_phase=phases[0],
        date_folder="2026-03-11",
        loop_state={},
    )

    assert exit_code == 0
    assert phase_calls == [1, 2]
    assert commit_calls == [1, 2]
    assert "Moving to phase 2: Second" in capsys.readouterr().out


def test_run_selected_phases_respects_explicit_phase_pin(monkeypatch, tmp_path, capsys) -> None:
    phase_calls: list[int] = []
    commit_calls: list[int] = []

    def fake_run_phase_loop(**kwargs):
        phase_calls.append(kwargs["phase"].number)
        return True, [], 1

    def fake_run_phase_commit(**kwargs):
        commit_calls.append(kwargs["phase"].number)

    monkeypatch.setattr(ralph_wiggum_loop, "run_phase_loop", fake_run_phase_loop)
    monkeypatch.setattr(ralph_wiggum_loop, "run_phase_commit", fake_run_phase_commit)

    plan_path = tmp_path / "demo-plan.instructions.md"
    plan_path.write_text("", encoding="utf-8")
    phases = [
        ralph_wiggum_loop.Phase(number=1, title="First", checked=False),
        ralph_wiggum_loop.Phase(number=2, title="Second", checked=False),
    ]

    exit_code = ralph_wiggum_loop.run_selected_phases(
        args=make_args(phase=1),
        repo_root=tmp_path,
        plan_path=plan_path,
        changes_path=tmp_path / "changes.md",
        learnings_path=tmp_path / "RALPH_LEARNINGS.md",
        loop_state_path=tmp_path / "loop.state.json",
        phases=phases,
        starting_phase=phases[0],
        date_folder="2026-03-11",
        loop_state={},
    )

    assert exit_code == 0
    assert phase_calls == [1]
    assert commit_calls == [1]
    assert "Next phase is 2: Second" in capsys.readouterr().out


def test_run_selected_phases_returns_blocked_when_review_items_remain(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    def fake_run_phase_loop(**kwargs):
        return False, [{"id": "R-001", "status": "open"}], 7

    monkeypatch.setattr(ralph_wiggum_loop, "run_phase_loop", fake_run_phase_loop)

    plan_path = tmp_path / "demo-plan.instructions.md"
    plan_path.write_text("", encoding="utf-8")
    phase = ralph_wiggum_loop.Phase(number=1, title="First", checked=False)

    exit_code = ralph_wiggum_loop.run_selected_phases(
        args=make_args(phase=None),
        repo_root=tmp_path,
        plan_path=plan_path,
        changes_path=tmp_path / "changes.md",
        learnings_path=tmp_path / "RALPH_LEARNINGS.md",
        loop_state_path=tmp_path / "loop.state.json",
        phases=[phase],
        starting_phase=phase,
        date_folder="2026-03-11",
        loop_state={},
    )

    assert exit_code == 2
    assert "hit the max iteration limit" in capsys.readouterr().out
