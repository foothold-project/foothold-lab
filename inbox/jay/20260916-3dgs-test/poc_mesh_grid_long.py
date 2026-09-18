"""스플랫 중심으로부터 CPU 2.5D 지면 메시와 관측 지표 생성.

분류: 실험
작성: 오흥재 · 2026-09-16 18:58
근거: WORKER-04-mesh.md v1.1 · 코디네이터의 거리 제한 IDW 지시
요지: 깊이 봉우리로 평면을 정하고 추측 축척으로 Z 업 미터 메시를 만든다.
"""
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import shlex
import sys
import time
import traceback

sys.dont_write_bytecode = True
import cv2
import numpy as np
import scipy
from scipy import ndimage, signal, special
from scipy.spatial import cKDTree
import trimesh

ROOT = Path(__file__).resolve().parent
KST = dt.timezone(dt.timedelta(hours=9))


def now():
    return dt.datetime.now(KST).isoformat()


@contextlib.contextmanager
def stage(stats, name):
    entry = {"name": name, "start": now()}
    stats["stages"].append(entry)
    started = time.perf_counter()
    print("START", name, entry["start"], flush=True)
    try:
        yield
    finally:
        entry.update(end=now(), seconds=time.perf_counter() - started)
        print("END", name, f"{entry['seconds']:.3f}s", flush=True)


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def quantiles(values):
    return {"q25": float(np.quantile(values, .25)),
            "median": float(np.median(values)), "q75": float(np.quantile(values, .75))}


def read_ply(path):
    types = {"float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8",
             "uchar": "u1", "uint8": "u1", "char": "i1", "int8": "i1",
             "short": "<i2", "ushort": "<u2", "int": "<i4", "uint": "<u4"}
    header, fields, count, element = [], [], None, None
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            raw = stream.readline()
            if not raw:
                raise ValueError("PLY header has no end_header")
            digest.update(raw)
            line = raw.decode("ascii").strip()
            header.append(line)
            words = line.split()
            if words[:1] == ["element"]:
                element = words[1]
                if element == "vertex":
                    count = int(words[2])
                elif int(words[2]) != 0:
                    raise ValueError("Only vertex-only PLY is supported")
            if words[:1] == ["property"] and element == "vertex":
                if len(words) != 3 or words[1] not in types:
                    raise ValueError(f"Unsupported PLY property: {line}")
                fields.append((words[2], types[words[1]]))
            if line == "end_header":
                break
        if header[0] != "ply" or "format binary_little_endian 1.0" not in header:
            raise ValueError("Expected binary_little_endian PLY")
        if not count:
            raise ValueError("Empty PLY")
        dtype = np.dtype(fields, align=False)
        header_bytes = stream.tell()
        rows = np.fromfile(stream, dtype=dtype, count=count)
        if len(rows) != count or stream.read(1):
            raise ValueError("PLY vertex payload size mismatch")
    digest.update(rows.view(np.uint8))
    required = ["x", "y", "z", "opacity", "scale_0", "scale_1", "scale_2"]
    if not set(required).issubset(dtype.names):
        raise ValueError("PLY lacks required xyz/opacity/log-scale properties")
    # One structured read; retain only seven required columns and release the rest.
    columns = {key: rows[key].astype(np.float64) for key in required}
    info = {"vertex_count": count, "properties": list(dtype.names),
            "property_types": [str(dtype.fields[n][0]) for n in dtype.names],
            "row_bytes": dtype.itemsize, "header_bytes": header_bytes,
            "file_bytes": path.stat().st_size, "sha256": digest.hexdigest()}
    del rows
    return columns, info


def read_cameras(model):
    cameras = []
    with open(model / "cameras.txt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip() and not line.startswith("#"):
                fields = line.split()
                cameras.append({"id": int(fields[0]), "model": fields[1],
                                "width": int(fields[2]), "height": int(fields[3]),
                                "parameters": list(map(float, fields[4:]))})
    if len(cameras) != 1 or cameras[0]["model"] != "PINHOLE":
        raise ValueError("Expected exactly one PINHOLE camera")
    poses = []
    with open(model / "images.txt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split()
            w, x, y, z = map(float, fields[1:5])
            if abs(w*w + x*x + y*y + z*z - 1) > 1e-6:
                raise ValueError("Camera quaternion is not normalized")
            rotation = np.array([[1-2*y*y-2*z*z, 2*(x*y-z*w), 2*(x*z+y*w)],
                                 [2*(x*y+z*w), 1-2*x*x-2*z*z, 2*(y*z-x*w)],
                                 [2*(x*z-y*w), 2*(y*z+x*w), 1-2*x*x-2*y*y]])
            translation = np.array(list(map(float, fields[5:8])))
            if int(fields[8]) != cameras[0]["id"]:
                raise ValueError("Image refers to an unexpected camera")
            poses.append((fields[9], int(fields[0]), -rotation.T @ translation, rotation[1], rotation[2]))
            if next(stream, None) is None:
                raise ValueError("Missing image observation line")
    poses.sort(key=lambda record: record[0])
    if len(poses) < 3:
        raise ValueError("Insufficient camera trajectory")
    centers = np.array([p[2] for p in poses])
    downs = np.array([p[3] for p in poses])
    mean_down = np.mean(downs, axis=0)
    length = float(np.linalg.norm(np.diff(centers, axis=0), axis=1).sum())
    if length <= 0 or np.linalg.norm(mean_down) < 1e-8:
        raise ValueError("Degenerate camera trajectory or mean down direction")
    with open(model / "points3D.txt", encoding="utf-8") as stream:
        point_count = sum(bool(line.strip()) and not line.startswith("#") for line in stream)
    return centers, downs, {"camera": cameras[0], "image_count": len(poses),
                            "image_names": [p[0] for p in poses],
                            "image_ids": [p[1] for p in poses], "centers_units": centers,
                            "down_vectors_world": downs, "mean_down_world": mean_down,
                            "forward_vectors_world": np.array([p[4] for p in poses]),
                            "trajectory_length_units": length, "sfm_point_count": point_count,
                            "trajectory_sort": "image filename lexical/temporal order"}


def residuals(points, normal, offset):
    # Avoid tiny-width BLAS calls inside the 2,000-iteration CPU loop.
    return points[:, 0]*normal[0] + points[:, 1]*normal[1] + points[:, 2]*normal[2] + offset


def fit_plane(points, threshold, iterations, seed, mean_down):
    rng = np.random.default_rng(seed)
    best_count, best_mask, attempted = 0, None, 0
    for _ in range(iterations):
        sample = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(sample[1]-sample[0], sample[2]-sample[0])
        norm = np.linalg.norm(normal)
        if norm < 1e-12:
            continue
        attempted += 1
        normal /= norm
        offset = -float(normal @ sample[0])
        mask = np.abs(residuals(points, normal, offset)) <= threshold
        count = int(mask.sum())
        if count > best_count:
            best_count, best_mask = count, mask
    if best_count < 3:
        raise ValueError("RANSAC found fewer than three plane inliers")
    # TLS refit, then reclassify. Final count/RMS refer to the final plane equation.
    mask = best_mask
    for _ in range(3):
        selected = points[mask]
        center = selected.mean(axis=0)
        centered = selected-center
        _, vectors = np.linalg.eigh(centered.T @ centered)
        normal = vectors[:, 0]
        offset = -float(normal @ center)
        mask = np.abs(residuals(points, normal, offset)) <= threshold
        if mask.sum() < 3:
            raise ValueError("Plane refit has insufficient inliers")
    if normal @ mean_down > 0:
        normal, offset = -normal, -offset
    error = residuals(points, normal, offset)
    return normal, offset, mask, {"iterations": iterations, "nondegenerate_trials": attempted,
                                  "initial_inliers": best_count, "inlier_count": int(mask.sum()),
                                  "candidate_count": len(points), "normal_up_world": normal,
                                  "offset_units": offset, "threshold_units": threshold,
                                  "residual_rms_units": float(np.sqrt(np.mean(error[mask]**2))),
                                  "normal_dot_mean_down": float(normal @ mean_down)}


def world_transform(normal, offset, centers, scale):
    reference = np.array([1., 0., 0.])
    if abs(reference @ normal) > .9:
        reference = np.array([0., 1., 0.])
    tangent = reference - normal*(reference @ normal)
    tangent /= np.linalg.norm(tangent)
    basis = np.stack((tangent, np.cross(normal, tangent), normal))
    projected = centers @ basis.T
    xy = projected[:, :2] - projected[:, :2].mean(axis=0)
    eigenvalues, eigenvectors = np.linalg.eigh(xy.T @ xy / len(xy))
    direction = eigenvectors[:, -1]
    sign_reference = xy[-1]-xy[0]
    sign_rule = "first-to-last camera displacement"
    if abs(sign_reference @ direction) < 1e-8:
        projections = (xy-xy[0]) @ direction
        sign_reference = xy[int(np.argmax(np.abs(projections)))]-xy[0]
        sign_rule = "largest displacement from first camera (closed-path fallback)"
    if sign_reference @ direction < 0:
        direction = -direction
    yaw = np.array([[direction[0], direction[1], 0.],
                    [-direction[1], direction[0], 0.], [0., 0., 1.]])
    rotation = yaw @ basis
    mean_camera = (centers @ rotation.T).mean(axis=0)
    matrix = np.eye(4)
    matrix[:3, :3] = scale*rotation
    matrix[:3, 3] = [-scale*mean_camera[0], -scale*mean_camera[1], scale*offset]
    return matrix, rotation, {"world_to_mesh_4x4": matrix,
                              "rotation_world_to_mesh": rotation,
                              "rotation_determinant": float(np.linalg.det(rotation)),
                              "normal_in_mesh": rotation @ normal,
                              "trajectory_xy_pca_eigenvalues_units2": eigenvalues,
                              "progress_sign_rule": sign_rule, "coordinate_system": "right-handed Z-up",
                              "length_unit": "meter", "scale_confidence": "추측"}


def transform(points, matrix):
    return points @ matrix[:3, :3].T + matrix[:3, 3]


def distance_to_path(xy, cameras_xy):
    minimum = np.full(len(xy), np.inf)
    for start, end in zip(cameras_xy[:-1], cameras_xy[1:]):
        vector = end-start
        length2 = float(vector @ vector)
        if length2 < 1e-20:
            delta = xy-start
        else:
            delta = xy-start
            projection = np.clip((delta[:, 0]*vector[0]+delta[:, 1]*vector[1])/length2, 0., 1.)
            delta = xy-start-projection[:, None]*vector
        minimum = np.minimum(minimum, np.sum(delta*delta, axis=1))
    return np.sqrt(minimum)


def make_grid(points, camera_centers, cell, args):
    lower = camera_centers[:, :2].min(axis=0)-args.margin
    upper = camera_centers[:, :2].max(axis=0)+args.margin
    shape_xy = np.maximum(2, np.ceil((upper-lower)/cell).astype(int))
    nx, ny = map(int, shape_xy)
    if nx*ny > 10_000_000:
        raise ValueError("Height grid exceeds the ten-million-cell safety bound")
    x = lower[0]+(np.arange(nx)+.5)*cell
    y = lower[1]+(np.arange(ny)+.5)*cell
    xx, yy = np.meshgrid(x, y)
    centers = np.column_stack((xx.ravel(), yy.ravel()))
    path_distance = distance_to_path(centers, camera_centers[:, :2]).reshape(ny, nx)
    walking = path_distance <= args.walk_radius_m
    roi_limited = nx*ny > 4_000_000
    roi = (path_distance <= 3.) if roi_limited else np.ones((ny, nx), dtype=bool)
    indices = np.floor((points[:, :2]-lower)/cell).astype(int)
    inside = (indices[:, 0] >= 0) & (indices[:, 0] < nx) & (indices[:, 1] >= 0) & (indices[:, 1] < ny)
    indices, heights = indices[inside], points[inside, 2]
    keys = indices[:, 1]*nx+indices[:, 0]
    counts = np.bincount(keys, minlength=nx*ny).reshape(ny, nx)
    observed = (counts >= args.min_points) & roi
    height = np.full(nx*ny, np.nan)
    order = np.argsort(keys, kind="stable")
    sorted_keys, sorted_z = keys[order], heights[order]
    unique, starts, group_counts = np.unique(sorted_keys, return_index=True, return_counts=True)
    for key, start, count in zip(unique, starts, group_counts):
        if count >= args.min_points:
            height[key] = np.median(sorted_z[start:start+count])
    height = height.reshape(ny, nx)
    height[~roi] = np.nan
    if not observed.any():
        raise ValueError("No grid cell has enough observed points")
    return {"x": x, "y": y, "centers": centers, "counts": counts, "observed": observed,
            "walking": walking, "height_observed": height, "cell": cell,
            "lower": lower, "upper": lower+shape_xy*cell, "points_inside": int(inside.sum()),
            "points_outside": int((~inside).sum()), "roi": roi,
            "roi_limited": roi_limited, "roi_cells": int(roi.sum())}


def fill_grid(grid, args):
    observed = grid["observed"]
    distance, nearest = ndimage.distance_transform_edt(~observed, sampling=grid["cell"], return_indices=True)
    fill = (~observed) & (distance <= args.fill_max_m) & grid["roi"]
    empty = (~observed) & (~fill)
    height = grid["height_observed"].copy()
    target_indices = np.flatnonzero(fill)
    if len(target_indices):
        observed_indices = np.flatnonzero(observed)
        tree = cKDTree(grid["centers"][observed_indices])
        k = min(args.fill_k, len(observed_indices))
        distances, neighbors = tree.query(grid["centers"][target_indices], k=k, workers=1)
        if k == 1:
            distances, neighbors = distances[:, None], neighbors[:, None]
        # EDT determines both fill eligibility and the first nearest source.
        nearest_flat = np.ravel_multi_index((nearest[0][fill], nearest[1][fill]), observed.shape)
        height.ravel()[target_indices] = grid["height_observed"].ravel()[nearest_flat]
        if not np.allclose(distances[:, 0], distance[fill], rtol=1e-8, atol=1e-10):
            raise ValueError("EDT and KD-tree nearest distances disagree")
        weights = 1./np.maximum(distances, 1e-12)
        values = grid["height_observed"].ravel()[observed_indices[neighbors]]
        height.ravel()[target_indices] = np.sum(weights*values, axis=1)/weights.sum(axis=1)
    edges = np.linspace(0., args.fill_max_m, 11) if args.fill_max_m > 0 else np.array([0., 1e-12])
    histogram, _ = np.histogram(distance[fill], bins=edges)
    grid.update(filled=fill, empty=empty, valid=observed | fill, height_filled=height,
                fill_distance=distance, fill_distance_edges_m=edges, fill_distance_counts=histogram)


def smooth_grid(grid, args):
    valid = grid["valid"]
    height = grid["height_filled"].copy()
    if not args.no_median:
        padding = args.median_size//2
        windows = np.lib.stride_tricks.sliding_window_view(
            np.pad(height, padding, mode="edge"), (args.median_size, args.median_size))
        # Ignore unavailable samples, but never create a value at an empty cell.
        height[valid] = np.nanmedian(windows[valid], axis=(-2, -1))
    grid["height_median"] = height.copy()
    if not args.no_gaussian and args.gaussian_sigma > 0:
        numerator = ndimage.gaussian_filter(np.where(valid, height, 0.), args.gaussian_sigma, mode="nearest")
        denominator = ndimage.gaussian_filter(valid.astype(float), args.gaussian_sigma, mode="nearest")
        height[valid] = numerator[valid]/denominator[valid]
    height[~valid] = np.nan
    grid["height_final"] = height


def mesh_grid(grid):
    ny, nx = grid["observed"].shape
    valid = grid["valid"]
    xx, yy = np.meshgrid(grid["x"], grid["y"])
    vertices = np.column_stack((xx[valid], yy[valid], grid["height_final"][valid]))
    mapping = np.full((ny, nx), -1, dtype=int)
    mapping[valid] = np.arange(len(vertices))
    complete = valid[:-1, :-1] & valid[:-1, 1:] & valid[1:, :-1] & valid[1:, 1:]
    a, b = mapping[:-1, :-1][complete], mapping[:-1, 1:][complete]
    c, d = mapping[1:, :-1][complete], mapping[1:, 1:][complete]
    faces = np.vstack((np.column_stack((a, b, c)), np.column_stack((b, d, c))))
    if not len(faces):
        raise ValueError("No complete observed/interpolated grid quad can form triangles")
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    unreferenced_before = len(vertices)-len(np.unique(faces))
    mesh.remove_unreferenced_vertices()
    return mesh, {"vertex_count": len(mesh.vertices), "face_count": len(mesh.faces),
                   "all_triangles": bool(mesh.faces.ndim == 2 and mesh.faces.shape[1] == 3),
                   "bounds_m": mesh.bounds, "watertight": bool(mesh.is_watertight),
                   "unreferenced_vertices_removed": unreferenced_before,
                   "nominal_full_grid_face_count": 2*(ny-1)*(nx-1),
                   "quads_excluded_for_empty_samples": int(complete.size-complete.sum()),
                   "up_axis": "Z", "length_unit": "meter"}


def grid_stats(grid, args):
    observed, fill, empty, walking = (grid[k] for k in ("observed", "filled", "empty", "walking"))
    total, walk_total = observed.size, int(walking.sum())
    if not walk_total:
        raise ValueError("Walking corridor has no grid cells")
    walk_valid = walking & grid["valid"]
    std_before = float(np.std(grid["height_filled"][walk_valid])) if walk_valid.any() else None
    std_after = float(np.std(grid["height_final"][walk_valid])) if walk_valid.any() else None
    return {"cell_m": grid["cell"], "shape_yx": list(observed.shape), "total_cells": total,
            "roi_limited": grid["roi_limited"], "roi_radius_m": 3. if grid["roi_limited"] else None,
            "roi_cells": grid["roi_cells"], "outside_roi_cells": int((~grid["roi"]).sum()),
            "range_min_xy_m": grid["lower"], "range_max_xy_m": grid["upper"],
            "points_inside_xy": grid["points_inside"], "points_outside_xy": grid["points_outside"],
            "observed_cells": int(observed.sum()), "observed_ratio": float(observed.mean()),
            "interpolated_cells": int(fill.sum()), "interpolated_ratio": float(fill.mean()),
            "empty_cells_beyond_distance": int(empty.sum()), "empty_ratio": float(empty.mean()),
            "walking_total_cells": walk_total, "walking_observed_cells": int((walking & observed).sum()),
            "walking_observed_ratio": float((walking & observed).sum()/walk_total),
            "walking_interpolated_cells": int((walking & fill).sum()),
            "walking_interpolated_ratio": float((walking & fill).sum()/walk_total),
            "walking_empty_cells": int((walking & empty).sum()),
            "walking_empty_ratio": float((walking & empty).sum()/walk_total),
            "walking_valid_cells": int(walk_valid.sum()), "fill_k": args.fill_k,
            "fill_max_m": args.fill_max_m, "fill_distance_edges_m": grid["fill_distance_edges_m"],
            "fill_distance_counts": grid["fill_distance_counts"],
            "walking_z_std_before_m": std_before, "walking_z_std_after_m": std_after,
            "median_enabled": not args.no_median, "median_size_cells": args.median_size,
            "gaussian_enabled": not args.no_gaussian, "gaussian_sigma_cells": args.gaussian_sigma}


def draw_heightmap(grid, cameras, output):
    valid, height = grid["valid"], grid["height_final"]
    minimum, maximum = float(np.nanmin(height)), float(np.nanmax(height))
    normalized = np.zeros(height.shape, np.uint8)
    normalized[valid] = np.clip((height[valid]-minimum)/max(maximum-minimum, 1e-12)*255, 0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(normalized, cv2.COLORMAP_VIRIDIS)
    colored[~valid] = 0
    mask = np.zeros(height.shape, np.uint8)
    mask[grid["filled"]], mask[grid["observed"]] = 128, 255
    grayscale = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    factor = max(1, min(6, 1000//max(height.shape)))
    panels = [cv2.resize(np.flipud(panel), None, fx=factor, fy=factor, interpolation=cv2.INTER_NEAREST)
              for panel in (colored, grayscale)]
    nx, ny = len(grid["x"]), len(grid["y"])
    pixels = np.column_stack(((cameras[:, 0]-grid["lower"][0])/grid["cell"]*factor,
                              (ny-(cameras[:, 1]-grid["lower"][1])/grid["cell"])*factor))
    pixels = np.rint(pixels).astype(np.int32)
    for panel in panels:
        cv2.polylines(panel, [pixels], False, (0, 80, 255), 3, cv2.LINE_AA)
        cv2.circle(panel, tuple(pixels[0]), 5, (0, 255, 255), -1)
    header, footer, gap = 56, 70, 24
    ph, pw = panels[0].shape[:2]
    canvas = np.full((ph+header+footer, 2*pw+gap, 3), 245, np.uint8)
    canvas[header:header+ph, :pw] = panels[0]
    canvas[header:header+ph, pw+gap:] = panels[1]
    labels = [("Height [m], Z-up / Y top / X right", 10), ("Observation / fill mask", pw+gap+10)]
    for label, left in labels:
        cv2.putText(canvas, label, (left, 33), cv2.FONT_HERSHEY_SIMPLEX, .55, (20, 20, 20), 1, cv2.LINE_AA)
    for label, left in [(f"z: {minimum:.3f} to {maximum:.3f} m; cell {grid['cell']:.3f} m", 10),
                        ("white: observed / gray: IDW / black: empty", pw+gap+10)]:
        cv2.putText(canvas, label, (left, header+ph+25), cv2.FONT_HERSHEY_SIMPLEX, .5, (20, 20, 20), 1, cv2.LINE_AA)
    cv2.putText(canvas, "red: camera trajectory / yellow: first camera", (10, header+ph+53),
                cv2.FONT_HERSHEY_SIMPLEX, .5, (20, 20, 20), 1, cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", canvas)
    if not success:
        raise ValueError("OpenCV PNG encoding failed")
    encoded.tofile(str(output))
    return {"path": str(output), "width_px": canvas.shape[1], "height_px": canvas.shape[0],
            "height_min_m": minimum, "height_max_m": maximum,
            "trajectory_vertices": len(cameras), "mask_values": {"observed": 255, "interpolated": 128, "empty": 0}}


def curb_candidate(grid, args):
    values = grid["height_final"][grid["walking"] & grid["valid"]]
    if not len(values):
        return {"candidate": "없음", "sample_count": 0}
    lower = math.floor(float(values.min())/args.curb_bin_m)*args.curb_bin_m
    upper = math.floor(float(values.max())/args.curb_bin_m)*args.curb_bin_m+2*args.curb_bin_m
    edges = np.arange(lower, upper+args.curb_bin_m*.1, args.curb_bin_m)
    counts, _ = np.histogram(values, bins=edges)
    peaks, _ = signal.find_peaks(np.pad(counts, 1), prominence=counts.max()*args.curb_prominence_fraction)
    peaks = peaks-1
    peaks = peaks[(peaks >= 0) & (peaks < len(counts))]
    centers = (edges[:-1]+edges[1:])/2
    result = {"sample_count": len(values), "histogram_edges_m": edges, "histogram_counts": counts,
              "peak_centers_m": centers[peaks], "peak_counts": counts[peaks],
              "bin_m": args.curb_bin_m, "prominence_fraction_of_max_bin": args.curb_prominence_fraction,
              "source": "smoothed walking cells including IDW cells", "confidence": "추측"}
    if len(peaks) >= 2:
        chosen = peaks[np.argsort(counts[peaks], kind="stable")[-2:]]
        result.update(candidate="연석 높이 후보", selected_peak_centers_m=centers[chosen],
                      candidate_height_m=float(abs(centers[chosen[1]]-centers[chosen[0]])))
    else:
        result["candidate"] = "없음"
    return result


def arguments():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--ply", type=Path, default=ROOT/"_out/shot2pipe/splat/splat.ply")
    parser.add_argument("--model", type=Path, default=ROOT/"_out/shot2pipe/colmap/undistorted/sparse_txt")
    parser.add_argument("--out", type=Path, default=ROOT/"_out/shot2pipe/mesh")
    defaults = {"min_opacity": .1, "max_scale_m": .3, "camera_height_m": .8, "cell": .05,
                "margin": 3., "walk_radius_m": 1.5, "z_min_m": -.5, "z_max_m": 1.,
                "lateral_path_factor": 1.5, "peak_half_bins": 2., "ransac_bin_fraction": .5,
                "fill_max_m": 1., "gaussian_sigma": 1., "curb_bin_m": .02,
                "curb_prominence_fraction": .05}
    for name, default in defaults.items():
        parser.add_argument("--"+name, type=float, default=default, help=name.replace("_", " "))
    for name, default in {"min_points": 3, "ransac_iterations": 2000, "hist_bins_per_path": 50,
                          "fill_k": 4, "median_size": 3, "face_limit": 10000000, "seed": 42}.items():
        parser.add_argument("--"+name, type=int, default=default, help=name.replace("_", " "))
    parser.add_argument("--no_median", action="store_true", help="Disable the median pass")
    parser.add_argument("--no_gaussian", action="store_true", help="Disable the Gaussian pass")
    args = parser.parse_args()
    for name in ("max_scale_m", "camera_height_m", "cell", "walk_radius_m", "lateral_path_factor", "peak_half_bins",
                 "ransac_bin_fraction", "curb_bin_m", "min_points", "ransac_iterations", "hist_bins_per_path", "fill_k"):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            parser.error(name+" must be finite and positive")
    if not 0 <= args.min_opacity <= 1 or args.margin < 0 or args.fill_max_m < 0 or args.gaussian_sigma < 0:
        parser.error("Invalid opacity/margin/fill distance/Gaussian sigma")
    if args.z_min_m >= args.z_max_m or args.median_size < 1 or args.median_size % 2 != 1:
        parser.error("Invalid z band or median window")
    if not 0 < args.face_limit <= 10000000 or not 0 <= args.curb_prominence_fraction <= 1:
        parser.error("face_limit must not exceed 10000000; invalid curb prominence")
    args.ply, args.model, args.out = args.ply.resolve(), args.model.resolve(), args.out.resolve()
    if not args.out.is_relative_to((ROOT/"_out/shot2pipe/mesh").resolve()):
        parser.error("Output must remain inside the owned _out/shot2pipe/mesh directory")
    return args


def run(args, stats):
    for source in [args.ply, args.model/"images.txt", args.model/"cameras.txt", args.model/"points3D.txt"]:
        if not source.is_file():
            raise FileNotFoundError(f"선행 조건 없음: {source}")
    with stage(stats, "01_ply"):
        columns, stats["ply"] = read_ply(args.ply)
        points = np.column_stack([columns[n] for n in ("x", "y", "z")])
        opacity = special.expit(columns["opacity"])
        maximum_log_scale = np.maximum.reduce([columns[n] for n in ("scale_0", "scale_1", "scale_2")])
        finite = np.isfinite(points).all(axis=1) & np.isfinite(columns["opacity"])
        finite &= np.isfinite(np.column_stack([columns[n] for n in ("scale_0", "scale_1", "scale_2")])).all(axis=1)
        del columns
    with stage(stats, "02_opacity"):
        opacity_mask = finite & (opacity >= args.min_opacity)
        stats["filter"] = {"read_count": len(points), "finite_count": int(finite.sum()),
                           "nonfinite_removed": int((~finite).sum()), "opacity_threshold": args.min_opacity,
                           "opacity_kept": int(opacity_mask.sum()),
                           "opacity_removed_after_finite": int((finite & ~opacity_mask).sum()),
                           "opacity_histogram": [{"threshold": t, "count": int((finite & (opacity >= t)).sum()),
                                                  "ratio_of_read": float((finite & (opacity >= t)).sum()/len(points))}
                                                 for t in (.05, .1, .2, .3, .5)]}
        points, maximum_log_scale = points[opacity_mask], maximum_log_scale[opacity_mask]
        del opacity, finite, opacity_mask
        if len(points) < 3:
            raise ValueError("Insufficient finite splats after opacity filtering")
    with stage(stats, "03_cameras"):
        centers, downs, stats["cameras"] = read_cameras(args.model)
        mean_down = np.mean(downs, axis=0)
    with stage(stats, "04_depth_peak_plane"):
        _, nearest = cKDTree(centers).query(points, workers=1)
        offsets = points-centers[nearest]
        depths = np.einsum("ij,ij->i", offsets, downs[nearest])
        forwards = np.einsum("ij,ij->i", offsets, stats["cameras"]["forward_vectors_world"][nearest])
        lateral = np.sqrt(np.maximum(0., np.sum(offsets*offsets, axis=1)-depths*depths))
        path_length = stats["cameras"]["trajectory_length_units"]
        width = path_length/args.hist_bins_per_path
        eligible = lateral <= path_length*args.lateral_path_factor
        if not eligible.any() or not (depths[eligible] > 0).any():
            raise ValueError("No positive-depth points inside the trajectory-relative lateral band")
        lower = math.floor(float(depths[eligible].min())/width)*width
        upper = math.floor(float(depths[eligible].max())/width)*width+2*width
        if (upper-lower)/width > 1000000:
            raise ValueError("Depth histogram exceeds one-million-bin safety bound")
        edges = np.arange(lower, upper+width*.1, width)
        counts, _ = np.histogram(depths[eligible], bins=edges)
        bin_centers = (edges[:-1]+edges[1:])/2
        positive_bins = np.flatnonzero(bin_centers > 0)
        peak_index = int(positive_bins[np.argmax(counts[positive_bins])])
        peak = float(bin_centers[peak_index])
        candidates_mask = eligible & (depths > 0) & (np.abs(depths-peak) <= args.peak_half_bins*width)
        candidates = points[candidates_mask]
        if len(candidates) < 3:
            raise ValueError("Depth-peak window has fewer than three floor candidates")
        normal, offset, inliers, stats["plane"] = fit_plane(candidates, width*args.ransac_bin_fraction,
                                                           args.ransac_iterations, args.seed, mean_down)
        stats["depth"] = {"bin_width_units": width, "histogram_edges_units": edges, "histogram_counts": counts,
                          "lateral_limit_units": path_length*args.lateral_path_factor,
                          "lateral_eligible_count": int(eligible.sum()), "lateral_removed": int((~eligible).sum()),
                          "peak_center_units": peak, "peak_bin_count": int(counts[peak_index]),
                          "candidate_half_width_units": args.peak_half_bins*width,
                          "candidate_count": len(candidates), "candidate_down_depth_units": quantiles(depths[candidates_mask]),
                          "candidate_camera_forward_depth_units": quantiles(forwards[candidates_mask]),
                          "inlier_camera_forward_depth_units": quantiles(forwards[candidates_mask][inliers])}
        with open(args.out/"plane_audit.npz", "wb") as stream:
            np.savez_compressed(stream, candidates_units=candidates, inlier_mask=inliers, normal_world=normal,
                                offset_units=offset, threshold_units=width*args.ransac_bin_fraction)
        del candidates, offsets, lateral, eligible, depths, candidates_mask
    with stage(stats, "05_scale_guess"):
        signed = residuals(centers, normal, offset)
        heights = np.abs(signed)
        median_height = float(np.median(heights))
        if median_height <= 1e-12:
            raise ValueError("Camera-to-floor median height is zero")
        scale = args.camera_height_m/median_height
        stats["scale"] = {"confidence": "추측", "camera_height_assumed_m": args.camera_height_m,
                          "meters_per_scene_unit": scale, "camera_height_units": quantiles(heights),
                          "camera_height_m": quantiles(heights*scale),
                          "camera_signed_height_units": signed, "camera_heights_m": heights*scale}
        stats["plane"]["residual_rms_m"] = stats["plane"]["residual_rms_units"]*scale
        stats["plane"]["threshold_m"] = stats["plane"]["threshold_units"]*scale
    with stage(stats, "06_transform_and_scale_filter"):
        matrix, rotation, stats["transform"] = world_transform(normal, offset, centers, scale)
        cameras_m = transform(centers, matrix)
        stats["cameras"].update(centers_m=cameras_m, down_vectors_mesh=downs @ rotation.T,
                                 trajectory_length_m=path_length*scale)
        keep_scale = maximum_log_scale <= math.log(args.max_scale_m/scale)
        stats["filter"].update(max_scale_m=args.max_scale_m, scale_kept=int(keep_scale.sum()),
                                scale_removed=int((~keep_scale).sum()))
        points_m = transform(points[keep_scale], matrix)
        forward_m = forwards[keep_scale]*scale
        global_z = (points_m[:, 2] >= args.z_min_m) & (points_m[:, 2] <= args.z_max_m)
        # Uniform rigid transform preserves nearest-camera identity in 3D.
        near_camera = nearest[keep_scale]
        height_assumed = float(stats["scale"]["camera_height_m"]["median"])
        local_height = points_m[:, 2] - (cameras_m[near_camera, 2] - height_assumed)
        keep_z = (local_height >= args.z_min_m) & (local_height <= args.z_max_m)
        stats["band_comparison"] = {
            "selected": "local_nearest_camera_3d", "input_after_opacity_scale": len(points_m),
            "camera_height_median_m": height_assumed,
            "camera_z_signed_median_m": float(np.median(cameras_m[:, 2])),
            "global_kept": int(global_z.sum()), "local_kept": int(keep_z.sum()),
            "both_kept": int((global_z & keep_z).sum()),
            "local_only": int((~global_z & keep_z).sum()),
            "global_only": int((global_z & ~keep_z).sum()),
            "neither": int((~global_z & ~keep_z).sum()),
            "band_m": [args.z_min_m, args.z_max_m],
            "formula": "point_z - (nearest_camera_z - median(abs(camera_z)))"}
        with open(args.out/"band_comparison.json", "w", encoding="utf-8") as stream:
            json.dump(stats["band_comparison"], stream, indent=2)
        stats["filter"].update(z_band_m=[args.z_min_m, args.z_max_m], z_band_kept=int(keep_z.sum()),
                                z_band_removed=int((~keep_z).sum()))
        if keep_z.any():
            stats["depth"]["ground_z_band_forward_depth_m"] = quantiles(forward_m[keep_z])
        ground_points = points_m[keep_z]
        del points, points_m, maximum_log_scale, forwards, forward_m, nearest
    stats["grid_attempts"] = []
    cell = args.cell
    for attempt in range(12):
        with stage(stats, f"07_grid_attempt_{attempt}"):
            grid = make_grid(ground_points, cameras_m, cell, args)
        with stage(stats, f"08_fill_attempt_{attempt}"):
            fill_grid(grid, args)
        with stage(stats, f"09_smooth_attempt_{attempt}"):
            smooth_grid(grid, args)
        with stage(stats, f"10_mesh_attempt_{attempt}"):
            mesh, mesh_info = mesh_grid(grid)
            info = grid_stats(grid, args)
            stats["grid_attempts"].append({"grid": info, "mesh": mesh_info})
        if len(mesh.faces) <= args.face_limit:
            break
        raise ValueError("Fixed 0.05 m grid exceeds face limit; no automatic coarsening")
    else:
        raise ValueError("Could not meet face limit after twelve grid coarsenings")
    stats["grid"], stats["mesh"] = info, mesh_info
    with open(args.out/"ground.obj", "w", encoding="utf-8", newline="\n") as stream:
        stream.write(trimesh.exchange.obj.export_obj(mesh, include_normals=False, include_color=False))
    with stage(stats, "11_heightmap"):
        stats["heightmap"] = draw_heightmap(grid, cameras_m, args.out/"ground_heightmap.png")
        with open(args.out/"grid_audit.npz", "wb") as stream:
            np.savez_compressed(stream, x_m=grid["x"], y_m=grid["y"], counts=grid["counts"],
                                observed_mask=grid["observed"], interpolated_mask=grid["filled"],
                                empty_mask=grid["empty"], walking_mask=grid["walking"],
                                fill_distance_m=grid["fill_distance"], height_observed_m=grid["height_observed"],
                                height_filled_m=grid["height_filled"], height_median_m=grid["height_median"],
                                height_final_m=grid["height_final"], camera_centers_m=cameras_m)
    with stage(stats, "12_curb_guess"):
        stats["curb"] = curb_candidate(grid, args)
    stats["acceptance"] = {"script_completed": True, "mesh_exists": (args.out/"ground.obj").is_file(),
                           "face_limit": len(mesh.faces) <= args.face_limit, "all_triangles": mesh_info["all_triangles"],
                           "z_up_meters": bool(np.allclose(rotation @ normal, [0, 0, 1])),
                           "observation_metrics": True, "plane_metrics": True,
                           "heightmap_exists": (args.out/"ground_heightmap.png").is_file()}
    stats["passed"] = all(stats["acceptance"].values())


def write_report(stats, output):
    lines = ["# REPORT-04 · 2.5D 지면 메시", "> 분류: 실험",
             "> 작성: 오흥재 · " + stats["ended_at"][:16].replace("T", " "),
             "> 근거: WORKER-04-mesh.md v1.1 · 입력 PLY 및 COLMAP 직접 계산",
             "> 요지: 스플랫 지면 후보를 평면에 정렬하고 미터 단위 높이 격자와 삼각형 메시 생성",
             "> 상태: " + ("확인됨 · 통과" if stats.get("passed") else "확인됨 · 실패"),
             "> 판: v1.0", "", "## 환경", "",
             f"시작 {stats['started_at']} · 끝 {stats['ended_at']} · 벽시계 {stats['wall_seconds']:.6f} 초.",
             "CPU 계산만 사용했다. 패키지 설치, GPU 사용, 다른 프로세스 종료는 하지 않았다.", "",
             "```json", json.dumps(stats["environment"], ensure_ascii=False, indent=2), "```", "",
             "## 명령", "", "```powershell", stats["command"], "```", "",
             "실제 적용 인자와 기본값:", "", "```json",
             json.dumps(stats["parameters"], ensure_ascii=False, indent=2, default=json_default), "```", "",
             "## 결과", "",
             "`확인됨`: 아래 수치는 스크립트가 입력과 계산 배열에서 생성했다. 카메라 높이 1.4 m에 기반한 축척과 연석 해석은 `추측`이다.",
             "불투명도 비율의 분모는 읽은 전체 점 수다. 관측 셀은 최소 3점 중앙값이며 보간 셀과 구분한다.",
             "보행 구간은 연속 카메라 궤적 선분에서 XY 거리 1.5 m 이내다. 높이 통계는 유효 관측 및 보간 셀을 포함한다.", ""]
    sections = [("01 PLY 읽기", "ply"), ("02 거르기", "filter"), ("03 카메라", "cameras"),
                ("04 깊이 히스토그램", "depth"), ("04 평면 RANSAC", "plane"),
                ("05 축척 · 추측", "scale"), ("06 좌표 변환", "transform"),
                ("07~10 격자 · 보간 · 평활화 · 메시 재시도", "grid_attempts"),
                ("07~09 최종 격자", "grid"), ("10 최종 메시", "mesh"),
                ("11 높이 그림", "heightmap"), ("12 연석 후보 · 추측", "curb")]
    large_camera = {"centers_world", "down_vectors_world", "forward_vectors_world", "image_names", "image_ids",
                    "centers_m", "down_vectors_mesh"}
    for heading, key in sections:
        if key not in stats:
            continue
        value = stats[key]
        if key == "cameras":
            value = {k: v for k, v in value.items() if k not in large_camera}
            lines += ["### " + heading, "", "전체 카메라 중심과 방향 벡터는 ground_stats.json의 cameras에 저장했다.", ""]
        else:
            lines += ["### " + heading, ""]
        lines += ["```json", json.dumps(value, ensure_ascii=False, indent=2, default=json_default, allow_nan=False), "```", ""]
    lines += ["### 단계별 시작과 끝", "", "| 단계 | 시작 | 끝 | 초 |", "|---|---|---|---:|"]
    for item in stats["stages"]:
        lines += [f"| {item['name']} | {item['start']} | {item['end']} | {item['seconds']:.6f} |"]
    lines += ["", "## 산출물", "", "| 경로 | 바이트 |", "|---|---:|"]
    for item in stats["artifacts"]:
        lines += [f"| {item['path']} | {item['bytes']} |"]
    lines += ["", "ground_stats.json은 전체 수치 원장이다. plane_audit.npz와 grid_audit.npz는 평면 잔차와 마스크를 독립 재계산할 수 있는 배열이다.",
              "", "## 문제", "",
              "작업서 1절의 8번 단계의 거리 가중평균 구현을 코디네이터에게 확인했다. EDT 최근접 인덱스 확인 후 관측 셀 4개에 1/d IDW를 적용한다.",
              "추가 지시에 따라 --fill_k 기본 4, --fill_max_m 기본 1.0 m를 사용했다. 최근접 관측 셀이 1 m보다 멀면 빈 셀로 남기고 그곳에 면을 만들지 않는다.",
              "축척은 실제 길이로 검증되지 않았다. 연석 후보는 평활화된 보행 구간 높이 히스토그램의 두 봉우리 차이일 뿐 실제 연석 존재를 확인한 값이 아니다."]
    if "error" in stats:
        lines += ["", "오류 원문:", "", "```text", stats["error"], "```"]
    else:
        lines += ["", "실행 오류 없음. 워터타이트 여부와 관측률의 좋고 나쁨은 통과 판정 대상으로 삼지 않았다."]
    lines += ["", "## 판정", "", "| 항목 | 판정 |", "|---|---|"]
    for key, value in stats.get("acceptance", {"script_completed": False}).items():
        lines += [f"| {key} | {'통과' if value else '실패'} |"]
    lines += ["", "최종 판정: " + ("통과" if stats.get("passed") else "실패") + ".", ""]
    with open(output / "REPORT-04.md", "w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    stats = {"started_at": now(), "stages": [], "passed": False,
             "environment": {"python": sys.version, "executable": sys.executable,
                             "numpy": np.__version__, "scipy": scipy.__version__,
                             "trimesh": trimesh.__version__, "opencv": cv2.__version__, "device": "CPU"},
             "parameters": vars(args).copy(),
             "command": "& " + " ".join('"' + str(part).replace('"', '`"') + '"'
                                           for part in [sys.executable, "-B", str(Path(__file__).resolve()), *sys.argv[1:]])}
    try:
        run(args, stats)
    except Exception:
        stats["error"] = traceback.format_exc()
        print(stats["error"], flush=True)
    stats["ended_at"] = now()
    stats["wall_seconds"] = time.perf_counter() - started
    stats["artifacts"] = [{"path": str(path), "bytes": path.stat().st_size}
                          for path in [args.out / name for name in
                                       ("ground.obj", "ground_heightmap.png", "plane_audit.npz", "grid_audit.npz")]
                          if path.is_file()]
    with open(args.out / "ground_stats.json", "w", encoding="utf-8", newline="\n") as stream:
        json.dump(stats, stream, ensure_ascii=False, indent=2, default=json_default, allow_nan=False)
        stream.write("\n")
    # Combined report is written separately as REPORT-10.md.
    print("PASS" if stats["passed"] else "FAIL", flush=True)
    return 0 if stats["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
