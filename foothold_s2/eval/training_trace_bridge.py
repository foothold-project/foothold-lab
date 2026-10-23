"""Read-only hooks from live rollouts to the sampled trace archive."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import torch

from foothold_s2.eval.train_trace import TrainTraceObserver, _sha256


class TrainingTraceBridge:
    def __init__(self, runner):
        self.runner = runner
        self.env = getattr(runner.env, "unwrapped", runner.env)
        self.robot = self.env.scene["robot"]
        self.contact = self.env.scene.sensors["contact_forces"]
        self.feet = [i for i, name in enumerate(self.robot.body_names) if name.endswith("_foot")]
        self.sensor_feet = [i for i, name in enumerate(self.contact.body_names) if name.endswith("_foot")]
        if len(self.feet) != 4 or [self.robot.body_names[i] for i in self.feet] != [self.contact.body_names[i] for i in self.sensor_feet]:
            raise ValueError("trace foot order mismatch")
        self.trace = TrainTraceObserver(
            Path(runner.log_dir) / "training_trace", "live_rollout", "training",
            self.env.scene.terrain.terrain_types, steps_per_update=runner.num_steps_per_env,
            step_dt_s=float(self.env.step_dt), sample_envs=min(8, self.env.num_envs))
        self.trace.attach_perception(runner.perception)
        self.episode = torch.zeros(self.env.num_envs, dtype=torch.long, device=self.env.device)
        self.active = False
        self.pending = None
        from foothold_s2.sensors.depth_aug import NEAR, FAR
        from foothold_s2.sensors.start_obs import AUG
        metadata = {
            "source": "training", "control_dt_s": float(self.env.step_dt),
            "foot_names": [self.robot.body_names[i] for i in self.feet],
            "joint_names": list(self.robot.joint_names),
            "root_quaternion": "wxyz, world", "foot_coordinates": "world meters, rigid body center",
            "foot_contact": "force norm > 1 N, pre transition",
            "foot_velocity_xy": "world XY at link center; not terrain tangent contact-point slip",
            "action": "PPO sampled action before wrapper clipping and actuator delay",
            "episode_id": "per environment counter in this run segment; increment after done",
            "depth": {"near_m": NEAR, "far_m": FAR, "kind": "distance_to_image_plane",
                      "stored": "actual normalized perception input, latest two delivered frames",
                      "sensor_depth_m": "latest raw meter frame separately saved; inf means no hit; may be newer than delayed policy frames",
                      "augmentation_enabled": bool(AUG.enabled),
                      "warning": "clipping and augmentation cannot be inverted to original sensor depth"},
            "height": "z_hit minus root_z clipped [-1,1] m; miss=-1; yaw-aligned 32x16, yx ordering",
            "grid": {"resolution_m": 0.05, "offset_x_m": 0.3,
                     "x_range_m": [-0.475, 1.075], "y_range_m": [-0.375, 0.375]},
            "reset_alignment": "state and action before env.step; reward/done after it; no trajectory joins across reset",
            "not_exact_replay": "GRU hidden and complete physics are not archived for every step or environment",
        }
        path = self.trace.out_dir / "coordinate_metadata.json"
        path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        self.trace.manifest["coordinate_metadata"] = {"file": path.name, "sha256": _sha256(path)}
        self.trace.manifest["conditions"] = []

    def _save_conditions(self):
        ids = self.trace.env_ids
        arrays = {"env_ids": ids}

        def put(name, value):
            if value is None:
                return
            value = value.detach() if hasattr(value, "detach") else value
            if hasattr(value, "device"):
                index = torch.as_tensor(ids, device=value.device, dtype=torch.long)
                value = value.index_select(0, index).cpu().numpy()
            else:
                value = np.asarray(value)[ids]
            arrays[name] = np.array(value, copy=True)

        physx = self.robot.root_physx_view
        put("mass_kg", physx.get_masses())
        put("com_pose", physx.get_coms())
        camera = self.env.scene.sensors["depth_cam"]
        put("camera_intrinsics", camera.data.intrinsic_matrices)
        put("camera_offset_pos", getattr(camera, "_offset_pos", None))
        put("camera_offset_quat", getattr(camera, "_offset_quat", None))
        action = self.env.action_manager.get_term("joint_pos")
        put("action_delay_substeps", getattr(action, "delay", None))
        for name, actuator in self.robot.actuators.items():
            for field in ("stiffness", "damping", "strength_scale"):
                put(f"actuator_{name}_{field}", getattr(actuator, field, None))
        path = self.trace.out_dir / f"conditions_{self.it:06d}.npz"
        temp = path.with_suffix(".npz.writing")
        with temp.open("wb") as stream:
            np.savez_compressed(stream, **arrays)
        os.replace(temp, path)
        self.trace.manifest["conditions"].append({"update": self.it, "file": path.name,
                                                   "sha256": _sha256(path),
                                                   "timing": "before rollout update, not per reset"})

    def begin_update(self, it):
        self.it = int(it)
        self.active = self.trace.begin_update(self.it)
        if self.active:
            self._save_conditions()

    def pre_step(self, actions):
        if not self.active:
            return
        data = self.robot.data
        terrain = self.env.scene.terrain
        # Clone the pre-transition state because env.step resets terminated envs.
        fields = {
            "sensor_depth_m": self.env.scene.sensors["depth_cam"].data.output["distance_to_image_plane"][..., 0],
            "root_pos_w": data.root_pos_w, "root_quat_w": data.root_quat_w,
            "foot_pos_w": data.body_pos_w[:, self.feet],
            "foot_velocity_xy": data.body_lin_vel_w[:, self.feet, :2],
            "foot_contact": self.contact.data.net_forces_w[:, self.sensor_feet].norm(dim=-1) > 1.0,
            "joint_pos": data.joint_pos, "joint_vel": data.joint_vel,
            "command": self.env.command_manager.get_command("base_velocity"),
            "terrain_type": terrain.terrain_types, "terrain_level": terrain.terrain_levels,
            "episode_id": self.episode, "actor_action": actions,
        }
        self.pending = {name: value.detach().clone() for name, value in fields.items()}

    def post_step(self, step_index, rewards, dones):
        if self.active:
            self.pending.update(reward=rewards, reset=dones,
                                terminated=self.env.reset_terminated,
                                timed_out=self.env.reset_time_outs)
            self.trace.capture_step(self.it, step_index, self.pending)
            self.pending = None
        self.episode += dones.long()

    def end_update(self):
        if self.active:
            self.trace.end_update(self.it)
        self.active = False

    def close(self):
        self.trace.close("run_segment_finished")
