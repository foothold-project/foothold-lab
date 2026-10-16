"""CPU-only S2 checkpoint loading and fixed-input inference audit.

No simulator, terrain case execution, score or comparison verdict is here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import torch

from s2_policy import build_s2
from s2_env_adapter_17v import expected_world_xy, training_map
from s2_map_obs import NUM_RAYS


class EvalContractError(RuntimeError):
    pass


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()


def known_maps():
    """Same adapter as training, with independent flat, miss and raised answers."""
    cfg=SimpleNamespace(ray_alignment="yaw",offset=SimpleNamespace(pos=(0.,0.,20.)),
                        pattern_cfg=SimpleNamespace(ordering="xy",size=(1.6,1.0),
                                                    resolution=.1,direction=(0.,0.,-1.)))
    pos=torch.tensor([[0.,0.,.5],[1.,0.,.5]],dtype=torch.float32)
    yaw=torch.zeros(2)
    xy=expected_world_xy(pos,yaw)
    hits=torch.cat((xy,torch.zeros(2,NUM_RAYS,1)),dim=-1)
    hits[0,0]=float("inf")
    hits[1,1,2]=.2
    sensor=SimpleNamespace(cfg=cfg,data=SimpleNamespace(pos_w=pos,ray_hits_w=hits))
    a,fa=training_map(sensor,mode="A",yaw_w=yaw,geometry_tolerance_m=.002)
    b,fb=training_map(sensor,mode="B",yaw_w=yaw,geometry_tolerance_m=.002)
    if fa.total or fb.total or a.shape!=(2,374) or b.shape!=(2,374):
        raise EvalContractError("known_map_shape_or_fault")
    if (not bool(torch.all(a==0)) or b[0,0]!=1 or b[0,187]!=0 or
        b[0,1]!=0 or b[0,188]!=1 or
        not bool(torch.isclose(b[1,1],torch.tensor(-.2))) or b[1,188]!=1):
        raise EvalContractError("known_map_answer")
    return {"A":a,"B":b,"sensor_pos_w":pos,"ray_hits_w":hits}


def fixed_obs(dims,mode):
    if mode not in ("A","B"):
        raise EvalContractError("arm_scope")
    maps=known_maps()
    return {"policy":torch.zeros(2,dims["policy"]),
            "single_obs":torch.zeros(2,dims["single_obs"]),
            "critic":torch.zeros(2,dims["critic"]),
            "map":maps[mode]}


def strict_load(path, *, expected_sha256, parent, mode, expected_env_config_sha256,
                map_init_seed):
    """Expected SHA is checked before trusted local torch deserialization."""
    if mode not in ("A","B") or not isinstance(expected_sha256,str) or len(expected_sha256)!=64:
        raise EvalContractError("checkpoint_identity_missing")
    if sha(path)!=expected_sha256:
        raise EvalContractError("checkpoint_hash")
    state=torch.load(path,map_location="cpu",weights_only=False)
    if not isinstance(state,dict):
        raise EvalContractError("checkpoint_container")
    required={"format","mode","plan","plan_sha256","env_config_sha256",
              "policy","s2_control","optimizer","rng","resume_supported",
              "discarded_transitions","encounter_states"}
    if set(state) not in (required,required|{"plumbing_meta"}):
        raise EvalContractError("checkpoint_keys")
    if (state["format"]!="s2-17v-checkpoint-only" or state["resume_supported"] is not False or
        state["mode"]!=mode or state["plan"].get("mode")!=mode or
        state["env_config_sha256"]!=expected_env_config_sha256):
        raise EvalContractError("checkpoint_contract")
    plan_bytes=json.dumps(state["plan"],sort_keys=True,separators=(",",":")).encode()
    if hashlib.sha256(plan_bytes).hexdigest()!=state["plan_sha256"]:
        raise EvalContractError("plan_hash")
    policy,_,_=build_s2(mode,parent=parent,map_init_seed=map_init_seed)
    expected=policy.state_dict()
    actual=state["policy"]
    if not isinstance(actual,dict) or actual.keys()!=expected.keys():
        raise EvalContractError("policy_keys")
    mismatch=[name for name,want in expected.items() if not isinstance(actual[name],torch.Tensor)
              or actual[name].shape!=want.shape or actual[name].dtype!=want.dtype]
    if mismatch:
        raise EvalContractError("policy_shape_dtype:"+",".join(mismatch[:3]))
    policy.load_state_dict(actual,strict=True)
    policy.eval()
    return policy,{"format":state["format"],"mode":mode,"checkpoint_sha256":expected_sha256,
                   "plan_sha256":state["plan_sha256"],"env_config_sha256":state["env_config_sha256"],
                   "policy_tensor_count":len(actual),
                   "policy_shapes_dtypes":{k:{"shape":list(v.shape),"dtype":str(v.dtype)}
                                           for k,v in actual.items()},
                   "top_level_keys":sorted(state)}


def compare_training_forward(training_policy, loaded_policy, dims, mode):
    obs=fixed_obs(dims,mode)
    training_policy.eval();loaded_policy.eval()
    with torch.no_grad():
        before_a=training_policy.act_inference(obs).detach().cpu()
        before_v=training_policy.evaluate(obs).detach().cpu()
        after_a=loaded_policy.act_inference(obs).detach().cpu()
        after_v=loaded_policy.evaluate(obs).detach().cpu()
    if not torch.equal(before_a,after_a):
        raise EvalContractError("action_forward_mismatch")
    if not torch.equal(before_v,after_v):
        raise EvalContractError("value_forward_mismatch")
    return {"mode":mode,"input_map_sha256":hashlib.sha256(obs["map"].numpy().tobytes()).hexdigest(),
            "action_shape":list(after_a.shape),"value_shape":list(after_v.shape),
            "action_sha256":hashlib.sha256(after_a.numpy().tobytes()).hexdigest(),
            "value_sha256":hashlib.sha256(after_v.numpy().tobytes()).hexdigest(),
            "action_equal":True,"value_equal":True}
