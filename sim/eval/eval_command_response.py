# -*- coding: utf-8 -*-
"""**명령 응답 하네스.** 시간에 따라 변하는 명령으로 정지 · 저속 · 회전을 잰다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-18
근거: `inbox/jay/20260918-v2-command-restore.md` · `timeseries.py` 93열 스키마 · `extras.py` POSTURE_COLUMNS
요지: 하네스 둘 가운데 «명령» 쪽. 주행 하네스를 한 줄도 안 건드린다
상태: 확정

## 하네스가 둘이다

| 무엇 | 어디 | 무엇을 보나 |
|---|---|---|
| **주행 하네스** | `eval_generalization.py` | 험지를 통과하는가 |
| **명령 응답 하네스** | 이 파일 | 멈추고 · 천천히 걷고 · 도는가 |

**배포 관문은 하나다.** 둘 다 통과해야 배포한다. 하네스만 나누고 관문을 안
합치면 보고서가 둘 나오고 아무도 둘 다 안 본다.

## 왜 주행 하네스 «안» 이 아니라 새 파일인가

`eval_generalization.py` 는 **명령이 안 변한다는 전제 위에 서 있다.**

    238~244행   lin_vel_y · ang_vel_z 를 (0,0) 으로, heading_command 를 False 로 못박는다
    1183행      매 스텝 명령을 되읽어 1e-5 를 넘게 어긋나면 그 자리에서 죽는다

**그 전제가 판정의 근거다.** 「0.5 m/s 직진에서 90 %」가 뜻을 가지려면 정말로
0.5 m/s 직진이었어야 하고, 1183행이 그것을 보증한다. 시간에 따라 변하는 명령은
이 보증을 깨므로 **하네스 안에 넣으면 안 된다.** 그래서 따로 둔다.

**이 파일은 성공률을 내지 않는다.** 판정은 지금도 `eval_generalization.py` 의
네 축 AND 하나다. 여기서 나오는 것은 **관측**이다.

## 무엇을 재나 (설계 문서 5-3 절)

| 재는 것 | 왜 |
|---|---|
| 명령 0 도달 시각 · 마지막 1초 잔류속도 | G1 정지와 정지 «유지» |
| **관절 목표각의 시간 변화량** | 정책 출력이 상수로 굳는가. 「얼음」의 정체 |
| 몸통 피치 · 롤 최대 · 낙상 | 무게중심 유지 |
| 명령 대 실속도 응답곡선 | G2 저속. 분포 경계가 어디서 갈라지나 |
| `ang_vel_z` 추종비 | G3 회전 |
| 발 미끄러짐 · 네 발 동시 접지 지속시간 | 멈춘 방식의 질 |

### 관절 목표각 변화량에 대해 (앞선 판의 과장을 물린다)

앞선 판은 「지금 아무도 이것을 안 쟀다」고 적었다. **틀렸다.**
`extras.POSTURE_COLUMNS` 에 **`action_delta_rms`** 가 이미 있다
(`eval_generalization.py` 1333행 · 1471행) `확인됨`. 관절 목표각은 액션의
아핀 변환이라 같은 신호다.

**새로운 것은 양이 아니라 «시간축»이다.** `action_delta_rms` 는 에피소드
하나에 숫자 하나라 「시간이 가면서 줄어드는가」를 물을 수 없다. 이 하네스는
스텝마다 남기므로 그것을 물을 수 있다.

    변화량이 0 으로 수렴    정책 출력이 굳었다. **이것은 이 값만으로 말할 수 있다**
    변화량이 계속 큼        정책이 계속 새 목표를 낸다. 몸이 따라오는지 «아닌지» 는
                            `joint_pos` 와 `base_*` 를 함께 봐야 안다.
                            **정상 보행도 이 값이 크다**

즉 굳었다는 것은 이 열 혼자 말할 수 있고, 안 따라온다는 것은 못 한다.

## 기록은 93열 스키마 그대로

`timeseries.py` 의 `columns_for()` 를 그대로 쓴다. **두 벌을 만들지 않는다.**
`joint_target_*` 12열이 이미 있어서 새 열이 필요 없다 `확인됨`.

**93열이다** (trace 17 + 몸통·명령 16 + 발 12 + 관절 48) `확인됨`.
`tests/test_timeseries.py` 의 `test_Go2_는_93열이다` 가 이 숫자를 못 박는다.
`timeseries.py` 머리글과 `sim/eval/README.md` 에 아직 「92열」로 적힌 자리가
있는데, `yaw_deg` 가 들어오기 전 숫자라 낡은 것이다.

다른 것은 명령 세 열(`cmd_vx_mps` · `cmd_vy_mps` · `cmd_wz_rps`)에 **스텝마다
실제로 정책이 본 값**이 들어간다는 것뿐이다. 하네스는 거기에 상수를 적는다
(`eval_generalization.py` 1113~1116행). 열은 같고 내용이 다르다.

`verify_against_row()` 는 부르지 않는다. 그것은 판정 표의 «그 줄» 과 대조하는
함수인데 프로브에는 대응하는 판정 행이 없다. 없는 것을 있는 척하지 않는다.

## 어느 체크포인트를 재나 (**기준선이 둘이다. 섞지 마십시오**)

| 이름 | 파일 | 쓰임 |
|---|---|---|
| **정책 기준선 (zero)** | `.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt` · sha256 `f2aa77bf` | **목표선.** D 의 출발점이기도 하다 |
| 배포본 | `models/foothold-v1.pt` · sha256 `c7612aef` | 현재선. 얼마나 잃었나 |
| D | (학습 뒤) | 되찾았나 |
| 참고용 | `logs/.../2026-08-11_20-32-58/model_1499.pt` · sha256 `512d543a` | **기준선이 아니다.** 팀장 재현본이다. 넣어도 되지만 참고로만 |

`logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58/params/env.yaml` 은 **설정**
기준선이다. 17항목 diff 를 뜨는 데만 쓰고 정책 기준선과 섞지 않는다.

foothold-v1 이 이어받은 `nvidia_pretrained.pt` 는 공식 파일과 해시도 크기도
다르지만 `model_state_dict` 17개 텐서가 전부 같고 `iter` 만 1499 에서 0 으로
바뀌어 있다 (팀장 실측). **「iter=0 으로 되감은 사본」이 사실이다.**

## 지형은 평지다

험지 성적은 축 1(하네스)이 잰다. 여기는 **「명령에 어떻게 반응하나」만** 본다.
지형을 섞으면 정지 실패가 명령 탓인지 지형 탓인지 안 갈린다.

평지를 쓰면 덤이 하나 있다. `height_scan` 과 `height_scan_with_gap` 은
**광선이 빗나갔을 때만** 다른데(`sim/eval/gap_observations.py`), 무한 평면에는
빗나가는 광선이 없다. 그래서 **세 정책이 글자 그대로 같은 관측을 본다**
`확인됨`. 어느 쪽으로 학습했든 기준선 대조가 공평하다.

`UnitreeGo2FlatEnvCfg` 를 **쓰지 않는다.** 그쪽은 `height_scanner` 를 통째로
떼서 관측이 48 차원이 된다(`flat_env_cfg.py`). 우리 정책 셋은 전부 235 차원이라
안 들어간다 `확인됨`. 그래서 rough 설정을 가져다 지형만 평면으로 바꾼다.

## 명령을 어떻게 주입하나

`heading_command=False` · `rel_heading_envs=0` · `rel_standing_envs=0` 으로 두면
`UniformVelocityCommand._update_command()` 가 **아무것도 덮어쓰지 않는다**
(`velocity_command.py` 143~163행) `확인됨`. 재표집도 `resampling_time_range` 를
크게 잡아 막는다. 그러면 `vel_command_b` 에 쓴 값이 그대로 남는다.

`ManagerBasedRLEnv.step()` 은 명령을 먼저 계산하고 그 다음에 관측을 만든다
(231행 · 236행). 그래서 **행동을 고르기 전에** 명령을 쓰고 관측을 다시 지어야
정책이 그 스텝의 명령을 본다. 안 그러면 한 스텝 밀린다. `PolicyCfg` 에 이력
항이 없어 관측을 두 번 지어도 값이 안 바뀐다 `확인됨`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

# 별표. Windows 우회. `eval_generalization.py` · `record_flat_baseline.py` 와
# 같은 이유이고 같은 순서다. Kit 를 띄운 뒤에 `rsl_rl.runners` 를 처음
# import 하면 프로세스가 통째로 죽는다.
import torch  # noqa: F401,E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

from isaaclab.app import AppLauncher  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import timeseries  # noqa: E402
import command_response_metrics as cmd_metrics  # noqa: E402


# ---------------------------------------------------------------------------
# 시나리오 · 명령 프로파일
# ---------------------------------------------------------------------------
#
# 프로파일은 `t` (초) 하나를 받아 `(vx, vy, wz)` 를 돌려준다. **정책이 학습한
# 범위 밖을 일부러 훑는다.** 그것이 이 도구의 목적이다.

def _stop_profile(t):
    """4초 전진한 뒤 명령을 0 으로 떨어뜨리고 6초를 본다. G1."""
    return (1.0, 0.0, 0.0) if t < 4.0 else (0.0, 0.0, 0.0)


def _ramp_profile(t):
    """0 에서 1.5 까지 20초에 걸쳐 선형으로. G2 응답곡선."""
    return (max(0.0, min(1.5, 1.5 * t / 20.0)), 0.0, 0.0)


def _turn_profile(t):
    """제자리에서 요레이트를 계단으로 훑는다. G3.

    각 3초씩 -1.0 · -0.5 · 0.0 · +0.5 · +1.0 이다. 맨 앞 1.5초와 마지막 구간
    뒤는 명령이 0 이다. **계단 사이에는 쉬는 구간이 없다.** 그래서 각 구간의
    앞쪽 절반은 직전 계단에서 넘어오는 과도구간이고, 추종비는 뒤쪽 절반만 본다.
    """
    steps = (-1.0, -0.5, 0.0, 0.5, 1.0)

    if t < 1.5:
        return (0.0, 0.0, 0.0)

    index = int((t - 1.5) // 3.0)

    if index >= len(steps):
        return (0.0, 0.0, 0.0)

    return (0.0, 0.0, steps[index])


# 회전 계단의 순서와 쉬는 구간을 바꾼 두 판. **`turn` 의 미달 한 칸이
# 「오른쪽이 약한 것」인지 「맨 마지막 칸이라 앞의 것이 쌓인 것」인지 가른다.**
#
# 2026-09-18 실측에서 D 의 `wz +1.00` 추종비가 0.253 으로 문턱(0.40) 아래였다.
# 그 칸은 `turn` 의 **맨 마지막**이라 앞 네 칸의 누적 요각 표류가 섞여 있다.
# 한 판으로는 안 갈리므로 둘을 따로 돌린다.
#
#   turn_rest  같은 순서에 칸 사이 쉬는 구간을 넣는다 -> 쌓임이 원인인가
#   turn_rev   쉬는 구간 없이 순서만 뒤집는다        -> 자리가 원인인가
#
# **둘 다 좋아지면** 쌓임이고, **`turn_rev` 에서만 좋아지면** 자리이고,
# **둘 다 그대로면** 진짜 좌우 비대칭이다.

TURN_STEPS = (-1.0, -0.5, 0.0, 0.5, 1.0)
TURN_LEAD_S = 1.5
TURN_HOLD_S = 3.0
TURN_REST_S = 1.5


def _turn_steps_profile(t, steps, rest_s):
    """계단 목록과 쉬는 구간 길이로 만든 요레이트 프로파일."""
    if t < TURN_LEAD_S:
        return (0.0, 0.0, 0.0)

    period = TURN_HOLD_S + rest_s
    elapsed = t - TURN_LEAD_S
    index = int(elapsed // period)

    if index >= len(steps):
        return (0.0, 0.0, 0.0)

    # 칸 안에서 앞 `TURN_HOLD_S` 만 명령을 주고 나머지는 쉰다.
    if (elapsed - index * period) >= TURN_HOLD_S:
        return (0.0, 0.0, 0.0)

    return (0.0, 0.0, steps[index])


def _turn_rest_profile(t):
    """`turn` 과 같은 순서 · 칸 사이에 1.5초씩 쉰다."""
    return _turn_steps_profile(t, TURN_STEPS, TURN_REST_S)


def _turn_rev_profile(t):
    """`turn` 과 같은 간격 · 순서만 뒤집는다. `+1.0` 이 맨 앞으로 온다."""
    return _turn_steps_profile(t, tuple(reversed(TURN_STEPS)), 0.0)


def _hold_profile(t):
    """처음부터 끝까지 전 명령 0. 인지 세션이 본 증상 그대로.

    「얼음」은 여기서 가장 깨끗하게 보인다. 걷다가 멈추는 것이 아니라
    **처음부터 서 있으라고만** 한다.
    """
    return (0.0, 0.0, 0.0)


SCENARIOS = {
    "stop": {"profile": _stop_profile, "duration_s": 10.0,
             "what": "4초 전진 뒤 명령 0. 정지와 정지 유지"},
    "ramp": {"profile": _ramp_profile, "duration_s": 20.0,
             "what": "0 에서 1.5 까지 선형 증가. 응답곡선"},
    "turn": {"profile": _turn_profile, "duration_s": 18.0,
             "what": "제자리 요레이트 계단 다섯. 회전 추종비"},
    "hold": {"profile": _hold_profile, "duration_s": 20.0,
             "what": "20초 내내 전 명령 0. 얼음"},

    # 아래 둘은 기본 실행(`all`)에 안 들어간다. `turn` 의 미달 칸을 가를 때만
    # 이름을 찍어 부른다. 기본에 넣으면 매번 8분이 더 든다.
    "turn_rest": {"profile": _turn_rest_profile, "duration_s": 25.0,
                  "what": "회전 계단 · 칸 사이 1.5초 쉼. 쌓임이 원인인가",
                  "extra": True},
    "turn_rev": {"profile": _turn_rev_profile, "duration_s": 18.0,
                 "what": "회전 계단 · 순서 뒤집음(+1.0 이 처음). 자리가 원인인가",
                 "extra": True},
}

# `--scenario all` 이 도는 기본 넷. `extra` 가 붙은 것은 빠진다.
DEFAULT_SCENARIOS = tuple(
    name for name, spec in SCENARIOS.items() if not spec.get("extra")
)


parser = argparse.ArgumentParser(
    description="명령 반응 프로브. 판정 하네스를 건드리지 않는다.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument("--checkpoint", type=str, required=True,
                    help="정책 체크포인트 `.pt`. rsl_rl 이 낸 것")
parser.add_argument("--label", type=str, default=None,
                    help="산출물에 적을 이름. 안 주면 체크포인트 파일 이름")
parser.add_argument("--scenario", type=str, default="all",
                    help="stop · ramp · turn · hold · all (쉼표로 여럿). `all` 은 기본 넷만 돈다. turn_rest · turn_rev 는 이름을 찍어야 돈다")
parser.add_argument("--num_envs", type=int, default=64,
                    help="같은 명령을 동시에 받는 로봇 수. 초기 자세 흩어짐이 표본")
parser.add_argument("--env_spacing", type=float, default=8.0,
                    help="평지에서 로봇 사이 간격 (m). 20초를 걸어도 안 부딪게")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--output_dir", type=str, required=True)
parser.add_argument("--contact_threshold_n", type=float, default=1.0,
                    help="이 힘을 넘으면 «닿았다». 발 접지 판정에만 쓴다")
parser.add_argument("--settle_speed_mps", type=float, default=0.05,
                    help="이 아래로 내려오면 «멈췄다». 정지 도달 시각 판정")
parser.add_argument("--keep_pushes", action="store_true",
                    help="바깥에서 미는 이벤트를 살린다. 기본은 끈다")
parser.add_argument("--overwrite", action="store_true",
                    help="출력 폴더에 앞 실행이 남아 있어도 지우고 덮어쓴다. "
                         "안 주면 시작 전에 죽는다")

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# parquet 이 없으면 **시뮬을 띄우기 전에** 죽는다. 7분 돌고 끝에서 죽지 않게.
timeseries.require_pyarrow()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402

from isaaclab.utils.math import quat_apply  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import metrics  # noqa: E402


# **기준 task.** NVIDIA Go2 rough 그대로다. 여기서 지형만 평면으로 바꾼다.
# gap 쪽 설정을 안 쓰는 이유는 모듈 머리글에 적었다. 평지에서는 두 height_scan
# 이 같은 값을 내므로 이쪽이 세 정책 모두에게 중립이다.
BASE_TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"

# 학습이 본 적 없는 명령을 주입하므로 재표집이 끼어들면 안 된다.
NEVER_RESAMPLE_S = 1.0e9


def refuse_dirty_output_dir(output_dir, scenario_names):
    """앞 실행이 남아 있으면 **시작 전에 죽는다.**

    같은 폴더에 두 번 쓰면 앞 실행의 parquet 이 그대로 남는다. 이번 실행에서
    어떤 env 가 표본이 모자라 파일을 안 쓰면 **그 자리에 앞 실행 파일이 남아**
    나중에 폴더를 훑는 사람이 두 실행을 섞어 읽는다. 3회차 검증에서
    재현됐다(앞 실행 `ep0002.parquet` 이 남고 JSON 은 전부 `null`).

    `--overwrite` 를 주면 지우고 간다. **안 주면 안 지운다.** 남의 결과를
    말없이 지우는 것이 더 나쁘다.
    """
    dirty = []

    for name in scenario_names:
        ts_dir = os.path.join(output_dir, name, "timeseries")

        if os.path.isdir(ts_dir) and os.listdir(ts_dir):
            dirty.append((name, ts_dir, len(os.listdir(ts_dir))))

    if not dirty:
        return

    if not args_cli.overwrite:
        lines = [
            "  - {} : {} 개 파일 ({})".format(name, count, ts_dir)
            for name, ts_dir, count in dirty
        ]

        raise RuntimeError(
            "출력 폴더에 앞 실행이 남아 있습니다:\n"
            + "\n".join(lines)
            + "\n\n같은 폴더에 다시 쓰면 이번에 안 쓴 자리에 앞 실행 파일이 "
            "남아 두 실행이 섞입니다.\n"
            "다른 --output_dir 을 주거나, 지우고 가려면 --overwrite 를 "
            "주십시오."
        )

    import shutil

    for name, ts_dir, _count in dirty:
        shutil.rmtree(ts_dir)
        print(f"[WARN] 앞 실행을 지웠습니다: {ts_dir}", flush=True)


def configure_probe(env_cfg):
    """평지로 바꾸고 명령을 «내가 쓰는 대로 남게» 만든다.

    `gap_wide_env_cfg.py` 의 조용한 실패 방지 패턴을 그대로 따른다. 덮은 뒤에
    되읽어 확인하고, 안 덮였으면 그 자리에서 터뜨린다.
    """
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.scene.env_spacing = args_cli.env_spacing
    env_cfg.seed = args_cli.seed

    # -- 지형을 무한 평면으로. `height_scanner` 는 그대로 둔다(관측 235 유지).
    env_cfg.scene.terrain.terrain_type = "plane"
    env_cfg.scene.terrain.terrain_generator = None
    env_cfg.scene.terrain.max_init_terrain_level = None

    if hasattr(env_cfg.curriculum, "terrain_levels"):
        env_cfg.curriculum.terrain_levels = None

    # -- 관측 잡음을 끈다. 프로브는 «정책이 무엇을 하는가» 를 재는 것이라
    #    잡음이 끼면 관절 목표각 변화량이 잡음 때문인지 정책 때문인지 안 갈린다.
    env_cfg.observations.policy.enable_corruption = False

    # -- 바깥에서 미는 것을 끈다. 「멈춰 서 있다가 무너진다」를 재는데 밀어 버리면
    #    무너진 원인이 밀린 것인지 스스로 무너진 것인지 안 갈린다.
    if not args_cli.keep_pushes:
        if hasattr(env_cfg.events, "push_robot"):
            env_cfg.events.push_robot = None
        if hasattr(env_cfg.events, "base_external_force_torque"):
            env_cfg.events.base_external_force_torque = None

    # -- 명령. 아래 넷이 다 맞아야 `_update_command()` 가 무위가 된다.
    cmd = env_cfg.commands.base_velocity
    cmd.resampling_time_range = (NEVER_RESAMPLE_S, NEVER_RESAMPLE_S)
    cmd.heading_command = False
    cmd.rel_heading_envs = 0.0
    cmd.rel_standing_envs = 0.0
    cmd.ranges.lin_vel_x = (0.0, 0.0)
    cmd.ranges.lin_vel_y = (0.0, 0.0)
    cmd.ranges.ang_vel_z = (0.0, 0.0)

    # `heading_command` 가 False 인데 `ranges.heading` 이 남아 있으면
    # Isaac Lab 이 경고를 낸다(`velocity_command.py` 70~73행). 지워 둔다.
    if getattr(cmd.ranges, "heading", None) is not None:
        cmd.ranges.heading = None

    verify_probe_config(env_cfg)

    return env_cfg


def verify_probe_config(env_cfg):
    """덮였는지 되읽는다. **안 덮였으면 여기서 죽는다.**

    상위 설정이 바뀌어 한 줄이라도 안 먹으면, 조용히 틀린 값을 내는 대신
    시작할 때 터진다. `gap_wide_env_cfg.py` 와 같은 판단이다.
    """
    problems = []

    terrain = env_cfg.scene.terrain

    if terrain.terrain_type != "plane":
        problems.append(f"지형이 평면이 아니다: {terrain.terrain_type!r}")

    if terrain.terrain_generator is not None:
        problems.append("terrain_generator 가 안 지워졌다")

    if env_cfg.scene.height_scanner is None:
        problems.append(
            "height_scanner 가 없다. 관측이 235 차원이 아니게 되어 "
            "정책이 안 들어간다"
        )

    if env_cfg.observations.policy.height_scan is None:
        problems.append("height_scan 관측항이 없다. 위와 같은 이유로 막는다")

    if env_cfg.observations.policy.enable_corruption:
        problems.append("관측 잡음이 안 꺼졌다")

    cmd = env_cfg.commands.base_velocity

    if cmd.heading_command:
        problems.append(
            "heading_command 가 True 다. 이러면 `_update_command()` 가 "
            "매 스텝 ang_vel_z 를 heading 오차로 덮어써서 주입이 안 남는다"
        )

    if cmd.rel_heading_envs != 0.0:
        problems.append(f"rel_heading_envs 가 0 이 아니다: {cmd.rel_heading_envs}")

    if cmd.rel_standing_envs != 0.0:
        problems.append(
            f"rel_standing_envs 가 0 이 아니다: {cmd.rel_standing_envs}. "
            "이러면 일부 env 의 명령 3축이 통째로 0 으로 덮인다"
        )

    if min(cmd.resampling_time_range) < 1.0e6:
        problems.append(
            f"resampling_time_range 가 너무 짧다: {cmd.resampling_time_range}. "
            "에피소드 중간에 재표집이 끼어들어 주입한 명령이 날아간다"
        )

    if problems:
        raise RuntimeError(
            "프로브 설정이 안 덮였다:\n  - " + "\n  - ".join(problems)
        )


def initial_forward_vectors(robot, num_envs, device):
    """시작 자세의 전방축 단위벡터. `eval_generalization.py` 289행과 같은 식."""
    local_x = torch.zeros((num_envs, 3), device=device)
    local_x[:, 0] = 1.0

    forward_w = quat_apply(robot.data.root_quat_w, local_x)
    forward_xy = forward_w[:, :2]

    return forward_xy / torch.linalg.vector_norm(
        forward_xy, dim=1, keepdim=True
    ).clamp_min(1.0e-8)


def resolve_foot_bodies(robot, contact_sensor):
    """발 넷의 번호를 관절체·접촉센서 **두 번호 공간에서** 따로 집는다.

    `eval_generalization.py` 525행과 같은 판단이다. 못 집으면 죽지 않고 발 열을
    빈 칸으로 남긴다. 발은 관측이지 판정이 아니다.
    """
    def slots_from(finder, label):
        try:
            found, names = finder(".*_foot")
        except Exception as error:  # noqa: BLE001
            print(f"[WARN] {label} 에서 발을 못 찾았습니다: {error}", flush=True)
            return None

        slots = timeseries.foot_slots(found, names)

        if slots is None:
            print(f"[WARN] {label} 의 발이 넷이 아닙니다: {names}", flush=True)

        return slots

    body_slots = slots_from(robot.find_bodies, "관절체")
    sensor_slots = slots_from(contact_sensor.find_bodies, "접촉 센서")

    if body_slots is None or sensor_slots is None:
        print("[WARN] 발 열(높이 · 접촉력)은 빈 칸으로 남습니다.", flush=True)
        return (None, None)

    return (body_slots, sensor_slots)


def load_policy(env, checkpoint_path, device):
    """rsl_rl 체크포인트에서 추론용 정책 하나.

    학습 설정은 레지스트리에서 가져온다. **구조가 안 맞으면 여기서 죽는다.**
    235 차원이 아닌 정책을 조용히 받아들이면 관측이 밀린 채로 돌아간다.
    """
    agent_cfg = load_cfg_from_registry(BASE_TASK, "rsl_rl_cfg_entry_point")

    if not isinstance(agent_cfg, dict):
        agent_cfg = agent_cfg.to_dict()

    runner = OnPolicyRunner(env, agent_cfg, log_dir=None, device=device)
    runner.load(checkpoint_path)

    # 관측 폭을 되읽어 못 박는다. 우리 정책 셋은 전부 235 차원이다 `확인됨`
    # (체크포인트 셋을 직접 열어 `actor.0.weight` 가 (512, 235) 인 것을 봤다).
    # 안 맞는 것을 조용히 받으면 관측이 밀린 채로 끝까지 돌아간다.
    observed = int(env.get_observations()["policy"].shape[-1])
    expected = policy_input_width(runner)

    if expected is None:
        print("[WARN] 정책의 입력 폭을 못 읽었습니다. 폭 대조를 건너뜁니다.",
              flush=True)
    elif observed != expected:
        raise RuntimeError(
            f"관측 폭이 안 맞습니다. 환경 {observed} · 정책 {expected}. "
            "height_scanner 를 떼는 설정을 쓰면 이렇게 됩니다"
        )
    else:
        print(f"[PASS] 관측 {observed} 차원이 정책과 맞습니다.", flush=True)

    return runner.get_inference_policy(device=device)


def policy_input_width(runner):
    """정책 첫 층의 입력 폭. 못 읽으면 `None`.

    rsl_rl 판이 올라가 속성 이름이 바뀌어도 **프로브가 죽지는 않게** 한다.
    이 값은 대조용이지 계산에 쓰이지 않는다.
    """
    try:
        for layer in runner.alg.policy.actor:
            if hasattr(layer, "in_features"):
                return int(layer.in_features)
    except Exception:  # noqa: BLE001
        return None

    return None


def build_layout(joint_names):
    """버퍼 자리표. `eval_generalization.py` 977행과 같은 규칙이다.

    **한 곳에만 적는다.** 담는 쪽과 푸는 쪽이 이 목록 하나를 함께 본다.
    숫자를 두 군데 적으면 한쪽만 고쳐도 오류가 안 나고 값만 밀린다.

    하네스와 다른 것은 `cmd` 3칸이 있다는 것뿐이다. 하네스는 명령이 상수라
    버퍼에 담을 필요가 없었다.
    """
    layout = (
        ("pos", 3),
        ("quat", 4),
        ("vel_b", 3),
        ("vel_w", 3),
        ("ang_b", 3),
        ("foot_pos", 12),
        ("foot_force", 4),
        ("joint_pos", len(joint_names)),
        ("joint_vel", len(joint_names)),
        ("joint_torque", len(joint_names)),
        ("joint_target", len(joint_names)),
        ("cmd", 3),
    )

    offset = {}
    width = 0

    for field, size in layout:
        offset[field] = (width, width + size)
        width += size

    return offset, width


def main():
    label = args_cli.label or os.path.splitext(
        os.path.basename(args_cli.checkpoint)
    )[0]

    if not os.path.isfile(args_cli.checkpoint):
        raise RuntimeError(f"체크포인트가 없습니다: {args_cli.checkpoint}")

    names = ([n.strip() for n in args_cli.scenario.split(",")]
             if args_cli.scenario != "all" else list(DEFAULT_SCENARIOS))

    unknown = [n for n in names if n not in SCENARIOS]

    if unknown:
        raise RuntimeError(
            f"모르는 시나리오: {unknown}. 있는 것은 {list(SCENARIOS)} 입니다."
        )

    # **시뮬을 띄우기 전에** 본다. 7분 돌고 끝에서 죽지 않게.
    refuse_dirty_output_dir(args_cli.output_dir, names)

    os.makedirs(args_cli.output_dir, exist_ok=True)

    env_cfg = load_cfg_from_registry(BASE_TASK, "env_cfg_entry_point")

    # 가장 긴 시나리오에 맞춘다. 짧은 시나리오는 그 길이에서 스스로 멈춘다.
    longest = max(SCENARIOS[n]["duration_s"] for n in names)
    env_cfg.episode_length_s = longest + 1.0

    configure_probe(env_cfg)

    env = gym.make(BASE_TASK, cfg=env_cfg)
    env = RslRlVecEnvWrapper(env)

    raw_env = env.unwrapped

    # 정책을 짓기 전에 한 번 돌려 센서·관측 버퍼를 채운다.
    # `eval_generalization.py` 780행과 같은 자리다.
    raw_env.reset()

    device = raw_env.device
    robot = raw_env.scene["robot"]
    contact_sensor = raw_env.scene.sensors["contact_forces"]

    dt = raw_env.step_dt
    num_envs = raw_env.num_envs

    joint_names = list(robot.data.joint_names)
    ts_columns = timeseries.columns_for(joint_names)
    ts_offset, raw_width = build_layout(joint_names)

    foot_body_slots, foot_sensor_slots = resolve_foot_bodies(robot, contact_sensor)

    command_term = raw_env.command_manager.get_term("base_velocity")

    policy = load_policy(env, args_cli.checkpoint, device)

    print("\n" + "=" * 78)
    print("명령 반응 프로브")
    print("=" * 78)
    print(f"정책        : {label}")
    print(f"체크포인트  : {args_cli.checkpoint}")
    print(f"sha256      : {metrics_file_sha256(args_cli.checkpoint)}")
    print(f"env         : {num_envs} 대 · 간격 {args_cli.env_spacing} m · 평지")
    print(f"스텝        : dt {dt:.4f} s  ({1.0 / dt:.1f} Hz)")
    print(f"관절 {len(joint_names)}개 : {joint_names}")
    print(f"열 수       : {len(ts_columns)}")
    print(f"시나리오    : {names}")
    print("[PASS] 설정이 전부 덮였습니다.", flush=True)

    summary = {}

    for name in names:
        summary[name] = run_scenario(
            name, env, raw_env, robot, contact_sensor, command_term,
            policy, device, dt, num_envs, joint_names, ts_columns,
            ts_offset, raw_width, foot_body_slots, foot_sensor_slots, label,
        )

    write_manifest(label, names, summary, dt, num_envs, joint_names, ts_columns)

    env.close()
    simulation_app.close()


def metrics_file_sha256(path):
    """체크포인트 지문. `run_manifest.json` 의 `policy_sha256` 과 같은 뜻."""
    import hashlib

    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def run_scenario(name, env, raw_env, robot, contact_sensor, command_term,
                 policy, device, dt, num_envs, joint_names, ts_columns,
                 ts_offset, raw_width, foot_body_slots, foot_sensor_slots,
                 label):
    """시나리오 하나를 끝까지 돌리고 parquet 과 지표를 낸다."""
    spec = SCENARIOS[name]
    profile = spec["profile"]
    n_steps = int(round(spec["duration_s"] / dt))

    print("\n" + "-" * 78)
    print(f"[{name}] {spec['what']}")
    print(f"        {spec['duration_s']:.1f} 초 · {n_steps} 스텝")
    print("-" * 78, flush=True)

    # **시나리오마다 처음부터 시작한다.** 앞 시나리오가 끝난 자세를 물려받으면
    # 「20초를 서 있었다」가 「이미 지쳐 있었다」와 섞인다.
    raw_env.reset()

    # 시작 자세를 잡아 둔다. `fwd_m` · `lat_m` 이 이 기준이다.
    start_xy = robot.data.root_pos_w[:, :2].clone()
    forward_dir = initial_forward_vectors(robot, num_envs, device)

    # 평지라 지면이 z = 0 이다. 험지 하네스는 타일 높이를 빼지만 여기는 뺄 것이 없다.
    floor_z = torch.zeros(num_envs, device=device)

    buffer = torch.zeros((num_envs, n_steps, raw_width), device=device)

    # 넘어진 env 는 그 자리에서 기록을 멈춘다. 리셋된 뒤의 값을 같은 에피소드에
    # 이어 붙이면 「넘어졌다가 멀쩡해졌다」가 된다.
    alive = torch.ones(num_envs, dtype=torch.bool, device=device)
    n_valid = torch.zeros(num_envs, dtype=torch.long, device=device)
    fell_at = torch.full((num_envs,), float("nan"), device=device)

    for step in range(n_steps):
        t = step * dt
        vx, vy, wz = profile(t)

        # **행동을 고르기 전에** 명령을 쓴다. `step()` 은 명령을 먼저 계산하고
        # 관측을 그 다음에 만드는데(231행 · 236행), 우리가 들고 있는 `obs` 는
        # 직전 스텝 것이라 이대로 쓰면 한 스텝 밀린다.
        command_term.vel_command_b[:, 0] = vx
        command_term.vel_command_b[:, 1] = vy
        command_term.vel_command_b[:, 2] = wz

        # 관측을 다시 지어 이번 스텝의 명령이 들어가게 한다. `PolicyCfg` 에
        # 이력 항이 없어 두 번 지어도 다른 값이 안 나온다.
        obs = env.get_observations()

        # **스텝 «전» 에 담는다** (`eval_generalization.py` 1209행과 같은 자리).
        # `env.step()` 안에서 에피소드가 끝나면 그 자리에서 리셋이 돌고
        # `ContactSensor.reset()` 이 접촉력과 그 이력을 0 으로 지운다. 스텝 뒤에
        # 담으면 넘어지는 순간의 발 접촉이 0 으로 둔갑한다.
        #
        # 담기는 것은 「시각 t 의 몸 상태」와 「그때 정책이 본 명령」 한 쌍이다.
        sample = collect_sample(
            robot, contact_sensor, command_term, num_envs, device,
            foot_body_slots, foot_sensor_slots,
        )

        room = alive.nonzero(as_tuple=False).flatten()

        if room.numel() > 0:
            buffer[room, n_valid[room]] = sample[room]
            n_valid[room] += 1

        with torch.inference_mode():
            action = policy(obs)

        env.step(action)

        # 넘어짐. `time_out` 이 아닌 종료만 낙상으로 센다.
        terminated = raw_env.termination_manager.terminated

        newly = alive & terminated

        if newly.any():
            # **`t` 가 아니라 `t + dt` 다.** 종료는 `env.step()` 이 끝난 뒤에
            # 확인하므로 그 시각은 이 스텝이 «끝난» 시각이다. `t` 로 적으면
            # 첫 스텝 낙상이 0.0 초가 되어 「시작하자마자」와 구별되지 않는다.
            fell_at[newly] = t + dt
            alive = alive & ~newly

        if not alive.any():
            # 저장값과 같은 눈금으로 적는다. `fell_at` 은 `t + dt` 다.
            print(f"        {t + dt:.2f} s 에 전부 넘어졌습니다.", flush=True)
            break

    return finish_scenario(
        name, spec, label, buffer, n_valid, fell_at, dt, num_envs,
        joint_names, ts_columns, ts_offset, start_xy, forward_dir, floor_z,
    )


def collect_sample(robot, contact_sensor, command_term, num_envs, device,
                   foot_body_slots, foot_sensor_slots):
    """이번 스텝의 원자료 한 줄(모든 env). **GPU 왕복을 한 번으로 묶는다.**

    `eval_generalization.py` 의 `timeseries_slice()` 와 같은 순서이고, 맨 뒤에
    명령 3칸이 붙는다.
    """
    parts = [
        robot.data.root_pos_w,
        robot.data.root_quat_w,
        robot.data.root_lin_vel_b,
        robot.data.root_lin_vel_w,
        robot.data.root_ang_vel_b,
    ]

    if foot_body_slots is None:
        parts.append(torch.full((num_envs, 16), float("nan"), device=device))
    else:
        foot_pos = robot.data.body_pos_w[:, foot_body_slots, :]

        # **이력 최댓값이 아니라 «지금» 접촉력이다.** 하네스는
        # `net_forces_w_history` 의 최댓값을 적는다(`eval_generalization.py`
        # 1036행).
        #
        # 이 센서는 `history_length=3` 이고(`velocity_env_cfg.py` 74행)
        # `update_period` 가 `sim.dt` 0.005 초다(같은 파일 320행 · 311행)
        # `확인됨`. 그래서 이력 세 칸은 **지금 · 5 ms 전 · 10 ms 전**이고
        # 최댓값은 10 ms 앞까지를 끌어온다. 제어 주기 20 ms 보다는 짧다.
        #
        # 걷는 판을 셀 때는 그것이 문제가 안 되지만 **「서 있는가」를 재는 순간
        # 치명적이다.** 발이 이미 떨어졌는데 10 ms 전 힘 때문에 접지로 세면
        # 미끄러짐과 동시 접지 시간이 둘 다 부풀어 오른다. 검증에서 실제로
        # 잡혔다 (네 발 접촉력이 지금 0 인데 2 N 으로 기록됨).
        #
        # 그래서 이 열은 **하네스와 뜻이 다르다.** `probe_manifest.json` 의
        # `foot_contact_semantics` 에 그렇게 적는다.
        forces = contact_sensor.data.net_forces_w[:, foot_sensor_slots, :]
        foot_force = torch.linalg.vector_norm(forces, dim=-1)

        parts.append(foot_pos.reshape(num_envs, 12))
        parts.append(foot_force)

    parts.append(robot.data.joint_pos)
    parts.append(robot.data.joint_vel)
    parts.append(robot.data.applied_torque)
    parts.append(robot.data.joint_pos_target)

    parts.append(command_term.vel_command_b[:, :3])

    return torch.cat([p.reshape(num_envs, -1) for p in parts], dim=1)


def rows_from_buffer(block, dt, joint_names, ts_offset, start_xy, fwd_dir,
                     floor_z):
    """버퍼 한 판을 93열 줄 목록으로. `timeseries_rows()` 와 같은 열 이름이다."""
    def cut(sample, field):
        low, high = ts_offset[field]
        return sample[low:high]

    rows = []

    for index, sample in enumerate(block):
        px, py, pz = cut(sample, "pos")
        qw, qx, qy, qz = cut(sample, "quat")
        vx_b, vy_b, _vz_b = cut(sample, "vel_b")
        vx_w, vy_w, vz_w = cut(sample, "vel_w")
        wx_b, wy_b, wz_b = cut(sample, "ang_b")

        foot_pos = cut(sample, "foot_pos")
        foot_force = cut(sample, "foot_force")

        cmd_vx, cmd_vy, cmd_wz = cut(sample, "cmd")

        roll_deg, pitch_deg, yaw_deg = timeseries.euler_deg_from_quat(
            qw, qx, qy, qz
        )

        here = (px, py)

        # 명령과 실제의 평면 오차. 하네스의 `vel_err_mps` 와 같은 뜻이고,
        # 여기서는 명령이 스텝마다 달라 그 스텝의 명령으로 잰다.
        row = {
            "frame": index,
            "t_s": index * dt,

            "cmd_vx_mps": cmd_vx,
            "vx_mps": vx_b,
            "vy_mps": vy_b,
            "speed_mps": math.hypot(vx_b, vy_b),
            "vel_err_mps": math.hypot(vx_b - cmd_vx, vy_b - cmd_vy),

            "fwd_m": metrics.forward_offset_m(start_xy, here, fwd_dir),
            "lat_m": metrics.lateral_offset_m(start_xy, here, fwd_dir),

            "base_z_m": pz - floor_z,
            "pitch_deg": pitch_deg,
            "roll_deg": roll_deg,
            "yaw_deg": yaw_deg,

            "base_x_m": px,
            "base_y_m": py,
            "base_z_w_m": pz,

            "base_qw": qw,
            "base_qx": qx,
            "base_qy": qy,
            "base_qz": qz,
            "base_yaw_deg": yaw_deg,

            "base_vx_w_mps": vx_w,
            "base_vy_w_mps": vy_w,
            "base_vz_w_mps": vz_w,

            "base_wx_rps": wx_b,
            "base_wy_rps": wy_b,
            "base_wz_rps": wz_b,

            "cmd_vy_mps": cmd_vy,
            "cmd_wz_rps": cmd_wz,
        }

        for slot_index, slot in enumerate(timeseries.FOOT_SLOTS):
            fx, fy, fz = foot_pos[3 * slot_index: 3 * slot_index + 3]

            row["foot_x_{}_m".format(slot)] = timeseries.not_nan(fx)
            row["foot_y_{}_m".format(slot)] = timeseries.not_nan(fy)

            height = timeseries.not_nan(fz)

            row["foot_z_{}_m".format(slot)] = (
                None if height is None else height - floor_z
            )

            row["foot_contact_{}_n".format(slot)] = timeseries.not_nan(
                foot_force[slot_index]
            )

        for prefix in timeseries.JOINT_PREFIXES:
            values = cut(sample, prefix)

            for jname, value in zip(joint_names, values):
                row["{}_{}".format(prefix, jname)] = value

        rows.append(row)

    return rows


def finish_scenario(name, spec, label, buffer, n_valid, fell_at, dt, num_envs,
                    joint_names, ts_columns, ts_offset, start_xy, forward_dir,
                    floor_z):
    """parquet 을 쓰고 env 마다 지표를 뽑아 시나리오 요약을 만든다."""
    out_dir = os.path.join(args_cli.output_dir, name)
    ts_dir = os.path.join(out_dir, "timeseries")
    os.makedirs(ts_dir, exist_ok=True)

    start_cpu = start_xy.cpu().tolist()
    fwd_cpu = forward_dir.cpu().tolist()
    floor_cpu = floor_z.cpu().tolist()
    valid_cpu = n_valid.cpu().tolist()
    fell_cpu = fell_at.cpu().tolist()

    per_env = []

    # **표본이 모자란 env 도 세어 둔다.** 시계열 지표는 못 내지만 「몇 대 중
    # 몇 대가 넘어졌나」의 분모와 분자에는 반드시 남아야 한다. 첫 스텝에
    # 넘어진 env 가 바로 이 경우이고, 빼 버리면 **가장 심하게 실패한 판이
    # 낙상률에서 사라진다.** 검증에서 잡힌 자리다.
    degenerate = []

    for env_id in range(num_envs):
        n = valid_cpu[env_id]

        if n <= 1:
            fell_s = fell_cpu[env_id]

            print(f"[WARN] env {env_id} 는 표본이 {n} 개뿐입니다. 시계열은 "
                  f"안 남기고 낙상 집계에만 넣습니다 "
                  f"(낙상 {'예' if fell_s == fell_s else '아니오'}).",
                  flush=True)

            degenerate.append(
                cmd_metrics.degenerate_entry(n, dt, fell_s, env_id=env_id)
            )
            continue

        block = buffer[env_id, :n].cpu().tolist()

        rows = rows_from_buffer(
            block, dt, joint_names, ts_offset,
            tuple(start_cpu[env_id]), tuple(fwd_cpu[env_id]), floor_cpu[env_id],
        )

        path = os.path.join(ts_dir, timeseries.episode_filename(env_id + 1))

        timeseries.write(
            path,
            {
                "schema": timeseries.SCHEMA,
                "probe": "command_response",
                "scenario": name,
                "policy_label": label,
                "env_id": str(env_id),
                "dt_s": repr(dt),
                "fell_at_s": repr(fell_cpu[env_id]),
                "joint_names": ",".join(joint_names),
            },
            rows,
            ts_columns,
        )

        per_env.append(cmd_metrics.episode_metrics(
            rows, dt, joint_names, fell_cpu[env_id],
            contact_threshold_n=args_cli.contact_threshold_n,
            settle_speed_mps=args_cli.settle_speed_mps,
            env_id=env_id,
            timeseries_file=os.path.basename(path),
        ))

    result = cmd_metrics.aggregate(
        per_env, degenerate, name, spec["what"]
    )

    print_scenario_summary(name, result)

    with open(os.path.join(out_dir, "per_env.json"), "w",
              encoding="utf-8") as handle:
        # **env 번호순으로 적는다.** 정상 판과 표본 부족 판을 그냥 이어 붙이면
        # 순서가 뒤섞여 parquet 파일과 대응이 안 된다.
        everyone = sorted(per_env + degenerate,
                          key=lambda entry: entry["env_id"])
        json.dump(everyone, handle, ensure_ascii=False, indent=2)

    return result


def print_scenario_summary(name, result):
    if not result.get("envs"):
        print(f"[WARN] {name}: 표본이 없습니다.", flush=True)
        return

    print(f"\n  env {result['envs']} 대 · 낙상 {result['fell_count']} 대 "
          f"({result['fell_ratio'] * 100:.0f} %)")

    if result.get("stop_time_s") is not None:
        print(f"  정지 도달      : {result['stop_time_s']:.2f} s "
              f"({result['stop_reached_count']}/{result['envs']} 대)")
    elif name in ("stop", "hold"):
        print("  정지 도달      : **한 대도 못 멈췄습니다**")

    print(f"  잔류속도(끝 1초): {_fmt(result['residual_speed_mps'])} m/s")
    print(f"  관절목표각 변화 : 전체 {_fmt(result['joint_target_delta_mean'])}"
          f" · 끝 1초 {_fmt(result['joint_target_delta_tail'])} rad/스텝")
    print(f"  피치 최대       : {_fmt(result['pitch_abs_max_deg'])} 도")
    print(f"  롤 최대         : {_fmt(result['roll_abs_max_deg'])} 도")
    print(f"  발 미끄러짐     : {_fmt(result['foot_slip_m'])} m")
    print(f"  네 발 동시접지  : {_fmt(result['quad_stance_s'])} s")

    if result["response_curve"]:
        pairs = "  ".join(
            f"{k}->{_fmt(v)}" for k, v in result["response_curve"].items()
        )
        print(f"  응답곡선        : {pairs}")

    if result["yaw_follow_ratio"]:
        pairs = "  ".join(
            f"{k}:{_fmt(v)}" for k, v in result["yaw_follow_ratio"].items()
        )
        print(f"  요레이트 추종비 : {pairs}")

    print(flush=True)


def _fmt(value):
    return "없음" if value is None else f"{value:.4f}"


def write_manifest(label, names, summary, dt, num_envs, joint_names,
                   ts_columns):
    """무엇으로 어떻게 쟀는지. 이것이 없으면 숫자를 나중에 못 읽는다."""
    from datetime import datetime, timezone

    path = os.path.join(args_cli.output_dir, "probe_manifest.json")

    payload = {
        "probe": "command_response",
        "probe_file": os.path.basename(__file__),
        "policy_label": label,

        # G4. 하네스 `run_manifest.json` 에는 아직 이 칸이 없다 (#428).
        "policy_checkpoint": os.path.abspath(args_cli.checkpoint),
        "policy_sha256": metrics_file_sha256(args_cli.checkpoint),

        "base_task": BASE_TASK,
        "terrain": "plane (무한 평면)",
        "terrain_note": (
            "평지라 높이 스캔 광선이 안 빗나간다. height_scan 과 "
            "height_scan_with_gap 이 같은 값을 내므로 어느 쪽으로 학습한 "
            "정책이든 같은 관측을 본다"
        ),
        "num_envs": num_envs,
        "env_spacing_m": args_cli.env_spacing,
        "seed": args_cli.seed,
        "step_dt_s": dt,
        "joint_names": joint_names,
        "timeseries_schema": timeseries.SCHEMA,
        "timeseries_columns": len(ts_columns),
        "pushes_enabled": bool(args_cli.keep_pushes),
        "overwrote_previous_run": bool(args_cli.overwrite),

        # **이 열은 하네스와 뜻이 다르다.** 읽는 사람이 반드시 알아야 한다.
        "foot_contact_semantics": (
            "foot_contact_*_n 은 그 스텝의 «지금» 접촉력이다. "
            "eval_generalization.py 는 같은 이름의 열에 net_forces_w_history "
            "최댓값을 적는다. 그 이력 세 칸은 지금과 5 ms 전과 10 ms 전이다 "
            "(history_length=3 · update_period=sim.dt=0.005). 프로브는 «서 있는가» 를 "
            "재는 도구라 이력 최댓값을 쓰면 이미 뗀 발이 접지로 세어져 "
            "미끄러짐과 동시 접지 시간이 부푼다. 두 파일의 이 열을 "
            "그대로 견주지 마십시오"
        ),
        "contact_threshold_n": args_cli.contact_threshold_n,
        "settle_speed_mps": args_cli.settle_speed_mps,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),

        "scenarios": {
            name: {
                "what": SCENARIOS[name]["what"],
                "duration_s": SCENARIOS[name]["duration_s"],
            }
            for name in names
        },

        "summary": summary,

        "not_a_judgement": (
            "이 파일은 성공률을 내지 않는다. 판정은 "
            "eval_generalization.py 의 네 축 AND 하나다"
        ),
    }

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    print(f"\n[PASS] 요약을 적었습니다: {path}", flush=True)


if __name__ == "__main__":
    main()
