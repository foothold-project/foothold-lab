"""Known-input W09/W08 producer tests, without Kit or a GPU."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Barrier, Lock
from types import SimpleNamespace

import pytest

from foothold_s2.scripts.ex42_flag_baseline_chain import (
    check_e1_gate, make_baseline, make_calibration, make_q4,
)
from foothold_s2.tests.test_ex42_e1f_flag_cpu import (
    CHECKPOINT_SHA, PLAN_SHA, _plan, _write_round,
)

ROOT = Path(__file__).parents[2]


def _p():
    return SimpleNamespace(document=_plan(), sha256=PLAN_SHA)


def test_w09_reads_both_counts_and_all_map_modes(tmp_path):
    plan = _p()
    root = tmp_path / "w09"
    _write_round(root / "flag_cells", plan.document, 42)
    result = make_baseline(root, plan=plan, checkpoint_sha256=CHECKPOINT_SHA,
                           mesh_sha256="m" * 64, seed=42)
    assert result["state"] == "measured"
    assert set(result["judge_cells"]) == set(plan.document["evaluation"]["flag_cells"]["judge_cases"])
    assert all(row["success_count"] == 64 for row in result["judge_cells"].values())
    assert set(result["receipts"]) == {"flag_one", "flag_four"}
    (root / "flag_cells" / "flag_four" / "flag_cells.json").unlink()
    with pytest.raises(FileNotFoundError):
        make_baseline(root, plan=plan, checkpoint_sha256=CHECKPOINT_SHA,
                      mesh_sha256="m" * 64, seed=42)


def test_w08_five_roots_produce_recountable_calibration_and_separate_q4(tmp_path):
    plan = _p()
    roots = []
    for index, seed in enumerate((42, 42, 43, 44, 45)):
        root = tmp_path / f"repeat_{index:02d}"
        _write_round(root / "flag_cells", plan.document, seed, fail_env=0 if index == 1 else None)
        roots.append(root)
    calibration = make_calibration(roots, plan=plan, checkpoint_sha256=CHECKPOINT_SHA)
    assert calibration["format"] == "foothold-ex42-flag-calibration/1"
    assert len(calibration["repeat_receipts"]) == 5
    assert calibration["repeat_width"]["flag_four_eval_gt"]["success_count"] == 1
    assert "proposed_q4" not in calibration
    q4 = make_q4(calibration, plan=plan)
    assert q4["by_cell"]["flag_four_eval_gt"]["success_count"] == 3
    assert q4["class"] == "assumption_not_applied_to_exit"
    with pytest.raises(ValueError, match="five"):
        make_calibration(roots[:-1], plan=plan, checkpoint_sha256=CHECKPOINT_SHA)
    raw = roots[1] / "flag_cells" / "flag_four" / "flag_four_eval_gt.json"
    raw.write_text(json.dumps({"forged": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="raw path or SHA"):
        make_calibration(roots, plan=plan, checkpoint_sha256=CHECKPOINT_SHA)


def test_w09_baseline_rejects_wrong_checkpoint_pin(tmp_path):
    plan = _p()
    root = tmp_path / "w09"
    _write_round(root / "flag_cells", plan.document, 42)
    with pytest.raises(ValueError, match="identity"):
        make_baseline(root, plan=plan, checkpoint_sha256="0" * 64,
                      mesh_sha256="m" * 64, seed=42)


def test_w09_requires_a_pinned_e1_graduation_gate(tmp_path):
    import hashlib

    measurement = tmp_path / "ex42_score.json"
    measurement.write_text('{"judgement":"PASS"}\n', encoding="utf-8")
    measurement_sha = hashlib.sha256(measurement.read_bytes()).hexdigest()
    gate = tmp_path / "p1_score.json"
    row = {"state": "complete", "stage_id": "E1", "checkpoint_iteration": 1000,
           "judgment": "PASS", "checkpoint_sha256": CHECKPOINT_SHA,
           "measurement": str(measurement), "measurement_sha256": measurement_sha}
    gate.write_text(json.dumps(row), encoding="utf-8")
    result = check_e1_gate(gate, checkpoint_sha256=CHECKPOINT_SHA)
    assert result["measurement_sha256"] == measurement_sha
    for key, value in (("judgment", "HOLD"), ("stage_id", "E0"),
                       ("checkpoint_iteration", 750), ("measurement_sha256", "0" * 64),
                       ("checkpoint_sha256", "0" * 64)):
        changed = {**row, key: value}
        gate.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ValueError, match="E1 m1000 PASS"):
            check_e1_gate(gate, checkpoint_sha256=CHECKPOINT_SHA)


def test_chain_dry_order_and_no_output_or_gpu(tmp_path, monkeypatch):
    from foothold_s2.scripts import ex42_flag_baseline_chain as chain

    checkpoint = tmp_path / "model_1000.pt"
    checkpoint.write_bytes(b"known graduate")
    gate_measure = tmp_path / "score.json"
    gate_measure.write_bytes(b"{}")
    gate = tmp_path / "p1_score.json"
    gate.write_text(json.dumps({"state": "complete", "stage_id": "E1",
                                "checkpoint_iteration": 1000, "judgment": "PASS",
                                "checkpoint_sha256": chain.digest(checkpoint),
                                "measurement": str(gate_measure),
                                "measurement_sha256": chain.digest(gate_measure)}), encoding="utf-8")
    plan_path = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
    monkeypatch.setattr(chain, "manifest_checkpoint_sha", lambda path: (chain.digest(path), 1000))
    monkeypatch.setattr(chain, "preflight", lambda path: {"mesh_sha256": "a" * 64})
    monkeypatch.setattr(chain, "flag_kit_commands",
                        lambda checkpoint, output, device, **kwargs:
                        [(name, ["cpu-test", "--count", name, "--seed", str(kwargs["seed"])])
                         for name in ("flag_one", "flag_four")])
    monkeypatch.setattr(chain, "gpu_identity", lambda device: (_ for _ in ()).throw(
        AssertionError("dry must not query GPU")))
    result = chain.run_chain(checkpoint, tmp_path / "out", "cuda:1", plan_path=plan_path,
                             mesh_dir=tmp_path, expected_checkpoint_sha256=chain.digest(checkpoint),
                             expected_mesh_sha256="a" * 64, e1_gate=gate, task="test",
                             execute=False)
    assert result["state"] == "DRY"
    assert [row["seed"] for row in result["rounds"]] == [42, 42, 42, 43, 44, 45]
    assert all(len(row["children"]) == 2 for row in result["rounds"])
    assert not (tmp_path / "out").exists()
    # Each pin is an independent launch identity gate. A forged expected SHA
    # must not be substituted into the later receipt or accepted as a dry run.
    with pytest.raises(ValueError, match="pinned E1 m1000 checkpoint"):
        chain.run_chain(checkpoint, tmp_path / "wrong_checkpoint", "cuda:1",
                        plan_path=plan_path, mesh_dir=tmp_path,
                        expected_checkpoint_sha256="0" * 64,
                        expected_mesh_sha256="a" * 64, e1_gate=gate,
                        task="test", execute=False)
    with pytest.raises(ValueError, match="pinned mesh SHA differs"):
        chain.run_chain(checkpoint, tmp_path / "wrong_mesh", "cuda:1",
                        plan_path=plan_path, mesh_dir=tmp_path,
                        expected_checkpoint_sha256=chain.digest(checkpoint),
                        expected_mesh_sha256="0" * 64, e1_gate=gate,
                        task="test", execute=False)
    assert not (tmp_path / "wrong_checkpoint").exists()
    assert not (tmp_path / "wrong_mesh").exists()


def test_six_rounds_write_w09_and_recountable_w08(tmp_path, monkeypatch):
    import sys
    import foothold_s2
    import foothold_s2.ex42_eval_once as once
    from foothold_s2.scripts import ex42_flag_baseline_chain as chain

    checkpoint = tmp_path / "model_1000.pt"
    checkpoint.write_bytes(b"known graduate")
    measurement = tmp_path / "score.json"
    measurement.write_bytes(b"{}")
    gate = tmp_path / "p1_score.json"
    gate.write_text(json.dumps({"state": "complete", "stage_id": "E1",
                                "checkpoint_iteration": 1000, "judgment": "PASS",
                                "checkpoint_sha256": chain.digest(checkpoint),
                                "measurement": str(measurement),
                                "measurement_sha256": chain.digest(measurement)}), encoding="utf-8")
    plan = _p()
    monkeypatch.setattr(chain.EX42Plan, "load", lambda path: plan)
    monkeypatch.setattr(chain, "manifest_checkpoint_sha", lambda path: (chain.digest(path), 1000))
    monkeypatch.setattr(chain, "preflight", lambda path: {"mesh_sha256": "a" * 64})
    monkeypatch.setattr(chain, "gpu_identity", lambda device: {"gpu_uuid": "GPU-" + "a" * 32})
    monkeypatch.setattr(chain, "child_env", lambda: {"CUDA_DEVICE_ORDER": "PCI_BUS_ID"})
    fake_commands = lambda checkpoint, output, device, **kwargs: [
        (name, ["cpu-test", "--count", name, "--seed", str(kwargs["seed"])])
        for name in ("flag_one", "flag_four")]
    monkeypatch.setattr(chain, "flag_kit_commands", fake_commands)
    monkeypatch.setattr(once, "flag_kit_commands", fake_commands)
    calls = []

    def hidden_child(argv, folder, *, env):
        root = Path(folder).parent.parent
        seed = int(argv[argv.index("--seed") + 1])
        if not (root / "flag_cells").exists():
            _write_round(root / "flag_cells", plan.document, seed,
                         checkpoint_sha=chain.digest(checkpoint))
            for name in ("flag_one", "flag_four"):
                receipt = root / "flag_cells" / name / "flag_cells.json"
                row = json.loads(receipt.read_text(encoding="utf-8"))
                row["run_identity"] = {"device": "cuda:1", "gpu_uuid": "GPU-" + "a" * 32}
                receipt.write_text(json.dumps(row), encoding="utf-8")
        calls.append((root, argv[argv.index("--count") + 1]))
        return {"state": "done", "rc": 0}

    child_module = SimpleNamespace(hidden_child=hidden_child)
    monkeypatch.setitem(sys.modules, "foothold_s2.ex41_eval_once", child_module)
    monkeypatch.setattr(foothold_s2, "ex41_eval_once", child_module, raising=False)
    out = tmp_path / "out"
    result = chain.run_chain(checkpoint, out, "cuda:1", plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
                             mesh_dir=tmp_path, expected_checkpoint_sha256=chain.digest(checkpoint),
                             expected_mesh_sha256="a" * 64, e1_gate=gate, task="test", execute=True)
    assert result["state"] == "complete" and len(calls) == 12
    assert (out / "w09_baseline.json").is_file()
    calibration = json.loads((out / "w08_calibration.json").read_text(encoding="utf-8"))
    assert calibration == make_calibration([out / "w08" / f"repeat_{i:02d}" for i in range(5)],
                                           plan=plan, checkpoint_sha256=chain.digest(checkpoint))
    assert json.loads((out / "w08_proposed_q4.json").read_text(encoding="utf-8"))["calibration_sha256"] == chain.digest(out / "w08_calibration.json")


def test_failed_kit_child_is_a_durable_hold_not_a_baseline(tmp_path, monkeypatch):
    from foothold_s2.scripts import ex42_flag_baseline_chain as chain

    def failed(*args, **kwargs):
        kwargs["record"]("flag_one", {"state": "HOLD", "reason": "child rc=1"})
        return {"flag_one": "child rc=1"}

    monkeypatch.setattr(chain, "execute_flag_children", failed)
    out = tmp_path / "round"
    with pytest.raises(ValueError, match="flag round HOLD"):
        chain.run_round(tmp_path / "model_1000.pt", out, "cuda:1", plan=_p(),
                        plan_path=tmp_path / "plan.yaml", mesh_dir=tmp_path,
                        mesh_sha256="a" * 64, checkpoint_sha256=CHECKPOINT_SHA,
                        seed=42, task="test", process=SimpleNamespace(), env={},
                        physical_gpu={"gpu_uuid": "GPU-test"})
    receipt = json.loads((out / "round_receipt.json").read_text(encoding="utf-8"))
    assert receipt["state"] == "HOLD" and receipt["failures"] == {"flag_one": "child rc=1"}
    assert not (out / "w09_baseline.json").exists()


def test_dual_device_keeps_seed_order_and_runs_two_groups_concurrently(tmp_path, monkeypatch):
    import sys
    import foothold_s2
    from foothold_s2.scripts import ex42_flag_baseline_chain as chain

    checkpoint = tmp_path / "model_1000.pt"
    checkpoint.write_bytes(b"known graduate")
    measurement = tmp_path / "score.json"
    measurement.write_bytes(b"{}")
    gate = tmp_path / "p1_score.json"
    gate.write_text(json.dumps({"state": "complete", "stage_id": "E1",
                                "checkpoint_iteration": 1000, "judgment": "PASS",
                                "checkpoint_sha256": chain.digest(checkpoint),
                                "measurement": str(measurement),
                                "measurement_sha256": chain.digest(measurement)}), encoding="utf-8")
    monkeypatch.setattr(chain, "manifest_checkpoint_sha", lambda path: (chain.digest(path), 1000))
    monkeypatch.setattr(chain.EX42Plan, "load", lambda path: _p())
    monkeypatch.setattr(chain, "preflight", lambda path: {"mesh_sha256": "a" * 64})
    monkeypatch.setattr(chain, "gpu_identity", lambda device: {"device": device, "gpu_uuid": device})
    monkeypatch.setattr(chain, "child_env", lambda: {})
    monkeypatch.setattr(chain, "flag_kit_commands",
                        lambda checkpoint, output, device, **kwargs: [("flag_one", [device])])
    monkeypatch.setitem(sys.modules, "foothold_s2.ex41_eval_once", SimpleNamespace())
    monkeypatch.setattr(foothold_s2, "ex41_eval_once", SimpleNamespace(), raising=False)
    barrier, lock = Barrier(2, timeout=2), Lock()
    seen = []

    def run_round(_checkpoint, root, device, **kwargs):
        index = 0 if root.name == "w09" else int(root.name.removeprefix("repeat_")) + 1
        if index in (0, 3):
            barrier.wait()
        with lock:
            seen.append((device, index, kwargs["seed"]))
        root.mkdir(parents=True)
        (root / "round_receipt.json").write_text(json.dumps({"device": device, "seed": kwargs["seed"]}), encoding="utf-8")

    monkeypatch.setattr(chain, "run_round", run_round)
    monkeypatch.setattr(chain, "make_baseline", lambda *args, **kwargs: {"source": "w09"})
    monkeypatch.setattr(chain, "make_calibration", lambda *args, **kwargs: {"repeat_width": {}})
    monkeypatch.setattr(chain, "make_q4", lambda *args, **kwargs: {"rule": "test"})
    out = tmp_path / "dual"
    result = chain.run_chain(checkpoint, out, None,
                             plan_path=ROOT / "foothold_s2/curriculum/ex42-prep.yaml",
                             mesh_dir=tmp_path, expected_checkpoint_sha256=chain.digest(checkpoint),
                             expected_mesh_sha256="a" * 64, e1_gate=gate, task="test", execute=True,
                             devices=("cuda:0", "cuda:1"))
    assert result["state"] == "complete"
    assert [row["seed"] for row in result["rounds"]] == [42, 42, 42, 43, 44, 45]
    assert [row["device"] for row in result["rounds"]] == ["cuda:0"] * 3 + ["cuda:1"] * 3
    assert [index for device, index, _ in seen if device == "cuda:0"] == [0, 1, 2]
    assert [index for device, index, _ in seen if device == "cuda:1"] == [3, 4, 5]
    assert len(result["round_receipts"]) == 6
    with pytest.raises(ValueError, match="dual assignment"):
        chain.round_devices(None, ("cuda:1", "cuda:0"))


def test_dual_device_cli_accepts_exact_pair(monkeypatch, tmp_path, capsys):
    from foothold_s2.scripts import ex42_flag_baseline_chain as chain
    received = []
    monkeypatch.setattr(chain, "run_chain", lambda *args, **kwargs: received.append(kwargs) or {"state": "DRY"})
    base = ["--checkpoint", str(tmp_path / "model_1000.pt"),
            "--expected-checkpoint-sha256", "a" * 64, "--e1-gate", str(tmp_path / "gate.json"),
            "--plan", str(tmp_path / "plan.yaml"), "--mesh-dir", str(tmp_path),
            "--expected-mesh-sha256", "b" * 64, "--out", str(tmp_path / "out")]
    assert chain.main([*base, "--devices", "cuda:0,cuda:1"]) == 0
    assert received[0]["devices"] == ("cuda:0", "cuda:1") and received[0]["execute"] is False
    with pytest.raises(SystemExit):
        chain.main([*base, "--devices", "cuda:1,cuda:0"])
