import csv
import hashlib
import json

import numpy as np
import pytest

from foothold_s2.eval.ex42_gait_contact import (
    FOOT_ORDER, summarize, summarize_both, validate_map_mode, write_csv,
    build_r5_contact_evidence, write_r5_raw_npz, foot_sole_height_m,
    write_r5_evidence_json,
)
from foothold_s2.eval.map_mode_cells import commands


def test_summarize_uses_bounded_flights_and_touchdown_cycles():
    per_foot = np.array([1, 0, 1, 1, 0, 1], dtype=bool)
    contact = np.broadcast_to(per_foot[:, None, None], (6, 1, 4)).copy()
    alive = np.ones((6, 1), dtype=bool)
    vx = np.arange(6, dtype=float)[:, None] / 10

    vy = -vx
    row = summarize(contact, alive, vx, 0.2, body_vy=vy)

    assert row["foot_order"] == list(FOOT_ORDER)
    assert row["contact_threshold"] == "net_forces_w[..., z] > 1 N"
    assert row["air_time_s_by_foot"]["FL_foot"] == {"p10": 0.2, "p50": 0.2, "p90": 0.2, "n": 2}
    assert row["cycle_period_s_by_foot"]["FL_foot"] == {"p10": 0.6000000000000001,
                                                        "p50": 0.6000000000000001,
                                                        "p90": 0.6000000000000001, "n": 1}
    assert row["complete_cycle_count_total"] == 4
    assert row["all_four_grounded_fraction"] == pytest.approx(4 / 6)
    assert row["body_forward_speed_median_mps"] == pytest.approx(0.25)
    assert row["body_lateral_speed_median_mps"] == pytest.approx(-0.25)
    assert row["body_backward_speed_median_mps"] == pytest.approx(-0.25)


def test_dead_gap_does_not_create_a_complete_flight_or_cycle():
    contact = np.zeros((5, 1, 4), dtype=bool)
    contact[0] = True
    contact[4] = True
    alive = np.array([[True], [True], [False], [True], [True]])
    vx = np.zeros((5, 1))

    row = summarize(contact, alive, vx, 0.02, body_vy=vx)

    assert row["air_time_s_by_foot"]["FL_foot"]["n"] == 0
    assert row["cycle_period_s_by_foot"]["FL_foot"]["n"] == 0


def test_csv_keeps_both_force_criteria_and_exact_threshold_decisions(tmp_path):
    force = np.zeros((1, 1, 4, 3), dtype=float)
    force[0, 0, :, 2] = [1.0, 1.01, 0.0, 2.0]
    force[0, 0, 0, 0] = 0.8  # norm > 1 although Fz == 1
    force[0, 0, 2, 0] = 1.1  # norm > 1 although Fz == 0
    alive = np.ones((1, 1, 1), dtype=bool)
    vx = np.array([[[0.1]]])
    path = write_csv(tmp_path / "raw.csv", ["fwd0.1"], [force], alive, vx, 0.02)

    with open(path, newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 1
    assert [rows[0][f"{name}_contact_fz_gt_1n"] for name in FOOT_ORDER] == ["0", "1", "0", "1"]
    assert [rows[0][f"{name}_contact_norm_gt_1n"] for name in FOOT_ORDER] == ["1", "1", "1", "1"]
    assert rows[0]["FR_foot_fz_n"] == "1.01"
    assert float(rows[0]["FL_foot_force_norm_n"]) == pytest.approx(np.sqrt(1.0**2 + 0.8**2))


def test_dual_summary_separates_force_norm_from_vertical_force():
    force = np.zeros((3, 1, 4, 3), dtype=float)
    force[:, :, :, 0] = 0.8
    force[:, :, :, 2] = 0.8
    alive = np.ones((3, 1), dtype=bool)
    vx = np.full((3, 1), -0.1)
    metrics = summarize_both(force, alive, vx, 0.02)
    assert metrics["force_norm_gt_1n"]["all_four_grounded_fraction"] == 1.0
    assert metrics["fz_gt_1n"]["all_four_grounded_fraction"] == 0.0


def test_gait_suite_has_exact_requested_lateral_and_backward_vectors():
    selected = commands("gait_speeds")
    assert {name: selected[name] for name in (
        "side+0.1", "side-0.1", "side+0.2", "side-0.2", "back0.1", "back0.2")
    } == {
        "side+0.1": (0.0, 0.1, 0.0), "side-0.1": (0.0, -0.1, 0.0),
        "side+0.2": (0.0, 0.2, 0.0), "side-0.2": (0.0, -0.2, 0.0),
        "back0.1": (-0.1, 0.0, 0.0), "back0.2": (-0.2, 0.0, 0.0),
    }


@pytest.mark.parametrize("mode", ("eval_gt", "eval_pred"))
def test_gait_contact_sweep_accepts_gt_and_policy_input_modes(mode):
    assert validate_map_mode(mode) == mode


def test_gait_contact_sweep_rejects_unrequested_map_modes():
    with pytest.raises(ValueError, match="eval_gt or eval_pred"):
        validate_map_mode("probe_prop_only")


def _known_r5_arrays():
    force = np.zeros((300, 64, 4, 3), dtype=np.float32)
    force[..., 0] = 1.1
    # One complete airborne interval per env and foot inside the [1, 6) window.
    force[50:100] = (1.1, 0.0, 0.0)  # norm contact, despite Fz == 0
    force[75] = 0.0
    height = np.full((300, 64, 4), 0.01, dtype=np.float32)
    height[75] = np.array([0.03, 0.04, 0.05, 0.06], dtype=np.float32)
    speed = np.full((300, 64, 4), 0.1, dtype=np.float32)
    alive = np.ones((300, 64), dtype=bool)
    return force, height, speed, alive


def test_r5_contact_evidence_recomputes_known_heights_drag_intervals_and_envs(tmp_path):
    force, height, speed, alive = _known_r5_arrays()
    path, digest = write_r5_raw_npz(
        tmp_path / "known.npz", force_xyz_n=force, foot_height_m=height,
        foot_xy_speed_mps=speed, alive=alive, command=(0.2, 0.0, 0.0),
        checkpoint_sha256="b" * 64, eval_seed=42, mode="eval_gt",
        code_head="c" * 40, dt=0.02,
    )
    result = build_r5_contact_evidence(
        [{"path": path, "sha256": digest}],
        checkpoint_sha256="b" * 64, dt=0.02,
    )
    assert result["format"] == "analyst-r5-contact-evidence/1"
    assert result["contact_definition"] == "norm_Fxyz_gt_1N"
    assert result["checkpoint_sha256"] == "b" * 64
    assert result["sources"] == [{"path": path, "sha256": digest}]
    assert result["feet"]["FL"]["complete_intervals"] == 64
    assert result["feet"]["FL"]["contributing_envs"] == 64
    assert result["feet"]["FL"]["single_sample_fraction"] == 1.0
    assert result["feet"]["FL"]["height_median_m"] == pytest.approx(0.03)
    assert result["feet"]["FL"]["height_peak_m"] == pytest.approx(0.03)
    assert result["feet"]["FL"]["drag_fraction"] == pytest.approx(249 / 250)
    assert result["feet"]["FL"]["negative_fraction_at_0p5"] == 1.0
    summary_path = write_r5_evidence_json(tmp_path / "r5_contact_evidence.json", result)
    with open(summary_path, encoding="utf-8") as stream:
        saved = json.load(stream)
    assert saved == result


def test_r5_npz_writer_records_norm_contact_identity_and_generated_checkpoint(tmp_path):
    force, height, speed, alive = _known_r5_arrays()
    path, digest = write_r5_raw_npz(
        tmp_path / "raw.npz", force_xyz_n=force, foot_height_m=height,
        foot_xy_speed_mps=speed, alive=alive, command=(0.2, 0.0, 0.0),
        checkpoint_sha256="b" * 64, eval_seed=42, mode="eval_pred",
        code_head="c" * 40, dt=0.02,
    )
    with np.load(path, allow_pickle=False) as raw:
        assert raw["format"].item() == "foothold-r5-contact-raw/1"
        assert raw["producer"].item() == "foothold_s2.eval.ex42_gait_contact"
        assert raw["contact_definition"].item() == "norm_Fxyz_gt_1N"
        assert raw["foot_names"].tolist() == ["FL", "FR", "RL", "RR"]
        assert raw["window_seconds"].tolist() == [1, 6]
        assert raw["contact"].dtype == np.bool_
        assert not raw["contact"][75, 0, 0]
        assert raw["force_xyz_n"][75, 0, 0, 2] == 0.0
        assert raw["foot_height_m"][75, 0, 0] == pytest.approx(0.03)
        identity = json.loads(raw["run_identity"].item())
        assert identity == {"checkpoint_sha256": "b" * 64, "eval_seed": 42,
                            "mode": "eval_pred", "code_head": "c" * 40}
    assert len(digest) == 64


def test_r5_raw_is_preserved_when_a_foot_has_no_complete_flight(tmp_path):
    force, height, speed, alive = _known_r5_arrays()
    force[...] = (1.1, 0.0, 0.0)
    path, digest = write_r5_raw_npz(
        tmp_path / "no-flight.npz", force_xyz_n=force, foot_height_m=height,
        foot_xy_speed_mps=speed, alive=alive, command=(0.2, 0.0, 0.0),
        checkpoint_sha256="b" * 64, eval_seed=42, mode="eval_gt",
        code_head="c" * 40, dt=0.02,
    )
    assert len(digest) == 64
    with pytest.raises(ValueError, match="complete per-foot intervals"):
        build_r5_contact_evidence([{"path": path, "sha256": digest}],
                                  checkpoint_sha256="b" * 64, dt=0.02)


def test_r5_evidence_rejects_missing_checkpoint_or_wrong_contact_contract():
    force, height, speed, alive = _known_r5_arrays()
    source = dict(force_xyz_n=force, foot_height_m=height, foot_xy_speed_mps=speed,
                  alive=alive, mode="eval_gt", command=(0.2, 0.0, 0.0),
                  path="raw.npz", sha256="a" * 64,
                  checkpoint_sha256="b" * 64,
                  run_identity={"checkpoint_sha256": "b" * 64, "eval_seed": 42,
                                "mode": "eval_gt", "code_head": "c" * 40})
    with pytest.raises(ValueError, match="checkpoint"):
        build_r5_contact_evidence([source], checkpoint_sha256=None, dt=0.02)
    with pytest.raises(ValueError, match="dt=0.02"):
        build_r5_contact_evidence([source], checkpoint_sha256="b" * 64, dt=0.01)


def test_r5_evidence_rejects_raw_force_mask_disagreement_even_with_updated_sha(tmp_path):
    force, height, speed, alive = _known_r5_arrays()
    path, _ = write_r5_raw_npz(
        tmp_path / "mutant.npz", force_xyz_n=force, foot_height_m=height,
        foot_xy_speed_mps=speed, alive=alive, command=(0.2, 0.0, 0.0),
        checkpoint_sha256="b" * 64, eval_seed=42, mode="eval_gt",
        code_head="c" * 40, dt=0.02,
    )
    with np.load(path, allow_pickle=False) as archive:
        values = {key: archive[key] for key in archive.files}
    values["contact"][50, 0, 0] = False
    np.savez_compressed(path, **values)
    with open(path, "rb") as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    with pytest.raises(ValueError, match=r"norm\(Fxyz\)>1N"):
        build_r5_contact_evidence([{"path": path, "sha256": digest}],
                                  checkpoint_sha256="b" * 64, dt=0.02)


def test_foot_sole_height_uses_go2_sphere_offset_radius_and_flat_origin():
    pos = np.zeros((1, 1, 4, 3), dtype=float)
    pos[..., 2] = 0.4
    quat = np.zeros((1, 1, 4, 4), dtype=float)
    quat[..., 0] = 1.0
    result = foot_sole_height_m(pos, quat, np.array([0.0]))
    assert result.shape == (1, 1, 4)
    assert result[0, 0, 0] == pytest.approx(0.4 - 0.022)


def test_foot_sole_height_sign_is_positive_above_flat_support():
    pos = np.zeros((2, 1, 4, 3), dtype=float)
    pos[0, ..., 2] = 0.022  # collision sphere bottom exactly touches z=0
    pos[1, ..., 2] = 0.072  # sole is 5 cm above the same support plane
    quat = np.zeros((2, 1, 4, 4), dtype=float)
    quat[..., 0] = 1.0

    result = foot_sole_height_m(pos, quat, np.array([0.0]))

    assert result[0, 0, 0] == pytest.approx(0.0)
    assert result[1, 0, 0] == pytest.approx(0.05)
    assert result[1, 0, 0] > result[0, 0, 0]


def test_foot_sole_height_uses_signed_go2_center_offset_after_rotation():
    pos = np.zeros((1, 1, 4, 3), dtype=float)
    pos[..., 2] = 0.022
    quat = np.zeros((1, 1, 4, 4), dtype=float)
    quat[..., 0] = np.sqrt(0.5)
    quat[..., 2] = np.sqrt(0.5)  # +90 degrees about body Y rotates local -X upward.

    result = foot_sole_height_m(pos, quat, np.array([0.0]))

    assert result[0, 0, 0] == pytest.approx(0.002)


def test_r5_drag_height_threshold_is_strictly_below_two_centimeters(tmp_path):
    force, height, speed, alive = _known_r5_arrays()
    height[50:300] = 0.03
    height[50] = 0.019
    height[51] = 0.020
    height[52] = 0.021
    path, digest = write_r5_raw_npz(
        tmp_path / "drag-boundary.npz", force_xyz_n=force, foot_height_m=height,
        foot_xy_speed_mps=speed, alive=alive, command=(0.2, 0.0, 0.0),
        checkpoint_sha256="b" * 64, eval_seed=42, mode="eval_gt",
        code_head="c" * 40, dt=0.02,
    )

    result = build_r5_contact_evidence(
        [{"path": path, "sha256": digest}], checkpoint_sha256="b" * 64, dt=0.02,
    )

    # Only the 1.9 cm samples count. The 2.0 cm boundary is excluded.
    assert result["feet"]["FL"]["drag_fraction"] == pytest.approx(1 / 250)


def test_r5_evidence_rejects_checkpoint_identity_mismatch(tmp_path):
    force, height, speed, alive = _known_r5_arrays()
    path, digest = write_r5_raw_npz(
        tmp_path / "checkpoint-mismatch.npz", force_xyz_n=force, foot_height_m=height,
        foot_xy_speed_mps=speed, alive=alive, command=(0.2, 0.0, 0.0),
        checkpoint_sha256="b" * 64, eval_seed=42, mode="eval_gt",
        code_head="c" * 40, dt=0.02,
    )

    with pytest.raises(ValueError, match="source checkpoint differs"):
        build_r5_contact_evidence(
            [{"path": path, "sha256": digest}], checkpoint_sha256="d" * 64, dt=0.02,
        )


def test_r5_evidence_rejects_stale_raw_sha_after_file_changes(tmp_path):
    force, height, speed, alive = _known_r5_arrays()
    path, original_digest = write_r5_raw_npz(
        tmp_path / "stale-sha.npz", force_xyz_n=force, foot_height_m=height,
        foot_xy_speed_mps=speed, alive=alive, command=(0.2, 0.0, 0.0),
        checkpoint_sha256="b" * 64, eval_seed=42, mode="eval_gt",
        code_head="c" * 40, dt=0.02,
    )
    with np.load(path, allow_pickle=False) as archive:
        values = {key: archive[key] for key in archive.files}
    values["foot_height_m"][50, 0, 0] += 0.001
    np.savez_compressed(path, **values)

    with pytest.raises(ValueError, match="SHA mismatch"):
        build_r5_contact_evidence(
            [{"path": path, "sha256": original_digest}], checkpoint_sha256="b" * 64, dt=0.02,
        )
