"""EX-30 · EX-31 짧은 Kit 시험의 기동 전 CPU 계약 (SONNET-X25). Kit 없이 시험된다.

시험 순서(실험 하나마다): fresh = B 부모(model_1500)에서 전환 후 10 갱신 -> 저장 -> 새 프로세스 resume = 그 자식 체크포인트를 받아 2 갱신.
자식 cfg 는 «B cfg 그대로, 처치(force_gt)만 다름» 이다(부모 contract=start 라 다른 명령을 넣으면 start_runner.py:325 에서 실행 무효).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from foothold_s2.runners.stage_transfer import ALLOWED_PARENT_SHA256, TransferSpec, file_sha256

TASK = "FootholdS2-Go2-S2-23f-B-v0"
PARENT_PATH = Path("C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt")
UPDATES = {"fresh": 10, "resume": 2}
EXPERIMENTS = ("EX-30", "EX-31")
SMOKE_COURSE_TAG = "t1-kit-smoke-no-course-stage"                       # T2 과정 상태가 없는 시험: spec 의 과정 칸에 이 문자열의 SHA 를 적는다
CHILD_SPEC_NAME = "child_spec.json"


def smoke_course_sha() -> str:
    return hashlib.sha256(SMOKE_COURSE_TAG.encode()).hexdigest()


def validate(args, hydra_args=()) -> None:
    """잘못된 기동을 Kit 이 뜨기 전에 거절한다."""
    if args.exp not in EXPERIMENTS:
        raise ValueError(f"exp 는 {EXPERIMENTS} 중 하나")
    if args.mode not in UPDATES:
        raise ValueError(f"mode 는 {tuple(UPDATES)} 중 하나")
    if args.task != TASK or args.agent != "rsl_rl_cfg_entry_point" or hydra_args:
        raise ValueError("B task 와 고정 agent cfg 만 쓴다(Hydra 덮어쓰기 없음)")
    if args.distributed or getattr(args, "resume", False):
        raise ValueError("분산과 일반 --resume 은 쓰지 않는다")
    if args.num_envs not in (None, 3072) or args.seed not in (None, 42):
        raise ValueError("B 계약: 3072 env, seed 42")
    if args.max_iterations is not None:
        raise ValueError("갱신 수는 mode 로 정해진다(fresh 10, resume 2). --max_iterations 를 주지 않는다")
    if args.mode == "fresh":
        if args.child_ckpt:
            raise ValueError("fresh 는 --child_ckpt 를 받지 않는다")
        if not Path(args.parent).is_file() or file_sha256(args.parent) not in ALLOWED_PARENT_SHA256:
            raise ValueError("부모가 허용 목록의 B model_1500.pt 가 아니다")
    else:
        ckpt = Path(args.child_ckpt or "")
        if not ckpt.is_file() or not (ckpt.parent / CHILD_SPEC_NAME).is_file():
            raise ValueError(f"resume 은 자식 체크포인트와 같은 폴더의 {CHILD_SPEC_NAME} 이 필요하다")


def make_spec(exp: str, parent_sha256: str, seed: int = 42) -> TransferSpec:
    return TransferSpec(parent_sha256=parent_sha256, experiment_id=exp, map_policy={"EX-30": "adaptive", "EX-31": "gt"}[exp], seed=seed, curriculum_spec_sha256=smoke_course_sha())


def write_child_spec(log_dir, spec: TransferSpec, parent_iter: int) -> Path:
    path = Path(log_dir) / CHILD_SPEC_NAME
    path.write_text(json.dumps({"spec": spec.__dict__, "parent_iter": int(parent_iter), "spec_sha256": spec.sha256()}, ensure_ascii=False, indent=2), encoding="utf-8")

    return path


def read_child_spec(ckpt_dir) -> tuple[TransferSpec, int]:
    data = json.loads((Path(ckpt_dir) / CHILD_SPEC_NAME).read_text(encoding="utf-8"))
    spec = TransferSpec(**data["spec"])

    if spec.sha256() != data["spec_sha256"]:
        raise ValueError("child_spec.json 의 spec 이 자신의 SHA 와 다르다")

    return spec, int(data["parent_iter"])


def resume_log_dir(ckpt: str, stamp: str, pid: int) -> Path:
    source = Path(ckpt)
    target = source.parent.parent / f"{source.parent.name}_resume_{stamp}_{pid}"

    if target.exists():
        raise FileExistsError(target)

    return target
