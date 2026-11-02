"""C76 m6000 plan uses known fixed terrain assignments and pinned inputs."""

from pathlib import Path
import sys

import pytest

from foothold_s2.eval import c_layer_queue as queue
from foothold_s2.eval import plan_c_layer as planner
from foothold_s2.terrains import columns


def test_assignments_match_fixed64_and_sparse50_columns():
    layout = planner.assignments()
    names = columns.column_types(columns.FULL, 50)
    for kind in planner.KINDS["continuous"]:
        env, col = layout[kind]
        assert env == col and names[col] == kind
    for kind in planner.KINDS["sparse"]:
        env, col = layout[kind]
        assert names[col] == kind
        assert [names[i] for i in planner.fixed_terrain.sparse_column_ids(names)][env] == kind


def test_complete_m6000_plan_and_wrong_checkpoint_rejected(tmp_path, monkeypatch):
    checkpoint = tmp_path / "model_6000.pt"
    checkpoint.write_bytes(b"known checkpoint")
    source = tmp_path / "source"
    source_file = source / "foothold_s2/eval/record_sol23f.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("# source\n", encoding="utf-8")
    recorder = tmp_path / "record_c_layer.py"
    recorder.write_text("# C_LAYER_SEED_V1\n", encoding="utf-8")
    (tmp_path / "overlay_25e.py").write_text("# fixed overlay\n", encoding="utf-8")
    composer = tmp_path / "compose.py"
    composer.write_text('VIDEO_RULE_VERSION = "v3.1-D137"\n', encoding="utf-8")
    monkeypatch.setattr(planner, "_head", lambda _root: "a" * 40)
    actual_sha = queue.sha256
    monkeypatch.setattr(queue, "sha256", lambda path: "d5e9ec40" + "a" * 56
                        if Path(path) == checkpoint else actual_sha(Path(path)))
    kw = dict(checkpoint=checkpoint, source_root=source, recorder=recorder,
              composer=composer, python=Path(sys.executable), playlist_dir=tmp_path / "_playlists",
              priority_markers={key: tmp_path / (key + ".busy")
                                for key in ("training", "evaluation", "a_layer")}, device="cuda:0")
    plan = planner.build_plan(**kw)
    assert plan["iteration"] == 6000 and len(plan["jobs"]) == 216
    assert queue.validate_plan(plan)["missing"] == 0
    assert all("-m6000-" in row["label"] for row in plan["jobs"])
    assert {row["map_mode"] for row in plan["jobs"]} == set(queue.MAP_MODES)
    wrong = tmp_path / "model_8000.pt"
    wrong.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="model_6000"):
        planner.build_plan(**{**kw, "checkpoint": wrong})
