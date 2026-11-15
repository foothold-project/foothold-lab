"""EX-30 · EX-31 창 2 장기 판의 기동 전 CPU 계약 (SONNET-X25 후속). Kit 없이 시험된다.

창 2 = 창 1 의 자식 model_1750 에서 정확 재개(restore_child) 후 추가 250 갱신(마지막 저장 model_2000). cfg 는 B 그대로이고 처치(EX-31 만 force_gt)도 창 1 과 같다.
창 1 의 child_spec.json(부모 B1500 번호 1500 의 spec)을 그대로 이어 받는다. 자동 기동 판정은 foothold_s2/window2_gate.py 가 맡는다.
"""

from __future__ import annotations

from pathlib import Path

from foothold_s2.ex3031_smoke_contract import CHILD_SPEC_NAME, EXPERIMENTS, PARENT_PATH, TASK, read_child_spec  # noqa: F401
from foothold_s2.ex3031_window1_contract import FINAL_ITER as W1_FINAL_ITER, PARENT_ITER

EXTRA_UPDATES = 250
START_ITER = W1_FINAL_ITER                                               # 1750: 재개하는 창 1 마지막 저장
FINAL_ITER = START_ITER + EXTRA_UPDATES                                  # 2000
SAVE_INTERVAL = 50
EXPECTED_CHECKPOINTS = tuple(f"model_{n}.pt" for n in range(START_ITER + SAVE_INTERVAL, FINAL_ITER + 1, SAVE_INTERVAL))      # model_1800 .. model_2000
ALLOWED_DEVICES = {"EX-30": ("cuda:0",), "EX-31": ("cuda:0",)}           # 창 2 는 GPU0 에서 순차(GPU1 은 화면 GPU)
RUN_ROOT_NAME = "foothold_s2_ex3031_w2"
CHILD_CKPT_NAME = f"model_{START_ITER}.pt"


def validate(args, hydra_args=()) -> None:
    """잘못된 기동을 Kit 이 뜨기 전에 거절한다. 갱신 수 · cfg 는 인자로 바꿀 수 없다."""
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
    ckpt = Path(args.child_ckpt or "")
    if ckpt.name != CHILD_CKPT_NAME or not ckpt.is_file():
        raise ValueError(f"재개 체크포인트는 창 1 의 {CHILD_CKPT_NAME} 이어야 한다(받은 값 {args.child_ckpt!r})")
    if not (ckpt.parent / CHILD_SPEC_NAME).is_file():
        raise ValueError(f"{CHILD_SPEC_NAME} 이 체크포인트와 같은 폴더에 있어야 한다")
    spec, parent_iter = read_child_spec(ckpt.parent)
    if spec.experiment_id != args.exp:
        raise ValueError(f"체크포인트 폴더의 실험 {spec.experiment_id} 와 --exp {args.exp} 가 다르다")
    if parent_iter != PARENT_ITER:
        raise ValueError(f"부모 번호가 {PARENT_ITER} 가 아니다: {parent_iter}")
    if args.device not in (None, *ALLOWED_DEVICES[args.exp]):
        raise ValueError(f"{args.exp} 창 2 는 {ALLOWED_DEVICES[args.exp]} 에서 돈다(받은 값 {args.device})")


def check_outputs(log_dir) -> list[str]:
    """끝난 판의 산출물에서 빠진 것(비어 있으면 정상): 경계 저장 model_1800..2000 · 영수증 · 결과 json · cfg 대조."""
    d = Path(log_dir)
    need = list(EXPECTED_CHECKPOINTS) + ["transfer_receipt_w2.json", "window2_result.json", "cfg_pair_diff.json"]

    return [n for n in need if not (d / n).is_file()]
