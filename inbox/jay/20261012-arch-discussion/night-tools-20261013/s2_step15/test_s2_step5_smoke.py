"""CPU parent action equality and deterministic 200-update live boundary fixture."""
from __future__ import annotations
from argparse import Namespace
import json
import math
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

import torch
from tensordict import TensorDict
from s2_policy import build_s2, load_parent_cpu
from s2_train_entry_17v import execute,execute_barrier
from s2_increment_barrier import atomic_json,sha
from test_s2_step5_live import fixture


class Encounters:
    def report(self):return {"gap":0,"stones":0}


class FakeRunner:
    def __init__(self):
        self.plan_sha256="fixture-plan"
        self.env=type("Env",(),{"final_cfg_sha256":"fixture-cfg","close":lambda self:None})()
        self.encounters=Encounters()
        self.discarded_transitions=0
        self.n=0
        self.algo=SimpleNamespace(ctl=SimpleNamespace(next_update_index=0))
    def save(self,path):Path(path).write_bytes(f"checkpoint:{self.n}".encode())
    def update_once(self):
        self.n+=1
        self.algo.ctl.next_update_index=self.n
        return {"status":"updated","surrogate":.1,"value":.2,"entropy":.3,
                "kl":.001,"optimizer_steps":20,"fault_counts":{},"other_nonfinite":{}}


def test():
    torch.set_num_threads(2)
    parent,meta=load_parent_cpu()
    policy,_,_=build_s2("A",parent=parent,map_init_seed=42)
    g=torch.Generator().manual_seed(7);n=16
    dims=meta["dims"]
    obs=TensorDict({"policy":torch.randn(n,dims["policy"],generator=g),
                    "critic":torch.randn(n,dims["critic"],generator=g),
                    "single_obs":torch.randn(n,dims["single_obs"],generator=g)},batch_size=[n])
    mapped=obs.clone();mapped["map"]=torch.zeros(n,374)
    with torch.no_grad():
        expected=parent.act_inference(obs)
        actual=policy.act_inference(mapped)
    assert torch.equal(expected,actual)
    print("PASS arm_A_parent_action_bit_equal_16")
    with tempfile.TemporaryDirectory(prefix="s2_step5_smoke_") as td:
        root=Path(td);m,_=fixture(root)
        args=Namespace(**m["plan"])
        args.resume=None
        args.freeze_updates=None
        args.encoder_lr_ratio=None
        args.barrier_contract=None
        args.device_binding={"index":0,"uuid":"GPU-FAKE-001"}
        fake=FakeRunner()
        with patch("s2_train_entry_17v.make_runner",return_value=(fake,{"ckpt_sha256":m["plan"]["parent_sha256"],"iter":20000})):
            result=execute(args,cpu_dry=False)
        assert result["status"]=="RUN_COMPLETE_UNVERIFIED",result
        assert result["executed_updates"]==200 and result["optimizer_steps_actual"]==4000
        assert result["stop_reason"] is None and result["nonfinite_count"]==0
        assert (Path(args.out_root)/"checkpoint_000000.pt").is_file()
        assert (Path(args.out_root)/"checkpoint_000200.pt").is_file()
        records=[json.loads(x) for x in (Path(args.out_root)/"updates.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(records)==200 and all(math.isfinite(float(rec[k])) for rec in records for k in
                                        ("surrogate","value","entropy","kl"))
        print("PASS deterministic_live_boundary_200_finite_and_checkpoints")
        short_root=root/"short_A"
        short=Namespace(**{**m["plan"],"stage":"short","updates":2000,
                           "out_root":str(short_root)})
        short.resume=None;short.freeze_updates=None;short.encoder_lr_ratio=None
        short.device_binding=args.device_binding
        grant_root=root/"grants"
        contract={"chain_id":"cpu_fixture_short","arm":"A","grant_root":str(grant_root),
                  "deadline_epoch":time.time()+100,"max_total_updates":2500,
                  "allowed_increments":[500],"initial_short_updates":2000,
                  "stop_file":str(root/"STOP"),"approval_sha256":"a"*64,
                  "poll_seconds":.01,"grant_timeout_s":2.}
        cp=root/"barrier.json";cp.write_text(json.dumps(contract),encoding="utf-8")
        short.barrier_contract=cp
        def grant(barrier,receipt):
            if barrier.update!=2000:return
            for arm in ("A","B"):
                atomic_json(grant_root/f"grant_{arm}_0000.json",
                    {"chain_id":contract["chain_id"],"arm":arm,"ordinal":0,
                     "start_update":2000,"size":500,
                     "previous_sha256":barrier.last_receipt_sha if arm=="A" else "synthetic_B_receipt",
                     "approval_sha256":"a"*64})
            atomic_json(grant_root/"pair_commit_0000.json",
                {"chain_id":contract["chain_id"],"ordinal":0,"approval_sha256":"a"*64,
                 "grant_sha256":{arm:sha(grant_root/f"grant_{arm}_0000.json") for arm in ("A","B")}})
        long_fake=FakeRunner()
        with patch("s2_train_entry_17v.make_runner",return_value=(long_fake,{"ckpt_sha256":m["plan"]["parent_sha256"],"iter":20000})):
            extended=execute_barrier(short,cpu_dry=False,barrier_callback=grant)
        assert extended["status"]=="RUN_COMPLETE_UNVERIFIED",extended
        assert extended["updates_per_arm"]==2500 and extended["segments"]==2
        for update in (0,200,2000,2500):
            assert (short_root/f"checkpoint_{update:06d}.pt").is_file(),update
        assert len((short_root/"updates.jsonl").read_text(encoding="utf-8").splitlines())==2500
        print("PASS deterministic_short_2000_plus_500_same_runner")


if __name__=="__main__":test()
