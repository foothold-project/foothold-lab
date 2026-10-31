"""Known-input CPU checks for the separate EX-40 progress consumer."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np

from foothold_s2 import ex40_checkpoint_reporter as reporter


SOURCE = Path("C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313")


class CheckpointReporterTest(unittest.TestCase):
    def test_real_three_checkpoint_rows_match_raw(self):
        if not SOURCE.is_dir():
            self.skipTest("EX-40 read-only source absent")
        ledger = reporter.ledger_rows(SOURCE / "score-watch" / "score_ledger.jsonl")
        selected = [entry for entry in ledger if entry["checkpoint_iteration"] in (500, 750, 1000)]
        self.assertEqual([entry["checkpoint_iteration"] for entry in selected], [500, 750, 1000])
        previous = None
        for entry in selected:
            score = reporter.pinned_score(entry)
            row = reporter.build_row(entry, score, previous, 8000)
            self.assertEqual(row["verdict"], score["verdict"])
            self.assertEqual(row["cells"]["eval_gt/fwd0.5"]["alive"],
                             score["cells"]["eval_gt/fwd0.5"]["alive_envs_at_end"])
            self.assertEqual(row["stand_passed"]["eval_gt"],
                             score["cells"]["eval_gt/flat_stand"]["passed_envs"])
            npz = Path(score["sources"]["map64"]).parent / "env_arrays_eval_pred_fwd0.5.npz"
            with np.load(npz, allow_pickle=False) as raw:
                mask = np.isfinite(raw["map_err_inrange_mean_cm"]) & (raw["map_err_inrange_steps"] > 0)
                direct = raw["map_err_inrange_mean_cm"][mask].mean()
                self.assertAlmostEqual(
                    row["map_error"]["eval_pred/fwd0.5"]["mean_of_env_means_cm"],
                    float(direct), places=6)
                self.assertEqual(row["map_error"]["eval_pred/fwd0.5"]["env_count"], int(mask.sum()))
            force_path = Path(score["sources"]["stand_eval_gt"]).parent / "stand_raw.npz"
            with np.load(force_path, allow_pickle=False) as raw:
                alive = raw["alive"][50:]
                four = ((raw["force_z"][50:] > 1).all(axis=2) & alive).sum(axis=0)
                direct_count = int(((alive.sum(axis=0) > 0) &
                                    (four >= .9 * alive.sum(axis=0))).sum())
            self.assertEqual(row["stand"]["eval_gt"]["all_four_90pct_envs"], direct_count)
            self.assertIn(f"m{entry['checkpoint_iteration']}", reporter.markdown(row))
            previous = row

    def test_duplicate_ledger_and_missing_score_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            row = {"format": "foothold-ex40-score-ledger/1", "checkpoint_iteration": 500}
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                reporter.ledger_rows(path)
            row.update(score_path=str(Path(tmp) / "missing.json"), score_sha256="0" * 64,
                       checkpoint_path=str(Path(tmp) / "model.pt"), checkpoint_sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "score file absent"):
                reporter.pinned_score(row)

    def test_video_receipt_requires_full_decode_and_identity(self):
        import cv2

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            video = base / "cmp.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 32))
            self.assertTrue(writer.isOpened())
            for _ in range(3):
                writer.write(np.full((32, 32, 3), 60, dtype=np.uint8))
            writer.release()
            row = {"update": 1500, "checkpoint_sha256": "a" * 64}
            receipt = {"format": "foothold-ex40-cmp/1", "checkpoint_sha256": "a" * 64,
                       "gpu_index": 1, "status": "PASS", "frame_count": 3,
                       "decoded_frames": 2, "mp4": str(video), "mp4_sha256": reporter.sha256(video)}
            path = base / "m1500.cmp.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frame readback"):
                reporter._video_receipt(base, row)
            receipt["decoded_frames"] = 3
            path.write_text(json.dumps(receipt), encoding="utf-8")
            request = {"previous_stage_sha256": "b" * 64}
            with self.assertRaisesRegex(ValueError, "identity"):
                reporter._video_receipt(base, row, request)
            receipt["previous_stage_sha256"] = "b" * 64
            path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertEqual(reporter._video_receipt(base, row, request), str(video))
            receipt["frame_count"] = receipt["decoded_frames"] = 4
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "decoded file frame count"):
                reporter._video_receipt(base, row, request)
            receipt["frame_count"] = receipt["decoded_frames"] = 3
            receipt["gpu_index"] = 0
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identity"):
                reporter._video_receipt(base, row)

    def test_ambiguous_delivery_is_not_sent_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            receipt = base / "m500.report.json"
            old = {"state": "delivery_uncertain", "checkpoint_sha256": "a" * 64,
                   "update": 500, "doc": "already-published"}
            reporter._write_json(receipt, old)
            sent = []
            result = reporter.publish({"update": 500, "checkpoint_sha256": "a" * 64},
                                      base / "unused", base, base / "sender",
                                      sender=lambda *_: sent.append(1))
            self.assertEqual(result, old)
            self.assertEqual(sent, [])
            old["state"] = "delivery_pending"
            reporter._write_json(receipt, old)
            self.assertEqual(reporter.publish({"update": 500, "checkpoint_sha256": "a" * 64},
                                              base / "unused", base, base / "sender",
                                              sender=lambda *_: sent.append(1)), old)
            self.assertEqual(sent, [])

    def test_cmp_request_marks_missing_first_comparator(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = {"update": 1500, "checkpoint_sha256": "a" * 64,
                   "sources": {"run": str(Path(tmp) / "run")}}
            ledger = [{"checkpoint_iteration": 1500, "checkpoint_path": "model_1500.pt",
                       "checkpoint_sha256": "a" * 64}]
            path = reporter._cmp_request(Path(tmp), row, ledger)
            request = reporter._read_json(path)
            self.assertIsNone(request["previous_stage_checkpoint"])
            self.assertEqual(request["gpu_index"], 1)
            self.assertEqual(reporter._cmp_request(Path(tmp), row, ledger), path)

    def test_publish_local_bare_remote_and_no_duplicate(self):
        if not SOURCE.is_dir():
            self.skipTest("EX-40 read-only source absent")
        entry = next(entry for entry in reporter.ledger_rows(SOURCE / "score-watch" / "score_ledger.jsonl")
                     if entry["checkpoint_iteration"] == 500)
        row = reporter.build_row(entry, reporter.pinned_score(entry), None, 8000)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bare, repo = base / "remote.git", base / "docs"
            subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", reporter.BRANCH, str(repo)], check=True, capture_output=True)
            for args in (("config", "user.email", "cpu@example.invalid"),
                         ("config", "user.name", "CPU Fixture"),
                         ("remote", "add", "origin", str(bare))):
                subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
            (repo / "readme.txt").write_text("fixture", encoding="utf-8")
            for args in (("add", "readme.txt"), ("commit", "-m", "fixture"),
                         ("push", "origin", f"HEAD:{reporter.BRANCH}")):
                subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
            sent = []
            sender = lambda _sender, path: sent.append(path.read_text(encoding="utf-8")) or True
            state = base / "state"
            first = reporter.publish(row, repo, state, base / "unused_sender.py", sender=sender)
            second = reporter.publish(row, repo, state, base / "unused_sender.py", sender=sender)
            self.assertEqual(first["state"], "sent")
            self.assertEqual(first, second)
            self.assertEqual(len(sent), 1)
            self.assertTrue((repo / reporter.STAGE_DIR / "PROGRESS-EX40-B0-m500.md").exists())
            self.assertTrue(subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                                           capture_output=True, text=True, check=True).stdout == "")

    def test_stage_chart_reads_pinned_training_and_evaluation_rows(self):
        if not SOURCE.is_dir():
            self.skipTest("EX-40 read-only source absent")
        entry = next(entry for entry in reporter.ledger_rows(SOURCE / "score-watch" / "score_ledger.jsonl")
                     if entry["checkpoint_iteration"] == 1000)
        row = reporter.build_row(entry, reporter.pinned_score(entry), None, 8000)
        row["training"] = reporter._training(Path(entry["run_dir"]), 1000, 8000,
                                              include_curves=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reporter._write_json(root / "m1000.row.json", row)
            self.assertEqual(reporter._read_json(root / "m1000.row.json"), row)
            charts = reporter._stage_charts(root, row, root, "known")
            self.assertEqual(len(charts), 4)
            self.assertTrue(all(path.stat().st_size > 1000 for path in charts))

    def test_retro_dry_run_repeated_keeps_prior_delta(self):
        if not SOURCE.is_dir():
            self.skipTest("EX-40 read-only source absent")
        first_two = reporter.ledger_rows(SOURCE / "score-watch" / "score_ledger.jsonl")[:2]
        self.assertEqual([row["checkpoint_iteration"] for row in first_two], [500, 750])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "ledger.jsonl"
            ledger.write_text("".join(json.dumps(row) + "\n" for row in first_two),
                              encoding="utf-8")
            state = root / "state"
            args = (ledger, root, state, root / "sender", 8000)
            self.assertEqual(len(reporter.run_once(*args, dry_run=True)), 2)
            pinned = reporter._read_json(state / "m750.row.json")
            self.assertEqual(len(reporter.run_once(*args, dry_run=True)), 2)
            self.assertEqual(pinned, reporter._read_json(state / "m750.row.json"))

    def test_bad_score_row_holds_without_blocking_later_checkpoint(self):
        if not SOURCE.is_dir():
            self.skipTest("EX-40 read-only source absent")
        entries = reporter.ledger_rows(SOURCE / "score-watch" / "score_ledger.jsonl")[:2]
        self.assertEqual([row["checkpoint_iteration"] for row in entries], [500, 750])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries[0] = dict(entries[0], score_path=str(root / "missing.json"))
            ledger = root / "ledger.jsonl"
            ledger.write_text("".join(json.dumps(row) + "\n" for row in entries),
                              encoding="utf-8")
            state = root / "state"
            results = reporter.run_once(ledger, root, state, root / "sender", 8000,
                                        dry_run=True)
            self.assertEqual([row["state"] for row in results], ["HOLD", "dry_run"])
            self.assertTrue((state / "m500.error.json").exists())
            self.assertTrue((state / "dry-run" / "PROGRESS-EX40-B0-m750.md").exists())


if __name__ == "__main__":
    unittest.main()
