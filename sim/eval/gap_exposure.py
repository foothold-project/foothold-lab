# -*- coding: utf-8 -*-
"""생성된 학습 지형의 도랑과 두 구간 직선 자취를 CPU 에서 교차 판정한다.

분류: 실험
작성: Codex 세션 (오흥재 지시) · 2026-09-20 09:35
근거: inbox/jay/20260920-FG-design.md v1.1 · fg_task1.md 5절
요지: 세 지형에 동일한 두 명령을 주어 에피소드 노출률과 첫 도달 거리를 센다
상태: 기하 측정 · 물리 시뮬 및 정책 성능과 다름
판: v1.0

Isaac Sim 을 불러오지 않는다. 지형 소스의 함수 본문은 AST 로 그대로 읽어
실행하고 cfg 기본값만 가져온다. Isaac 전용 import 와 configclass 는 실행하지
않는다. 도랑 경계는 공식 생성 함수가 반환한 실제 메시 꼭짓점에서 추출한다.
처음 자세는 +x 다. 각 구간은 뽑힌 세계 heading 으로 즉시 직진하는 근사라
회전 시간 · 정지 2 % · 리셋 위치와 yaw 잡음 · 점프와 추락은 모델링하지 않는다.
원래 8 m 타일 경계에 닿으면 그 에피소드의 이동을 끝내며 이웃 타일은 안 본다.
rotated 의 회전된 슬랩 바깥 빈 모서리는 도랑으로 세지 않는다.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import trimesh
from scipy.spatial import ConvexHull


DEFAULT_GAP_DIR = Path(
    "C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/"
    "locomotion/velocity/config/go2/gap_training"
)
ROOT = Path(__file__).resolve().parents[2]


def load_geometry(gap_dir: Path):
    """시뮬 의존성 없이 원본 함수와 명시된 cfg 기본값을 읽는다."""
    paths = (gap_dir / "gap_terrain.py", ROOT / "sim/policy/omni_gap_terrain.py")
    namespace = {"np": np, "trimesh": trimesh}
    defaults = {"size": (8.0, 8.0), "proportion": 0.1}
    hashes = {}
    for path in paths:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
        # 미래형 주석을 유지해 cfg 형식 힌트가 런타임 의존성을 만들지 않게 한다.
        body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
        body.extend(node for node in tree.body if isinstance(node, ast.FunctionDef))
        exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                     str(path), "exec"), namespace)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, ast.AnnAssign) and member.value is not None:
                        defaults[member.target.id] = ast.literal_eval(member.value)
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return namespace, defaults, hashes


def top_hull(vertices: np.ndarray) -> np.ndarray:
    """윗면 점들의 반시계 방향 볼록 껍질을 반환한다."""
    points = np.unique(vertices[np.isclose(vertices[:, 2], 0), :2], axis=0)
    return points[ConvexHull(points).vertices]


def gap_polygons(meshes, mode, size):
    """실제로 생성된 메시에서 도랑의 외곽과 고리 안쪽 섬을 얻는다."""
    if mode == "ring":
        inner = top_hull(meshes[0].vertices)
        vertices = np.vstack([mesh.vertices for mesh in meshes[1:]])
        center = np.asarray(size) / 2
        near = np.linalg.norm(vertices[:, :2] - center, axis=1) < min(size) / 2 - 1e-9
        return top_hull(vertices[near]), inner
    # 두 직사각 슬랩의 마주 보는 면이 도랑 양쪽 경계다. 회전 뒤에도 같다.
    first, second = (top_hull(mesh.vertices) for mesh in meshes)
    normal = second.mean(axis=0) - first.mean(axis=0)
    normal /= np.linalg.norm(normal)
    left = first[np.isclose(first @ normal, max(first @ normal))]
    right = second[np.isclose(second @ normal, min(second @ normal))]
    points = np.vstack((left, right))
    return points[ConvexHull(points).vertices], None


def polygon_interval(point, direction, length, polygon):
    """반직선의 [0, length] 중 볼록 다각형 안에 드는 거리 구간을 구한다."""
    edges = np.roll(polygon, -1, axis=0) - polygon
    normals = np.column_stack((-edges[:, 1], edges[:, 0]))
    value = np.sum((point - polygon) * normals, axis=1)
    slope = normals @ direction
    parallel = np.abs(slope) < 1e-12
    if np.any(parallel & (value < -1e-10)):
        return None
    positive = slope > 1e-12
    negative = slope < -1e-12
    lower = max(0.0, float(np.max(-value[positive] / slope[positive], initial=-np.inf)))
    upper = min(length, float(np.min(-value[negative] / slope[negative], initial=np.inf)))
    return (lower, upper) if upper - lower > 1e-10 else None


def first_gap_distance(point, direction, length, outer, inner):
    """도랑 외곽 구간에서 안쪽 섬 구간을 빼고 첫 양의 길이 노출을 찾는다."""
    interval = polygon_interval(point, direction, length, outer)
    if interval is None:
        return None
    start, end = interval
    island = None if inner is None else polygon_interval(point, direction, length, inner)
    if island is None or island[0] > start + 1e-10:
        return start
    start = max(start, island[1])
    return start if end - start > 1e-10 else None


def episode(origin, headings, speeds, outer, inner, size):
    """두 10 초 구간을 이어 걷는다. 타일 경계에 닿으면 남은 명령은 버린다."""
    point = np.asarray(origin[:2], dtype=float).copy()
    travelled = 0.0
    for heading, speed in zip(headings, speeds):
        direction = np.array((np.cos(heading), np.sin(heading)))
        boundary = np.full(2, np.inf)
        for axis in range(2):
            if direction[axis] > 1e-12:
                boundary[axis] = (size[axis] - point[axis]) / direction[axis]
            elif direction[axis] < -1e-12:
                boundary[axis] = -point[axis] / direction[axis]
        limit = max(0.0, float(min(boundary)))
        length = min(float(speed) * 10.0, limit)
        hit = first_gap_distance(point, direction, length, outer, inner)
        if hit is not None:
            return travelled + hit
        if limit <= float(speed) * 10.0 + 1e-10:
            return None
        point += direction * length
        travelled += length
    return None


def measure(gap_dir: Path, episodes: int = 10000):
    """seed 42 와 같은 명령 표본으로 세 모드의 에피소드 노출을 비교한다."""
    functions, defaults, hashes = load_geometry(gap_dir)
    np.random.seed(42)
    headings = np.random.uniform(-np.pi, np.pi, (episodes, 2))
    speeds = np.random.uniform(0.4, 1.5, (episodes, 2))
    rows = []
    for mode in ("forward_gap", "rotated", "ring"):
        cfg = SimpleNamespace(**(defaults | {"mode": mode}))
        generator = functions["forward_gap_terrain" if mode == "forward_gap" else "omni_gap_terrain"]
        distances, angles = [], []
        sweep_hits = 0
        for index in range(episodes):
            # 고정 기하는 재사용하되 회전 모드는 에피소드마다 실제 타일을 생성한다.
            if index == 0 or mode == "rotated":
                meshes, origin = generator(0.5, cfg)
                outer, inner = gap_polygons(meshes, mode, cfg.size)
            if mode == "rotated":
                angles.append(meshes[0].metadata["gap_rotation_rad"])
            if index == 0:
                for heading in np.linspace(-np.pi, np.pi, 360, endpoint=False):
                    sweep_hits += episode(origin, [heading], [0.4], outer, inner, cfg.size) is not None
            distance = episode(origin, headings[index], speeds[index], outer, inner, cfg.size)
            if distance is not None:
                distances.append(distance)
        row = {
            "terrain": mode, "episodes": episodes, "exposed_episodes": len(distances),
            "exposure_rate": len(distances) / episodes,
            "mean_first_exposure_distance_m": float(np.mean(distances)) if distances else None,
            "first_tile_360_direction_hits": int(sweep_hits),
        }
        if angles:
            counts, bins = np.histogram(angles, bins=12, range=(-np.pi, np.pi))
            row["rotation_histogram"] = {"edges_rad": bins.tolist(), "counts": counts.tolist()}
        rows.append(row)
    hashes[Path(__file__).name] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {
        "seed": 42, "difficulty": 0.5, "tile_size_m": [8, 8],
        "gap_width_range_m": list(defaults["gap_width_range"]),
        "gap_width_m": sum(defaults["gap_width_range"]) / 2,
        "ring_radius_m": defaults["ring_radius"], "ring_num_sides": defaults["num_sides"],
        "heading_range_rad": [-np.pi, np.pi], "vx_range_m_s": [0.4, 1.5],
        "command_interval_s": 10, "episode_duration_s": 20, "initial_yaw_rad": 0,
        "method": "실제 메시 도랑과 직선 교차. 첫 구간 끝에서 둘째 구간 시작. 최초 타일 이탈에서 종료.",
        "limits": "회전 동역학 · 정지 명령 · 리셋 잡음 · 추락 미포함. 정책 성공률이 아니다.",
        "ring_radius_rationale": "중심선 2.5/0.4=6.25초. 최대폭 바깥반지름 2.70m, 착지판 최소 1.30m, 승급거리 4m 안쪽.",
        "source_sha256": hashes, "results": rows,
    }


def main():
    """세 지형 표와 재현용 JSON 을 저장한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-dir", type=Path, default=DEFAULT_GAP_DIR)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "sim/eval/results/20260920-FG-exposure.json")
    args = parser.parse_args()
    result = measure(args.gap_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("| 지형 | 노출 에피소드 | 노출률 | 첫 노출 평균 거리 (m) |")
    print("|---|---:|---:|---:|")
    for row in result["results"]:
        print(f"| {row['terrain']} | {row['exposed_episodes']}/{row['episodes']} | "
              f"{row['exposure_rate']:.2%} | {row['mean_first_exposure_distance_m']:.6f} |")
    print("회전 각도 12칸 빈도:", result["results"][1]["rotation_histogram"]["counts"])


if __name__ == "__main__":
    main()
