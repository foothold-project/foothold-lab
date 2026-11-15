"""Deterministic diagnostic terrain. Isaac and trimesh are imported only when a scene is built."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ANSWER_PATH = Path(__file__).with_name("s2_scene_answer_a2.json")


def answer_bytes():
    return ANSWER_PATH.read_bytes()


def answer_sha256():
    return hashlib.sha256(answer_bytes()).hexdigest()


def answer():
    return json.loads(answer_bytes())


def oracle(kind: str, xy):
    """Return world-local hit z, finite mask and distance to nearest relevant edge."""
    spec = answer()
    xy = np.asarray(xy, dtype=float)
    x, y = xy[..., 0], xy[..., 1]
    z = np.zeros(x.shape, dtype=float)
    finite = np.ones(x.shape, dtype=bool)
    edge = np.full(x.shape, np.inf, dtype=float)
    def rect_distance(rect):
        x0,x1=rect["x_range"];y0,y1=rect["y_range"]
        inside=(x>=x0)&(x<=x1)&(y>=y0)&(y<=y1)
        inner=np.minimum.reduce((x-x0,x1-x,y-y0,y1-y))
        outer=np.hypot(np.maximum.reduce((x0-x,x-x1,np.zeros_like(x))),
                       np.maximum.reduce((y0-y,y-y1,np.zeros_like(y))))
        return np.where(inside,inner,outer)
    def apply(rect, value, *, hit=True):
        nonlocal z, finite, edge
        x0, x1 = rect["x_range"]
        y0, y1 = rect["y_range"]
        inside = (x > x0) & (x < x1) & (y > y0) & (y < y1)
        edge = np.minimum(edge, rect_distance(rect))
        z = np.where(inside, value, z)
        finite = np.where(inside, hit, finite)
    if kind == "flat":
        pass
    elif kind == "obstacles":
        apply(spec["step"], spec["step"]["top_z_m"])
    elif kind == "stepping_stones":
        for rect in spec["stones"]:
            apply(rect, rect["top_z_m"])
    elif kind == "gap":
        gap = spec["gap"]
        x0, x1 = gap["x_range"]
        y0, y1 = gap["y_range"]
        edge = np.minimum(edge,rect_distance(gap))
        inside = (x > x0) & (x < x1) & (y > y0) & (y < y1)
        deep = inside & (x < gap["deep_x_range"][1])
        z = np.where(deep, gap["deep_z_m"], z)
        finite = np.where(inside & ~deep, False, finite)
        edge = np.minimum(edge,np.where((y>=y0)&(y<=y1),
                                        np.abs(x-gap["deep_x_range"][1]),np.inf))
    else:
        raise ValueError("unknown terrain kind")
    return z, finite, edge


def _plane(x0, x1, y0, y1, z):
    import trimesh
    vertices = np.array(((x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)),dtype=float)
    return trimesh.Trimesh(vertices=vertices, faces=np.array(((0,1,2),(0,2,3))), process=False)


def _box(rect):
    import trimesh
    x0,x1=rect["x_range"];y0,y1=rect["y_range"];top=rect["top_z_m"]
    center=((x0+x1)/2,(y0+y1)/2,top/2)
    return trimesh.creation.box((x1-x0,y1-y0,top),trimesh.transformations.translation_matrix(center))


def _terrain(kind, difficulty, cfg):
    del difficulty
    spec=answer(); sx,sy=cfg.size; ox,oy=sx/2,sy/2
    if tuple(cfg.size)!=tuple(spec["terrain_size_m"]):raise ValueError("scene size drift")
    def shifted(mesh):
        mesh.apply_translation((ox,oy,0))
        return mesh
    meshes=[]
    if kind=="gap":
        g=spec["gap"];x0,x1=g["x_range"];y0,y1=g["y_range"]
        meshes.extend((_plane(-ox,x0,-oy,oy,0),_plane(x1,ox,-oy,oy,0),
                       _plane(x0,x1,-oy,y0,0),_plane(x0,x1,y1,oy,0),
                       _plane(x0,g["deep_x_range"][1],y0,y1,g["deep_z_m"])))
    else:
        meshes.append(_plane(-ox,ox,-oy,oy,0))
        if kind=="obstacles":meshes.append(_box(spec["step"]))
        if kind=="stepping_stones":meshes.extend(_box(rect) for rect in spec["stones"])
    return [shifted(mesh) for mesh in meshes], np.array((ox,oy,0.0))


def flat_terrain(difficulty,cfg):return _terrain("flat",difficulty,cfg)
def obstacle_terrain(difficulty,cfg):return _terrain("obstacles",difficulty,cfg)
def gap_terrain(difficulty,cfg):return _terrain("gap",difficulty,cfg)
def stones_terrain(difficulty,cfg):return _terrain("stepping_stones",difficulty,cfg)


def build_generator(seed: int):
    from isaaclab.terrains import TerrainGeneratorCfg
    from isaaclab.terrains.sub_terrain_cfg import SubTerrainBaseCfg
    funcs=(flat_terrain,obstacle_terrain,gap_terrain,stones_terrain)
    kinds=answer()["order"]
    return TerrainGeneratorCfg(seed=seed,curriculum=True,size=tuple(answer()["terrain_size_m"]),
                               border_width=0.0,num_rows=1,num_cols=4,use_cache=False,
                               sub_terrains={kind:SubTerrainBaseCfg(function=fn,proportion=.25)
                                             for kind,fn in zip(kinds,funcs)})
