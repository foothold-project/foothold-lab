#!/usr/bin/env python3
"""레일즈 높이×두께 평가. 학습 없음.

Go2 몸체: Unitree 공개 URDF 계열 (mujoco_menagerie).
보행: 열린 루프 PD 트로트. Unitree 스포츠 모드·공개 RL 정책 아님. Isaac 기준선 아님.
판정: 6초 동안 전진 3 m, 몸통이 너무 낮거나 기울면 낙상.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import tempfile
from pathlib import Path

import mujoco
import numpy as np

from rails_scene import write_scene
from walk_trot import STAND, trot_targets

ROOT = Path(__file__).resolve().parent


def _flat_xml() -> str:
    go2 = (ROOT / "go2_collision.xml").resolve()
    return f"""<mujoco model="go2_flat">
  <include file="{go2}"/>
  <worldbody>
    <light pos="0 0 2" dir="0 0 -1" directional="true"/>
    <geom name="floor" type="plane" size="20 20 0.05" friction="0.9 0.02 0.01"/>
  </worldbody>
</mujoco>
"""


def _quat_pitch_roll(q: np.ndarray) -> tuple[float, float]:
    w, x, y, z = q
    sinp = 2 * (w * y - z * x)
    sinp = max(-1.0, min(1.0, sinp))
    pitch = math.asin(sinp)
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    return pitch, roll


def rollout(
    xml: str,
    duration_s: float = 6.0,
    settle_s: float = 0.5,
    target_m: float = 3.0,
) -> dict:
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_resetDataKeyframe(model, data, 0)
    # 트로트가 몸통 -x 로 가서, 머리를 -x 로 돌리면 세계 +x 가 진행 방향이 된다.
    data.qpos[3:7] = np.array([0.0, 0.0, 0.0, 1.0])
    mujoco.mj_forward(model, data)
    dt = model.opt.timestep
    n_settle = int(settle_s / dt)
    n_run = int(duration_s / dt)
    fallen = False
    t0 = None
    x0 = None

    for i in range(n_settle + n_run):
        t = i * dt
        if i < n_settle:
            data.ctrl[:] = STAND
        else:
            if t0 is None:
                t0 = t
                x0 = float(data.qpos[0])
            data.ctrl[:] = trot_targets(t - t0)
        mujoco.mj_step(model, data)
        z = float(data.qpos[2])
        pitch, roll = _quat_pitch_roll(data.qpos[3:7])
        if z < 0.12 or abs(pitch) > 0.9 or abs(roll) > 0.9:
            fallen = True
            break

    x = float(data.qpos[0])
    forward = 0.0 if x0 is None else x - x0
    elapsed = (i + 1) * dt
    return {
        "forward_m": forward,
        "duration_s": elapsed,
        "fallen": int(fallen),
        "survived": int(not fallen),
        "success": int((not fallen) and forward >= target_m),
        "final_z": float(data.qpos[2]),
    }


def parse_list(s: str) -> list[float]:
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--heights", default="0.05,0.115,0.18", help="미터. 예: 0.05,0.115,0.18")
    p.add_argument("--thicknesses", default="0.08,0.18,0.30", help="미터. 안팎 같은 값")
    p.add_argument("--isaac-split", action="store_true", help="안쪽 8cm 바깥 18cm 고정, 높이만 스윕")
    p.add_argument("--flat", action="store_true", help="턱 없이 평지만")
    p.add_argument("--episodes", type=int, default=1)
    p.add_argument("--duration", type=float, default=6.0)
    p.add_argument("--out", type=Path, default=ROOT / "results" / "grid.csv")
    args = p.parse_args()

    rows = []
    if args.flat:
        xml = _flat_xml()
        for ep in range(args.episodes):
            r = rollout(xml, duration_s=args.duration)
            r.update(height_m=0.0, thickness_m=0.0, episode=ep, kind="flat")
            rows.append(r)
            print(f"flat ep{ep} forward={r['forward_m']:.2f}m fallen={r['fallen']} success={r['success']}")
    elif args.isaac_split:
        heights = parse_list(args.heights)
        for h in heights:
            with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as tmp:
                path = write_scene(Path(tmp.name), height=h, thickness_inner=0.08, thickness_outer=0.18)
            xml = Path(path).read_text(encoding="utf-8")
            for ep in range(args.episodes):
                r = rollout(xml, duration_s=args.duration)
                r.update(height_m=h, thickness_inner_m=0.08, thickness_outer_m=0.18, episode=ep, kind="isaac_split")
                rows.append(r)
                print(
                    f"h={h*100:.1f}cm inner=8 outer=18 ep{ep} "
                    f"forward={r['forward_m']:.2f}m fallen={r['fallen']} success={r['success']}"
                )
    else:
        heights = parse_list(args.heights)
        thicks = parse_list(args.thicknesses)
        for h in heights:
            for th in thicks:
                with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as tmp:
                    path = write_scene(Path(tmp.name), height=h, thickness_inner=th, thickness_outer=th)
                xml = Path(path).read_text(encoding="utf-8")
                for ep in range(args.episodes):
                    r = rollout(xml, duration_s=args.duration)
                    r.update(height_m=h, thickness_m=th, episode=ep, kind="square")
                    rows.append(r)
                    print(
                        f"h={h*100:.1f}cm t={th*100:.1f}cm ep{ep} "
                        f"forward={r['forward_m']:.2f}m fallen={r['fallen']} success={r['success']}"
                    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for row in rows for k in row})
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
