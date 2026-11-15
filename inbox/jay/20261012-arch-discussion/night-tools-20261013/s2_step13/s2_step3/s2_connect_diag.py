"""S2 Isaac connection capture candidate. Importing does not start Isaac.

Exit 0 means CPU checker accepted data; exit 42 means data hold. Unverified
origin, driver and sensor timestamp fields remain empty, never fabricated.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time

import numpy as np

from s2_env_config import BASE_TASK, DIAG_KINDS, EnvironmentSpec, configure_env
from s2_connect_check import Criteria, check_path, HOLD_CODE


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def isolated_output(root: Path, forbidden: tuple[Path, ...]):
    root = root.resolve()
    for item in forbidden:
        if root == item.resolve() or item.resolve() in root.parents:
            raise ValueError("diagnostic output inside read-only source")
    root.mkdir(parents=True, exist_ok=False)
    return root


def capture(provider_factory, *, spec: EnvironmentSpec, steps: int, reset_yaw_rad: float):
    """Five scenes use one shared cfg builder, two frames after an explicit reset."""
    if type(steps) is not int or steps < 1:
        raise ValueError("positive diagnostic steps required")
    rows = []
    for kind in DIAG_KINDS:
        provider = provider_factory(kind, spec, reset_yaw_rad if kind == "flat_yaw" else 0.0)
        try:
            provider.reset()
            first = provider.sample()
            for _ in range(steps):
                provider.step_zero()
            last = provider.sample()
            rows.append((first, last))
        finally:
            provider.close()
    keys = ("pos_w", "ray_hits_w", "root_pos_w", "root_quat_w", "env_origin_w", "height", "mask",
            "episode_ids", "frame_tokens")
    data = {key: np.stack([[row[0][key], row[1][key]] for row in rows]) for key in keys}
    data["reset_receipt"] = np.stack([row[0]["reset_receipt"] for row in rows])
    return data


class IsaacProvider:
    """Calls from ce12/dump_native_v2.py:161-232, 283-286, 289-324, 368-369."""
    def __init__(self, kind, spec, reset_yaw_rad):
        import gymnasium as gym
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from isaaclab_tasks.utils import load_cfg_from_registry
        import isaaclab_tasks  # noqa: F401
        base = load_cfg_from_registry(BASE_TASK, "env_cfg_entry_point")
        cfg = configure_env(base, spec, diagnostic_kind=kind, reset_yaw_rad=reset_yaw_rad)
        self.env = RslRlVecEnvWrapper(gym.make(BASE_TASK, cfg=cfg))
        self.raw = self.env.unwrapped
        self.robot = self.raw.scene["robot"]
        self.scanner = self.raw.scene.sensors["height_scanner"]
        self.spec, self.num_envs = spec, spec.num_envs
        self.steps = self.resets = 0

    def reset(self):
        self.raw.reset()
        self.steps = 0
        self.resets += 1

    def step_zero(self):
        import torch
        self.env.step(torch.zeros_like(self.raw.action_manager.action))
        self.steps += 1

    def sample(self):
        from s2_env_adapter import training_map, yaw_from_quat_wxyz
        d, hs = self.robot.data, self.scanner
        pos, hits = hs.data.pos_w.detach().clone(), hs.data.ray_hits_w.detach().clone()
        quat = d.root_quat_w.detach().clone()
        try:
            mapped, _ = training_map(hs, mode="B", yaw_w=yaw_from_quat_wxyz(quat),
                                     geometry_tolerance_m=self.spec.geometry_tolerance_m)
            hm = mapped[:, :187].detach().cpu().numpy()
            mask = mapped[:, 187:].detach().cpu().numpy()
        except Exception:
            hm = np.full((self.num_envs, 187), np.nan, dtype=np.float32)
            mask = np.full_like(hm, np.nan)
        def cpu(x):
            return x.detach().float().cpu().numpy()
        return {"pos_w": cpu(pos), "ray_hits_w": cpu(hits), "root_pos_w": cpu(d.root_pos_w),
                "root_quat_w": cpu(quat),
                "env_origin_w": np.full((self.num_envs, 3), np.nan, dtype=np.float32),
                "height": hm, "mask": mask,
                "episode_ids": np.full(self.num_envs, self.resets, dtype=np.int64),
                "frame_tokens": np.full(self.num_envs, self.steps, dtype=np.int64),
                "reset_receipt": np.ones(self.num_envs, dtype=np.int64)}

    def close(self):
        self.env.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    for key in ("parent", "out_root", "criteria"):
        ap.add_argument("--" + key, required=True)
    for key in ("seed", "num_envs", "steps"):
        ap.add_argument("--" + key, required=True, type=int)
    for key in ("gap_proportion", "stones_proportion", "step_height_m", "step_width_m",
                "geometry_tolerance_m", "reset_yaw_rad"):
        ap.add_argument("--" + key, required=True, type=float)
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(ap)
    a = ap.parse_args(argv)
    if not a.headless or not Path(a.parent).is_file():
        raise ValueError("headless flag and existing parent required")
    spec = EnvironmentSpec(a.seed, a.num_envs, a.gap_proportion, a.stones_proportion,
                           a.step_height_m, a.step_width_m, a.geometry_tolerance_m)
    criteria = Criteria(**json.loads(Path(a.criteria).read_text(encoding="utf-8")))
    root = isolated_output(Path(a.out_root), (Path("C:/isaac/ext/go2_rl_robotlab/_eval"),
                                               Path("C:/isaac/ext/go2_rl_robotlab/source")))
    launcher = AppLauncher(a)
    app = launcher.app
    try:
        arrays = capture(IsaacProvider, spec=spec, steps=a.steps, reset_yaw_rad=a.reset_yaw_rad)
        np.savez_compressed(root / "capture.npz", **arrays)
        try:
            isaac_version = importlib.metadata.version("isaaclab")
        except importlib.metadata.PackageNotFoundError:
            isaac_version = None
        import torch
        meta = {"cases": list(DIAG_KINDS), "steps": a.steps, "env_config_sha256": spec.sha256(),
                "parent_sha256": sha256_file(a.parent), "code_sha256": sha256_file(__file__),
                "capture_sha256": sha256_file(root / "capture.npz"), "isaac_version": isaac_version,
                "torch_version": torch.__version__, "driver_version": None,
                "reset_evidence": "explicit_reset_call_only", "terrain_assignment_verified": False,
                "started_epoch": time.time()}
        (root / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
        result = check_path(root, criteria)
        (root / "check.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        return 0 if result["verdict"] == "PASS" else HOLD_CODE
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
