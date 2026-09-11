"""평가 하네스 활성본. Candidate 스냅샷에서 갈라져 나온 실행 본체.

원본: `provenance/candidate-20260822/eval_generalization.py`
그 파일은 손대지 않습니다. 여기만 고칩니다.

**판정 식은 전부 `metrics.py` 의 순수 함수를 부릅니다.** 이 파일은 시뮬레이터에서
값을 모으는 일만 합니다. `tests/` 가 `metrics.py` 를 스냅샷 원문과 대조합니다.

스냅샷과 다른 것 여섯 가지 (#125 4번 · #99 2번):

| 무엇 | 스냅샷 | 여기 |
|---|---|---|
| 판정·집계 | 본문에 인라인 | `metrics.py` 순수 함수 호출 |
| 원시 CSV | 19열 | 27열 (`ADDED_COLUMNS` 여덟) |
| 방향 판정 | 에피소드 **끝점** 이탈 | **통과선(`--min_progress_m`) 위** 이탈 |
| 지형 | 험지 10종 전부 | `--terrains` 로 고름 |
| env 생성 | 등록된 태스크 + hydra | 설정 클래스에서 직접 |
| 시간축 자료 | 없음 | `--timeseries` 로 에피소드마다 parquet (**기본 꺼짐**) |

**분석 열 셋을 더한 이유** (`traversal_success` · `gate_speed_mps` ·
`speed_drop_ratio`). 성공률 한 숫자로는 「왜 떨어졌나」를 못 묻는다.
못 넘은 에피소드와 넘었는데 느렸던 에피소드가 같은 0 이고, 관성으로 넘은
에피소드와 보폭을 조절해 넘은 에피소드가 같은 1 이다.

**셋 다 판정에 안 넣었다.** `overall_success` 는 그대로 네 축의 AND 다.
`traversal_success` 는 **이름에 `success` 가 들어가지만 성공률이 아니다.**
속도 추종을 뺀 세 축의 AND 이고, 문서 · 표 · 발표에 성공률로 적으면 안 된다.
식과 경고는 `metrics.traversal_success` 에 한 번 더 적혀 있다.

**시계열을 기본 꺼짐으로 둔 이유.** 켜면 에피소드마다 parquet 한 장이 더 나오고
스텝마다 GPU 버퍼가 하나 더 찬다. 지금까지의 실행이 전부 무거워지면 안 된다.
인자를 안 주면 CSV 도 실행 시간도 지금과 같다. 켜면 **성공한 에피소드도 함께**
남는다. 같은 난이도에서 넘은 것과 못 넘은 것을 겹쳐 보는 것이 이 자료의 쓰임새다.

**머리 접촉 열 셋을 더한 이유.** 실기 Go2 는 머리 앞면에 라이다가 있는데
(`docs/ROBOT-SPEC.md`) 종료 조건이 `body_names="base"` 하나라 **머리는 판정 밖이었다.**
「이 정책이 센서를 위험하게 쓰는가」를 실기 이식 전에 알려면 그 접촉이 기록돼야 한다.

**판정에는 안 넣었다.** `overall_success` 는 그대로 네 축의 AND 다. 근거 셋은
`docs/research/20260909-head-contact-observation.md` 에 적었다. 요지는 ① AND 에 축을
더하면 성공률이 반드시 깎이고 ② 「몇 N 부터 부서지는가」의 근거가 우리에게 없고
③ 종료 조건을 더하면 `termination_reason` 이 조용히 거짓말을 시작한다는 것이다.

**방향 판정을 옮긴 이유** (#99 2번). 멘토 기준은 「목표점에 도달했을 때 좌우
5 cm」입니다. 스냅샷은 에피소드가 끝나는 자리에서 쟀는데, 20초 x 1.0 m/s 면
끝점이 20 m 라 목표점 10 m 의 두 배 지점입니다. 그래서 **전진이 통과선을
지나는 순간**을 재고, 끝점 이탈과 최대 이탈은 관측 열로 함께 남깁니다.

**env 를 직접 만드는 이유.** 스냅샷은 RunPod 컨테이너 안에 등록돼 있던
`Isaac-Velocity-Unseen-Unitree-Go2-v0` 를 hydra 로 불렀습니다. 그 등록본을
회수하지 못했습니다 (`PROVENANCE.md` §2). 그래서 활성 설정
`generalization_env_cfg.py` 에서 곧바로 만듭니다. 정책 학습 설정(agent_cfg)만
NVIDIA 공식 rough 태스크의 등록본에서 가져옵니다. 체크포인트가 그것으로
학습됐기 때문입니다.

**지형 하나만 재는 이유.** 타일이 8 m 인데 기준이 10 m 라, 험지 10종은 앞 4 m 만
지형이고 뒤 6 m 는 평평한 테두리입니다. 그 상태로 낸 험지 수치는 지형 수치가
아닙니다. `PROVENANCE.md` §7 「8 m 타일과 10 m 기준이 안 맞는다」 참고.
`flat` 은 테두리도 평지라 영향이 없습니다.

**고르지 않은 지형도 물리적으로는 함께 돕니다.** 설정에서 빼면 지형 인덱스가
밀려 500판 기록과 대조가 끊깁니다. 그래서 11종을 그대로 굽고, 기록만 고릅니다.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

# ★ Windows 우회. Kit 를 띄우기 **전에** 네이티브 확장을 선점 import 한다.
#
# Kit 로드 뒤에 `rsl_rl.runners` 를 처음 import 하면 프로세스가 통째로 죽는다
# (`Windows fatal exception: access violation`, 2026-09-03 실측).
# Kit 가 자기 런타임을 먼저 물고 들어가서 같은 네이티브 심볼이 두 번 로드되기
# 때문이다. `C:\isaac\IsaacLab\eval_go2.py` 가 8/11 에 같은 자리에서 같은 우회를
# 적어 뒀다. 스냅샷은 Linux 컨테이너에서 돌아 이 문제를 겪지 않았다.
#
# **이 네 줄의 순서를 바꾸거나 아래로 내리지 마십시오.**
import torch  # noqa: F401,E402
from tensordict import TensorDict  # noqa: F401,E402
import rsl_rl.runners  # noqa: F401,E402

from isaaclab.app import AppLauncher

_HERE = os.path.dirname(os.path.abspath(__file__))

if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import metrics  # noqa: E402
import extras as csv_extras  # noqa: E402
import terrains  # noqa: E402
import timeseries  # noqa: E402

parser = argparse.ArgumentParser(
    description="Evaluate Go2 on the generalization terrain set (active harness)."
)
parser.add_argument("--checkpoint", type=str, required=True,
                    help="rsl_rl 체크포인트 .pt 경로")
parser.add_argument("--terrain_set", type=str, default="unseen10",
                    choices=["unseen10", "rough6"],
                    help="어느 지형 집합을 굽나. `unseen10` 은 정책이 못 본 험지 10종, "
                         "`rough6` 은 체크포인트가 학습에 쓴 험지 6종")
parser.add_argument("--terrains", type=str, default="flat",
                    help="기록할 지형. 쉼표로 여럿. 'all' 이면 전부")
parser.add_argument("--difficulty", type=float, default=None,
                    help="지형 난이도 하나(0 초과 1 이하). 주면 "
                         "`difficulty_range` 를 (d, d) 로 덮어써 타일 전부가 "
                         "정확히 이 난이도가 된다. 안 주면 설정 파일 값을 "
                         "그대로 쓴다(스냅샷과 같은 동작)")
parser.add_argument("--rail_thickness", type=float, default=None,
                    help="`rails` 의 턱 두께(m)를 하나로 못 박는다. 안 주면 설정 "
                         "그대로 (0.08, 0.18) 무작위다. **난이도가 두께를 안 "
                         "건드리므로** 같은 난이도 칸 안에서도 두꺼운 판과 얇은 "
                         "판이 섞인다. 축을 하나로 만들 때만 쓴다. `unseen10` 전용")
parser.add_argument("--episodes", type=int, default=100,
                    help="기록할 지형 하나당 총 에피소드 수")
parser.add_argument("--envs_per_terrain", type=int, default=10,
                    help="지형 하나에 붙일 env 수. 전체 env = 이 값 x 지형 수")
parser.add_argument("--eval_duration", type=float, default=20.0,
                    help="에피소드 제한 시간(초)")
parser.add_argument("--command_vx", type=float, default=1.0,
                    help="고정 전진 명령(m/s)")
parser.add_argument("--min_progress_m", type=float, default=10.0,
                    help="통과로 치는 최소 전진 거리(m)")
parser.add_argument("--max_velocity_mae", type=float, default=0.25,
                    help="속도 추종 판정 문턱(m/s)")
# **규격 2 가 기본값이다** (2026-09-11 전환). 빗나간 광선을 학습과 같은 +1 로 읽는다.
#   왜: 구멍 위에서 광선이 아무것도 못 맞히는데, 옛 기본 함수는 그 자리를 -1 로
#   잘랐다. 이 눈금에서 -1 은 «내 몸통보다 높이 솟은 것», 곧 벽이다. 구멍을
#   장애물이라고 알려 주고 있었다. 실측: gap 1/28/100 (옛 규격 0/0/6).
parser.add_argument("--gap_aware_scan", action="store_true",
                    help="(지금은 기본값이라 아무 일도 안 한다. 옛 명령과의 호환용)")
parser.add_argument("--legacy_miss_scan", action="store_true",
                    help="**결함 규격 1** 로 되돌린다. 빗나간 광선을 -1(벽)로 읽는다. manifest 에 eval_spec_version=1 이 찍힌 결과를 재현할 때만 쓴다.")
parser.add_argument("--max_lateral_drift", type=float, default=0.05,
                    help="통과선 위 좌우 이탈 판정 문턱(m). 멘토 기준 5 cm")
parser.add_argument("--head_contact_threshold_n", type=float, default=1.0,
                    help="머리 접촉으로 세는 힘 문턱(N). **판정에 안 쓴다.** "
                         "기본 1.0 은 몸통 종료 조건과 같은 자다")
parser.add_argument("--output_dir", type=str, required=True)
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--spawn_xy_range", type=float, default=0.10,
                    help="초기 x/y 흔들기(m)")
parser.add_argument("--yaw_range_deg", type=float, default=5.0,
                    help="초기 방위 흔들기(도)")
parser.add_argument("--joint_pos_scale", type=float, default=0.05,
                    help="초기 관절 위치 흔들기 비율")
parser.add_argument("--note", type=str, default="",
                    help="조건 기록에 남길 한 줄")

# ---------------------------------------------------------------- 시계열 (기본 꺼짐)
#
# **기본이 꺼짐인 이유.** 켜면 에피소드마다 parquet 한 장이 더 나오고 스텝마다
# GPU 버퍼가 하나 더 찬다. 지금까지의 실행이 전부 무거워지면 안 된다.
# 인자를 안 주면 아래 코드는 한 줄도 돌지 않고 CSV 도 지금과 같다.
parser.add_argument("--timeseries", action="store_true",
                    help="에피소드마다 시간축 원자료를 parquet 으로 남긴다. "
                         "`<output_dir>/timeseries/ep0001.parquet` 부터 "
                         "**raw CSV 의 줄 순서대로** 번호가 붙는다. "
                         "성공한 에피소드도 함께 남는다. `pyarrow` 가 필요하다")

AppLauncher.add_app_launcher_args(parser)

args_cli, _ = parser.parse_known_args()

# ★ Kit 를 띄우기 **전에** 판다. 없는 채로 시작하면 에피소드를 다 돌고 첫 파일을
#   쓰는 자리에서 죽는다. 7분을 버리지 않으려고 여기서 본다.
if args_cli.timeseries:
    timeseries.require_pyarrow()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# ---------------------------------------------------------------- Kit 기동 후

from rsl_rl.runners import OnPolicyRunner  # noqa: E402

from isaaclab.envs import ManagerBasedRLEnv  # noqa: E402
from isaaclab.utils.assets import retrieve_file_path  # noqa: E402
from isaaclab.utils.math import quat_apply  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

import isaaclab_tasks  # noqa: F401,E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import importlib  # noqa: E402

# 체크포인트를 학습시킨 NVIDIA 공식 태스크. agent_cfg 만 여기서 가져온다.
POLICY_TASK = "Isaac-Velocity-Rough-Unitree-Go2-v0"

# 지형 집합을 `--terrain_set` 으로 고른다. 설정 모듈은 **고른 것만** 임포트한다.
# 둘 다 임포트하면 안 쓰는 쪽의 설정까지 만들어져 애먼 곳에서 죽을 수 있다.
_SET_NAMES, _SET_MODULE, _SET_CLASS = terrains.terrain_set(args_cli.terrain_set)

TERRAIN_NAMES = list(_SET_NAMES)

ENV_CFG_CLASS = getattr(importlib.import_module(_SET_MODULE), _SET_CLASS)


def configure_evaluation(env_cfg, agent_cfg, envs_per_terrain):
    """스냅샷 `configure_evaluation` 과 같은 자리. 인자 이름과 값만 CLI 로 뺐다."""
    env_cfg.seed = args_cli.seed
    agent_cfg.seed = args_cli.seed

    env_cfg.scene.num_envs = envs_per_terrain * len(TERRAIN_NAMES)

    terrain_gen = env_cfg.scene.terrain.terrain_generator

    if terrain_gen is None:
        raise RuntimeError("Benchmark task does not use a TerrainGenerator.")

    terrain_gen.seed = args_cli.seed
    terrain_gen.curriculum = True

    if terrain_gen.num_cols != len(TERRAIN_NAMES):
        raise RuntimeError(
            f"Expected {len(TERRAIN_NAMES)} terrain columns, "
            f"but config has {terrain_gen.num_cols}."
        )

    env_cfg.scene.terrain.max_init_terrain_level = 0

    if hasattr(env_cfg.curriculum, "terrain_levels"):
        env_cfg.curriculum.terrain_levels = None

    env_cfg.episode_length_s = args_cli.eval_duration

    cmd = env_cfg.commands.base_velocity

    cmd.ranges.lin_vel_x = (args_cli.command_vx, args_cli.command_vx)
    cmd.ranges.lin_vel_y = (0.0, 0.0)
    cmd.ranges.ang_vel_z = (0.0, 0.0)

    cmd.heading_command = False
    cmd.rel_heading_envs = 0.0
    cmd.rel_standing_envs = 0.0

    env_cfg.observations.policy.enable_corruption = False

    # 빗나간 광선을 어떻게 읽을지. 규격을 바꾸는 팔이라 manifest 에 반드시 남긴다.
    # 규격 2 가 기본. --legacy_miss_scan 을 줄 때만 옛 동작으로 돌아간다.
    globals()["_MISS_VALUE"] = None
    globals()["_SPEC_VERSION"] = 1 if args_cli.legacy_miss_scan else 2
    if not args_cli.legacy_miss_scan:
        # _SET_MODULE 은 모듈 «이름» 이다 (194행). 객체로 바꿔 부른다.
        globals()["_MISS_VALUE"] = importlib.import_module(
            _SET_MODULE).apply_gap_aware_scan(env_cfg)

    for event in ("push_robot", "base_external_force_torque", "add_base_mass", "base_com"):
        if hasattr(env_cfg.events, event):
            setattr(env_cfg.events, event, None)

    spawn_range = args_cli.spawn_xy_range
    yaw_range_rad = math.radians(args_cli.yaw_range_deg)
    joint_scale = args_cli.joint_pos_scale

    if getattr(env_cfg.events, "reset_base", None) is not None:
        env_cfg.events.reset_base.params["pose_range"] = {
            "x": (-spawn_range, spawn_range),
            "y": (-spawn_range, spawn_range),
            "yaw": (-yaw_range_rad, yaw_range_rad),
        }

        env_cfg.events.reset_base.params["velocity_range"] = {
            "x": (0.0, 0.0),
            "y": (0.0, 0.0),
            "z": (0.0, 0.0),
            "roll": (0.0, 0.0),
            "pitch": (0.0, 0.0),
            "yaw": (0.0, 0.0),
        }

    if getattr(env_cfg.events, "reset_robot_joints", None) is not None:
        env_cfg.events.reset_robot_joints.params["position_range"] = (
            1.0 - joint_scale,
            1.0 + joint_scale,
        )
        env_cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)


def initial_forward_vectors(robot, num_envs, device):
    """스냅샷 그대로. 시작 자세의 전방축 단위벡터."""
    local_x = torch.zeros((num_envs, 3), device=device)
    local_x[:, 0] = 1.0

    forward_w = quat_apply(robot.data.root_quat_w, local_x)
    forward_xy = forward_w[:, :2]

    forward_xy = forward_xy / torch.linalg.vector_norm(
        forward_xy, dim=1, keepdim=True
    ).clamp_min(1.0e-8)

    return forward_xy


def verify_mapping(raw_env, envs_per_terrain):
    """env 가 어느 지형에 앉았는지 되읽어 확인한다. 스냅샷 `print_and_verify_mapping`.

    스냅샷은 env 하나에 지형 하나라 `terrain_type == env_id` 를 봤습니다.
    여기는 지형당 env 가 여럿이라 `env_id // envs_per_terrain` 을 봅니다.
    Isaac Lab 이 `terrain_types = floor(arange(N) / (N / num_cols))` 로 배정합니다
    (`terrain_importer.py` 348행).
    """
    terrain = raw_env.scene.terrain
    cfg_names = list(raw_env.cfg.scene.terrain.terrain_generator.sub_terrains.keys())

    print("\n" + "=" * 80)
    print("ENV -> TERRAIN MAPPING")
    print("=" * 80)

    if cfg_names != TERRAIN_NAMES:
        print("Configured terrain order:")
        print(cfg_names)
        print("Expected terrain order:")
        print(TERRAIN_NAMES)
        raise RuntimeError(
            "sub_terrains dictionary order does not match benchmark definition."
        )

    types = terrain.terrain_types.detach().cpu().tolist()
    levels = terrain.terrain_levels.detach().cpu().tolist()
    origins = terrain.env_origins.detach().cpu().tolist()

    for env_id in range(raw_env.num_envs):
        terrain_type = int(types[env_id])
        expected = env_id // envs_per_terrain

        if terrain_type != expected:
            raise RuntimeError(
                f"Mapping mismatch: env {env_id} -> terrain_type {terrain_type}, "
                f"expected {expected}"
            )

        if env_id % envs_per_terrain == 0:
            print(
                f"env {env_id:03d}"
                f" | terrain_type={terrain_type:2d}"
                f" | level={int(levels[env_id])}"
                f" | terrain={TERRAIN_NAMES[terrain_type]:<22}"
                f" | origin=({origins[env_id][0]:7.2f},"
                f" {origins[env_id][1]:7.2f},"
                f" {origins[env_id][2]:6.2f})"
            )

    print("\n[PASS] env-to-terrain mapping is deterministic and correct.")


def verify_commands(raw_env, command_vx):
    """명령이 정말 고정됐는지 되읽는다. 스냅샷 그대로."""
    command = raw_env.command_manager.get_command("base_velocity")

    expected = torch.zeros_like(command)
    expected[:, 0] = command_vx

    max_error = torch.max(torch.abs(command - expected)).item()

    print("\n" + "=" * 80)
    print("COMMAND VERIFICATION")
    print("=" * 80)
    print(f"env 000 | vx={command[0, 0].item(): .3f}"
          f" | vy={command[0, 1].item(): .3f}"
          f" | wz={command[0, 2].item(): .3f}")
    print(f"max deviation from ({command_vx}, 0, 0) = {max_error:.3e}")

    if max_error > 1.0e-6:
        raise RuntimeError(
            f"Commands are not fixed as expected. max error={max_error}"
        )

    print("\n[PASS] all robots receive the same velocity command.")


def resolve_head_bodies(raw_env):
    """접촉 센서에서 머리 링크의 번호를 뽑고, 못 찾으면 **죽는다.**

    **이 함수가 있는 이유가 이것이다.** 이름이 틀리면 힘을 하나도 못 읽는데
    오류는 안 난다. 그러면 `head_contact_count` 가 판마다 0 으로 채워지고,
    CSV 는 「머리가 한 번도 안 닿았다」고 **또박또박 거짓말을 한다.**
    종료코드도 0 이고 파일도 정상이라 아무도 못 알아챈다.

    그래서 여기서 세 가지를 세어 보고 하나라도 어긋나면 `RuntimeError` 다.

    | 무엇 | 왜 |
    |---|---|
    | 센서가 있나 | 없으면 접촉을 아예 못 읽는다 |
    | 이름이 둘 다 잡히나 | USD 가 바뀌어 이름이 달라졌을 수 있다 |
    | 센서가 몸 전체를 보나 | `prim_path` 가 좁혀졌으면 머리가 목록 밖이다 |

    `contact_forces` 는 `ContactSensorCfg(prim_path=".../Robot/.*")` 라 강체 19개를
    전부 본다 (`velocity_env_cfg.py:74`). 즉 머리도 이미 센서 안에 있다.
    종료 조건만 `body_names="base"` 로 좁혀 볼 뿐이다.
    """
    sensor = raw_env.scene.sensors.get("contact_forces")

    if sensor is None:
        raise RuntimeError(
            "접촉 센서 `contact_forces` 가 씬에 없습니다. 머리 접촉을 잴 수 없습니다.\n"
            f"  있는 센서: {list(raw_env.scene.sensors.keys())}"
        )

    available = list(sensor.body_names)

    # **이름 확인을 `find_bodies` 보다 먼저 한다.** 순서를 바꾸면 안 된다.
    #
    # `find_bodies` 는 못 찾으면 자기가 `ValueError` 를 던지고 죽는다
    # (`string.py:267`). 그러면 이 아래 메시지가 **영영 안 보인다.**
    # 2026-09-09 에 일부러 틀린 이름을 넣어 확인했고, 그때 나온 것은 IsaacLab 의
    # 정규식 오류였다. 틀렸다는 것은 알려 주지만 「프로브를 다시 돌려라」는
    # 안 알려 준다. 그 한 줄이 다음 사람의 30분이다.
    missing = [n for n in metrics.HEAD_BODY_NAMES if n not in available]

    if missing:
        raise RuntimeError(
            "머리 링크를 접촉 센서에서 못 찾았습니다. 이대로 두면 접촉 열이\n"
            "전부 0 으로 채워지고 CSV 가 조용히 거짓말을 합니다.\n"
            f"  찾는 이름 : {list(metrics.HEAD_BODY_NAMES)}\n"
            f"  못 찾음   : {missing}\n"
            f"  센서 목록 : {available}\n"
            "USD 가 바뀌었으면 `sim/eval/probe_go2_bodies.py` 를 다시 돌려\n"
            "`metrics.HEAD_BODY_NAMES` 를 고치십시오."
        )

    ids, names = sensor.find_bodies(list(metrics.HEAD_BODY_NAMES), preserve_order=True)

    print("\n" + "=" * 80)
    print("HEAD CONTACT SENSOR (관측 전용 · 판정에 안 들어감)")
    print("=" * 80)
    print(f"센서 강체 수 : {len(available)}")
    print(f"머리 링크    : {names}  -> 번호 {ids}")
    print(f"힘 문턱      : {args_cli.head_contact_threshold_n:.3f} N")
    print("\n[PASS] 머리 링크를 접촉 센서에서 찾았습니다.")

    return ids


def resolve_obstacle_zones(terrain_cfg, recorded):
    """지형마다 장애물 구간 `(시작 m, 끝 m)` 을 **설정에서 계산한다.**

    `speed_drop_ratio` 가 이 구간 안에서 최저 속도를 집습니다. 식과 근거는
    `terrains.obstacle_zone_m` 에 있습니다. **지형 이름으로 숫자를 박아 두지
    않습니다.** 설정 종류와 그 안의 값에서 계산하므로 `--difficulty` 를 바꾸면
    구간도 함께 움직입니다.

    난이도는 `difficulty_range` 의 **가운데 값**을 씁니다. 이 설정은
    `num_rows == 1` 이고 하네스가 `--difficulty d` 를 받으면 범위를 `(d, d)` 로
    덮어쓰므로, 그때는 타일의 실제 난이도와 **정확히 같습니다.** 범위가 넓으면
    타일마다 다르고 이 값은 대표값 하나입니다 `미확인`.
    """
    low, high = terrain_cfg.difficulty_range
    difficulty = (low + high) / 2.0

    zones = {}

    print("\n" + "=" * 80)
    print("OBSTACLE ZONE (speed_drop_ratio 를 재는 구간 · 설정에서 계산)")
    print("=" * 80)
    print(f"difficulty (대표값) : {difficulty:.3f}    "
          f"타일 {terrain_cfg.size[0]:.2f} m")
    print(f"{'terrain':<22} {'시작 m':>8} {'끝 m':>8}   근거")

    for name in recorded:
        sub_cfg = terrain_cfg.sub_terrains[name]

        zone = terrains.obstacle_zone_m(sub_cfg, difficulty, terrain_cfg.size[0])

        start, end, basis = zone
        zones[name] = (start, end)

        print(f"{name:<22} {start:8.3f} {end:8.3f}   {basis}")

    print("\n[PASS] 지형 {}종의 장애물 구간을 설정에서 계산했습니다.".format(len(zones)))

    return zones


def resolve_contact_parts(contact_sensor):
    """접촉 센서의 강체를 발·허벅지·종아리·몸통 넷으로 가른다.

    **새 센서를 안 붙인다.** `contact_forces` 는 `prim_path=".../Robot/.*"` 라
    이미 강체 19개를 전부 덮고 있다 `확인됨` (2026-09-11 · 이름 목록을 직접
    읽어 확인했다). CSV 설계서가 「허벅지·종아리는 센서를 붙여야 함」이라
    적은 것은 그 사실을 모르고 쓴 것이다.

    Returns:
        `{부위: [강체 번호]}`. 한 부위라도 비면 **죽는다.** 빈 채로 두면
        그 열이 전부 0 이 되고 「한 번도 안 닿았다」로 읽힌다 (원칙 2).
    """
    names = list(contact_sensor.body_names)
    parts = {"foot": [], "thigh": [], "calf": [], "base": []}

    for index, name in enumerate(names):
        low = name.lower()

        if low.endswith("_foot"):
            parts["foot"].append(index)
        elif "thigh" in low:
            parts["thigh"].append(index)
        elif "calf" in low:
            parts["calf"].append(index)
        elif low in ("base", "trunk") or "head" in low:
            # 몸통과 머리를 한 묶음으로 본다. 판정 종료 조건이 보는 자리와 같다.
            parts["base"].append(index)

    empty = [k for k, v in parts.items() if not v]

    if empty:
        raise RuntimeError(
            "접촉 부위 %s 에 해당하는 강체를 못 찾았습니다. 센서 강체 이름: %s"
            % (empty, names))

    print("[PASS] 접촉 부위 · " + " · ".join(
        "%s %d개" % (k, len(v)) for k, v in parts.items()), flush=True)

    return parts


def resolve_foot_bodies(robot, contact_sensor):
    """발 넷의 강체 번호를 **두 곳에서** 집는다. 못 집으면 `(None, None)`.

    번호 공간이 둘이라 따로 집어야 합니다. `body_pos_w` 는 **관절체**의 번호를
    쓰고 `net_forces_w` 는 **접촉 센서**의 번호를 씁니다. 같은 발이라도 두 번호가
    다를 수 있고, 섞어 쓰면 오류 없이 엉뚱한 강체를 읽습니다.

    못 집으면 죽지 않고 발 열을 **빈 칸**으로 남깁니다. 발 높이는 관측이지
    판정이 아니고, 이것 때문에 평가 전체가 서면 안 됩니다. 대신 소리는 냅니다.
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

    print(f"[PASS] 발 강체: 관절체 {body_slots} · 접촉 센서 {sensor_slots}"
          f"  ({' · '.join(timeseries.FOOT_SLOTS).upper()} 순서)", flush=True)

    return (body_slots, sensor_slots)


def episode_targets(recorded_terrains, envs_per_terrain, episodes, device):
    """env 별 목표 에피소드 수. 기록하지 않는 지형은 0 이라 처음부터 비활성이다.

    지형 하나에 env 가 여럿이므로 총 `episodes` 판을 그 env 들에 고르게 나눕니다.
    나머지는 앞쪽 env 부터 한 판씩 더 받습니다. 합은 정확히 `episodes` 입니다.
    """
    num_envs = envs_per_terrain * len(TERRAIN_NAMES)
    targets = torch.zeros(num_envs, dtype=torch.long, device=device)

    base, extra = divmod(episodes, envs_per_terrain)

    for name in recorded_terrains:
        first = TERRAIN_NAMES.index(name) * envs_per_terrain

        for k in range(envs_per_terrain):
            targets[first + k] = base + (1 if k < extra else 0)

    return targets


def save_csv(rows, summary_rows, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    raw_path = os.path.join(output_dir, "generalization_raw.csv")
    summary_path = os.path.join(output_dir, "generalization_summary.csv")

    with open(raw_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.RAW_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics.SUMMARY_COLUMNS))
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\n" + "=" * 80)
    print("RESULT FILES")
    print("=" * 80)
    print(raw_path)
    # 파일로 보내면 stdout 이 블록 버퍼이고 Kit 는 종료할 때 안 비운다.
    # 그래서 이 줄들이 로그에서 조용히 사라져 있었다 (2026-09-10 발견).
    print(summary_path, flush=True)

    return raw_path, summary_path


def file_sha256(path):
    """파일 지문. 정책이 정말 그 파일이었는지 나중에 대조하는 자리."""
    digest = hashlib.sha256()

    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def environment_record():
    """무엇 위에서 돌았는가. 하나가 없어도 실행을 죽이지 않는다.

    7분짜리 실행이 조건 기록 한 줄 때문에 끝에서 터지면 안 됩니다.
    못 읽은 항목은 문자열로 사유를 남깁니다.
    """
    record = {}

    def attempt(key, fn):
        try:
            record[key] = fn()
        except Exception as error:  # noqa: BLE001
            record[key] = f"<못 읽음: {error}>"

    attempt("python_version", lambda: platform.python_version())
    attempt("platform", lambda: platform.platform())
    attempt("hostname", lambda: platform.node())
    attempt("torch_version", lambda: torch.__version__)
    attempt("cuda_version", lambda: torch.version.cuda)

    attempt("gpu_names", lambda: [
        torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())
    ])

    attempt("isaaclab_version", lambda: __import__("isaaclab").__version__)
    attempt("rsl_rl_version", lambda: importlib.metadata.version("rsl-rl-lib"))

    def isaaclab_commit():
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(__import__("isaaclab").__file__)
        )))

        return subprocess.check_output(
            ["git", "-C", root, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()

    attempt("isaaclab_commit", isaaclab_commit)

    def repo_commit():
        return subprocess.check_output(
            ["git", "-C", _HERE, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()

    attempt("repo_commit", repo_commit)

    return record


def save_run_manifest(output_dir, extra):
    """무엇으로 어떻게 쟀는지. 사람이 읽는 조건 기록은 이것을 근거로 쓴다."""
    path = os.path.join(output_dir, "run_manifest.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(extra, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(path, flush=True)

    return path


def main():
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if args_cli.terrains.strip().lower() == "all":
        recorded = list(TERRAIN_NAMES)
    else:
        recorded = [t.strip() for t in args_cli.terrains.split(",") if t.strip()]

    unknown = [t for t in recorded if t not in TERRAIN_NAMES]

    if unknown:
        raise ValueError(f"Unknown terrain(s): {unknown}. Known: {TERRAIN_NAMES}")

    envs_per_terrain = args_cli.envs_per_terrain

    env_cfg = ENV_CFG_CLASS()
    agent_cfg = load_cfg_from_registry(POLICY_TASK, "rsl_rl_cfg_entry_point")

    configure_evaluation(env_cfg, agent_cfg, envs_per_terrain)

    # 난이도 하나로 못 박기 (#125 3번의 난이도 격자를 «한 판 한 난이도» 로 쓴다).
    #
    # 설정 파일의 `difficulty_range` 는 (0.5, 0.5) 그대로 둔다. 여기서만 덮어쓴다.
    # 그래야 인자를 안 준 실행이 지금까지와 **글자 그대로 같은 값**을 내고,
    # `tests/test_terrains.py` 의 「이 커밋에서 난이도를 안 건드린다」도 계속 산다.
    #
    # **왜 (d, d) 인가.** 이 설정은 `curriculum=True` · `num_rows=1` 이고,
    # Isaac Lab 은 난이도를 이렇게 만든다 (`terrain_generator.py:260-262`) `확인됨`:
    #
    #     difficulty = (sub_row + U(0,1)) / num_rows
    #     difficulty = lower + (upper - lower) x difficulty
    #
    # `lower == upper == d` 면 둘째 줄이 d 로 떨어진다. 난수는 그대로 소비되므로
    # 난이도만 다르고 난수 소비는 같다. 스윕의 칸끼리 비교가 되는 근거가 이것이다.
    if args_cli.difficulty is not None:
        if not 0.0 < args_cli.difficulty <= 1.0:
            raise ValueError(
                f"--difficulty 는 0 초과 1 이하여야 합니다. 받은 값: {args_cli.difficulty}"
            )

        env_cfg.scene.terrain.terrain_generator.difficulty_range = (
            args_cli.difficulty,
            args_cli.difficulty,
        )

    # `rails` 턱 두께 못 박기.
    #
    # **왜 필요한가.** `rail_thickness_range=(0.08, 0.18)` 은 난이도가 안 건드리는
    # 자리다 (`mesh_terrains.py` 의 `rails_terrain` 은 `rail_height` 만 보간한다).
    # 그래서 난이도를 고정해도 두께는 판마다 무작위로 뽑히고, 그 편차가 성공률에
    # 그대로 섞여 들어간다. 벽 구간을 촘촘히 잴 때는 축이 하나여야 한다.
    #
    # **이 인자를 준 실행은 기존 판과 조건이 다르다.** 나란히 놓지 말 것.
    # manifest 의 `rail_thickness_fixed_m` 가 그 표시다.
    if args_cli.rail_thickness is not None:
        if args_cli.terrain_set != "unseen10":
            raise ValueError(
                f"--rail_thickness 는 `unseen10` 전용입니다. "
                f"받은 집합: {args_cli.terrain_set}"
            )

        rails_cfg = env_cfg.scene.terrain.terrain_generator.sub_terrains.get("rails")

        if rails_cfg is None:
            raise RuntimeError(
                "`rails` 하위 지형을 못 찾았습니다. 두께를 못 박을 자리가 없습니다."
            )

        rails_cfg.rail_thickness_range = (
            args_cli.rail_thickness,
            args_cli.rail_thickness,
        )

    # 덮어쓴 뒤 **되읽어서** 찍는다. 인자를 그대로 찍으면 덮어쓰기가 안 먹어도 같은 줄이 나온다.
    print("\n" + "=" * 80)
    print("TERRAIN DIFFICULTY")
    print("=" * 80)
    print(f"difficulty_range : {env_cfg.scene.terrain.terrain_generator.difficulty_range}"
          f"  (덮어씀: {args_cli.difficulty is not None})")

    _rails = env_cfg.scene.terrain.terrain_generator.sub_terrains.get("rails")

    if _rails is not None:
        print(f"rail_thickness   : {_rails.rail_thickness_range}"
              f"  (덮어씀: {args_cli.rail_thickness is not None})")

    if getattr(args_cli, "device", None) is not None:
        env_cfg.sim.device = args_cli.device
        agent_cfg.device = args_cli.device

    raw_env = ManagerBasedRLEnv(cfg=env_cfg)

    verify_mapping(raw_env, envs_per_terrain)

    # 머리 링크를 못 찾으면 **여기서 죽는다.** 7분을 다 돌고 0 으로 찬 CSV 를
    # 받는 것보다 낫다.
    head_body_ids = resolve_head_bodies(raw_env)

    raw_env.reset()

    verify_commands(raw_env, args_cli.command_vx)

    env = RslRlVecEnvWrapper(raw_env, clip_actions=agent_cfg.clip_actions)

    resume_path = retrieve_file_path(args_cli.checkpoint)

    print("\n[INFO] Loading checkpoint:")
    print(resume_path)

    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(resume_path)

    policy = runner.get_inference_policy(device=raw_env.device)
    policy_nn = runner.alg.policy

    obs = env.get_observations()

    verify_commands(raw_env, args_cli.command_vx)

    num_envs = raw_env.num_envs
    device = raw_env.device
    dt = raw_env.step_dt

    # 판정 기준값. `min_progress_m` 은 비율이 아니라 미터로 직접 받는다.
    #
    # 스냅샷은 `min_progress = min_progress_ratio x command_vx x eval_duration` 이었다.
    # 1.0 m/s x 20 s = 20 m 라 10 m 기준은 비율 0.5 다. 비율로 적으면 「0.5 가 무슨
    # 뜻인가」를 매번 되짚어야 해서 미터로 받고, 비율은 그 자리에서 되계산해 남긴다.
    ideal_distance = metrics.ideal_distance_m(args_cli.command_vx, args_cli.eval_duration)
    min_progress = args_cli.min_progress_m
    min_progress_ratio = min_progress / ideal_distance if ideal_distance > 0.0 else 0.0

    # 세계가 이상 거리를 담는가. 담지 못하면 그 판은 정책이 아니라 **낙하**를 잰다.
    #
    # 2026-09-03 에 이것을 안 보고 20초를 돌려 로봇이 14.1 m 에서 지형 밖으로
    # 나갔다 (`results/20260903-flat-10m/README.md` §5-2). 그때는 사람이 표를
    # 보고 알아챘다. 여기서 먼저 걸리게 둔다.
    terrain_cfg = env_cfg.scene.terrain.terrain_generator

    terrain_border_width = terrain_cfg.border_width
    forward_extent = terrain_cfg.num_rows * terrain_cfg.size[0] / 2.0 + terrain_border_width

    if forward_extent < ideal_distance:
        raise RuntimeError(
            f"""지형이 이 시간을 담지 못합니다. 그대로 돌리면 로봇이 세계 밖으로 나가고,
그 판은 정책 성능이 아니라 낙하를 재게 됩니다.
  전방 한계   : {forward_extent:.2f} m  (= num_rows({terrain_cfg.num_rows})
                x size[0]({terrain_cfg.size[0]}) / 2 + border_width({terrain_border_width}))
  필요한 거리 : {ideal_distance:.2f} m  (= command_vx({args_cli.command_vx})
                x eval_duration({args_cli.eval_duration}))
시간을 줄이지 말고 `generalization_env_cfg.py` 의 `border_width` 를 키우십시오.
테두리는 격자 바깥이라 험지 10종의 타일도 env_origin 도 안 움직입니다."""
        )

    targets = episode_targets(recorded, envs_per_terrain, args_cli.episodes, device)
    total_target = int(targets.sum().item())

    max_steps = int(round(args_cli.eval_duration / dt)) + 2

    episode_counts = torch.zeros(num_envs, dtype=torch.long, device=device)

    elapsed = torch.zeros(num_envs, device=device)
    velocity_error_sum = torch.zeros(num_envs, device=device)
    reward_sum = torch.zeros(num_envs, device=device)
    sample_count = torch.zeros(num_envs, dtype=torch.long, device=device)

    # 경로 표본. 최대 좌우 이탈은 끝점이 아니라 경로 전체에서 집는다 (#125 1번).
    # 에피소드가 끝날 때만 CPU 로 내린다. 매 스텝 내리면 GPU 가 멈춘다.
    path_buf = torch.zeros((num_envs, max_steps, 2), device=device)
    path_len = torch.zeros(num_envs, dtype=torch.long, device=device)

    # 머리 접촉 표본. 스텝마다 머리 링크 둘에 걸린 힘의 최댓값 하나를 담는다.
    # 경로 버퍼와 같은 규칙이다. 판이 끝날 때만 CPU 로 내린다.
    head_contact_sensor = raw_env.scene.sensors["contact_forces"]
    head_buf = torch.zeros((num_envs, max_steps), device=device)
    head_len = torch.zeros(num_envs, dtype=torch.long, device=device)

    # 전진 속도 표본. **경로 표본과 같은 스텝 · 같은 자리에 담는다.**
    # `speed_buf[e, i]` 는 `path_buf[e, i]` 와 같은 순간의 값이어야 하고,
    # `gate_speed_mps` · `speed_drop_ratio` 가 그 짝맞음을 전제로 셈한다.
    #
    # 담는 것은 **몸통 좌표계의 전진 성분**이다. 명령(`--command_vx`)이 걸리는
    # 축이 그 축이고, `overlay/trace.py` 의 `vx_mps` 도 같은 값이다.
    speed_buf = torch.zeros((num_envs, max_steps), device=device)

    # ── FOOTHOLD CSV v1 · 더한 32열의 누적 ─────────────────────────────
    #
    # **스텝마다 목록에 쌓지 않는다.** 백분위가 필요한 둘만 버퍼를 쓰고
    # 나머지는 합·최댓값만 들고 다닌다. 18,000판 x 300스텝 x 12관절을
    # 목록으로 들면 6,480만 개가 된다.
    contact_parts = resolve_contact_parts(head_contact_sensor)
    part_names = list(csv_extras.CONTACT_PARTS)
    part_ids = [torch.tensor(contact_parts[p], dtype=torch.long, device=device)
                for p in part_names]

    n_parts = len(part_names)
    part_peak = torch.zeros((num_envs, n_parts), device=device)
    part_impulse = torch.zeros((num_envs, n_parts), device=device)
    part_steps = torch.zeros((num_envs, n_parts), dtype=torch.long, device=device)
    part_events = torch.zeros((num_envs, n_parts), dtype=torch.long, device=device)
    part_was = torch.zeros((num_envs, n_parts), dtype=torch.bool, device=device)

    # 자세 둘만 버퍼를 쓴다. 95분위는 전부를 봐야 나온다.
    roll_buf = torch.zeros((num_envs, max_steps), device=device)
    pitch_buf = torch.zeros((num_envs, max_steps), device=device)
    surf_pitch_buf = torch.zeros((num_envs, max_steps), device=device)
    posture_len = torch.zeros(num_envs, dtype=torch.long, device=device)

    vx_err_sq = torch.zeros(num_envs, device=device)
    vy_sq = torch.zeros(num_envs, device=device)
    torque_sq = torch.zeros(num_envs, device=device)
    action_delta_sq = torch.zeros(num_envs, device=device)
    motion_steps = torch.zeros(num_envs, dtype=torch.long, device=device)
    action_steps = torch.zeros(num_envs, dtype=torch.long, device=device)
    # 액션 크기를 `robot` 에서 읽지 않는다. 이 자리에서는 아직 안 만들어졌다
    # `확인됨` (2026-09-11 · UnboundLocalError 로 죽었다).
    prev_action = torch.zeros(
        (num_envs, raw_env.action_manager.total_action_dim), device=device)
    have_prev_action = torch.zeros(num_envs, dtype=torch.bool, device=device)

    # 발 미끄러짐. 두 스텝이 «연속으로» 닿아 있을 때만 잰다.
    slip_sum = torch.zeros(num_envs, device=device)
    prev_foot_xy = torch.zeros((num_envs, 4, 2), device=device)
    prev_foot_touch = torch.zeros((num_envs, 4), dtype=torch.bool, device=device)

    # 험지 참여도. 「넘을 것이 있었나」와 「실제로 탔나」를 따로 센다.
    BIG = 1.0e9
    scan_lo = torch.full((num_envs,), BIG, device=device)
    scan_hi = torch.full((num_envs,), -BIG, device=device)
    under_lo = torch.full((num_envs,), BIG, device=device)
    under_hi = torch.full((num_envs,), -BIG, device=device)

    height_sensor = raw_env.scene.sensors["height_scanner"]

    # 몸통 바로 아래 광선 하나. 「지금 밟고 있는 높이」다.
    _ray_local = (height_sensor.data.ray_hits_w[0, :, :2]
                  - height_sensor.data.pos_w[0, :2].unsqueeze(0))
    center_ray = int(torch.argmin(torch.linalg.norm(_ray_local, dim=1)).item())
    print("[PASS] 중심 광선 %d / %d"
          % (center_ray, height_sensor.data.ray_hits_w.shape[1]), flush=True)

    # 정책 파일 해시. 한 번만 낸다. 판마다 다시 읽으면 18,000번 읽는다.
    policy_sha = file_sha256(resume_path) if os.path.isfile(resume_path) else ""
    run_id = os.path.basename(os.path.normpath(args_cli.output_dir))
    spec_version = globals().get("_SPEC_VERSION")

    env_index = torch.arange(num_envs, device=device)

    robot = raw_env.scene["robot"]

    start_pos = robot.data.root_pos_w[:, :2].clone()
    forward_dir = initial_forward_vectors(robot, num_envs, device)

    terrain_origins = raw_env.scene.terrain.env_origins[:, :2].clone()
    start_offset = start_pos - terrain_origins
    start_yaw = torch.atan2(forward_dir[:, 1], forward_dir[:, 0])

    ground_z = raw_env.scene.terrain.env_origins[:, 2].clone()

    obstacle_zones = resolve_obstacle_zones(terrain_cfg, recorded)

    # ------------------------------------------------------------ 시계열 (기본 꺼짐)
    #
    # `--timeseries` 를 안 주면 `ts_buf` 는 끝까지 `None` 이고 아래 코드는 한 줄도
    # 안 돈다. CSV 도 실행 시간도 지금과 같다.
    ts_buf = None
    ts_columns = None
    ts_offset = None
    ts_dir = ""
    joint_names = None
    foot_body_slots = None
    foot_sensor_slots = None
    ts_first_report = None
    ts_written = 0

    # **시계열과 무관하게 항상 해석한다.** 예전에는 `--timeseries` 를 줄 때만
    # 풀어서, 안 주면 `foot_slip_distance_proxy_m` 이 조용히 0 으로 나갔다
    # `확인됨` (2026-09-11 · 200판 전부 0.0000 이었다).
    foot_body_slots, foot_sensor_slots = resolve_foot_bodies(
        robot, head_contact_sensor
    )

    if args_cli.timeseries:
        joint_names = list(robot.data.joint_names)
        ts_columns = timeseries.columns_for(joint_names)

        ts_dir = os.path.join(args_cli.output_dir, "timeseries")
        os.makedirs(ts_dir, exist_ok=True)

        # 스텝마다 CPU 로 내리지 않는다. GPU 에 쌓아 두고 **에피소드가 끝날 때만**
        # 한 번 내린다. 경로 · 머리 접촉 버퍼와 같은 규칙이다.
        #
        # **자리표를 여기 한 번만 적는다.** 담는 쪽(`timeseries_slice`)과 푸는
        # 쪽(`timeseries_rows`)이 이 목록 하나를 함께 본다. 숫자를 두 군데 적으면
        # 한쪽만 고쳐도 오류가 안 나고 값만 밀린다.
        ts_layout = (
            ("pos", 3),          # root_pos_w        x y z (세계)
            ("quat", 4),         # root_quat_w       w x y z
            ("vel_b", 3),        # root_lin_vel_b    몸통 좌표계 선속도
            ("vel_w", 3),        # root_lin_vel_w    세계 선속도
            ("ang_b", 3),        # root_ang_vel_b    몸통 좌표계 각속도
            ("foot_pos", 12),    # 발 넷의 세계 위치 (FL FR RL RR) x (x y z)
            ("foot_force", 4),   # 발 넷의 접촉력 크기
            ("joint_pos", len(joint_names)),
            ("joint_vel", len(joint_names)),
            ("joint_torque", len(joint_names)),
            ("joint_target", len(joint_names)),
            ("vel_err", 1),
        )

        ts_offset = {}
        raw_width = 0

        for field, width in ts_layout:
            ts_offset[field] = (raw_width, raw_width + width)
            raw_width += width

        ts_buf = torch.zeros((num_envs, max_steps, raw_width), device=device)

        print("\n" + "=" * 80)
        print("TIMESERIES (에피소드마다 parquet 한 장 · 성공한 것도 남긴다)")
        print("=" * 80)
        print(f"관절 {len(joint_names)}개 : {joint_names}")
        print(f"열 수      : {len(ts_columns)}")
        print(f"버퍼       : {num_envs} env x {max_steps} 스텝 x {raw_width} 값"
              f"  = {ts_buf.numel() * 4 / 1024 / 1024:.1f} MiB")
        print(f"폴더       : {ts_dir}")
        print("[PASS] 시계열을 켰습니다.", flush=True)

    def timeseries_slice():
        """이번 스텝의 원자료 한 줄(모든 env). **GPU 왕복을 한 번으로 묶는다.**

        env 마다 `.item()` 을 부르면 그때마다 동기화가 걸린다. 한 텐서로 쌓아
        버퍼에 그대로 넣고, CPU 로는 에피소드가 끝날 때만 내린다.
        """
        parts = [
            robot.data.root_pos_w,                 # 3
            robot.data.root_quat_w,                # 4
            robot.data.root_lin_vel_b,             # 3
            robot.data.root_lin_vel_w,             # 3
            robot.data.root_ang_vel_b,             # 3
        ]

        if foot_body_slots is None:
            parts.append(torch.full((num_envs, 16), float("nan"), device=device))
        else:
            foot_pos = robot.data.body_pos_w[:, foot_body_slots, :]   # (N, 4, 3)

            forces = head_contact_sensor.data.net_forces_w_history[
                :, :, foot_sensor_slots, :
            ]
            foot_force = torch.linalg.vector_norm(forces, dim=-1).amax(dim=1)

            parts.append(foot_pos.reshape(num_envs, 12))
            parts.append(foot_force)

        parts.append(robot.data.joint_pos)
        parts.append(robot.data.joint_vel)
        parts.append(robot.data.applied_torque)
        parts.append(robot.data.joint_pos_target)

        parts.append(planar_vel_error.reshape(num_envs, 1))

        return torch.cat([p.reshape(num_envs, -1) for p in parts], dim=1)

    def timeseries_rows(env_id, n_samples, start_xy, fwd_dir, floor_z):
        """버퍼 한 판을 parquet 줄 목록으로 푼다. **CPU 왕복은 여기서 한 번.**

        `ts_layout` 의 자리표를 그대로 되읽습니다. 담는 쪽과 같은 목록을 보므로
        한쪽만 고쳐 값이 밀리는 일이 없습니다.
        """
        block = ts_buf[env_id, :n_samples].cpu().tolist()

        def cut(sample, field):
            low, high = ts_offset[field]
            return sample[low:high]

        rows = []

        for index, sample in enumerate(block):
            px, py, pz = cut(sample, "pos")
            qw, qx, qy, qz = cut(sample, "quat")
            vx_b, vy_b, vz_b = cut(sample, "vel_b")
            vx_w, vy_w, vz_w = cut(sample, "vel_w")
            wx_b, wy_b, wz_b = cut(sample, "ang_b")

            foot_pos = cut(sample, "foot_pos")
            foot_force = cut(sample, "foot_force")

            roll_deg, pitch_deg, yaw_deg = timeseries.euler_deg_from_quat(
                qw, qx, qy, qz
            )

            here = (px, py)

            row = {
                "frame": index,
                "t_s": index * dt,

                "cmd_vx_mps": args_cli.command_vx,
                "vx_mps": vx_b,
                "vy_mps": vy_b,
                "speed_mps": math.hypot(vx_b, vy_b),
                "vel_err_mps": cut(sample, "vel_err")[0],

                "fwd_m": metrics.forward_offset_m(start_xy, here, fwd_dir),
                "lat_m": metrics.lateral_offset_m(start_xy, here, fwd_dir),

                "base_z_m": pz - floor_z,
                "pitch_deg": pitch_deg,
                "roll_deg": roll_deg,

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

                # 명령은 `configure_evaluation` 이 y · yaw 를 0 으로 못 박고
                # 스텝마다 되읽어 확인한다. 그 확인이 깨지면 위에서 죽는다.
                "cmd_vy_mps": 0.0,
                "cmd_wz_rps": 0.0,
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

                for name, value in zip(joint_names, values):
                    row["{}_{}".format(prefix, name)] = value

            rows.append(row)

        return rows

    results = []

    print("\n" + "=" * 80)
    print("GENERALIZATION EVALUATION")
    print("=" * 80)
    print(f"recorded terrains      : {recorded}")
    print(f"envs / terrain         : {envs_per_terrain}")
    print(f"total envs (simulated) : {num_envs}")
    print(f"episodes / terrain     : {args_cli.episodes}")
    print(f"total target episodes  : {total_target}")
    print(f"evaluation duration    : {args_cli.eval_duration:.2f} s")
    print(f"step_dt                : {dt:.4f} s  ({max_steps - 2} steps / episode)")
    print(f"command vx             : {args_cli.command_vx:.2f} m/s")
    print(f"ideal distance         : {ideal_distance:.2f} m")
    print(f"minimum progress       : {min_progress:.2f} m  (ratio {min_progress_ratio:.3f})")
    print(f"max velocity MAE       : {args_cli.max_velocity_mae:.2f} m/s")
    print(f"max lateral drift      : {args_cli.max_lateral_drift:.3f} m"
          f"  (at the {min_progress:.2f} m gate)")
    print(f"terrain border width   : {terrain_border_width:.2f} m"
          f"  -> forward extent {forward_extent:.2f} m")
    print(f"seed                   : {args_cli.seed}")
    print("=" * 80, flush=True)

    while simulation_app.is_running():

        if torch.all(episode_counts >= targets):
            break

        active = episode_counts < targets

        pre_step_pos = robot.data.root_pos_w[:, :2].clone()

        command = raw_env.command_manager.get_command("base_velocity").clone()

        expected = torch.zeros_like(command)
        expected[:, 0] = args_cli.command_vx

        command_error = torch.max(torch.abs(command - expected)).item()

        if command_error > 1.0e-5:
            raise RuntimeError(
                f"Command changed during evaluation. max deviation={command_error}"
            )

        actual_vel_b = robot.data.root_lin_vel_b[:, :2].clone()

        planar_vel_error = torch.linalg.vector_norm(actual_vel_b - command[:, :2], dim=1)

        # 경로 표본을 먼저 담는다. 스냅샷이 끝점으로 쓰는 `pre_step_pos` 와 같은 값이라
        # 이 버퍼의 마지막 표본이 곧 그 끝점이다.
        room = active & (path_len < max_steps)

        # **세 버퍼를 같은 마스크 · 같은 첨자로 한 자리에서 채운다.**
        # 따로 채우면 어느 한쪽만 밀려도 오류가 안 나고, 통과선 속도만 조용히
        # 다른 스텝의 값이 된다. 짝이 맞아야 하는 것은 여기서 함께 움직인다.
        path_buf[env_index[room], path_len[room]] = pre_step_pos[room]
        speed_buf[env_index[room], path_len[room]] = actual_vel_b[room, 0]

        if ts_buf is not None:
            ts_buf[env_index[room], path_len[room]] = timeseries_slice()[room]

        path_len[room] += 1

        # 머리 접촉을 **스텝 전에** 담는다. 경로 표본과 같은 자리다.
        #
        # **스텝 뒤에 담으면 안 된다** `확인됨`. `env.step()` 이 끝난 판을 그 자리에서
        # 되감고, `ContactSensor.reset()` 이 `net_forces_w` 와 그 이력을 **0 으로
        # 지운다** (`contact_sensor.py:151-152`, `manager_based_rl_env.py:221`).
        # 즉 스텝 뒤에 읽으면 넘어진 판의 충격이 지워진 뒤를 읽게 된다.
        #
        # **대신 마지막 한 스텝을 못 본다.** 판이 끝나는 그 스텝의 힘은 다음 회차에
        # 읽혔을 텐데 그때는 이미 지워져 있다. 경로 버퍼가 갖는 한 스텝 지연과 같은
        # 성질이고, 이 열은 판정이 아니라 경고등이라 그대로 둔다 `미확인`
        # (그 한 스텝이 최댓값이었을 판이 얼마나 되는지는 안 재봤다).
        #
        # 이력 전체의 최댓값을 쓴다. 센서는 `sim.dt`(0.005 s)마다 갱신되고 정책은
        # `step_dt`(0.02 s)마다 도므로, 이력 3칸이 한 스텝 안의 물리 하위스텝 4개 중
        # 3개를 덮는다. 순간값 하나만 읽으면 나머지 3개의 충격을 놓친다.
        # 종료 조건 `mdp.illegal_contact` 도 같은 이력을 같은 방식으로 본다.
        head_history = head_contact_sensor.data.net_forces_w_history[:, :, head_body_ids, :]
        head_force = torch.linalg.vector_norm(head_history, dim=-1).amax(dim=2).amax(dim=1)

        head_room = active & (head_len < max_steps)
        head_buf[env_index[head_room], head_len[head_room]] = head_force[head_room]
        head_len[head_room] += 1

        # ── FOOTHOLD CSV v1 · 스텝 누적 ────────────────────────────────
        #
        # **머리 접촉과 같은 자리에서 담는다.** 스텝 «전» 이다. `env.step()` 이
        # 끝난 판을 그 자리에서 되감으면서 접촉 이력을 0 으로 지우기 때문이다
        # (같은 이유가 바로 위 머리 접촉 주석에 적혀 있다).
        act_f = active.float()

        # 자세 둘. 95분위를 내려면 스텝마다 남겨야 한다.
        q = robot.data.root_quat_w
        qw, qx, qy, qz = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
        roll_rad = torch.atan2(2.0 * (qw * qx + qy * qz),
                               1.0 - 2.0 * (qx * qx + qy * qy))
        pitch_rad = torch.asin(torch.clamp(2.0 * (qw * qy - qz * qx), -1.0, 1.0))

        # 지면 기울기. 높이 스캔을 로봇 전방축에 최소제곱으로 맞춘다.
        # 몸 기울기에서 이것을 빼면 «지면 기준» 기울기가 된다. 비탈을 오를 때
        # 몸이 기우는 것과 평지에서 휘청이는 것을 가른다.
        hits_w = height_sensor.data.ray_hits_w
        hit_z = hits_w[..., 2]
        ok = torch.isfinite(hit_z)
        rel_xy = hits_w[..., :2] - height_sensor.data.pos_w[:, :2].unsqueeze(1)
        along = (rel_xy * forward_dir.unsqueeze(1)).sum(dim=2)
        w = ok.float()
        cnt = w.sum(dim=1).clamp_min(1.0)
        z_safe = torch.where(ok, hit_z, torch.zeros_like(hit_z))
        mx = (along * w).sum(dim=1) / cnt
        mz = (z_safe * w).sum(dim=1) / cnt
        dx = (along - mx.unsqueeze(1)) * w
        dz = (z_safe - mz.unsqueeze(1)) * w
        var = (dx * dx).sum(dim=1)
        slope_rad = torch.atan2((dx * dz).sum(dim=1), var.clamp_min(1.0e-6))
        slope_rad = torch.where(var > 1.0e-6, slope_rad, torch.zeros_like(slope_rad))

        p_room = active & (posture_len < max_steps)
        idx = env_index[p_room]
        roll_buf[idx, posture_len[p_room]] = torch.rad2deg(roll_rad[p_room]).abs()
        pitch_buf[idx, posture_len[p_room]] = torch.rad2deg(pitch_rad[p_room]).abs()
        surf_pitch_buf[idx, posture_len[p_room]] = torch.rad2deg(
            pitch_rad[p_room] - slope_rad[p_room]).abs()
        posture_len[p_room] += 1

        # 속도와 토크. 합만 들고 다닌다.
        vx_err_sq += act_f * (actual_vel_b[:, 0] - args_cli.command_vx) ** 2
        vy_sq += act_f * actual_vel_b[:, 1] ** 2
        torque_sq += act_f * (robot.data.applied_torque ** 2).mean(dim=1)
        motion_steps += active.long()

        # 부위별 접촉. 이력 전체의 최댓값을 쓴다. 머리 접촉과 같은 방식이다.
        hist = head_contact_sensor.data.net_forces_w_history
        mag = torch.linalg.vector_norm(hist, dim=-1).amax(dim=1)     # (envs, bodies)

        for p_i, ids in enumerate(part_ids):
            f = mag[:, ids].amax(dim=1)
            touching = active & (f > args_cli.head_contact_threshold_n)

            part_peak[:, p_i] = torch.maximum(
                part_peak[:, p_i], torch.where(active, f, torch.zeros_like(f)))
            part_impulse[:, p_i] += torch.where(
                touching, f * dt, torch.zeros_like(f))
            part_steps[:, p_i] += touching.long()
            part_events[:, p_i] += (touching & ~part_was[:, p_i]).long()
            part_was[:, p_i] = touching

        # 험지 참여도.
        #   scan     몸 주변 1.6 x 1.0 m 안에 «넘을 것이 있었나»
        #   under    몸 «바로 아래» 지면이 위아래로 얼마나 움직였나
        big = torch.where(ok, hit_z, torch.full_like(hit_z, -BIG))
        small = torch.where(ok, hit_z, torch.full_like(hit_z, BIG))
        any_hit = ok.any(dim=1) & active

        scan_hi = torch.where(any_hit, torch.maximum(scan_hi, big.amax(dim=1)), scan_hi)
        scan_lo = torch.where(any_hit, torch.minimum(scan_lo, small.amin(dim=1)), scan_lo)

        under = hit_z[:, center_ray]
        under_ok = torch.isfinite(under) & active
        under_hi = torch.where(under_ok, torch.maximum(under_hi, under), under_hi)
        under_lo = torch.where(under_ok, torch.minimum(under_lo, under), under_lo)

        # 발 미끄러짐. 두 스텝이 «연속으로» 닿아 있을 때만 센다.
        if foot_body_slots is not None and foot_sensor_slots is not None:
            fxy = robot.data.body_pos_w[:, foot_body_slots, :2]
            ff = mag[:, foot_sensor_slots]
            touch = ff > args_cli.head_contact_threshold_n
            both = touch & prev_foot_touch & active.unsqueeze(1)
            step_move = torch.linalg.vector_norm(fxy - prev_foot_xy, dim=2)
            slip_sum += (step_move * both.float()).sum(dim=1)
            prev_foot_xy = fxy.clone()
            prev_foot_touch = touch.clone()

        elapsed[active] += dt
        velocity_error_sum[active] += planar_vel_error[active]
        sample_count[active] += 1

        with torch.inference_mode():
            actions = policy(obs)
            obs, reward, dones, extras = env.step(actions)
            policy_nn.reset(dones)

        reward_sum[active] += reward[active]

        # 명령이 프레임마다 얼마나 바뀌나. 첫 스텝은 «직전» 이 없어 안 센다.
        act_now = actions.detach()
        counted = active & have_prev_action
        action_delta_sq += counted.float() * ((act_now - prev_action) ** 2).mean(dim=1)
        action_steps += counted.long()
        prev_action = torch.where(active.unsqueeze(1), act_now, prev_action)
        have_prev_action = have_prev_action | active

        terminated = raw_env.reset_terminated.clone()
        timed_out = raw_env.reset_time_outs.clone()

        done_ids = torch.nonzero((terminated | timed_out) & active, as_tuple=False).squeeze(-1)

        if done_ids.numel() == 0:
            continue

        for env_id_tensor in done_ids:
            env_id = int(env_id_tensor.item())

            terrain_type = int(raw_env.scene.terrain.terrain_types[env_id].item())
            terrain_name = TERRAIN_NAMES[terrain_type]

            n_samples = int(path_len[env_id].item())
            path_xy = [tuple(p) for p in path_buf[env_id, :n_samples].tolist()]
            path_speed = speed_buf[env_id, :n_samples].tolist()

            n_head = int(head_len[env_id].item())
            head_forces = head_buf[env_id, :n_head].tolist()

            start_xy = tuple(start_pos[env_id].tolist())
            end_xy = tuple(pre_step_pos[env_id].tolist())
            fwd = tuple(forward_dir[env_id].tolist())

            row_metrics = metrics.episode_metrics(
                start_xy=start_xy,
                end_xy=end_xy,
                forward_dir=fwd,
                velocity_error_sum=velocity_error_sum[env_id].item(),
                reward_sum=reward_sum[env_id].item(),
                sample_count=int(sample_count[env_id].item()),
                elapsed_s=elapsed[env_id].item(),
                timed_out=bool(timed_out[env_id].item()),
                terminated=bool(terminated[env_id].item()),
                path_xy=path_xy if path_xy else None,
                command_vx=args_cli.command_vx,
                eval_duration=args_cli.eval_duration,
                min_progress_ratio=min_progress_ratio,
                max_velocity_mae=args_cli.max_velocity_mae,
                max_lateral_drift=args_cli.max_lateral_drift,
                gate_progress_m=min_progress,
                head_contact_forces=head_forces,
                head_contact_threshold_n=args_cli.head_contact_threshold_n,
                step_dt=dt,

                # 속도 두 열. 경로 표본과 **같은 목록 길이 · 같은 첨자**다.
                path_speed_mps=path_speed if path_speed else None,
                obstacle_zone_m=obstacle_zones.get(terrain_name),
            )

            episode_number = int(episode_counts[env_id].item()) + 1

            row = {
                "terrain": terrain_name,
                "env_id": env_id,
                "episode": episode_number,
                "start_x_offset_m": round(start_offset[env_id, 0].item(), 4),
                "start_y_offset_m": round(start_offset[env_id, 1].item(), 4),
                "start_yaw_deg": round(math.degrees(start_yaw[env_id].item()), 3),
                "overall_success": row_metrics["overall_success"],
                "survival_success": row_metrics["survival_success"],
                "progress_success": row_metrics["progress_success"],
                "tracking_success": row_metrics["tracking_success"],
                "direction_success": row_metrics["direction_success"],
                "termination_reason": row_metrics["termination_reason"],
                "duration_s": round(row_metrics["duration_s"], 4),
                "forward_progress_m": round(row_metrics["forward_progress_m"], 4),
                "ideal_distance_m": round(row_metrics["ideal_distance_m"], 4),
                "progress_ratio": round(row_metrics["progress_ratio"], 4),
                "lateral_drift_m": round(row_metrics["lateral_drift_m"], 4),
                "peak_lateral_drift_m": round(row_metrics["peak_lateral_drift_m"], 4),
                "gate_lateral_drift_m": (
                    ""
                    if row_metrics["gate_lateral_drift_m"] is None
                    else round(row_metrics["gate_lateral_drift_m"], 4)
                ),
                "velocity_mae_mps": round(row_metrics["velocity_mae_mps"], 4),
                "mean_reward_per_step": round(row_metrics["mean_reward_per_step"], 6),

                # 분석 열 셋. **판정 열이 아니다.**
                #
                # `traversal_success` 는 이름에 `success` 가 들어가지만
                # **성공률이 아니다.** 성공률은 `overall_success` 하나다.
                # 이 열은 속도 추종을 뺀 세 축의 AND 이고, 「넘긴 했는데 느렸던」
                # 에피소드를 세는 데만 쓴다 (`metrics.traversal_success`).
                "traversal_success": row_metrics["traversal_success"],
                "gate_speed_mps": (
                    ""
                    if row_metrics["gate_speed_mps"] is None
                    else round(row_metrics["gate_speed_mps"], 4)
                ),
                "speed_drop_ratio": (
                    ""
                    if row_metrics["speed_drop_ratio"] is None
                    else round(row_metrics["speed_drop_ratio"], 4)
                ),

                # 머리 접촉 관측 셋. **판정 열이 아니다.** 위 다섯 판정 열은
                # 이 값이 무엇이든 안 바뀐다.
                "head_contact_count": row_metrics["head_contact_count"],
                "head_contact_peak_n": round(row_metrics["head_contact_peak_n"], 3),
                "head_contact_first_s": (
                    ""
                    if row_metrics["head_contact_first_s"] is None
                    else round(row_metrics["head_contact_first_s"], 4)
                ),
            }

            # ── FOOTHOLD CSV v1 · 더한 32열 ────────────────────────────
            #
            # **판정을 안 바꾼다.** 위 27열은 손대지 않았고 `overall_success`
            # 는 여전히 네 축의 AND 다. 아래는 전부 관측이다.
            def blank(v, digits=4):
                return "" if v is None else round(float(v), digits)

            n_post = int(posture_len[env_id].item())
            n_motion = int(motion_steps[env_id].item())
            n_action = int(action_steps[env_id].item())

            row["roll_abs_p95_deg"] = blank(csv_extras.percentile(
                roll_buf[env_id, :n_post].tolist(), 95), 3)
            row["pitch_abs_p95_deg"] = blank(csv_extras.percentile(
                pitch_buf[env_id, :n_post].tolist(), 95), 3)
            row["surface_relative_pitch_abs_p95_deg"] = blank(csv_extras.percentile(
                surf_pitch_buf[env_id, :n_post].tolist(), 95), 3)

            row["forward_velocity_rmse_mps"] = blank(csv_extras.rms_from_sum_sq(
                vx_err_sq[env_id].item(), n_motion))
            row["lateral_velocity_rms_mps"] = blank(csv_extras.rms_from_sum_sq(
                vy_sq[env_id].item(), n_motion))
            row["joint_torque_rms_nm"] = blank(csv_extras.rms_from_sum_sq(
                torque_sq[env_id].item(), n_motion), 3)
            row["action_delta_rms"] = blank(csv_extras.rms_from_sum_sq(
                action_delta_sq[env_id].item(), n_action), 5)
            row["foot_slip_distance_proxy_m"] = blank(slip_sum[env_id].item())

            for p_i, part in enumerate(part_names):
                row["{}_peak_force_n".format(part)] = blank(
                    part_peak[env_id, p_i].item(), 3)
                row["{}_impulse_proxy_ns".format(part)] = blank(
                    part_impulse[env_id, p_i].item(), 4)
                row["{}_contact_time_s".format(part)] = blank(
                    int(part_steps[env_id, p_i].item()) * dt)
                row["{}_contact_events".format(part)] = int(
                    part_events[env_id, p_i].item())

            # 험지 참여도. 한 번도 못 맞혔으면 빈 칸이다. 0 이 아니다.
            _slo = scan_lo[env_id].item()
            _shi = scan_hi[env_id].item()
            _ulo = under_lo[env_id].item()
            _uhi = under_hi[env_id].item()

            scan_relief = (None if _slo > _shi
                           else csv_extras.relief_m(_slo, _shi))
            under_relief = (None if _ulo > _uhi
                            else csv_extras.relief_m(_ulo, _uhi))

            row["terrain_relief_scan_m"] = blank(scan_relief)
            row["terrain_relief_underfoot_m"] = blank(under_relief)
            row["terrain_engagement_ratio"] = blank(
                csv_extras.engagement_ratio(under_relief, scan_relief), 4)

            row["episode_id"] = csv_extras.episode_id(
                terrain_name, spec_version, args_cli.difficulty,
                args_cli.command_vx, episode_number)
            row["eval_spec_version"] = spec_version
            row["policy_sha256"] = policy_sha
            row["seed"] = args_cli.seed
            row["run_id"] = run_id

            if list(row.keys()) != list(metrics.RAW_COLUMNS):
                raise RuntimeError(
                    "Raw column order drifted from metrics.RAW_COLUMNS.\n"
                    f"row     : {list(row.keys())}\n"
                    f"expected: {list(metrics.RAW_COLUMNS)}"
                )

            results.append(row)
            episode_counts[env_id] += 1

            # 시계열 한 장. **번호는 raw CSV 의 줄 순서다** (`len(results)`).
            # 통과한 에피소드도 예외 없이 남긴다. 실패한 것만 남기면 같은
            # 난이도에서 넘은 것과 못 넘은 것을 겹쳐 볼 수 없다.
            if ts_buf is not None:
                ts_rows = timeseries_rows(
                    env_id, n_samples, start_xy, fwd,
                    float(ground_z[env_id].item()),
                )

                ts_path = os.path.join(
                    ts_dir, timeseries.episode_filename(len(results))
                )

                timeseries.write(
                    ts_path,
                    {
                        "terrain": terrain_name,
                        "env_id": env_id,
                        "episode": episode_number,
                        "csv_row": len(results),
                        "fps": 1.0 / dt if dt > 0.0 else 0.0,
                        "dt_s": dt,
                        "command_vx_mps": args_cli.command_vx,
                        "eval_duration_s": args_cli.eval_duration,
                        "gate_m": min_progress,
                        "eval_spec_version": globals().get("_SPEC_VERSION"),
                        "gap_aware_scan": not bool(args_cli.legacy_miss_scan),
                        "height_scan_miss_value": globals().get("_MISS_VALUE"),
                        "min_progress_m": min_progress,
                        "max_lateral_drift_m": args_cli.max_lateral_drift,
                        "max_velocity_mae_mps": args_cli.max_velocity_mae,
                        "obstacle_zone_start_m": obstacle_zones[terrain_name][0],
                        "obstacle_zone_end_m": obstacle_zones[terrain_name][1],
                        "overall_success": row["overall_success"],
                        "traversal_success": row["traversal_success"],
                        "termination_reason": row["termination_reason"],
                        "policy_checkpoint": resume_path.replace("\\", "/"),
                    },
                    ts_rows,
                    ts_columns,
                )

                ts_written += 1

                # 첫 장만 되읽어 **정말 읽히는지 · 몇 줄 몇 열인지**를 잰다.
                # 모든 장을 되읽으면 실행이 두 배로 느려지고, 한 장도 안 되읽으면
                # 「썼다」는 종료코드만 믿게 된다 (원칙 2 · 3).
                if ts_first_report is None:
                    back_meta, back_rows = timeseries.read(ts_path)

                    ts_first_report = {
                        "path": ts_path,
                        "rows": len(back_rows),
                        "columns": len(back_rows[0]),
                        "parquet_bytes": os.path.getsize(ts_path),
                        "csv_bytes": timeseries.measure_csv_size(
                            ts_rows, ts_columns
                        ),
                        "checks": timeseries.verify_against_row(back_rows, row),
                    }

                    del back_meta

            done_total = int(episode_counts.sum().item())

            print(
                f"[{terrain_name:<18}] "
                f"{done_total:3d}/{total_target} "
                f"| env {env_id:03d} ep {episode_number:02d} "
                f"| ok={int(row['overall_success'])} "
                f"| surv={int(row['survival_success'])} "
                f"| fwd={row['forward_progress_m']:6.2f}m "
                f"| gate={row['gate_lateral_drift_m'] if row['gate_lateral_drift_m'] == '' else format(row['gate_lateral_drift_m'], '5.3f')}m "
                f"| end={row['lateral_drift_m']:5.3f}m "
                f"| peak={row['peak_lateral_drift_m']:5.3f}m "
                f"| vMAE={row['velocity_mae_mps']:4.2f} "
                f"| trav={int(row['traversal_success'])} "
                f"| gateV={row['gate_speed_mps'] if row['gate_speed_mps'] == '' else format(row['gate_speed_mps'], '5.2f')} "
                f"| drop={row['speed_drop_ratio'] if row['speed_drop_ratio'] == '' else format(row['speed_drop_ratio'], '5.2f')} "
                f"| head={row['head_contact_count']:3d}스텝/{row['head_contact_peak_n']:7.1f}N",
                flush=True,
            )

            # 다음 판을 위해 이 env 만 되감는다. 스냅샷과 같은 순서.
            start_pos[env_id] = robot.data.root_pos_w[env_id, :2]

            local_x = torch.tensor([[1.0, 0.0, 0.0]], device=device)

            new_forward = quat_apply(robot.data.root_quat_w[env_id: env_id + 1], local_x)[0, :2]
            new_forward = new_forward / torch.linalg.vector_norm(new_forward).clamp_min(1.0e-8)

            forward_dir[env_id] = new_forward
            start_offset[env_id] = start_pos[env_id] - terrain_origins[env_id]
            start_yaw[env_id] = torch.atan2(new_forward[1], new_forward[0])

            elapsed[env_id] = 0.0
            velocity_error_sum[env_id] = 0.0
            reward_sum[env_id] = 0.0
            sample_count[env_id] = 0
            path_len[env_id] = 0
            head_len[env_id] = 0

            # ── 더한 32열의 누적도 되돌린다 ────────────────────────────
            #
            # **여기를 빼면 앞 판의 값이 다음 판에 새어 든다.** 머리 접촉
            # 첫 시각이 오염된 것과 같은 부류의 사고다.
            posture_len[env_id] = 0
            motion_steps[env_id] = 0
            action_steps[env_id] = 0
            vx_err_sq[env_id] = 0.0
            vy_sq[env_id] = 0.0
            torque_sq[env_id] = 0.0
            action_delta_sq[env_id] = 0.0
            have_prev_action[env_id] = False
            slip_sum[env_id] = 0.0
            prev_foot_touch[env_id] = False
            part_peak[env_id] = 0.0
            part_impulse[env_id] = 0.0
            part_steps[env_id] = 0
            part_events[env_id] = 0
            part_was[env_id] = False
            scan_lo[env_id] = BIG
            scan_hi[env_id] = -BIG
            under_lo[env_id] = BIG
            under_hi[env_id] = -BIG

    if len(results) == 0:
        raise RuntimeError("No evaluation episodes were recorded.")

    # 관문 · 접촉 열이 통째로 비면 소리를 낸다 (원칙 2).
    #
    # 링크 이름이 맞고 센서도 있는데 **한 판도 표본을 못 담은** 경우가 남는다.
    # 그러면 `head_contact_peak_n` 이 전부 0.0 이 되고 CSV 는 「어느 판도 머리가
    # 안 닿았다」로 읽힌다. 진짜로 안 닿은 것과 못 잰 것을 여기서 가른다.
    #
    # **「최댓값이 전부 0」을 실패로 치지 않는다.** 평지 100판이면 그것이 정답이다.
    # 표본 수가 0 인 것만 잡는다. 그건 물리적으로 불가능하다.
    # ── 더한 열이 통째로 죽었는지 본다 (원칙 2) ───────────────────────
    #
    # 값이 «전부 같은» 열은 거의 언제나 안 잰 것이다. 진짜로 전부 같을 수
    # 있는 열(실행 내내 안 바뀌는 추적 열, 평지에서 0 인 기복)은 뺀다.
    #
    # 2026-09-11 에 `foot_slip_distance_proxy_m` 이 200판 전부 0.0000 으로
    # 나갔다. 오류는 없었고 CSV 는 「한 번도 안 미끄러졌다」로 읽혔다.
    _alive_check = (
        "roll_abs_p95_deg", "pitch_abs_p95_deg",
        "surface_relative_pitch_abs_p95_deg",
        "forward_velocity_rmse_mps", "lateral_velocity_rms_mps",
        "joint_torque_rms_nm", "action_delta_rms",
        "foot_slip_distance_proxy_m",
        "foot_peak_force_n", "foot_contact_events",
    )

    if len(results) >= 10:
        dead = [c for c in _alive_check
                if len({str(r.get(c)) for r in results}) == 1]

        if dead:
            raise RuntimeError(
                "열 %s 이 %d 판 내내 한 값이었습니다. 안 재고 있을 소지가 큽니다.%s"
                "이대로 CSV 를 내면 「그런 일이 없었다」로 읽힙니다."
                % (dead, len(results), chr(10)))

    empty = [r for r in results if r["head_contact_count"] is None]

    if empty:
        raise RuntimeError(
            f"머리 접촉을 못 잰 판이 {len(empty)}개입니다. 표본이 안 담겼습니다.\n"
            "이대로 CSV 를 내면 「안 닿았다」로 읽힙니다."
        )

    # 관문 · 시계열이 판정 표와 짝이 맞는가 (원칙 2 · 3).
    #
    # 「썼다」는 보고를 결과로 치지 않는다. **폴더를 실제로 세고, 한 장을 실제로
    # 되읽고, 그 장을 접으면 표의 그 줄이 나오는지 본다.** 셋 중 하나라도
    # 어긋나면 여기서 죽는다. 어긋난 시계열로 그린 그림은 멀쩡해 보인다.
    if ts_buf is not None:
        on_disk = sorted(
            name for name in os.listdir(ts_dir) if name.endswith(".parquet")
        )

        print("\n" + "=" * 80)
        print("TIMESERIES CHECK")
        print("=" * 80)
        print(f"판정 표 줄 수   : {len(results)}")
        print(f"쓴 파일 수      : {ts_written}")
        print(f"폴더에 있는 수  : {len(on_disk)}")

        if ts_first_report is not None:
            report_first = ts_first_report

            saving = (
                report_first["csv_bytes"] / report_first["parquet_bytes"]
                if report_first["parquet_bytes"] > 0
                else 0.0
            )

            print(f"첫 장           : {report_first['path']}")
            print(f"  줄 x 열       : {report_first['rows']} x "
                  f"{report_first['columns']}")
            print(f"  parquet       : {report_first['parquet_bytes']:,} B")
            print(f"  같은 자료 CSV : {report_first['csv_bytes']:,} B"
                  f"  ({saving:.1f}배)")
            print("  접어서 대조 (첫 에피소드):")

            for name, want, got, delta, ok in report_first["checks"]:
                mark = "OK  " if ok else "FAIL"
                want_text = "-" if want is None else f"{want:.4f}"
                got_text = "-" if got is None else f"{got:.4f}"
                delta_text = "-" if delta is None else f"{delta:.5f}"

                print(f"    [{mark}] {name:<22} 표={want_text:<10} "
                      f"시계열={got_text:<10} 차이={delta_text}")

        problems = []

        if len(on_disk) != len(results):
            problems.append(
                f"파일 {len(on_disk)}장인데 판정 표는 {len(results)}줄입니다"
            )

        if ts_written != len(results):
            problems.append(
                f"쓴 것이 {ts_written}장인데 판정 표는 {len(results)}줄입니다"
            )

        if ts_first_report is None:
            problems.append("첫 장을 되읽지 못했습니다")
        else:
            failed = [c[0] for c in ts_first_report["checks"] if not c[4]]

            if failed:
                problems.append("접어서 대조가 안 맞습니다: " + ", ".join(failed))

        if problems:
            raise RuntimeError(
                "시계열이 판정 표와 짝이 안 맞습니다. 이대로 두면 그림은 멀쩡히\n"
                "나오고 값만 밀립니다.\n  · " + "\n  · ".join(problems)
            )

        # ★ **여기서 반드시 흘려보낸다.** 파이썬 stdout 은 파일로 보낼 때
        #   블록 버퍼이고, Kit 는 종료할 때 그 버퍼를 안 비운다. 2026-09-10 에
        #   실제로 이 관문의 출력이 로그에서 통째로 사라졌다 (`RESULT FILES` 와
        #   `SUMMARY` 도 같은 이유로 오래 안 보이고 있었다).
        #
        #   관문이 실패하면 `RuntimeError` 로 종료코드가 서므로 «막는 힘» 은
        #   그대로였지만, **통과했을 때 무엇을 보고 통과라 했는지가 안 보였다.**
        #   그것은 「관문이 스스로 눈을 감는」 부류의 절반이다.
        print("\n[PASS] 시계열 {}장이 판정 표 {}줄과 짝이 맞습니다.".format(
            len(on_disk), len(results)
        ), flush=True)

    summary_rows = metrics.summarize(results, recorded)

    raw_path, summary_path = save_csv(results, summary_rows, args_cli.output_dir)

    save_run_manifest(
        args_cli.output_dir,
        {
            "harness": "sim/eval/eval_generalization.py",
            "policy_checkpoint": resume_path,
            "policy_sha256": file_sha256(resume_path),
            "started_at_utc": started_at,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "environment": environment_record(),
            "terrain_set": args_cli.terrain_set,
            "terrain_set_names": list(TERRAIN_NAMES),
            "recorded_terrains": recorded,
            "envs_per_terrain": envs_per_terrain,
            "total_envs_simulated": num_envs,
            "episodes_per_terrain": args_cli.episodes,
            "episodes_recorded": len(results),
            "eval_duration_s": args_cli.eval_duration,
            "step_dt_s": dt,
            "command_vx_mps": args_cli.command_vx,
            "ideal_distance_m": ideal_distance,
            "min_progress_m": min_progress,
            "min_progress_ratio": min_progress_ratio,
            "max_velocity_mae_mps": args_cli.max_velocity_mae,
            "max_lateral_drift_m": args_cli.max_lateral_drift,
            # 어느 «규격» 으로 쟀는가. **이 세 줄이 없으면 옛 숫자와 새 숫자를
            # 나중에 구별할 수 없다.** 2026-09-11 에 한 번 빠뜨려 78개 실행이
            # 규격 없이 쌓였다. 규격을 바꾸는 팔은 반드시 여기 남긴다.
            #   `--gap_aware_scan` 은 이제 아무 일도 안 하는 호환용 팔이다.
            #   실제로 규격을 가르는 것은 `--legacy_miss_scan` 하나다.
            "eval_spec_version": globals().get("_SPEC_VERSION"),
            "gap_aware_scan": not bool(args_cli.legacy_miss_scan),
            "height_scan_miss_value": globals().get("_MISS_VALUE"),
            "direction_measured_at": "gate",
            "direction_gate_m": min_progress,

            # 머리 접촉. **판정 축이 아니다.** 나중에 이 CSV 를 다시 읽는 사람이
            # 「이 숫자가 성공률에 들어갔나」를 물을 때 답이 여기 있어야 한다.
            "head_contact_body_names": list(metrics.HEAD_BODY_NAMES),
            "head_contact_body_ids": head_body_ids,
            "head_contact_threshold_n": args_cli.head_contact_threshold_n,
            "head_contact_in_success_judgement": False,
            "success_axes": [
                "survival_success",
                "progress_success",
                "tracking_success",
                "direction_success",
            ],

            # 분석 열 셋. **판정 축이 아니다.** 위 `success_axes` 가 넷 그대로인
            # 것이 그 보증이다. 나중에 이 CSV 를 읽는 사람이 「이 숫자가
            # 성공률에 들어갔나」를 물을 때 답이 여기 있어야 한다.
            "traversal_success_axes": [
                "survival_success",
                "progress_success",
                "direction_success",
            ],
            "traversal_success_is_a_success_rate": False,
            "gate_speed_measured_at": "gate",
            "gate_speed_source": "root_lin_vel_b[:, 0]",
            "speed_drop_ratio_definition": (
                "장애물 구간 안 최저 전진 속도 / 명령 전진 속도. "
                "구간은 출발점 기준 전진거리이고 지형 설정에서 계산한다"
            ),
            "obstacle_zones_m": {
                name: list(zone) for name, zone in obstacle_zones.items()
            },
            "obstacle_zone_basis": {
                name: terrains.obstacle_zone_m(
                    terrain_cfg.sub_terrains[name],
                    (terrain_cfg.difficulty_range[0]
                     + terrain_cfg.difficulty_range[1]) / 2.0,
                    terrain_cfg.size[0],
                )[2]
                for name in recorded
            },

            # 시계열. 안 켰으면 `enabled: false` 하나만 남는다.
            "timeseries": (
                {"enabled": False}
                if ts_buf is None
                else {
                    "enabled": True,
                    "dir": "timeseries",
                    "format": "parquet",
                    "compression": "zstd",
                    "schema": timeseries.SCHEMA,
                    "files": ts_written,
                    "columns": len(ts_columns),
                    "joint_names": joint_names,
                    "column_names": list(ts_columns),
                    "feet_measured": foot_body_slots is not None,
                    "includes_successful_episodes": True,
                    "numbering": "raw CSV 의 줄 순서. ep0001 이 첫 줄",
                    "first_file": ts_first_report and {
                        "rows": ts_first_report["rows"],
                        "columns": ts_first_report["columns"],
                        "parquet_bytes": ts_first_report["parquet_bytes"],
                        "same_data_csv_bytes": ts_first_report["csv_bytes"],
                    },
                }
            ),
            "terrain_border_width_m": terrain_border_width,
            "terrain_forward_extent_m": forward_extent,
            "terrain_size_m": list(terrain_cfg.size),
            "terrain_num_rows": terrain_cfg.num_rows,
            "terrain_num_cols": terrain_cfg.num_cols,

            # **cfg 에서 되읽는다. 인자를 그대로 옮겨 적지 않는다.**
            # 인자를 적으면 「덮어쓰기가 실제로 먹었나」를 이 파일이 증언하지 못한다.
            "terrain_difficulty_range": list(terrain_cfg.difficulty_range),
            "terrain_difficulty_overridden": args_cli.difficulty is not None,

            # `rails` 두께를 못 박았나. 못 박은 판과 안 박은 판은 조건이 다르다.
            # cfg 에서 되읽는다.
            "rail_thickness_range": (
                list(terrain_cfg.sub_terrains["rails"].rail_thickness_range)
                if "rails" in terrain_cfg.sub_terrains else None
            ),
            "rail_thickness_fixed_m": args_cli.rail_thickness,
            "terrain_curriculum": terrain_cfg.curriculum,
            "terrain_border_width_changed_from": 10.0,
            "seed": args_cli.seed,
            "spawn_xy_range_m": args_cli.spawn_xy_range,
            "yaw_range_deg": args_cli.yaw_range_deg,
            "joint_pos_scale": args_cli.joint_pos_scale,
            "device": str(env_cfg.sim.device),
            "observation_dim": int(obs["policy"].shape[-1]),
            "argv": sys.argv,
            "note": args_cli.note,
        },
    )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80, flush=True)

    for row in summary_rows:
        print(
            f"{row['terrain']:<18}"
            f" | n={row['episodes']:3d}"
            f" | overall={100 * row['overall_success_rate']:6.1f}%"
            f" | survival={100 * row['survival_rate']:6.1f}%"
            f" | progress={100 * row['progress_success_rate']:6.1f}%"
            f" | tracking={100 * row['tracking_success_rate']:6.1f}%"
            f" | direction={100 * row['direction_success_rate']:6.1f}%"
            f" | fwd={row['mean_forward_progress_m']:6.2f}m"
        )

    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
