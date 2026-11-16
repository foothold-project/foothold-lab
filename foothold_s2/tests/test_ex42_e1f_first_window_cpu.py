"""E1F first window (m250) handed to E2 on the team lead's recorded approval (lead 2026-11-17 01:13, ledger 900/901).
The ledger is a throw-away git repository, the boundary score and measurement are small real-shaped files, the E1F judge's raw-file
recount is replaced by a stand-in (the real recount runs on the real m250 files in the receipt build). CPU only."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from types import SimpleNamespace

import pytest

from foothold_s2 import ex42_e1f_first_window as fw
from foothold_s2 import ex42_e1_cap_handoff as cap

CASES = ["flag_one_eval_gt", "flag_one_eval_pred", "flag_four_eval_gt", "flag_four_eval_pred"]
SHA = "13caeb4a" + "0" * 56
DECISION = "cf082122"


def _items():
    items = {"maintenance_current": {"judgement": "PASS"}, "flag_calibration": {"judgement": "PASS"},
             "maintenance_previous": {"judgement": "HOLD", "reason": fw.NO_PREVIOUS_REASON}}
    for case in CASES:
        items[f"{case}_current"] = {"judgement": "PASS", "valid_count": 64, "survival_count": 64}
        items[f"{case}_previous"] = {"judgement": "HOLD", "reason": fw.NO_PREVIOUS_REASON}
    return items


def test_the_first_window_items_pass_only_in_the_one_expected_shape():
    fw.check_first_window_items(_items(), CASES)


@pytest.mark.parametrize("mutate, why", [
    (lambda i: i["flag_one_eval_gt_current"].update(judgement="HOLD"), "a current cell on hold"),
    (lambda i: i["flag_one_eval_gt_current"].update(judgement="FAIL"), "a current cell failing"),
    (lambda i: i["flag_four_eval_pred_current"].update(survival_count=63), "survival 63"),
    (lambda i: i["flag_four_eval_pred_current"].update(valid_count=60), "valid count 60"),
    (lambda i: i["maintenance_current"].update(judgement="HOLD"), "maintenance current not PASS"),
    (lambda i: i["flag_calibration"].update(judgement="HOLD"), "calibration not PASS"),
    (lambda i: i["flag_one_eval_gt_previous"].update(judgement="PASS"), "a previous cell PASS (so it is not the first window)"),
    (lambda i: i["flag_one_eval_gt_previous"].update(reason="낮음"), "a previous cell on hold for another reason"),
    (lambda i: i["maintenance_previous"].update(judgement="PASS"), "maintenance previous PASS"),
    (lambda i: i["maintenance_previous"].update(judgement="FAIL"), "maintenance previous FAIL"),
    (lambda i: i.pop("flag_four_eval_gt_previous"), "a previous cell missing"),
    (lambda i: i.update(extra_item={"judgement": "HOLD"}), "an extra held item"),
])
def test_any_other_shape_is_refused(mutate, why):
    items = copy.deepcopy(_items())
    mutate(items)
    with pytest.raises((ValueError, KeyError)):
        fw.check_first_window_items(items, CASES)


def _ledger(tmp_path, *, round_="m250", sha8="13caeb4a", decision=DECISION, tag=fw.LINE_TAG, phrase=fw.APPROVAL_PHRASE,
            path=fw.LEDGER_PATH, published=True):
    repo = tmp_path / "ledger"
    repo.mkdir()
    line = f"2026-11-17 01:16\tlead\t{tag} E1F · {round_} · {sha8} · 근거 팀장 결정 {decision} · {phrase} · 생존 64/64"
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text("first\n" + line + "\nlast\n", encoding="utf-8")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    for argv in (["init", "-q"], ["add", path], ["commit", "-q", "-m", "ledger"]):
        subprocess.run(["git", "-C", str(repo), *argv], check=True, env=env, capture_output=True)
    if published:
        subprocess.run(["git", "-C", str(repo), "update-ref", f"refs/remotes/{fw.LEDGER_REMOTE_REF}", "HEAD"], check=True, env=env, capture_output=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    return repo, {"commit": commit, "path": path, "line": 2, "line_text": line,
                  "line_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(), "decision_id": decision}


def _check(repo, approval, **kw):
    fw._check_approval(approval, repo, iteration=kw.get("iteration", 250), checkpoint_sha256=kw.get("sha", SHA))


def test_the_published_ledger_line_is_accepted(tmp_path):
    repo, approval = _ledger(tmp_path)
    _check(repo, approval)


@pytest.mark.parametrize("kw, what", [
    ({"round_": "m500"}, "another round"),
    ({"sha8": "deadbeef"}, "another checkpoint"),
    ({"tag": "[승인 줄]"}, "no tag"),
    ({"phrase": "넘김"}, "no approval phrase"),
    ({"published": False}, "a local commit that is not on the published ledger branch"),
    ({"path": "inbox/other.tsv"}, "another ledger file"),
])
def test_a_ledger_line_that_does_not_name_this_approval_is_refused(tmp_path, kw, what):
    repo, approval = _ledger(tmp_path, **kw)
    with pytest.raises(ValueError):
        _check(repo, approval)


def test_an_edited_or_invented_ledger_line_is_refused(tmp_path):
    repo, approval = _ledger(tmp_path)
    fake = dict(approval, line_text=approval["line_text"] + " · 추가")
    fake["line_sha256"] = hashlib.sha256(fake["line_text"].encode("utf-8")).hexdigest()
    with pytest.raises(ValueError):
        _check(repo, fake)                                            # sha matches its text, but the ledger has no such line
    with pytest.raises(ValueError):
        _check(repo, dict(approval, line_sha256="0" * 64))            # text differs from its sha
    with pytest.raises(ValueError):
        _check(repo, dict(approval, decision_id=""))
    with pytest.raises(ValueError):
        _check(repo, {k: v for k, v in approval.items() if k != "decision_id"})
    with pytest.raises(ValueError):
        _check(None, approval)                                        # no ledger repository named


def _write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _world(tmp_path, monkeypatch, *, judgment="HOLD", iteration=250, items=None, interval=250, recount=True, state="complete"):
    plan_file = _write(tmp_path / "plan.json", {"evaluation": {"interval_updates": interval}})
    plan = SimpleNamespace(sha256=_sha(plan_file), document={"evaluation": {"interval_updates": interval}}, path=plan_file)
    cells = {"eval_gt": {"fwd0.1": {"judgment": "PASS", "role": "judge"}}}
    measurement = _write(tmp_path / "m/measurement.json", {"checkpoint_sha256": SHA, "cell_judgments": cells, "maintenance_source_sha256": plan.sha256,
                                                          "stage_exit": {"items": items or _items()}})
    p1 = _write(tmp_path / "m/p1_score.json", {
        "state": state, "stage_id": "E1F", "judgment": judgment, "plan_sha256": "a" * 64, "checkpoint_iteration": iteration,
        "checkpoint_sha256": SHA, "measurement": str(measurement), "measurement_sha256": _sha(measurement), "cell_judgments": cells,
        "map_matrix": [{"map_mode": "eval_gt", "command": "fwd0.1", "role": "judge"}],
        "evaluation_plan": {"path": str(plan_file), "sha256": plan.sha256}})
    repo, approval = _ledger(tmp_path)
    monkeypatch.setattr("foothold_s2.curriculum.ex42_prep.EX42Plan.load", staticmethod(lambda path: plan))
    adapter = SimpleNamespace(verify=lambda measured, a, b, plan=None: ({"x": 1} if recount else {}))
    monkeypatch.setattr("foothold_s2.ex42_stage_judges.adapter_for", lambda doc, stage: adapter)
    monkeypatch.setattr("foothold_s2.ex42_e1f_judge.contract", lambda doc: {"judge_cases": CASES})
    return p1, repo, approval


def _build(p1, repo, approval, out):
    return fw.build_first_window_handoff(p1, out, repo=repo, commit=approval["commit"], ledger_path=approval["path"], line=approval["line"],
                                         line_text=approval["line_text"], decision_id=approval["decision_id"])


def test_a_first_window_hold_reads_back_end_to_end(tmp_path, monkeypatch):
    p1, repo, approval = _world(tmp_path, monkeypatch)
    out = tmp_path / "m/first_window_handoff.json"
    row = _build(p1, repo, approval, out)
    assert row["hold_items"] == sorted(k for k, v in _items().items() if v["judgement"] == "HOLD")
    got = fw.read_first_window_handoff(out, repo=repo)
    assert got["kind"] == "first_window_handoff" and got["p1_score_path"] == str(p1.resolve())
    with pytest.raises(ValueError, match="never overwritten"):
        _build(p1, repo, approval, out)


@pytest.mark.parametrize("kw, why", [
    ({"judgment": "PASS"}, "a PASS boundary uses the PASS gate"),
    ({"judgment": "FAIL"}, "a FAIL boundary"),
    ({"state": "running"}, "a score that is not complete"),
    ({"iteration": 500}, "not the first window (m500)"),
    ({"recount": False}, "raw cells not recounted"),
])
def test_other_boundaries_are_refused(tmp_path, monkeypatch, kw, why):
    p1, repo, approval = _world(tmp_path, monkeypatch, **kw)
    out = tmp_path / "m/first_window_handoff.json"
    with pytest.raises(ValueError):
        _build(p1, repo, approval, out)
        fw.read_first_window_handoff(out, repo=repo)


def test_a_hand_edited_receipt_is_refused(tmp_path, monkeypatch):
    p1, repo, approval = _world(tmp_path, monkeypatch)
    out = tmp_path / "m/first_window_handoff.json"
    _build(p1, repo, approval, out)
    body = json.loads(out.read_text(encoding="utf-8"))
    for key, value in (("checkpoint_sha256", "f" * 64), ("checkpoint_iteration", 500), ("hold_items", []), ("measurement_sha256", "0" * 64)):
        edited = tmp_path / f"m/edit_{key}.json"
        _write(edited, dict(body, **{key: value}))
        with pytest.raises(ValueError):
            fw.read_first_window_handoff(edited, repo=repo)
    p1.write_text(p1.read_text(encoding="utf-8") + " ", encoding="utf-8")        # the boundary score changed after the receipt was cut
    with pytest.raises(ValueError, match="sha differs"):
        fw.read_first_window_handoff(out, repo=repo)


def test_a_receipt_that_does_not_read_back_is_not_left_behind(tmp_path, monkeypatch):
    p1, repo, approval = _world(tmp_path, monkeypatch)
    out = tmp_path / "m/first_window_handoff.json"
    wrong = dict(approval, decision_id="")
    with pytest.raises(ValueError):
        fw.main(["--p1-score", str(p1), "--out", str(out), "--ledger-repo", str(repo), "--ledger-commit", wrong["commit"],
                 "--ledger-path", wrong["path"], "--ledger-line", "2", "--ledger-line-text", wrong["line_text"], "--decision-id", "x"])
    assert not out.exists()


def _gate(tmp_path, **kw):
    body = {"state": "first_window_handoff", "judgment": "FIRST_WINDOW_HANDOFF", "stage_id": "E1F", "plan_sha256": "0" * 64}
    body.update(kw)
    return _write(tmp_path / "gate.json", body)


@pytest.mark.parametrize("kw", [{"judgment": "PASS"}, {"stage_id": "E1"}, {"plan_sha256": "0" * 64}, {"state": "complete", "judgment": "HOLD"}])
def test_evidence_and_budget_refuse_a_receipt_that_is_not_this_e1f_first_window(tmp_path, kw):
    from pathlib import Path
    from foothold_s2.ex42_stage_evidence import produce
    from foothold_s2.ex42_stage_handoff import measured_budget
    template = Path(__file__).resolve().parents[1] / "curriculum" / "ex42-prep.yaml"
    gate = _gate(tmp_path, **kw)
    manifest = _write(tmp_path / "manifest.json", {"progress": {"completed_updates": 250}})
    with pytest.raises(ValueError):
        produce(template_path=template, source_path=template, target="E2", gate_path=gate, manifest_path=manifest, output_dir=tmp_path / "out")
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        measured_budget(template, template, manifest, gate)
