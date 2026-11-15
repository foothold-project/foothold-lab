"""Evaluation-only RobotLab adapter. Import after AppLauncher; never used by training.

The cfg changes follow _eval/q_eval_cmdr.py:228-301,335-386. The reset hook
follows Isaac Lab manager_based_rl_env.py:204-241. Live Kit behavior is unverified.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from s2_eval_case_fingerprint import (assign_one_case, tile_mesh_sha,
                                      initial_state_sha, case_fingerprint,
                                      ray_usd_correspondence)
from s2_eval_cases import canonical
from s2_eval_cpu import sha
from s2_eval_pre_reset import PreResetStep
from s2_env_adapter_17v import yaw_from_quat_wxyz
from s2_packet_17v import AtomicPacket
from s2_sensor_tracker_17v import SensorUpdateTracker


class KitAdapterHold(RuntimeError):
    pass


def checked_mount(scanner):
    """A3.2 approved source check, copied from s2_train_entry_17v.py:54-72."""
    try:
        pos, quat = scanner._offset
        pos, quat = pos.detach(), quat.detach()
        if pos.ndim != 2 or quat.ndim != 2 or pos.shape[1] != 3 or quat.shape != (pos.shape[0], 4):
            raise ValueError("sensor mount shape")
        if not bool(torch.isfinite(pos).all() and torch.isfinite(quat).all()):
            raise ValueError("sensor mount nonfinite")
        if not bool(torch.all(pos == pos[0])) or not bool(torch.all(quat == quat[0])):
            raise ValueError("sensor mount varies by env")
        identity = torch.tensor([1., 0., 0., 0.], device=quat.device, dtype=quat.dtype)
        if not bool(torch.allclose(quat[0], identity, atol=1e-6)):
            raise ValueError("sensor mount rotation")
        value = tuple(float(x) for x in pos[0].tolist())
        if value != (0., 0., 0.):
            raise ValueError("sensor mount nonzero")
        return value
    except Exception as ex:
        raise KitAdapterHold("sensor_mount_unverified:" + str(ex)) from ex


def reset_root_q(env, env_ids, pose_range, asset_cfg=None):
    """The pinned Q reset: xy/z uniform offset, yaw fixed, body velocity zero."""
    import isaaclab.utils.math as math_utils
    if asset_cfg is None:
        from isaaclab.managers import SceneEntityCfg
        asset_cfg = SceneEntityCfg("robot")
    asset = env.scene[asset_cfg.name]
    root = asset.data.default_root_state[env_ids].clone()
    bounds = torch.tensor([pose_range.get(k, (0., 0.)) for k in ("x", "y", "z")], device=asset.device)
    offset = math_utils.sample_uniform(bounds[:, 0], bounds[:, 1], (len(env_ids), 3), device=asset.device)
    pos = root[:, :3] + env.scene.env_origins[env_ids] + offset
    yaw = env._q_yaw[env_ids]
    zero = torch.zeros_like(yaw)
    quat = math_utils.quat_mul(root[:, 3:7], math_utils.quat_from_euler_xyz(zero, zero, yaw))
    asset.write_root_pose_to_sim(torch.cat([pos, quat], dim=-1), env_ids=env_ids)
    asset.write_root_velocity_to_sim(torch.zeros(len(env_ids), 6, device=asset.device), env_ids=env_ids)


def _source(path, expected):
    p = Path(path).resolve(strict=True)
    if sha(p) != expected:
        raise KitAdapterHold("terrain_source_sha256")
    return p


def _cfg(case):
    import gymnasium as gym  # noqa: F401  registry is imported below
    from isaaclab.managers import EventTermCfg
    from isaaclab_tasks.utils import load_cfg_from_registry
    import robot_lab.tasks  # noqa: F401
    from robot_lab.tasks.go2.mdp.terrains import TERRAIN_CFG

    base = load_cfg_from_registry("RobotLab-Go2-v0", "env_cfg_entry_point")
    cfg = copy.deepcopy(base)
    cfg.scene.num_envs = 1
    cfg.seed = case["eval_seed"]
    cfg.sim.device = "cuda:0"
    cfg.sim.physx.gpu_max_rigid_patch_count = 2 ** 17
    cfg.sim.physx.gpu_collision_stack_size = 64 * 1024 * 1024
    cfg.observations.policy.enable_corruption = False
    cfg.observations.single_obs.enable_corruption = False
    cfg.events.randomize_push_robot = None
    cfg.events.reset_robot_joints.params["position_range"] = (1., 1.)
    cfg.events.reset_base = EventTermCfg(func=reset_root_q, mode="reset",
            params={"pose_range": {"x": (-.5, .5), "y": (-.5, .5), "z": (0., .2)}})
    cfg.curriculum.terrain_levels = None
    cfg.curriculum.base_linear_velocity = None
    cfg.curriculum.base_height_l2 = None
    cfg.episode_length_s = 30.
    if case["terrain_set"] == "unseen10":
        path = _source(case["terrain_source"], case["terrain_source_sha256"])
        import importlib.util
        spec = importlib.util.spec_from_file_location("s2_pinned_unseen_cfg", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        base_terrain = module.GO2_UNSEEN_TERRAINS_CFG
    elif case["terrain_set"] == "train":
        base_terrain = TERRAIN_CFG
    else:
        raise KitAdapterHold("terrain_set")
    if case["family"] not in base_terrain.sub_terrains:
        raise KitAdapterHold("terrain_family")
    terrain = copy.deepcopy(base_terrain)
    terrain.sub_terrains = {case["family"]: copy.deepcopy(base_terrain.sub_terrains[case["family"]])}
    terrain.sub_terrains[case["family"]].proportion = 1.
    terrain.num_cols = 1
    terrain.num_rows = 10
    terrain.difficulty_range = (case["difficulty"], case["difficulty"])
    terrain.curriculum = True
    terrain.seed = case["terrain_seed"]
    terrain.use_cache = False
    cfg.scene.terrain.terrain_generator = terrain
    cfg.scene.terrain.max_init_terrain_level = None
    ranges = cfg.commands.base_velocity.terrain_max_command_ranges
    if case["family"] not in ranges:
        ranges[case["family"]] = dict(ranges["obstacles"])
    return cfg, terrain


def _world_meshes():
    import omni.usd
    from pxr import UsdGeom, Gf
    stage = omni.usd.get_context().get_stage()
    cache = UsdGeom.XformCache()
    out = []
    for prim in stage.Traverse():
        if not str(prim.GetPath()).startswith("/World/ground") or not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        transform = cache.GetLocalToWorldTransform(prim)
        points = [list(transform.Transform(Gf.Vec3d(*p))) for p in mesh.GetPointsAttr().Get()]
        indices = list(mesh.GetFaceVertexIndicesAttr().Get())
        counts = list(mesh.GetFaceVertexCountsAttr().Get())
        faces, at = [], 0
        for count in counts:
            faces.append([int(i) for i in indices[at:at + count]])
            at += count
        if at != len(indices):
            raise KitAdapterHold("usd_face_indices")
        out.append({"prim_path": str(prim.GetPath()), "points": points, "faces": faces})
    return out


def _plain(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


class EvalIsaacAdapter:
    def __init__(self, case, mode, *, hook_source_path, hook_source_sha256):
        import gymnasium as gym
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from robot_lab.tasks.go2.rsl_rl_cfg import MoECTSRunnerCfg
        if mode not in ("A", "B"):
            raise KitAdapterHold("mode")
        self.case = case
        cfg, terrain = _cfg(case)
        self.terrain_cfg = terrain
        self.env = None
        self.raw_env = gym.make("RobotLab-Go2-v0", cfg=cfg)
        self.raw = self.raw_env.unwrapped
        # RslRlVecEnvWrapper.__init__ calls reset. The event term reads this value.
        self.raw._q_yaw = torch.zeros(1, device=self.raw.device)
        self.env = RslRlVecEnvWrapper(self.raw_env,
                                      clip_actions=MoECTSRunnerCfg().clip_actions)
        self.robot = self.raw.scene["robot"]
        from isaaclab.sim.utils import get_current_stage
        prim = get_current_stage().GetPrimAtPath("/World/envs/env_0/Robot")
        refs = prim.GetMetadata("references") if prim.IsValid() else None
        self.usd_robot_references = sorted({str(ref.assetPath) for field in
                ("explicitItems", "prependedItems", "addedItems", "appendedItems")
                for ref in (getattr(refs, field, []) if refs is not None else []) if ref.assetPath})
        if not self.usd_robot_references:
            raise KitAdapterHold("robot_usd_reference_unverified")
        self.command = self.raw.command_manager.get_term("base_velocity")
        self.command_target = torch.tensor([case["command"]["cmd"]], device=self.raw.device)
        def fixed_resample(env_ids):
            self.command.commands[env_ids] = self.command_target[env_ids]
            self.command.time_left[env_ids] = 1.e9
        self.command._resample = fixed_resample
        self.tracker = SensorUpdateTracker(self.raw.scene.sensors["height_scanner"],
                num_envs=1, step_getter=lambda: self.raw.common_step_counter,
                root_pose_getter=lambda: self.robot.data.root_pose_w,
                expected_hook_path=hook_source_path, expected_hook_sha256=hook_source_sha256)
        self.mount = checked_mount(self.raw.scene.sensors["height_scanner"])
        self.episode_ids = torch.zeros(1, dtype=torch.long, device=self.raw.device)
        self._source_receipt = None
        self._reset_receipt = None
        self._fp = None
        self._initial = None
        self._obs = None
        self._pre_reset_receipts = []
        self.pre_reset = PreResetStep(self.env, self.raw, self._capture_batch, num_envs=1)

    def _capture_batch(self, *, initial=False):
        d = self.robot.data
        terminated = getattr(self.raw, "reset_terminated", None)
        if terminated is None and not initial:
            raise KitAdapterHold("termination_state_before_reset_missing")
        scanner = self.raw.scene.sensors["height_scanner_small"]
        contact = self.raw.scene.sensors["contact_forces"].data.net_forces_w
        if not bool(torch.isfinite(contact).all()):
            raise KitAdapterHold("contact_force_nonfinite")
        z = scanner.data.ray_hits_w[..., 2]
        ground = torch.nanmean(torch.where(torch.isfinite(z), z, torch.nan), dim=1)
        if not bool(torch.isfinite(ground).all()):
            raise KitAdapterHold("ground_z_unverified")
        return [{"pos": _plain(d.root_pos_w[i]), "yaw": float(d.heading_w[i]),
                 "vb": _plain(d.root_lin_vel_b[i]), "wb": _plain(d.root_ang_vel_b[i]),
                 "grav_z": float(d.projected_gravity_b[i, 2]),
                 "hag": float(d.root_pos_w[i, 2] - ground[i]),
                 "term": False if initial else bool(terminated[i]),
                 "contact_force_max_n": float(torch.linalg.vector_norm(contact[i], dim=-1).max()),
                 "contact_forces_sha256": hashlib.sha256(contact[i].detach().cpu().contiguous().numpy().tobytes()).hexdigest()}
                for i in range(self.raw.num_envs)]

    def _initial_fingerprint(self):
        d = self.robot.data
        view = self.robot.root_physx_view
        actuators = {}
        for name, act in self.robot.actuators.items():
            entry = {"stiffness": _plain(act.stiffness[0]), "damping": _plain(act.damping[0])}
            if hasattr(act, "positions_delay_buffer"):
                entry["delay_lags"] = _plain(act.positions_delay_buffer.time_lags[0])
            actuators[name] = entry
        if not actuators:
            raise KitAdapterHold("actuators_missing")
        ground = self.raw.scene.terrain.cfg.physics_material
        ground_material = {"static_friction": float(ground.static_friction),
                           "dynamic_friction": float(ground.dynamic_friction),
                           "restitution": float(ground.restitution),
                           "friction_combine_mode": str(ground.friction_combine_mode)}
        if (ground_material["static_friction"] != self.case["friction"] or
            ground_material["dynamic_friction"] != self.case["friction"]):
            raise KitAdapterHold("actual_ground_friction_diff")
        action_term = self.raw.action_manager.get_term("joint_pos")
        digest, parts = initial_state_sha(root_state_w=d.root_state_w[0],
                joint_pos=d.joint_pos[0], joint_vel=d.joint_vel[0],
                body_masses=view.get_masses()[0], body_materials=view.get_material_properties()[0],
                actuator_state=actuators, command=self.case["command"],
                physics_dt=self.case["physics_dt"], policy_dt=self.case["policy_dt"],
                body_coms=view.get_coms()[0], ground_material=ground_material,
                motor_offset=action_term._offset)
        return digest, parts

    def reset(self, case):
        if case != self.case:
            raise KitAdapterHold("case_identity")
        previous_generation = 0
        if self._obs is not None:
            previous_generation = self.tracker.snapshot()[1]["generation"]
        assignment = assign_one_case(self.raw.scene.terrain, case)
        raw_obs, _ = self.raw.reset(seed=case["eval_seed"])
        self._obs = {k: v.detach().clone() for k, v in raw_obs.items()}
        self.episode_ids += 1
        self._initial = self._capture_batch(initial=True)[0]
        initial_sha, parts = self._initial_fingerprint()
        origin = assignment["env_origin_w"]
        tile_size = self.terrain_cfg.size
        current_meshes = _world_meshes()
        mesh_sha = tile_mesh_sha(current_meshes, center_xy=origin[:2], size_xy=tile_size)
        scanner_hits = self.raw.scene.sensors["height_scanner"].data.ray_hits_w[0]
        finite_hits = scanner_hits[torch.isfinite(scanner_hits).all(dim=-1)].detach().cpu().numpy()
        if len(finite_hits) < 8:
            raise KitAdapterHold("ray_usd_finite_samples_missing")
        selected = finite_hits[np.linspace(0, len(finite_hits)-1, min(32, len(finite_hits)), dtype=int)]
        self._ray_usd_receipt = ray_usd_correspondence(current_meshes, selected)
        zone_end = None
        if case["family"] in ("gap", "stepping_stones"):
            import importlib.util
            terrain_source = Path(case["terrain_source"])
            zone_source = terrain_source.with_name("terrains.py")
            from s2_eval_cases import SOURCE_SHA
            _source(zone_source, SOURCE_SHA["terrains.py"])
            spec = importlib.util.spec_from_file_location("s2_pinned_terrain_zones", zone_source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            zone_end = float(module.obstacle_zone_m(self.terrain_cfg.sub_terrains[case["family"]],
                                                    case["difficulty"], tile_size[0])[1])
        self._fp = case_fingerprint(case, mesh_sha256=mesh_sha, initial_sha256=initial_sha,
                                    initial_components=parts, origin_x=float(origin[0]), zone_end_x=zone_end)
        self._fp["terrain_row"] = assignment["terrain_row"]
        self._fp["terrain_column"] = assignment["terrain_column"]
        self._fp["env_origin_w"] = origin
        self._fp["terrain_config_sha256"] = hashlib.sha256(canonical(json.loads(
                json.dumps(self.terrain_cfg.to_dict(), sort_keys=True, default=str)))).hexdigest()
        self._fp["ray_current_usd"] = self._ray_usd_receipt
        receipt = self.tracker.snapshot()[1]
        self._reset_receipt = {"case_id": case["case_id"], "eval_seed": case["eval_seed"],
                "episode_id": int(self.episode_ids[0]), "previous_sensor_generation": previous_generation,
                "post_reset_sensor_refresh": receipt["generation"] > previous_generation,
                "initial_state_sha256": initial_sha}
        return self._obs

    def case_fingerprint(self):
        return dict(self._fp)

    def reset_receipt(self):
        return dict(self._reset_receipt)

    def initial_physical_state(self):
        return dict(self._initial)

    def capture_packet_after_sensor_update(self):
        sensor, receipt = self.tracker.snapshot()
        self._source_receipt = dict(receipt)
        d = self.robot.data
        return AtomicPacket(self._obs, sensor, d.root_pos_w.detach().clone(),
                d.root_quat_w.detach().clone(), self.episode_ids.clone(),
                receipt["step"], receipt["step"], receipt["generation"], receipt["raw_sha256"],
                f'{receipt["step"]}:{receipt["generation"]}:{receipt["raw_sha256"]}',
                receipt, self.mount)

    def read_sensor_source_receipt(self):
        return self.tracker.source_receipt()

    def step_recorded(self, action):
        obs, _, done, state, _, receipt = self.pre_reset.step_recorded(action, env_index=0)
        self._pre_reset_receipts.append(receipt)
        self._obs = {k: v.detach().clone() for k, v in obs.items()}
        if done:
            self.episode_ids += 1
        return self._obs, done, state

    def close(self):
        had_wrapped = getattr(self, "env", None) is not None
        try:
            if hasattr(self, "tracker"):
                self.tracker.detach()
        finally:
            raw = getattr(self, "raw_env", None)
            self.raw_env = None
            self.env = None
            if raw is not None:
                raw.close()
            del raw
            for name in ("raw", "robot", "tracker", "command", "pre_reset"):
                if hasattr(self, name):
                    delattr(self, name)
            import gc
            gc.collect()
            if had_wrapped:
                from isaaclab.sensors.ray_caster.ray_caster import RayCaster
                from isaaclab.sim import SimulationContext
                if SimulationContext.instance() is not None:
                    raise KitAdapterHold("simulation_context_not_released")
                if RayCaster._instance_count != 0 or RayCaster.meshes:
                    raise KitAdapterHold("raycaster_cache_not_released")

    def pre_reset_receipts(self):
        return list(self._pre_reset_receipts)


def factory(*, hook_source_path, hook_source_sha256):
    def create(case, mode):
        adapter = EvalIsaacAdapter.__new__(EvalIsaacAdapter)
        try:
            adapter.__init__(case, mode, hook_source_path=hook_source_path,
                             hook_source_sha256=hook_source_sha256)
            return adapter
        except BaseException:
            adapter.close()
            raise
    return create
