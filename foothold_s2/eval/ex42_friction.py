"""Approved EX-42 evaluation material, isolated from all training DR paths.

Ground is authored before scene creation. Robot collision materials are pinned
through PhysX after startup DR is disabled. Both are read back, never inferred
from the configuration receipt. No Isaac/Kit import occurs on the CPU path.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path

import yaml

DEFAULT_PLAN = Path(__file__).resolve().parents[1] / 'curriculum/ex42-prep.yaml'


def load_policy(path):
    path = Path(path).resolve(strict=True)
    blob = path.read_bytes()
    doc = yaml.safe_load(blob.decode('utf-8-sig'))
    cell = (doc.get('assumptions_pending_lead') or {}).get('evaluation_friction') or {}
    if cell.get('approved') is not True or not isinstance(cell.get('decision'), str) or not cell['decision'].strip():
        raise ValueError('EX-42 evaluation friction requires explicit approved decision')
    value = cell.get('value') or {}
    for key in ('static', 'dynamic'):
        x = value.get(key)
        if type(x) not in (int, float) or not math.isfinite(x) or x < 0:
            raise ValueError('EX-42 evaluation friction is missing or invalid: ' + key)
    if value['dynamic'] > value['static']:
        raise ValueError('EX-42 dynamic friction exceeds static friction')
    return {'plan_path': str(path), 'plan_sha256': hashlib.sha256(blob).hexdigest(),
            'decision': cell['decision'], 'static': float(value['static']),
            'dynamic': float(value['dynamic']), 'combine_mode': 'average'}


def map_policy(args):
    """Recognize direct EX-42 fixed-physics calls as well as the bundle CLI.

    N21 has its own explicit DR-on recording contract. It is not a fixed-
    friction maintenance cell and must never be relabelled as one.
    """
    path = getattr(args, 'ex42_evaluation_plan', None)
    ex42 = bool(path or (not getattr(args, 'n21_record_only', False) and (
        getattr(args, 'mesh_dir', None) or getattr(args, 'ex42_maintenance', False)
        or getattr(args, 'ex42_kind_family', None))))
    if not ex42:
        return None
    if getattr(args, 'dr_mode', 'off') != 'off':
        raise ValueError('EX-42 fixed evaluation friction requires DR-off')
    return load_policy(path or DEFAULT_PLAN)


def configure(env_cfg, policy):
    if policy is None:
        return
    if getattr(env_cfg.events, 'physics_material', None) is not None:
        raise ValueError('EX-42 evaluation friction requires material randomization disabled')
    # Do not mutate a class-level cfg object shared with a training task.
    material = deepcopy(env_cfg.scene.terrain.physics_material)
    material.static_friction = policy['static']
    material.dynamic_friction = policy['dynamic']
    material.friction_combine_mode = policy['combine_mode']
    env_cfg.scene.terrain.physics_material = material
    env_cfg.sim.physics_material = deepcopy(material)


def terrain_readback(raw):
    """Read the physics material actually bound to each terrain collision prim."""
    import omni.usd
    from pxr import Usd, UsdPhysics, UsdShade, PhysxSchema

    stage = omni.usd.get_context().get_stage()
    root = stage.GetPrimAtPath(raw.scene.terrain.cfg.prim_path)
    if not root.IsValid():
        raise RuntimeError('EX-42 terrain prim is absent')
    rows = []
    for prim in Usd.PrimRange(root):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        if not UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get():
            continue
        material, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial(materialPurpose='physics')
        if not material or not material.GetPrim().HasAPI(UsdPhysics.MaterialAPI):
            raise RuntimeError('EX-42 terrain collision has no bound physics material: ' + str(prim.GetPath()))
        physics = UsdPhysics.MaterialAPI(material.GetPrim())
        physx = PhysxSchema.PhysxMaterialAPI(material.GetPrim())
        rows.append({'collision_path': str(prim.GetPath()), 'material_path': str(material.GetPath()),
                     'static': physics.GetStaticFrictionAttr().Get(),
                     'dynamic': physics.GetDynamicFrictionAttr().Get(),
                     'combine_mode': str(physx.GetFrictionCombineModeAttr().Get())})
    return rows


def verify(raw, policy):
    if policy is None:
        return None
    import torch

    materials = torch.as_tensor(raw.scene['robot'].root_physx_view.get_material_properties()).detach().cpu()
    if (materials.ndim != 3 or materials.shape[-1] != 3 or not materials.numel()
            or not torch.isfinite(materials).all()):
        raise RuntimeError('EX-42 robot material readback is empty or nonfinite')
    for i, key in enumerate(('static', 'dynamic')):
        if not torch.allclose(materials[..., i], torch.full_like(materials[..., i], policy[key]), atol=1e-6, rtol=0):
            raise RuntimeError('EX-42 robot material readback differs: ' + key)
    ground = terrain_readback(raw)
    if not ground:
        raise RuntimeError('EX-42 terrain has no material readback')
    for row in ground:
        for key in ('static', 'dynamic'):
            x = row.get(key)
            if x is None or not math.isfinite(x) or abs(x-policy[key]) > 1e-6:
                raise RuntimeError('EX-42 terrain material readback differs: ' + key)
        if row.get('combine_mode') != policy['combine_mode']:
            raise RuntimeError('EX-42 terrain friction combine mode differs')
    return {**policy, 'state': 'verified', 'robot': {
                'source': 'root_physx_view.get_material_properties',
                'shape': list(materials.shape),
                'static_min': float(materials[..., 0].min()), 'static_max': float(materials[..., 0].max()),
                'dynamic_min': float(materials[..., 1].min()), 'dynamic_max': float(materials[..., 1].max()),
                'material_sha256': hashlib.sha256(materials.numpy().tobytes()).hexdigest()},
            'terrain': ground}


def install_and_verify(raw, policy):
    if policy is None:
        return None
    import torch

    view = raw.scene['robot'].root_physx_view
    materials = view.get_material_properties().clone()
    materials[..., 0] = policy['static']
    materials[..., 1] = policy['dynamic']
    indices = torch.arange(materials.shape[0], dtype=torch.int32, device='cpu')
    view.set_material_properties(materials, indices)
    return verify(raw, policy)
