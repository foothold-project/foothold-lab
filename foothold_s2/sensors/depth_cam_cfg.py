"""D435i 시뮬 카메라 cfg (11 §6). Isaac Lab 2.3.2 `RayCasterCameraCfg` · `PinholeCameraPatternCfg`.

상수와 기하(광선 각 · 광축이 바닥에 닿는 거리)는 Kit 없이 CPU 로 시험하고(11 §7 L0), cfg 객체는 Kit 안에서만 만든다.

단일 결합 Mesh 제약(VERIFY-astra-final 1): 설치 `RayCaster` 는 mesh_prim_paths 를 하나만 받고(ray_caster.py 164~166 행),
그 아래 Plane 이 있으면 Plane 을, 아니면 첫 Mesh 자식만 읽는다(177 · 183 행). 지형 생성기는 패치를 하나의 메시로 합치므로
(terrain_generator.py 166 행) `/World/ground` 하나를 가리키고 그 아래 ground plane · 별도 Mesh 를 두지 않는다.
"""

from __future__ import annotations

import math

# 11 §2 (전부 가정 · SPEC 2.2~2.4 절)
WIDTH = HEIGHT = 60
FX, FY, CX, CY = 55.9, 54.1, 30.0, 30.0
INTRINSIC = [FX, 0.0, CX, 0.0, FY, CY, 0.0, 0.0, 1.0]
OFFSET_POS = (0.25, 0.0, 0.12)  # base 기준
PITCH_DEG = 35.0  # 아래로 35° (팀장 승인 J-C)
# world 규약(x 앞 · z 위) 에서 +y 축으로 +35° 돌린 쿼터니언 (w, x, y, z). 11 §6 의 (0.9537, 0, 0.3007, 0)
OFFSET_ROT = (math.cos(math.radians(PITCH_DEG) / 2), 0.0, math.sin(math.radians(PITCH_DEG) / 2), 0.0)
UPDATE_PERIOD = 0.1  # 10 Hz
MESH_PRIM_PATHS = ["/World/ground"]


def quat_rotate(q, v):
    """(w, x, y, z) 쿼터니언으로 3 벡터를 돌린다 (Kit 없이 기하 시험용)."""
    w, x, y, z = q
    vx, vy, vz = v
    # t = 2 * cross(q.xyz, v)
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def edge_ray_angles_deg() -> tuple[float, float]:
    """가장자리 화소 중심까지가 아니라 영상 끝(0 · 60)까지의 반각: 가로 · 세로."""
    return math.degrees(math.atan(CX / FX)), math.degrees(math.atan(CY / FY))


def ground_hit_x(base_height: float, extra_pitch_deg: float = 0.0, q=OFFSET_ROT) -> float | None:
    """카메라 광축(world 규약 +x)을 extra_pitch 만큼 더 숙여 평지 z = 0 에 닿는 base 기준 x. 안 닿으면 None."""
    a = math.radians(extra_pitch_deg)
    d = quat_rotate(q, (math.cos(a), 0.0, -math.sin(a)))
    z0 = base_height + OFFSET_POS[2]
    if d[2] >= 0:
        return None
    return OFFSET_POS[0] + z0 / -d[2] * d[0]


def make_depth_camera_cfg(prim_path: str = "{ENV_REGEX_NS}/Robot/base"):
    """Kit 안에서만 부른다."""
    from isaaclab.sensors import RayCasterCameraCfg
    from isaaclab.sensors.ray_caster.patterns import PinholeCameraPatternCfg

    return RayCasterCameraCfg(
        prim_path=prim_path,
        mesh_prim_paths=list(MESH_PRIM_PATHS),
        update_period=UPDATE_PERIOD,
        offset=RayCasterCameraCfg.OffsetCfg(pos=OFFSET_POS, rot=OFFSET_ROT, convention="world"),
        data_types=["distance_to_image_plane"],
        depth_clipping_behavior="none",  # 미검출은 inf -> normalize 에서 1.0
        pattern_cfg=PinholeCameraPatternCfg.from_intrinsic_matrix(INTRINSIC, WIDTH, HEIGHT),
        debug_vis=False,
    )
