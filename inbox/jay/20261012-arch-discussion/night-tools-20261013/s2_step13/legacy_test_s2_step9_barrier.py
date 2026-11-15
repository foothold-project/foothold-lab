"""CPU known answers for short request, paired grants and receipt comparison."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time

from make_barrier_contract import build_pair,ContractHold
from s2_increment_barrier import IncrementBarrier,BarrierHold,issue_pair_grants,sha
from s2_compare_ab import freeze,compare_short
from s2_train_manifest import seal
from s2_train_contract import TrainHold,canonical
from test_s2_increment_barrier import FakeLearner
from test_s2_compare import event


HERE=Path(__file__).resolve().parent


def rejects(label,fn,kind,want):
    try:fn()
    except kind as ex:assert str(ex)==want,(label,str(ex),want)
    else:raise AssertionError(label)
    print("PASS reject_"+label)


def requests(root,criteria_sha="a"*64):
    pair={arm:json.loads((HERE/f"request_short_{arm}.json").read_text(encoding="utf-8"))
          for arm in ("A","B")}
    for arm,r in pair.items():
        r.update(deadline_epoch=2000000000.,approval_id="fixture-id",approval_by="fixture-only",
                 evaluation_criteria_sha256=criteria_sha,max_wall_s=3600,
                 min_free_vram_bytes=1,running_floor_vram_bytes=1,
                 min_free_disk_bytes=2**30,max_disk_bytes=2**30,
                 approval_path=str(root/f"approval_{arm}.json"),
                 prelaunch_report_path=str(root/f"prelaunch_{arm}.json"),
                 status_path=str(root/f"status_{arm}.json"),log_path=str(root/f"log_{arm}.txt"),
                 claim_root=str(root/f"claim_{arm}"),gpu_lease_root=str(root/"leases"))
        r["plan"].update(deadline_epoch=2000000000.,out_root=str(root/f"output_{arm}"),
                         stop_file=str(root/f"STOP_{arm}"),
                         barrier_contract=str(root/f"barrier_{arm}.json"),
                         sensor_hook_path=str(HERE/"s2_sensor_tracker_17v.py"))
    return pair


def criteria_fixture(root):
    criteria={"terrains":["gap"],"arms":["A","B-mlp"],"final_checkpoint":2000,
              "window_updates":200,"min_assigned":2,"min_approach":2,"min_blocks":2,
              "bootstrap_reps":20,"bootstrap_seed":7,"z":1.96,
              "min_mean_delta":0.,"min_delta_lower":0.}
    cp=root/"criteria.json";lp=root/"criteria.lock";dp=root/"events.json"
    cp.write_text(json.dumps(criteria),encoding="utf-8");digest=freeze(cp,lp)["criteria_sha256"]
    events=[event(arm,"gap",n,j,outcome) for n in range(200,2001,200)
            for j in (0,1) for arm,outcome in (("A","fall"),("B-mlp","pass"))]
    dp.write_text(json.dumps({"stages":{str(n):"PASS" for n in range(200,2001,200)},
                              "events":events}),encoding="utf-8")
    return cp,lp,dp,digest


def comparison_fixture(root,requests,criteria_sha):
    manifests={};receipts={}
    for arm,request in requests.items():
        manifest=seal(request,root/f"manifest_{arm}.json")
        manifest_path=root/f"manifest_{arm}.json";manifest_path.write_bytes(canonical(manifest))
        out=Path(manifest["plan"]["out_root"]);out.mkdir()
        hashes={}
        for n in range(0,2001,200):
            name=f"checkpoint_{n:06d}.pt";p=out/name;p.write_bytes(f"{arm}:{n}".encode())
            hashes[name]=sha(p)
        receipt={"chain_id":manifest["chain_id"],"arm":arm,"stage":"short",
                 "manifest_sha256":hashlib.sha256(canonical(manifest)).hexdigest(),
                 "verdict":"RUN_COMPLETE_UNVERIFIED","boundary_ok":True,
                 "family_active_count":0,"parent_sha256_before":manifest["plan"]["parent_sha256"],
                 "parent_sha256_after":manifest["plan"]["parent_sha256"],
                 "executed_updates":2500,"out_root":str(out),
                 "checkpoint_sha256":hashes,"stage0_passed":False}
        receipt_path=root/f"receipt_{arm}.json";receipt_path.write_text(json.dumps(receipt),encoding="utf-8")
        manifests[arm]=manifest_path;receipts[arm]=receipt_path
    return manifests,receipts


def bind_data(dp,requests,receipts,digest):
    data=json.loads(dp.read_text(encoding="utf-8"))
    data.update(chain_id=requests["A"]["chain_id"],criteria_sha256=digest,
                source_receipts={arm:sha(receipts[arm]) for arm in ("A","B")})
    dp.write_text(json.dumps(data),encoding="utf-8")


def test():
    raw={arm:json.loads((HERE/f"request_short_{arm}.json").read_text(encoding="utf-8"))
         for arm in ("A","B")}
    a,b=raw["A"],raw["B"]
    assert a["chain_id"]==b["chain_id"] and a["plan"]["seed"]==b["plan"]["seed"]==11
    assert a["plan"]["map_init_seed"]==b["plan"]["map_init_seed"]==7
    for arm in ("A","B"):
        p=raw[arm]["plan"]
        assert (p["stage"],p["arm"],p["num_envs"],p["updates"],p["checkpoint_interval"])==("short",arm,1024,2000,200)
        assert (p["rollout_steps"],p["epochs"],p["minibatches"],p["lr"],p["schedule"])==(24,5,4,.001,"adaptive")
        assert raw[arm]["extension"]=={"initial_short_updates":2000,"max_total_updates":2500,"allowed_increments":[500]}
        with tempfile.TemporaryDirectory() as td:
            rejects("request_"+arm+"_undecided",lambda:seal(raw[arm],Path(td)/"m.json"),TrainHold,"undecided_value")
    print("PASS short_requests_e1_values_and_same_seed")
    with tempfile.TemporaryDirectory(prefix="s2_step9_short_") as td:
        root=Path(td);cp,lp,dp,digest=criteria_fixture(root);req=requests(root,digest)
        contracts=build_pair(req,approval_id="fixture-id",approval_sha256="a"*64,
                             grant_root=root/"grants",poll_seconds=.01,grant_timeout_s=.05)
        for arm in ("A","B"):
            Path(req[arm]["plan"]["barrier_contract"]).write_text(
                json.dumps(contracts[arm]),encoding="utf-8")
        assert all(c["initial_short_updates"]==2000 and c["allowed_increments"]==[500] for c in contracts.values())
        print("PASS barrier_pair_contract_same_identity")
        for label,mutate,want in (
            ("arm_mismatch",lambda q:q["B"]["plan"].update(arm="A"),"arm_or_stage_mismatch"),
            ("other_chain",lambda q:q["B"].update(chain_id="other"),"chain_mismatch"),
        ):
            wrong=copy.deepcopy(req);mutate(wrong)
            rejects(label,lambda:build_pair(wrong,approval_id="fixture-id",approval_sha256="a"*64,
                     grant_root=root/"grants",poll_seconds=.01,grant_timeout_s=.05),ContractHold,want)
        learners={arm:FakeLearner(root,arm) for arm in ("A","B")}
        barriers={arm:IncrementBarrier(contracts[arm],learners[arm]) for arm in ("A","B")}
        first={arm:barriers[arm].initial() for arm in ("A","B")}
        rejects("increment_400",lambda:issue_pair_grants(contracts,first,size=400,
                approval_sha256="a"*64),BarrierHold,"pair_budget")
        issue_pair_grants(contracts,first,size=500,approval_sha256="a"*64)
        extended={arm:barriers[arm].wait_grant_and_extend() for arm in ("A","B")}
        assert all(x["end_update"]==2500 for x in extended.values())
        print("PASS paired_grants_2000_plus_500_same_process")
        rejects("total_over_2500",lambda:issue_pair_grants(contracts,extended,size=500,
                approval_sha256="a"*64),BarrierHold,"pair_budget")
        manifests,receipts=comparison_fixture(root,req,digest)
        bind_data(dp,req,receipts,digest)
        result=compare_short(dp,cp,lp,manifests,receipts)
        assert result["status"]=="잠정 · 0단계 미통과" and result["stage0_passed"] is False
        assert result["checkpoint_boundaries"]==list(range(0,2001,200))
        print("PASS short_compare_provisional_stage0_not_passed")
        r=json.loads(receipts["B"].read_text());r["stage0_passed"]=True
        receipts["B"].write_text(json.dumps(r),encoding="utf-8")
        r=json.loads(receipts["A"].read_text());r["stage0_passed"]=True
        receipts["A"].write_text(json.dumps(r),encoding="utf-8")
        bind_data(dp,req,receipts,digest)
        assert compare_short(dp,cp,lp,manifests,receipts)["status"]=="잠정 · 0단계 통과"
        print("PASS short_compare_stage0_passed_still_provisional")
        r=json.loads(receipts["B"].read_text());r["checkpoint_sha256"].pop("checkpoint_000400.pt")
        receipts["B"].write_text(json.dumps(r),encoding="utf-8")
        rejects("checkpoint_400_missing",lambda:compare_short(dp,cp,lp,manifests,receipts),
                ValueError,"short_checkpoint_boundary_missing")
        r["checkpoint_sha256"]["checkpoint_000400.pt"]=sha(Path(r["out_root"])/"checkpoint_000400.pt")
        receipts["B"].write_text(json.dumps(r),encoding="utf-8")
        bind_data(dp,req,receipts,digest)
        data=json.loads(dp.read_text());data["source_receipts"]["B"]="0"*64
        dp.write_text(json.dumps(data),encoding="utf-8")
        rejects("unbound_evaluation_data",lambda:compare_short(dp,cp,lp,manifests,receipts),
                ValueError,"short_evaluation_provenance_mismatch")
        bind_data(dp,req,receipts,digest)
        m=json.loads(manifests["B"].read_text());m["plan"]["seed"]=12
        manifests["B"].write_text(json.dumps(m),encoding="utf-8")
        rejects("different_seed",lambda:compare_short(dp,cp,lp,manifests,receipts),
                ValueError,"short_training_conditions_mismatch")
        m["plan"]["seed"]=11;m["plan"]["parent"]="other-parent"
        manifests["B"].write_text(json.dumps(m),encoding="utf-8")
        rejects("different_parent",lambda:compare_short(dp,cp,lp,manifests,receipts),
                ValueError,"short_training_conditions_mismatch")
        m["plan"]["parent"]=req["B"]["plan"]["parent"]
        m["evaluation_criteria_sha256"]="0"*64
        manifests["B"].write_text(json.dumps(m),encoding="utf-8")
        rejects("different_evaluation",lambda:compare_short(dp,cp,lp,manifests,receipts),
                ValueError,"short_manifest_conditions_mismatch")


if __name__=="__main__":test()
