"""CPU receipt and map-contract checks for a no-extension short pair."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile

from legacy_test_s2_step9_barrier import criteria_fixture,bind_data
from s2_compare_ab import compare_short
from s2_train_contract import canonical


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step9_compare_single_") as td:
        root=Path(td);cp,lp,dp,digest=criteria_fixture(root)
        raw={arm:json.loads((Path(__file__).parent/f"request_short_{arm}.json").read_text(encoding="utf-8"))
             for arm in ("A","B")}
        manifests={};receipts={}
        for arm,r in raw.items():
            out=root/arm;out.mkdir()
            plan=dict(r["plan"],out_root=str(out),parent_sha256=r["plan"]["parent_sha256"])
            m={"chain_id":r["chain_id"],"gpu_uuid":r["gpu_uuid"],
               "extension_disabled":True,
               "checkpoint_boundaries":list(range(0,2001,200)),
               "evaluation_criteria_sha256":digest,"map_contract_verified":False,"plan":plan}
            mp=root/f"manifest_{arm}.json";mp.write_bytes(canonical(m));manifests[arm]=mp
            hashes={}
            for n in range(0,2001,200):
                name=f"checkpoint_{n:06d}.pt";path=out/name;path.write_bytes(f"{arm}:{n}".encode())
                hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
            receipt={"chain_id":m["chain_id"],"arm":arm,"stage":"short",
                "manifest_sha256":hashlib.sha256(canonical(m)).hexdigest(),
                "verdict":"RUN_COMPLETE_UNVERIFIED","boundary_ok":True,
                "family_active_count":0,"family_cleanup_confirmed":True,
                "gpu_lease_released":True,"usd_lock_released":True,
                "parent_sha256_before":plan["parent_sha256"],
                "parent_sha256_after":plan["parent_sha256"],
                "executed_updates":2000,"extension_disabled":True,
                "out_root":str(out),"checkpoint_sha256":hashes,"stage0_passed":False}
            rp=root/f"receipt_{arm}.json";rp.write_text(json.dumps(receipt),encoding="utf-8")
            receipts[arm]=rp
        bind_data(dp,raw,receipts,digest)
        result=compare_short(dp,cp,lp,manifests,receipts)
        assert result["comparison_ready"] is False and result["status"]=="잠정 · 지도 계약 미확인"
        assert all("판정 보류" in value for value in result["final_only"].values())
        print("PASS no_map_contract_suppresses_effect_claim")
        for mp in manifests.values():
            m=json.loads(mp.read_text());m["map_contract_verified"]=True;mp.write_bytes(canonical(m))
        for arm,rp in receipts.items():
            receipt=json.loads(rp.read_text());receipt["manifest_sha256"]=hashlib.sha256(manifests[arm].read_bytes()).hexdigest()
            rp.write_text(json.dumps(receipt))
        bind_data(dp,raw,receipts,digest)
        result=compare_short(dp,cp,lp,manifests,receipts)
        assert result["comparison_ready"] is True and result["status"]=="잠정 · 0단계 미통과"
        print("PASS verified_map_still_exploratory_without_stage0_pass")
        b=json.loads(receipts["B"].read_text());b["executed_updates"]=2500
        receipts["B"].write_text(json.dumps(b))
        try:compare_short(dp,cp,lp,manifests,receipts)
        except ValueError as ex:assert str(ex)=="short_receipt_unverified"
        else:raise AssertionError("extended receipt accepted")
        print("PASS reject_extended_receipt")


if __name__=="__main__":test()
