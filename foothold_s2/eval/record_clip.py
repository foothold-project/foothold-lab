"""평가 길(S1Adapter · v2 어댑터)로 정책 하나의 한 장면을 영상으로 찍는다 (lead 10/21 「수치만 보지 말고 영상으로」).

    python -m foothold_s2.eval.record_clip --policy s1scan|v2 --checkpoint <pt> --label <표시 이름> --terrain random_rough --noise 0.01,0.06
        --cmd 0.5,0,0 --seconds 8 --mp4 <폴더>/<이름>.mp4 --headless --device cuda:1

같은 시드 · 같은 지형 · 같은 시작점(출발 흔들기 0)으로 정책만 바꿔 찍는다. 카메라는 몸통을 따라가는 옆모습, 위쪽 HUD(명령 대 실제 속도 · 시각 · 발 접촉), 아래 띠(정책 · 지형 · 명령).
렌더는 화면용 GPU 에서만 된다 (CUDA_VISIBLE_DEVICES 로 가리면 창 생성에서 멈춘다). 프레임마다 밝기를 재서 기록한다.
"""

import argparse
import json
import os
import sys

import h5py  # noqa: F401
import tensordict  # noqa: F401
import torch
import rsl_rl.runners  # noqa: F401

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--policy", required=True)
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--label", required=True)
parser.add_argument("--terrain", default="random_rough")
parser.add_argument("--noise", default=None)
parser.add_argument("--cmd", default="0.5,0,0")
parser.add_argument("--seconds", type=float, default=8.0)
parser.add_argument("--width", type=int, default=960)
parser.add_argument("--height", type=int, default=540)
parser.add_argument("--fps", type=int, default=25)
parser.add_argument("--out", default=None)                       # run_kit.sh 가 폴더를 넣어 준다 (쓰지 않음)
parser.add_argument("--mp4", required=True)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
args.enable_cameras = True
app = AppLauncher(args).app
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import av  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import isaaclab_tasks  # noqa: E402,F401

import foothold_s2.tasks  # noqa: E402,F401
from foothold_s2.eval import adapters, runtime, terrain_sets  # noqa: E402

cmd = tuple(float(x) for x in args.cmd.split(","))
adapter = adapters.S2Adapter(args.policy[2:]) if args.policy.startswith("s2") else adapters.S1Adapter(args.policy[2:]) if args.policy.startswith("s1") else terrain_sets.isaaclab_adapter(args.policy, "unseen10")
adapter.render_mode = "rgb_array"
adapter.viewer_resolution = (args.width, args.height)
generator = terrain_sets.merged_generator([args.terrain], 0.5, 42)

if args.noise:
    lo_, hi_ = (float(x) for x in args.noise.split(","))
    generator.sub_terrains[args.terrain].noise_range = (lo_, hi_)

built = adapter.make_env(generator=generator, num_envs=1, duration_s=args.seconds + 2.0, seed=42, difficulty=0.5, base_cmd=[cmd],
                         spawn_xy_range=0.0, yaw_range_deg=0.0, joint_pos_scale=0.0, device=args.device)
raw = built["raw"]
pin = runtime.CommandPin(1, raw.device, [cmd])
term = adapter.pin_command(raw, pin)
env, policy, policy_nn, obs = adapter.load_policy(built, args.checkpoint)
raw.reset()
runtime.EpisodeRunner._write_command(term, pin.want)
obs = env.get_observations()
robot = raw.scene["robot"]
sensor = raw.scene["contact_forces"]
foot_s, _ = sensor.find_bodies(".*_foot")
dt = raw.step_dt
every = max(1, int(round(1.0 / (args.fps * dt))))
fps = 1.0 / (every * dt)
font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22)
font_big = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 26)
font_small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 18)
os.makedirs(os.path.dirname(os.path.abspath(args.mp4)), exist_ok=True)
container = av.open(args.mp4, mode="w")
stream = container.add_stream("libx264", rate=int(round(fps)))
stream.width, stream.height, stream.pix_fmt = args.width, args.height, "yuv420p"
stream.options = {"crf": "20", "preset": "medium"}
foot_r_ids, _ = robot.find_bodies(".*_foot")
base_s, _ = sensor.find_bodies("base")
step_stats = {"height": [], "base_contact": [], "yaw": []}
steps = int(round(args.seconds / dt))
_p0 = robot.data.root_pos_w[0].cpu().numpy()
raw.sim.set_camera_view(eye=(_p0[0] - 0.4, _p0[1] - 1.9, _p0[2] + 0.55), target=(_p0[0] + 0.1, _p0[1], _p0[2] + 0.12))

for _warm in range(12):                                         # 촬영 전 예열 렌더
    raw.render()

log = {"label": args.label, "terrain": args.terrain, "noise": args.noise, "cmd": cmd, "frames": 0, "means": [], "vx": [], "t": [], "contact": []}
prev_frame = None
same_run = max_same = 0
terrain_text = "%s%s" % (args.terrain, (" (노이즈 %s)" % args.noise) if args.noise else "")


def hud(frame, t, vx_cmd, vx_act, yaw_deg, feet_contact):
    img = Image.fromarray(frame)
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    d.rectangle([0, 0, w, 64], fill=(0, 0, 0, 150))
    d.text((14, 6), "명령 vx %.2f m/s" % vx_cmd, font=font_big, fill=(255, 255, 255, 255))
    d.text((300, 6), "실제 vx %.2f m/s" % vx_act, font=font_big,
           fill=(120, 255, 160, 255) if abs(vx_act - vx_cmd) < 0.15 else (255, 170, 90, 255))
    d.text((590, 6), "시각 %.1f s" % t, font=font_big, fill=(255, 255, 255, 255))
    d.text((14, 38), "방향(요) %+.0f 도  ·  발 접촉 %d/4" % (yaw_deg, feet_contact), font=font_small, fill=(210, 210, 210, 255))
    bx0, bx1, by = w - 330, w - 20, 40
    d.rectangle([bx0, by, bx1, by + 12], outline=(255, 255, 255, 200))
    scale = (bx1 - bx0) / 1.0
    d.rectangle([bx0, by, bx0 + max(0.0, min(1.0, vx_act)) * scale, by + 12], fill=(120, 255, 160, 220))
    d.line([bx0 + min(1.0, vx_cmd) * scale, by - 4, bx0 + min(1.0, vx_cmd) * scale, by + 16], fill=(255, 220, 80, 255), width=3)
    d.rectangle([0, h - 40, w, h], fill=(0, 0, 0, 170))
    d.text((14, h - 34), "%s  ·  %s  ·  명령 (%.2f, %.2f, %.2f)" % (args.label, terrain_text, cmd[0], cmd[1], cmd[2]),
           font=font, fill=(255, 255, 255, 255))

    return np.asarray(img)


for k in range(steps):
    with torch.inference_mode():
        obs, _r, dones, _x = env.step(policy(obs))
        policy_nn.reset(dones)

    runtime.EpisodeRunner._write_command(term, pin.want)

    # 매 스텝 통계(영상 프레임과 무관): 몸 원점 높이(지면 = 접촉한 발 구 바닥의 평균 높이) · 몸통(base) 접촉 · 요
    feet_z = robot.data.body_pos_w[0, foot_r_ids, 2]
    in_contact = sensor.data.net_forces_w[0, foot_s, :].norm(dim=-1) > 1.0

    if bool(in_contact.any()):
        ground_z = float(feet_z[in_contact].mean()) - 0.022
        step_stats["height"].append(float(robot.data.root_pos_w[0, 2]) - ground_z)

    step_stats["base_contact"].append(bool(sensor.data.net_forces_w[0, base_s, :].norm(dim=-1).max() > 1.0))
    _q = robot.data.root_quat_w[0].cpu().numpy()
    step_stats["yaw"].append(float(np.degrees(np.arctan2(2 * (_q[0] * _q[3] + _q[1] * _q[2]), 1 - 2 * (_q[2] ** 2 + _q[3] ** 2)))))

    if k % every:
        continue

    pos = robot.data.root_pos_w[0].cpu().numpy()
    raw.sim.set_camera_view(eye=(pos[0] - 0.4, pos[1] - 1.9, pos[2] + 0.55), target=(pos[0] + 0.1, pos[1], pos[2] + 0.12))
    frame = np.ascontiguousarray(raw.render())[..., :3]

    attempts = 0

    while float(frame.astype(np.float32).mean()) < 10.0 and attempts < 30:    # Isaac Sim 5.1 은 렌더 버퍼가 아직 안 찼으면 전부 0 을 돌려준다: 밝을 때까지 다시 렌더 (sim/eval/render_capture.py 와 같은 규칙)
        attempts += 1
        app.update()
        frame = np.ascontiguousarray(raw.render())[..., :3]

    log.setdefault("retries", []).append(attempts)

    if frame.shape[0] != args.height or frame.shape[1] != args.width:
        frame = np.asarray(Image.fromarray(frame).resize((args.width, args.height)))

    mean = float(frame.astype(np.float32).mean())
    q = robot.data.root_quat_w[0].cpu().numpy()
    yaw = float(np.degrees(np.arctan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2))))
    vx = float(robot.data.root_lin_vel_b[0, 0])
    contact = int((sensor.data.net_forces_w[0, foot_s, :].norm(dim=-1) > 1.0).sum())
    out = hud(frame, k * dt, cmd[0], vx, yaw, contact)

    if prev_frame is not None and float(np.abs(out.astype(np.int16) - prev_frame.astype(np.int16)).mean()) < 0.02:
        same_run += 1
        max_same = max(max_same, same_run)
    else:
        same_run = 0

    prev_frame = out
    log["means"].append(mean)
    log["vx"].append(vx)
    log["t"].append(k * dt)
    log["contact"].append(contact)
    log["frames"] += 1

    for packet in stream.encode(av.VideoFrame.from_ndarray(out, format="rgb24")):
        container.mux(packet)

for packet in stream.encode():
    container.mux(packet)

container.close()
summary = {k: v for k, v in log.items() if k not in ("means", "vx", "t", "contact", "retries")}
summary["min_mean_brightness"] = float(min(log["means"]))
summary["max_identical_consecutive_frames"] = int(max_same)
summary["fps"] = fps
summary["body_height_over_ground_median_m"] = float(np.median(step_stats["height"]))
summary["body_height_over_ground_p10_m"] = float(np.percentile(step_stats["height"], 10))
summary["base_contact_fraction_of_steps(>1N)"] = float(np.mean(step_stats["base_contact"]))
summary["yaw_abs_max_deg"] = float(np.max(np.abs(step_stats["yaw"])))
summary["yaw_final_deg"] = float(step_stats["yaw"][-1])
summary["render_retries_max"] = int(max(log["retries"]))
summary["frames_that_needed_retry"] = int(sum(1 for r in log["retries"] if r))
summary["vx_by_second"] = [float(np.mean([v for v, t in zip(log["vx"], log["t"]) if int(t) == s])) for s in range(int(args.seconds))]
summary["feet_in_contact_by_second"] = [float(np.mean([c for c, t in zip(log["contact"], log["t"]) if int(t) == s])) for s in range(int(args.seconds))]
summary["forward_progress_m"] = float(np.sum(np.array(log["vx"]) * (every * dt)))
json.dump(summary, open(os.path.splitext(args.mp4)[0] + ".json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("CLIP", args.mp4, "frames", log["frames"], "min brightness %.1f" % summary["min_mean_brightness"], "max identical run", max_same, flush=True)
sys.stdout.flush()
os._exit(0)
