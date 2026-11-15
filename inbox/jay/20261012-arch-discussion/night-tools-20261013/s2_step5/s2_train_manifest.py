"""CPU-only manifest sealing. All training and resource choices come from the request JSON."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from s2_train_contract import CODE,HERE,PYTHON,PARENT_SHA,SCOPE,TrainHold,canonical,entry_argv,sha,undecided

REQUIRED=("chain_id","gpu_index","gpu_uuid","gpu_bus_id","max_wall_s",
          "min_free_vram_bytes","running_floor_vram_bytes","min_free_disk_bytes",
          "max_disk_bytes","deadline_epoch","approval_path","prelaunch_report_path",
          "status_path","log_path","claim_root","gpu_lease_root","usd_lock_path","plan")
PLAN_REQUIRED=("stage","parent","agent_yaml","sensor_hook_path","out_root","stop_file",
               "arm","encoder_mode","schedule","seed","num_envs","updates",
               "rollout_steps","epochs","minibatches","checkpoint_interval",
               "map_init_seed","gap_proportion","stones_proportion","step_height_m",
               "step_width_m","geometry_tolerance_m","deadline_epoch","lr",
               "clip_param","gamma","lam","value_loss_coef","entropy_coef",
               "max_grad_norm","desired_kl","use_clipped_value_loss")


def seal(request:dict,manifest_path:Path):
    if not isinstance(request,dict) or any(k not in request for k in REQUIRED):
        raise TrainHold("request_required_fields")
    if undecided(request):raise TrainHold("undecided_value")
    plan=request["plan"]
    if not isinstance(plan,dict) or any(k not in plan for k in PLAN_REQUIRED):
        raise TrainHold("plan_required_fields")
    m=dict(request);p=dict(plan)
    if "manifest_path" in m and Path(m["manifest_path"]).resolve()!=manifest_path.resolve():
        raise TrainHold("manifest_path_conflict")
    if "scope" in m and m["scope"]!=SCOPE:raise TrainHold("scope_conflict")
    if "observer_mode" in m and m["observer_mode"]!="attended":raise TrainHold("observer_mode_conflict")
    if "retry_count" in m and m["retry_count"]!=0:raise TrainHold("retry_count_conflict")
    if sha(p["parent"])!=PARENT_SHA:raise TrainHold("parent_checkpoint_hash")
    p["parent_sha256"]=PARENT_SHA
    p["agent_yaml_sha256"]=sha(p["agent_yaml"])
    p["sensor_hook_sha256"]=sha(p["sensor_hook_path"])
    if p["stage"]=="short":p["barrier_contract_sha256"]=sha(p["barrier_contract"])
    m.update(scope=SCOPE,observer_mode="attended",retry_count=0,
             manifest_path=str(manifest_path.resolve()),python_path=str(PYTHON.resolve()),
             python_sha256=sha(PYTHON),entry_path=str(HERE/"s2_train_entry_17v.py"),
             code_hashes={name:sha(HERE/name) for name in CODE},plan=p)
    m["entry_argv"]=entry_argv(m)
    return m


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--request",required=True,type=Path)
    ap.add_argument("--manifest",required=True,type=Path)
    a=ap.parse_args()
    if a.manifest.exists():raise TrainHold("manifest_reused")
    m=seal(json.loads(a.request.read_text(encoding="utf-8")),a.manifest)
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    with a.manifest.open("xb") as out:out.write(canonical(m))
    print(json.dumps({"manifest_path":str(a.manifest),"manifest_sha256":sha(a.manifest)},sort_keys=True))


if __name__=="__main__":main()
