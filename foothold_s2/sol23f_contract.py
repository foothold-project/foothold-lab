"""SOL-23f 기동 전 순수 CPU 계약. Kit 시작 전에 잘못된 판과 마감을 거절한다."""

from datetime import datetime
from pathlib import Path
import time


TASKS = {
    "B": "FootholdS2-Go2-S2-23f-B-v0",
    "TopDown": "FootholdS2-Go2-S2-23f-TopDown-v0",
    "SB": "FootholdS2-Go2-S2-SB-v0",                        # EX-33 S-B: B 와 같은 설정 + 에피소드 단위 지도 끔(p_map_off)
}
BUDGET_VARIANTS = ("B", "SB")                                   # seed 42 · 3072 env · 1501 회로 고정되는 판
MAP_INPUT = {"B": "reconstruction", "TopDown": "reconstruction", "SB": "reconstruction"}
FORCE_GT = {"B": True, "TopDown": False, "SB": True}
CKPT_VARIANT = {"B": "B_friction_only", "TopDown": "START_TopDown", "SB": "SB_map_switch"}


def validate_launch(args, hydra_args=(), now: float | None = None) -> float:
    if args.variant not in TASKS or args.task != TASKS[args.variant]:
        raise ValueError("variant and task do not match")
    if args.agent != "rsl_rl_cfg_entry_point" or hydra_args:
        raise ValueError("SOL-23f requires pinned agent cfg and no Hydra overrides")
    if args.distributed:
        raise ValueError("SOL-23f runs one process per experiment")
    if getattr(args, "resume", False):
        raise ValueError("use --resume_from for an isolated SOL-23f segment; --resume is not supported")
    if args.map_input not in (None, MAP_INPUT[args.variant]):
        raise ValueError(f"map_input must be {MAP_INPUT[args.variant]}")
    if not 0 < args.max_wall_s <= 86400:
        raise ValueError("max-wall-s must be within 24 h")
    try:
        end_by = datetime.fromisoformat(args.end_by)
    except (TypeError, ValueError) as exc:
        raise ValueError("end-by must be ISO8601 with a time zone") from exc
    if end_by.tzinfo is None:
        raise ValueError("end-by needs an explicit time zone")
    p_off = getattr(args, "p_map_off", None)
    if args.variant != "SB" and p_off is not None:
        raise ValueError("--p_map_off is for the SB variant only")
    if args.variant in BUDGET_VARIANTS:
        smoke = getattr(args, "smoke_updates", None)
        if args.variant == "B":
            if smoke not in (None, 10):
                raise ValueError("B smoke-updates must be exactly 10")
            if smoke and getattr(args, "resume_from", None):
                raise ValueError("B smoke cannot resume a main run")
        else:                                                   # SB: 10 회 새 시험, 그 체크포인트에서 이어 2 회
            if smoke not in (None, 10, 2):
                raise ValueError("SB smoke-updates must be 10 (fresh) or 2 (resume of the 10-update smoke)")
            if smoke == 10 and getattr(args, "resume_from", None):
                raise ValueError("SB 10-update smoke cannot resume")
            if smoke == 2 and not getattr(args, "resume_from", None):
                raise ValueError("SB 2-update smoke needs --resume_from the 10-update smoke checkpoint")
            if p_off is not None and not 0.0 < float(p_off) < 1.0:
                raise ValueError("p_map_off must be inside (0, 1)")
        if args.num_envs not in (None, 3072) or args.seed not in (None, 42) or args.max_iterations not in (None, 1501):
            raise ValueError(f"{args.variant} is pinned to seed 42, 3072 envs, 1501 updates")
    elif getattr(args, "smoke_updates", None) is not None:
        raise ValueError("smoke-updates is reserved for B")
    elif args.force_gt:
        raise ValueError("TopDown requires force_gt=False for AdaSmpl")
    elif args.max_iterations is not None and not 0 < args.max_iterations <= 20000:
        raise ValueError("TopDown max_iterations must be within 1..20000")
    t = time.time() if now is None else now
    deadline = min(t + args.max_wall_s, end_by.timestamp())
    if deadline <= t:
        raise ValueError("deadline has already passed")
    return deadline


def resume_parent(path: str, variant: str) -> dict:
    """Read and validate the parent before opening a distinct output segment."""
    import hashlib
    import torch

    checkpoint = Path(path).resolve(strict=True)
    if not checkpoint.is_file():
        raise ValueError("resume checkpoint is not a file")
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    from foothold_s2.runners.start_runner import CKPT_FORMAT

    expected = CKPT_VARIANT[variant]
    own = state.get("sol23f") or {}
    if checkpoint.name == "model_initial.pt" or own.get("initial_snapshot") is True:
        raise ValueError("initial snapshot is diagnostic and not a completed resume checkpoint")
    if state.get("format") != CKPT_FORMAT or own.get("variant") != expected:
        raise ValueError("resume checkpoint format/variant mismatch")
    if own.get("depth_delay_ticks") != (1 if variant in BUDGET_VARIANTS else 0):
        raise ValueError("resume checkpoint depth_delay_ticks mismatch or missing")
    required = ("iter", "model_state_dict", "optimizer_state_dict", "perception_state_dict",
                "perception_optimizer_state_dict", "adasmpl", "env_state", "rng")
    missing = [key for key in required if key not in state]
    if missing:
        raise ValueError(f"resume checkpoint missing keys: {missing}")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    return {"checkpoint": str(checkpoint), "sha256": digest, "completed_update": int(state["iter"])}


def segment_dir(parent: dict, stamp: str, pid: int) -> Path:
    source = Path(parent["checkpoint"])
    target = source.parent.parent / f"{source.parent.name}_resume_{stamp}_{pid}"
    if target.exists():
        raise FileExistsError(target)
    return target
