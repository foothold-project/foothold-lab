"""Go2 관절 모델 (17 §1). Kit 안에서만 불린다. 숫자는 `go2_params.py`.

hip · thigh 는 Isaac Lab Go2 값 그대로, 종아리만 URDF 값(45.43 N·m · 15.70 rad/s). `velocity_limit_sim` 은 두지 않는다.
"""

from isaaclab.actuators import DCMotorCfg
from isaaclab_assets.robots.unitree import UNITREE_GO2_CFG

from foothold_s2.robots import go2_params as gp

GO2_S1_CFG = UNITREE_GO2_CFG.replace(
    actuators={
        "hip_thigh": DCMotorCfg(joint_names_expr=gp.HIP_THIGH_JOINTS, **gp.HIP_THIGH),
        "calf": DCMotorCfg(joint_names_expr=gp.CALF_JOINTS, **gp.CALF),
    }
)
