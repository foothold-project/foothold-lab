"""11 §7 L0 CPU 시험: 내부 파라미터 · 쿼터니언 부호와 광축이 바닥에 닿는 거리 · 증강 기대값 · 단일 Mesh 경로."""

import ast
import math
import os

import torch

from foothold_s2.sensors import depth_cam_cfg as cam
from foothold_s2.sensors.depth_aug import DepthAugCfg, augment, normalize, shape_masks, smooth_noise


def test_intrinsics_edge_angle():
    h, v = cam.edge_ray_angles_deg()
    assert math.isclose(h, 28.22, abs_tol=0.05)  # 11 §7 「±28.25°」 = atan(30/55.9)
    assert math.isclose(v, 29.01, abs_tol=0.05)


def test_quaternion_matches_doc_and_hits_ground():
    assert all(math.isclose(a, b, abs_tol=1e-4) for a, b in zip(cam.OFFSET_ROT, (0.9537, 0.0, 0.3007, 0.0)))
    base_h = 0.33  # 카메라 높이 0.45 = base 0.33 + 0.12 (11 §7)
    assert math.isclose(cam.ground_hit_x(base_h), 0.893, abs_tol=0.01)
    assert math.isclose(cam.ground_hit_x(base_h, +29.0), 0.47, abs_tol=0.01)
    assert math.isclose(cam.ground_hit_x(base_h, -29.0), 4.53, abs_tol=0.02)
    # negative control: 부호를 뒤집으면 광축이 위를 봐서 바닥에 안 닿는다
    w, x, y, z = cam.OFFSET_ROT
    assert cam.ground_hit_x(base_h, 0.0, (w, x, -y, z)) is None


def test_single_mesh_path_ast():
    assert cam.MESH_PRIM_PATHS == ["/World/ground"]
    src = open(cam.__file__, encoding="utf-8").read()
    calls = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "RayCasterCameraCfg"]
    assert len(calls) == 1
    kw = {k.arg for k in calls[0].keywords}
    assert {"mesh_prim_paths", "update_period", "offset", "pattern_cfg", "data_types"} <= kw


def test_installed_raycaster_rejects_two_meshes():
    """negative control 의 근거: 설치 RayCaster 가 경로 둘을 NotImplementedError 로 막는지 소스로 확인 (Kit 없이)."""
    path = r"C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/ray_caster.py"
    if not os.path.exists(path):
        return
    src = open(path, encoding="utf-8").read()
    assert "NotImplementedError" in src and "mesh_prim_paths" in src


def test_aug_off_equals_normalize_and_shapes_fill_one():
    g = torch.Generator().manual_seed(0)
    d = 0.5 + 2.0 * torch.rand(4, 60, 60, generator=g)
    none = DepthAugCfg(noise_sigma_m=0.0, min_valid_m=0.0, hole_level_max=0.0, max_shapes=0)
    assert torch.equal(augment(d, none, torch.Generator().manual_seed(1)), normalize(d))
    two = DepthAugCfg(noise_sigma_m=0.0, min_valid_m=0.0, hole_level_max=0.0, max_shapes=2)
    out = augment(d, two, torch.Generator().manual_seed(2))
    occ = shape_masks(4, 60, 60, 2, torch.Generator().manual_seed(2))  # 같은 난수 순서가 아니므로 차이로 본다
    diff = out != normalize(d)
    assert (out[diff] == 1.0).all()  # 바뀐 화소는 전부 먼 값
    assert diff.any() and occ.any()


def test_normalize_missing_is_one():
    d = torch.tensor([[0.2, 1.6, 3.0, float("inf"), float("nan"), 5.0]])
    assert torch.allclose(normalize(d), torch.tensor([[0.0, 0.5, 1.0, 1.0, 1.0, 1.0]]))


def test_perlin_hole_fraction_at_04():
    noise = smooth_noise(2000, 60, 60, 6, torch.Generator().manual_seed(0))
    frac = float((noise < 0.4).float().mean())
    assert 0.2 <= frac <= 0.5, frac  # 11 §7 「Perlin 0.4 에서 구멍 비율 0.2~0.5」
