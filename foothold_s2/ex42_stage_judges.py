"""Stage exit judges: the plan names the adapter, the evaluation calls it (no stage id is spelled in the callers).

A stage row of the plan may carry `exit_judge: <adapter name>`. E0 and E1 keep their reviewed adapters as the default
(no plan edit, so no plan re-pin); a stage with no adapter judges nothing: its score stays HOLD with the reason, and a
PASS/FAIL claimed for it is refused. The scripter plugs a stage's judge in by registering an adapter here.

Adapter contract (input / output shapes, shared by every stage):
  judge(ctx, score) -> score
      ctx has: stage_id, checkpoint, evaluation, cfg, cfg_path, root, digest, plan (the maintenance-source plan dict),
      baseline loader helpers via ex42_e0_judge. Returns the measured score with `judgement` in PASS / HOLD / FAIL and
      the stage's own evidence under `stage_exit`: {judgement, windows, items{name: {role judge|record, judgement}}}.
  verify(score, judgment, expected) -> dict
      Re-checks, on the P1 side, that a PASS / FAIL score carries its evidence (cells, two windows, ...). `expected` is
      the 26-cell aggregate. Raises ValueError; returns extra result fields to copy into the P1 receipt.
Aggregate rule everywhere: FAIL if any judge item FAILs, else HOLD if any is HOLD or missing, else PASS."""
from __future__ import annotations

from typing import Any, Callable

LEGACY_DEFAULT = {"E0": "map39_e0", "E1": "map39_e1_two_window"}
ADAPTERS: dict[str, "StageJudge"] = {}


class StageJudge:
    name = ""

    def judge(self, ctx: Any, score: dict) -> dict:
        raise NotImplementedError

    def verify(self, score: dict, judgment: str, expected: str) -> dict:
        raise NotImplementedError


def register(adapter: StageJudge) -> StageJudge:
    if not adapter.name or adapter.name in ADAPTERS:
        raise ValueError(f"EX-42 judge adapter name {adapter.name!r} is empty or taken")
    ADAPTERS[adapter.name] = adapter
    return adapter


def adapter_name(plan_doc: dict, stage_id: str) -> str | None:
    row = next((r for r in plan_doc.get("stages", []) if r.get("id") == stage_id), None)
    if row is None:
        raise ValueError(f"EX-42 stage {stage_id!r} is not in the plan")
    return row.get("exit_judge", LEGACY_DEFAULT.get(stage_id))


def adapter_for(plan_doc: dict, stage_id: str) -> StageJudge | None:
    """The stage's registered adapter, None when the stage names none; an unknown name is an error (typo)."""
    name = adapter_name(plan_doc, stage_id)
    if name is None:
        return None
    if name not in ADAPTERS:
        raise ValueError(f"EX-42 stage {stage_id} names the unknown judge adapter {name!r}")
    return ADAPTERS[name]


def aggregate(states) -> str:
    states = list(states)
    return "FAIL" if "FAIL" in states else "HOLD" if (not states or "HOLD" in states) else "PASS"


def previous_window(ctx: Any) -> dict | None:
    """The immediately preceding boundary's measured score of the same stage and run (None for the first window);
    identity-checked against its P1 receipt, checkpoint file and score config. For two-window exits."""
    from foothold_s2.ex42_e1_judge import previous_e1_score
    return previous_e1_score(ctx.checkpoint, ctx.evaluation, ctx.plan["evaluation"]["interval_updates"],
                             ctx.digest(ctx.cfg_path), stage_id=ctx.stage_id)


# ---- the two reviewed adapters (behavior moved here unchanged) -------------------------------------------------
def _map39_cell_check(score: dict, judgment: str, modes) -> str:
    cells = score.get("cell_judgments") or {}
    if (set(cells) != set(modes) or
            any(set(cells[mode]) != set(score["map64"].get(mode, {})) for mode in modes) or
            any(cells[mode][case].get("role") != "judge" for mode in ("eval_gt", "eval_pred") for case in cells[mode]) or
            any(cells["probe_prop_only"][case].get("role") != "record_only" for case in cells["probe_prop_only"]) or
            any(cells[mode][case].get("judgment") not in ("PASS", "HOLD", "FAIL")
                for mode in ("eval_gt", "eval_pred") for case in cells[mode])):
        raise ValueError("EX-42 P1 judged E0 cell evidence missing or stage differs")
    verdicts = [cells[mode][case]["judgment"] for mode in ("eval_gt", "eval_pred") for case in cells[mode]]
    expected = aggregate(verdicts)
    if len(verdicts) != 26:
        raise ValueError("EX-42 P1 aggregate judgment differs from 26 cells")
    return expected


class _E0(StageJudge):
    name = "map39_e0"
    modes = ("eval_gt", "eval_pred", "probe_prop_only")

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import judge, load_baseline
        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        return judge(score, baseline, measured)

    def verify(self, score, judgment, expected):
        if _map39_cell_check(score, judgment, self.modes) != judgment:
            raise ValueError("EX-42 P1 aggregate judgment differs from 26 cells")
        return {}


class _E1(_E0):
    name = "map39_e1_two_window"

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import load_baseline
        from foothold_s2.ex42_e1_judge import judge_e1, previous_e1_score
        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        prior = previous_e1_score(ctx.checkpoint, ctx.evaluation, ctx.plan["evaluation"]["interval_updates"],
                                  ctx.digest(ctx.cfg_path))
        return judge_e1(score, baseline, measured, ctx.plan, previous=prior)

    def verify(self, score, judgment, expected):
        exit_row = score.get("e1_exit") or {}
        maintenance = exit_row.get("maintenance", {})
        landing = exit_row.get("d44", {})
        states = (expected, maintenance.get("previous"), landing.get("current", {}).get("judgement"),
                  landing.get("previous", {}).get("judgement"))
        if (score.get("stage_id") != "E1" or exit_row.get("judgement") != judgment or
                maintenance.get("current") != expected or set(landing) != {"current", "previous"} or
                any(state not in ("PASS", "HOLD", "FAIL") for state in states) or aggregate(states) != judgment):
            raise ValueError("EX-42 P1 E1 two-window exit evidence differs")
        return {"e1_exit": score["e1_exit"]}


register(_E0())
register(_E1())
