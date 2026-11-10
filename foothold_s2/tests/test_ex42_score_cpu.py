"""Known-input EX-42 measurement and missing-evidence guards; no Kit required."""
import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.eval.axis_v2_cells import case_specs
from foothold_s2.eval.ex42_foot_metrics import per_env
from foothold_s2.eval.map_mode_cells import commands as expected_commands
from foothold_s2.ex42_eval_once import (commands, gpu_identity, child_env,
                                        observed_child_identity, receipt_device_fields)
from foothold_s2.ex42_score import MODES, config, digest, measure


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    cfg = config()[0]
    model = tmp_path / "model_1000.pt"
    model.write_bytes(b"known-checkpoint")
    sha = digest(model)
    out = tmp_path / "evaluation"
    rows = [{"env": i, "alive_at_end": True, "vx_abs_error_mean_alive_mps": .1,
             "vy_abs_error_mean_alive_mps": .2, "wz_abs_error_mean_alive_radps": .3,
             "command_xy_projection_integral_m": 2.0} for i in range(64)]
    cases = ["fwd0.5", "fwd1.0", "spin+1.2", "spin-1.2", "back0.5", "back1.0",
             "side+0.5", "side-0.5", "diag-fwd+side+", "diag-fwd+side-",
             "diag-back+side+", "diag-back+side-", "stop"]
    write_json(out / "map64/map_modes.json", {
        "checkpoint_sha256": sha, "envs": 64, "steps": 300, "eval_seed": 42,
        "command_suite": "extended", "dr_off": ["physics_material"],
        "curriculum_off": ["terrain_levels"], "commands": expected_commands("extended"),
        "modes": {mode: {case: {"per_env": rows} for case in cases} for mode in MODES}})
    feet = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
    for mode in MODES:
        folder = out / f"stand_{mode}"
        folder.mkdir(parents=True)
        np.savez_compressed(folder / "stand_raw.npz", force_z=np.ones((1, 64, 4)))
        write_json(folder / "stand.json", {
            "format": "foothold-ex40-stand/1", "checkpoint_sha256": sha, "mode": mode,
            "envs": 64, "seconds": cfg["stand_seconds"],
            "skip_seconds": cfg["stand_skip_seconds"], "contact_force_n": cfg["stand_contact_n"],
            "feet": feet, "raw_sha256": digest(folder / "stand_raw.npz"),
            "per_env": [{"alive_at_end": True, "feet": {
                foot: {"contact_fraction_gt1n": .75} for foot in feet}} for _ in range(64)]})
    axis_dir = out / "axis_v2"
    axis_dir.mkdir()
    modes = {}
    for mode in MODES:
        modes[mode] = {}
        for spec in case_specs():
            name = spec["name"]
            filename = f"axis_v2_{mode}_{name}.npz"
            contact = np.zeros((300, 64, 4), bool)
            contact[0:2] = True
            speed = np.ones((300, 64, 4)) * 2
            np.savez_compressed(axis_dir / filename, alive=np.ones((300, 64), bool),
                                contact=contact, foot_xy_speed_mps=speed, dt=np.array(.02))
            modes[mode][name] = {"raw_file": filename, "raw_sha256": digest(axis_dir / filename),
                                 "alive_at_end": 64, "by_terrain_kind": {},
                                 "per_env": [{} for _ in range(64)]}
    write_json(axis_dir / "axis_v2.json", {
        "schema": "foothold-axis-v2/1", "checkpoint_sha256": sha,
        "envs": 64, "steps": 300, "eval_seed": 42, "fixed_level": 2, "dt_s": .02,
        "dr_off": ["physics_material"], "curriculum_off": ["terrain_levels"],
        "foot_order": feet, "ex42_maintenance": {"schema": "foothold-ex42-foot-xy/1"},
        "modes": modes})
    return model, out


def test_foot_duty_phase_drag_known_input():
    valid = np.ones((4, 1), bool)
    contact = np.zeros((4, 1, 4), bool)
    contact[0, 0, 0] = contact[2, 0, 0] = True
    contact[1, 0, 1] = True
    speed = np.ones((4, 1, 4)) * 2
    row = per_env(valid, contact, speed, .02)[0]
    assert row["duty_by_foot"] == [.5, .25, 0, 0]
    assert row["phase_from_FL_cycle"] == [0, .5, None, None]
    assert row["foot_drag_proxy_m_by_foot"] == pytest.approx([.08, .04, 0, 0])


def test_measure_complete_is_hold_without_approved_baseline(tmp_path):
    model, out = fixture(tmp_path)
    row = measure(model, out)
    assert row["judgement"] == "HOLD"
    assert row["map64"]["eval_gt"]["fwd0.5"]["alive_at_end"] == 64
    assert row["stand"]["eval_gt"]["per_foot_contact_fraction_median"]["FL_foot"] == .75
    assert row["axis_v2"]["eval_gt"]["fwd0.5"]["foot_drag_proxy_m_by_foot_median"] == pytest.approx([.08]*4)
    assert row["maintenance_items"]["W57_spin_survival"]["by_mode_and_direction"]["eval_gt"] == {
        "spin+1.2": 64, "spin-1.2": 64}


def test_measure_rejects_missing_foot_speed_and_sha_mutation(tmp_path):
    model, out = fixture(tmp_path)
    target = out / "axis_v2/axis_v2_eval_gt_fwd0.5.npz"
    target.write_bytes(b"mutated")
    with pytest.raises(ValueError, match="SHA differs"):
        measure(model, out)
    model, out = fixture(tmp_path / "second")
    target = out / "axis_v2/axis_v2_eval_gt_fwd0.5.npz"
    with np.load(target) as z:
        np.savez_compressed(target, alive=z["alive"], contact=z["contact"], dt=z["dt"])
    axis = json.loads((out / "axis_v2/axis_v2.json").read_text())
    axis["modes"]["eval_gt"]["fwd0.5"]["raw_sha256"] = digest(target)
    write_json(out / "axis_v2/axis_v2.json", axis)
    with pytest.raises(ValueError, match="lacks foot_xy_speed_mps"):
        measure(model, out)


def test_measure_rejects_old_ex41_axis_receipt(tmp_path):
    model, out = fixture(tmp_path)
    axis = json.loads((out / "axis_v2/axis_v2.json").read_text())
    axis.pop("ex42_maintenance")
    write_json(out / "axis_v2/axis_v2.json", axis)
    with pytest.raises(ValueError, match="foot speed marker"):
        measure(model, out)


def test_measure_rejects_mislabeled_spin_command(tmp_path):
    model, out = fixture(tmp_path)
    path = out / "map64/map_modes.json"
    row = json.loads(path.read_text())
    row["commands"]["spin+1.2"] = [0, 0, 0]
    write_json(path, row)
    with pytest.raises(ValueError, match="13-command coverage"):
        measure(model, out)


def test_commands_include_real_ex42_axis_and_three_modes(tmp_path):
    rows = commands("/tmp/model.pt", tmp_path, "cuda:1")
    assert [r["name"] for r in rows] == ["map64", "stand_eval_gt", "stand_probe_prop_only",
                                          "stand_eval_pred", "axis_v2"]
    axis = rows[-1]["argv"]
    assert "--ex42-maintenance" in axis and "--axis-v2" in axis
    assert all("--headless" in row["argv"] for row in rows)
    gpu0 = commands("/tmp/model.pt", tmp_path, "cuda:0")
    assert len(gpu0) == len(rows)
    assert all(r["argv"][r["argv"].index("--device") + 1] == "cuda:0" for r in gpu0)
    with pytest.raises(ValueError, match="unsupported experiment queue device"):
        commands("/tmp/model.pt", tmp_path, "cuda:2")


def test_ex42_physical_device_and_override_receipt(tmp_path):
    inventory = ("0, GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b, 00000000:41:00.0\n"
                 "1, GPU-315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f, 00000000:81:00.0\n")
    physical = gpu_identity("cuda:0", query=lambda: inventory)
    receipt = receipt_device_fields("cuda:0", physical)
    assert receipt["physical_gpu"]["gpu_uuid"] == "GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"
    assert receipt["device_override"] == {"registered": "cuda:1", "used": "cuda:0"}
    assert "device_override" not in receipt_device_fields(
        "cuda:1", gpu_identity("cuda:1", query=lambda: inventory))
    with pytest.raises(ValueError, match="physical GPU UUID differs"):
        gpu_identity("cuda:0", query=lambda: inventory.replace("c08e23b0", "wrong-id"))

    env = child_env({"CUDA_VISIBLE_DEVICES": "1,0", "CUDA_DEVICE_ORDER": "FASTEST_FIRST"})
    assert "CUDA_VISIBLE_DEVICES" not in env
    assert env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"

    for name, basename in (("map64", "map_modes.json"), ("axis_v2", "axis_v2.json"),
                           ("stand_eval_gt", "stand.json")):
        write_json(tmp_path / name / basename, {"run_identity": {
            "device": "cuda:0", "gpu_uuid": "c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"}})
        assert observed_child_identity(tmp_path, name, physical)["device"] == "cuda:0"
        write_json(tmp_path / name / basename, {"run_identity": {
            "device": "cuda:0", "gpu_uuid": "315d098f-5fe0-26a0-0d2e-26e2d4c1ae4f"}})
        with pytest.raises(ValueError, match="Kit physical GPU UUID differs"):
            observed_child_identity(tmp_path, name, physical)
