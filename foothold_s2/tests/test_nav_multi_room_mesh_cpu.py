import json

import numpy as np

from foothold_s2.nav import room_generator as rg
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh


def test_six_rooms_share_one_x_spaced_mesh_and_keep_their_starts_inside(tmp_path):
    rooms = [rg.make_room(seed, rg.FIRST_ROUND_CFG)[1] for seed in range(6)]

    manifest = rg.write_rooms(rooms, tmp_path, n_starts=4, start_seed=73)
    mesh = load_combined_mesh(tmp_path / "terrain_mesh.npz", manifest["mesh_sha256"])
    origins = mesh["origins"]

    assert origins.shape == (6, 4, 3)
    assert mesh["column_family"] == ["room"] * 4
    assert manifest["room_count"] == 6
    assert manifest["room_gap_m"] == rg.ROOM_GAP_M
    assert manifest["mesh_sha256"] == "a81203c0254c55462f1effc4759d98499fc091c993d514bd7fadeafb882204f0"
    assert manifest["mesh_sha256"] == load_combined_mesh(
        tmp_path / "terrain_mesh.npz"
    )["mesh_sha256"]

    vertices = mesh["vertices"]
    pitch = rg.ROOM_M + rg.ROOM_GAP_M
    assert np.isclose(vertices[:, 0].min(), 0.0)
    assert np.isclose(vertices[:, 0].max(), (len(rooms) - 1) * pitch + rg.ROOM_M)
    for row, room in enumerate(rooms):
        offset = row * pitch
        local = origins[row].copy()
        local[:, 0] -= offset
        assert np.all((local[:, 0] >= 0.0) & (local[:, 0] < rg.ROOM_M))
        assert np.all((local[:, 1] >= 0.0) & (local[:, 1] < rg.ROOM_M))
        ij = np.floor(local[:, [1, 0]] / rg.RES).astype(int)
        assert (room.cell[ij[:, 0], ij[:, 1]] == rg.CELL_FLAT).all()
        assert np.allclose(local[:, 2], room.height[ij[:, 0], ij[:, 1]])
    for row in range(len(rooms) - 1):
        gap_lo = row * pitch + rg.ROOM_M
        gap_hi = (row + 1) * pitch
        assert not ((vertices[:, 0] > gap_lo + 1e-6) &
                    (vertices[:, 0] < gap_hi - 1e-6)).any()

    saved = json.loads((tmp_path / "room_manifest.json").read_text(encoding="utf-8"))
    assert saved["mesh_sha256"] == manifest["mesh_sha256"]
    assert saved["origins_shape"] == [6, 4, 3]


def test_origin_xy_of_a_multi_room_mesh_drops_the_row_shift_and_keeps_the_start_point(tmp_path):
    """reviewer 03:35: body -> room frame subtracts the room row's x shift (row x pitch), not the env origin."""
    import numpy as np
    from foothold_s2.nav import grade_map as gm, nav_task as nt, room_generator as rg
    from pathlib import Path
    table = gm.load_grade_table(Path(__file__).resolve().parents[1] / "nav" / "grade_table_draft.yaml")
    rooms = [rg.make_room(s, rg.FIRST_ROUND_CFG, table)[1] for s in (3, 4)]
    manifest = rg.write_rooms(rooms, tmp_path, n_starts=4)
    origins = np.load(tmp_path / "terrain_mesh.npz")["origins"]                   # (rooms, K, 3), mesh frame
    rows = np.array([1, 0, 1, 0]); cols = np.array([2, 3, 0, 1])
    world_xy = origins[rows, cols, :2]
    got = nt.room_frame_origin_xy(world_xy, rows, manifest["room_pitch_m"])
    for k in range(4):
        local = np.array(manifest["rooms"][rows[k]]["starts_local_xyz"])[cols[k], :2]
        assert np.allclose(got[k], local, atol=1e-3)                              # the room-frame origin is the start point in room frame
    assert not np.allclose(got[0], world_xy[0])                                   # row 1 was shifted by one pitch
    task = nt.NavTask([nt.make_asset(r, table) for r in rooms], 4, np.random.default_rng(0))
    task.set_rooms_from_rows(rows, env_origins_xy=world_xy, pitch_m=manifest["room_pitch_m"])
    assert np.allclose(task.origin_xy, got) and list(task.room_id) == list(rows)
