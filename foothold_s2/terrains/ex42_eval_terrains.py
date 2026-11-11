"""Fixed evaluation-only geometry. No training registry or training mesh writes.

Canonical task dimensions: CURRICULUM-GATES lines 229, 393, 394, 600 at
368d03e2061b505fc72ad73e9cd2527a766e7738. Layout choices absent from that
table are explicitly marked as assumptions in each column's provenance.
All fixed geometries have ONE row; START's nominal L9 is metadata, not row 9.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from foothold_s2.eval import start_sheet as ss
from foothold_s2.terrains import sparse_terrains as sparse
from foothold_s2.terrains import start_go2_v2 as train

FORMAT = 'foothold-ex42-evaluation-mesh/1'
CG_COMMIT = '368d03e2061b505fc72ad73e9cd2527a766e7738'
CG_PATH = 'inbox/jay/20261026-experiments/CURRICULUM-GATES.md'
SIZE = sparse.TILE
START_VARIANTS = ('start_go2_eval_gap115', 'start_go2_eval_sup085', 'start_go2_eval_both')
LANDING = 'eval_stairs_landing_016'
PAPER = tuple(f'eval_stairs_{n:03d}' for n in (10,15,20,25)) + tuple(f'eval_slope_{n}' for n in (30,35,45))
KINDS = (LANDING,) + PAPER + tuple(f'{v}__{k}' for v in START_VARIANTS for k in ss.KINDS)
RESET_RANGES = {k: {axis: (0.,0.) for axis in ('x','y','yaw')} for k in KINDS}


@dataclass
class EvalTile:
    kind: str
    mesh: object
    origin: np.ndarray
    anchors: dict
    dimensions: dict
    sources: list
    nominal_level: int
    seed: int
    layout_assumptions: dict


def _source(lines):
    return {'grade': 'project_decision', 'commit': CG_COMMIT, 'path': CG_PATH, 'lines': lines,
            'url': f'https://github.com/foothold-project/foothold-lab/blob/{CG_COMMIT}/{CG_PATH}#L{lines[0]}'}


def _mesh_boxes(boxes):
    import trimesh
    pieces = []
    for x0,x1,y0,y1,z0,z1 in boxes:
        if not (x1>x0 and y1>y0 and z1>z0):
            raise ValueError('nonpositive box dimensions')
        pieces.append(trimesh.creation.box((x1-x0,y1-y0,z1-z0),
            trimesh.transformations.translation_matrix(((x0+x1)/2,(y0+y1)/2,(z0+z1)/2))))
    return trimesh.util.concatenate(pieces)


def _stairs(kind, seed):
    landing = kind == LANDING
    rise = .16 if landing else int(kind.rsplit('_',1)[1])/100
    tread = .30  # CG:394, same existing stage_stairs tread.
    platform = 1.2 if landing else 3.0
    # Construct OUTWARD from the required platform. Isaac's platform_width is
    # only a lower-bound-like cfg input; its //+1 formula can shrink the surface.
    rings = round((6.0-platform)/(2*tread))
    top = (rings+1)*rise
    boxes = [(0.,8.,0.,8.,-.20,0.)]
    for k in range(rings+1):
        width = platform+2*k*tread
        boxes.append((4-width/2,4+width/2,4-width/2,4+width/2,-.20,top-k*rise))
    origin = np.array([4.,4.,top] if landing else [.5,4.,0.])
    anchors = {'approach':[.5,4.,0.], 'landing_center':[4.,4.,top],
               'landing_bounds_xy':[4-platform/2,4+platform/2,4-platform/2,4+platform/2],
               'stop_band_x':[1+2*tread,1+3*tread]}
    dims = {'step_height_m':rise,'tread_m':tread,'landing_depth_m':platform,
            'landing_width_m':platform,'riser_count':rings+1,'top_height_m':top}
    assumptions = {'square_landing_width_m':platform, 'layout':'concentric square stairs, 8 x 8 m carrier',
                   'outer_stair_width_m':6., 'ground_border_m':1.,
                   'reference':'rough_go2_cfg.py:21-22,34-36 platform 3 and tread .3; exact 1.2 square is evaluation layout'}
    return EvalTile(kind,_mesh_boxes(boxes),origin,anchors,dims,[_source([229,394,600])],0,seed,assumptions)


def _slope(kind, seed):
    import trimesh
    angle = int(kind.rsplit('_',1)[1])
    peak = 2*math.tan(math.radians(angle))
    # Analytic planar strips. No heightfield conversion / slope-threshold warp.
    xs, zs = [0.,1.,3.,5.,7.,8.], [0.,0.,peak,peak,0.,0.]
    v, f = [], []
    for a,b,za,zb in zip(xs,xs[1:],zs,zs[1:]):
        i=len(v)
        v.extend([(a,0.,za),(b,0.,zb),(b,8.,zb),(a,8.,za)])
        f.extend([(i,i+1,i+2),(i,i+2,i+3)])
    mesh = trimesh.Trimesh(vertices=v,faces=f,process=False)
    return EvalTile(kind,mesh,np.array([.5,4.,0.]),{'approach':[.5,4.,0.],'top':[4.,4.,peak]},
        {'slope_deg':angle,'horizontal_ramp_run_m':2.,'rise_m':peak,'top_flat_m':2.},[_source([394])],0,seed,
        {'layout':'straight up/down planar ramp, 8 x 8 m carrier; 1 m flat entry/exit',
         'top_flat_m':2.,'reference':'rough_go2_cfg.py:31-33 platform 2; run and borders are evaluation layout'})


def _start(kind, seed):
    variant, base = kind.split('__')
    gap_factor = 1.15 if variant in (START_VARIANTS[0],START_VARIANTS[2]) else 1.
    support_factor = .85 if variant in (START_VARIANTS[1],START_VARIANTS[2]) else 1.
    # Same seed stream for the same kind across the three variants, independent
    # of selected columns or their order. Height/randomness conventions unchanged.
    kind_seed = int.from_bytes(hashlib.sha256(f'{seed}:{base}'.encode()).digest()[:8],'little')
    rng = np.random.default_rng(kind_seed)
    depth = float(rng.uniform(*ss.DEPTH_RANGE))
    boxes = sparse._frame(depth)
    bottom = -depth-ss.FLOOR_THICKNESS
    lo, hi = ss.ZONE_X
    ylo,yhi = sparse.STRIP
    dims = {'depth_m':depth,'gap_factor':gap_factor,'support_factor':support_factor,
            'variant':variant,'base_kind':base,'kind_seed':kind_seed,'source_preset':'start_orig',
            'training_preset':'start_go2_v2','nominal_level':9,'applied_axes':[]}

    def add(x0,x1,y0,y1,jitter=True):
        z = float(rng.uniform(-ss.HEIGHT_JITTER,ss.HEIGHT_JITTER)) if jitter else 0.
        boxes.append((x0,x1,y0,y1,bottom,z))

    if base == 'gaps':
        gap = ss.GAP_WIDTH[1]*train.SCALE_X*gap_factor
        platform = ((hi-lo)-ss.N_GAPS*gap)/(ss.N_GAPS+1)
        if platform<=0:
            raise ValueError('gap variant has no support')
        x=lo
        for _ in range(ss.N_GAPS+1):
            add(x,x+platform,0.,8.,False)
            x+=platform+gap
        dims.update(gap_width_m=gap,platform_length_m=platform,count=ss.N_GAPS,applied_axes=['gap_x'])
    elif base == 'balance_beams':
        width=ss.BEAM_WIDTH[1]*train.SCALE_Y*support_factor
        add(lo,hi,4-width/2,4+width/2)
        dims.update(beam_width_m=width,beam_length_m=hi-lo,applied_axes=['support_y'],
                    training_L9_override_m=train.BEAM_WIDTH[1],
                    note='nominal scaled L9 baseline .154875, not training override .09; CG:393')
    elif base == 'stepping_beams':
        width=ss.STEP_BEAM_WIDTH[1]*train.SCALE_X*support_factor
        gap=ss.STEP_BEAM_GAP[1]*train.SCALE_X*gap_factor
        n=math.floor((hi-lo+gap)/(width+gap))
        x0=lo+((hi-lo)-(n*width+(n-1)*gap))/2
        for i in range(n):
            x=x0+i*(width+gap)
            add(x,x+width,ylo,yhi)
        dims.update(beam_thickness_m=width,gap_x_m=gap,count=n,applied_axes=['gap_x','support_x'])
    else:
        sx,sy = ss.STONE_SIZE[1]*train.SCALE_X,ss.STONE_SIZE[1]*train.SCALE_Y*support_factor
        gx,gy = ss.STONE_GAP_X[1]*train.SCALE_X*gap_factor,ss.STONE_GAP_Y[1]*train.SCALE_Y
        nx,ny = math.floor((hi-lo+gx)/(sx+gx)),math.floor((yhi-ylo+gy)/(sy+gy))
        ox=lo+((hi-lo)-(nx*sx+(nx-1)*gx))/2
        oy=ylo+((yhi-ylo)-(ny*sy+(ny-1)*gy))/2
        for c in range(nx):
            shift=float(rng.uniform(-ss.STONE_COLUMN_JITTER,ss.STONE_COLUMN_JITTER))*gx
            for r in range(ny):
                dx=float(rng.uniform(-ss.STONE_JITTER,ss.STONE_JITTER))*gx
                dy=float(rng.uniform(-ss.STONE_JITTER,ss.STONE_JITTER))*gy
                x=min(max(ox+c*(sx+gx)+shift+dx,lo),hi-sx)
                y=min(max(oy+r*(sy+gy)+dy,ylo),yhi-sy)
                add(x,x+sx,y,y+sy)
        dims.update(stone_x_m=sx,stone_y_m=sy,gap_x_m=gx,gap_y_m=gy,columns=nx,rows=ny,
                    jitter=ss.STONE_JITTER,column_jitter=ss.STONE_COLUMN_JITTER,
                    applied_axes=['gap_x','support_y'])
    return EvalTile(kind,_mesh_boxes(boxes),np.array([.5,4.,0.]),
        {'approach':[.5,4.,0.],'goal':[7.5,4.,0.],'completion_x':7.},dims,[_source([393])],9,seed,
        {'layout':'sparse_terrains.py:26-28,71-77: 8 x 8 carrier; central 8 x 4 strip',
         'randomness':'nominal L9 high randomness; actual stone gaps include jitter',
         'unchanged_fields':'pit depth, height jitter, stone x size and y gap, beam y length'})


def build_tile(kind, *, seed):
    if kind not in KINDS or type(seed) is not int or not 0<=seed<2**32:
        raise ValueError('known evaluation kind and explicit uint32 seed required')
    if kind.startswith('eval_stairs_'):
        return _stairs(kind,seed)
    if kind.startswith('eval_slope_'):
        return _slope(kind,seed)
    return _start(kind,seed)


def write_mesh(folder, *, kinds, seed):
    """CPU-only immutable output. Refuses existing destinations, even same seed.

Run with CUDA_VISIBLE_DEVICES='' so #636's RNG receipt covers only CPU and
does not initialize a live training GPU. No Kit or model is loaded here.
"""
    import trimesh
    import torch
    from foothold_s2.terrains.mesh_rng import seeded_mesh_rng
    if not kinds or len(set(kinds))!=len(kinds) or any(k not in KINDS for k in kinds):
        raise ValueError('unique, known evaluation columns required')
    if torch.cuda.is_available():
        raise ValueError("CPU builder requires CUDA_VISIBLE_DEVICES='' before Python starts")
    folder=Path(folder)
    if folder.exists():
        raise FileExistsError(folder)
    meshes, origins, columns = [], [], []
    with seeded_mesh_rng(seed) as receipt:
        for c,kind in enumerate(kinds):
            t=build_tile(kind,seed=seed)
            offset=np.array([0.,c*SIZE[1],0.])
            t.mesh.apply_translation(offset)
            origin=t.origin+offset
            meshes.append(t.mesh)
            origins.append(origin)
            columns.append({'column':c,'kind':kind,'family':'V','fixed_nominal_level':t.nominal_level,
                'origin_world_m':origin.tolist(),'tile_offset_m':offset.tolist(), 'tile_size_m':list(SIZE),
                'anchors_local_m':t.anchors,'dimensions':t.dimensions,'sources':t.sources,
                'layout_assumptions':t.layout_assumptions,'reset_ranges':RESET_RANGES[kind]})
        # Same 20 m exterior floor as rough_go2_cfg, needed by scanner rays
        # behind the x=.5 entry. Four OUTSIDE bands, never a floor across pits.
        width=len(kinds)*SIZE[1]
        meshes.append(_mesh_boxes([(-20.,0.,-20.,width+20.,-.2,0.),
            (8.,28.,-20.,width+20.,-.2,0.),(0.,8.,-20.,0.,-.2,0.),
            (0.,8.,width,width+20.,-.2,0.)]))
        mesh=trimesh.util.concatenate(meshes)
    vertices=np.asarray(mesh.vertices,dtype=np.float32)
    faces=np.asarray(mesh.faces,dtype=np.int32)
    folder.mkdir(parents=True,exist_ok=False)
    npz=folder/'terrain_mesh.npz'
    np.savez_compressed(npz,vertices=vertices,faces=faces,origins=np.array([origins]),
                        column_family=np.array(['V']*len(kinds)))
    source_paths=[Path(__file__),Path(train.__file__),Path(ss.__file__),Path(sparse.__file__)]
    root=Path(__file__).resolve().parents[2]
    doc={'format':FORMAT,'training_allowed':False,'seed':seed,'origins_shape':[1,len(kinds),3],
         'row_semantics':'one fixed geometry row; nominal START L9 is column metadata, not curriculum row',
         'mesh_sha256':hashlib.sha256(vertices.tobytes()+faces.tobytes()).hexdigest(),
         'mesh_file_sha256':hashlib.sha256(npz.read_bytes()).hexdigest(),'columns':columns,
         'exterior_border_m':20.,'border_source':'rough_go2_cfg.py:42-43; outside grid only, pits preserved',
         'rng_provenance':receipt,'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}}
    (folder/'mesh_manifest.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return doc
