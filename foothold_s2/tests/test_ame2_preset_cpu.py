"""Known dimensions and physical support for the opt-in AME-2 Go2 mix."""
import numpy as np
import pytest
from types import SimpleNamespace
from dataclasses import replace

from foothold_s2.terrains import ame2_preset as p


ENDPOINTS = {
    "stair_up": ("step_height_m", .05, .27),
    "stair_down": ("step_height_m", .05, .27),
    "rough": ("noise_amplitude_m", 0, .08),
    "boxes": ("box_height_m", .05, .30),
    "climb_up": ("ledge_height_m", .1, .53),
    "climb_down": ("ledge_height_m", .2, .6),
    "gap": ("gap_m", .18, .7),
    "pallets": ("gap_m", .08, .35),
    "stones": ("stone_side_m", .71, .41),
    "beam": ("beam_width_m", .9, .18),
    "consecutive": ("first_ring_height_m", .05, .3),
    "obstacles": ("density_per_m2", 0, .5),
}


@pytest.mark.parametrize("kind", p.KINDS)
def test_all_twelve_kinds_have_measured_go2_endpoints_and_spawn(kind):
    key, low, high = ENDPOINTS[kind]
    assert p.dimensions(kind, 0)[key] == pytest.approx(low)
    assert p.dimensions(kind, 9)[key] == pytest.approx(high)
    tile = p.build_tile(kind, 9, 43)
    again = p.build_tile(kind, 9, 43)
    assert tile.boxes == again.boxes
    if tile.rough_height_m is not None:
        np.testing.assert_array_equal(tile.rough_height_m, again.rough_height_m)
    assert tile.origin.shape == (3,) and np.isfinite(tile.origin).all()
    assert 0 <= tile.origin[0] <= p.SIZE and 0 <= tile.origin[1] <= p.SIZE
    assert tile.boxes or tile.rough_height_m is not None


def test_sparse_gap_has_real_hole_and_half_physical_floor():
    virtual = p.build_tile("gap", 9, 43)
    physical = p.build_tile("gap", 9, 42)
    assert virtual.floor_mode == "virtual" and physical.floor_mode == "physical"
    assert virtual.floor_height_m is not None and physical.floor_height_m is not None
    assert all(not (b.x0 <= 6 <= b.x1 and b.y0 <= 6 <= b.y1) for b in virtual.boxes)
    assert any(b.x0 <= 6 <= b.x1 and b.y0 <= 6 <= b.y1 for b in physical.boxes)
    assert virtual.origin[0] < 4 and virtual.origin[2] == 0
    p.validate_tile(virtual)
    p.validate_tile(physical)
    bridged = replace(virtual, boxes=virtual.boxes + (p.Box(5.8, 6.2, 5.8, 6.2, -.2, 0),))
    with pytest.raises(ValueError, match="bridged"):
        p.validate_tile(bridged)
    with pytest.raises(ValueError, match="physical sparse floor missing"):
        p.validate_tile(replace(physical, boxes=physical.boxes[1:]))


def test_paper_family_proportions_are_complete():
    assert set(p.PROPORTIONS) == set(p.KINDS)
    assert sum(p.PROPORTIONS.values()) == pytest.approx(1.)
    assert p.PROPORTIONS["stones"] == .30 and p.PROPORTIONS["climb_up"] == .20


def test_obstacles_include_positive_and_negative_geometry():
    low = p.build_tile("obstacles", 0, 42)
    high = p.build_tile("obstacles", 9, 42)
    assert len(low.boxes) == 144
    assert any(box.z1 > 0 for box in high.boxes)
    assert any(box.z1 < 0 for box in high.boxes)


def test_rough_undulation_slope_and_per_cell_noise_separately():
    assert np.count_nonzero(p.build_tile("rough", 0, 42).rough_height_m) == 0
    for level in (5, 9):
        tile = p.build_tile("rough", level, 42)
        z = tile.rough_height_m
        x = np.linspace(0, p.SIZE, z.shape[0])
        declared = tile.dimensions["undulation_slope_deg"]
        wave = np.tan(np.radians(declared)) * 3 / (2 * np.pi) * np.sin(2 * np.pi * x / 3)
        wave_slope_deg = float(np.degrees(np.arctan(
            np.max(np.abs(np.diff(wave))) / p.HORIZONTAL_SCALE)))
        assert wave_slope_deg <= declared + 1e-9
        if level == 9:
            assert 19 <= wave_slope_deg <= 20
        assert np.ptp(z[:11]) == pytest.approx(0.0, abs=1e-12)
        # Entry shaping ends at x=2 m. The authored roughness remains exact
        # across the body of the tile and keeps the declared noise span.
        noise = z[20:] - wave[20:, None]
        assert tile.dimensions["noise_amplitude_m"] * 2 == pytest.approx(.16 * level / 9)
        assert np.max(np.abs(noise)) <= tile.dimensions["noise_amplitude_m"] + 1e-12
        assert np.ptp(noise) <= 2 * tile.dimensions["noise_amplitude_m"] + 1e-12
        assert np.unique(noise).size == noise.size  # independently sampled cells
        if level == 9:
            combined_slope = float(np.degrees(np.arctan(
                np.max(np.abs(np.diff(z, axis=0))) / p.HORIZONTAL_SCALE)))
            assert combined_slope > declared  # 20° is not a bound on rough+undulation


def test_mesh_cpu_arrays_and_mutation_rejection():
    for kind in ("rough", "beam", "stones", "pallets", "obstacles"):
        meshes = p.mesh_arrays(p.build_tile(kind, 5, 42))
        assert meshes and all(len(mesh.vertices) > 0 and len(mesh.faces) > 0 for mesh in meshes)
        assert all(np.isfinite(mesh.vertices).all() for mesh in meshes)
    with pytest.raises(ValueError, match="kind and integer level"):
        p.build_tile("gap", 10, 42)
    with pytest.raises(ValueError, match="explicit uint32"):
        p.build_tile("gap", 0, -1)
    with pytest.raises(ValueError, match="box escapes"):
        p._box(0, 13, 0, 1, 0)
    assert p._tile_seed("gap", .5, 42) != p._tile_seed("gap", .6, 42)


def test_isaac_tile_function_shape_without_kit():
    cfg = SimpleNamespace(size=(12., 12.), kind="stones", seed=42, ame2_level=5)
    meshes, origin = p.tile_function(.5, cfg)
    assert len(meshes) == 1 and len(meshes[0].faces) > 100
    assert np.isfinite(meshes[0].vertices).all() and 0 <= origin[0] <= 12
    cfg.size = (8., 8.)
    with pytest.raises(ValueError, match="12x12"):
        p.tile_function(.5, cfg)
