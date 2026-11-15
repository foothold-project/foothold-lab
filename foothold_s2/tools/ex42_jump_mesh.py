"""Build CPU-only family-F mesh, flags and provenance. Does not start Kit or train.

python -m foothold_s2.tools.ex42_jump_mesh --seed 42 --out /new/output/directory
The directory must not exist. CPU manifests cannot satisfy the measured terrain
prestart gate; a lead-authorized mounting/measurement run is still required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from foothold_s2.terrains import jump_preset as jp

REPO = Path(__file__).resolve().parents[2]
SOURCE_FILES = (
    'foothold_s2/terrains/jump_preset.py',
    'foothold_s2/terrains/ex42_flag_producer.py',
    'foothold_s2/terrains/ex42_combined.py',
    'foothold_s2/terrains/ex42_column_reset.py',
    'foothold_s2/terrains/ex42_mesh_mount.py',
    'foothold_s2/scripts/ex42_mesh_build.py',
    'foothold_s2/tools/ex42_jump_mesh.py',
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_support(data, flags):
    """Ray-test the saved float32 triangles, all rows, origins and four goals.

    This is a geometric support check, not an articulated Go2 reset/rollout.
    A circumscribed rectangle covers every rotation of a 0.70 x 0.50 m patch
    and the existing XY reset jitter. Flags use both approach/exit plateaus.
    """
    import numpy as np
    from foothold_s2.terrains.ex42_mesh_mount import MeshHeights

    heights = MeshHeights(data['vertices'], data['faces'])
    extent = .5 + np.hypot(.35,.25)
    offsets = np.array([[x,y] for x in (-extent,0.,extent) for y in (-extent,0.,extent)])
    cells = []
    for row in range(jp.LAYOUT_ROWS):
        for col,kind in enumerate(jp.KINDS):
            origin = data['origins'][row,col]
            patch = heights.at(origin[:2]+offsets)
            goal_z = heights.at(flags[row,col])
            level = min(row,jp.LEVEL_COUNTS[kind]-1)
            value = jp.LEVEL_VALUES_M[kind][level]
            expected_goals = [0.]*4 if kind == 'jump_gap' else (
                [value,value,0.,0.] if kind == 'jump_down_low' else [0.,0.,value,value])
            if (not np.isfinite(patch).all() or not np.isfinite(goal_z).all()
                    or not np.allclose(patch,origin[2],rtol=0,atol=1e-6)
                    or not np.allclose(goal_z,expected_goals,rtol=0,atol=1e-6)):
                raise ValueError(f'F support mismatch: row={row}, kind={kind}')
            cells.append({'row':row,'column':col,'kind':kind,'physical_level':level,
                          'origin_z_m':float(origin[2]),
                          'reset_support_error_max_m':float(np.abs(patch-origin[2]).max()),
                          'flag_support_z_m':goal_z.tolist()})
    return {'format':'foothold-ex42-jump-cpu-support/1','status':'passed',
            'method':'downward_trimesh_rays_on_serialized_float32_mesh',
            'cells_checked':len(cells),'reset_rays_per_cell':len(offsets),
            'flag_rays_per_cell':4,'reset_envelope_half_width_m':float(extent),
            'articulated_robot_mount_test':False,'cells':cells}


def write_bundle(out: Path, *, seed: int):
    from foothold_s2.terrains.ex42_combined import combine_family_parts
    from foothold_s2.terrains.ex42_column_reset import build_column_table
    from foothold_s2.scripts.ex42_mesh_build import build_flags, write_mesh_arrays
    from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh

    out = Path(out)
    if out.exists():
        raise FileExistsError(f'output exists, refusing to replace evidence: {out}')
    part = jp.build_family_cpu(seed=seed)
    combined = combine_family_parts([part])
    flags, provenance = build_flags([part], combined)
    out.mkdir(parents=True, exist_ok=False)
    npz = out/'terrain_mesh.npz'
    write_mesh_arrays(npz, combined, flags)
    stored = load_combined_mesh(npz)
    cpu_check = verify_support(stored, flags)
    (out/'cpu_support.json').write_text(json.dumps(cpu_check,sort_keys=True,indent=2,
        allow_nan=False)+'\n',encoding='utf-8')
    source = {'commit': jp.SOURCE_COMMIT, 'path': jp.SOURCE_PATH, 'section': jp.SOURCE_SECTION}
    assumptions = {
        'grade': 'project_assumption', 'tile_size_m': list(jp.TILE_SIZE),
        'gap_depth_m': jp.GAP_DEPTH_M, 'floor_thickness_m': jp.FLOOR_THICKNESS_M,
        'obstacle_x_fraction': .5, 'origin_xy_m': [1.,4.],
        'desired_flags_local_xy_m': jp.desired_flags().tolist(),
        'reset_patch_rectangle_m': [.70,.50], 'reset_xy_jitter_m': [-.5,.5],
    }
    kinds = []
    for kind in jp.KINDS:
        dimensions = [jp.build_tile(kind, level, seed=seed).dimensions
                      for level in range(jp.LEVEL_COUNTS[kind])]
        kinds.append({'family':'F', 'kind':kind, 'stage':jp.STAGES[kind],
                      'preset_id':jp.PRESET_ID, 'physical_level_dimensions_m':dimensions,
                      'dimension_source':source, 'dimension_grade':'approved_project_ladder',
                      'layout_grade':'project_assumption'})
    manifest = {
        'format':'foothold-ex42-combined-mesh/1', 'status':'cpu_generated',
        'training_ready':False, 'seed':int(seed), 'mesh_file':'terrain_mesh.npz',
        'mesh_sha256':stored['mesh_sha256'], 'npz_sha256':_sha(npz),
        'families_present':['F'], 'families_missing':['A','B','C','D','E'],
        'columns_by_family':{'F':len(jp.KINDS)},
        'column_family':combined['column_family'], 'column_kinds':list(jp.KINDS),
        'origins_shape':list(combined['origins'].shape), 'bounds_m':combined['bounds'],
        'join_axis':combined['axis'], 'offsets_m':combined['offsets'],
        'vertex_count':len(stored['vertices']), 'face_count':len(stored['faces']),
        'mesh_file_sha256':_sha(npz),
        'row_physical_levels':{k:[min(r,jp.LEVEL_COUNTS[k]-1) for r in range(jp.LAYOUT_ROWS)]
                               for k in jp.KINDS},
        'reset_ranges_by_column':build_column_table(combined['column_family']),
        'flag_provenance':provenance, 'kinds':kinds, 'layout_assumptions':assumptions,
        'cpu_support_receipt':{'path':'cpu_support.json','sha256':_sha(out/'cpu_support.json')},
        'source_files_sha256':{p:_sha(REPO/p) for p in SOURCE_FILES},
        'rng_provenance':{'algorithm':'no_random_draws', 'state_modified':False,
               'different_seed_is_independent_geometry':False},
        'measurements':{}, 'training_started':False,
        'pending':['kit_mount', 'gpu_memory', 'ray_throughput',
                                    'training_exposure_and_approval'],
    }
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n'
    (out/'mesh_manifest.json').write_text(payload, encoding='utf-8')
    # Deliberately not status=measured, and no invented original paper dimensions.
    terrain = {'format':'foothold-ex42-terrain-manifest/1', 'status':'cpu_generated',
               'training_presets':{'F':jp.PRESET_ID}, 'kinds':kinds,
               'mesh_manifest_sha256':_sha(out/'mesh_manifest.json'),
               'measurements':{}, 'receipt_ids':[], 'pending':manifest['pending']}
    (out/'terrain_manifest.json').write_text(json.dumps(terrain, ensure_ascii=False,
        sort_keys=True, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = write_bundle(args.out, seed=args.seed)
    except (ValueError, FileExistsError) as exc:
        print(json.dumps({'status':'error', 'error':str(exc)}))
        return 2
    print(json.dumps({'status':result['status'], 'mesh_sha256':result['mesh_sha256'],
                      'npz_sha256':result['npz_sha256'], 'output':str(args.out)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
