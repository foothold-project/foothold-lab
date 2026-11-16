"""E1 -> E1F handoff without a graduation PASS (lead 2026-11-16 15:41 / 16:32): the cap handoff receipt and its readers.
The ledger is a throw-away git repository; the boundary score is a small real-shaped E1 p1_score. Read-only on real OUT files."""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from foothold_s2 import ex42_e1_cap_handoff as cap
from foothold_s2.scripts.ex42_e1_materialize_evidence import build_evidence
from foothold_s2.scripts.ex42_flag_baseline_chain import check_e1_gate
from foothold_s2.tests.test_ex42_e1_materialize_evidence_cpu import PLAN, _fixture, _sha, _write

DECISION = "de927fbf"


def _cell(judgement="FAIL", survival=64, envs=64, success=44):
    return {"judgement": judgement, "R": 0.89, "survival": survival, "envs": envs, "success": success, "command_mps": 0.1,
            "per_env_R": [0.9] * 64}


def _p1(plan, cp_sha, measurement, *, maintenance="PASS", judgment="FAIL", current=None, previous=None, iteration=1750):
    return {"state": "complete", "stage_id": "E1", "judgment": judgment, "plan_sha256": plan.sha256,
            "checkpoint_iteration": iteration, "checkpoint_sha256": cp_sha,
            "measurement": str(measurement), "measurement_sha256": _sha(measurement),
            "map_matrix": [{"map_mode": "eval_gt", "command": "fwd0.5", "role": "judge"}],
            "cell_judgments": {"eval_gt": {"fwd0.5": {"role": "judge", "judgment": "PASS" if maintenance == "PASS" else "FAIL"}}},
            "e1_exit": {"maintenance": {"current": maintenance, "previous": "HOLD"}, "judgement": judgment},
            "e1_exit_v2": {"current": {"judgement": judgment, "items": current if current is not None else
                                       {"low/L0/eval_gt/fwd0.1": _cell(), "low/L5/eval_pred/fwd0.1": _cell(success=40)}},
                           "previous": {"judgement": "HOLD", "items": previous if previous is not None else
                                        {"low/L5/eval_gt/side-0.2": _cell(success=49)}}}}


def _ledger(tmp_path, cp_sha, *, round_="m1750", sha8=None, decision=DECISION, tag=None, path=None, published=True, name="ledger"):
    repo = tmp_path / name
    repo.mkdir()
    rel = path or cap.LEDGER_PATH
    line = (f"2026-11-16 16:40\tlead\t{tag or cap.LINE_TAG} E1 · {round_} · {sha8 or cp_sha[:8]} · 근거 원장 {decision} · "
            f"「{cap.APPROVAL_PHRASE}」 · 유지 PASS")
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text("first line\n" + line + "\nlast line\n", encoding="utf-8")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    for argv in (["init", "-q"], ["add", rel], ["commit", "-q", "-m", "ledger"]):
        subprocess.run(["git", "-C", str(repo), *argv], check=True, env=env, capture_output=True)
    if published:                                  # the commit is on the published ledger branch (a remote ref of this copy)
        subprocess.run(["git", "-C", str(repo), "update-ref", f"refs/remotes/{cap.LEDGER_REMOTE_REF}", "HEAD"], check=True, env=env, capture_output=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    return repo, commit, line


def _setup(tmp_path, *, p1_kw=None, ledger_kw=None, decision=DECISION, p1_tamper=None):
    plan, run, gate, log, mesh, baseline, cp_sha = _fixture(tmp_path)
    measurement = run / "eval/m1750/measurement.json"
    _write(measurement, {"checkpoint_sha256": cp_sha, "judgement": "FAIL", "maintenance_source_sha256": plan.sha256})
    body = _p1(plan, cp_sha, measurement, **(p1_kw or {}))
    _write(measurement, {"checkpoint_sha256": cp_sha, "judgement": "FAIL", "maintenance_source_sha256": plan.sha256,
                         "cell_judgments": body["cell_judgments"], "e1_exit": body["e1_exit"], "e1_exit_v2": body["e1_exit_v2"]})
    body["measurement_sha256"] = _sha(measurement)
    if p1_tamper is not None:                       # an edit of the boundary score AFTER the measurement was written
        p1_tamper(body)
    p1_path = _write(run / "eval/m1750/p1_score.json", body)
    repo, commit, line = _ledger(tmp_path, cp_sha, **(ledger_kw or {}))
    out = run / "eval/m1750/e1_cap_handoff.json"
    cap.build_cap_handoff(p1_path, out, repo=repo, commit=commit, ledger_path=(ledger_kw or {}).get("path") or cap.LEDGER_PATH,
                          line=2, line_text=line, decision_id=decision)
    return plan, run, out, log, mesh, baseline, cp_sha, repo, p1_path, gate


def _evidence(run, out, log, mesh, baseline):
    return build_evidence(source_plan_path=PLAN, parent_manifest_path=run / "manifest.json", gate_receipt_path=out,
                          training_log_path=log, evaluation_mesh_path=mesh, w09_baseline_path=baseline)


def _fake_recount(measured, p1, policy_plan):
    """Stand-in for the E1 judge's raw-file recount on the small synthetic fixtures: the measurement's exit evidence is the score's."""
    extras = {k: measured.get(k) for k in ("e1_exit", "e1_exit_v2")}
    if any(p1.get(k) != v for k, v in extras.items()):
        raise ValueError("cap handoff boundary score differs from the exit evidence recounted from its measurement")


def _tamper_maintenance(body):
    """A hand-edited boundary score: the maintenance table made PASS while the measurement says HOLD."""
    body["cell_judgments"]["eval_gt"]["fwd0.5"]["judgment"] = "PASS"
    body["e1_exit"]["maintenance"]["current"] = "PASS"


def _tamper_survival(body):
    """A hand-edited boundary score: a missed cell's survival 59 made 60 (the floor) while the measurement says 59."""
    body["e1_exit_v2"]["current"]["items"]["low/L0/eval_gt/fwd0.1"]["survival"] = 60


@pytest.fixture(autouse=True)
def _ledger_env(monkeypatch, request):
    monkeypatch.delenv(cap.LEDGER_REPO_ENV, raising=False)
    if "real_files" not in request.node.name:           # the real-file tests run the real recount
        monkeypatch.setattr(cap, "_recount_exit", _fake_recount)


def test_an_approved_cap_handoff_gives_evidence_that_says_cap_handoff_and_never_a_pass(tmp_path, monkeypatch):
    plan, run, out, log, mesh, baseline, cp_sha, repo, _p1_path, _gate = _setup(tmp_path)
    monkeypatch.setenv(cap.LEDGER_REPO_ENV, str(repo))
    ev = _evidence(run, out, log, mesh, baseline)
    assert ev["gate_sha256"] == _sha(out) and ev["checkpoint_sha256"] == cp_sha and ev["source_stage"] == "E1"
    pred = ev["predecessor_exit"]
    assert pred["mode"] == "cap_handoff" and pred["receipt_sha256"] == _sha(out)
    assert pred["unmet_cells"] == ["current/low/L0/eval_gt/fwd0.1", "current/low/L5/eval_pred/fwd0.1", "previous/low/L5/eval_gt/side-0.2"]
    assert pred["ledger_line_sha256"] == json.loads(out.read_text())["lead_approval"]["line_sha256"]
    receipt = json.loads(out.read_text())
    assert receipt["state"] == "cap_handoff" and receipt["judgment"] == "CAP_HANDOFF" and "PASS" not in (receipt["state"], receipt["judgment"])


def test_the_pass_gate_path_is_untouched_and_a_failed_score_without_a_receipt_is_refused(tmp_path):
    plan, run, gate, log, mesh, baseline, cp_sha = _fixture(tmp_path)
    ev = build_evidence(source_plan_path=PLAN, parent_manifest_path=run / "manifest.json", gate_receipt_path=gate,
                        training_log_path=log, evaluation_mesh_path=mesh, w09_baseline_path=baseline)
    assert "predecessor_exit" not in ev                                    # a PASS gate writes no cap handoff key
    row = json.loads(gate.read_text())
    row["judgment"] = "FAIL"                                               # the same file as a failed score, no receipt
    gate.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="complete PASS"):
        build_evidence(source_plan_path=PLAN, parent_manifest_path=run / "manifest.json", gate_receipt_path=gate,
                       training_log_path=log, evaluation_mesh_path=mesh, w09_baseline_path=baseline)
    with pytest.raises(ValueError, match="complete E1 exit PASS"):
        check_e1_gate(gate, checkpoint_sha256=cp_sha, exit_updates=(1750,))


def test_check_e1_gate_reads_the_receipt_and_names_its_kind(tmp_path, monkeypatch):
    plan, run, out, log, mesh, baseline, cp_sha, repo, _p, _g = _setup(tmp_path)
    monkeypatch.setenv(cap.LEDGER_REPO_ENV, str(repo))
    got = check_e1_gate(out, checkpoint_sha256=cp_sha, exit_updates=(1750,))
    assert got["kind"] == "cap_handoff" and got["sha256"] == _sha(out)
    with pytest.raises(ValueError, match="another checkpoint"):
        check_e1_gate(out, checkpoint_sha256="0" * 64, exit_updates=(1750,))
    with pytest.raises(ValueError):                                        # not an exit boundary of the plan
        check_e1_gate(out, checkpoint_sha256=cp_sha, exit_updates=(250,))


@pytest.mark.parametrize("case,match", [
    ("other_checkpoint_line", "does not name"),       # the approval line carries another saved model sha
    ("other_round_line", "does not name"),            # the approval line is for another round
    ("no_decision_id", "does not name"),
    ("other_tag", "does not name"),
    ("maintenance_hold", "maintenance"),
    ("survival_59", "survival floor"),
    ("nothing_missed", "survival floor|no missed"),
    ("other_ledger_file", "registered decisions file"),
    ("local_only_commit", "not on origin"),
    ("p1_maintenance_edited", "cell judgments differ"),
    ("p1_survival_edited", "recounted from its measurement"),
    ("line_not_in_ledger", "not in the ledger"),
    ("line_text_edited", "differs from its sha"),
    ("unmet_value_forged", "missed-cell record"),
    ("measurement_sha", "boundary score|measurement"),
    ("state_complete", "not an E1 cap"),
    ("judgment_pass", "not an E1 cap"),
    ("p1_is_pass", "PASS"),
    ("no_ledger_repo", "ledger repository"),
])
def test_each_forgery_or_missing_condition_is_refused(tmp_path, monkeypatch, case, match):
    kw, ledger_kw, decision, tamper = {}, {}, DECISION, None
    if case == "other_checkpoint_line":
        ledger_kw = {"sha8": "deadbeef"}
    elif case == "other_round_line":
        ledger_kw = {"round_": "m1500"}
    elif case == "no_decision_id":
        ledger_kw = {"decision": "someone-else"}
    elif case == "other_tag":
        ledger_kw = {"tag": "[다른 줄]"}
    elif case == "maintenance_hold":
        kw = {"maintenance": "HOLD"}
    elif case == "survival_59":
        kw = {"current": {"low/L0/eval_gt/fwd0.1": _cell(survival=59)}}
    elif case == "nothing_missed":
        kw = {"current": {"low/L0/eval_gt/fwd0.1": _cell("PASS")}, "previous": {}}
    elif case == "other_ledger_file":
        ledger_kw = {"path": "other/decisions.tsv"}
    elif case == "local_only_commit":
        ledger_kw = {"published": False}
    elif case == "p1_maintenance_edited":
        kw = {"maintenance": "HOLD"}
        tamper = _tamper_maintenance
    elif case == "p1_survival_edited":
        kw = {"current": {"low/L0/eval_gt/fwd0.1": _cell(survival=59)}}
        tamper = _tamper_survival
    elif case == "p1_is_pass":
        kw = {"judgment": "PASS"}
    try:
        plan, run, out, log, mesh, baseline, cp_sha, repo, p1_path, _g = _setup(tmp_path, p1_kw=kw, ledger_kw=ledger_kw, decision=DECISION, p1_tamper=tamper)
    except ValueError:
        return                                                       # the builder's own read-back may already refuse
    monkeypatch.setenv(cap.LEDGER_REPO_ENV, str(repo))
    receipt = json.loads(out.read_text())
    if case == "line_not_in_ledger":
        text = receipt["lead_approval"]["line_text"] + " extra"
        receipt["lead_approval"].update(line_text=text, line_sha256=cap.hashlib.sha256(text.encode()).hexdigest())
    elif case == "line_text_edited":
        receipt["lead_approval"]["line_text"] += " "
    elif case == "unmet_value_forged":
        receipt["unmet_cells"][0]["success"] = 63
    elif case == "measurement_sha":
        receipt["measurement_sha256"] = "0" * 64
    elif case == "state_complete":
        receipt["state"] = "complete"
    elif case == "judgment_pass":
        receipt["judgment"] = "PASS"
    elif case == "no_ledger_repo":
        monkeypatch.delenv(cap.LEDGER_REPO_ENV)
    out.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        cap.read_cap_handoff(out, exit_updates=(1750,))
    with pytest.raises(ValueError):                                  # and the evidence builder refuses it too
        _evidence(run, out, log, mesh, baseline)


def test_a_receipt_next_to_a_pass_gate_is_not_the_way_in_when_the_boundary_passed(tmp_path, monkeypatch):
    """PASS wins: a boundary score that is PASS cannot be handed over with a cap receipt."""
    plan, run, out, log, mesh, baseline, cp_sha, repo, p1_path, gate = _setup(tmp_path, p1_kw={"judgment": "PASS"})
    with pytest.raises(ValueError, match="PASS"):
        cap.read_cap_handoff(out, exit_updates=(1750,), repo=repo)
    assert json.loads(gate.read_text())["judgment"] == "PASS"            # the PASS gate itself stays the way in (its tests are the old ones)


REAL = Path("/home/jay/data/foothold/s2_lab/ex42_main_20261116_115728/main/EX-42-B-E1-v28u_20261116_115728")


@pytest.mark.skipif(not (REAL / "eval/scores/m2500/p1_score.json").is_file(), reason="m2500 OUT not on this machine")
def test_the_recount_on_the_real_m2500_boundary_gives_the_missed_cells_planner_named_and_reads_nothing_else():
    p1 = json.loads((REAL / "eval/scores/m2500/p1_score.json").read_text())
    assert (p1["state"], p1["judgment"], p1["stage_id"], p1["checkpoint_iteration"]) == ("complete", "FAIL", "E1", 2500)
    failed, held = cap.unmet_cells(p1)
    cur = {c["item_id"]: (c["success"], c["survival"]) for c in failed if c["window"] == "current"}
    assert cur == {"low/L0/eval_gt/fwd0.1": (44, 64), "low/L5/eval_gt/fwd0.1": (40, 64),
                   "low/L0/eval_pred/fwd0.1": (43, 64), "low/L5/eval_pred/fwd0.1": (44, 64)}
    assert {c["item_id"]: c["success"] for c in failed if c["window"] == "previous"} == {
        "low/L5/eval_gt/side-0.2": 49, "low/L5/eval_pred/fwd0.1": 49}
    assert held == [] and cap.maintenance_judgement(p1) == "PASS" and cap.survival_below_floor(failed) == []
    assert _sha(REAL / "model_2500.pt").startswith("a6f6ef40")


# ---- the whole materialize chain on the known E1 fixture, with a cap receipt instead of a PASS gate ----
from foothold_s2.tests.test_ex42_materialize_cpu import dump, known, sha  # noqa: E402,F401


def _known_to_cap(known, tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "_recount_exit", lambda *a: None)          # the known fixture's measurement is a legacy six-case file
    run_dir = known["gate_receipt"].parent
    p1 = json.loads(known["gate_receipt"].read_text())
    cp_sha = p1["checkpoint_sha256"]
    p1["judgment"] = "FAIL"
    p1["e1_exit"] = {**p1["e1_exit"], "judgement": "FAIL"}
    p1["e1_exit_v2"] = {"current": {"judgement": "FAIL", "items": {"low/L0/eval_gt/fwd0.1": _cell()}},
                        "previous": {"judgement": "HOLD", "items": {}}}
    p1_path = run_dir / "p1_fail.json"
    dump(p1_path, p1)
    repo, commit, line = _ledger(tmp_path, cp_sha)
    receipt = run_dir / "e1_cap_handoff.json"
    cap.build_cap_handoff(p1_path, receipt, repo=repo, commit=commit, ledger_path=cap.LEDGER_PATH, line=2,
                          line_text=line, decision_id=DECISION)
    monkeypatch.setenv(cap.LEDGER_REPO_ENV, str(repo))
    ev = json.loads(known["evidence"].read_text())
    ev["gate_sha256"] = sha(receipt)
    ev["predecessor_exit"] = {"mode": "cap_handoff", "receipt_sha256": sha(receipt),
                              "ledger_line_sha256": json.loads(receipt.read_text())["lead_approval"]["line_sha256"],
                              "unmet_cells": ["current/low/L0/eval_gt/fwd0.1"]}
    dump(known["evidence"], ev)
    known["gate_receipt"] = receipt
    return receipt


def test_materialize_publishes_an_e1f_plan_from_a_cap_receipt_and_the_launch_proof_accepts_it(known, tmp_path, monkeypatch):
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    from foothold_s2.ex42_stage_materialize import materialize, validate_materialized_transition
    receipt = _known_to_cap(known, tmp_path, monkeypatch)
    result = materialize(**known)
    plan = EX42Plan.load(result["plan"])
    proof = validate_materialized_transition(plan, target_stage="E1F", gate_receipt_path=receipt, expected_gate_sha256=sha(receipt))
    assert proof["source_stage_id"] == "E1"
    launch = validate_automatic_stage_launch(plan, result["approvals"], target_stage="E1F", parent_manifest_path=known["parent_manifest"],
                                             gate_receipt_path=receipt, expected_gate_sha256=sha(receipt))
    assert launch["source_stage_id"] == "E1" and launch["automatic_launch_authorized"] is True


@pytest.mark.parametrize("change", ["no_cap_evidence", "evidence_other_receipt", "evidence_mode_pass", "no_ledger_repo", "receipt_edited"])
def test_materialize_refuses_a_cap_receipt_that_is_unbound_or_unreadable(known, tmp_path, monkeypatch, change):
    from foothold_s2.ex42_stage_materialize import materialize
    receipt = _known_to_cap(known, tmp_path, monkeypatch)
    ev = json.loads(known["evidence"].read_text())
    if change == "no_cap_evidence":
        del ev["predecessor_exit"]
    elif change == "evidence_mode_pass":
        ev["predecessor_exit"]["mode"] = "gate_pass"                    # the evidence must say cap_handoff, never a PASS
    elif change == "evidence_other_receipt":
        ev["predecessor_exit"]["receipt_sha256"] = "0" * 64
    elif change == "no_ledger_repo":
        monkeypatch.delenv(cap.LEDGER_REPO_ENV)
    elif change == "receipt_edited":
        row = json.loads(receipt.read_text())
        row["unmet_cells"][0]["success"] = 63
        dump(receipt, row)
        ev["gate_sha256"] = ev["predecessor_exit"]["receipt_sha256"] = sha(receipt)
    dump(known["evidence"], ev)
    with pytest.raises((ValueError, OSError, KeyError)):
        materialize(**known)
    assert not known["out"].exists()


LEDGER = Path("/home/jay/mai/wt/foothold-lab/lead-ledger-1303")
LEDGER_COMMIT = "2f213c2aba9b4df22a41f690552881e649296ccb"
LEDGER_PATH = "inbox/jay/20261104-ex41-restart/decisions.tsv"
LEDGER_LINE_SHA = "724bd459b329c80d4937a5ab43798e31b4c03e272abf5121f3380a64426e0218"
M2500_SHA = "a6f6ef408f1efe9aee024383513526612655b08b5d5d5c5ff71c9018aec94723"


@pytest.mark.skipif(not LEDGER.exists(), reason="ledger copy not on this machine")
def test_the_real_ledger_line_859_passes_the_reader_checks_for_m2500_and_not_for_another_model_or_round():
    """Read only: the line the team lead wrote for the m2500 handoff."""
    raw = cap._ledger_lines(LEDGER, LEDGER_COMMIT, LEDGER_PATH)[858]
    assert cap.hashlib.sha256(raw).hexdigest() == LEDGER_LINE_SHA
    approval = {"commit": LEDGER_COMMIT, "path": LEDGER_PATH, "line": 859, "line_text": raw.decode("utf-8"),
                "line_sha256": LEDGER_LINE_SHA, "decision_id": "de927fbf"}
    cap._check_approval(approval, LEDGER, iteration=2500, checkpoint_sha256=M2500_SHA)
    with pytest.raises(ValueError, match="does not name"):
        cap._check_approval(approval, LEDGER, iteration=2500, checkpoint_sha256="deadbeef" + "0" * 56)
    with pytest.raises(ValueError, match="does not name"):
        cap._check_approval(approval, LEDGER, iteration=2250, checkpoint_sha256=M2500_SHA)


@pytest.mark.skipif(not (REAL / "eval/scores/m2500/p1_score.json").is_file() or not LEDGER.exists(), reason="real m2500 files or ledger copy missing")
def test_real_files_the_real_recount_accepts_the_real_boundary_and_refuses_an_edited_copy(tmp_path):
    """Read only on the OUT and the ledger copy; the receipts are written into tmp. The real E1 judge recounts from the raw files."""
    p1_src = REAL / "eval/scores/m2500/p1_score.json"
    text = cap._ledger_lines(LEDGER, LEDGER_COMMIT, LEDGER_PATH)[858].decode("utf-8")
    ups = (1750, 2000, 2250, 2500, 2750)
    out = tmp_path / "ok.json"
    cap.build_cap_handoff(p1_src, out, repo=LEDGER, commit=LEDGER_COMMIT, ledger_path=LEDGER_PATH, line=859, line_text=text,
                          decision_id="de927fbf")
    assert cap.read_cap_handoff(out, exit_updates=ups, repo=LEDGER)["checkpoint_iteration"] == 2500
    edited = json.loads(p1_src.read_text())
    edited["e1_exit_v2"]["current"]["items"]["low/L0/eval_gt/fwd0.1"]["success"] = 52         # one missed cell made look like a pass
    edited_path = tmp_path / "p1_edited.json"
    edited_path.write_text(json.dumps(edited), encoding="utf-8")
    bad = tmp_path / "bad.json"
    cap.build_cap_handoff(edited_path, bad, repo=LEDGER, commit=LEDGER_COMMIT, ledger_path=LEDGER_PATH, line=859, line_text=text,
                          decision_id="de927fbf")
    with pytest.raises(ValueError, match="recounted from its measurement|raw|differs"):
        cap.read_cap_handoff(bad, exit_updates=ups, repo=LEDGER)


def test_the_automatic_launch_proof_reads_the_receipt_itself_and_refuses_a_wrong_ledger_line(known, tmp_path, monkeypatch):
    """Called directly (the transition replay stubbed away), the launch proof is the only reader: a wrong ledger refuses."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2 import ex42_stage_materialize as mat
    from foothold_s2.ex42_auto_authorization import validate_automatic_stage_launch
    receipt = _known_to_cap(known, tmp_path, monkeypatch)
    result = mat.materialize(**known)
    plan = EX42Plan.load(result["plan"])
    monkeypatch.setattr(mat, "validate_materialized_transition",
                        lambda *a, **k: {"source_plan_sha256": json.loads(receipt.read_text())["plan_sha256"], "source_stage_id": "E1"})
    other, _commit, _line = _ledger(tmp_path, "0" * 64, name="other_ledger")        # a ledger that does not hold the approval line
    monkeypatch.setenv(cap.LEDGER_REPO_ENV, str(other))
    with pytest.raises(ValueError, match="not in the ledger|not on origin|does not name"):
        validate_automatic_stage_launch(plan, result["approvals"], target_stage="E1F", parent_manifest_path=known["parent_manifest"],
                                        gate_receipt_path=receipt, expected_gate_sha256=sha(receipt))
