"""CPU known-answer and integration checks. No Kit or GPU imports."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import s2_foot_reward as reward
from s2_foot_config import BASELINE_WEIGHTS, WEIGHT, add_foot_reward, manager_reward_receipt, validate_variant
from s2_foot_query import (FootQueryTracker, MESH_PATH, FOOT_NAMES, COLLISION_OFFSET_M,
                           make_ray_starts, grid_offsets, kit_step_record)

HERE = Path(__file__).resolve().parent
PARENT_CFG = Path("C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/tasks/go2/env_cfg.py")
E1_YAML = Path("C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/params/env.yaml")
STEP14_CONFIG_FIXTURE = HERE/'fixtures_s2_step15'/'step14_s2_env_config_17v.py'
STEP14_CONFIG_SHA256 = 'b8fda54bf8570e91e786f9efa86e0ef6e84138312a8ae3fe9b3671eb04ad5ccc'


def fixture(n=1):
    centers = torch.zeros(n, 4, 3)
    centers[..., 2] = .022
    forces = torch.zeros(n, 4, 3)
    forces[..., 2] = 2
    heights = torch.zeros(n, 4, 9)
    status = torch.full((n, 4, 9), reward.HIT, dtype=torch.uint8)
    return centers, heights, status, forces


def hand_triangle_mesh_heights(spacing=.05):
    """18 planar triangles, one 1 cm square per sample; independent ray hit table."""
    offsets = [(x, y) for x in (-spacing, 0, spacing) for y in (-spacing, 0, spacing)]
    low = {(0, -spacing), (-spacing, -spacing)}
    triangles = []
    for x, y in offsets:
        z = -.30 if (x, y) in low else 0.
        a = (x-.005, y-.005, z)
        b = (x+.005, y-.005, z)
        c = (x+.005, y+.005, z)
        d = (x-.005, y+.005, z)
        triangles.extend(((a,b,c),(a,c,d)))
    answer = []
    for x, y in offsets:
        hits=[]
        for triangle in triangles:
            minx,maxx=min(v[0] for v in triangle),max(v[0] for v in triangle)
            miny,maxy=min(v[1] for v in triangle),max(v[1] for v in triangle)
            if minx<=x<=maxx and miny<=y<=maxy:
                hits.append(triangle[0][2])
        assert hits and len(set(hits))==1
        answer.append(hits[0])
    return answer


class TestFoot(unittest.TestCase):
    def test_step14_and_none_config_dict_identical(self):
        from s2_env_config_17v import EnvironmentSpec, configure_env
        self.assertEqual(hashlib.sha256(STEP14_CONFIG_FIXTURE.read_bytes()).hexdigest(),
                         STEP14_CONFIG_SHA256)
        specmod=importlib.util.spec_from_file_location('step14_env_cfg',STEP14_CONFIG_FIXTURE)
        previous=importlib.util.module_from_spec(specmod)
        sys.modules[specmod.name]=previous
        specmod.loader.exec_module(previous)
        spec=EnvironmentSpec(42,8,.15,.15,.1,.2,.001)
        def base():
            return SimpleNamespace(seed=0,scene=SimpleNamespace(num_envs=1,
                terrain=SimpleNamespace(terrain_generator=SimpleNamespace(sub_terrains={"flat":1}))))
        # Use the same copied overlay in both modules; only the cfg call differs.
        with patch.object(previous,'make_overlay',side_effect=lambda terrain,**kw:terrain),\
             patch('s2_env_config_17v.make_overlay',side_effect=lambda terrain,**kw:terrain):
            left=previous.configure_env(base(),spec,diagnostic_kind=None,reset_yaw_rad=None)
            right=configure_env(base(),spec,diagnostic_kind=None,reset_yaw_rad=None)
        add_foot_reward(right)
        serialize=lambda obj: json.dumps(obj,sort_keys=True,default=lambda v:vars(v),separators=(',',':')).encode()
        self.assertEqual(serialize(left),serialize(right))

    def test_known_triangle_mesh_cardinal_diagonal(self):
        p,h,s,f=fixture()
        h[0,0]=torch.tensor(hand_triangle_mesh_heights())
        self.assertEqual(h[0,0].tolist(),[-.30000001192092896,0,0,-.30000001192092896,0,0,0,0,0])
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[3.])

    def test_flat(self):
        self.assertEqual(reward.feet_center_any9_v1(*fixture()).cost.tolist(),[0.])

    def test_installed_urdf_four_collision_spheres(self):
        path=Path('C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf')
        root=ET.parse(path).getroot()
        for name in FOOT_NAMES:
            node=root.find(f"./link[@name='{name}']/collision")
            self.assertIsNotNone(node)
            self.assertEqual(tuple(float(v) for v in node.find('origin').attrib['xyz'].split()),
                             COLLISION_OFFSET_M)
            self.assertEqual(float(node.find('geometry/sphere').attrib['radius']),reward.RADIUS_M)

    def test_cardinal_diagonal_both_swing_and_all_feet(self):
        p,h,s,f=fixture()
        h[0,0,1]=-.3
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[1.])
        h.zero_();h[0,0,0]=-.3
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[2.])
        h[0,0,1]=-.3
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[3.])
        f[0,0,2]=0
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[0.])
        f[...,2]=2;h[:,:,0]=-.3;h[:,:,1]=-.3
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[12.])

    def test_central_override_and_counter(self):
        p,h,s,f=fixture();h[0,0,4]=-.3
        out=reward.feet_center_any9_v1(p,h,s,f)
        self.assertEqual((out.cost.tolist(),out.central_discrepancy.tolist()),([3.],[1]))

    def test_z_translation_invariance(self):
        p,h,s,f=fixture();h[0,0,1]=-.3
        first=reward.feet_center_any9_v1(p,h,s,f).cost
        p[...,2]+=17.25;h+=17.25
        self.assertTrue(torch.equal(first,reward.feet_center_any9_v1(p,h,s,f).cost))

    def test_strict_boundaries(self):
        p,h,s,f=fixture();h[0,0,1]=-.20
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[0.])
        h[0,0,1]=-.201;f[0,0,2]=1.
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[0.])
        f[0,0,2]=1.001
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[1.])

    def test_no_hit_and_bad_values(self):
        p,h,s,f=fixture();s[0,0,1]=reward.NO_HIT;h[0,0,1]=float('inf')
        self.assertEqual(reward.feet_center_any9_v1(p,h,s,f).cost.tolist(),[1.])
        s[0,0,1]=reward.HIT
        with self.assertRaisesRegex(ValueError,"foot_hit_nonfinite"):
            reward.feet_center_any9_v1(p,h,s,f)
        h[0,0,1]=float('nan')
        with self.assertRaisesRegex(ValueError,"foot_hit_nonfinite"):
            reward.feet_center_any9_v1(p,h,s,f)
        s[0,0,1]=0
        with self.assertRaisesRegex(ValueError,"foot_query_invalid"):
            reward.feet_center_any9_v1(p,h,s,f)

    def test_foot_permutation(self):
        p,h,s,f=fixture();h[0,0,1]=-.3;h[0,1,0]=-.3
        baseline=reward.feet_center_any9_v1(p,h,s,f).cost
        ix=[2,0,3,1]
        self.assertTrue(torch.equal(baseline,reward.feet_center_any9_v1(p[:,ix],h[:,ix],s[:,ix],f[:,ix]).cost))

    def test_grid_world_xy_and_no_accumulation(self):
        p,_,_,_=fixture();before=p.clone()
        starts=make_ray_starts(p,.05)
        self.assertEqual(grid_offsets(.05,device='cpu',dtype=torch.float32)[0].tolist(),[-.05000000074505806,-.05000000074505806,0.])
        self.assertTrue(torch.equal(starts,make_ray_starts(p,.05)))
        self.assertTrue(torch.equal(before,p))
        self.assertAlmostEqual(float(starts[0,0,4,2]),20.022,places=5)
        hits=starts.clone();hits[...,2]=0
        _,_,_,f=fixture()
        kw=dict(centers=p,forces=f,hits=hits,frame_id=torch.tensor([0]),
                episode_id=torch.tensor([0]),tile_origin=torch.zeros(1,3),
                tile_size_xy=(4.,4.),mesh_path=MESH_PATH)
        wrong=starts.clone();wrong[...,2]+=20
        with self.assertRaisesRegex(ValueError,'foot_start_mismatch'):
            FootQueryTracker(1,.05).capture(**kw,ray_starts=wrong)

    def test_query_no_hit_and_invalids(self):
        p,_,_,f=fixture();start=make_ray_starts(p,.05)
        hits=start.clone();hits[...,2]=0
        tracker=FootQueryTracker(1,.05)
        kw=dict(centers=p,forces=f,hits=hits,frame_id=torch.tensor([0]),
                episode_id=torch.tensor([0]),tile_origin=torch.zeros(1,3),
                tile_size_xy=(4.,4.),mesh_path=MESH_PATH)
        q=tracker.capture(**kw)
        self.assertTrue(torch.equal(q.starts,start))
        self.assertTrue(bool((q.status==reward.HIT).all()))
        tracker2=FootQueryTracker(1,.05)
        miss=hits.clone();miss[0,0,1]=float('inf')
        q=tracker2.capture(**{**kw,'hits':miss})
        self.assertEqual(reward.feet_center_any9_v1(q.centers,q.heights,q.status,q.forces).cost.tolist(),[1.])
        record=kit_step_record(q,reward.feet_center_any9_v1(q.centers,q.heights,q.status,q.forces),
                               body_ids=[0,1,2,3],dt=.02)
        self.assertAlmostEqual(record['weighted_reward'][0],-.0002,places=7)
        self.assertEqual(record['ray_hits_w_m'][0][0][1][2],'+inf')
        for bad, error in ((float('nan'),'foot_hit_invalid'),(float('-inf'),'foot_hit_invalid')):
            badhits=hits.clone();badhits[0,0,1,2]=bad
            with self.assertRaisesRegex(ValueError,error):
                FootQueryTracker(1,.05).capture(**{**kw,'hits':badhits})
        with self.assertRaisesRegex(ValueError,'foot_range_too_short'):
            FootQueryTracker(1,.05).capture(**{**kw,'max_distance_m':20.})
        with self.assertRaisesRegex(ValueError,'foot_outside_tile'):
            FootQueryTracker(1,.05).capture(**{**kw,'tile_size_xy':(.05,.05)})
        with self.assertRaisesRegex(ValueError,'foot_mesh_mismatch'):
            FootQueryTracker(1,.05).capture(**{**kw,'mesh_path':'wrong'})

    def test_async_reset_and_stale(self):
        p,_,_,f=fixture(2);hits=make_ray_starts(p,.05);hits[...,2]=0
        tracker=FootQueryTracker(2,.05)
        kw=dict(centers=p,forces=f,hits=hits,tile_origin=torch.zeros(2,3),
                tile_size_xy=(4.,4.),mesh_path=MESH_PATH)
        tracker.capture(**kw,frame_id=torch.tensor([1,1]),episode_id=torch.tensor([0,0]))
        tracker.reset(torch.tensor([0]))
        tracker.capture(**kw,frame_id=torch.tensor([0,2]),episode_id=torch.tensor([1,0]))
        with self.assertRaisesRegex(ValueError,'foot_frame_stale'):
            tracker.capture(**kw,frame_id=torch.tensor([0,3]),episode_id=torch.tensor([1,0]))
        with self.assertRaisesRegex(ValueError,'foot_episode_stale'):
            tracker.capture(**kw,frame_id=torch.tensor([1,3]),episode_id=torch.tensor([0,0]))

    def test_none_is_byte_identical_and_opt_in_only_reward(self):
        cfg=SimpleNamespace(rewards=SimpleNamespace(**{k:SimpleNamespace(weight=v) for k,v in BASELINE_WEIGHTS.items()}),
                            observations={'policy':48,'single_obs':48,'critic':101},scene={'existing':'same'})
        before=json.dumps(cfg,default=lambda x:vars(x),sort_keys=True).encode()
        self.assertIs(add_foot_reward(cfg),cfg)
        self.assertEqual(before,json.dumps(cfg,default=lambda x:vars(x),sort_keys=True).encode())
        cfg2=copy.deepcopy(cfg)
        add_foot_reward(cfg2,variant='feet_center_any9_v1',spacing_m=.05,
                        term_factory=lambda **kw:SimpleNamespace(**kw))
        self.assertEqual(cfg2.observations,cfg.observations)
        self.assertEqual(cfg2.scene,cfg.scene)
        self.assertEqual(set(vars(cfg2.rewards))-set(vars(cfg.rewards)),{'feet_center_any9_v1'})
        self.assertEqual(cfg2.rewards.feet_center_any9_v1.weight,-.01)
        with self.assertRaisesRegex(ValueError,'requires_explicit'):
            validate_variant('feet_center_any9_v1',None)
        with self.assertRaisesRegex(ValueError,'none_forbids'):
            validate_variant('none',.05)

    def test_manager_receipt_and_e1_15_term_table(self):
        class Manager:
            def __init__(self,weights):self.weights=weights;self.active_terms=list(weights)
            def get_term_cfg(self,name):return SimpleNamespace(weight=self.weights[name])
        baseline=manager_reward_receipt(Manager(BASELINE_WEIGHTS))
        self.assertEqual(baseline['count'],15)
        self.assertEqual(manager_reward_receipt(Manager({**BASELINE_WEIGHTS,'feet_center_any9_v1':WEIGHT}),
                                                variant='feet_center_any9_v1')['count'],16)
        with self.assertRaisesRegex(ValueError,'mismatch'):
            manager_reward_receipt(Manager({**BASELINE_WEIGHTS,'feet_center_any9_v1':WEIGHT}))
        tree=ast.parse(PARENT_CFG.read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RewardsCfg')
        actual={}
        for node in cls.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                term=node.targets[0].id
                if isinstance(node.value,ast.Call):
                    weight=next((k.value for k in node.value.keywords if k.arg=='weight'),None)
                    if weight is not None:actual[term]=ast.literal_eval(weight)
        self.assertEqual(actual,BASELINE_WEIGHTS)
        text=E1_YAML.read_text(encoding='utf-8')
        block=text.split('\nrewards:\n',1)[1].split('\nterminations:\n',1)[0]
        yaml_weights={}
        name=None
        for line in block.splitlines():
            match=re.match(r'^  ([a-z_0-9]+):$',line)
            if match:name=match.group(1)
            match=re.match(r'^    weight: ([-+0-9.eE]+)$',line)
            if match:yaml_weights[name]=float(match.group(1))
        self.assertEqual(yaml_weights,BASELINE_WEIGHTS)

    def test_request_selector_is_explicit_and_sealed_argv(self):
        from s2_train_contract import entry_argv
        from s2_train_manifest import PLAN_REQUIRED
        plan={key:'v' for key in PLAN_REQUIRED}
        plan.update(stage='smoke',encoder_mode='full_freeze')
        manifest={'plan':plan,'python_path':'python','manifest_path':'manifest',
                  'approval_path':'approval'}
        base=entry_argv(manifest)
        self.assertNotIn('--reward_variant',base)
        plan['reward_variant']='feet_center_any9_v1'
        plan['foot_spacing_m']=.05
        selected=entry_argv(manifest)
        self.assertEqual(selected[selected.index('--reward_variant')+1],'feet_center_any9_v1')
        self.assertEqual(selected[selected.index('--foot_spacing_m')+1],'0.05')
        self.assertEqual(len(selected),len(base)+4)


if __name__=='__main__':
    run=unittest.main(verbosity=2,exit=False)
    if not run.result.wasSuccessful():raise SystemExit(1)
    print('PASS s2_step15_foot 16/16')
