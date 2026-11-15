"""CPU-only additive flags for an existing measured mesh, into a NEW folder.

No geometry is rebuilt. Original measurements are copied as inherited evidence,
not a new Kit run. The execution terrain_manifest must be regenerated separately
so old approval/file hashes cannot silently bind to this new NPZ.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from foothold_s2.terrains import ame2_preset, jeplo_preset, hipan_posture, sparse_terrains
from foothold_s2.terrains.ex42_column_reset import family_column_kinds
from foothold_s2.terrains.ex42_mesh_mount import load_combined_mesh
from foothold_s2.terrains.ex42_flag_producer import family_flags, combine_flags
from foothold_s2.scripts.ex42_mesh_build import write_mesh_arrays


def _sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_annotation(destination):
    """Read back both artifacts; flags cannot authorize changed geometry or measurements.

    Geometry SHA covers vertices/faces only. Compare every original array including
    origins and column order, and bind the copied measurements to their real source.
    This is CPU evidence, never a new Kit measurement or launch approval.
    """
    from foothold_s2.terrains.columns import CONTINUOUS
    from foothold_s2.terrains.ex42_column_reset import build_column_table
    from foothold_s2.terrains.ex42_flags import load_flag_table

    destination = Path(destination).resolve(strict=True)
    receipt = json.loads((destination/'mesh_manifest.json').read_text(encoding='utf-8'))
    inherited = receipt['flag_annotation_source']
    source = Path(inherited['folder']).resolve(strict=True)
    if source == destination or any(inherited.get(key) is not value for key, value in {
            'geometry_preserved': True, 'measurements_inherited': True,
            'new_kit_validation': False, 'execution_manifest_regeneration_required': True}.items()):
        raise ValueError('flag annotation must preserve the measured source and require a new execution manifest')
    for key, filename, label in [('manifest_sha256', 'mesh_manifest.json', 'source manifest'),
                                 ('npz_sha256', 'terrain_mesh.npz', 'source NPZ')]:
        if _sha(source/filename) != inherited.get(key):
            raise ValueError(f'{label} SHA mismatch')
    old = json.loads((source/'mesh_manifest.json').read_text(encoding='utf-8'))
    aggregate = old['aggregate_file']
    if (Path(aggregate).name != aggregate or aggregate != receipt['aggregate_file']
            or (source/aggregate).read_bytes() != (destination/aggregate).read_bytes()):
        raise ValueError('inherited aggregate differs from the source measurement')
    npz = destination/'terrain_mesh.npz'
    file_sha = _sha(npz)
    if file_sha != receipt.get('mesh_file_sha256'):
        raise ValueError('annotated NPZ file SHA mismatch')
    with np.load(source/'terrain_mesh.npz', allow_pickle=False) as a, np.load(npz, allow_pickle=False) as b:
        if 'flags' in a.files or set(b.files) != set(a.files) | {'flags'}:
            raise ValueError('annotation may only add flags to the original NPZ members')
        for key in a.files:
            before, after = a[key], b[key]
            if (before.dtype != after.dtype or before.shape != after.shape
                    or before.tobytes() != after.tobytes()):
                raise ValueError(f'original array changed: {key}')
        unchanged = sorted(a.files)
    geometry = load_combined_mesh(npz, old['mesh_sha256'])
    if geometry['mesh_sha256'] != receipt['mesh_sha256']:
        raise ValueError('annotation geometry SHA differs')
    rows, columns = geometry['origins'].shape[:2]
    flags = load_flag_table(npz, rows, columns)
    if flags is None:
        raise ValueError('annotated flags missing')
    table = build_column_table(geometry['column_family'])
    for col, kind in enumerate(table):
        fallback = kind['family'] == 'A' and kind['kind'] in CONTINUOUS
        valid = np.isnan(flags[:, col]).all() if fallback else np.isfinite(flags[:, col]).all()
        if kind['kind'] is None or not valid:
            raise ValueError(f'flags do not cover the declared kind: column {col}')
    return dict(inherited, source=str(source), mesh_file_sha256=file_sha,
                mesh_sha256=geometry['mesh_sha256'], original_arrays_unchanged=unchanged,
                aggregate_sha256=_sha(destination/aggregate), flags_shape=list(flags.shape),
                flags_sha256=hashlib.sha256(flags.tobytes()).hexdigest(), flags_bytes=flags.nbytes,
                finite_cells=int(np.isfinite(flags).all(axis=(2, 3)).sum()),
                fallback_cells=int(np.isnan(flags).all(axis=(2, 3)).sum()))


def annotate(source, destination):
    source, destination=Path(source).resolve(),Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    manifest_path=source/'mesh_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('format')!='foothold-ex42-combined-mesh/1' or manifest.get('join_axis')!=1:
        raise ValueError('only the measured, column-joined combined mesh is supported')
    source_npz=source/'terrain_mesh.npz';source_sha=_sha(source_npz)
    if manifest.get('mesh_file_sha256',source_sha)!=source_sha:
        raise ValueError('source NPZ SHA mismatch')
    data=load_combined_mesh(source_npz,manifest['mesh_sha256'])
    if list(data['origins'].shape)!=manifest['origins_shape']:
        raise ValueError('source origins shape differs from receipt')
    names=data['column_family'];families=list(dict.fromkeys(names))
    if families!=manifest['families_present']:
        raise ValueError('source family order differs from receipt')
    sizes={'A':sparse_terrains.TILE,'B':(ame2_preset.SIZE,)*2,
           'C':(jeplo_preset.SIZE,)*2,'D':hipan_posture.TILE_SIZE,'E':sparse_terrains.TILE}
    centroid=data['vertices'][data['faces']][:,:,:2].mean(1)
    parts=[];col=0;started=time.perf_counter()
    for family in families:
        count=names.count(family);kinds=family_column_kinds(family,count)
        if (family not in sizes or len(kinds)!=count or any(k is None for k in kinds)
                or names[col:col+count]!=[family]*count
                or manifest['columns_by_family'].get(family)!=count):
            raise ValueError('unknown/reordered family layout cannot be inferred')
        size=sizes[family];shift=float(manifest['offsets_m'][family]);width=count*size[1]
        if not np.isfinite(shift):
            raise ValueError('nonfinite family offset')
        # Outside borders are excluded; all original arrays remain untouched.
        keep=(centroid[:,1]>=shift-width/2)&(centroid[:,1]<shift+width/2)
        vertices=data['vertices'].astype(np.float64);vertices[:,1]-=shift
        origins=data['origins'][:,col:col+count].copy();origins[:,:,1]-=shift
        flags,meta=family_flags(vertices,data['faces'][keep],origins,family,kinds,size)
        parts.append(dict(name=family,origins=origins,flags=flags,flag_metadata=meta))
        col+=count
    flags,provenance=combine_flags(parts,{'axis':1,'offsets':manifest['offsets_m']})
    elapsed=time.perf_counter()-started
    # Check every source receipt before publishing any output.
    aggregate_name=manifest['aggregate_file']
    if Path(aggregate_name).name!=aggregate_name:
        raise ValueError('aggregate_file must be a sibling filename')
    aggregate_bytes=(source/aggregate_name).read_bytes()
    if 'flag_provenance' in manifest:
        raise ValueError('source already carries flags; use the original source for a new revision')
    destination.mkdir(parents=True,exist_ok=False)
    write_mesh_arrays(destination/'terrain_mesh.npz',data,flags)
    (destination/aggregate_name).write_bytes(aggregate_bytes)
    manifest.update(flag_provenance=provenance,flag_generation_seconds=elapsed,
        mesh_file_sha256=_sha(destination/'terrain_mesh.npz'),
        flag_annotation_source={'folder':str(source),'manifest_sha256':_sha(manifest_path),
            'npz_sha256':source_sha,'geometry_preserved':True,'measurements_inherited':True,
            'new_kit_validation':False,'execution_manifest_regeneration_required':True})
    (destination/'mesh_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,
        indent=2,allow_nan=False)+'\n',encoding='utf-8')
    verify_annotation(destination)
    return manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--table',type=Path,
                        help='Optional execution plan; requires --declarations. No approval is modified.')
    parser.add_argument('--declarations',type=Path,action='append',
                        help='Publish terrain_manifest after original measurement/pin validation.')
    args=parser.parse_args(argv)
    if bool(args.table) != bool(args.declarations):
        parser.error('--table and --declarations must be supplied together')
    result=annotate(args.source,args.out)
    summary={key:result[key] for key in ('mesh_sha256','mesh_file_sha256','flag_generation_seconds')}
    if args.table:
        from foothold_s2.tools.ex42_execution_manifest import (
            EX42Plan, assemble_saved_mesh, read_declarations, write_once)
        plan=EX42Plan.load(args.table)
        execution=assemble_saved_mesh(plan,args.out,read_declarations(args.declarations),args.declarations)
        plan.validate_terrain_manifest(execution)
        path=args.out/'terrain_manifest.json'
        write_once(path,execution)
        summary['terrain_manifest_sha256']=_sha(path)
    print(json.dumps(summary))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
