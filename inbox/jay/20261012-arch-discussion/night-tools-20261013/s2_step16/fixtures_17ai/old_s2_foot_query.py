"""World-XY 36 ray adapter and fail-closed frame validation for S2-2."""
from __future__ import annotations

from dataclasses import dataclass
import math
import torch

from s2_foot_reward import HIT, NO_HIT

FOOT_NAMES = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
COLLISION_OFFSET_M = (-0.002, 0.0, 0.0)  # all four installed Go2 URDF collision spheres
MESH_PATH = "/World/ground"
RAY_START_ABOVE_FOOT_M = 20.0
MAX_DISTANCE_M = 30.0


def grid_offsets(spacing_m: float, *, device, dtype):
    if type(spacing_m) not in (int, float) or not 0 < spacing_m <= 0.05:
        raise ValueError("foot_spacing_invalid")
    s = float(spacing_m)
    return torch.tensor([(x, y, 0.) for x in (-s, 0., s) for y in (-s, 0., s)],
                        device=device, dtype=dtype)


def make_ray_starts(centers: torch.Tensor, spacing_m: float):
    if centers.ndim != 3 or centers.shape[1:] != (4, 3) or not bool(torch.isfinite(centers).all()):
        raise ValueError("foot_centers_invalid")
    offsets = grid_offsets(spacing_m, device=centers.device, dtype=centers.dtype)
    starts = centers.unsqueeze(2) + offsets.view(1, 1, 9, 3)
    starts = starts.clone()
    starts[..., 2] += RAY_START_ABOVE_FOOT_M
    return starts


@dataclass(frozen=True)
class FootQuery:
    centers: torch.Tensor
    forces: torch.Tensor
    starts: torch.Tensor
    hits: torch.Tensor
    heights: torch.Tensor
    status: torch.Tensor
    episode_id: torch.Tensor
    frame_id: torch.Tensor
    step: int
    mesh_path: str


class FootQueryTracker:
    """Episode-aware validator. Caller supplies fresh pose, forces and mesh hits."""
    def __init__(self, num_envs: int, spacing_m: float, *, device="cpu", mesh_path=MESH_PATH):
        if num_envs < 1 or mesh_path != MESH_PATH:
            raise ValueError("foot_query_setup")
        grid_offsets(spacing_m, device=device, dtype=torch.float32)
        self.spacing_m = float(spacing_m)
        self.mesh_path = mesh_path
        self.episode_id = torch.zeros(num_envs, dtype=torch.long, device=device)
        self.frame_id = torch.full((num_envs,), -1, dtype=torch.long, device=device)
        self._last_starts = None

    def reset(self, env_ids):
        self.episode_id[env_ids] += 1
        self.frame_id[env_ids] = -1

    def capture(self, *, centers, forces, hits, frame_id, episode_id,
                tile_origin, tile_size_xy, mesh_path, max_distance_m=MAX_DISTANCE_M,
                ray_starts=None):
        n = self.episode_id.numel()
        if mesh_path != self.mesh_path:
            raise ValueError("foot_mesh_mismatch")
        if centers.shape != (n, 4, 3) or forces.shape != (n, 4, 3) or hits.shape != (n, 4, 9, 3):
            raise ValueError("foot_capture_shape")
        if frame_id.shape != (n,) or episode_id.shape != (n,) or tile_origin.shape != (n, 3):
            raise ValueError("foot_capture_frame_shape")
        if not bool(torch.equal(episode_id, self.episode_id)):
            raise ValueError("foot_episode_stale")
        if not bool((frame_id > self.frame_id).all()):
            raise ValueError("foot_frame_stale")
        if not bool(torch.isfinite(tile_origin).all()):
            raise ValueError("foot_tile_nonfinite")
        starts = make_ray_starts(centers, self.spacing_m)
        if ray_starts is not None and (ray_starts.shape != starts.shape or
            not bool(torch.allclose(ray_starts,starts,atol=1e-5,rtol=0))):
            raise ValueError("foot_start_mismatch")
        if self._last_starts is not None and bool(torch.equal(frame_id, self.frame_id + 1)):
            unchanged = torch.all(centers == self._last_centers, dim=(1, 2))
            if bool((unchanged & torch.any(starts != self._last_starts, dim=(1, 2, 3))).any()):
                raise ValueError("foot_start_accumulated")
        if type(tile_size_xy) not in (tuple, list) or len(tile_size_xy) != 2 or any(float(v) <= 0 for v in tile_size_xy):
            raise ValueError("foot_tile_size")
        if type(max_distance_m) not in (int, float) or max_distance_m <= 0:
            raise ValueError("foot_range_invalid")
        floor = tile_origin[:, None, None, 2] - 1.0
        if not bool(((starts[..., 2] - floor) <= max_distance_m).all()):
            raise ValueError("foot_range_too_short")
        for axis in (0, 1):
            limit = float(tile_size_xy[axis]) / 2
            if not bool(((starts[..., axis] - tile_origin[:, None, None, axis]).abs() <= limit).all()):
                raise ValueError("foot_outside_tile")
        finite = torch.isfinite(hits).all(-1)
        no_hit = torch.isposinf(hits).all(-1)
        if not bool((finite | no_hit).all()):
            raise ValueError("foot_hit_invalid")
        # A hit must lie on the downward ray and inside the configured reach.
        if not bool(((hits[..., :2][finite] - starts[..., :2][finite]).abs() <= 1e-3).all()):
            raise ValueError("foot_hit_xy_mismatch")
        if not bool(((starts[..., 2][finite] - hits[..., 2][finite]) >= 0).all()):
            raise ValueError("foot_hit_above_start")
        if not bool(((starts[..., 2][finite] - hits[..., 2][finite]) <= max_distance_m).all()):
            raise ValueError("foot_hit_out_of_range")
        status = torch.where(finite, HIT, NO_HIT).to(torch.uint8)
        self.frame_id = frame_id.clone()
        self._last_centers = centers.clone()
        self._last_starts = starts.clone()
        return FootQuery(centers.clone(), forces.clone(), starts, hits.clone(), hits[..., 2].clone(),
                         status, episode_id.clone(), frame_id.clone(), int(frame_id.max()), mesh_path)


def live_raycast(env, tracker: FootQueryTracker, *, spacing_m: float):
    """Static-source-checked Kit path; actual USD foot pose remains Kit-unverified."""
    from isaaclab.sensors.ray_caster.ray_caster import RayCaster
    from isaaclab.utils.math import quat_apply
    from isaaclab.utils.warp import raycast_mesh

    robot = env.scene["robot"]
    contact = env.scene.sensors["contact_forces"]
    ids, names = robot.find_bodies(list(FOOT_NAMES), preserve_order=True)
    if tuple(names) != FOOT_NAMES or len(ids) != 4:
        raise ValueError("foot_body_order_unverified")
    contact_ids = [contact.body_names.index(name) for name in FOOT_NAMES]
    step_before = int(env.common_step_counter)
    pose = robot.data.body_pos_w[:, ids, :].clone()
    quat = robot.data.body_quat_w[:, ids, :].clone()
    offset = torch.tensor(COLLISION_OFFSET_M, device=pose.device, dtype=pose.dtype).expand_as(pose)
    centers = pose + quat_apply(quat.reshape(-1, 4), offset.reshape(-1, 3)).reshape_as(pose)
    forces = contact.data.net_forces_w[:, contact_ids, :].clone()
    starts = make_ray_starts(centers, spacing_m)
    rays = torch.zeros_like(starts)
    rays[..., 2] = -1
    mesh = RayCaster.meshes.get(MESH_PATH)
    if mesh is None:
        raise ValueError("foot_mesh_not_loaded")
    hits = raycast_mesh(starts.reshape(env.num_envs, 36, 3),
                        rays.reshape(env.num_envs, 36, 3), mesh=mesh,
                        max_dist=MAX_DISTANCE_M)[0].reshape(env.num_envs, 4, 9, 3)
    if int(env.common_step_counter) != step_before:
        raise ValueError("foot_step_changed_during_query")
    # episode_length_buf may reset independently per environment.
    episode_step = env.episode_length_buf.clone().to(torch.long)
    if not hasattr(tracker, "_episode_step"):
        tracker._episode_step = torch.full_like(episode_step, -1)
    reset_ids = torch.nonzero(episode_step < tracker._episode_step, as_tuple=False).flatten()
    if reset_ids.numel():
        tracker.reset(reset_ids)
    tracker._episode_step = episode_step.clone()
    frame = episode_step
    if not bool((frame > tracker.frame_id).all()):
        raise ValueError("foot_frame_not_fresh")
    terrain = env.scene.terrain
    size = env.cfg.scene.terrain.terrain_generator.size
    return tracker.capture(centers=centers, forces=forces, hits=hits, frame_id=frame,
                           episode_id=tracker.episode_id.clone(), tile_origin=terrain.env_origins,
                           tile_size_xy=size, mesh_path=MESH_PATH,ray_starts=starts)


def kit_step_record(query: FootQuery, result, *, body_ids, dt: float, weight=-0.01):
    """Small bounded Kit check evidence row. Caller controls 8 env / 300 step cap."""
    if query.centers.shape[0] > 8 or len(body_ids) != 4 or dt <= 0 or weight != -0.01:
        raise ValueError("foot_kit_record_scope")
    def as_list(value):
        def clean(item):
            if isinstance(item,list):return [clean(v) for v in item]
            if isinstance(item,float) and not math.isfinite(item):
                return "+inf" if item > 0 else "invalid"
            return item
        return clean(value.detach().cpu().tolist())
    return {"step":query.step,"episode_id":as_list(query.episode_id),
            "frame_id":as_list(query.frame_id),"body_ids":list(body_ids),
            "body_names":list(FOOT_NAMES),
            "mesh_path":query.mesh_path,"foot_centers_w_m":as_list(query.centers),
            "ray_starts_w_m":as_list(query.starts),"ray_hits_w_m":as_list(query.hits),
            "query_status":as_list(query.status),"contact_forces_w_n":as_list(query.forces),
            "raw_cost":as_list(result.cost),
            "central_discrepancy":as_list(result.central_discrepancy),
            "weighted_reward":as_list(result.cost*weight*dt),"dt_s":dt}
