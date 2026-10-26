"""Known-input CPU checks for the EX-35 result generator."""

import json
import tempfile
import unittest
from pathlib import Path

from gen_result import collect, render


class ResultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.eval_dir = self.root / "eval"
        self.train_dir = self.root / "train"
        self.baseline = self.root / "baseline.json"
        self.train_dir.mkdir()
        self.baseline.write_text(json.dumps({"turn": {f"S-B10|eval_gt|{name}": {"Q": 0.4} for name in ("fwd_then_left", "right_then_left", "indep_left")}}), encoding="utf-8")
        names = ("fwd_then_left", "right_then_left", "indep_left", *(f"case_{i}" for i in range(5)))
        cases = {name: {"Q": 0.5, "C": 0.2, "kept": 16} for name in names}
        for name, state in (("m1750", "NEW_TASK_PENDING"), ("m1950", "MAINTAIN_FAIL"), ("m2000", "MAINTAIN_FAIL")):
            folder = self.eval_dir / name
            folder.mkdir(parents=True)
            doc = {"state": state, "mode": "eval_gt", "reasons": [{"case": "case", "cond": "drop_Q", "limit": 0.6, "value": 0.5}], "detail": {"it_in_stage": int(name[1:]) - 1500, "min_stay": 500, "cases": dict(cases)}}
            (folder / "ex35_verdict.json").write_text(json.dumps(doc), encoding="utf-8")
        receipt = {"validate_launch": "ok", "parent_sha256": "a" * 64, "expected_parent_sha256": "a" * 64, "parent_iter": 1500, "first_iter": 1501, "last_iter": 2000, "remaining_updates": 500, "args": {"device": "cuda:0", "num_envs": "3072", "seed": "42", "max_iterations": "2001"}}
        (self.train_dir / "launch_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        (self.train_dir / "run.log").write_text("Learning iteration 2000/2001\nTime elapsed: 03:22:27\nTRAIN_START_STATUS done", encoding="utf-8")
        (self.train_dir / "rc.txt").write_text("rc=0", encoding="utf-8")

    def test_known_result_is_deterministic(self):
        data = collect(self.eval_dir, self.train_dir, self.baseline)
        self.assertEqual(data["window_decision"], "HOLD")
        self.assertEqual(data["checkpoint_pair_row6"], "REVERT")
        self.assertEqual(render(data), render(collect(self.eval_dir, self.train_dir, self.baseline)))
        self.assertIn("창 판정은 **HOLD", render(data))

    def test_mutated_final_state_is_rejected(self):
        path = self.eval_dir / "m2000/ex35_verdict.json"
        doc = json.loads(path.read_text())
        doc["state"] = "PASS"
        path.write_text(json.dumps(doc))
        with self.assertRaises(AssertionError):
            collect(self.eval_dir, self.train_dir, self.baseline)

    def test_missing_completion_is_rejected(self):
        (self.train_dir / "run.log").write_text("Learning iteration 1999/2001\nTime elapsed: 03:22:27")
        with self.assertRaises(AssertionError):
            collect(self.eval_dir, self.train_dir, self.baseline)


if __name__ == "__main__":
    unittest.main()
