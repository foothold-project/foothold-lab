"""Independent raw artifact recount and immutable hash-linked stage receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


class ReceiptHold(RuntimeError):pass


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(1<<20),b""):
            h.update(part)
    return h.hexdigest()


def recount_stage(manifest,stage,record,verdict):
    if verdict.get("verdict")!="PASS" or verdict.get("stage")!=stage:
        raise ReceiptHold("stage_not_pass")
    artifacts=record.get("artifacts",{})
    if not artifacts:raise ReceiptHold("artifacts_missing")
    for name,entry in artifacts.items():
        path=Path(entry.get("path",""))
        if not path.is_file() or path.stat().st_size<=0 or _sha(path)!=entry.get("sha256"):
            raise ReceiptHold("artifact_bad:"+name)
    counted={"artifacts":{key:{"sha256":v["sha256"],"bytes":Path(v["path"]).stat().st_size}
                          for key,v in artifacts.items()}}
    if stage=="connect":
        import numpy as np
        with np.load(artifacts["connect_npz"]["path"],allow_pickle=False) as raw:
            steps=raw["sim_step"]
            if len(steps)!=256 or raw["pos_w"].shape!=(256,8,3):
                raise ReceiptHold("connect_raw_count")
            counted["control_steps"]=int(len(steps))
            counted["optimizer_steps"]={"A":0,"B":0}
    else:
        counted["optimizer_steps"]={}
        counted["control_steps"]={}
        for arm in ("A","B"):
            result=json.loads(Path(artifacts[arm+"_result"]["path"]).read_text(encoding="utf-8"))
            expected=manifest["stages"][stage]["updates_per_arm"]*manifest["stages"][stage]["epochs"]*manifest["stages"][stage]["minibatches"]
            if result.get("arm")!=arm or result.get("optimizer_steps_actual")!=expected or result.get("executed_updates")!=manifest["stages"][stage]["updates_per_arm"]:
                raise ReceiptHold("training_raw_count:"+arm)
            counted["optimizer_steps"][arm]=expected
            counted["control_steps"][arm]=result["executed_updates"]
    return counted


def commit_stage(claim_root:Path,manifest,stage,record,verdict,*,previous_sha256:str|None):
    counted=recount_stage(manifest,stage,record,verdict)
    receipt={"chain_id":manifest["chain_id"],"stage":stage,"arm":"pair" if stage!="connect" else "A",
             "attempt":record["attempt"],"previous_sha256":previous_sha256,
             "record_sha256":hashlib.sha256(_canonical(record)).hexdigest(),
             "manifest_sha256":hashlib.sha256(_canonical(manifest)).hexdigest(),
             "parent_sha256":manifest["inputs"]["parent_sha256"],
             "code_sha256":manifest["inputs"]["code_sha256"],
             "device_uuid_by_arm":manifest["gpu_uuid_by_arm"],
             "start_update":0 if stage=="connect" else 0,
             "end_update":0 if stage=="connect" else manifest["stages"][stage]["updates_per_arm"],
             "faults":0,"discarded":0,"family_state":"WAITING_AT_BARRIER" if stage=="short_ab" else "TERMINATED",
             "counted":counted}
    path=claim_root/(stage+".receipt.json")
    if path.exists():raise ReceiptHold("receipt_reused")
    temp=path.with_suffix(".receipt.tmp")
    temp.write_bytes(_canonical(receipt))
    os.replace(temp,path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def commit_extension(claim_root:Path,manifest,ordinal:int,pair:dict,*,previous_sha256:str):
    path=claim_root/f"extend_{ordinal:04d}.receipt.json"
    if path.exists():raise ReceiptHold("receipt_reused")
    if set(pair)!={"A","B"} or any(pair[arm].get("previous_sha256")!=previous_sha256
                                   for arm in ("A","B")):
        raise ReceiptHold("extension_previous_receipt")
    receipt={"chain_id":manifest["chain_id"],"stage":"extend","arm":"pair",
             "ordinal":ordinal,"previous_sha256":previous_sha256,
             "pair_sha256":hashlib.sha256(_canonical(pair)).hexdigest(),
             "A_checkpoint_sha256":pair["A"]["checkpoint_sha256"],
             "B_checkpoint_sha256":pair["B"]["checkpoint_sha256"],
             "A_raw_sha256":pair["A"]["raw_sha256"],"B_raw_sha256":pair["B"]["raw_sha256"],
             "A_optimizer_steps":pair["A"]["optimizer_steps"],
             "B_optimizer_steps":pair["B"]["optimizer_steps"],
             "start_update":pair["A"]["start_update"],"end_update":pair["A"]["end_update"],
             "family_state":"WAITING_AT_BARRIER"}
    temp=path.with_suffix(".receipt.tmp")
    temp.write_bytes(_canonical(receipt))
    os.replace(temp,path)
    return hashlib.sha256(path.read_bytes()).hexdigest()
