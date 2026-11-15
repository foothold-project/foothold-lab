"""Approved one-arm S2 training launch contract. Import and validation are CPU-only."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import time
from s2_plumbing import check_sequence

HERE=Path(__file__).resolve().parent
PYTHON=Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
PARENT_SHA="c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8"
SCOPE="s2_one_arm_training_attended"
PLUMBING_SCOPE="s2_plumbing_attended_one_shot"
CODE=("s2_train_entry_17v.py","s2_train_launch.py","s2_train_contract.py",
      "s2_train_manifest.py",
      "s2_foot_reward.py","s2_foot_query.py","s2_foot_config.py",
      "s2_plumbing.py","s2_task_contract.py",
      "s2_env_config_17v.py","s2_terrain_overlay_17v.py","s2_env_adapter_17v.py",
      "s2_sensor_tracker_17v.py","s2_packet_17v.py","s2_runner_17v.py",
      "s2_ppo_17v.py","s2_policy.py","s2_map_obs.py","s2_increment_barrier.py",
      "s2_encoder_policy.py","s2_job_owner.py","s2_resource_lease.py",
      "s2_stage0_resources_a2.py","s2_device_binding_a2.py","usd_isolate_run_v3.py")
USD_WRAPPER_SHA="97da75f5a45b4ad7ae9058a5d5cb4e7fb1de9cd82a5e283b30dd6e07406e94f9"

class TrainHold(RuntimeError):pass

def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def undecided(value):
    if isinstance(value,str):return value.strip().upper()=="UNDECIDED"
    if isinstance(value,dict):return any(undecided(x) for x in value.values())
    if isinstance(value,(list,tuple)):return any(undecided(x) for x in value)
    return False

def entry_argv(m):
    p=m["plan"]
    fields=("parent","agent_yaml","out_root","stop_file","arm","encoder_mode","schedule",
            "seed","num_envs","updates","rollout_steps","epochs","minibatches",
            "checkpoint_interval","map_init_seed","gap_proportion","stones_proportion",
            "step_height_m","step_width_m","geometry_tolerance_m","deadline_epoch",
            "lr","clip_param","gamma","lam","value_loss_coef","entropy_coef",
            "max_grad_norm","desired_kl","use_clipped_value_loss")
    args=[str(m["python_path"]),"-B",str(HERE/"usd_isolate_run_v3.py"),
          str(HERE/"s2_train_entry_17v.py")]
    args.extend(("--stage",str(p["stage"])))
    for key in fields:args.extend(("--"+key,str(p[key])))
    if p.get("reward_variant", "none") != "none":
        args.extend(("--reward_variant",str(p["reward_variant"]),
                     "--foot_spacing_m",str(p["foot_spacing_m"])))
    if p["stage"]=="plumbing":args.extend(("--input_path",str(m["input_path"])))
    if p["encoder_mode"]=="schedule":
        args.extend(("--freeze_updates",str(p["freeze_updates"]),
                     "--encoder_lr_ratio",str(p["encoder_lr_ratio"])))
    if p.get("barrier_contract"):
        args.extend(("--barrier_contract",str(p["barrier_contract"])))
    if p.get("extension_disabled") is True:args.append("--extension_disabled")
    args.extend(("--manifest",str(m["manifest_path"]),"--approval",str(m["approval_path"]),
                 "--headless","--device","cuda:0"))
    return args

SHORT_MATCH=("parent_sha256","agent_yaml_sha256","encoder_mode","schedule",
    "reward_variant","foot_spacing_m",
    "seed","num_envs","updates","rollout_steps","epochs","minibatches",
    "checkpoint_interval","map_init_seed","gap_proportion","stones_proportion",
    "step_height_m","step_width_m","geometry_tolerance_m","lr","clip_param",
    "gamma","lam","value_loss_coef","entropy_coef","max_grad_norm",
    "desired_kl","use_clipped_value_loss")

def short_conditions_sha256(m):
    return hashlib.sha256(canonical({k:m["plan"].get(k) for k in SHORT_MATCH})).hexdigest()

def check_short_sequence(m):
    """The second single run is admitted only after the first receipt is final."""
    pair=m.get("short_pair")
    if not isinstance(pair,dict) or pair.get("pair_id")!=m.get("chain_id"):
        raise TrainHold("short_pair_identity")
    if pair.get("ordinal")==1:
        if m["plan"]["arm"]!="A" or pair.get("previous_receipt_path") or pair.get("previous_receipt_sha256"):
            raise TrainHold("short_first_arm")
        return True
    if pair.get("ordinal")!=2 or m["plan"]["arm"]!="B":
        raise TrainHold("short_second_arm")
    prior_path=Path(pair.get("previous_receipt_path") or "missing")
    if not prior_path.is_file() or sha(prior_path)!=pair.get("previous_receipt_sha256"):
        raise TrainHold("previous_short_receipt_hash")
    prior=json.loads(prior_path.read_text(encoding="utf-8"))
    if (prior.get("chain_id")!=m["chain_id"] or prior.get("arm")!="A" or
        prior.get("stage")!="short" or prior.get("extension_disabled") is not True or
        prior.get("verdict")!="RUN_COMPLETE_UNVERIFIED" or
        prior.get("family_cleanup_confirmed") is not True or
        prior.get("family_active_count")!=0 or
        prior.get("gpu_lease_released") is not True or
        prior.get("usd_lock_released") is not True or
        prior.get("parent_sha256_before")!=PARENT_SHA or
        prior.get("parent_sha256_after")!=PARENT_SHA or
        prior.get("short_conditions_sha256")!=short_conditions_sha256(m) or
        prior.get("executed_updates")!=2000 or
        prior.get("out_root")==m["plan"]["out_root"] or
        prior.get("claim_path")==str(Path(m["claim_root"])/(m["chain_id"]+"-B.claim")) or
        prior.get("execution_id")==m.get("execution_id")):
        raise TrainHold("previous_short_not_clean")
    return True

def _inside(path,folder):
    p=Path(path).resolve();root=Path(folder).resolve()
    return p==root or root in p.parents

def validate(m,approval,*,now=None,check_files=True,phase="prepare"):
    now=time.time() if now is None else now
    if not isinstance(m,dict) or not isinstance(approval,dict):raise TrainHold("manifest_or_approval")
    if undecided(m) or undecided(approval):raise TrainHold("undecided_value")
    stage=m.get("plan",{}).get("stage") if isinstance(m.get("plan"),dict) else None
    scope=PLUMBING_SCOPE if stage=="plumbing" else SCOPE
    if m.get("scope")!=scope or m.get("observer_mode")!="attended" or m.get("retry_count")!=0:
        raise TrainHold("attended_one_arm_scope")
    if (approval.get("status")!="APPROVED" or approval.get("scope")!=scope or
        approval.get("chain_id")!=m.get("chain_id") or not approval.get("by") or
        not approval.get("approval_id") or approval.get("eula_accepted") is not True):
        raise TrainHold("approval_missing_or_eula")
    if approval.get("manifest_sha256")!=hashlib.sha256(canonical(m)).hexdigest():
        raise TrainHold("approval_digest")
    if not (now<float(m.get("deadline_epoch",0))<=float(approval.get("expires_epoch",0))):
        raise TrainHold("deadline_or_expiry")
    if m.get("gpu_index")!=0 or not m.get("gpu_uuid") or not m.get("gpu_bus_id"):
        raise TrainHold("gpu_identity")
    for key in ("max_wall_s","min_free_vram_bytes","running_floor_vram_bytes",
                "min_free_disk_bytes","max_disk_bytes"):
        value=m.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
            raise TrainHold("resource_budget_"+key)
    if m["max_disk_bytes"]<16*1024*1024:raise TrainHold("output_budget_too_small")
    if m["deadline_epoch"]-now<m["max_wall_s"]+30:raise TrainHold("cleanup_time_missing")
    if str(Path(m.get("python_path","missing")).resolve()).lower()!=str(PYTHON.resolve()).lower():
        raise TrainHold("python_interpreter")
    if Path(m.get("entry_path","missing")).resolve()!=(HERE/"s2_train_entry_17v.py").resolve():
        raise TrainHold("entry_path")
    p=m.get("plan")
    if not isinstance(p,dict):raise TrainHold("plan_missing")
    from s2_foot_config import validate_variant
    try:validate_variant(p.get("reward_variant","none"),p.get("foot_spacing_m"))
    except ValueError as ex:raise TrainHold(str(ex)) from ex
    if (p.get("num_envs")!=1024 and not (stage=="plumbing" and
        type(p.get("num_envs")) is int and 2<=p["num_envs"]<=1024)) or \
       p.get("gap_proportion")!=.15 or p.get("stones_proportion")!=.15:
        raise TrainHold("sparse_1024_plan")
    if p.get("deadline_epoch")!=m["deadline_epoch"]:
        raise TrainHold("child_deadline_differs")
    if p.get("arm") not in ("A","B") or p.get("seed") is None or p.get("encoder_mode") not in ("full_freeze","schedule"):
        raise TrainHold("arm_seed_encoder")
    if "PLUMBING_ONLY_" in str(p.get("parent","")):
        raise TrainHold("plumbing_parent_forbidden")
    if p.get("stage")=="plumbing":
        if type(p.get("updates")) is not int or p["updates"] not in (1,2) or p.get("checkpoint_interval")!=p["updates"]:
            raise TrainHold("plumbing_update_boundary")
        if any(p.get(k) for k in ("barrier_contract","resume","increment","allowed_increments","max_total_updates","grant")):
            raise TrainHold("plumbing_barrier_resume_forbidden")
        if (type(p.get("rollout_steps")) is not int or type(p.get("epochs")) is not int or
            type(p.get("minibatches")) is not int or min(p["rollout_steps"],p["epochs"],p["minibatches"])<=0 or
            p["rollout_steps"]*p["num_envs"]<p["minibatches"] or
            (p["rollout_steps"]*p["num_envs"])%p["minibatches"]):
            raise TrainHold("plumbing_batch_divisibility")
        if m["max_wall_s"]>600:raise TrainHold("plumbing_wall_cap")
        if m.get("plumbing_only") is not True:raise TrainHold("plumbing_only_required")
        if m.get("stage0_passed") is not False:raise TrainHold("stage0_must_be_false")
        if m.get("input_path") not in ("live_raycaster_unverified","synthetic_known_answer"):
            raise TrainHold("input_path_required")
        try:check_sequence(m)
        except Exception as ex:raise TrainHold(str(ex)) from ex
    elif p.get("stage")=="smoke":
        if m.get("plumbing_only") is True:raise TrainHold("plumbing_auto_promotion_forbidden")
        if p.get("updates")!=200 or p.get("checkpoint_interval")!=200:
            raise TrainHold("smoke_200_boundary")
    elif p.get("stage")=="short":
        if m.get("plumbing_only") is True:raise TrainHold("plumbing_auto_promotion_forbidden")
        if p.get("updates")!=2000 or p.get("checkpoint_interval")!=200:
            raise TrainHold("short_2000_boundary")
        if p.get("extension_disabled") is True:
            if (m.get("extension_disabled") is not True or
                p.get("barrier_contract") or p.get("resume") or p.get("increment") or
                p.get("grant") or p.get("max_total_updates") or
                p.get("allowed_increments") or m.get("extension") or
                m.get("checkpoint_boundaries")!=list(range(0,2001,200)) or
                m.get("exploratory_short") is not True or
                type(m.get("map_contract_verified")) is not bool or
                m.get("stage0_state") not in ("UNVERIFIED","HOLD","FAIL","PASS") or
                not m.get("execution_id") or
                m.get("completion_deadline_cap_epoch")!=1792206000 or
                m["deadline_epoch"]>m["completion_deadline_cap_epoch"]):
                raise TrainHold("short_single_scope")
            check_short_sequence(m)
            if m["map_contract_verified"] is not True:
                raise TrainHold("short_map_contract_unverified")
        elif not p.get("barrier_contract") or not p.get("barrier_contract_sha256"):
            raise TrainHold("extension_barrier_missing")
    else:raise TrainHold("stage_scope")
    if p.get("use_clipped_value_loss") not in ("true","false"):
        raise TrainHold("value_clip_choice")
    if p.get("parent_sha256")!=PARENT_SHA or not p.get("agent_yaml_sha256"):
        raise TrainHold("parent_pin")
    output_keys=("out_root","stop_file")
    manifest_keys=("status_path","log_path","prelaunch_report_path","claim_root","gpu_lease_root")
    for key in output_keys:
        if not p.get(key):raise TrainHold("output_path_missing_"+key)
    for key in manifest_keys:
        if not m.get(key):raise TrainHold("output_path_missing_"+key)
    for path in [*(p[key] for key in output_keys),*(m[key] for key in manifest_keys)]:
        if any(_inside(path,root) for root in
               ("C:/isaac/ext/go2_rl_robotlab/_eval","C:/isaac/ext/go2_rl_robotlab/source")):
            raise TrainHold("readonly_output")
    if phase not in ("prepare","child"):raise TrainHold("contract_phase")
    output=Path(p["out_root"])
    if Path(p["stop_file"]).exists():raise TrainHold("output_or_STOP_exists")
    if phase=="prepare" and output.exists():raise TrainHold("output_or_STOP_exists")
    if phase=="child" and output.exists() and {x.name for x in output.iterdir()}!={"usd"}:
        raise TrainHold("output_or_STOP_exists")
    for key in ("status_path","log_path","prelaunch_report_path"):
        if not m.get(key) or (phase=="prepare" and Path(m[key]).exists()):
            raise TrainHold("output_path_reused_"+key)
    if Path(m.get("usd_lock_path","missing")).resolve()!=Path(
        "C:/isaac/ext/go2_rl_robotlab/_eval/slot/isaac_convert.lock").resolve():
        raise TrainHold("usd_lock_path")
    if (Path(m.get("usd_root","missing")).resolve()!=
        (Path(p["out_root"]).resolve()/"usd").resolve() or
        m.get("expect_conversions")!=1 or
        sha(HERE/"usd_isolate_run_v3.py")!=USD_WRAPPER_SHA):
        raise TrainHold("usd_isolation_contract")
    if entry_argv(m)!=m.get("entry_argv"):raise TrainHold("entry_argv_exact")
    if any(str(x).count("--device") for x in m["entry_argv"][:-2]):
        raise TrainHold("device_duplicate")
    hashes=m.get("code_hashes")
    if not isinstance(hashes,dict) or set(hashes)!=set(CODE):raise TrainHold("code_closure")
    if check_files:
        for name in CODE:
            if not (HERE/name).is_file() or sha(HERE/name)!=hashes[name]:
                raise TrainHold("code_hash_"+name)
        if sha(PYTHON)!=m.get("python_sha256"):raise TrainHold("python_hash")
        if sha(p["parent"])!=PARENT_SHA or sha(p["agent_yaml"])!=p["agent_yaml_sha256"]:
            raise TrainHold("parent_or_yaml_hash")
        if sha(p["sensor_hook_path"])!=p.get("sensor_hook_sha256"):
            raise TrainHold("sensor_hook_hash")
        if p.get("stage")=="short" and p.get("extension_disabled") is not True and sha(p["barrier_contract"])!=p["barrier_contract_sha256"]:
            raise TrainHold("barrier_contract_hash")
        if p.get("stage")=="short" and p.get("extension_disabled") is not True:
            barrier=json.loads(Path(p["barrier_contract"]).read_text(encoding="utf-8"))
            if (barrier.get("chain_id")!=m["chain_id"] or barrier.get("arm")!=p["arm"] or
                barrier.get("approval_id")!=approval["approval_id"] or
                barrier.get("stop_file")!=p["stop_file"] or
                barrier.get("deadline_epoch")!=m["deadline_epoch"] or
                barrier.get("initial_short_updates")!=2000 or
                barrier.get("max_total_updates",0)<2500 or
                barrier.get("allowed_increments")!=[500]):
                raise TrainHold("extension_barrier_identity")
    return True
