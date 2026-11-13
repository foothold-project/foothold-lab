"""EX-42 M (map-off supplementary branch): entry, run state, budget and return, as one chain (CPU only, fail closed).

CG v0.17c E.1 M row: at an approved source stage's boundary, when the off survival is below the GT survival minus 6/64 at
the fixed levels L3 / L6 / L9 and that boundary changes no other axis, the run branches into M (p_map_off 0.1 -> 0.3). M
runs 500 updates plus one +500 extension. It returns to the stage it was entered from, p_map_off 0.3 kept, the source's
two windows counted anew. M updates do not count toward the source maximum; they do count toward the EX-42 budget. Not out
by 1,000 -> notify and still return.

The pieces, all pure files + decisions (no Kit, no training here):
  entry_decision     the CG condition from `map_off_cells.json` (missing / foreign / unproven evidence is never an entry)
  publish_entry      the M plan + approvals pair for one entry: the source's commands, shares, terrain and levels copied
                     under M, source approved by the plan's M contract, M approval cell approved and unchanged in scope
  decide_m_boundary  one M boundary: continue / extend / return / notify-and-return, once per boundary (resume safe)
  publish_return     the source stage's plan with p_map_off 0.3 kept and a `window_floor` row: the late judges
                     (`ex42_late_exit_judges._LateJudge`) count only prior windows measured under that return plan

The plan's M contract lists the approved sources (`authorization_contract.source_stage_ids`). An empty list means no
source is approved yet and every entry is refused; this module never widens it.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable

import yaml

from foothold_s2.eval.ex42_map_off_cells import FILE as CELLS_FILE, LEVELS, read_cells
from foothold_s2.ex42_late_exit_judges import M_MAX_UPDATES, MAPOFF_GAP_ENVS, m_return_decision

FORMAT = "foothold-ex42-map-off-branch/1"
STATE_FORMAT = "foothold-ex42-map-off-branch-state/1"
STATE_FILE = "m_branch_state.json"
TRANSITION = "transition.json"
P_MAP_OFF_AFTER = 0.3
OWN_AXIS = "map_off_probability"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path) -> str:
    return _sha_bytes(Path(path).read_bytes())


def _canonical_sha(obj) -> str:
    return _sha_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def _row(doc: dict, stage_id: str) -> dict:
    rows = [r for r in doc.get("stages", []) if r.get("id") == stage_id]
    if len(rows) != 1:
        raise ValueError(f"EX-42 plan has no unique stage {stage_id!r}")
    return rows[0]


def approved_sources(doc: dict) -> list:
    """The source stages the plan's M contract approves. Empty = none approved yet."""
    ids = (_row(doc, "M").get("authorization_contract") or {}).get("source_stage_ids")
    stage_ids = [r.get("id") for r in doc["stages"]]
    if (not isinstance(ids, list) or any(not isinstance(i, str) or i not in stage_ids or i == "M" for i in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("EX-42 M contract source_stage_ids is malformed")
    return ids


def _require_approved(doc: dict, source_stage_id: str) -> None:
    approved = approved_sources(doc)
    if source_stage_id not in approved:
        raise ValueError(f"M source stage {source_stage_id!r} is not approved (approved: {approved or 'none'})")


# ---- entry ------------------------------------------------------------------------------------------------------------
def entry_decision(doc: dict, source_stage_id: str, cells_path, *, checkpoint_sha256: str, changed_axes,
                   plan_sha256: str | None = None, mesh_sha256: str | None = None) -> dict:
    """enter / no_entry / hold at one source boundary. ValueError for a source the plan does not approve.
    Missing, foreign (other checkpoint / plan / mesh / stage) or self-inconsistent evidence is a HOLD, never an entry;
    a boundary that changed another axis is no entry; an unknown axis change is a HOLD."""
    _require_approved(doc, source_stage_id)
    if not isinstance(changed_axes, (list, tuple)) or any(not isinstance(a, str) for a in changed_axes):
        return {"action": "hold", "state": "axis_change_unknown", "reason": "this boundary's changed axes are not known"}
    try:
        row = read_cells(cells_path, checkpoint_sha256=checkpoint_sha256, plan_sha256=plan_sha256,
                         mesh_sha256=mesh_sha256, stage_id=source_stage_id)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"action": "hold", "state": "evidence_unusable", "reason": f"{type(exc).__name__}: {exc}"}
    if row is None:
        return {"action": "hold", "state": "evidence_missing", "reason": "map_off fixed-level cells absent"}
    gaps = {level: row["levels"][level]["eval_gt_alive"] - row["levels"][level]["map_off_alive"] for level in LEVELS}
    base = {"gaps_envs": gaps, "limit_envs": MAPOFF_GAP_ENVS, "cells_sha256": _sha_file(cells_path)}
    others = sorted(a for a in changed_axes if a != OWN_AXIS)
    if others:
        return {**base, "action": "no_entry", "state": "other_axis_changed",
                "reason": f"this boundary also changes {others}"}
    if all(gap <= MAPOFF_GAP_ENVS for gap in gaps.values()):
        return {**base, "action": "no_entry", "state": "map_off_within_limit"}
    return {**base, "action": "enter", "state": "map_off_below_gt"}


def pin_source(doc: dict, source_stage_id: str) -> dict:
    """What M inherits from the source stage, copied from the plan's source row (never from M's own placeholder)."""
    _require_approved(doc, source_stage_id)
    row = _row(doc, source_stage_id)
    missing = [k for k in ("commands", "shares", "terrain", "maximum_updates", "parent") if k not in row]
    if missing or f"exposure_at_{source_stage_id}" not in row["terrain"]:
        raise ValueError(f"source stage {source_stage_id} lacks {missing or 'its terrain exposure'}: nothing to inherit")
    pin = {"source_stage_id": source_stage_id, "commands": deepcopy(row["commands"]), "shares": deepcopy(row["shares"]),
           "terrain": deepcopy(row["terrain"]), "maximum_updates": row["maximum_updates"],
           "p_map_off": deepcopy(row.get("p_map_off") or {"continuous": 0.1, "sparse": 0.0})}
    pin["pin_sha256"] = _canonical_sha({k: v for k, v in pin.items()})
    return pin


def _m_row(doc: dict, pin: dict, *, parent: dict) -> dict:
    source = pin["source_stage_id"]
    row = deepcopy(_row(doc, "M"))
    terrain = deepcopy(pin["terrain"])
    terrain["exposure_at_M"] = terrain.pop(f"exposure_at_{source}")
    row.update(enabled=True, commands=deepcopy(pin["commands"]), shares=deepcopy(pin["shares"]), terrain=terrain,
               parent=parent, p_map_off={"continuous": P_MAP_OFF_AFTER, "sparse": pin["p_map_off"].get("sparse", 0.0)},
               branch_origin={"stage_id": source, "pin_sha256": pin["pin_sha256"]})
    return row


def _dump(doc) -> bytes:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True).encode()


def _publish(out, template_dir: Path, plan_bytes: bytes, approval_bytes: bytes, transition: dict) -> Path:
    """One immutable folder per boundary: a duplicate or resumed attempt is a FileExistsError, never a second pair."""
    destination = Path(out).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"immutable output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="." + destination.name + ".", dir=destination.parent))
    try:
        for path in template_dir.rglob("*"):
            relative = path.relative_to(template_dir)
            if ("provenance" in relative.parts or path.name == TRANSITION or not path.is_file()
                    or path.suffix not in (".yaml", ".yml", ".json") or path.is_symlink()):
                continue
            (staging / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, staging / relative)
        (staging / "ex42-prep.yaml").write_bytes(plan_bytes)
        (staging / "ex42-approvals.yaml").write_bytes(approval_bytes)
        transition = {**transition, "plan_sha256": _sha_bytes(plan_bytes), "approval_sha256": _sha_bytes(approval_bytes)}
        (staging / TRANSITION).write_text(json.dumps(transition, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        from foothold_s2.curriculum.ex42_prep import EX42Plan
        EX42Plan.load(staging / "ex42-prep.yaml")                      # the published plan must load by itself
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def _approval_cell(approvals_doc: dict, stage_row: dict) -> dict:
    cell = approvals_doc.get("stage_m_authorization")
    scope = (cell or {}).get("scope") if isinstance(cell, dict) else None
    if (not isinstance(scope, dict) or cell.get("approved") is not True or cell.get("optional_branch") is not True
            or scope.get("stage_id") != "M" or scope.get("maximum_updates") != stage_row["maximum_updates"]
            or scope.get("start_update") != 0 or scope.get("later_stages_authorized") is not False):
        raise ValueError("M approval cell is not approved with the plan's own scope; nothing widens it")
    return cell


def publish_entry(*, plan_path, approvals_path, source_stage_id: str, cells_path, checkpoint_sha256: str,
                  source_iteration: int, changed_axes, budget_limit: int, budget_used: int, out) -> dict:
    """The M plan + approvals pair for one entry. The entry condition is evaluated again here (a caller's claim is not
    evidence). `budget_used` is the EX-42 total before M; M's cap is reserved against `budget_limit`."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    plan = EX42Plan.load(plan_path)
    doc = deepcopy(plan.document)
    row = _row(doc, "M")
    source_row = _row(doc, source_stage_id)
    decision = entry_decision(doc, source_stage_id, cells_path, checkpoint_sha256=checkpoint_sha256,
                              changed_axes=changed_axes, plan_sha256=plan.sha256, mesh_sha256=None)
    if decision["action"] != "enter":
        raise ValueError(f"M entry condition is not met: {decision['state']}")
    if type(source_iteration) is not int or source_iteration <= 0:
        raise ValueError("source iteration must be a positive int")
    cap = row["maximum_updates"] + row["extension_updates"] * row["extension_max_count"]
    if (type(budget_limit) is not int or type(budget_used) is not int or budget_used < 0
            or budget_limit < budget_used + cap or cap != M_MAX_UPDATES):
        raise ValueError("EX-42 budget cannot hold M's reserved 1,000 updates")
    approvals = yaml.safe_load(Path(approvals_path).read_text(encoding="utf-8-sig"))
    cell = _approval_cell(approvals, row)
    pin = pin_source(doc, source_stage_id)
    parent = {"source_stage_id": source_stage_id, "manifest_local_update": source_iteration,
              "checkpoint_key": f"model_{source_iteration}.pt", "sha256": checkpoint_sha256,
              "cumulative_update": source_row["parent"]["cumulative_update"] + source_iteration}
    cell.setdefault("prerequisites", {}).update(
        branch_origin_stage_id=source_stage_id, return_stage_id=source_stage_id,
        entry_condition_receipt_sha256=decision["cells_sha256"])
    cell["scope"]["parent_sha256"] = checkpoint_sha256
    cell.setdefault("entry", {})["source_stage"] = source_stage_id
    row_after = _m_row(doc, pin, parent=parent)
    doc["stages"] = [row_after if r["id"] == "M" else r for r in doc["stages"]]
    approval_bytes = _dump(approvals)
    doc["stage_zero"]["approval_sha256"] = _sha_bytes(approval_bytes)
    transition = {"format": FORMAT, "kind": "enter", "source_stage_id": source_stage_id, "pin_sha256": pin["pin_sha256"],
                  "source_plan": str(Path(plan_path).resolve()), "source_plan_sha256": plan.sha256,
                  "source_approvals": str(Path(approvals_path).resolve()),
                  "source_approvals_sha256": _sha_file(approvals_path),
                  "source_iteration": source_iteration, "checkpoint_sha256": checkpoint_sha256,
                  "entry": {k: decision[k] for k in ("gaps_envs", "limit_envs", "cells_sha256")},
                  "budget": {"limit": budget_limit, "used_before_m": budget_used, "reserved": cap,
                             "basis": "ex42_new_updates", "m_counts_toward_source_maximum": False},
                  "boundary_interval": doc["evaluation"]["interval_updates"], "training_started": False}
    folder = _publish(out, Path(plan_path).resolve().parent, _dump(doc), approval_bytes, transition)
    return {"plan": str(folder / "ex42-prep.yaml"), "approvals": str(folder / "ex42-approvals.yaml"),
            "plan_sha256": _sha_file(folder / "ex42-prep.yaml"), "folder": str(folder), "source_stage_id": source_stage_id,
            "entry": transition["entry"]}


# ---- M boundaries -----------------------------------------------------------------------------------------------------
def _read_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _load_transition(plan_path) -> dict:
    transition = _read_json(Path(plan_path).resolve().parent / TRANSITION)
    if transition.get("format") != FORMAT or transition.get("kind") != "enter":
        raise ValueError("plan folder is not an M branch entry")
    return transition


def decide_m_boundary(plan_path, p1_path, iteration: int, judgement: str, *, notify: Callable | None = None,
                      return_out=None) -> dict:
    """One M boundary (M-local `iteration`, `judgement` the M exit judge's verdict) -> a decision for the hand-off.
    Once per boundary: a repeated call of the same boundary, or any call after the branch has decided to return, answers
    with the stored decision and counts nothing twice. `return_out` is the folder the return plan pair is published into
    (once). A failing `notify` is recorded and reported (`notified` False), never turned into success."""
    transition = _load_transition(plan_path)
    interval = transition["boundary_interval"]
    if type(iteration) is not int or iteration <= 0 or iteration % interval or iteration > M_MAX_UPDATES:
        raise ValueError(f"M boundary {iteration!r} is not a multiple of {interval} within {M_MAX_UPDATES}")
    state_path = Path(p1_path).resolve().parent / STATE_FILE
    state = (_read_json(state_path) if state_path.is_file() else
             {"format": STATE_FORMAT, "source_stage_id": transition["source_stage_id"], "plan_sha256": transition["plan_sha256"],
              "last_boundary": 0, "extension_used": False, "status": "running", "last_decision": None})
    if state.get("format") != STATE_FORMAT or state.get("plan_sha256") != transition["plan_sha256"]:
        raise ValueError("M branch state belongs to another plan")
    if state["status"] != "running" or iteration == state["last_boundary"]:
        return {**state["last_decision"], "duplicate": True}
    if iteration < state["last_boundary"]:
        raise ValueError("M boundary goes backwards")
    source = transition["source_stage_id"]
    step = m_return_decision(source_stage=source, m_updates=iteration, m_judgement=judgement,
                             extension_used=state["extension_used"])
    budget = {"m_updates": iteration, "ex42_budget_used_after": transition["budget"]["used_before_m"] + iteration,
              "source_stage_updates_counted": transition["source_iteration"], "m_updates_count_toward_source_maximum": False,
              "m_updates_count_toward_ex42_budget": True}
    decision = {"stage_id": "M", "boundary_iteration": iteration, "judgment": judgement, "m_state": step["state"],
                "budget": budget, "p_map_off": P_MAP_OFF_AFTER, "return_to": source}
    if step["action"] in ("continue", "extend"):
        limit = step.get("next_maximum", 500 if state["extension_used"] is False else M_MAX_UPDATES)
        decision.update(action="continue", state="m_extension" if step["action"] == "extend" else "m_continues",
                        target_stage="M", segment_end=min(iteration + interval, limit),
                        plan=str(Path(plan_path).resolve()),
                        approvals=str(Path(plan_path).resolve().parent / "ex42-approvals.yaml"))
        state["extension_used"] = state["extension_used"] or step["action"] == "extend"
        state["status"] = "running"
    else:
        exhausted = step["action"] == "notify_and_return"
        decision.update(action="launch", state=("m_exhausted_return_to_source" if exhausted else "m_exit_return_to_source"),
                        target_stage=source, notification_required=exhausted, notified=None,
                        source_windows_counted_after_return=0, required_new_windows_after_return=2)
        if exhausted:
            message = (f"M did not exit within {M_MAX_UPDATES} updates (judgement {judgement}); "
                       f"returning to {source} with p_map_off {P_MAP_OFF_AFTER} kept")
            try:
                if notify is None:
                    raise ValueError("no notification channel was given")
                notify(message)
                decision["notified"] = True
            except Exception as exc:        # a failed notice stays visible: the return still happens, the flag says so
                decision.update(notified=False, notify_error=f"{type(exc).__name__}: {exc}")
        if return_out is None:
            raise ValueError("a return needs the folder to publish the source plan pair into")
        decision.update(publish_return(plan_path, return_out, m_iteration=iteration))
        state["status"] = "returned"
    state.update(last_boundary=iteration, last_decision=decision)
    _write_json_atomic(state_path, state)
    return decision


def publish_return(plan_path, out, *, m_iteration: int) -> dict:
    """The source stage's own plan again (read from the entry's pinned source plan, bytes checked), its row carrying
    p_map_off 0.3 and a window floor: windows measured before this return never count toward the two new ones."""
    transition = _load_transition(plan_path)
    source_plan = Path(transition["source_plan"])
    if _sha_file(source_plan) != transition["source_plan_sha256"] or \
            _sha_file(transition["source_approvals"]) != transition["source_approvals_sha256"]:
        raise ValueError("the source plan or approvals changed after M was entered")
    doc = yaml.safe_load(source_plan.read_text(encoding="utf-8-sig"))
    source = transition["source_stage_id"]
    row = _row(doc, source)
    row["p_map_off"] = {"continuous": P_MAP_OFF_AFTER, "sparse": (row.get("p_map_off") or {}).get("sparse", 0.0)}
    row["window_floor"] = {"after_m_iteration": m_iteration, "after_checkpoint": f"model_{m_iteration}.pt",
                           "required_new_windows": 2, "entry_checkpoint_sha256": transition["checkpoint_sha256"]}
    doc["branch_return"] = {"from_stage": "M", "to_stage": source, "m_updates": m_iteration, "entry_plan": str(Path(plan_path).resolve())}
    approval_bytes = Path(transition["source_approvals"]).read_bytes()
    doc["stage_zero"]["approval_sha256"] = _sha_bytes(approval_bytes)
    return_transition = {"format": FORMAT, "kind": "return", "source_stage_id": source, "m_updates": m_iteration,
                         "entry_plan_sha256": transition["plan_sha256"], "entry_plan": str(Path(plan_path).resolve()),
                         "source_plan_sha256": transition["source_plan_sha256"],
                         "ex42_budget_used_after": transition["budget"]["used_before_m"] + m_iteration,
                         "training_started": False}
    folder = _publish(out, source_plan.resolve().parent, _dump(doc), approval_bytes, return_transition)
    return {"plan": str(folder / "ex42-prep.yaml"), "approvals": str(folder / "ex42-approvals.yaml"),
            "return_plan_sha256": _sha_file(folder / "ex42-prep.yaml")}


def branch_from_env(env) -> Callable | None:
    """The `branch` callable of the hand-off: publishes an entry pair under EX42_MATERIALIZE_OUT_ROOT, with the EX-42
    budget measured from the template plan (EX42_MATERIALIZE_TEMPLATE_PLAN), the boundary manifest and the gate receipt as
    the stage materializer does. None when no out root is set (the branch is then never entered by itself)."""
    root = env.get("EX42_MATERIALIZE_OUT_ROOT")
    if not root:
        return None

    def run(*, plan_path, approvals_path, source_stage_id, cells_path, checkpoint_sha256, source_iteration,
            changed_axes, parent_manifest, gate_receipt):
        template = env.get("EX42_MATERIALIZE_TEMPLATE_PLAN")
        if not template:
            raise ValueError("materialize setting missing: EX42_MATERIALIZE_TEMPLATE_PLAN")
        from foothold_s2.ex42_stage_handoff import measured_budget
        budget = measured_budget(template, plan_path, parent_manifest, gate_receipt)
        return publish_entry(plan_path=plan_path, approvals_path=approvals_path, source_stage_id=source_stage_id,
                             cells_path=cells_path, checkpoint_sha256=checkpoint_sha256,
                             source_iteration=source_iteration, changed_axes=changed_axes,
                             budget_limit=budget["limit"], budget_used=budget["used"],
                             out=Path(root) / f"M_{source_stage_id}_{_sha_file(gate_receipt)[:12]}")
    return run
