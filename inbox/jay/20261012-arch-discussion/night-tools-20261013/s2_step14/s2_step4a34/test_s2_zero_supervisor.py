"""Stage-0-only supervisor fake. No Isaac/GPU or real process termination."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import numpy as np

from s2_connect_check_17v import Criteria,check_arrays
from test_s2_connect_17v import fixture
from s2_zero_supervisor import canonical,digest,run_zero,ZeroHold
from s2_stage_gate_17v import zero_stage_verdict


class Lease:
    def __init__(self):self.released=None
    def acquire(self):return self
    def release(self,*,family_empty):self.released=family_empty


class Owner:
    def __init__(self,*,hang=False):self.pid=701;self.hang=hang;self.stopped=False;self.closed=False
    def launch(self,argv,cwd,env):
        assert argv[0]==sys.executable and env["CUDA_VISIBLE_DEVICES"]=="0"
    def active_count(self):return 1 if self.hang and not self.stopped else 0
    def exit_code(self):return 124 if self.stopped else 0
    def stop_owned(self,*,wait_seconds):self.stopped=True
    def close(self):
        assert self.active_count()==0
        self.closed=True


def case(root):
    out=root/"capture";out.mkdir(parents=True)
    meta,arrays=fixture()
    np.savez_compressed(out/"capture.npz",**arrays)
    diag=Path(__file__).parent/"s2_connect_diag_17v.py"
    parent=root/"parent.pt";parent.write_bytes(b"synthetic-parent")
    criteria=root/"criteria.json"
    criteria.write_text(json.dumps({"xy_tolerance_m":.002,"z_tolerance_m":.002,
                      "boundary_exclusion_m":.005,"steps":256,"warmup_steps":16}))
    meta["capture_sha256"]=digest(out/"capture.npz")
    meta["parent_sha256"]=digest(parent)
    meta["code_sha256"]=digest(diag)
    (out/"meta.json").write_text(json.dumps(meta),encoding="utf-8")
    check=check_arrays(meta,arrays,Criteria(.002,.002,.005,256,16))
    assert check["verdict"]=="PASS",check
    (out/"check.json").write_text(json.dumps(check),encoding="utf-8")
    m={"chain_id":"stage0-fixture","attempt":"first","python_path":sys.executable,
       "python_sha256":digest(Path(sys.executable)),"diag_path":str(diag),"diag_sha256":digest(diag),
       "criteria_path":str(criteria),"criteria_sha256":digest(criteria),
       "parent_path":str(parent),"parent_sha256":digest(parent),"out_root":str(out),
       "claim_root":str(root/"claims"),"status_path":str(root/"chain_status.json"),
       "stop_path":str(root/"STOP"),"lease_root":str(root/"leases"),
       "gpu_uuid":"fixture-uuid-A","gpu_index":0,
       "deadline_epoch":1792206000,"max_wall_s":15,"max_disk_bytes":1000,
       "diag_args":["--parent",str(parent),"--criteria",str(criteria),"--out_root",str(out),
                    "--num_envs","8","--steps","256","--headless"]}
    a={"status":"APPROVED","by":"synthetic-only","chain_id":m["chain_id"],
       "expires_epoch":1792206000,"manifest_sha256":hashlib.sha256(canonical(m)).hexdigest()}
    return m,a


def main():
    with tempfile.TemporaryDirectory(prefix="s2_zero_") as td:
        root=Path(td);m,a=case(root)
        owner=Owner();lease=Lease()
        result=run_zero(m,a,owner_factory=lambda:owner,lease_factory=lambda r,u:lease,cpu_fixture=True)
        assert result["verdict"]=="PASS" and owner.closed and lease.released is True,result
        print("PASS stage0_fake_owner_receipt_status")
        receipt=root/"claims"/"stage0-fixture-first.claim"/"stage0.receipt.json"
        assert receipt.is_file() and json.loads(receipt.read_text())["verdict"]["verdict"]=="PASS"
        assert json.loads((root/"chain_status.json").read_text())["state"]=="COMPLETE"
        print("PASS atomic_receipt_and_status")
        try:run_zero(m,a,owner_factory=lambda:Owner(),lease_factory=lambda r,u:Lease(),cpu_fixture=True)
        except ZeroHold as ex:assert str(ex)=="claim_reused"
        else:raise AssertionError("claim_reused")
        print("PASS chain_claim_once")
        rec=json.loads(receipt.read_text())["record"]
        rec["artifacts"]["capture.npz"]="0"*64
        bad=zero_stage_verdict(m,rec,now_epoch=time.time())
        assert bad["verdict"]=="HOLD" and "artifact_hash" in bad["reasons"]
        print("PASS forged_receipt_hash_rejected")
        rec=json.loads(receipt.read_text())["record"]
        rec["control_steps"]=255
        bad=zero_stage_verdict(m,rec,now_epoch=time.time())
        assert "step_count" in bad["reasons"]
        print("PASS incomplete_step_count_rejected")
        root2=root/"deadline";root2.mkdir()
        m2,a2=case(root2)
        now=[time.time()]
        def clock():return now[0]
        def sleep(_):now[0]+=16
        hang=Owner(hang=True);l2=Lease()
        held=run_zero(m2,a2,owner_factory=lambda:hang,lease_factory=lambda r,u:l2,
                      clock=clock,mono=lambda:now[0],sleep=sleep,cpu_fixture=True)
        assert held["verdict"]=="HOLD" and "deadline" in held["reasons"] and hang.stopped and l2.released is True,held
        print("PASS stage0_deadline_owned_family_stop")

if __name__=="__main__":main()
