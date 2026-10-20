"""START 축 3 짧은 명령의 시작점. lead 결정 10/20, CPU 순수 계산."""

from functools import lru_cache

import numpy as np

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


def _window(cmd, zone=ZONE):
    velocity = np.asarray(cmd[:2], dtype=float)
    if not np.all(np.isfinite(velocity)):
        raise ValueError("유한한 명령만 허용")
    distance = float(np.linalg.norm(velocity) * 2.)
    if distance <= EPS or (velocity[0] < 0 and distance > MAX_BACK_REFERENCE_M + EPS):
        return None, distance
    displacement = velocity / np.linalg.norm(velocity) * (distance + BODY_MARGIN_M)
    zone = np.array(zone)
    # 직사각형은 볼록이므로 시작과 여유 끝점이 안이면 선분 전체가 안이다.
    low = zone[:, 0] + np.maximum(-displacement, 0.)
    high = zone[:, 1] - np.maximum(displacement, 0.)
    return (low, high), distance


def valid_start(origin, boxes, cmd):
    window, _ = _window(cmd)
    if window is None:
        return False
    point = np.asarray(origin, dtype=float)
    low, high = window
    if not np.all((point[:2] >= low - EPS) & (point[:2] <= high + EPS)):
        return False
    return any(x0 - EPS <= point[0] <= x1 + EPS and y0 - EPS <= point[1] <= y1 + EPS
               and abs(point[2] - z1) <= EPS
               for x0, x1, y0, y1, _, z1 in boxes)


def select_start(boxes, cmd, zone=ZONE):
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


@lru_cache(maxsize=128)
def start_plan(difficulty, cmd):
    from foothold_s2.terrains.sparse_terrains import build_tile

    # 앞의 세 상자는 입구·출구·구덩이 바닥이다. 발판 후보에서 반드시 뺀다.
    return {name: select_start(build_tile(kind, difficulty).boxes[3:], cmd)
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


def legacy_start(name, cfg, difficulty, meshes, cmd):
    try:
        zone, floor = legacy_region(name, cfg, difficulty)
    except (AttributeError, TypeError, ValueError):
        result = select_start([], cmd)
        return dict(result, reason="sparse_region_unavailable")
    result = select_start(support_boxes(meshes, floor), cmd, zone)
    return dict(result, zone=[list(axis) for axis in zone])


def install_fixed_reset(raw, names):
    """환경 생성 뒤, 첫 평가 reset 전에 설치한다. 이후 자동 reset에도 적용된다."""
    import torch

    term = raw.event_manager.get_term_cfg("reset_base")
    original = term.func
    fixed_types = [i for i, name in enumerate(names)
                   if name in KINDS or name in ("gap", "stepping_stones", "floating_ring")]

    def reset(env, env_ids, **params):
        ids = torch.arange(env.num_envs, device=env.device) if env_ids is None else torch.as_tensor(
            env_ids, device=env.device)
        selected = torch.zeros(len(ids), dtype=torch.bool, device=env.device)
        for kind in fixed_types:
            selected |= env.scene.terrain.terrain_types[ids] == kind
        if (~selected).any():
            original(env, ids[~selected], **params)
        if selected.any():
            fixed = dict(params)
            fixed["pose_range"] = dict(params.get("pose_range", {}), x=(0., 0.), y=(0., 0.), yaw=(0., 0.))
            original(env, ids[selected], **fixed)

    term.func = reset
    raw.event_manager.set_term_cfg("reset_base", term)
    if raw.event_manager.get_term_cfg("reset_base").func is not reset:
        raise RuntimeError("방향별 시작점 reset 설치 실패")
