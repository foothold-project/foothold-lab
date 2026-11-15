"""CPU fake-owner proof that short completion is revised after resource cleanup."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from s2_train_contract import canonical,entry_argv
from s2_train_launch import run
import s2_train_launch as launch
from test_s2_step5_live import fixture,Meter


class Lock:
    def __init__(self,fail=False):self.fd=object();self.fail=fail
    def acquire(self):return self
    def release(self,*,family_empty):
        assert family_empty
        if self.fail:raise RuntimeError("known release failure")
        self.fd=None


class Owner:
    def __init__(self):self.pid=9901;self.launched=False;self.polls=0
    def launch(self,argv,cwd,env,log_path):
        root=Path(argv[argv.index("--out_root")+1]);root.mkdir()
        (root/"result.json").write_text(json.dumps({"status":"RUN_COMPLETE_UNVERIFIED",
            "executed_updates":2000,"parent_sha256_before":"fixture"}),encoding="utf-8")
        log_path.write_text("CPU fake owner",encoding="utf-8")
        self.launched=True
    def active_count(self):
        self.polls+=1
        return 1 if self.launched and self.polls==1 else 0
    def exit_code(self):return 0
    def close(self):pass
    def stop_owned(self,**kwargs):raise AssertionError("unexpected stop")


def one(root,release_failure,parent_change=False):
    root.mkdir(parents=True)
    m,a=fixture(root)
    m["plan"].update(stage="short",updates=2000,checkpoint_interval=200,
                     extension_disabled=True)
    m.update(execution_id="fixture-A",extension_disabled=True,
             completion_deadline_cap_epoch=1792206000,
             checkpoint_boundaries=list(range(0,2001,200)),
             exploratory_short=True,map_contract_verified=True,stage0_state="HOLD",
             short_pair={"pair_id":m["chain_id"],"ordinal":1})
    m["entry_argv"]=entry_argv(m)
    a["manifest_sha256"]=hashlib.sha256(canonical(m)).hexdigest()
    Path(m["prelaunch_report_path"]).write_text(json.dumps({"status":"GO",
        "manifest_sha256":a["manifest_sha256"],"checked_epoch":time.time()}),encoding="utf-8")
    real_sha=launch.sha;parent_calls=[0]
    def measured_sha(path):
        if Path(path)==Path(m["plan"]["parent"]):
            parent_calls[0]+=1
            if parent_change and parent_calls[0]>=3:return "0"*64
        return real_sha(path)
    with (patch("s2_train_launch.usd_evidence",return_value={"verified":True}),
          patch("s2_train_launch.verify_short_single_result",return_value=True),
          patch("s2_train_launch.sha",side_effect=measured_sha)):
        receipt=run(m,a,owner_factory=Owner,meter_factory=Meter,
            disk_probe=lambda path:100000000,tree_probe=lambda path:0,
            gpu_lock=lambda *args:Lock(release_failure),usd_lock=lambda *args:Lock(),
            process_probe=lambda:[],sleep=lambda seconds:None)
    stored=json.loads((Path(receipt["claim_path"])/"chain.receipt.json").read_text(encoding="utf-8"))
    assert stored==receipt
    assert stored["family_cleanup_confirmed"] is True and stored["family_active_count"]==0
    assert stored["usd_lock_released"] is True
    if parent_change:
        assert stored["verdict"]=="HOLD" and stored["parent_sha256_before"]!=stored["parent_sha256_after"]
    elif release_failure:
        assert stored["verdict"]=="HOLD" and stored["reason"]=="cleanup_error"
        assert stored["gpu_lease_released"] is False
    else:
        assert stored["verdict"]=="RUN_COMPLETE_UNVERIFIED" and stored["gpu_lease_released"] is True
    return stored


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step9_cleanup_") as td:
        root=Path(td)
        one(root/"normal",False)
        print("PASS short_cleanup_complete_receipt")
        one(root/"release_failure",True)
        print("PASS short_release_failure_final_receipt_hold")
        one(root/"parent_change",False,parent_change=True)
        print("PASS short_parent_change_hold")


if __name__=="__main__":test()
