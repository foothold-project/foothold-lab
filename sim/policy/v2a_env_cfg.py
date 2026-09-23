# -*- coding: utf-8 -*-
"""v2a · F 의 고리 지형과 명령에 석헌의 `rails` 를 더한 판.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: inbox/jay/20260921-v2-design.md v1.0 (커밋 c766f97) 1 절
요지: 축 1 을 먼저 고정한다. `lin_vel_x` 하한을 «안 열고» 정지는 `rel_standing` 으로 산다
상태: 구현 · 학습 전
판: v1.0

## F 에서 바뀌는 것 둘

1. `rails` 0.10 을 더하고 **rough6 비중을 0.18 -> 0.15 · 슬로프 0.09 -> 0.10** 로 다시 나눈다
2. 학습량 1500 -> **3000** (설정이 아니라 `--max_iterations` 로 준다)

`omni_gap` 은 F 의 것 그대로이고 명령 여섯 칸도 F 와 같다.
`rails` 값은 **평가 하네스에서 그대로 가져왔다**
(`sim/eval/generalization_env_cfg.py` 97~102 행 · 석헌과 같은 값).

**학습에 넣은 지형으로 평가하므로 `rails` 는 「미경험 험지」주장에서 빠진다.**
설계 6 절 5 번에 적혀 있다.

## 이 파일을 v2b 와 «한 모듈로 합치지 마십시오** `확인됨`

`standing_envs()` 는 모듈 전역 `REL_STANDING_ENVS` 를 **부를 때** 읽는다.
두 파일을 합치면 나중에 정의된 v2b 의 0.10 이 v2a 것까지 덮어써서
**v2a 가 조용히 0.10 으로 학습한다.** 오류도 안 난다.
`tests/test_v2_cpu.py` 를 짜다 실제로 겪었다.

## 아래 네 «선언» 은 v2c · v2d 가 한 칸씩 물려받아 바꾼다

`standing_envs` · `scanner_drift_range` · `height_scan_noise` ·
`scanner_offset_pos` 넷은 v2a 가 **바꾸지 않는 값까지 적어 둔 것**이다.
되읽기가 이 넷을 검사하므로, 자식 판은 **자기가 바꾼 칸만 덮어쓰면**
나머지가 v2a 와 같다는 것이 구조로 보증된다.

**v2a 의 동작은 이 선언으로 안 바뀐다** · 돌아간 학습의 `params/env.yaml`
에서 읽은 값 그대로다 (`drift_range` (0,0) · `ray_cast_drift_range` 셋 다
(0,0) · `offset.pos` (0,0,20) · `height_scan` 잡음 ±0.10).
"""

from __future__ import annotations

from math import pi

import isaaclab.terrains as terrain_gen
from isaaclab.utils import configclass

from .gap_wide_env_cfg import UnitreeGo2GapWideEnvCfg
from .omni_gap_terrain import OmniGapTerrainCfg


# 설계 1 절의 여덟 종. 합이 1.00 이어야 한다 (아래에서 되읽는다).
TERRAIN_PROPORTIONS = {
    "pyramid_stairs": 0.15,
    "pyramid_stairs_inv": 0.15,
    "boxes": 0.15,
    "random_rough": 0.15,
    "hf_pyramid_slope": 0.10,
    "hf_pyramid_slope_inv": 0.10,
    "omni_gap": 0.10,
    "rails": 0.10,
}
ROUGH_KEYS = (
    "pyramid_stairs", "pyramid_stairs_inv", "boxes",
    "random_rough", "hf_pyramid_slope", "hf_pyramid_slope_inv",
)
RAILS_THICKNESS_RANGE = (0.08, 0.18)
RAILS_HEIGHT_RANGE = (0.05, 0.18)
RAILS_PLATFORM_WIDTH = 1.5
KEEP_POSE_RANGE = {
    "x": (-0.10, 0.10), "y": (-0.20, 0.20), "yaw": (-0.05, 0.05),
}
REL_STANDING_ENVS = 0.02

# 아래 셋은 v2a 가 «안 건드리는» 값이다. 그래도 적어 두고 검사한다.
# 상류 기본값이 바뀌면 학습이 시작되기 전에 걸린다.
SCANNER_DRIFT_RANGE = {"x": (0.0, 0.0), "y": (0.0, 0.0), "z": (0.0, 0.0)}
SCANNER_OFFSET_POS = (0.0, 0.0, 20.0)
HEIGHT_SCAN_NOISE = (-0.10, 0.10)


@configclass
class UnitreeGo2V2aEnvCfg(UnitreeGo2GapWideEnvCfg):
    """보상 · 관측 · 리셋을 B 에서 물려받고 지형과 명령만 바꾼다."""

    def __post_init__(self):
        super().__post_init__()
        terrains = self.scene.terrain.terrain_generator.sub_terrains

        old_gap = terrains.pop("forward_gap")
        terrains["omni_gap"] = OmniGapTerrainCfg(
            proportion=TERRAIN_PROPORTIONS["omni_gap"],
            size=old_gap.size,
            gap_width_range=old_gap.gap_width_range,
            slab_thickness=old_gap.slab_thickness,
            mode="ring", ring_radius=2.5,
        )
        terrains["rails"] = terrain_gen.MeshRailsTerrainCfg(
            proportion=TERRAIN_PROPORTIONS["rails"],
            rail_thickness_range=RAILS_THICKNESS_RANGE,
            rail_height_range=RAILS_HEIGHT_RANGE,
            platform_width=RAILS_PLATFORM_WIDTH,
        )
        for name in ROUGH_KEYS:
            terrains[name].proportion = TERRAIN_PROPORTIONS[name]

        command = self.commands.base_velocity
        command.heading_command = True
        command.ranges.heading = (-pi, pi)
        command.rel_heading_envs = 1.0
        command.ranges.ang_vel_z = (-1.0, 1.0)
        command.rel_standing_envs = self.standing_envs()
        command.ranges.lin_vel_x = (0.4, 1.5)
        command.resampling_time_range = (10.0, 10.0)

        # **네 선언을 실제로 «건다».** v2a 에서는 상류 기본값과 같아 아무
        # 일도 안 하지만, 자식 판은 선언 하나만 덮어쓰면 적용까지 따라온다.
        scanner = self.scene.height_scanner
        scanner.ray_cast_drift_range = dict(self.scanner_drift_range())
        scanner.offset.pos = tuple(self.scanner_offset_pos())
        noise = self.observations.policy.height_scan.noise
        noise.n_min, noise.n_max = self.height_scan_noise()

        self._verify_overrides()

    def standing_envs(self):
        """v2b 가 **이 한 칸만** 덮어쓴다. 나머지는 물려받아 같다."""
        return REL_STANDING_ENVS

    def scanner_drift_range(self):
        """v2c 가 덮어쓴다. 에피소드마다 다시 뽑히는 «상관» 드리프트."""
        return SCANNER_DRIFT_RANGE

    def height_scan_noise(self):
        """v2c 가 덮어쓴다. **매 정책 스텝** 다시 뽑히는 셀별 백색 잡음."""
        return HEIGHT_SCAN_NOISE

    def scanner_offset_pos(self):
        """v2d 가 덮어쓴다. 격자 중심의 몸통 기준 위치."""
        return SCANNER_OFFSET_POS

    def _verify_overrides(self):
        """명령 · 지형 · 비중 · 리셋을 되읽는다. 어긋나면 학습을 시작하지 않는다."""
        problems = []
        command = self.commands.base_velocity
        checks = (
            ("heading_command", command.heading_command, True),
            ("heading", command.ranges.heading, (-pi, pi)),
            ("rel_heading_envs", command.rel_heading_envs, 1.0),
            ("ang_vel_z", command.ranges.ang_vel_z, (-1.0, 1.0)),
            ("rel_standing_envs", command.rel_standing_envs, self.standing_envs()),
            ("lin_vel_x", command.ranges.lin_vel_x, (0.4, 1.5)),
            ("lin_vel_y", command.ranges.lin_vel_y, (0.0, 0.0)),
            ("resampling_time_range", command.resampling_time_range, (10.0, 10.0)),
            ("max_init_terrain_level", self.scene.terrain.max_init_terrain_level, 2),
        )
        for name, actual, wanted in checks:
            if actual != wanted:
                problems.append(f"{name}: {actual!r} (기대값 {wanted!r})")

        terrains = self.scene.terrain.terrain_generator.sub_terrains
        if set(terrains) != set(TERRAIN_PROPORTIONS):
            problems.append(f"지형 키가 다르다: {sorted(terrains)!r}")
        for name, wanted in TERRAIN_PROPORTIONS.items():
            actual = getattr(terrains.get(name), "proportion", None)
            if actual != wanted:
                problems.append(f"비중 {name}: {actual!r} (기대값 {wanted!r})")

        # **합을 따로 센다.** 여덟 칸이 각각 맞아도 합이 1 이 아니면 표본이 밀린다.
        total = sum(
            getattr(terrains[name], "proportion", 0.0) for name in terrains)
        if abs(total - 1.0) > 1e-9:
            problems.append(f"비중 합이 1 이 아니다: {total!r}")

        gap = terrains.get("omni_gap")
        if not isinstance(gap, OmniGapTerrainCfg):
            problems.append("omni_gap 이 OmniGapTerrainCfg 가 아니다")
        else:
            for name, wanted in (("mode", "ring"), ("ring_radius", 2.5),
                                 ("gap_width_range", (0.15, 0.40)),
                                 ("slab_thickness", 1.0), ("num_sides", 64)):
                actual = getattr(gap, name)
                if actual != wanted:
                    problems.append(f"omni_gap.{name}: {actual!r} (기대값 {wanted!r})")

        rails = terrains.get("rails")
        if not isinstance(rails, terrain_gen.MeshRailsTerrainCfg):
            problems.append("rails 가 MeshRailsTerrainCfg 가 아니다")
        else:
            # 범위 둘은 리스트로 들어올 수 있어 tuple 로 맞춰 견준다.
            for name, wanted in (
                    ("rail_thickness_range", RAILS_THICKNESS_RANGE),
                    ("rail_height_range", RAILS_HEIGHT_RANGE)):
                actual = tuple(getattr(rails, name))
                if actual != wanted:
                    problems.append(f"rails.{name}: {actual!r} (기대값 {wanted!r})")
            if rails.platform_width != RAILS_PLATFORM_WIDTH:
                problems.append(
                    f"rails.platform_width: {rails.platform_width!r} "
                    f"(기대값 {RAILS_PLATFORM_WIDTH!r})")

        scanner = self.scene.height_scanner
        drift = {k: tuple(v) for k, v in
                 dict(getattr(scanner, "ray_cast_drift_range", {})).items()}
        if drift != {k: tuple(v) for k, v in self.scanner_drift_range().items()}:
            problems.append(
                f"ray_cast_drift_range: {drift!r} (기대값 {self.scanner_drift_range()!r})")
        if tuple(scanner.offset.pos) != tuple(self.scanner_offset_pos()):
            problems.append(
                f"height_scanner.offset.pos: {tuple(scanner.offset.pos)!r} "
                f"(기대값 {self.scanner_offset_pos()!r})")
        noise = self.observations.policy.height_scan.noise
        if (noise.n_min, noise.n_max) != tuple(self.height_scan_noise()):
            problems.append(
                f"height_scan 잡음: {(noise.n_min, noise.n_max)!r} "
                f"(기대값 {tuple(self.height_scan_noise())!r})")

        pose = self.events.reset_base.params["pose_range"]
        for axis, wanted in KEEP_POSE_RANGE.items():
            if pose.get(axis) != wanted:
                problems.append(f"pose_range.{axis}: {pose.get(axis)!r}")

        if problems:
            raise RuntimeError(
                type(self).__name__ + " 설정이 어긋났다:\n  - "
                + "\n  - ".join(problems))
