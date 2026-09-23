# -*- coding: utf-8 -*-
"""v2a · v2b · v2c · v2d 설정 덮어쓰기를 CPU 에서 검증한다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: inbox/jay/20260921-v2-design.md v1.0 (c766f97) 1 절 · 돌고 있는 학습의 params/env.yaml
요지: 되읽기 관문이 «실제로 막는지» 를 칸마다 깨뜨려 확인하고, 자식 판들이 v2a 와 «자기 칸만» 다른지를 구조로 확인한다
상태: CPU 단위 검사 · Isaac 환경 통합 검사가 아님
판: v1.0

## 왜 필요한가

`_verify_overrides` 는 **환경을 만들 때만** 돈다. 그래서 학습을 걸어야
확인되는데, 그때는 이미 GPU 를 세 시간 잡은 뒤다. 그리고 **관문이 있다는
것과 관문이 막는다는 것은 다르다** · 이 저장소에서 하루에 네 개가 뚫렸다.

여기서는 `pxr` 없이 **클래스 본문만** 읽어 돌린다 (`test_fg_cpu.py` 와 같은 수법).
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

POLICY_DIR = Path(__file__).resolve().parents[1]


def classes_from_source(path, names, namespace):
    """지정한 클래스의 본문과 모듈 수준 상수만 읽는다. import 는 건너뛴다."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in names:
            node.decorator_list = []
            nodes.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            nodes.append(node)
    body = [ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0)] + nodes
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=body, type_ignores=[])), str(path), "exec"), namespace)


class FakeRails(object):
    def __init__(self, proportion=None, rail_thickness_range=None,
                 rail_height_range=None, platform_width=None):
        self.proportion = proportion
        self.rail_thickness_range = rail_thickness_range
        self.rail_height_range = rail_height_range
        self.platform_width = platform_width


class FakeOmniGap(object):
    def __init__(self, proportion=None, size=None, gap_width_range=None,
                 slab_thickness=None, mode=None, ring_radius=None):
        self.proportion = proportion
        self.size = size
        self.gap_width_range = gap_width_range
        self.slab_thickness = slab_thickness
        self.mode = mode
        self.ring_radius = ring_radius
        self.num_sides = 64


ROUGH_BASE = {
    "pyramid_stairs": 0.18, "pyramid_stairs_inv": 0.18, "boxes": 0.18,
    "random_rough": 0.18, "hf_pyramid_slope": 0.09, "hf_pyramid_slope_inv": 0.09,
}


class FakeBase(object):
    """`UnitreeGo2GapWideEnvCfg` 가 물려주는 모양만 흉내 낸다."""

    def __post_init__(self):
        sub = {name: NS(proportion=value) for name, value in ROUGH_BASE.items()}
        sub["forward_gap"] = NS(
            proportion=0.10, size=(8.0, 8.0),
            gap_width_range=(0.15, 0.40), slab_thickness=1.0)
        self.scene = NS(terrain=NS(
            terrain_generator=NS(sub_terrains=sub), max_init_terrain_level=2))
        self.commands = NS(base_velocity=NS(
            heading_command=False, rel_heading_envs=0.0, rel_standing_envs=0.0,
            resampling_time_range=(10.0, 10.0),
            ranges=NS(heading=(0.0, 0.0), ang_vel_z=(0.0, 0.0),
                      lin_vel_x=(0.5, 1.5), lin_vel_y=(0.0, 0.0))))
        self.events = NS(reset_base=NS(params={"pose_range": {
            "x": (-0.10, 0.10), "y": (-0.20, 0.20), "yaw": (-0.05, 0.05)}}))
        # 상류 기본값. 돌아간 학습의 params/env.yaml 에서 읽은 그대로다.
        self.scene.height_scanner = NS(
            ray_cast_drift_range={"x": (0.0, 0.0), "y": (0.0, 0.0), "z": (0.0, 0.0)},
            drift_range=(0.0, 0.0),
            offset=NS(pos=(0.0, 0.0, 20.0), rot=(1.0, 0.0, 0.0, 0.0)))
        self.observations = NS(policy=NS(
            enable_corruption=True,
            height_scan=NS(noise=NS(n_min=-0.10, n_max=0.10))))


def base_namespace():
    return {
        "configclass": lambda cls: cls,
        "UnitreeGo2GapWideEnvCfg": FakeBase,
        "OmniGapTerrainCfg": FakeOmniGap,
        "terrain_gen": NS(MeshRailsTerrainCfg=FakeRails),
        "pi": 3.141592653589793,
    }


def load():
    """두 클래스를 **각자의 이름공간** 에 올린다.

    한 이름공간에 겹쳐 올리면 안 된다. 두 파일 다 모듈 수준에
    `REL_STANDING_ENVS` 를 두는데, `standing_envs()` 가 그것을 **부를 때**
    읽으므로 나중에 올린 v2b 의 0.10 이 v2a 것까지 덮어쓴다. 진짜 모듈은
    전역이 따로라 안 그런다 · **여기서만 나는 일**이라 이렇게 갈라 둔다.
    """
    ns_a = base_namespace()
    classes_from_source(
        POLICY_DIR / "v2a_env_cfg.py", {"UnitreeGo2V2aEnvCfg"}, ns_a)

    out = [ns_a["UnitreeGo2V2aEnvCfg"]]
    for letter in ("b", "c", "d"):
        child = base_namespace()
        child["UnitreeGo2V2aEnvCfg"] = ns_a["UnitreeGo2V2aEnvCfg"]
        classes_from_source(
            POLICY_DIR / ("v2%s_env_cfg.py" % letter),
            {"UnitreeGo2V2%sEnvCfg" % letter}, child)
        out.append(child["UnitreeGo2V2%sEnvCfg" % letter])
    return out


V2A, V2B, V2C, V2D = load()


def build(cls):
    obj = cls()
    obj.__post_init__()
    return obj


class BuildTests(unittest.TestCase):
    """돌고 있는 학습의 `params/env.yaml` 과 같은 값이 나와야 한다."""

    def test_v2a_terrain_and_commands(self):
        cfg = build(V2A)
        sub = cfg.scene.terrain.terrain_generator.sub_terrains
        self.assertEqual(
            {k: round(v.proportion, 4) for k, v in sorted(sub.items())},
            {"boxes": 0.15, "hf_pyramid_slope": 0.10,
             "hf_pyramid_slope_inv": 0.10, "omni_gap": 0.10,
             "pyramid_stairs": 0.15, "pyramid_stairs_inv": 0.15,
             "rails": 0.10, "random_rough": 0.15})
        self.assertAlmostEqual(sum(v.proportion for v in sub.values()), 1.0)
        self.assertNotIn("forward_gap", sub)
        cmd = cfg.commands.base_velocity
        self.assertEqual(cmd.ranges.lin_vel_x, (0.4, 1.5))
        self.assertEqual(cmd.ranges.ang_vel_z, (-1.0, 1.0))
        self.assertEqual(cmd.rel_standing_envs, 0.02)
        self.assertTrue(cmd.heading_command)

    def test_rails_values_match_the_eval_harness(self):
        sub = build(V2A).scene.terrain.terrain_generator.sub_terrains
        rails = sub["rails"]
        self.assertEqual(tuple(rails.rail_thickness_range), (0.08, 0.18))
        self.assertEqual(tuple(rails.rail_height_range), (0.05, 0.18))
        self.assertEqual(rails.platform_width, 1.5)

    def test_omni_gap_carries_f_values(self):
        gap = build(V2A).scene.terrain.terrain_generator.sub_terrains["omni_gap"]
        self.assertEqual(gap.mode, "ring")
        self.assertEqual(gap.ring_radius, 2.5)
        self.assertEqual(tuple(gap.gap_width_range), (0.15, 0.40))
        self.assertEqual(gap.slab_thickness, 1.0)


class SingleVariableTests(unittest.TestCase):
    """**두 판의 주장** · `rel_standing_envs` 하나만 다르다."""

    def test_v2b_overrides_exactly_one_method(self):
        own = {n for n in vars(V2B) if not n.startswith("__")}
        self.assertEqual(own, {"standing_envs"})

    def test_standing_values(self):
        self.assertEqual(build(V2A).commands.base_velocity.rel_standing_envs, 0.02)
        self.assertEqual(build(V2B).commands.base_velocity.rel_standing_envs, 0.10)

    def test_everything_else_is_identical(self):
        a, b = build(V2A), build(V2B)
        sa = {k: round(v.proportion, 6)
              for k, v in a.scene.terrain.terrain_generator.sub_terrains.items()}
        sb = {k: round(v.proportion, 6)
              for k, v in b.scene.terrain.terrain_generator.sub_terrains.items()}
        self.assertEqual(sa, sb)
        ca, cb = a.commands.base_velocity, b.commands.base_velocity
        for field in ("heading_command", "rel_heading_envs", "resampling_time_range"):
            self.assertEqual(getattr(ca, field), getattr(cb, field), field)
        for field in ("heading", "ang_vel_z", "lin_vel_x", "lin_vel_y"):
            self.assertEqual(getattr(ca.ranges, field),
                             getattr(cb.ranges, field), field)


class GuardTests(unittest.TestCase):
    """**관문을 칸마다 깨뜨린다.** 안 막으면 그 칸은 관문이 아니다."""

    def broken(self, mutate):
        """`_verify_overrides` 직전 상태를 만들고 한 칸만 망가뜨려 다시 검사한다."""
        cfg = build(V2A)
        mutate(cfg)
        with self.assertRaises(RuntimeError) as caught:
            cfg._verify_overrides()
        return str(caught.exception)

    def test_command_fields_are_guarded(self):
        cases = {
            "rel_standing_envs": lambda c: setattr(
                c.commands.base_velocity, "rel_standing_envs", 0.10),
            "heading_command": lambda c: setattr(
                c.commands.base_velocity, "heading_command", False),
            "rel_heading_envs": lambda c: setattr(
                c.commands.base_velocity, "rel_heading_envs", 0.75),
            "lin_vel_x": lambda c: setattr(
                c.commands.base_velocity.ranges, "lin_vel_x", (0.0, 1.5)),
            "ang_vel_z": lambda c: setattr(
                c.commands.base_velocity.ranges, "ang_vel_z", (0.0, 0.0)),
            "resampling_time_range": lambda c: setattr(
                c.commands.base_velocity, "resampling_time_range", (5.0, 5.0)),
            "max_init_terrain_level": lambda c: setattr(
                c.scene.terrain, "max_init_terrain_level", None),
        }
        for name, mutate in cases.items():
            with self.subTest(field=name):
                self.assertIn(name, self.broken(mutate))

    def test_terrain_proportion_is_guarded(self):
        message = self.broken(lambda c: setattr(
            c.scene.terrain.terrain_generator.sub_terrains["rails"],
            "proportion", 0.30))
        self.assertIn("rails", message)

    def test_missing_terrain_is_guarded(self):
        message = self.broken(lambda c: c.scene.terrain
                              .terrain_generator.sub_terrains.pop("rails"))
        self.assertIn("지형 키가 다르다", message)

    def test_sum_is_guarded_even_when_every_cell_is_unchecked(self):
        """**합 검사가 따로 있는 이유.**

        지형을 하나 더 «끼워 넣으면» 여덟 칸은 다 제값인데 합이 1.10 이 된다.
        키 검사가 먼저 걸리므로, 합 검사가 실제로 도는지 보려면 메시지에
        둘 다 있어야 한다.
        """
        message = self.broken(lambda c: c.scene.terrain.terrain_generator
                              .sub_terrains.__setitem__("intruder", NS(proportion=0.10)))
        self.assertIn("비중 합이 1 이 아니다", message)

    def test_rails_geometry_is_guarded(self):
        for field, value in (("rail_thickness_range", (0.08, 0.20)),
                             ("rail_height_range", (0.05, 0.20)),
                             ("platform_width", 2.0)):
            with self.subTest(field=field):
                message = self.broken(lambda c, f=field, v=value: setattr(
                    c.scene.terrain.terrain_generator.sub_terrains["rails"], f, v))
                self.assertIn("rails." + field, message)

    def test_omni_gap_is_guarded(self):
        message = self.broken(lambda c: setattr(
            c.scene.terrain.terrain_generator.sub_terrains["omni_gap"],
            "mode", "line"))
        self.assertIn("omni_gap.mode", message)

    def test_pose_range_is_guarded(self):
        message = self.broken(lambda c: c.events.reset_base.params["pose_range"]
                              .__setitem__("y", (-1.0, 1.0)))
        self.assertIn("pose_range.y", message)

    def test_v2b_guard_expects_its_own_standing_value(self):
        """v2b 에서 0.02 는 **틀린 값**이어야 한다. 물려받은 검사가 살아 있는지."""
        cfg = build(V2B)
        cfg.commands.base_velocity.rel_standing_envs = 0.02
        with self.assertRaises(RuntimeError) as caught:
            cfg._verify_overrides()
        self.assertIn("rel_standing_envs", str(caught.exception))

    def test_clean_config_does_not_raise(self):
        """**반대쪽도 본다.** 늘 던지는 관문은 관문이 아니라 고장이다."""
        for cls in (V2A, V2B):
            with self.subTest(cls=cls.__name__):
                build(cls)._verify_overrides()


def scanner_state(cfg):
    """한 판의 «지각» 설정을 한 덩이로. 두 판을 견줄 때 쓴다."""
    scanner = cfg.scene.height_scanner
    noise = cfg.observations.policy.height_scan.noise
    return {
        "drift": {k: tuple(v) for k, v in dict(scanner.ray_cast_drift_range).items()},
        "offset": tuple(scanner.offset.pos),
        "noise": (noise.n_min, noise.n_max),
        "sensor_drift": tuple(scanner.drift_range),
    }


def terrain_and_commands(cfg):
    """지형 비중과 명령 여섯 칸. 자식 판이 건드리면 안 되는 자리."""
    cmd = cfg.commands.base_velocity
    return {
        "terrain": {k: round(v.proportion, 6) for k, v
                    in cfg.scene.terrain.terrain_generator.sub_terrains.items()},
        "heading_command": cmd.heading_command,
        "rel_heading_envs": cmd.rel_heading_envs,
        "resampling": tuple(cmd.resampling_time_range),
        "heading": tuple(cmd.ranges.heading),
        "ang_vel_z": tuple(cmd.ranges.ang_vel_z),
        "lin_vel_x": tuple(cmd.ranges.lin_vel_x),
        "lin_vel_y": tuple(cmd.ranges.lin_vel_y),
    }


class PerceptionChildTests(unittest.TestCase):
    """**v2c · v2d 의 주장** · v2a 에서 자기 칸만 다르다."""

    def test_v2c_overrides_exactly_two_methods(self):
        self.assertEqual(
            {n for n in vars(V2C) if not n.startswith("__")},
            {"scanner_drift_range", "height_scan_noise"})

    def test_v2d_overrides_exactly_one_method(self):
        self.assertEqual(
            {n for n in vars(V2D) if not n.startswith("__")},
            {"scanner_offset_pos"})

    def test_v2c_changes_only_drift_and_noise(self):
        a, c = scanner_state(build(V2A)), scanner_state(build(V2C))
        self.assertEqual(
            c["drift"],
            {"x": (-0.05, 0.05), "y": (-0.05, 0.05), "z": (-0.05, 0.05)})
        self.assertEqual(c["noise"], (-0.02, 0.02))
        self.assertEqual(c["offset"], a["offset"])
        self.assertEqual(c["sensor_drift"], a["sensor_drift"])
        self.assertEqual({k for k in a if a[k] != c[k]}, {"drift", "noise"})

    def test_v2d_changes_only_the_grid_offset(self):
        a, d = scanner_state(build(V2A)), scanner_state(build(V2D))
        self.assertEqual(d["offset"], (0.2, 0.0, 20.0))
        self.assertEqual(d["drift"], a["drift"])
        self.assertEqual(d["noise"], a["noise"])
        self.assertEqual({k for k in a if a[k] != d[k]}, {"offset"})

    def test_children_do_not_touch_terrain_or_commands(self):
        want = terrain_and_commands(build(V2A))
        for name, cls in (("v2b", V2B), ("v2c", V2C), ("v2d", V2D)):
            with self.subTest(policy=name):
                self.assertEqual(terrain_and_commands(build(cls)), want)

    def test_v2b_does_not_touch_perception(self):
        self.assertEqual(scanner_state(build(V2B)), scanner_state(build(V2A)))

    def test_v2c_and_v2d_keep_v2a_standing(self):
        for name, cls in (("v2c", V2C), ("v2d", V2D)):
            with self.subTest(policy=name):
                self.assertEqual(
                    build(cls).commands.base_velocity.rel_standing_envs, 0.02)


class PerceptionGuardTests(unittest.TestCase):
    """**자식 판의 관문도 깨뜨려 본다.** 물려받은 검사가 자기 값을 본다."""

    def broken(self, cls, mutate):
        cfg = build(cls)
        mutate(cfg)
        with self.assertRaises(RuntimeError) as caught:
            cfg._verify_overrides()
        return str(caught.exception)

    def test_v2c_guard_rejects_v2a_drift(self):
        message = self.broken(V2C, lambda c: setattr(
            c.scene.height_scanner, "ray_cast_drift_range",
            {"x": (0.0, 0.0), "y": (0.0, 0.0), "z": (0.0, 0.0)}))
        self.assertIn("ray_cast_drift_range", message)

    def test_v2c_guard_rejects_v2a_noise(self):
        def mutate(cfg):
            cfg.observations.policy.height_scan.noise.n_min = -0.10
            cfg.observations.policy.height_scan.noise.n_max = 0.10
        self.assertIn("height_scan 잡음", self.broken(V2C, mutate))

    def test_v2d_guard_rejects_v2a_offset(self):
        message = self.broken(V2D, lambda c: setattr(
            c.scene.height_scanner.offset, "pos", (0.0, 0.0, 20.0)))
        self.assertIn("height_scanner.offset.pos", message)

    def test_v2a_guard_rejects_v2c_drift(self):
        """반대 방향도 본다. v2a 에서 드리프트가 켜져 있으면 막아야 한다."""
        message = self.broken(V2A, lambda c: setattr(
            c.scene.height_scanner, "ray_cast_drift_range",
            {"x": (-0.05, 0.05), "y": (-0.05, 0.05), "z": (-0.05, 0.05)}))
        self.assertIn("ray_cast_drift_range", message)

    def test_a_partially_applied_drift_is_caught(self):
        """세 축 중 «하나만» 어긋나도 걸리나."""
        message = self.broken(V2C, lambda c: c.scene.height_scanner
                              .ray_cast_drift_range.__setitem__("y", (0.0, 0.0)))
        self.assertIn("ray_cast_drift_range", message)

    def test_clean_children_do_not_raise(self):
        for name, cls in (("v2c", V2C), ("v2d", V2D)):
            with self.subTest(policy=name):
                build(cls)._verify_overrides()


if __name__ == "__main__":
    unittest.main()
