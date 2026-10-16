"""Actual E1 checkpoint CPU dry entry and unsupported environment resume."""
import sys
import tempfile
from pathlib import Path
import torch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"s2_step3"))
from test_s2_step3_entry import args
sys.path.insert(0,str(HERE))
from s2_train_entry_17v import execute, FakeS2Env
from s2_train_entry_17v import execute_barrier
from s2_increment_barrier import atomic_json,sha
import json
import time


def main():
    torch.set_num_threads(2)
    with tempfile.TemporaryDirectory(prefix="s2_17v_entry_") as td:
        root=Path(td)
        result=execute(args(root/"normal",updates=1),cpu_dry=True)
        assert result["status"]=="PASS" and result["executed_updates"]==1 and result["optimizer_steps_actual"]==1,result
        assert result["parent_sha256"]=="c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8"
        print("PASS real_E1_cpu_dry_one_update")
        ckpt=root/"normal"/"checkpoint_000001.pt"
        assert ckpt.is_file() and ckpt.stat().st_size>0
        print("PASS checkpoint_nonzero")
        denied=execute(args(root/"resume",resume=ckpt),cpu_dry=True)
        assert denied["status"]=="HOLD" and "environment resume is unsupported" in denied["stop_reason"],denied
        print("PASS environment_resume_fail_closed")
        fake=FakeS2Env({"policy":1,"single_obs":1,"critic":1},2)
        _,_,_,extras=fake.step(torch.zeros(2,12))
        assert "time_outs" in extras and extras["time_outs"].shape==(2,)
        print("PASS timeout_channel_exposed")
        a=args(root/"barrier_run",updates=1)
        barrier_root=root/"grants"
        contract={"chain_id":"cpu-e1","arm":"B","grant_root":str(barrier_root),
                  "deadline_epoch":time.time()+100,"max_total_updates":2,
                  "allowed_increments":[1],"initial_short_updates":1,
                  "stop_file":str(root/"STOP"),"approval_sha256":"a"*64,
                  "poll_seconds":.01,"grant_timeout_s":2.}
        cp=root/"contract.json";cp.write_text(json.dumps(contract),encoding="utf-8")
        a.barrier_contract=cp
        def grant(barrier,receipt):
            if barrier.update!=1:return
            atomic_json(barrier_root/"grant_A_0000.json",
                        {"chain_id":"cpu-e1","arm":"A","ordinal":0,"start_update":1,
                         "size":1,"previous_sha256":"synthetic_A_receipt",
                         "approval_sha256":"a"*64})
            atomic_json(barrier_root/"grant_B_0000.json",
                        {"chain_id":"cpu-e1","arm":"B","ordinal":0,"start_update":1,
                         "size":1,"previous_sha256":barrier.last_receipt_sha,
                         "approval_sha256":"a"*64})
            atomic_json(barrier_root/"pair_commit_0000.json",
                        {"chain_id":"cpu-e1","ordinal":0,"approval_sha256":"a"*64,
                         "grant_sha256":{arm:sha(barrier_root/f"grant_{arm}_0000.json") for arm in ("A","B")}})
        chained=execute_barrier(a,cpu_dry=True,barrier_callback=grant)
        assert chained["status"]=="COMPLETE" and chained["updates_per_arm"]==2 and chained["segments"]==2
        assert ((root/"barrier_run"/"checkpoint_000001.pt").is_file() and
                (root/"barrier_run"/"checkpoint_000002.pt").is_file())
        print("PASS real_E1_same_runner_two_segments")

if __name__=="__main__":main()
