# -*- coding: utf-8 -*-
"""명령에 어떻게 반응하는가. **시간에 따라 변하는 명령**으로 정책을 흔들어 본다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-18
근거: `inbox/jay/20260918-v2-command-restore.md` 5-3 절 · `timeseries.py` 92열 스키마
요지: 정지 · 저속 · 회전을 재는 프로브. 판정 하네스를 한 줄도 안 건드린다
상태: 확정

## 왜 하네스 «안» 이 아니라 새 파일인가

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

**관절 목표각 변화량이 이 도구의 요점이다.** 지금 아무도 이것을 안 쟀다.

    변화량이 0 으로 수렴    정책 출력이 굳었다. 「얼음」이 정책 쪽이다
    변화량이 계속 큼        정책은 움직이는데 몸이 안 따라온다. 「얼음」이 몸 쪽이다

둘은 원인이 다르고 처방도 다르다. 한 열이 그것을 가른다.

## 기록은 92열 스키마 그대로

`timeseries.py` 의 `columns_for()` 를 그대로 쓴다. **두 벌을 만들지 않는다.**
`joint_target_*` 12열이 이미 있어서 새 열이 필요 없다 `확인됨`.

다른 것은 명령 세 열(`cmd_vx_mps` · `cmd_vy_mps` · `cmd_wz_rps`)에 **스텝마다
실제로 정책이 본 값**이 들어간다는 것뿐이다. 하네스는 거기에 상수를 적는다
(`eval_generalization.py` 1113~1116행). 열은 같고 내용이 다르다.

`verify_against_row()` 는 부르지 않는다. 그것은 판정 표의 «그 줄» 과 대조하는
함수인데 프로브에는 대응하는 판정 행이 없다. 없는 것을 있는 척하지 않는다.

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
from overlay import trace as trace_mod  # noqa: E402,F401


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

    각 3초씩 -1.0 · -0.5 · 0.0 · +0.5 · +1.0 이다. 앞뒤 1.5초는 가만히 두어
    직전 구간의 관성이 다음 구간에 안 섞이게 한다.
    """
    steps = (-1.0, -0.5, 0.0, 0.5, 1.0)

    if t < 1.5:
        return (0.0, 0.0, 0.0)

    index = int((t - 1.5) // 3.0)

    if index >= len(steps):
        return (0.0, 0.0, 0.0)

    return (0.0, 0.0, steps[index])


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
}


parser = argparse.ArgumentParser(
    description="명령 반응 프로브. 판정 하네스를 건드리지 않는다.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument("--checkpoint", type=str, required=True,
                    help="정책 체크포인트 `.pt`. rsl_rl 이 낸 것")
parser.add_argument("--label", type=str, default=None,
                    help="산출물에 적을 이름. 안 주면 체크포인트 파일 이름")
parser.add_argument("--scenario", type=str, default="all",
                    help="stop · ramp · turn · hold · all (쉼표로 여럿)")
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

AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# parquet 이 없으면 **시뮬을 띄우기 전에** 죽는다. 7분 돌고 끝에서 죽지 않게.
timeseries.require_pyarrow()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402,F401
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
             if args_cli.scenario != "all" else list(SCENARIOS))

    unknown = [n for n in names if n not in SCENARIOS]

    if unknown:
        raise RuntimeError(
            f"모르는 시나리오: {unknown}. 있는 것은 {list(SCENARIOS)} 입니다."
        )

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
            fell_at[newly] = t
            alive = alive & ~newly

        if not alive.any():
            print(f"        {t:.2f} s 에 전부 넘어졌습니다.", flush=True)
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

        forces = contact_sensor.data.net_forces_w_history[
            :, :, foot_sensor_slots, :
        ]
        foot_force = torch.linalg.vector_norm(forces, dim=-1).amax(dim=1)

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
    """버퍼 한 판을 92열 줄 목록으로. `timeseries_rows()` 와 같은 열 이름이다."""
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

    for env_id in range(num_envs):
        n = valid_cpu[env_id]

        if n <= 1:
            print(f"[WARN] env {env_id} 는 표본이 {n} 개뿐이라 건너뜁니다.",
                  flush=True)
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

        per_env.append(
            episode_metrics(rows, dt, joint_names, fell_cpu[env_id])
        )

    result = aggregate(per_env, name, spec)

    print_scenario_summary(name, result)

    with open(os.path.join(out_dir, "per_env.json"), "w",
              encoding="utf-8") as handle:
        json.dump(per_env, handle, ensure_ascii=False, indent=2)

    return result


def episode_metrics(rows, dt, joint_names, fell_at_s):
    """env 하나의 5-3 절 지표. **전부 92열에서 나온다.**"""
    n = len(rows)
    last_window = max(1, int(round(1.0 / dt)))

    cmd_vx = [r["cmd_vx_mps"] for r in rows]
    cmd_wz = [r["cmd_wz_rps"] for r in rows]
    vx = [r["vx_mps"] for r in rows]
    vy = [r["vy_mps"] for r in rows]
    wz = [r["base_wz_rps"] for r in rows]
    speed = [r["speed_mps"] for r in rows]

    # -- 관절 목표각의 시간 변화량. 이 도구의 요점.
    target_keys = ["joint_target_{}".format(j) for j in joint_names]
    target_delta = []

    for index in range(1, n):
        prev = rows[index - 1]
        here = rows[index]
        total = sum(abs(here[k] - prev[k]) for k in target_keys)
        target_delta.append(total)

    # -- 정지. 명령이 처음 0 이 된 뒤 언제 실제로 멈췄나.
    zero_from = next(
        (i for i, c in enumerate(cmd_vx)
         if abs(c) < 1.0e-9 and abs(cmd_wz[i]) < 1.0e-9),
        None,
    )

    stop_time_s = None

    if zero_from is not None:
        for index in range(zero_from, n):
            window = speed[index:index + last_window]

            if window and max(window) < args_cli.settle_speed_mps:
                stop_time_s = (index - zero_from) * dt
                break

    tail = slice(max(0, n - last_window), n)

    return {
        "samples": n,
        "duration_s": n * dt,
        "fell": fell_at_s == fell_at_s,          # NaN 이면 False
        "fell_at_s": None if fell_at_s != fell_at_s else fell_at_s,

        # G1
        "stop_time_s": stop_time_s,
        "residual_speed_mps": _mean(speed[tail]),
        "residual_vx_mps": _mean(vx[tail]),
        "residual_vy_mps": _mean(vy[tail]),

        # 「얼음」
        "joint_target_delta_mean": _mean(target_delta),
        "joint_target_delta_tail": _mean(target_delta[max(0, n - 1 - last_window):]),
        "joint_target_delta_max": max(target_delta) if target_delta else None,

        # 무게중심
        "pitch_abs_max_deg": max((abs(r["pitch_deg"]) for r in rows), default=None),
        "roll_abs_max_deg": max((abs(r["roll_deg"]) for r in rows), default=None),
        "base_z_min_m": min((r["base_z_m"] for r in rows), default=None),
        "base_z_tail_m": _mean([r["base_z_m"] for r in rows[tail]]),

        # G2 · G3
        "response": response_curve(cmd_vx, vx, dt),
        "yaw_follow": yaw_follow(cmd_wz, wz),

        # 멈춘 방식의 질
        "foot_slip_m": foot_slip(rows),
        "quad_stance_s": quad_stance_s(rows, dt),
    }


def _mean(values):
    clean = [v for v in values if v is not None and v == v]
    return sum(clean) / len(clean) if clean else None


def response_curve(cmd_vx, vx, dt):
    """명령 격자마다 «정상상태» 실속도. G2.

    램프는 명령이 계속 움직이므로 구간마다 뒤쪽 절반만 본다. 앞쪽 절반은
    직전 명령에서 넘어오는 과도구간이라 정상상태가 아니다.
    """
    grid = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.25, 1.5]
    out = {}

    for target in grid:
        picked = [v for c, v in zip(cmd_vx, vx) if abs(c - target) < 0.05]

        if len(picked) >= 2:
            out["{:.2f}".format(target)] = _mean(picked[len(picked) // 2:])

    return out


def yaw_follow(cmd_wz, wz):
    """요레이트 추종비. G3. 명령이 0 인 구간은 비를 만들 수 없어 뺀다."""
    out = {}

    for target in (-1.0, -0.5, 0.5, 1.0):
        picked = [w for c, w in zip(cmd_wz, wz) if abs(c - target) < 1.0e-6]

        if len(picked) >= 2:
            actual = _mean(picked[len(picked) // 2:])
            out["{:+.2f}".format(target)] = {
                "actual_rps": actual,
                "ratio": None if actual is None else actual / target,
            }

    return out


def foot_slip(rows):
    """접지 중인 발이 수평으로 움직인 거리 합 (m).

    발이 땅에 닿아 있는데 자리가 움직이면 미끄러진 것이다. 접촉력이 문턱을
    넘은 스텝만 세고, 발 열이 빈 칸이면 `None` 을 돌려준다.
    """
    total = 0.0
    counted = False

    for slot in timeseries.FOOT_SLOTS:
        fx_key = "foot_x_{}_m".format(slot)
        fy_key = "foot_y_{}_m".format(slot)
        fn_key = "foot_contact_{}_n".format(slot)

        for index in range(1, len(rows)):
            prev, here = rows[index - 1], rows[index]

            if None in (prev[fx_key], here[fx_key], prev[fn_key], here[fn_key]):
                continue

            if min(prev[fn_key], here[fn_key]) < args_cli.contact_threshold_n:
                continue

            total += math.hypot(here[fx_key] - prev[fx_key],
                                here[fy_key] - prev[fy_key])
            counted = True

    return total if counted else None


def quad_stance_s(rows, dt):
    """네 발이 동시에 닿아 있던 가장 긴 구간 (초).

    멈춘 방식의 질이다. 네 발로 버티고 서 있으면 길고, 계속 발을 바꿔 딛으면
    짧다. 「얼음」이면 아주 길게 나온다.
    """
    keys = ["foot_contact_{}_n".format(s) for s in timeseries.FOOT_SLOTS]

    longest = 0
    run = 0

    for row in rows:
        values = [row[k] for k in keys]

        if any(v is None for v in values):
            return None

        if min(values) >= args_cli.contact_threshold_n:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    return longest * dt


def aggregate(per_env, name, spec):
    """env 들을 하나로 접는다. 중앙값이 아니라 평균과 퍼짐을 함께 낸다."""
    if not per_env:
        return {"scenario": name, "what": spec["what"], "envs": 0}

    def across(key):
        return _mean([e[key] for e in per_env])

    fell = [e for e in per_env if e["fell"]]

    merged_response = {}

    for entry in per_env:
        for grid_key, value in entry["response"].items():
            merged_response.setdefault(grid_key, []).append(value)

    merged_yaw = {}

    for entry in per_env:
        for grid_key, value in entry["yaw_follow"].items():
            merged_yaw.setdefault(grid_key, []).append(value["ratio"])

    return {
        "scenario": name,
        "what": spec["what"],
        "envs": len(per_env),
        "fell_count": len(fell),
        "fell_ratio": len(fell) / len(per_env),

        "stop_time_s": _mean(
            [e["stop_time_s"] for e in per_env if e["stop_time_s"] is not None]
        ),
        "stop_reached_count": sum(
            1 for e in per_env if e["stop_time_s"] is not None
        ),

        "residual_speed_mps": across("residual_speed_mps"),
        "joint_target_delta_mean": across("joint_target_delta_mean"),
        "joint_target_delta_tail": across("joint_target_delta_tail"),
        "pitch_abs_max_deg": across("pitch_abs_max_deg"),
        "roll_abs_max_deg": across("roll_abs_max_deg"),
        "base_z_tail_m": across("base_z_tail_m"),
        "foot_slip_m": across("foot_slip_m"),
        "quad_stance_s": across("quad_stance_s"),

        "response_curve": {k: _mean(v) for k, v in sorted(merged_response.items())},
        "yaw_follow_ratio": {k: _mean(v) for k, v in sorted(merged_yaw.items())},
    }


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
