"""S2 finite unattended chain controller. CPU fixture runs; live launch is fail closed.

The controller has no LLM or Isaac import. An eventual live executor must prove OS family
ownership, common leases, raw validator and hard deadline watchdog before use.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import argparse
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
import shutil

import s2_stage_gate_17v as G
from s2_chain_receipt import ReceiptHold, commit_stage


class Hold(RuntimeError):
    pass


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _positive(x) -> bool:
    return type(x) in (int, float) and math.isfinite(x) and x > 0


def validate_bundle(manifest: dict, approval: dict, *, now_epoch: float, cpu_fixture: bool) -> None:
    """Single location for the approval contract. An ASTRA recommendation is not approval."""
    try:
        if approval["status"] != "APPROVED" or not approval["by"] or not approval["approval_id"]:
            raise Hold("approval_missing")
        if any(re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) is None for value in
               (manifest["chain_id"], approval["approval_id"])):
            raise Hold("claim_identifier")
        if approval["manifest_sha256"] != hashlib.sha256(canonical(manifest)).hexdigest():
            raise Hold("approval_digest")
        if approval["chain_id"] != manifest["chain_id"] or now_epoch >= approval["expires_epoch"]:
            raise Hold("approval_expired_or_wrong_chain")
        if manifest["approval"]["frozen_sha256"] != G.frozen_digest(manifest) or manifest["approval"]["status"] != "APPROVED":
            raise Hold("stage3_approval_unbound")
        if manifest["approval"]["by"] != approval["by"]:
            raise Hold("approver_mismatch")
        if now_epoch >= manifest["deadline_epoch"] or manifest["deadline_epoch"] > approval["expires_epoch"]:
            raise Hold("deadline")
        if not cpu_fixture and approval["runtime_certification"] != "VERIFIED":
            raise Hold("runtime_certification")
        if not cpu_fixture:
            # No claim of safe Windows Job ownership or legacy slot/guard repair in this CPU candidate.
            raise Hold("live_executor_unverified")
        if manifest["stage_graph"] != [*G.STAGES, "extend"] or manifest["auto_retries"] != 0:
            raise Hold("stage_graph_or_retry")
        contract = manifest["runtime_contract"]
        for key in ("python_executable", "python_sha256", "import_inventory", "usd_assets",
                    "argv_by_stage", "seed_by_stage", "encoder_by_arm", "ppo_sha256",
                    "environment_sha256", "evaluation_sha256", "comparator_sha256",
                    "checkpoint_boundaries", "max_transitions_by_stage", "max_output_bytes_by_stage"):
            if key not in contract or contract[key] in (None, "", "UNDECIDED"):
                raise Hold("runtime_contract_"+key)
        if contract["encoder_by_arm"] != {"A": "mlp", "B": "mlp"}:
            raise Hold("first_chain_encoder")
        if not isinstance(contract["argv_by_stage"], dict) or set(contract["argv_by_stage"]) != set(G.STAGES):
            raise Hold("argv_stage")
        for stage, argv in contract["argv_by_stage"].items():
            if not isinstance(argv, list) or not argv or any(type(v) is not str or not v or
                                                            any(x in v for x in ("\x00", "\n", "\r")) for v in argv):
                raise Hold("argv_schema")
            if argv[0] != contract["python_executable"]:
                raise Hold("argv_executable")
        if not Path(contract["python_executable"]).is_file() or sha(Path(contract["python_executable"])) != contract["python_sha256"]:
            raise Hold("python_hash")
        for group in ("import_inventory", "usd_assets"):
            paths=contract[group]
            if not isinstance(paths, dict) or not paths or any(not Path(p).is_file() or sha(Path(p))!=digest
                                                                 for p,digest in paths.items()):
                raise Hold(group+"_hash")
        if any(not _positive(value) for group in ("max_transitions_by_stage", "max_output_bytes_by_stage")
               for value in contract[group].values()):
            raise Hold("runtime_budget")
        if contract["checkpoint_boundaries"] != sorted(set(contract["checkpoint_boundaries"])):
            raise Hold("checkpoint_boundaries")
        extension = manifest["extension"]
        required = ("candidate_increments", "max_total_updates", "max_increments", "max_disk_bytes",
                    "reserve_seconds", "heartbeat_seconds", "stale_after_seconds", "stop_file", "claim_root")
        if any(k not in extension for k in required):
            raise Hold("extension_missing")
        sizes = extension["candidate_increments"]
        if not isinstance(sizes, list) or not sizes or any(type(x) is not int or x <= 0 for x in sizes) or sizes != sorted(set(sizes), reverse=True):
            raise Hold("extension_sizes")
        if any(not _positive(extension[k]) for k in ("max_total_updates", "max_increments", "max_disk_bytes",
                                                      "reserve_seconds", "heartbeat_seconds", "stale_after_seconds")):
            raise Hold("extension_budget")
        if extension["stale_after_seconds"] <= extension["heartbeat_seconds"]:
            raise Hold("heartbeat_contract")
        if not extension["stop_file"] or not extension["claim_root"]:
            raise Hold("path_missing")
        if Path(extension["stop_file"]).exists():
            raise Hold("stop_file")
        inventory = manifest["file_inventory"]
        if not inventory or any(not Path(p).is_file() or sha(Path(p)) != h for p, h in inventory.items()):
            raise Hold("file_inventory")
        for key in ("gpu_uuid_by_arm", "common_usd_lock", "gpu_lease_root", "validator_sha256",
                    "criteria_sha256", "max_vram_mib_by_arm", "max_wall_s_by_stage"):
            if key not in manifest or manifest[key] in (None, "", "UNDECIDED"):
                raise Hold("contract_missing_" + key)
        if set(manifest["gpu_uuid_by_arm"]) != {"A", "B"} or len(set(manifest["gpu_uuid_by_arm"].values())) != 2:
            raise Hold("device_pair")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, Hold):
            raise
        raise Hold("approval_schema") from exc


def claim_chain(manifest: dict, approval: dict) -> Path:
    """Consume once per whole bundle, never per arm or output path."""
    root = Path(manifest["extension"]["claim_root"])
    root.mkdir(parents=True, exist_ok=True)
    claim = root / (manifest["chain_id"] + "-" + approval["approval_id"] + ".claim")
    try:
        claim.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise Hold("claim_reused") from exc
    (claim / "approval.sha256").write_text(hashlib.sha256(canonical(approval)).hexdigest(), encoding="ascii")
    return claim


def child_claim(chain_claim: Path, stage: str, arm: str, ordinal: int) -> Path:
    if stage not in (*G.STAGES, "extend") or arm not in ("A", "B", "pair") or type(ordinal) is not int or ordinal < 0:
        raise Hold("child_claim_schema")
    path = chain_claim / f"{stage}-{arm}-{ordinal}.claim"
    try:
        path.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise Hold("child_claim_reused") from exc
    return path


class Status:
    def __init__(self, path: Path, interval: float, *, chain_id: str, deadline_epoch: float):
        self.path = path
        self.interval = interval
        self.data = {"chain_id": chain_id, "state": "STARTING", "current_stage": None, "last_verdict": None,
                     "next_stage": "connect", "update": 0, "last_artifact_epoch": None, "deadline_epoch": deadline_epoch}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.failed = threading.Event()
        self._thread = None

    def write(self, **changes):
        with self._lock:
            self.data.update(changes)
            self.data["heartbeat_epoch"] = time.time()
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
            for attempt in range(200):
                try:
                    os.replace(tmp, self.path)
                    break
                except PermissionError:
                    if attempt == 199:
                        raise
                    time.sleep(.01)

    def start(self):
        self.write()
        def loop():
            while not self._stop.wait(self.interval):
                try:
                    self.write()
                except OSError:
                    self.failed.set()
                    self._stop.set()
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=max(1, self.interval*2))


def inspect_status(path: Path, *, now_epoch: float, stale_after_seconds: float, min_artifact_age: float) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        age = now_epoch - state["heartbeat_epoch"]
        artifact_age = None if state["last_artifact_epoch"] is None else now_epoch-state["last_artifact_epoch"]
        return {"state": state["state"], "heartbeat_stale": age > stale_after_seconds,
                "artifact_stale": artifact_age is None or artifact_age > min_artifact_age,
                "heartbeat_age_s": age, "artifact_age_s": artifact_age}
    except (OSError, KeyError, ValueError, TypeError):
        return {"state": "UNKNOWN", "heartbeat_stale": True, "artifact_stale": True}


def _preflight(manifest: dict, *, monotonic_end: float, status: Status):
    if Path(manifest["extension"]["stop_file"]).exists():
        raise Hold("stop_file")
    if time.time() >= manifest["deadline_epoch"] or time.monotonic() >= monotonic_end:
        raise Hold("deadline")
    if status.failed.is_set():
        raise Hold("heartbeat_write_failed")
    if shutil.disk_usage(status.path.parent).free < manifest["extension"]["max_disk_bytes"]:
        raise Hold("disk_reserve")
    if any(not Path(p).is_file() or sha(Path(p)) != h for p, h in manifest["file_inventory"].items()):
        raise Hold("file_inventory_changed")


def choose_increment(manifest: dict, *, now_epoch: float, monotonic_end: float,
                     completed_updates: int, ordinal: int, measured: list[dict]) -> int | None:
    ex = manifest["extension"]
    if ordinal >= ex["max_increments"] or completed_updates >= ex["max_total_updates"] or not measured:
        return None
    remaining = min(manifest["deadline_epoch"]-now_epoch, monotonic_end-time.monotonic())
    # Conservative recent per-update rate and checkpoint/termination cost, including the short A/B observation.
    recent = measured[-3:]
    rate = max(x["wall_s"]/x["updates"] for x in recent)
    overhead = max(x["checkpoint_and_stop_s"] for x in recent)
    for size in ex["candidate_increments"]:
        if completed_updates+size <= ex["max_total_updates"] and rate*size+overhead+ex["reserve_seconds"] < remaining:
            return size
    return None


def validate_extension_pair(manifest: dict, pair: dict, *, ordinal: int, size: int,
                            previous_sha256: str, previous_update: int) -> str:
    """Recount a small raw receipt contract; actual sensor validator remains separately required."""
    seen = set()
    for arm in ("A", "B"):
        r = pair.get(arm)
        if not isinstance(r, dict):
            raise Hold("extension_arm_missing")
        expected = {"chain_id": manifest["chain_id"], "arm": arm, "ordinal": ordinal,
                    "start_update": previous_update, "end_update": previous_update+size,
                    "previous_sha256": previous_sha256, "device_uuid": manifest["gpu_uuid_by_arm"][arm]}
        if any(r.get(k) != v for k, v in expected.items()):
            raise Hold("extension_identity")
        if r.get("attempt") in seen or not r.get("attempt"):
            raise Hold("extension_attempt")
        seen.add(r["attempt"])
        if r.get("validator_sha256") != manifest["validator_sha256"] or r.get("validator_verdict") != "PASS":
            raise Hold("extension_validator")
        if r.get("faults") != 0 or r.get("discarded") != 0 or r.get("optimizer_steps") != size*r.get("steps_per_update", -1):
            raise Hold("extension_integrity")
        checkpoint = Path(r.get("checkpoint_path", ""))
        raw = Path(r.get("raw_path", ""))
        if not checkpoint.is_file() or checkpoint.stat().st_size == 0 or sha(checkpoint) != r.get("checkpoint_sha256"):
            raise Hold("extension_checkpoint")
        if not raw.is_file() or raw.stat().st_size == 0 or sha(raw) != r.get("raw_sha256"):
            raise Hold("extension_raw")
        data = json.loads(raw.read_text(encoding="utf-8"))
        if data.get("faults") != 0 or data.get("updates") != size or data.get("packet_count", 0) <= 0:
            raise Hold("extension_raw_recount")
        if r.get("family_state") != "WAITING_AT_BARRIER":
            raise Hold("extension_family")
    return hashlib.sha256(canonical(pair)).hexdigest()


def run_chain(manifest: dict, approval: dict, executor, *, status_path: Path, cpu_fixture: bool,
              now_epoch: float | None = None) -> dict:
    if now_epoch is None:
        now_epoch = time.time()
    validate_bundle(manifest, approval, now_epoch=now_epoch, cpu_fixture=cpu_fixture)
    claim = claim_chain(manifest, approval)
    status = Status(status_path, manifest["extension"]["heartbeat_seconds"], chain_id=manifest["chain_id"],
                    deadline_epoch=manifest["deadline_epoch"])
    monotonic_end = time.monotonic()+manifest["deadline_epoch"]-now_epoch
    status.start()
    previous = None
    previous_receipt_sha = None
    seen_attempts = set()
    history = []
    try:
        for idx, stage in enumerate(G.STAGES):
            _preflight(manifest, monotonic_end=monotonic_end, status=status)
            for arm in (("A",) if idx==0 else ("A","B")):
                child_claim(claim, stage, arm, 0)
            status.write(state="RUNNING", current_stage=stage, next_stage=None)
            record = executor.initial(stage, manifest["stages"][stage], previous)
            result = G.verdict(manifest, stage, record, previous=previous,
                               seen_attempts=seen_attempts, now_epoch=time.time())
            status.write(last_verdict=result["verdict"], last_artifact_epoch=time.time())
            if result["verdict"] != "PASS":
                raise Hold(stage + ":" + ",".join(result["reasons"]))
            previous_receipt_sha = commit_stage(claim, manifest, stage, record, result,
                                                previous_sha256=previous_receipt_sha)
            seen_attempts.add(record["attempt"])
            if idx < len(G.STAGES)-1 and result.get("next_args", {}).get("stage") != G.STAGES[idx+1]:
                raise Hold("stage_next_args")
            previous = result
            status.write(next_stage=G.STAGES[idx+1] if idx < len(G.STAGES)-1 else "extend")
        observation = executor.timing_observation()
        if not all(_positive(observation.get(k)) for k in ("updates", "wall_s", "checkpoint_and_stop_s")):
            raise Hold("timing_unmeasured")
        history.append(observation)
        update = manifest["stages"]["short_ab"]["updates_per_arm"]
        prior_sha = hashlib.sha256(canonical(previous)).hexdigest()
        ordinal = 0
        while True:
            _preflight(manifest, monotonic_end=monotonic_end, status=status)
            size = choose_increment(manifest, now_epoch=time.time(), monotonic_end=monotonic_end,
                                    completed_updates=update, ordinal=ordinal, measured=history)
            if size is None:
                status.write(state="COMPLETE", current_stage=None, next_stage=None, update=update, last_verdict="PASS")
                return {"state": "COMPLETE", "updates_per_arm": update, "extensions": ordinal, "claim": str(claim)}
            child_claim(claim, "extend", "A", ordinal)
            child_claim(claim, "extend", "B", ordinal)
            status.write(state="RUNNING", current_stage="extend", next_stage=None, update=update)
            pair, timing = executor.extend(size, ordinal, update, prior_sha)
            prior_sha = validate_extension_pair(manifest, pair, ordinal=ordinal, size=size,
                                                previous_sha256=prior_sha, previous_update=update)
            if not all(_positive(timing.get(k)) for k in ("updates", "wall_s", "checkpoint_and_stop_s")) or timing["updates"] != size:
                raise Hold("extension_timing")
            history.append(timing)
            update += size
            ordinal += 1
            status.write(state="AT_BARRIER", current_stage="extend", next_stage="extend", update=update,
                         last_artifact_epoch=time.time(), last_verdict="PASS")
    except (Hold, ReceiptHold, OSError, ValueError, KeyError, TypeError) as exc:
        status.write(state="HOLD", last_verdict="HOLD", next_stage=None, reason=str(exc))
        return {"state": "HOLD", "reason": str(exc), "claim": str(claim)}
    finally:
        status.close()


class FixtureExecutor:
    """Frozen local record files for CPU tests only. It never launches Isaac."""
    def __init__(self, plan: dict):
        self.plan = plan
        self.delay = plan["delay_seconds"]

    def initial(self, stage, _stage_plan, _previous):
        time.sleep(self.delay)
        return json.loads(Path(self.plan["initial_records"][stage]).read_text(encoding="utf-8"))

    def timing_observation(self):
        return self.plan["timing_observation"]

    def extend(self, _size, ordinal, _update, _prior_sha):
        time.sleep(self.delay)
        item = self.plan["extensions"][ordinal]
        return json.loads(Path(item["pair_path"]).read_text(encoding="utf-8")), item["timing"]


def launch_detached_cpu_fixture(*, script: Path, manifest: Path, approval: Path,
                                fixture_plan: Path, status: Path, log: Path) -> subprocess.Popen:
    """Windows detached example. Only registered CPU fixture entry is permitted."""
    if os.name != "nt" or script.resolve() != Path(__file__).resolve():
        raise Hold("detached_fixture_only_windows_self")
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    creation = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    stream = log.open("ab")
    try:
        return subprocess.Popen([sys.executable, "-B", str(script), "--cpu-fixture-plan", str(fixture_plan),
                                 "--manifest", str(manifest), "--approval", str(approval), "--status", str(status)],
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                env=env, creationflags=creation, close_fds=True)
    finally:
        stream.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu-fixture-plan", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--approval", type=Path, required=True)
    ap.add_argument("--status", type=Path, required=True)
    a = ap.parse_args(argv)
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "-1":
        raise Hold("cpu_only")
    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    approval = json.loads(a.approval.read_text(encoding="utf-8"))
    plan = json.loads(a.cpu_fixture_plan.read_text(encoding="utf-8"))
    result = run_chain(manifest, approval, FixtureExecutor(plan), status_path=a.status, cpu_fixture=True)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["state"] == "COMPLETE" else 42


if __name__ == "__main__":
    raise SystemExit(main())
