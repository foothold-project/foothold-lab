"""Known-input CPU tests for D48 reset-derived C-layer capture."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
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


def fixture(tmp_path: Path, *, complete: bool = True):
    checkpoint = tmp_path / "model_8000.pt"
    recorder = tmp_path / "record.py"
    composer = tmp_path / "compose.py"
    checkpoint.write_bytes(b"checkpoint")
    recorder.write_bytes(b"# C_LAYER_SEED_V1\n")
    composer.write_bytes(b"# CPU composer fixture\n")
    rows = []
    cells = q.inventory(KINDS) if complete else [("boxes", 2, "eval_gt")]
    for kind, level, mode in cells:
        label = video_style.capture_name("EX40", kind, level, 7, 8000, segment=mode)
        rows.append({"kind": kind, "level": level, "map_mode": mode, "env_id": 7,
                     "label": label, "seeds": [42, 43, 44, 45],
                     "policy": {"experiment": "SB", "source_root": str(tmp_path),
                                "source_profile": "C76", "source_head": "a" * 40,
                                "source_recorder_sha256": "b" * 64, "selection_role": "c_layer",
                                "terrain_set": ("fixed64" if kind in KINDS["continuous"] else "sparse50"),
                                "fixed_terrain": True, "fixed_level": level,
                                "geometry_seed": 20261026,
                                "command": [1.0, 0.0, 0.0], "duration_s": 18.0,
                                "seed": "{seed}", "c_layer_reference": True,
                                "checkpoint_sha256": q.sha256(checkpoint), "envs": 64,
                                "map_mode": mode, "env_id": 7, "kind": kind, "col": 4},
                     "recorder_argv": ["python", str(recorder), "--policy", "{policy}",
                                       "--checkpoint", str(checkpoint), "--label", "{label}",
                                       "--mp4", "{mp4}"]})
    plan = {"status": "approved_canon", "canon_label": "EX40", "iteration": 8000,
            "kinds": KINDS, "checkpoint": str(checkpoint), "checkpoint_sha256": q.sha256(checkpoint),
            "priority_markers": {name: str(tmp_path / (name + ".busy"))
                                 for name in ("training", "evaluation", "a_layer")},
            "recorder": str(recorder), "recorder_sha256": q.sha256(recorder),
            "composer": str(composer), "composer_sha256": q.sha256(composer), "jobs": rows}
    return plan, rows


def make_capture(mp4: Path, plan: dict, row: dict, seed: int, resets: int):
    mp4.write_bytes(b"cpu fake video")
    mp4.with_name("review.json").write_text(json.dumps({
        "checkpoint_sha256": plan["checkpoint_sha256"], "label": row["label"], "seed": seed,
        "selected_environment": {"env_id": 7, "kind": row["kind"], "level": row["level"]},
        "map_modes": {"map_mode": {"requested": row["map_mode"]}},
        "style": {"style_id": video_style.STYLE_ID},
        "frames": 450, "fps": 25, "duration_s": 18.0, "resets": resets,
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


def test_inventory_and_seed_gate(tmp_path):
    plan, rows = fixture(tmp_path)
    assert len(q.inventory(KINDS)) == 216
    assert q.validate_plan(plan)["ready"] == 216
    rows[0]["seeds"] = [42, 42]
    with pytest.raises(ValueError, match="distinct"):
        q.validate_plan(plan)
    rows[0]["seeds"] = [42, 43, 44, 45]
    Path(plan["recorder"]).write_bytes(b"legacy seed 42 only")
    plan["recorder_sha256"] = q.sha256(Path(plan["recorder"]))
    with pytest.raises(ValueError, match="variable-seed"):
        q.validate_plan(plan)


def test_partial_plan_cannot_launch(tmp_path):
    plan, _ = fixture(tmp_path, complete=False)
    assert q.validate_plan(plan)["missing"] == 215
    with pytest.raises(ValueError, match="216"):
        q.run_one(plan, out=tmp_path / "out", high_priority_markers=[])


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


@pytest.mark.parametrize(("resets", "expected"), [(0, "실패 없음"), (1, "성공 없음")])
def test_four_attempt_cap_and_missing_role(tmp_path, monkeypatch, resets, expected):
    plan, _ = fixture(tmp_path)
    run, calls = fake_capture(plan, [resets] * 4)
    monkeypatch.setattr(q.subprocess, "run", run)
    out = tmp_path / "out"
    for _ in range(4):
        q.run_one(plan, out=out, high_priority_markers=[])
    summary = q._summary(out, plan["jobs"][0])
    assert summary["state"] == "exhausted" and summary["missing"] == [expected]
    assert len(calls) == 4
    assert not (out / "attempts" / summary["cell"] / "05").exists()


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


def test_missing_mode_video_never_reports_all_cells_closed(tmp_path, monkeypatch):
    plan, _ = fixture(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setattr(q, "_summary", lambda _out, row: {
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
