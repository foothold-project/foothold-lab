# -*- coding: utf-8 -*-
"""E 조건 · 틈을 바라보는 비율과 요 명령의 크기를 나눈 학습 환경.

분류: 실험
작성: Codex 세션 (오흥재 지시) · 2026-09-19 23:59
근거: `inbox/jay/20260919-E-design.md` v1.1 2·3절 · 작업 1 설정 지시
요지: B 를 직접 상속하고 E 명령 분포를 명시한다. 보상 · 지형 · 리셋은 유지한다
상태: 설정 작성 · 학습 전
판: v1.0

## 이 파일이 답하는 질문

**「틈을 바라보게 하면서 요 제어를 지킬 수 있는가.」**

설계 정본은 D 의 gap 하락을 노출 감소로 진단하고, E 에서는 명령 분포만
바꾼다. 기존 배포본이 무너지지 않는 것이 우선이다. gap 회복과 rails 유지가
실제로 함께 가능한지는 학습과 평가 뒤에 판단한다. 지금은 성능 미측정이다.

## 왜 B 를 직접 상속하는가

`UnitreeGo2GapWideEnvCfg` 에서 시작해 여섯 설정을 명시적으로 덮는다.
D 를 상속하면 D 의 값이 섞여 E 의 조건을 코드에서 바로 읽기 어렵다.
`gap_env_cfg.py` · `gap_wide_env_cfg.py` · `gap_cmd_env_cfg.py` 는 각 판의
재현을 위해 그대로 둔다.

| 설정 | E 값 | 설계 근거 |
|---|---|---|
| `heading_command` · `ranges.heading` | True · (-0.5, 0.5) | 3-1절 · 틈을 바라보는 범위 |
| `rel_heading_envs` | 0.75 | 3-2절 · heading 과 직접 요 명령의 비율 |
| `ranges.lin_vel_x` | (0.4, 1.5) | 3-3절 · 커리큘럼 문턱에서 유도한 하한 |
| `ranges.ang_vel_z` | (-1.0, 1.0) | 3-2절 · D 의 요 명령 범위 유지 |
| `rel_standing_envs` | 0.02 | 2절 · D 의 정지 명령 비율 유지 |

D 대비 바뀌는 것은 heading 범위 · heading 환경 비율 · 전진 속도 하한이다.
`heading_command` 와 `ranges.heading` 은 함께 명시한다. 켜기만 하고 범위를
두지 않으면 Isaac Lab 이 환경을 만들지 못하므로 자기검사에서도 잡는다.

## heading 비율과 요 크기를 왜 나누는가

설계 3-2절의 소스 분석에 따르면 요 명령은 모든 환경에서 먼저 표집되고,
heading 환경에서만 heading 오차로 덮인다. heading 범위를 좁히기만 하면
그 오차로 만드는 요 명령도 작아진다.

E 는 heading 환경 비율을 0.75 로 두어 나머지 환경에 직접 표집한
(-1.0, 1.0) 요 명령을 남긴다. **0.75 는 유도된 값이 아니라 설계의 절충값**
이다 `추측`. 이 비율이 rails 성능을 지키는지는 아직 확인하지 않았다.
정지 환경에서는 명령 전부가 0 이 되므로 직접 요 환경 모두가 항상 회전
명령을 받는다는 뜻은 아니다.

## 전진 속도 하한은 왜 0.4 인가

설계 3-3절은 지형 크기 (8.0, 8.0) · 에피소드 20.0 s · 횡속도 0 을
기준으로 승급 문턱 4.0 m 와 강등 문턱 vx × 10.0 m 를 비교한다.
그 둘이 만나는 하한이 0.4 m/s 다. 응답곡선은 이 값의 근거로 쓰지 않는다.
저속 고정 명령에서의 비용은 후속 평가 대상이며 이 파일은 판정하지 않는다.

## 무엇을 그대로 두는가

보상 · 관측 · 지형 · 커리큘럼 · 리셋은 B 에서 물려받는다. 횡이동도 열지
않는다. 자기검사는 작업서가 지정한 gap 폭과 비율 · 횡속도 · 초기 지형
단계 · 리셋 자세를 되읽는다. 상위 설정이 바뀌어 이 값들이 흔들리면
E 를 같은 조건으로 재현했다고 볼 수 없으므로 즉시 실패시킨다.

## 설치와 실행 범위

저장소의 이 파일이 정본이다. Isaac Lab 의 Go2 `gap_training/` 에 복사하고
같은 폴더 `__init__.py` 에 `Isaac-Velocity-GapE-Unitree-Go2-v0` 를 추가한다.
학습 러너는 기존 `gap_ppo_cfg:UnitreeGo2GapPPORunnerCfg` 를 쓴다.
설정 객체 생성 · 학습 · GPU 검증은 다음 작업에서 수행한다.
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .gap_wide_env_cfg import UnitreeGo2GapWideEnvCfg


# 설계 정본 2절. E 의 여섯 설정은 여기서만 정한다.
CMD_LIN_VEL_X = (0.4, 1.5)
CMD_ANG_VEL_Z = (-1.0, 1.0)
CMD_HEADING_COMMAND = True
CMD_HEADING = (-0.5, 0.5)
CMD_REL_HEADING_ENVS = 0.75
CMD_REL_STANDING_ENVS = 0.02

# B 에서 그대로 물려받아야 하는 것. 되읽어 확인만 하고 쓰지는 않는다.
# 명령 외의 조건이 흔들리면 E 의 변경 효과를 같은 기준으로 비교할 수 없다.
KEEP_GAP_WIDTH_RANGE = (0.15, 0.40)
KEEP_GAP_PROPORTION = 0.10
KEEP_LIN_VEL_Y = (0.0, 0.0)
KEEP_MAX_INIT_TERRAIN_LEVEL = 2
KEEP_POSE_RANGE = {
    "x": (-0.10, 0.10),
    "y": (-0.20, 0.20),
    "yaw": (-0.05, 0.05),
}


@configclass
class UnitreeGo2GapEEnvCfg(UnitreeGo2GapWideEnvCfg):
    """B 와 동일하되 설계 정본의 E 명령 분포를 직접 덮는다."""

    def __post_init__(self):
        super().__post_init__()

        command = self.commands.base_velocity

        command.ranges.lin_vel_x = CMD_LIN_VEL_X
        command.ranges.ang_vel_z = CMD_ANG_VEL_Z
        command.heading_command = CMD_HEADING_COMMAND
        command.ranges.heading = CMD_HEADING
        command.rel_heading_envs = CMD_REL_HEADING_ENVS
        command.rel_standing_envs = CMD_REL_STANDING_ENVS

        self._verify_overrides()

    def _verify_overrides(self):
        """덮은 값과 보존할 값을 되읽고 어긋나면 즉시 실패시킨다.

        D 의 검사 패턴을 따른다. heading 범위가 None 인 경우에도 튜플 변환
        오류로 끝내지 않고, 설정 문제를 모아 RuntimeError 로 보고한다.
        """
        problems = []

        command = self.commands.base_velocity
        heading = getattr(command.ranges, "heading", None)

        # -- 명시한 여섯 설정이 정말 덮였는가
        checks = (
            ("lin_vel_x", tuple(command.ranges.lin_vel_x), CMD_LIN_VEL_X),
            ("ang_vel_z", tuple(command.ranges.ang_vel_z), CMD_ANG_VEL_Z),
            ("heading_command", command.heading_command, CMD_HEADING_COMMAND),
            ("heading", tuple(heading) if heading is not None else None, CMD_HEADING),
            ("rel_heading_envs", command.rel_heading_envs, CMD_REL_HEADING_ENVS),
            ("rel_standing_envs", command.rel_standing_envs,
             CMD_REL_STANDING_ENVS),
        )

        for name, actual, wanted in checks:
            if actual != wanted:
                problems.append(f"{name} 이 안 덮였다: {actual!r} (원하는 값 {wanted!r})")

        # -- heading 을 켰으면 범위가 있어야 한다 (`velocity_command.py` 65행).
        if command.heading_command and heading is None:
            problems.append(
                "heading_command 를 켰는데 ranges.heading 이 없다. "
                "이대로면 환경 생성에서 죽는다"
            )

        # -- B 에서 물려받아야 하는 것이 흔들리지 않았는가
        gap = self.scene.terrain.terrain_generator.sub_terrains["forward_gap"]

        if tuple(gap.gap_width_range) != KEEP_GAP_WIDTH_RANGE:
            problems.append(
                f"forward_gap 폭이 B 와 다르다: {tuple(gap.gap_width_range)!r}"
            )

        if gap.proportion != KEEP_GAP_PROPORTION:
            problems.append(f"forward_gap 비율이 B 와 다르다: {gap.proportion!r}")

        if tuple(command.ranges.lin_vel_y) != KEEP_LIN_VEL_Y:
            problems.append(
                f"lin_vel_y 가 열렸다: {tuple(command.ranges.lin_vel_y)!r}. "
                "E 는 횡이동을 안 연다"
            )

        if self.scene.terrain.max_init_terrain_level != KEEP_MAX_INIT_TERRAIN_LEVEL:
            problems.append(
                "max_init_terrain_level 이 B 와 다르다: "
                f"{self.scene.terrain.max_init_terrain_level!r}"
            )

        pose_range = self.events.reset_base.params["pose_range"]

        for axis, wanted in KEEP_POSE_RANGE.items():
            actual = tuple(pose_range.get(axis, ()))

            if actual != wanted:
                problems.append(
                    f"reset_base.pose_range.{axis} 가 B 와 다르다: {actual!r}"
                )

        if problems:
            raise RuntimeError(
                "E 설정이 어긋났다:\n  - " + "\n  - ".join(problems)
            )
