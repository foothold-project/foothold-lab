"""START 축 3 짧은 명령의 시작점. lead 결정 10/20, CPU 순수 계산."""

from functools import lru_cache

import numpy as np

from foothold_s2.robots import go2_kinematics as fk

FOOT_EDGE_MARGIN_M = .05  # lead 가정 10/21 N1e: 발 구 가장자리에서 5 cm
YAW_STEP_DEG = 15
MAX_SUPPORT_HEIGHT_SPREAD_M = .03  # lead 가정 10/21 N1d
MIN_SOLE_CLEARANCE_M = .01        # lead 결정 10/21 N1d 선택 2

KINDS = {
    "stepping_stones_start": "stepping_stones_high",  # lead 결정 10/20: high만
    "balance_beams": "balance_beams",
    "stepping_beams": "stepping_beams",
    "gaps_start": "gaps",
}
ZONE = ((1.0, 7.0), (2.0, 6.0))
BODY_MARGIN_M = 0.3               # lead 가정
MAX_BACK_REFERENCE_M = 0.6        # lead 정정 10/20: 뒤 칸만. 관측 옆 속도는 자르지 않는다.
EPS = 1.e-8


def rotate_xy(xy, yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    return np.asarray(xy) @ np.array([[c, s], [-s, c]])


def _window(cmd, zone=ZONE, yaw=0.):
    velocity = np.asarray(cmd[:2], dtype=float)
    if not np.all(np.isfinite(velocity)):
        raise ValueError("유한한 명령만 허용")
    distance = float(np.linalg.norm(velocity) * 2.)
    if distance <= EPS or (velocity[0] < 0 and distance > MAX_BACK_REFERENCE_M + EPS):
        return None, distance
    displacement = rotate_xy(velocity / np.linalg.norm(velocity) * (distance + BODY_MARGIN_M), yaw)
    zone = np.array(zone)
    # 직사각형은 볼록이므로 시작과 여유 끝점이 안이면 선분 전체가 안이다.
    low = zone[:, 0] + np.maximum(-displacement, 0.)
    high = zone[:, 1] - np.maximum(displacement, 0.)
    return (low, high), distance


def _previous_start(boxes, cmd, zone=ZONE):
    """지지 패치와 방향별 허용 영역의 교집합에서 (4,4)에 가장 가까운 점."""
    window, distance = _window(cmd, zone)
    base = dict(reference_m=distance, margin_m=BODY_MARGIN_M, eligible=False,
                status="no_start", label="시작점 없음 · 판정 제외", origin=None)
    if window is None:
        return dict(base, reason="reference_over_0.6" if distance > MAX_BACK_REFERENCE_M else "zero_reference")
    low, high = window
    candidates = []
    for x0, x1, y0, y1, _, z1 in boxes:
        lo = np.maximum(low, [x0 + EPS, y0 + EPS])
        hi = np.minimum(high, [x1 - EPS, y1 - EPS])
        if np.any(lo > hi):
            continue
        xy = np.clip([4., 4.], lo, hi)
        candidates.append((float(np.sum((xy - 4.) ** 2)), -z1, float(xy[0]), float(xy[1])))
    if not candidates:
        return dict(base, reason="no_supported_patch")
    _, neg_z, x, y = min(candidates)
    return dict(base, status="ready", label="시작점 확인", origin=[x, y, -neg_z],
                eligible=True, reason="")


def merge_support_boxes(boxes):
    """같은 높이에서 완전한 변을 공유하는 사각형만 합친다. 구멍은 메우지 않는다."""
    rows = [list(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        for axis in (0, 2):
            other = 2 - axis
            groups = {}
            for row in rows:
                key = tuple(round(row[k], 7) for k in (other, other+1, 5))
                groups.setdefault(key, []).append(row)
            merged = []
            for group in groups.values():
                group.sort(key=lambda b: b[axis])
                current = group[0].copy()
                for row in group[1:]:
                    if row[axis] <= current[axis+1] + EPS:
                        current[axis+1] = max(current[axis+1], row[axis+1])
                        current[4] = min(current[4], row[4])
                        changed = True
                    else:
                        merged.append(current)
                        current = row.copy()
                merged.append(current)
            rows = merged
    return np.asarray(rows, dtype=float).reshape(-1, 6)


def _safe_rects(boxes):
    boxes = merge_support_boxes(boxes)
    inset = fk.FOOT_RADIUS_M + FOOT_EDGE_MARGIN_M
    low = boxes[:, [0, 2]] + inset
    high = boxes[:, [1, 3]] - inset
    keep = np.all(low <= high + EPS, axis=1)
    return boxes[keep], low[keep], high[keep]


def valid_start(origin, boxes, cmd, zone=ZONE, *, feet=None, yaw=0.):
    window, _ = _window(cmd, zone, yaw)
    if window is None:
        return False
    xy = np.asarray(origin[:2])
    if not np.all((xy >= window[0]-EPS) & (xy <= window[1]+EPS)):
        return False
    patches, low, high = _safe_rects(boxes)
    foot_xy = rotate_xy((fk.foot_centers() if feet is None else np.asarray(feet))[:, :2], yaw) + xy
    heights = _support_heights(foot_xy, patches, low, high)
    return heights is not None and np.ptp(heights) <= MAX_SUPPORT_HEIGHT_SPREAD_M + EPS


def _support_heights(foot_xy, patches, lows, highs):
    heights = []
    for point in foot_xy:
        ok = np.all((point >= lows-EPS) & (point <= highs+EPS), axis=1)
        if not ok.any():
            return None
        heights.append(float(patches[ok, 5].max()))
    return np.asarray(heights)


def root_height_for_supports(heights, foot_center_z):
    """네 발 모두 구 바닥 간격 >= 1 cm. 가장 작은 간격은 정확히 1 cm다."""
    heights, foot_center_z = np.asarray(heights), np.asarray(foot_center_z)
    if heights.shape != (4,) or foot_center_z.shape != (4,) or not (
            np.isfinite(heights).all() and np.isfinite(foot_center_z).all()):
        raise ValueError('높이 계산에는 네 지지면과 네 발 중심의 유한한 z가 필요합니다')
    return float(np.max(heights - foot_center_z + fk.FOOT_RADIUS_M) + MIN_SOLE_CLEARANCE_M)


def _foot_edge_distances(foot_xy, heights, patches, lows, highs):
    """선택된 높이의 지지 사각형 경계까지 중심 거리. 겹치면 가장 넓은 여유를 쓴다.

    coplanar 전체 변은 이미 합쳤다. 비직사각형 합집합은 확장하지 않으므로 보수적인 거리다.
    """
    distances = []
    for point, height in zip(foot_xy, heights):
        ok = (np.all((point >= lows-EPS) & (point <= highs+EPS), axis=1)
              & (np.abs(patches[:, 5]-height) <= EPS))
        supports = patches[ok]
        to_edges = np.column_stack((point[0]-supports[:, 0], supports[:, 1]-point[0],
                                    point[1]-supports[:, 2], supports[:, 3]-point[1]))
        distances.append(float(to_edges.min(axis=1).max()))
    return np.asarray(distances)


def select_start(boxes, cmd, zone=ZONE, *, feet=None, terrain_origin_z=0., root_height_m=fk.DEFAULT_ROOT_HEIGHT_M):
    """24개 yaw마다 네 발의 허용 root 사각형을 정확히 교차한다. 위치 격자는 쓰지 않는다.

    몸 원점이 발판 위일 필요는 없다. 지지면 높이 차 <= 3 cm인 후보만 선택한다.
    root 높이는 네 발 구 바닥의 최소 간격이 1 cm가 되게 정한다. 실제 접촉 보장은 아니다.
    """
    previous = _previous_start(boxes, cmd, zone)
    feet = fk.foot_centers() if feet is None else np.asarray(feet, dtype=float)
    if feet.shape != (4, 3) or not np.all(np.isfinite(feet)):
        raise ValueError('네 발의 유한한 FK 좌표가 필요합니다')
    root_z = previous['origin'][2] if previous['origin'] is not None else float(terrain_origin_z)
    base = dict(previous, status='no_start', label='시작점 없음 · 판정 제외', origin=None,
                eligible=False, previous_origin=previous['origin'], previous_status=previous['status'],
                previous_reason=previous['reason'], yaw_rad=None, feet_body=feet.tolist(),
                foot_radius_m=fk.FOOT_RADIUS_M, foot_edge_margin_m=FOOT_EDGE_MARGIN_M,
                foot_order=list(fk.LEGS),
                yaw_step_deg=YAW_STEP_DEG, height_rule='max(support_z - FK_foot_z + radius) + 0.01',
                max_support_height_spread_m=MAX_SUPPORT_HEIGHT_SPREAD_M,
                min_sole_clearance_m=MIN_SOLE_CLEARANCE_M,
                reset_joint_jitter=False, reset_pose_jitter=False,
                comparison_note='N1e 뒤·옆: 기본 관절 고정, 높이차 3 cm 이하, 발 구 바닥 최소 여유 1 cm, 발 구 가장자리 여유 5 cm',
                root_height_m=root_height_m, terrain_origin_z=None, previous_terrain_origin_z=root_z,
                xy_only_candidate=None,
                default_joint_pos=[list(v) for v in fk.DEFAULT_JOINT_POS])
    if previous['reason'] in ('reference_over_0.6', 'zero_reference'):
        return base
    patches, lows, highs = _safe_rects(boxes)
    best = best_xy = None
    min_spread = float('inf')
    for angle in range(0, 360, YAW_STEP_DEG):
        yaw = float(np.deg2rad(angle))
        window, _ = _window(cmd, zone, yaw)
        offsets = rotate_xy(feet[:, :2], yaw)
        # (root low, root high), initially the motion-safe zone. Intersect each foot's patch union.
        regions = [(window[0], window[1])]
        for offset in offsets:
            new = []
            for low, high in regions:
                lo = np.maximum(low, lows-offset)
                hi = np.minimum(high, highs-offset)
                ok = np.all(lo <= hi+EPS, axis=1)
                new.extend(zip(lo[ok], hi[ok]))
            regions = new
            if not regions:
                break
        for low, high in regions:
            xy = np.clip([4., 4.], low, high)
            heights = _support_heights(xy+offsets, patches, lows, highs)
            if heights is None:
                continue
            spread = float(np.ptp(heights))
            min_spread = min(min_spread, spread)
            key = (round(float(np.sum((xy-4.)**2)), 12), angle, float(xy[0]), float(xy[1]))
            candidate = (key, xy, yaw, offsets, heights)
            if best_xy is None or key < best_xy[0]:
                best_xy = candidate
            if spread > MAX_SUPPORT_HEIGHT_SPREAD_M + EPS:
                continue
            if best is None or key < best[0]:
                best = candidate

    def pose_record(candidate, spawn_z):
        _, xy, yaw, offsets, heights = candidate
        world = np.column_stack((xy+offsets, feet[:, 2]+spawn_z))
        edge_distances = _foot_edge_distances(world[:, :2], heights, patches, lows, highs)
        return dict(origin=[float(xy[0]), float(xy[1]), float(root_z)], yaw_rad=yaw,
                    feet_world=world.tolist(), support_heights_m=heights.tolist(),
                    foot_center_edge_distances_m=edge_distances.tolist(),
                    foot_edge_clearances_m=(edge_distances-fk.FOOT_RADIUS_M).tolist(),
                    support_height_spread_m=float(np.ptp(heights)),
                    foot_air_gaps_m=(world[:, 2]-heights).tolist(),
                    sole_air_gaps_m=(world[:, 2]-heights-fk.FOOT_RADIUS_M).tolist())

    if best_xy is not None:
        # 현재 XY 여유의 최근접 후보에 옛 root 높이를 적용한 비교 기록. 실행용 fallback이 아니다.
        base['xy_only_candidate'] = dict(pose_record(best_xy, root_z+root_height_m), eligible=False, status='record_only')
        base['minimum_candidate_height_spread_m'] = min_spread
    if best is None:
        return dict(base, reason='support_height_spread_exceeded' if best_xy is not None else 'no_four_foot_support')
    spawn_z = float(root_height_for_supports(best[4], feet[:, 2]))
    # 지형 원점 z는 보존한다. 로봇 reset의 z 오프셋만 조절해 지형 기준을 바꾸지 않는다.
    offset_z = float(spawn_z - float(root_z) - float(root_height_m))   # numpy float64 가 pose_range 에 섞이면 torch 가 double 로 만들어 reset 이 죽는다 (Kit 예행에서 확인)
    base.update(pose_record(best, spawn_z))
    return dict(base, status='ready', label='네 발 XY·높이차 확인 · 접촉 미확인',
                terrain_origin_z=root_z, root_z_offset_m=offset_z,
                spawn_root_z_m=spawn_z, eligible=True, reason='')


@lru_cache(maxsize=128)
def start_plan(difficulty, cmd, root_height_m=fk.DEFAULT_ROOT_HEIGHT_M):
    from foothold_s2.terrains.sparse_terrains import build_tile

    # 앞의 세 상자는 입구·출구·구덩이 바닥이다. 발판 후보에서 반드시 뺀다.
    return {name: select_start(build_tile(kind, difficulty).boxes[3:], cmd, root_height_m=root_height_m)
            for name, kind in KINDS.items()}


def legacy_region(name, cfg, difficulty):
    """설정이 정의한 feature 외곽. START 띠를 기존 지형에 대입하지 않는다."""
    sx, sy = cfg.size
    if name == "stepping_stones":
        # 설치본 height_field/utils.py: border_pixels = int(border_width / scale) + 1.
        border = (int(cfg.border_width / cfg.horizontal_scale) + 1) * cfg.horizontal_scale
        return ((border, sx - border), (border, sy - border)), cfg.holes_depth
    if name in ("gap", "floating_ring"):
        widths = cfg.gap_width_range if name == "gap" else cfg.ring_width_range
        width = widths[0] + difficulty * (widths[1] - widths[0])
        half = cfg.platform_width / 2. + width
        # gap은 중앙 발판과 주위 틈의 외곽, ring은 고리의 외곽이다.
        return ((sx / 2. - half, sx / 2. + half),
                (sy / 2. - half, sy / 2. + half)), (0. if name == "floating_ring" else -np.inf)
    raise ValueError("듬성한 영역을 추출할 수 없는 지형: %s" % name)


def support_boxes(meshes, floor):
    """같은 높이의 위쪽 삼각형 두 개가 정확한 사각형을 이룰 때만 지지 패치로 쓴다."""
    boxes = []
    for mesh in meshes:
        edges = {}
        for index in np.flatnonzero(mesh.face_normals[:, 2] > 1. - EPS):
            face = mesh.faces[index]
            if mesh.triangles[index, 0, 2] <= floor + EPS:
                continue
            for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                edges.setdefault(tuple(sorted((int(a), int(b)))), []).append(index)
        for pair in edges.values():
            if len(pair) != 2:
                continue
            points = mesh.triangles[pair].reshape(-1, 3)
            lo, hi = points.min(axis=0), points.max(axis=0)
            area = (hi[0] - lo[0]) * (hi[1] - lo[1])
            if hi[2] - lo[2] <= EPS and area > EPS and np.isclose(
                    mesh.area_faces[pair].sum(), area, atol=EPS, rtol=1.e-6):
                boxes.append([lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]])
    return boxes


def legacy_start(name, cfg, difficulty, meshes, cmd, *, terrain_origin_z=0., root_height_m=fk.DEFAULT_ROOT_HEIGHT_M):
    try:
        zone, floor = legacy_region(name, cfg, difficulty)
    except (AttributeError, TypeError, ValueError):
        result = select_start([], cmd, terrain_origin_z=terrain_origin_z, root_height_m=root_height_m)
        return dict(result, reason="sparse_region_unavailable")
    result = select_start(support_boxes(meshes, floor), cmd, zone,
                          terrain_origin_z=terrain_origin_z, root_height_m=root_height_m)
    return dict(result, zone=[list(axis) for axis in zone])


def install_fixed_reset(raw, names, plan):
    """환경 생성 뒤, 첫 평가 reset 전에 설치한다. 이후 자동 reset에도 적용된다."""
    import torch

    robot = raw.scene['robot']
    fk.validate_default_pose(robot.joint_names, robot.data.default_joint_pos.detach().cpu().numpy())
    term = raw.event_manager.get_term_cfg("reset_base")
    original = term.func
    fixed_types = [i for i, name in enumerate(names)
                   if name in KINDS or name in ("gap", "stepping_stones", "floating_ring")]
    for kind in fixed_types:
        record = plan[names[kind]]
        if record['status'] != 'ready' or record['yaw_rad'] is None:
            raise ValueError('시작점 없는 칸은 실행할 수 없습니다')
        actual_height = robot.data.default_root_state[:, 2].detach().cpu().numpy()
        if not np.allclose(actual_height, record['root_height_m'], atol=1e-6, rtol=0):
            raise ValueError('기본 root 높이가 시작점 기록과 다릅니다')

    def reset(env, env_ids, **params):
        ids = torch.arange(env.num_envs, device=env.device) if env_ids is None else torch.as_tensor(
            env_ids, device=env.device)
        selected = torch.zeros(len(ids), dtype=torch.bool, device=env.device)
        for kind in fixed_types:
            selected |= env.scene.terrain.terrain_types[ids] == kind
        if (~selected).any():
            original(env, ids[~selected], **params)
        for kind in fixed_types:
            match = env.scene.terrain.terrain_types[ids] == kind
            if not match.any():
                continue
            fixed = dict(params)
            yaw = float(plan[names[kind]]['yaw_rad'])
            offset_z = float(plan[names[kind]]['root_z_offset_m'])
            fixed["pose_range"] = dict(params.get("pose_range", {}), x=(0., 0.), y=(0., 0.),
                                       z=(offset_z, offset_z), roll=(0., 0.), pitch=(0., 0.), yaw=(yaw, yaw))
            original(env, ids[match], **fixed)

    term.func = reset
    raw.event_manager.set_term_cfg("reset_base", term)
    if raw.event_manager.get_term_cfg("reset_base").func is not reset:
        raise RuntimeError("방향별 시작점 reset 설치 실패")

    joint_term = raw.event_manager.get_term_cfg('reset_robot_joints')
    original_joints = joint_term.func

    def reset_joints(env, env_ids, **params):
        ids = torch.arange(env.num_envs, device=env.device) if env_ids is None else torch.as_tensor(
            env_ids, device=env.device)
        selected = torch.zeros(len(ids), dtype=torch.bool, device=env.device)
        for kind in fixed_types:
            selected |= env.scene.terrain.terrain_types[ids] == kind
        if (~selected).any():
            original_joints(env, ids[~selected], **params)
        if selected.any():
            # 원래 event 함수가 scale인지 offset인지에 기대지 않고 실제 default 값을 쓴다.
            asset = env.scene['robot']
            chosen = ids[selected]
            pos = asset.data.default_joint_pos[chosen].clone()
            vel = torch.zeros_like(pos)
            asset.write_joint_state_to_sim(pos, vel, env_ids=chosen)

    joint_term.func = reset_joints
    raw.event_manager.set_term_cfg('reset_robot_joints', joint_term)
    if raw.event_manager.get_term_cfg('reset_robot_joints').func is not reset_joints:
        raise RuntimeError('기본 관절 자세 reset 설치 실패')
