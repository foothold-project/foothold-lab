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
