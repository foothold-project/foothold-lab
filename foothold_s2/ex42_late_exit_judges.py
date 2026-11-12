"""E6a / E6b / M exit judges and the M return decision (CPU only, fail closed).

CURRICULUM-GATES v0.17c E.1 rows (read when this was written):
  E6a  every boundary: height tracking error <= 0.02 m (boundaries 1, 2) or roll <= 0.05 rad (boundary 3), two windows + maintenance
  E6b  the three D kinds at their representative level, two windows + maintenance
  M    off-map survival >= eval_gt survival - 6/64 at the fixed levels L3 / L6 / L9, two windows (M returns to the source stage)

The measured evidence (posture cells, map-off fixed-level cells, the E6b kind bundle) has no producer in this tree yet. A judge
therefore reads a raw evidence file with a stated format, recomputes the verdict from its numbers (the file's own verdict is
never trusted) and answers HOLD when the file or the common kind consumer is absent. Nothing here invents a measurement.
"""
from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

from foothold_s2.ex42_stage_judges import StageJudge, aggregate, previous_window, register

POSTURE_LIMITS = {"posture_height": 0.02, "posture_roll": 0.05}                 # m, rad (CG E6a, assumption)
POSTURE_FORMAT = "foothold-ex42-posture-cells/1"
MAPOFF_FORMAT = "foothold-ex42-mapoff-cells/1"
MAPOFF_LEVELS = ("L3", "L6", "L9")
MAPOFF_GAP_ENVS = 6                                                              # of 64 (D60 shape, assumption)
M_MAX_UPDATES = 1000                                                             # 500 + 500 extension (CG E.1 M row)
E6A_AXES = ("posture_height", "posture_height", "posture_roll")
SHA = re.compile(r"[0-9a-f]{64}")


def hold(reason):
    return {"role": "judge", "judgement": "HOLD", "reason": reason}


def _read(folder: Path, name: str, fmt: str, ctx_sha: str) -> dict | None:
    path = Path(folder) / name
    if not path.is_file():
        return None
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    if row.get("format") != fmt or row.get("checkpoint_sha256") != ctx_sha:
        raise ValueError(f"{name} format or checkpoint identity differs")
    return row


def _number(value):
    if type(value) not in (int, float) or value != value or value in (float("inf"), float("-inf")):
        raise ValueError("evidence number is not finite")
    return float(value)


def posture_window(row: dict | None, boundary_index: int) -> dict:
    """E6a one boundary: the tracking error median of the axis this boundary opened, against its fixed limit."""
    if row is None:
        return hold("posture_cells 없음")
    axis = E6A_AXES[boundary_index]
    if row.get("boundary_index") != boundary_index or row.get("axis") != axis:
        raise ValueError("posture evidence boundary or axis differs from the fixed E6a order")
    error, limit = _number(row["tracking_error_median"]), POSTURE_LIMITS[axis]
    return {"role": "judge", "judgement": "PASS" if error <= limit else "FAIL", "axis": axis,
            "boundary_index": boundary_index,
            "tracking_error_median": error, "limit": limit}


def mapoff_window(row: dict | None) -> dict:
    """M: off survival >= gt survival - 6 envs at L3, L6 and L9 (all three, nothing skipped)."""
    if row is None:
        return hold("map_off fixed-level cells 없음")
    levels = row.get("levels") or {}
    if set(levels) != set(MAPOFF_LEVELS) or row.get("envs") != 64:
        raise ValueError("map-off evidence levels or env count differ")
    gaps = {}
    for name in MAPOFF_LEVELS:
        gt, off = levels[name]["eval_gt_alive"], levels[name]["map_off_alive"]
        if type(gt) is not int or type(off) is not int or not (0 <= gt <= 64 and 0 <= off <= 64):
            raise ValueError("map-off survival counts invalid")
        gaps[name] = gt - off
    return {"role": "judge", "judgement": "PASS" if all(g <= MAPOFF_GAP_ENVS for g in gaps.values()) else "FAIL",
            "gap_envs": gaps, "limit_envs": MAPOFF_GAP_ENVS}


def _prior_folder(ctx):
    match = re.fullmatch(r"model_(\d+)\.pt", Path(ctx.checkpoint).name)
    previous = int(match.group(1)) - ctx.plan["evaluation"]["interval_updates"]
    return None if previous <= 0 else Path(ctx.evaluation).parent / f"m{previous}"


class _LateJudge(StageJudge):
    stage_id = ""

    def window_item(self, folder, ctx, score):              # one window of the stage's own evidence
        raise NotImplementedError

    def extra_items(self, ctx, score, now, old):            # evidence beyond maintenance + the two windows
        return {}

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import judge as maintenance, load_baseline
        if ctx.stage_id != self.stage_id:
            raise ValueError("late stage adapter and context identity differ")
        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        current = maintenance(score, baseline, measured)
        prior_score = previous_window(ctx)
        prior = maintenance(prior_score, baseline, measured) if prior_score else None
        try:
            now = self.window_item(Path(ctx.evaluation), ctx, score)
            folder = _prior_folder(ctx)
            old = (self.window_item(folder, ctx, prior_score)
                   if prior_score and folder is not None else hold("직전 창 없음"))
            extra = self.extra_items(ctx, score, now, old)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            now = old = hold(f"{type(exc).__name__}: {exc}")
            extra = {}
        items = {"maintenance_current": {"role": "judge", "judgement": current["judgement"]},
                 "maintenance_previous": {"role": "judge", "judgement": prior["judgement"] if prior else "HOLD"},
                 f"{self.item}_current": now, f"{self.item}_previous": old, **extra}
        verdict = aggregate(row["judgement"] for row in items.values())
        current.update(stage_id=self.stage_id, judgement=verdict, evaluation=str(ctx.evaluation),
                       stage_exit={"adapter": self.name, "judgement": verdict, "windows": 2, "items": items})
        return current

    def verify(self, score, judgment, expected, plan=None):
        from types import SimpleNamespace
        from foothold_s2.ex42_score import ROOT, config, digest
        if plan is None or score.get("stage_id") != self.stage_id:
            raise ValueError(f"EX-42 {self.stage_id} P1 plan or stage identity absent")
        exit_row = score.get("stage_exit") or {}
        items = exit_row.get("items") or {}
        if (exit_row.get("adapter") != self.name or exit_row.get("windows") != 2 or
                exit_row.get("judgement") != judgment or
                aggregate(row.get("judgement") for row in items.values()) != judgment or
                items.get("maintenance_current", {}).get("judgement") != expected):
            raise ValueError(f"EX-42 {self.stage_id} P1 aggregate differs")
        cfg, cfg_path = config()
        receipt = json.loads((Path(score["evaluation"]) / "eval_receipt.json").read_text(encoding="utf-8-sig"))
        source = receipt.get("evaluation_plan") or {}
        policy_path = Path(source.get("path", ""))
        if (digest(cfg_path) != score.get("score_config_sha256") or not policy_path.is_file() or
                digest(policy_path) != source.get("sha256")):
            raise ValueError(f"EX-42 {self.stage_id} P1 evaluation policy or score config differs")
        ctx = SimpleNamespace(root=ROOT, cfg=cfg, cfg_path=cfg_path, digest=digest, plan=plan, stage_id=self.stage_id,
                              plan_path=policy_path, checkpoint=Path(score["checkpoint"]),
                              evaluation=Path(score["evaluation"]), checkpoint_sha=score["checkpoint_sha256"],
                              seed=score["conditions"]["eval_seed"])
        replay = self.judge(ctx, dict(score))
        if replay["stage_exit"] != exit_row or replay["judgement"] != judgment:
            raise ValueError(f"EX-42 {self.stage_id} P1 exit differs from raw evidence replay")
        return {"stage_exit": exit_row}


class E6aPostureTwoWindowJudge(_LateJudge):
    name, stage_id, item = "posture_two_window_e6a", "E6a", "posture"

    def window_item(self, folder, ctx, score):
        row = _read(Path(folder) / "posture_cells", "posture_cells.json", POSTURE_FORMAT,
                    (score or {}).get("checkpoint_sha256", ctx.checkpoint_sha))
        index = None if row is None else row.get("boundary_index")
        return posture_window(row, index if type(index) is int and 0 <= index < len(E6A_AXES) else 0)

    def extra_items(self, ctx, score, now, old):
        """Both windows must measure the same boundary (same number, hence same axis); two axes never make one exit."""
        same = (now.get("boundary_index") is not None and now.get("boundary_index") == old.get("boundary_index")
                and now.get("axis") == old.get("axis"))
        return {"same_boundary": {"role": "judge", "judgement": "PASS" if same else "HOLD",
                                  **({} if same else {"reason": "두 창의 경계 번호 또는 축이 다름"})}}


class MapOffTwoWindowJudge(_LateJudge):
    name, stage_id, item = "mapoff_two_window_m", "M", "mapoff"

    def window_item(self, folder, ctx, score):
        return mapoff_window(_read(Path(folder) / "map_off_cells", "map_off_cells.json", MAPOFF_FORMAT,
                                   (score or {}).get("checkpoint_sha256", ctx.checkpoint_sha)))


class E6bKindTwoWindowJudge(_LateJudge):
    """The three D kinds ride the common named-kind consumer; without it nothing passes (same port as E4/E5, #733)."""
    name, stage_id, item = "kind_two_window_e6b", "E6b", "kind"

    def window_item(self, folder, ctx, score):
        return hold("stage_common_kind_consumer_unavailable")

    def judge(self, ctx, score):
        try:
            reader = getattr(importlib.import_module("foothold_s2.ex42_e3_judge"), "read_stage_bundle", None)
        except ModuleNotFoundError:
            reader = None
        if reader is not None:
            raise NotImplementedError("common read_stage_bundle exists now: wire E6b to it (verify the three D kinds)")
        return super().judge(ctx, score)


def m_return_decision(*, source_stage: str, m_updates: int, m_judgement: str, extension_used: bool) -> dict:
    """What happens after an M boundary (CG E.1 M row, ledger 11/11 19:38 2).

    M always returns to the stage it was entered from, with p_map_off 0.3 kept and the source's two windows counted anew.
    M updates never count toward the source stage maximum (they do count toward the 20,000 budget). If M has not exited by
    its 1,000 updates the run is notified and still returns to the source stage."""
    if not source_stage or type(m_updates) is not int or m_updates < 0 or m_judgement not in ("PASS", "HOLD", "FAIL"):
        raise ValueError("M return inputs invalid")
    base = {"return_to": source_stage, "p_map_off": 0.3, "source_windows_required": 2,
            "counts_toward_source_maximum": False, "counts_toward_ex42_budget": True}
    if m_judgement == "PASS":
        return {**base, "action": "return", "state": "m_exit_pass"}
    if m_updates >= M_MAX_UPDATES:
        return {**base, "action": "notify_and_return", "state": "m_exhausted"}
    if m_updates >= 500 and extension_used is not True:
        return {**base, "action": "extend", "state": "m_extension", "next_maximum": M_MAX_UPDATES}
    return {**base, "action": "continue", "state": "m_continues"}


for _judge in (E6aPostureTwoWindowJudge(), E6bKindTwoWindowJudge(), MapOffTwoWindowJudge()):
    register(_judge)
