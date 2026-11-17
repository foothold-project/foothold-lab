"""하위 정책의 고유감각 관측 45 칸이 Isaac Lab 3.0 에서도 2.3.2 와 같은 뜻인지 시뮬 안에서 대조한다 (lead 11/17 13:22 · 「관측 순서 · 쿼터니언」).
관측 45 = base_ang_vel 0:3 · projected_gravity 3:6 · velocity_commands 6:9 · joint_pos_rel 9:21 · joint_vel_rel 21:33 · last_action 33:45 (tasks/s1_env_cfg.py PolicyCfg 순서).
방법: 몸통을 알려진 각도로 기울여 쓰고 (쓰는 쿼터니언은 `lab_compat.quat_to_sim`) 한 스텝 뒤에, 시뮬이 돌려주는 관측 칸과 같은 시점의 몸통 상태에서 손으로 계산한 값을 견준다.
쿼터니언 순서가 어느 한쪽에서 틀리면 중력 투영 3 칸이 크게 어긋난다 (오류 없이 값만 틀어지는 곳). 계산부는 numpy 만 (CPU 시험), `kit_probe` 만 Kit 에서 돈다.
"""
from __future__ import annotations

import numpy as np

SLICES = {"base_ang_vel": (0, 3), "projected_gravity": (3, 6), "velocity_commands": (6, 9),
          "joint_pos_rel": (9, 21), "joint_vel_rel": (21, 33), "last_action": (33, 45)}
ATOL = 1.0e-4
# 2.3.2 에서 하위 정책이 학습된 관절 순서 (sim/eval/results/20260929-axis2-ext-clips/v1/probe_manifest.json 의 joint_names · 종류별로 FL FR RL RR)
JOINT_NAMES_232 = tuple(f"{leg}_{part}_joint" for part in ("hip", "thigh", "calf") for leg in ("FL", "FR", "RL", "RR"))
TILT_RPY = (0.3, -0.2, 0.9)                      # 라디안: 몸통 기울임 (종료 조건 안쪽 · 가정) + 방향 돌림


def quat_wxyz_from_rpy(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr, cp, sp, cy, sy = (np.cos(roll / 2), np.sin(roll / 2), np.cos(pitch / 2), np.sin(pitch / 2), np.cos(yaw / 2), np.sin(yaw / 2))
    return np.array([cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy])


def projected_gravity(q_wxyz) -> np.ndarray:
    """몸 틀에서 본 중력 방향 (월드 (0, 0, -1) 을 q 의 역으로 돌린 것). q (n, 4) wxyz."""
    q = np.asarray(q_wxyz, dtype=np.float64)
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    g = np.array([0.0, 0.0, -1.0])
    # v' = v + 2w (u x v) + 2 u x (u x v) 의 역회전 (u -> -u)
    u = -np.stack([x, y, z], axis=1)
    t = 2.0 * np.cross(u, g)
    return g + w[:, None] * t + np.cross(u, t)


def compare_obs(obs, *, quat_wxyz, ang_vel_b, command, joint_pos, default_joint_pos, joint_vel, last_action, atol: float = ATOL) -> dict:
    """obs (n, >=45) 시뮬이 준 관측 · 나머지는 같은 시점 상태 (모두 numpy). 칸별 최대 절대 오차와 통과 여부."""
    o = np.asarray(obs, dtype=np.float64)[:, :45]
    want = {"base_ang_vel": ang_vel_b, "projected_gravity": projected_gravity(quat_wxyz), "velocity_commands": np.asarray(command)[:, :3],
            "joint_pos_rel": np.asarray(joint_pos) - np.asarray(default_joint_pos), "joint_vel_rel": joint_vel, "last_action": last_action}
    errs = {name: float(np.abs(o[:, a:b] - np.asarray(want[name], dtype=np.float64)).max()) for name, (a, b) in SLICES.items()}
    return {"max_abs_err": errs, "atol": atol, "passed": all(e <= atol for e in errs.values()), "n": int(o.shape[0])}


def kit_probe(nav, rpy=TILT_RPY) -> dict:
    """Kit 안에서만. 몸통을 rpy 로 기울여 쓰고 영 행동으로 한 스텝 돌려, 관측 45 칸을 같은 시점 상태와 견준다. 실패해도 예외 대신 {"error": ...} (본 확인을 막지 않는다)."""
    import torch

    from foothold_s2.lab_compat import quat_to_sim, quat_wxyz, th

    try:
        nav.reset()
        raw, robot = nav.raw, nav.raw.scene["robot"]
        pose = th(robot.data.root_link_pose_w).clone()
        q = torch.as_tensor(quat_wxyz_from_rpy(*rpy), dtype=pose.dtype, device=pose.device).expand(pose.shape[0], 4)
        pose[:, 3:7] = quat_to_sim(q)
        robot.write_root_pose_to_sim(pose, env_ids=torch.arange(pose.shape[0], device=pose.device))
        obs, _r, _d, _e = nav.env.step(torch.zeros(nav.n, 12, device=pose.device))
        policy = obs["policy"] if not hasattr(obs, "shape") else obs
        d = robot.data
        n = lambda x: th(x).detach().cpu().numpy().astype(np.float64)
        jp, jd = n(d.joint_pos), n(d.default_joint_pos)
        res = compare_obs(policy.detach().cpu().numpy(), quat_wxyz=n(quat_wxyz(d.root_quat_w)), ang_vel_b=n(d.root_ang_vel_b),
                          command=nav.term.vel_command_b.detach().cpu().numpy(), joint_pos=jp, default_joint_pos=jd,
                          joint_vel=n(d.joint_vel), last_action=np.zeros_like(jp))
        names = list(getattr(d, "joint_names", None) or robot.joint_names)
        res["joint_names"] = names
        res["joint_order_ok"] = names == list(JOINT_NAMES_232)                 # 관측 joint_pos_rel · joint_vel_rel · last_action · 행동 12 칸이 이 순서에 걸려 있다
        res["passed"] = bool(res["passed"] and res["joint_order_ok"])
        res["tilt_rpy"] = list(rpy)
        res["written_quat_sim"] = [float(v) for v in n(quat_to_sim(q))[0]]
        return res
    except BaseException as exc:                                     # noqa: BLE001 (Kit 오류가 본 확인을 가리지 않게: 이유만 남긴다)
        return {"error": f"{type(exc).__name__}: {exc}"[:400], "passed": False}


# ---------------------------------------------------------------- 깊이 카메라 방향 (reviewer 13:38 조건 1)
def rotate_wxyz(q_wxyz, v) -> np.ndarray:
    """wxyz 쿼터니언 (4,) 로 v (3,) 를 돌린다."""
    w, x, y, z = (float(c) for c in q_wxyz)
    u = np.array([x, y, z]); v = np.asarray(v, dtype=np.float64)
    t = 2.0 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def cfg_rot_to_wxyz(rot, major: int):
    """cfg 의 OffsetCfg.rot 튜플 (이 판이 받는 순서) -> wxyz."""
    return (rot[3], rot[0], rot[1], rot[2]) if major >= 3 else tuple(rot)


def expected_center_depth(base_pos, base_quat_wxyz, ground_z: float, cam_pos_b, cam_rot_wxyz) -> float:
    """몸통 자세에서 카메라 중심 화소가 지면 평면 (z = ground_z) 을 보는 distance_to_image_plane [m] (= 중심 광선이 앞축이라 광선 길이). 지면을 안 보면 None.
    cam_rot_wxyz = 몸 틀에서 카메라 틀로 (앞축 +x · convention world)."""
    fwd_b = rotate_wxyz(cam_rot_wxyz, (1.0, 0.0, 0.0))
    fwd = rotate_wxyz(base_quat_wxyz, fwd_b)
    pos = np.asarray(base_pos, dtype=np.float64) + rotate_wxyz(base_quat_wxyz, cam_pos_b)
    if fwd[2] >= -1e-6:
        return None
    return float((ground_z - pos[2]) / fwd[2])


def kit_camera_probe(nav, depth_fn, ground_z_fn, tol: float = 0.05) -> dict:
    """Kit 안에서만. 몸통이 서 있는 자세에서 한 스텝 뒤 깊이 카메라 중심 화소 (90 · 160) 대 계산한 지면 거리를 env 마다 견준다. 맞은 env 비율이 절반 이상이면 통과 (방 바닥이 평평하지 않은 칸은 틀릴 수 있어 전부는 요구 안 함).
    ground_z_fn(env_index) -> 그 env 의 바닥 높이 (부르는 쪽이 env 원점 높이로 준다)."""
    import torch

    from foothold_s2.lab_compat import lab_major, quat_wxyz, th
    from foothold_s2.nav import hl_student

    try:
        nav.reset()
        nav.env.step(torch.zeros(nav.n, 12, device=nav.raw.device))
        nav.env.step(torch.zeros(nav.n, 12, device=nav.raw.device))
        d = nav.raw.scene["robot"].data
        pos = th(d.root_pos_w).detach().cpu().numpy().astype(np.float64)
        quat = th(quat_wxyz(d.root_quat_w)).detach().cpu().numpy().astype(np.float64)
        depth = th(depth_fn()).detach().cpu().numpy().astype(np.float64).reshape(pos.shape[0], hl_student.DEPTH_H, hl_student.DEPTH_W)
        rot = cfg_rot_to_wxyz(hl_student_cfg_rot(), lab_major())
        got, want = depth[:, hl_student.DEPTH_H // 2, hl_student.DEPTH_W // 2], []
        for i in range(pos.shape[0]):
            want.append(expected_center_depth(pos[i], quat[i], ground_z_fn(i), hl_student.CAMERA_POS_M, rot))
        want = np.array([np.nan if w is None else w for w in want])
        rel = np.abs(got - want) / want
        good = float(np.nanmean(rel <= tol))
        return {"passed": bool(good >= 0.5), "fraction_within_tol": good, "tol": tol, "median_got_m": float(np.nanmedian(got)),
                "median_want_m": float(np.nanmedian(want)), "pitch_deg": hl_student.CAMERA_PITCH_DEG}
    except BaseException as exc:                                     # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"[:400], "passed": False}


def hl_student_cfg_rot():
    from foothold_s2.lab_compat import quat_cfg
    from foothold_s2.nav import hl_student

    return quat_cfg(hl_student.pitch_down_quat_wxyz(hl_student.CAMERA_PITCH_DEG))
