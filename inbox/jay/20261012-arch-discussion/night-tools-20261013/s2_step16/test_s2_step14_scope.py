"""CPU known-answer and scope mutations. No process or Kit launch."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from s2_eval_cases import seal, canonical
from s2_eval_cpu import sha
from s2_eval_scope import CODE_NAMES, ScopeHold, required_argv, validate
from s2_eval_driver import PARENT_E1_SHA256, AGENT_YAML_SHA256
from s2_eval_supervisor import _output_verdict, observer_armed, run_eval, EvalSupervisorHold


HERE = Path(__file__).resolve().parent


class TestScope(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=HERE.parent)
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        cases = seal(phase="smoke", counts={"gap": 2, "stepping_stones": 2, "flat": 0, "stairs_up": 0},
                     eval_seeds=[101, 102, 103, 104], learning_seeds=[7, 11], command="fwd10",
                     difficulty=.5, terrain_source_sha256="a"*64, terrain_source="pinned_source.py",
                     geometry_sha256="b"*64, friction=1.)
        parent_root = Path("C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192")
        for arm in ("A", "B"):
            (root / arm).write_bytes(arm.encode())
        job = {"schema": "s2-eval-job-v1", "phase": "smoke", "update": 0,
               "inference": "act_inference", "cases_sha256": cases["cases_sha256"],
               "parent": {"path": str(parent_root / "model_20000.pt"), "sha256": PARENT_E1_SHA256},
               "agent_yaml": {"path": str(parent_root / "params/agent.yaml"), "sha256": AGENT_YAML_SHA256},
               "arms": {arm: {"checkpoint": str(root / arm), "checkpoint_sha256": sha(root / arm),
                                "env_config_sha256": "e"*64, "map_init_seed": 0} for arm in ("A", "B")}}
        cp, jp = root / "cases.json", root / "job.json"
        cp.write_bytes(canonical(cases) + b"\n")
        jp.write_bytes(canonical(job) + b"\n")
        m = {"scope": "s2_eval_kit_smoke_once", "purpose": "evaluation_information_only",
             "chain_id": "fixture", "attempt": "once", "claim_root": str(root / "claims"),
             "status_path": str(root / "status.json"), "stop_path": str(root / "STOP"),
             "deadline_epoch": 150., "max_wall_s": 100, "observer_mode": "attended",
             "observer_registration_path": str(root / "registration.json"),
             "observer_log_path": str(root / "observer" / "observer.log"),
             "max_launches": 1, "retry_count": 0, "training_updates": 0,
             "python_path": str(HERE / "s2_eval_cases.py"),
             "isolate_path": str(HERE / "usd_isolate_run_v3.py"),
             "driver_path": str(HERE / "s2_eval_driver.py"),
             "job_path": str(jp), "cases_path": str(cp),
             "episodes_path": str(root / "episodes" / "episodes.json"),
             "log_path": str(root / "log" / "child.log"),
             "usd_root": str(root / "usd"), "usd_lock_path": str(root / "fake.lock"),
             "lease_root": str(root / "leases"), "gpu_uuid": "GPU-fixture", "gpu_index": 0,
             "gpu_bus_id": "0000:01:00.0", "asset_path": "fixture-asset",
             "asset_closure_sha256": "c"*64, "hook_source_path": str(HERE / "s2_sensor_tracker_17v.py"),
             "code_hashes": {name: sha(HERE / name) for name in CODE_NAMES}, "phase": "smoke",
             "min_free_vram_bytes": 1, "running_floor_vram_bytes": 1,
             "min_free_disk_bytes": 1, "max_disk_bytes": 1000000,
             "expect_conversions": "any", "usd_conversion_cap": 8}
        for key in ("python", "isolate", "driver", "job", "hook_source"):
            m[key + "_sha256"] = sha(m[key + "_path"])
        m["cases_file_sha256"] = sha(cp)
        m["argv"] = required_argv(m)
        self.m = m

    def approve(self, m):
        return {"status": "APPROVED", "scope": m["scope"], "by": "fixture",
                "manifest_sha256": hashlib.sha256(canonical(m)).hexdigest(),
                "expires_epoch": 200.}

    def test_known_answer_scope(self):
        result = validate(self.m, self.approve(self.m), now=100., fixture=True)
        self.assertEqual(len(result["cases"]["cases"]), 4)

    def test_mutated_argv_caught(self):
        m = copy.deepcopy(self.m)
        m["argv"][-1] = "cpu"
        with self.assertRaisesRegex(ScopeHold, "exact_argv"):
            validate(m, self.approve(m), now=100., fixture=True)

    def test_scope_and_deadline_caught(self):
        for key, value, want in (("training_updates", 1, "evaluation_only_scope"),
                                  ("phase", "full", "evaluation_only_scope"),
                                  ("deadline_epoch", 201., "resource_or_deadline")):
            with self.subTest(key=key):
                m = copy.deepcopy(self.m)
                m[key] = value
                with self.assertRaisesRegex(ScopeHold, want):
                    validate(m, self.approve(m), now=100., fixture=True)

    def test_code_mutation_caught(self):
        m = copy.deepcopy(self.m)
        m["code_hashes"]["s2_eval_kit_adapter.py"] = "0"*64
        with self.assertRaisesRegex(ScopeHold, "code_closure_sha256"):
            validate(m, self.approve(m), now=100., fixture=True)

    def test_paired_fingerprint_and_observer_receipt(self):
        m = self.m
        cases = json.loads(Path(m["cases_path"]).read_text())
        rows = [{"case_id": c["case_id"], "arm": arm, "fingerprint": {"mesh_sha256": "a"*64},
                 "missing_reason": None, "usd_robot_references": ["robot.usd"]}
                for c in cases["cases"] for arm in ("A", "B")]
        episodes = {"schema": "s2-eval-episodes-v1", "cases_sha256": cases["cases_sha256"],
                    "cases_file_sha256": m["cases_file_sha256"], "job_file_sha256": m["job_sha256"],
                    "records": rows, "comparison_ready": False, "performance_verified": False}
        out = Path(m["episodes_path"])
        out.parent.mkdir()
        out.write_bytes(canonical(episodes) + b"\n")
        observer_log = Path(m["observer_log_path"])
        observer_log.parent.mkdir()
        observer_log.write_text("watchdog_started\n", encoding="utf-8")
        with patch("s2_eval_supervisor.usd_evidence", return_value={"checked": True}):
            verdict = _output_verdict(m, rc=0, family_empty=True, reason=None,
                                      asset_before=None, observer={"status": "ARMED"})
            self.assertEqual(verdict["verdict"], "INFORMATION_ONLY")
            episodes["records"][1]["fingerprint"]["mesh_sha256"] = "b"*64
            out.write_bytes(canonical(episodes) + b"\n")
            changed = _output_verdict(m, rc=0, family_empty=True, reason=None,
                                      asset_before=None, observer={"status": "ARMED"})
            self.assertEqual(changed["verdict"], "HOLD")
            self.assertIn("paired_physical_fingerprint_diff", changed["reasons"])

    def test_observer_identity_mutation(self):
        m = self.m
        watcher_path = HERE / "s2_step4a34" / "s2_hard_watchdog.py"
        args = ["python", str(watcher_path), "--pid", str(os.getpid()),
                "--create-time", "30.0", "--status-path", m["status_path"],
                "--hard-deadline-epoch", str(m["deadline_epoch"]),
                "--log", m["observer_log_path"]]
        class Process:
            def __init__(self, birth, argv):
                self.birth, self.argv = birth, argv
            def create_time(self): return self.birth
            def is_running(self): return True
            def cmdline(self): return self.argv
        registration = {"manifest_sha256": hashlib.sha256(canonical(m)).hexdigest(),
                        "status": "ARMED", "status_path": m["status_path"],
                        "log_path": m["observer_log_path"], "hard_deadline_epoch": 150.,
                        "pid": 987654, "create_time": 40., "supervisor_create_time": 30.}
        Path(m["observer_registration_path"]).write_bytes(canonical(registration))
        table = {os.getpid(): Process(30., []), 987654: Process(40., args)}
        self.assertEqual(observer_armed(m, process_lookup=table.__getitem__)["pid"], 987654)
        table[987654] = Process(41., args)
        with self.assertRaisesRegex(EvalSupervisorHold, "observer_pid_reused_or_dead"):
            observer_armed(m, process_lookup=table.__getitem__)

    def test_fake_owner_receipt_and_family_release(self):
        m = self.m
        events = []
        cases = json.loads(Path(m["cases_path"]).read_text())
        class Lease:
            def __init__(self, name): self.name = name
            def acquire(self): events.append(self.name + ":acquire"); return self
            def release(self, *, family_empty):
                events.append(self.name + ":release:" + str(family_empty))
        class Owner:
            pid = 12345
            def launch(self, argv, cwd, env, log_path):
                events.append("launch")
                rows = [{"case_id": c["case_id"], "arm": arm,
                         "fingerprint": {"mesh_sha256": "a"*64},
                         "missing_reason": None, "usd_robot_references": ["robot.usd"]}
                        for c in cases["cases"] for arm in ("A", "B")]
                out = Path(m["episodes_path"])
                out.parent.mkdir(parents=True)
                out.write_bytes(canonical({"schema": "s2-eval-episodes-v1",
                    "cases_sha256": cases["cases_sha256"],
                    "cases_file_sha256": m["cases_file_sha256"],
                    "job_file_sha256": m["job_sha256"],
                    "records": rows, "comparison_ready": False,
                    "performance_verified": False, "runtime": {"pid": self.pid}}) + b"\n")
                Path(log_path).write_text("fake child\n")
                watch = Path(m["observer_log_path"])
                watch.parent.mkdir()
                watch.write_text("watchdog_started\n")
            def active_count(self): return 0
            def exit_code(self): return 0
            def close(self): events.append("owner:close")
        with patch("s2_eval_supervisor.usd_evidence", return_value={"checked": True}):
            verdict = run_eval(m, self.approve(m), clock=lambda: 100., mono=lambda: 1.,
                    owner_factory=Owner, lease_factory=lambda root, uuid: Lease("gpu"),
                    lock_factory=lambda path: Lease("usd"),
                    observer_check=lambda manifest: {"status": "ARMED"}, fixture=True)
        self.assertEqual(verdict["verdict"], "INFORMATION_ONLY")
        self.assertEqual(events, ["gpu:acquire", "usd:acquire", "launch", "owner:close",
                                  "gpu:release:True", "usd:release:True"])
        claim = Path(m["claim_root"]) / "fixture-once.claim"
        receipt = json.loads((claim / "eval.receipt.json").read_text())
        self.assertTrue(receipt["family_empty"])
        self.assertEqual(receipt["verdict"]["information_only"], True)


if __name__ == "__main__":
    unittest.main()
