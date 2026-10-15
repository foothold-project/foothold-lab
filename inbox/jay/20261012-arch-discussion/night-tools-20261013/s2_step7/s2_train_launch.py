"""Attended one-arm S2 launch. A4 r2 ownership rules; unattended remains closed."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from s2_job_owner import JobOwner,WinKernel
from s2_resource_lease import gpu_lease,usd_conversion_lock
from s2_stage0_resources_a2 import NvmlMeter,disk_free,tree_bytes,preflight as resource_preflight,running
from s2_train_contract import TrainHold,canonical,entry_argv,sha,validate,HERE
from s2_plumbing import known_input_probe,verify_result,verify_live_evidence

CHILD_ENV={"OMNI_KIT_ACCEPT_EULA":"YES","PYTHONUNBUFFERED":"1",
           "CUDA_DEVICE_ORDER":"PCI_BUS_ID","CUDA_VISIBLE_DEVICES":"0"}

def child_environment(base,m=None):
    env=dict(base);env.update(CHILD_ENV)
    if m is not None:
        env["FOOTHOLD_USD_ROOT"]=str(m["usd_root"])
        env["FOOTHOLD_EXPECT_CONVERSIONS"]=str(m["expect_conversions"])
    return env

def usd_evidence(m,result):
    root=Path(m["usd_root"]).resolve()
    state_path=root/"isolate_state.json";assigned_path=root/"assigned.jsonl"
    if not state_path.is_file() or not assigned_path.is_file() or not isinstance(result,dict):
        raise TrainHold("usd_isolation_evidence_missing")
    state=json.loads(state_path.read_text(encoding="utf-8"))
    assigned=[json.loads(line) for line in assigned_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if (state.get("version")!="v3" or Path(state.get("root","missing")).resolve()!=root or
        state.get("expect_conversions")!="1" or state.get("conversions")!=1 or
        state.get("blocked") or len(assigned)!=1 or
        assigned[0].get("kind") not in ("assigned","explicit_inside")):
        raise TrainHold("usd_isolation_state_invalid")
    directory=Path(assigned[0]["usd_dir"]).resolve()
    if root not in directory.parents or not directory.is_dir():
        raise TrainHold("usd_assigned_outside_run")
    asset=Path(assigned[0]["asset_path"])
    generated=directory/(asset.stem+".usd")
    refs=[Path(x).resolve() for x in result.get("usd_reference_paths",[])]
    if not generated.is_file() or refs!=[generated]:
        raise TrainHold("usd_actual_reference_mismatch")
    return {"root":str(root),"state_sha256":sha(state_path),
            "assigned_sha256":sha(assigned_path),"conversion_count":1,
            "generated_path":str(generated),"generated_sha256":sha(generated),
            "actual_reference_paths":[str(x) for x in refs],
            "warnings":state.get("warnings",[]),"verified":True}

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_bytes(canonical(value))
    os.replace(tmp,path)

def competing_isaac():
    import psutil
    found=[]
    for p in psutil.process_iter(["pid","name"]):
        try:
            name=(p.info["name"] or "").lower()
            if "kit.exe" in name or "isaac-sim" in name:found.append(p.info["pid"])
        except (psutil.AccessDenied,psutil.NoSuchProcess) as ex:
            raise TrainHold("process_inventory_unreadable") from ex
    return found

def prelaunch(m,a,*,meter=None,disk_probe=disk_free,process_probe=competing_isaac,
              gpu_lock=gpu_lease,usd_lock=usd_conversion_lock,clock=time.time):
    report={"status":"NO_GO","checked_epoch":clock(),
            "manifest_sha256":hashlib.sha256(canonical(m)).hexdigest()}
    own_meter=None;gpu=None;usd=None
    try:
        validate(m,a,now=clock())
        if m["plan"]["stage"]=="plumbing":report["known_input"]=known_input_probe()
        if process_probe():raise TrainHold("competing_isaac")
        if Path(m["usd_root"]).exists():raise TrainHold("usd_root_preexisting")
        if meter is None:own_meter=NvmlMeter();meter=own_meter
        sample=meter.probe(0)
        free=disk_probe(Path(m["plan"]["out_root"]).parent)
        resource_preflight(sample,free,m)
        gpu=gpu_lock(Path(m["gpu_lease_root"]),m["gpu_uuid"]).acquire()
        usd=usd_lock(Path(m["usd_lock_path"])).acquire()
        report.update(status="GO",device=sample,free_disk_bytes=free,
                      child_env_keys=CHILD_ENV,entry_argv=entry_argv(m),cwd=str(HERE),
                      stdin="NUL",observer_mode="attended",usd_root=m["usd_root"],
                      usd_root_preexisting=Path(m["usd_root"]).exists())
    except Exception as ex:report["reason"]=str(ex)
    finally:
        if usd is not None:usd.release(family_empty=True)
        if gpu is not None:gpu.release(family_empty=True)
        if own_meter is not None:own_meter.close()
    path=Path(m["prelaunch_report_path"])
    if path.exists():raise TrainHold("prelaunch_reused")
    atomic_json(path,report)
    return report

def run(m,a,*,owner_factory=None,meter_factory=NvmlMeter,disk_probe=disk_free,
        tree_probe=tree_bytes,gpu_lock=gpu_lease,usd_lock=usd_conversion_lock,
        process_probe=competing_isaac,clock=time.time,mono=time.monotonic,sleep=time.sleep):
    validate(m,a,now=clock(),phase="child")
    report_path=Path(m["prelaunch_report_path"])
    if not report_path.is_file():raise TrainHold("prelaunch_missing")
    report=json.loads(report_path.read_text(encoding="utf-8"))
    if (report.get("status")!="GO" or report.get("manifest_sha256")!=hashlib.sha256(canonical(m)).hexdigest()
        or not 0<=clock()-report.get("checked_epoch",0)<=60):
        raise TrainHold("prelaunch_stale_or_mismatched")
    claim=Path(m["claim_root"])/(m["chain_id"]+"-"+m["plan"]["arm"]+".claim")
    claim.parent.mkdir(parents=True,exist_ok=True)
    claim.mkdir(exist_ok=False)
    atomic_json(claim/"approval_digest.json",{"sha256":hashlib.sha256(canonical(a)).hexdigest()})
    started=clock();limit=mono()+min(m["max_wall_s"],m["deadline_epoch"]-started)
    status=Path(m["status_path"]);stop=Path(m["plan"]["stop_file"])
    owner=None;gpu=None;usd=None;meter=None;reason=None;exit_code=None;family_empty=False
    receipt=None;parent_before=None;cleanup_confirmed=False
    initial_sample=None;initial_free=None;min_free_vram=None;min_free_disk=None;max_output_bytes=0
    def beat(state,**fields):
        atomic_json(status,{"chain_id":m["chain_id"],"arm":m["plan"]["arm"],
            "stage":m["plan"]["stage"],"state":state,"heartbeat_epoch":clock(),
            "remaining_s":max(0,min(m["deadline_epoch"]-clock(),limit-mono())),**fields})
    try:
        gpu=gpu_lock(Path(m["gpu_lease_root"]),m["gpu_uuid"]).acquire()
        usd=usd_lock(Path(m["usd_lock_path"])).acquire()
        meter=meter_factory();first=meter.probe(0)
        initial_free=disk_probe(Path(m["plan"]["out_root"]).parent)
        initial_sample=dict(first);min_free_vram=first["free_vram_bytes"];min_free_disk=initial_free
        resource_preflight(first,initial_free,m)
        if process_probe():raise TrainHold("competing_isaac")
        parent_before=sha(m["plan"]["parent"])
        usd_preexisting=Path(m["usd_root"]).exists()
        if usd_preexisting:raise TrainHold("usd_root_preexisting")
        owner=(owner_factory or (lambda:JobOwner(WinKernel())))()
        argv=entry_argv(m)
        log=Path(m["log_path"]);log.parent.mkdir(parents=True,exist_ok=True)
        owner.launch(argv,HERE,child_environment(os.environ,m),log_path=log)
        beat("RUNNING",pid=owner.pid,argv=argv,cwd=str(HERE))
        while owner.active_count():
            if stop.exists():reason="STOP";break
            if clock()>=m["deadline_epoch"] or mono()>=limit:reason="deadline";break
            try:
                sample=meter.probe(0)
                free=disk_probe(Path(m["plan"]["out_root"]).parent)
                used=max(initial_free-free,tree_probe(Path(m["plan"]["out_root"]))+tree_probe(log.parent))
                min_free_vram=min(min_free_vram,sample["free_vram_bytes"])
                min_free_disk=min(min_free_disk,free);max_output_bytes=max(max_output_bytes,used)
                running(sample,free,used,m)
                beat("RUNNING",device=sample,free_disk_bytes=free,output_bytes=used)
            except Exception as ex:reason="resource:"+str(ex);break
            sleep(1.)
        if reason:owner.stop_owned(wait_seconds=10.)
        family_empty=owner.active_count()==0
        exit_code=owner.exit_code()
        result_path=Path(m["plan"]["out_root"])/(
            "chain_result.json" if m["plan"].get("barrier_contract") else "result.json")
        result=json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else None
        plumbing=m["plan"]["stage"]=="plumbing"
        checkpoints=sorted(Path(m["plan"]["out_root"]).glob(
            "PLUMBING_ONLY_checkpoint_*.pt" if plumbing else "checkpoint_*.pt"))
        count=None if result is None else result.get("executed_updates",result.get("updates_per_arm"))
        usd_record=None
        try:usd_record=usd_evidence(m,result)
        except Exception as ex:reason="usd_proof:"+str(ex)
        if plumbing:
            try:
                boundary_ok=verify_result(m,result,Path(m["plan"]["out_root"]))
                boundary_ok=verify_live_evidence(m,result)
            except Exception as ex:boundary_ok=False;reason="plumbing_proof:"+str(ex)
        else:
            required=(0,200) if m["plan"]["stage"]=="smoke" else (0,200,2000,count)
            boundary_ok=(type(count) is int and
                         (count==200 if m["plan"]["stage"]=="smoke" else count>=2500 and count%500==0) and
                         all((Path(m["plan"]["out_root"])/f"checkpoint_{n:06d}.pt").is_file()
                             for n in required) and all(p.stat().st_size>0 for p in checkpoints))
        parent_after=sha(m["plan"]["parent"])
        receipt={"chain_id":m["chain_id"],"arm":m["plan"]["arm"],"stage":m["plan"]["stage"],
            "claim_path":str(claim),"job_pid":owner.pid,
            "gpu_lease_root":m["gpu_lease_root"],"usd_lock_path":m["usd_lock_path"],
            "pair_id":m["chain_id"] if plumbing else None,
            "pair_ordinal":m.get("plumbing_pair",{}).get("ordinal") if plumbing else None,
            "out_root":m["plan"]["out_root"],"gpu_uuid":m["gpu_uuid"],
            "manifest_sha256":hashlib.sha256(canonical(m)).hexdigest(),
            "approval_sha256":hashlib.sha256(canonical(a)).hexdigest(),
            "started_epoch":started,"ended_epoch":clock(),"exit_code":exit_code,
            "family_active_count":owner.active_count(),"reason":reason,
            "result_sha256":sha(result_path) if result_path.is_file() else None,
            "checkpoint_sha256":{p.name:sha(p) for p in checkpoints},
            "usd_isolation":usd_record,
            "usd_root_preexisting_at_launch":usd_preexisting,
            "device_binding_evidence_sha256":sha(Path(m["usd_root"])/"device_binding.json")
                if (Path(m["usd_root"])/"device_binding.json").is_file() else None,
            "prelaunch_device":report.get("device"),"initial_device":initial_sample,
            "initial_free_disk_bytes":initial_free,"min_free_vram_bytes":min_free_vram,
            "min_free_disk_bytes":min_free_disk,"max_output_bytes":max_output_bytes,
            "resource_limits":{k:m[k] for k in ("min_free_vram_bytes","running_floor_vram_bytes",
                "min_free_disk_bytes","max_disk_bytes","max_wall_s")},
            "argv":argv,"python_path":m["python_path"],
            "device_binding":None if result is None else result.get("device_binding"),
            "runtime_imports":None if result is None else result.get("runtime_imports"),
            "final_cfg_sha256":None if result is None else result.get("final_cfg_sha256"),
            "sensor_mount_translation_b":None if result is None else result.get("sensor_mount_translation_b"),
            "tensor_contracts":None if result is None else [r.get("tensor_contract") for r in result.get("records",[])],
            "completed_iteration":None if result is None else result.get("completed_iteration"),
            "vector_steps":None if result is None else result.get("vector_steps"),
            "optimizer_steps_actual":None if result is None else result.get("optimizer_steps_actual"),
            "sensor_reads_total":None if result is None else result.get("sensor_reads_total"),
            "log_sha256":sha(log) if log.is_file() else None,
            "executed_updates":count,"boundary_ok":boundary_ok,
            "rollout_steps":m["plan"]["rollout_steps"],
            "environment_steps":None if result is None else result.get("environment_steps"),
            "input_path":m.get("input_path"),
            "input_limitation":None if result is None else result.get("input_limitation"),
            "plumbing_checks":None if result is None else result.get("plumbing_checks"),
            "stage0_passed":False if plumbing else None,
            "performance_verified":False if plumbing else None,
            "parent_sha256_before":parent_before,"parent_sha256_after":parent_after,
            "verdict":"RUN_COMPLETE_UNVERIFIED" if reason is None and exit_code==0 and result and
                 result.get("status")=="RUN_COMPLETE_UNVERIFIED" and family_empty and boundary_ok and
                 (not plumbing or parent_before==parent_after) else "HOLD"}
        atomic_json(claim/"chain.receipt.json",receipt)
        beat("FINISHED" if receipt["verdict"]=="RUN_COMPLETE_UNVERIFIED" else "HOLD",
             verdict=receipt["verdict"],reason=reason,exit_code=exit_code,family_active_count=owner.active_count())
        return receipt
    except Exception as ex:
        reason="launch_exception:"+repr(ex)
        try:beat("HOLD",reason=reason)
        except OSError:pass
        receipt={"chain_id":m["chain_id"],"arm":m["plan"]["arm"],
            "verdict":"HOLD","reason":reason,"started_epoch":started,"ended_epoch":clock(),
            "family_active_count":None if owner is None else owner.active_count(),
            "parent_sha256_before":parent_before,
            "parent_sha256_after":sha(m["plan"]["parent"]) if parent_before else None}
        atomic_json(claim/"chain.receipt.json",receipt)
        return receipt
    finally:
        if owner is not None:
            try:
                if owner.active_count():owner.stop_owned(wait_seconds=10.)
                family_empty=owner.active_count()==0
                owner.close()
                cleanup_confirmed=family_empty
            except Exception:family_empty=False
        else:family_empty=True
        cleanup_errors=[];gpu_released=False;usd_released=False
        if gpu is not None:
            try:
                gpu.release(family_empty=family_empty)
                gpu_released=(getattr(gpu,"fd",None) is None) if hasattr(gpu,"fd") else bool(getattr(gpu,"released",False))
            except Exception as ex:cleanup_errors.append("gpu_lease:"+repr(ex))
        if usd is not None:
            try:
                usd.release(family_empty=family_empty)
                usd_released=(getattr(usd,"fd",None) is None) if hasattr(usd,"fd") else bool(getattr(usd,"released",False))
            except Exception as ex:cleanup_errors.append("usd_lock:"+repr(ex))
        if meter is not None:
            try:meter.close()
            except Exception as ex:cleanup_errors.append("meter:"+repr(ex))
        if m["plan"]["stage"]=="plumbing" and receipt is not None:
            receipt["family_cleanup_confirmed"]=cleanup_confirmed
            receipt["family_active_count"]=0 if cleanup_confirmed else None
            receipt["gpu_lease_released"]=gpu_released
            receipt["usd_lock_released"]=usd_released
            receipt["cleanup_errors"]=cleanup_errors
            if not cleanup_confirmed:receipt["verdict"]="HOLD";receipt["reason"]="family_cleanup_unconfirmed"
            if not receipt["gpu_lease_released"] or not receipt["usd_lock_released"]:
                receipt["verdict"]="HOLD";receipt["reason"]="resource_cleanup_unconfirmed"
            if cleanup_errors:
                receipt["verdict"]="HOLD";receipt["reason"]="cleanup_error"
            atomic_json(claim/"chain.receipt.json",receipt)
            (claim/"chain.receipt.sha256").write_text(sha(claim/"chain.receipt.json"),encoding="ascii")
            beat("FINISHED" if receipt["verdict"]=="RUN_COMPLETE_UNVERIFIED" else "HOLD",
                 verdict=receipt["verdict"],reason=receipt.get("reason"),
                 family_active_count=receipt.get("family_active_count"),
                 family_cleanup_confirmed=cleanup_confirmed)

def main():
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--approval",required=True,type=Path);p.add_argument("--prelaunch",action="store_true")
    x=p.parse_args();m=json.loads(x.manifest.read_text(encoding="utf-8"))
    a=json.loads(x.approval.read_text(encoding="utf-8"))
    if x.manifest.resolve()!=Path(m.get("manifest_path","missing")).resolve() or \
       x.approval.resolve()!=Path(m.get("approval_path","missing")).resolve():
        raise TrainHold("approval_file_path_differs")
    result=prelaunch(m,a) if x.prelaunch else run(m,a)
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0 if result.get("status")=="GO" or result.get("verdict")=="RUN_COMPLETE_UNVERIFIED" else 42

if __name__=="__main__":raise SystemExit(main())
