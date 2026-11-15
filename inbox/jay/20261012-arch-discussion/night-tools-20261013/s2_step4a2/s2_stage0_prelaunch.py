"""Read-only go/no-go check for lead immediately before an attended one-shot launch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from s2_resource_lease import gpu_lease,usd_conversion_lock
from s2_stage0_contract_a2 import validate_a2
from s2_stage0_resources_a2 import NvmlMeter,disk_free,preflight
from s2_zero_supervisor import validate,atomic_json,canonical


def competing_isaac_processes():
    import psutil
    found=[]
    for process in psutil.process_iter(["pid","name"]):
        try:
            name=(process.info["name"] or "").lower()
            if "kit.exe" in name or "isaac-sim" in name:
                found.append({"pid":process.info["pid"],"name":name})
        except (psutil.AccessDenied,psutil.NoSuchProcess) as ex:
            raise RuntimeError("process_inventory_unreadable") from ex
    return found


def prelaunch(manifest,approval,*,meter=None,disk_probe=disk_free,process_probe=competing_isaac_processes,
              gpu_lock=gpu_lease,usd_lock=usd_conversion_lock,clock=time.time):
    bundle=Path(__file__).resolve().parent
    report={"status":"NO_GO","checked_epoch":clock(),"manifest_sha256":hashlib.sha256(canonical(manifest)).hexdigest()}
    nvml=None;gpu=None;usd=None
    try:
        validate(manifest,approval,now=clock(),cpu_fixture=False)
        validate_a2(manifest,bundle)
        if manifest["deadline_epoch"]-clock()<manifest["max_wall_s"]+30:
            raise RuntimeError("insufficient_deadline_for_cleanup")
        if process_probe():raise RuntimeError("other_isaac_process_present")
        if meter is None:nvml=NvmlMeter();meter=nvml
        sample=meter.probe(manifest["gpu_index"])
        free=disk_probe(Path(manifest["out_root"]).parent)
        preflight(sample,free,manifest)
        gpu=gpu_lock(Path(manifest["lease_root"]),manifest["gpu_uuid"]).acquire()
        usd=usd_lock(Path(manifest["usd_lock_path"])).acquire()
        report.update(status="GO",device=sample,free_disk_bytes=free,
                      observer_mode="attended",termination="Job Object owner only",
                      logs=manifest["log_path"],usd_root=manifest["usd_root"],
                      output=manifest["out_root"],retry_count=0)
    except Exception as ex:
        report["reason"]=str(ex)
    finally:
        if usd is not None:usd.release(family_empty=True)
        if gpu is not None:gpu.release(family_empty=True)
        if nvml is not None:nvml.close()
    path=Path(manifest["prelaunch_report_path"])
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise RuntimeError("prelaunch_report_reused")
    atomic_json(path,report)
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--approval",type=Path,required=True)
    a=ap.parse_args()
    m=json.loads(a.manifest.read_text(encoding="utf-8"))
    approval=json.loads(a.approval.read_text(encoding="utf-8"))
    report=prelaunch(m,approval)
    print(json.dumps(report,sort_keys=True),flush=True)
    return 0 if report["status"]=="GO" else 42


if __name__=="__main__":raise SystemExit(main())
