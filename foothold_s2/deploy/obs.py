"""S1-blind 관측 조립 (Isaac 과 같은 순서 · 스케일). numpy 만 쓴다.

Isaac 정책 그룹: 항마다 11 스텝 이력을 «항 단위로» 평탄화해 이어 붙인다(오래된 것 먼저, 최신이 마지막).
항 순서: base_ang_vel(3) projected_gravity(3) velocity_commands(3) joint_pos_rel(12) joint_vel_rel(12) last_action(12).
리셋 직후에는 이력 전체가 첫 관측으로 채워진다(기록으로 확인, test_deploy_obs.py).
"""

import numpy as np

HISTORY = 11
DIMS = (3, 3, 3, 12, 12, 12)


def projected_gravity(quat_wxyz):
    """몸 틀에서 본 중력 방향(단위): R^T [0, 0, -1]. quat 는 (w, x, y, z), 몸 -> 세계 회전."""
    w, x, y, z = (float(v) for v in quat_wxyz)
    gx = -(2.0 * (x * z - w * y))
    gy = -(2.0 * (y * z + w * x))
    gz = -(1.0 - 2.0 * (x * x + y * y))

    return np.array([gx, gy, gz], dtype=np.float32)


class ObsAssembler:
    """한 로봇의 관측 조립기. 모든 관절 벡터는 «Isaac 순서» (호출 쪽 어댑터가 SDK 순서에서 바꿔서 넘긴다)."""

    def __init__(self, default_q_isaac, history=HISTORY):
        self.default_q = np.asarray(default_q_isaac, dtype=np.float32)
        self.history = history
        self.buf = None

    def _frame(self, q, dq, quat_wxyz, gyro_b, cmd, last_action):
        return [
            np.asarray(gyro_b, dtype=np.float32),
            projected_gravity(quat_wxyz),
            np.asarray(cmd, dtype=np.float32),
            np.asarray(q, dtype=np.float32) - self.default_q,
            np.asarray(dq, dtype=np.float32),
            np.asarray(last_action, dtype=np.float32),
        ]

    def reset(self):
        self.buf = None

    def step(self, q, dq, quat_wxyz, gyro_b, cmd, last_action):
        """한 제어 스텝(50 Hz)의 관측 (history x 45 = 495). 첫 호출(또는 reset 뒤)은 이력을 현재 값으로 채운다."""
        frame = self._frame(q, dq, quat_wxyz, gyro_b, cmd, last_action)

        if self.buf is None:
            self.buf = [np.repeat(f[None, :], self.history, axis=0) for f in frame]
        else:
            self.buf = [np.concatenate([b[1:], f[None, :]], axis=0) for b, f in zip(self.buf, frame)]

        return np.concatenate([b.reshape(-1) for b in self.buf]).astype(np.float32)
