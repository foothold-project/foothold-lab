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

CHILD_ENV={"OMNI_KIT_ACCEPT_EULA":"YES","PYTHONUNBUFFERED":"1",
           "CUDA_DEVICE_ORDER":"PCI_BUS_ID","CUDA_VISIBLE_DEVICES":"0"}

def child_environment(base):
    env=dict(base);env.update(CHILD_ENV)
    return env

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
        if process_probe():raise TrainHold("competing_isaac")
        if meter is None:own_meter=NvmlMeter();meter=own_meter
        sample=meter.probe(0)
        free=disk_probe(Path(m["plan"]["out_root"]).parent)
        resource_preflight(sample,free,m)
        gpu=gpu_lock(Path(m["gpu_lease_root"]),m["gpu_uuid"]).acquire()
        usd=usd_lock(Path(m["usd_lock_path"])).acquire()
        report.update(status="GO",device=sample,free_disk_bytes=free,
                      child_env_keys=CHILD_ENV,entry_argv=entry_argv(m),cwd=str(HERE),
                      stdin="NUL",observer_mode="attended")
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
    def beat(state,**fields):
        atomic_json(status,{"chain_id":m["chain_id"],"arm":m["plan"]["arm"],
            "stage":m["plan"]["stage"],"state":state,"heartbeat_epoch":clock(),
            "remaining_s":max(0,min(m["deadline_epoch"]-clock(),limit-mono())),**fields})
    try:
        gpu=gpu_lock(Path(m["gpu_lease_root"]),m["gpu_uuid"]).acquire()
        usd=usd_lock(Path(m["usd_lock_path"])).acquire()
        meter=meter_factory();first=meter.probe(0)
        initial_free=disk_probe(Path(m["plan"]["out_root"]).parent)
        resource_preflight(first,initial_free,m)
        if process_probe():raise TrainHold("competing_isaac")
        owner=(owner_factory or (lambda:JobOwner(WinKernel())))()
        argv=entry_argv(m)
        log=Path(m["log_path"]);log.parent.mkdir(parents=True,exist_ok=True)
        owner.launch(argv,HERE,child_environment(os.environ),log_path=log)
        beat("RUNNING",pid=owner.pid,argv=argv,cwd=str(HERE))
        while owner.active_count():
            if stop.exists():reason="STOP";break
            if clock()>=m["deadline_epoch"] or mono()>=limit:reason="deadline";break
            try:
                sample=meter.probe(0)
                free=disk_probe(Path(m["plan"]["out_root"]).parent)
                used=max(initial_free-free,tree_probe(Path(m["plan"]["out_root"]))+tree_probe(log.parent))
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
        checkpoints=sorted(Path(m["plan"]["out_root"]).glob("checkpoint_*.pt"))
        count=None if result is None else result.get("executed_updates",result.get("updates_per_arm"))
        required=(0,200) if m["plan"]["stage"]=="smoke" else (0,200,2000,count)
        boundary_ok=(type(count) is int and
                     (count==200 if m["plan"]["stage"]=="smoke" else count>=2500 and count%500==0) and
                     all((Path(m["plan"]["out_root"])/f"checkpoint_{n:06d}.pt").is_file()
                         for n in required) and all(p.stat().st_size>0 for p in checkpoints))
        receipt={"chain_id":m["chain_id"],"arm":m["plan"]["arm"],"stage":m["plan"]["stage"],
            "manifest_sha256":hashlib.sha256(canonical(m)).hexdigest(),
            "approval_sha256":hashlib.sha256(canonical(a)).hexdigest(),
            "started_epoch":started,"ended_epoch":clock(),"exit_code":exit_code,
            "family_active_count":owner.active_count(),"reason":reason,
            "result_sha256":sha(result_path) if result_path.is_file() else None,
            "checkpoint_sha256":{p.name:sha(p) for p in checkpoints},
            "log_sha256":sha(log) if log.is_file() else None,
            "executed_updates":count,"boundary_ok":boundary_ok,
            "verdict":"RUN_COMPLETE_UNVERIFIED" if reason is None and exit_code==0 and result and
                 result.get("status")=="RUN_COMPLETE_UNVERIFIED" and family_empty and boundary_ok else "HOLD"}
        atomic_json(claim/"chain.receipt.json",receipt)
        beat("FINISHED" if receipt["verdict"]=="RUN_COMPLETE_UNVERIFIED" else "HOLD",
             verdict=receipt["verdict"],reason=reason,exit_code=exit_code,family_active_count=owner.active_count())
        return receipt
    except Exception as ex:
        reason="launch_exception:"+repr(ex)
        try:beat("HOLD",reason=reason)
        except OSError:pass
        atomic_json(claim/"chain.receipt.json",{"chain_id":m["chain_id"],"arm":m["plan"]["arm"],
            "verdict":"HOLD","reason":reason,"started_epoch":started,"ended_epoch":clock(),
            "family_active_count":None if owner is None else owner.active_count()})
        return {"verdict":"HOLD","reason":reason}
    finally:
        if owner is not None:
            try:
                if owner.active_count():owner.stop_owned(wait_seconds=10.)
                family_empty=owner.active_count()==0
                owner.close()
            except Exception:family_empty=False
        else:family_empty=True
        if gpu is not None:gpu.release(family_empty=family_empty)
        if usd is not None:usd.release(family_empty=family_empty)
        if meter is not None:meter.close()

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
