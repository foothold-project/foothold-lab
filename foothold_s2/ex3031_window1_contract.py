"""EX-30 · EX-31 창 1 장기 판의 기동 전 CPU 계약 (SONNET-X25 후속). Kit 없이 시험된다.

창 1 = 부모 B1500 에서 추가 250 갱신(마지막 저장 model_1750). 두 판의 차이는 지도 처치(force_gt) 하나이고, 부모 지형 칸(terrain_levels/types)은 두 판 똑같이 이어 쓴다
(설계 v1.0 §2.2). 명령 · 지형 커리큘럼 · DR · 보상 · agent cfg 는 B 그대로. 팀장 승인 전에는 띄우지 않는다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from foothold_s2.ex3031_smoke_contract import PARENT_PATH, TASK, CHILD_SPEC_NAME, EXPERIMENTS, read_child_spec, write_child_spec  # noqa: F401
from foothold_s2.runners.stage_transfer import ALLOWED_PARENT_SHA256, TransferSpec, file_sha256

EXTRA_UPDATES = 250
PARENT_ITER = 1500
FINAL_ITER = PARENT_ITER + EXTRA_UPDATES                                 # 1750
SAVE_INTERVAL = 50
EXPECTED_CHECKPOINTS = tuple(f"model_{n}.pt" for n in range(PARENT_ITER + SAVE_INTERVAL, FINAL_ITER + 1, SAVE_INTERVAL))      # model_1550 .. model_1750
DEVICE = {"EX-30": "cuda:0", "EX-31": "cuda:1"}                          # GPU1 은 화면 GPU 라 학습만 한다(촬영 금지)
ALLOWED_DEVICES = {"EX-30": ("cuda:0",), "EX-31": ("cuda:1", "cuda:0")}   # EX-31 은 10/25 04:42 GPU1 메모리 페이징으로 중단, 팀장 결정으로 EX-30 이 끝난 뒤 cuda:0 에서 단독 재기동
STAGGER_SECONDS = 30
WINDOW1_COURSE_TAG = "ex3031-window1-b-contract-no-course-stage"        # T2 과정 상태가 없는 창: spec 의 과정 칸에 이 문자열의 SHA 를 적는다
TERRAIN_RESTORE = "parent_levels"
RUN_ROOT_NAME = "foothold_s2_ex3031_w1"


def course_sha() -> str:
    return hashlib.sha256(WINDOW1_COURSE_TAG.encode()).hexdigest()


def validate(args, hydra_args=()) -> None:
    """잘못된 기동을 Kit 이 뜨기 전에 거절한다. 갱신 수 · 학습률 · cfg 는 인자로 바꿀 수 없다."""
    if args.exp not in EXPERIMENTS:
        raise ValueError(f"exp 는 {EXPERIMENTS} 중 하나")
    if args.task != TASK or args.agent != "rsl_rl_cfg_entry_point" or hydra_args:
        raise ValueError("B task 와 고정 agent cfg 만 쓴다(Hydra 덮어쓰기 없음)")
    if args.distributed or getattr(args, "resume", False):
        raise ValueError("분산과 일반 --resume 은 쓰지 않는다")
    if args.num_envs not in (None, 3072) or args.seed not in (None, 42):
        raise ValueError("B 계약: 3072 env, seed 42")
    if args.max_iterations is not None:
        raise ValueError(f"갱신 수는 {EXTRA_UPDATES} 로 고정이다. --max_iterations 를 주지 않는다")
    if not Path(args.parent).is_file() or file_sha256(args.parent) not in ALLOWED_PARENT_SHA256:
        raise ValueError("부모가 허용 목록의 B model_1500.pt 가 아니다")
    if args.device not in (None, *ALLOWED_DEVICES[args.exp]):
        raise ValueError(f"{args.exp} 는 {ALLOWED_DEVICES[args.exp]} 에서 돈다(받은 값 {args.device})")


def make_spec(exp: str, parent_sha256: str, seed: int = 42) -> TransferSpec:
    return TransferSpec(parent_sha256=parent_sha256, experiment_id=exp, map_policy={"EX-30": "adaptive", "EX-31": "gt"}[exp], seed=seed, curriculum_spec_sha256=course_sha(),
                        terrain_restore=TERRAIN_RESTORE)


def check_outputs(log_dir) -> list[str]:
    """끝난 판의 산출물에서 빠진 것(비어 있으면 정상): 경계 저장 model_1550..1750 · child_spec · 영수증 · 결과 json."""
    d = Path(log_dir)
    need = list(EXPECTED_CHECKPOINTS) + [CHILD_SPEC_NAME, "transfer_receipt.json", "window1_result.json", "cfg_pair_diff.json"]

    return [n for n in need if not (d / n).is_file()]
