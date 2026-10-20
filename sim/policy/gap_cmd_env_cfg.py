# -*- coding: utf-8 -*-
"""D 조건 · B 에서 **명령 손잡이 넷만** 되돌린 학습 환경.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-18
근거: `inbox/jay/20260918-v2-command-restore.md` 4절 · 팀장 기준선 `env.yaml` 과 `models/foothold-v1.env.yaml` 전수 대조
요지: B 와 다섯 줄만 다르다. 정지 · 저속 · 회전을 되찾고 gap 은 그대로 둔다
상태: 확정
판: v1.0

## 이 파일이 답하는 질문

**「명령을 좁힐 필요가 있었는가.」**

foothold-v1 은 NVIDIA Go2 rough 에서 17개 값을 바꾼 것이고, 그중 9개가 전진
전용 제약이었다. 9개 전부가 「틈을 만나는 표본을 최대화한다」는 하나의 목적에
정렬돼 있었고, 그 설계는 목적에 맞았다. **잘못은 특화 산출물을 범용 vN 으로
배포하면서 대가를 기록하지 않은 것이다.**

그래서 손잡이를 기능별로 가른다.

| 손잡이 | 무엇을 위한 것 | D 에서 |
|---|---|---|
| `reset pose_range` | 틈을 **만나게** 함 (표본) | **유지** |
| `max_init_terrain_level` | 학습 **가능**하게 | **유지** |
| `lin_vel_x` 하한 | 건널 관성 | **되돌림** |
| `ang_vel_z` · `heading` · `standing` | 옆으로 안 새게 | **되돌림** |

앞 둘은 「틈을 만나는 것」이고 뒤 둘은 「어떻게 걷는가」다. 목적이 다르므로
**뒤 둘만 되돌린다.** 로봇은 여전히 틈을 향해 서고, 정지 · 저속 · 회전 명령이
학습 분포에 들어온다.

**그것이 능력으로 이어지는지는 아직 모른다.** 학습하고 재 봐야 안다. 이 파일이
하는 것은 「조건을 만든다」까지다.

## 왜 새 파일인가

`gap_env_cfg.py`(A) 와 `gap_wide_env_cfg.py`(B) 를 **고치지 않는다.** 그 자리에서
고치면 A 와 B 를 다시 재현할 수 없다. `gap_wide_env_cfg.py` 가 A 에 대해 한
판단과 같은 판단이다.

## 다섯 줄이 왜 손잡이 넷인가

`heading_command` 와 `rel_heading_envs` 는 한 쌍이라 함께 움직인다. 따로 켜면
뜻이 없다.

## `ang_vel_z` 를 왜 여는가 (안 열면 회전이 통째로 죽는다)

`heading_command=True` 면 `UniformVelocityCommand._update_command()` 가 매 스텝
요레이트 명령을 이렇게 **덮어쓴다** (`velocity_command.py` 150~160행) `확인됨`.

    vel_command_b[:, 2] = clip(heading_control_stiffness x heading_error,
                               ranges.ang_vel_z[0], ranges.ang_vel_z[1])

즉 `ranges.ang_vel_z` 는 **heading 제어기 출력의 상하한**이다. B 처럼 (0, 0) 으로
두면 클립 상하한이 둘 다 0 이라 **요레이트 «명령» 이 언제나 정확히 0** 이 된다.
heading 을 켜도 회전 명령이 안 생긴다. 그래서 둘을 함께 움직인다.

명령이 0 인 것과 로봇이 실제로 안 도는 것은 다른 말이다. 코드에서 확인한 것은
앞의 것이다.

곁들여 알아 둘 것이 하나 있다. `rel_heading_envs = 1.0` 이면 표집된 모든 환경의
요레이트가 heading 오차에서 나온다.

**그렇다고 「생성 방식이 다르니 분포 밖」이라고 말할 수는 없다.** 정책이 보는
명령 벡터는 어느 쪽으로 만들었든 같은 세 숫자다.

다른 것은 **명령끼리의 짝과 시간 모양**이다. heading 제어기가 만든 요레이트는
전진 속도와 함께 움직이고 heading 오차가 줄면 따라 줄어든다. 프로브가 주는
계단형 요레이트는 그 짝을 안 따른다. 프로브 결과를 읽을 때 이 차이를 감안해야
한다. 얼마나 벌어지는지는 아직 재지 않았다 `미측정`.

## `rel_standing_envs` 가 정지의 유일한 통로다

`_update_command()` 는 standing 환경의 명령 **3축 전부**를 0 으로 만든다
(`vel_command_b[standing_env_ids, :] = 0.0`) `확인됨`. 이 2 % 가 정책이 「전
명령 0」을 보는 유일한 자리다. B 는 이것이 0.0 이라 **정지를 한 번도 안 봤다.**

## `lin_vel_y` 를 왜 안 여는가

Go2 에 횡보행 수요가 낮고, 손잡이를 하나 더 열면 원인 분리가 흐려진다.
한 번에 하나씩 본다. 필요해지면 다음 판에서 연다.

## 설치

이 파일은 저장소가 정본이고, 실행하려면 Isaac Lab 쪽으로 복사해야 한다.

    copy sim\\policy\\gap_cmd_env_cfg.py ^
      C:\\isaac\\IsaacLab\\source\\isaaclab_tasks\\isaaclab_tasks\\manager_based\\
      locomotion\\velocity\\config\\go2\\gap_training\\gap_cmd_env_cfg.py

그리고 같은 폴더 `__init__.py` 에 `Isaac-Velocity-GapWideCmd-Unitree-Go2-v0`
등록 블록을 **더한다** (기존 세 블록은 안 건드린다).

## 어디서 출발하나

**NVIDIA 공식 가중치다.**

    .pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt
    sha256 f2aa77bf · 6,881,762 B

foothold-v1 이 이어받은 `nvidia_pretrained.pt` 와 `model_state_dict` 가 같고
`iter` 만 0 으로 되감겨 있다(팀장 실측). **D 도 같은 자리에서 출발해야 B 와의
비교가 성립한다.**

팀장 기준선 `2026-08-11_20-32-58/model_1499.pt` 는 **출발점이 아니다.** 그 런의
`env.yaml` 은 17항목 diff 를 뜨는 «설정» 기준선으로만 쓴다.

## 몇 번 돌리나

`max_iterations` 는 `gap_ppo_cfg.py` 에 **100** 으로 박혀 있다 `확인됨`.
foothold-v1 의 1501 은 CLI 로 준 값이다. **D 도 CLI 로 줘야 한다.**
안 주면 100 iter 짜리가 나온다.
"""

from __future__ import annotations

from isaaclab.utils import configclass

from .gap_wide_env_cfg import UnitreeGo2GapWideEnvCfg


# 설계 문서 4-1 절. **여기 하나만 고치면 된다.**
CMD_LIN_VEL_X = (0.0, 1.5)
CMD_ANG_VEL_Z = (-1.0, 1.0)
CMD_HEADING_COMMAND = True
CMD_REL_HEADING_ENVS = 1.0
CMD_REL_STANDING_ENVS = 0.02

# B 에서 **그대로 물려받아야** 하는 것. 되읽어 확인만 하고 쓰지는 않는다.
# 상위 클래스가 바뀌어 이것들이 흔들리면 D 는 더 이상 「명령만 되돌린 B」가
# 아니게 되고, 그러면 이 판이 무엇을 재는 판인지 말할 수 없다.
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
class UnitreeGo2GapWideCmdEnvCfg(UnitreeGo2GapWideEnvCfg):
    """B 와 동일하되 명령 손잡이 넷만 NVIDIA Go2 rough 쪽으로 되돌린다."""

    def __post_init__(self):
        super().__post_init__()

        command = self.commands.base_velocity

        command.ranges.lin_vel_x = CMD_LIN_VEL_X
        command.ranges.ang_vel_z = CMD_ANG_VEL_Z
        command.heading_command = CMD_HEADING_COMMAND
        command.rel_heading_envs = CMD_REL_HEADING_ENVS
        command.rel_standing_envs = CMD_REL_STANDING_ENVS

        self._verify_overrides()

    def _verify_overrides(self):
        """조용한 실패를 막는다. **안 덮였거나 딴 것이 흔들렸으면 여기서 터진다.**

        `gap_wide_env_cfg.py` 의 패턴을 그대로 따르되, 바꾼 것뿐 아니라
        **안 바꾸기로 한 것까지** 본다. 설계 문서 9절 「학습 전」 관문을 코드로
        옮긴 것이다. 사람이 훑으면 또 빠진다.
        """
        problems = []

        command = self.commands.base_velocity

        # -- 바꾼 다섯 줄이 정말 덮였는가
        checks = (
            ("lin_vel_x", tuple(command.ranges.lin_vel_x), CMD_LIN_VEL_X),
            ("ang_vel_z", tuple(command.ranges.ang_vel_z), CMD_ANG_VEL_Z),
            ("heading_command", command.heading_command, CMD_HEADING_COMMAND),
            ("rel_heading_envs", command.rel_heading_envs, CMD_REL_HEADING_ENVS),
            ("rel_standing_envs", command.rel_standing_envs,
             CMD_REL_STANDING_ENVS),
        )

        for name, actual, wanted in checks:
            if actual != wanted:
                problems.append(f"{name} 이 안 덮였다: {actual!r} (원하는 값 {wanted!r})")

        # -- `heading_command` 를 켰으면 `ranges.heading` 이 있어야 한다.
        #    없으면 Isaac Lab 이 환경을 짓다가 죽는다 (`velocity_command.py` 65행).
        if command.heading_command and getattr(command.ranges, "heading", None) is None:
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
                "D 는 횡이동을 안 연다"
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
                "D 설정이 어긋났다:\n  - " + "\n  - ".join(problems)
            )
