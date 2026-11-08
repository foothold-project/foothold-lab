"""EX-42 fail-closed curriculum runtime entry gate.

The v0.16 table is preparation-only. This gate validates runtime inputs and
refuses to attach training until measured terrain, approvals, graduation, and
an approved runtime schedule all exist.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from foothold_s2.curriculum.ex42_prep import APPROVAL_FORMAT, EX42Plan


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


def read_approved_dr_schedule(approvals_path: str | Path,
                              stage_ids: tuple[str, ...]) -> tuple[dict[str, float], str]:
    """Load a complete, explicitly approved stage-scale map. Never supply defaults."""
    path = Path(approvals_path).resolve(strict=True)
    doc = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict) or doc.get("format") != APPROVAL_FORMAT:
        raise ValueError("EX-42 approval format invalid for DR schedule")
    schedule = doc.get("domain_randomization")
    if (not isinstance(schedule, dict) or schedule.get("approved") is not True
            or not isinstance(schedule.get("decision_id"), str)
            or not schedule["decision_id"].strip()):
        raise ValueError("EX-42 approved DR schedule missing")
    scales = schedule.get("stage_scales")
    if not isinstance(scales, dict) or set(scales) != set(stage_ids):
        raise ValueError("EX-42 DR schedule must explicitly cover every stage")
    normalized: dict[str, float] = {}
    for stage_id in stage_ids:
        value = scales[stage_id]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0):
            raise ValueError(f"EX-42 DR scale invalid for stage {stage_id}")
        normalized[stage_id] = float(value)
    return normalized, schedule["decision_id"]


class EX42StageTransitionConsumer:
    """Consume caller-selected sequential stage transitions and approved DR values.

    Stage promotion/maintenance judgement remains external. Missing or late score
    evidence cannot delay the planned scale and is returned as a measurement gap.
    """

    def __init__(self, plan: EX42Plan, approvals_path: str | Path,
                 *, current_stage_id: str | None = None):
        stages = plan.runtime_stages
        if not isinstance(stages, tuple) or not stages:
            raise ValueError("EX-42 plan has no stages")
        self.stages = tuple(stages)
        self.stage_ids = tuple(row.get("id") for row in self.stages)
        if (any(not isinstance(stage, str) or not stage for stage in self.stage_ids)
                or len(set(self.stage_ids)) != len(self.stage_ids)):
            raise ValueError("EX-42 stage IDs are missing or duplicated")
        self.approvals_path = Path(approvals_path).resolve(strict=True)
        self.approval_doc = yaml.safe_load(self.approvals_path.read_text(encoding="utf-8-sig"))
        self.stage_scales, self.decision_id = read_approved_dr_schedule(self.approvals_path, self.stage_ids)
        self.stage_index = 0
        if current_stage_id is not None:
            if current_stage_id not in self.stage_ids:
                raise ValueError("EX-42 current stage is unknown")
            self.stage_index = self.stage_ids.index(current_stage_id)

    @property
    def current_stage_id(self) -> str:
        return self.stage_ids[self.stage_index]

    def transition(self, env: Any, next_stage_id: str, *, boundary_iteration: int,
                   expected_score_iteration: int,
                   observed_score_iteration: int | None) -> dict[str, Any]:
        next_index = self.stage_index + 1
        if next_index >= len(self.stage_ids) or next_stage_id != self.stage_ids[next_index]:
            raise ValueError("EX-42 transition must advance exactly one planned stage")
        from foothold_s2.ex42_gate_checks import validate_automatic_rule
        planned_scale = self.stage_scales[next_stage_id]
        rule = {"field": "domain_randomization", "decision_id": self.decision_id,
                "choices": [planned_scale], "boundaries": [next_stage_id]}
        validate_automatic_rule(rule=rule, approval=self.approval_doc,
                                value=planned_scale, boundary=next_stage_id)
        evidence = resolve_missing_score_dr_boundary(
            planned_scale=planned_scale,
            boundary_iteration=boundary_iteration,
            expected_score_iteration=expected_score_iteration,
            observed_score_iteration=observed_score_iteration,
        )
        target = getattr(env, "unwrapped", env)
        target._ex42_stage_id = next_stage_id
        target._ex42_stage_config = self.stages[next_index]
        target._ex40_dr_scale = evidence["applied_scale"]
        self.stage_index = next_index
        return {
            "stage_before": self.stage_ids[next_index - 1],
            "stage_after": next_stage_id,
            "boundary_iteration": boundary_iteration,
            "decision_id": self.decision_id,
            "automatic_action_receipt": {
                "field": "domain_randomization", "state": "approved_value_selected",
                "decision_id": self.decision_id, "boundary": next_stage_id,
                "value": evidence["applied_scale"], "approval_validated": True,
                "runtime_application": "not_implemented_preparation_only",
            },
            **evidence,
        }


class EX42Runtime:
    """Keep the generic runtime factory from silently treating EX-42 as EX-40."""

    @staticmethod
    def transition_consumer(plan: EX42Plan, approvals_path: str | Path,
                            *, current_stage_id: str | None = None) -> EX42StageTransitionConsumer:
        """Build the stage-transition consumer from the approved EX-42 schedule."""
        return EX42StageTransitionConsumer(
            plan, approvals_path, current_stage_id=current_stage_id)

    @staticmethod
    def training_chain(plan: EX42Plan, *, approvals_path: str | Path,
                       parent_manifest_path: str | Path, run_dir: str | Path,
                       repo_root: str | Path, queue_path: str | Path,
                       dispatch_path: str | Path | None = None,
                       alert_sender: Any = None,
                       score_argv_factory: Any = None,
                       machine_profile: dict[str, Any] | None = None,
                       boundary_provider: Any = None,
                       p1_interval: int = 250):
        """Build the runner-owned chain adapter without granting launch approval."""
        from foothold_s2.ex42_chain import EX42TrainingChain
        return EX42TrainingChain(
            plan=plan, approvals_path=approvals_path,
            parent_manifest_path=parent_manifest_path, run_dir=run_dir,
            repo_root=repo_root, queue_path=queue_path,
            dispatch_path=dispatch_path, alert_sender=alert_sender,
            score_argv_factory=score_argv_factory,
            machine_profile=machine_profile,
            boundary_provider=boundary_provider, p1_interval=p1_interval)

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
