"""E1 -> E1F handoff WITHOUT a graduation PASS, on the team lead's recorded approval (lead 2026-11-16 15:41).

One receipt kind, `e1_cap_handoff.json` (state `cap_handoff`, judgment `CAP_HANDOFF`; never `complete` / `PASS`, so no reader of the
PASS gate can mistake it for one). It pins:
  * the boundary p1_score.json of the handed-over checkpoint (its own sha, and its measurement file sha), which must NOT be a PASS
    (if the boundary passed, the PASS gate is the only way and this receipt is refused);
  * the cells that missed the bar, recomputed from that p1_score (a receipt whose list differs from the recount is refused);
  * the maintenance table verdict (must be PASS) and a survival floor on the missed cells (current window, 60 of 64);
  * the team lead's ledger line: commit, path inside the repository, the full line text, its sha256 (bytes without the newline) and the
    decision id. The text is looked up again with `git show <commit>:<path>` at read time (the line number is only a hint); the line
    must carry the tag `[상한 넘김 승인 줄 · cap_handoff]`, the decision's phrase, the decision id (the earlier ledger decision it rests
    on, e.g. `de927fbf`) and the run `E1 · m<iteration> · <first 8 hex of the checkpoint sha256>`.
The ledger repository location is an argument or the environment variable EX42_LEDGER_REPO, never a path in this code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

FORMAT = "foothold-ex42-e1-cap-handoff/1"
STATE = "cap_handoff"
JUDGMENT = "CAP_HANDOFF"
LINE_TAG = "[상한 넘김 승인 줄 · cap_handoff]"
APPROVAL_PHRASE = "E1F 로 넘어가되 저속 칸은 E1F 에서 기록 평가로 계속"     # the team lead's decision 2, quoted in the approval line
LEDGER_REPO_ENV = "EX42_LEDGER_REPO"
LEDGER_PATH = "inbox/jay/20261104-ex41-restart/decisions.tsv"          # the ledger file is fixed here, the receipt cannot name another
LEDGER_REMOTE_REF = "origin/feature/verify-v2-mvp-jay"               # the approval commit must already be on the published ledger branch
_WINDOWS = ("current", "previous")


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _scalars(item: dict) -> dict:
    return {k: v for k, v in item.items() if isinstance(v, (bool, int, float, str)) or v is None}


def unmet_cells(p1: dict) -> tuple[list[dict], list[str]]:
    """(FAIL items with their scalar values, names of HOLD items) of the E1 exit judge, current and previous window."""
    exit_row = p1.get("e1_exit_v2")
    if not isinstance(exit_row, dict):
        raise ValueError("E1 boundary score has no e1_exit_v2 to take the missed cells from")
    failed, held = [], []
    for window in _WINDOWS:
        items = (exit_row.get(window) or {}).get("items") or {}
        for name, item in sorted(items.items()):
            if item.get("judgement") == "FAIL":
                failed.append({"window": window, "item_id": name, **_scalars(item)})
            elif item.get("judgement") == "HOLD":
                held.append(f"{window}/{name}")
    return failed, held


def maintenance_judgement(p1: dict) -> str:
    """PASS only when the maintenance table of the boundary score is PASS: current-window maintenance and every judge cell."""
    cells = p1.get("cell_judgments")
    rows = p1.get("map_matrix")
    if not isinstance(cells, dict) or not isinstance(rows, list) or not rows:
        return "HOLD"
    for row in rows:
        if row.get("role") == "judge":
            value = (cells.get(row.get("map_mode")) or {}).get(row.get("command")) or {}
            if value.get("judgment") != "PASS" or value.get("role") != "judge":
                return "HOLD"
    return "PASS" if (p1.get("e1_exit") or {}).get("maintenance", {}).get("current") == "PASS" else "HOLD"


def survival_below_floor(failed: list[dict], *, floor: int = 60, of: int = 64) -> list[str]:
    """Missed cells of the current window whose survival is under floor/of (scaled to the cell's envs)."""
    out = []
    for cell in failed:
        envs = cell.get("envs")
        survival = cell.get("survival")
        if cell.get("window") != "current":
            continue
        if type(envs) is not int or type(survival) is not int or envs <= 0 or survival * of < floor * envs:
            out.append(cell["item_id"])
    return out


def _ledger_lines(repo, commit: str, path: str) -> list[bytes]:
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("ledger commit must be a full 40-hex sha")
    if path != LEDGER_PATH:
        raise ValueError("ledger path is not the registered decisions file")
    shown = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"], capture_output=True, check=False)
    if shown.returncode != 0:
        raise ValueError("ledger commit or path cannot be read")
    return [raw.rstrip(b"\r") for raw in shown.stdout.split(b"\n")]


def _check_approval(approval, repo, *, iteration: int, checkpoint_sha256: str) -> None:
    if not isinstance(approval, dict) or set(approval) != {"commit", "path", "line", "line_text", "line_sha256", "decision_id"}:
        raise ValueError("cap handoff approval pin has the wrong fields")
    repo = repo or os.environ.get(LEDGER_REPO_ENV)
    if not repo:
        raise ValueError(f"cap handoff needs the ledger repository ({LEDGER_REPO_ENV} or the repo argument)")
    if approval["path"] != LEDGER_PATH:
        raise ValueError("ledger path is not the registered decisions file")
    ancestor = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", approval["commit"], LEDGER_REMOTE_REF],
                              capture_output=True, check=False)
    if ancestor.returncode != 0:
        raise ValueError(f"cap handoff ledger commit is not on {LEDGER_REMOTE_REF} (a local commit is not an approval)")
    text = approval["line_text"]
    if not isinstance(text, str) or hashlib.sha256(text.encode("utf-8")).hexdigest() != approval["line_sha256"]:
        raise ValueError("cap handoff ledger line text differs from its sha")
    if text.encode("utf-8") not in _ledger_lines(repo, approval["commit"], approval["path"]):
        raise ValueError("cap handoff ledger line is not in the ledger at that commit")
    needles = (LINE_TAG, APPROVAL_PHRASE, approval["decision_id"], f"E1 · m{iteration} · {checkpoint_sha256[:8]}")
    if not approval["decision_id"] or any(not isinstance(n, str) or n not in text for n in needles):
        raise ValueError("cap handoff ledger line does not name this approval, stage, round and checkpoint")


def _ref_path(ref: dict, base: Path) -> Path:
    path = Path(ref["path"])
    return path if path.is_absolute() else base / path


def _recount_exit(measured: dict, p1: dict, policy_plan) -> None:
    """The same recount validate_source_exit does for a PASS gate, minus the PASS requirement: the measurement's cell judgments
    must be the score's, and the E1 judge recounts its exit evidence from the measurement (raw files) and must get the score's."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_stage_judges import adapter_for
    if policy_plan is None:                       # the plan the boundary was judged under, named by the score itself
        ref = p1.get("evaluation_plan")
        if not isinstance(ref, dict) or not ref.get("path"):
            raise ValueError("cap handoff cannot find the evaluation plan the boundary was judged under")
        policy_plan = EX42Plan.load(ref["path"])
        if policy_plan.sha256 != ref.get("sha256"):
            raise ValueError("cap handoff evaluation plan sha differs")
    policy_sha = measured.get("maintenance_source_sha256")
    if policy_sha is not None and policy_sha != policy_plan.sha256:
        raise ValueError("cap handoff evaluation policy differs from the measured maintenance_source_sha256")
    adapter = adapter_for(policy_plan.document, "E1")
    if adapter is None:
        raise ValueError("E1 judge is unavailable")
    extras = adapter.verify(measured, p1["judgment"], "PASS", plan=policy_plan.document)
    if not extras or any(p1.get(k) != v for k, v in extras.items()):
        raise ValueError("cap handoff boundary score differs from the exit evidence recounted from its measurement")


def read_cap_handoff(path, *, exit_updates: tuple[int, ...], repo=None, policy_plan=None) -> dict:
    """Verify the receipt against its own pinned files and the ledger; returns the gate-shaped dict the consumers use."""
    path = Path(path).resolve(strict=True)
    row = _json(path)
    if (row.get("format") != FORMAT or row.get("state") != STATE or row.get("judgment") != JUDGMENT
            or row.get("stage_id") != "E1"):
        raise ValueError("not an E1 cap handoff receipt")
    p1_ref = row.get("p1_score")
    if not isinstance(p1_ref, dict):
        raise ValueError("cap handoff lacks its boundary score")
    p1_path = _ref_path(p1_ref, path.parent).resolve(strict=True)
    if _sha(p1_path) != p1_ref.get("sha256"):
        raise ValueError("cap handoff boundary score sha differs")
    p1 = _json(p1_path)
    if (p1.get("state") != "complete" or p1.get("stage_id") != "E1"
            or p1.get("judgment") == "PASS"):
        raise ValueError("boundary score is a PASS (use the PASS gate) or not a complete E1 score")
    for key in ("checkpoint_iteration", "checkpoint_sha256", "plan_sha256", "measurement", "measurement_sha256"):
        if row.get(key) != p1.get(key) or row.get(key) in (None, ""):
            raise ValueError(f"cap handoff {key} differs from the boundary score")
    if row["checkpoint_iteration"] not in exit_updates:
        raise ValueError("cap handoff checkpoint is not an E1 exit boundary")
    measurement = _ref_path({"path": row["measurement"]}, p1_path.parent)
    if not measurement.is_file() or _sha(measurement) != row["measurement_sha256"]:
        raise ValueError("cap handoff measurement is missing or its sha differs")
    measured = _json(measurement)
    if (measured.get("checkpoint_sha256") != p1.get("checkpoint_sha256")
            or not isinstance(measured.get("cell_judgments"), dict) or measured["cell_judgments"] != p1.get("cell_judgments")):
        raise ValueError("cap handoff measurement and boundary score cell judgments differ")
    _recount_exit(measured, p1, policy_plan)
    failed, held = unmet_cells(p1)
    if row.get("unmet_cells") != failed or row.get("hold_items") != held:
        raise ValueError("cap handoff missed-cell record differs from the boundary score")
    maintenance = maintenance_judgement(p1)
    if row.get("maintenance_judgement") != maintenance or maintenance != "PASS":
        raise ValueError("cap handoff needs the maintenance table PASS")
    if not failed or survival_below_floor(failed):
        raise ValueError("cap handoff has no missed cell, or a missed cell is under the survival floor")
    previous = row.get("previous_p1_score")
    if previous is not None:
        prev_path = _ref_path(previous, path.parent).resolve(strict=True)
        if _sha(prev_path) != previous.get("sha256"):
            raise ValueError("cap handoff previous score sha differs")
    _check_approval(row.get("lead_approval"), repo, iteration=row["checkpoint_iteration"], checkpoint_sha256=row["checkpoint_sha256"])
    return {**row, "kind": "cap_handoff", "path": str(path), "sha256": _sha(path), "p1_score_path": str(p1_path),
            "unmet_cell_names": sorted(f"{c['window']}/{c['item_id']}" for c in failed)}


def build_cap_handoff(p1_score_path, out, *, repo, commit, ledger_path, line, line_text, decision_id,
                      previous_p1_score_path=None) -> dict:
    """Write the receipt next to the boundary score (atomic, never overwrites) and read it back."""
    p1_path = Path(p1_score_path).resolve(strict=True)
    out = Path(out)
    if out.exists():
        raise ValueError("cap handoff receipt already exists; it is never overwritten")
    p1 = _json(p1_path)
    failed, held = unmet_cells(p1)
    row = {"format": FORMAT, "state": STATE, "judgment": JUDGMENT, "stage_id": "E1",
           "plan_sha256": p1.get("plan_sha256"), "checkpoint_iteration": p1.get("checkpoint_iteration"),
           "checkpoint_sha256": p1.get("checkpoint_sha256"),
           "measurement": p1.get("measurement"), "measurement_sha256": p1.get("measurement_sha256"),
           "p1_score": {"path": str(p1_path), "sha256": _sha(p1_path)},
           "previous_p1_score": (None if previous_p1_score_path is None else
                                 {"path": str(Path(previous_p1_score_path).resolve(strict=True)),
                                  "sha256": _sha(Path(previous_p1_score_path).resolve(strict=True))}),
           "unmet_cells": failed, "hold_items": held, "maintenance_judgement": maintenance_judgement(p1),
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
    p.add_argument("--source-plan", required=True, help="source plan, for the E1 exit boundaries")
    p.add_argument("--ledger-repo", default=None, help=f"default: ${LEDGER_REPO_ENV}")
    p.add_argument("--ledger-commit", required=True)
    p.add_argument("--ledger-path", required=True)
    p.add_argument("--ledger-line", type=int, required=True)
    p.add_argument("--ledger-line-text", required=True, help="the whole ledger line, as committed")
    p.add_argument("--decision-id", required=True)
    p.add_argument("--previous-p1-score", default=None)
    a = p.parse_args(argv)
    from foothold_s2.curriculum.ex42_prep import EX42Plan, stage_exit_updates
    exit_updates = stage_exit_updates(EX42Plan.load(a.source_plan).document, "E1")
    build_cap_handoff(a.p1_score, a.out, repo=a.ledger_repo or os.environ.get(LEDGER_REPO_ENV), commit=a.ledger_commit,
                      ledger_path=a.ledger_path, line=a.ledger_line, line_text=a.ledger_line_text,
                      decision_id=a.decision_id,
                      previous_p1_score_path=a.previous_p1_score)
    try:
        read_cap_handoff(a.out, exit_updates=exit_updates, repo=a.ledger_repo)
    except Exception:
        Path(a.out).unlink()          # a receipt that does not read back is not left behind
        raise
    print(f"cap handoff receipt written and read back: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
