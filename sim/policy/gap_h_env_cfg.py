# -*- coding: utf-8 -*-
"""H 조건 · F 의 고리 지형에 D 의 `lin_vel_x` 하한.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-20
근거: inbox/jay/20260920-H-design.md v1.0 2절 · 2-2절
요지: F 에서 `lin_vel_x` 하한 하나만 0.4 에서 0.0 으로 되돌린다
상태: 구현 · 학습 전
판: v1.0

## 이 판이 왜 있나

2 x 2 (하한 x 지형) 의 **비어 있는 네 번째 칸**이다.

```
            +x 띠        고리
하한 0.0    D           H  <- 여기
하한 0.4    E · G       F
```

**어느 쪽에서 봐도 단일 변수다.**

```
H 대 F     lin_vel_x 하한만 다르다        (0.0 대 0.4)
H 대 D     학습 지형만 다르다             (고리 대 +x 띠)
```

지금까지 넷은 서로 둘 이상이 달라 결과를 한 손잡이에 못 돌렸다.

## F 를 «복사»했지 상속하지 않았다

설계 2-2 절이 「`gap_f_env_cfg.py` 를 복사해 `lin_vel_x` 만 고친다」고 했다.
E · F · G 가 전부 B 를 직접 상속하는 관례와도 맞는다.

F 를 상속하면 **나중에 F 가 바뀔 때 H 가 조용히 따라 움직인다.** F 는 이미
학습이 끝난 판이라 그 설정이 굳어 있어야 하고, H 는 **그때의 F** 와 한 칸만
달라야 한다. 그래서 베껴 둔다.

**베끼면 둘이 갈라질 수 있으므로 「한 칸만 다른지」를 따로 잰다.** 학습 전에
두 설정을 지어 칸끼리 견주고 그 결과를 판정문에 싣는다. 자기검사 안에서 F 를
지어 견주는 방법도 있으나, `__post_init__` 이 `sub_terrains` 에서
`forward_gap` 을 꺼내는(pop) 구조라 **같은 설정을 두 번 짓는 것이 안전한지
확인되지 않았다.** 확인 안 된 것을 자기검사에 넣지 않는다.

`_verify_overrides` 는 F 의 것과 같은 검사에 하한만 새 값으로 둔다.
"""

from __future__ import annotations

from math import pi

from isaaclab.utils import configclass

from .gap_wide_env_cfg import UnitreeGo2GapWideEnvCfg
from .omni_gap_terrain import OmniGapTerrainCfg


# **H 가 F 와 다른 단 하나.** D 의 `CMD_LIN_VEL_X` 와 같은 값이다.
CMD_LIN_VEL_X = (0.0, 1.5)

# 아래는 F 에서 그대로 베낀 것이다. 하나라도 바꾸면 단일 변수가 깨진다.
CMD_HEADING_COMMAND = True
CMD_HEADING = (-pi, pi)
CMD_REL_HEADING_ENVS = 1.0
CMD_ANG_VEL_Z = (-1.0, 1.0)
CMD_REL_STANDING_ENVS = 0.02

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
class UnitreeGo2GapHEnvCfg(UnitreeGo2GapWideEnvCfg):
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
        command.heading_command = CMD_HEADING_COMMAND
        command.ranges.heading = CMD_HEADING
        command.rel_heading_envs = CMD_REL_HEADING_ENVS
        command.ranges.ang_vel_z = CMD_ANG_VEL_Z
        command.rel_standing_envs = CMD_REL_STANDING_ENVS
        command.ranges.lin_vel_x = CMD_LIN_VEL_X
        self._verify_overrides()

    def _verify_overrides(self):
        """명령 여섯 칸과 지형 · 횡속도 · 초기 단계 · 리셋 보존을 되읽는다."""
        problems = []
        command = self.commands.base_velocity
        checks = (
            ("heading_command", command.heading_command, CMD_HEADING_COMMAND),
            ("heading", command.ranges.heading, CMD_HEADING),
            ("rel_heading_envs", command.rel_heading_envs, CMD_REL_HEADING_ENVS),
            ("ang_vel_z", command.ranges.ang_vel_z, CMD_ANG_VEL_Z),
            ("rel_standing_envs", command.rel_standing_envs, CMD_REL_STANDING_ENVS),
            ("lin_vel_x", command.ranges.lin_vel_x, CMD_LIN_VEL_X),
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
            raise RuntimeError("H 설정이 어긋났다:\n  - " + "\n  - ".join(problems))
