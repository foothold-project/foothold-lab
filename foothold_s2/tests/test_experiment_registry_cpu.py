from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from foothold_s2.experiment_registry import (
    FORMAT,
    REPO_ROOT,
    load_experiment,
    operational_definition,
    output_paths,
    source_path,
    device_contract,
    device_contract_sha256,
    queue_gpu_identity,
)


def test_ex41_definition_matches_current_operational_inputs_and_paths():
    exp = load_experiment("EX-41")
    values = exp["operational_values"]
    assert device_contract(exp) == {
        "training": "cuda:0", "evaluation": "cuda:1",
        "video": "cuda:1", "w78": "cuda:1",
    }
    plan = yaml.safe_load(source_path(exp, "curriculum").read_text(encoding="utf-8"))
    score = json.loads(source_path(exp, "score_config").read_text(encoding="utf-8"))

    assert values["parent"]["update"] == plan["parent_update"] == 6000
    assert source_path(exp, "maintenance_map64").as_posix().endswith("score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json")
    assert values["parent"]["sha256"] == plan["parent_sha256"]
    assert values["training"]["interval_updates"] == plan["fixed_schedule"]["interval_updates"] == 250
    assert [r["dr_scale"] for r in values["training"]["stages"]] == plan["fixed_schedule"]["dr_stage_end_scales"]
    assert [r["push_vmax_mps"] for r in values["training"]["stages"]] == plan["fixed_schedule"]["push_vmax_mps"]
    assert values["evaluation"]["checkpoint_first"] == score["checkpoint_first"]
    assert values["evaluation"]["checkpoint_stride"] == score["checkpoint_stride"]
    assert values["evaluation"]["environments"] == score["envs"]

    actual = output_paths(exp, "20261106_170000", s2_lab="C:/Users/AI-WS01/s2_lab",
                          run_name="EX-41-B-main_20261106_170000")
    expected_root = Path("C:/Users/AI-WS01/s2_lab/ex41_main_20261106_170000")
    assert actual["root"] == expected_root
    assert actual["main"] == expected_root / "main/EX-41-B-main_20261106_170000"
    assert actual["scores"] == expected_root / "eval/scores"
    assert actual["push250"] == expected_root / "eval/push250"
    assert actual["score_watch"] == expected_root / "eval/score-watch"


def test_ex42_definition_points_at_preparation_contract_and_approved_schedule():
    exp = load_experiment("EX-42")
    plan = yaml.safe_load(source_path(exp, "curriculum").read_text(encoding="utf-8"))
    approvals = yaml.safe_load(source_path(exp, "approvals").read_text(encoding="utf-8"))
    assert exp["status"] == "preparation_only"
    assert exp["operational_values"]["operations_enabled"] is False
    assert exp["operational_values"]["training"]["stages_from"] == exp["files"]["curriculum"]
    assert plan["status"] == "preparation_only"
    assert approvals["domain_randomization"]["decision_id"] == "lead-relay-teamlead-20261106-1725-dr-1.0-fixed"


def test_registry_accepts_new_definition_without_code_identifier_changes(tmp_path):
    registry = tmp_path / "experiments"
    registry.mkdir()
    document = {
        "format": FORMAT, "experiment_id": "EX-99", "status": "preparation_only",
        "files": {}, "paths": {"slug": "ex99", "root_template": "{slug}_{stamp}",
                                 "directories": {"scores": "eval/scores"}},
    }
    (registry / "EX-99.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")
    assert load_experiment("EX-99", registry_root=registry)["experiment_id"] == "EX-99"
    with pytest.raises(FileNotFoundError):
        load_experiment("EX-98", registry_root=registry)

    source = (REPO_ROOT / "foothold_s2/experiment_registry.py").read_text(encoding="utf-8")
    assert not re.search(r"EX-(?:41|42|99)|ex(?:41|42|99)_", source, re.IGNORECASE)


def test_registry_rejects_explicit_path_escape_and_bad_stamp():
    exp = load_experiment("EX-41")
    broken = {**exp, "paths": {**exp["paths"], "directories": {"scores": "../scores"}}}
    with pytest.raises(ValueError, match="unsafe"):
        output_paths(broken, "20261106_170000", s2_lab="C:/Users/AI-WS01/s2_lab")
    with pytest.raises(ValueError, match="stamp"):
        output_paths(exp, "now", s2_lab="C:/Users/AI-WS01/s2_lab")


def test_operational_experiment_registry_paths_and_preparation_guard(tmp_path):
    from foothold_s2.experiment_registry import operational_definition, paths_for_run
    ex41 = operational_definition("EX-41")
    root = tmp_path / "ex41_main_20261106_220000"
    run = root / "main" / "EX-41-B-main_20261106_220000"
    run.mkdir(parents=True)
    paths = paths_for_run(ex41, run)
    assert paths["root"] == root
    assert paths["scores"] == root / "eval" / "scores"
    assert paths["push250"] == root / "eval" / "push250"
    assert paths["score_watch"] == root / "eval" / "score-watch"
    with pytest.raises(ValueError, match="operations are not enabled"):
        operational_definition("EX-42")


def test_operating_tools_do_not_embed_a_new_experiment_name():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    paths = [root / "foothold_s2/ex41_score_watch.py",
             root / "foothold_s2/eval/ex41_push250_watch.py",
             root / "_out/tools/ex41/boundary_report.py"]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "EX-42" not in source
    with pytest.raises(FileNotFoundError):
        load_experiment("EX-99")


def test_stage_end_jobs_take_identity_and_contract_from_experiment(tmp_path, monkeypatch):
    from foothold_s2 import ex41_score_watch as watch
    definition = operational_definition("EX-41")
    checkpoint = tmp_path / "model_750.pt"
    checkpoint.write_bytes(b"known checkpoint")
    source = tmp_path / "video-source"
    source.mkdir()
    monkeypatch.setattr(watch, "_stage_video_contract", lambda _definition: (source, (("W57", "fwd1.0", "eval_gt"),)))
    jobs = watch.stage_end_queue_specs(checkpoint, tmp_path / "score-watch" / "model_750_abcd",
                                      {"envs": 64, "map_steps": 10, "eval_seed": 42},
                                      definition=definition)
    assert jobs[0]["id"].startswith("ex41-stage-")
    assert jobs[0]["owner"] == "ex41_score_watch"
    w78 = next(row for row in jobs if row["phase"] == "w78_v2:eval_gt:stairs_side_left")
    args = w78["argv"]
    assert args[args.index("--terrain-levels") + 1] == "2,5"
    assert args[args.index("--stair-start-angles-deg") + 1] == "0,30,60,90"
    assert args[args.index("--terrain-skill-v2-cases") + 1] == "stairs_side_left"


def test_stage_end_jobs_read_each_device_role_and_queue_gpu_from_definition(tmp_path, monkeypatch):
    from copy import deepcopy
    from foothold_s2 import ex41_score_watch as watch
    definition = deepcopy(operational_definition("EX-41"))
    definition["devices"] = {"training": "cuda:0", "evaluation": "cuda:0",
                             "video": "cuda:1", "w78": "cuda:0"}
    checkpoint = tmp_path / "model_750.pt"
    checkpoint.write_bytes(b"known checkpoint")
    source = tmp_path / "video-source"
    source.mkdir()
    monkeypatch.setattr(watch, "_stage_video_contract",
                        lambda _definition: (source, (("W57", "fwd1.0", "eval_gt"),)))
    jobs = watch.stage_end_queue_specs(
        checkpoint, tmp_path / "score-watch", {"envs": 64, "map_steps": 10, "eval_seed": 42},
        definition=definition)
    by_phase = {row["phase"]: row for row in jobs}
    assert by_phase["axis_v2"]["gpu"] == 0
    assert by_phase["axis_v2"]["gpu_uuid"] == "GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b"
    assert by_phase["axis_v2"]["argv"][by_phase["axis_v2"]["argv"].index("--device") + 1] == "cuda:0"
    w78 = by_phase["w78_v2:eval_gt:stairs_side_left"]
    assert w78["gpu"] == 0 and w78["argv"][w78["argv"].index("--device") + 1] == "cuda:0"
    video = by_phase["W57:fwd1.0:eval_gt"]
    assert video["gpu"] == 1 and video["argv"][video["argv"].index("--device") + 1] == "cuda:1"


def test_device_contract_is_complete_and_canonical():
    exp = operational_definition("EX-41")
    changed = {**exp, "devices": {**exp["devices"], "evaluation": "cuda:0"}}
    assert device_contract_sha256(changed) != device_contract_sha256(exp)
    assert queue_gpu_identity("cuda:0") == (0, "c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b")
    invalid = {**exp, "devices": {**exp["devices"], "w78": "cuda:9"}}
    with pytest.raises(ValueError, match="registered CUDA"):
        device_contract(invalid)


