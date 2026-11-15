"""Stage-0-only owner. No Isaac import. Live use needs an external approval bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from s2_job_owner import JobOwner, WinKernel, OwnershipHold
from s2_resource_lease import gpu_lease, LeaseHold
from s2_stage_gate_17v import zero_stage_verdict


class ZeroHold(RuntimeError):pass


def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()


def canonical(obj)->bytes:
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def atomic_json(path:Path,value):
    tmp=path.with_name(path.name+".tmp")
    tmp.write_bytes(canonical(value))
    for attempt in range(200):
        try:os.replace(tmp,path);return
        except PermissionError:
            if attempt==199:raise
            time.sleep(.01)


def validate(manifest,approval,*,now,cpu_fixture=False):
    for k in ("chain_id","attempt","python_path","python_sha256","diag_path","diag_sha256",
              "criteria_path","criteria_sha256","parent_path","parent_sha256","out_root",
              "claim_root","status_path","stop_path","lease_root","gpu_uuid","gpu_index",
              "diag_args","deadline_epoch","max_wall_s","max_disk_bytes"):
        if k not in manifest or manifest[k] in (None,"","UNDECIDED"):
            raise ZeroHold("missing_"+k)
    if any(re.fullmatch(r"[A-Za-z0-9_.-]{1,80}",manifest[k]) is None for k in ("chain_id","attempt")):
        raise ZeroHold("claim_id")
    if approval.get("status")!="APPROVED" or approval.get("chain_id")!=manifest["chain_id"] or not approval.get("by"):
        raise ZeroHold("approval_missing")
    if approval.get("manifest_sha256")!=hashlib.sha256(canonical(manifest)).hexdigest():
        raise ZeroHold("approval_digest")
    if approval.get("expires_epoch",0)<=now or manifest["deadline_epoch"]>approval["expires_epoch"]:
        raise ZeroHold("approval_expired")
    if type(manifest["gpu_index"]) is not int or manifest["gpu_index"] not in (0,1):
        raise ZeroHold("gpu_index")
    if type(manifest["deadline_epoch"]) not in (int,float) or not now<manifest["deadline_epoch"]<=1792206000:
        raise ZeroHold("deadline")
    if any(type(manifest[k]) not in (int,float) or not 0<manifest[k]<1e15 for k in ("max_wall_s","max_disk_bytes")):
        raise ZeroHold("budget")
    for name in ("python","diag","criteria","parent"):
        p=Path(manifest[name+"_path"])
        if not p.is_file() or p.stat().st_size==0 or digest(p)!=manifest[name+"_sha256"]:
            raise ZeroHold("input_hash_"+name)
    if Path(manifest["stop_path"]).exists():raise ZeroHold("STOP")
    out=Path(manifest["out_root"]).resolve()
    if Path(manifest["diag_path"]).resolve()!=Path(__file__).with_name("s2_connect_diag_17v.py").resolve():
        raise ZeroHold("unregistered_diagnostic")
    workspace=Path(__file__).resolve().parents[1]
    for key in ("out_root","claim_root","lease_root","status_path"):
        target=Path(manifest[key]).resolve()
        if not cpu_fixture and workspace not in target.parents:
            raise ZeroHold("write_outside_workspace_"+key)
    for forbidden in (Path("C:/isaac/ext/go2_rl_robotlab/_eval").resolve(),
                      Path("C:/isaac/ext/go2_rl_robotlab/source").resolve()):
        if out==forbidden or forbidden in out.parents:raise ZeroHold("output_readonly")
    args=manifest["diag_args"]
    if not isinstance(args,list) or any(type(x) is not str or not x or any(c in x for c in "\r\n\x00") for x in args):
        raise ZeroHold("diag_args")
    required={"--parent":manifest["parent_path"],"--criteria":manifest["criteria_path"],
              "--out_root":manifest["out_root"],"--num_envs":"8","--steps":"256"}
    for flag,value in required.items():
        if args.count(flag)!=1 or args.index(flag)+1>=len(args) or args[args.index(flag)+1]!=value:
            raise ZeroHold("diag_arg_"+flag)
    if "--headless" not in args:raise ZeroHold("headless")


def run_zero(manifest,approval,*,owner_factory=None,lease_factory=None,
             clock=time.time,mono=time.monotonic,sleep=time.sleep,cpu_fixture=False):
    validate(manifest,approval,now=clock(),cpu_fixture=cpu_fixture)
    claim_root=Path(manifest["claim_root"])
    claim_root.mkdir(parents=True,exist_ok=True)
    claim=claim_root/(manifest["chain_id"]+"-"+manifest["attempt"]+".claim")
    try:claim.mkdir(exist_ok=False)
    except FileExistsError as ex:raise ZeroHold("claim_reused") from ex
    atomic_json(claim/"approval.json",{"sha256":hashlib.sha256(canonical(approval)).hexdigest()})
    status_path=Path(manifest["status_path"])
    status_path.parent.mkdir(parents=True,exist_ok=True)
    deadline_mono=mono()+min(manifest["max_wall_s"],manifest["deadline_epoch"]-clock())
    owner=None;lease=None;reason=None;rc=None;family_empty=False
    status={"chain_id":manifest["chain_id"],"stage":"connect","state":"STARTING",
            "last_packet_epoch":None,"last_artifact_epoch":None,"remaining_s":None,
            "next_boundary":"stage0_verdict","update":0}
    def emit(**kw):
        status.update(kw);status["heartbeat_epoch"]=clock()
        status["remaining_s"]=max(0,min(manifest["deadline_epoch"]-clock(),deadline_mono-mono()))
        atomic_json(status_path,status)
    try:
        lease=(lease_factory or gpu_lease)(Path(manifest["lease_root"]),manifest["gpu_uuid"]).acquire()
        owner=(owner_factory or (lambda:JobOwner(WinKernel())))()
        env=os.environ.copy();env["CUDA_VISIBLE_DEVICES"]=str(manifest["gpu_index"])
        argv=[manifest["python_path"],"-B",manifest["diag_path"],*manifest["diag_args"]]
        owner.launch(argv,Path(manifest["diag_path"]).parent,env)
        emit(state="RUNNING",pid=owner.pid)
        while owner.active_count():
            if Path(manifest["stop_path"]).exists():reason="STOP";break
            if clock()>=manifest["deadline_epoch"] or mono()>=deadline_mono:reason="deadline";break
            emit()
            sleep(min(1.,max(.01,deadline_mono-mono())))
        if reason:
            owner.stop_owned(wait_seconds=10.)
        family_empty=owner.active_count()==0
        rc=owner.exit_code()
        emit(state="VALIDATING",family_active_count=owner.active_count())
        out=Path(manifest["out_root"])
        artifacts={name:digest(out/name) for name in ("capture.npz","meta.json","check.json")
                   if (out/name).is_file() and (out/name).stat().st_size>0}
        record={"chain_id":manifest["chain_id"],"stage":"connect","attempt":manifest["attempt"],
                "device_uuid":manifest["gpu_uuid"],"exit_code":rc,"family_active_count":owner.active_count(),
                "optimizer_steps":0,"control_steps":256,"env_count":8,"out_root":str(out),
                "python_sha256":digest(Path(manifest["python_path"])),
                "diag_sha256":digest(Path(manifest["diag_path"])),
                "criteria_sha256":digest(Path(manifest["criteria_path"])),"artifacts":artifacts}
        verdict=zero_stage_verdict(manifest,record,now_epoch=clock())
        if reason:verdict={**verdict,"verdict":"HOLD","reasons":sorted(set(verdict["reasons"]+[reason]))}
        atomic_json(claim/"stage0.receipt.json",{"record":record,"verdict":verdict,
                    "approval_sha256":hashlib.sha256(canonical(approval)).hexdigest(),
                    "manifest_sha256":hashlib.sha256(canonical(manifest)).hexdigest()})
        emit(state="COMPLETE" if verdict["verdict"]=="PASS" else "HOLD",
             last_verdict=verdict["verdict"],last_artifact_epoch=clock(),reasons=verdict["reasons"])
        return verdict
    except (OSError,OwnershipHold,LeaseHold,ZeroHold,ValueError) as ex:
        reason=str(ex)
        try:emit(state="HOLD",reasons=[reason])
        except OSError:pass
        return {"stage":"connect","verdict":"HOLD","reasons":[reason]}
    finally:
        if owner is not None:
            try:
                if owner.active_count():owner.stop_owned(wait_seconds=10.)
                family_empty=owner.active_count()==0
                owner.close()
            except OwnershipHold:
                family_empty=False
        if lease is not None:
            try:lease.release(family_empty=family_empty)
            except LeaseHold:pass


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--approval",type=Path,required=True)
    a=ap.parse_args(argv)
    m=json.loads(a.manifest.read_text(encoding="utf-8"))
    approval=json.loads(a.approval.read_text(encoding="utf-8"))
    verdict=run_zero(m,approval)
    print(json.dumps(verdict,sort_keys=True),flush=True)
    return 0 if verdict["verdict"]=="PASS" else 42


if __name__=="__main__":raise SystemExit(main())
