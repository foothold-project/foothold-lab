"""Unitree RL Mjlab Go2 속도 정책 (ONNX) 을 MuJoCo에서 돌린다.

정책: Hugging Face `diasAiMaster/unitree-go2-velocity-flat`
프레임워크: unitree_rl_mjlab (MuJoCo Warp) · 태스크 Unitree-Go2-Flat
관측 45차원. gait_phase 없음. action scale 0.5.
deploy.yaml 의 joint_ids_map 으로 MuJoCo FL-FR-RL-RR 과 정책 FR-FL-RR-RL 을 맞춘다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parent
POLICY_DIR = ROOT / "vendor" / "unitree_go2_policy"

JOINT_IDS_MAP = np.array([3, 4, 5, 0, 1, 2, 9, 10, 11, 6, 7, 8], dtype=np.int64)
DEFAULT_POS_POLICY = np.array(
    [-0.1, 0.9, -1.8, 0.1, 0.9, -1.8, -0.1, 0.9, -1.8, 0.1, 0.9, -1.8],
    dtype=np.float64,
)
KP_POLICY = np.array([20, 20, 40, 20, 20, 40, 20, 20, 40, 20, 20, 40], dtype=np.float64)
KD_POLICY = np.array([1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 2], dtype=np.float64)
ACTION_SCALE = 0.5


def gravity_body(quat_wxyz: np.ndarray) -> np.ndarray:
    w, x, y, z = quat_wxyz
    return np.array(
        [
            2 * (-z * x + w * y),
            -2 * (z * y + w * x),
            1 - 2 * (w * w + z * z),
        ],
        dtype=np.float64,
    )


def to_policy(mj: np.ndarray) -> np.ndarray:
    out = np.empty(12, dtype=np.float64)
    out[:] = mj[JOINT_IDS_MAP]
    return out


def from_policy(pol: np.ndarray) -> np.ndarray:
    out = np.empty(12, dtype=np.float64)
    out[JOINT_IDS_MAP] = pol
    return out


class Go2MjlabPolicy:
    def __init__(self) -> None:
        onnx_path = str(POLICY_DIR / "policy.onnx")
        self.sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        self.obs_name = self.sess.get_inputs()[0].name
        self.last_action = np.zeros(12, dtype=np.float64)
        self.kp_mj = from_policy(KP_POLICY)
        self.kd_mj = from_policy(KD_POLICY)
        self.default_mj = from_policy(DEFAULT_POS_POLICY)

    def reset(self) -> None:
        self.last_action[:] = 0.0

    def act(self, data, cmd: np.ndarray) -> np.ndarray:
        qj_mj = np.array(data.qpos[7:19], dtype=np.float64)
        dqj_mj = np.array(data.qvel[6:18], dtype=np.float64)
        quat = np.array(data.qpos[3:7], dtype=np.float64)
        omega = np.array(data.qvel[3:6], dtype=np.float64)
        qj = to_policy(qj_mj) - DEFAULT_POS_POLICY
        dqj = to_policy(dqj_mj)
        obs = np.concatenate(
            [
                omega,
                gravity_body(quat),
                cmd,
                qj,
                dqj,
                self.last_action,
            ]
        ).astype(np.float32)
        action = self.sess.run(None, {self.obs_name: obs.reshape(1, 45)})[0].reshape(12)
        action = np.clip(action, -100.0, 100.0)
        self.last_action = action.astype(np.float64)
        target_pol = action * ACTION_SCALE + DEFAULT_POS_POLICY
        return from_policy(target_pol)

    def torque(self, data, target_mj: np.ndarray) -> np.ndarray:
        q = np.array(data.qpos[7:19], dtype=np.float64)
        dq = np.array(data.qvel[6:18], dtype=np.float64)
        return (target_mj - q) * self.kp_mj + (0.0 - dq) * self.kd_mj
