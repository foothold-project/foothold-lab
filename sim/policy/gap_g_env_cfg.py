# -*- coding: utf-8 -*-
"""G 조건 · heading 유지 제어 없이 직접 요 명령을 받는 학습 환경.

분류: 실험
작성: Codex 세션 (오흥재 지시) · 2026-09-20 09:33
근거: inbox/jay/20260920-FG-design.md v1.1 · fg_task1.md 3절
요지: B 지형은 유지하고 heading 제어를 끈 채 전진 · 요 · 정지 분포를 지정한다
상태: 구현 · 학습 전
판: v1.0
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .gap_terrain import ForwardGapTerrainCfg
from .gap_wide_env_cfg import UnitreeGo2GapWideEnvCfg


@configclass
class UnitreeGo2GapGEnvCfg(UnitreeGo2GapWideEnvCfg):
    """B 를 직접 상속하며 지형 · 보상 · 관측 · 리셋을 바꾸지 않는다."""

    def __post_init__(self):
        super().__post_init__()
        command = self.commands.base_velocity
        command.heading_command = False
        # 비활성 heading 범위를 남기면 Isaac Lab 이 경고하므로 명시적으로 지운다.
        command.ranges.heading = None
        command.ranges.ang_vel_z = (-1.0, 1.0)
        command.ranges.lin_vel_x = (0.4, 1.5)
        command.rel_standing_envs = 0.02
        self._verify_overrides()

    def _verify_overrides(self):
        """명령과 B 의 원래 forward_gap 을 확인하고 어긋나면 실패한다."""
        problems = []
        command = self.commands.base_velocity
        for name, actual, wanted in (
            ("heading_command", command.heading_command, False),
            ("heading", command.ranges.heading, None),
            ("ang_vel_z", command.ranges.ang_vel_z, (-1.0, 1.0)),
            ("lin_vel_x", command.ranges.lin_vel_x, (0.4, 1.5)),
            ("rel_standing_envs", command.rel_standing_envs, 0.02),
        ):
            if actual != wanted:
                problems.append(f"{name}: {actual!r} (기대값 {wanted!r})")
        gap = self.scene.terrain.terrain_generator.sub_terrains.get("forward_gap")
        if type(gap) is not ForwardGapTerrainCfg:
            problems.append("forward_gap 이 B 의 원래 지형이 아니다")
        else:
            for name, wanted in (("proportion", 0.10), ("gap_width_range", (0.15, 0.40)),
                                 ("gap_center_ratio", 0.5), ("approach_distance", 1.5),
                                 ("slab_thickness", 1.0), ("minimum_spawn_x", 0.75)):
                actual = getattr(gap, name)
                if actual != wanted:
                    problems.append(f"forward_gap.{name}: {actual!r} (기대값 {wanted!r})")
        if problems:
            raise RuntimeError("G 설정이 어긋났다:\n  - " + "\n  - ".join(problems))
