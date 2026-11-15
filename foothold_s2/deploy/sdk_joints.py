"""Go2 SDK 모터 번호와 Isaac 관절 순서 (unitree_rl_lab `unitree.py` 의 joint_sdk_names, unitree_mujoco 모터 번호와 같음).

SDK 순서: FR(hip thigh calf) FL RR RL. Isaac 순서는 env 가 알려 준다(`deploy.yaml` 의 joint_names_isaac).
"""

import numpy as np

SDK_JOINT_NAMES = (
    "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
    "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
    "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
    "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint",
)


def permutation(isaac_names, sdk_names=SDK_JOINT_NAMES):
    """`isaac_vec[perm_to_isaac] ` 가 아니라 이름으로 만든 두 순열.

    sdk_to_isaac[i] = SDK 모터 i 의 값이 들어갈 Isaac 인덱스. isaac_to_sdk[j] = Isaac 인덱스 j 가 SDK 의 몇 번째인가.
    """
    isaac_names = list(isaac_names)
    sdk_names = list(sdk_names)

    if sorted(isaac_names) != sorted(sdk_names):
        raise ValueError("관절 이름 집합이 다르다: %r vs %r" % (sorted(isaac_names), sorted(sdk_names)))

    sdk_to_isaac = np.array([isaac_names.index(n) for n in sdk_names])
    isaac_to_sdk = np.array([sdk_names.index(n) for n in isaac_names])

    return sdk_to_isaac, isaac_to_sdk


def sdk_vec_to_isaac(sdk_vec, isaac_names, sdk_names=SDK_JOINT_NAMES):
    """SDK 순서 (..., 12) -> Isaac 순서."""
    _, isaac_to_sdk = permutation(isaac_names, sdk_names)

    return np.asarray(sdk_vec)[..., isaac_to_sdk]


def isaac_vec_to_sdk(isaac_vec, isaac_names, sdk_names=SDK_JOINT_NAMES):
    """Isaac 순서 (..., 12) -> SDK 순서."""
    sdk_to_isaac, _ = permutation(isaac_names, sdk_names)

    return np.asarray(isaac_vec)[..., sdk_to_isaac]
