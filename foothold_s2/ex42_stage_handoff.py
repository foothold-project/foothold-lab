"""EX-42 hand-off after a stage's last boundary evaluation (team lead c5471d37, contract #639).

The gate PASS plus an existing, bounded approval cell for the next stage lets the next stage start by itself; any
other case only says so in the notice. This module decides and starts the lead's launcher script; every check of the
approval and of the predecessor PASS is `ex42_auto_authorization.validate_automatic_stage_launch`, and the launcher
(the same script that started the stage that just ended) still runs the normal training entry preflight.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from typing import Any

LAUNCH_RECORD = "next_stage_launch.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extension_ceiling(iteration: int, cap: int, step: int, count: int):
    """The end a HOLD-only extension may reach from this boundary, or None. The stage runs to its base cap
    (`maximum_updates`); each extension adds `step` (`extension_updates`), at most `count` (`extension_max_count`)."""
    if type(step) is not int or type(count) is not int or step <= 0 or count <= 0 or iteration < cap:
        return None
    done = (iteration - cap) // step
    return cap + (done + 1) * step if done < count else None


def _extension_authorized(approvals_path, stage_id) -> bool:
    from foothold_s2.curriculum.ex42_prep import _read_yaml
    cell = _read_yaml(Path(approvals_path)).get(f"stage_{stage_id.lower()}_authorization")
    return isinstance(cell, dict) and cell.get("extension_authorized") is True


def _continue_decision(plan, approvals_path, stage_id, iteration, base, manifest_path, p1):
    """Same stage, from this boundary's saved checkpoint: allowed only inside the bounds of the stage's own approval
    cell (scope maximum, cell interval; read through the stage's own validator) under the scoped automatic policy.
    No PASS is needed to go on. The plan's first stage has no boundary to continue from."""
    from foothold_s2.curriculum.ex42_prep import _read_yaml, scoped_automatic_policy
    if plan.document["stages"][0].get("id") == stage_id:
        return {**base, "action": "notify", "state": "not_ready", "reason": f"{stage_id} has no boundary to continue from"}
    try:
        if not scoped_automatic_policy(_read_yaml(Path(approvals_path)).get("automatic_launch_allowed")):
            raise ValueError("scoped automatic policy is not enabled")
        pin = next(row for row in plan.document["stages"] if row["id"] == stage_id)["parent"]["sha256"]
        from foothold_s2.scripts.ex42_training_entry import stage_approval_validator
        proof = stage_approval_validator(plan, stage_id)(plan, approvals_path, pin)
        bound = proof["scope"]["maximum_updates"]
        interval = proof.get("boundary_evaluation_interval_updates", plan.document["evaluation"]["interval_updates"])
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
        name = f"model_{iteration}.pt"
        checkpoint = Path(manifest_path).parent / name
        if (manifest.get("checkpoints", {}).get(name) != p1.get("checkpoint_sha256")
                or _sha256(checkpoint) != p1.get("checkpoint_sha256")
                or manifest.get("progress", {}).get("completed_updates") != iteration):
            raise ValueError("the boundary checkpoint is not the manifest's latest save that was scored")
        end = min(iteration + interval, bound)
        if iteration >= bound:
            row = next(r for r in plan.document["stages"] if r["id"] == stage_id)
            ceiling = (extension_ceiling(iteration, bound, row.get("extension_updates"), row.get("extension_max_count", 0))
                       if p1.get("judgment") == "HOLD" and _extension_authorized(approvals_path, stage_id) else None)
            if ceiling is None:      # not HOLD, no extension authorized, or every extension used
                return {**base, "action": "notify", "state": "stage_bound_reached_not_ready",
                        "reason": f"update {iteration} is the approved bound {bound} (extensions used or not open) "
                                  f"and the gate did not pass"}
            end = min(iteration + interval, ceiling)
    except (ValueError, OSError, KeyError, StopIteration, json.JSONDecodeError) as exc:
        return {**base, "action": "notify", "state": "continue_not_authorized",
                "reason": f"not authorized to continue by itself: {exc}"}
    return {**base, "action": "continue", "state": "stage_continues", "target_stage": stage_id,
            "resume_checkpoint": str(checkpoint), "segment_end": end,
            "plan": str(plan.path), "approvals": str(Path(approvals_path).resolve()),     # the run's own pinned pair
            "authorization": proof}


def decide_next_stage(plan_path, approvals_path, stage_id, iteration, p1_path, manifest_path,
                      materialize=None) -> dict[str, Any] | None:
    """None when this update is not a boundary of the stage. Otherwise a decision for the boundary:
    launch (the gate passed at or after the stage minimum and the next stage has its approved cell), continue (the
    same stage goes on from this save), or notify (anything else, with the reason).

    `materialize` (see `materializer_from_env`) publishes the next stage's plan / approvals / transition from this
    boundary's evidence when the next stage has no parent pin yet; the launch is then authorized against that
    published pair and carries it to the launcher (EX42_AUTO_PLAN / EX42_AUTO_APPROVALS)."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    plan = plan_path if isinstance(plan_path, EX42Plan) else EX42Plan.load(plan_path)
    stages = plan.document["stages"]
    index = next((i for i, row in enumerate(stages) if row.get("id") == stage_id), None)
    if index is None:
        return None
    minimum = stages[index].get("minimum_updates")
    boundary = iteration == minimum
    if index > 0 and not boundary:          # the plan's evaluation interval, so a removed cell still gets a notice
        interval = plan.document.get("evaluation", {}).get("interval_updates")
        limit = stages[index].get("maximum_updates", minimum)
        limit += (stages[index].get("extension_updates") or 0) * (stages[index].get("extension_max_count") or 0)
        boundary = type(interval) is int and interval > 0 and 0 < iteration <= limit and iteration % interval == 0
    if not boundary:
        return None
    following = plan.following_stage_id(stage_id)
    p1 = json.loads(Path(p1_path).read_text(encoding="utf-8-sig"))
    base = {"stage_id": stage_id, "boundary_iteration": iteration, "judgment": p1.get("judgment"),
            "next_stage_id": following, "checkpoint_sha256": p1.get("checkpoint_sha256"),
            "gate_sha256": _sha256(p1_path)}
    if not (p1.get("judgment") == "PASS" and iteration >= minimum and following is not None):
        if index > 0:      # not ready (or only a PASS before the stage minimum): the stage goes on from this save
            return _continue_decision(plan, approvals_path, stage_id, iteration, base, manifest_path, p1)
        return {**base, "action": "notify", "state": "not_ready",
                "reason": "no following stage" if following is None else f"gate judgment is {p1.get('judgment')}"}
    launch_plan, launch_approvals, pair = plan, approvals_path, {}
    if materialize is not None and not isinstance(next(r for r in stages if r["id"] == following).get("parent"), dict):
        try:
            made = materialize(target_stage=following, gate_receipt=p1_path, parent_manifest=manifest_path,
                               source_plan=plan.path)
            launch_plan, launch_approvals = EX42Plan.load(made["plan"]), made["approvals"]
            pair = {"plan": made["plan"], "approvals": made["approvals"], "materialized_plan_sha256": made["plan_sha256"]}
        except (ValueError, OSError, KeyError, TypeError) as exc:      # FileExistsError is an OSError: one launch per boundary
            return {**base, "action": "notify", "state": "next_stage_ready_for_approval",
                    "reason": f"not authorized to start by itself: materialize refused: {exc}"}
    try:
        proof = validate_automatic_stage_launch(
            launch_plan, launch_approvals, target_stage=following, parent_manifest_path=manifest_path,
            gate_receipt_path=p1_path, expected_gate_sha256=_sha256(p1_path))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        return {**base, "action": "notify", "state": "next_stage_ready_for_approval",
                "reason": f"not authorized to start by itself: {exc}"}
    return {**base, "action": "launch", "state": "next_stage_authorized", "target_stage": following,
            "authorization": proof, "gate_sha256": proof["gate_sha256"], **pair}


def start_launcher(decision, launcher, output, *, parent_manifest, parent_checkpoint, gate_receipt, popen=subprocess.Popen):
    """Run the lead's launcher once for an authorized decision. The record file is created exclusively first, so a
    second evaluation of the same boundary cannot start a second training."""
    launcher = Path(launcher)
    if not launcher.is_absolute() or not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise ValueError("EX-42 next-stage launcher must be an absolute path to an executable file")
    output = Path(output)
    kind = "continue" if decision["action"] == "continue" else "next_stage"
    record = {"format": "foothold-ex42-next-stage-launch/1", "action": kind, "target_stage": decision["target_stage"],
              "launcher": str(launcher), "launcher_sha256": _sha256(launcher),
              "gate_sha256": decision["gate_sha256"], "state": "starting",
              **({"resume_checkpoint": decision["resume_checkpoint"], "segment_end": decision["segment_end"]}
                 if kind == "continue" else {})}
    with open(output / LAUNCH_RECORD, "x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, sort_keys=True)
    env = {**os.environ, "EX42_AUTO_ACTION": kind, "EX42_AUTO_TARGET_STAGE": decision["target_stage"],
           "EX42_AUTO_PARENT_MANIFEST": str(parent_manifest), "EX42_AUTO_PARENT_CHECKPOINT": str(parent_checkpoint),
           "EX42_AUTO_GATE_RECEIPT": str(gate_receipt), "EX42_AUTO_GATE_SHA256": decision["gate_sha256"]}
    if decision.get("plan"):    # a materialized pair (next stage) or the running stage's own pair (continue)
        env.update(EX42_AUTO_PLAN=str(decision["plan"]), EX42_AUTO_APPROVALS=str(decision["approvals"]))
        record.update(plan=str(decision["plan"]), approvals=str(decision["approvals"]))
    if kind == "continue":      # the same stage goes on in the same run directory: resume from this boundary save
        env.update(EX42_AUTO_RESUME_CHECKPOINT=decision["resume_checkpoint"],
                   EX42_AUTO_SEGMENT_END=str(decision["segment_end"]))
    with open(output / "next_stage_launcher.log", "ab") as log:
        child = popen([str(launcher)], env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                      start_new_session=True)
    record.update(state="started", pid=child.pid)
    (output / LAUNCH_RECORD).write_text(json.dumps(record, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return record


def materializer_from_env(env):
    """The `materialize` callable of `decide_next_stage`, or None when no template is configured. Everything comes from
    the environment (machine profile): EX42_MATERIALIZE_TEMPLATE_PLAN / _TEMPLATE_APPROVALS (the approved template),
    _EVIDENCE_DIR (the runner writes <target>.json there from the finished stage's logs and baselines), _OUT_ROOT (one
    immutable folder per target and gate is created under it) and the explicit budget triple _BUDGET_LIMIT / _USED /
    _BASIS. A missing piece refuses the materialization (a notice), it is never guessed.
    E1F is published together with the completed W09+W08 flag chain (`EX42_FLAG_CHAIN`, optional pin
    `EX42_FLAG_CHAIN_SHA256`): its approval needs `calibration_sha256` and the `flag_baseline`, so without the chain the
    handoff does not start it (fail closed, a notice) instead of freezing a plan with an empty calibration."""
    names = ("TEMPLATE_PLAN", "TEMPLATE_APPROVALS", "EVIDENCE_DIR", "OUT_ROOT")
    if not env.get("EX42_MATERIALIZE_TEMPLATE_PLAN"):
        return None

    def run(*, target_stage, gate_receipt, parent_manifest, source_plan):
        missing = [n for n in names + ("BUDGET_LIMIT", "BUDGET_USED", "BUDGET_BASIS") if not env.get("EX42_MATERIALIZE_" + n)]
        if missing:
            raise ValueError("materialize setting missing: " + ", ".join("EX42_MATERIALIZE_" + n for n in missing))
        evidence = Path(env["EX42_MATERIALIZE_EVIDENCE_DIR"]) / f"{target_stage}.json"
        if not evidence.is_file():
            raise ValueError(f"materialize evidence {evidence} is missing (written from the finished stage's own records)")
        from foothold_s2.ex42_stage_materialize import FLAG_CHAIN_TARGET, materialize
        flag_chain = None
        if target_stage == FLAG_CHAIN_TARGET:
            chain = env.get("EX42_FLAG_CHAIN")
            if not chain or not Path(chain).is_file():
                raise ValueError(f"{target_stage} needs the completed flag chain (EX42_FLAG_CHAIN) for calibration_sha256 and "
                                 "flag_baseline; not started without it")
            pin = env.get("EX42_FLAG_CHAIN_SHA256")
            if pin and _sha256(chain) != pin:
                raise ValueError("EX42_FLAG_CHAIN differs from its EX42_FLAG_CHAIN_SHA256 pin")
            flag_chain = chain
        return materialize(
            plan=env["EX42_MATERIALIZE_TEMPLATE_PLAN"], source_plan=source_plan,
            approvals=env["EX42_MATERIALIZE_TEMPLATE_APPROVALS"], target=target_stage, parent_manifest=parent_manifest,
            gate_receipt=gate_receipt, evidence=evidence, budget_limit=int(env["EX42_MATERIALIZE_BUDGET_LIMIT"]),
            budget_used=int(env["EX42_MATERIALIZE_BUDGET_USED"]), budget_basis=env["EX42_MATERIALIZE_BUDGET_BASIS"],
            out=Path(env["EX42_MATERIALIZE_OUT_ROOT"]) / f"{target_stage}_{_sha256(gate_receipt)[:12]}",
            flag_chain=flag_chain)
    return run


def register_launched_training(queue_path, dispatch_path, *, pid, log, title, gpus=(0, 1), now=None):
    """Put the launched training into the GPU queue as an external process (`queue external`), so the dispatcher sees
    both GPUs busy and starts no queued evaluation on them. The launcher must `exec` the trainer: the registered PID is
    the launcher's, and the queue settles the item when that process ends."""
    now = _dt.datetime.now() if now is None else now
    spec = importlib.util.spec_from_file_location("ex42_handoff_dispatch", str(dispatch_path))
    if spec is None or spec.loader is None:
        raise ValueError("EX-42 GPU dispatcher unavailable")
    dispatch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dispatch)
    stamp = "%m-%d %H:%M"
    from types import SimpleNamespace
    args = SimpleNamespace(qaction="external", title=title, gpu=list(gpus), priority=1, pid=int(pid),
                           start=(now - _dt.timedelta(minutes=1)).strftime(stamp),
                           end=(now + _dt.timedelta(hours=12)).strftime(stamp), log=str(log), owner="ex42-auto")
    return dispatch.queue_cmd(args, {"queue": str(queue_path)})
