"""E1F -> E2 handoff from the FIRST boundary window (m250), on the team lead's recorded approval (lead 2026-11-17 01:13, ledger line 900).

Why a receipt: the E1F exit judge needs two windows. At the first boundary (m250) it has no earlier window, so `maintenance_previous` and the
four `flag_*_previous` items are HOLD with the reason "직전 창 없음" (structural, not a measurement) and the stage judgment is HOLD. The team
lead approved handing m250 over anyway. This module is the cap_handoff counterpart (`ex42_e1_cap_handoff.py`): one receipt kind,
`e1f_first_window_handoff.json` (state `first_window_handoff`, judgment `FIRST_WINDOW_HANDOFF`; never `complete` / `PASS`). The reader refuses
anything but exactly that situation:
  * the boundary p1_score.json is complete, stage E1F, judgment HOLD (a PASS uses the PASS gate; a FAIL is refused), at the plan's FIRST window
    (checkpoint_iteration == evaluation.interval_updates);
  * the measurement behind it recounts under the E1F judge (`adapter.verify`) and its cell judgments are the score's;
  * the only non-PASS exit items are `maintenance_previous` and the `<case>_previous` flag items, and each flag one carries the reason
    "직전 창 없음"; every `current` item, the calibration and the maintenance table (every judge cell) are PASS; current flag survival is 64/64;
  * the team lead's ledger line: commit on the published ledger branch, the registered decisions file, the full text and its sha256, tag
    `[첫 창 보류 넘김 승인 줄 · first_window_handoff]`, the approval phrase, a decision id, and the run `E1F · m<iteration> · <first 8 hex of the
    checkpoint sha256>`; the text is looked up again with `git show <commit>:<path>` at read time.
Nothing else is relaxed: the evidence, budget, parent and pin checks of the later steps are the PASS path's.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from foothold_s2.ex42_e1_cap_handoff import (LEDGER_PATH, LEDGER_REMOTE_REF, LEDGER_REPO_ENV, _ledger_lines, maintenance_judgement)

FORMAT = "foothold-ex42-e1f-first-window-handoff/1"
STATE = "first_window_handoff"
JUDGMENT = "FIRST_WINDOW_HANDOFF"
STAGE = "E1F"
LINE_TAG = "[첫 창 보류 넘김 승인 줄 · first_window_handoff]"
APPROVAL_PHRASE = "직전 창 칸만 보류인 E1F 첫 창을 E2 부모로 넘김"
NO_PREVIOUS_REASON = "직전 창 없음"
SURVIVAL_ENVS = 64


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _ref_path(ref: dict, base: Path) -> Path:
    path = Path(ref["path"])
    return path if path.is_absolute() else base / path


def hold_items(items: dict) -> list[str]:
    return sorted(name for name, item in items.items() if item.get("judgement") == "HOLD")


def check_first_window_items(items: dict, judge_cases) -> None:
    """The exit items of the first window: the structural HOLDs only, everything measured PASS with full survival."""
    expected_hold = {"maintenance_previous"} | {f"{case}_previous" for case in judge_cases}
    if any(item.get("judgement") == "FAIL" for item in items.values()):
        raise ValueError("first window handoff: an exit item FAILs")
    if set(hold_items(items)) != expected_hold:
        raise ValueError("first window handoff: the HOLD items are not exactly the previous-window items")
    for case in judge_cases:
        if items[f"{case}_previous"].get("reason") != NO_PREVIOUS_REASON:
            raise ValueError(f"first window handoff: {case}_previous is not HOLD for lack of an earlier window")
        current = items[f"{case}_current"]
        if (current.get("judgement") != "PASS" or current.get("valid_count") != SURVIVAL_ENVS
                or current.get("survival_count") != SURVIVAL_ENVS):
            raise ValueError(f"first window handoff: {case}_current is not PASS with survival {SURVIVAL_ENVS}/{SURVIVAL_ENVS}")
    for name in ("maintenance_current", "flag_calibration"):
        if items[name].get("judgement") != "PASS":
            raise ValueError(f"first window handoff: {name} is not PASS")


def _check_approval(approval, repo, *, iteration: int, checkpoint_sha256: str) -> None:
    if not isinstance(approval, dict) or set(approval) != {"commit", "path", "line", "line_text", "line_sha256", "decision_id"}:
        raise ValueError("first window handoff approval pin has the wrong fields")
    repo = repo or os.environ.get(LEDGER_REPO_ENV)
    if not repo:
        raise ValueError(f"first window handoff needs the ledger repository ({LEDGER_REPO_ENV} or the repo argument)")
    if approval["path"] != LEDGER_PATH:
        raise ValueError("ledger path is not the registered decisions file")
    ancestor = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", approval["commit"], LEDGER_REMOTE_REF],
                              capture_output=True, check=False)
    if ancestor.returncode != 0:
        raise ValueError(f"first window handoff ledger commit is not on {LEDGER_REMOTE_REF} (a local commit is not an approval)")
    text = approval["line_text"]
    if not isinstance(text, str) or hashlib.sha256(text.encode("utf-8")).hexdigest() != approval["line_sha256"]:
        raise ValueError("first window handoff ledger line text differs from its sha")
    if text.encode("utf-8") not in _ledger_lines(repo, approval["commit"], approval["path"]):
        raise ValueError("first window handoff ledger line is not in the ledger at that commit")
    needles = (LINE_TAG, APPROVAL_PHRASE, approval["decision_id"], f"{STAGE} · m{iteration} · {checkpoint_sha256[:8]}")
    if not approval["decision_id"] or any(not isinstance(n, str) or n not in text for n in needles):
        raise ValueError("first window handoff ledger line does not name this approval, stage, round and checkpoint")


def read_first_window_handoff(path, *, repo=None, policy_plan=None) -> dict:
    """Verify the receipt against its own pinned files and the ledger; returns the receipt dict plus `p1_score_path`."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_judges import adapter_for
    path = Path(path).resolve(strict=True)
    row = _json(path)
    if (row.get("format") != FORMAT or row.get("state") != STATE or row.get("judgment") != JUDGMENT or row.get("stage_id") != STAGE):
        raise ValueError("not an E1F first window handoff receipt")
    p1_ref = row.get("p1_score")
    if not isinstance(p1_ref, dict):
        raise ValueError("first window handoff lacks its boundary score")
    p1_path = _ref_path(p1_ref, path.parent).resolve(strict=True)
    if _sha(p1_path) != p1_ref.get("sha256"):
        raise ValueError("first window handoff boundary score sha differs")
    p1 = _json(p1_path)
    if p1.get("state") != "complete" or p1.get("stage_id") != STAGE or p1.get("judgment") != "HOLD":
        raise ValueError("boundary score is not a complete E1F HOLD (a PASS uses the PASS gate)")
    for key in ("checkpoint_iteration", "checkpoint_sha256", "plan_sha256", "measurement", "measurement_sha256", "evaluation_plan"):
        if row.get(key) != p1.get(key) or row.get(key) in (None, ""):
            raise ValueError(f"first window handoff {key} differs from the boundary score")
    ref = p1["evaluation_plan"]
    if policy_plan is None:
        policy_plan = EX42Plan.load(ref["path"])
    if policy_plan.sha256 != ref.get("sha256"):
        raise ValueError("first window handoff evaluation plan sha differs")
    if row["checkpoint_iteration"] != policy_plan.document["evaluation"]["interval_updates"]:
        raise ValueError("first window handoff is only for the first boundary window")
    measurement = _ref_path({"path": row["measurement"]}, p1_path.parent)
    if not measurement.is_file() or _sha(measurement) != row["measurement_sha256"]:
        raise ValueError("first window handoff measurement is missing or its sha differs")
    measured = _json(measurement)
    if (measured.get("checkpoint_sha256") != p1.get("checkpoint_sha256")
            or not isinstance(measured.get("cell_judgments"), dict) or measured["cell_judgments"] != p1.get("cell_judgments")):
        raise ValueError("first window handoff measurement and boundary score cell judgments differ")
    if measured.get("maintenance_source_sha256") not in (None, policy_plan.sha256):
        raise ValueError("first window handoff evaluation policy differs from the measured maintenance_source_sha256")
    adapter = adapter_for(policy_plan.document, STAGE)
    if adapter is None:
        raise ValueError("E1F judge is unavailable")
    extras = adapter.verify(measured, "HOLD", "PASS", plan=policy_plan.document)       # raw flag cells, calibration and evidence files recounted
    if not extras:
        raise ValueError("first window handoff exit evidence is not recounted")
    items = (measured.get("stage_exit") or {}).get("items") or {}
    from foothold_s2.ex42_e1f_judge import contract
    check_first_window_items(items, contract(policy_plan.document)["judge_cases"])
    if maintenance_judgement({**p1, "e1_exit": {"maintenance": {"current": items["maintenance_current"]["judgement"]}}}) != "PASS":
        raise ValueError("first window handoff needs the maintenance table PASS")
    if row.get("hold_items") != hold_items(items):
        raise ValueError("first window handoff hold record differs from the measured items")
    _check_approval(row.get("lead_approval"), repo, iteration=row["checkpoint_iteration"], checkpoint_sha256=row["checkpoint_sha256"])
    return {**row, "kind": STATE, "path": str(path), "sha256": _sha(path), "p1_score_path": str(p1_path)}


def build_first_window_handoff(p1_score_path, out, *, repo, commit, ledger_path, line, line_text, decision_id) -> dict:
    """Write the receipt next to the boundary score (atomic, never overwrites)."""
    p1_path = Path(p1_score_path).resolve(strict=True)
    out = Path(out)
    if out.exists():
        raise ValueError("first window handoff receipt already exists; it is never overwritten")
    p1 = _json(p1_path)
    measured = _json(_ref_path({"path": p1["measurement"]}, p1_path.parent))
    row = {"format": FORMAT, "state": STATE, "judgment": JUDGMENT, "stage_id": STAGE,
           "plan_sha256": p1.get("plan_sha256"), "checkpoint_iteration": p1.get("checkpoint_iteration"),
           "checkpoint_sha256": p1.get("checkpoint_sha256"), "evaluation_plan": p1.get("evaluation_plan"),
           "measurement": p1.get("measurement"), "measurement_sha256": p1.get("measurement_sha256"),
           "p1_score": {"path": str(p1_path), "sha256": _sha(p1_path)},
           "hold_items": hold_items((measured.get("stage_exit") or {}).get("items") or {}),
           "lead_approval": {"commit": commit, "path": ledger_path, "line": line, "line_text": line_text,
                             "line_sha256": hashlib.sha256(line_text.encode("utf-8")).hexdigest(), "decision_id": decision_id}}
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.link(tmp, out)            # fails if out appeared meanwhile: no overwrite
    finally:
        tmp.unlink()
    return row


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--p1-score", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ledger-repo", default=None, help=f"default: ${LEDGER_REPO_ENV}")
    p.add_argument("--ledger-commit", required=True)
    p.add_argument("--ledger-path", required=True)
    p.add_argument("--ledger-line", type=int, required=True)
    p.add_argument("--ledger-line-text", required=True, help="the whole ledger line, as committed")
    p.add_argument("--decision-id", required=True)
    a = p.parse_args(argv)
    build_first_window_handoff(a.p1_score, a.out, repo=a.ledger_repo or os.environ.get(LEDGER_REPO_ENV), commit=a.ledger_commit,
                               ledger_path=a.ledger_path, line=a.ledger_line, line_text=a.ledger_line_text, decision_id=a.decision_id)
    try:
        read_first_window_handoff(a.out, repo=a.ledger_repo)
    except Exception:
        Path(a.out).unlink()          # a receipt that does not read back is not left behind
        raise
    print(f"first window handoff receipt written and read back: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
