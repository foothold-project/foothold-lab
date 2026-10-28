"""Answer-known CPU checks for W28; no GPU and no Kit process is started."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import queue_w28 as q


def spec(name, kind="capture", gpu=1, units=2, ready_file=None):
    value = {"id": name, "kind": kind, "priority": q.PRIORITY[kind], "gpu": gpu,
             "owner": "cpu-test", "authorization_ref": "cpu-only-fixture",
             "output": "cpu-output", "cwd": ".", "argv": [sys.executable, "-c", "pass"],
             "units": [{"id": str(i), "args": [],
                        "verify_argv": [sys.executable, "-c", "pass"]} for i in range(units)]}
    if ready_file is not None:
        value["ready_file"] = str(ready_file)
    return value


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "queue.json"
        self.idle = lambda gpu: (True, "cpu_fixture_idle")
        self.executed = []

    def run_fake(self, job, unit):
        self.executed.append((job["id"], unit["id"]))
        return 0, "cpu-fixture-log"

    def step(self, gpu=1, sources=None):
        return q.one(self.path, gpu, idle=self.idle, sources=sources, executor=self.run_fake)

    def test_priority_rechecks_between_units_and_no_mid_unit_kill(self):
        q.register(self.path, spec("render", units=2))
        self.assertEqual(self.step()[1], "render/0")
        q.register(self.path, spec("judge", kind="judge", units=1))
        self.assertEqual(self.step()[1], "judge/0")
        self.assertEqual(self.step()[1], "render/1")
        self.assertEqual(self.executed, [("render", "0"), ("judge", "0"), ("render", "1")])
        self.assertEqual([j["state"] for j in q.read(self.path)["jobs"]], ["done", "done"])

    def test_ready_file_allows_lower_job_in_gap(self):
        ready = self.root / "checkpoint.ready"
        q.register(self.path, spec("judge", kind="judge", units=1, ready_file=ready))
        q.register(self.path, spec("capture", units=2))
        self.assertEqual(self.step()[1], "capture/0")
        ready.write_text("ready", encoding="utf-8")
        self.assertEqual(self.step()[1], "judge/0")
        self.assertEqual(self.step()[1], "capture/1")

    def test_busy_gpu_and_marker_hold_without_claim(self):
        q.register(self.path, spec("capture", units=1))
        self.idle = lambda gpu: (False, "gpu_busy")
        self.assertEqual(self.step(), ("waiting", "gpu_busy"))
        self.assertIsNone(q.read(self.path)["jobs"][0]["claim"])
        self.idle = lambda gpu: (True, "idle")
        marker = self.root / "PRIORITY_BUSY"
        marker.write_text("bad marker", encoding="utf-8")
        self.assertIn("priority_busy_marker", self.step(sources={"priority_busy": str(marker)})[1])
        self.assertEqual(self.executed, [])

    def test_failure_stops_job_and_later_jobs_continue(self):
        q.register(self.path, spec("bad", units=2))
        q.register(self.path, spec("good", units=1))
        self.assertEqual(q.one(self.path, 1, idle=self.idle,
                               executor=lambda j, u: (7, "failed.log"))[0], "failed")
        self.assertEqual(self.step()[1], "good/0")
        self.assertEqual(q.read(self.path)["jobs"][0]["next_unit"], 0)

    def test_claim_is_durable_and_duplicate_runner_does_not_relaunch(self):
        q.register(self.path, spec("capture", units=1))
        job, reason = q.claim_one(self.path, 1, idle=self.idle)
        self.assertEqual(reason, "claimed")
        self.assertEqual(q.claim_one(self.path, 1, idle=self.idle)[1], "existing_claim_requires_review")
        self.assertEqual(q.finish_unit(self.path, job["id"], "0", 0, "log"), "done")

    def test_duplicate_registration_and_missing_authorization_rejected(self):
        q.register(self.path, spec("capture", units=1))
        with self.assertRaisesRegex(ValueError, "duplicate job"):
            q.register(self.path, spec("capture", units=1))
        bad = spec("bad", units=1)
        bad["authorization_ref"] = ""
        with self.assertRaisesRegex(ValueError, "authorization_ref"):
            q.register(self.path, bad)

    def test_cpu_composition_is_separate_lane(self):
        q.register(self.path, spec("compose", kind="compose", gpu=None, units=1))
        self.assertEqual(self.step(gpu=None)[1], "compose/0")
        self.assertIn("CPU 합성", q.screen(q.read(self.path)))

    def test_real_cpu_command_one_unit(self):
        output = self.root / "out"
        target = self.root / "done.txt"
        job = spec("real-cpu", kind="compose", gpu=None, units=1)
        job.update({"output": str(output), "cwd": str(self.root),
                    "argv": [sys.executable, "-c", f"from pathlib import Path; Path(r'{target}').write_text('ok')"]})
        q.register(self.path, job)
        self.assertEqual(q.one(self.path, None)[0], "done")
        self.assertEqual(target.read_text(), "ok")


if __name__ == "__main__":
    unittest.main()
