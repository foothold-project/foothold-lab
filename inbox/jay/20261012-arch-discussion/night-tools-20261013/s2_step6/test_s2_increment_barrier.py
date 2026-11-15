"""Same live object across short comparison and extension, CPU fake executor."""
import hashlib
import json
from pathlib import Path
import tempfile
import time

from s2_increment_barrier import IncrementBarrier,BarrierHold,issue_pair_grants,atomic_json,sha


class FakeLearner:
    def __init__(self,root,arm):self.root=root;self.arm=arm;self.calls=[];self.weights=0
    def run_updates(self,n):
        self.calls.append(n);self.weights+=n
        return {"status":"PASS","updates":n,"faults":0,"discarded":0,
                "optimizer_steps":n*20,"packet_count":n*24*2}
    def checkpoint_at(self,update):
        path=self.root/f"{self.arm}_{update}.pt"
        path.write_bytes(f"weights {self.arm} {self.weights}".encode())
        return path


def contract(root,arm):
    return {"chain_id":"fixture-chain","arm":arm,"grant_root":str(root),
            "deadline_epoch":time.time()+100,"max_total_updates":4,
            "allowed_increments":[2,1],"initial_short_updates":2,
            "stop_file":str(root/"STOP"),"approval_sha256":"a"*64,
            "poll_seconds":.01,"grant_timeout_s":.05}


def check(name,good):
    print("PASS" if good else "FAIL",name)
    assert good,name


def main():
    with tempfile.TemporaryDirectory(prefix="s2_barrier_") as td:
        root=Path(td);contracts={x:contract(root,x) for x in ("A","B")}
        learners={x:FakeLearner(root,x) for x in ("A","B")}
        barriers={x:IncrementBarrier(contracts[x],learners[x]) for x in ("A","B")}
        receipts={x:barriers[x].initial() for x in ("A","B")}
        check("short_common_boundary",all(r["end_update"]==2 for r in receipts.values()))
        issue_pair_grants(contracts,receipts,size=2,approval_sha256="a"*64)
        extended={x:barriers[x].wait_grant_and_extend() for x in ("A","B")}
        check("same_learner_objects_increment",all(learners[x].calls==[2,2] and
              learners[x].weights==4 and extended[x]["end_update"]==4 for x in ("A","B")))
        check("grant_consumed_once",all((root/f"grant_{x}_0000.consumed.json").is_file() for x in ("A","B")))
        try:issue_pair_grants(contracts,receipts,size=2,approval_sha256="a"*64)
        except BarrierHold as e:check("grant_reuse_rejected",str(e)=="grant_reused")
        else:check("grant_reuse_rejected",False)
        try:barriers["A"].wait_grant_and_extend()
        except BarrierHold as e:check("no_unapproved_extra_update",str(e)=="grant_timeout")
        else:check("no_unapproved_extra_update",False)
        root2=root/"wrong";root2.mkdir();c=contract(root2,"A");b=IncrementBarrier(c,FakeLearner(root2,"A"));r=b.initial()
        atomic_json(root2/"grant_A_0000.json",{"chain_id":c["chain_id"],"arm":"B","ordinal":0,
                    "start_update":2,"size":2,"previous_sha256":b.last_receipt_sha,
                    "approval_sha256":c["approval_sha256"]})
        atomic_json(root2/"grant_B_0000.json",{"chain_id":c["chain_id"],"arm":"B","ordinal":0,
                    "start_update":2,"size":2,"previous_sha256":"other",
                    "approval_sha256":c["approval_sha256"]})
        atomic_json(root2/"pair_commit_0000.json",{"chain_id":c["chain_id"],"ordinal":0,
                    "approval_sha256":c["approval_sha256"],
                    "grant_sha256":{"A":sha(root2/"grant_A_0000.json"),
                                    "B":sha(root2/"grant_B_0000.json")}})
        try:b.wait_grant_and_extend()
        except BarrierHold as e:check("wrong_arm_grant_rejected",str(e)=="grant_identity")
        else:check("wrong_arm_grant_rejected",False)
        root4=root/"unpaired";root4.mkdir();c4=contract(root4,"A");b4=IncrementBarrier(c4,FakeLearner(root4,"A"));b4.initial()
        atomic_json(root4/"grant_A_0000.json",{"chain_id":c4["chain_id"],"arm":"A","ordinal":0,
                    "start_update":2,"size":2,"previous_sha256":b4.last_receipt_sha,
                    "approval_sha256":c4["approval_sha256"]})
        try:b4.wait_grant_and_extend()
        except BarrierHold as e:check("partial_pair_not_executed",str(e)=="grant_timeout")
        else:check("partial_pair_not_executed",False)
        root3=root/"stopped";root3.mkdir();c3=contract(root3,"A");b3=IncrementBarrier(c3,FakeLearner(root3,"A"));b3.initial()
        (root3/"STOP").write_text("stop")
        try:b3.wait_grant_and_extend()
        except BarrierHold as e:check("STOP_at_barrier",str(e)=="STOP")
        else:check("STOP_at_barrier",False)

if __name__=="__main__":main()
