# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
#   ^ Isaac Lab 의 play.py 복사본이라 원본 저작권 표시를 남긴다.

"""stepping_stones 단독 지형 평가 스크립트.

이 파일은 "시험 조건"을 정한다. 땅은 terrain_cfg.py 가 정한다.

원본은 IsaacLab/scripts/reinforcement_learning/rsl_rl/play.py 다.
원본과 다른 곳은 딱 세 군데다.
  1) 평가 전용 인자 5개    (--command_vx 등)
  2) main() 안의 "평가 조건 고정" 블록 (1)~(6)
  3) 재생 루프 안의 CSV 기록

학습이 아니다. 이미 학습이 끝난 신경망을 불러와 돌려보기만 한다.
가중치는 한 번도 바뀌지 않는다.

Pod 실행:
    cd /workspace/isaaclab && ./isaaclab.sh -p \
        scripts/reinforcement_learning/rsl_rl/play_eval.py \
        --task Isaac-Velocity-Rough-Unitree-Go2-Play-v0 \
        --use_pretrained_checkpoint --num_envs 10 --headless \
        --video --video_length 1000 --command_vx 0.5 \
        --eval_name B1_vx0.5 --out_dir <볼륨>/results
"""

# ============================================================================
# 1부. 시뮬레이터를 켜기 전에 할 일
#
# Isaac Sim 은 특이하다. 시뮬레이터 앱을 먼저 켜지 않으면 isaaclab 관련
# import 가 실패한다. 그래서 파일이 "앱 켜기 전"과 "앱 켠 뒤" 두 덩이로 나뉜다.
# ============================================================================

"""Launch Isaac Sim Simulator first."""

import argparse  # 명령줄 인자(--task, --num_envs 같은 것)를 읽는 표준 라이브러리
import math  # 각도를 라디안으로 바꾸는 데 쓴다 (math.radians)
import os  # 파일 경로 다루기, 환경변수 읽기
import sys  # 파이썬이 모듈을 찾는 경로 목록(sys.path)을 건드리는 데 쓴다

# AppLauncher = Isaac Sim 앱을 켜 주는 도우미. 이것만 앱 켜기 전에 import 할 수 있다.
from isaaclab.app import AppLauncher

# local imports
# cli_args 는 원본 play.py 옆(IsaacLab/scripts/reinforcement_learning/rsl_rl/)에 있는
# 형제 파일이다. 원본은 같은 폴더에 있어서 그냥 import 되지만,
# 이 스크립트는 개인 저장소(sim/eval/)에 있어 그 폴더가 검색 경로에 없다.
# 파일을 복사해 오지 않고 Pod 안 Isaac Lab 의 것을 그대로 쓴다 - 버전이 어긋날 일이 없다.
# ISAACLAB_PATH 는 isaaclab.sh:19 가 export 하므로 파이썬이 물려받는다.
# append = 검색 경로의 맨 뒤에 붙인다. insert(0, ...) 로 앞에 넣으면
# 같은 이름 파일이 양쪽에 있을 때 isaaclab 쪽이 이겨서, 내가 고친 terrain_cfg.py 대신
# 옛날 사본이 잡히는 사고가 난다. 스크립트 자기 폴더가 항상 먼저 오게 뒤에 붙인다.
sys.path.append(
    os.path.join(
        # 환경변수가 있으면 그걸 쓰고, 없으면 Pod 의 기본 위치를 쓴다
        os.environ.get("ISAACLAB_PATH", "/workspace/isaaclab"),
        "scripts/reinforcement_learning/rsl_rl",
    ),
)

# 위에서 경로를 넣었으므로 이제 찾을 수 있다.
# isort: skip = "import 정렬 도구야, 이 줄은 건드리지 마라" 라는 표시.
# 순서가 바뀌면 위 sys.path 조작보다 먼저 실행돼서 실패한다.
import cli_args  # isort: skip

# ---------------------------------------------------------------------------
# 명령줄 인자 정의. 여기 적힌 것만 --옵션 으로 줄 수 있다.
# ---------------------------------------------------------------------------

# add argparse arguments
parser = argparse.ArgumentParser(description="Train an RL agent with RSL-RL.")

# --video 를 붙이면 True. 안 붙이면 False. 영상 녹화 여부.
parser.add_argument("--video", action="store_true", default=False, help="Record videos during training.")
# 영상 길이를 "스텝 수"로 준다. 초가 아니다. 50 Hz 이므로 1000 스텝 = 20초.
parser.add_argument("--video_length", type=int, default=200, help="Length of the recorded video (in steps).")
# Fabric = Isaac Sim 의 빠른 데이터 경로. 끄면 느려지지만 호환성이 올라간다. 보통 안 건드린다.
parser.add_argument(
    "--disable_fabric", action="store_true", default=False, help="Disable fabric and use USD I/O operations."
)
# 동시에 돌릴 로봇 마리 수. 우리는 10.
parser.add_argument("--num_envs", type=int, default=None, help="Number of environments to simulate.")
# 어떤 환경을 쓸지 이름으로 고른다. 예: Isaac-Velocity-Rough-Unitree-Go2-Play-v0
parser.add_argument("--task", type=str, default=None, help="Name of the task.")
# 어떤 학습 알고리즘 설정을 쓸지. 기본값을 그대로 둔다.
parser.add_argument(
    "--agent", type=str, default="rsl_rl_cfg_entry_point", help="Name of the RL agent configuration entry point."
)
# 난수 씨앗. 지형 씨앗(terrain_cfg.py 의 seed)과는 다른 것으로, 환경 전체의 난수다.
parser.add_argument("--seed", type=int, default=None, help="Seed used for the environment")
# NVIDIA 가 배포한 사전학습 모델을 받아서 쓴다. 우리가 학습시킨 게 아니다.
parser.add_argument(
    "--use_pretrained_checkpoint",
    action="store_true",
    help="Use the pre-trained checkpoint from Nucleus.",
)
# 실시간 속도로 돌린다. headless 로 영상만 뽑을 때는 안 쓴다(느려지기만 한다).
parser.add_argument("--real-time", action="store_true", default=False, help="Run in real-time, if possible.")

# --- 여기부터 평가 전용 인자. 원본 play.py 에 없다. ---

# 로봇에게 내릴 전진 속도 [m/s]. 이 값 하나로 A(1.0) / B1(0.5) 이 갈린다.
parser.add_argument("--command_vx", type=float, default=1.0, help="고정 전진 속도 [m/s]. A=1.0 / B1=0.5")
# 에피소드 하나의 길이 [초]. 이 시간이 지나면 time_out 으로 끝난다.
parser.add_argument("--eval_duration", type=float, default=20.0, help="에피소드 길이 [s]. 20 s @ 1.0 m/s = 10 m")
# 결과 CSV 파일 이름 앞에 붙일 꼬리표. 실험마다 다르게 줘야 덮어쓰지 않는다.
# 이름이 run_name 이 아닌 이유: cli_args 가 --run_name 을 이미 쓰고 있어 충돌한다.
parser.add_argument("--eval_name", type=str, default="run", help="결과 파일 접두어")
# 붙이면 지형을 바꾸지 않는다. 태스크 원래 지형(= 학습에 쓴 6종)으로 돌아간다.
# "실패가 정말 지형 때문인가"를 가르는 대조군 실험용.
parser.add_argument(
    "--keep_terrain",
    action="store_true",
    default=False,
    help="지형을 바꾸지 않고 태스크 원래 지형(학습 분포)으로 돌린다. 대조군용",
)
# 붙이면 stepping_stones 대신 평지(FLAT_EVAL_CFG)로 돌린다.
# --keep_terrain 과는 다르다. --keep_terrain 은 "태스크 원래 지형 6종",
# --flat 은 "내가 만든 평지 하나". 둘 다 주면 --keep_terrain 이 이긴다.
parser.add_argument("--flat", action="store_true", default=False,
                    help="지형을 평지(FLAT_EVAL_CFG)로 바꾼다. stepping_stones 대조군용")
# 붙이면 "앞 2 m 평지 -> 그 뒤 징검다리" 지형(RUNUP_STONES_EVAL_CFG)으로 돌린다.
# --flat 과 함께 주면 --mixed 가 이긴다 (평지는 대조군, 이쪽이 본 실험이라서).
# 우선순위: --keep_terrain > --mixed > --flat > (기본) STEPPING_STONES_EVAL_CFG
parser.add_argument("--mixed", action="store_true", default=False,
                    help="평지 조주 2 m 뒤에 징검다리가 나오는 지형(RUNUP_STONES_EVAL_CFG)으로 바꾼다")
# ─── [2026-09-07 추가 M2-1] --mixed8 ────────────────────────────────────────
#   왜: --mixed(=M1) 은 팀 원본에서 platform_width 와 size 를 «동시에» 바꾼 지형이라
#       A2 와 변경점이 둘이다. --mixed8 은 platform_width 하나만 바꾼 지형이라
#       A2 와 변경점이 하나다. 두 스위치를 다 남겨 두는 이유는 M1 데이터를 나중에
#       다시 돌려 재현할 수 있어야 하기 때문이다(옛 스위치를 지우면 재현이 끊긴다).
#   우선순위: --keep_terrain > --mixed8 > --mixed > --flat > (기본)
#   원본에는 이 블록이 없었다.
parser.add_argument("--mixed8", action="store_true", default=False,
                    help="M2 지형(RUNUP8_STONES_EVAL_CFG). 8x8 타일 그대로 + 조주 2 m. "
                         "--mixed 와 달리 팀 원본 대비 변경점이 platform_width 하나뿐이다")
# ─── 여기까지 M2-1 ──────────────────────────────────────────────────────────
# ─── [2026-09-08 추가 G-1] --terrain_cfg ────────────────────────────────────
#   왜: terrain_cfg.py 에 BRIDGE_HS100_GAP10 / GAP_SWEEP_CFGS 를 만들어 뒀지만
#       play_eval.py 에는 그것을 «고르는 스위치가 없었다». --flat/--mixed/--mixed8 은
#       이름이 박힌 세 지형만 부른다. 그래서 틈 스윕을 돌릴 수가 없었다.
#   쓰는 법: --terrain_cfg BRIDGE_HS100_GAP10
#            --terrain_cfg GAP_SWEEP_CFGS:gap025   <- 딕셔너리 안의 항목
#            (terrain_audit.py 의 --cfg 와 «같은 문법»이다. 일부러 맞췄다.)
#   우선순위: --keep_terrain > --terrain_cfg > --mixed8 > --mixed > --flat > (기본)
#   원본에는 이 블록이 없었다.
parser.add_argument("--terrain_cfg", type=str, default=None,
                    help="terrain_cfg.py 안의 생성기 이름을 직접 지정한다. "
                         "'GAP_SWEEP_CFGS:gap025' 처럼 딕셔너리 항목도 된다")
# ─── 여기까지 G-1 ───────────────────────────────────────────────────────────
# 지형 난이도를 한 값으로 못 박는다. 0.0 = 가장 쉬움, 1.0 = 가장 어려움.
# 안 주면(None) terrain_cfg.py 에 적힌 difficulty_range 를 그대로 쓴다(지금은 0.5 고정).
# 🔴 이 축은 horizontal_scale=0.1 에 잘려서 실제로는 5단계밖에 안 생긴다.
#    0.0~0.1 = 틈 0.00 m(돌이 붙어 있음) / 0.2~0.5 = 돌 0.50 m·틈 0.10 m
#    0.6~0.8 = 돌 0.40 m·틈 0.10 m / 0.9 = 돌 0.30 m·틈 0.10 m / 1.0 = 돌 0.30 m·틈 0.20 m
parser.add_argument("--difficulty", type=float, default=None,
                    help="지형 난이도를 이 값 하나로 고정한다 (0.0~1.0). 안 주면 terrain_cfg 값을 쓴다")
# ─── [2026-09-07 수정 E] --out_dir 을 필수로 ──────────────────────────────
#   원본: parser.add_argument("--out_dir", type=str,
#                             default="<볼륨>/runs/results", help="CSV 저장 폴더")
#   🔴 왜 바꾸나: runs/ 폴더는 2026-09-07 에 지웠다("실행 하나 = 폴더 하나" 규칙으로
#      옮기면서). 그런데 기본값이 살아 있으면 --out_dir 을 한 번 빠뜨리는 순간
#      os.makedirs 가 runs/results 를 조용히 되살리고 결과가 거기 쌓인다.
#      에러가 안 난다. 실행 폴더 규칙이 그 자리에서 깨지는데 알아챌 방법이 없다.
#      09-03 의 교훈이 「조용한 실패가 제일 비싸다」였다.
#   required=True 로 두면 안 줬을 때 argparse 가 즉시 죽는다:
#      play_eval.py: error: the following arguments are required: --out_dir
#      기본값이 사라졌으므로 옛 명령줄과 호환이 깨진다 - 그게 의도다.
#      옛 명령은 어차피 없어진 폴더를 가리키고 있어서 지금 그대로 쓰면 안 된다.
parser.add_argument("--out_dir", type=str, required=True,
                    help="🔴 필수. 이 실행 하나의 결과 폴더 (예: <볼륨>/experiments/20260907_heading/A2h_s42)")
# ─── 여기까지 E ────────────────────────────────────────────────────────────
parser.add_argument("--episodes", type=int, default=0,
                    help="env 마다 이 횟수만큼 에피소드를 마치면 끝낸다. 0 이면 안 쓴다(영상 길이로 끝냄)")
# 🔴 --headless 는 여기서 만들면 안 된다.
#    아래 AppLauncher.add_app_launcher_args(parser) 가 이미 만들어 준다.
#    두 번 만들면 argparse 가 "conflicting option string: --headless" 로 즉시 죽는다.
#    --device, --video 도 마찬가지다.

# 월드 +X 방향을 계속 바라보도록 하는 제어를 켠다.
# action="store_true" = 값 없이 --heading 만 쓰면 True. 안 쓰면 False.
# 기본을 False 로 둔 이유: 기존 A2 명령줄이 그대로 재현돼야 비교가 된다.
# ─── [2026-09-07 추가 S-1] 발 접촉 로깅 ──────────────────────────────────────
#   왜: 보폭을 «몸통 z 진동 5 Hz + 트롯 가정» 으로 «유도» 했는데, 그건 가설이다.
#       발이 언제 어디에 닿는지를 직접 찍으면 가정 없이 확정된다.
#   왜 별도 파일인가: 본 CSV 의 열을 늘리면 기존 실행들과 스키마가 달라져
#       summarize.py 와 지금까지의 비교가 전부 깨진다. 옆에 한 장 더 쓴다.
parser.add_argument("--log_feet", action="store_true", default=False,
                    help="발 4개의 위치·접촉을 <eval_name>_feet.csv 에 따로 기록한다")
# ─── 여기까지 S-1 ────────────────────────────────────────────────────────────
parser.add_argument("--heading", action="store_true", default=False,
                    help="월드 +X 방향 유지 제어를 켠다 (학습 때와 같은 조건)")
# 에피소드가 시작되고 이 시간 동안은 명령을 전부 0으로 만들어 제자리에 세운다.
parser.add_argument("--warmup", type=float, default=0.0,
                    help="에피소드 시작 후 이 시간[s] 동안 명령 0으로 제자리 대기")
# 중심선 복귀 P 제어. 기본 0.0 = 끔.
# 켜면 "정책"이 아니라 "정책 + 내가 만든 제어기"를 재게 되므로 주 조건이 아니다.
parser.add_argument("--lateral_kp", type=float, default=0.0,
                    help="0이면 끔. >0이면 중심선 복귀 P 제어 (실험용, 기본 조건 아님)")
parser.add_argument("--lateral_max", type=float, default=0.3,
                    help="복귀 횡속도 상한 [m/s]")

# RSL-RL(학습 라이브러리)이 쓰는 인자들을 통째로 더한다. --checkpoint, --run_name 등이 여기서 온다.
# append RSL-RL cli arguments
cli_args.add_rsl_rl_args(parser)
# Isaac Sim 앱이 쓰는 인자들을 더한다. --headless, --device 등이 여기서 온다.
# append AppLauncher cli args
AppLauncher.add_app_launcher_args(parser)

# parse the arguments
# parse_known_args = 아는 인자만 args_cli 에 담고, 모르는 것은 hydra_args 로 넘긴다.
# Hydra(설정 관리 도구)가 나머지를 받아 처리하기 때문에 parse_args 가 아니다.
args_cli, hydra_args = parser.parse_known_args()

# ─── [2026-09-07 추가 A] 실제로 친 명령줄을 통째로 보관 ────────────────────
#   왜: 조금 아래에서 sys.argv 를 Hydra 몫만 남기고 통째로 덮어쓴다.
#       그래서 main() 안에서 sys.argv 를 읽으면 --heading 도 --eval_name 도
#       이미 사라진 뒤다. manifest.json 의 command 필드는 "한 달 뒤에 이 실행을
#       그대로 재현하는 근거" 이므로, 덮어쓰기 전에 원본을 한 번 떠 둔다.
#   list(...) 로 복사하는 이유: sys.argv 는 리스트라 그냥 대입하면 같은 객체를
#       가리켜, 아래의 덮어쓰기가 이 변수에도 그대로 비친다.
#   원본에는 이 두 줄이 없었다.
_ORIG_ARGV = list(sys.argv)
# ─── 여기까지 A ──────────────────────────────────────────────────────────

# always enable cameras to record video
# 영상을 찍으려면 카메라가 켜져 있어야 한다. --video 를 줬으면 자동으로 켜 준다.
if args_cli.video:
    args_cli.enable_cameras = True

# clear out sys.argv for Hydra
# Hydra 는 sys.argv 를 직접 읽는다. 우리가 이미 소비한 인자를 지우고
# Hydra 몫만 남겨 두지 않으면 "모르는 인자"라고 에러를 낸다.
sys.argv = [sys.argv[0]] + hydra_args

# launch omniverse app
# 여기서 Isaac Sim 이 실제로 켜진다. 이 줄 위로는 isaaclab 관련 import 를 못 한다.
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# ============================================================================
# 2부. 시뮬레이터가 켜진 뒤에야 할 수 있는 import 들
# ============================================================================

"""Rest everything follows."""

import os  # 위에서 이미 import 했지만 원본 구조를 그대로 둔다
import time  # 실시간 모드에서 프레임 간격을 맞추는 데 쓴다

import gymnasium as gym  # 강화학습 환경의 표준 규격(reset/step). Isaac Lab 도 이 규격을 따른다
import torch  # 신경망 연산. 관측/행동이 전부 torch 텐서다

# Runner = 학습 알고리즘을 감싸는 껍데기. 우리는 학습이 아니라 "불러오기"에만 쓴다.
from rsl_rl.runners import DistillationRunner, OnPolicyRunner

from isaaclab.envs import (
    DirectMARLEnv,  # 다중 에이전트 환경 (우리는 안 씀, 아래에서 타입 검사만 함)
    DirectMARLEnvCfg,  # 그 설정 타입
    DirectRLEnvCfg,  # 직접 방식 환경 설정 타입
    ManagerBasedRLEnvCfg,  # 우리가 쓰는 방식. 관측/보상/종료를 "매니저"로 쪼개 관리한다
    multi_agent_to_single_agent,  # 다중->단일 변환기
)
from isaaclab.utils.assets import retrieve_file_path  # 원격 경로의 파일을 받아 로컬 경로로 준다
from isaaclab.utils.dict import print_dict  # 딕셔너리를 보기 좋게 출력

from isaaclab_rl.rsl_rl import (
    RslRlBaseRunnerCfg,  # 러너 설정 타입
    RslRlVecEnvWrapper,  # Isaac Lab 환경을 RSL-RL 이 이해하는 모양으로 감싸는 껍데기
    export_policy_as_jit,  # 정책을 TorchScript(.pt)로 내보내기 - 실기 배포용
    export_policy_as_onnx,  # 정책을 ONNX 로 내보내기 - 실기 배포용
)
from isaaclab_rl.utils.pretrained_checkpoint import get_published_pretrained_checkpoint  # NVIDIA 배포 모델 받기

import isaaclab_tasks  # noqa: F401
#   ^ 직접 쓰지는 않지만 반드시 import 해야 한다. 이 줄이 실행되면서
#     "Isaac-Velocity-Rough-Unitree-Go2-Play-v0" 같은 태스크 이름들이 gym 에 등록된다.
#     noqa: F401 = "안 쓰는 import 라고 경고하지 마라" 라는 표시.
from isaaclab_tasks.utils import get_checkpoint_path  # logs/ 폴더에서 최신 체크포인트 찾기
from isaaclab_tasks.utils.hydra import hydra_task_config  # 태스크 이름 -> 설정 객체 자동 연결

# PLACEHOLDER: Extension template (do not remove this comment)


# @hydra_task_config = 이 데코레이터가 --task 이름을 보고 알맞은 설정 객체를 만들어
# main() 의 인자로 넣어 준다. 이 시점에 env_cfg 의 __post_init__ 이 이미 다 끝나 있다.
# 그래서 아래 (1) 블록에서 넣는 지형 설정이 덮어써지지 않는다.
@hydra_task_config(args_cli.task, args_cli.agent)
def main(env_cfg: ManagerBasedRLEnvCfg | DirectRLEnvCfg | DirectMARLEnvCfg, agent_cfg: RslRlBaseRunnerCfg):
    """Play with RSL-RL agent."""
    # grab task name for checkpoint path
    # "namespace:Isaac-..." 형태로 올 수 있어 콜론 뒤만 남긴다.
    task_name = args_cli.task.split(":")[-1]
    # 체크포인트는 학습용 이름으로 저장돼 있다. "-Play" 를 떼서 학습 이름을 만든다.
    # 예: Isaac-Velocity-Rough-Unitree-Go2-Play-v0 -> Isaac-Velocity-Rough-Unitree-Go2-v0
    train_task_name = task_name.replace("-Play", "")

    # override configurations with non-hydra CLI arguments
    # 명령줄로 준 값들(--device, --checkpoint 등)을 학습 설정에 반영한다.
    agent_cfg: RslRlBaseRunnerCfg = cli_args.update_rsl_rl_cfg(agent_cfg, args_cli)
    # --num_envs 를 줬으면 그 값을, 안 줬으면 설정에 들어 있던 기본값을 쓴다.
    env_cfg.scene.num_envs = args_cli.num_envs if args_cli.num_envs is not None else env_cfg.scene.num_envs

    # set the environment seed
    # note: certain randomizations occur in the environment initialization so we set the seed here
    # 환경 초기화 중에 난수를 쓰는 곳이 있어서 씨앗을 여기서 못 박는다.
    env_cfg.seed = agent_cfg.seed
    # 계산 장치. --device 를 줬으면 그것, 아니면 설정 기본값(보통 cuda:0).
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    # ========================================================================
    # 여기부터 평가 조건 고정. 원본 play.py 에 없는 블록이다.
    #
    # 반드시 아래 gym.make() 보다 위에 있어야 한다.
    # gym.make 가 env_cfg 를 읽어서 환경을 만들기 때문에,
    # 그 뒤에 env_cfg 를 고쳐 봐야 이미 만들어진 환경에는 반영되지 않는다.
    # ========================================================================

    # ---- (1) 지형 교체 ----
    # --keep_terrain 을 안 줬을 때만 우리 지형으로 바꾼다.
    if not args_cli.keep_terrain:
        # terrain_cfg.py 는 이 파일과 같은 폴더에 있다.
        # 파이썬은 실행하는 스크립트의 폴더를 검색 경로 맨 앞에 자동으로 넣으므로
        # 패키지(__init__.py)를 만들지 않아도 이렇게 부를 수 있다.
        # 함수 안에서 import 하는 이유: --keep_terrain 일 때는 아예 안 읽히게 하려고.
        # ─── [2026-09-07 수정 M2-2] --mixed8 가지를 맨 앞에 추가 ─────────
        #   원본: if args_cli.mixed: ... 로 시작했다.
        #   --mixed8 을 --mixed 보다 «앞» 에 두는 이유: 둘 다 주는 실수를 했을 때
        #   변경점이 하나뿐인 쪽(M2)이 이기는 게 안전하다.
        # ─── [2026-09-08 추가 G-2] --terrain_cfg 를 맨 앞 가지로 ──────────
        #   왜: 이름을 «직접» 준 것이 가장 구체적인 지시다. 다른 스위치와 같이
        #   줬을 때 이쪽이 이겨야 놀라는 일이 없다.
        #   원본에는 이 가지가 없었다.
        if args_cli.terrain_cfg:
            import terrain_cfg as _tc
            if ":" in args_cli.terrain_cfg:
                _dname, _key = args_cli.terrain_cfg.split(":", 1)
                _EVAL_TERRAIN = getattr(_tc, _dname)[_key]
            else:
                _EVAL_TERRAIN = getattr(_tc, args_cli.terrain_cfg)
        # ─── 여기까지 G-2 ──────────────────────────────────────────────────
        elif args_cli.mixed8:
            from terrain_cfg import RUNUP8_STONES_EVAL_CFG as _EVAL_TERRAIN
        elif args_cli.mixed:
            from terrain_cfg import RUNUP_STONES_EVAL_CFG as _EVAL_TERRAIN
        # ─── 여기까지 M2-2 ────────────────────────────────────────────────
        elif args_cli.flat:
            from terrain_cfg import FLAT_EVAL_CFG as _EVAL_TERRAIN
        else:
            from terrain_cfg import STEPPING_STONES_EVAL_CFG as _EVAL_TERRAIN

        # --difficulty 를 줬으면 난이도를 그 값 하나로 못 박는다.
        # (lo, hi) 를 같은 값으로 두면 타일 전부가 그 난이도가 된다.
        # 아래 [EVAL] 줄에 difficulty=(값, 값) 으로 찍히는지 반드시 눈으로 확인한다.
        if args_cli.difficulty is not None:
            _EVAL_TERRAIN.difficulty_range = (args_cli.difficulty, args_cli.difficulty)

        # 태스크가 원래 쓰던 지형(6종 섞인 것)을 통째로 우리 것으로 바꿔 끼운다.
        env_cfg.scene.terrain.terrain_generator = _EVAL_TERRAIN

    # ---- (2) PLAY 설정이 꺼 놓은 것 되돌리기 ----
    # -Play 태스크는 rough_env_cfg.py:74-79 에서 max_init_terrain_level 을 None 으로 둔다.
    # None 이면 로봇을 아무 난이도 행에나 뿌린다. 우리는 0행 하나뿐이라 0 으로 못 박는다.
    env_cfg.scene.terrain.max_init_terrain_level = 0
    # 커리큘럼 항목이 있으면 끈다. 평가 중에 난이도가 오르내리면 조건이 흔들린다.
    # hasattr = "그 속성이 있는지" 검사. 태스크에 따라 없을 수도 있어 먼저 확인한다.
    if hasattr(env_cfg.curriculum, "terrain_levels"):
        env_cfg.curriculum.terrain_levels = None

    # ---- (3) 명령 고정 ----
    # 정책은 "명령을 따르는" 모델이다. 명령 [vx, vy, wz] 3개가 관측 235개 중에 들어간다.
    # 기본값은 매 에피소드 -1.0~1.0 에서 무작위로 뽑는다. 그대로 두면
    # 10마리가 제각각 다른 속도로, 일부는 뒤로, 일부는 서 있게 된다.
    cmd = env_cfg.commands.base_velocity  # 길어서 짧은 이름에 담아 둔다 (같은 객체를 가리킨다)
    # 전진 속도. (a, b) 는 "a 이상 b 이하에서 뽑는다"는 뜻이라 a == b 면 고정이 된다.
    cmd.ranges.lin_vel_x = (args_cli.command_vx, args_cli.command_vx)
    # 옆걸음 금지
    cmd.ranges.lin_vel_y = (0.0, 0.0)
    # ---- 회전 명령: 두 설정이 반드시 한 세트다 ----
    # velocity_command.py:154-158 을 보면 heading_command 가 켜졌을 때
    #     vel_command_b[:,2] = clip(stiffness * 방향오차, ang_vel_z[0], ang_vel_z[1])
    # 즉 ang_vel_z 는 "뽑는 범위" 가 아니라 "잘라내는 범위" 로 재사용된다.
    #   - heading ON  + ang_vel_z=(0,0)   -> 방향 보정이 항상 0 으로 잘려 제어가 안 먹는다
    #   - heading OFF + ang_vel_z=(-1,1)  -> 무작위 회전 명령이 되어 로봇이 제멋대로 돈다
    # 그래서 둘을 따로 두지 않고 항상 같이 바꾼다.
    if args_cli.heading:
        # 학습 때와 같은 조건. 학습은 rel_heading_envs=1.0 으로 돌았다.
        cmd.heading_command = True
        cmd.rel_heading_envs = 1.0            # 전원에게 적용
        cmd.heading_control_stiffness = 0.5   # 방향오차 -> 회전명령 변환 이득 (평지 검증값)
        cmd.ranges.heading = (0.0, 0.0)       # 목표 방향 = 월드 +X. heading_w 가 월드 기준이다
        cmd.ranges.ang_vel_z = (-1.0, 1.0)    # ★ 보정이 잘리지 않게 풀어 준다
    else:
        # 기존 A2 조건. 회전 명령이 영구히 0 이라 방향 피드백이 없다.
        cmd.heading_command = False
        cmd.rel_heading_envs = 0.0
        cmd.ranges.ang_vel_z = (0.0, 0.0)
    # "가만히 서 있어" 명령을 받을 env 비율. 기본 0.02(2%). 0으로 만들어 전원 전진시킨다.
    cmd.rel_standing_envs = 0.0

    # ---- (4) 외란 제거 ----
    # 학습 때는 일부러 흔들어서 튼튼하게 만든다. 평가 때는 방해물이다.
    # 켜 두면 로봇이 넘어졌을 때 지형 탓인지 밀쳐진 탓인지 구분할 수 없다.
    # 정책이 보는 관측값에 잡음을 섞는 기능. 끈다.
    env_cfg.observations.policy.enable_corruption = False
    # 10~15초마다 로봇 속도를 ±0.5 m/s 만큼 밀어 버리는 기능. 없앤다.
    if hasattr(env_cfg.events, "push_robot"):
        env_cfg.events.push_robot = None
    # 리셋할 때 몸통에 무작위 힘/토크를 거는 기능. 없앤다.
    if hasattr(env_cfg.events, "base_external_force_torque"):
        env_cfg.events.base_external_force_torque = None

    # ---- (4a) 출발 자세 고정 ----
    # 이게 없으면 10마리가 사방으로 흩어진다.
    # 명령 lin_vel_x 는 "월드 기준 +x" 가 아니라 "로봇 몸 기준 앞" 이다.
    # 기본 reset_base 는 yaw 를 -3.14~3.14(=-180~180도)로 뽑으므로
    # 전부 "앞으로" 가지만 월드에서 보면 제각각 방향이 된다.
    # 초기 속도도 6축 ±0.5 로 흔들어 놓기 때문에 출발부터 떠밀린다.
    # 값은 팀 정본과 동일 (benchmark-setup-lim.md:371-373, 463-491).
    _SPAWN_XY = 0.10  # 출발 위치가 흔들릴 폭 [m]. 0 이 아닌 이유는 아래 참고.
    _YAW = math.radians(5.0)  # 출발 방향이 흔들릴 폭. 5도를 라디안으로 바꾼다.
    _JOINT_SCALE = 0.05  # 관절 초기 각도가 기본 자세에서 흔들릴 비율 (±5%)
    # 완전히 0 으로 만들지 않는 것은 팀 선택이다. 10마리가 완벽한 복제품이면
    # 실험이 아니라 같은 것을 10번 그린 것이 된다.

    # reset_base 라는 이벤트가 있으면 그 파라미터를 덮어쓴다.
    # getattr(..., None) = 없으면 None 을 돌려줘라. 태스크마다 다를 수 있어 방어한다.
    if getattr(env_cfg.events, "reset_base", None) is not None:
        # 몸통을 어디에, 어느 방향으로 놓을지
        env_cfg.events.reset_base.params["pose_range"] = {
            "x": (-_SPAWN_XY, _SPAWN_XY),  # 앞뒤로 ±0.10 m
            "y": (-_SPAWN_XY, _SPAWN_XY),  # 좌우로 ±0.10 m
            "yaw": (-_YAW, _YAW),  # 방향은 ±5도만
        }
        # 출발 순간에 줄 속도. 전부 0 = 완전히 정지 상태에서 시작.
        env_cfg.events.reset_base.params["velocity_range"] = {
            "x": (0.0, 0.0),
            "y": (0.0, 0.0),
            "z": (0.0, 0.0),
            "roll": (0.0, 0.0),
            "pitch": (0.0, 0.0),
            "yaw": (0.0, 0.0),
        }

    # 관절(다리)의 출발 상태도 같은 이유로 좁힌다.
    if getattr(env_cfg.events, "reset_robot_joints", None) is not None:
        # 기본 자세 각도에 곱할 배율. 0.95 ~ 1.05 사이에서 뽑는다.
        env_cfg.events.reset_robot_joints.params["position_range"] = (1.0 - _JOINT_SCALE, 1.0 + _JOINT_SCALE)
        # 관절 초기 속도. 0 = 다리가 멈춘 상태에서 시작.
        env_cfg.events.reset_robot_joints.params["velocity_range"] = (0.0, 0.0)

    # ---- (5) 에피소드 길이 ----
    # 이 시간이 지나면 time_out 으로 끝나고 로봇이 출발점으로 되돌아간다.
    # warmup 은 측정 시간에서 빼는 게 아니라 앞에 붙인다.
    # 안 그러면 실제로 걷는 시간이 줄어 A2 와 비교가 깨진다.
    # args_cli. 을 빼면 NameError 가 난다 (파이썬은 인자를 전역 변수로 만들지 않는다).
    env_cfg.episode_length_s = args_cli.eval_duration + args_cli.warmup

    # ---- (6) 카메라가 0번 로봇을 따라가게 ----
    # 기본은 고정 시점이라 로봇이 걸어가면 화면 밖으로 나간다.
    env_cfg.viewer.origin_type = "asset_root"  # 특정 물체를 기준으로 카메라를 놓는다
    env_cfg.viewer.asset_name = "robot"  # 그 물체는 로봇
    env_cfg.viewer.env_index = 0  # 10마리 중 0번만 따라간다 (영상에는 0번만 나온다)
    env_cfg.viewer.eye = (-3.0, 2.0, 1.5)  # 카메라 위치: 뒤 3 m, 옆 2 m, 위 1.5 m
    env_cfg.viewer.lookat = (0.0, 0.0, 0.4)  # 바라보는 지점: 로봇 몸통 높이쯤

    # 설정이 제대로 먹었는지 한 줄로 찍는다. 실행하자마자 눈으로 확인할 수 있다.
    # terrain=1x10, curriculum=True 가 아니면 PLAY 설정이 이긴 것이다.
    _tg = env_cfg.scene.terrain.terrain_generator
    print(
        f"[EVAL] vx={args_cli.command_vx} m/s  duration={args_cli.eval_duration} s  "
        f"terrain={_tg.num_rows}x{_tg.num_cols}  size={_tg.size}  curriculum={_tg.curriculum}  "
        f"difficulty={_tg.difficulty_range}  sub={list(_tg.sub_terrains)}"
    )

    # ---- 평지/험지 경계 x 좌표를 계산해서 찍는다 ----
    #
    # 왜 필요한가: CSV 의 x 는 "출발 타일 원점 기준" 위치다. 조주 지형에서
    # "험지에 들어간 뒤 몇 m 에서 넘어졌나"를 세려면 경계 x 를 알아야 한다.
    # 그 값을 README 에 손으로 적어 두면 platform_width 를 고쳤을 때 같이 안 따라온다.
    # 그래서 지형 설정에서 매번 다시 계산해 로그에 남긴다.
    #
    # 근거 두 곳:
    #   hf_terrains.py:431-435  판(platform)을 지형 격자 정중앙에 놓는다
    #   height_field/utils.py:44-58  격자는 sub 지형 border_width 만큼 안으로 밀려 있다
    # 높이지도(Hf...) 계열 지형에만 platform 이 있다. 평지(Mesh...)는 없으므로 건너뛴다.
    # ─── [2026-09-07 추가 B0] 경계 변수를 두 갈래 앞에서 먼저 만들어 둔다 ────
    #   왜: 아래 if 가 참일 때만 _boundary_x 가 생긴다. 평지(--flat)는 platform 이
    #       없어 else 로 빠지고, 그러면 _boundary_x 라는 이름 자체가 안 만들어진다.
    #       manifest 를 쓰는 곳(수정 B)에서 그 이름을 읽으면 NameError 로 죽는다.
    #       미리 None 으로 만들어 두면 "경계가 없다" 가 값으로 표현된다.
    #   _end_x 는 지형 종류와 무관하게 항상 같은 식이라 여기서 한 번에 정한다.
    #       (아래 if 안의 같은 대입은 그대로 뒀다 - 같은 값이라 지워도 되지만
    #        원본 줄을 안 건드리는 쪽을 택했다.)
    _end_x = 0.5 * _tg.size[0]  # 타일이 끝나는 x [m]. 그 뒤는 border_width 평지다
    _boundary_x = None  # 평지가 끝나고 험지가 시작하는 x [m]. platform 이 없으면 None
    # ─── 여기까지 B0 ────────────────────────────────────────────────────────
    _sub = next(iter(_tg.sub_terrains.values()))
    _pw = getattr(_sub, "platform_width", None)
    if _pw is not None and hasattr(_sub, "holes_depth"):
        _hs = _tg.horizontal_scale
        _bpx = int(_sub.border_width / _hs) + 1     # 안쪽으로 밀린 테두리 [픽셀]
        _wpx = int(_tg.size[0] / _hs) + 1           # 타일 전체 [픽셀]
        _spx = _wpx - 2 * _bpx                      # 지형이 실제로 그려지는 폭 [픽셀]
        _ppx = int(_pw / _hs)                       # 평평한 판 [픽셀]
        # 판의 "앞쪽 끝" 픽셀 -> m 로 바꾸고, 출발점(타일 중심 = size[0]/2)을 뺀다
        _boundary_x = (_bpx + (_spx + _ppx) // 2) * _hs - 0.5 * _tg.size[0]
        # 험지가 끝나는 곳. 그 뒤는 border_width 20 m 의 평지라 측정 의미가 없다
        _end_x = 0.5 * _tg.size[0]
        print(
            f"[EVAL] platform_width={_pw} m  ->  평지 구간 x < {_boundary_x:+.2f} m,  "
            f"징검다리 구간 {_boundary_x:+.2f} ~ {_end_x:+.2f} m (길이 {_end_x - _boundary_x:.2f} m)"
        )
        print(
            f"[EVAL] CSV 의 x 는 출발 타일 원점 기준. '험지 진입 후 거리' = x - {_boundary_x:.2f}"
        )
    else:
        print("[EVAL] 이 지형에는 platform 이 없다(평지 계열). 경계 x 없음.")
    # ---- 평가 조건 고정 끝 ----

    # ========================================================================
    # 3부. 학습된 모델을 찾아서 불러온다
    # ========================================================================

    # specify directory for logging experiments
    # 우리가 직접 학습시킨 경우 체크포인트가 이 폴더 밑에 쌓인다.
    log_root_path = os.path.join("logs", "rsl_rl", agent_cfg.experiment_name)
    # 상대경로를 절대경로로 바꾼다. cd 한 위치에 따라 달라지는 것을 막는다.
    log_root_path = os.path.abspath(log_root_path)
    print(f"[INFO] Loading experiment from directory: {log_root_path}")

    # 모델을 어디서 가져올지 세 갈래로 나뉜다.
    if args_cli.use_pretrained_checkpoint:
        # (가) NVIDIA 가 배포한 사전학습 모델을 받는다. 우리가 지금 쓰는 길이다.
        resume_path = get_published_pretrained_checkpoint("rsl_rl", train_task_name)
        if not resume_path:
            print("[INFO] Unfortunately a pre-trained checkpoint is currently unavailable for this task.")
            return  # 없으면 여기서 함수를 끝낸다
    elif args_cli.checkpoint:
        # (나) --checkpoint 로 파일을 직접 지정한 경우. 팀원 모델을 쓸 때 이 길이다.
        resume_path = retrieve_file_path(args_cli.checkpoint)
    else:
        # (다) 아무것도 안 줬으면 logs/ 에서 가장 최근 것을 찾는다.
        # 🔴 /data 는 팀 공용이다. 팀원이 학습을 돌리면 여기에 model_1.pt(1 iteration =
        #    사실상 학습 안 된 모델)가 생기고, 그게 "가장 최근" 이 되어 조용히 선택된다.
        #    그러면 로봇이 제자리에 서 있기만 하는데 에러는 안 난다. 2026-09-03 에 실제로 겪었다.
        resume_path = get_checkpoint_path(log_root_path, agent_cfg.load_run, agent_cfg.load_checkpoint)
        print("🔴 [EVAL] --use_pretrained_checkpoint 도 --checkpoint 도 안 줬습니다. "
              f"logs/ 의 최신 파일을 씁니다 -> {resume_path}\n"
              "         평가 실험이라면 거의 확실히 --use_pretrained_checkpoint 를 빠뜨린 것입니다.")

    # 체크포인트 파일이 든 폴더. 영상도 이 아래에 떨어진다.
    log_dir = os.path.dirname(resume_path)

    # set the log directory for the environment (works for all environment types)
    env_cfg.log_dir = log_dir

    # ─── [2026-09-07 추가 B] manifest.json 기록 ─────────────────────────────
    #   왜: 결과 폴더가 스스로를 설명하지 않으면 일주일 뒤에 그 CSV 는
    #       "무슨 조건인지 모르는 숫자 더미" 가 된다 (위키 05 · R-0q 원칙 4).
    #       조건을 내 기억이나 터미널 스크롤백에 두면 그날 저녁이면 사라진다.
    #
    #   왜 하필 이 자리인가 - 두 가지 이유로 여기가 유일한 자리다.
    #     (1) resume_path 가 바로 위(3부)에서 막 정해졌다. 이보다 위에 두면
    #         "어느 체크포인트를 썼나" 를 못 적는다. 그게 09-03 사고의 핵심이었다.
    #     (2) 바로 아래 gym.make() 는 Isaac Sim 세계를 짓느라 1~2분이 걸린다.
    #         manifest 작성이 실패한다면 그 1~2분을 쓰기 전에 죽는 게 낫다.
    #
    #   🔴 원본에는 이 블록이 없었다. 지금까지는 손으로 만들어 넣는 절차뿐이었다.
    # -----------------------------------------------------------------------
    import hashlib  # 파일 내용을 64자리 지문으로 줄인다. 이름이 아니라 내용으로 증명한다
    import json  # manifest 를 JSON 한 장으로 쓴다
    from datetime import datetime, timezone  # 실행 시각을 UTC 로 남긴다

    def _sha256(path):
        """파일 하나의 SHA256 지문을 문자열로 돌려준다. 못 읽으면 None."""
        # 왜 통째로 read() 하지 않나: .pt 가 수십 MB 라 한 번에 메모리에 올릴 이유가 없다.
        # 1 MB 씩 끊어 읽으며 해시를 갱신한다.
        try:
            h = hashlib.sha256()
            with open(path, "rb") as _f:
                for _chunk in iter(lambda: _f.read(1 << 20), b""):
                    h.update(_chunk)
            return h.hexdigest()
        except OSError:
            # 파일이 없거나 못 읽어도 실행 자체를 죽이지 않는다.
            # manifest 는 기록용이지 실행 조건이 아니다.
            return None

    def _pair(v):
        """(a, b) 같은 짝을 JSON 이 담을 수 있는 리스트로 바꾼다. 짝이 아니면 None."""
        # 🔴 이게 필요한 이유: commands_cfg.py:75 의 ranges.heading 은 기본값이 None 이다.
        #    --heading 을 안 주면 우리 코드가 그 값을 설정하지 않으므로 None 인 채로 온다.
        #    그대로 list(None) 을 부르면 TypeError 로 실행이 통째로 죽는다.
        #    resampling_time_range 도 설정에 따라 MISSING 센티넬일 수 있어 같이 막는다.
        return list(v) if isinstance(v, (tuple, list)) else None

    def _sub_to_dict(v):
        """sub_terrain 설정 객체 하나를 JSON 에 담을 수 있는 dict 로 편다."""
        # to_dict() 는 Isaac Lab 의 @configclass 가 모든 설정 객체에 붙여 주는 메서드다
        # (isaaclab/utils/configclass.py:98). holes_depth 같은 값을 통째로 펼쳐 준다.
        return v.to_dict() if hasattr(v, "to_dict") else str(v)

    # ---- 낙상 판정 조건 ----
    # 왜 적나: "무엇을 낙상으로 세는가" 가 다르면 낙상률 숫자는 비교가 안 된다.
    # 값의 출처는 velocity_env_cfg.py:270-273 의 base_contact 종료항이다.
    _mf_term = getattr(getattr(env_cfg, "terminations", None), "base_contact", None)
    _mf_term_params = (getattr(_mf_term, "params", None) or {}) if _mf_term is not None else {}
    _mf_term_sensor = _mf_term_params.get("sensor_cfg")

    # ─── [2026-09-07 추가 M2-5] 실제로 등록된 종료 조건 «전부» ────────────────
    #   왜: codex 검토 결론으로 M2 는 A2/M1 과 termination 이 완전히 같아야 한다
    #       (정체 종료 term_stall 은 M2 뒤로 미룬다). 그 사실을 manifest 가 스스로
    #       증명해야 한다.
    #   왜 "term_stall": false 를 «안» 쓰나: 그건 사람이 손으로 적는 주장이라
    #       나중에 조건이 늘어도 false 로 남는다. 등록된 항목 목록을 그대로 적으면
    #       term_stall 이 없다는 사실이 목록에 term_stall 이 «없음» 으로 나온다.
    #   try/except 인 이유: manifest 는 기록용이다. 여기서 죽으면 GPU 시간을 버린다.
    try:
        _mf_terms_active = sorted(k for k, v in vars(env_cfg.terminations).items() if v is not None)
    except Exception as _e:  # noqa: BLE001  기록 실패가 실행을 막으면 안 된다
        _mf_terms_active = f"<unavailable: {_e}>"
    # ─── 여기까지 M2-5 ────────────────────────────────────────────────────────

    # ---- 매 실행 폴더에 한 장 ----
    # os.makedirs 를 여기서 한 번 더 부르는 이유: 아래 5부의 makedirs 는 이 블록보다
    # 한참 뒤에 있다. 여기서 먼저 폴더를 만들어야 manifest 를 쓸 수 있다.
    # exist_ok=True 라 두 번 불러도 에러가 안 난다.
    os.makedirs(args_cli.out_dir, exist_ok=True)
    _manifest_path = os.path.join(args_cli.out_dir, "manifest.json")

    def _write_manifest(status):
        """manifest.json 을 status 만 바꿔 두 번 쓴다.

        왜 두 번인가: 시작 시점에 'started' 로 한 장 남겨 두면, 실행이 중간에
        죽어도 "무슨 조건으로 돌리려다 죽었는지" 가 폴더에 남는다.
        끝까지 갔을 때만 'completed' 로 덮어쓴다. 그래서 나중에 폴더 목록만 봐도
        "완주한 실행" 과 "죽은 실행" 이 갈린다. 이게 없으면 둘이 똑같이 생겼다.
        """
        _m = {
            # 스키마 이름과 판. 나중에 필드를 늘렸을 때 "이건 v1 로 쓴 것" 을 가른다.
            "schema": "foothold-eval-manifest/1",
            # 이 실행의 짧은 이름. --eval_name 이 그대로 CSV 접두어이자 run_id 다.
            "run_id": args_cli.eval_name,
            # 평가인지 학습인지. 이 스크립트는 평가 전용이라 고정값이다.
            "kind": "eval",
            # 이 실행이 속한 질문 폴더 이름 (예: 20260907_heading).
            # out_dir 이 .../<질문폴더>/<run_id>_s<seed> 라는 규칙(위키 R-0q)에서
            # 한 칸 위 폴더 이름을 떼어 온다. normpath 는 끝의 / 를 정리한다.
            "question_dir": os.path.basename(os.path.dirname(os.path.normpath(args_cli.out_dir))),
            # 🔴 null 인 이유: "이 실행으로 무엇을 알아내려 하는가" 는 사람의 문장이다.
            #    코드가 아는 값이 아니므로 지어내지 않는다. 돌린 뒤 손으로 한 줄 적는다.
            "question": None,
            # 🔴 null 인 이유: Pod 안에서는 계정이 항상 root 다. os.environ["USER"] 를
            #    쓰면 전부 "root" 로 적혀 소유자 정보가 되지 못한다. 손으로 적는다.
            "owner": None,
            # 실행 시각. UTC 로 남긴다 - 한국 시간으로 적으면 나중에 로그와 대조할 때
            # 9시간을 매번 더하고 빼야 한다.
            "created_at_utc": datetime.now(timezone.utc).isoformat(),

            # ---- 체크포인트: 09-03 사고를 막는 자물쇠 ----
            "checkpoint": {
                # 실제로 불러온 .pt 의 절대경로. 3부에서 세 갈래 중 하나로 정해졌다.
                "path": resume_path,
                # 🔴 이 한 줄이 핵심이다. 이름이 같아도 내용이 다르면 지문이 다르다.
                #    "팀원의 model_1.pt 를 조용히 집었다" 를 사후에 잡아낼 유일한 근거.
                "sha256": _sha256(resume_path),
                # 어느 갈래로 정해졌나. 셋 중 마지막(logs_latest_UNPINNED)은 위험 표시다.
                "source": (
                    "pretrained_resolver"  # --use_pretrained_checkpoint. 0단계 pin 때만 쓴다
                    if args_cli.use_pretrained_checkpoint
                    else "cli_absolute"  # --checkpoint <절대경로>. 평소에는 이것이어야 한다
                    if args_cli.checkpoint
                    else "logs_latest_UNPINNED"  # 🔴 아무것도 안 줌. logs/ 최신을 집었다
                ),
            },

            # ---- 코드 버전 ----
            # 왜 해시인가: /data 에는 git 이 없다. 커밋 해시가 없으므로
            # 파일 내용의 지문이 유일한 버전 표식이다 (위키 R-0q 표 마지막 줄).
            "code": {
                "play_eval_py_sha256": _sha256(os.path.abspath(__file__)),
                # terrain_cfg.py 는 이 파일과 같은 폴더에 있다.
                "terrain_cfg_py_sha256": _sha256(
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "terrain_cfg.py")
                ),
                # 🔴 null 인 이유: Isaac Lab 커밋 해시를 얻으려면 .git 이 있어야 하는데
                #    Pod 의 <볼륨>/isaaclab 은 git 저장소가 아니다. 템플릿 이름
                #    (IsaacLab-2.3.2-Go2) 이 사실상의 버전 표식이고 그건 코드가 모른다.
                "isaaclab_commit": None,
            },

            # ---- 실제로 친 명령 ----
            "command": {
                # 수정 A 에서 떠 둔 원본. 이게 없으면 Hydra 가 sys.argv 를 지운 뒤라
                # --heading 을 줬는지조차 남지 않는다.
                "argv": _ORIG_ARGV,
                # 어느 폴더에서 쳤나. isaaclab.sh 는 자기 위치 기준으로 파이썬을 찾으므로
                # cwd 가 다르면 아예 안 돈다. 재현할 때 필요한 값이다.
                "cwd": os.getcwd(),
            },

            # ---- 지형 ----
            "terrain": {
                # 어느 스위치로 지형이 정해졌나. [EVAL] 로그 줄과 교차 검증하는 값이다.
                # 우선순위는 인자 정의부 주석과 같다: keep_terrain > mixed > flat > 기본
                "switch": (
                    "keep_terrain"
                    if args_cli.keep_terrain
                    # ─── [2026-09-08 추가 G-3] --terrain_cfg 를 기록에 남긴다 ──
                    #   왜: 이 문자열이 없으면 manifest 만 보고 gap025 실행과
                    #   gap050 실행을 구분할 수 없다. 둘 다 "stepping_stones" 로 찍힌다.
                    #   원본에는 이 가지가 없었다.
                    else "terrain_cfg:" + str(args_cli.terrain_cfg)
                    if args_cli.terrain_cfg
                    # ─── 여기까지 G-3 ───────────────────────────────────────
                    # ─── [2026-09-07 추가 M2-3] mixed8 을 기록에 남긴다 ─────
                    #   왜: 이 문자열이 없으면 manifest 만 보고 M1 과 M2 를 구분할 수
                    #   없다. 두 실험은 runup_x_m 이 2.0 으로 같아서 그 값으로도 못 가른다.
                    #   가르는 것은 boundary_x_m(4.0 vs 8.0)뿐인데, 그건 간접 증거다.
                    else "mixed8"  # RUNUP8_STONES_EVAL_CFG. 8x8 타일 + 조주 2 m
                    if args_cli.mixed8
                    # ─── 여기까지 M2-3 ──────────────────────────────────────
                    else "mixed"  # RUNUP_STONES_EVAL_CFG. 앞 2 m 평지 + 뒤 6 m 징검다리
                    if args_cli.mixed
                    else "flat"
                    if args_cli.flat
                    else "stepping_stones"
                ),
                # 🔴 여기 값들이 없으면 A2h ↔ F1h ↔ M1h 비교가 깨진다 (위키 08 · D-2 ①).
                #    "통과선이 4 m 인지 8 m 인지 20 m 인지" 를 모른 채 숫자만 나란히 놓게 된다.
                "resolved": {
                    # 통과선 [m]. 타일이 끝나는 x. 로봇은 타일 한복판에서 출발하므로
                    # size[0]/2 다. 징검다리 8x8 -> 4.0 / 조주 16x16 -> 8.0 / 평지 40x16 -> 20.0.
                    # summarize.py 의 --pass_x 에 그대로 넣는 값이다.
                    "boundary_x_m": _end_x,
                    # 평지 조주가 끝나고 험지가 시작하는 x [m].
                    # 위 B0 ~ [EVAL] 경계 계산 블록이 platform_width 에서 실제로 계산한 값이다
                    # (hf_terrains.py:431-435 근거). platform 이 없는 평지 지형은 null.
                    # summarize.py 의 --runup 에 그대로 넣는 값이다.
                    "runup_x_m": _boundary_x,
                    # 실제로 험지가 깔린 길이 [m]. 조주가 있으면 통과선 - 조주선.
                    # 🔴 A2h(4.00 m) 와 M1h(6.xx m) 의 "험지 길이" 가 다르다는 사실이
                    #    이 한 줄에 남는다. 없으면 낙상률을 같은 표에 놓는 순간 비교가 깨진다.
                    "usable_terrain_len_m": (_end_x - _boundary_x) if _boundary_x is not None else _end_x,
                    # 험지 판정에 쓴 평평한 판의 한 변 [m]. 조주 구간의 길이를 결정한다.
                    "platform_width_m": _pw,
                },
                # 타일 크기 [m]. (8,8) 징검다리 / (16,16) 조주 / (40,16) 평지.
                "size": _pair(getattr(_tg, "size", None)),
                "num_rows": getattr(_tg, "num_rows", None),
                "num_cols": getattr(_tg, "num_cols", None),
                "curriculum": getattr(_tg, "curriculum", None),
                # --difficulty 를 줬으면 (값, 값) 으로 못 박혀 있다. 안 줬으면 cfg 원래 값.
                "difficulty_range": _pair(getattr(_tg, "difficulty_range", None)),
                # --difficulty 로 덮어썼는지 여부. 위 difficulty_range 만 봐서는
                # "cfg 가 원래 (0.5,0.5)" 인지 "내가 0.5 로 못 박았는지" 가 안 갈린다.
                "difficulty_override": args_cli.difficulty,
                "border_width": getattr(_tg, "border_width", None),
                "horizontal_scale": getattr(_tg, "horizontal_scale", None),
                # 🔴 돌 배치 난수 시드. 아래 episode.env_seed 와 다른 값이다.
                #    terrain_cfg.py 의 세 지형 모두 seed=42 로 못 박혀 있다.
                #    None 이 나오면 --keep_terrain 으로 태스크 원래 지형을 쓴 것이고,
                #    그러면 실행마다 돌 배치가 달라진다.
                "terrain_seed": getattr(_tg, "seed", None),
                # holes_depth · stone_distance_range 같은 값을 통째로 편다.
                # 이걸 안 적으면 "돌 간격을 바꾼 뒤의 런" 과 "그 전 런" 이 구별되지 않는다.
                "sub_terrains": {k: _sub_to_dict(v) for k, v in _tg.sub_terrains.items()},
            },

            # ---- 명령(속도·방향) 설정 ----
            # 🔴 heading 세 값은 한 세트다. 하나만 적으면 재현이 안 된다.
            #    heading_command 가 True 인데 ang_vel_z 가 (0,0) 이면 방향 보정이
            #    항상 0 으로 잘려 제어가 안 먹는다 (위 명령 고정 블록 주석 참고).
            "commands_cfg": {
                "heading_command": cmd.heading_command,
                "heading_control_stiffness": cmd.heading_control_stiffness,
                # ang_vel_z 는 heading 이 켜지면 "뽑는 범위" 가 아니라 "잘라내는 범위" 로
                # 재사용된다. 그래서 이름을 clip 으로 적는다 - 값의 뜻이 이름에 남게.
                "ang_vel_z_clip": _pair(cmd.ranges.ang_vel_z),
                "rel_heading_envs": cmd.rel_heading_envs,
                "heading_range": _pair(cmd.ranges.heading),  # --heading 없으면 None 이 정상
                "lin_vel_x": _pair(cmd.ranges.lin_vel_x),
                "lin_vel_y": _pair(cmd.ranges.lin_vel_y),
                "rel_standing_envs": cmd.rel_standing_envs,
                # 명령을 몇 초마다 다시 뽑나. 기본 (10,10). warmup 이 안 풀린
                # 09-03 사고(위키 08 · S-3)의 원인이 정확히 이 값이었다.
                "resampling_time_range": _pair(getattr(cmd, "resampling_time_range", None)),
            },

            # ---- 에피소드 ----
            "episode": {
                # 🔴 환경 난수 시드. 위 terrain_seed 와 다른 값이다.
                #    rl_cfg.py:141 의 기본값 42 를 Go2 cfg 가 덮지 않으므로 보통 42 다.
                "env_seed": env_cfg.seed,
                "num_envs": env_cfg.scene.num_envs,
                # env 한 마리가 채울 에피소드 수. 0 이면 영상 길이로 끝낸다는 뜻.
                "episodes_per_env": args_cli.episodes,
                # 🔴 총 표본 수. 팀 규칙은 "칸당 100" 인데 A2 는 38 이었다.
                #    적어 두지 않으면 표본 수가 다른 것끼리 비교하게 된다.
                #    --episodes 0 이면 몇 판이 돌지 미리 알 수 없으므로 null 이다.
                "total_episodes": (
                    env_cfg.scene.num_envs * args_cli.episodes if args_cli.episodes > 0 else None
                ),
                "eval_duration_s": args_cli.eval_duration,
                "warmup_s": args_cli.warmup,
                # 실제로 환경에 들어간 값 = eval_duration + warmup.
                "episode_length_s": env_cfg.episode_length_s,
                # 한 스텝의 시간 [초]. sim.dt x decimation. CSV 의 step 을 초로 바꿀 때 쓴다.
                "step_dt_s": env_cfg.sim.dt * env_cfg.decimation,
                "command_vx": args_cli.command_vx,
                # 중심선 복귀 P 제어. 0 이 아니면 "정책" 이 아니라 "정책 + 내 제어기" 를
                # 잰 것이다. 이 값이 0 인지 확인 안 하면 결과의 의미가 달라진다.
                "lateral_kp": args_cli.lateral_kp,
                "lateral_max": args_cli.lateral_max,
            },

            # ---- 낙상 판정 ----
            "termination": {
                # 어느 링크의 접촉을 낙상으로 세나. 기본은 "base" 하나뿐이다.
                "base_contact_body_names": getattr(_mf_term_sensor, "body_names", None),
                # 몇 N 을 넘으면 낙상인가. 기본 1.0.
                "threshold_N": _mf_term_params.get("threshold"),
                # [M2-5] 이 실행에 실제로 걸린 종료 조건 전부. A2/M1 과 같아야 한다.
                # term_stall 이 이 목록에 없으면 정체 종료는 «꺼져 있다».
                "active_terms": _mf_terms_active,
            },

            # ---- 무작위화(외란) ----
            # 평가에서 전부 껐다는 사실 자체가 조건이다. 안 적으면 "이 런은 외란이
            # 켜져 있었나" 를 나중에 코드를 뒤져 확인해야 한다.
            "randomization": {
                "observation_corruption": env_cfg.observations.policy.enable_corruption,
                "push_robot": getattr(env_cfg.events, "push_robot", None) is not None,
                "base_external_force_torque": getattr(env_cfg.events, "base_external_force_torque", None)
                is not None,
                "spawn_xy_m": _SPAWN_XY,
                "spawn_yaw_rad": _YAW,
                "joint_scale": _JOINT_SCALE,
            },

            # ---- 이 폴더에 무엇이 떨어지나 ----
            "outputs": {
                "steps_csv": f"{args_cli.eval_name}_steps.csv",
                # 수정 C 로 out_dir/video/ 안에 떨어지게 바꿨다. --video 없으면 null.
                "video_dir": "video" if args_cli.video else None,
                # 🔴 null 인 이유: stdout 은 셸의 tee 가 만든다. 스크립트는 자기 출력이
                #    어느 파일로 흘러가는지 모른다. 폴더 규칙상 stdout.log 이지만
                #    코드가 확인한 값이 아니므로 지어내지 않는다.
                "stdout_log": None,
                # 🔴 null 인 이유: metrics.json 은 실행이 끝난 뒤 summarize.py --json 이
                #    만든다. 이 시점에는 아직 없다.
                "metrics_json": None,
            },

            # started -> completed. 위 _write_manifest docstring 참고.
            "status": status,
        }
        # ensure_ascii=False: 한글 값이 \uXXXX 로 깨져 나오지 않게.
        # indent=2: 사람이 열어 읽는 파일이다. 용량보다 가독성이 중요하다.
        # default=str: to_dict() 가 함수 객체 같은 것을 남겨도 JSON 이 죽지 않게
        #              문자열로 떨어뜨린다. manifest 때문에 실행이 죽으면 안 된다.
        with open(_manifest_path, "w", encoding="utf-8") as _mf:
            json.dump(_m, _mf, ensure_ascii=False, indent=2, default=str)
        print(f"[EVAL] manifest({status}) -> {_manifest_path}")

    _write_manifest("started")
    # ─── 여기까지 B ──────────────────────────────────────────────────────────

    # ========================================================================
    # 4부. 환경을 만들고 껍데기를 씌운다
    # ========================================================================

    # create isaac environment
    # 여기서 실제 시뮬레이션 세계가 만들어진다. 위에서 고친 env_cfg 가 이때 읽힌다.
    # render_mode="rgb_array" = 화면을 그림 배열로 뽑을 수 있게 한다 (영상 녹화에 필요).
    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)

    # convert to single-agent instance if required by the RL algorithm
    # 다중 에이전트 환경이면 단일로 바꾼다. Go2 는 해당 없음.
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    # wrap for video recording
    # 껍데기(wrapper) = 환경을 감싸서 기능을 하나 더 붙이는 방식.
    if args_cli.video:
        # 원본 play.py 는 체크포인트 폴더 밑(log_dir/videos/play)에 rl-video-step-0.mp4 로 저장한다.
        # 이름이 항상 같아서 다음 실행이 앞의 영상을 덮어쓴다. 두 곳을 바꿔 해결한다.
        video_kwargs = {
            # ─── [2026-09-07 수정 C] 영상을 실행 폴더 "안" 으로 ─────────────
            #   원본: os.path.join(args_cli.out_dir, "..", "videos")
            #   그러면 --out_dir 이 .../20260907_heading/A2h_s42 일 때 영상은
            #   .../20260907_heading/videos/ 로, 즉 실행 폴더 "밖" 으로 떨어진다.
            #   폴더 규칙이 "실행 하나 = 폴더 하나"(위키 R-0q 원칙 1)인데 첫날부터
            #   깨지는 셈이다. 영상만 형제 폴더에 남으면 "이 CSV 와 이 영상이 같은
            #   실행인가" 를 파일 이름으로 추측하게 된다 - 추측이 들어가면 결과가 아니다.
            #   폴더째 scp 로 받을 때 영상만 안 따라오는 것도 이것 때문이다.
            #   ".." 를 빼고 out_dir 밑의 video/ 로 내린다.
            "video_folder": os.path.join(args_cli.out_dir, "video"),
            # ─── 여기까지 C ────────────────────────────────────────────────
            # (나) 파일 이름 앞머리. 기본값이 "rl-video" 라서 다 같은 이름이 됐다.
            #      실험 이름을 넣으면 B1_vx0.5-step-0.mp4 처럼 갈린다.
            "name_prefix": args_cli.eval_name,
            "step_trigger": lambda step: step == 0,  # 0번째 스텝에 딱 한 번 녹화를 시작
            "video_length": args_cli.video_length,  # 몇 스텝을 찍을지
            "disable_logger": True,  # 부가 로그 끄기
        }
        print("[INFO] Recording videos during training.")
        print_dict(video_kwargs, nesting=4)
        env = gym.wrappers.RecordVideo(env, **video_kwargs)

    # wrap around environment for rsl-rl
    # RSL-RL 라이브러리가 기대하는 입출력 모양으로 바꿔 주는 껍데기.
    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)

    print(f"[INFO]: Loading model checkpoint from: {resume_path}")

    # load previously trained model
    # 설정에 적힌 러너 종류에 따라 알맞은 것을 만든다. log_dir=None = 학습 로그 안 남김.
    if agent_cfg.class_name == "OnPolicyRunner":
        runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    elif agent_cfg.class_name == "DistillationRunner":
        runner = DistillationRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    else:
        raise ValueError(f"Unsupported runner class: {agent_cfg.class_name}")
    # 체크포인트 파일에서 신경망 가중치를 읽어 넣는다. 이 순간 모델이 완성된다.
    runner.load(resume_path)

    # obtain the trained policy for inference
    # 추론(inference) 전용 함수를 꺼낸다. 관측을 넣으면 행동이 나오는 함수다.
    # 여기서부터 가중치는 절대 안 바뀐다. 학습이 아니다.
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    # extract the neural network module
    # we do this in a try-except to maintain backwards compatibility.
    # 신경망 본체를 꺼낸다. Isaac Lab 버전에 따라 속성 이름이 달라서 두 번 시도한다.
    try:
        # version 2.3 onwards
        policy_nn = runner.alg.policy
    except AttributeError:
        # version 2.2 and below
        policy_nn = runner.alg.actor_critic

    # extract the normalizer
    # 정규화기 = 관측값의 크기를 고르게 맞춰 주는 장치. 학습 때 쓰던 것을 그대로 써야 한다.
    # 이것도 버전에 따라 이름이 달라 세 갈래로 확인한다.
    if hasattr(policy_nn, "actor_obs_normalizer"):
        normalizer = policy_nn.actor_obs_normalizer
    elif hasattr(policy_nn, "student_obs_normalizer"):
        normalizer = policy_nn.student_obs_normalizer
    else:
        normalizer = None

    # export policy to onnx/jit
    # 정책을 파이썬 없이도 돌릴 수 있는 형식으로 내보낸다.
    # 나중에 실기(Go2)에 올릴 때 쓰는 파일이다. 지금 평가에는 영향이 없다.
    export_model_dir = os.path.join(os.path.dirname(resume_path), "exported")
    export_policy_as_jit(policy_nn, normalizer=normalizer, path=export_model_dir, filename="policy.pt")
    export_policy_as_onnx(policy_nn, normalizer=normalizer, path=export_model_dir, filename="policy.onnx")

    # 한 스텝의 시간 [초]. sim.dt(0.005) x decimation(4) = 0.02 초 = 50 Hz.
    dt = env.unwrapped.step_dt

    # ========================================================================
    # 5부. 계측 준비. 원본 play.py 에 없는 블록이다.
    #
    # play.py 는 재생기라서 아무 수치도 남기지 않는다.
    # 판정 5축(생존/전진/속도추종/방향)을 계산하려면 원본 데이터가 필요하다.
    # ========================================================================

    # reset environment
    import csv  # 표준 라이브러리. 표 형식 파일 쓰기.

    # env 는 껍데기가 여러 겹 씌워져 있다. unwrapped 로 알맹이를 꺼낸다.
    _u = env.unwrapped
    # 로봇 객체. 위치/속도/관절 상태가 여기 들어 있다.
    _robot = _u.scene["robot"]
    # 접촉 센서. 몸의 각 부위가 무엇에 얼마나 세게 닿았는지 담고 있다.
    _contact = _u.scene.sensors["contact_forces"]
    # base 링크(몸통)의 번호를 찾는다. 종료 조건이 감시하는 바로 그 링크다.
    # find_bodies 는 (번호목록, 이름목록) 을 돌려주므로 [0][0] 으로 첫 번호를 꺼낸다.
    _base_id = _robot.find_bodies("base")[0][0]
    # 허벅지 링크들. 종료 조건이 안 보는 곳이라 "주저앉기" 를 여기서 관측한다.
    # Go2 링크명은 소문자(FL_thigh)다. 원본 undesired_contacts 의 ".*THIGH" 는 ANYmal 이름이라 안 맞는다.
    _thigh_ids = _robot.find_bodies(".*_thigh")[0]
    # 각 env 가 어느 난이도 칸(열)에 있는지. terrain_importer.py:348 이 만들어 둔 텐서다.
    _terr = _u.scene.terrain
    _col = getattr(_terr, "terrain_types", None)
    # env 마다 몇 번째 에피소드인지. 스텝 CSV 에서 에피소드를 가르려면 이 열이 있어야 한다.
    _ep = torch.zeros(_u.num_envs, dtype=torch.long, device=_u.device)
    _step_dt = _u.step_dt  # 한 스텝의 시간. 스텝 번호를 초로 바꿀 때 쓴다.
    _n = _u.num_envs  # 로봇 마리 수 (10)

    # 명령 버퍼를 가진 객체. 여기 vel_command_b[:, 0/1/2] 가 정책이 보는 명령 3개다.
    _cmd_term = _u.command_manager.get_term("base_velocity")
    # warmup 을 "초" 에서 "스텝 수" 로 바꾼다. 1.0 초 / 0.02 = 50 스텝.
    _warm_steps = int(round(args_cli.warmup / _step_dt))
    # 개입이 필요한 실험인지 미리 판정해 둔다 (매 스텝 if 를 줄인다).
    _intervene = (_warm_steps > 0) or (args_cli.lateral_kp > 0.0)
    print(f"[EVAL] heading={args_cli.heading} warmup={args_cli.warmup}s({_warm_steps}스텝) "
          f"lateral_kp={args_cli.lateral_kp}")

    # 저장 폴더가 없으면 만든다. exist_ok=True = 이미 있어도 에러 안 냄.
    os.makedirs(args_cli.out_dir, exist_ok=True)
    # 파일 이름은 <eval_name>_steps.csv. 실험마다 eval_name 을 바꿔야 안 덮어쓴다.
    _csv_path = os.path.join(args_cli.out_dir, f"{args_cli.eval_name}_steps.csv")
    # newline="" 은 csv 모듈이 요구하는 관용구다. 안 주면 빈 줄이 끼어든다.
    _fh = open(_csv_path, "w", newline="")
    _w = csv.writer(_fh)
    # 첫 줄은 열 이름. 나중에 이 이름으로 읽는다.
    _w.writerow(
        [
            "step",  # 스텝 번호 (0부터)
            "t",  # 시각 [초]
            "env",  # 몇 번 로봇인지 (0~9)
            "x",  # 출발 타일 기준 앞뒤 위치 [m]
            "y",  # 좌우 위치 [m]
            "z",  # 높이 [m]. 서 있으면 0.3 대, 주저앉으면 0.1 아래
            "vx_w",  # 월드 기준 전진 속도 [m/s]
            "vy_w",  # 월드 기준 옆 속도 [m/s]
            "vx_b",  # 몸 기준 전진 속도 [m/s]. 속도추종 오차는 이것으로 잰다
            "cmd_vx",  # 정책이 실제로 본 전진 명령. warmup 중이면 0 이어야 한다
            "cmd_wz",  # 정책이 실제로 본 회전 명령. heading 제어가 먹으면 0 이 아니다
            "yaw",  # 월드 기준 몸통 방향 [rad]. 0 이 +X. heading 제어의 입력이다
            "terrain_col",  # 어느 난이도 칸(열)인가. 새 KPI 의 축
            "episode",  # 이 env 의 몇 번째 에피소드인가
            "base_force_N",  # 몸통에 걸린 접촉력 [N]. 1.0 을 넘으면 낙상 판정
            "thigh_force_N",  # 허벅지 접촉력 최대 [N]. 종료 조건이 안 보는 곳
            "done",  # 이 스텝에 에피소드가 끝났는지 (0/1)
            "term_base_contact",  # 끝난 이유가 낙상인지 (0/1)
            "term_time_out",  # 끝난 이유가 시간 초과인지 (0/1)
        ]
    )
    print(f"[EVAL] CSV -> {_csv_path}")

    # ─── [2026-09-07 추가 S-2] 발 CSV ───────────────────────────────────────
    #   한 줄 = 한 스텝 x 한 로봇 x 한 발. 4발 x 10마리 x 1000스텝 = 4만 줄.
    _feet_fh = _feet_w = None
    if args_cli.log_feet:
        _feet_path = os.path.join(args_cli.out_dir, f"{args_cli.eval_name}_feet.csv")
        _feet_fh = open(_feet_path, "w", newline="")
        _feet_w = csv.writer(_feet_fh)
        _feet_w.writerow([
            "step", "t", "env", "episode",
            "foot",     # 발 이름 (FL/FR/RL/RR)
            "fx",       # 타일 원점 기준 발 앞뒤 위치 [m]  <- 보폭은 이 값의 착지 간격이다
            "fy",       # 좌우 [m]
            "fz",       # 높이 [m]. 지형 높이를 그대로 따라간다
            "force_N",  # 이 발의 접촉력 크기 [N]
            "contact",  # force_N > 1.0 이면 1. 착지 판정
        ])
        print(f"[EVAL] 발 CSV -> {_feet_path}")
    # ─── 여기까지 S-2 ───────────────────────────────────────────────────────

    # ========================================================================
    # 6부. 재생 루프. 여기가 실제로 로봇이 움직이는 곳이다.
    # ========================================================================

    # 첫 관측을 받는다. 관측 = 로봇이 보는 235개 숫자
    # (몸 속도 9 + 명령 3 + 관절 36 + 높이스캔 187).
    obs = env.get_observations()
    timestep = 0  # 지금까지 몇 스텝 돌았는지

    # ─── [2026-09-07 추가 M2-4] base -> 앞발 x 거리를 «실측» 해서 한 줄 찍는다 ──
    #   왜 필요한가: CSV 의 x 는 몸통 중심(base)이다. 그런데 지형과 먼저 만나는 것은
    #   앞발이다. summarize.py 가 "평지에서 낙상" 을 base x < 경계 로 판정하는 바람에
    #   M1 낙상 136건 중 61건(45%)이 «평지 낙상» 으로 잘못 분류돼 험지 낙상거리
    #   집계에서 통째로 빠졌다. 그 61건의 base x 중앙값은 1.965 m - 경계(2.0 m)에서
    #   3.5 cm 모자란 것이고, 앞발은 이미 돌 위에 있었다.
    #   보정하려면 base -> 앞발 x 거리가 필요한데, Go2 의 USD 는 Nucleus 에만 있어
    #   노트북에서 읽을 수 없다. 추측하지 않고 시뮬레이터에게 직접 묻는다.
    #
    #   🔴 이 블록은 «읽기만» 한다. 명령도 상태도 건드리지 않으므로 M1 과의 비교가
    #      깨지지 않는다. 값이 필요 없으면 로그 한 줄이 늘어날 뿐이다.
    #   원본에는 이 블록이 없었다.
    try:
        _foot_ids, _foot_names = _robot.find_bodies(".*_foot")
        # body_pos_w = 월드 기준 각 링크 위치 [env, 링크, xyz]. root_pos_w = 몸통 중심.
        _dx_all = (_robot.data.body_pos_w[:, _foot_ids, 0]
                   - _robot.data.root_pos_w[:, 0:1])          # [env, 발]
        _dx_per_foot = _dx_all.mean(dim=0)                     # env 10마리 평균
        _pairs = ", ".join(f"{n}={v:+.3f}" for n, v in zip(_foot_names, _dx_per_foot.tolist()))
        # 우리가 쓰는 값은 «가장 앞선 발» 의 오프셋이다. 지형과 먼저 만나는 것이 그것이므로.
        _foot_dx = float(_dx_per_foot.max())
        print(f"[EVAL] base->발 x 오프셋 [m]: {_pairs}")
        print(f"[EVAL] 🔴 summarize.py --foot_dx 에 넣을 값 = {_foot_dx:.3f}")
    except Exception as _e:
        # 여기서 죽으면 평가 전체가 날아간다. 진단용 출력이 본 실험을 막으면 안 된다.
        _foot_dx = None
        print(f"[EVAL] base->발 오프셋 측정 실패(무시하고 계속): {_e}")
    # ─── 여기까지 M2-4 ──────────────────────────────────────────────────────

    # ─── [2026-09-07 추가 S-3] 접촉 센서 쪽 발 인덱스 ───────────────────────
    #   위 M2-4 가 구한 _foot_ids 는 «로봇» 링크 번호다. 힘은 «접촉 센서» 에서 읽는데
    #   두 객체의 링크 순서가 같다는 보장이 없다. 기존 코드(1105-1106행)는 같다고
    #   가정하고 있는데, 여기서 실제로 이름을 대조해 확인한다. 다르면 센서 쪽 번호를 쓴다.
    _cf_ids = _foot_ids
    if args_cli.log_feet:
        try:
            _cf_names = list(getattr(_contact, "body_names", []) or [])
            if _cf_names:
                _cf_ids = [_cf_names.index(n) for n in _foot_names]
                if _cf_ids != list(_foot_ids):
                    print(f"[EVAL] 🔴 접촉센서와 로봇의 링크 순서가 다르다. 센서 번호를 쓴다: {_cf_ids}")
        except Exception as _e:
            print(f"[EVAL] 접촉센서 발 번호 대조 실패(로봇 번호를 그대로 씀): {_e}")
        print(f"[EVAL] 발 링크 {list(_foot_names)}")
    # ─── 여기까지 S-3 ───────────────────────────────────────────────────────

    # simulate environment
    # 시뮬레이터 창이 살아 있는 동안 계속 돈다.
    while simulation_app.is_running():
        start_time = time.time()  # 실시간 모드에서 프레임 간격을 맞추려고 시각을 잰다

        # 🔴 원본은 torch.inference_mode() 였다. no_grad() 로 바꾼 이유:
        #    inference_mode 안에서 만들어진 텐서는 "추론 전용" 표시가 붙어
        #    아래에서 vel_command_b 를 덮어쓰면 나중에 env 리셋이 막힌다.
        #    no_grad() 는 기울기만 끄고 그 제약이 없다. 속도 차이는 무시할 수준이다.
        with torch.no_grad():
            # ---- 명령 개입 ----
            # 여기서 고친 명령이 이번 스텝에 정책이 보는 명령이 된다.
            if _intervene:
                if args_cli.lateral_kp > 0.0:
                    # 중심선 = 이 env 타일의 원점. 즉 env_origins 기준 y = 0.
                    # (임석헌 코드는 "루프 시작 위치" 를 쓰는데, 그건 1회 실행용이다.
                    #  우리는 --episodes 로 계속 리셋하므로 리셋되면 기준이 틀어진다.)
                    _ey = _robot.data.root_pos_w[:, 1] - _u.scene.env_origins[:, 1]
                    # 오차 반대 방향으로 되돌리는 속도. 상한을 둬서 급격히 안 꺾이게 한다.
                    _vyw = torch.clamp(-args_cli.lateral_kp * _ey,
                                       -args_cli.lateral_max, args_cli.lateral_max)
                    # 명령은 "몸 기준" 이므로 월드 (vx, vy) 를 현재 방향만큼 회전시킨다.
                    _yaw = _robot.data.heading_w
                    _vxw = torch.full_like(_vyw, args_cli.command_vx)
                    _cmd_term.vel_command_b[:, 0] = torch.cos(_yaw) * _vxw + torch.sin(_yaw) * _vyw
                    _cmd_term.vel_command_b[:, 1] = -torch.sin(_yaw) * _vxw + torch.cos(_yaw) * _vyw
                else:
                    # 🔴 warmup 이 vel_command_b 를 0 으로 덮어쓰면 그 0 이 영구히 남는다.
                    #    lin_vel_x 는 "리샘플링" 때만 다시 뽑히는데
                    #    (velocity_env_cfg.py:96 resampling_time_range=(10,10) -> 10초에 한 번)
                    #    그 사이에는 아무도 되돌려 주지 않는다.
                    #    그래서 매 스텝 원래 명령을 다시 써 넣는다. 값은 항상 같으므로 부작용이 없다.
                    _cmd_term.vel_command_b[:, 0] = args_cli.command_vx
                    _cmd_term.vel_command_b[:, 1] = 0.0
                if _warm_steps > 0:
                    # episode_length_buf = env 마다 "이번 에피소드에서 몇 스텝 지났나".
                    # 리셋되면 0 으로 돌아간다. 전역 timestep 으로 세면
                    # 첫 에피소드에만 정지가 걸리고 2번째부터는 안 걸린다.
                    _warm = _u.episode_length_buf < _warm_steps
                    _cmd_term.vel_command_b[_warm, :] = 0.0
                # ★ 명령 버퍼만 바꾸면 obs 는 아직 옛날 명령을 담고 있다.
                #   다시 만들어야 정책이 바뀐 명령을 본다. 빼면 제어가 한 박자 늦는다.
                obs = env.get_observations()

            # 정책이 실제로 본 명령을 그대로 남겨 둔다. CSV 검증용.
            # env.step() 뒤에 읽으면 heading 제어가 이미 덮어써서 다른 값이 나온다.
            _cmd_seen = _cmd_term.vel_command_b.clone()
            # 같은 시점의 몸통 방향. cmd_wz = clip(0.5 * (0 - yaw)) 이므로
            # 이 둘을 나란히 놓아야 heading 제어가 먹었는지 눈으로 확인된다.
            _yaw_seen = _robot.data.heading_w.clone()

            # agent stepping
            # 관측 235개를 넣으면 관절 목표 12개가 나온다. 이게 신경망의 전부다.
            actions = policy(obs)
            # env stepping
            # 그 행동으로 물리 시뮬레이션을 한 스텝 진행한다.
            # 돌려받는 것: 새 관측, 보상(안 씀), 종료 여부, 부가정보(안 씀).
            # 밑줄(_) = "받긴 받는데 안 쓴다" 는 관습.
            # 주의: 이 줄 안에서 끝난 env 는 이미 출발점으로 되돌려진 상태다.
            obs, _, dones, _ = env.step(actions)
            # reset recurrent states for episodes that have terminated
            # 신경망이 기억(순환 상태)을 갖는 종류면, 끝난 로봇의 기억을 지운다.
            policy_nn.reset(dones)

            # ---- 한 스텝 기록 ----
            # 로봇의 월드 좌표에서 타일 원점을 빼서 "출발점 기준 위치"로 만든다.
            _pos = _robot.data.root_pos_w - _u.scene.env_origins
            # 월드 기준 몸통 속도 [m/s]. 몸 기준이 아니라 월드 기준이라 방향이 섞여 있다.
            _vel = _robot.data.root_lin_vel_w
            # 몸통에 걸린 접촉력의 크기. xyz 세 성분을 norm 으로 하나의 크기로 만든다.
            _f = torch.norm(_contact.data.net_forces_w[:, _base_id, :], dim=-1)
            _ft = torch.norm(_contact.data.net_forces_w[:, _thigh_ids, :], dim=-1).max(dim=1)[0]
            _velb = _robot.data.root_lin_vel_b
            # 이번 스텝에 "낙상"으로 끝난 로봇들 (True/False 배열)
            _tb = _u.termination_manager.get_term("base_contact")
            # 이번 스텝에 "시간 초과"로 끝난 로봇들
            _tt = _u.termination_manager.get_term("time_out")
            _t = timestep * _step_dt  # 스텝 번호를 초로 환산

            # 로봇 10마리를 한 마리씩 한 줄로 쓴다. 1000 스텝 x 10 마리 = 1만 줄.
            for _i in range(_n):
                _w.writerow(
                    [
                        timestep,
                        round(_t, 3),
                        _i,
                        # .item() = 텐서에서 파이썬 숫자 하나를 꺼낸다.
                        # round 로 자릿수를 줄여 파일 크기를 아낀다.
                        round(_pos[_i, 0].item(), 4),
                        round(_pos[_i, 1].item(), 4),
                        round(_pos[_i, 2].item(), 4),
                        round(_vel[_i, 0].item(), 4),
                        round(_vel[_i, 1].item(), 4),
                        round(_velb[_i, 0].item(), 4),
                        round(_cmd_seen[_i, 0].item(), 3),
                        round(_cmd_seen[_i, 2].item(), 3),
                        round(_yaw_seen[_i].item(), 4),
                        int(_col[_i].item()) if _col is not None else -1,
                        int(_ep[_i].item()),
                        round(_f[_i].item(), 2),
                        round(_ft[_i].item(), 2),
                        int(dones[_i].item()),  # True/False 를 1/0 으로
                        int(_tb[_i].item()),
                        int(_tt[_i].item()),
                    ]
                )

            # ─── [2026-09-07 추가 S-4] 발 4개 기록 ───────────────────────────
            #   본 루프 «안» 이 아니라 «뒤» 에 두는 이유: 텐서를 발마다 한 번씩
            #   꺼내는 대신 한 번에 CPU 로 내려 반복문은 파이썬 리스트만 훑게 한다.
            if _feet_w is not None:
                _fp = (_robot.data.body_pos_w[:, _foot_ids, :]
                       - _u.scene.env_origins[:, None, :]).cpu().tolist()   # [env][발][xyz]
                _ff = torch.norm(_contact.data.net_forces_w[:, _cf_ids, :], dim=-1).cpu().tolist()
                for _i in range(_n):
                    _epi = int(_ep[_i].item())
                    for _k, _fn in enumerate(_foot_names):
                        _fz = _ff[_i][_k]
                        _feet_w.writerow([
                            timestep, round(_t, 3), _i, _epi, _fn,
                            round(_fp[_i][_k][0], 4),
                            round(_fp[_i][_k][1], 4),
                            round(_fp[_i][_k][2], 4),
                            round(_fz, 2),
                            1 if _fz > 1.0 else 0,   # 1 N = 종료조건이 쓰는 것과 같은 문턱
                        ])
            # ─── 여기까지 S-4 ────────────────────────────────────────────────

            # 끝난 env 의 에피소드 번호를 올린다. 기록을 마친 뒤여야
            # 마지막 스텝이 이전 에피소드 번호로 남는다.
            _ep += dones.long()

        # 🔴 timestep 증가는 --video 와 무관하다.
        # 원본 play.py 는 이 줄이 if args_cli.video 안에 있었다. 원본은 영상 없이 돌면
        # 사람이 끌 때까지 도는 대화형 재생기라 문제가 없었지만, 우리는 CSV 를 쓰므로
        # (1) step·t 열이 전 행 0 이 되고 (2) 아래 break 에 영원히 안 닿아 루프가 안 끝난다.
        timestep += 1

        # 에피소드 수로 끝내기. 100 에피소드 측정은 영상 없이 이쪽으로 돈다.
        # 모든 env 가 목표 횟수를 채웠을 때 끝낸다. 한 마리라도 덜 돌면 칸의 n 이 어긋난다.
        if args_cli.episodes > 0 and int(_ep.min().item()) >= args_cli.episodes:
            break

        # 영상을 찍는 중이면 목표 길이에서 멈춘다.
        if args_cli.video and timestep >= args_cli.video_length:
            break

        # time delay for real-time evaluation
        # 실시간 모드일 때만, 한 스텝이 실제 0.02 초가 되도록 남는 시간만큼 쉰다.
        sleep_time = dt - (time.time() - start_time)
        if args_cli.real_time and sleep_time > 0:
            time.sleep(sleep_time)

    # 파일을 닫아야 버퍼에 남은 내용이 디스크에 실제로 쓰인다.
    _fh.close()
    if _feet_fh is not None:
        _feet_fh.close()
    print(f"[EVAL] CSV 저장 완료: {_csv_path}")
    # ─── [2026-09-07 수정 D] 안내 경로를 C 와 맞추고, manifest 를 완주로 도장 ───
    #   원본: os.path.join(args_cli.out_dir, '..', 'videos')
    #   C 에서 저장 위치를 바꿨으므로 여기 안내문도 같이 안 바꾸면 화면에는
    #   없는 경로가 찍힌다. 안내문이 거짓이면 안 보느니만 못하다.
    if args_cli.video:
        print(f"[EVAL] 영상 -> {os.path.join(args_cli.out_dir, 'video')}/{args_cli.eval_name}-step-0.mp4")
    # 여기까지 왔다는 것은 루프가 정상적으로 끝났다는 뜻이다. manifest 를 다시 써서
    # status 를 completed 로 바꾼다. 중간에 죽으면 started 인 채로 남아,
    # 나중에 폴더만 보고 "완주" 와 "죽음" 이 갈린다.
    _write_manifest("completed")
    # ─── 여기까지 D ────────────────────────────────────────────────────────

    # close the simulator
    # 환경을 정리한다. 영상 파일도 이때 마무리돼 저장된다.
    env.close()


# 이 파일을 직접 실행했을 때만 아래가 돈다.
# 다른 파일이 import 했을 때는 안 돈다는 뜻인데, 이 스크립트는 항상 직접 실행한다.
if __name__ == "__main__":
    # run the main function
    main()
    # close sim app
    # Isaac Sim 앱을 끈다. 이걸 안 하면 프로세스가 안 죽는다.
    simulation_app.close()
