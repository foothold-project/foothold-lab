"""EX-42 combined terrain mesh + aggregate measurements (queued Kit job, no training).

Builds each family's FULL grid with its own generator, joins them with
foothold_s2.terrains.ex42_combined (one mesh + one terrain_origins tensor), then measures the
three plan aggregates on that mesh (DESIGN-EX42-TERRAIN section 8):
  generation_seconds  wall clock of the family generators (sum)
  peak_memory_gib     warp mesh upload + 3,072-env ray buffers; max of torch peak and the
                      device free-memory drop (warp memory is outside the torch allocator)
  ray_count_per_second  downward grid rays, 3,072 env x (187 height-scan + 3,600 depth) per
                      cast, 20 warm-up + 100 timed casts, device synchronised

Families without generator code are reported missing. In that case the three numbers
are written under `partial_*` keys in aggregate_partial_mesh.json, which assemble_manifest does
not accept, so a partial mesh can never pass as the final aggregate.

Run only through the GPU queue (device cuda:1 or as lead assigns with --device).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
ALL_FAMILIES = ("A", "B", "C", "D", "E")
SUPPORTED_FAMILIES = ALL_FAMILIES + ("F",)  # F is opt-in; existing training geometry stays unchanged.
AGGREGATE_KEYS = ("peak_memory_gib", "generation_seconds", "ray_count_per_second")
ENVS = 3072
HEIGHT_SCAN_RAYS = 17 * 11          # EX-40 env.yaml height_scanner 0.1 m grid [1.6, 1.0]
DEPTH_RAYS = 60 * 60                # depth_cam 60 x 60
WARMUP, TIMED = 20, 100
FAMILY_COLUMNS = {"A": 50, "B": 12, "C": 7, "D": 3, "E": 4}   # A: columns.FULL_COLS, C: one column per kind, E: four kinds


def aggregate_files(families_present: list[str], values: dict[str, float]) -> tuple[str, dict[str, Any]]:
    """File name + payload. Final names only when every family is present."""
    if any(not isinstance(values.get(k), (int, float)) or not values[k] > 0 for k in AGGREGATE_KEYS):
        raise ValueError("aggregate values must be positive numbers")
    if len(families_present) != len(set(families_present)) or set(families_present) - set(SUPPORTED_FAMILIES):
        raise ValueError('families must be known and unique')
    if set(ALL_FAMILIES).issubset(families_present):
        return "aggregate_measurements.json", {k: float(values[k]) for k in AGGREGATE_KEYS}
    return "aggregate_partial_mesh.json", {
        **{f"partial_{k}": float(values[k]) for k in AGGREGATE_KEYS},
        "families_present": sorted(families_present),
        "families_missing": sorted(set(ALL_FAMILIES) - set(families_present)),
        "valid_for_manifest": False,
    }


def grid_offsets(nx: int, ny: int, pitch: float = 0.1):
    import numpy as np

    xs = (np.arange(nx) - (nx - 1) / 2.0) * pitch
    ys = (np.arange(ny) - (ny - 1) / 2.0) * pitch
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    return np.stack([gx.ravel(), gy.ravel()], axis=1)


def _family_generator(family: str, seed: int):
    """(TerrainGeneratorCfg, columns) for one family's full grid. Kit python only."""
    if family == "F":
        from foothold_s2.terrains.jump_preset import build_family_generator

        return build_family_generator(seed=seed)
    from foothold_s2.terrains import columns
    from foothold_s2.terrains.rough_go2_cfg import build_generator, continuous_subterrains

    if family == "A":
        from foothold_s2.terrains.start_go2_v2 import sparse_subterrains   # EX-42 A: scaled preset start_go2_v2

        subs = {**continuous_subterrains(), **sparse_subterrains(dict(columns.SPARSE))}
        return build_generator(subs, columns.FULL_COLS, seed)
    if family == "B":
        from foothold_s2.terrains import ame2_preset

        equal = {kind: 1.0 / len(ame2_preset.KINDS) for kind in ame2_preset.KINDS}      # one column per kind
        return ame2_preset.build_generator(seed=seed, num_cols=FAMILY_COLUMNS["B"], proportions=equal)
    if family == "C":
        from foothold_s2.terrains import jeplo_preset

        return jeplo_preset.build_generator(seed=seed, num_cols=FAMILY_COLUMNS["C"])
    if family == "D":
        from foothold_s2.terrains import hipan_posture

        return hipan_posture.build_family_generator(seed=seed)      # 10 rows x 3 kinds, border 0
    if family == "E":
        from foothold_s2.terrains.ex42 import PAPER_EXT_SPECS, paper_ext_subterrains

        equal = {spec.kind: 1.0 for spec in PAPER_EXT_SPECS}
        return build_generator(paper_ext_subterrains(equal), FAMILY_COLUMNS["E"], seed)
    raise ValueError(f"no generator code for terrain family {family!r} in this repository")


def build_and_measure(families: list[str], *, seed: int, device: str, out_dir: Path) -> dict[str, Any]:
    import numpy as np
    import torch
    import warp as wp
    from isaaclab.terrains import TerrainGenerator
    from isaaclab.utils.warp import convert_to_warp_mesh, raycast_mesh
    from foothold_s2.terrains.ex42_combined import combine_family_parts, family_column_summary
    from foothold_s2.terrains.mesh_rng import seeded_mesh_rng
    from foothold_s2.terrains.columns import column_types

    parts, seconds = [], {}
    # cfg.seed alone does not seed boxes (Torch) or random_rough (legacy NumPy).
    # Seed before the first family/config, then preserve the consumed states.
    with seeded_mesh_rng(seed) as rng_provenance:
        for family in families:
            cfg = _family_generator(family, seed)
            started = time.perf_counter()
            generated = TerrainGenerator(cfg)
            seconds[family] = time.perf_counter() - started
            parts.append({"name": family, "mesh": generated.terrain_mesh,
                          "origins": generated.terrain_origins, "size": cfg.size,
                          "kinds": column_types({k: v.proportion for k, v in cfg.sub_terrains.items()},
                                                cfg.num_cols)})
    combined = combine_family_parts(parts, axis=1)
    flag_started = time.perf_counter()
    flags, flag_provenance = build_flags(parts, combined)
    flag_seconds = time.perf_counter() - flag_started
    vertices = combined["vertices"].astype(np.float32)
    faces = combined["faces"].astype(np.int32)
    mesh_sha = hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest()

    torch.cuda.synchronize(device)
    free_before, _total = torch.cuda.mem_get_info(device)
    torch.cuda.reset_peak_memory_stats(device)
    mesh = convert_to_warp_mesh(vertices, faces, device)
    rng = np.random.default_rng(seed)
    origins = combined["origins"]
    rows, cols = origins.shape[0], origins.shape[1]
    picks = origins[rng.integers(0, rows, ENVS), rng.integers(0, cols, ENVS)]       # (ENVS, 3)
    pattern = np.concatenate([grid_offsets(17, 11), grid_offsets(60, 60)])           # (3787, 2)
    starts = np.repeat(picks[:, None, :], len(pattern), axis=1).copy()
    starts[:, :, :2] += pattern[None]
    starts[:, :, 2] += 5.0
    starts_t = torch.tensor(starts.reshape(-1, 3), dtype=torch.float32, device=device)
    dirs_t = torch.zeros_like(starts_t)
    dirs_t[:, 2] = -1.0
    rays_per_cast = int(starts_t.shape[0])

    def cast():
        raycast_mesh(starts_t, dirs_t, mesh)
        wp.synchronize_device(device)
        torch.cuda.synchronize(device)

    for _ in range(WARMUP):
        cast()
    timings = []
    for _ in range(TIMED):
        t0 = time.perf_counter()
        cast()
        timings.append(time.perf_counter() - t0)
    free_after, _ = torch.cuda.mem_get_info(device)
    gib = 2.0 ** 30
    peak_torch = torch.cuda.max_memory_allocated(device) / gib
    drop = max(0.0, (free_before - free_after) / gib)
    mean = float(np.mean(timings))
    values = {
        "generation_seconds": float(sum(seconds.values())),
        "peak_memory_gib": max(peak_torch, drop),
        "ray_count_per_second": rays_per_cast / mean,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    write_mesh_arrays(out_dir / "terrain_mesh.npz", combined, flags)
    # File identity includes origins and column metadata, unlike mesh_sha above.
    with (out_dir / "terrain_mesh.npz").open("rb") as stream:
        mesh_file_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    name, payload = aggregate_files(families, values)
    (out_dir / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "format": "foothold-ex42-combined-mesh/1", "seed": seed, "device": device,
        "rng_provenance": rng_provenance, "mesh_file_sha256": mesh_file_sha,
        "flag_provenance": flag_provenance, "flag_generation_seconds": flag_seconds,
        "families_present": families, "families_missing": sorted(set(ALL_FAMILIES) - set(families)),
        "mesh_sha256": mesh_sha, "vertex_count": int(len(vertices)), "face_count": int(len(faces)),
        "origins_shape": list(combined["origins"].shape), "join_axis": combined["axis"],
        "columns_by_family": family_column_summary(combined["column_family"]),
        "offsets_m": combined["offsets"], "bounds_m": combined["bounds"],
        "generation_seconds_by_family": seconds, "aggregate_file": name,
        "aggregates": values,
        "ray_measurement": {"envs": ENVS, "rays_per_env": len(pattern), "rays_per_cast": rays_per_cast,
                            "warmup": WARMUP, "timed": TIMED, "mean_s": mean,
                            "p50_s": float(np.percentile(timings, 50)),
                            "p95_s": float(np.percentile(timings, 95)), "max_s": float(max(timings)),
                            "pattern": "downward grid rays (187 height-scan + 3600 depth); proxy, not the sensor patterns"},
        "memory_measurement": {"torch_peak_gib": peak_torch, "free_memory_drop_gib": drop},
        "training_started": False,
    }
    (out_dir / "mesh_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def build_flags(parts, combined):
    """CPU route producer, after all random geometry is fixed; no RNG replay."""
    from foothold_s2.terrains.ex42_flag_producer import family_flags, combine_flags
    for part in parts:
        part['flags'], part['flag_metadata'] = family_flags(
            part['mesh'].vertices, part['mesh'].faces, part['origins'],
            part['name'], part['kinds'], part['size'])
    return combine_flags(parts, combined)


def write_mesh_arrays(path, combined, flags):
    """Same geometry/origins bytes as before; additive #657 world-XY field."""
    import numpy as np
    # Consumer validation is exercised after writing in the CPU roundtrip test.
    expected = (*combined['origins'].shape[:2], 4, 2)
    if flags.shape != expected:
        raise ValueError(f'flags shape must be {expected}')
    if not (np.isfinite(flags).all(axis=(2, 3)) | np.isnan(flags).all(axis=(2, 3))).all():
        raise ValueError('flags require wholly finite or wholly missing cells')
    np.savez_compressed(path, vertices=combined['vertices'].astype(np.float32),
                        faces=combined['faces'].astype(np.int32), origins=combined['origins'],
                        column_family=np.array(combined['column_family']), flags=flags)


def build_parser(app_launcher: Any | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--family", action="append", choices=SUPPORTED_FAMILIES,
                        help="repeatable; default A B C D E; F jump terrain is opt-in")
    parser.add_argument("--seed", type=int, default=42)
    if app_launcher is None:
        parser.add_argument("--device", default="cuda:1")
        parser.add_argument("--headless", action="store_true", default=True)
    else:
        app_launcher.add_app_launcher_args(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(REPO))
    from isaaclab.app import AppLauncher

    args, _ = build_parser(AppLauncher).parse_known_args(argv)
    families = args.family or list(ALL_FAMILIES)
    app = AppLauncher(args).app
    code = 0
    try:
        manifest = build_and_measure(families, seed=args.seed, device=args.device, out_dir=args.out)
        print(json.dumps({"state": "done", "aggregate_file": manifest["aggregate_file"],
                          "families_missing": manifest["families_missing"],
                          "aggregates": manifest["aggregates"]}), flush=True)
    except Exception as exc:
        print(json.dumps({"state": "failed", "error_type": type(exc).__name__, "error": str(exc)}),
              flush=True)
        code = 1
    sys.stdout.flush()
    app.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
