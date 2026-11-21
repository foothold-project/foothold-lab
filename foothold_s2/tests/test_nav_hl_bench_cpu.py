"""HiPAN 원문 시험 평가 (hl_bench) 의 CPU 부분: 시작점 그대로 쓰는 방 메시 · 과제 표 (시작점 -> 그 과제 목표) · 기록기 종료 원인 · 채점 ·
결과 폴더 sha 목록 대조. Kit 없음."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from foothold_s2.nav import bench_tasks as bt
from foothold_s2.nav import grade_map as gm
from foothold_s2.nav import hl_bench as hb
from foothold_s2.nav import nav_task
from foothold_s2.nav import room_generator as rg


@pytest.fixture(scope="module")
def docs(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench")
    for kind in bt.TYPES:
        (out / f"tasks_{kind}.json").write_text(json.dumps(bt.make_type_tasks(kind, per_band=2)), encoding="utf-8")
    return hb.load_docs(out), out


def test_rooms_keep_the_task_starts_as_mesh_origins(docs, tmp_path):
    d, _ = docs
    rooms, starts = hb.bench_rooms(d)
    rg.write_rooms(rooms, tmp_path, starts_by_room=starts)
    origins = np.load(tmp_path / "terrain_mesh.npz")["origins"]
    assert origins.shape == (4, 6, 3)
    for r, doc in enumerate(d):
        local = origins[r, :, :2] - np.array([r * (rg.ROOM_M + rg.ROOM_GAP_M), 0.0])
        assert np.allclose(local, [t["start_xy"] for t in doc["tasks"]])
    with pytest.raises(ValueError, match="same K"):
        rg.write_rooms(rooms, tmp_path / "x", starts_by_room=[s[:3] if i else s for i, s in enumerate(starts)])


def test_the_table_gives_each_start_its_own_task_goal(docs):
    d, _ = docs
    rooms, _ = hb.bench_rooms(d)
    table = gm.load_grade_table(bt.NAV / "grade_table_draft.yaml")
    task = nav_task.NavTask([nav_task.make_asset(r, table) for r in rooms], 4, np.random.default_rng(0))
    task.room_id = np.arange(4)
    sha = hb.install_bench_table(task, d)
    assert len(sha) == 64 and task.table_tol_m == hb.BENCH_TOL_M
    for r, doc in enumerate(d):
        for t in doc["tasks"]:
            goal, pts = task._table_pick(r, np.array(t["start_xy"]))
            assert np.allclose(goal, t["goal_xy"]) and np.allclose(pts[0], t["start_xy"])
            assert hb.task_of(d, r, t["start_xy"]) == t["id"]
    assert task._table_pick(0, np.array(d[0]["tasks"][0]["start_xy"]) + 1.0) is None       # 시작점이 아닌 자리는 표 밖


def _state(n, pos, done=False, timed_out=False, collision=False):
    q = np.zeros((n, 4)); q[:, 0] = 1.0
    return SimpleNamespace(quat_w=q, track_err=np.zeros((2, n, 3)), pos_local=np.column_stack([pos, np.full(n, 0.3)]),
                           vel_b=np.zeros((n, 3)), yaw_rate=np.zeros(n), applied=np.zeros((n, 5)),
                           collision=np.full(n, collision), done=np.full(n, done), timed_out=np.full(n, timed_out))


def test_recorder_tells_reached_fall_timeout_and_stuck_apart():
    rec = hb.BenchRecorder(4, 200, 0.1)
    for t in range(60):
        pos = np.array([[0.1 * t, 0], [0.1 * t, 0], [0.1 * t, 0], [1.0, 1.0]])
        done = t == 59
        st = _state(4, pos, done=done, timed_out=done)
        st.done = np.array([False, t == 30, done, done]); st.timed_out = np.array([False, False, done, done])
        rec.observe(st, pos, reached=np.array([t == 20, False, False, False]))
    assert list(rec.reason) == ["reached", "fall", "timeout", "stuck"]
    assert list(rec.end_tick) == [20, 30, 59, 59] and np.isnan(rec.traj[21, 0]).all() and not np.isnan(rec.traj[21, 2]).any()


def test_score_and_end_facts(docs):
    d, _ = docs
    doc = d[0]
    t = doc["tasks"][0]
    good = {"env_id": 0, "task_id": 0, "path_xy": [t["start_xy"], t["goal_xy"]], "collisions": 0}
    dup = {"env_id": 5, "task_id": 0, "path_xy": [t["start_xy"]], "collisions": 0}
    s = hb.score_type(doc, [dup, good])
    assert s["tasks_covered"] == 1 and s["sr"] == 1.0 and 0 < s["spl"] <= 1.0          # 같은 과제는 env 번호가 작은 쪽
    rooms, _ = hb.bench_rooms(d)
    g = gm.make_grade_map(rooms[0], gm.load_grade_table(bt.NAV / "grade_table_draft.yaml"))
    f = hb.end_facts(rooms[0], g, np.array(t["goal_xy"]), np.array(t["start_xy"]))
    assert f["passage_width_m"] > 0 and abs(f["goal_shortest_from_end_m"] - t["shortest_m"]) < 0.3


def test_manifest_catches_a_missing_or_changed_file(tmp_path):
    (tmp_path / "a.json").write_text("1"); (tmp_path / "sub").mkdir(); (tmp_path / "sub" / "b.npz").write_bytes(b"xy")
    hb.write_manifest(tmp_path)
    assert hb.verify_manifest(tmp_path) == []
    (tmp_path / "sub" / "b.npz").write_bytes(b"xz")
    assert len(hb.verify_manifest(tmp_path)) == 2
    (tmp_path / "sub" / "b.npz").unlink()
    assert len(hb.verify_manifest(tmp_path)) == 1


def test_print_mode_runs_without_kit(docs, capsys):
    _, out = docs
    assert hb.main(["--model", "x.pt", "--tasks-dir", str(out), "--out", "/nonexistent/o", "--print"]) == 0
    got = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert got["tasks_per_type"] == 6 and got["num_envs_needed"] == 24 and got["seeds"] == list(range(10)) and got["success_m"] == 0.2


def test_every_task_gets_exactly_one_env():
    import torch
    origins = torch.arange(4 * 6 * 3, dtype=torch.float32).reshape(4, 6, 3)
    t = SimpleNamespace(terrain_origins=origins, terrain_levels=torch.zeros(24, dtype=torch.long),
                        terrain_types=torch.zeros(24, dtype=torch.long), env_origins=torch.zeros(24, 3))
    hb.assign_bench_envs(t, 24)
    pairs = set(zip(t.terrain_levels.tolist(), t.terrain_types.tolist()))
    assert len(pairs) == 24 and torch.equal(t.env_origins[7], origins[3, 1])
    with pytest.raises(ValueError, match="num_envs = rooms x starts"):
        hb.assign_bench_envs(t, 20)
