"""Go2 모델 숫자 (17-GO2-MODEL). Kit 없이 읽고 시험한다. 실제 cfg 는 `go2_cfg.py`.

종아리만 따로 떼어 URDF 값으로 둔다(팀장 승인 F-D2): 토크 45.43 N·m · 속도 15.70 rad/s.
hip · thigh 는 Isaac Lab Go2 값 그대로(23.5 · 30.0). Kp 25 · Kd 0.5 는 모두 같다.
`velocity_limit_sim`(PhysX 상한)은 적용하지 않는다: DCMotor 곡선이 15.70 을 넘는 속도에서 추진 토크를
음수로 만들어 물리적으로 제동한다 (17 §1 동결값, 가정).
"""

import math

import torch

HIP_THIGH_JOINTS = [".*_hip_joint", ".*_thigh_joint"]
CALF_JOINTS = [".*_calf_joint"]

HIP_THIGH = dict(effort_limit=23.5, saturation_effort=23.5, velocity_limit=30.0,
                 stiffness=25.0, damping=0.5, friction=0.0)
CALF = dict(effort_limit=45.43, saturation_effort=45.43, velocity_limit=15.70,
            stiffness=25.0, damping=0.5, friction=0.0)

# 도메인 무작위화 (17 §5, PIE Table II 위임). 값은 (하한, 상한).
PIE = {
    "base_mass_add_kg": (-1.0, 2.0),
    "gain_scale": (0.9, 1.1),            # Kp · Kd 배율. 모터 세기 배율(0.9~1.1)은 따로 구현하지 않음(열린 항목)
    "com_shift_m": (-0.05, 0.05),
    "friction": (0.2, 1.2),
    "reset_joint_scale": (1.0, 1.0),     # 초기 관절 0.5~1.5 의 단위가 열린 항목이라 Isaac Lab 기본(1.0, 1.0) 유지
}

# 시스템 지연 0~15 ms 는 DCMotor 를 DelayedPD 로 바꿔야 해서 S1 1 차에 넣지 않았다 (열린 항목, 보고에 적음).

TERMINATION = {"max_tilt_rad": 1.5, "foot_below_ground_m": 0.25}   # 17 §7 (가정) 문턱 0.2 -> 0.25: 계단 단 최대 0.23 + 0.02 (lead 10/21, fbg2 측정에서 계단 레벨 9 오판 56 건)


def dc_motor_clip(effort, joint_vel, effort_limit, saturation_effort, velocity_limit):
    """DCMotor 의 토크 한계 곡선 (설치 `actuator_pd.py` `_clip_effort` 와 같은 식).

    상한 = min(effort_limit, saturation x (1 - qd / vlim)), 하한 = max(-effort_limit, saturation x (-1 - qd / vlim)).
    속도는 먼저 +- vlim x (1 + effort_limit / saturation) 로 자른다.
    """
    effort = torch.as_tensor(effort, dtype=torch.float32)
    qd = torch.as_tensor(joint_vel, dtype=torch.float32)
    vel_at_effort_lim = velocity_limit * (1.0 + effort_limit / saturation_effort)
    qd = torch.clip(qd, min=-vel_at_effort_lim, max=vel_at_effort_lim)
    top = saturation_effort * (1.0 - qd / velocity_limit)
    bottom = saturation_effort * (-1.0 - qd / velocity_limit)
    max_effort = torch.clip(top, max=effort_limit)
    min_effort = torch.clip(bottom, min=-effort_limit)

    return torch.clip(effort, min=min_effort, max=max_effort)


def calf_clip(effort, joint_vel):
    return dc_motor_clip(effort, joint_vel, CALF["effort_limit"], CALF["saturation_effort"],
                         CALF["velocity_limit"])


# URDF 에서 읽은 비율(17 §1): 종아리 / hip 토크 = 45.43 / 23.7 = 1.92, 속도 30.1 / 15.70 = 1.92
URDF_RATIO = (45.43 / 23.7, 30.1 / 15.70)
assert math.isclose(URDF_RATIO[0], URDF_RATIO[1], rel_tol=0.01)
