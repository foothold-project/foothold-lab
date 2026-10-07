# -*- coding: utf-8 -*-
"""F·G 의 메시와 설정 덮어쓰기를 CPU 에서 검증한다.

분류: 실험
작성: Codex 세션 (오흥재 지시) · 2026-09-20 09:40
근거: fg_task1.md · 생성된 메시 · Isaac Lab 의 기존 A·B 설정 함수
요지: 도랑 공간 · 슬랩 부피 · 경계 · 회전 · 자기검사 실패를 직접 확인한다
상태: CPU 단위 검사 · Isaac 환경 통합 검사가 아님
판: v1.0
"""

from __future__ import annotations

import ast
import copy
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

import numpy as np

# **`trimesh` 가 없으면 건너뛴다.** 저장소의 표준 시험 명령은 시스템 python 을
# 쓰는데 `trimesh` 는 isaac311 환경에만 있다. 여기서 죽으면 «시험이 깨졌다» 로
# 보이지만 실제로는 «이 환경에서는 못 재는 것» 이다. 둘을 가른다.
#
#     isaac311 로 돌리면 10개가 실제로 돈다
#     시스템 python 으로 돌리면 10개가 skip 된다
try:
    import trimesh
except ImportError:  # pragma: no cover
    trimesh = None

if trimesh is None:
    raise unittest.SkipTest(
        "trimesh 가 없다. isaac311 환경에서 돌려야 이 시험이 실제로 돈다")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "sim/eval"))
import gap_exposure as exposure


def classes_from_source(path, names, namespace):
    """지정한 클래스의 본문만 읽는다. 환경 생성 대신 설정 함수만 검사한다."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in names:
            node.decorator_list = []
            nodes.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            nodes.append(node)
    body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + nodes
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), "exec"), namespace)


class GeometryTests(unittest.TestCase):
    """검사식은 실제 메시의 부피 · 윗면 삼각형 · 반환 원점을 읽는다."""

    @classmethod
    def setUpClass(cls):
        cls.functions, cls.defaults, _ = exposure.load_geometry(exposure.DEFAULT_GAP_DIR)

    def generate(self, **overrides):
        cfg = NS(**(self.defaults | overrides))
        return self.functions["omni_gap_terrain"](0.5, cfg)

    def test_ring_closed_slabs_volume_and_empty_trench(self):
        for sides, size in ((64, (8, 8)), (9, (9, 7)), (65, (8, 8))):
            with self.subTest(sides=sides, size=size):
                meshes, origin = self.generate(num_sides=sides, size=size)
                np.testing.assert_allclose(origin, [size[0] / 2, size[1] / 2, 0])
                width = 0.275
                area_factor = sides * math.sin(2 * math.pi / sides) / 2
                trench_area = area_factor * ((2.5 + width / 2) ** 2 - (2.5 - width / 2) ** 2)
                self.assertAlmostEqual(sum(mesh.volume for mesh in meshes), size[0] * size[1] - trench_area)
                for mesh in meshes:
                    self.assertTrue(mesh.is_watertight)
                    self.assertTrue(mesh.is_winding_consistent)
                    self.assertGreater(mesh.volume, 0)
                    np.testing.assert_allclose(mesh.bounds[:, 2], [-1, 0])
                bounds = trimesh.util.concatenate(meshes).bounds
                np.testing.assert_allclose(bounds[:, :2], [[0, 0], size], atol=1e-12)

    def test_top_mesh_has_support_only_outside_trench(self):
        meshes, origin = self.generate()
        triangles = np.concatenate([m.triangles[m.face_normals[:, 2] > 0.9, :, :2] for m in meshes])
        def supported(point):
            edges = np.roll(triangles, -1, axis=1) - triangles
            rel = point - triangles
            cross = edges[:, :, 0] * rel[:, :, 1] - edges[:, :, 1] * rel[:, :, 0]
            return np.any(np.all(cross >= -1e-10, axis=1))
        for angle in np.linspace(0, 2 * np.pi, 720, endpoint=False):
            direction = np.array((np.cos(angle), np.sin(angle)))
            self.assertTrue(supported(origin[:2] + 2.30 * direction))
            self.assertFalse(supported(origin[:2] + 2.50 * direction))
            self.assertTrue(supported(origin[:2] + 2.70 * direction))
        for x in np.linspace(0, 8, 81):
            for point in ((x, 0), (x, 8), (0, x), (8, x)):
                self.assertTrue(supported(np.array(point)))

    def test_rotation_matches_original_and_seed(self):
        cfg = NS(**self.defaults)
        original, origin = self.functions["forward_gap_terrain"](0.5, cfg)
        np.random.seed(42)
        expected_angle = np.random.uniform(-np.pi, np.pi)
        np.random.seed(42)
        meshes, rotated_origin = self.generate(mode="rotated")
        transform = trimesh.transformations.rotation_matrix(expected_angle, [0, 0, 1], [4, 4, 0])
        for old, new in zip(original, meshes):
            np.testing.assert_allclose(new.vertices, trimesh.transform_points(old.vertices, transform))
            self.assertEqual(new.metadata["gap_rotation_rad"], expected_angle)
        np.testing.assert_allclose(rotated_origin, trimesh.transform_points(origin[None, :], transform)[0])

    def test_invalid_geometry_raises(self):
        for kwargs in ({"mode": "oops"}, {"ring_radius": 4}, {"ring_radius": 0.01},
                       {"num_sides": 7}, {"num_sides": 64.5}, {"slab_thickness": 0},
                       {"gap_width_range": (-1, 0.4)}, {"size": (0, 8)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.generate(**kwargs)

    def test_ring_every_direction_at_minimum_speed(self):
        meshes, origin = self.generate()
        outer, inner = exposure.gap_polygons(meshes, "ring", (8, 8))
        for heading in np.linspace(-np.pi, np.pi, 720, endpoint=False):
            distance = exposure.episode(origin, [heading, heading + np.pi], [0.4, 0.4], outer, inner, (8, 8))
            self.assertIsNotNone(distance)
            self.assertTrue(2.35 < distance < 2.37)

    def test_second_leg_continues_and_boundary_stops_episode(self):
        outer = np.array(((5, 0), (5.3, 0), (5.3, 8), (5, 8)))
        # 첫 구간 1m 북진, 둘째 동진. 첫 노출 누적 거리는 1+1=2m 다.
        self.assertAlmostEqual(exposure.episode([4, 4, 0], [np.pi / 2, 0], [0.1, 0.4], outer, None, (8, 8)), 2)
        # 첫 구간에 서쪽 경계에 닿으면 둘째 동진은 실행하면 안 된다.
        self.assertIsNone(exposure.episode([4, 4, 0], [np.pi, 0], [1, 1], outer, None, (8, 8)))

    def test_tangent_and_short_segment_do_not_count(self):
        outer = np.array(((2, 2), (3, 2), (3, 3), (2, 3)))
        self.assertIsNone(exposure.first_gap_distance(np.array([0, 0]), np.array([1, 0]), 4, outer, None))
        self.assertIsNone(exposure.first_gap_distance(np.array([0, 2.5]), np.array([1, 0]), 1, outer, None))
        self.assertAlmostEqual(exposure.first_gap_distance(np.array([0, 2.5]), np.array([1, 0]), 4, outer, None), 2)


class ConfigTests(unittest.TestCase):
    """Isaac 객체를 대체한 그릇에 실제 A·B·F·G 설정 함수를 순서대로 적용한다."""

    @classmethod
    def setUpClass(cls):
        gap_dir = exposure.DEFAULT_GAP_DIR
        functions, _, _ = exposure.load_geometry(gap_dir)
        class TerrainBase:
            size = (8, 8)
            proportion = 1.0
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        class RoughBase:
            def __init__(self):
                terrains = {name: NS(proportion=0) for name in (
                    "pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
                    "hf_pyramid_slope", "hf_pyramid_slope_inv")}
                self.scene = NS(terrain=NS(terrain_generator=NS(sub_terrains=terrains)))
                self.commands = NS(base_velocity=NS(ranges=NS(heading=(-math.pi, math.pi))))
                self.events = NS(reset_base=NS(params={}))
                self.observations = NS(policy=NS(height_scan=NS()))
                self.__post_init__()
            def __post_init__(self):
                pass
        namespace = functions | {
            "np": np, "pi": math.pi, "copy": copy, "SubTerrainBaseCfg": TerrainBase,
            "UnitreeGo2RoughEnvCfg": RoughBase, "GapTerminationsCfg": NS,
            "SceneEntityCfg": lambda value: value,
            "gap_observations": NS(height_scan_with_gap=None),
        }
        classes_from_source(gap_dir / "gap_terrain.py", {"ForwardGapTerrainCfg"}, namespace)
        classes_from_source(ROOT / "sim/policy/omni_gap_terrain.py", {"OmniGapTerrainCfg"}, namespace)
        classes_from_source(gap_dir / "gap_env_cfg.py", {"UnitreeGo2GapEnvCfg"}, namespace)
        classes_from_source(gap_dir / "gap_wide_env_cfg.py", {"UnitreeGo2GapWideEnvCfg"}, namespace)
        classes_from_source(ROOT / "sim/policy/gap_f_env_cfg.py", {"UnitreeGo2GapFEnvCfg"}, namespace)
        classes_from_source(ROOT / "sim/policy/gap_g_env_cfg.py", {"UnitreeGo2GapGEnvCfg"}, namespace)
        cls.namespace = namespace

    def test_b_preserved_and_f_g_independent(self):
        ns = self.namespace
        before = ns["UnitreeGo2GapWideEnvCfg"]()
        f = ns["UnitreeGo2GapFEnvCfg"]()
        g = ns["UnitreeGo2GapGEnvCfg"]()
        after = ns["UnitreeGo2GapWideEnvCfg"]()
        self.assertIn("forward_gap", before.scene.terrain.terrain_generator.sub_terrains)
        self.assertIn("forward_gap", after.scene.terrain.terrain_generator.sub_terrains)
        self.assertNotIn("forward_gap", f.scene.terrain.terrain_generator.sub_terrains)
        self.assertIn("forward_gap", g.scene.terrain.terrain_generator.sub_terrains)
        self.assertEqual(after.commands.base_velocity.ranges.lin_vel_x, (0.5, 1.5))
        self.assertIsNone(g.commands.base_velocity.ranges.heading)

    def test_f_all_guards_reject_corruption(self):
        mutations = [
            lambda c: setattr(c.commands.base_velocity, "heading_command", False),
            lambda c: setattr(c.commands.base_velocity.ranges, "heading", None),
            lambda c: setattr(c.commands.base_velocity, "rel_heading_envs", 0),
            lambda c: setattr(c.commands.base_velocity.ranges, "ang_vel_z", (0, 0)),
            lambda c: setattr(c.commands.base_velocity, "rel_standing_envs", 0),
            lambda c: setattr(c.commands.base_velocity.ranges, "lin_vel_x", (0, 1.5)),
            lambda c: setattr(c.commands.base_velocity.ranges, "lin_vel_y", (-1, 1)),
            lambda c: setattr(c.scene.terrain, "max_init_terrain_level", 3),
            lambda c: c.scene.terrain.terrain_generator.sub_terrains.pop("omni_gap"),
        ]
        for name in ("mode", "ring_radius", "proportion", "gap_width_range", "num_sides"):
            mutations.append(lambda c, name=name: setattr(c.scene.terrain.terrain_generator.sub_terrains["omni_gap"], name, None))
        for name in self.namespace["KEEP_ROUGH_PROPORTIONS"]:
            mutations.append(lambda c, name=name: setattr(c.scene.terrain.terrain_generator.sub_terrains[name], "proportion", 0))
        for name in ("x", "y", "yaw"):
            mutations.append(lambda c, name=name: c.events.reset_base.params["pose_range"].pop(name))
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                cfg = self.namespace["UnitreeGo2GapFEnvCfg"]()
                mutation(cfg)
                with self.assertRaises(RuntimeError):
                    cfg._verify_overrides()

    def test_g_guards_reject_corruption(self):
        for name, target in (("heading_command", "command"), ("heading", "range"),
                             ("ang_vel_z", "range"), ("lin_vel_x", "range"),
                             ("rel_standing_envs", "command"), ("proportion", "gap")):
            with self.subTest(name=name):
                cfg = self.namespace["UnitreeGo2GapGEnvCfg"]()
                command = cfg.commands.base_velocity
                obj = {"command": command, "range": command.ranges,
                       "gap": cfg.scene.terrain.terrain_generator.sub_terrains["forward_gap"]}[target]
                setattr(obj, name, "오염")
                with self.assertRaises(RuntimeError):
                    cfg._verify_overrides()
        cfg = self.namespace["UnitreeGo2GapGEnvCfg"]()
        cfg.scene.terrain.terrain_generator.sub_terrains.pop("forward_gap")
        with self.assertRaises(RuntimeError):
            cfg._verify_overrides()


if __name__ == "__main__":
    unittest.main()
