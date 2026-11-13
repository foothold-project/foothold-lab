"""E2 named-kind evidence and the lead-approved forward plus four-flag denominator."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import yaml

from foothold_s2.eval.ex42_kind_completion import read_start_kind_cell
from foothold_s2.eval.ex42_kind_flag_cells import read_kind_flag_cell
from foothold_s2.ex42_stage_judges import StageJudge, aggregate, previous_window, register

MODES = ("eval_gt", "eval_pred", "probe_prop_only")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _spec(plan: dict) -> dict:
    spec = plan["evaluation"]["e2_kind_cells"]
    promotion = plan["evaluation"]["promotion"]
    if (spec.get("family") != "A" or spec.get("kind") != "stepping_stones_low" or
            spec.get("level") != 0 or spec.get("flag_count") != "flag_four" or
            spec.get("valid_min_each") != 48 or
            spec.get("judge_modes") != ["eval_gt", "eval_pred"] or
            spec.get("record_modes") != ["probe_prop_only"] or
            promotion.get("window_episodes") != 64 or promotion.get("windows") != 2):
        raise ValueError("EX-42 E2 named-kind exit contract differs")
    return spec


def score_mode(forward: dict, flag: dict, *, valid_min_each: int,
               success_min: int, survival_min: int, weak_fraction: float) -> dict:
    """Judge each 64-env subcell; combined counts are evidence only."""
    values = (forward, flag)
    if (any(type(row.get("valid_count")) is not int or not 0 <= row["valid_count"] <= 64 or
            any(type(row.get(key)) is not int or not 0 <= row[key] <= row["valid_count"]
                for key in ("success_count", "survival_count")) for row in values) or
            type(valid_min_each) is not int or not 0 < valid_min_each <= 64 or
            type(success_min) is not int or type(survival_min) is not int or
            not 0 <= success_min <= survival_min <= 64 or
            type(weak_fraction) not in (float, int) or not math.isfinite(weak_fraction) or
            not 0 < weak_fraction < 1):
        raise ValueError("EX-42 E2 kind counts or thresholds invalid")
    valid = sum(row["valid_count"] for row in values)
    success = sum(row["success_count"] for row in values)
    survival = sum(row["survival_count"] for row in values)
    success_floor = math.ceil(success_min * valid / 64)
    survival_floor = math.ceil(survival_min * valid / 64)
    def subcell(row: dict) -> dict:
        # Keep the current proportional rule for valid counts below 64 in one place.
        floor_success = math.ceil(success_min * row["valid_count"] / 64)
        floor_survival = math.ceil(survival_min * row["valid_count"] / 64)
        verdict = ("HOLD" if row["valid_count"] < valid_min_each else
                   "PASS" if row["success_count"] >= floor_success and
                             row["survival_count"] >= floor_survival else "FAIL")
        return {**row, "success_min": floor_success, "survival_min": floor_survival,
                "judgement": verdict}

    forward_scored, flag_scored = (subcell(row) for row in values)
    state = ("HOLD" if "HOLD" in (forward_scored["judgement"], flag_scored["judgement"])
             else "PASS" if forward_scored["judgement"] == flag_scored["judgement"] == "PASS"
             else "FAIL")
    # The old weak-subcell plan key remains pinned; this warning is record only.
    warnings = [name for name, row in zip(("forward", "flag_four"), values)
                if row["success_count"] < math.ceil(success_min * row["valid_count"] * weak_fraction / 64)]
    return {"judgement": state, "valid_count": valid, "success_count": success,
            "survival_count": survival, "success_min": success_floor,
            "survival_min": survival_floor, "subcell_valid_min": valid_min_each,
            "weak_subcell_warnings": warnings,
            "forward": forward_scored, "flag_four": flag_scored}


def read_bundle(folder: Path, *, plan: dict, plan_sha256: str, mesh: dict,
                checkpoint_sha256: str, seed: int) -> dict:
    spec = _spec(plan)
    folder = Path(folder)
    flag = read_kind_flag_cell(folder / "flag_four", plan=plan,
                               plan_sha256=plan_sha256, mesh=mesh,
                               checkpoint_sha256=checkpoint_sha256, seed=seed,
                               family=spec["family"], kind=spec["kind"], level=spec["level"])
    output = {}
    promotion = plan["evaluation"]["promotion"]
    for mode in MODES:
        forward = read_start_kind_cell(folder / "forward", mesh=mesh,
                                       checkpoint_sha256=checkpoint_sha256, seed=seed,
                                       family=spec["family"], kind=spec["kind"],
                                       level=spec["level"], mode=mode,
                                       seconds=spec["forward_seconds"],
                                       settle_s=spec["completion_settle_s"])
        output[mode] = score_mode(
            forward, flag[mode], valid_min_each=spec["valid_min_each"],
            success_min=promotion["success_min"], survival_min=promotion["survival_min"],
            weak_fraction=spec["weak_subcell_warning_fraction_of_success_floor"])
        output[mode]["role"] = "record_only" if mode == "probe_prop_only" else "judge"
    return output


def checked_previous_bundle(prior_score: dict | None, *, evaluation: Path, plan: dict,
                            plan_sha256: str, mesh: dict, seed: int) -> dict | None:
    """Recount the prior window from its raw files before it can help E2 exit."""
    if prior_score is None or "e2_kind" not in prior_score:
        return None
    expected_folder = Path(evaluation).parent / f"m{Path(prior_score['checkpoint']).stem.removeprefix('model_')}" / "kind_cells"
    recorded = prior_score["e2_kind"]
    if (recorded.get("evaluation") != str(expected_folder) or
            recorded.get("mesh_sha256") != mesh["mesh_sha256"] or
            prior_score.get("maintenance_source_sha256") != plan_sha256 or
            prior_score.get("conditions", {}).get("eval_seed") != seed):
        raise ValueError("EX-42 E2 previous kind window identity differs")
    failure = recorded.get("child_failure")
    if failure is not None:
        marker = expected_folder / "child_failures.json"
        if (failure != {"path": str(marker), "sha256": _sha(marker)} or
                any(recorded.get("modes", {}).get(mode, {}).get("judgement") != "HOLD"
                    for mode in MODES)):
            raise ValueError("EX-42 E2 previous child failure evidence differs")
        return recorded["modes"]
    recounted = read_bundle(expected_folder, plan=plan, plan_sha256=plan_sha256,
                            mesh=mesh, checkpoint_sha256=prior_score["checkpoint_sha256"], seed=seed)
    if recorded.get("modes") != recounted:
        raise ValueError("EX-42 E2 previous kind window differs from its raw evidence")
    return recounted


class E2KindTwoWindowJudge(StageJudge):
    name = "kind_two_window_e2"

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import judge as judge_maintenance, load_baseline
        from foothold_s2.eval.ex42_mesh_eval import preflight

        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        current = judge_maintenance(score, baseline, measured)
        prior_score = previous_window(ctx)
        prior = judge_maintenance(prior_score, baseline, measured) if prior_score else None
        map_row = json.loads((ctx.evaluation / "map64" / "map_modes.json").read_text(encoding="utf-8-sig"))
        recorded_mesh = map_row.get("ex42_mesh") or {}
        mesh = preflight(Path(recorded_mesh["manifest"]).parent)
        if mesh["mesh_sha256"] != recorded_mesh.get("mesh_sha256"):
            raise ValueError("EX-42 E2 score mesh differs from pinned map64")
        d44_dir = ctx.evaluation / "d44"
        if (d44_dir / "d44_cells.json").is_file():
            from foothold_s2.eval.ex42_d44_cells import read_evidence
            score["d44_cells"] = read_evidence(
                d44_dir, plan=ctx.plan, plan_sha256=ctx.digest(ctx.plan_path),
                checkpoint_sha256=ctx.checkpoint_sha, seed=ctx.seed)
        flag_dir = ctx.evaluation / "flag_cells"
        for count in ("flag_one", "flag_four"):
            if (flag_dir / count / "flag_cells.json").is_file():
                from foothold_s2.eval.ex42_flag_cells import read_evidence
                score.setdefault("flag_cells", {}).update(read_evidence(
                    flag_dir / count, plan=ctx.plan, plan_sha256=ctx.digest(ctx.plan_path),
                    checkpoint_sha256=ctx.checkpoint_sha, seed=ctx.seed, count=count))
        for retained in ("d44_cells", "flag_cells"):
            if retained in score:
                current[retained] = score[retained]
        failure_path = ctx.evaluation / "kind_cells" / "child_failures.json"
        if failure_path.is_file():
            failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
            if (failure.get("format") != "foothold-ex42-e2-child-failures/1" or
                    failure.get("checkpoint_sha256") != ctx.checkpoint_sha or
                    not isinstance(failure.get("reason"), str) or not failure["reason"]):
                raise ValueError("EX-42 E2 child failure marker identity invalid")
            now = {mode: {"judgement": "HOLD", "reason": failure["reason"],
                          "role": "record_only" if mode == "probe_prop_only" else "judge"}
                   for mode in MODES}
        else:
            now = read_bundle(ctx.evaluation / "kind_cells", plan=ctx.plan,
                              plan_sha256=ctx.digest(ctx.plan_path), mesh=mesh,
                              checkpoint_sha256=ctx.checkpoint_sha, seed=ctx.seed)
        old = checked_previous_bundle(prior_score, evaluation=ctx.evaluation, plan=ctx.plan,
                                      plan_sha256=ctx.digest(ctx.plan_path), mesh=mesh, seed=ctx.seed)
        current["stage_id"] = "E2"
        current["e2_kind"] = {"modes": now, "previous_modes": old,
                              "mesh_sha256": mesh["mesh_sha256"],
                              "evaluation": str(ctx.evaluation / "kind_cells"),
                              **({"child_failure": {"path": str(failure_path),
                                                       "sha256": _sha(failure_path)}} if failure_path.is_file() else {})}
        from foothold_s2.ex42_exchange_watch import compare
        from foothold_s2.ex42_learned_cells_evidence import judge_two_boundaries
        exchange = compare(current, prior_score, measured=measured, baseline=baseline,
                           kind_now=now, kind_previous=old)
        approvals_path = ctx.plan_path.parent / ctx.plan["approval_file"]
        approvals = yaml.safe_load(approvals_path.read_text(encoding="utf-8-sig"))
        authorization = approvals["stage_e2_authorization"]
        if authorization.get("approved") is not True:
            raise ValueError("EX-42 E2 learned_cells threshold authorization absent")
        learned = judge_two_boundaries(
            ctx.checkpoint, stage_id="E2", plan=ctx.plan,
            plan_sha256=current.get("execution_plan_sha256", ""),
            interval=ctx.plan["evaluation"]["interval_updates"],
            min_episodes=authorization["exit_gate"]["learned_cells_min"],
            previous_kind_pass=bool(old and all(old[mode]["judgement"] == "PASS"
                                                for mode in ("eval_gt", "eval_pred"))))
        items = {"maintenance_current": {"role": "judge", "judgement": current["judgement"]},
                 "maintenance_previous": {"role": "judge", "judgement": prior["judgement"] if prior else "HOLD"},
                 "learned_cells": learned,
                 "exchange_watch": exchange}
        for mode in ("eval_gt", "eval_pred"):
            items[f"{mode}_current"] = {"role": "judge", **now[mode]}
            items[f"{mode}_previous"] = ({"role": "judge", **old[mode]} if old and mode in old
                                          else {"role": "judge", "judgement": "HOLD", "reason": "직전 창 없음"})
        items["probe_prop_only_current"] = {"role": "record_only", **now["probe_prop_only"]}
        verdict = aggregate(item["judgement"] for item in items.values() if item["role"] == "judge")
        current.update(stage_id="E2", judgement=verdict,
                       stage_exit={"adapter": self.name, "judgement": verdict,
                                   "windows": 2, "items": items})
        return current

    def verify(self, score, judgment, expected, plan=None):
        from foothold_s2.ex42_stage_judges import _map39_cell_check
        if plan is None or score.get("stage_id") != "E2":
            raise ValueError("EX-42 E2 P1 plan or stage identity missing")
        exit_row = score.get("stage_exit") or {}
        items = exit_row.get("items") or {}
        required = {"maintenance_current", "maintenance_previous", "learned_cells", "exchange_watch",
                    "eval_gt_current", "eval_gt_previous", "eval_pred_current", "eval_pred_previous",
                    "probe_prop_only_current"}
        if (exit_row.get("adapter") != self.name or exit_row.get("windows") != 2 or
                exit_row.get("judgement") != judgment or
                set(items) != required or
                any(item.get("judgement") not in ("PASS", "HOLD", "FAIL") for item in items.values()) or
                any(items[key].get("role") != ("record_only" if key == "probe_prop_only_current" else "judge")
                    for key in required) or
                _map39_cell_check(score, judgment, MODES) != expected or
                items.get("maintenance_current", {}).get("judgement") != expected or
                aggregate(item.get("judgement") for item in items.values()
                          if item.get("role") == "judge") != judgment):
            raise ValueError("EX-42 E2 P1 aggregate stage exit differs")
        # The scorer cannot issue PASS until the training exposure and exchange
        # evidence is connected. A forged PASS must never skip that HOLD.
        if judgment == "PASS" and any(items.get(key, {}).get("judgement") != "PASS"
                                      for key in ("learned_cells", "exchange_watch")):
            raise ValueError("EX-42 E2 training evidence absent")
        kind = score.get("e2_kind") or {}
        folder = Path(kind.get("evaluation", ""))
        if folder.name != "kind_cells" or not folder.parent.is_dir():
            raise ValueError("EX-42 E2 kind evaluation directory missing")
        map_row = json.loads((folder.parent / "map64" / "map_modes.json").read_text(encoding="utf-8-sig"))
        recorded_mesh = map_row.get("ex42_mesh") or {}
        from foothold_s2.eval.ex42_mesh_eval import preflight
        mesh = preflight(Path(recorded_mesh["manifest"]).parent)
        if mesh["mesh_sha256"] != kind.get("mesh_sha256") or mesh["mesh_sha256"] != recorded_mesh.get("mesh_sha256"):
            raise ValueError("EX-42 E2 P1 mesh identity differs")
        failure = kind.get("child_failure")
        if failure:
            path = folder / "child_failures.json"
            if (failure != {"path": str(path), "sha256": _sha(path)} or
                    judgment == "PASS" or any(items[f"{mode}_current"]["judgement"] != "HOLD"
                        for mode in ("eval_gt", "eval_pred"))):
                raise ValueError("EX-42 E2 child failure cannot prove PASS")
        else:
            recounted = read_bundle(folder, plan=plan,
                                    plan_sha256=score["maintenance_source_sha256"], mesh=mesh,
                                    checkpoint_sha256=score["checkpoint_sha256"],
                                    seed=score["conditions"]["eval_seed"])
            if kind.get("modes") != recounted or any(
                    items[f"{mode}_current"] != {"role": "judge", **recounted[mode]}
                    for mode in ("eval_gt", "eval_pred")):
                raise ValueError("EX-42 E2 P1 kind score differs from raw")
        from foothold_s2.ex42_e1_judge import previous_e1_score
        previous = previous_e1_score(Path(score["checkpoint"]), folder.parent,
                                     plan["evaluation"]["interval_updates"],
                                     score["score_config_sha256"], stage_id="E2")
        old = checked_previous_bundle(previous, evaluation=folder.parent, plan=plan,
                                      plan_sha256=score["maintenance_source_sha256"], mesh=mesh,
                                      seed=score["conditions"]["eval_seed"])
        if kind.get("previous_modes") != old or (judgment == "PASS" and old is None) or any(
                items[f"{mode}_previous"]["judgement"] != "HOLD" if old is None else
                items[f"{mode}_previous"] != {"role": "judge", **old[mode]}
                for mode in ("eval_gt", "eval_pred")):
            raise ValueError("EX-42 E2 P1 previous kind window differs from raw")
        return {"stage_exit": exit_row}


register(E2KindTwoWindowJudge())
