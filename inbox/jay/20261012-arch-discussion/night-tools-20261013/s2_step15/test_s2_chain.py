"""Known-answer CPU fake chain and counterexamples. No GPU/Isaac launch."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import psutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "s2_step3"))
from test_s2_step3_contract import stage_fixture, train_record
from test_s2_connect_17v import fixture
from s2_stage_gate_17v import frozen_digest, verdict
from s2_chain_runner import FixtureExecutor, Hold, canonical, inspect_status, run_chain, sha


def check(label, good):
    print(("PASS" if good else "FAIL") + " " + label, flush=True)
    if not good:
        raise AssertionError(label)


def make_case(root: Path, *, deadline_offset=100, max_increments=1, delay=0):
    root.mkdir(parents=True, exist_ok=True)
    meta, arrays = fixture()
    from s2_connect_check_17v import Criteria
    criteria = Criteria(.002, .002, .005, 256, 16)
    m, connect = stage_fixture(root, meta, arrays, criteria)
    m["stages"]["connect"]["diag_steps"] = 256
    m["deadline_epoch"] = time.time()+deadline_offset
    m["chain_id"] = "cpu-fixture-" + root.name
    asset = root / "fixture.usd"
    asset.write_text("#usda 1.0", encoding="utf-8")
    m["stage_graph"] = ["connect", "smoke", "short_ab", "extend"]
    m["auto_retries"] = 0
    m["runtime_contract"] = {
        "python_executable": sys.executable, "python_sha256": sha(Path(sys.executable)),
        "import_inventory": {str(HERE/"s2_chain_runner.py"): sha(HERE/"s2_chain_runner.py")},
        "usd_assets": {str(asset): sha(asset)},
        "argv_by_stage": {s: [sys.executable, str(HERE/"s2_chain_runner.py")]
                          for s in ("connect", "smoke", "short_ab")},
        "seed_by_stage": {"connect": 1, "smoke": 2, "short_ab": 3},
        "encoder_by_arm": {"A": "mlp", "B": "mlp"},
        "ppo_sha256": "a"*64, "environment_sha256": "b"*64,
        "evaluation_sha256": "c"*64, "comparator_sha256": "d"*64,
        "checkpoint_boundaries": [0, 2, 4],
        "max_transitions_by_stage": {"connect": 1, "smoke": 2, "short_ab": 4},
        "max_output_bytes_by_stage": {"connect": 100, "smoke": 100, "short_ab": 100}}
    m["extension"] = {"candidate_increments": [2, 1], "max_total_updates": 4,
                      "max_increments": max_increments, "max_disk_bytes": 1000000000, "reserve_seconds": 1,
                      "heartbeat_seconds": .05, "stale_after_seconds": .3,
                      "stop_file": str(root / "STOP"), "claim_root": str(root / "claims")}
    m["gpu_uuid_by_arm"] = {"A": "synthetic-gpu-1", "B": "synthetic-gpu-0"}
    m["common_usd_lock"] = str(root / "synthetic_usd_lock")
    m["gpu_lease_root"] = str(root / "synthetic_leases")
    m["validator_sha256"] = "d"*64
    m["criteria_sha256"] = "e"*64
    m["max_vram_mib_by_arm"] = {"A": 100, "B": 100}
    m["max_wall_s_by_stage"] = {"connect": 10, "smoke": 10, "short_ab": 10, "extend": 10}
    m["file_inventory"] = {str(HERE / "s2_chain_runner.py"): sha(HERE / "s2_chain_runner.py")}
    m["approval"]["frozen_sha256"] = frozen_digest(m)
    c = verdict(m, "connect", connect, now_epoch=time.time())
    smoke = train_record(root, c)
    s = verdict(m, "smoke", smoke, previous=c, now_epoch=time.time())
    short = train_record(root, s)
    short["attempt"] = "short1"
    t = verdict(m, "short_ab", short, previous=s, now_epoch=time.time())
    assert [c["verdict"], s["verdict"], t["verdict"]] == ["PASS"]*3
    records = {}
    for stage, rec in (("connect", connect), ("smoke", smoke), ("short_ab", short)):
        p = root / (stage+"_record.json")
        p.write_text(json.dumps(rec), encoding="utf-8")
        records[stage] = str(p)
    prior = "AUTO"
    pair = {}
    for arm in ("A", "B"):
        cp = root / (arm+".pt")
        raw = root / (arm+"_raw.json")
        import torch
        torch.save({"format":"s2-17v-checkpoint-only","mode":arm,"resume_supported":False,
                    "policy":{"w":torch.ones(1)},"optimizer":{"state":{"x":1}}},cp)
        raw.write_text(json.dumps({"faults": 0, "updates": 2, "packet_count": 4,
                                   "rows":[{"update":3,"optimizer_steps":4,"packet_count":2,"faults":0,"discarded":0},
                                           {"update":4,"optimizer_steps":4,"packet_count":2,"faults":0,"discarded":0}]}), encoding="utf-8")
        pair[arm] = {"chain_id": m["chain_id"], "arm": arm, "ordinal": 0,
                     "start_update": 2, "end_update": 4, "previous_sha256": prior,
                     "device_uuid": m["gpu_uuid_by_arm"][arm], "attempt": "synthetic-"+arm,
                     "validator_sha256": m["validator_sha256"], "validator_verdict": "PASS",
                     "faults": 0, "discarded": 0, "optimizer_steps": 8, "steps_per_update": 4,
                     "device_peak_mib":50,"device_min_free_mib":50,
                     "checkpoint_path": str(cp), "checkpoint_sha256": sha(cp),
                     "raw_path": str(raw), "raw_sha256": sha(raw), "family_state": "WAITING_AT_BARRIER"}
    pp = root / "pair.json"
    pp.write_text(json.dumps(pair), encoding="utf-8")
    plan = {"delay_seconds": delay, "initial_records": records,
            "timing_observation": {"updates": 2, "wall_s": 2, "checkpoint_and_stop_s": 1},
            "extensions": [{"pair_path": str(pp), "timing": {"updates": 2, "wall_s": 2, "checkpoint_and_stop_s": 1}}]}
    a = {"status": "APPROVED", "by": "synthetic-fixture", "approval_id": "fixture-1",
         "chain_id": m["chain_id"], "expires_epoch": m["deadline_epoch"]+1,
         "runtime_certification": "SYNTHETIC_ONLY", "manifest_sha256": hashlib.sha256(canonical(m)).hexdigest()}
    return m, a, plan, pair


def test_all():
    with tempfile.TemporaryDirectory(prefix="s2_step4_chain_") as td:
        root = Path(td)
        m, a, plan, pair = make_case(root / "normal")
        status = root / "normal" / "chain_status.json"
        result = run_chain(m, a, FixtureExecutor(plan), status_path=status, cpu_fixture=True)
        check("normal_chain_to_extension_checkpoint", result["state"] == "COMPLETE" and result["updates_per_arm"] == 4)
        check("status_heartbeat_and_boundary", json.loads(status.read_text())["state"] == "COMPLETE" and
              "heartbeat_epoch" in json.loads(status.read_text()))
        try:
            run_chain(m, a, FixtureExecutor(plan), status_path=status, cpu_fixture=True)
        except Hold as exc:
            check("approval_claim_once", str(exc) == "claim_reused")
        else:
            check("approval_claim_once", False)
        changed = copy.deepcopy(a)
        changed["manifest_sha256"] = "0"*64
        try:
            run_chain(m, changed, FixtureExecutor(plan), status_path=root/"x.json", cpu_fixture=True)
        except Hold as exc:
            check("approval_digest", str(exc) == "approval_digest")
        else:
            check("approval_digest", False)
        m2, a2, p2, _ = make_case(root / "stage_hold")
        result_path = Path(json.loads(Path(p2["initial_records"]["smoke"]).read_text())["artifacts"]["B_result"]["path"])
        data = json.loads(result_path.read_text())
        data["status"] = "HOLD"
        result_path.write_text(json.dumps(data), encoding="utf-8")
        held = run_chain(m2, a2, FixtureExecutor(p2), status_path=root/"stage_hold"/"chain_status.json", cpu_fixture=True)
        check("one_arm_hold_both_no_next", held["state"] == "HOLD" and "artifact_hash" in held["reason"] and
              not (root/"stage_hold"/"claims"/(m2["chain_id"]+"-"+a2["approval_id"]+".claim")/"short_ab-pair-0.claim").exists())
        m3, a3, p3, _ = make_case(root / "deadline", deadline_offset=3)
        ended = run_chain(m3, a3, FixtureExecutor(p3), status_path=root/"deadline"/"chain_status.json", cpu_fixture=True)
        check("deadline_checkpoint_boundary", ended["state"] == "COMPLETE" and ended["updates_per_arm"] == 2)
        m4, a4, p4, _ = make_case(root / "stop")
        class StopExecutor(FixtureExecutor):
            def initial(self, stage, plan, previous):
                rec = super().initial(stage, plan, previous)
                if stage == "connect":
                    Path(m4["extension"]["stop_file"]).write_text("STOP")
                return rec
        stopped = run_chain(m4, a4, StopExecutor(p4), status_path=root/"stop"/"chain_status.json", cpu_fixture=True)
        check("stop_after_connect", stopped["state"] == "HOLD" and "stop_file" in stopped["reason"] and
              not (root/"stop"/"claims"/(m4["chain_id"]+"-"+a4["approval_id"]+".claim")/"smoke-pair-0.claim").exists())
        status.write_text(json.dumps({"state": "RUNNING", "heartbeat_epoch": time.time()-10,
                                      "last_artifact_epoch": time.time()-10}))
        check("stale_heartbeat_and_artifact", all(inspect_status(status, now_epoch=time.time(), stale_after_seconds=.3,
                                                                  min_artifact_age=.3)[k] for k in ("heartbeat_stale", "artifact_stale")))
        m5, a5, p5, pair5 = make_case(root / "raw_hold")
        raw = Path(pair5["B"]["raw_path"])
        raw.write_text(json.dumps({"faults": 1, "updates": 2, "packet_count": 4,
                                   "rows":[{"update":3,"optimizer_steps":4,"packet_count":2,"faults":0,"discarded":0},
                                           {"update":4,"optimizer_steps":4,"packet_count":2,"faults":1,"discarded":0}]}))
        pair5["B"]["raw_sha256"] = sha(raw)
        Path(p5["extensions"][0]["pair_path"]).write_text(json.dumps(pair5), encoding="utf-8")
        held = run_chain(m5, a5, FixtureExecutor(p5), status_path=root/"raw_hold"/"chain_status.json", cpu_fixture=True)
        check("extension_raw_fault_holds_both", held["state"] == "HOLD" and held["reason"] == "extension_raw_recount")
        m7, a7, p7, pair7 = make_case(root / "partial_checkpoint")
        cp7 = Path(pair7["B"]["checkpoint_path"])
        cp7.write_bytes(b"interrupted checkpoint")
        pair7["B"]["checkpoint_sha256"] = sha(cp7)
        Path(p7["extensions"][0]["pair_path"]).write_text(json.dumps(pair7), encoding="utf-8")
        partial = run_chain(m7, a7, FixtureExecutor(p7),
                            status_path=root/"partial_checkpoint"/"chain_status.json", cpu_fixture=True)
        check("incomplete_checkpoint_holds_pair", partial["state"] == "HOLD" and
              partial["reason"] == "extension_checkpoint_incomplete")
        m8, a8, p8, pair8 = make_case(root / "stale_receipt")
        pair8["B"]["previous_sha256"] = "0"*64
        Path(p8["extensions"][0]["pair_path"]).write_text(json.dumps(pair8), encoding="utf-8")
        stale = run_chain(m8, a8, FixtureExecutor(p8),
                          status_path=root/"stale_receipt"/"chain_status.json", cpu_fixture=True)
        check("stale_previous_receipt_holds_pair", stale["state"] == "HOLD" and
              stale["reason"] == "extension_identity")
        m6, a6, p6, _ = make_case(root / "detached", delay=.3)
        mp, ap, fp = (root/"detached"/n for n in ("manifest.json", "approval.json", "plan.json"))
        mp.write_text(json.dumps(m6), encoding="utf-8")
        ap.write_text(json.dumps(a6), encoding="utf-8")
        fp.write_text(json.dumps(p6), encoding="utf-8")
        pid_file = root/"detached"/"child.pid"
        cmd = [sys.executable, "-B", str(HERE/"s2_fake_parent.py"), "--manifest", str(mp), "--approval", str(ap),
               "--fixture-plan", str(fp), "--status", str(root/"detached"/"chain_status.json"),
               "--log", str(root/"detached"/"child.log"), "--pid-file", str(pid_file)]
        env = os.environ.copy(); env["CUDA_VISIBLE_DEVICES"] = "-1"
        parent = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if pid_file.exists(): break
                time.sleep(.05)
            check("fake_parent_started_child", pid_file.exists())
            parent.terminate()  # Only the fake parent created by this test.
            parent.wait(timeout=5)
            state_path = root/"detached"/"chain_status.json"
            state = None
            for _ in range(400):
                if state_path.exists():
                    try: state = json.loads(state_path.read_text(encoding="utf-8"))
                    except (PermissionError, OSError, json.JSONDecodeError): state = None
                if state is not None and state.get("state") == "COMPLETE": break
                time.sleep(.05)
            if state is None or state.get("state") != "COMPLETE":
                print("DETACHED_DEBUG", (root/"detached"/"child.log").read_text(encoding="utf-8", errors="replace")[-2000:])
            check("detached_chain_survives_own_parent", state is not None and state.get("state") == "COMPLETE")
            try:
                psutil.Process(int(pid_file.read_text())).wait(timeout=10)
            except psutil.NoSuchProcess:
                pass
        finally:
            if parent.poll() is None:
                parent.terminate(); parent.wait(timeout=5)


if __name__ == "__main__":
    test_all()
