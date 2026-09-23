# -*- coding: utf-8 -*-
"""F 조건 · 넓은 heading 명령과 스폰을 둘러싼 고리 도랑.

분류: 실험
작성: Codex 세션 (오흥재 지시) · 2026-09-20 09:33
근거: inbox/jay/20260920-FG-design.md v1.1 · fg_task1.md 2절
요지: B 의 forward_gap 을 ring 으로 교체하고 F 명령 여섯 칸을 명시한다
상태: 구현 · 학습 전
판: v1.0
"""

from __future__ import annotations

from math import pi

from isaaclab.utils import configclass

from .gap_wide_env_cfg import UnitreeGo2GapWideEnvCfg
from .omni_gap_terrain import OmniGapTerrainCfg


KEEP_ROUGH_PROPORTIONS = {
    "pyramid_stairs": 0.18,
    "pyramid_stairs_inv": 0.18,
    "boxes": 0.18,
    "random_rough": 0.18,
    "hf_pyramid_slope": 0.09,
    "hf_pyramid_slope_inv": 0.09,
}
KEEP_POSE_RANGE = {
    "x": (-0.10, 0.10), "y": (-0.20, 0.20), "yaw": (-0.05, 0.05),
}


@configclass
class UnitreeGo2GapFEnvCfg(UnitreeGo2GapWideEnvCfg):
    """보상 · 관측 · 리셋을 B 에서 물려받고 지형과 명령만 바꾼다."""

    def __post_init__(self):
        super().__post_init__()
        terrains = self.scene.terrain.terrain_generator.sub_terrains
        old_gap = terrains.pop("forward_gap")
        terrains["omni_gap"] = OmniGapTerrainCfg(
            proportion=old_gap.proportion,
            size=old_gap.size,
            gap_width_range=old_gap.gap_width_range,
            slab_thickness=old_gap.slab_thickness,
            mode="ring", ring_radius=2.5,
        )
        command = self.commands.base_velocity
        command.heading_command = True
        command.ranges.heading = (-pi, pi)
        command.rel_heading_envs = 1.0
        command.ranges.ang_vel_z = (-1.0, 1.0)
        command.rel_standing_envs = 0.02
        command.ranges.lin_vel_x = (0.4, 1.5)
        self._verify_overrides()

    def _verify_overrides(self):
        """명령 여섯 칸과 지형 · 횡속도 · 초기 단계 · 리셋 보존을 되읽는다."""
        problems = []
        command = self.commands.base_velocity
        checks = (
            ("heading_command", command.heading_command, True),
            ("heading", command.ranges.heading, (-pi, pi)),
            ("rel_heading_envs", command.rel_heading_envs, 1.0),
            ("ang_vel_z", command.ranges.ang_vel_z, (-1.0, 1.0)),
            ("rel_standing_envs", command.rel_standing_envs, 0.02),
            ("lin_vel_x", command.ranges.lin_vel_x, (0.4, 1.5)),
            ("lin_vel_y", command.ranges.lin_vel_y, (0.0, 0.0)),
            ("max_init_terrain_level", self.scene.terrain.max_init_terrain_level, 2),
        )
        for name, actual, wanted in checks:
            if actual != wanted:
                problems.append(f"{name}: {actual!r} (기대값 {wanted!r})")
        terrains = self.scene.terrain.terrain_generator.sub_terrains
        if set(terrains) != set(KEEP_ROUGH_PROPORTIONS) | {"omni_gap"}:
            problems.append(f"지형 키가 다르다: {sorted(terrains)!r}")
        gap = terrains.get("omni_gap")
        if not isinstance(gap, OmniGapTerrainCfg):
            problems.append("omni_gap 이 OmniGapTerrainCfg 가 아니다")
        else:
            for name, wanted in (("mode", "ring"), ("ring_radius", 2.5),
                                 ("proportion", 0.10), ("gap_width_range", (0.15, 0.40)),
                                 ("slab_thickness", 1.0), ("num_sides", 64)):
                actual = getattr(gap, name)
                if actual != wanted:
                    problems.append(f"omni_gap.{name}: {actual!r} (기대값 {wanted!r})")
        for name, wanted in KEEP_ROUGH_PROPORTIONS.items():
            actual = getattr(terrains.get(name), "proportion", None)
            if actual != wanted:
                problems.append(f"rough6.{name}: {actual!r} (기대값 {wanted!r})")
        pose = self.events.reset_base.params["pose_range"]
        for axis, wanted in KEEP_POSE_RANGE.items():
            if pose.get(axis) != wanted:
                problems.append(f"pose_range.{axis}: {pose.get(axis)!r}")
        if problems:
            raise RuntimeError("F 설정이 어긋났다:\n  - " + "\n  - ".join(problems))
