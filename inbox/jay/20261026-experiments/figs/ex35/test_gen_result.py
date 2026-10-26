"""Known-input CPU checks for the EX-35 result generator."""

import json
import hashlib
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
        self.evidence = {name: self.root / name for name in ("window_default", "window", "a11", "remeasure_log", "chain_map", "remeasure_map", "cmp_video", "repro_compare", "repro_a1", "repro_a2", "repro_b")}
        window = {"branch": "STOP", "decision": {"row": 4, "action": "A11 판독 파일 없음"}, "a11": {"state": "unfilled"}, "missing_inputs": {"latest": [], "prev": []}, "states": {"latest": {"state": "MAINTAIN_FAIL"}, "prev": {"state": "MAINTAIN_FAIL"}}}
        self.evidence["window_default"].write_text(json.dumps(window), encoding="utf-8")
        window["decision"] = {"row": 6, "action": "REVERT: 유지 실패 연속 두 저장본"}
        window["a11"] = {"state": "clear", "yes": []}
        self.evidence["window"].write_text(json.dumps(window), encoding="utf-8")
        lines = []
        for iteration in (2000, 1950, 1900, 1850, 1800):
            for stage in ("map64", "map64_eval_pred", "L6", "L9"):
                lines.extend((f"2026-10-27 05:00:00 start /tmp/m{iteration}/{stage}/", f"2026-10-27 05:00:01 end ok /tmp/m{iteration}/{stage}/ rc=0"))
        self.evidence["remeasure_log"].write_text("\n".join(lines), encoding="utf-8")
        old = {"modes": {f"k{i}": float(i) for i in range(74)}, "source_sha256": {"foothold_s2.eval.eval_map_modes": "old"}}
        new = {"modes": {f"k{i}": float(i + (1 if i < 28 else 0)) for i in range(74)}, "source_sha256": {"foothold_s2.eval.eval_map_modes": "new"}}
        self.evidence["chain_map"].write_text(json.dumps(old), encoding="utf-8")
        self.evidence["remeasure_map"].write_text(json.dumps(new), encoding="utf-8")
        video_bytes = b"known cmp bytes"
        self.evidence["cmp_video"].write_bytes(video_bytes)
        a11 = {"reader": "lead", "time": "2026-10-27 05:19 KST", "checkpoint_sha256": "a" * 64, "cmp_video": {"sha256": hashlib.sha256(video_bytes).hexdigest()}, "items": {str(i): "없음" for i in range(1, 6)}, "memo": ["m1500 왼쪽, m2000 오른쪽으로 휨"]}
        self.evidence["a11"].write_text(json.dumps(a11), encoding="utf-8")
        self.evidence["repro_compare"].write_text("A1 대 A2: 다른 수치 27 / 56", encoding="utf-8")
        for name in ("a1", "a2", "b"):
            values = {f"k{i}": float(i + (1 if name == "a2" and i < 27 else 2 if name == "b" and i < 29 else 0)) for i in range(56)}
            doc = {"modes": values, "checkpoint_sha256": "a" * 64, "eval_seed": 42, "source_sha256": {"foothold_s2.eval.eval_map_modes": "same"}, "run_identity": {"device": "cuda:1" if name == "b" else "cuda:0"}}
            self.evidence[f"repro_{name}"].write_text(json.dumps(doc), encoding="utf-8")

    def collect(self):
        return collect(self.eval_dir, self.train_dir, self.baseline, self.evidence)

    def test_known_result_is_deterministic(self):
        data = self.collect()
        self.assertEqual(data["window_decision"], "STOP")
        self.assertEqual(data["window_default_row"], 4)
        self.assertEqual(data["window_row"], 6)
        self.assertEqual(data["window_evidence"]["map64_numeric_changed"], 28)
        self.assertEqual(data["window_evidence"]["repro_a1_a2_changed"], 27)
        self.assertEqual(render(data), render(self.collect()))
        self.assertIn("**STOP 6행**", render(data))

    def test_mutated_final_state_is_rejected(self):
        path = self.eval_dir / "m2000/ex35_verdict.json"
        doc = json.loads(path.read_text())
        doc["state"] = "PASS"
        path.write_text(json.dumps(doc))
        with self.assertRaises(AssertionError):
            self.collect()

    def test_missing_completion_is_rejected(self):
        (self.train_dir / "run.log").write_text("Learning iteration 1999/2001\nTime elapsed: 03:22:27")
        with self.assertRaises(AssertionError):
            self.collect()

    def test_window_row_mutation_is_rejected(self):
        path = self.evidence["window"]
        doc = json.loads(path.read_text())
        doc["decision"]["row"] = 4
        path.write_text(json.dumps(doc))
        with self.assertRaises(AssertionError):
            self.collect()

    def test_map_mismatch_count_mutation_is_rejected(self):
        path = self.evidence["remeasure_map"]
        doc = json.loads(path.read_text())
        doc["modes"]["k28"] += 1
        path.write_text(json.dumps(doc))
        with self.assertRaises(AssertionError):
            self.collect()

    def test_a11_missing_item_is_rejected(self):
        path = self.evidence["a11"]
        doc = json.loads(path.read_text())
        doc["items"]["5"] = "있음"
        path.write_text(json.dumps(doc))
        with self.assertRaises(AssertionError):
            self.collect()

    def test_repro_repeat_mutation_is_rejected(self):
        path = self.evidence["repro_a2"]
        doc = json.loads(path.read_text())
        doc["modes"]["k27"] += 1
        path.write_text(json.dumps(doc))
        with self.assertRaises(AssertionError):
            self.collect()


if __name__ == "__main__":
    unittest.main()
