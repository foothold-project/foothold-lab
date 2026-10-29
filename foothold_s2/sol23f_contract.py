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


REVERT_SEEDS = (42,)                                            # D21: 되돌림도 원래 시드 42. 다른 시드는 전체 과정 끝의 별도 평가에서만 쓴다.
EXTEND_MAX_ITERATIONS = 3001                                    # 이어 가기 판 총 회차 상한(부모 회차 + N 의 N 은 resume_budget 이 따로 1..1500 으로 잰다)
EX38_CONTINUE_MAX_ITERATIONS = 4502                            # m3001 완료 뒤 m3002..4501, 추가 1500 회
EX39_PARENT_SHA256 = "7ff575f356c27ab6280fa2e01dce40f806bbfdd89d4306ae63c827b3ff16706c"
# EX-35 계열(이어 가기 총 회차 > 1501, 또는 s2a 의 smoke 2)이 부모로 받는 저장본: sha256 -> 그 저장본의 회차. 손 명령(train_sb.py 직접)도 이 표를 통과해야 한다(W19).
RESUME_PARENTS = {
    "4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d": 1500,      # S-B10 model_1500.pt (EX-35 main · smoke2)
    "eba0fbdd7e8cdb2f4a3750ee1125e55063fbb36eb9d1377692fad26f850fb548": 2000,      # EX-35 model_2000.pt (extend · extend_smoke2)
}
COMMAND_MODES = ("start", "s2a", "basic_gait")
COMMAND_CONTRACT = {"start": "start", "s2a": "walkturn_v1", "basic_gait": "basic_gait_v1"}


def is_extended_resume(args) -> bool:
    """이어 가기 판에서 총 회차(--max_iterations)를 1501 보다 크게 주었나: SB 의 smoke 가 아닌 이어 가기일 때만 참."""
    mi = getattr(args, "max_iterations", None)

    return args.variant == "SB" and bool(getattr(args, "resume_from", None)) and getattr(args, "smoke_updates", None) is None and mi is not None and mi > 1501


def budget_iterations(args) -> int:
    """BUDGET 판(B · SB)이 쓸 총 회차: smoke 10, 이어 가기 확장 판은 준 값, 그 밖에는 1501(기존 계약 그대로)."""
    if getattr(args, "smoke_updates", None) == 10:
        return 10
    if getattr(args, "basic_ex39_arm", None) and getattr(args, "smoke_updates", None) == 2:
        return int(args.max_iterations)

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

    out = {"command_mode": mode, "command_contract": COMMAND_CONTRACT[mode], "clock_scatter": getattr(args, "clock_scatter", None) == "on"}
    if mode == "basic_gait":
        from foothold_s2.commands.mixed_core import basic_shares, BASIC_SLOTS, ex39_shares

        share = getattr(args, "basic_new_share", None)
        share = 0.30 if share is None else share
        out["basic_new_share"] = share
        ex39_arm = getattr(args, "basic_ex39_arm", None)
        if ex39_arm:
            out["command_contract"] = "basic_gait_ex39"
        out["basic_shares"] = ex39_shares() if ex39_arm else dict(zip(BASIC_SLOTS, basic_shares(share)))
        out["ex39_arm"] = ex39_arm
    return out


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
    if getattr(args, "basic_ex39_arm", None):
        from foothold_s2.basic_gait_ex38_continue import check_parent

        if sha != EX39_PARENT_SHA256 or getattr(args, "basic_ex39_parent_sha", None) != sha:
            raise ValueError("EX-39 parent SHA256 differs from completed EX-38 model_3001.pt")
        parent = check_parent(path, sha)
        expected = int(getattr(args, "basic_ex39_updates", 0))
        smoke = getattr(args, "smoke_updates", None)
        limit = 2 if smoke == 2 else expected
        if expected not in (1500, 3000) or int(args.max_iterations) != 3002 + limit:
            raise ValueError("EX-39 max_iterations must match the main budget or two-update smoke")
        resume_budget(int(args.max_iterations), parent["completed_update"], limit=limit)
        return parent["completed_update"]
    ex38_cont_sha = getattr(args, "basic_ex38_continue_parent_sha", None)
    if ex38_cont_sha:
        from foothold_s2.basic_gait_ex38_continue import check_parent

        parent = check_parent(path, ex38_cont_sha)
        resume_budget(int(args.max_iterations), parent["completed_update"], limit=1500)
        return parent["completed_update"]
    if getattr(args, "basic_ex38", False) and sha != "4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d":
        raise ValueError("EX-38 parent must be the pinned S-B10 model_1500.pt")

    basic_arm = getattr(args, "basic_extend_arm", None)
    if basic_arm is not None:
        from foothold_s2.basic_gait_extend_parent import check_parent

        parent = check_parent(path, basic_arm, getattr(args, "basic_extend_parent_sha", ""))
        resume_budget(int(args.max_iterations), parent["completed_update"])
        return parent["completed_update"]

    if sha not in RESUME_PARENTS:
        raise ValueError(f"--resume_from 저장본의 sha256 이 허용표에 없다: {sha}")
    parent_iter = RESUME_PARENTS[sha]

    if getattr(args, "smoke_updates", None) is None:
        resume_budget(int(args.max_iterations), parent_iter,
                      limit=18500 if getattr(args, "basic_ex38", False) else 1500)

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
    basic_share = getattr(args, "basic_new_share", None)
    basic_arm = getattr(args, "basic_extend_arm", None)
    basic_sha = getattr(args, "basic_extend_parent_sha", None)
    ex38 = bool(getattr(args, "basic_ex38", False))
    ex39_arm = getattr(args, "basic_ex39_arm", None)
    ex39_updates = getattr(args, "basic_ex39_updates", None)
    ex39_levels = getattr(args, "basic_ex39_level_count", None)
    ex39_sha = getattr(args, "basic_ex39_parent_sha", None)
    ex38_cont = getattr(args, "basic_ex38_continue_parent_sha", None)
    if ex39_arm is not None:
        if (ex39_arm not in ("A", "B") or (ex39_updates, ex39_levels) not in ((1500, 3), (3000, 4))
                or ex39_sha != EX39_PARENT_SHA256 or ex38 or ex38_cont
                or basic_arm is not None or basic_sha is not None
                or args.variant != "SB" or cm != "basic_gait" or cs != "on"
                or not ((getattr(args, "basic_stage", None) == "main" and is_extended_resume(args)
                         and getattr(args, "smoke_updates", None) is None)
                        or (getattr(args, "basic_stage", None) == "smoke"
                            and getattr(args, "smoke_updates", None) == 2))
                or float(basic_share or 0) != 0.40 or p_off != 0.1
                or int(args.max_iterations) != 3002 + (2 if getattr(args, "smoke_updates", None) == 2 else ex39_updates)
                or getattr(args, "fast_gt_only", False)
                or not getattr(args, "basic_lin_vel_z_schedule", False)
                or getattr(args, "basic_feet_regulation_weight", None) is not None):
            raise ValueError("EX-39 requires the pinned EX-38 parent, command distribution and ordinary perception")
        from foothold_s2.rewards.basic_gait_bundle import E1_CANDIDATE

        if any(getattr(args, flag, None) != value for flag, value in (
                ("basic_track_ang_weight", E1_CANDIDATE["track_ang_vel"]),
                ("basic_track_lin_weight", E1_CANDIDATE["track_lin_vel"]),
                ("basic_joint_acc_weight", E1_CANDIDATE["joint_acc"]),
                ("basic_hip_pos_weight", E1_CANDIDATE["hip_pos_penalty"]))):
            raise ValueError("EX-39 must retain EX-38 reward weights")
    elif ex39_updates is not None or ex39_levels is not None or ex39_sha is not None:
        raise ValueError("EX-39 options require an EX-39 arm")
    if ex38_cont and not ex38:
        raise ValueError("EX-38 continuation SHA requires --basic-ex38")
    if ex38_cont and args.max_iterations is not None and args.max_iterations > EX38_CONTINUE_MAX_ITERATIONS:
        raise ValueError(f"EX-38 continuation max_iterations at most {EX38_CONTINUE_MAX_ITERATIONS}")
    fast_gt = bool(getattr(args, "fast_gt_only", False))
    reward_slots = ("basic_feet_regulation_weight", "basic_track_ang_weight",
                    "basic_track_lin_weight", "basic_joint_acc_weight", "basic_hip_pos_weight")
    if (any(getattr(args, name, None) is not None for name in reward_slots)
            or bool(getattr(args, "basic_lin_vel_z_schedule", False))) and basic_arm is None and not ex38 and not ex39_arm:
        raise ValueError("basic reward bundle is reserved for an EX-36 extension parent")
    if basic_arm is not None or ex38 or ex39_arm:
        from foothold_s2.rewards.basic_gait_bundle import validate_settings

        validate_settings({"track_ang_vel": getattr(args, "basic_track_ang_weight", None),
                           "track_lin_vel": getattr(args, "basic_track_lin_weight", None),
                           "joint_acc": getattr(args, "basic_joint_acc_weight", None),
                           "hip_pos_penalty": getattr(args, "basic_hip_pos_weight", None)},
                          bool(getattr(args, "basic_lin_vel_z_schedule", False)),
                          getattr(args, "basic_feet_regulation_weight", None))
    if fast_gt and (basic_arm is None or cm != "basic_gait" or args.variant != "SB"
                    or getattr(args, "basic_stage", None) != "main"
                    or getattr(args, "smoke_updates", None) is not None):
        raise ValueError("fast_gt_only requires a completed EX-36 basic-gait extension parent")
    if ex38:
        from foothold_s2.rewards.basic_gait_bundle import E1_CANDIDATE

        if (basic_arm is not None or basic_sha is not None or fast_gt or args.variant != "SB"
                or cm != "basic_gait" or getattr(args, "basic_stage", None) != "main"
                or getattr(args, "smoke_updates", None) is not None
                or not is_extended_resume(args) or float(basic_share or 0) != 0.30
                or cs != "on" or p_off != 0.1
                or not getattr(args, "basic_lin_vel_z_schedule", False)
                or getattr(args, "basic_feet_regulation_weight", None) is not None
                or any(getattr(args, flag, None) != value for flag, value in (
                    ("basic_track_ang_weight", E1_CANDIDATE["track_ang_vel"]),
                    ("basic_track_lin_weight", E1_CANDIDATE["track_lin_vel"]),
                    ("basic_joint_acc_weight", E1_CANDIDATE["joint_acc"]),
                    ("basic_hip_pos_weight", E1_CANDIDATE["hip_pos_penalty"])))):
            raise ValueError("EX-38 requires pinned parent basic-gait settings and ordinary perception")
    if (basic_arm is None) != (basic_sha is None):
        raise ValueError("EX-36 extend arm and parent SHA must be supplied together")
    if basic_arm is not None and (args.variant != "SB" or cm != "basic_gait"
                                  or getattr(args, "basic_stage", None) != "main"
                                  or not getattr(args, "resume_from", None)
                                  or getattr(args, "smoke_updates", None) is not None
                                  or not is_extended_resume(args)):
        raise ValueError("EX-36 extend requires a main-stage basic-gait SB resume")
    if cm not in (None, *COMMAND_MODES) or cs not in (None, "on", "off"):
        raise ValueError(f"command_mode must be one of {COMMAND_MODES}, clock_scatter on/off")
    if basic_share is not None and cm != "basic_gait":
        raise ValueError("--basic-new-share requires --command_mode basic_gait")
    if cm == "basic_gait":
        from foothold_s2.commands.mixed_core import basic_shares

        basic_shares(0.30 if basic_share is None else basic_share)
        basic_root = getattr(args, "basic_log_root", None)
        basic_stage = getattr(args, "basic_stage", None)
        if not basic_root or not Path(basic_root).is_absolute() or basic_stage not in ("smoke", "main"):
            raise ValueError("basic_gait requires an absolute --basic-log-root and --basic-stage smoke|main")
        if basic_stage == "smoke" and getattr(args, "smoke_updates", None) not in (2, 10):
            raise ValueError("basic smoke stage requires --smoke-updates 2 or 10")
        if basic_stage == "main" and getattr(args, "smoke_updates", None) is not None:
            raise ValueError("basic main stage forbids --smoke-updates")
    elif getattr(args, "basic_log_root", None) is not None or getattr(args, "basic_stage", None) is not None:
        raise ValueError("basic output flags require --command_mode basic_gait")
    if args.variant != "SB" and (cm not in (None, "start") or cs == "on"):
        raise ValueError("non-START command modes and --clock_scatter on are for the SB variant only")
    if (cm == "s2a" or (cs == "on" and cm != "basic_gait")) and getattr(args, "smoke_updates", None) != 2 and not is_extended_resume(args):
        raise ValueError("--command_mode s2a / --clock_scatter on need --resume_from and --max_iterations above 1501 (otherwise 0 updates run and the run ends as done)")
    if cm == "s2a" and getattr(args, "smoke_updates", None) == 10:
        raise ValueError("s2a command mode starts from a parent checkpoint: use --resume_from (smoke 2) or the main resume")
    if verify_parent and args.variant == "SB" and (is_extended_resume(args) or (getattr(args, "smoke_updates", None) == 2 and cm in ("s2a", "basic_gait"))):
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
        if args.num_envs not in (None, 3072) or args.seed not in (None, 42):
            raise ValueError(f"{args.variant} is pinned to seed 42 and 3072 envs, including resume and revert")
        max_total = (3002 + (2 if getattr(args, "smoke_updates", None) == 2 else ex39_updates) if ex39_arm else EX38_CONTINUE_MAX_ITERATIONS if ex38_cont else 20001 if ex38
                     else 3001 if basic_arm is None else {"A": 4501, "B": 3001}.get(basic_arm, 0))
        if args.max_iterations not in (None, 1501) and not ((is_extended_resume(args) or (ex39_arm and getattr(args, "smoke_updates", None) == 2)) and args.max_iterations <= max_total):
            raise ValueError(f"{args.variant} is pinned to 1501 updates (this resume kind allows at most {max_total})")
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
