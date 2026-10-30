"""SOL-23f 전용 저장, 갱신 경계 중단, 관측 증거. 기존 runner는 변경하지 않는다."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import torch

from foothold_s2.runners.start_runner import StartRunner


class DeadlineReached(RuntimeError):
    """완료한 갱신을 저장한 뒤 계획된 마감에 도달했다."""


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def material_summary(materials: torch.Tensor) -> dict:
    """Summarize realized PhysX material samples, not only the cfg ranges."""
    if materials.ndim != 3 or materials.shape[-1] != 3 or materials.numel() == 0:
        raise ValueError("material tensor must be [env, shape, static/dynamic/restitution]")
    if not torch.isfinite(materials).all():
        raise ValueError("nonfinite material properties")
    return {
        "envs": int(materials.shape[0]), "shapes_per_env": int(materials.shape[1]),
        "static_min": float(materials[..., 0].min().item()),
        "static_max": float(materials[..., 0].max().item()),
        "dynamic_min": float(materials[..., 1].min().item()),
        "dynamic_max": float(materials[..., 1].max().item()),
        "dynamic_le_static_all": bool((materials[..., 1] <= materials[..., 0]).all().item()),
        "sample_env0_shape0": materials[0, 0].tolist(),
    }


def save_material_array(materials: torch.Tensor, log_dir: str | Path) -> dict:
    """Persist every realized PhysX robot material in env/shape order."""
    summary = material_summary(materials)
    array = materials.detach().contiguous().cpu().numpy()
    path = Path(log_dir) / "robot_material_env_shape_3.npy"
    with path.open("wb") as stream:
        np.save(stream, array, allow_pickle=False)
    return {**summary, "array_file": path.name, "array_sha256": sha256(path),
            "array_dtype": str(array.dtype), "array_shape": list(array.shape)}


def tensor_summary(value: torch.Tensor) -> dict:
    data = value.detach().contiguous().cpu()
    if data.numel() == 0 or not torch.isfinite(data).all():
        raise ValueError("empty or nonfinite realized physics tensor")
    return {"shape": list(data.shape), "min": float(data.min()), "max": float(data.max()),
            "mean": float(data.float().mean()), "sha256": hashlib.sha256(data.numpy().tobytes()).hexdigest()}


def contact_tangent_stats(body_velocity_w: torch.Tensor, forces_w: torch.Tensor,
                          eligible: torch.Tensor | None = None) -> tuple[torch.Tensor, torch.Tensor]:
    """정적 지면에 닿은 발의 월드 XY 접선속력 합과 표본 수."""
    if body_velocity_w.shape != forces_w.shape or body_velocity_w.shape[-1] != 3:
        raise ValueError("foot velocity/force shape mismatch")
    contact = torch.linalg.vector_norm(forces_w, dim=-1) > 1.0
    if eligible is not None:
        contact = contact & eligible[:, None]
    speed = torch.linalg.vector_norm(body_velocity_w[..., :2], dim=-1)
    return torch.where(contact, speed, 0.0).sum(), contact.sum()


class StepEvidence:
    """Lab termination_manager.compute 직후, reset 직전에 종료 사유와 발속력을 누적한다."""

    def __init__(self, env, log_dir: str):
        self.env = env
        self.log_dir = log_dir
        manager = env.termination_manager
        self.terms = tuple(manager.active_terms)
        robot = env.scene["robot"]
        sensor = env.scene.sensors["contact_forces"]
        robot_feet = [i for i, name in enumerate(robot.body_names) if name.endswith("_foot")]
        sensor_feet = [i for i, name in enumerate(sensor.body_names) if name.endswith("_foot")]
        if len(robot_feet) != 4 or len(sensor_feet) != 4:
            raise ValueError("footXY requires four matching foot bodies")
        robot_names = [robot.body_names[i] for i in robot_feet]
        sensor_names = [sensor.body_names[i] for i in sensor_feet]
        if robot_names != sensor_names:
            raise ValueError(f"foot body order mismatch: {robot_names} != {sensor_names}")
        self.robot_feet, self.sensor_feet = robot_feet, sensor_feet
        self.counts = {name: torch.zeros((), dtype=torch.int64, device=env.device) for name in self.terms}
        self.speed_sum = torch.zeros((), device=env.device)
        self.contact_count = torch.zeros((), dtype=torch.int64, device=env.device)
        self.steps = 0

        original = manager.compute

        def measured_compute():
            done = original()
            for name in self.terms:
                self.counts[name] += manager.get_term(name).sum()
            velocities = robot.data.body_lin_vel_w[:, self.robot_feet, :]
            forces = sensor.data.net_forces_w[:, self.sensor_feet, :]
            # compute() precedes reset. A terminal sample is still physical
            # evidence; only the next post-reset step would contain a jump.
            speed, count = contact_tangent_stats(velocities, forces)
            self.speed_sum += speed
            self.contact_count += count
            self.steps += 1
            return done

        manager.compute = measured_compute

    def flush(self, it: int) -> dict:
        dt = float(self.env.step_dt)
        length = float(self.speed_sum.item()) * dt
        duration = int(self.contact_count.item()) * dt
        row = {
            "it": it,
            "steps": self.steps,
            "termination_counts": {name: int(count.item()) for name, count in self.counts.items()},
            "contact_foot_samples": int(self.contact_count.item()),
            "foot_xy_tangent_speed_mean_mps": (
                length / duration if duration else None
            ),
            "contact_foot_xy_path_m": length,
            "contact_foot_duration_s": duration,
            "reset_boundary_excluded": True,
            "ground_reference": "static world XY",
            "foot_point": "rigid body center",
            "contact_threshold_N": 1.0,
        }
        row["joint_position_rad"] = tensor_summary(self.env.scene["robot"].data.joint_pos)
        camera = self.env.scene.sensors.get("depth_cam")
        if camera is not None and hasattr(camera, "_offset_pos"):
            row["camera_offset_position"] = tensor_summary(camera._offset_pos)
            row["camera_offset_quaternion"] = tensor_summary(camera._offset_quat)
            row["camera_intrinsic_fx"] = tensor_summary(camera.data.intrinsic_matrices[..., 0, 0])
        action_manager = getattr(self.env, "action_manager", None)
        if action_manager is not None:
            joint_action = action_manager.get_term("joint_pos")
            if hasattr(joint_action, "delay"):
                row["action_delay_substeps"] = tensor_summary(joint_action.delay)
        with open(os.path.join(self.log_dir, "step_evidence.jsonl"), "a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        for count in self.counts.values():
            count.zero_()
        self.speed_sum.zero_()
        self.contact_count.zero_()
        self.steps = 0
        return row


class Sol23FRunner(StartRunner):
    """공통 학습 수학은 StartRunner 그대로, 저장과 마감만 이 판에 추가한다."""

    variant = "unset"

    def __init__(self, *args, deadline_epoch: float | None = None, stop_file: str | None = None,
                 evidence: StepEvidence | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.deadline_epoch = deadline_epoch
        self.stop_file = stop_file
        self.evidence = evidence
        if self.variant == "START_TopDown" and self.perception.cfg.depth_delay_ticks != 0:
            raise ValueError("TopDown requires depth_delay_ticks=0 in saved perception cfg")

    def reset_segment_physics(self) -> dict:
        """A new simulator must reset at restored terrain origins before learning."""
        raw = getattr(self.env, "unwrapped", self.env)
        terrain = raw.scene.terrain
        levels, types = terrain.terrain_levels.clone(), terrain.terrain_types.clone()
        origins = terrain.terrain_origins[levels, types]
        counter = getattr(raw, "common_step_counter", None)
        curriculum = raw.curriculum_manager
        original_compute = curriculum.compute
        curriculum.compute = lambda *args, **kwargs: None
        try:
            self.env.reset()
        finally:
            curriculum.compute = original_compute
        if not torch.equal(terrain.terrain_levels, levels) or not torch.equal(terrain.terrain_types, types):
            raise RuntimeError("resume physical reset changed restored terrain labels")
        if not torch.equal(terrain.env_origins, origins) or not torch.equal(raw.scene.env_origins, origins):
            raise RuntimeError("resume physical reset changed restored terrain origins")
        if counter is not None and raw.common_step_counter != counter:
            raise RuntimeError("resume physical reset changed restored update counter")
        return {"performed": True, "curriculum_update_skipped_once": True,
                "num_envs": int(len(levels)), "origin_sha256": tensor_summary(origins)["sha256"],
                "physical_resume_identical": False}

    def state_dict(self, infos: dict | None = None) -> dict:
        state = super().state_dict(infos)
        state["sol23f"] = {
            "variant": self.variant,
            "physical_resume_identical": False,
            "force_gt": bool(self.adasmpl.force_gt),                 # 실제로 쓰는 값(resume_adasmpl 로 덮은 뒤에는 덮은 값). 설정값이 아니라 AdaSmpl 의 값을 적는다
            "map_input": self.pcfg.get("map_input"),
            "depth_delay_ticks": int(self.perception.cfg.depth_delay_ticks),
        }
        return state

    def save(self, path: str, infos: dict | None = None) -> None:
        """번호 붙은 model_N.pt도 latest.pt처럼 임시 파일 뒤 원자 교체한다."""
        tmp = f"{path}.tmp"
        torch.save(self.state_dict(infos), tmp)
        os.replace(tmp, path)

    def save_initial(self, path: str) -> None:
        """Write a diagnostic snapshot that cannot be used as a resume parent."""
        state = {**self.state_dict()}
        state["sol23f"] = {**state["sol23f"], "initial_snapshot": True}
        tmp = f"{path}.tmp"
        torch.save(state, tmp)
        os.replace(tmp, path)

    def load(self, path: str, load_optimizer: bool = True, map_location: str | None = None) -> dict:
        state = torch.load(path, weights_only=False, map_location="cpu")
        own = state.get("sol23f") or {}
        continuous = getattr(self, "continuous_curriculum", None)
        saved_stage = state.get("continuous_curriculum")
        if continuous is not None and saved_stage is not None:
            if (saved_stage.get("plan_sha256") != continuous.plan.sha256
                    or saved_stage.get("effective_sha256") != continuous.plan.effective_sha256):
                raise ValueError("W55 resume curriculum SHA mismatch")
            self.pcfg["force_gt"] = bool(own.get("force_gt"))
        if own.get("variant") != self.variant:
            raise ValueError("SOL-23f variant mismatch on resume")
        if own.get("force_gt") != bool(self.pcfg.get("force_gt", False)) and self.pcfg.get("resume_adasmpl") is None:
            raise ValueError("SOL-23f force_gt mismatch on resume")      # 덮어쓰기 인자(resume_adasmpl)가 있으면 저장본 값에서 설정 값으로 바뀌는 것이 의도이며 StartRunner 가 사건으로 기록한다
        if own.get("map_input") != self.pcfg.get("map_input"):
            raise ValueError("SOL-23f map_input mismatch on resume")
        if own.get("depth_delay_ticks") != self.perception.cfg.depth_delay_ticks:
            raise ValueError("SOL-23f depth_delay_ticks mismatch on resume")
        return super().load(path, load_optimizer=load_optimizer, map_location=map_location)

    def log(self, locs: dict, width: int = 80, pad: int = 35) -> None:
        super().log(locs, width, pad)
        it = int(locs["it"])
        if self.evidence is not None:
            self.evidence.flush(it)
        due = self.deadline_epoch is not None and time.time() >= self.deadline_epoch
        stop = self.stop_file is not None and os.path.isfile(self.stop_file)
        if due or stop:
            name = f"model_{it}.pt"
            path = os.path.join(self.log_dir, name)
            self.save(path)
            self._manifest_checkpoint(it, name, self.env.num_envs)
            if getattr(self, "continuous_curriculum", None) is not None:
                self.continuous_curriculum.on_checkpoint(it, path)
            self.save_latest()
            raise DeadlineReached(json.dumps({
                "reason": "deadline" if due else "stop_file", "iter": it,
                "checkpoint": path, "sha256": sha256(path),
                "physical_resume_identical": False,
            }))


class BRunner(Sol23FRunner):
    variant = "B_friction_only"


class SBRunner(Sol23FRunner):
    """EX-33 S-B: B 와 같은 설정에 에피소드 단위 지도 끔(p_map_off). 체크포인트 variant 이름이 B 와 달라 서로 이어 가지 못한다."""

    variant = "SB_map_switch"


class TopDownRunner(Sol23FRunner):
    variant = "START_TopDown"
