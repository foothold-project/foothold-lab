"""CPU counterexamples and positive controls for ASTRA 17ai step16."""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parent
WRAPPER = ROOT/"fixtures_17ai"/"vecenv_wrapper.py"
WRAPPER_SHA = "fbd71e80818fc711594963e2beb78de9ae72b2ef4916ac2f92038cd169b7472d"
OLD_FOOT = ROOT/"fixtures_17ai"/"old_s2_foot_query.py"
OLD_FOOT_SHA = "7a1a224f21d0046a15181d24d0a599b18fb0dce2d7c94f8ff4b617a88753e464"
sys.path.insert(0, str(ROOT))

from s2_eval_cpu import EvalContractError, sha, strict_load
from s2_eval_usd_provenance import evidence as usd_evidence
from s2_eval_kit_adapter import EvalIsaacAdapter, factory, reset_root_q
from s2_foot_query import FootQueryTracker, bind_reset_ids, live_raycast
from s2_foot_scenes import truth_rows, SCENES, terrain_mesh
from s2_foot_kit_supervisor import verdict
from s2_foot_kit_supervisor import run_foot
from s2_foot_kit_scope import validate as validate_foot, required_argv as foot_argv
from s2_foot_kit_scope import CODE_NAMES as FOOT_CODE, canonical as foot_canonical
from s2_foot_manager_evidence import bind_manager_compute
from s2_foot_config import BASELINE_WEIGHTS, WEIGHT

PASS = []
CAUGHT = []


def ok(name, condition):
    assert condition, name
    PASS.append(name)


def caught(name, want, fn):
    try:
        fn()
    except Exception as ex:
        actual = str(ex)
        assert want in actual, (name, want, actual)
        CAUGHT.append({"name": name, "first_FAIL": actual, "want": want})
    else:
        raise AssertionError(name + " accepted")


def module(name, **items):
    m = ModuleType(name)
    m.__path__ = []
    m.__dict__.update(items)
    return m


def test_wrapper():
    ok("installed wrapper fixture pinned", sha(WRAPPER)==WRAPPER_SHA)
    tree = ast.parse(WRAPPER.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RslRlVecEnvWrapper")
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    source = ast.fix_missing_locations(ast.Module(body=[init], type_ignores=[]))

    class FakeAsset:
        device = "cpu"
        def __init__(self):
            self.data = SimpleNamespace(default_root_state=torch.tensor([[0.,0.,.5,1.,0.,0.,0.,0.,0.,0.,0.,0.,0.]]))
        def write_root_pose_to_sim(self, *a, **k): pass
        def write_root_velocity_to_sim(self, *a, **k): pass

    class FakeRaw:
        def __init__(self, *, fail=False):
            self.device = "cpu"; self.num_envs = 1; self.max_episode_length = 100
            self.action_manager = SimpleNamespace(total_action_dim=12)
            self.scene = SimpleNamespace(sensors={"height_scanner":object()},
                                          env_origins=torch.zeros(1,3))
            self.asset = FakeAsset(); self.scene.__getitem__ = None
            self.command_manager = SimpleNamespace(get_term=lambda name:
                SimpleNamespace(commands=torch.zeros(1,3), time_left=torch.zeros(1)))
            self.fail = fail; self.closed = 0; self.resets = 0

    class Scene:
        def __init__(self, raw): self.raw=raw; self.sensors={"height_scanner":object()}; self.env_origins=torch.zeros(1,3)
        def __getitem__(self, name): return self.raw.asset

    class FakeEnv:
        def __init__(self, *, fail=False):
            self.unwrapped = FakeRaw(fail=fail)
            self.unwrapped.scene = Scene(self.unwrapped)
        def reset(self):
            self.unwrapped.resets += 1
            reset_root_q(self.unwrapped, torch.tensor([0]), {"x":(0,0),"y":(0,0),"z":(0,0)})
            if self.unwrapped.fail:
                raise RuntimeError("wrapper_reset_failure")
        def close(self): self.unwrapped.closed += 1

    ns = {"ManagerBasedRLEnv": FakeRaw, "DirectRLEnv": FakeRaw,
          "gym": SimpleNamespace(spaces=SimpleNamespace(flatdim=lambda x:12))}
    exec(compile(source, str(WRAPPER), "exec"), ns)
    class ActualInit:
        __init__ = ns["__init__"]
        @property
        def unwrapped(self): return self.env.unwrapped
        def _modify_action_space(self): pass

    class Prim:
        def IsValid(self): return True
        def GetMetadata(self, k): return SimpleNamespace(explicitItems=[SimpleNamespace(assetPath="x.usd")])
    stage = SimpleNamespace(GetPrimAtPath=lambda p: Prim())
    mathmod = module("isaaclab.utils.math", sample_uniform=lambda lo,hi,shape,device:torch.zeros(shape),
                     quat_from_euler_xyz=lambda x,y,z:torch.tensor([[1.,0.,0.,0.]]),
                     quat_mul=lambda a,b:a)
    modules = {
        "isaaclab": module("isaaclab"),
        "isaaclab.utils": module("isaaclab.utils", math=mathmod),
        "isaaclab.sim": module("isaaclab.sim", SimulationContext=SimpleNamespace(instance=lambda:None)),
        "isaaclab.sensors": module("isaaclab.sensors"),
        "isaaclab.sensors.ray_caster": module("isaaclab.sensors.ray_caster"),
        "isaaclab_rl": module("isaaclab_rl"),
        "robot_lab": module("robot_lab"),
        "robot_lab.tasks": module("robot_lab.tasks"),
        "robot_lab.tasks.go2": module("robot_lab.tasks.go2"),
        "gymnasium": module("gymnasium", make=lambda *a, **k: FakeEnv()),
        "isaaclab_rl.rsl_rl": module("isaaclab_rl.rsl_rl", RslRlVecEnvWrapper=ActualInit),
        "robot_lab.tasks.go2.rsl_rl_cfg": module("robot_lab.tasks.go2.rsl_rl_cfg",
            MoECTSRunnerCfg=lambda:SimpleNamespace(clip_actions=1.)),
        "isaaclab.sim.utils": module("isaaclab.sim.utils", get_current_stage=lambda:stage),
        "isaaclab.utils.math": mathmod,
        "isaaclab.managers": module("isaaclab.managers", SceneEntityCfg=lambda name:SimpleNamespace(name=name)),
        "isaaclab.sensors.ray_caster.ray_caster": module("isaaclab.sensors.ray_caster.ray_caster",
            RayCaster=SimpleNamespace(_instance_count=0, meshes={})),
    }
    import s2_eval_kit_adapter as adapter_mod
    made = []
    def make(*a, **k):
        env = FakeEnv(fail=len(made) == 1)
        made.append(env)
        return env
    modules["gymnasium"].make = make
    with patch.dict(sys.modules, modules), patch.object(adapter_mod, "_cfg", return_value=(object(),object())), \
         patch.object(adapter_mod, "SensorUpdateTracker", return_value=SimpleNamespace(detach=lambda:None)), \
         patch.object(adapter_mod, "checked_mount", return_value=(0.,0.,0.)):
        fake = FakeEnv()
        caught("old wrapper before yaw", "_q_yaw", lambda: ActualInit(fake))
        ok("old counterexample reset before close", fake.unwrapped.resets == 1 and fake.unwrapped.closed == 0)
        create = factory(hook_source_path="x", hook_source_sha256="y")
        good = create({"command":{"cmd":[0,0,0]}}, "A")
        ok("actual wrapper init sees yaw", made[0].unwrapped.resets == 1 and
           hasattr(made[0].unwrapped, "_q_yaw"))
        good.close()
        ok("normal close exactly once", made[0].unwrapped.closed == 1)
        caught("wrapper constructor failure", "wrapper_reset_failure",
               lambda:create({"command":{"cmd":[0,0,0]}}, "A"))
        ok("failed wrapper raw close exactly once", made[1].unwrapped.closed == 1)


def test_checkpoint():
    from s2_policy import load_parent_cpu, build_s2, make_optimizer, E1_CKPT
    from s2_runner_17v import S2Runner, _hash_plan
    parent, _ = load_parent_cpu(E1_CKPT)
    policy, _, _ = build_s2("A", parent=parent, map_init_seed=0)
    optimizer, ctl = make_optimizer(policy, .001, encoder_mode="full_freeze")
    runner = S2Runner.__new__(S2Runner)
    runner.mode = "A"; runner.plan={"mode":"A", "encoder_mode":"full_freeze",
        "freeze_updates":None,"encoder_lr_ratio":None}
    runner.plan_sha256=_hash_plan(runner.plan); runner.env_config_sha256="a"*64
    runner.discarded_transitions=0; runner.encounters=SimpleNamespace(states={})
    runner.algo=SimpleNamespace(policy=policy, optimizer=optimizer, ctl=ctl)
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"model.pt"; runner.save(p)
        args=dict(expected_sha256=sha(p), parent=parent, mode="A",
                  expected_env_config_sha256="a"*64, map_init_seed=0,
                  expected_update=0, expected_plan_sha256=runner.plan_sha256,
                  expected_encoder_mode="full_freeze")
        _, receipt = strict_load(p, **args)
        ok("update zero identity receipt", receipt["completed_updates"] == 0 and
           receipt["optimizer_slot_count"] == 0)
        state=torch.load(p,map_location="cpu",weights_only=False)
        bad=Path(td)/"bad.pt"
        state["s2_control"]={}; torch.save(state,bad)
        caught("empty control", "checkpoint_update_identity",
               lambda: strict_load(bad, **dict(args, expected_sha256=sha(bad))))
        state=torch.load(p,map_location="cpu",weights_only=False)
        state["s2_control"]["completed_updates"]=2000
        state["s2_control"]["next_update_index"]=2000
        torch.save(state,bad)
        caught("job zero vs checkpoint 2000", "checkpoint_update_identity",
               lambda: strict_load(bad, **dict(args, expected_sha256=sha(bad))))
        state=torch.load(p,map_location="cpu",weights_only=False)
        state["plumbing_meta"]={"parent_sha256":"p"*64,"plumbing_only":True,
                                "manifest_sha256":"m"*64}
        torch.save(state,bad)
        _, pinned = strict_load(bad, **dict(args, expected_sha256=sha(bad),
                                          expected_parent_sha256="p"*64))
        ok("parent identity in receipt", pinned["parent_sha256"]=="p"*64)
        caught("parent identity mutation", "checkpoint_parent_identity",
               lambda: strict_load(bad, **dict(args, expected_sha256=sha(bad),
                                                expected_parent_sha256="q"*64)))
        caught("plan identity mutation", "checkpoint_plan_or_encoder_identity",
               lambda: strict_load(bad, **dict(args, expected_sha256=sha(bad),
                                                expected_plan_sha256="0"*64)))
        state=torch.load(p,map_location="cpu",weights_only=False)
        state["optimizer"]["state"][0]={"step":torch.tensor(1.)}
        state["s2_control"]["optimizer"]["state"][0]={"step":torch.tensor(1.)}
        torch.save(state,bad)
        caught("update zero optimizer step", "update_zero_optimizer_nonzero",
               lambda: strict_load(bad, **dict(args, expected_sha256=sha(bad))))


def test_conversion_cap():
    with tempfile.TemporaryDirectory() as td:
        with patch.dict(os.environ, {"FOOTHOLD_USD_ROOT":td,
                                  "FOOTHOLD_EXPECT_CONVERSIONS":"any",
                                  "FOOTHOLD_CONVERSION_CAP":"8"}):
            spec=importlib.util.spec_from_file_location("isolate_test_17ai", ROOT/"usd_isolate_run_v3.py")
            m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        calls=[]
        class Converter:
            def __init__(self,cfg):
                calls.append(cfg.asset_path)
                self._usd_dir=cfg.usd_dir
        m.patch(SimpleNamespace(AssetConverterBase=Converter), "cpu_test")
        cfg=SimpleNamespace(usd_dir=str(Path(td)/"inside"), asset_path="robot.urdf")
        for i in range(8): Converter(cfg)
        ok("eight original converter calls", len(calls)==8 and m._STATE["conversion_successes"]==8)
        caught("ninth constructor entry", "hard cap 8", lambda:Converter(cfg))
        ok("ninth original not called", len(calls)==8 and m._STATE["conversions"]==9)


def test_usd_case_links():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); usd=root/"usd"; usd.mkdir()
        asset=root/"robot.urdf"; asset.write_text("fixture")
        folder=usd/"conversion1"; folder.mkdir()
        robot=folder/"robot.usd"; robot.write_text("fixture")
        state={"version":"v3","expect_conversions":"any","root":str(usd),
               "conversions":1,"conversion_successes":1,"conversion_cap":8,
               "blocked":[],"warnings":[]}
        (usd/"isolate_state.json").write_text(json.dumps(state))
        row={"kind":"assigned","usd_dir":str(folder),"asset_path":str(asset),
             "case_arm":"gap-001-s1001:A","n":1}
        (usd/"assigned.jsonl").write_text(json.dumps(row)+"\n")
        case={"case_id":"gap-001-s1001","arm":"A","executed":True,
              "missing_reason":None,"usd_robot_references":[str(robot)]}
        linked=usd_evidence(usd,asset,[str(robot)],max_entries=8,case_rows=[case])
        ok("case arm converter USD Robot link", linked["case_arm_links"][0]["entry"]==1 and
           linked["converter_successes"]==1)
        case["usd_robot_references"]=[str(usd/"other.usd")]
        caught("wrong Robot reference", "converter_usd_robot_reference_mismatch",
               lambda:usd_evidence(usd,asset,[str(robot)],max_entries=8,case_rows=[case]))


def test_foot_reset():
    names=("FL_foot","FR_foot","RL_foot","RR_foot")
    quat=torch.tensor([1.,0.,0.,0.]).expand(2,4,4).clone()
    robot=SimpleNamespace(data=SimpleNamespace(body_pos_w=torch.zeros(2,4,3),body_quat_w=quat),
                          find_bodies=lambda wanted,preserve_order:(list(range(4)),list(names)))
    contact=SimpleNamespace(body_names=list(names),data=SimpleNamespace(net_forces_w=torch.zeros(2,4,3)))
    terrain=SimpleNamespace(env_origins=torch.zeros(2,3))
    class Scene:
        def __init__(self):
            self.sensors={"contact_forces":contact}; self.terrain=terrain
        def __getitem__(self,k): return robot
    class Env:
        scene=Scene(); num_envs=2; common_step_counter=1
        episode_length_buf=torch.tensor([1,1])
        cfg=SimpleNamespace(scene=SimpleNamespace(terrain=SimpleNamespace(
            terrain_generator=SimpleNamespace(size=(8.,8.)))))
        def _reset_idx(self, ids): self.episode_length_buf[ids]=0
    env=Env()
    raycaster=SimpleNamespace(meshes={"/World/ground":object()})
    modules={"isaaclab.sensors.ray_caster.ray_caster":module("ray",RayCaster=raycaster),
             "isaaclab.utils.math":module("math",quat_apply=lambda q,v:v),
             "isaaclab.utils.warp":module("warp",raycast_mesh=lambda starts,dirs,mesh,max_dist:
                  (torch.stack([starts[...,0],starts[...,1],torch.zeros_like(starts[...,2])],-1),))}
    tracker=FootQueryTracker(2,.05)
    bind_reset_ids(env,tracker)
    with patch.dict(sys.modules, modules):
        ok("old foot source fixture pinned", sha(OLD_FOOT)==OLD_FOOT_SHA)
        spec=importlib.util.spec_from_file_location("old_s2_foot_query_17ai",OLD_FOOT)
        old=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=old
        spec.loader.exec_module(old)
        old_env=Env(); old_env.episode_length_buf=torch.tensor([1,1])
        old_tracker=old.FootQueryTracker(2,.05)
        old.live_raycast(old_env,old_tracker,spacing_m=.05)
        old_env._reset_idx(torch.tensor([0]))
        old_env.episode_length_buf[:]=torch.tensor([1,2]);old_env.common_step_counter=2
        caught("old natural reset 1 to 1", "foot_frame_not_fresh",
               lambda:old.live_raycast(old_env,old_tracker,spacing_m=.05))
        first=live_raycast(env,tracker,spacing_m=.05)
        old_condition=bool((torch.tensor([1,1]) < torch.tensor([1,1])).any())
        ok("old 1 to 1 reset inference fails", old_condition is False)
        env._reset_idx(torch.tensor([0])); env.episode_length_buf[:]=torch.tensor([1,2])
        env.common_step_counter=2
        second=live_raycast(env,tracker,spacing_m=.05)
        ok("partial natural reset IDs", second.episode_id.tolist()==[1,0] and
           second.frame_id.tolist()==[1,2])
        env._reset_idx(torch.tensor([1])); env.episode_length_buf[:]=torch.tensor([2,1])
        env.common_step_counter=3
        third=live_raycast(env,tracker,spacing_m=.05)
        ok("explicit reset IDs", third.episode_id.tolist()==[1,1] and
           third.frame_id.tolist()==[2,1])


def test_scenes_and_verdict():
    ok("straight truth cost three", truth_rows("straight")["cost"]==3 and
       [i for i,v in enumerate(truth_rows("straight")["danger"]) if v]==[6,7,8])
    ok("diagonal truth cost two", truth_rows("diagonal")["cost"]==2 and
       [i for i,v in enumerate(truth_rows("diagonal")["danger"]) if v]==[8])
    ok("cardinal only truth cost one", truth_rows("cardinal_slot")["cost"]==1)
    for scene in SCENES:
        mesh, origin = terrain_mesh(0.5, SimpleNamespace(size=(8.,8.),
                                    anchor_xy=(0.,0.), scene_tag=scene))
        ok("mesh " + scene, len(mesh)==1 and len(mesh[0].faces)>0 and
           origin.tolist()==[4.,4.,0.])
    with tempfile.TemporaryDirectory() as td:
        v=verdict({},rc=1,family_empty=False,reason="STOP",observer_log=Path(td)/"missing")
        ok("missing foot evidence is HOLD", v["verdict"]=="HOLD" and
           v["comparison_ready"] is False)


def test_manager_and_supervisor():
    names=list(BASELINE_WEIGHTS)+["feet_center_any9_v1"]
    weights={**BASELINE_WEIGHTS,"feet_center_any9_v1":WEIGHT}
    class Manager:
        active_terms=names
        def __init__(self):
            self._episode_sums={"feet_center_any9_v1":torch.zeros(1)}
            self._step_reward=torch.zeros(1,16)
        def get_term_cfg(self,name): return SimpleNamespace(weight=weights[name],func=lambda env:0)
        def compute(self,dt):
            value=torch.tensor([-0.03])
            self._step_reward[:,15]=value
            self._episode_sums["feet_center_any9_v1"]+=value*dt
            return value*dt
    manager=Manager()
    env=SimpleNamespace(reward_manager=manager,step_dt=.02,common_step_counter=1,
        _s2_foot_last_query=SimpleNamespace(episode_id=torch.tensor([0])),
        _s2_foot_last_cost=SimpleNamespace(cost=torch.tensor([3.])))
    receipt=bind_manager_compute(env)
    manager.compute(.02)
    ok("actual manager output and accumulator", receipt["count"]==16 and
       len(env._s2_foot_manager_rows)==1 and
       abs(env._s2_foot_manager_rows[0]["actual_weighted"][0]+.0006)<1e-8)
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        m={"chain_id":"foot", "attempt":"one", "claim_root":str(root/"claims"),
           "status_path":str(root/"status.json"), "max_wall_s":20,
           "deadline_epoch":time.time()+20,"lease_root":str(root/"lease"),
           "gpu_uuid":"fixture", "usd_lock_path":str(root/"lock"),
           "usd_root":str(root/"usd"), "gpu_index":0, "python_path":"python",
           "isolate_path":"isolate", "driver_path":"driver", "request_path":"request",
           "request_sha256":"a"*64,"result_path":str(root/"result.json"),
           "log_path":str(root/"child.log"), "stop_path":str(root/"STOP"),
           "observer_log_path":str(root/"observer.log"),
           "scope":"s2_foot_kit_check_once", "purpose":"one_shot_no_learning"}
        class Resource:
            def acquire(self): return self
            def release(self,**k): pass
        class Owner:
            pid=123
            def __init__(self): self.launched=0
            def launch(self,argv,cwd,env,log_path):
                self.launched+=1
                Path(m["result_path"]).write_text("{}")
            def active_count(self): return 0
            def exit_code(self): return 0
            def close(self): pass
        owner=Owner()
        m["observer_registration_path"]=str(root/"observer.json")
        result=run_foot(m,{},owner_factory=lambda:owner,
            lease_factory=lambda *x:Resource(),lock_factory=lambda *x:Resource(),
            observer_check=lambda x:{"status":"ARMED"},fixture=True,
            validator=lambda *x,**k:None)
        ok("one shot claim and HOLD receipt", owner.launched==1 and result["verdict"]=="HOLD" and
           (root/"claims"/"foot-one.claim"/"foot.receipt.json").is_file())
        caught("claim cannot be reused", "claim_reused", lambda:run_foot(m,{},owner_factory=lambda:owner,
            lease_factory=lambda *x:Resource(),lock_factory=lambda *x:Resource(),
            observer_check=lambda x:{"status":"ARMED"},fixture=True,
            validator=lambda *x,**k:None))


def test_foot_scope():
    with tempfile.TemporaryDirectory(dir=ROOT.parent) as td:
        root=Path(td); now=time.time()
        request={"scope":"s2_foot_kit_check_once","scenes":list(SCENES),
                 "training_updates":0,"optimizer_steps":0,"steps_per_scene":20,
                 "max_wall_s":120,"seed":7}
        request_path=root/"request.json"; request_path.write_text(json.dumps(request))
        python=Path(sys.executable)
        m={"scope":"s2_foot_kit_check_once","purpose":"one_shot_no_learning",
           "chain_id":"foot", "attempt":"first", "claim_root":str(root/"claims"),
           "status_path":str(root/"status.json"),"stop_path":str(root/"STOP"),
           "observer_registration_path":str(root/"observer.json"),
           "observer_log_path":str(root/"observer.log"),"lease_root":str(root/"leases"),
           "usd_lock_path":str(root/"lock"),"usd_root":str(root/"usd"),
           "result_path":str(root/"result.json"),"log_path":str(root/"child.log"),
           "python_path":str(python),"python_sha256":sha(python),
           "isolate_path":str(ROOT/"usd_isolate_run_v3.py"),
           "isolate_sha256":sha(ROOT/"usd_isolate_run_v3.py"),
           "driver_path":str(ROOT/"s2_foot_kit_driver.py"),
           "driver_sha256":sha(ROOT/"s2_foot_kit_driver.py"),
           "request_path":str(request_path),"request_sha256":sha(request_path),
           "gpu_uuid":"synthetic-gpu-0","gpu_index":0,"deadline_epoch":now+100,
           "max_wall_s":120,"max_launches":1,"retry_count":0,
           "observer_mode":"attended","max_envs":2,"max_control_steps":300,
           "training_updates":0,"optimizer_steps":0,
           "min_free_vram_bytes":1,"running_floor_vram_bytes":1,
           "min_free_disk_bytes":1,"max_disk_bytes":1000000,
           "code_hashes":{name:sha(ROOT/name) for name in FOOT_CODE}}
        m["argv"]=foot_argv(m)
        approval={"status":"APPROVED","scope":m["scope"],"by":"fixture",
                  "manifest_sha256":__import__("hashlib").sha256(foot_canonical(m)).hexdigest(),
                  "expires_epoch":now+110}
        ok("dedicated foot scope positive", validate_foot(m,approval,now=now,fixture=True)==request)
        bad=copy.deepcopy(approval);bad["manifest_sha256"]="0"*64
        caught("foot approval digest mutation", "direct_approval_missing",
               lambda:validate_foot(m,bad,now=now,fixture=True))
        (root/"STOP").write_text("stop")
        caught("foot STOP before launch", "STOP",
               lambda:validate_foot(m,approval,now=now,fixture=True))


def main():
    torch.set_num_threads(2)
    test_wrapper(); test_checkpoint(); test_conversion_cap(); test_usd_case_links(); test_foot_reset()
    test_scenes_and_verdict(); test_manager_and_supervisor(); test_foot_scope()
    print(json.dumps({"normal_PASS":PASS,"mutants_CAUGHT":CAUGHT},ensure_ascii=False))


if __name__ == "__main__": main()
