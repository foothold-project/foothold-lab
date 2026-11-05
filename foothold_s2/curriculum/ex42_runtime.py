"""EX-42 fail-closed curriculum runtime entry gate.

The v0.16 table is preparation-only. This gate validates runtime inputs and
refuses to attach training until measured terrain, approvals, graduation, and
an approved runtime schedule all exist.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from foothold_s2.curriculum.ex42_prep import EX42Plan


class EX42Runtime:
    """Keep the generic runtime factory from silently treating EX-42 as EX-40."""

    def __init__(
        self, plan: EX42Plan, env_count: int, device: str, log_dir: str | Path,
        *, approvals_path: str | Path, graduation_path: str | Path | None,
        terrain_manifest_path: str | Path | None, score_dir: str | Path | None = None,
        terrain_policy: dict[str, Any] | None = None, segment_index: int = 0,
    ) -> None:
        if plan.document.get("status") != "preparation_only":
            raise ValueError("EX-42 plan status must remain preparation_only until lead approval")
        if env_count != plan.document["environment"]["num_envs"]:
            raise ValueError("EX-42 runtime environment count differs from the pinned table")
        if device not in {"cuda:0", "cuda:1"}:
            raise ValueError("EX-42 runtime device must be explicit")
        blockers = plan.launch_blockers(
            approvals_path, graduation_path, terrain_manifest_path
        )
        if blockers:
            raise ValueError(f"EX-42 preparation-only runtime is blocked: {', '.join(blockers)}")
        if plan.document.get("status") != "runtime_approved":
            raise ValueError("EX-42 runtime requires a separately approved runtime schedule")
        raise NotImplementedError(
            "EX-42 active curriculum transitions remain unimplemented"
        )
