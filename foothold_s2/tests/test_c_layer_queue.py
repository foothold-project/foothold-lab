"""Known-input CPU tests for D48 reset-derived C-layer capture."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2.eval import c_layer_queue as q
from foothold_s2.eval import video_style
from foothold_s2.eval.video25 import record_c_layer


KINDS = {
    "continuous": ["pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
                   "hf_pyramid_slope", "hf_pyramid_slope_inv", "stage_stairs"],
    "sparse": ["stepping_stones_low", "stepping_stones_high", "balance_beams",
               "stepping_beams", "gaps"],
}


@pytest.fixture(autouse=True)
def fake_frame_decoder(monkeypatch):
    """Queue fixtures use byte strings, while frame statistics are tested separately."""
    monkeypatch.setattr(q, "audit_video", lambda *_a, **_k: {"pass": True, "frames": 450})
    def simulated_recorder(argv, log_path, env, **_kwargs):
        with log_path.open("wb") as log:
            result = q.subprocess.run(argv, env=env, stdout=log, stderr=subprocess.STDOUT)
        return result.returncode
    monkeypatch.setattr(q, "run_recorder", simulated_recorder)
    monkeypatch.setattr(q, "_gpu_gate", lambda _plan, _job: {"job": "c-layer", "admit_next_unit": True})


def fixture(tmp_path: Path, *, complete: bool = True):
    checkpoint = tmp_path / "model_8000.pt"
    recorder = tmp_path / "record.py"
    composer = tmp_path / "compose.py"
    checkpoint.write_bytes(b"checkpoint")
    recorder.write_bytes(b"# C_LAYER_SEED_V1\n")
    composer.write_bytes(b'VIDEO_RULE_VERSION = "v3.4-D168"\n')
    overlay = tmp_path / "overlay_25e.py"
    overlay.write_bytes(b"# fixed overlay\n")
    rows = []
    cells = q.inventory(KINDS) if complete else [("boxes", 2, "eval_gt")]
    for kind, level, mode in cells:
        label = video_style.capture_name("EX40", kind, level, 7, 8000, segment=mode)
        rows.append({"kind": kind, "level": level, "map_mode": mode, "env_id": 7,
                     "label": label, "seeds": [42, 43],
                     "policy": {"experiment": "SB", "source_root": str(tmp_path),
                                "source_profile": "C76", "source_head": "a" * 40,
                                "source_recorder_sha256": "b" * 64, "selection_role": "c_layer",
                                "terrain_set": ("fixed64" if kind in KINDS["continuous"] else "sparse50"),
                                "fixed_terrain": True, "fixed_level": level,
                                "geometry_seed": 20261026,
                                "command": [1.0, 0.0, 0.0], "duration_s": 18.0,
                                "seed": "{seed}", "c_layer_reference": True,
                                "hide_others": True,
                                "checkpoint_sha256": q.sha256(checkpoint), "envs": 64,
                                "map_mode": mode, "env_id": 7, "kind": kind, "col": 4},
                     "recorder_argv": ["python", str(recorder), "--policy", "{policy}",
                                       "--checkpoint", str(checkpoint), "--label", "{label}",
                                       "--mp4", "{mp4}", "--device", "cuda:1"]})
    plan = {"status": "approved_canon", "canon_label": "EX40", "iteration": 8000,
            "kinds": KINDS, "checkpoint": str(checkpoint), "checkpoint_sha256": q.sha256(checkpoint),
            "priority_markers": {name: str(tmp_path / (name + ".busy"))
                                 for name in ("training", "evaluation", "a_layer")},
            "recorder": str(recorder), "recorder_sha256": q.sha256(recorder),
            "composer": str(composer), "composer_sha256": q.sha256(composer), "jobs": rows}
    plan["playlist_dir"] = str(tmp_path / "_playlists")
    plan["queue"] = str(Path(q.__file__).resolve())
    plan["queue_sha256"] = q.sha256(Path(q.__file__).resolve())
    gpu_tool = Path(__file__).resolve().parents[2] / "_out/tools/gpu_jobs/gpu_jobs.py"
    gpu_config = Path(__file__).resolve().parents[2] / "_out/tools/gpu_jobs/jobs.json"
    plan["gpu_jobs_tool"], plan["gpu_jobs_tool_sha256"] = str(gpu_tool), q.sha256(gpu_tool)
    plan["gpu_jobs_config"], plan["gpu_jobs_config_sha256"] = str(gpu_config), q.sha256(gpu_config)
    plan["runtime_sources_sha256"] = {
        str(path): q.sha256(path) for path in (
            overlay,
            *(Path(q.__file__).parent / name for name in
              ("c_layer_segmentation.py", "c_layer_frame_audit.py", "video_rule.py")),
        )
    }
    return plan, rows


def make_capture(mp4: Path, plan: dict, row: dict, seed: int, resets: int):
    mp4.write_bytes(b"cpu fake video")
    mp4.with_name("review.json").write_text(json.dumps({
        "checkpoint_sha256": plan["checkpoint_sha256"], "label": row["label"], "seed": seed,
        "selected_environment": {"env_id": 7, "kind": row["kind"], "level": row["level"]},
        "map_modes": {"map_mode": {"requested": row["map_mode"]}},
        "style": {"style_id": video_style.STYLE_ID},
        "frames": 450, "fps": 25, "duration_s": 18.0, "resets": resets,
        "robot_instance_evidence": [{"selected_robot_pixels": 1000,
                                     "other_robot_pixels": 0} for _ in range(450)],
    }), encoding="utf-8")
    done = np.zeros(900, dtype=bool)
    done[:resets] = True
    np.savez(mp4.with_name("review_feet.npz"), t=np.arange(900) * .02, dt=.02, done=done)


def fake_capture(plan: dict, outcomes: list[int]):
    calls = []

    def run(argv, **_kwargs):
        if argv[0] == "ffprobe":
            return subprocess.CompletedProcess(argv, 0, '{"streams":[{"nb_read_frames":"450"}]}', "")
        if "--plan-only" in argv:
            policy = json.loads(argv[argv.index("--policy") + 1])
            preview = {"spec": policy, "target_frames": 450,
                       "checkpoint_profile": {"checkpoint_sha256": plan["checkpoint_sha256"]}}
            return subprocess.CompletedProcess(argv, 0, json.dumps(preview), "")
        if argv[1] == plan["composer"]:
            styled = Path(argv[argv.index("--out") + 1])
            styled.write_bytes(b"composed HUD video")
            styled.with_suffix(".json").write_text(json.dumps({
                "sha256": q.sha256(styled), "frames": 450, "fps": 25,
                "video_rule_version": q.VIDEO_RULE_VERSION,
                "composer_sha256": plan["composer_sha256"],
                "checkpoint_sha256": plan["checkpoint_sha256"],
                "capture": argv[argv.index("--capture") + 1],
            }), encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0)
        calls.append(argv)
        row = plan["jobs"][0]
        mp4 = Path(argv[argv.index("--mp4") + 1])
        policy = json.loads(argv[argv.index("--policy") + 1])
        make_capture(mp4, plan, row, policy["seed"], outcomes[len(calls) - 1])
        return subprocess.CompletedProcess(argv, 0)

    return run, calls


def test_no_progress_is_failure_without_success_receipt(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path)
    fake_run, _ = fake_capture(plan, [0])
    monkeypatch.setattr(q.subprocess, "run", fake_run)
    def timed_out(_argv, log_path, _env, **_kwargs):
        log_path.write_text("Kit started, no frame\n", encoding="utf-8")
        raise ValueError("recorder_no_progress_timeout after 600s; last_frame=0")
    monkeypatch.setattr(q, "run_recorder", timed_out)
    out = tmp_path / "out"
    result = q.run_one(plan, out=out, high_priority_markers=[], only_cell=q._slot(rows[0]))
    assert result["state"] == "capture_failed"
    assert "no_progress_timeout" in result["reason"]
    assert not list((out / "receipts").glob("*_success.json"))
    assert not list((out / "receipts").glob("*_fail.json"))


def test_recorder_child_env_matches_seq_video_block(tmp_path):
    python = tmp_path / "isaac311" / "python.exe"
    parent = {"PATH": "original-path", "CUDA_VISIBLE_DEVICES": "0",
              "OMNI_KIT_ACCEPT_EULA": "NO"}
    child = q.recorder_child_env(str(python), parent)
    prefix = str(python.parent)
    expected_paths = [prefix, *(str(python.parent / part) for part in
                                ("Library/mingw-w64/bin", "Library/usr/bin",
                                 "Library/bin", "Scripts", "bin"))]
    assert child["PATH"] == os.pathsep.join([*expected_paths, "original-path"])
    assert {key: child[key] for key in ("CONDA_PREFIX", "OMNI_KIT_ACCEPT_EULA",
                                         "CUDA_DEVICE_ORDER", "PYTHONUNBUFFERED",
                                         "KMP_DUPLICATE_LIB_OK", "PYTHONUTF8")} == {
        "CONDA_PREFIX": prefix, "OMNI_KIT_ACCEPT_EULA": "YES",
        "CUDA_DEVICE_ORDER": "PCI_BUS_ID", "PYTHONUNBUFFERED": "1",
        "KMP_DUPLICATE_LIB_OK": "TRUE", "PYTHONUTF8": "1"}
    assert "CUDA_VISIBLE_DEVICES" not in child
    assert parent["CUDA_VISIBLE_DEVICES"] == "0"


def test_real_python_child_observes_kit_env_without_visible_device():
    child_env = q.recorder_child_env(sys.executable,
                                    {**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    keys = ("CONDA_PREFIX", "OMNI_KIT_ACCEPT_EULA", "CUDA_DEVICE_ORDER",
            "PYTHONUNBUFFERED", "KMP_DUPLICATE_LIB_OK", "CUDA_VISIBLE_DEVICES")
    script = "import json,os;print(json.dumps({k:os.environ.get(k) for k in " + repr(keys) + "}))"
    completed = subprocess.run([sys.executable, "-c", script], env=child_env,
                               capture_output=True, text=True, check=True)
    observed = json.loads(completed.stdout)
    assert observed == {"CONDA_PREFIX": str(Path(sys.executable).parent),
                        "OMNI_KIT_ACCEPT_EULA": "YES", "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
                        "PYTHONUNBUFFERED": "1", "KMP_DUPLICATE_LIB_OK": "TRUE",
                        "CUDA_VISIBLE_DEVICES": None}


def test_dispatcher_child_imports_real_source_from_unrelated_cwd(tmp_path):
    source_root = Path(__file__).resolve().parents[2]
    child_env = q.recorder_child_env(
        sys.executable, {**os.environ, "PYTHONPATH": ""}, source_root=source_root)
    completed = subprocess.run(
        [sys.executable, "-c", "import foothold_s2; print(foothold_s2.__file__)"],
        cwd=tmp_path, env=child_env, capture_output=True, text=True, check=True)
    assert str(source_root).lower() in completed.stdout.lower()


def test_recorder_preflight_capture_and_composer_receive_same_kit_env(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path)
    python = tmp_path / "isaac311" / "python.exe"
    rows[0]["recorder_argv"][0] = str(python)
    real_fake, _ = fake_capture(plan, [0])
    seen = []

    def capture_run(argv, **kwargs):
        if argv[0] == str(python):
            seen.append((argv, kwargs.get("env")))
        return real_fake(argv, **kwargs)

    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    monkeypatch.setattr(q.subprocess, "run", capture_run)
    result = q.run_one(plan, out=tmp_path / "out", high_priority_markers=[],
                       only_cell=q._slot(rows[0]))
    assert result["event"] == "captured"
    assert len(seen) == 3
    assert "--plan-only" in seen[0][0]
    assert "--plan-only" not in seen[1][0]
    assert seen[2][0][1] == plan["composer"]
    for _, env in seen:
        assert env["CONDA_PREFIX"] == str(python.parent)
        assert env["OMNI_KIT_ACCEPT_EULA"] == "YES"
        assert env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
        assert "CUDA_VISIBLE_DEVICES" not in env


def test_plan_rejects_wrong_or_mixed_cuda_device(tmp_path):
    plan, rows = fixture(tmp_path)
    rows[0]["recorder_argv"][-1] = "cpu"
    with pytest.raises(ValueError, match="cuda:0 or cuda:1"):
        q.validate_plan(plan)
    rows[0]["recorder_argv"][-1] = "cuda:0"
    with pytest.raises(ValueError, match="mixes recorder GPU"):
        q.validate_plan(plan)


def test_traceback_in_zero_exit_child_log_is_technical_failure(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path)
    fake_run, _ = fake_capture(plan, [0])

    def with_traceback(argv, **kwargs):
        result = fake_run(argv, **kwargs)
        if argv[1] == plan["recorder"] and "--plan-only" not in argv:
            kwargs["stdout"].write(b"Traceback (most recent call last):\nValueError: hidden\n")
        return result

    monkeypatch.setattr(q.subprocess, "run", with_traceback)
    out = tmp_path / "out"
    result = q.run_one(plan, out=out, high_priority_markers=[], only_cell=q._slot(rows[0]))
    assert result["state"] == "capture_failed"
    assert "Traceback" in result["reason"]
    assert not list(out.glob("*.mp4"))
    assert q._summary(out, rows[0])["attempts"] == 0


def test_inventory_and_seed_gate(tmp_path):
    plan, rows = fixture(tmp_path)
    assert len(q.inventory(KINDS)) == 216
    assert q.validate_plan(plan)["ready"] == 216
    rows[0]["seeds"] = [42, 42]
    with pytest.raises(ValueError, match="distinct"):
        q.validate_plan(plan)
    rows[0]["seeds"] = [42, 43, 44]
    with pytest.raises(ValueError, match="one to two"):
        q.validate_plan(plan)
    rows[0]["seeds"] = [42, 43]
    Path(plan["recorder"]).write_bytes(b"legacy seed 42 only")
    plan["recorder_sha256"] = q.sha256(Path(plan["recorder"]))
    with pytest.raises(ValueError, match="variable-seed"):
        q.validate_plan(plan)


def test_old_composer_and_missing_robot_visibility_are_held(tmp_path):
    plan, rows = fixture(tmp_path)
    rows[0]["policy"].pop("hide_others")
    with pytest.raises(ValueError, match="hide other robots"):
        q.validate_plan(plan)
    rows[0]["policy"]["hide_others"] = True
    composer = Path(plan["composer"])
    composer.write_text('VIDEO_RULE_VERSION = "v2"\n', encoding="utf-8")
    plan["composer_sha256"] = q.sha256(composer)
    with pytest.raises(ValueError, match="older video rule"):
        q.validate_plan(plan)


def test_changed_segmentation_or_overlay_source_holds_before_capture(tmp_path):
    plan, _rows = fixture(tmp_path)
    assert q.validate_plan(plan)["ready"] == 216
    overlay = tmp_path / "overlay_25e.py"
    overlay.write_bytes(b"# changed while plan was pending\n")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        q.validate_plan(plan)
    plan["runtime_sources_sha256"][str(overlay)] = q.sha256(overlay)
    assert q.validate_plan(plan)["ready"] == 216
    plan["runtime_sources_sha256"].pop(str(overlay))
    with pytest.raises(ValueError, match="runtime source inventory"):
        q.validate_plan(plan)


def test_playlist_rejects_receipt_without_v3_rule(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path)
    run, _ = fake_capture(plan, [0])
    monkeypatch.setattr(q.subprocess, "run", run)
    out = tmp_path / "out"
    result = q.run_one(plan, out=out, high_priority_markers=[], only_cell=q._slot(rows[0]))
    assert result["event"] == "captured"
    receipt = next((out / "receipts").glob("*_success.json"))
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data.pop("video_rule_version")
    receipt.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="video_rule_hold"):
        q.publish_playlists(plan, out)


def test_partial_plan_cannot_launch(tmp_path):
    plan, _ = fixture(tmp_path, complete=False)
    assert q.validate_plan(plan)["missing"] == 215
    with pytest.raises(ValueError, match="216"):
        q.run_one(plan, out=tmp_path / "out", high_priority_markers=[])


def test_only_cell_keeps_full_plan_gate_and_stops_after_target(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path)
    run, calls = fake_capture(plan, [0])
    monkeypatch.setattr(q.subprocess, "run", run)
    target = q._slot(rows[0])
    out = tmp_path / "out"
    result = q.run_one(plan, out=out, high_priority_markers=[], only_cell=target)
    assert result["event"] == "captured" and result["cell"] == target
    assert len(calls) == 1
    with pytest.raises(ValueError, match="absent"):
        q.run_one(plan, out=out, high_priority_markers=[], only_cell="unknown_L0_eval_gt")
    rows.pop()
    with pytest.raises(ValueError, match="216"):
        q.run_one(plan, out=out, high_priority_markers=[], only_cell=target)


def test_two_outcomes_publish_canonical_without_eval_suffix(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path)
    run, calls = fake_capture(plan, [0, 1])
    monkeypatch.setattr(q.subprocess, "run", run)
    out = tmp_path / "out"
    first = q.run_one(plan, out=out, high_priority_markers=[])
    second = q.run_one(plan, out=out, high_priority_markers=[])
    assert first["event"] == second["event"] == "captured"
    assert second["cell"] == first["cell"]
    assert second["state"] == "complete"
    assert len(calls) == 2
    assert [json.loads(argv[argv.index("--policy") + 1])["seed"] for argv in calls] == [42, 43]
    receipts = list((out / "receipts").glob("*_success.json")) + list((out / "receipts").glob("*_fail.json"))
    assert len(receipts) == 2
    assert all(json.loads(p.read_text(encoding="utf-8"))["canonical"] is True for p in receipts)
    assert all("evalfail" not in p.name for p in out.glob("*.mp4"))
    assert not (out / "attempts" / first["cell"] / "03").exists()
    assert rows[0]["label"] not in [p.stem for p in out.glob("*.mp4")]


def test_first_pass_seeks_one_success_and_keeps_failed_attempt_only(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path)
    plan["target_results"] = ["success"]
    run, calls = fake_capture(plan, [1, 0])
    monkeypatch.setattr(q.subprocess, "run", run)
    out = tmp_path / "out"
    first = q.run_one(plan, out=out, high_priority_markers=[], only_cell=q._slot(rows[0]))
    assert first["event"] == "captured" and first["state"] == "pending"
    assert first["missing"] == ["성공 없음"]
    assert not list((out / "receipts").glob("*_fail.json"))
    assert not list(out.glob("*-fail.mp4"))
    second = q.run_one(plan, out=out, high_priority_markers=[], only_cell=q._slot(rows[0]))
    assert second["state"] == "complete" and second["missing"] == []
    assert len(calls) == 2 and len(list((out / "receipts").glob("*_success.json"))) == 1
    assert (out / "attempts" / first["cell"] / "01" / "attempt.json").is_file()
    assert (out / "attempts" / first["cell"] / "02" / "attempt.json").is_file()


def test_first_pass_rejects_unknown_target_results(tmp_path):
    plan, _ = fixture(tmp_path)
    plan["target_results"] = ["fail"]
    with pytest.raises(ValueError, match="target_results"):
        q.validate_plan(plan)


@pytest.mark.parametrize(("resets", "expected"), [(0, "실패 없음"), (1, "성공 없음")])
def test_two_attempt_cap_and_missing_role(tmp_path, monkeypatch, resets, expected):
    plan, _ = fixture(tmp_path)
    run, calls = fake_capture(plan, [resets] * 2)
    monkeypatch.setattr(q.subprocess, "run", run)
    out = tmp_path / "out"
    for _ in range(2):
        q.run_one(plan, out=out, high_priority_markers=[])
    summary = q._summary(out, plan["jobs"][0])
    assert summary["state"] == "exhausted" and summary["missing"] == [expected]
    assert len(calls) == 2
    assert not (out / "attempts" / summary["cell"] / "03").exists()


def test_failed_child_does_not_use_seed_budget_or_publish(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    def fail_live(argv, **_kw):
        if "--plan-only" in argv:
            policy = json.loads(argv[argv.index("--policy") + 1])
            return subprocess.CompletedProcess(argv, 0, json.dumps({"spec": policy, "target_frames": 450,
                "checkpoint_profile": {"checkpoint_sha256": plan["checkpoint_sha256"]}}), "")
        return subprocess.CompletedProcess(argv, 9)
    monkeypatch.setattr(q.subprocess, "run", fail_live)
    out = tmp_path / "out"
    result = q.run_one(plan, out=out, high_priority_markers=[])
    assert result["state"] == "capture_failed" and result["ordinal"] == 1
    assert (out / "attempts" / result["cell"] / "01" / "failure.json").is_file()
    assert result["cell_summary"]["attempts"] == 0
    assert result["cell_summary"]["technical_failures"] == 1
    assert result["cell_summary"]["state"] == "pending"
    assert not list(out.glob("*.mp4"))


def test_four_technical_failures_retry_same_seed_then_measure_first_outcome(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    good_run, captures = fake_capture(plan, [0])
    seen_seeds = []

    def fail_then_succeed(argv, **kwargs):
        if "--plan-only" in argv or argv[0] == "ffprobe" or argv[1] == plan["composer"]:
            return good_run(argv, **kwargs)
        seen_seeds.append(json.loads(argv[argv.index("--policy") + 1])["seed"])
        if len(seen_seeds) <= 4:
            return subprocess.CompletedProcess(argv, 9)
        return good_run(argv, **kwargs)

    monkeypatch.setattr(q.subprocess, "run", fail_then_succeed)
    out = tmp_path / "out"
    for attempt in range(4):
        result = q.run_one(plan, out=out, high_priority_markers=[])
        assert result["state"] == "capture_failed"
        assert result["cell_summary"]["attempts"] == 0
        assert result["cell_summary"]["state"] == "pending"
        assert result["cell_summary"]["technical_failures"] == attempt + 1
    measured = q.run_one(plan, out=out, high_priority_markers=[])
    assert measured["event"] == "captured"
    assert measured["attempts"] == 1 and measured["technical_failures"] == 4
    assert measured["state"] == "pending" and seen_seeds == [42] * 5
    assert len(captures) == 1
    assert (out / "attempts" / measured["cell"] / "05" / "attempt.json").is_file()


def test_canonical_video_comes_from_hud_composer_not_raw_capture(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    run, _calls = fake_capture(plan, [0])
    monkeypatch.setattr(q.subprocess, "run", run)
    out = tmp_path / "out"
    result = q.run_one(plan, out=out, high_priority_markers=[])
    receipt = json.loads((out / "receipts" / (result["cell"] + "_success.json")).read_text(encoding="utf-8"))
    assert Path(receipt["video"]).read_bytes() == b"composed HUD video"
    assert Path(receipt["attempt_dir"], "styled.mp4").read_bytes() == b"composed HUD video"
    assert receipt["composer_sha256"] == plan["composer_sha256"]
    playlist = Path(plan["playlist_dir"]) / "EX40-C-m08000-all.m3u8"
    assert playlist.is_file()
    assert str(Path(receipt["video"])) in playlist.read_text(encoding="utf-8")


def test_playlist_uses_verified_receipts_and_keeps_fail_separate(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    run, _calls = fake_capture(plan, [0, 1])
    monkeypatch.setattr(q.subprocess, "run", run)
    out = tmp_path / "out"
    q.run_one(plan, out=out, high_priority_markers=[])
    q.run_one(plan, out=out, high_priority_markers=[])
    root = Path(plan["playlist_dir"])
    all_lines = (root / "EX40-C-m08000-all.m3u8").read_text(encoding="utf-8").splitlines()
    fail_lines = (root / "EX40-C-m08000-fail.m3u8").read_text(encoding="utf-8").splitlines()
    assert len([line for line in all_lines if line.endswith(".mp4")]) == 2
    assert len([line for line in fail_lines if line.endswith(".mp4")]) == 1
    receipt = next((out / "receipts").glob("*_success.json"))
    source = json.loads(receipt.read_text(encoding="utf-8"))["video"]
    Path(source).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA256"):
        q.publish_playlists(plan, out)


def test_failed_full_frame_audit_never_publishes_or_consumes_seed(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    run, _calls = fake_capture(plan, [0])
    monkeypatch.setattr(q.subprocess, "run", run)
    monkeypatch.setattr(q, "audit_video", lambda *_a, **_k: {
        "pass": False, "issues": ["frame_17_dark_scene"]})
    out = tmp_path / "out"
    result = q.run_one(plan, out=out, high_priority_markers=[])
    assert result["state"] == "capture_failed"
    assert result["cell_summary"]["attempts"] == 0
    assert result["cell_summary"]["technical_failures"] == 1
    assert not list(out.glob("*.mp4"))


def test_missing_mode_video_never_reports_all_cells_closed(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setattr(q, "_summary", lambda _out, row, _targets: {
        "cell": q._slot(row), "state": "exhausted", "attempts": 4,
        "technical_failures": 0, "attempt_dirs": 4, "next_ordinal": 5,
        "missing": ["성공 없음", "실패 없음"], "incomplete": [], "receipts": {},
    })
    monkeypatch.setattr(q.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("closed seed budget must not launch child")))
    result = q.run_one(plan, out=out, high_priority_markers=[])
    assert result["state"] == "canonical_missing_hold"
    assert len(result["missing_cells"]) == 216
    assert result["mode_video_counts"] == {mode: 0 for mode in q.MAP_MODES}


def test_preflight_wrong_seed_fails_before_kit_child(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    def wrong_seed(argv, **_kw):
        assert "--plan-only" in argv
        policy = json.loads(argv[argv.index("--policy") + 1])
        policy["seed"] += 1
        return subprocess.CompletedProcess(argv, 0, json.dumps({"spec": policy, "target_frames": 450,
            "checkpoint_profile": {"checkpoint_sha256": plan["checkpoint_sha256"]}}), "")
    monkeypatch.setattr(q.subprocess, "run", wrong_seed)
    result = q.run_one(plan, out=tmp_path / "out", high_priority_markers=[])
    assert result["state"] == "capture_failed" and "preflight" in result["reason"]


def test_reset_count_mismatch_and_seed_mismatch(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path, complete=False)
    mp4 = tmp_path / rows[0]["label"] / "review.mp4"
    mp4.parent.mkdir()
    make_capture(mp4, plan, rows[0], 42, 0)
    monkeypatch.setattr(q.subprocess, "run", lambda argv, **_kw: subprocess.CompletedProcess(
        argv, 0, '{"streams":[{"nb_read_frames":"450"}]}', ""))
    assert q.verify_attempt(mp4, rows[0], plan, ffprobe="ffprobe", seed=42)[1] == "success"
    with pytest.raises(ValueError, match="seed"):
        q.verify_attempt(mp4, rows[0], plan, ffprobe="ffprobe", seed=43)
    meta = json.loads(mp4.with_name("review.json").read_text(encoding="utf-8"))
    meta["resets"] = 1
    mp4.with_name("review.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="reset count"):
        q.verify_attempt(mp4, rows[0], plan, ffprobe="ffprobe", seed=42)


def test_higher_priority_yields_without_child(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    marker = tmp_path / "PRIORITY_BUSY"
    marker.write_text("eval", encoding="utf-8")
    monkeypatch.setattr(q.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("launched despite priority")))
    assert q.run_one(plan, out=tmp_path / "out", high_priority_markers=[marker])["state"] == "yielded_to_higher_priority"


def test_incomplete_attempt_holds_instead_of_skipping_seed(tmp_path, monkeypatch):
    plan, rows = fixture(tmp_path)
    out = tmp_path / "out"
    root = out / "attempts" / q._slot(rows[0]) / "01"
    root.mkdir(parents=True)
    (root / "started.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(q.subprocess, "run", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("incomplete attempt was silently skipped")))
    result = q.run_one(plan, out=out, high_priority_markers=[])
    assert result["state"] == "incomplete_attempt_hold"
    assert result["attempts"] == 0 and result["attempt_dirs"] == 1


@pytest.mark.parametrize(("terrain_set", "kind", "col"), [
    ("fixed64", "boxes", 4), ("sparse50", "gaps", 40),
])
def test_c76_recorder_accepts_variable_seeds_without_eval_receipt(tmp_path, terrain_set, kind, col):
    base = {"experiment": "SB", "source_profile": "C76", "c_layer_reference": True,
            "source_root": str(tmp_path), "source_head": "a" * 40,
            "source_recorder_sha256": "b" * 64,
            "terrain_set": terrain_set, "fixed_terrain": True, "fixed_level": 2,
            "physics_mode": "sparse_eval_reference", "envs": 64, "env_id": 7,
            "kind": kind, "col": col, "selection_role": "c_layer",
            "geometry_seed": record_c_layer.C_LAYER_GEOMETRY_SEED,
            "checkpoint_sha256": "c" * 64, "map_mode": "eval_gt",
            "command": [1.0, 0.0, 0.0], "duration_s": 18.0}
    for seed in (42, 43, 44, 45):
        assert record_c_layer.parse_spec(json.dumps(dict(base, seed=seed)))["seed"] == seed
    with pytest.raises(ValueError):
        record_c_layer.parse_spec(json.dumps(dict(base, seed=43, c_layer_reference=False)))


def test_c76_continuous_mesh_seed_stays_fixed_across_capture_seeds(tmp_path):
    plan, rows = fixture(tmp_path)
    row = next(row for row in rows if row["kind"] == "boxes" and row["map_mode"] == "eval_gt")
    for capture_seed in (42, 43, 44, 45):
        spec = record_c_layer.parse_spec(json.dumps(dict(row["policy"], seed=capture_seed)))
        generator = SimpleNamespace(seed=None)
        env_cfg = SimpleNamespace(scene=SimpleNamespace(terrain=SimpleNamespace(terrain_generator=generator)))
        assert record_c_layer.pin_c_layer_geometry_seed(env_cfg, spec) == 20261026
        assert generator.seed == 20261026 and spec["seed"] == capture_seed
    bad = dict(row["policy"], seed=43, geometry_seed=43)
    with pytest.raises(ValueError, match="geometry seed"):
        record_c_layer.parse_spec(json.dumps(bad))
    row["policy"]["geometry_seed"] = 43
    with pytest.raises(ValueError, match="geometry seed"):
        q.validate_plan(plan)


def test_gpu0_plan_skips_gpu1_marker_gate_but_gpu1_plan_calls_it(monkeypatch):
    calls = []
    monkeypatch.setattr(q.subprocess, "run", lambda argv, **_k: calls.append(argv) or SimpleNamespace(
        returncode=3, stdout=json.dumps({"job": "c-layer", "admit_next_unit": False}), stderr=""))
    gpu0 = {"jobs": [{"recorder_argv": ["py", "rec.py", "--device", "cuda:0"]}],
            "gpu_jobs_tool": "gate.py", "gpu_jobs_config": "jobs.json"}
    gpu1 = {"jobs": [{"recorder_argv": ["py", "rec.py", "--device", "cuda:1"]}],
            "gpu_jobs_tool": "gate.py", "gpu_jobs_config": "jobs.json"}
    import importlib
    fresh = importlib.reload(q)  # the autouse fixture replaced _gpu_gate
    assert fresh._gpu_gate(gpu0, "c-layer")["admit_next_unit"] is True
    assert calls == []
    assert fresh._gpu_gate(gpu1, "c-layer")["admit_next_unit"] is False
    assert calls and calls[0][-2:] == ["gate", "c-layer"]
