"""CPU-only short A/B barrier contract builder. Does not grant or run updates."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import re


class ContractHold(ValueError):pass


MATCH_FIELDS=("parent","agent_yaml","encoder_mode","schedule","seed",
              "num_envs","rollout_steps","epochs","minibatches","map_init_seed",
              "gap_proportion","stones_proportion","step_height_m","step_width_m",
              "geometry_tolerance_m","lr","clip_param","gamma","lam",
              "value_loss_coef","entropy_coef","max_grad_norm","desired_kl",
              "use_clipped_value_loss")


def build_pair(requests,*,approval_id,approval_sha256,grant_root,poll_seconds,
               grant_timeout_s):
    if set(requests)!={"A","B"}:raise ContractHold("arm_pair_required")
    if (not isinstance(approval_id,str) or not approval_id.strip() or
        approval_id=="UNDECIDED" or not re.fullmatch("[0-9a-fA-F]{64}",approval_sha256)):
        raise ContractHold("approval_identity_missing")
    if (not grant_root or grant_root=="UNDECIDED" or
        any(type(v) not in (int,float) or not math.isfinite(v) or v<=0
            for v in (poll_seconds,grant_timeout_s))):
        raise ContractHold("barrier_wait_budget")
    a,b=requests["A"],requests["B"]
    if (not isinstance(a,dict) or not isinstance(b,dict) or
        a.get("chain_id")!=b.get("chain_id") or not a.get("chain_id") or
        a["chain_id"]=="UNDECIDED"):
        raise ContractHold("chain_mismatch")
    plans={arm:requests[arm].get("plan") for arm in ("A","B")}
    if any(not isinstance(p,dict) or p.get("arm")!=arm or p.get("stage")!="short"
           for arm,p in plans.items()):raise ContractHold("arm_or_stage_mismatch")
    if any(plans["A"].get(k)!=plans["B"].get(k) for k in MATCH_FIELDS):
        raise ContractHold("comparison_conditions_mismatch")
    if any(p.get("num_envs")!=1024 or p.get("updates")!=2000 or
           p.get("checkpoint_interval")!=200 or p.get("encoder_mode")!="full_freeze" or
           p.get("seed")!=11 or p.get("map_init_seed")!=7 for p in plans.values()):
        raise ContractHold("short_scope_mismatch")
    if any(p.get("gap_proportion")!=.15 or p.get("stones_proportion")!=.15 for p in plans.values()):
        raise ContractHold("terrain_scope_mismatch")
    if any(requests[arm].get("extension")!={"initial_short_updates":2000,
            "max_total_updates":2500,"allowed_increments":[500]} for arm in ("A","B")):
        raise ContractHold("extension_scope_mismatch")
    if any(requests[arm].get("approval_id")!=approval_id for arm in ("A","B")):
        raise ContractHold("approval_id_mismatch")
    if (a.get("deadline_epoch")!=b.get("deadline_epoch") or
        type(a.get("deadline_epoch")) not in (int,float) or
        not math.isfinite(a["deadline_epoch"]) or a["deadline_epoch"]<=0 or
        any(p.get("deadline_epoch")!=a["deadline_epoch"] for p in plans.values())):
        raise ContractHold("deadline_mismatch")
    if any(not p.get("stop_file") or p["stop_file"]=="UNDECIDED" or
           not p.get("barrier_contract") or p["barrier_contract"]=="UNDECIDED"
           for p in plans.values()):
        raise ContractHold("barrier_paths_unresolved")
    if plans["A"]["stop_file"]==plans["B"]["stop_file"] or \
       plans["A"]["barrier_contract"]==plans["B"]["barrier_contract"]:
        raise ContractHold("arm_paths_not_isolated")
    return {arm:{"chain_id":a["chain_id"],"arm":arm,"approval_id":approval_id,
            "approval_sha256":approval_sha256.lower(),"grant_root":str(Path(grant_root).resolve()),
            "stop_file":plans[arm]["stop_file"],"deadline_epoch":a["deadline_epoch"],
            "initial_short_updates":2000,"max_total_updates":2500,
            "allowed_increments":[500],"poll_seconds":poll_seconds,
            "grant_timeout_s":grant_timeout_s} for arm in ("A","B")}


def main(argv=None):
    parser=argparse.ArgumentParser()
    for name in ("request-a","request-b","approval-id","approval-sha256",
                 "grant-root","out-a","out-b"):parser.add_argument("--"+name,required=True)
    parser.add_argument("--poll-seconds",type=float,required=True)
    parser.add_argument("--grant-timeout-s",type=float,required=True)
    args=parser.parse_args(argv)
    requests={arm:json.loads(Path(getattr(args,"request_"+arm.lower())).read_text(encoding="utf-8"))
              for arm in ("A","B")}
    contracts=build_pair(requests,approval_id=args.approval_id,
                         approval_sha256=args.approval_sha256,grant_root=args.grant_root,
                         poll_seconds=args.poll_seconds,grant_timeout_s=args.grant_timeout_s)
    outputs={arm:Path(getattr(args,"out_"+arm.lower())) for arm in ("A","B")}
    if outputs["A"].resolve()==outputs["B"].resolve() or any(p.exists() for p in outputs.values()):
        raise ContractHold("output_reused")
    if any(outputs[arm].resolve()!=Path(requests[arm]["plan"]["barrier_contract"]).resolve()
           for arm in ("A","B")):
        raise ContractHold("barrier_output_path_mismatch")
    for arm in ("A","B"):
        outputs[arm].parent.mkdir(parents=True,exist_ok=True)
        with outputs[arm].open("x",encoding="utf-8") as stream:
            json.dump(contracts[arm],stream,ensure_ascii=False,sort_keys=True,indent=2)
    print(json.dumps({arm:str(outputs[arm]) for arm in ("A","B")},sort_keys=True))
    return 0


if __name__=="__main__":raise SystemExit(main())
