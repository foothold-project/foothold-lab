"""One-shot Kit child for S2-2 feet. Import stays CPU-only until kit_main."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import h5py  # noqa: F401  approved native preload
import tensordict  # noqa: F401  approved native preload
import numpy as np
import torch

from s2_foot_scenes import SCENES, SPACING_M, height, terrain_mesh
from s2_foot_config import add_foot_reward
from s2_foot_query import FOOT_NAMES, COLLISION_OFFSET_M, kit_step_record
from s2_foot_manager_evidence import bind_manager_compute


class FootKitHold(RuntimeError):
    pass


def _json(path, value):
    target = Path(path)
    if target.exists():
        raise FootKitHold("output_exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, sort_keys=True, allow_nan=False, indent=2), encoding="utf-8")


def collision_spheres(stage, centers):
    """Read current USD sphere geometry and compare with pose-derived centers."""
    from pxr import UsdGeom, Gf
    cache = UsdGeom.XformCache()
    found = {}
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if not prim.IsA(UsdGeom.Sphere):
            continue
        for name in FOOT_NAMES:
            if name.lower() not in path.lower():
                continue
            sphere = UsdGeom.Sphere(prim)
            matrix = cache.GetLocalToWorldTransform(prim)
            point = matrix.Transform(Gf.Vec3d(0, 0, 0))
            radius = float(sphere.GetRadiusAttr().Get())
            scale = matrix.ExtractScale()
            radius_w = radius * max(float(v) for v in scale)
            found.setdefault(name, []).append({"path": path,
                    "center_w": [float(point[i]) for i in range(3)], "radius_m": radius_w})
    if set(found) != set(FOOT_NAMES):
        raise FootKitHold("usd_foot_collision_spheres_missing")
    selected = []
    for env_idx in range(centers.shape[0]):
        for i, name in enumerate(FOOT_NAMES):
            want = centers[env_idx, i].detach().cpu().numpy()
            rows = [item for item in found[name] if abs(item["radius_m"]-.022) <= .001]
            if not rows:
                raise FootKitHold("usd_foot_collision_radius")
            item = min(rows, key=lambda x: np.linalg.norm(np.asarray(x["center_w"])-want))
            error = float(np.linalg.norm(np.asarray(item["center_w"])-want))
            if error > .001:
                raise FootKitHold("usd_foot_collision_center")
            selected.append(dict(item, body=name, env_index=env_idx, center_error_m=error))
    return selected


def compare_scene_rays(scene, query, origin, anchor):
    """Independent analytic hit Z for every observed ray, with boundary band."""
    xy = query.starts[..., :2].detach().cpu().numpy()
    actual = query.hits[..., 2].detach().cpu().numpy()
    expected = np.empty_like(actual)
    boundary = np.zeros_like(actual, dtype=bool)
    for index in np.ndindex(actual.shape):
        x, y = xy[index] - origin[index[0], :2]
        expected[index] = height(scene, float(x), float(y), anchor=anchor)
        ax, ay = anchor
        if scene in ("straight", "translated_straight"):
            boundary[index] = abs((x-ax)-.025) <= .005
        elif scene == "diagonal":
            boundary[index] = abs((x-ax)+(y-ay)-.075) <= .005
        elif scene in ("cardinal_slot", "finite_hole"):
            edges = ((.04, .06, -.02, .02) if scene == "cardinal_slot" else
                     (.04, .16, -.06, .06))
            boundary[index] = min(abs(x-ax-edges[0]), abs(x-ax-edges[1]),
                                  abs(y-ay-edges[2]), abs(y-ay-edges[3])) <= .005
    finite = np.isfinite(actual)
    nonboundary = ~boundary
    if np.count_nonzero(nonboundary) < 4 or not np.all(finite[nonboundary]):
        raise FootKitHold("scene_nonboundary_ray_missing")
    errors = np.abs(actual[nonboundary]-expected[nonboundary])
    if np.max(errors) > .001:
        raise FootKitHold("scene_ray_height_mismatch")
    return {"nonboundary_count": int(np.count_nonzero(nonboundary)),
            "boundary_count": int(np.count_nonzero(boundary)),
            "max_nonboundary_z_error_m": float(np.max(errors)),
            "expected_hit_z_m": expected.tolist(), "boundary_mask": boundary.tolist()}


def _make_cfg(scene, anchor, num_envs, seed):
    import copy
    from isaaclab.utils import configclass
    from isaaclab.terrains import SubTerrainBaseCfg
    from isaaclab.managers import EventTermCfg
    from isaaclab_tasks.utils import load_cfg_from_registry
    import robot_lab.tasks  # noqa: F401
    from s2_eval_kit_adapter import reset_root_q

    @configclass
    class KnownSceneCfg(SubTerrainBaseCfg):
        function = terrain_mesh
        scene_tag: str = scene
        anchor_xy: tuple[float, float] = anchor

    cfg = copy.deepcopy(load_cfg_from_registry("RobotLab-Go2-v0", "env_cfg_entry_point"))
    cfg.seed = seed
    cfg.scene.num_envs = num_envs
    cfg.sim.device = "cuda:0"
    cfg.scene.terrain.terrain_generator = copy.deepcopy(cfg.scene.terrain.terrain_generator)
    terrain = cfg.scene.terrain.terrain_generator
    terrain.size = (8., 8.)
    terrain.num_rows = 1
    terrain.num_cols = 2 if num_envs == 2 else 1
    terrain.sub_terrains = {"known_" + scene: KnownSceneCfg(size=terrain.size)}
    terrain.curriculum = False
    terrain.use_cache = False
    cfg.scene.terrain.max_init_terrain_level = None
    cfg.events.randomize_push_robot = None
    cfg.events.reset_robot_joints.params["position_range"] = (1., 1.)
    cfg.events.reset_base = EventTermCfg(func=reset_root_q, mode="reset",
        params={"pose_range": {"x": (0., 0.), "y": (0., 0.), "z": (0., 0.)}})
    add_foot_reward(cfg, variant="feet_center_any9_v1", spacing_m=SPACING_M)
    return cfg


def run_scene(scene, anchor, *, seed, steps, total_before, deadline_mono):
    import gymnasium as gym
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
    from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg
    from isaaclab.sim.utils import get_current_stage
    num_envs = 2 if scene == "reset_flat" else 1
    phases = {"create_start_epoch": time.time(), "step_start_epoch": None,
              "close_start_epoch": None, "close_end_epoch": None}
    cfg = _make_cfg(scene, anchor, num_envs, seed)
    raw_env = gym.make("RobotLab-Go2-v0", cfg=cfg)
    raw = raw_env.unwrapped
    raw._q_yaw = torch.zeros(num_envs, device=raw.device)
    def sample_at_reward(query):
        origin = raw.scene.terrain.env_origins.detach().cpu().numpy()
        return {"analytic_rays": compare_scene_rays(scene, query, origin, anchor),
                "usd_collision_spheres": collision_spheres(get_current_stage(), query.centers)}

    manager_receipt = bind_manager_compute(raw, sample_hook=sample_at_reward)
    wrapped = None
    rows = []
    reset_receipt = None
    try:
        wrapped = RslRlVecEnvWrapper(raw_env, clip_actions=MoECTSRunnerCfg().clip_actions)
        obs, _ = raw.reset(seed=seed)
        phases["step_start_epoch"] = time.time()
        if scene == "flat":
            robot = raw.scene["robot"]
            ids, _ = robot.find_bodies(list(FOOT_NAMES), preserve_order=True)
            p = robot.data.body_pos_w[0, ids[0], :2].detach().cpu().numpy()
            origin = raw.scene.terrain.env_origins[0, :2].detach().cpu().numpy()
            anchor = (float(p[0]-origin[0]+COLLISION_OFFSET_M[0]), float(p[1]-origin[1]))
        for local_step in range(steps):
            if time.monotonic() >= deadline_mono or total_before + local_step + 1 > 300:
                raise FootKitHold("foot_deadline_or_control_step_cap")
            action = torch.zeros(num_envs, raw.action_manager.total_action_dim, device=raw.device)
            wrapped.step(action)
            query = raw._s2_foot_last_query
            result = raw._s2_foot_last_cost
            manager = raw._s2_foot_manager_rows[-1]
            ids, names = raw.scene["robot"].find_bodies(list(FOOT_NAMES), preserve_order=True)
            if tuple(names) != FOOT_NAMES:
                raise FootKitHold("foot_body_order")
            row = kit_step_record(query, result, body_ids=ids, dt=float(raw.step_dt),
                                  control_step=total_before+local_step+1,
                                  manager_evidence=manager)
            row["analytic_rays"] = manager["analytic_rays"]
            row["usd_collision_spheres"] = manager["usd_collision_spheres"]
            rows.append(row)
            if scene == "reset_flat" and local_step == 1:
                before = query.episode_id.detach().cpu().tolist()
                raw._s2_foot_explicit_reset = True
                try:
                    raw.reset(env_ids=torch.tensor([0], device=raw.device))
                finally:
                    raw._s2_foot_explicit_reset = False
                after = raw._s2_foot_tracker.episode_id.detach().cpu().tolist()
                if after != [before[0]+1, before[1]]:
                    raise FootKitHold("partial_reset_generation")
                reset_receipt = {"before": before, "after": after, "reset_ids": [0]}
        return {"scene": scene, "rows": rows, "manager_terms": manager_receipt,
                "anchor_xy": anchor, "partial_reset": reset_receipt,
                "reset_events": list(raw._s2_foot_tracker.reset_events),
                "phases": phases}, anchor
    finally:
        phases["close_start_epoch"] = time.time()
        raw_env.close()
        del wrapped, raw, raw_env
        import gc
        gc.collect()
        from isaaclab.sensors.ray_caster.ray_caster import RayCaster
        from isaaclab.sim import SimulationContext
        if SimulationContext.instance() is not None:
            raise FootKitHold("simulation_context_not_released")
        if RayCaster._instance_count != 0 or RayCaster.meshes:
            raise FootKitHold("raycaster_cache_not_released")
        phases["close_end_epoch"] = time.time()


def run(request, output):
    if request.get("scope") != "s2_foot_kit_check_once" or request.get("training_updates") != 0 or \
       request.get("optimizer_steps") != 0 or request.get("scenes") != list(SCENES) or \
       type(request.get("seed")) is not int or \
       type(request.get("max_wall_s")) is not int or not 0 < request["max_wall_s"] <= 900 or \
       type(request.get("steps_per_scene")) is not int or not 1 <= request["steps_per_scene"] <= 37 or \
       request["steps_per_scene"] * len(SCENES) > 300:
        raise FootKitHold("foot_request_scope")
    deadline = time.monotonic() + request["max_wall_s"]
    evidence = []
    anchor = (0., 0.)
    total = 0
    for scene in SCENES:
        scene_anchor = ((anchor[0]+.1, anchor[1]) if scene == "translated_straight" else anchor)
        item, measured_anchor = run_scene(scene, scene_anchor, seed=request["seed"],
                     steps=request["steps_per_scene"], total_before=total,
                     deadline_mono=deadline)
        if scene == "flat":
            anchor = measured_anchor
        evidence.append(item)
        total += request["steps_per_scene"]
    result = {"schema": "s2-foot-kit-check-v1", "scope": request["scope"],
              "training_updates": 0, "optimizer_steps": 0, "control_steps": total,
              "max_envs": 2, "scenes": evidence, "kit_only_evidence": True,
              "natural_termination_tested": any(event["source"] == "natural"
                    for scene in evidence for event in scene["reset_events"]),
              "untested_branches": [] if any(event["source"] == "natural"
                    for scene in evidence for event in scene["reset_events"])
                    else ["natural_termination"]}
    _json(output, result)
    return result


def kit_main(argv=None):
    from isaaclab.app import AppLauncher
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--request-sha256", required=True)
    p.add_argument("--out", required=True)
    AppLauncher.add_app_launcher_args(p)
    a = p.parse_args(argv)
    if (not a.headless or a.device != "cuda:0" or
        os.environ.get("FOOTHOLD_S2_FOOT_PURPOSE") != "one_shot_no_learning" or
        os.environ.get("FOOTHOLD_CONVERSION_CAP") != "8"):
        raise FootKitHold("supervised_foot_only")
    data = Path(a.request).read_bytes()
    if hashlib.sha256(data).hexdigest() != a.request_sha256:
        raise FootKitHold("request_sha256")
    request = json.loads(data)
    launcher = AppLauncher(a)
    try:
        result = run(request, a.out)
    finally:
        launcher.app.close()
    print(json.dumps({"status": "HOLD_PENDING_VERDICT", "steps": result["control_steps"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(kit_main())
