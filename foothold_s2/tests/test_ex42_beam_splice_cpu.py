"""CPU tests for the B/beam splice mesh (short beam, level-scaled tilt), its plan pin draft, and what a same-run resume does with a new mesh pin."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from foothold_s2.scripts import ex42_beam_splice_mesh as bm
from foothold_s2.terrains import ame2_preset as b

ROOT = Path(__file__).resolve().parents[2]
SRC = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1118_easy10/seed42_E0_c333_flags_E2_1111_v2_edge_easy10")
AGG = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2")
needs_mesh = pytest.mark.skipif(not (SRC / "terrain_mesh.npz").is_file() or not AGG.is_dir(), reason="the easy10 mesh folder is not on this machine")


def test_the_tilt_limit_follows_the_level_and_a_table_replaces_it():
    k = bm.knobs_from()
    assert [bm.angle_limit(r, k) for r in (0, 9)] == [0.0, 0.1]
    assert bm.angle_limit(3, k) == pytest.approx(0.1 * 3 / 9)
    t = bm.knobs_from(rpy_by_level=[0.0] * 9 + [0.05])
    assert bm.angle_limit(9, t) == 0.05 and bm.angle_limit(4, t) == 0.0


@pytest.mark.parametrize("bad", [dict(beam_length_m=0.0), dict(beam_start_x_m=0.5), dict(beam_start_x_m=11.0), dict(rpy_max_rad=0.5),
                                 dict(rpy_level_div=0.0), dict(rpy_by_level=[0.0] * 9)])
def test_bad_knobs_are_refused(bad):
    with pytest.raises(ValueError):
        bm.knobs_from(**bad)


def test_the_top_face_is_read_from_the_untilted_top_and_entry_align_puts_it_on_the_platform_top():
    flat = bm.box_vertices(2, 4, 5.5, 6.5, -0.2, 0.0)
    assert bm.top_at(flat, 2.02, 6.0) == pytest.approx(0.0)
    tilted = bm.box_vertices(2, 4, 5.5, 6.5, -0.2, 0.0, 0.1, 0.1, 0.0)
    a, c, _ = bm.top_plane(tilted)
    assert abs(a) == pytest.approx(np.tan(0.1), rel=0.05) and abs(bm.top_at(tilted, 2.02, 6.0)) > 0.05          # a tilted beam has a step at the entry
    rng = np.random.default_rng(1)
    for align in (False, True):
        first, beam, last, meas = bm.new_tile_vertices(9, (-0.3, -0.1), rng, bm.knobs_from(entry_align=align), 0.18)
        entry = bm.top_at(beam, 2.02, 6.0)
        assert (abs(entry) < 1e-9) if align else abs(entry - meas["entry_step_before_align_m"]) < 1e-9
        assert first[:, 0].max() == pytest.approx(2.0) and last[:, 0].min() == pytest.approx(4.0)
        assert last[:, 2].min() == pytest.approx(-0.3) and last[:, 2].max() == pytest.approx(-0.1)             # the old height rule is kept


@needs_mesh
def test_the_real_splice_changes_only_beam_vertices_and_the_entry_step_falls_below_ten_cm(tmp_path):
    dst = tmp_path / "beam"
    res = bm.build(SRC, dst, aggregate_from=AGG)
    proof = bm.verify_beam_splice(dst)
    assert proof["faces_byte_equal"] and proof["other_arrays_byte_equal"] and proof["source_chain_verified"]
    assert res["mesh_sha256"] != json.loads((SRC / "mesh_manifest.json").read_text(encoding="utf-8-sig"))["mesh_sha256"]
    for row in proof["measured_changed_tiles"][:3]:                                                       # L0..L2: the planner's +15 / +24 / +39 cm
        assert abs(row["entry_step_m"]) < 0.10, row
    assert all(abs(r["beam_length_m"] - 2.0) < 1e-3 for r in proof["measured_changed_tiles"])
    # a damaged copy is refused: one vertex outside the beam tiles moved
    bad = tmp_path / "bad"
    shutil.copytree(dst, bad)
    with np.load(bad / "terrain_mesh.npz", allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    arrays["vertices"][0, 2] += 0.01
    np.savez_compressed(bad / "terrain_mesh.npz", **arrays)
    with pytest.raises(ValueError):
        bm.verify_beam_splice(bad)


@needs_mesh
def test_the_knobs_off_values_zero_the_tilt_and_align_the_entry(tmp_path):
    dst = tmp_path / "flat"
    bm.build(SRC, dst, aggregate_from=AGG, rpy_max_rad=0.0, entry_align=True)
    proof = bm.verify_beam_splice(dst)
    assert all(abs(r["entry_step_m"]) < 1e-3 and r["top_slope_xy"] == [0.0, 0.0] for r in proof["measured_changed_tiles"])


# ---- plan pin draft and what a same-run resume does with it --------------------------------------------------------------------------
def _fake_mesh(folder: Path):
    folder.mkdir()
    (folder / "mesh_manifest.json").write_text(json.dumps({"mesh_sha256": "ab" * 32}), encoding="utf-8")
    for name in ("terrain_mesh.npz", "terrain_manifest.json"):
        (folder / name).write_bytes(name.encode())


def test_the_pin_draft_changes_only_the_profile_and_the_stage_names_and_the_plan_sha_moves(tmp_path):
    from foothold_s2.tools import ex42_beam_pin_draft as pd
    table = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
    text = table.read_text(encoding="utf-8")
    _fake_mesh(tmp_path / "mesh")
    out = pd.draft(text, tmp_path / "mesh", "e2_easy10_beam_edge", "note")
    old, new = text.splitlines(), out.splitlines()
    added = [ln for ln in new if ln not in old]
    assert sum(ln.strip() == "training_mesh_profile: e2_easy10_beam_edge" for ln in added) == text.count("training_mesh_profile: e2_easy10_edge") >= 7
    assert "training_mesh_profile: e2_easy10_edge" not in out and out.count("e2_easy10_beam_edge:") == 1
    with pytest.raises(ValueError):
        pd.draft(out, tmp_path / "mesh", "e2_easy10_beam_edge", "note")                                   # twice is refused


def test_the_runtime_state_a_resume_compares_has_no_mesh_identity_but_the_plan_sha_covers_the_pin():
    import inspect
    from foothold_s2.scripts import ex42_training_entry as entry
    src = inspect.getsource(entry)
    start = src.index("def state_dict(self) -> dict[str, Any]:\n        return {\"format\": \"foothold-ex42-stage-zero-state/1\"")
    body = src[start:start + 900]
    assert "plan_sha256" in body and "mesh" not in body                                                    # the only handle on the mesh is the plan sha


def test_a_mesh_file_that_differs_from_the_plans_pin_is_refused_before_anything_loads(tmp_path):
    from foothold_s2.ex42_stage_mesh import pinned_stage_mesh
    _fake_mesh(tmp_path / "mesh")
    doc = {"stages": [{"id": "E2", "training_mesh_profile": "p"}],
           "training_mesh_profiles": {"p": {"directory": str(tmp_path / "mesh"), "geometry_sha256": "ab" * 32,
                                           "files": {n: "00" * 32 for n in ("terrain_mesh.npz", "mesh_manifest.json", "terrain_manifest.json")}}}}
    with pytest.raises(ValueError, match="SHA differs"):
        pinned_stage_mesh(doc, "E2")


E0_RUN = Path("/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218")


@pytest.mark.skipif(not (E0_RUN / "model_250.pt").is_file(), reason="the real E0 run is not on this machine")
def test_a_resume_under_the_draft_plan_is_refused_by_the_plan_sha_pin_of_the_saved_state(tmp_path):
    """The checkpoint was saved under the live plan. A plan with only the mesh pin changed has another sha256 and the boundary resume refuses it."""
    from foothold_s2.curriculum.ex42_prep import EX42Plan
    from foothold_s2.tests.test_ex42_stage_resume_cpu import _boundary_checkpoint, _validate
    from foothold_s2.tools import ex42_beam_pin_draft as pd
    table = ROOT / "foothold_s2/curriculum/ex42-prep.yaml"
    _fake_mesh(tmp_path / "mesh")
    plan_dir = tmp_path / "draft"
    plan_dir.mkdir()
    for sibling in table.parent.glob("*.yaml"):
        if sibling.name != table.name:
            (plan_dir / sibling.name).write_bytes(sibling.read_bytes())
    (plan_dir / table.name).write_text(pd.draft(table.read_text(encoding="utf-8"), tmp_path / "mesh", "e2_easy10_beam_edge", "n"), encoding="utf-8")
    draft_sha = EX42Plan.load(plan_dir / table.name).sha256
    args = _boundary_checkpoint(tmp_path)
    assert draft_sha != args[2]
    assert _validate(*args)["state"] == "manifest_checkpoint_self_resume_verified"                       # the live plan passes
    with pytest.raises(ValueError, match="curriculum pins"):
        _validate(args[0], args[1], draft_sha, args[3])                                                   # the draft plan does not
