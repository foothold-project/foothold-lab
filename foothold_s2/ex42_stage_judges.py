"""Stage exit judges: the plan names the adapter, the evaluation calls it (no stage id is spelled in the callers).

A stage row of the plan may carry `exit_judge: <adapter name>`. E0 and E1 keep their reviewed adapters as the default
(no plan edit, so no plan re-pin); a stage with no adapter judges nothing: its score stays HOLD with the reason, and a
PASS/FAIL claimed for it is refused. The scripter plugs a stage's judge in by registering an adapter here.

Adapter contract (input / output shapes, shared by every stage):
  judge(ctx, score) -> score
      ctx has: stage_id, checkpoint, evaluation, cfg, cfg_path, root, digest, plan (the maintenance-source plan dict),
      baseline loader helpers via ex42_e0_judge. Returns the measured score with `judgement` in PASS / HOLD / FAIL and
      the stage's own evidence under `stage_exit`: {judgement, windows, items{name: {role judge|record, judgement}}}.
  verify(score, judgment, expected, plan=None) -> dict
      Re-checks, on the P1 side, that a PASS / FAIL score carries its evidence (cells, two windows, ...). `expected` is
      the 26-cell aggregate, `plan` the plan document (passed by keyword). Raises ValueError; returns extra result
      fields to copy into the P1 receipt. ctx also has plan_path, checkpoint_sha and seed.
Aggregate rule everywhere: FAIL if any judge item FAILs, else HOLD if any is HOLD or missing, else PASS."""
from __future__ import annotations

from typing import Any

LEGACY_DEFAULT = {"E0": "map39_e0", "E1": "map39_e1_two_window"}
ADAPTERS: dict[str, "StageJudge"] = {}


def retained_paper_cells(plan: dict, stage_id: str) -> tuple[str, ...]:
    """Keep both earlier paper cells from E2 onward without changing E1F's live path."""
    stages = [row["id"] for row in plan["stages"]]
    if len(stages) != len(set(stages)) or stage_id not in stages or not {"E1", "E1F"} <= set(stages):
        raise ValueError("EX-42 paper-cell stage order is absent or duplicated")
    index = stages.index(stage_id)
    if stage_id == "E1F":
        return ("flag_cells",)
    return tuple(name for anchor, name in (("E1", "d44"), ("E1F", "flag_cells"))
                 if index >= stages.index(anchor))


class StageJudge:
    name = ""

    def judge(self, ctx: Any, score: dict) -> dict:
        raise NotImplementedError

    def verify(self, score: dict, judgment: str, expected: str, plan: dict | None = None) -> dict:
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

    def verify(self, score, judgment, expected, plan=None):
        if _map39_cell_check(score, judgment, self.modes) != judgment:
            raise ValueError("EX-42 P1 aggregate judgment differs from 26 cells")
        return {}


class _E1(_E0):
    name = "map39_e1_two_window"

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import load_baseline
        from foothold_s2.ex42_e1_judge import judge_e1, previous_e1_score
        from foothold_s2.eval.ex42_d44_cells import read_evidence
        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        if (ctx.evaluation / "d44" / "d44_cells.json").is_file():
            score["d44_cells"] = read_evidence(
                ctx.evaluation / "d44", plan=ctx.plan, plan_sha256=ctx.digest(ctx.plan_path),
                checkpoint_sha256=ctx.checkpoint_sha, seed=ctx.seed)
        prior = previous_e1_score(ctx.checkpoint, ctx.evaluation, ctx.plan["evaluation"]["interval_updates"],
                                  ctx.digest(ctx.cfg_path))
        return judge_e1(score, baseline, measured, ctx.plan, previous=prior)

    def verify(self, score, judgment, expected, plan=None):
        expected = _map39_cell_check(score, judgment, self.modes)          # the 26-cell structure first
        if plan is None:
            raise ValueError("EX-42 P1 E1 two-window exit needs the plan document")
        exit_row = score.get("e1_exit") or {}
        maintenance = exit_row.get("maintenance", {})
        landing = exit_row.get("d44", {})
        required = plan["evaluation"]["paper_cells"]["stairs_landing"].get("judge_cases") or []
        cases = landing.get("cases")
        if (not isinstance(required, list) or any(not isinstance(case_id, str) or not case_id for case_id in required)
                or len(set(required)) != len(required) or not isinstance(cases, dict) or set(cases) != set(required)
                or landing.get("required_cases") != required):
            raise ValueError("EX-42 P1 E1 D44 case evidence missing")
        case_states = [cases[case_id].get(which, {}).get("judgement")
                       for case_id in required for which in ("current", "previous")]
        if any(state not in ("PASS", "HOLD", "FAIL") for state in case_states):
            raise ValueError("EX-42 P1 E1 D44 case judgment invalid")
        from foothold_s2.ex42_e1_judge import _landing_window
        for case_id in required:                                          # per-case re-derivation from the raw evidence
            if cases[case_id]["current"] != _landing_window((score.get("d44_cells") or {}).get(case_id), plan, case_id):
                raise ValueError("EX-42 P1 E1 two-window exit evidence differs")
            previous_row = cases[case_id]["previous"]
            if previous_row["judgement"] in ("PASS", "FAIL") and _landing_window(previous_row, plan, case_id) != previous_row:
                raise ValueError("EX-42 P1 E1 prior D44 raw evidence differs")
        current_states = [cases[case_id]["current"]["judgement"] for case_id in required]
        previous_states = [cases[case_id]["previous"]["judgement"] for case_id in required]
        states = (expected, maintenance.get("previous"), landing.get("current", {}).get("judgement"),
                  landing.get("previous", {}).get("judgement"))
        if (score.get("stage_id") != "E1" or exit_row.get("judgement") != judgment or
                maintenance.get("current") != expected or
                set(landing) != {"required_cases", "cases", "current", "previous"} or
                landing["current"].get("judgement") != aggregate(current_states) or
                landing["previous"].get("judgement") != aggregate(previous_states) or
                any(state not in ("PASS", "HOLD", "FAIL") for state in states) or aggregate(states) != judgment):
            raise ValueError("EX-42 P1 E1 two-window exit evidence differs")
        return {"e1_exit": score["e1_exit"]}


class _E1V2(_E1):
    """Approved E1 exit v2; the six-cell D44 raw remains intact for diagnosis."""
    name = "map39_e1_v2_two_window"

    def judge(self, ctx, score):
        from foothold_s2.ex42_e0_judge import load_baseline
        from foothold_s2.ex42_e1_judge import previous_e1_score
        from foothold_s2.ex42_e1_v2 import judge_e1_v2, measure_cells
        from foothold_s2.eval.ex42_d44_cells import read_evidence
        baseline = load_baseline(ctx.root, ctx.cfg, ctx.digest)
        baseline["_sha256"] = ctx.cfg["baseline"]["sha256"]
        measured = ctx.plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        if (ctx.evaluation / "d44" / "d44_cells.json").is_file():
            from foothold_s2.ex42_e1_wide import active as wide_active
            receipt_sha = ctx.digest(ctx.plan_path)
            if wide_active(score, ctx.plan):
                import json
                receipt = json.loads((ctx.evaluation / "d44" / "d44_cells.json").read_text(encoding="utf-8-sig"))
                allowed = {receipt_sha, score["execution_plan_sha256"]}
                receipt_sha = receipt.get("plan_sha256")
                if receipt_sha not in allowed:
                    raise ValueError("E1 C1 D44 Kit plan SHA is neither execution nor evaluation plan")
            score["d44_cells"] = read_evidence(
                ctx.evaluation / "d44", plan=ctx.plan, plan_sha256=receipt_sha,
                checkpoint_sha256=ctx.checkpoint_sha, seed=ctx.seed)
        score["e1_v2_evaluation"] = str(ctx.evaluation)
        score["e1_v2_cells"] = measure_cells(ctx.evaluation, ctx.checkpoint_sha, ctx.seed)
        from foothold_s2.ex42_e1_wide import active as wide_active
        if wide_active(score, ctx.plan):
            from foothold_s2.ex42_e1_wide import read_cells, cap_from_training
            from foothold_s2.ex42_score import _json
            mesh_sha = _json(ctx.evaluation / "map64" / "map_modes.json")["ex42_mesh"]["mesh_sha256"]
            score["e1_wide_evaluation"] = str(ctx.evaluation)
            score["e1_wide_cells"] = read_cells(ctx.evaluation, ctx.checkpoint_sha, ctx.seed,
                                                 ctx.plan, mesh_sha)
            score["e1_wide_cap"] = cap_from_training(ctx.checkpoint,
                                                     score["execution_plan_sha256"], mesh_sha)
        prior = previous_e1_score(ctx.checkpoint, ctx.evaluation, ctx.plan["evaluation"]["interval_updates"],
                                  ctx.digest(ctx.cfg_path))
        return judge_e1_v2(score, baseline, measured, ctx.plan, previous=prior,
                           checkpoint=ctx.checkpoint, evaluation=ctx.evaluation, seed=ctx.seed)

    def verify(self, score, judgment, expected, plan=None):
        from pathlib import Path
        from foothold_s2.ex42_e0_judge import load_baseline
        from foothold_s2.ex42_e1_judge import previous_e1_score
        from foothold_s2.ex42_e1_v2 import judge_e1_v2, measure_cells
        from foothold_s2.ex42_score import ROOT, config, digest
        if plan is None or score.get("stage_id") != "E1":
            raise ValueError("EX-42 P1 E1 v2 plan or stage missing")
        if any(key not in score for key in ("checkpoint", "e1_v2_evaluation", "e1_v2_cells", "e1_exit_v2")):
            raise ValueError("EX-42 P1 E1 v2 score evidence missing")
        if _map39_cell_check(score, judgment, self.modes) != expected:
            raise ValueError("EX-42 P1 E1 v2 maintenance cells differ")
        cfg, cfg_path = config()
        baseline = load_baseline(ROOT, cfg, digest)
        baseline["_sha256"] = cfg["baseline"]["sha256"]
        measured = plan["assumptions_pending_lead"]["q4_two_window_range"]["value"]["measured"]
        checkpoint, evaluation = Path(score["checkpoint"]), Path(score["e1_v2_evaluation"])
        actual = measure_cells(evaluation, score["checkpoint_sha256"], score["conditions"]["eval_seed"])
        if actual != score.get("e1_v2_cells"):
            raise ValueError("EX-42 P1 E1 v2 raw cell evidence differs")
        from foothold_s2.ex42_e1_wide import active as wide_active
        if wide_active(score, plan):
            from foothold_s2.ex42_e1_wide import read_cells, cap_from_training
            from foothold_s2.ex42_score import _json
            mesh_sha = _json(evaluation / "map64" / "map_modes.json")["ex42_mesh"]["mesh_sha256"]
            counted_wide = read_cells(evaluation, score["checkpoint_sha256"],
                                      score["conditions"]["eval_seed"], plan, mesh_sha)
            counted_cap = cap_from_training(checkpoint, score["execution_plan_sha256"], mesh_sha)
            if (counted_wide != score.get("e1_wide_cells") or counted_cap != score.get("e1_wide_cap")
                    or score.get("e1_wide_evaluation") != str(evaluation)):
                raise ValueError("EX-42 P1 E1 C1 raw cell or cap evidence differs")
        prior = previous_e1_score(checkpoint, evaluation, plan["evaluation"]["interval_updates"],
                                  score["score_config_sha256"])
        if prior is not None and "e1_v2_cells" in prior:
            prior_raw = measure_cells(Path(prior["e1_v2_evaluation"]), prior["checkpoint_sha256"],
                                      prior["conditions"]["eval_seed"])
            if prior_raw != prior["e1_v2_cells"]:
                raise ValueError("EX-42 P1 prior E1 v2 raw cell evidence differs")
        recalculated = judge_e1_v2(score, baseline, measured, plan, previous=prior,
                                   checkpoint=checkpoint, evaluation=evaluation,
                                   seed=score["conditions"]["eval_seed"])
        if (recalculated["judgement"] != judgment or
                recalculated["e1_exit_v2"] != score.get("e1_exit_v2") or
                recalculated["e1_exit"] != score.get("e1_exit")):
            raise ValueError("EX-42 P1 E1 v2 two-window judgment differs")
        return {"e1_exit": score["e1_exit"], "e1_exit_v2": score["e1_exit_v2"]}


register(_E0())
register(_E1())
register(_E1V2())

# E1F owns its policy and registers the adapter when the reviewed E0/E1 table
# is ready. Importing only this registry must be sufficient for adapter_for().
from foothold_s2 import ex42_e1f_judge  # noqa: E402,F401
from foothold_s2 import ex42_e2_judge  # noqa: E402,F401
