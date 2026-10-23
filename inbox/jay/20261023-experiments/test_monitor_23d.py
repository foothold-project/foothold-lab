import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import monitor_23d as monitor


class Monitor23dTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / "fake-run"
        self.run.mkdir()
        self.state = self.root / "review-state.json"
        self.seq_video = self.root / "fake_seq_video.py"
        self.seq_video.write_text(
            "import hashlib,json,pathlib,sys\n"
            "p=pathlib.Path(sys.argv[sys.argv.index('--verify-receipt')+1])\n"
            "r=json.loads(p.read_text())\n"
            "assert all(hashlib.sha256((p.parent/n).read_bytes()).hexdigest()==h for n,h in r['files'].items())\n"
            "print(json.dumps({'ok':True}))\n",
            encoding="utf-8",
        )
        self.write_json(self.run / "manifest.json", {
            "schema": "foothold-manifest/1",
            "run": {"name": "B", "started_at": "2026-10-23 20:00:00",
                    "cli_args": {"run_name": "B"}},
            "progress": {"completed_updates": 500, "total_env_steps": 100},
            "checkpoints": {},
        })
        self.write_json(self.run / "train_start_status.json", {
            "state": "running", "iter": 500, "time": "2026-10-23T20:30:00",
        })
        self.add_checkpoints((500,))

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def add_checkpoints(self, iterations):
        manifest_path = self.run / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for iteration in iterations:
            name = f"model_{iteration}.pt"
            checkpoint = self.run / name
            checkpoint.write_bytes(f"known model checkpoint {iteration}".encode())
            manifest["checkpoints"][name] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        manifest["progress"]["completed_updates"] = max(iterations)
        self.write_json(manifest_path, manifest)
        self.write_json(self.run / "train_start_status.json", {
            "state": "running", "iter": max(iterations), "time": "2026-10-23T21:00:00",
        })

    def scan(self, *, now=1792789200, deadline=1792875600, publish=True):
        return monitor.scan([self.run], self.state, publish=publish,
                            deadline=deadline, now=now)

    def test_runner_manifest_and_numeric_checkpoint_order(self):
        self.add_checkpoints((500, 1000, 1500, 2500, 3500))
        result = self.scan()
        self.assertEqual([r["iteration"] for r in result["created"]],
                         [500, 1000, 1500, 2500, 3500])
        self.assertEqual(result["state"]["runs"][str(self.run.resolve())]
                         ["last_requested_iteration"], 3500)

    def test_three_hour_signal_chooses_latest_checkpoint_not_older_1550(self):
        now = 1792789200
        self.add_checkpoints((500, 1000, 1500))
        first = self.scan(now=now)
        self.assertEqual([r["iteration"] for r in first["created"]], [500, 1000, 1500])
        state = monitor.load_state(self.state)
        run_state = state["runs"][str(self.run.resolve())]
        run_state["last_requested_iteration"] = 1500
        run_state["last_requested_epoch"] = now - monitor.POST_TIME_SECONDS - 1
        monitor.atomic_json(self.state, state)
        self.add_checkpoints((1550, 2000))
        after_timer = self.scan(now=now)
        self.assertEqual([r["iteration"] for r in after_timer["created"]], [2000])

    def test_concurrent_state_transitions_do_not_lose_updates(self):
        self.add_checkpoints((500,))
        requests = {
            f"req-{i}": {"id": f"req-{i}", "state": "pending",
                         "completion_evidence": None}
            for i in range(16)
        }
        monitor.atomic_json(self.state, {"version": 2, "requests": requests, "runs": {}})
        script = Path(monitor.__file__)

        def claim(request_id):
            return subprocess.run(
                [sys.executable, str(script), "transition", "--state", str(self.state),
                 "--id", request_id, "--to", "claimed"],
                capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
            )

        def scan_and_publish():
            return subprocess.run(
                [sys.executable, str(script), "scan", "--run", str(self.run),
                 "--state", str(self.state), "--deadline", "2026-10-24T21:00:00+00:00",
                 "--publish"],
                capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
            )

        with ThreadPoolExecutor(max_workers=16) as pool:
            claims = [pool.submit(claim, request_id) for request_id in requests]
            scan = pool.submit(scan_and_publish)
            results = [future.result() for future in claims] + [scan.result()]
        self.assertTrue(all(result.returncode == 0 for result in results),
                        [result.stderr for result in results if result.returncode])
        final = monitor.load_state(self.state)
        claimed = [row for request_id, row in final["requests"].items()
                   if request_id.startswith("req-")]
        scanned = [row for request_id, row in final["requests"].items()
                   if not request_id.startswith("req-")]
        self.assertEqual(len(claimed), 16)
        self.assertTrue(all(row["state"] == "claimed" for row in claimed))
        self.assertEqual([row["iteration"] for row in scanned], [500])

    def test_dry_run_known_checkpoint_does_not_write(self):
        result = self.scan(publish=False)
        self.assertTrue(result["dry_run"])
        self.assertEqual(len(result["created"]), 1)
        self.assertFalse(self.state.exists())
        self.assertEqual(result["created"][0]["checkpoint_sha256"],
                         hashlib.sha256((self.run / "model_500.pt").read_bytes()).hexdigest())

    def test_checkpoint_manifest_sha_mismatch_is_ignored(self):
        manifest = json.loads((self.run / "manifest.json").read_text(encoding="utf-8"))
        manifest["checkpoints"]["model_500.pt"] = "0" * 64
        self.write_json(self.run / "manifest.json", manifest)
        self.assertEqual(self.scan()["created"], [])

    def test_incomplete_live_status_is_reported_without_fabricating_failure(self):
        (self.run / "train_start_status.json").unlink()
        result = self.scan()
        self.assertEqual(result["created"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("train_start_status.json", result["errors"][0]["error"])

    def test_duplicate_and_restart_keep_state_in_single_canonical_file(self):
        first = self.scan()
        request = first["created"][0]
        monitor.transition(self.state, request["id"], "claimed", "review started")
        second = self.scan(now=1792789300)
        self.assertEqual(second["created"], [])
        self.assertEqual(second["unresolved"][0]["state"], "claimed")
        reloaded = monitor.load_state(self.state)
        self.assertEqual(reloaded["requests"][request["id"]]["state"], "claimed")

    def test_deadline_stops_new_requests_but_retains_failed_unfinished(self):
        request = self.scan()["created"][0]
        monitor.transition(self.state, request["id"], "failed", "review unavailable")
        self.add_checkpoints((1000,))
        result = self.scan(now=1792875601, deadline=1792875600)
        self.assertEqual(result["created"], [])
        self.assertEqual([r["state"] for r in result["unresolved"]], ["failed"])

    def test_completed_requires_verified_receipt_and_matching_checkpoint(self):
        request = self.scan()["created"][0]
        with self.assertRaises(ValueError):
            monitor.transition(self.state, request["id"], "completed")
        monitor.transition(self.state, request["id"], "claimed")
        with self.assertRaises(ValueError):
            monitor.transition(self.state, request["id"], "completed",
                               receipt_path=self.root / "absent.done", seq_video=self.seq_video)

        files = {}
        for name in ("clip.mp4", "clip.json", "clip_feet.npz"):
            target = self.root / name
            target.write_bytes(name.encode())
            files[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        receipt_path = self.root / "clip.done"
        self.write_json(receipt_path, {"files": files, "checkpoint_sha256": "f" * 64})
        with self.assertRaises(ValueError):
            monitor.transition(self.state, request["id"], "completed",
                               receipt_path=receipt_path, seq_video=self.seq_video)
        self.write_json(receipt_path, {
            "files": files,
            "checkpoint_sha256": request["checkpoint_sha256"],
        })
        completed = monitor.transition(self.state, request["id"], "completed",
                                        receipt_path=receipt_path, seq_video=self.seq_video)
        self.assertEqual(completed["state"], "completed")
        self.assertEqual(completed["completion_evidence"]["verifier_returncode"], 0)
        self.assertEqual(completed["completion_evidence"]["file_sha256"], files)


if __name__ == "__main__":
    unittest.main()
