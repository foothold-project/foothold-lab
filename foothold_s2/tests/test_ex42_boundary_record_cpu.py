"""Boundary evaluation attaches the G1 / G1b bundles (record only) and writes brief.json. No Kit, no GPU."""
from __future__ import annotations

import json
from pathlib import Path

from foothold_s2 import ex42_eval_once as once
from foothold_s2.ex42_score import config


def _rows(tmp_path):
    cfg = config()[0]
    return once.g1_record_commands("/c/model_250.pt", tmp_path, "cuda:0", cfg, eval_seed=7, mesh_dir="/m",
                                   evaluation_plan=None)


def test_g1_and_g1b_run_as_record_only_eval_gt_children(tmp_path):
    rows = _rows(tmp_path)
    assert [r["name"] for r in rows] == ["hipan_g1", "hipan_g1b"]
    for r in rows:
        a = r["argv"]
        assert a[a.index("--command-suite") + 1] == r["name"] and a[a.index("--modes") + 1] == "eval_gt"
        assert a[a.index("--eval-seed") + 1] == "7" and a[a.index("--mesh-dir") + 1] == "/m"
        assert Path(a[a.index("--out") + 1]) == tmp_path / "record_only" / r["name"]


def test_the_scored_bundle_does_not_contain_the_record_only_suites(tmp_path):
    names = {c["name"] for c in once.commands("/c/model_250.pt", tmp_path, "cuda:0", config()[0], eval_seed=7)}
    assert not names & {"hipan_g1", "hipan_g1b"}


def _g1_file(path, name="side"):
    env = {"vx_abs_error_mean_alive_mps": 0.1, "vy_abs_error_mean_alive_mps": 0.2, "wz_abs_error_mean_alive_radps": 0.0}
    doc = {"commands": {name: [0.0, 0.4, 0.0]},
           "modes": {"eval_gt": {name: {"alive_envs_at_end": 64, "per_env": [env]}}}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))


def test_brief_collects_the_record_only_results_and_links_the_previous_label(tmp_path):
    _g1_file(tmp_path / "record_only" / "hipan_g1" / "map_modes.json")
    score = tmp_path / "ex42_score.json"
    score.write_text(json.dumps({"judgement": "HOLD", "maintenance_judgement": "PASS", "reason": "x"}))
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps({"label": "E1_m250"}))
    res = once.write_boundary_brief(tmp_path, label="E1_m500", iteration=500, score_path=score, events_dir=None,
                                    prev_brief=prev)
    assert res["state"] == "done"
    doc = json.loads((tmp_path / "brief.json").read_text())
    assert doc["g1"]["rows"]["side"]["follow"] == {"vy": 0.5}
    assert doc["g1b"] == "없음" and doc["d44"] == "없음" and doc["prev_label"] == "E1_m250"
    assert doc["score"]["judgement"] == "HOLD"                       # copied, never decided here


def test_a_broken_source_is_recorded_and_does_not_raise(tmp_path):
    bad = tmp_path / "record_only" / "hipan_g1" / "map_modes.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json")
    res = once.write_boundary_brief(tmp_path, label="E1_m500", iteration=500, score_path=tmp_path / "none.json",
                                    events_dir=None)
    assert res["state"] == "failed" and not (tmp_path / "brief.json").exists()
