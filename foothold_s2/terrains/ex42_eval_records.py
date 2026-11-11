"""Remaining fixed record columns from CG:393 and E.8, never training presets.

Target heights/widths are canonical. Carrier placement is an explicit evaluation
layout, not a claim to reproduce the paper scene or a demonstrated Go2 ability.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

BEAM_RECORDS = ('eval_balance_090', 'eval_balance_0765')
STAIR_RECORDS = ('eval_stairs_027', 'eval_stairs_030')
PHYSICAL_RECORDS = ('gap_090', 'gap_100', 'climb_down_075', 'climb_down_088',
                    'consecutive_040', 'high_ledge_075', 'crawl_020')
KINDS = BEAM_RECORDS + STAIR_RECORDS + PHYSICAL_RECORDS
REVERSE_CASES = {'eval_stairs_015_reverse': 'eval_stairs_015',
                 'eval_stairs_020_reverse': 'eval_stairs_020'}


def case_contract(case_id):
    """Consumer metadata only; applying yaw/commands remains the evaluator's job.

Forward and reverse cases use the same saved triangles. A reverse ascent faces
away from the stairs (yaw pi) and commands negative body vx from the approach.
"""
    from . import ex42_eval_terrains as et
    geometry = REVERSE_CASES.get(case_id, case_id)
    if geometry not in et.KINDS:
        raise ValueError('unknown evaluation case')
    role, stage = 'record', None
    if case_id == et.LANDING:
        role, stage = 'judge', 'E1'
    elif case_id in ('eval_stairs_010','eval_stairs_015','eval_stairs_020',
                     'eval_stairs_025','eval_slope_30','eval_slope_35'):
        role, stage = 'judge', 'E4'
    reverse = case_id in REVERSE_CASES or case_id == 'eval_stairs_010'
    return {'case_id':case_id, 'geometry_id':geometry, 'role':role,
            'judge_from_stage':stage, 'training_allowed':False,
            'body_command_vx_sign':-1 if reverse else None,
            'approach_yaw_rad':math.pi if reverse else 0.,
            'source':et._source([392,393,394,590,591,592])}


def build_tile(kind, *, seed):
    from . import ex42_eval_terrains as et
    from . import hipan_posture as hp
    if kind not in KINDS or kind in STAIR_RECORDS:
        raise ValueError('record builder requires a non-stair record kind')
    boxes = [(0.,8.,0.,8.,-.2,0.)]
    origin = np.array([.5,4.,0.])
    anchors = {'approach':origin.tolist(), 'goal':[7.5,4.,0.]}
    dims = {'role':'record'}
    assumptions = {'layout':'fixed 8 x 8 m evaluation carrier',
                   'training_exposure':0, 'not_a_paper_scene_reproduction':True}
    lines = [593,594,595,596,599]
    if kind in BEAM_RECORDS or kind.startswith('gap_'):
        base = 'balance_beams' if kind in BEAM_RECORDS else 'gaps'
        kind_seed = int.from_bytes(hashlib.sha256(f'{seed}:{base}'.encode()).digest()[:8],'little')
        rng = np.random.default_rng(kind_seed)
        depth = float(rng.uniform(*et.ss.DEPTH_RANGE))
        boxes = et.sparse._frame(depth)
        bottom = -depth-et.ss.FLOOR_THICKNESS
        dims.update(depth_m=depth,kind_seed=kind_seed)
        if base == 'balance_beams':
            width = .09 if kind == 'eval_balance_090' else .09*.85
            z = float(rng.uniform(-et.ss.HEIGHT_JITTER,et.ss.HEIGHT_JITTER))
            boxes.append((1.,7.,4-width/2,4+width/2,bottom,z))
            dims.update(beam_width_m=width,support_height_m=z,beam_length_m=6.)
            assumptions['layout_source']='sparse_terrains._frame and CG:393 width ladder; same kind RNG as START variants'
            lines=[393,595]
        else:
            width = .9 if kind == 'gap_090' else 1.
            count = et.ss.N_GAPS
            support=(6-count*width)/(count+1)
            for i in range(count+1):
                x=1+i*(support+width)
                boxes.append((x,x+support,0.,8.,bottom,0.))
            dims.update(gap_width_m=width,count=count,platform_length_m=support)
            assumptions['layout_source']='start_sheet.N_GAPS=3 in ZONE_X=(1,7), same kind RNG depth; absolute gap width from CG:592'
            lines=[592,625]
    elif kind.startswith('climb_down_'):
        height = .75 if kind == 'climb_down_075' else .88
        boxes.append((0.,4.,0.,8.,0.,height))
        # Root x=1 keeps the full 1.6 m scanner over the initial high support.
        origin=np.array([1.,4.,height])
        anchors['approach']=origin.tolist()
        anchors['drop_edge_x']=4.
        dims.update(ledge_height_m=height,direction='down')
        assumptions['layout_source']='hipan_posture half-tile ledge, inverted; 1 m start for scanner footprint'
        lines=[594]
    elif kind == 'high_ledge_075':
        boxes.append((4.,8.,0.,8.,0.,.75))
        anchors.update(ledge_edge_x=4.,landing_center=[6.,4.,.75],goal=[7.5,4.,.75])
        dims.update(ledge_height_m=.75,direction='up')
        assumptions['layout_source']='hipan_posture high_ledge rear half layout; CG:593 absolute target'
        lines=[360,593,625]
    elif kind == 'consecutive_040':
        # Same 0,a,a+b,a,0 pattern as AME-2. Only horizontal carrier placement
        # is adapted from its 12 m tile to the existing 8 m evaluation carrier.
        boxes=[]
        edges=np.linspace(0.,8.,6)
        for a,b,z in zip(edges[:-1],edges[1:],(0.,.4,.8,.4,0.)):
            boxes.append((float(a),float(b),0.,8.,-.2,z))
        dims.update(rise_m=.4,top_height_m=.8,plateau_length_m=1.6)
        assumptions['layout_source']='ame2_preset consecutive five-plateau pattern; 12 m carrier scaled horizontally to 8 m (layout assumption)'
        lines=[598]
    else:
        roof=hp.DEFAULT_THICKNESS_M
        boxes.append((2.,6.,0.,8.,.20,.20+roof))
        dims.update(ceiling_clearance_m=.20,roof_thickness_m=roof)
        anchors['tunnel_exit_x']=6.
        assumptions['layout_source']='hipan_posture crawl roof over middle half; CG:599 clearance'
        lines=[360,599,625]
    return et.EvalTile(kind,et._mesh_boxes(boxes),origin,anchors,dims,
                       [et._source(lines)],0,seed,assumptions)
