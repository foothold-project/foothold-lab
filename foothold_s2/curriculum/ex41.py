"""Frozen EX-41 B1 contract. Interface-only revision, not executable."""
from pathlib import Path
from typing import Callable
from foothold_s2.curriculum.continuous import Plan, Runtime, Stage


class EX41Plan(Plan):
    """Plan-compatible stages S2-0/S2a/S2b/S2c/T0_prime.

    Public attributes: is_ex41=True, parent_update=7500, parent_sha256,
    path/sha256/effective_sha256, stages:list[Stage], heading_cfg/stand_cfg,
    domain_randomization, terrain_curriculum, gate_cfg, promotion/shadow_gate,
    boundary_path, approvals_path, stage_meta. load_plan is the public entry.
    stage_meta[id] includes minimum_updates, maximum_updates, terrain policy.
    """
    def __init__(self, path: str | Path, *, arm: str | None = None,
                 smoke_boundaries: tuple[int, ...] | None = None):
        raise NotImplementedError('EX41 interface only')


class EX41Runtime(Runtime):
    """Runtime-compatible local-n state machine plus committed W72 config.

    Public inherited methods: attach/start/on_reset/on_update_start,
    record_pre_step/record_post_step/flush_consumption/on_checkpoint,
    state_dict/load_state_dict/on_resume_checkpoint/after_physical_resume_reset.
    start(parent_sha256) verifies the transfer parent; it is not EX40 scratch.
    Properties: finished:bool, stop_requested:bool, max_updates:int,
    effective:dict, stage_meta and pending evaluation are in checkpoint state.
    Externally supported stage ids: S2-0, S2a, S2b, S2c, T0_prime.
    """
    def __init__(self, plan, env_count: int, device: str, log_dir: str | Path,
                 score_dir: str | Path | None = None,
                 terrain_policy: dict | None = None, segment_index: int = 0):
        raise NotImplementedError('EX41 interface only')

    def set_stage_changed_hook(self, callback: Callable[[Stage, dict], dict]) -> None:
        """Install before attach/start; called at initial application and boundary.

        callback(stage, effective) MUST apply approved terrain/mirror/PPO fields
        and return JSON-serializable actual readback. effective contains:
          iteration:int, stage_id:str, terrain:{policy,level_cap},
          critic_mirror:bool, ppo:{entropy_coef,desired_kl},
          dr:{scale,target_scale,ramp_updates},
          reward_weights:dict, heading:dict, shares:dict, ranges:dict.
        On invalid config callback is never invoked. Callback failure must not
        be reported applied. Rollback requires callback(previous_stage, previous
        effective); failed rollback propagates to the supervisor, never a PASS.
        Commands change per env on reset; global reward/PPO/map fields change at
        update boundary. Effective map usage remains separately logged per env.
        """
        raise NotImplementedError('EX41 interface only')

    def boundary_receipt(self) -> dict | None:
        """Last foothold-ex41-application/1 record, or None before first apply.

        Keys: event_id, status(applied/rejected), iteration, stage_before,
        stage_after, config_commit, config_sha256, approval_sha256,
        score_sha256, checkpoint_sha256, decisions, before, after, readback,
        reason. Persisted in one append-only ex41_application.jsonl in NEW run.
        event_id is deterministic and checkpointed for idempotent resume.
        Rejected config retains before; after never pretends unconsumed values.
        """
        raise NotImplementedError('EX41 interface only')
