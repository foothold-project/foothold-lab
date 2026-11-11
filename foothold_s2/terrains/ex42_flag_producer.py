"""Four supported goals from the actual generated triangles, without RNG replay.

A continuous columns retain their existing straight-line fallback. A sparse
targets follow sparse_terrains.FLAG_X. B/C/D/E routing is a project assumption:
four progressing targets on real support; D wall uses its +y bypass and crawl
uses the floor below the roof. These are goals, not a collision-free motion
plan, foothold sequence, or evidence that the robot can complete the course.
"""
from __future__ import annotations

import hashlib
import numpy as np

FORMAT = 'foothold-ex42-flags/1'
COUNT = 4


def _barycentric(tri, point):
    a=tri[:,0,:2];u=tri[:,1,:2]-a;v=tri[:,2,:2]-a
    d=np.asarray(point)-a
    det=u[:,0]*v[:,1]-u[:,1]*v[:,0]
    s=(d[:,0]*v[:,1]-d[:,1]*v[:,0])/det
    t=(u[:,0]*d[:,1]-u[:,1]*d[:,0])/det
    return s,t


def _nearest_xy(tri, point):
    """Closest point in each triangle's XY projection, moved just inside it."""
    s,t=_barycentric(tri,point)
    inside=(s>=0)&(t>=0)&(s+t<=1)
    candidates=[]
    for i,j in ((0,1),(1,2),(2,0)):
        a=tri[:,i,:2];edge=tri[:,j,:2]-a
        fraction=np.clip(((point-a)*edge).sum(1)/(edge*edge).sum(1),0,1)
        candidates.append(a+fraction[:,None]*edge)
    candidates=np.stack(candidates,axis=1)
    best=((candidates-point)**2).sum(2).argmin(1)
    xy=candidates[np.arange(len(tri)),best]
    xy[inside]=point
    # Layout assumption: stay inside a triangle instead of on a cliff edge.
    return .99*xy+.01*tri[:,:,:2].mean(1)


def _top(tri, point):
    s,t=_barycentric(tri,point)
    hit=(s>=-1e-7)&(t>=-1e-7)&(s+t<=1+1e-7)
    z=tri[:,0,2]+s*(tri[:,1,2]-tri[:,0,2])+t*(tri[:,2,2]-tri[:,0,2])
    return float(z[hit].max()) if hit.any() else float('nan')


def tile_flags(family, kind, triangles, origin, size):
    """Return local (4,2) metres and auditable support heights/rule metadata."""
    from foothold_s2.terrains import columns, sparse_terrains
    from foothold_s2.terrains import ame2_preset, jeplo_preset, hipan_posture, ex42, jump_preset
    kinds = {'A': set(columns.FULL), 'B': set(ame2_preset.KINDS),
             'C': set(jeplo_preset.KINDS), 'D': set(hipan_posture.KINDS),
             'E': {spec.kind for spec in ex42.PAPER_EXT_SPECS}, 'F': set(jump_preset.KINDS)}
    if family not in kinds or kind not in kinds[family]:
        raise ValueError(f'unknown flag family/kind: {family}/{kind}')
    if family=='A' and kind in columns.CONTINUOUS:
        return np.full((COUNT,2),np.nan), {'rule':'existing_continuous_straight','grade':'code'}
    origin=np.asarray(origin,dtype=float);size=np.asarray(size,dtype=float)
    tri=np.asarray(triangles,dtype=float)
    if (origin.shape!=(3,) or size.shape!=(2,) or tri.ndim!=3 or tri.shape[1:]!=(3,3)
            or not np.isfinite(tri).all() or not np.isfinite(origin).all()
            or not np.isfinite(size).all() or (size<=0).any()):
        raise ValueError('invalid flag geometry')
    normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    tri=tri[normals[:,2]>1e-10]
    if not len(tri):
        raise ValueError(f'{family}/{kind}: no upward support')
    if family == 'F':
        # Fixed approach/exit goals, never projected into a gap or onto a pit
        # floor. Fail loudly if the actual mesh does not support the contract.
        targets = jump_preset.desired_flags(size)
        heights = [_top(tri, point) for point in targets]
        if (not np.isfinite(heights).all() or min(heights) < -1e-6
                or (targets < 0).any() or (targets >= size).any()
                or targets[0,0] <= origin[0] or np.diff(targets[:,0]).min() <= .02):
            raise ValueError(f'F/{kind}: missing progressing approach/exit support')
        return targets, {'rule':'jump_approach_exit_support_goals', 'grade':'project_assumption',
                         'support_z_m':heights, 'desired_xy_m':targets.tolist(),
                         'goal_count':COUNT, 'not_a_motion_plan':True}
    # D crawl has two upward surfaces. The known floor at origin.z is the
    # support; a top-down height scan of the roof is not the support here.
    if family=='D' and kind=='crawl':
        tri=tri[np.max(np.abs(tri[:,:,2]-origin[2]),axis=1)<1e-5]
    if not len(tri):
        raise ValueError(f'{family}/{kind}: no floor support')
    pool=tri
    if family=='A' and kind in sparse_terrains.KINDS and kind!='flat':
        pool=tri[tri[:,:,2].mean(1)>tri[:,:,2].min()+.15]
    elif family=='C' and kind=='gap':
        pool=tri[tri[:,:,2].min(1)>-.15]
    elif family=='B' and kind in ('gap','pallets','stones','beam'):
        # Optional physical pit floor spans the whole tile. Virtual-floor
        # tiles have no such face; never infer their floor from a support.
        broad=(np.ptp(tri[:,:,0],axis=1)>.9*size[0])&(np.ptp(tri[:,:,1],axis=1)>.9*size[1])
        flat=np.ptp(tri[:,:,2],axis=1)<1e-7
        floor=tri[broad&flat,:,2]
        if len(floor):
            floor_z=float(floor.min())
            pool=tri[tri[:,:,2].max(1)>floor_z+1e-5]
    elif family=='B' and kind=='obstacles':
        pool=tri[np.max(np.abs(tri[:,:,2]),axis=1)<1e-5]
    if not len(pool):
        raise ValueError(f'{family}/{kind}: no usable support')
    rule='four_progressing_support_goals'
    xs=np.linspace(origin[0]+.5,size[0]-.75,COUNT)
    targets=np.column_stack((xs,np.full(COUNT,origin[1])))
    if family=='A':
        targets=np.column_stack((sparse_terrains.FLAG_X,np.full(COUNT,size[1]/2)))
        rule='start_flag_x_projected_to_actual_mesh'
    if family=='D' and kind=='wall':
        # The source wall is the only elevated component. Read its actual
        # end and x faces, so non-default caller dimensions remain correct.
        wall=tri[tri[:,:,2].mean(1)>origin[2]+.1]
        if not len(wall):
            raise ValueError('D/wall: elevated wall missing')
        edge=wall[:,:,:2].reshape(-1,2)
        x0,x1=edge[:,0].min(),edge[:,0].max()
        y1=edge[:,1].max();corridor=size[1]-y1
        if corridor<=0:
            raise ValueError('D/wall: no bypass corridor')
        targets=np.array([[x0-.5,y1+corridor/2],[x1+.5,y1+corridor/2],
                          [x1+1.5,origin[1]],[size[0]-.75,origin[1]]])
        rule='wall_actual_plus_y_bypass'
        pool=tri[np.max(np.abs(tri[:,:,2]-origin[2]),axis=1)<1e-5]
    points=[];heights=[];previous=float(origin[0])
    for target in targets:
        projected=_nearest_xy(pool,target)
        candidates=np.concatenate((projected,pool[:,:,:2].mean(1)))
        distance=((candidates-target)**2).sum(1)
        order=np.argsort(distance,kind='stable')
        selected=None
        for idx in order:
            xy=candidates[idx]
            if (xy[0]<=previous+.02 or (xy<0).any() or (xy>=size).any()
                    or distance[idx]>(size[0]/4)**2):
                continue
            support=_top(pool,xy);actual=_top(tri,xy)
            if np.isfinite(support) and abs(support-actual)<1e-5:
                selected=(xy.copy(),support);break
        if selected is None:
            raise ValueError(f'{family}/{kind}: no progressing support near {target.tolist()}')
        xy,z=selected;points.append(xy);heights.append(z);previous=float(xy[0])
    return np.asarray(points), {'rule':rule,'grade':'project_assumption',
        'support_z_m':heights,'desired_xy_m':targets.tolist(),
        'goal_count':COUNT,'not_a_motion_plan':True}


def family_flags(vertices, faces, origins, family, kinds, size):
    """Read a centered Isaac family grid without changing a triangle or RNG."""
    o=np.asarray(origins,dtype=float)
    if o.ndim!=3 or o.shape[2]!=3 or o.shape[1]!=len(kinds):
        raise ValueError('flag kinds/origin shape differs')
    rows,cols=o.shape[:2];sx,sy=size
    tri=np.asarray(vertices,dtype=float)[np.asarray(faces,dtype=np.int64)]
    centroids=tri[:,:,:2].mean(1)
    rr=np.floor((centroids[:,0]+rows*sx/2)/sx).astype(int)
    cc=np.floor((centroids[:,1]+cols*sy/2)/sy).astype(int)
    valid=(rr>=0)&(rr<rows)&(cc>=0)&(cc<cols)
    ids=np.flatnonzero(valid);keys=rr[ids]*cols+cc[ids]
    order=np.argsort(keys,kind='stable');ids=ids[order];keys=keys[order]
    flags=np.full((rows,cols,COUNT,2),np.nan,dtype=np.float32);metadata=[]
    for row in range(rows):
        for col,kind in enumerate(kinds):
            key=row*cols+col;lo,hi=np.searchsorted(keys,[key,key+1])
            offset=np.array([(row-rows/2)*sx,(col-cols/2)*sy,0.])
            local=tri[ids[lo:hi]]-offset
            xy,meta=tile_flags(family,kind,local,o[row,col]-offset,size)
            flags[row,col]=xy+offset[:2]
            metadata.append({'row':row,'local_column':col,'family':family,'kind':kind,
                             'tile_offset_m':offset.tolist(),**meta})
    return flags,metadata


def combine_flags(parts, combined):
    arrays=[];cells=[];column=0
    for part in parts:
        flags=np.asarray(part['flags'],dtype=np.float32).copy()
        if flags.shape!=(*np.asarray(part['origins']).shape[:2],COUNT,2):
            raise ValueError('family flags shape differs')
        flags[...,combined['axis']]+=combined['offsets'][part['name']]
        arrays.append(flags)
        cells.extend([{**m,'column':column+m['local_column']} for m in part['flag_metadata']])
        column+=flags.shape[1]
    flags=np.concatenate(arrays,axis=1)
    finite=np.isfinite(flags).all(axis=(2,3));missing=np.isnan(flags).all(axis=(2,3))
    if not (finite|missing).all():
        raise ValueError('partial or infinite flag cell')
    return flags,{'format':FORMAT,'coordinates':'world_xy_m','shape':list(flags.shape),
        'sha256':hashlib.sha256(flags.tobytes()).hexdigest(),
        'finite_cells':int(finite.sum()),'straight_fallback_cells':int(missing.sum()),'cells':cells}
