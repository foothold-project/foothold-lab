"""kit_factories 의 CPU 부분: 설정 검사 · 방 만들기 (한 메시 · 줄 = 방) · 줄 이동량을 뺀 방 틀 원점."""
import json
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.nav import kit_factories as kf, room_generator as rg

TABLE = Path(__file__).resolve().parents[1] / "nav" / "grade_table_draft.yaml"


def _cfg(tmp_path, **kw):
    c = {"lower_checkpoint": "x", "lower_sha256": "y", "num_envs": 6, "device": "cpu", "seed": 0, "room_count": 2, "room_seed": 3, "n_starts": 3,
         "room_dir": str(tmp_path / "rooms"), "grade_table": str(TABLE)}
    c.update(kw)
    return c


def test_config_requires_every_key_and_positive_counts(tmp_path):
    p = tmp_path / "c.json"
    c = _cfg(tmp_path); del c["seed"]
    p.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="seed"):
        kf.load_config(p)
    p.write_text(json.dumps(_cfg(tmp_path, n_starts=0)))
    with pytest.raises(ValueError, match=">= 1"):
        kf.load_config(p)
    with pytest.raises(RuntimeError):
        kf.load_config(None)


def test_prepare_rooms_writes_one_mesh_with_a_row_per_room_and_refuses_to_overwrite(tmp_path):
    cfg = _cfg(tmp_path)
    r = kf.prepare_rooms(cfg)
    assert r["manifest"]["format"] == "hipan-rooms/1" and len(r["assets"]) == 2 and r["mesh"].exists()
    assert np.load(r["mesh"])["origins"].shape == (2, 3, 3)
    with pytest.raises(FileExistsError):
        kf.prepare_rooms(cfg)


def test_make_task_converts_with_the_row_shift_not_the_env_origin(tmp_path):
    r = kf.prepare_rooms(_cfg(tmp_path))
    rows = np.array([0, 1, 0, 1, 0, 1])
    local = np.array(r["manifest"]["rooms"][0]["starts_local_xyz"])[:, :2]
    org = np.array([[local[0, 0] + rows[i] * (rg.ROOM_M + rg.ROOM_GAP_M), local[0, 1]] for i in range(6)])
    task = kf.make_task(r["assets"], 6, 0, rows, org)
    assert (task.room_id == rows).all() and np.allclose(task.origin_xy, np.tile(local[0], (6, 1)))
