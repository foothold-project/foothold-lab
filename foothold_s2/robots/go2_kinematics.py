"""Go2 URDF의 3-DOF 다리 FK. NumPy만 사용하며 Kit를 기동하지 않는다.

근거: MGDP all_dog/go2/urdf/go2.urdf 및 robot_lab resources/go2/urdf/go2.urdf.
축 x/y/y, hip 원점 (+-0.1934, +-0.0465, 0), 옆 링크 0.0955,
thigh/calf 0.213, foot collision sphere offset (-0.002, 0, 0), radius 0.022.
기본 관절값은 Isaac Lab unitree.py UNITREE_GO2_CFG. 실행 시 default_joint_pos와 대조한다.
"""
import numpy as np
import re

LEGS = ('FL', 'FR', 'RL', 'RR')
JOINT_NAMES = tuple(f'{leg}_{part}_joint' for leg in LEGS for part in ('hip', 'thigh', 'calf'))
DEFAULT_JOINT_POS = ((.1, .8, -1.5), (-.1, .8, -1.5), (.1, 1., -1.5), (-.1, 1., -1.5))
FOOT_RADIUS_M = .022
DEFAULT_ROOT_HEIGHT_M = .4


def foot_centers(joint_pos=DEFAULT_JOINT_POS):
    """FL, FR, RL, RR의 충돌 구 중심을 base 좌표로 반환한다."""
    q = np.asarray(joint_pos, dtype=float)
    if q.shape != (4, 3) or not np.all(np.isfinite(q)):
        raise ValueError('Go2 FK에는 유한한 4 x 3 관절값이 필요합니다')
    result = []
    for i, (hip, thigh, calf) in enumerate(q):
        side = 1. if i % 2 == 0 else -1.
        front = 1. if i < 2 else -1.
        x = -.213*np.sin(thigh) - .213*np.sin(thigh+calf) - .002*np.cos(thigh+calf)
        z = -.213*np.cos(thigh) - .213*np.cos(thigh+calf) + .002*np.sin(thigh+calf)
        y = side*.0955
        result.append([front*.1934+x, side*.0465+y*np.cos(hip)-z*np.sin(hip),
                       y*np.sin(hip)+z*np.cos(hip)])
    return np.asarray(result)


def validate_default_pose(joint_names, joint_pos):
    """지원하는 기본 자세가 바뀌면 옛 FK로 평가하지 않고 실행을 중단한다."""
    order = [list(joint_names).index(name) for name in JOINT_NAMES]
    actual = np.asarray(joint_pos)[..., order]
    if not np.allclose(actual, np.asarray(DEFAULT_JOINT_POS).reshape(12), atol=1e-6, rtol=0):
        raise ValueError('default_joint_pos가 FK 기준과 다릅니다. 시작점 재계산 필요')


def root_height_from_cfg(robot_cfg):
    state = robot_cfg.init_state
    joints = []
    for name in JOINT_NAMES:
        matches = [value for expr, value in state.joint_pos.items() if re.fullmatch(expr, name)]
        if len(matches) != 1:
            raise ValueError('FK 기본 자세의 관절 정규식이 모호합니다: '+name)
        joints.append(matches[0])
    validate_default_pose(JOINT_NAMES, joints)
    if not np.allclose(state.pos[:2], 0.) or not np.allclose(state.rot, (1., 0., 0., 0.)):
        raise ValueError('FK는 기본 root x/y=0 및 단위 quaternion만 지원합니다')
    return float(state.pos[2])
