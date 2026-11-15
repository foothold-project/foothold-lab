"""CPU-checkable plumbing evidence and isolated two-arm sequence rules."""
from __future__ import annotations
import hashlib
import copy
import json
import math
from pathlib import Path

import torch
from s2_map_obs import NUM_RAYS,grid_ray_xy_body,map_obs_a,map_obs_b
from s2_env_adapter_17v import training_map
from s2_env_config_17v import BASE_TASK
from s2_task_contract import contact_termination_for


class PlumbingHold(RuntimeError):pass


WARNING=("PLUMBING_ONLY: This checkpoint must not be used for A/B performance, "
         "map effect, or as a starting point for later training.")
ROUNDTRIP_TOLERANCE=1e-6


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_training_cfg(cfg, task=BASE_TASK):
    """Reject the A3 eight-case gravity/contact bypass in any learning cfg."""
    try:
        rigid=cfg.scene.robot.spawn.rigid_props
        contact=getattr(cfg.terminations,contact_termination_for(task))
    except AttributeError as ex:raise PlumbingHold("training_cfg_physics_unknown") from ex
    if rigid is None or getattr(rigid,"disable_gravity",None) is not False:
        raise PlumbingHold("diagnostic_gravity_leak")
    if contact is None:raise PlumbingHold("diagnostic_contact_leak")
    if getattr(cfg.scene.robot.spawn,"fix_base",False) is not False:
        raise PlumbingHold("diagnostic_root_fix_leak")
    return True


def known_input_probe():
    """Known ray axes, one miss, finite height and A/B masks before a live sensor."""
    grid=grid_ray_xy_body()
    if (grid.shape!=(NUM_RAYS,2) or
        not torch.allclose(grid[0],torch.tensor([-.8,-.5]),atol=1e-6) or
        not torch.allclose(grid[1],torch.tensor([-.7,-.5]),atol=1e-6) or
        not torch.allclose(grid[-1],torch.tensor([.8,.5]),atol=1e-6)):
        raise PlumbingHold("known_ray_axis_order")
    pos=torch.tensor([[0.,0.,1.]])
    hits=torch.cat((grid.unsqueeze(0),torch.full((1,NUM_RAYS,1),.25)),dim=-1)
    hits[0,0]=math.inf
    b,faults=map_obs_b(pos,hits,strict=True)
    a=map_obs_a(1)
    if (b.shape!=(1,374) or a.shape!=(1,374) or faults.total!=0 or
        not bool(torch.isfinite(b).all()) or not bool(torch.equal(a,torch.zeros_like(a))) or
        float(b[0,0])!=1. or float(b[0,NUM_RAYS])!=0. or
        not bool(torch.allclose(b[0,1:NUM_RAYS],torch.full((NUM_RAYS-1,),.25))) or
        not bool(torch.all(b[0,NUM_RAYS+1:]==1))):
        raise PlumbingHold("known_map_answer")
    return {"tensor_sha256":hashlib.sha256(b.cpu().contiguous().numpy().tobytes()).hexdigest(),
            "shape":[1,374],"rays":NUM_RAYS,"mask_valid":NUM_RAYS-1,
            "mask_miss":1,"height_valid":.25,"first_xy":[-.8,-.5],"last_xy":[.8,.5]}


def policy_sha(policy):
    digest=hashlib.sha256()
    for name,value in sorted(policy.state_dict().items()):
        tensor=value.detach().cpu().contiguous()
        digest.update(name.encode());digest.update(str(tuple(tensor.shape)).encode())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def group_snapshot(policy):
    groups=dict(policy.param_groups())
    groups["map_projection"]=list(policy.actor_in_map.parameters())
    return {name:[p.detach().clone() for p in params] for name,params in groups.items()}


def group_change(policy,before,optimizer):
    groups=dict(policy.param_groups())
    groups["map_projection"]=list(policy.actor_in_map.parameters())
    included={id(p):float(g["lr"]) for g in optimizer.param_groups for p in g["params"]}
    result={}
    for name,params in groups.items():
        old=before[name]
        diffs=[(p.detach()-v).abs() for p,v in zip(params,old)]
        result[name]={"optimizer_included":all(id(p) in included for p in params),
                      "actual_lr":sorted(set(included[id(p)] for p in params if id(p) in included)),
                      "changed_tensors":sum(bool(torch.any(d!=0)) for d in diffs),
                      "max_abs_diff":max((float(d.max()) for d in diffs),default=0.0),
                      "finite":all(bool(torch.isfinite(p).all()) for p in params)}
    return result


def _same(left,right):
    if isinstance(left,torch.Tensor):
        if not isinstance(right,torch.Tensor) or left.shape!=right.shape or left.dtype!=right.dtype:
            return False
        return torch.equal(left.detach().cpu(),right.detach().cpu())
    if isinstance(left,dict):return isinstance(right,dict) and left.keys()==right.keys() and all(_same(left[k],right[k]) for k in left)
    if isinstance(left,(tuple,list)):return type(left)==type(right) and len(left)==len(right) and all(_same(a,b) for a,b in zip(left,right))
    return left==right


def fixed_policy_input(dims,arm,device):
    n=2
    obs={"policy":torch.zeros(n,dims["policy"],device=device),
         "single_obs":torch.zeros(n,dims["single_obs"],device=device),
         "critic":torch.zeros(n,dims["critic"],device=device)}
    if arm=="A":obs["map"]=map_obs_a(n,device=device)
    elif arm=="B":
        known_input_probe()
        grid=grid_ray_xy_body().to(device)
        pos=torch.tensor([[0.,0.,1.],[0.,0.,1.]],device=device)
        hits=torch.cat((grid.unsqueeze(0).expand(n,-1,-1),
                        torch.full((n,NUM_RAYS,1),.25,device=device)),dim=-1)
        obs["map"],faults=map_obs_b(pos,hits,strict=True)
        if faults.total or not bool(torch.all(obs["map"][:,NUM_RAYS:]==1)):
            raise PlumbingHold("arm_B_ideal_map")
    else:raise PlumbingHold("arm_scope")
    return obs


def expected_synthetic_map_sha(rows,arm):
    mapped=synthetic_answer_tensor(rows,arm)
    return hashlib.sha256(mapped.cpu().contiguous().numpy().tobytes()).hexdigest()


def synthetic_answer_tensor(rows,arm,*,device=None,dtype=torch.float32):
    """Independent answer for the actual capture's root_z - 0.25 hit height."""
    if arm=="A":return torch.zeros((rows,2*NUM_RAYS),device=device,dtype=dtype)
    if arm!="B":raise PlumbingHold("arm_scope")
    height=torch.full((rows,NUM_RAYS),-.25,device=device,dtype=dtype)
    mask=torch.ones((rows,NUM_RAYS),device=device,dtype=dtype)
    height[:,0]=1.;mask[:,0]=0.
    return torch.cat((height,mask),dim=-1)


def verify_synthetic_capture_packet(packet,*,arm,geometry_tolerance_m):
    """Check capture -> packet -> map, including B even when A receives zero map."""
    yaw=packet.validate(previous=None,previous_done=None)
    b,faults=training_map(packet.sensor,mode="B",yaw_w=yaw,
                          geometry_tolerance_m=geometry_tolerance_m)
    expected=synthetic_answer_tensor(b.shape[0],"B",device=b.device,dtype=b.dtype)
    if faults.total or not torch.equal(b,expected):
        raise PlumbingHold("synthetic_capture_map_answer_mismatch")
    actual,_=training_map(packet.sensor,mode=arm,yaw_w=yaw,
                          geometry_tolerance_m=geometry_tolerance_m)
    arm_expected=synthetic_answer_tensor(b.shape[0],arm,device=actual.device,dtype=actual.dtype)
    if not torch.equal(actual,arm_expected):
        raise PlumbingHold("synthetic_capture_map_answer_mismatch")
    digest=hashlib.sha256(actual.detach().cpu().contiguous().numpy().tobytes()).hexdigest()
    return {"path":"IsaacS2Env.capture_packet -> AtomicPacket -> training_map",
            "arm":arm,"rows":b.shape[0],"b_height_valid":-.25,"first_ray_height":1.,
            "first_ray_mask":0.,"b_mask_valid":NUM_RAYS-1,
            "actor_map_sha256":digest,
            "b_reference_sha256":hashlib.sha256(b.detach().cpu().contiguous().numpy().tobytes()).hexdigest()}


def roundtrip_policy(runner,checkpoint,dims,arm):
    policy=runner.algo.policy
    device=next(policy.parameters()).device
    inp=fixed_policy_input(dims,arm,device)
    with torch.no_grad():
        before=policy.act_inference(inp).detach().clone()
        value_before=policy.evaluate(inp).detach().clone()
    state=torch.load(checkpoint,map_location="cpu",weights_only=False)
    transient=policy.distribution
    policy.distribution=None
    try:fresh=copy.deepcopy(policy)
    finally:policy.distribution=transient
    with torch.no_grad():
        for p in fresh.parameters():p.zero_()
    fresh.load_state_dict(state["policy"],strict=True)
    with torch.no_grad():
        after=fresh.act_inference(inp).detach().clone()
        value_after=fresh.evaluate(inp).detach().clone()
    action_diff=float((before-after).abs().max())
    value_diff=float((value_before-value_after).abs().max())
    if not math.isfinite(action_diff+value_diff) or max(action_diff,value_diff)>ROUNDTRIP_TOLERANCE:
        raise PlumbingHold("checkpoint_output_mismatch")
    if not _same(state["optimizer"],runner.algo.optimizer.state_dict()) or \
       not _same(state["s2_control"],runner.algo.ctl.state_dict()):
        raise PlumbingHold("checkpoint_optimizer_control_mismatch")
    digest=hashlib.sha256()
    for key in sorted(inp):digest.update(inp[key].detach().cpu().contiguous().numpy().tobytes())
    return {"checkpoint_sha256":file_sha(checkpoint),"same_output":True,
            "fresh_policy_object":fresh is not policy,"strict_load":True,
            "tolerance":ROUNDTRIP_TOLERANCE,"action_max_abs_diff":action_diff,
            "value_max_abs_diff":value_diff,"optimizer_control_match":True,
            "input_sha256":digest.hexdigest(),
            "output_sha256":hashlib.sha256(before.cpu().contiguous().numpy().tobytes()).hexdigest()}


def check_sequence(m):
    pair=m.get("plumbing_pair")
    if not isinstance(pair,dict) or pair.get("pair_id")!=m.get("chain_id"):
        raise PlumbingHold("pair_identity")
    ordinal=pair.get("ordinal")
    if type(ordinal) is not int or ordinal not in (1,2):raise PlumbingHold("pair_ordinal")
    if ordinal==1:
        if pair.get("previous_receipt_path") or pair.get("previous_receipt_sha256"):
            raise PlumbingHold("first_arm_has_predecessor")
        return {"ordinal":1,"previous":None}
    path=Path(pair.get("previous_receipt_path") or "missing")
    if not path.is_file():raise PlumbingHold("previous_arm_incomplete")
    if file_sha(path)!=pair.get("previous_receipt_sha256"):
        raise PlumbingHold("previous_receipt_hash")
    prior=json.loads(path.read_text(encoding="utf-8"))
    if (prior.get("stage")!="plumbing" or prior.get("pair_id")!=m["chain_id"] or
        prior.get("pair_ordinal")!=1 or
        prior.get("arm")==m["plan"]["arm"] or prior.get("gpu_uuid")!=m["gpu_uuid"] or
        prior.get("verdict")!="RUN_COMPLETE_UNVERIFIED" or
        prior.get("plumbing_checks")!="PASS" or
        prior.get("boundary_ok") is not True or
        prior.get("family_active_count")!=0 or prior.get("family_cleanup_confirmed") is not True or
        prior.get("parent_sha256_before")!=m["plan"]["parent_sha256"] or
        prior.get("parent_sha256_after")!=m["plan"]["parent_sha256"] or
        prior.get("input_path") not in ("live_raycaster_unverified","synthetic_known_answer")):
        raise PlumbingHold("previous_arm_not_clean")
    if pair.get("human_confirmed") is not True or not pair.get("human_verifier"):
        raise PlumbingHold("second_arm_human_review_missing")
    consent_path=Path(pair.get("second_consent_path") or "missing")
    if not consent_path.is_file() or file_sha(consent_path)!=pair.get("second_consent_sha256"):
        raise PlumbingHold("second_arm_direct_consent_missing")
    consent=json.loads(consent_path.read_text(encoding="utf-8"))
    if (consent.get("by")!="오흥재" or consent.get("scope")!="s2_plumbing_second_arm_one_shot" or
        consent.get("chain_id")!=m["chain_id"] or consent.get("arm")!=m["plan"]["arm"]):
        raise PlumbingHold("second_arm_direct_consent_identity")
    earlier=Path(prior.get("out_root") or "missing").resolve()
    current=Path(m["plan"]["out_root"]).resolve()
    if earlier==current or earlier in current.parents or current in earlier.parents:
        raise PlumbingHold("arm_output_not_isolated")
    return {"ordinal":2,"previous":file_sha(path)}


def verify_result(m,result,root):
    """A child claim is evidence only when every plumbing measurement is present."""
    p=m["plan"]
    if not isinstance(result,dict) or result.get("status")!="RUN_COMPLETE_UNVERIFIED":
        raise PlumbingHold("plumbing_child_status")
    if (result.get("stage")!="plumbing" or result.get("plumbing_only") is not True or
        result.get("arm")!=p["arm"] or result.get("input_path")!=m["input_path"] or
        result.get("manifest_sha256")!=hashlib.sha256(
            json.dumps(m,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()):
        raise PlumbingHold("plumbing_result_identity")
    if (result.get("executed_updates")!=p["updates"] or
        result.get("rollout_steps")!=p["rollout_steps"] or
        result.get("num_envs")!=p["num_envs"] or
        result.get("environment_steps")!=p["updates"]*p["rollout_steps"]*p["num_envs"]):
        raise PlumbingHold("iteration_step_accounting")
    if (result.get("start_iteration")!=0 or result.get("completed_iteration")!=p["updates"] or
        result.get("vector_steps")!=p["updates"]*p["rollout_steps"] or
        result.get("optimizer_steps_actual")!=p["updates"]*p["epochs"]*p["minibatches"]):
        raise PlumbingHold("iteration_step_accounting")
    if result.get("plumbing_checks")!="PASS" or result.get("stage0_passed") is not False or \
       result.get("performance_verified") is not False:
        raise PlumbingHold("plumbing_verdict_scope")
    marker=Path(root)/"PLUMBING_ONLY.txt"
    if not marker.is_file() or WARNING not in marker.read_text(encoding="utf-8") or \
       "manifest_sha256="+result["manifest_sha256"] not in marker.read_text(encoding="utf-8"):
        raise PlumbingHold("plumbing_marker")
    expected=(0,p["updates"])
    for n in expected:
        path=Path(root)/f"PLUMBING_ONLY_checkpoint_{n:06d}.pt"
        if not path.is_file() or path.stat().st_size==0:
            raise PlumbingHold("plumbing_checkpoint_boundary")
        state=torch.load(path,map_location="cpu",weights_only=False)
        meta=state.get("plumbing_meta",{})
        if (meta.get("plumbing_only") is not True or meta.get("stage")!="plumbing" or
            meta.get("manifest_sha256")!=result["manifest_sha256"] or
            meta.get("parent_sha256")!=p["parent_sha256"] or
            meta.get("input_path")!=m["input_path"] or state.get("resume_supported") is not False):
            raise PlumbingHold("plumbing_checkpoint_content")
    if list(Path(root).glob("checkpoint_*.pt")):
        raise PlumbingHold("unmarked_checkpoint")
    if (result.get("parameter_changed") is not True or
        not result.get("parameter_sha256_before") or
        not result.get("parameter_sha256_after") or
        result["parameter_sha256_before"]==result["parameter_sha256_after"]):
        raise PlumbingHold("weights_unchanged")
    rt=result.get("roundtrip") or {}
    if (rt.get("same_output") is not True or rt.get("fresh_policy_object") is not True or
        rt.get("strict_load") is not True or rt.get("optimizer_control_match") is not True or
        rt.get("tolerance")!=ROUNDTRIP_TOLERANCE or
        max(rt.get("action_max_abs_diff",math.inf),rt.get("value_max_abs_diff",math.inf))>ROUNDTRIP_TOLERANCE):
        raise PlumbingHold("checkpoint_output_mismatch")
    if result.get("nonfinite_count")!=0:raise PlumbingHold("nonfinite_record")
    if result.get("discarded_transitions")!=0:raise PlumbingHold("discarded_transitions")
    if (result.get("sensor_reads_total")!=p["updates"]*p["rollout_steps"]+1 or
        result.get("sensor_bootstrap_reads")!=1 or
        type(result.get("sensor_reset_env_reads")) is not int or result["sensor_reset_env_reads"]<0):
        raise PlumbingHold("sensor_read_accounting")
    records=result.get("records")
    if not isinstance(records,list) or len(records)!=p["updates"]:
        raise PlumbingHold("iteration_records")
    for index,record in enumerate(records):
        if record.get("iteration")!=index or record.get("rollout_steps")!=p["rollout_steps"]:
            raise PlumbingHold("iteration_step_accounting")
        if record.get("nonfinite_count")!=0:raise PlumbingHold("nonfinite_record")
        for key in ("loss","kl","entropy","gradient_norm_min","gradient_norm_max","learning_rate"):
            value=record.get(key)
            if type(value) not in (int,float) or not math.isfinite(value):
                raise PlumbingHold("nonfinite_"+key)
        if record["gradient_norm_min"]<=0 or record["learning_rate"]<=0:
            raise PlumbingHold("zero_gradient_or_lr")
        frozen=p["encoder_mode"]=="full_freeze" or index<p["freeze_updates"]
        if record.get("encoder_frozen") is not frozen:
            raise PlumbingHold("encoder_freeze_schedule")
        changes=record.get("group_changes",{})
        grads=record.get("preclip_group_grad_norms")
        if (not isinstance(grads,list) or len(grads)!=p["epochs"]*p["minibatches"] or
            not all(k in changes for k in ("actor","critic","map_encoder","map_projection","student_encoder")) or
            not all(math.isfinite(float(v)) for g in grads for v in g.values())):
            raise PlumbingHold("group_evidence_missing")
        if (changes["actor"]["changed_tensors"]==0 or changes["critic"]["changed_tensors"]==0 or
            (p["arm"]=="B" and changes["map_projection"]["changed_tensors"]==0) or
            (p["arm"]=="B" and index>=1 and changes["map_encoder"]["changed_tensors"]==0) or
            (frozen and changes["student_encoder"]["changed_tensors"]!=0) or
            not all(c["finite"] for c in changes.values())):
            raise PlumbingHold("group_path_disconnected")
        if (not all(changes[k]["optimizer_included"] for k in ("actor","critic","map_encoder","map_projection")) or
            changes["student_encoder"]["optimizer_included"] is not (p["encoder_mode"]=="schedule") or
            not all(c["actual_lr"] and all(math.isfinite(lr) and lr>0 for lr in c["actual_lr"])
                for k,c in changes.items() if k!="student_encoder")):
            raise PlumbingHold("optimizer_group_membership_or_lr")
        if p["arm"]=="B" and not any(g.get("map_projection",0)>0 for g in grads):
            raise PlumbingHold("map_projection_gradient_zero")
        if p["arm"]=="B" and index>=1 and not any(g.get("map_encoder",0)>0 for g in grads):
            raise PlumbingHold("map_encoder_gradient_zero")
        contract=record.get("tensor_contract",{})
        if (set(contract)!={"map","actions","rewards","dones","timeouts"} or
            any(x.get("nonfinite")!=0 for x in contract.values()) or
            contract["map"].get("shape")!=[p["rollout_steps"]*p["num_envs"],374] or
            contract["actions"].get("shape")!=[p["rollout_steps"]*p["num_envs"],result.get("action_dim")] or
            contract["rewards"].get("shape")!=[p["rollout_steps"],p["num_envs"]] or
            contract["dones"].get("shape")!=[p["rollout_steps"],p["num_envs"]] or
            contract["timeouts"].get("shape")!=[p["num_envs"]]):
            raise PlumbingHold("tensor_contract_invalid")
        if not record.get("map_input_sha256") or not record.get("last_packet_receipt",{}).get("raw_sha256"):
            raise PlumbingHold("input_provenance_missing")
    if m["input_path"]=="live_raycaster_unverified" and \
       result.get("input_limitation")!="success is limited to plumbing connection":
        raise PlumbingHold("live_input_limited_claim")
    return True


def verify_live_evidence(m,result):
    """Additional live-only proof. CPU fixtures cannot satisfy the attended receipt."""
    from s2_device_binding_a2 import normalize_uuid
    if result.get("cpu_dry") is not False or "FakeS2Env" in result.get("input_injection",""):
        raise PlumbingHold("cpu_fixture_not_live")
    binding=result.get("device_binding") or {}
    kit=binding.get("kit_observed") or {}
    if (binding.get("torch_logical_device")!=0 or
        normalize_uuid(binding.get("torch_uuid"))!=normalize_uuid(m["gpu_uuid"]) or
        binding.get("kit_requested_device")!=0 or
        kit.get("/physics/cudaDevice")!=0 or kit.get("/renderer/activeGpu")!=0):
        raise PlumbingHold("live_device_binding_missing")
    imports=result.get("runtime_imports") or {}
    for name in ("torch","rsl_rl","isaaclab","robot_lab","gymnasium"):
        item=imports.get(name) or {}
        if not item.get("path") or item["path"]=="None" or not Path(item["path"]).is_file():
            raise PlumbingHold("runtime_import_unverified_"+name)
    cfg=result.get("final_cfg")
    if not isinstance(cfg,dict) or hashlib.sha256(json.dumps(cfg,sort_keys=True,default=str).encode()).hexdigest()!=result.get("final_cfg_sha256"):
        raise PlumbingHold("final_cfg_content_hash")
    try:
        spawn=cfg["scene"]["robot"]["spawn"]
        if spawn["rigid_props"]["disable_gravity"] is not False or spawn["fix_base"] is not False:
            raise PlumbingHold("final_cfg_diagnostic_intervention")
        if cfg["terminations"][contact_termination_for(BASE_TASK)] is None:
            raise PlumbingHold("final_cfg_diagnostic_intervention")
    except (KeyError,TypeError) as ex:raise PlumbingHold("final_cfg_critical_value_missing") from ex
    diff=result.get("parent_cfg_diff")
    if not isinstance(diff,dict) or any(
        key not in ("/seed","/scene/num_envs") and
        not key.startswith("/scene/terrain/terrain_generator/") for key in diff):
        raise PlumbingHold("final_cfg_unexpected_diff")
    if result.get("sensor_mount_translation_b") not in ((0.,0.,0.),[0.,0.,0.]):
        raise PlumbingHold("sensor_mount_unverified")
    obs=result.get("observation_contract") or {}
    for name in ("policy","single_obs","critic"):
        item=obs.get(name) or {}
        shape=item.get("shape")
        dims=result.get("parent_obs_dims") or {}
        if (not isinstance(shape,list) or shape!=[m["plan"]["num_envs"],dims.get(name)] or
            item.get("nonfinite")!=0 or not item.get("dtype") or not item.get("device")):
            raise PlumbingHold("observation_contract_missing")
    if not result.get("usd_reference_paths"):
        raise PlumbingHold("usd_reference_unverified")
    if m["input_path"]=="synthetic_known_answer":
        if ("IsaacS2Env.capture_packet synthetic rays" not in result.get("input_injection","") or
            "actor map injection does not read RayCaster data" not in result["input_injection"] or
            result.get("synthetic_sensor_scope")!="actor map injection does not read real sensor; critic height_scan reads height_scanner"):
            raise PlumbingHold("synthetic_injection_not_isaac")
        capture=result.get("synthetic_capture_answer") or {}
        rows=m["plan"]["num_envs"]
        if (result.get("synthetic_capture_checks")!=result.get("sensor_reads_total") or
            capture.get("path")!="IsaacS2Env.capture_packet -> AtomicPacket -> training_map" or
            capture.get("rows")!=rows or capture.get("arm")!=m["plan"]["arm"] or
            capture.get("b_height_valid")!=-.25 or capture.get("first_ray_height")!=1. or
            capture.get("first_ray_mask")!=0. or capture.get("b_mask_valid")!=NUM_RAYS-1 or
            capture.get("b_reference_sha256")!=expected_synthetic_map_sha(rows,"B") or
            capture.get("actor_map_sha256")!=expected_synthetic_map_sha(rows,m["plan"]["arm"])):
            raise PlumbingHold("synthetic_capture_answer_mismatch")
        expected=expected_synthetic_map_sha(m["plan"]["rollout_steps"]*m["plan"]["num_envs"],m["plan"]["arm"])
        if any(rec.get("map_input_sha256")!=expected for rec in result.get("records",[])):
            raise PlumbingHold("synthetic_map_known_answer_mismatch")
    else:
        if result.get("input_injection")!="RayCaster tracker snapshot":
            raise PlumbingHold("live_sensor_input_unverified")
        for rec in result.get("records",[]):
            source=rec.get("last_packet_receipt") or {}
            if (source.get("hook_source_sha256")!=m["plan"]["sensor_hook_sha256"] or
                len(source.get("generation_by_env",[]))!=m["plan"]["num_envs"] or
                len(source.get("sensor_timestamp_by_env",[]))!=m["plan"]["num_envs"]):
                raise PlumbingHold("live_sensor_packet_unverified")
    return True
