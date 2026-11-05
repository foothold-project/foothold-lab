"""EX-42 fail-closed curriculum runtime entry gate.

The v0.16 table is preparation-only. This gate validates runtime inputs and
refuses to attach training until measured terrain, approvals, graduation, and
an approved runtime schedule all exist.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from foothold_s2.curriculum.ex42_prep import EX42Plan


def resolve_missing_score_dr_boundary(
    *, planned_scale: float, boundary_iteration: int,
    expected_score_iteration: int, observed_score_iteration: int | None,
) -> dict[str, Any]:
    """Keep scheduled DR on time when that boundary's score is absent or late.

    This records an evidence gap only. It does not decide maintenance-based
    exposure promotion or rollback; those remain under the existing stage
    policy and the unresolved lead question.
    """
    if (isinstance(planned_scale, bool) or not isinstance(planned_scale, (int, float))
            or not 0.0 <= float(planned_scale) <= 1.0):
        raise ValueError("EX-42 planned DR scale must be in [0, 1]")
    if (type(boundary_iteration) is not int or boundary_iteration <= 0
            or type(expected_score_iteration) is not int or expected_score_iteration < 0):
        raise ValueError("EX-42 boundary and expected score iterations are invalid")
    if observed_score_iteration == expected_score_iteration:
        return {
            "status": "score_available",
            "reason": None,
            "boundary_iteration": boundary_iteration,
            "expected_score_iteration": expected_score_iteration,
            "observed_score_iteration": observed_score_iteration,
            "dr_action": "follow_schedule",
            "planned_scale": float(planned_scale),
            "applied_scale": float(planned_scale),
            "learning_continues": True,
        }
    reason = "score_missing" if observed_score_iteration is None else "score_late_or_wrong_iteration"
    return {
        "status": "measurement_gap",
        "reason": reason,
        "boundary_iteration": boundary_iteration,
        "expected_score_iteration": expected_score_iteration,
        "observed_score_iteration": observed_score_iteration,
        "dr_action": "follow_schedule_record_gap",
        "planned_scale": float(planned_scale),
        "applied_scale": float(planned_scale),
        "learning_continues": True,
        "maintenance_action": "not_decided_here",
    }


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
