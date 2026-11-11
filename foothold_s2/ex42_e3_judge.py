"""E3 exit from the actual opened terrain, raw kind cells and two save windows."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from foothold_s2.ex42_stage_judges import StageJudge, aggregate, previous_window, register
from foothold_s2.eval.ex42_mesh_eval import preflight
from foothold_s2.eval.ex42_stage_kind_bundle import e3_target_inventory, read_e3_window

MODES = ("eval_gt", "eval_pred", "probe_prop_only")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mesh(score: dict, evaluation: Path) -> dict:
    row = json.loads((evaluation / "map64" / "map_modes.json").read_text(encoding="utf-8-sig"))
    recorded = row.get("ex42_mesh") or {}
    mesh = preflight(Path(recorded["manifest"]).parent)
    if mesh["mesh_sha256"] != recorded.get("mesh_sha256"):
        raise ValueError("EX-42 E3 pinned map64 mesh differs")
    return mesh


def recount(score: dict, *, plan: dict, evaluation: Path, mesh: dict) -> dict:
    """A marker or missing receipt is HOLD. Every PASS is recomputed from the raw traces."""
    from foothold_s2.ex42_learned_cells_evidence import read_stage_exposure

    folder = evaluation / "kind_cells_e3"
    if score.get("stage_id") != "E3" or score.get("checkpoint_sha256") is None:
        raise ValueError("EX-42 E3 score identity differs")
    marker = folder / "child_failures.json"
    if marker.is_file():
        failure = json.loads(marker.read_text(encoding="utf-8-sig"))
        if (failure.get("format") != "foothold-ex42-e3-child-failures/1" or
                failure.get("checkpoint_sha256") != score["checkpoint_sha256"] or
                not failure.get("reason")):
            raise ValueError("EX-42 E3 child failure marker differs")
        return {"judgement": "HOLD", "reason": failure["reason"],
                "child_failure": {"path": str(marker), "sha256": _sha(marker)},
                "mesh_sha256": mesh["mesh_sha256"], "evaluation": str(folder)}
    table = [{"family": family, "kind": kind}
             for family, kind in zip(mesh["column_family"], mesh["columns"])]
    exposure = read_stage_exposure(Path(score["checkpoint"]), stage_id="E3", plan=plan,
                                   plan_sha256=score["execution_plan_sha256"], column_table=table)
    if exposure is None:
        return {"judgement": "HOLD", "reason": "E3 학습 노출 영수증 없음",
                "mesh_sha256": mesh["mesh_sha256"], "evaluation": str(folder)}
    inventory = e3_target_inventory(plan, exposure["opened_kinds"])
    if exposure["mesh_sha256"] != mesh["mesh_sha256"]:
        raise ValueError("EX-42 E3 training and evaluation mesh differ")
    cells = (read_e3_window(folder, inventory=inventory, plan=plan,
                            plan_sha256=score["maintenance_source_sha256"], mesh=mesh,
                            checkpoint_sha256=score["checkpoint_sha256"],
                            seed=score["conditions"]["eval_seed"])
             if inventory["opened_cells"] else {})
    states = [row[mode]["judgement"] for row in cells.values()
              for mode in ("eval_gt", "eval_pred")]
    if inventory["missing_targets"] or not states:
        states.append("HOLD")
    return {"judgement": aggregate(states), "inventory": inventory, "cells": cells,
            "stage_exposure": exposure["receipts"],
            "mesh_sha256": mesh["mesh_sha256"], "evaluation": str(folder)}


def _retained(score: dict, *, evaluation: Path, plan: dict, plan_sha256: str,
              checkpoint_sha256: str, seed: int) -> None:
    from foothold_s2.eval.ex42_d44_cells import read_evidence as read_d44
    from foothold_s2.eval.ex42_flag_cells import read_evidence as read_flag

    score["d44_cells"] = read_d44(evaluation / "d44", plan=plan,
                                  plan_sha256=plan_sha256,
                                  checkpoint_sha256=checkpoint_sha256, seed=seed)
    flags = {}
    for count in ("flag_one", "flag_four"):
        flags.update(read_flag(evaluation / "flag_cells" / count, plan=plan,
                               plan_sha256=plan_sha256,
                               checkpoint_sha256=checkpoint_sha256, seed=seed, count=count))
    score["flag_cells"] = flags


class E3KindTwoWindowJudge(StageJudge):
    name = "kind_two_window_e3"

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import judge as judge_maintenance, load_baseline
        from foothold_s2.ex42_exchange_watch import compare
        from foothold_s2.ex42_learned_cells_evidence import judge_two_boundaries

        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        now = judge_maintenance(score, baseline, measured)
        old_score = previous_window(ctx)
        old = judge_maintenance(old_score, baseline, measured) if old_score else None
        plan_sha = ctx.digest(ctx.plan_path)
        _retained(now, evaluation=ctx.evaluation, plan=ctx.plan, plan_sha256=plan_sha,
                  checkpoint_sha256=ctx.checkpoint_sha, seed=ctx.seed)
        mesh = _mesh(now, ctx.evaluation)
        current_kind = recount(now, plan=ctx.plan, evaluation=ctx.evaluation, mesh=mesh)
        prior_evaluation = (Path(old_score["e3_kind"]["evaluation"]).parent
                            if old_score and "e3_kind" in old_score else None)
        prior_mesh = _mesh(old_score, prior_evaluation) if prior_evaluation else None
        if prior_mesh and prior_mesh["mesh_sha256"] != mesh["mesh_sha256"]:
            raise ValueError("EX-42 E3 prior and current evaluation mesh differ")
        previous_kind = (recount(old_score, plan=ctx.plan, evaluation=prior_evaluation, mesh=prior_mesh)
                         if prior_evaluation else None)
        now["stage_id"] = "E3"
        now["e3_kind"] = {**current_kind, "previous": previous_kind}
        kind_states = [current_kind["judgement"],
                       previous_kind["judgement"] if previous_kind else "HOLD"]
        if (current_kind.get("cells") and previous_kind and previous_kind.get("cells") and
                set(current_kind["cells"]) != set(previous_kind["cells"])):
            kind_states.append("HOLD")
        prior_pass = {}
        for key, bundle in (previous_kind or {}).get("cells", {}).items():
            family, kind = key.split("/", 2)[:2]
            prior_pass[(family, kind)] = prior_pass.get((family, kind), False) or all(
                bundle[mode]["judgement"] == "PASS" for mode in ("eval_gt", "eval_pred"))
        learned = judge_two_boundaries(
            ctx.checkpoint, stage_id="E3", plan=ctx.plan,
            plan_sha256=now.get("execution_plan_sha256", ""),
            interval=ctx.plan["evaluation"]["interval_updates"],
            min_episodes=ctx.plan["evaluation"]["e3_kind_exit"]["learned_cells_min"],
            registered_kind_passes=prior_pass)
        comparisons = []
        if old and previous_kind and current_kind.get("cells") and previous_kind.get("cells"):
            for key, bundle in current_kind["cells"].items():
                if key in previous_kind["cells"]:
                    comparisons.append(compare(now, old, measured=measured, baseline=baseline,
                                               kind_now=bundle, kind_previous=previous_kind["cells"][key],
                                               stage_id="E3", kind_score_key="e3_kind"))
        exchange = {"role": "judge", "judgement": aggregate(r["judgement"] for r in comparisons),
                    "cells": comparisons, "reason": "E3 직전 경계 종류별 비교 결측" if not comparisons else None}
        # The command share must be demonstrated by a pinned training readback.
        # Neither the E3 prep stage nor the current exposure receipt records it yet.
        flag_share = {"role": "judge", "judgement": "HOLD", "reason": "E3 깃발 명령 15% 실현 원자료 없음"}
        items = {
            "maintenance_current": {"role": "judge", "judgement": now["judgement"]},
            "maintenance_previous": {"role": "judge", "judgement": old["judgement"] if old else "HOLD"},
            "kind_current": {"role": "judge", "judgement": kind_states[0]},
            "kind_previous": {"role": "judge", "judgement": kind_states[1]},
            "kind_coverage": {"role": "judge", "judgement": aggregate(kind_states)},
            "learned_cells": learned, "exchange_watch": exchange, "flag_share": flag_share,
        }
        verdict = aggregate(row["judgement"] for row in items.values())
        now.update(judgement=verdict, stage_exit={"adapter": self.name, "judgement": verdict,
                                                 "windows": 2, "items": items})
        return now

    def verify(self, score, judgment, expected, plan=None):
        from foothold_s2.ex42_stage_judges import _map39_cell_check
        if plan is None or score.get("stage_id") != "E3":
            raise ValueError("EX-42 E3 P1 plan or stage identity absent")
        exit_row = score.get("stage_exit") or {}
        items = exit_row.get("items") or {}
        required = {"maintenance_current", "maintenance_previous", "kind_current", "kind_previous",
                    "kind_coverage", "learned_cells", "exchange_watch", "flag_share"}
        if (exit_row.get("adapter") != self.name or exit_row.get("windows") != 2 or
                set(items) != required or exit_row.get("judgement") != judgment or
                _map39_cell_check(score, judgment, MODES) != expected or
                items["maintenance_current"].get("judgement") != expected or
                aggregate(row.get("judgement") for row in items.values()) != judgment):
            raise ValueError("EX-42 E3 P1 aggregate differs")
        current = score.get("e3_kind") or {}
        folder = Path(current.get("evaluation", ""))
        if folder.name != "kind_cells_e3" or not folder.parent.is_dir():
            raise ValueError("EX-42 E3 P1 raw folder absent")
        mesh = _mesh(score, folder.parent)
        recounted = recount(score, plan=plan, evaluation=folder.parent, mesh=mesh)
        if ({key: value for key, value in current.items() if key != "previous"} != recounted or
                items["kind_current"].get("judgement") != recounted["judgement"]):
            raise ValueError("EX-42 E3 P1 current kind differs from raw")
        from foothold_s2.ex42_e1_judge import previous_e1_score
        prior_score = previous_e1_score(Path(score["checkpoint"]), folder.parent,
                                       plan["evaluation"]["interval_updates"],
                                       score["score_config_sha256"], stage_id="E3")
        if prior_score is None:
            if current.get("previous") is not None or items["kind_previous"].get("judgement") != "HOLD":
                raise ValueError("EX-42 E3 P1 missing prior window was forged")
        else:
            prior_folder = Path(prior_score["e3_kind"]["evaluation"])
            prior_mesh = _mesh(prior_score, prior_folder.parent)
            if prior_mesh["mesh_sha256"] != mesh["mesh_sha256"]:
                raise ValueError("EX-42 E3 P1 prior mesh differs")
            prior_recount = recount(prior_score, plan=plan, evaluation=prior_folder.parent, mesh=prior_mesh)
            if (current.get("previous") != prior_recount or
                    items["kind_previous"].get("judgement") != prior_recount["judgement"]):
                raise ValueError("EX-42 E3 P1 prior kind differs from raw")
        if (judgment == "PASS" and items["flag_share"]["judgement"] != "PASS"):
            raise ValueError("EX-42 E3 P1 flag exposure absent")
        if judgment == "PASS" and (recounted["judgement"] != "PASS" or
                                    any(items[key]["judgement"] != "PASS" for key in required)):
            raise ValueError("EX-42 E3 P1 raw or training evidence cannot prove PASS")
        return {"stage_exit": exit_row}


register(E3KindTwoWindowJudge())
