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


def _maintenance_verdict(p1) -> str | None:
    """The boundary's maintenance table verdict, read from the measured score the gate receipt pins by SHA256.
    E1 records it as `maintenance_judgement`, later stages as `stage_exit.items.maintenance_current`. Anything
    unreadable, unpinned or differing from the pin is None: an unproven table is never read as a pass."""
    try:
        path, pin = Path(p1["measurement"]), p1["measurement_sha256"]
        if _sha256(path) != pin:
            return None
        score = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(score, dict):
            return None
        items = (score.get("stage_exit") or {}).get("items") or {}
        verdict = score.get("maintenance_judgement") or (items.get("maintenance_current") or {}).get("judgement")
    except (AttributeError, KeyError, TypeError, OSError, ValueError):
        return None
    return verdict if verdict in ("PASS", "HOLD", "FAIL") else None


def _continue_decision(plan, approvals_path, stage_id, iteration, base, manifest_path, p1, p1_path):
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
        extension = None
        if iteration >= bound:
            row = next(r for r in plan.document["stages"] if r["id"] == stage_id)
            ceiling = (extension_ceiling(iteration, bound, row.get("extension_updates"), row.get("extension_max_count", 0))
                       if p1.get("judgment") == "HOLD" and _extension_authorized(approvals_path, stage_id) else None)
            if ceiling is None:      # not HOLD, no extension authorized, or every extension used
                return {**base, "action": "notify", "state": "stage_bound_reached_not_ready",
                        "reason": f"update {iteration} is the approved bound {bound} (extensions used or not open) "
                                  f"and the gate did not pass"}
            end = min(iteration + interval, ceiling)
            from foothold_s2.ex42_extension_evidence import improvement_evidence
            extension = improvement_evidence(plan, stage_id, iteration, interval, Path(p1_path))
    except (AttributeError, TypeError, ValueError, OSError, KeyError, StopIteration, json.JSONDecodeError) as exc:
        return {**base, "action": "notify", "state": "continue_not_authorized",
                "reason": f"not authorized to continue by itself: {exc}"}
    # Team lead rule (16:58): only a PASS maintenance table starts the next segment by itself; HOLD, FAIL and an
    # unreadable table are all a notice.
    maintenance = _maintenance_verdict(p1)
    if maintenance != "PASS":
        return {**base, "action": "notify", "state": "continue_held_by_maintenance",
                "reason": (f"maintenance table is {maintenance} at this boundary" if maintenance
                           else "maintenance table verdict is not readable from the pinned measurement")
                          + f": the next segment (end {end}) was not started; resume by hand after a decision"}
    if extension is not None and extension["state"] != "PASS":
        return {**base, "action": "notify", "state": "extension_needs_lead_review",
                "reason": f"HOLD extension has no verified improvement evidence: {extension['reason']}",
                "extension_evidence": extension}
    return {**base, "action": "continue", "state": "stage_continues", "target_stage": stage_id,
            "resume_checkpoint": str(checkpoint), "segment_end": end,
            **({"extension_evidence": extension} if extension is not None else {}),
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
            return _continue_decision(plan, approvals_path, stage_id, iteration, base, manifest_path, p1, p1_path)
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
    if decision.get("extension_evidence") is not None:
        record["extension_evidence"] = decision["extension_evidence"]
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


def _used_before(source, stage_id) -> int:
    """What the counted stages before `stage_id` used: the `budget.used` its own materialization recorded, read from
    the transition file next to the stage's plan and bound to that plan by its SHA."""
    name = (source.document.get("materialization") or {}).get("transition_file")
    path = Path(source.path).parent / name if isinstance(name, str) and name else None
    if path is None or not path.is_file():
        raise ValueError(f"budget: the plan of {stage_id} has no materialization transition to read the earlier use from")
    transition = json.loads(path.read_text(encoding="utf-8-sig"))
    used = (transition.get("budget") or {}).get("used")
    if (transition.get("new_plan_sha") != source.sha256 or transition.get("target_stage") != stage_id
            or type(used) is not int or used < 0):
        raise ValueError(f"budget: the materialization transition of {stage_id} does not belong to its plan")
    return used


def measured_budget(template_path, source_path, manifest_path, gate_path):
    """Active lineage only: origin checkpoint + this completed segment, not a fixed env counter.

    `training_budget.count_from_stage` (decisions.tsv 2026-11-13 15:17): the stages before it (basic gait: E0, E1, E1F)
    are outside the budget, so a boundary of one of them has used 0. From that stage on the use is what the earlier
    counted stages used (recorded by the stage's own materialization) plus this stage's completed updates. A plan
    without the cell counts every stage from E0 on, as before."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_gate_checks import validate_score_pair
    template, source = EX42Plan.load(template_path), EX42Plan.load(source_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    gate = json.loads(Path(gate_path).read_text(encoding="utf-8-sig"))
    if gate.get("state") != "complete" or gate.get("plan_sha256") != source.sha256:
        raise ValueError("budget source gate plan/state differs")
    iteration = gate.get("checkpoint_iteration")
    if type(iteration) is not int or iteration <= 0 or manifest.get("progress", {}).get("completed_updates") != iteration:
        raise ValueError("budget source is not the completed boundary checkpoint")
    checkpoint = Path(manifest_path).resolve().parent / f"model_{iteration}.pt"
    validate_score_pair(expected_iteration=iteration, score=gate, manifest=manifest,
                        checkpoint_exists=checkpoint.is_file(), checkpoint_sha256=_sha256(checkpoint))
    stage = next((r for r in source.document["stages"] if r["id"] == gate.get("stage_id")), None)
    cumulative = ((stage or {}).get("parent") or {}).get("cumulative_update")
    origin = next(r for r in template.document["stages"] if r["id"] == "E0")["parent"]["cumulative_update"]
    budget = template.document.get("training_budget") or {}
    limit = budget.get("maximum_updates")
    if (any(type(n) is not int for n in (cumulative, origin, limit)) or cumulative < origin
            or budget.get("basis") != "ex42_new_updates" or budget.get("count_m_updates") is not True):
        raise ValueError("budget plan has no valid EX42 cumulative origin or approved counter")
    ids, first = [r["id"] for r in template.document["stages"]], budget.get("count_from_stage")
    if first is None:
        used = cumulative + iteration - origin
    elif first not in ids or gate.get("stage_id") not in ids or ids.index(first) == 0:
        raise ValueError("budget plan counts from a stage it does not have (or from its first stage)")
    elif ids.index(gate["stage_id"]) < ids.index(first):
        used = 0                                             # basic gait: outside the budget
    else:
        used = (0 if gate["stage_id"] == first else _used_before(source, gate["stage_id"])) + iteration
    if used > limit:
        raise ValueError("actual cumulative EX42 budget exhausted")
    return {"basis": budget["basis"], "limit": limit, "used": used, "local_updates": iteration,
            **({"count_from_stage": first} if first is not None else {}),
            "parent_cumulative_update": cumulative, "origin_cumulative_update": origin,
            "stage": gate["stage_id"], "source_plan_sha256": source.sha256,
            "manifest_sha256": _sha256(manifest_path), "gate_sha256": _sha256(gate_path)}


def materializer_from_env(env):
    """The `materialize` callable of `decide_next_stage`, or None when no template is configured. Everything comes from
    the environment (machine profile): EX42_MATERIALIZE_TEMPLATE_PLAN / _TEMPLATE_APPROVALS (the approved template),
    _EVIDENCE_DIR (the runner writes <target>.json there from the finished stage's logs and baselines), _OUT_ROOT (one
    immutable folder per target and gate is created under it). Budget is derived from the stage boundary's plan,
    manifest and gate. Fixed _BUDGET_* environment values are ignored.
    A missing artifact refuses the materialization (a notice), it is never guessed.
    E1F is published together with the completed W09+W08 flag chain (`EX42_FLAG_CHAIN`, optional pin
    `EX42_FLAG_CHAIN_SHA256`): its approval needs `calibration_sha256` and the `flag_baseline`, so without the chain the
    handoff does not start it (fail closed, a notice) instead of freezing a plan with an empty calibration."""
    names = ("TEMPLATE_PLAN", "TEMPLATE_APPROVALS", "EVIDENCE_DIR", "OUT_ROOT")
    if not env.get("EX42_MATERIALIZE_TEMPLATE_PLAN"):
        return None

    def run(*, target_stage, gate_receipt, parent_manifest, source_plan):
        missing = [n for n in names if not env.get("EX42_MATERIALIZE_" + n)]
        if missing:
            raise ValueError("materialize setting missing: " + ", ".join("EX42_MATERIALIZE_" + n for n in missing))
        evidence = Path(env["EX42_MATERIALIZE_EVIDENCE_DIR"]) / f"{target_stage}.json"
        if not evidence.is_file():
            if target_stage == "E1F":
                raise ValueError(f"materialize evidence {evidence} is missing (W09/W08 bridge produces E1F evidence)")
            from foothold_s2.ex42_stage_evidence import produce
            evidence = produce(template_path=env["EX42_MATERIALIZE_TEMPLATE_PLAN"], source_path=source_plan,
                               target=target_stage, gate_path=gate_receipt, manifest_path=parent_manifest,
                               output_dir=env["EX42_MATERIALIZE_EVIDENCE_DIR"],
                               bindings_path=env.get("EX42_MATERIALIZE_BINDINGS_FILE"))
        from foothold_s2.ex42_stage_materialize import FLAG_CHAIN_TARGET, materialize
        if target_stage == "E2":
            from foothold_s2.ex42_stage_materialize import _json, _checked_ref
            from foothold_s2.ex42_stage_evidence import validate_m0_m3
            from foothold_s2.curriculum.ex42_prep import EX42Plan
            supplied = _json(evidence).get("bindings", {}).get("prerequisites.m0_m3_receipt_sha256")
            validate_m0_m3(_checked_ref(supplied, evidence.parent),
                           EX42Plan.load(env["EX42_MATERIALIZE_TEMPLATE_PLAN"]))
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
        budget = measured_budget(env["EX42_MATERIALIZE_TEMPLATE_PLAN"], source_plan, parent_manifest, gate_receipt)
        return materialize(
            plan=env["EX42_MATERIALIZE_TEMPLATE_PLAN"], source_plan=source_plan,
            approvals=env["EX42_MATERIALIZE_TEMPLATE_APPROVALS"], target=target_stage, parent_manifest=parent_manifest,
            gate_receipt=gate_receipt, evidence=evidence, budget_limit=budget["limit"], budget_used=budget["used"], budget_basis=budget["basis"],
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
