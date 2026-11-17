"""환경 차이 확인 (OPS v0.2 5.1 절 · lead 11/17 14:08): 정본 3 하위 정책을 Isaac Lab 3.0 PhysX 에서 평지 하나에 걸려 본다.
명령 다섯 (전진 0.1 · 전진 0.2 · 옆 +0.2 · 옆 -0.2 · yaw 0.5) 을 6 초씩, 32 env, 같은 시드. 칸마다 평균 이동 · 넘어짐 · 성공.
성공 = 안 넘어졌고, 1 초 뒤 명령 축의 실제 평균 속도가 명령의 0.8~1.2 배, 0.5 초 창 평균과 명령의 평균 절대 차 (MAE) 가 명령의 20 % 이하 (line50.py 의 유지 성공과 같은 식).
계산부는 numpy 만 (CPU 시험). 시뮬을 부르는 `run_cases` 는 Kit 에서만. OPS v0.2 원문은 이 세션에서 못 찾아, 기준은 lead 메시지의 항목 그대로다 (원문과 다르면 CASES · 식만 고치면 된다).
"""
from __future__ import annotations

import numpy as np

HIGH_DT_S = 0.1                      # 상위 틱 (하위 5 스텝 x 0.02 s)
SECONDS = 6.0
SETTLE_S = 1.0
ENVS = 32
CASES = (("fwd0.1", (0.1, 0.0, 0.0)), ("fwd0.2", (0.2, 0.0, 0.0)), ("side+0.2", (0.0, 0.2, 0.0)), ("side-0.2", (0.0, -0.2, 0.0)), ("yaw0.5", (0.0, 0.0, 0.5)))
WINDOW_TICKS = 5                     # 0.5 초


def flat_room_spec(seed: int = 0) -> dict:
    """방 전체가 평지 (프리미티브 없음) 인 명세. room_generator.build_room 에 넘긴다."""
    from foothold_s2.nav import room_generator as rg

    spec = rg.generate_spec(seed, rg.RoomConfig(sparse_patch_kinds=()))
    spec["tiles"] = np.zeros_like(np.asarray(spec["tiles"])).tolist()       # TILE_FLAT = 0
    spec["primitives"] = []
    return spec


def score_case(track_err, done, pos_start, pos_end, command, *, seconds: float = SECONDS, settle_s: float = SETTLE_S) -> dict:
    """track_err (T, 5, n, 3) = 상위 틱마다 하위 5 스텝의 (실제 - 명령) · done (n,) bool 윈도 안에 끝남 · pos_*: (n, 2) 월드 xy · command (3,).
    명령 축 = 절댓값이 가장 큰 칸. 이동 = 끝난 env 를 뺀 평균 직선 거리 (시작 방향이 무작위라 +x 가 아님) [m] · 회전 명령이면 평균 속도 비율만."""
    err = np.asarray(track_err, dtype=np.float64)
    cmd = np.asarray(command, dtype=np.float64)
    ax = int(np.argmax(np.abs(cmd)))
    c = float(cmd[ax])
    n = err.shape[2]
    done = np.asarray(done, dtype=bool)
    actual = c + err[..., ax].mean(1)                                  # (T, n) 틱 평균 실제 속도
    skip = int(round(settle_s / HIGH_DT_S))
    a = actual[skip:]
    ratio = a.mean(0) / c
    w = (a.shape[0] // WINDOW_TICKS) * WINDOW_TICKS
    mae = np.abs(a[:w].reshape(-1, WINDOW_TICKS, n).mean(1) - c).mean(0)
    ok = (~done) & (ratio >= 0.8) & (ratio <= 1.2) & (mae <= 0.2 * abs(c))
    moved = np.hypot(*(np.asarray(pos_end, dtype=np.float64) - np.asarray(pos_start, dtype=np.float64)).T)
    alive = ~done
    return {"command": [float(x) for x in cmd], "envs": int(n), "fell": int(done.sum()), "success": int(ok.sum()),
            "mean_ratio": float(ratio[alive].mean()) if alive.any() else None, "mean_move_m": float(moved[alive].mean()) if alive.any() else None,
            "mae_over": int((mae > 0.2 * abs(c)).sum()), "seconds": seconds}


def run_cases(nav, *, on_tick=None, ticks: int | None = None) -> dict:
    """Kit 에서만. 칸마다 reset -> 같은 명령 ticks 번. on_tick(case_name, tick_index, step) 는 영상 · 깊이 저장용 훅."""
    ticks = int(round(SECONDS / HIGH_DT_S)) if ticks is None else ticks
    out = {}
    for name, cmd in CASES:
        s0 = nav.reset()
        start = np.asarray(s0.pos_w)[:, :2].copy()
        errs, done_any = [], np.zeros(nav.n, dtype=bool)
        command = np.tile(np.asarray(cmd, dtype=np.float64), (nav.n, 1))
        s = s0
        for t in range(ticks):
            s = nav.step(command)
            errs.append(np.asarray(s.track_err))
            done_any |= np.asarray(s.done, dtype=bool)
            if on_tick is not None:
                on_tick(name, t, s)
        out[name] = score_case(np.stack(errs), done_any, start, np.asarray(s.pos_w)[:, :2], cmd, seconds=ticks * HIGH_DT_S)
    return out


def verdict(result: dict, *, min_success_frac: float = 0.8) -> dict:
    """칸마다 성공 수가 envs 의 min_success_frac 이상이고 넘어진 env 가 없으면 PASS 인 표시만 (정본 3 의 2.3.2 기준값은 없어 임계는 가정 · 판정은 lead)."""
    rows = {k: bool(v["success"] >= min_success_frac * v["envs"] and v["fell"] == 0) for k, v in result.items()}
    return {"per_case_pass": rows, "all_pass": all(rows.values()), "assumed_min_success_frac": min_success_frac}


# ---------------------------------------------------------------- Kit 쪽: 걷는 RGB 영상 · 35 도 깊이 저장 (Kit 에서만)
RGB_H, RGB_W = 240, 320
RGB_OFFSET_POS = (-1.6, 0.0, 0.8)        # 몸통 뒤 위 (몸 틀) · 가정: 걷는 모습이 보이게 (실측 아님)
RGB_PITCH_DEG = 20.0
SAVE_ENVS = 4
VIDEO_CASE = "fwd0.2"


def rgb_camera_cfg():
    """몸통 따라가는 RGB 카메라 (3.0: CameraCfg · 2.x: TiledCameraCfg). 렌더링 앱 필요 (enable_cameras)."""
    import isaaclab.sim as sim_utils
    from isaaclab.sensors import camera as cam

    from foothold_s2.lab_compat import lab_major, quat_cfg
    from foothold_s2.nav.hl_student import pitch_down_quat_wxyz

    cfg_cls = cam.CameraCfg if lab_major() >= 3 else cam.TiledCameraCfg
    return cfg_cls(prim_path="{ENV_REGEX_NS}/Robot/base/rgb_cam", update_period=0.0, height=RGB_H, width=RGB_W, data_types=["rgb"],
                   spawn=sim_utils.PinholeCameraCfg(focal_length=18.0, focus_distance=400.0, horizontal_aperture=20.955, clipping_range=(0.1, 50.0)),
                   offset=cfg_cls.OffsetCfg(pos=RGB_OFFSET_POS, rot=quat_cfg(pitch_down_quat_wxyz(RGB_PITCH_DEG)), convention="world"))


class Recorder:
    """VIDEO_CASE 칸에서 첫 SAVE_ENVS 개 env 의 RGB (틱마다) 와 35 도 깊이를 모은다. 카메라 센서가 없으면 그쪽은 건너뜀 (이유를 notes 에)."""

    def __init__(self, raw, rgb: bool, depth: bool):
        from foothold_s2.lab_compat import th

        self.th, self.raw, self.frames, self.depth, self.pos, self.quat, self.notes = th, raw, [], [], [], [], []
        self.rgb_on, self.depth_on = rgb, depth

    def __call__(self, case, t, s):
        if case != VIDEO_CASE:
            return
        self.pos.append(np.asarray(s.pos_w)[:SAVE_ENVS].copy()); self.quat.append(np.asarray(s.quat_w)[:SAVE_ENVS].copy())
        if self.rgb_on:
            try:
                img = self.th(self.raw.scene["rgb_camera"].data.output["rgb"])[:SAVE_ENVS, ..., :3].detach().cpu().numpy().astype(np.uint8)
                self.frames.append(img)
            except Exception as exc:                          # noqa: BLE001
                self.notes.append(f"rgb tick {t}: {type(exc).__name__}: {exc}"[:200]); self.rgb_on = False
        if self.depth_on:
            try:
                d = self.th(self.raw.scene["depth_camera"].data.output["distance_to_image_plane"])[:SAVE_ENVS].detach().cpu().numpy()
                self.depth.append(d.reshape(d.shape[0], d.shape[1], d.shape[2]).astype(np.float16))
            except Exception as exc:                          # noqa: BLE001
                self.notes.append(f"depth tick {t}: {type(exc).__name__}: {exc}"[:200]); self.depth_on = False

    def save(self, out) -> dict:
        from pathlib import Path

        out = Path(out)
        info = {"notes": list(self.notes)}
        if self.depth:
            from foothold_s2.nav import hl_student

            np.savez_compressed(out / "depth35_fwd0.2.npz", depth=np.stack(self.depth), pos_w=np.stack(self.pos), quat_w=np.stack(self.quat),
                                pitch_deg=hl_student.CAMERA_PITCH_DEG, cam_pos_b=np.asarray(hl_student.CAMERA_POS_M), dt=HIGH_DT_S,
                                note="distance_to_image_plane [m] (T, env, 180, 320) float16 · 첫 4 env · 몸 자세 pos_w/quat_w(wxyz)")
            info["depth_frames"] = len(self.depth)
        if self.frames:
            fr = np.stack(self.frames)                           # (T, env, H, W, 3)
            np.savez_compressed(out / "rgb_fwd0.2.npz", rgb=fr[:, 0], dt=HIGH_DT_S)
            info["rgb_frames"] = int(fr.shape[0])
            try:
                from moviepy import ImageSequenceClip

                ImageSequenceClip([f for f in fr[:, 0]], fps=int(round(1.0 / HIGH_DT_S))).write_videofile(str(out / "walk_fwd0.2.mp4"), logger=None)
                info["video"] = "walk_fwd0.2.mp4"
            except Exception as exc:                              # noqa: BLE001 (moviepy 없음: npz 만 · Pod 에서 pip install --target 으로 깔아야 함)
                info["video_error"] = f"{type(exc).__name__}: {exc}"[:200]
        return info
