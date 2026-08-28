#!/usr/bin/env python3
"""공식 unitree_rl_mjlab Go2 속도 정책으로 레일즈를 50회 평가한다.

판정은 사이트 일반화 벤치와 같다.
https://foothold-project.vercel.app/research-generalization-benchmark-10-terrains
docs/research/benchmark-setup-lim.md
  종합 = 생존 AND 전진 AND 추종 AND 방향
  전진 성공 = 이상 거리의 70% (0.5 m/s × 시간)
  추종 성공 = planar velocity MAE 0.25 m/s 이하
  방향 성공 = 측면 0.75 m 이하
  생존 = 제한시간까지 낙상 없음

에피소드 길이는 영상 10초에 맞춘다. 사이트 본문은 6초다.
레일즈 기하는 팀 v2: 높이 11.5 cm, 안쪽 8 cm, 바깥 18 cm.
로봇 시각은 mujoco_menagerie Go2 메시. 충돌 박스는 그 모델과 같다.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import tempfile
from pathlib import Path

# 헤드리스: 영상 없이 돌릴 때는 disable. 영상은 xvfb-run + glfw.
if "MUJOCO_GL" not in os.environ:
    os.environ["MUJOCO_GL"] = "disable"

import imageio.v2 as imageio
import mujoco
import numpy as np

from official_policy import DEFAULT_POS_POLICY, Go2MjlabPolicy, from_policy
from rails_scene import GO2_MOTOR_XML, write_scene

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "results" / "official_rails"


def _quat_yaw(q: np.ndarray) -> float:
    w, x, y, z = q
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def _track_camera(model: mujoco.MjModel) -> mujoco.MjvCamera:
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(cam)
    cam.type = mujoco.mjtCamera.mjCAMERA_TRACKING
    cam.trackbodyid = int(model.body("base").id)
    cam.distance = 2.2
    cam.azimuth = 145.0
    cam.elevation = -22.0
    return cam


def rollout(
    xml: str,
    policy: Go2MjlabPolicy,
    seed: int,
    duration_s: float = 10.0,
    cmd_vx: float = 0.5,
    record: bool = False,
    video_path: Path | None = None,
    video_fps: int = 30,
    xml_path: Path | None = None,
) -> dict:
    rng = np.random.default_rng(seed)
    if xml_path is not None:
        model = mujoco.MjModel.from_xml_path(str(xml_path))
    else:
        model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    yaw = float(rng.uniform(-0.15, 0.15))
    data.qpos[0] += float(rng.uniform(-0.08, 0.08))
    data.qpos[1] += float(rng.uniform(-0.08, 0.08))
    data.qpos[3:7] = np.array(
        [math.cos(yaw / 2.0), 0.0, 0.0, math.sin(yaw / 2.0)]
    )
    data.qpos[7:19] = from_policy(DEFAULT_POS_POLICY)
    mujoco.mj_forward(model, data)

    policy.reset()
    cmd = np.array([cmd_vx, 0.0, 0.0], dtype=np.float64)
    dt = model.opt.timestep
    decim = 10  # 0.002 * 10 = 0.02 s, 50 Hz
    n_steps = int(duration_s / dt)
    x0, y0 = float(data.qpos[0]), float(data.qpos[1])
    vel_err_sum = 0.0
    n_ctrl = 0
    fallen = False
    fall_t = ""
    freeze_xy = None
    freeze_z = None
    frames = []
    renderer = None
    cam = None
    scene_option = None
    if record:
        renderer = mujoco.Renderer(model, height=352, width=640, max_geom=20000)
        cam = _track_camera(model)
        scene_option = mujoco.MjvOption()
        # 시각 메시(group 2)만. 충돌 박스(group 3)는 끈다.

    target = from_policy(DEFAULT_POS_POLICY)
    for i in range(n_steps):
        if i % decim == 0 and not fallen:
            target = policy.act(data, cmd)
            vx = float(data.qvel[0])
            vy = float(data.qvel[1])
            vel_err_sum += abs(math.hypot(vx, vy) - cmd_vx)
            n_ctrl += 1
        data.ctrl[:] = policy.torque(data, target)
        mujoco.mj_step(model, data)
        z = float(data.qpos[2])
        pitch = math.asin(max(-1.0, min(1.0, 2 * (data.qpos[3] * data.qpos[5] - data.qpos[6] * data.qpos[4]))))
        roll = math.atan2(
            2 * (data.qpos[3] * data.qpos[4] + data.qpos[5] * data.qpos[6]),
            1 - 2 * (data.qpos[4] ** 2 + data.qpos[5] ** 2),
        )
        if z < 0.12 or abs(pitch) > 1.0 or abs(roll) > 1.0:
            if not fallen:
                fallen = True
                fall_t = (i + 1) * dt
                freeze_xy = (float(data.qpos[0]), float(data.qpos[1]))
                freeze_z = z
            if not record:
                break
        if record and renderer is not None:
            cur = int(i * video_fps * dt)
            prev = int((i - 1) * video_fps * dt) if i else -1
            if cur != prev:
                renderer.update_scene(data, camera=cam, scene_option=scene_option)
                frames.append(renderer.render().copy())

    if freeze_xy is not None:
        x, y = freeze_xy
        final_z = freeze_z
    else:
        x, y = float(data.qpos[0]), float(data.qpos[1])
        final_z = float(data.qpos[2])
    forward = x - x0
    lateral = abs(y - y0)
    duration = float(fall_t) if fallen and fall_t != "" else duration_s
    vel_mae = vel_err_sum / max(n_ctrl, 1)
    ideal = cmd_vx * duration_s
    min_progress = 0.70 * ideal
    survival = (not fallen) and duration >= duration_s - 1e-6
    progress = forward >= min_progress
    tracking = vel_mae <= 0.25
    direction = lateral <= 0.75
    overall = survival and progress and tracking and direction

    if record and video_path is not None and frames:
        video_path.parent.mkdir(parents=True, exist_ok=True)
        imageio.mimsave(video_path, frames, fps=video_fps, codec="libx264", quality=7)
    if renderer is not None:
        renderer.close()

    return {
        "episode": None,
        "seed": seed,
        "forward_progress_m": forward,
        "lateral_drift_m": lateral,
        "velocity_mae_mps": vel_mae,
        "duration_s": duration,
        "fallen": int(fallen),
        "fall_time_s": fall_t if fall_t != "" else "",
        "survival_success": int(survival),
        "progress_success": int(progress),
        "tracking_success": int(tracking),
        "direction_success": int(direction),
        "overall_success": int(overall),
        "final_z": final_z,
        "min_progress_m": min_progress,
        "ideal_distance_m": ideal,
        "command_vx": cmd_vx,
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    fwd = [r["forward_progress_m"] for r in rows]
    failed = [r for r in rows if r["fallen"]]
    mean_fall = (
        sum(float(r["fall_time_s"]) for r in failed) / len(failed) if failed else ""
    )
    return {
        "terrain": "rails",
        "episodes": n,
        "overall_success_rate": sum(r["overall_success"] for r in rows) / n,
        "survival_rate": sum(r["survival_success"] for r in rows) / n,
        "progress_success_rate": sum(r["progress_success"] for r in rows) / n,
        "tracking_success_rate": sum(r["tracking_success"] for r in rows) / n,
        "direction_success_rate": sum(r["direction_success"] for r in rows) / n,
        "mean_forward_progress_m": float(np.mean(fwd)),
        "std_forward_progress_m": float(np.std(fwd, ddof=1)) if n > 1 else 0.0,
        "mean_lateral_drift_m": float(np.mean([r["lateral_drift_m"] for r in rows])),
        "mean_velocity_mae_mps": float(np.mean([r["velocity_mae_mps"] for r in rows])),
        "mean_episode_duration_s": float(np.mean([r["duration_s"] for r in rows])),
        "mean_fall_time_s": mean_fall,
        "height_m": 0.115,
        "thickness_inner_m": 0.08,
        "thickness_outer_m": 0.18,
        "policy": "unitree_rl_mjlab Unitree-Go2-Flat ONNX (diasAiMaster/unitree-go2-velocity-flat)",
        "duration_s_protocol": 10.0,
        "site_duration_s": 6.0,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", type=int, default=50)
    p.add_argument("--duration", type=float, default=10.0)
    p.add_argument("--cmd-vx", type=float, default=0.5)
    p.add_argument("--videos", type=int, default=1, help="앞에서부터 몇 개를 10초 영상으로 저장할지")
    p.add_argument(
        "--only-episodes",
        type=str,
        default="",
        help="쉼표로 나눈 에피소드 번호만 돈다. 시드는 50회와 같다 (1000+ep).",
    )
    p.add_argument("--keep-csv", action="store_true", help="raw/summary CSV를 덮지 않음")
    p.add_argument("--flat", action="store_true")
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    video_dir = OUT_DIR / "videos"
    video_dir.mkdir(exist_ok=True)

    scene_path = None
    if args.flat:
        go2 = GO2_MOTOR_XML.resolve()
        assets = go2.parent / "assets"
        xml = f"""<mujoco model="go2_flat">
  <compiler meshdir="{assets}"/>
  <include file="{go2}"/>
  <worldbody>
    <light pos="0 0 2" dir="0 0 -1" directional="true"/>
    <geom name="floor" type="plane" size="20 20 0.05" friction="0.9 0.02 0.01"/>
  </worldbody>
</mujoco>
"""
        kind = "flat"
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as tmp:
            tmp.write(xml)
            scene_path = Path(tmp.name)
    else:
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as tmp:
            scene_path = write_scene(
                Path(tmp.name),
                height=0.115,
                thickness_inner=0.08,
                thickness_outer=0.18,
                robot_xml=GO2_MOTOR_XML,
            )
        xml = Path(scene_path).read_text(encoding="utf-8")
        kind = "rails_v2"

    policy = Go2MjlabPolicy()
    if args.only_episodes.strip():
        episode_ids = [int(x) for x in args.only_episodes.split(",") if x.strip() != ""]
    else:
        episode_ids = list(range(args.episodes))
    rows = []
    for i_run, ep in enumerate(episode_ids):
        if args.only_episodes.strip():
            record = args.videos != 0
        else:
            record = i_run < args.videos
        video_path = video_dir / f"{kind}-ep{ep:02d}.mp4"
        r = rollout(
            xml,
            policy,
            seed=1000 + ep,
            duration_s=args.duration,
            cmd_vx=args.cmd_vx,
            record=record,
            video_path=video_path if record else None,
            xml_path=scene_path,
        )
        r["episode"] = ep
        r["kind"] = kind
        rows.append(r)
        print(
            f"{kind} ep{ep:02d} fwd={r['forward_progress_m']:.2f}m "
            f"surv={r['survival_success']} prog={r['progress_success']} "
            f"track={r['tracking_success']} dir={r['direction_success']} "
            f"overall={r['overall_success']} fallen={r['fallen']}"
        )

    summ = summarize(rows)
    if not args.keep_csv:
        raw_path = OUT_DIR / "raw.csv"
        sum_path = OUT_DIR / "summary.csv"
        keys = list(rows[0].keys())
        with raw_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        with sum_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(summ.keys()))
            w.writeheader()
            w.writerow(summ)
        print(f"raw {raw_path}")
        print(f"summary {sum_path}")

    n = len(rows)
    print("\n=== summary ===")
    print(f"n={n} overall={100*summ['overall_success_rate']:.1f}% "
          f"survival={100*summ['survival_rate']:.1f}% "
          f"forward={summ['mean_forward_progress_m']:.2f}±{summ['std_forward_progress_m']:.2f}m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
