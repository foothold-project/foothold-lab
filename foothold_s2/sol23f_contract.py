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


REVERT_SEEDS = (43, 44, 45)                                    # 이어 가기 시드(되돌림 용도로 예약; 가정, lead 04:48 확인). 인자만으로 revert 와 main 을 가를 수 없어 validate 는 이어 가기 전체에 열고, ex35_launch 가 revert 에만 허용한다
EXTEND_MAX_ITERATIONS = 3001                                    # 이어 가기 판 총 회차 상한(부모 회차 + N 의 N 은 resume_budget 이 따로 1..1500 으로 잰다)
# EX-35 계열(이어 가기 총 회차 > 1501, 또는 s2a 의 smoke 2)이 부모로 받는 저장본: sha256 -> 그 저장본의 회차. 손 명령(train_sb.py 직접)도 이 표를 통과해야 한다(W19).
RESUME_PARENTS = {
    "4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d": 1500,      # S-B10 model_1500.pt (EX-35 main · smoke2)
    "eba0fbdd7e8cdb2f4a3750ee1125e55063fbb36eb9d1377692fad26f850fb548": 2000,      # EX-35 model_2000.pt (extend · extend_smoke2)
}
COMMAND_MODES = ("start", "s2a")
COMMAND_CONTRACT = {"start": "start", "s2a": "walkturn_v1"}


def is_extended_resume(args) -> bool:
    """이어 가기 판에서 총 회차(--max_iterations)를 1501 보다 크게 주었나: SB 의 smoke 가 아닌 이어 가기일 때만 참."""
    mi = getattr(args, "max_iterations", None)

    return args.variant == "SB" and bool(getattr(args, "resume_from", None)) and getattr(args, "smoke_updates", None) is None and mi is not None and mi > 1501


def budget_iterations(args) -> int:
    """BUDGET 판(B · SB)이 쓸 총 회차: smoke 10, 이어 가기 확장 판은 준 값, 그 밖에는 1501(기존 계약 그대로)."""
    if getattr(args, "smoke_updates", None) == 10:
        return 10

    return int(args.max_iterations) if is_extended_resume(args) else 1501


def resume_budget(max_iterations: int, parent_completed_update: int, limit: int = 1500) -> dict:
    """이어 가기 확장 판의 회차 영수증: 부모가 끝낸 회차 + 남은 N 회 = 총 회차. N 은 1..limit 이어야 한다."""
    remaining = int(max_iterations) - (int(parent_completed_update) + 1)

    if not 1 <= remaining <= limit:
        raise ValueError(f"max_iterations {max_iterations} 은 부모 회차 {parent_completed_update} 뒤 남은 {remaining} 회를 만든다(허용 1..{limit})")

    return {"parent_completed_update": int(parent_completed_update), "max_iterations": int(max_iterations), "remaining": remaining}


def command_settings(args) -> dict:
    """명령 처치 설정(manifest): 표집기 이름 · 계약 이름 · 흩기."""
    mode = getattr(args, "command_mode", None) or "start"

    return {"command_mode": mode, "command_contract": COMMAND_CONTRACT[mode], "clock_scatter": getattr(args, "clock_scatter", None) == "on"}


def file_sha256(path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)

    return h.hexdigest()


def check_resume_parent(args) -> int:
    """이어 가기 부모 저장본의 sha256 을 RESUME_PARENTS 와 대조하고 그 회차를 돌려준다. 이어 가기 총 회차는 부모 회차 뒤 1 회 이상이어야 한다(0 회 판 거절)."""
    path = getattr(args, "resume_from", None)

    if not path or not Path(path).is_file():
        raise ValueError(f"--resume_from 저장본 파일이 없다: {path}")
    sha = file_sha256(path)

    if sha not in RESUME_PARENTS:
        raise ValueError(f"--resume_from 저장본의 sha256 이 허용표에 없다: {sha}")
    parent_iter = RESUME_PARENTS[sha]

    if getattr(args, "smoke_updates", None) is None:
        resume_budget(int(args.max_iterations), parent_iter)                     # 남은 회차 1..1500 (0 회 · 너무 긴 판 거절)

    return parent_iter


def validate_launch(args, hydra_args=(), now: float | None = None, verify_parent: bool = True) -> float:
    """verify_parent=False 는 CPU 시험 전용(가짜 경로). 실제 기동(train_sol23f_common)은 기본값 True 로 부른다."""
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
    cm, cs = getattr(args, "command_mode", None), getattr(args, "clock_scatter", None)
    if cm not in (None, *COMMAND_MODES) or cs not in (None, "on", "off"):
        raise ValueError(f"command_mode must be one of {COMMAND_MODES}, clock_scatter on/off")
    if args.variant != "SB" and (cm not in (None, "start") or cs == "on"):
        raise ValueError("--command_mode s2a and --clock_scatter on are for the SB variant only")
    if (cm == "s2a" or cs == "on") and getattr(args, "smoke_updates", None) != 2 and not is_extended_resume(args):
        raise ValueError("--command_mode s2a / --clock_scatter on need --resume_from and --max_iterations above 1501 (otherwise 0 updates run and the run ends as done)")
    if cm == "s2a" and getattr(args, "smoke_updates", None) == 10:
        raise ValueError("s2a command mode starts from a parent checkpoint: use --resume_from (smoke 2) or the main resume")
    if verify_parent and args.variant == "SB" and (is_extended_resume(args) or (getattr(args, "smoke_updates", None) == 2 and cm == "s2a")):
        check_resume_parent(args)
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
        if args.num_envs not in (None, 3072) or not (args.seed in (None, 42) or (args.seed in REVERT_SEEDS and is_extended_resume(args))):
            raise ValueError(f"{args.variant} is pinned to seed 42 (a resume run may use one of {REVERT_SEEDS}) and 3072 envs")
        if args.max_iterations not in (None, 1501) and not (is_extended_resume(args) and args.max_iterations <= EXTEND_MAX_ITERATIONS):
            raise ValueError(f"{args.variant} is pinned to 1501 updates (a SB resume run may give a larger total, at most {EXTEND_MAX_ITERATIONS})")
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
