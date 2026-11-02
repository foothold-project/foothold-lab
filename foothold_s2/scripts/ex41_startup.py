"""CPU-safe EX-41 launch and score-contract helpers.

This module does not start Isaac or a simulator. The entrypoint uses these
checks before AppLauncher and the simulator setup after authorization.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from foothold_s2.curriculum.continuous import load_plan
from foothold_s2.curriculum.ex41_fixed import CELLS, CASES, baseline_counts, maintenance
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


def configure_ex41_train_cfg(train_cfg: dict[str, Any], plan, parent_path: str | Path) -> dict[str, Any]:
    """Set mandatory transfer flags and the parent reference in a fresh cfg."""
    cfg = dict(train_cfg)
    cfg["ex41_pose_commands"] = True
    cfg["ex41_w86_required"] = True
    cfg["ex41_parent"] = {
        "path": str(Path(parent_path).resolve()),
        "sha256": plan.parent_sha256,
        "iteration": plan.parent_update,
    }
    # The runner uses zero-based iteration indices; one extra loop entry is
    # needed to observe the runtime's terminal completed-update boundary.
    cfg["max_iterations"] = 6501
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
    """Install the fixed terrain, existing DR consumers, and W86 before gym.make."""
    from foothold_s2.curriculum.ex41 import prepare_terrain_cfg
    from foothold_s2.curriculum.ex40_dr_runtime import install_runtime_events
    from foothold_s2.rewards.w86_runtime import prepare_env_cfg

    dr = plan.domain_randomization
    ranges = dr["full_ranges"]
    event_receipt = install_runtime_events(
        env_cfg, ranges, tuple(dr["push_interval_s"]),
        delay_max_s=float(ranges["delay_s"][1]))
    dr_receipt = install_initial_dr_scale(env_cfg, plan.initial_dr_scale)
    terrain_receipt = prepare_terrain_cfg(env_cfg, plan)
    w86_receipt = prepare_env_cfg(env_cfg, plan)
    return {"events": event_receipt, "initial_dr": dr_receipt,
            "terrain": terrain_receipt, "w86": w86_receipt}


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


def maintenance_counts_from_map_modes(map_modes: dict[str, Any], baseline: dict[str, int]) -> dict[str, dict[str, int]]:
    """Convert the fixed map-mode evaluation's 39 survival cells to numbers."""
    if not isinstance(map_modes, dict) or map_modes.get("envs") != 64:
        raise ValueError("EX-41 maintenance source must contain 64-env map modes")
    modes = map_modes.get("modes")
    if not isinstance(modes, dict) or set(modes) != {"eval_gt", "probe_prop_only", "eval_pred"}:
        raise ValueError("EX-41 maintenance source must have all three map modes")
    if set(baseline) != set(CELLS):
        raise ValueError("EX-41 baseline must contain exactly 39 cells")
    out = {}
    for mode in ("eval_gt", "probe_prop_only", "eval_pred"):
        cases = modes[mode]
        if not isinstance(cases, dict) or not set(CASES) <= set(cases):
            raise ValueError(f"EX-41 maintenance source cases incomplete: {mode}")
        for case in CASES:
            row = cases[case]
            if (not isinstance(row, dict) or row.get("env_count") != 64
                    or len(row.get("per_env", [])) != 64
                    or type(row.get("alive_envs_at_end")) is not int
                    or not 0 <= row["alive_envs_at_end"] <= 64):
                raise ValueError(f"EX-41 invalid 64-env count: {mode}/{case}")
            key = f"{mode}/{case}" + ("_record_only" if mode == "eval_pred" else "")
            out[key] = {"passed": row["alive_envs_at_end"],
                        "baseline_passed": baseline[key], "total": 64}
    if set(out) != set(CELLS):
        raise ValueError("EX-41 maintenance count output is not the exact 39-cell set")
    return out


def add_maintenance_counts(score: dict[str, Any], map_modes: dict[str, Any],
                           baseline: dict[str, int], map_modes_path: str | Path) -> dict[str, Any]:
    """Enrich an existing score draft without inventing its stage verdict."""
    if not isinstance(score, dict) or score.get("format") != "foothold-ex41-score/1":
        raise ValueError("EX-41 score draft format differs")
    if (type(score.get("iteration")) is not int
            or not isinstance(score.get("metrics"), dict)
            or not isinstance(score.get("evidence"), list)
            or any(type(score.get(k)) is not bool
                   for k in ("maintenance_pass", "stage_pass", "safety_stop"))):
        raise ValueError("EX-41 score draft fields or existing verdicts missing")
    if (map_modes.get("checkpoint_iter") != score["iteration"]
            or map_modes.get("checkpoint_sha256") != score.get("checkpoint_sha256")):
        raise ValueError("EX-41 map-mode checkpoint does not match score draft")
    checkpoint = Path(score["checkpoint_path"]).resolve(strict=True)
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if (checkpoint.name != f"model_{score['iteration']}.pt"
            or digest != score["checkpoint_sha256"]):
        raise ValueError("EX-41 score checkpoint path or SHA differs")
    counts = maintenance_counts_from_map_modes(map_modes, baseline)
    result = dict(score)
    metrics = dict(result.get("metrics") or {})
    metrics["maintenance_counts"] = counts
    result["metrics"] = metrics
    result["maintenance_pass"] = maintenance(counts, baseline) == []
    evidence = list(result.get("evidence") or [])
    evidence_path = Path(map_modes_path).resolve(strict=True)
    evidence_row = {"path": str(evidence_path),
                    "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest()}
    if evidence_row not in evidence:
        evidence.append(evidence_row)
    result["evidence"] = evidence
    return result


def enrich_score_file(score_path: str | Path, map_modes_path: str | Path,
                      table_path: str | Path, out_path: str | Path) -> Path:
    plan = load_fixed_plan(table_path)
    baseline = baseline_counts(plan)
    score = json.loads(Path(score_path).read_text(encoding="utf-8-sig"))
    map_modes = json.loads(Path(map_modes_path).read_text(encoding="utf-8-sig"))
    if (score.get("schedule_sha256") != plan.effective_sha256
            or score.get("parent_sha256") != plan.parent_sha256
            or score.get("baseline_checkpoint_sha256") != plan.parent_sha256):
        raise ValueError("EX-41 score draft plan or parent differs")
    result = add_maintenance_counts(score, map_modes, baseline, map_modes_path)
    target = Path(out_path)
    if target.resolve() == Path(score_path).resolve():
        raise ValueError("EX-41 enriched score must not overwrite its draft")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(target)
    return target
