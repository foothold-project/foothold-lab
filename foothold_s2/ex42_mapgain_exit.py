"""E2 v1 stage exit by MAP GAIN over two consecutive boundaries (proposal: sonnet-code-lx 11/20, lead 18:08 (B), planner CHECK-E2V1-GOAL-1120 (2)).

The old E2 exit (`kind_two_window_e2`, ex42_kind_stage_judge) is a window pass: success and survival counts of every open kind in two windows. The team lead's goal for
E2 v1 is "graduation is the map gain, two windows". This adapter, `mapgain_two_boundary_e2`, keeps the parts of the old exit that are not about the kinds (the maintenance
table in two windows and the learned_cells training evidence, same code and same thresholds) and replaces the kind items by the map-gain verdicts the boundary judge
(`tools/ex42_v1_mapgain_boundary.py`) writes to `eval/scores/m<iter>/mapgain_outcomes.json` + `mapgain_meta.json`:

* the judged kinds are the stage's single-kind rules whose share is above the hold floor 0.03 (a kind a re-entry already holds at 0.03 is graduated and left to the
  maintenance table), the same rule as `ex42_kind_stage_judge.required_kinds`;
* a kind passes a boundary when its verdict there is `graduate` or `ceiling` AT THE END LEVEL (`kind_level_cap.end`, 5). Below the end level the verdict is a cap raise, not
  a graduation (HOLD). `not_yet` at the end level is FAIL; `undecidable`, `incomplete` or a missing file is HOLD;
* the stage passes when every judged kind passes two CONSECUTIVE boundaries (this one and the one `interval` iterations earlier) and the maintenance and
  learned_cells items pass;
* the outcomes are bound to the checkpoint: `mapgain_meta.json` carries the sha256 of the evaluated model file and a mismatch is an error, not a HOLD.
Dropped on purpose: the kind-cell exchange watch (it compares the old forward cells that no longer judge a kind); the boundary judge's own harm test (right map alive not more
than 10 below map-off) covers what it guarded for the kinds. Nothing here starts training. The plan does not name this adapter: a new OUT does, through
`ex42_e2_reentry_draft --exit-judge mapgain_two_boundary_e2`.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import yaml

from foothold_s2.ex42_stage_judges import StageJudge, aggregate, previous_window, register

NAME = "mapgain_two_boundary_e2"
STAGE = "E2"
GRADUATED_VERDICTS = ("graduate", "ceiling")
HOLD_FLOOR = 0.03


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def judged_kinds(plan: dict) -> list[str]:
    """Single-kind rules of the stage start block above the 0.03 hold floor, `family/kind`, in plan order."""
    row = next(r for r in plan["stages"] if r["id"] == STAGE)
    rules = row["terrain"][f"exposure_at_{STAGE}"]["positive"]
    return [f"{r['family']}/{r['kind']}" for r in rules if "kind" in r and r.get("share", 0) > HOLD_FLOOR + 1e-9]


def end_level(plan: dict) -> int:
    row = next(r for r in plan["stages"] if r["id"] == STAGE)
    end = (row["terrain"].get("kind_level_cap") or {}).get("end")
    if type(end) is not int or end < 1:
        raise ValueError("EX-42 map-gain exit needs the row's kind_level_cap end level")
    return end


def read_outcomes(scores_dir: Path, checkpoint: Path) -> dict | None:
    """{family/kind: verdict row} of one boundary, None when the boundary left no outcome file. A meta file that is missing or names another
    checkpoint is an error (outcomes that cannot be tied to the model file are not evidence)."""
    scores_dir = Path(scores_dir)
    outcomes, meta = scores_dir / "mapgain_outcomes.json", scores_dir / "mapgain_meta.json"
    if not outcomes.is_file():
        return None
    if not meta.is_file():
        raise ValueError(f"EX-42 map-gain outcomes {outcomes} have no mapgain_meta.json (re-run the boundary judge with --checkpoint)")
    record = json.loads(meta.read_text(encoding="utf-8-sig"))
    if record.get("format") != "foothold-ex42-mapgain-meta/1" or record.get("checkpoint_sha256") != _sha(checkpoint):
        raise ValueError(f"EX-42 map-gain outcomes {outcomes} belong to another checkpoint than {Path(checkpoint).name}")
    return json.loads(outcomes.read_text(encoding="utf-8-sig"))


def kind_state(row: dict | None, end: int) -> dict:
    """One kind at one boundary: PASS graduate/ceiling at the end level, FAIL not_yet at the end level, else HOLD with the reason."""
    if row is None:
        return {"role": "judge", "judgement": "HOLD", "reason": "이 경계에 이 종의 지도 이득 판정이 없음"}
    base = {"role": "judge", "verdict": row.get("verdict"), "level": row.get("level")}
    if row.get("level") != end:
        return {**base, "judgement": "HOLD", "reason": f"끝 수준 {end} 이 아님 (상한 올림 단계)"}
    if row.get("verdict") in GRADUATED_VERDICTS:
        return {**base, "judgement": "PASS"}
    if row.get("verdict") == "not_yet":
        return {**base, "judgement": "FAIL"}
    return {**base, "judgement": "HOLD", "reason": f"판정 불가 ({row.get('verdict')})"}


def kind_items(kinds: list[str], now: dict | None, previous: dict | None, end: int) -> dict:
    items = {}
    for kind in kinds:
        items[f"{kind}/L{end}/mapgain_current"] = kind_state((now or {}).get(kind), end)
        items[f"{kind}/L{end}/mapgain_previous"] = kind_state((previous or {}).get(kind), end)
    return items


def previous_dir(evaluation: Path, checkpoint: Path, interval: int) -> tuple[Path, Path] | None:
    """(scores folder, model file) of the boundary one interval earlier, None for the first window."""
    iteration = int(re.fullmatch(r"model_(\d+)\.pt", Path(checkpoint).name).group(1))
    if iteration <= interval:
        return None
    old = Path(checkpoint).with_name(f"model_{iteration - interval}.pt")
    return Path(evaluation).parent / f"m{iteration - interval}", old


def read_pair(evaluation: Path, checkpoint: Path, interval: int) -> tuple[dict | None, dict | None]:
    now = read_outcomes(evaluation, checkpoint)
    before = previous_dir(evaluation, checkpoint, interval)
    old = read_outcomes(before[0], before[1]) if before and before[1].is_file() else None
    return now, old


class MapGainTwoBoundaryJudge(StageJudge):
    name = NAME

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import judge as judge_maintenance, load_baseline
        from foothold_s2.ex42_kind_stage_judge import exit_gate_mismatch, gate_checked
        from foothold_s2.ex42_learned_cells_evidence import judge_two_boundaries

        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        current = judge_maintenance(score, baseline, measured)
        prior_score = previous_window(ctx)
        prior = judge_maintenance(prior_score, baseline, measured) if prior_score else None
        interval = ctx.plan["evaluation"]["interval_updates"]
        kinds, end = judged_kinds(ctx.plan), end_level(ctx.plan)
        now, old = read_pair(ctx.evaluation, ctx.checkpoint, interval)
        items = kind_items(kinds, now, old, end)
        approvals = yaml.safe_load((ctx.plan_path.parent / ctx.plan["approval_file"]).read_text(encoding="utf-8-sig"))
        authorization = approvals[f"stage_{STAGE.lower()}_authorization"]
        if authorization.get("approved") is not True:
            raise ValueError("EX-42 map-gain exit learned_cells threshold authorization absent")
        learned = judge_two_boundaries(
            ctx.checkpoint, stage_id=STAGE, plan=ctx.plan, plan_sha256=current.get("execution_plan_sha256", ""), interval=interval,
            min_episodes=authorization["exit_gate"]["learned_cells_min"], previous_kind_pass=False,
            named_kinds={tuple(k.split("/", 1)): items[f"{k}/L{end}/mapgain_previous"]["judgement"] == "PASS" for k in kinds})
        learned = gate_checked(learned, exit_gate_mismatch(ctx.plan, authorization["exit_gate"]))
        all_items = {"maintenance_current": {"role": "judge", "judgement": current["judgement"]},
                     "maintenance_previous": {"role": "judge", "judgement": prior["judgement"] if prior else "HOLD"},
                     "learned_cells": learned, **items}
        verdict = aggregate(item["judgement"] for item in all_items.values() if item["role"] == "judge")
        current.update(stage_id=STAGE, judgement=verdict,
                       mapgain_exit={"evaluation": str(ctx.evaluation), "judged_kinds": kinds, "end_level": end, "now": now, "previous": old},
                       stage_exit={"adapter": self.name, "judgement": verdict, "windows": 2, "items": all_items})
        return current

    def verify(self, score, judgment, expected, plan=None):
        from foothold_s2.ex42_stage_judges import _map39_cell_check
        if plan is None or score.get("stage_id") != STAGE:
            raise ValueError("EX-42 map-gain P1 plan or stage identity missing")
        exit_row, body = score.get("stage_exit") or {}, score.get("mapgain_exit") or {}
        items = exit_row.get("items") or {}
        kinds, end = judged_kinds(plan), end_level(plan)
        if body.get("judged_kinds") != kinds or body.get("end_level") != end:
            raise ValueError("EX-42 map-gain P1 judged kinds differ from the plan")
        now, old = read_pair(Path(body.get("evaluation", "")), Path(score["checkpoint"]), plan["evaluation"]["interval_updates"])
        if body.get("now") != now or body.get("previous") != old:
            raise ValueError("EX-42 map-gain P1 outcomes differ from the files")
        names = {"maintenance_current", "maintenance_previous", "learned_cells", *kind_items(kinds, now, old, end)}
        if (exit_row.get("adapter") != self.name or exit_row.get("windows") != 2 or exit_row.get("judgement") != judgment or set(items) != names or
                any(item.get("judgement") not in ("PASS", "HOLD", "FAIL") or item.get("role") != "judge" for item in items.values()) or
                _map39_cell_check(score, judgment, ("eval_gt", "eval_pred", "probe_prop_only")) != expected or
                items.get("maintenance_current", {}).get("judgement") != expected or
                aggregate(item.get("judgement") for item in items.values()) != judgment):
            raise ValueError("EX-42 map-gain P1 aggregate stage exit differs")
        if any(items[k] != v for k, v in kind_items(kinds, now, old, end).items()):
            raise ValueError("EX-42 map-gain P1 kind items differ from the recount")
        if judgment == "PASS" and items["learned_cells"].get("judgement") != "PASS":
            raise ValueError("EX-42 map-gain training evidence absent")
        return {"stage_exit": exit_row}


register(MapGainTwoBoundaryJudge())
