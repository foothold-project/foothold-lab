import json

import numpy as np

from foothold_s2.eval.map_error import record_only_summary
from foothold_s2.ex41_score_watch import map64_stand_error_record_only


def test_record_only_summary_uses_only_paired_finite_environment_rows():
    summary = record_only_summary(
        [1.0, 2.0, float("nan"), 100.0],
        [4.0, float("nan"), 9.0, 20.0],
        source="known.npz",
    )
    assert summary == {
        "schema": "foothold-map-error-record-only/1",
        "decision_use": "none_record_only",
        "source": "known.npz",
        "state": "measured",
        "mean_of_env_step_means_cm": 50.5,
        "maximum_env_step_cellmax_cm": 20.0,
        "valid_envs": 2,
    }


def test_score_watch_reads_map64_and_stand_error_as_record_only(tmp_path):
    map_dir = tmp_path / "map64"
    map_dir.mkdir()
    np.savez(map_dir / "env_arrays_eval_pred_fwd.npz", env=np.arange(2))
    summary = {
        "schema": "foothold-map-error-record-only/1",
        "decision_use": "none_record_only",
        "source": "env_arrays_eval_pred_fwd.npz:map_err_all_*_cm",
        "state": "measured",
        "mean_of_env_step_means_cm": 1.5,
        "maximum_env_step_cellmax_cm": 5.0,
        "valid_envs": 2,
    }
    map_doc = {
        "env_arrays": {"eval_pred/fwd": "env_arrays_eval_pred_fwd.npz"},
        "modes": {"eval_pred": {"fwd": {
            "restoration_error_record_only": summary,
        }}},
    }
    map_path = map_dir / "map_modes.json"
    map_path.write_text(json.dumps(map_doc), encoding="utf-8")
    stand_paths = {}
    for mode in ("eval_gt", "probe_prop_only", "eval_pred"):
        stand_dir = tmp_path / f"stand_{mode}"
        stand_dir.mkdir()
        np.savez(stand_dir / "stand_raw.npz", map_err_all_mean_cm=np.array([1.0]))
        (stand_dir / "stand.json").write_text(json.dumps({
            "restoration_error_record_only": summary,
        }), encoding="utf-8")
        stand_paths[mode] = stand_dir / "stand.json"

    result, refs = map64_stand_error_record_only(map_path, stand_paths)
    assert result["decision_use"] == "none_record_only"
    assert result["map64"]["eval_pred"]["fwd"]["maximum_env_step_cellmax_cm"] == 5.0
    assert set(result["stand"]) == {"eval_gt", "probe_prop_only", "eval_pred"}
    assert len(refs) == 5
