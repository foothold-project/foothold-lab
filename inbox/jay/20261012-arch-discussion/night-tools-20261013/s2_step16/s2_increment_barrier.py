"""Same-process finite extension barrier. CPU protocol; no environment resume.

Each grant is written atomically by the supervisor and consumed once by rename.
The learner keeps its policy, optimizer, environment and RNG in the same process.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import time


class BarrierHold(RuntimeError):pass


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):h.update(block)
    return h.hexdigest()


def atomic_json(path:Path,value):
    tmp=path.with_name(path.name+".tmp")
    tmp.write_bytes(canonical(value))
    os.replace(tmp,path)


class IncrementBarrier:
    def __init__(self,contract:dict,executor,*,clock=time.time,mono=time.monotonic,sleep=time.sleep):
        required=("chain_id","arm","grant_root","deadline_epoch","max_total_updates",
                  "allowed_increments","initial_short_updates","stop_file","approval_sha256",
                  "poll_seconds","grant_timeout_s")
        if any(k not in contract or contract[k] in (None,"","UNDECIDED") for k in required):
            raise BarrierHold("contract_missing")
        if contract["arm"] not in ("A","B") or not isinstance(contract["allowed_increments"],list):
            raise BarrierHold("contract_arm_or_sizes")
        sizes=contract["allowed_increments"]
        if sizes!=sorted(set(sizes),reverse=True) or any(type(x) is not int or x<1 for x in sizes):
            raise BarrierHold("increments_invalid")
        if any(type(contract[k]) not in (int,float) or not math.isfinite(contract[k]) or contract[k]<=0
               for k in ("deadline_epoch","max_total_updates","initial_short_updates","poll_seconds","grant_timeout_s")):
            raise BarrierHold("budget_invalid")
        if type(contract["max_total_updates"]) is not int or type(contract["initial_short_updates"]) is not int:
            raise BarrierHold("update_count_type")
        if contract["initial_short_updates"]>contract["max_total_updates"]:
            raise BarrierHold("initial_over_budget")
        self.c=contract;self.executor=executor;self.clock=clock;self.mono=mono;self.sleep=sleep
        self.root=Path(contract["grant_root"]);self.root.mkdir(parents=True,exist_ok=True)
        self.update=0;self.ordinal=0;self.last_receipt_sha=None

    def _preflight(self):
        if Path(self.c["stop_file"]).exists():raise BarrierHold("STOP")
        if self.clock()>=self.c["deadline_epoch"]:raise BarrierHold("deadline")

    def _run_segment(self,size:int):
        self._preflight()
        if self.update+size>self.c["max_total_updates"]:raise BarrierHold("update_budget")
        start=self.update
        result=self.executor.run_updates(size)
        if result.get("status")!="PASS" or result.get("updates")!=size or result.get("faults")!=0 or result.get("discarded")!=0:
            raise BarrierHold("segment_invalid")
        self.update+=size
        checkpoint=Path(self.executor.checkpoint_at(self.update))
        if not checkpoint.is_file() or checkpoint.stat().st_size==0:
            raise BarrierHold("checkpoint_incomplete")
        receipt={"chain_id":self.c["chain_id"],"arm":self.c["arm"],"ordinal":self.ordinal,
                 "start_update":start,"end_update":self.update,"updates":size,
                 "checkpoint_path":str(checkpoint),"checkpoint_sha256":sha(checkpoint),
                 "raw":result,"previous_sha256":self.last_receipt_sha,
                 "family_state":"WAITING_AT_BARRIER"}
        target=self.root/f"receipt_{self.c['arm']}_{self.ordinal:04d}.json"
        if target.exists():raise BarrierHold("receipt_reused")
        atomic_json(target,receipt)
        self.last_receipt_sha=sha(target)
        return receipt

    def initial(self):
        if self.update!=0:raise BarrierHold("initial_reused")
        return self._run_segment(self.c["initial_short_updates"])

    def wait_grant_and_extend(self):
        if self.update==0:raise BarrierHold("initial_missing")
        current=self.ordinal
        grant=self.root/f"grant_{self.c['arm']}_{current:04d}.json"
        commit=self.root/f"pair_commit_{current:04d}.json"
        consumed=grant.with_suffix(".consumed.json")
        start_mono=self.mono()
        while not (grant.is_file() and commit.is_file()):
            self._preflight()
            if self.mono()-start_mono>=self.c["grant_timeout_s"]:raise BarrierHold("grant_timeout")
            self.sleep(self.c["poll_seconds"])
        if consumed.exists():raise BarrierHold("grant_reused")
        pair=json.loads(commit.read_text(encoding="utf-8"))
        other="B" if self.c["arm"]=="A" else "A"
        other_grant=self.root/f"grant_{other}_{current:04d}.json"
        if not other_grant.is_file():other_grant=other_grant.with_suffix(".consumed.json")
        if (pair.get("chain_id")!=self.c["chain_id"] or pair.get("ordinal")!=current or
            pair.get("approval_sha256")!=self.c["approval_sha256"] or
            pair.get("grant_sha256",{}).get(self.c["arm"])!=sha(grant) or
            not other_grant.is_file() or pair.get("grant_sha256",{}).get(other)!=sha(other_grant)):
            raise BarrierHold("pair_commit_identity")
        os.replace(grant,consumed)
        value=json.loads(consumed.read_text(encoding="utf-8"))
        expected={"chain_id":self.c["chain_id"],"arm":self.c["arm"],"ordinal":current,
                  "start_update":self.update,"previous_sha256":self.last_receipt_sha,
                  "approval_sha256":self.c["approval_sha256"]}
        if any(value.get(k)!=v for k,v in expected.items()):raise BarrierHold("grant_identity")
        size=value.get("size")
        if type(size) is not int or size not in self.c["allowed_increments"]:
            raise BarrierHold("grant_size")
        self.ordinal+=1
        return self._run_segment(size)


def issue_pair_grants(contracts:dict,receipts:dict,*,size:int,approval_sha256:str):
    if set(contracts)!={"A","B"} or set(receipts)!={"A","B"}:
        raise BarrierHold("pair_missing")
    if receipts["A"]["end_update"]!=receipts["B"]["end_update"]:
        raise BarrierHold("pair_boundary")
    roots={Path(contracts[arm]["grant_root"]).resolve() for arm in ("A","B")}
    if len(roots)!=1:raise BarrierHold("pair_grant_root")
    if any(contracts[arm]["chain_id"]!=contracts["A"]["chain_id"] or
           contracts[arm]["approval_sha256"]!=approval_sha256 for arm in ("A","B")):
        raise BarrierHold("pair_contract")
    for arm in ("A","B"):
        c=contracts[arm];r=receipts[arm]
        if (r["arm"]!=arm or r["family_state"]!="WAITING_AT_BARRIER" or
            r["checkpoint_sha256"]!=sha(r["checkpoint_path"])):
            raise BarrierHold("pair_receipt")
        if size not in c["allowed_increments"] or r["end_update"]+size>c["max_total_updates"]:
            raise BarrierHold("pair_budget")
    grants=[]
    for arm in ("A","B"):
        c=contracts[arm];r=receipts[arm]
        root=Path(c["grant_root"])
        path=root/f"grant_{arm}_{r['ordinal']:04d}.json"
        if path.exists() or path.with_suffix(".consumed.json").exists():raise BarrierHold("grant_reused")
        grants.append((path,{"chain_id":c["chain_id"],"arm":arm,"ordinal":r["ordinal"],
                             "start_update":r["end_update"],"size":size,
                             "previous_sha256":sha(root/f"receipt_{arm}_{r['ordinal']:04d}.json"),
                             "approval_sha256":approval_sha256}))
    commit=next(iter(roots))/f"pair_commit_{receipts['A']['ordinal']:04d}.json"
    if commit.exists():raise BarrierHold("pair_commit_reused")
    for path,value in grants:atomic_json(path,value)
    atomic_json(commit,{"chain_id":contracts["A"]["chain_id"],"ordinal":receipts["A"]["ordinal"],
                        "approval_sha256":approval_sha256,
                        "grant_sha256":{path.name.split("_")[1]:sha(path) for path,_ in grants}})
