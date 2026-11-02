"""CPU-safe EX-41 launch and score-contract helpers.

This module does not start Isaac or a simulator. The entrypoint uses these
checks before AppLauncher and the simulator setup after authorization.
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.curriculum import w72


def load_fixed_plan(path: str | Path):
    plan = load_plan(path, arm="B")
    if not getattr(plan, "fixed_schedule", None):
        raise ValueError("EX-41 startup requires the approved fixed5000 plan")
    if plan.parent_update != 6000 or plan.initial_dr_scale != 0.5:
        raise ValueError("EX-41 startup parent or initial DR scale differs")
    return plan


def authorization_snapshot(plan) -> dict[str, Any]:
    """Read committed W72 files. Does not alter boundary or approval state."""
    return w72.read_committed_pair(plan.boundary_path, plan.approvals_path)


def require_production_authorization(plan) -> dict[str, Any]:
    snapshot = authorization_snapshot(plan)
    values = snapshot["config"]["values"]
    if values.get("w71_ready") is not True:
        raise ValueError("EX-41 production start blocked: W71 consumer is not verified")
    return snapshot


def validate_rehearsal_request(updates: int, output_dir: str | Path,
                               device: str, headless: bool,
                               distributed: bool = False) -> Path:
    """Allow only the explicitly bounded, isolated 10-update Kit rehearsal."""
    if type(updates) is not int or updates != 10:
        raise ValueError("EX-41 rehearsal is fixed to exactly 10 updates")
    path = Path(output_dir)
    if not path.is_absolute() or path.parent.name.lower() != "s2_lab":
        raise ValueError("EX-41 rehearsal output must be an absolute s2_lab child")
    if not re.fullmatch(r"ex41_rehearsal_[0-9]{8}_[0-9]{6}", path.name):
        raise ValueError("EX-41 rehearsal output must use ex41_rehearsal_YYYYMMDD_HHMMSS")
    if device != "cuda:0" or not headless or distributed:
        raise ValueError("EX-41 rehearsal requires headless cuda:0 and one process")
    if path.exists() and any(path.iterdir()):
        raise ValueError("EX-41 rehearsal output must be new or empty")
    return path


def configure_ex41_train_cfg(train_cfg: dict[str, Any], plan, parent_path: str | Path,
                             rehearsal_updates: int | None = None) -> dict[str, Any]:
    """Set mandatory transfer flags and the parent reference in a fresh cfg."""
    cfg = dict(train_cfg)
    cfg["ex41_pose_commands"] = True
    cfg["ex41_w86_required"] = True
    cfg["ex41_parent"] = {
        "path": str(Path(parent_path).resolve()),
        "sha256": plan.parent_sha256,
        "iteration": plan.parent_update,
    }
    if rehearsal_updates is None:
        # The runner uses zero-based iteration indices; one extra loop entry is
        # needed to observe the runtime's terminal completed-update boundary.
        cfg["max_iterations"] = 6501
    else:
        if type(rehearsal_updates) is not int or rehearsal_updates != 10:
            raise ValueError("EX-41 rehearsal is fixed to exactly 10 updates")
        cfg["max_iterations"] = rehearsal_updates
        cfg["save_interval"] = 1
        cfg["ex41_rehearsal"] = True
    if cfg.get("ex41_w86_required") is not True:
        raise ValueError("EX-41 requires W86")
    return cfg


def verify_m6000_parent(plan, parent_path: str | Path) -> dict[str, Any]:
    """Verify the selected parent bytes, run manifest, and pinned saved configs."""
    checkpoint = Path(parent_path).resolve(strict=True)
    if checkpoint.name != "model_6000.pt":
        raise ValueError("EX-41 parent must be model_6000.pt")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if digest != plan.parent_sha256:
        raise ValueError("EX-41 m6000 checkpoint SHA differs from fixed plan")
    manifest_path = checkpoint.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (manifest.get("checkpoints", {}).get(checkpoint.name) != digest
            or not isinstance(manifest.get("progress", {}).get("completed_updates"), int)
            or manifest["progress"]["completed_updates"] < 6000):
        raise ValueError("EX-41 m6000 checkpoint manifest does not prove saved progress")
    params = checkpoint.parent / "params"
    env_path, agent_path = params / "env.yaml", params / "agent.yaml"
    if hashlib.sha256(env_path.read_bytes()).hexdigest() != plan.baseline_env_yaml_sha256:
        raise ValueError("EX-41 parent env.yaml SHA differs from fixed plan")
    if hashlib.sha256(agent_path.read_bytes()).hexdigest() != plan.baseline_agent_yaml_sha256:
        raise ValueError("EX-41 parent agent.yaml SHA differs from fixed plan")
    return {"checkpoint": str(checkpoint), "sha256": digest,
            "completed_updates": manifest["progress"]["completed_updates"],
            "env_yaml_sha256": plan.baseline_env_yaml_sha256,
            "agent_yaml_sha256": plan.baseline_agent_yaml_sha256}


def prepare_ex41_env_cfg(env_cfg: Any, plan) -> dict[str, Any]:
    """Install EX-41-only pose observations, terrain, DR consumers, and W86 before gym.make."""
    from foothold_s2.curriculum.ex41 import prepare_terrain_cfg
    from foothold_s2.curriculum.ex40_dr_runtime import install_runtime_events
    from foothold_s2.rewards.w86_runtime import prepare_env_cfg
    from foothold_s2.sensors.start_obs import apply_ex41_pose_observation

    dr = plan.domain_randomization
    ranges = dr["full_ranges"]
    apply_ex41_pose_observation(env_cfg)
    pose_receipt = {"group": "pose_cmd", "shape_per_env": [2],
                    "columns": ["height_delta_m", "body_roll_rad"],
                    "configured_value": [0.0, 0.0],
                    "producer": "foothold_s2.sensors.start_obs.zero_pose_command"}
    event_receipt = install_runtime_events(
        env_cfg, ranges, tuple(dr["push_interval_s"]),
        delay_max_s=float(ranges["delay_s"][1]))
    dr_receipt = install_initial_dr_scale(env_cfg, plan.initial_dr_scale)
    terrain_receipt = prepare_terrain_cfg(env_cfg, plan)
    w86_receipt = prepare_env_cfg(env_cfg, plan)
    return {"events": event_receipt, "initial_dr": dr_receipt,
            "terrain": terrain_receipt, "w86": w86_receipt,
            "pose_observation": pose_receipt}


def first_observation_readback(raw: Any, expected_envs: int) -> dict[str, Any]:
    """Validate and summarize the actual first TensorDict consumed by StartRunner."""
    required = {"policy": [45], "depth": [60, 60], "gt_map": [512],
                "gt_feet": [100], "base_vel": [3], "contacts": [4],
                "pose_cmd": [2]}
    groups = {}
    for name, expected_shape in required.items():
        if name not in raw.keys():
            raise ValueError(f"EX-41 first observation missing group {name}")
        value = raw[name]
        got = list(value.shape[1:])
        if name == "depth" and value[0].numel() == 3600:
            got = [60, 60]
        if got != expected_shape or int(value.shape[0]) != int(expected_envs):
            raise ValueError(f"EX-41 first observation shape differs for {name}: {list(value.shape)}")
        groups[name] = list(value.shape[1:])
    pose = raw["pose_cmd"]
    if not bool(pose.isfinite().all().item()):
        raise ValueError("EX-41 first pose_cmd is not finite")
    nonzero_by_column = pose.detach().ne(0).any(dim=0).cpu().tolist()
    if nonzero_by_column != [False, False]:
        raise ValueError("EX-41 first pose_cmd columns are not both zero")
    return {"groups": groups,
            "pose_cmd": {"columns": ["height_delta_m", "body_roll_rad"],
                         "zero_by_column": [True, True],
                         "shape": list(pose.shape)}}


@contextmanager
def capture_first_observation(env: Any):
    """Record StartRunner's existing first read without computing observations twice."""
    original = env.get_observations
    receipt: dict[str, Any] = {}

    def capture(*args, **kwargs):
        raw = original(*args, **kwargs)
        if not receipt:
            receipt.update(first_observation_readback(raw, env.num_envs))
        return raw

    env.get_observations = capture
    try:
        yield receipt
    finally:
        env.get_observations = original


def install_initial_dr_scale(env_cfg: Any, scale: float) -> dict[str, Any]:
    """Seed the existing EX40 reset terms before the environment's first reset.

    Isaac's reset manager calls these configured functions with the environment
    and env_ids. Wrapping the actual registered functions makes the initial
    scale visible to the existing DR consumers without replacing their logic.
    """
    if type(scale) not in (int, float) or float(scale) != 0.5:
        raise ValueError("EX-41 initial DR scale must be the approved 0.5")
    events = getattr(env_cfg, "events", None)
    names = ("ex40_base_com", "ex40_actuator_gains", "ex40_motor_strength")
    rows = {}
    for name in names:
        term = getattr(events, name, None)
        func = getattr(term, "func", None)
        if not callable(func):
            raise ValueError(f"EX-41 reset DR consumer missing: {name}")

        def seeded(env, *args, _func=func, **kwargs):
            env._ex40_dr_scale = 0.5
            env._ex41_initial_dr_scale_applied = 0.5
            return _func(env, *args, **kwargs)

        term.func = seeded
        rows[name] = "wrapped-existing-reset-consumer"
    return {"scale": 0.5, "before_first_reset": True, "reset_terms": rows}


def set_live_initial_dr_scale(dr_runtime: Any, env: Any, scale: float) -> dict[str, Any]:
    """Align the existing runtime readback and env before the first rollout."""
    if type(scale) not in (int, float) or float(scale) != 0.5:
        raise ValueError("EX-41 initial DR scale must be the approved 0.5")
    dr_runtime.scale = 0.5
    env._ex40_dr_scale = 0.5
    if getattr(env, "_ex40_dr_scale", None) != 0.5 or dr_runtime.scale != 0.5:
        raise ValueError("EX-41 initial DR readback did not apply")
    return {"runtime_scale": dr_runtime.scale, "env_scale": env._ex40_dr_scale}


def enrich_score_file(score_path: str | Path, map_modes_path: str | Path,
                      stand_paths: dict[str, str | Path],
                      table_path: str | Path, out_path: str | Path) -> Path:
    """Use the analyst-owned raw-evidence contract for all EX-41 score fields."""
    from foothold_s2.curriculum.ex41_scoring import enrich_score_metrics

    plan = load_fixed_plan(table_path)
    score = json.loads(Path(score_path).read_text(encoding="utf-8-sig"))
    result = enrich_score_metrics(score, map_modes_path, stand_paths, plan)
    target = Path(out_path)
    if target.resolve() == Path(score_path).resolve():
        raise ValueError("EX-41 enriched score must not overwrite its draft")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(target)
    return target
