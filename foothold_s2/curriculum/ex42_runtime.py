"""EX-42 fail-closed curriculum runtime entry gate.

The v0.16 table is preparation-only. This gate validates runtime inputs and
refuses to attach training until measured terrain, approvals, graduation, and
an approved runtime schedule all exist.
"""
from __future__ import annotations

import math
import hashlib
import os
from pathlib import Path
import subprocess
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
        self.plan = plan
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
                   observed_score_iteration: int | None,
                   runner: Any = None) -> dict[str, Any]:
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
        stage = self.stages[next_index]
        mirror_enabled = False                      # on from the stage that turns it on until a stage says off
        for row in self.stages[:next_index + 1]:
            mirror_enabled = row.get("critic_mirror", mirror_enabled)
            if type(mirror_enabled) is not bool:
                raise ValueError("EX-42 stage critic mirror must be a bool")
        mirror_receipt = {"stage_id": next_stage_id, "enabled": mirror_enabled,
                          "decision_id": None, "applied": False}
        setter = getattr(runner, "set_ex41_critic_mirror", None) if runner is not None else None
        if mirror_enabled and getattr(runner, "ex41_critic_mirror", False) is True:
            mirror_receipt["inherited"] = True      # already on from an earlier stage's grant: nothing to apply
        elif mirror_enabled:
            rule = {"field": "critic_mirror", "decision_id": "D174",
                    "choices": [True], "boundaries": ["E1"]}
            from foothold_s2.ex42_gate_checks import validate_automatic_rule
            validate_automatic_rule(rule=rule, approval=self.approval_doc,
                                    value=True, boundary=next_stage_id)
            if not callable(setter):
                raise ValueError("EX-42 E1 critic mirror needs the existing StartRunner setter")
            proof = critic_mirror_proof(self.plan, self.approvals_path, next_stage_id)
            commit = proof["config_commit"]
            setter(True, approval=proof)
            mirror_receipt.update(decision_id="D174", applied=True,
                                  authorization={"plan_sha256": proof["plan_sha256"],
                                                 "approval_sha256": proof["approval_sha256"],
                                                 "config_commit": commit})
        elif callable(setter) and getattr(runner, "ex41_critic_mirror", False) is not False:
            setter(False, approval=None)
            mirror_receipt["applied"] = True
        target = getattr(env, "unwrapped", env)
        target._ex42_stage_id = next_stage_id
        target._ex42_stage_config = stage
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
            "critic_mirror_receipt": mirror_receipt,
            **evidence,
        }


def critic_mirror_proof(plan: EX42Plan, approvals_path: str | Path, stage_id: str = "E1") -> dict[str, Any]:
    """The D174 grant StartRunner.set_ex41_critic_mirror checks against the plan and approval bytes.

    Used at the in-process E0 -> E1 boundary and at the start of a stand-alone stage whose parent was loaded with
    the mirror off (E1, and every later stage: the mirror stays on once on). The runner re-reads both files:
    - plan in a git tree: from `config_commit`; an uncommitted or edited file makes it refuse (W72 HOLD style).
    - plan in a materialized outdir (a `transition.json` next to it): the runner checks both byte hashes against the
      receipt and the transition record's new_plan_sha against the plan; the gate chain itself was checked by the
      launcher before the trainer started (ex42_auto_authorization).
    """
    approvals_path = Path(approvals_path).resolve(strict=True)
    proof = {"format": "foothold-ex42-critic-mirror-approval/1",
             "stage_id": stage_id, "decision_id": "D174",
             "plan_path": str(plan.path), "plan_sha256": plan.sha256,
             "approval_path": str(approvals_path),
             "approval_sha256": hashlib.sha256(approvals_path.read_bytes()).hexdigest()}
    transition = Path(plan.path).resolve().parent / "transition.json"
    if transition.is_file():
        proof["transition_path"] = str(transition)
    else:
        proof["config_commit"] = subprocess.check_output(
            ["git", "-C", str(plan.path.parent), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL).decode().strip()
    return proof


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
                       p1_interval: int = 250,
                       parent_pin: dict[str, Any] | None = None,
                       current_stage_id: str | None = None,
                       defer_until_pid: int | None = None):
        """Build the runner-owned chain adapter without granting launch approval."""
        from foothold_s2.ex42_chain import EX42TrainingChain
        return EX42TrainingChain(
            plan=plan, approvals_path=approvals_path,
            parent_manifest_path=parent_manifest_path, run_dir=run_dir,
            repo_root=repo_root, queue_path=queue_path,
            dispatch_path=dispatch_path, alert_sender=alert_sender,
            score_argv_factory=score_argv_factory,
            machine_profile=machine_profile,
            boundary_provider=boundary_provider, p1_interval=p1_interval,
            parent_pin=parent_pin, current_stage_id=current_stage_id,
            defer_until_pid=defer_until_pid)

    def __init__(
        self, plan: EX42Plan, env_count: int, device: str, log_dir: str | Path,
        *, approvals_path: str | Path, graduation_path: str | Path | None,
        terrain_manifest_path: str | Path | None, score_dir: str | Path | None = None,
        terrain_policy: dict[str, Any] | None = None, segment_index: int = 0,
    ) -> None:
        if plan.document.get("status") != "preparation_only":
            raise ValueError("EX-42 plan status must remain preparation_only until lead approval")
        # torchrun creates one environment per rank. The table records the
        # whole M3 allocation, while env_count is local to this rank.
        world_size = int(os.environ.get("WORLD_SIZE", "1"))
        rank = int(os.environ.get("RANK", "0"))
        planned = plan.document["environment"]["num_envs"]
        if (planned != 6144 or world_size != 2 or not 0 <= rank < world_size
                or env_count != 3072 or env_count * world_size != planned):
            raise ValueError("EX-42 runtime requires 3072 env per rank x 2 ranks = 6144 total")
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
