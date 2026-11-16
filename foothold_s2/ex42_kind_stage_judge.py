"""E3, E4 and E5 named-kind exit: one two-window judge per stage over the kinds the training receipt says are open.

planner DESIGN-E3E5-EXIT-JUDGE-1116 section 2.1 (lead + planner adopted it under the team lead's delegation). It generalizes
`ex42_e2_judge` from one kind (stepping_stones_low, level 0) to the stage's kind list, nothing else:

* the judged kinds are the stage's named kinds (the start block's `kind` rules and `terrain.k_ladder.order`, never the
  continuous ones: the maintenance table judges those);
* a kind is judged at the level cap it is open at in the boundary's exposure receipt (`opened_kinds`), not the plan's start block;
* graduation = every named kind of the stage is open (the ladder is done), every open kind passes both windows in
  `eval_gt` and `eval_pred` at its cap, the maintenance table passes both windows, learned_cells and the exchange
  watch pass (the same E2 gates). Any kind without a previous window is HOLD; `probe_prop_only` is recorded only.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import yaml

from foothold_s2.eval.ex42_kind_completion import read_start_kind_cell
from foothold_s2.ex42_stage_judges import StageJudge, aggregate, previous_window, register

MODES = ("eval_gt", "eval_pred", "probe_prop_only")
STAGES = ("E3", "E4", "E5")
RULES = ("travel", "center_max")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def kind_dir(kind: str) -> str:
    """`B/stair_up` -> `B__stair_up` (one folder per kind under `kind_cells`)."""
    return kind.replace("/", "__")


def _spec(plan: dict) -> dict:
    spec = plan["evaluation"]["kind_stage_cells"]
    promotion = plan["evaluation"]["promotion"]
    completion = spec.get("completion")
    if (spec.get("forward_command") != "fwd1.0" or spec.get("judge_modes") != ["eval_gt", "eval_pred"] or
            spec.get("record_modes") != ["probe_prop_only"] or
            type(spec.get("envs_per_kind")) is not int or not 0 < spec["envs_per_kind"] <= 64 or
            type(spec.get("valid_min_each")) is not int or not 0 < spec["valid_min_each"] <= spec["envs_per_kind"] or
            not isinstance(completion, dict) or completion.get("A", {}).get("rule") != "start_finish_platform" or
            promotion.get("window_episodes") != 64 or promotion.get("windows") != 2):
        raise ValueError("EX-42 named-kind stage exit contract differs")
    for key, rule in completion.items():
        if key == "A":
            continue
        if (not re.fullmatch(r"[BCE]/\w+", key) or rule.get("rule") not in RULES or
                type(rule.get("m")) not in (int, float) or not 0 < rule["m"] <= 12):
            raise ValueError("EX-42 named-kind stage completion rule invalid")
    return spec


def required_kinds(plan: dict, stage_id: str) -> list[str]:
    """The stage's named kinds, `family/kind`: start-block rules that name one kind, then the ladder order."""
    row = next(r for r in plan["stages"] if r["id"] == stage_id)
    terrain = row["terrain"]
    names = [f"{rule['family']}/{rule['kind']}" for rule in terrain[f"exposure_at_{stage_id}"]["positive"] if "kind" in rule]
    names += [f"{entry['family']}/{entry['kind']}" for entry in (terrain.get("k_ladder") or {}).get("order", [])]
    if len(set(names)) != len(names):
        raise ValueError("EX-42 stage kind list repeats a kind")
    return names


def opened_kinds(checkpoint: Path, *, stage_id: str, plan_sha256: str, plan: dict) -> dict[str, int]:
    """`family/kind` -> level cap, from the exposure receipt the training wrote at this checkpoint's boundary (every rank
    folded). The ladder is replayed from the plan and the receipt's recorded outcomes, so a forged receipt cannot open a kind."""
    from types import SimpleNamespace
    from foothold_s2.ex42_exposure_receipt import read_boundary_receipt, recompute_from_plan
    body = read_boundary_receipt(checkpoint, stage_id=stage_id, plan_sha256=plan_sha256)
    recompute_from_plan(body, SimpleNamespace(document=plan))
    return dict(body["opened_kinds"])


def score_kind(cell: dict, *, valid_min_each: int, success_min: int, survival_min: int, envs: int) -> dict:
    """One named kind, one mode. Thresholds are the promotion counts (per 64 episodes) scaled to the cell's valid envs."""
    if (type(cell.get("valid_count")) is not int or not 0 <= cell["valid_count"] <= envs or
            any(type(cell.get(key)) is not int or not 0 <= cell[key] <= cell["valid_count"]
                for key in ("success_count", "survival_count")) or
            type(valid_min_each) is not int or not 0 < valid_min_each <= envs or
            type(success_min) is not int or type(survival_min) is not int or not 0 <= success_min <= survival_min <= 64):
        raise ValueError("EX-42 named-kind counts or thresholds invalid")
    valid = cell["valid_count"]
    success_floor = math.ceil(success_min * valid / 64)
    survival_floor = math.ceil(survival_min * valid / 64)
    state = ("HOLD" if valid < valid_min_each
             else "PASS" if cell["success_count"] >= success_floor and cell["survival_count"] >= survival_floor else "FAIL")
    return {"judgement": state, "valid_count": valid, "success_count": cell["success_count"],
            "survival_count": cell["survival_count"], "success_min": success_floor,
            "survival_min": survival_floor, "cell": cell}


def finish_anchor(mesh: dict, *, family: str, kind: str, level: int, completion: dict) -> dict | None:
    """None = family A's measured finish platform (the E2 rule). Other kinds: the plan's registered straight-line travel
    (their reset yaw is random or the finish platform is not measurable, so there is no map-forward arrival line).
    A kind with no registered rule raises KeyError: the caller records HOLD, never a pass."""
    if family == "A":
        return None
    rule = completion[f"{family}/{kind}"]
    if rule["rule"] == "center_max":
        return {"center_max_m": float(rule["m"]), "kind": kind, "level": level, "family": family,
                "method": f"center_max_{rule['m']}m_from_the_cell_origin"}
    return {"travel_m": float(rule["m"]), "kind": kind, "level": level, "family": family,
            "method": f"travel_{rule['m']}m_from_the_first_sample"}


def read_kind_modes(folder: Path, kinds: dict[str, int], *, plan: dict, mesh: dict,
                    checkpoint_sha256: str, seed: int) -> dict:
    """{kind: {mode: scored cell}} recounted from the raw Kit files, `folder/<kind_dir>/` per kind."""
    spec = _spec(plan)
    promotion = plan["evaluation"]["promotion"]
    out = {}
    marker = Path(folder) / "child_failures.json"
    failures = {}
    if marker.is_file():
        record = json.loads(marker.read_text(encoding="utf-8-sig"))
        if (record.get("format") != "foothold-ex42-kind-stage-child-failures/1" or
                record.get("checkpoint_sha256") != checkpoint_sha256 or not isinstance(record.get("failures"), dict)):
            raise ValueError("EX-42 named-kind child failure marker identity invalid")
        failures = record["failures"]
    for kind, level in sorted(kinds.items()):
        family, name = kind.split("/", 1)
        out[kind] = {"level": level}
        if kind in failures:
            for mode in MODES:
                out[kind][mode] = {"judgement": "HOLD", "reason": f"종 평가 자식 실패: {failures[kind]}",
                                   "role": "record_only" if mode == "probe_prop_only" else "judge",
                                   "child_failure": {"path": str(marker), "sha256": _sha(marker)}}
            continue
        try:
            anchor = finish_anchor(mesh, family=family, kind=name, level=level, completion=spec["completion"])
        except KeyError:
            for mode in MODES:
                out[kind][mode] = {"judgement": "HOLD", "reason": "이 종의 건넘 기준이 plan 에 없다",
                                   "role": "record_only" if mode == "probe_prop_only" else "judge"}
            continue
        for mode in MODES:
            cell = read_start_kind_cell(Path(folder) / kind_dir(kind), mesh=mesh, checkpoint_sha256=checkpoint_sha256,
                                        seed=seed, family=family, kind=name, level=level, mode=mode,
                                        seconds=spec["forward_seconds"], settle_s=spec["completion_settle_s"],
                                        envs=spec["envs_per_kind"], anchor=anchor)
            scored = score_kind(cell, valid_min_each=spec["valid_min_each"], success_min=promotion["success_min"],
                                survival_min=promotion["survival_min"], envs=spec["envs_per_kind"])
            scored["role"] = "record_only" if mode == "probe_prop_only" else "judge"
            out[kind][mode] = scored
    return out


def checked_previous(prior_score: dict | None, *, evaluation: Path, plan: dict, plan_sha256: str,
                     mesh: dict, seed: int) -> dict | None:
    """Recount the prior window from its raw files; only kinds the prior window judged come back."""
    if prior_score is None or "kind_stage" not in prior_score:
        return None
    recorded = prior_score["kind_stage"]
    expected_folder = Path(evaluation).parent / f"m{Path(prior_score['checkpoint']).stem.removeprefix('model_')}" / "kind_cells"
    if (recorded.get("evaluation") != str(expected_folder) or recorded.get("mesh_sha256") != mesh["mesh_sha256"] or
            prior_score.get("maintenance_source_sha256") != plan_sha256 or
            prior_score.get("conditions", {}).get("eval_seed") != seed):
        raise ValueError("EX-42 previous named-kind window identity differs")
    kinds = {name: row["level"] for name, row in recorded.get("modes", {}).items()}
    recounted = read_kind_modes(expected_folder, kinds, plan=plan, mesh=mesh,
                                checkpoint_sha256=prior_score["checkpoint_sha256"], seed=seed)
    if recorded.get("modes") != recounted:
        raise ValueError("EX-42 previous named-kind window differs from its raw evidence")
    return recounted


def write_ladder_evidence(checkpoint: Path, evaluation: Path, interval: int, outcomes: dict) -> None:
    """`ladder_outcomes.json` (this boundary) and `ladder_outcomes_list.json` (one entry per boundary so far, the file
    `EX42_LADDER_OUTCOMES` takes: entry b - 1 is the evidence the ladder reads at boundary b; a boundary that left none is {})."""
    iteration = int(re.fullmatch(r"model_(\d+)\.pt", Path(checkpoint).name).group(1))
    boundary = iteration // interval
    earlier = []
    for back in range(boundary - 1, 0, -1):          # the nearest earlier boundary that left its list; the gap is padded below
        previous = Path(evaluation).parent / f"m{back * interval}" / "ladder_outcomes_list.json"
        if previous.is_file():
            earlier = json.loads(previous.read_text(encoding="utf-8"))
            break
    entries = (earlier + [{}] * (boundary - 1))[:boundary - 1] + [outcomes]
    Path(evaluation).mkdir(parents=True, exist_ok=True)
    (Path(evaluation) / "ladder_outcomes.json").write_text(json.dumps(outcomes, sort_keys=True), encoding="utf-8")
    (Path(evaluation) / "ladder_outcomes_list.json").write_text(json.dumps(entries, sort_keys=True), encoding="utf-8")


def stage_items(kinds: dict[str, int], now: dict, old: dict | None, ladder: dict) -> dict:
    """The exit items that belong to the kinds (maintenance, learned_cells and the exchange watch are added by the caller)."""
    items = {"kind_ladder": ladder}
    for kind, level in sorted(kinds.items()):
        for mode in ("eval_gt", "eval_pred"):
            items[f"{kind}/L{level}/{mode}_current"] = {"role": "judge", **now[kind][mode]}
            previous = (old or {}).get(kind)
            items[f"{kind}/L{level}/{mode}_previous"] = (
                {"role": "judge", **previous[mode]} if previous and previous.get("level") == level
                else {"role": "judge", "judgement": "HOLD", "reason": "직전 창 없음"})
        items[f"{kind}/L{level}/probe_prop_only_current"] = {"role": "record_only", **now[kind]["probe_prop_only"]}
    return items


def ladder_item(required: list[str], opened: dict[str, int]) -> dict:
    pending = [kind for kind in required if kind not in opened]
    return {"role": "judge", "judgement": "HOLD" if pending else "PASS", "pending": pending,
            "required_count": len(required)}


def ladder_outcomes(kinds: dict[str, int], now: dict, old: dict | None) -> dict:
    """The evidence `ladder_terrain` reads for this boundary: first_window_pass = this window passed in both judged
    modes; target_level_reached = this and the previous window passed at the kind's open level (the plan keeps the cap
    it opened with, so the open level is the target)."""
    def passed(row):
        return row is not None and all(row[mode]["judgement"] == "PASS" for mode in ("eval_gt", "eval_pred"))
    out = {}
    for kind, level in sorted(kinds.items()):
        here = passed(now[kind])
        before = (old or {}).get(kind)
        out[kind] = {"first_window_pass": bool(here),
                     "target_level_reached": bool(here and before and before.get("level") == level and passed(before))}
    return out


class KindStageTwoWindowJudge(StageJudge):
    def __init__(self, stage_id: str):
        if stage_id not in STAGES:
            raise ValueError("EX-42 named-kind stage judge is for E3, E4 and E5")
        self.stage_id = stage_id
        self.name = f"kind_two_window_{stage_id.lower()}"

    def judge(self, ctx, score):
        from foothold_s2.eval.ex42_mesh_eval import preflight
        from foothold_s2.ex42_e0_judge import judge as judge_maintenance, load_baseline
        from foothold_s2.ex42_exchange_watch import compare
        from foothold_s2.ex42_learned_cells_evidence import judge_two_boundaries

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
            raise ValueError("EX-42 named-kind score mesh differs from pinned map64")
        plan_sha = ctx.digest(ctx.plan_path)
        opened = opened_kinds(ctx.checkpoint, stage_id=self.stage_id, plan_sha256=score["execution_plan_sha256"], plan=ctx.plan)
        required = required_kinds(ctx.plan, self.stage_id)
        kinds = {kind: opened[kind] for kind in required if kind in opened}
        now = read_kind_modes(ctx.evaluation / "kind_cells", kinds, plan=ctx.plan, mesh=mesh,
                              checkpoint_sha256=ctx.checkpoint_sha, seed=ctx.seed)
        old = checked_previous(prior_score, evaluation=ctx.evaluation, plan=ctx.plan, plan_sha256=plan_sha,
                               mesh=mesh, seed=ctx.seed)
        current["stage_id"] = self.stage_id
        current["kind_stage"] = {"modes": now, "previous_modes": old, "mesh_sha256": mesh["mesh_sha256"],
                                 "evaluation": str(ctx.evaluation / "kind_cells"), "opened_kinds": opened}
        exchange = compare(current, prior_score, measured=measured, baseline=baseline,
                           kind_now=_by_mode(now), kind_previous=_by_mode(old) if old else None,
                           kind_key="kind_stage", subcells=tuple(sorted(kinds)))
        approvals = yaml.safe_load((ctx.plan_path.parent / ctx.plan["approval_file"]).read_text(encoding="utf-8-sig"))
        authorization = approvals[f"stage_{self.stage_id.lower()}_authorization"]
        if authorization.get("approved") is not True:
            raise ValueError("EX-42 named-kind learned_cells threshold authorization absent")
        learned = judge_two_boundaries(
            ctx.checkpoint, stage_id=self.stage_id, plan=ctx.plan, plan_sha256=current.get("execution_plan_sha256", ""),
            interval=ctx.plan["evaluation"]["interval_updates"], min_episodes=authorization["exit_gate"]["learned_cells_min"],
            previous_kind_pass=False,
            named_kinds={tuple(kind.split("/", 1)): bool(old and kind in old and all(old[kind][m]["judgement"] == "PASS"
                                                                                  for m in ("eval_gt", "eval_pred")))
                         for kind in kinds})
        items = {"maintenance_current": {"role": "judge", "judgement": current["judgement"]},
                 "maintenance_previous": {"role": "judge", "judgement": prior["judgement"] if prior else "HOLD"},
                 "learned_cells": learned, "exchange_watch": exchange,
                 **stage_items(kinds, now, old, ladder_item(required, opened))}
        verdict = aggregate(item["judgement"] for item in items.values() if item["role"] == "judge")
        current.update(stage_id=self.stage_id, judgement=verdict,
                       stage_exit={"adapter": self.name, "judgement": verdict, "windows": 2, "items": items})
        outcomes = ladder_outcomes(kinds, now, old)
        current["ladder_outcomes"] = outcomes
        write_ladder_evidence(ctx.checkpoint, ctx.evaluation, ctx.plan["evaluation"]["interval_updates"], outcomes)
        return current

    def verify(self, score, judgment, expected, plan=None):
        from foothold_s2.ex42_stage_judges import _map39_cell_check
        if plan is None or score.get("stage_id") != self.stage_id:
            raise ValueError("EX-42 named-kind P1 plan or stage identity missing")
        exit_row = score.get("stage_exit") or {}
        items = exit_row.get("items") or {}
        kind = score.get("kind_stage") or {}
        kinds = {name: row["level"] for name, row in (kind.get("modes") or {}).items()}
        required_names = {"maintenance_current", "maintenance_previous", "learned_cells", "exchange_watch", "kind_ladder"}
        for name, level in kinds.items():
            required_names |= {f"{name}/L{level}/{mode}_{window}" for mode in ("eval_gt", "eval_pred") for window in ("current", "previous")}
            required_names.add(f"{name}/L{level}/probe_prop_only_current")
        if (exit_row.get("adapter") != self.name or exit_row.get("windows") != 2 or exit_row.get("judgement") != judgment or
                set(items) != required_names or
                any(item.get("judgement") not in ("PASS", "HOLD", "FAIL") for item in items.values()) or
                any(items[key].get("role") != ("record_only" if key.endswith("probe_prop_only_current") else "judge")
                    for key in required_names) or
                _map39_cell_check(score, judgment, MODES) != expected or
                items.get("maintenance_current", {}).get("judgement") != expected or
                aggregate(item.get("judgement") for item in items.values() if item.get("role") == "judge") != judgment):
            raise ValueError("EX-42 named-kind P1 aggregate stage exit differs")
        if judgment == "PASS" and any(items.get(key, {}).get("judgement") != "PASS"
                                      for key in ("learned_cells", "exchange_watch", "kind_ladder")):
            raise ValueError("EX-42 named-kind training evidence or ladder absent")
        folder = Path(kind.get("evaluation", ""))
        if folder.name != "kind_cells" or not folder.parent.is_dir():
            raise ValueError("EX-42 named-kind evaluation directory missing")
        map_row = json.loads((folder.parent / "map64" / "map_modes.json").read_text(encoding="utf-8-sig"))
        recorded_mesh = map_row.get("ex42_mesh") or {}
        from foothold_s2.eval.ex42_mesh_eval import preflight
        mesh = preflight(Path(recorded_mesh["manifest"]).parent)
        if mesh["mesh_sha256"] != kind.get("mesh_sha256") or mesh["mesh_sha256"] != recorded_mesh.get("mesh_sha256"):
            raise ValueError("EX-42 named-kind P1 mesh identity differs")
        opened = kind.get("opened_kinds") or {}
        required = required_kinds(plan, self.stage_id)
        if kinds != {k: opened[k] for k in required if k in opened} or items["kind_ladder"] != ladder_item(required, opened):
            raise ValueError("EX-42 named-kind P1 opened kinds differ from the exposure receipt")
        receipt_opened = opened_kinds(Path(score["checkpoint"]), stage_id=self.stage_id,
                                      plan_sha256=score["execution_plan_sha256"], plan=plan)
        if receipt_opened != opened:
            raise ValueError("EX-42 named-kind P1 opened kinds differ from the exposure receipt")
        recounted = read_kind_modes(folder, kinds, plan=plan, mesh=mesh, checkpoint_sha256=score["checkpoint_sha256"],
                                    seed=score["conditions"]["eval_seed"])
        if kind.get("modes") != recounted:
            raise ValueError("EX-42 named-kind P1 kind score differs from raw")
        from foothold_s2.ex42_e1_judge import previous_e1_score
        previous = previous_e1_score(Path(score["checkpoint"]), folder.parent, plan["evaluation"]["interval_updates"],
                                     score["score_config_sha256"], stage_id=self.stage_id)
        old = checked_previous(previous, evaluation=folder.parent, plan=plan, plan_sha256=score["maintenance_source_sha256"],
                               mesh=mesh, seed=score["conditions"]["eval_seed"])
        if kind.get("previous_modes") != old or (judgment == "PASS" and old is None):
            raise ValueError("EX-42 named-kind P1 previous window differs from raw")
        if items != {**items, **stage_items(kinds, recounted, old, items["kind_ladder"])}:
            raise ValueError("EX-42 named-kind P1 kind items differ from the recount")
        return {"stage_exit": exit_row}


def _by_mode(bundle: dict) -> dict:
    """{kind: {mode: row}} -> {mode: {kind: row}} (the exchange watch compares by mode, then by sub-cell)."""
    return {mode: {kind: row[mode] for kind, row in bundle.items()} for mode in MODES}


for _stage in STAGES:
    register(KindStageTwoWindowJudge(_stage))
