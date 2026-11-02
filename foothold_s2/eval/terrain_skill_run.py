"""W78 terrain skill suite (lead 11/01): stairs sideways · backwards · climb-then-turn-down · climb-then-back-down, steep slope.
Imported by eval_map_modes after its app setup, like axis_v2_run. Same contract as W57: one fixed terrain assignment,
heading off, fixed command per phase, raw arrays kept, no pass threshold (a later card sets one).

Geometry (Isaac Lab pyramid generators): `pyramid_stairs` / `hf_pyramid_slope` rise toward the tile centre, the `_inv`
kinds sink toward it, and every robot resets near its tile centre. So walking outward descends on the first and climbs on
the second, whatever the heading. Each case names the kinds it is about (`kinds`); all 64 envs run every case and the
summary is split by kind, so the other kinds are a free control.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import torch

from foothold_s2.eval import axis_v2_cells as cells
from foothold_s2.eval import map_mode_cells
from foothold_s2.eval.axis_v2_run import foot_ids, _atomic_json, _finite, yaw_from_quat
from foothold_s2.runners.manifest import sha256_file

STAIRS = ("pyramid_stairs", "pyramid_stairs_inv")
SLOPES = ("hf_pyramid_slope", "hf_pyramid_slope_inv")
# name: (phases [(command (vx, vy, wz), seconds)], kinds the case is about)
CASES = {
    "stairs_fwd": ([((0.5, 0.0, 0.0), 6.0)], STAIRS),
    "stairs_side_left": ([((0.0, 0.5, 0.0), 6.0)], STAIRS),
    "stairs_side_right": ([((0.0, -0.5, 0.0), 6.0)], STAIRS),
    "stairs_back": ([((-0.5, 0.0, 0.0), 6.0)], STAIRS),
    "stairs_fwd_turn_return": ([((0.5, 0.0, 0.0), 4.0), ((0.0, 0.0, 1.2), 2.6), ((0.5, 0.0, 0.0), 4.0)], STAIRS),
    "stairs_fwd_back_return": ([((0.5, 0.0, 0.0), 4.0), ((-0.5, 0.0, 0.0), 4.0)], STAIRS),
    "slope_fwd1.0": ([((1.0, 0.0, 0.0), 5.0)], SLOPES),
    # yaw bias at 1.0 m/s with the training heading controller off (as W57) and on (as 50 % of training forward episodes)
    "flat_fwd1.0": ([((1.0, 0.0, 0.0), 6.0)], ("random_rough", "boxes")),
    "flat_fwd1.0_heading": ([((1.0, 0.0, 0.0), 6.0)], ("random_rough", "boxes")),
}
HEADING_CASES = {"flat_fwd1.0_heading"}   # heading on, target = reset yaw; the command term computes wz itself


def case_steps(phases, dt: float) -> list[int]:
    steps = [int(round(seconds / dt)) for _cmd, seconds in phases]
    if any(s < 1 for s in steps):
        raise ValueError("every phase needs at least one control step")
    return steps


def execute_phases(env, raw, robot, term, policy, sensor, feet, phases, steps, heading=False):
    """Per-step command boundary identical to axis_v2_run.execute_case_loop (stand off). heading=False as W57;
    heading=True keeps the term's own heading wz (target = reset yaw) and only sets vx, vy."""
    n, total = env.num_envs, sum(steps)
    alive = torch.ones(n, dtype=torch.bool, device=raw.device)
    z = torch.zeros(total, n, device=raw.device)
    xy = torch.zeros(total, n, 2, device=raw.device)
    vx, vy, wz = torch.zeros_like(z), torch.zeros_like(z), torch.zeros_like(z)
    valid = torch.zeros(total, n, dtype=torch.bool, device=raw.device)
    contact = torch.zeros(total, n, 4, dtype=torch.bool, device=raw.device)
    cmd_post = torch.zeros(total, n, 3, device=raw.device)
    yaw = torch.zeros(total, n, device=raw.device)
    psi0 = yaw_from_quat(robot.data.root_quat_w).clone()
    origin = raw.scene.env_origins[:, :2].clone()
    obs = env.get_observations()
    step = 0
    for (command, _sec), count in zip(phases, steps):
        for _ in range(count):
            if heading:
                term.vel_command_b[:, :2] = torch.tensor(command[:2], device=raw.device)
                if step == 0:
                    term.vel_command_b[:, 2] = 0.0
                term.heading.fill_(True)
                term.psi_star.copy_(psi0)
            else:
                term.vel_command_b[:, :3] = torch.tensor(command, device=raw.device)
                term.heading.fill_(False)
                term.psi_star.zero_()
            term.stand.fill_(False)
            action = policy(obs)
            obs, _reward, done, _extras = env.step(action)
            cmd_post[step] = term.vel_command_b[:, :3]
            policy.reset(done)
            valid[step] = alive & ~done.bool()
            alive &= ~done.bool()
            data = robot.data
            z[step] = data.root_pos_w[:, 2]
            yaw[step] = yaw_from_quat(data.root_quat_w)
            xy[step] = data.root_pos_w[:, :2] - origin
            vx[step] = data.root_lin_vel_b[:, 0]
            vy[step] = data.root_lin_vel_b[:, 1]
            wz[step] = data.root_ang_vel_b[:, 2]
            contact[step] = torch.linalg.vector_norm(sensor.data.net_forces_w[:, feet], dim=-1) > cells.CONTACT_N
            step += 1
    return {"z": z, "xy": xy, "vx": vx, "vy": vy, "wz": wz, "valid": valid, "contact": contact, "cmd_post": cmd_post, "yaw": yaw, "psi0": psi0}


def env_rows(tiles, z0, z, xy, valid, steps, yaw=None, psi0=None):
    """Per env: survival, height change and outward distance at each phase end (last valid sample)."""
    ends = np.cumsum(steps) - 1
    radius = np.linalg.norm(xy, axis=-1)
    rows = []
    for i, tile in enumerate(tiles):
        alive_end = bool(valid[-1, i])
        last = int(np.nonzero(valid[:, i])[0][-1]) if valid[:, i].any() else -1
        phase = []
        for e in ends:
            k = min(int(e), last)
            phase.append({"dz_m": _finite(z[k, i] - z0[i]) if k >= 0 else None,
                          "radius_m": _finite(radius[k, i]) if k >= 0 else None,
                          "alive": bool(valid[int(e), i])})
        rows.append({**tile, "alive_end": alive_end, "alive_steps": int(valid[:, i].sum()),
                     "dz_max_m": _finite(np.max(z[: last + 1, i]) - z0[i]) if last >= 0 else None,
                     "dz_min_m": _finite(np.min(z[: last + 1, i]) - z0[i]) if last >= 0 else None,
                     "dyaw_deg": (_finite(np.degrees(np.unwrap(np.concatenate([[psi0[i]], yaw[: last + 1, i]]))[-1] - psi0[i]))
                                  if yaw is not None and last >= 0 else None),
                     "phases": phase})
    return rows


def run_suite(args, env, raw, robot, term, agent_cfg, adapters, fixed_terrain,
              terrain_names, dr_off, curriculum_off, run_identity):
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    final, partial = out_dir / "terrain_skill.json", out_dir / "terrain_skill.partial.json"
    if final.exists() or partial.exists():
        raise RuntimeError("W78 requires a fresh output directory")
    if not args.fixed_terrain or args.fixed_level is None or args.terrain_set != "default":
        raise ValueError("W78 requires --fixed-terrain --fixed-level N on the default terrain set")
    n, dt = env.num_envs, float(raw.step_dt)
    sensor, feet = foot_ids(raw)
    if bool(term.is_flag_env.any()):
        raise RuntimeError("W78 fixed command suite requires no flag environments")
    source_paths = (Path(__file__), Path(cells.__file__), Path(sys.modules["__main__"].__file__),
                    Path(adapters.__file__), Path(fixed_terrain.__file__))
    result = {"schema": "foothold-terrain-skill/1", "suite": "W78-v1",
              "checkpoint": args.checkpoint, "checkpoint_sha256": sha256_file(args.checkpoint),
              "ex41_checkpoint_preparation": getattr(args, "ex41_checkpoint_preparation", None),
              "source_sha256": {p.name: sha256_file(str(p)) for p in source_paths}, "run_identity": run_identity,
              "envs": n, "dt_s": dt, "eval_seed": args.eval_seed, "fixed_level": args.fixed_level,
              "dr_off": dr_off, "curriculum_off": curriculum_off,
              "cases": {k: {"phases": [[list(c), s] for c, s in v[0]], "kinds": list(v[1])} for k, v in CASES.items()},
              "modes": {}, "terrain_tiles": None,
              "measurement_note": "dz = body height change from the reset pose; radius = distance from the tile origin; no pass threshold"}
    for mode in args.modes.split(","):
        if mode not in ("eval_gt", "eval_pred", "probe_prop_only"):
            raise ValueError(f"unknown W78 map mode {mode!r}")
        runner, sd = adapters.load_s2_runner(
            env, agent_cfg.to_dict(), args.checkpoint, args.device,
            checkpoint_state=getattr(args, "ex41_checkpoint_state", None))
        result.setdefault("checkpoint_iter", int(sd.get("iter", -1)))
        result["modes"][mode] = {}
        for name, (phases, kinds) in CASES.items():
            steps = case_steps(phases, dt)
            torch.manual_seed(args.eval_seed)
            env.reset()
            terrain_record = fixed_terrain.apply(raw, args.fixed_level)
            env.reset()
            terrain = raw.scene.terrain
            tiles = map_mode_cells.terrain_rows(terrain.terrain_levels.cpu().numpy(),
                                                terrain.terrain_types.cpu().numpy(), terrain_names)
            if not {t["kind"] for t in tiles} >= set(kinds):
                raise RuntimeError(f"W78 terrain assignment lacks {kinds} for {name}")
            if result["terrain_tiles"] is None:
                result["terrain_tiles"], result["fixed_terrain"] = tiles, terrain_record
            elif tiles != result["terrain_tiles"]:
                raise RuntimeError("W78 terrain assignment changed between cases")
            z0 = robot.data.root_pos_w[:, 2].clone().cpu().numpy()
            policy = adapters.S2Policy(runner, n, z_mode="mean", act_mode="mean", map_mode=mode)
            policy.reset(torch.ones(n, dtype=torch.bool, device=raw.device))
            map_mode_cells.disable_heading_for_fixed_eval(term)
            s = execute_phases(env, raw, robot, term, policy, sensor, feet, phases, steps, heading=name in HEADING_CASES)
            z, xy, valid = (s[k].cpu().numpy() for k in ("z", "xy", "valid"))
            rows = env_rows(tiles, z0, z, xy, valid, steps, s["yaw"].cpu().numpy(), s["psi0"].cpu().numpy())
            by_kind = {}
            for kind in sorted({t["kind"] for t in tiles}):
                sel = [r for r in rows if r["kind"] == kind]
                by_kind[kind] = {"env_count": len(sel), "alive_at_end": sum(r["alive_end"] for r in sel),
                                 "dyaw_median_deg": cells.finite_median([r["dyaw_deg"] for r in sel]),
                                 "phase_dz_median_m": [cells.finite_median([r["phases"][p]["dz_m"] for r in sel])
                                                       for p in range(len(steps))],
                                 "phase_radius_median_m": [cells.finite_median([r["phases"][p]["radius_m"] for r in sel])
                                                           for p in range(len(steps))],
                                 "phase_alive": [sum(r["phases"][p]["alive"] for r in sel) for p in range(len(steps))]}
            filename = f"terrain_skill_{mode}_{name}.npz"
            np.savez_compressed(out_dir / filename, z=z, xy=xy, vx=s["vx"].cpu().numpy(), vy=s["vy"].cpu().numpy(),
                                wz=s["wz"].cpu().numpy(), yaw=s["yaw"].cpu().numpy(), valid=valid, contact=s["contact"].cpu().numpy(),
                                cmd_post=s["cmd_post"].cpu().numpy(), z0=z0, phase_steps=np.array(steps),
                                terrain_kind=np.array([r["kind"] for r in tiles]), dt=dt)
            result["modes"][mode][name] = {"kinds": list(kinds), "phase_steps": steps, "by_terrain_kind": by_kind,
                                           "raw_file": filename, "raw_sha256": sha256_file(str(out_dir / filename)),
                                           "per_env": rows}
            _atomic_json(partial, result)
            focus = {k: (by_kind[k]["alive_at_end"], by_kind[k]["phase_dz_median_m"], by_kind[k]["dyaw_median_deg"]) for k in kinds}
            print("TERRAIN_SKILL_CASE", mode, name, json.dumps(focus), flush=True)
    _atomic_json(final, result)
    partial.unlink()
    print("TERRAIN_SKILL_DONE", final, flush=True)
    return result
