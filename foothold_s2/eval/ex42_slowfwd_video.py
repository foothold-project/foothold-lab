"""EX-42 slow-forward video: one command of the G1b suite on level-0 fixed terrain, filming one env.

The evaluator is eval_map_modes (--command-suite hipan_g1b --fixed-terrain --fixed-level 0 --modes eval_gt, 64 envs,
seed 42): same environment configuration, same DR-off / friction / curriculum-off setup, same per-command reset and
policy stepping, and the commands run in the suite's order in one process (state carries from one command to the next),
so the earlier commands are replayed unfilmed before the filmed one. One chosen env is rendered (the others are
hidden); rendering never advances physics. Every replayed and the filmed command is compared with a reference
env_arrays folder (a no-video eval_map_modes run of the same checkpoint) when one is given.

The capture folder (review.mp4, review_feet.npz, review.json, review.done) is what the rule 4 composer reads; the
command strip is drawn from the recorded cmd_post column.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401
from isaaclab.app import AppLauncher

from foothold_s2.eval import eval_dr_mode, ex42_friction

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--task", default="FootholdS2-Go2-S2-SB-v0")
parser.add_argument("--checkpoint", type=Path, required=True)
parser.add_argument("--ex42-evaluation-plan", type=Path, required=True)
parser.add_argument("--envs", type=int, default=64)
parser.add_argument("--steps", type=int, default=300)
parser.add_argument("--eval-seed", type=int, default=42)
parser.add_argument("--suite", default="hipan_g1b")
parser.add_argument("--command", required=True, help="the filmed command name of the suite")
parser.add_argument("--film-kind", default="random_rough", help="film the smallest level-0 env of this terrain kind")
parser.add_argument("--film-env", type=int, default=None, help="override --film-kind with an explicit env")
parser.add_argument("--reference-dir", type=Path, default=None, help="no-video eval_map_modes output of the same checkpoint")
parser.add_argument("--no-video", action="store_true")
parser.add_argument("--out", type=Path, required=True)
eval_dr_mode.add_arguments(parser)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.enable_cameras = not args.no_video
if args.envs != 64 or args.eval_seed < 0 or not args.checkpoint.is_file() or args.out.exists():
    parser.error("slow-forward video needs 64 envs, a fresh output and a pinned checkpoint")
if args.dr_mode != "off":
    parser.error("slow-forward video is a DR-off evaluation")
friction_policy = ex42_friction.map_policy(args)
app = AppLauncher(args).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import isaaclab_tasks  # noqa: E402,F401
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import load_cfg_from_registry  # noqa: E402

import foothold_s2.sb_tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, ex41_eval_loader, fixed_terrain, map_mode_cells  # noqa: E402
from foothold_s2.terrains import columns  # noqa: E402

FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
START_OFFSET_MAX_M = 0.5
EXPECTED_DR_OFF = ["physics_material", "add_base_mass"]
FIXED_LEVEL = 0
SECONDS_LABEL = {"fwd0.1": "전진 0.1 m/s (L0)", "fwd0.2": "전진 0.2 m/s (L0)"}


class Film:
    """One selected env, rendered while all 64 envs run exactly as the evaluator runs them."""

    def __init__(self, raw, annotator, capture_dir):
        import av
        from foothold_s2.eval.ex42_d44_video import WIDTH, HEIGHT, FPS
        self.raw, self.annotator = raw, annotator
        self.screen, self.robots = [], []
        self.intrinsics = None
        self.capture_dir = capture_dir
        self.capture_dir.mkdir(parents=True, exist_ok=False)
        self.clean = av.open(str(self.capture_dir / "review.mp4"), mode="w")
        self.clean_stream = self.clean.add_stream("libx264", rate=FPS)
        self.clean_stream.width, self.clean_stream.height, self.clean_stream.pix_fmt = WIDTH, HEIGHT, "yuv420p"
        self.clean_stream.options = {"crf": "18", "preset": "medium"}
        self.rows = {key: [] for key in ("t", "seg", "foot_pos_w", "foot_contact", "root_pos_w", "root_quat_w",
                                        "roll", "pitch", "vx", "vy", "wz", "command", "done", "time_out",
                                        "map_use_gt", "gt_map", "refined_map")}
        self.snap, self.overlay, self.overlay_info, self.frame_ticks = {}, None, [], []

    def tick(self, k, dt, foot_pos, contact, root, quat, vel, wz, command, done):
        w, x, y, z = (float(v) for v in quat)
        roll = float(np.arctan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
        pitch = float(np.arcsin(np.clip(2 * (w * y - z * x), -1.0, 1.0)))
        snap = self.snap
        if self.overlay is not None:
            self.overlay.record_step(foot_pos, contact)
        for key, value in (("t", k * dt), ("seg", 0), ("foot_pos_w", foot_pos), ("foot_contact", contact),
                           ("root_pos_w", root), ("root_quat_w", quat), ("roll", roll), ("pitch", pitch),
                           ("vx", float(vel[0])), ("vy", float(vel[1])), ("wz", float(wz)),
                           ("command", command), ("done", bool(done)), ("time_out", False),
                           ("map_use_gt", bool(snap.get("use_gt", False))),
                           ("gt_map", snap.get("gt_map", np.empty((0,), np.float32)).reshape(-1)),
                           ("refined_map", snap.get("refined_map", np.empty((0,), np.float32)).reshape(-1))):
            self.rows[key].append(np.asarray(value))

    def frame(self, env_id, root, command):
        import av
        import numpy as np
        from foothold_s2.eval.c_layer_frame_audit import project_world_point
        from foothold_s2.eval.c_layer_segmentation import robot_pixel_evidence, require_single_visible_robot
        from foothold_s2.eval.video25.record_c_layer import follow_camera_pose
        from foothold_s2.eval.ex42_d44_video import WIDTH, HEIGHT
        raw = self.raw
        eye, target = follow_camera_pose(root)
        raw.sim.set_camera_view(eye=eye, target=target)
        self.overlay_info.append({"frame": len(self.screen), **self.overlay.draw(command, self.snap)})
        before = (int(raw.common_step_counter), raw.scene["robot"].data.root_pos_w.detach().cpu().clone())
        for _ in range(2 if self.screen else 8):   # first frame: camera move and annotator need a few renders to settle
            raw.sim.render()
        image = np.ascontiguousarray(raw.render(recompute=True))[..., :3]
        after = (int(raw.common_step_counter), raw.scene["robot"].data.root_pos_w.detach().cpu())
        if before[0] != after[0] or not torch.equal(before[1], after[1]):
            raise RuntimeError("slow-forward rendering advanced physics")
        if image.shape[:2] != (HEIGHT, WIDTH) or float(image.astype(np.float32).mean()) <= 10.0:
            raise RuntimeError("slow-forward render frame dimension or brightness invalid")
        projection = project_world_point(root, eye, target, width=WIDTH, height=HEIGHT,
                                         focal_length_mm=self.intrinsics[0],
                                         horizontal_aperture_mm=self.intrinsics[1])
        self.screen.append({"root_center_px": projection,
                            "root_in_frame": 0 <= projection[0] < WIDTH and 0 <= projection[1] < HEIGHT,
                            "expected_static": False, "camera_eye_w": eye, "camera_target_w": target,
                            "focal_length_mm": self.intrinsics[0], "horizontal_aperture_mm": self.intrinsics[1]})
        pixels = robot_pixel_evidence(self.annotator.get_data(), selected_env=env_id,
                                      env_count=args.envs, height=HEIGHT, width=WIDTH)
        require_single_visible_robot(pixels)
        self.robots.append(pixels)
        for packet in self.clean_stream.encode(av.VideoFrame.from_ndarray(image, format="rgb24")):
            self.clean.mux(packet)

    def close(self):
        try:
            for packet in self.clean_stream.encode():
                self.clean.mux(packet)
        finally:
            self.clean.close()
            self.annotator.detach()


def _configure():
    env_cfg = load_cfg_from_registry(args.task, "env_cfg_entry_point")
    agent_cfg = load_cfg_from_registry(args.task, "rsl_rl_cfg_entry_point")
    env_cfg.scene.num_envs = args.envs
    env_cfg.sim.device = args.device
    agent_cfg.device = args.device
    if not args.no_video:
        env_cfg.viewer.resolution = (1280, 720)
    dr_mode = eval_dr_mode.DRMode.from_args(args, env_cfg, capture_per_env=False)
    dr_off = adapters.disable_eval_randomization(env_cfg)
    if sorted(dr_off) != sorted(EXPECTED_DR_OFF):
        raise RuntimeError("disabled DR list %r differs from %r" % (dr_off, EXPECTED_DR_OFF))
    curriculum_off = []
    for name in ("terrain_levels", "command_range"):
        if getattr(env_cfg.curriculum, name, None) is not None:
            setattr(env_cfg.curriculum, name, None)
            curriculum_off.append(name)
    env_cfg.commands.base_velocity.resampling_time_range = (1.0e9, 1.0e9)
    ex42_friction.configure(env_cfg, friction_policy)
    return env_cfg, agent_cfg, dr_mode, dr_off, curriculum_off


def _compare(reference_dir, cname, vx, al, dn, fw_end):
    """Per-env comparison with the reference env_arrays_eval_gt_<cmd>.npz (None when there is no reference)."""
    if reference_dir is None:
        return None
    path = Path(reference_dir) / f"env_arrays_eval_gt_{cname}.npz"
    if not path.is_file():
        return {"reference": str(path), "state": "reference file absent"}
    ref = np.load(path, allow_pickle=False)
    vx_diff = float(np.abs(ref["vx"].astype(np.float64) - vx.astype(np.float64)).max())
    row = {"reference": str(path), "reference_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
           "vx_max_abs_diff_mps": vx_diff,
           "alive_equal": bool(np.array_equal(ref["alive"], al)), "dones_equal": bool(np.array_equal(ref["dones"], dn)),
           "fwd_end_max_abs_diff_m": float(np.abs(ref["fwd_end_m"].astype(np.float64) - fw_end.astype(np.float64)).max())}
    row["same"] = bool(row["alive_equal"] and row["dones_equal"] and vx_diff <= 1.0e-4 and row["fwd_end_max_abs_diff_m"] <= 1.0e-3)
    return row


def _run_command(env, raw, dr_mode, runner, robot, term, sensor, body_ids, sensor_ids, cname, cmd, dt, checkpoint_preparation,
                 terrain_names, film=None, film_env=None):
    """eval_map_modes' per-command rollout (mode eval_gt, level 0 fixed terrain), plus optional filming of one env."""
    mode, dev, S = "eval_gt", raw.device, args.steps
    torch.manual_seed(args.eval_seed)
    dr_mode.begin(raw, "%s/%s" % (mode, cname), S, env.num_envs, dt)
    env.reset()
    terrain = raw.scene.terrain
    res_fixed = fixed_terrain.apply(raw, FIXED_LEVEL)
    env.reset()
    lv, ty = fixed_terrain.fixed_assignment(env.num_envs, res_fixed["rows"], res_fixed["cols"], FIXED_LEVEL)
    if not (np.array_equal(terrain.terrain_levels.cpu().numpy(), lv) and np.array_equal(terrain.terrain_types.cpu().numpy(), ty)):
        raise RuntimeError("fixed terrain tiles changed after reset")
    offset = (robot.data.root_pos_w[:, :2] - raw.scene.env_origins[:, :2]).abs().max().item()
    if offset > START_OFFSET_MAX_M + 1.0e-3:
        raise RuntimeError("%s: robot starts %.3f m from the env origin" % (cname, offset))
    term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)
    map_mode_cells.disable_heading_for_fixed_eval(term)
    policy = adapters.S2Policy(runner, env.num_envs, z_mode="mean", act_mode="mean", map_mode=mode)
    obs = env.get_observations()
    if checkpoint_preparation["checkpoint_pose_commands"]:
        ex41_eval_loader.verify_ex41_pose_observation(obs)
    alive = torch.ones(env.num_envs, dtype=torch.bool, device=dev)
    VX = torch.zeros(S, env.num_envs, device=dev)
    FW = torch.zeros(S, env.num_envs, device=dev)
    AL = torch.zeros(S, env.num_envs, dtype=torch.bool, device=dev)
    DN = torch.zeros(S, env.num_envs, dtype=torch.bool, device=dev)
    origins = raw.scene.env_origins
    for k in range(S):
        term.vel_command_b[:, :3] = torch.tensor(cmd, device=dev)
        map_mode_cells.assert_heading_off_for_fixed_eval(term)
        dr_mode.step(raw, k)
        a = policy(obs)
        obs, _r, dones, _x = env.step(a)
        map_mode_cells.assert_heading_off_for_fixed_eval(term)
        policy.reset(dones)
        AL[k] = alive & ~dones.bool()
        VX[k] = robot.data.root_lin_vel_b[:, 0]
        FW[k] = robot.data.root_pos_w[:, 0] - origins[:, 0]
        DN[k] = dones.bool()
        alive = alive & ~dones.bool()
        if film is not None:
            e = film_env
            data = robot.data
            root_e = data.root_pos_w[e].detach().cpu().numpy().copy()
            force = torch.linalg.vector_norm(sensor.data.net_forces_w[:, sensor_ids], dim=-1)
            cmd_e = term.vel_command_b[e, :3].detach().cpu().numpy().copy()
            film.tick(k, dt, data.body_pos_w[e, body_ids].detach().cpu().numpy().copy(),
                      (force[e] > 1.0).detach().cpu().numpy().copy(), root_e,
                      data.root_quat_w[e].detach().cpu().numpy().copy(), data.root_lin_vel_b[e].detach().cpu().numpy().copy(),
                      float(data.root_ang_vel_b[e, 2]), cmd_e, bool(dones[e]))
            if k % round(1.0 / (25 * dt)) == 0:
                film.frame_ticks.append(k)
                film.frame(e, root_e, tuple(float(v) for v in cmd_e))
    vx, al, dn, fw = VX.cpu().numpy(), AL.cpu().numpy(), DN.cpu().numpy(), FW.cpu().numpy()
    return {"vx": vx, "alive": al, "dones": dn, "fwd": fw, "terrain_levels": terrain.terrain_levels.cpu().numpy(),
            "terrain_types": terrain.terrain_types.cpu().numpy(),
            "assignment_sha256": fixed_terrain.assignment_sha256(terrain.terrain_levels.cpu().numpy(),
                                                                  terrain.terrain_types.cpu().numpy())}


def write_capture(film, cname, cmd, film_env, kind, per_env, dt, checkpoint_sha, terrain_sha, args_out):
    """25e capture folder (review.json / review_feet.npz / review.done) for the rule 4 composer."""
    from foothold_s2.eval import video_style
    cap = film.capture_dir
    steps = len(film.rows["t"])
    sample = film.frame_ticks
    frames = len(sample)
    duration = steps * dt
    if abs(duration * 25 - frames) > 1e-6 or sample != list(range(0, steps, round(1.0 / (25 * dt)))):
        raise RuntimeError("capture frames do not tile the recorded physics steps")
    commands = [{"name": cname, "label": SECONDS_LABEL.get(cname, cname), "target": list(cmd),
                 "start_s": 0.0, "duration_s": float(duration)}]
    arrays = {k: np.stack(v) for k, v in film.rows.items() if k not in ("gt_map", "refined_map")}
    for key in ("gt_map", "refined_map"):
        sizes = {row.size for row in film.rows[key]}
        arrays[key] = (np.stack(film.rows[key]).astype(np.float32) if len(sizes) == 1 and 0 not in sizes
                       else np.empty((0,), np.float32))
    arrays["body_height_foot_center_m"] = (arrays["root_pos_w"][:, 2] - arrays["foot_pos_w"][:, :, 2].mean(axis=1)).astype(np.float32)
    arrays["seg"] = arrays["seg"].astype(np.int8)
    arrays["dt"] = np.float64(dt)
    np.savez_compressed(cap / "review_feet.npz", **arrays)
    style = {"style_id": video_style.STYLE_ID, "approved": True, "allow_unapproved": False,
             "values": dict(video_style.APPROVED_STYLE), "approved_values": dict(video_style.APPROVED_STYLE)}
    meta = {"label": "slowfwd", "scene": f"G1b {cname} L0 {kind} env {film_env}",
            "task_selection": {"terrain_type": kind, "selected_tile": {"level": FIXED_LEVEL}},
            "selected_environment": {"env_id": film_env, "kind": kind, "level": FIXED_LEVEL, "col": per_env["col"],
                                     "selection_role": f"smallest level-0 env of kind {kind}"},
            "map_modes": {"map_mode": {"requested": "eval_gt"}},
            "step_contract": {"duration_s": duration, "physics_dt_s": dt, "physics_steps": steps,
                              "video_fps": 25, "video_frames": frames, "video_sample_step_indices": sample,
                              "commands": commands, "policy_modes": {"latent": "mean", "action": "mean"}},
            "camera_screen_projection": film.screen, "robot_instance_evidence": film.robots,
            "overlay_25e": {"legend": film.legend, "scene_foot_scan_visible": False,
                            "attention_hook": film.overlay.attn_hook_ok,
                            "saturation_multiplier": film.overlay.saturation_multiplier,
                            "frames": film.overlay_info, "attention_rows_per_step": film.overlay.attn_rows},
            "style": style, "lighting": film.style["lighting"], "checkpoint_sha256": checkpoint_sha,
            "mesh_sha256": terrain_sha, "per_env_row": per_env, "case_id": f"{args.suite}/{cname}"}
    (cap / "review.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (cap / "review.done").write_text("done\n", encoding="utf-8")


def main():
    env = None
    phase = "configure"
    try:
        print("SLOWFWD_PHASE", phase, flush=True)
        env_cfg, agent_cfg, dr_mode, dr_off, curriculum_off = _configure()
        phase = "checkpoint"
        checkpoint_state, checkpoint_preparation = ex41_eval_loader.load_checkpoint_for_eval(env_cfg, args.checkpoint)
        phase = "gym_make"
        env, raw = eval_dr_mode.make_wrapped_env_after_dr_ready(
            (lambda task, cfg: gym.make(task, cfg=cfg) if args.no_video else gym.make(task, cfg=cfg, render_mode="rgb_array")),
            RslRlVecEnvWrapper, args.task, env_cfg, agent_cfg.clip_actions, dr_mode)
        friction_receipt = ex42_friction.install_and_verify(raw, friction_policy)
        film = None
        film_env = args.film_env
        robot, sensor = raw.scene["robot"], raw.scene["contact_forces"]
        term = raw.command_manager.get_term("base_velocity")
        dt = float(raw.step_dt)
        map_mode_cells.disable_heading_for_fixed_eval(term)
        body, sensing = list(robot.body_names), list(sensor.body_names)
        if any(body.count(n) != 1 or sensing.count(n) != 1 for n in FEET):
            raise RuntimeError("four uniquely named robot and sensor feet are required")
        body_ids, sensor_ids = [body.index(n) for n in FEET], [sensing.index(n) for n in FEET]
        gen = raw.scene.terrain.cfg.terrain_generator
        terrain_names = columns.column_types({k: float(v.proportion) for k, v in gen.sub_terrains.items()}, int(gen.num_cols))
        # the fixed level-0 assignment is a function of the env number only: pick the filmed env now
        lv0, ty0 = fixed_terrain.fixed_assignment(args.envs, int(raw.scene.terrain.terrain_origins.shape[0]),
                                                  int(raw.scene.terrain.terrain_origins.shape[1]), FIXED_LEVEL)
        if film_env is None:
            film_env = next((i for i in range(args.envs) if terrain_names[int(ty0[i])] == args.film_kind), None)
            if film_env is None:
                raise RuntimeError("no level-0 env of kind %r" % args.film_kind)
        kind = terrain_names[int(ty0[film_env])]
        cmds = map_mode_cells.commands(args.suite)
        order = list(cmds)
        if args.command not in order:
            raise ValueError("--command is not in the suite")
        if not args.no_video:
            import omni.usd
            import omni.replicator.core as rep
            from pxr import UsdGeom
            from foothold_s2.eval import video_style
            from foothold_s2.eval.ex42_d44_video import prepare_render_product
            from foothold_s2.eval.c_layer_segmentation import ensure_only_selected_visible
            style = video_style.APPROVED_STYLE
            lighting = video_style.apply_lighting_profile(video_style.lighting_profile_settings(
                style["lighting_profile"], dome_intensity=style["dome_intensity"],
                three_point_intensity=style["three_point_intensity"],
                three_point_angle_deg=style["three_point_angle_deg"],
                three_point_elevation_deg=style["three_point_elevation_deg"],
                three_point_shadows=style["three_point_shadows"]))
            hidden = video_style.hide_nonselected_robot_roots(
                omni.usd.get_context().get_stage(), env_cfg.scene.robot.prim_path, film_env, args.envs)
            hidden["visibility_check"] = ensure_only_selected_visible(
                omni.usd.get_context().get_stage(), hidden["visible_robot_root"],
                hidden["hidden_robot_roots"], UsdGeom.Imageable)
            product = prepare_render_product(raw)
            annotator = rep.AnnotatorRegistry.get_annotator(
                "instance_id_segmentation_fast", init_params={"colorize": False}, device="cpu")
            annotator.attach([product])
            cam = UsdGeom.Camera(omni.usd.get_context().get_stage().GetPrimAtPath("/OmniverseKit_Persp"))
            args.out.mkdir(parents=True, exist_ok=False)
            film = Film(raw, annotator, args.out / f"{args.command}_env{film_env}_capture")
            film.intrinsics = (float(cam.GetFocalLengthAttr().Get()), float(cam.GetHorizontalApertureAttr().Get()))
            film.style = {"style_id": video_style.STYLE_ID, "values": style, "lighting": lighting,
                          "hidden_robot_roots": len(hidden["hidden_robot_roots"])}
        runner, saved = adapters.load_s2_runner(env, agent_cfg.to_dict(), args.checkpoint, args.device,
                                                checkpoint_state=checkpoint_state)
        if film is not None:
            from foothold_s2.eval.video25.overlay_25e import SceneOverlay, LEGEND
            perception = runner.perception
            original_advance = perception._advance
            fe = film_env

            def tapped_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map):
                result = original_advance(h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map)
                out = result[2]

                def row(values):
                    if values is None or not values.numel():
                        return np.empty((0,), dtype=np.float32)
                    return values[fe].reshape(-1).detach().float().cpu().numpy()
                film.snap.clear()
                film.snap.update({"depth": depth2[fe, -1].detach().float().cpu().numpy(),
                                  "gt_map": gt_map[fe].detach().float().cpu().numpy(),
                                  "rough_map": row(out.get("rough")), "refined_map": row(out.get("refined")),
                                  "use_gt": bool(use_gt[fe].item()),
                                  "first_after_reset": bool(first[fe].item())})
                return result
            perception._advance = tapped_advance
            foot_ids_r, _names = robot.find_bodies(".*_foot")
            # the attention hook turns off torch's MHA fastpath and changes the policy's numerics: no hook here
            film.overlay = SceneOverlay(raw, robot, foot_ids_r, type("NoAttention", (), {})(), env_index=film_env,
                                        saturation_multiplier=film.style["values"]["overlay_saturation"])
            film.legend = LEGEND
        checkpoint_sha = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        args.out.mkdir(parents=True, exist_ok=True)
        fidelity, last = {}, None
        for cname in order[:order.index(args.command) + 1]:
            filmed = cname == args.command
            try:
                last = _run_command(env, raw, dr_mode, runner, robot, term, sensor, body_ids, sensor_ids, cname,
                                    tuple(cmds[cname]), dt, checkpoint_preparation, terrain_names,
                                    film=film if filmed else None, film_env=film_env)
            finally:
                if filmed and film is not None:
                    film.close()
            fidelity[cname] = _compare(args.reference_dir, cname, last["vx"], last["alive"], last["dones"],
                                       last["fwd"][-1])
            print("SLOWFWD_COMMAND", cname, "filmed" if filmed else "replayed",
                  json.dumps(fidelity[cname]), flush=True)
        per_env = {"env": film_env, "kind": kind, "level": FIXED_LEVEL, "col": int(ty0[film_env]),
                   "alive_end": bool(last["alive"][-1, film_env]), "fwd_end_m": float(last["fwd"][-1, film_env]),
                   "vx_mean_alive": float(last["vx"][:, film_env][last["alive"][:, film_env]].mean()),
                   "command": list(cmds[args.command])}
        np.savez_compressed(args.out / f"env_arrays_eval_gt_{args.command}.npz", vx=last["vx"], alive=last["alive"],
                            dones=last["dones"], fwd=last["fwd"], terrain_level=last["terrain_levels"],
                            terrain_col=last["terrain_types"], dt=dt)
        if film is not None:
            write_capture(film, args.command, tuple(cmds[args.command]), film_env, kind, per_env, dt, checkpoint_sha,
                          last["assignment_sha256"], args.out)
        receipt = {"schema": "foothold-ex42-slowfwd-video/1", "checkpoint": str(args.checkpoint.resolve()),
                   "checkpoint_sha256": checkpoint_sha, "suite": args.suite, "command": args.command,
                   "film_env": film_env, "per_env_row": per_env, "eval_seed": args.eval_seed, "steps": args.steps,
                   "replayed_before": order[:order.index(args.command)], "fidelity": fidelity,
                   "fixed_terrain_assignment_sha256": last["assignment_sha256"],
                   "evaluation_friction": friction_receipt, "dr_off": dr_off, "curriculum_off": curriculum_off,
                   "plan": str(args.ex42_evaluation_plan), "no_video": bool(args.no_video)}
        (args.out / "slowfwd_receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
        print("SLOWFWD_DONE", args.out, flush=True)
    except BaseException as exc:
        print("SLOWFWD_FAILED", phase, repr(exc), file=sys.stderr, flush=True)
        traceback.print_exc()
        os._exit(1)      # Isaac Kit's close path can turn an uncaught child exception into rc 0
    finally:
        if env is not None:
            env.close()
        app.close()


if __name__ == "__main__":
    main()
