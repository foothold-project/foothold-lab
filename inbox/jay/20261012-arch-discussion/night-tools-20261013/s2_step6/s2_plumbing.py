"""CPU-checkable plumbing evidence and isolated two-arm sequence rules."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

import torch
from s2_map_obs import NUM_RAYS,grid_ray_xy_body,map_obs_a,map_obs_b


class PlumbingHold(RuntimeError):pass


WARNING=("PLUMBING_ONLY: This checkpoint must not be used for A/B performance, "
         "map effect, or as a starting point for later training.")


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_training_cfg(cfg):
    """Reject the A3 eight-case gravity/contact bypass in any learning cfg."""
    try:
        rigid=cfg.scene.robot.spawn.rigid_props
        contact=cfg.terminations.base_contact
    except AttributeError as ex:raise PlumbingHold("training_cfg_physics_unknown") from ex
    if rigid is None or getattr(rigid,"disable_gravity",None) is not False:
        raise PlumbingHold("diagnostic_gravity_leak")
    if contact is None:raise PlumbingHold("diagnostic_contact_leak")
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
    return {"shape":[1,374],"rays":NUM_RAYS,"mask_valid":NUM_RAYS-1,
            "mask_miss":1,"height_valid":.25,"first_xy":[-.8,-.5],"last_xy":[.8,.5]}


def policy_sha(policy):
    digest=hashlib.sha256()
    for name,value in sorted(policy.state_dict().items()):
        tensor=value.detach().cpu().contiguous()
        digest.update(name.encode());digest.update(str(tuple(tensor.shape)).encode())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


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


def roundtrip_policy(runner,checkpoint,dims,arm):
    policy=runner.algo.policy
    device=next(policy.parameters()).device
    inp=fixed_policy_input(dims,arm,device)
    with torch.no_grad():before=policy.act_inference(inp).detach().clone()
    # This file was just saved by this process. Environment resume stays unsupported.
    state=torch.load(checkpoint,map_location=device,weights_only=False)
    with torch.no_grad():
        policy.actor_in.bias.add_(.125)
        disturbed=policy.act_inference(inp).detach().clone()
    if torch.equal(before,disturbed):raise PlumbingHold("checkpoint_perturbation_ineffective")
    policy.load_state_dict(state["policy"],strict=True)
    with torch.no_grad():after=policy.act_inference(inp).detach().clone()
    if not torch.equal(before,after):raise PlumbingHold("checkpoint_output_mismatch")
    return {"checkpoint_sha256":file_sha(checkpoint),"same_output":True,
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
        prior.get("boundary_ok") is not True or
        prior.get("family_active_count")!=0 or prior.get("family_cleanup_confirmed") is not True or
        prior.get("parent_sha256_before")!=m["plan"]["parent_sha256"] or
        prior.get("parent_sha256_after")!=m["plan"]["parent_sha256"] or
        prior.get("input_path") not in ("live_raycaster_unverified","synthetic_known_answer")):
        raise PlumbingHold("previous_arm_not_clean")
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
    marker=Path(root)/"PLUMBING_ONLY.txt"
    if not marker.is_file() or WARNING not in marker.read_text(encoding="utf-8") or \
       "manifest_sha256="+result["manifest_sha256"] not in marker.read_text(encoding="utf-8"):
        raise PlumbingHold("plumbing_marker")
    expected=(0,p["updates"])
    for n in expected:
        path=Path(root)/f"PLUMBING_ONLY_checkpoint_{n:06d}.pt"
        if not path.is_file() or path.stat().st_size==0:
            raise PlumbingHold("plumbing_checkpoint_boundary")
    if list(Path(root).glob("checkpoint_*.pt")):
        raise PlumbingHold("unmarked_checkpoint")
    if (result.get("parameter_changed") is not True or
        not result.get("parameter_sha256_before") or
        not result.get("parameter_sha256_after") or
        result["parameter_sha256_before"]==result["parameter_sha256_after"]):
        raise PlumbingHold("weights_unchanged")
    if not result.get("roundtrip",{}).get("same_output"):
        raise PlumbingHold("checkpoint_output_mismatch")
    if result.get("nonfinite_count")!=0:raise PlumbingHold("nonfinite_record")
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
    if m["input_path"]=="live_raycaster_unverified" and \
       result.get("input_limitation")!="success is limited to plumbing connection":
        raise PlumbingHold("live_input_limited_claim")
    return True
