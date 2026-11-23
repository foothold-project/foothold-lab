"""HiPAN first-turn probe on one obstacle-free room. Evaluation only.

The trained teacher emits every command. The lower command space, task
observation and navigation environment are the same consumers as hl_eval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from foothold_s2.nav import teacher_obs

DEFAULT_BEARINGS = (0, 90, -90, 135, -135, 180)
FIRST_FORWARD_MPS = 0.2
MEDIAN_LIMIT_DEG = 20.0
P90_LIMIT_DEG = 35.0
PRE_FORWARD_DRIFT_M = 0.15
REACH_DROP_LIMIT = 0.10


def parse_bearings(raw: str) -> tuple[float, ...]:
    values = tuple(float(s.strip()) for s in raw.split(","))
    if not values or len(set(values)) != len(values) or not all(math.isfinite(x) for x in values):
        raise ValueError("bearings must be distinct finite angles")
    return values


def goal_at_bearing(start_xy, yaw_rad, bearing_deg, distance_m):
    """Positive bearing is to the robot's left, in the room XY frame."""
    if not math.isfinite(distance_m) or distance_m <= 0:
        raise ValueError("goal distance must be positive and finite")
    angle = np.asarray(yaw_rad) + np.deg2rad(bearing_deg)
    start = np.asarray(start_xy, dtype=np.float64)
    return start + distance_m * np.stack((np.cos(angle), np.sin(angle)), axis=-1)


def table_median_distance(task) -> float:
    """Use the actual flat-room task table, not a hand-selected distance."""
    distances = []
    for room in task.table or []:
        for start, row in zip(room["starts"], room["rows"]):
            distances.extend(float(np.linalg.norm(np.asarray(goal) - start))
                             for goal, _path in row["ok"] + row["wound"])
    if not distances:
        raise ValueError("flat-room task table contains no start-goal pairs")
    return float(np.median(distances))


def _path_is_flat(grade, start, goal, margin_m=0.5) -> bool:
    from foothold_s2.nav import grade_map as gm

    samples = start[None] + np.linspace(0.0, 1.0, 64)[:, None] * (goal - start)[None]
    if np.any(samples < margin_m) or np.any(samples > grade.grade.shape[0] * grade.res - margin_m):
        return False
    cells = np.floor(samples / grade.res).astype(int)
    return bool(np.all(grade.grade[cells[:, 0], cells[:, 1]] == gm.FREE))


def place_first_goals(task, state, bearings, episodes_per_bearing, distance_m) -> dict:
    """Replace only the first goal in selected envs; never replace HL actions."""
    pos = teacher_obs.to_room_frame(state.pos_local, task.origin_xy)[:, :2]
    yaw = teacher_obs.yaw_from_quat_wxyz(state.quat_w)
    selected: dict[float, list[int]] = {}
    used: set[int] = set()
    # Diagonal directions have fewer feasible starts in a finite room.
    for bearing in sorted(bearings, key=lambda x: -abs(math.sin(math.radians(x))) * abs(math.cos(math.radians(x)))):
        picked = []
        for i in range(task.n):
            if i in used:
                continue
            goal = goal_at_bearing(pos[i], yaw[i], bearing, distance_m)
            grade = task.assets[task.room_id[i]].grade
            if not _path_is_flat(grade, pos[i], goal):
                continue
            picked.append(i)
            used.add(i)
            task.start[i], task.goal[i] = pos[i].copy(), goal
            task.path[i] = np.stack((pos[i], goal))
            pgcl = task.pgcl[i]
            pgcl.level = 99  # one direct goal, no intervening subgoal
            pgcl.start_episode(task.path[i], grade)
            task.subgoal[i] = pgcl.target.point
            if len(picked) == episodes_per_bearing:
                break
        if len(picked) != episodes_per_bearing:
            raise ValueError(f"bearing {bearing:g} has {len(picked)}/{episodes_per_bearing} flat starts")
        selected[bearing] = picked
    ids = np.array([i for b in bearings for i in selected[b]], dtype=np.int64)
    return {"ids": ids, "bearing_deg": np.repeat(np.asarray(bearings), episodes_per_bearing),
            "start_xy": pos[ids].copy(), "start_yaw": yaw[ids].copy(), "goal_xy": task.goal[ids].copy()}


def judge_turns(bearing_deg, first_error_deg, pre_forward_drift_m, reached, command, valid_tick) -> dict:
    """Predeclared four-part criterion plus the stand-and-spin command share."""
    bearing = np.asarray(bearing_deg)
    errors = np.asarray(first_error_deg, float)
    drift = np.asarray(pre_forward_drift_m, float)
    reached = np.asarray(reached, bool)
    command = np.asarray(command, float)
    valid_tick = np.asarray(valid_tick, bool)
    rows = {}
    for b in sorted(set(bearing.tolist())):
        mask = bearing == b
        finite = np.isfinite(errors[mask]) & np.isfinite(drift[mask])
        err = np.abs(errors[mask][finite])
        away = drift[mask][finite]
        cmd_mask = valid_tick[:, mask]
        cmd = command[:, mask, :3]
        spin = (cmd[..., 0] < .05) & (np.abs(cmd[..., 2]) > .2)
        rows[str(float(b))] = {"envs": int(mask.sum()), "first_forward_envs": int(finite.sum()),
                        "median_abs_error_deg": float(np.median(err)) if len(err) else None,
                        "p90_abs_error_deg": float(np.percentile(err, 90)) if len(err) else None,
                        "max_pre_forward_drift_m": float(away.max()) if len(away) else None,
                        "reached_fraction": float(reached[mask].mean()),
                        "stand_spin_command_fraction": float(spin[cmd_mask].mean()) if cmd_mask.any() else None}
    baseline = rows.get("0.0")
    if baseline is None:
        raise ValueError("0 degree bearing is required as the reach baseline")
    for row in rows.values():
        row["four_parts_pass"] = bool(
            row["first_forward_envs"] == row["envs"]
            and row["median_abs_error_deg"] <= MEDIAN_LIMIT_DEG
            and row["p90_abs_error_deg"] <= P90_LIMIT_DEG
            and row["max_pre_forward_drift_m"] <= PRE_FORWARD_DRIFT_M
            and row["reached_fraction"] >= baseline["reached_fraction"] - REACH_DROP_LIMIT)
    return {"criterion": {"first_forward_mps": FIRST_FORWARD_MPS,
                          "median_abs_error_deg_max": MEDIAN_LIMIT_DEG,
                          "p90_abs_error_deg_max": P90_LIMIT_DEG,
                          "pre_forward_drift_m_max": PRE_FORWARD_DRIFT_M,
                          "reach_drop_from_zero_max": REACH_DROP_LIMIT},
            "rows": rows, "high_level_already_turns": all(r["four_parts_pass"] for r in rows.values())}


def run_probe(env, actor, bearings, episodes_per_bearing, distance_m, max_ticks):
    """Use the saved teacher actor and the real TeacherVecEnv/CommandSpace path."""
    import torch

    obs = env.reset()
    placed = place_first_goals(env.task, env.state, bearings, episodes_per_bearing, distance_m)
    if hasattr(env, "_set_episode_limits"):
        env._set_episode_limits(placed["ids"])
    obs = env._obs(env.state)
    ids, n = placed["ids"], len(placed["ids"])
    first_error = np.full(n, np.nan)
    first_drift = np.full(n, np.nan)
    max_pre_forward = np.zeros(n)
    reached = np.zeros(n, bool)
    finished = np.zeros(n, bool)
    xy_rows, yaw_rows, goal_rows, cmd_rows, stand_rows, reach_rows, active_rows = [], [], [], [], [], [], []
    for _ in range(max_ticks):
        active = ~finished
        with torch.inference_mode():
            action = actor(obs.to(env.device))
        obs, _reward, done, _timeout, _info = env.step(action)
        state = env.state
        xy = teacher_obs.to_room_frame(state.pos_local, env.task.origin_xy)[ids, :2]
        yaw = teacher_obs.yaw_from_quat_wxyz(state.quat_w)[ids]
        cmd = np.asarray(state.applied)[ids, :3].copy()
        hit = np.asarray(env.task_reached, bool)[ids]
        ended = np.asarray(done.cpu().numpy(), bool)[ids]
        before_forward = active & np.isnan(first_error) & ~ended
        max_pre_forward[before_forward] = np.maximum(
            max_pre_forward[before_forward],
            np.linalg.norm(xy[before_forward] - placed["start_xy"][before_forward], axis=1))
        fresh = active & np.isnan(first_error) & (np.asarray(state.vel_b)[ids, 0] > FIRST_FORWARD_MPS) & ~ended
        if fresh.any():
            direction = np.arctan2(placed["goal_xy"][fresh, 1] - xy[fresh, 1],
                                   placed["goal_xy"][fresh, 0] - xy[fresh, 0])
            delta = np.arctan2(np.sin(direction - yaw[fresh]), np.cos(direction - yaw[fresh]))
            first_error[fresh] = np.rad2deg(delta)
            first_drift[fresh] = max_pre_forward[fresh]
        reached |= hit & active
        finished |= ended | hit
        valid = active & ~ended
        xy_rows.append(np.where(valid[:, None], xy, np.nan))
        yaw_rows.append(np.where(valid, yaw, np.nan))
        goal_rows.append(placed["goal_xy"].copy())
        cmd_rows.append(np.where(valid[:, None], cmd, np.nan))
        stand_rows.append(np.where(valid, np.asarray(state.stand)[ids], False))
        reach_rows.append(hit & active)
        active_rows.append(valid)
        if finished.all():
            break
    arrays = {"env_id": ids, "bearing_deg": placed["bearing_deg"],
              "start_xy": placed["start_xy"], "start_yaw": placed["start_yaw"],
              "first_error_deg": first_error, "pre_forward_drift_m": first_drift,
              "reached": reached, "body_xy": np.asarray(xy_rows), "body_yaw": np.asarray(yaw_rows),
              "goal_xy": np.asarray(goal_rows), "command_vx_vy_wz": np.asarray(cmd_rows),
              "stand": np.asarray(stand_rows), "reach_tick": np.asarray(reach_rows),
              "valid_tick": np.asarray(active_rows)}
    return arrays, judge_turns(placed["bearing_deg"], first_error, first_drift, reached,
                               arrays["command_vx_vy_wz"], arrays["valid_tick"])


def _flat_teacher_env(cfg, checkpoint, checkpoint_sha256, num_envs):
    from foothold_s2.lab_compat import require_declared_major
    from foothold_s2.nav import grade_map, kit_factories, nav_task, room_generator as rg

    kit_factories.launch_app(cfg, False)
    require_declared_major()
    from foothold_s2.tasks.nav_env_cfg import build_nav_env
    flat_cfg = rg.RoomConfig(weights=(1.0, 0.0, 0.0, 0.0), layout="old", n_patches=0,
                             sparse_patch_kinds=(), p_wall=0.0, p_table=0.0, p_box=0.0)
    _spec, room = rg.make_room(int(cfg["room_seed"]), cfg=flat_cfg)
    if np.any(room.cell[5:-5, 5:-5] != rg.CELL_FLAT):
        raise ValueError("turn probe room has an obstacle or nonflat interior")
    room_dir = Path(cfg["room_dir"])
    if room_dir.exists():
        raise FileExistsError(f"{room_dir} exists; turn probe never overwrites a room")
    table = grade_map.load_grade_table(cfg["grade_table"])
    manifest = rg.write_rooms([room], room_dir, n_starts=int(cfg["n_starts"]), start_seed=int(cfg["room_seed"]))
    nav, _ = build_nav_env(checkpoint=checkpoint, expected_sha256=checkpoint_sha256,
                           room_mesh_npz=room_dir / "terrain_mesh.npz", room_mesh_sha256=manifest["mesh_sha256"],
                           num_envs=num_envs, device=cfg["device"], seed=int(cfg["seed"]))
    rows = nav.raw.scene.terrain.terrain_levels.cpu().numpy()
    starts = [rg.start_points(room, int(cfg["n_starts"]), seed=int(cfg["room_seed"]))[:, :2]]
    task = kit_factories.make_task([nav_task.make_asset(room, table)], num_envs, int(cfg["seed"]), rows,
                                   nav.raw.scene.env_origins[:, :2].cpu().numpy(), starts,
                                   int(cfg.get("task_table_per_start", 32)),
                                   reach_m=float(cfg["reach_m"]) if "reach_m" in cfg else None)
    return nav, task, manifest


def _sha(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def lower_preflight(path, expected_sha=None):
    import torch
    from foothold_s2.eval.ex41_eval_loader import _input_width

    digest = _sha(path)
    if expected_sha is not None and digest != expected_sha:
        raise ValueError("lower checkpoint SHA differs from the registered checkpoint")
    state = torch.load(path, map_location="cpu", weights_only=False)
    widths = (_input_width(state, "actor.0.weight"), _input_width(state, "critic.0.weight"))
    if state.get("ex41_pose_commands") is not True or widths != (98, 666) or not isinstance(state.get("perception_state_dict"), dict):
        raise ValueError(f"lower checkpoint cannot use the HiPAN EX-41 98/666 adapter: {widths}")
    return {"sha256": digest, "actor_critic_inputs": widths, "pose_commands": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hl-checkpoint", required=True)
    parser.add_argument("--lower-checkpoint", required=True)
    parser.add_argument("--bearings", default="0,90,-90,135,-135,180")
    parser.add_argument("--episodes-per-bearing", type=int, default=32)
    parser.add_argument("--dist-m", type=float)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-ticks", type=int, default=600)
    args = parser.parse_args(argv)
    bearings = parse_bearings(args.bearings)
    if 0 not in bearings or args.episodes_per_bearing < 32 or args.max_ticks < 1:
        parser.error("0 degree baseline, at least 32 episodes per bearing and positive max-ticks required")
    out = Path(args.out)
    if out.suffix != ".npz":
        parser.error("--out must end in .npz")
    if out.exists() or out.with_suffix(".json").exists():
        parser.error("output exists; turn probe never overwrites")
    out.parent.mkdir(parents=True, exist_ok=True)
    from foothold_s2.nav import hl_eval, hl_train, kit_factories

    cfg = kit_factories.load_config()
    cfg["device"] = args.device
    rc = 1
    try:
        kit_factories.launch_app(cfg, False)
        grade_table = Path(__file__).resolve().parents[1] / "nav" / "grade_table_draft.yaml"
        if _sha(grade_table) != "47cc43c84acc39b863873a1f2fa50c7a95d3d96ed9a24fbf138acaedb332ecc1":
            raise ValueError("local grade table differs from the m2000 training code")
        cfg["grade_table"] = str(grade_table)
        canonical_sha = cfg["lower_sha256"] if _sha(args.lower_checkpoint) == cfg["lower_sha256"] else None
        lower = lower_preflight(args.lower_checkpoint, canonical_sha)
        cfg.update(lower_checkpoint=str(Path(args.lower_checkpoint).resolve()), lower_sha256=lower["sha256"],
                   num_envs=max(int(cfg["num_envs"]), args.episodes_per_bearing * len(bearings) * 4),
                   room_count=1, room_dir=str(out.parent / (out.stem + "_flat_room")))
        nav, task, room_manifest = _flat_teacher_env(cfg, args.lower_checkpoint, lower["sha256"], cfg["num_envs"])
        env = hl_train.TeacherVecEnv(nav, task, device=args.device)
        actor, _std, iteration = hl_eval.load_actor(args.hl_checkpoint, device=args.device)
        distance = args.dist_m if args.dist_m is not None else table_median_distance(task)
        arrays, judgment = run_probe(env, actor, bearings, args.episodes_per_bearing, distance, args.max_ticks)
        np.savez_compressed(out, **arrays)
        receipt = {"format": "foothold-hipan-first-turn/1", "hl_checkpoint": str(Path(args.hl_checkpoint).resolve()),
                   "hl_sha256": _sha(args.hl_checkpoint), "iteration": iteration,
                   "lower_checkpoint": str(Path(args.lower_checkpoint).resolve()), "lower": lower,
                   "device": args.device, "distance_m": distance, "distance_source": "task_table_median" if args.dist_m is None else "argument",
                   "episodes_per_bearing": args.episodes_per_bearing, "max_ticks": args.max_ticks,
                   "flat_room_mesh_sha256": room_manifest["mesh_sha256"], "judgment": judgment}
        out.with_suffix(".json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        rc = 0
        print(json.dumps({"out": str(out), "judgment": judgment}, ensure_ascii=False), flush=True)
    finally:
        kit_factories.finish(rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
