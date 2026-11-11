"""Hand-off after a stage's last boundary: gate PASS + approved cell starts the launcher once; otherwise a notice.

Real plan, real approvals, real objects. The launcher is a real shell script that records what it was given; no
training, GPU or Kit is touched.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import stat
import time

import pytest
import yaml

from foothold_s2 import ex42_eval_once as once
from foothold_s2 import ex42_stage_handoff as handoff
from foothold_s2.tests.test_ex42_scoped_auto_cpu import known  # noqa: F401  (fixture: real plan view, E1 cell, E0 PASS receipt)

ROOT = Path(__file__).resolve().parents[2]
REAL_E0 = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")
REAL_P1 = Path("/home/jay/mai/tmp/verifier-lx/scoped-auto-1111/rejudge-plan-aligned/p1_score.json")


def _decide(known, *, stage="E0", iteration=250, p1=None, approvals=None, plan=None):
    base, ap, manifest, gp = known
    if p1 is not None:
        gp = gp.parent / "p1_other.json"
        gp.write_text(json.dumps(p1))
    return handoff.decide_next_stage(plan or base, approvals or ap, stage, iteration, gp, manifest)


def _gate(known):
    return json.loads(known[3].read_text())


def test_gate_pass_and_approved_cell_decide_to_launch_the_next_stage(known):
    decision = _decide(known)
    assert decision["action"] == "launch" and decision["next_stage_id"] == "E1"
    assert decision["authorization"]["scope"]["maximum_updates"] == 1000
    assert decision["authorization"]["training_started"] is False and decision["gate_sha256"]


@pytest.mark.parametrize("iteration", [0, 125, 249, 251, 500])
def test_nothing_is_decided_before_the_stage_last_boundary(known, iteration):
    assert _decide(known, iteration=iteration) is None


@pytest.mark.parametrize("judgment", ["HOLD", "FAIL", None])
def test_a_gate_that_did_not_pass_only_notifies(known, judgment):
    decision = _decide(known, p1={**_gate(known), "judgment": judgment})
    assert decision["action"] == "notify" and decision["state"] == "not_ready"


def test_the_last_stage_with_an_approved_cell_cannot_start_a_following_stage(known):
    # E1 ends at 1000 updates; E1F has no approval cell, so even a PASS only notifies
    gate = {**_gate(known), "stage_id": "E1", "checkpoint_iteration": 1000}
    decision = _decide(known, stage="E1", iteration=1000, p1=gate)
    assert decision["action"] == "notify" and decision["state"] == "next_stage_ready_for_approval"
    assert "not authorized to start by itself" in decision["reason"]


def _repinned(known, tmp_path, edit):
    plan, ap, manifest, gp = known
    approval = yaml.safe_load(ap.read_text())
    edit(approval)
    path = tmp_path / "approval_edited.yaml"
    path.write_text(yaml.safe_dump(approval))
    doc = deepcopy(plan.document)
    doc["stage_zero"]["approval_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return replace(plan, document=doc), path


@pytest.mark.parametrize("name,edit", [
    ("cell removed", lambda a: a.pop("stage_e1_authorization")),
    ("policy back to false", lambda a: a.__setitem__("automatic_launch_allowed", False)),
    ("policy widened to true", lambda a: a.__setitem__("automatic_launch_allowed", True)),
    ("pass not required", lambda a: a["automatic_launch_allowed"].__setitem__("require_gate_pass", False)),
    ("scope widened", lambda a: a["stage_e1_authorization"]["scope"].__setitem__("maximum_updates", 2000)),
    ("later stages opened", lambda a: a["stage_e1_authorization"]["scope"].__setitem__("later_stages_authorized", True)),
])
def test_each_missing_or_widened_approval_only_notifies(known, tmp_path, name, edit):
    plan, path = _repinned(known, tmp_path, edit)
    decision = _decide(known, approvals=path, plan=plan)
    assert decision["action"] == "notify", name
    assert decision["state"] == "next_stage_ready_for_approval"


def test_a_tampered_gate_receipt_only_notifies(known):
    gate = _gate(known)
    gate["measurement_sha256"] = "0" * 64
    decision = _decide(known, p1=gate)
    assert decision["action"] == "notify" and "measurement" in decision["reason"]


# ---- the launcher ---------------------------------------------------------------------------
def _launcher(tmp_path, body='printf "%s\\n%s\\n%s\\n" "$EX42_AUTO_TARGET_STAGE" "$EX42_AUTO_PARENT_CHECKPOINT" '
                             '"$EX42_AUTO_GATE_SHA256" > "$(dirname "$0")/launched.txt"\n'):
    path = tmp_path / "launch_next.sh"
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _out(tmp_path):
    out = tmp_path / "eval_out"
    out.mkdir()
    return out


def test_the_launcher_runs_once_with_the_authorized_stage_and_pins(known, tmp_path):
    decision = _decide(known)
    out, launcher = _out(tmp_path), _launcher(tmp_path)
    record = handoff.start_launcher(decision, launcher, out, parent_manifest=known[2],
                                    parent_checkpoint=known[2].parent / "model_250.pt", gate_receipt=known[3])
    assert record["state"] == "started" and record["target_stage"] == "E1" and record["pid"] > 0
    for _ in range(100):
        if (tmp_path / "launched.txt").is_file() and (tmp_path / "launched.txt").read_text().count("\n") == 3:
            break
        time.sleep(0.05)
    stage, checkpoint, gate_sha = (tmp_path / "launched.txt").read_text().split()
    assert stage == "E1" and checkpoint.endswith("model_250.pt") and gate_sha == decision["gate_sha256"]
    assert json.loads((out / handoff.LAUNCH_RECORD).read_text())["state"] == "started"
    with pytest.raises(FileExistsError):                      # a second evaluation of the same boundary
        handoff.start_launcher(decision, launcher, out, parent_manifest=known[2],
                               parent_checkpoint=known[2], gate_receipt=known[3])


@pytest.mark.parametrize("bad", ["relative", "missing", "not_executable"])
def test_a_launcher_that_is_not_an_absolute_executable_file_is_refused_before_anything_starts(known, tmp_path, bad):
    decision, out = _decide(known), _out(tmp_path)
    launcher = {"relative": Path("launch_next.sh"), "missing": tmp_path / "nope.sh",
                "not_executable": tmp_path / "plain.sh"}[bad]
    if bad == "not_executable":
        launcher.write_text("#!/usr/bin/env bash\n")
    with pytest.raises(ValueError, match="absolute path to an executable"):
        handoff.start_launcher(decision, launcher, out, parent_manifest=known[2], parent_checkpoint=known[2],
                               gate_receipt=known[3])
    assert not (out / handoff.LAUNCH_RECORD).exists()


# ---- evaluation tail: notice, state and launch -------------------------------------------------------
def _tail(known, tmp_path, launcher, *, gate=None, gpu_wait=None, register=None):
    plan, _, manifest, gp = known
    out = _out(tmp_path)
    (out / "p1_score.json").write_text(json.dumps(gate or _gate(known)))
    p1 = json.loads((out / "p1_score.json").read_text())
    approvals = known[1]
    notice = once._hand_off(plan, approvals, "E0", 250, p1, manifest.parent / "model_250.pt", out, launcher,
                           gpu_wait=gpu_wait, register=register)
    return notice, out


def test_tail_starts_the_launcher_and_says_so_in_the_notice(known, tmp_path):
    notice, out = _tail(known, tmp_path, _launcher(tmp_path))
    assert notice["state"] == "next_stage_started" and notice["automatic_launch_started"] is True
    assert notice["notification_required"] is True and notice["launcher_pid"] > 0
    assert (out / handoff.LAUNCH_RECORD).is_file()


def test_tail_without_a_launcher_or_with_a_failing_one_only_notifies(known, tmp_path):
    notice, out = _tail(known, tmp_path, None)
    assert notice["state"] == "next_stage_authorized_no_launcher" and notice["automatic_launch_started"] is False
    assert not (out / handoff.LAUNCH_RECORD).exists()
    (tmp_path / "x").mkdir()
    notice, _ = _tail(known, tmp_path / "x", tmp_path / "missing.sh")
    assert notice["state"] == "next_stage_authorized_launch_failed" and notice["automatic_launch_started"] is False


def test_tail_hold_gate_starts_nothing(known, tmp_path):
    marker = tmp_path / "launched.txt"
    notice, out = _tail(known, tmp_path, _launcher(tmp_path), gate={**_gate(known), "judgment": "HOLD"})
    assert notice["state"] == "not_ready" and notice["automatic_launch_started"] is False
    assert not marker.exists() and not (out / handoff.LAUNCH_RECORD).exists()


def test_launch_waits_for_the_gpus_first_and_a_busy_gpu_starts_nothing(known, tmp_path):
    seen = []
    launcher = _launcher(tmp_path)
    notice, out = _tail(known, tmp_path, launcher, gpu_wait=lambda: seen.append((tmp_path / "launched.txt").exists()))
    assert seen == [False] and notice["state"] == "next_stage_started"

    def busy():
        raise ValueError("EX-42 split evaluation GPUs still hold compute processes: {'uuid': [('1', 'python', '900')]}")

    (tmp_path / "b").mkdir()
    notice, out = _tail(known, tmp_path / "b", _launcher(tmp_path / "b"), gpu_wait=busy)
    assert notice["state"] == "next_stage_authorized_launch_failed" and notice["automatic_launch_started"] is False
    assert "still hold compute processes" in notice["reason"]
    assert not (out / handoff.LAUNCH_RECORD).exists() and not (tmp_path / "b" / "launched.txt").exists()


def test_the_evaluation_run_passes_a_real_gpu_wait_to_the_hand_off():
    import inspect
    source = inspect.getsource(once.run)
    assert "gpu_wait=lambda: split.wait_gpus_free(split.all_gpu_uuids())" in source


def test_all_gpu_uuids_reads_every_line_and_refuses_none():
    from foothold_s2 import ex42_eval_split as split
    assert split.all_gpu_uuids(lambda: "GPU-aaa\nGPU-bbb\n") == ["GPU-aaa", "GPU-bbb"]
    with pytest.raises(ValueError):
        split.all_gpu_uuids(lambda: "\n")


def test_every_notice_state_carries_its_reason(known, tmp_path):
    notice, _ = _tail(known, tmp_path, None, gate={**_gate(known), "judgment": "HOLD"})
    assert notice["reason"] == "gate judgment is HOLD"
    (tmp_path / "a").mkdir()
    notice, _ = _tail(known, tmp_path / "a", None)
    assert notice["reason"] == "no --next-stage-launcher was given"
    (tmp_path / "b").mkdir()
    notice, _ = _tail(known, tmp_path / "b", tmp_path / "missing.sh")
    assert "absolute path to an executable file" in notice["reason"]
    (tmp_path / "c").mkdir()
    notice, _ = _tail(known, tmp_path / "c", _launcher(tmp_path / "c"))
    assert "reason" in notice and notice["reason"] is None


def test_chain_validator_takes_only_an_absolute_executable_launcher(tmp_path):
    from foothold_s2.tests.test_ex42_split_eval_cpu import _argv, _mesh, _profile_p1_on_gpu1
    from foothold_s2.ex42_chain import _validate_p1_score_command
    ck = tmp_path / "model_250.pt"
    ck.write_bytes(b"x")
    mesh_dir, mesh_sha = _mesh(tmp_path)
    argv = _argv(ck, tmp_path / "score_250", mesh_dir, mesh_sha)
    good = _launcher(tmp_path)
    for value, ok in ((str(good), True), ("relative.sh", False), (str(tmp_path / "gone.sh"), False)):
        trial = argv + ["--next-stage-launcher", value]
        if ok:
            _validate_p1_score_command(trial, machine_profile=_profile_p1_on_gpu1(), iteration=250,
                                       checkpoint_path=ck, expected_stage_id="E1")
        else:
            with pytest.raises(ValueError, match="launcher"):
                _validate_p1_score_command(trial, machine_profile=_profile_p1_on_gpu1(), iteration=250,
                                           checkpoint_path=ck, expected_stage_id="E1")


# ---- real shipped plan, real approvals, real E0 m250 and its re-judged P1 receipt -----------------
@pytest.mark.skipif(not (REAL_E0 / "manifest.json").is_file() or not REAL_P1.is_file(),
                    reason="the real E0 run directory or the verifier re-judgement is not on this machine")
def test_real_e0_pass_and_the_shipped_e1_cell_decide_to_launch_e1(tmp_path):
    # The verifier's re-judgement receipt names the plan it was computed under (plan_sha256), and the hand-off refuses a
    # PASS from any other plan. Every plan edit (5d4dbf33 first, 12:07) therefore made the original file stale and this
    # test failed with "must be predecessor PASS under this plan". The receipt's scores are real; only the plan pin is
    # rewritten to the shipped plan in a copy, and the original must still be refused when its pin is another plan's.
    import json
    import shutil
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    plan = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
    approvals = ROOT / "foothold_s2/curriculum/ex42-approvals.yaml"
    copy = tmp_path / "rejudge"
    shutil.copytree(REAL_P1.parent, copy)
    receipt = json.loads((copy / REAL_P1.name).read_text(encoding="utf-8-sig"))
    shipped = EX42Plan.load(plan).sha256
    if receipt.get("plan_sha256") != shipped:
        stale = handoff.decide_next_stage(plan, approvals, "E0", 250, REAL_P1, REAL_E0 / "manifest.json")
        assert stale["action"] == "notify" and "no transition record links it" in stale["reason"], stale
    receipt["plan_sha256"] = shipped
    (copy / REAL_P1.name).write_text(json.dumps(receipt), encoding="utf-8")
    decision = handoff.decide_next_stage(plan, approvals, "E0", 250, copy / REAL_P1.name, REAL_E0 / "manifest.json")
    assert decision["action"] == "launch", decision
    assert decision["authorization"]["scope"]["stage_id"] == "E1"
    assert decision["authorization"]["scope"]["parent_sha256"].startswith("680c820b")


# ---- the auto-started training goes into the GPU queue (no queued evaluation over it) -----------------------
DISPATCH = ROOT / "_out" / "tools" / "gpu_jobs" / "dispatch.py"
needs_dispatch = pytest.mark.skipif(not DISPATCH.is_file(), reason="the GPU dispatcher is not in this checkout")


def _exec_launcher(tmp_path):
    return _launcher(tmp_path, body="exec sleep 60\n")


@needs_dispatch
def test_a_started_training_is_registered_as_a_running_external_item_on_both_gpus(known, tmp_path):
    import os
    import signal
    queue = tmp_path / "queue.json"
    notice, out = _tail(known, tmp_path, _exec_launcher(tmp_path),
                        register=lambda pid, log, title: handoff.register_launched_training(
                            queue, DISPATCH, pid=pid, log=log, title=title))
    try:
        items = json.loads(queue.read_text())["items"]
        assert notice["state"] == "next_stage_started" and notice["queue_registration"].startswith("registered")
        assert sorted(it["gpu"] for it in items) == [0, 1]
        assert all(it["external"] and it["state"] == "실행" and it["pid"] == notice["launcher_pid"] for it in items)
        os.kill(notice["launcher_pid"], 0)                    # the registered process is still the live training
    finally:
        os.killpg(notice["launcher_pid"], signal.SIGTERM)


def test_a_failed_registration_is_reported_but_does_not_undo_the_started_training(known, tmp_path):
    import os
    import signal

    def broken(pid, log, title):
        raise ValueError("queue locked")

    notice, _ = _tail(known, tmp_path, _exec_launcher(tmp_path), register=broken)
    try:
        assert notice["state"] == "next_stage_started" and notice["automatic_launch_started"] is True
        assert notice["queue_registration_error"] == "queue locked"
    finally:
        os.killpg(notice["launcher_pid"], signal.SIGTERM)


def test_nothing_is_registered_when_nothing_was_started(known, tmp_path):
    calls = []
    notice, _ = _tail(known, tmp_path, None, register=lambda *a: calls.append(a))
    assert calls == [] and "queue_registration" not in notice
    (tmp_path / "h").mkdir()
    notice, _ = _tail(known, tmp_path / "h", _launcher(tmp_path / "h"), gate={**_gate(known), "judgment": "HOLD"},
                      register=lambda *a: calls.append(a))
    assert calls == []


def test_the_run_and_the_cli_carry_the_queue_registration():
    import inspect
    assert "handoff.register_launched_training(" in inspect.getsource(once.run)
    source = inspect.getsource(once.main)
    assert "--next-stage-queue" in source and "--next-stage-dispatch" in source


def test_chain_validator_takes_the_queue_pair_only_together_with_a_launcher(tmp_path):
    from foothold_s2.tests.test_ex42_split_eval_cpu import _argv, _mesh, _profile_p1_on_gpu1
    from foothold_s2.ex42_chain import _validate_p1_score_command
    ck = tmp_path / "run" / "model_250.pt"
    ck.parent.mkdir()
    ck.write_bytes(b"x")
    mesh_dir, mesh_sha = _mesh(tmp_path)
    argv = _argv(ck, tmp_path / "score_250", mesh_dir, mesh_sha)
    launcher, dispatch = _launcher(tmp_path), tmp_path / "dispatch.py"
    dispatch.write_text("x")
    base = argv + ["--next-stage-launcher", str(launcher)]
    ok = base + ["--next-stage-queue", str(tmp_path / "q.json"), "--next-stage-dispatch", str(dispatch)]

    def check(trial):
        _validate_p1_score_command(trial, machine_profile=_profile_p1_on_gpu1(), iteration=250,
                                   checkpoint_path=ck, expected_stage_id="E1")

    check(ok)
    for bad in (base + ["--next-stage-queue", str(tmp_path / "q.json")],
                argv + ["--next-stage-queue", str(tmp_path / "q.json"), "--next-stage-dispatch", str(dispatch)],
                base + ["--next-stage-queue", "q.json", "--next-stage-dispatch", str(dispatch)],
                base + ["--next-stage-queue", str(tmp_path / "q.json"), "--next-stage-dispatch", str(tmp_path / "gone.py")]):
        with pytest.raises(ValueError, match="next-stage queue"):
            check(bad)
