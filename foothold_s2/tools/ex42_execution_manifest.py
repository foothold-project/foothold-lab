"""CPU-only inventory from a saved EX-42 combined mesh and explicit declarations.

No Kit receipt is fabricated: geometry is read back from the already measured
mesh, and aggregate timings retain their original proxy-sensor scope. Nominal
dimensions come from the declaration owner; exact generator parameters and
source hashes are recorded separately. Missing declarations stay partial.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

import numpy as np

from foothold_s2.curriculum.ex42_prep import EX42Plan
from foothold_s2.scripts.ex42_kit_measure import buildable_kinds, DECLARATION_FIELDS
from foothold_s2.terrains import ame2_preset as b, hipan_posture as d
from foothold_s2.terrains import jeplo_preset as c, columns, ex42, start_go2_v2 as a
from foothold_s2.terrains.ex42_column_reset import family_column_kinds
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh

REPO = Path(__file__).resolve().parents[2]
TERRAINS = REPO/'foothold_s2/terrains'
SOURCE_FILES = ('columns.py', 'rough_go2_cfg.py', 'start_go2_v2.py',
                'sparse_terrains.py', 'ame2_preset.py', 'jeplo_preset.py',
                'hipan_posture.py', 'ex42.py', 'ex42_column_reset.py')


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'JSON object required: {path}')
    return value


def read_declarations(paths):
    result = {}
    for path in paths:
        for family, kinds in read_object(path).items():
            if not isinstance(kinds, dict):
                raise ValueError(f'declaration family must be an object: {family}')
            for kind, row in kinds.items():
                existing = result.setdefault(family, {})
                if kind in existing and existing[kind] != row:
                    raise ValueError(f'conflicting declaration: {family}/{kind}')
                existing[kind] = copy.deepcopy(row)
    return result


def generator_inventory():
    return buildable_kinds()


def _literal(node, constants):
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [_literal(value, constants) for value in node.elts]
    return ast.literal_eval(node)


def rough_parameters():
    """Read literal cfg arguments without importing Isaac Lab or substituting classes."""
    tree = ast.parse((TERRAINS/'rough_go2_cfg.py').read_text())
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'continuous_subterrains')
    mapping = next(n.value for n in fn.body if isinstance(n, ast.Return))
    result = {}
    for key, call in zip(mapping.keys, mapping.values):
        result[ast.literal_eval(key)] = {kw.arg: _literal(kw.value, constants)
                                        for kw in call.keywords if kw.arg != 'proportion'}
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_generator')
    call = next(n.value for n in fn.body if isinstance(n, ast.Return))
    size = next(_literal(k.value, constants) for k in call.keywords if k.arg == 'size')
    return result, tuple(size)


def generator_parameters(family, kind):
    if family == 'continuous' or (family == 'A' and kind in columns.CONTINUOUS):
        return {'cfg': rough_parameters()[0][kind]}
    if family == 'A':
        # Public constants are the exact products consumed by the scaled generator.
        keys = ('SIZE', 'ZONE_X', 'STONE_SIZE_X', 'STONE_SIZE_Y', 'STONE_GAP_X',
                'STONE_GAP_Y', 'BEAM_WIDTH', 'STEP_BEAM_WIDTH', 'STEP_BEAM_GAP',
                'GAP_WIDTH', 'DEPTH_RANGE', 'PLATFORM_Z', 'HEIGHT_JITTER')
        return {'constants': {key: getattr(a, key) for key in keys}}
    if family == 'B':
        return {'size_m': b.SIZE, 'levels': {str(level): b.dimensions(kind, level) for level in range(10)}}
    if family == 'C':
        return {'size_m': c.SIZE, 'horizontal_scale_m': c.H, 'vertical_scale_m': c.V,
                'border_cells': c.BORDER, 'inner_cells': c.INNER,
                'nominal_to_grid_note': 'Declaration dimensions are nominal; generator quantizes at H/V.'}
    if family == 'D':
        return {'levels': {str(level): d.build_tile(kind, level, seed=0,
                wall_height_m=d.WALL_HEIGHT_M, corridor_width_m=d.CORRIDOR_WIDTH_M).dimensions
                for level in range(d.LEVEL_COUNTS[kind])}, 'dimension_source': d.PRESET_SOURCE}
    if family == 'E':
        spec = next(spec for spec in ex42.PAPER_EXT_SPECS if spec.kind == kind)
        return {'cfg_type': spec.cfg_type, 'range_key': spec.range_key,
                'range_value': list(spec.range_value), 'fixed': dict(spec.fixed)}
    raise ValueError(f'unknown generator family {family}')


def declaration_errors(row):
    if not isinstance(row, dict):
        return list(DECLARATION_FIELDS)
    errors = [name for name in DECLARATION_FIELDS if row.get(name) is None]
    for key in ('preset_id', 'paper_reference'):
        if not isinstance(row.get(key), str) or not row[key].strip():
            errors.append(key)
    if type(row.get('physical_flag')) is not bool:
        errors.append('physical_flag')
    for key in ('original_dimensions_m', 'training_dimensions_m', 'evaluation_dimensions_m'):
        dims = row.get(key)
        if (not isinstance(dims, dict) or not dims or any(
                not isinstance(k, str) or not k or type(v) not in (int, float)
                or not math.isfinite(v) or v <= 0 for k, v in dims.items())):
            errors.append(key)
    train, evaluate, directions = (row.get(k) for k in (
        'training_dimensions_m', 'evaluation_dimensions_m', 'evaluation_axis_directions'))
    if (not all(isinstance(v, dict) for v in (train, evaluate, directions))
            or set(train) != set(evaluate) or set(train) != set(directions)):
        errors.append('evaluation_axis_directions')
    elif not errors:
        for axis, direction in directions.items():
            if (direction not in ('same', 'lower', 'higher')
                    or (direction == 'same' and evaluate[axis] != train[axis])
                    or (direction == 'lower' and evaluate[axis] >= train[axis])
                    or (direction == 'higher' and evaluate[axis] <= train[axis])):
                errors.append('evaluation_axis_directions:'+axis)
    return sorted(set(errors))


def check_measurements(measurements, receipt, keys):
    for key in keys:
        value = measurements.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'aggregate measurement invalid: {key}')
        if receipt.get('aggregates', {}).get(key) != value:
            raise ValueError(f'aggregate differs from measured mesh receipt: {key}')


def dimension_crosscheck(family, kind, declaration):
    """B/D expose dimensions directly; do not let a declaration alter those numbers."""
    if family not in ('B', 'D'):
        return {'state': 'nominal_declaration',
                'note': 'Exact parameters/source hashes retained; nominal C values precede grid rounding.'}
    params = generator_parameters(family, kind)
    levels = params['levels']
    result = {}
    for key, value in declaration['training_dimensions_m'].items():
        match = re.search(r'_l(\d+)(?=_)', key)
        level = match.group(1) if match else max(levels, key=int)
        raw_key = re.sub(r'_l\d+(?=_)', '', key)
        expected = (b.SIZE if family == 'B' and key == 'tile_size_m'
                    else levels.get(level, {}).get(raw_key))
        if expected is None:
            raise ValueError(f'no generator dimension for {family}/{kind}/{key}')
        if not math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f'declaration/code dimension mismatch: {family}/{kind}/{key} {value} != {expected}')
        result[key] = expected
    return {'state': 'code_matches', 'code_values': result}


def column_face_mask(centroids, *, columns, total_columns, size, rows, offset):
    # Isaac TerrainGenerator centres rows on x and columns on y. Safe spawn
    # origins may shift within a tile and must not be used as grid centres.
    sx, sy = size
    mask = np.zeros(len(centroids), dtype=bool)
    inside_x = (centroids[:, 0] >= -sx*rows/2) & (centroids[:, 0] < sx*rows/2)
    for col in columns:
        low = offset + (col-total_columns/2)*sy
        mask |= inside_x & (centroids[:, 1] >= low) & (centroids[:, 1] < low+sy)
    return mask


def hash_selected_faces(vertices, faces, mask):
    selected = faces[mask]
    if not len(selected):
        raise ValueError('empty kind geometry selection')
    indices, remapped = np.unique(selected, return_inverse=True)
    v = np.asarray(vertices[indices], dtype='<f4')
    f = np.asarray(remapped.reshape(-1, 3), dtype='<i4')
    return {'geometry_sha256': hashlib.sha256(v.tobytes()+f.tobytes()).hexdigest(),
            'vertex_count': len(v), 'face_count': len(f),
            'bounds_m': [v.min(0).tolist(), v.max(0).tolist()]}


def assemble_saved_mesh(plan, mesh_dir, declarations, declaration_paths):
    mesh_dir = Path(mesh_dir).resolve(strict=True)
    receipt_path = mesh_dir/'mesh_manifest.json'
    aggregate_path = mesh_dir/'aggregate_measurements.json'
    receipt, measurements = read_object(receipt_path), read_object(aggregate_path)
    if (receipt.get('format') != 'foothold-ex42-combined-mesh/1'
            or receipt.get('training_started') is not False or receipt.get('families_missing') != []
            or receipt.get('join_axis') != 1):
        raise ValueError('complete non-training column-joined mesh receipt required')
    contract = plan.document['terrain_manifest_contract']
    check_measurements(measurements, receipt, contract['required_measurements'])
    pinned = plan.document['assumptions_pending_lead']['terrain_manifest_measurements']['value']
    if receipt['mesh_sha256'] != pinned['mesh_sha256']:
        raise ValueError('mesh identity differs from the plan measurement pin')
    if any(measurements[key] != pinned[key] for key in contract['required_measurements']):
        raise ValueError('aggregate differs from the plan measurement pin')
    if ('mesh_file_sha256' in receipt
            and sha_file(mesh_dir/'terrain_mesh.npz') != receipt['mesh_file_sha256']):
        raise ValueError('saved mesh file SHA differs from measurement receipt')
    annotation = None
    if 'flag_annotation_source' in receipt:
        from foothold_s2.tools.ex42_mesh_flags import verify_annotation
        annotation = verify_annotation(mesh_dir)
    mesh = load_combined_mesh(mesh_dir/'terrain_mesh.npz', receipt['mesh_sha256'])
    actual_counts = dict(Counter(mesh['column_family']))
    if actual_counts != receipt['columns_by_family'] or list(mesh['origins'].shape) != receipt['origins_shape']:
        raise ValueError('saved mesh layout differs from measurement receipt')
    inventory = generator_inventory()
    if {k: len(v) for k, v in inventory.items()} != contract['kind_count_by_family']:
        raise ValueError('generator inventory differs from plan')
    extra = {(f, k) for f, kinds in declarations.items() for k in kinds
             if f not in inventory or k not in inventory[f]}
    if extra:
        raise ValueError(f'unknown declaration kinds: {sorted(extra)}')
    if actual_counts != {'A': columns.FULL_COLS, 'B': len(b.KINDS), 'C': len(c.KINDS),
                         'D': len(d.KINDS), 'E': len(ex42.PAPER_EXT_SPECS)}:
        raise ValueError('saved mesh columns cannot be mapped to generator inventory')
    sizes = {'A': rough_parameters()[1], 'B': (b.SIZE, b.SIZE), 'C': (c.SIZE, c.SIZE),
             'D': d.TILE_SIZE, 'E': rough_parameters()[1]}
    # Accumulate vertex coordinates without materializing a faces x 3 x 3 array.
    vertices, faces = mesh['vertices'], mesh['faces']
    centres = sum(vertices[faces[:, i]].astype(np.float64) for i in range(3))/3
    geometry = {}
    for family, count in actual_counts.items():
        names = family_column_kinds(family, count)
        if len(names) != count or None in names or set(names) != set(inventory[family]):
            raise ValueError(f'incomplete generator column mapping: {family}')
        global_columns = [i for i, f in enumerate(mesh['column_family']) if f == family]
        if global_columns != list(range(global_columns[0], global_columns[0]+count)):
            raise ValueError(f'noncontiguous family columns: {family}')
        for kind in inventory[family]:
            local = [i for i, name in enumerate(names) if name == kind]
            selected = column_face_mask(centres, columns=local, total_columns=count,
                    size=sizes[family], rows=len(mesh['origins']), offset=receipt['offsets_m'][family])
            geometry[family, kind] = hash_selected_faces(vertices, faces, selected) | {
                'columns': [global_columns[i] for i in local],
                'rows': list(range(len(mesh['origins']))),
                'scope': 'saved mesh faces with centroid in kind columns; generator outer border excluded',
                'hash_encoding': 'sorted source vertex indices; little-endian float32 vertices + remapped int32 faces'}
    rows, missing = [], []
    for family, kinds in inventory.items():
        for kind in kinds:
            declaration = declarations.get(family, {}).get(kind)
            gaps = declaration_errors(declaration)
            preset = plan.document['environment']['training_presets'].get(family)
            if not isinstance(preset, str) or not preset:
                gaps.append('plan.training_presets.'+family)
            elif isinstance(declaration, dict) and declaration.get('preset_id') != preset:
                gaps.append('preset_id differs from plan')
            if gaps:
                missing.append({'family': family, 'kind': kind, 'fields': sorted(set(gaps)),
                                'available_generator_parameters': generator_parameters(family, kind)})
                continue
            source_family = 'A' if family == 'continuous' else family
            geom = geometry[source_family, kind]
            rows.append(copy.deepcopy(declaration) | {'family': family, 'kind': kind,
                'geometry_sha256': geom['geometry_sha256'], 'geometry_selection': geom,
                'generator_parameters': generator_parameters(family, kind),
                'dimension_crosscheck': dimension_crosscheck(family, kind, declaration),
                'dimension_scope': 'owner-declared nominal dimensions; exact code parameters recorded separately',
                'geometry_family': source_family})
    source_files = [TERRAINS/name for name in SOURCE_FILES]
    source_files += [REPO/'foothold_s2/eval/start_sheet.py',
                     REPO/'foothold_s2/scripts/ex42_mesh_build.py']
    manifest = {'format': 'foothold-ex42-terrain-manifest/1',
        'status': 'partial' if missing else 'measured',
        'training_presets': copy.deepcopy(plan.document['environment']['training_presets']),
        'measurements': measurements, 'kinds': rows,
        'receipt_ids': ['combined-mesh:'+mesh['mesh_sha256'], 'aggregate:'+sha_file(aggregate_path)],
        'family_counts_expected': contract['kind_count_by_family'],
        'family_counts_observed': dict(Counter(row['family'] for row in rows)),
        'missing_declarations': missing,
        'blockers': ['declarations_missing_or_invalid'] if missing else [],
        'provenance': {
            'mesh_directory': str(mesh_dir), 'mesh_sha256': mesh['mesh_sha256'],
            'mesh_file_sha256': sha_file(mesh_dir/'terrain_mesh.npz'),
            'mesh_manifest_sha256': sha_file(receipt_path),
            'aggregate_sha256': sha_file(aggregate_path), 'plan_sha256': plan.sha256,
            'declarations': [{'path': str(Path(p).resolve()), 'sha256': sha_file(p)} for p in declaration_paths],
            'generator_sources': {str(p.relative_to(REPO)): sha_file(p) for p in source_files},
            'source_scope': 'reader/inventory/parameter sources, not an attestation of the historical mesh build HEAD',
            'seed': receipt['seed'], 'measurement_device': receipt['device'],
            'measurement_scope': 'combined mesh aggregate; not independent per-kind timing or real sensor timing',
            'ray_measurement': receipt.get('ray_measurement'),
            'memory_measurement': receipt.get('memory_measurement'),
            'continuous_alias_scope': 'seven A columns/kinds reused, not seven additional measured kinds',
            'evaluation_geometry_measured': False, 'cpu_readback_only': True,
            'training_started': False}}
    if annotation is not None:
        manifest['provenance']['flag_annotation'] = annotation
        manifest['provenance']['measurement_scope'] += (
            '; inherited from byte-identical source geometry, no new Kit run for added flags')
    if not missing:
        plan.validate_terrain_manifest(manifest)
    return manifest


def write_once(path, value):
    """Atomic publication without replacing an earlier, different receipt."""
    path = Path(path)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n').encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == raw:
            return
        raise FileExistsError(f'refuse to replace different artifact: {path}')
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', suffix='.pending', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp, path)  # fails if another writer published first
    finally:
        os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--table', type=Path, default=REPO/'foothold_s2/curriculum/ex42-prep.yaml')
    parser.add_argument('--mesh-dir', type=Path, required=True)
    parser.add_argument('--declarations', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    plan = EX42Plan.load(args.table)
    manifest = assemble_saved_mesh(plan, args.mesh_dir, read_declarations(args.declarations), args.declarations)
    write_once(args.output, manifest)
    print(json.dumps({'status': manifest['status'], 'kinds': len(manifest['kinds']),
        'missing': [{'family': r['family'], 'kind': r['kind'], 'fields': r['fields']}
                    for r in manifest['missing_declarations']],
        'mesh_sha256': manifest['provenance']['mesh_sha256'],
        'output': str(args.output.resolve()), 'sha256': sha_file(args.output)}, ensure_ascii=False))
    return 0 if manifest['status'] == 'measured' else 2


if __name__ == '__main__':
    raise SystemExit(main())
