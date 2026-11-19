"""CPU tests for the cropped evaluation mesh (crop_to_cells, crop_cells_for, and that the default path is untouched)."""
import hashlib
import pathlib

import numpy as np
import pytest

from foothold_s2.eval import ex42_mesh_eval
from foothold_s2.terrains import ex42_mesh_mount as mm


def _grid_mesh(rows=3, cols=4, tile=8.0):
    """One quad (two triangles) per tile and a 0.5 m-high step, origins at the tile centres, rows along x."""
    vertices, faces, origins = [], [], np.zeros((rows, cols, 3))
    for r in range(rows):
        for c in range(cols):
            x0, y0 = r * tile, c * tile
            base = len(vertices)
            vertices += [[x0, y0, 0.0], [x0 + tile, y0, 0.5], [x0 + tile, y0 + tile, 0.0], [x0, y0 + tile, 0.5]]
            faces += [[base, base + 1, base + 2], [base, base + 2, base + 3]]
            origins[r, c] = [x0 + tile / 2, y0 + tile / 2, 0.0]
    return np.array(vertices, dtype=np.float32), np.array(faces, dtype=np.int32), origins


def test_crop_keeps_the_cell_and_its_margin_and_nothing_else():
    v, f, o = _grid_mesh()
    tile_x, tile_y = np.full(4, 8.0), 8.0
    nv, nf, rec = mm.crop_to_cells(v, f, o, tile_x, tile_y, [(1, 2)], 0.0)
    assert rec["faces_before"] == len(f) == 24 and rec["faces_after"] == 2 and rec["cells"] == [[1, 2]]
    assert {tuple(map(tuple, nv[t].tolist())) for t in nf} == {tuple(map(tuple, v[t].tolist())) for t in f[[2 * (1 * 4 + 2), 2 * (1 * 4 + 2) + 1]]}   # the original coordinates
    nv8, nf8, rec8 = mm.crop_to_cells(v, f, o, tile_x, tile_y, [(1, 2)], 8.0)
    assert rec8["faces_after"] == 18                                                                       # the 3x3 neighbourhood
    assert rec8["margin_m"] == 8.0


def test_cropped_triangles_are_the_original_triangles():
    v, f, o = _grid_mesh()
    nv, nf, _ = mm.crop_to_cells(v, f, o, np.full(4, 8.0), 8.0, [(0, 0), (2, 3)], 4.0)
    cropped = {tuple(map(tuple, nv[t].tolist())) for t in nf}
    original = {tuple(map(tuple, v[t].tolist())) for t in f}
    assert cropped <= original and len(cropped) == len(nf)
    assert nf.min() == 0 and nf.max() == len(np.unique(nf)) - 1                                            # renumbered densely


def test_huge_margin_reproduces_the_whole_mesh_and_its_sha():
    v, f, o = _grid_mesh()
    nv, nf, rec = mm.crop_to_cells(v, f, o, np.full(4, 8.0), 8.0, [(0, 0)], 1e6)
    assert nv.tolist() == v.tolist() and nf.tolist() == f.tolist()
    assert rec["cropped_mesh_sha256"] == hashlib.sha256(v.astype(np.float32).tobytes() + f.astype(np.int32).tobytes()).hexdigest()


def test_crop_refuses_bad_input():
    v, f, o = _grid_mesh()
    tx = np.full(4, 8.0)
    with pytest.raises(ValueError):
        mm.crop_to_cells(v, f, o, tx, 8.0, [(5, 0)], 4.0)
    with pytest.raises(ValueError):
        mm.crop_to_cells(v, f, o, tx, 8.0, [(0, 9)], 4.0)
    with pytest.raises(ValueError):
        mm.crop_to_cells(v, f, o, tx, 8.0, [(0, 0)], -1.0)
    with pytest.raises(ValueError):
        mm.crop_to_cells(v, f, o, tx, 8.0, [], 4.0)
    with pytest.raises(ValueError):
        mm.crop_to_cells(v + 1000.0, f, o, tx, 8.0, [(0, 0)], 0.0)                                         # nothing near the cell


def test_crop_cells_follow_the_evaluated_cells():
    record = {"eval_cols": 3, "columns": ["a", "gap", "b", "gap"], "column_family": ["A", "B", "B", "C"]}
    assert ex42_mesh_eval.crop_cells_for(record, level=2) == [(2, 0), (2, 1), (2, 2)]
    assert ex42_mesh_eval.crop_cells_for(record, level=6, family="B", kind="gap") == [(6, 1)]
    with pytest.raises(ValueError):
        ex42_mesh_eval.crop_cells_for(record, level=None)
    with pytest.raises(ValueError):
        ex42_mesh_eval.crop_cells_for(record, level=0, family="E", kind="gap")


def test_the_default_paths_do_not_pass_or_build_anything_cropped():
    root = pathlib.Path(mm.__file__).resolve().parents[1]
    mount = (root / "terrains" / "ex42_mesh_mount.py").read_text(encoding="utf-8")
    assert "    if crop_cells is None:\n        return CombinedMeshGeneratorCfg()" in mount                  # the uncropped cfg is the one it always was
    assert "crop_cells=None, crop_margin: float | None = None" in mount
    mesh_eval = (root / "eval" / "ex42_mesh_eval.py").read_text(encoding="utf-8")
    assert "    if crop_margin is None:\n        env_cfg.scene.terrain.terrain_generator = mesh_file_generator_cfg(\n            record[\"mesh_npz\"], record[\"mesh_sha256\"])" in mesh_eval
    modes = (root / "eval" / "eval_map_modes.py").read_text(encoding="utf-8")
    assert "    if args.crop_margin is None:\n        args.ex42_mesh = _attach_ex42_mesh(env_cfg, args.mesh_dir)" in modes
    assert 'parser.add_argument("--crop-margin", type=float, default=None' in modes
    assert "args.device != \"cpu\"" in modes                                                                  # CPU evaluation only
    for name in ("train_start.py", "ex42_training_entry.py"):                                                  # training never touches it
        text = (root / "scripts" / name).read_text(encoding="utf-8")
        assert "crop_cells" not in text and "crop_to_cells" not in text and "crop_margin" not in text
