"""CPU-safe EX-42 train_start caller helpers.

This module wires approved plan/parent inputs to the existing StartRunner hook.
It does not grant launch authorization; the current EX-42 plan remains
preparation_only and train_start rejects it before AppLauncher is created.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.curriculum.ex42_runtime import EX42Runtime


def make_score_argv_factory(serialized: str):
    """Parse a JSON argv vector with one explicit {iteration} placeholder."""
    try:
        template = json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise ValueError("EX-42 P1 score command must be a JSON argv array") from exc
    if (not isinstance(template, list) or not template
            or any(not isinstance(part, str) or not part for part in template)):
        raise ValueError("EX-42 P1 score command must be a non-empty string argv array")
    occurrences = sum(part.count("{iteration}") for part in template)
    if occurrences != 1:
        raise ValueError("EX-42 P1 score argv must contain {iteration} exactly once")

    def build(iteration: int) -> list[str]:
        if type(iteration) is not int or iteration < 0:
            raise ValueError("EX-42 P1 checkpoint iteration must be non-negative")
        return [part.replace("{iteration}", str(iteration)) for part in template]

    return build


def build_ex42_training_chain(*, plan_path: str | Path,
                              approvals_path: str | Path,
                              parent_manifest_path: str | Path,
                              run_dir: str | Path,
                              repo_root: str | Path,
                              queue_path: str | Path,
                              score_argv_json: str,
                              dispatch_path: str | Path | None = None,
                              boundary_provider: Any = None,
                              p1_interval: int = 250):
    """Load the pinned EX-42 plan and approved parent, then construct its chain."""
    plan = EX42Plan.load(plan_path)
    if plan.document.get("status") != "preparation_only":
        raise ValueError("EX-42 plan must remain preparation_only until launch approval")
    return EX42Runtime.training_chain(
        plan=plan,
        approvals_path=approvals_path,
        parent_manifest_path=parent_manifest_path,
        run_dir=run_dir,
        repo_root=repo_root,
        queue_path=queue_path,
        dispatch_path=dispatch_path,
        score_argv_factory=make_score_argv_factory(score_argv_json),
        boundary_provider=boundary_provider,
        p1_interval=p1_interval,
    )


def attach_ex42_training_chain(runner: Any, chain: Any) -> None:
    """Pass the constructed chain through the supported StartRunner API."""
    attach = getattr(runner, "attach_ex42_training_chain", None)
    if not callable(attach):
        raise TypeError("EX-42 training caller requires StartRunner.attach_ex42_training_chain")
    attach(chain)


def build_and_attach_ex42_training_chain(runner: Any, **inputs: Any):
    """Shared train_start path, also callable in CPU-only integration tests."""
    chain = build_ex42_training_chain(**inputs)
    attach_ex42_training_chain(runner, chain)
    return chain
