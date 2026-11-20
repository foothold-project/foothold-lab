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
* the level a verdict was measured at must be the level the TRAINING had open for that kind: the latest `exposure_receipt_start_<n>_rank0.json` with n below the
  boundary (the same receipt the chain reads to build --caps) gives `opened_kinds`; a verdict whose level differs (a hand-typed --caps) is an error, and a boundary
  without that receipt is HOLD. Each verdict also records the geometry sha256 of the mesh it was measured on, which must be a mesh of the plan's training profiles or
  the registered beam evaluation mesh (EVAL_MESHES); anything else is an error;
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
# Kinds of the E2 start block that are the THIRD learning order (lead-lx 11/20 18:3x, look-at (a) answer): the boundary eval does not measure them yet, so until a boundary
# carries a verdict row for one of them it is recorded as "undecidable, not learned yet" (role record_only) and does not block the stage. From the boundary on whose eval
# measures it (a row in the current or the previous boundary) it is judged like any other kind, and a row missing at the other boundary is then a HOLD.
NOT_LEARNED_YET = ("B/gap", "C/gap", "B/beam")
# Evaluation meshes that are not a training profile of the plan: the v1 boundary eval measures gap and beam kinds on the beam mesh (ex42_v1_boundary_eval.sh V1_MESH).
EVAL_MESHES = {"7deb20ce792dfc408e9c1ba032448e684f233f58f3e517659606094d3063abba": "sonnet_beam_mesh_1119/b2m_rpy_lv"}


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


def training_caps(checkpoint: Path) -> dict[str, int] | None:
    """`family/kind` -> the level cap the training had open in the segment that ended at this checkpoint: `opened_kinds` of the latest
    `exposure_receipt_start_<n>_rank0.json` next to the model file with n below the checkpoint's iteration. None when there is none."""
    checkpoint = Path(checkpoint)
    iteration = int(re.fullmatch(r"model_(\d+)\.pt", checkpoint.name).group(1))
    best = None
    for path in checkpoint.parent.glob("exposure_receipt_start_*_rank0.json"):
        n = int(re.fullmatch(r"exposure_receipt_start_(\d+)_rank0\.json", path.name).group(1))
        if n < iteration and (best is None or n > best[0]):
            best = (n, path)
    return dict(json.loads(best[1].read_text(encoding="utf-8-sig"))["opened_kinds"]) if best else None


def allowed_meshes(plan: dict) -> set[str]:
    return {p["geometry_sha256"] for p in plan["training_mesh_profiles"].values()} | set(EVAL_MESHES)


def check_rows(kinds: list[str], rows: dict | None, caps: dict | None, meshes: set[str], where: str) -> None:
    """Raise when a verdict was not measured at the level the training had open or on a mesh the plan does not know (not a HOLD: the file lies)."""
    for kind in kinds:
        row = (rows or {}).get(kind)
        if row is None or caps is None:
            continue
        if kind in caps and row.get("level") != caps[kind]:
            raise ValueError(f"EX-42 map-gain {where} {kind} was measured at L{row.get('level')} but the training receipt had it open at L{caps[kind]}")
        if row.get("mesh_sha256") not in meshes:
            raise ValueError(f"EX-42 map-gain {where} {kind} mesh {str(row.get('mesh_sha256'))[:12]} is not a mesh of the plan or the registered evaluation mesh")


def kind_state(row: dict | None, end: int, caps_known: bool = True) -> dict:
    """One kind at one boundary: PASS graduate/ceiling at the end level, FAIL not_yet at the end level, else HOLD with the reason."""
    if row is None:
        return {"role": "judge", "judgement": "HOLD", "reason": "이 경계에 이 종의 지도 이득 판정이 없음"}
    if not caps_known:
        return {"role": "judge", "judgement": "HOLD", "reason": "이 경계의 학습 영수증 (exposure_receipt_start) 이 없어 수준을 대조 못 함"}
    base = {"role": "judge", "verdict": row.get("verdict"), "level": row.get("level")}
    if row.get("level") != end:
        return {**base, "judgement": "HOLD", "reason": f"끝 수준 {end} 이 아님 (상한 올림 단계)"}
    if row.get("verdict") in GRADUATED_VERDICTS:
        return {**base, "judgement": "PASS"}
    if row.get("verdict") == "not_yet":
        return {**base, "judgement": "FAIL"}
    return {**base, "judgement": "HOLD", "reason": f"판정 불가 ({row.get('verdict')})"}


def kind_items(kinds: list[str], now: dict | None, previous: dict | None, end: int, *, caps_now: dict | None = None, caps_previous: dict | None = None,
               meshes: set[str] | None = None) -> dict:
    """The per-kind exit items. caps_*: training receipts of the two boundaries (None = no receipt: HOLD); meshes: the allowed mesh shas (None = not checked)."""
    if meshes is not None:
        check_rows(kinds, now, caps_now, meshes, "current boundary")
        check_rows(kinds, previous, caps_previous, meshes, "previous boundary")
    items = {}
    for kind in kinds:
        if kind in NOT_LEARNED_YET and (now or {}).get(kind) is None and (previous or {}).get(kind) is None:
            skipped = {"role": "record_only", "judgement": "HOLD", "reason": "판정 불가 (아직 안 배움: 셋째 순서, 경계 평가에 아직 없음)"}
            items[f"{kind}/L{end}/mapgain_current"] = items[f"{kind}/L{end}/mapgain_previous"] = skipped
            continue
        items[f"{kind}/L{end}/mapgain_current"] = kind_state((now or {}).get(kind), end, caps_now is not None or meshes is None)
        items[f"{kind}/L{end}/mapgain_previous"] = kind_state((previous or {}).get(kind), end, caps_previous is not None or meshes is None)
    return items


def exit_items(plan: dict, evaluation: Path, checkpoint: Path):
    """(kinds, end level, now rows, previous rows, items): everything the judge and its P1 recount derive from the files."""
    interval = plan["evaluation"]["interval_updates"]
    kinds, end = judged_kinds(plan), end_level(plan)
    now, old = read_pair(evaluation, checkpoint, interval)
    before = previous_dir(evaluation, checkpoint, interval)
    caps_now = training_caps(checkpoint)
    caps_old = training_caps(before[1]) if before else None
    return kinds, end, now, old, kind_items(kinds, now, old, end, caps_now=caps_now, caps_previous=caps_old, meshes=allowed_meshes(plan))


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
        kinds, end, now, old, items = exit_items(ctx.plan, ctx.evaluation, ctx.checkpoint)
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
        kinds, end, now, old, recount = exit_items(plan, Path(body.get("evaluation", "")), Path(score["checkpoint"]))
        if body.get("judged_kinds") != kinds or body.get("end_level") != end:
            raise ValueError("EX-42 map-gain P1 judged kinds differ from the plan")
        if body.get("now") != now or body.get("previous") != old:
            raise ValueError("EX-42 map-gain P1 outcomes differ from the files")
        names = {"maintenance_current", "maintenance_previous", "learned_cells", *recount}
        if (exit_row.get("adapter") != self.name or exit_row.get("windows") != 2 or exit_row.get("judgement") != judgment or set(items) != names or
                any(item.get("judgement") not in ("PASS", "HOLD", "FAIL") or item.get("role") not in ("judge", "record_only") for item in items.values()) or
                _map39_cell_check(score, judgment, ("eval_gt", "eval_pred", "probe_prop_only")) != expected or
                items.get("maintenance_current", {}).get("judgement") != expected or
                aggregate(item.get("judgement") for item in items.values() if item.get("role") == "judge") != judgment):
            raise ValueError("EX-42 map-gain P1 aggregate stage exit differs")
        if any(items[k] != v for k, v in recount.items()):
            raise ValueError("EX-42 map-gain P1 kind items differ from the recount")
        if judgment == "PASS" and items["learned_cells"].get("judgement") != "PASS":
            raise ValueError("EX-42 map-gain training evidence absent")
        return {"stage_exit": exit_row}


register(MapGainTwoBoundaryJudge())
