"""CPU regressions for cross-GPU ranks and read-only external job tracking."""

from argparse import Namespace
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess
import tempfile
import unittest
from unittest.mock import patch

import dispatch as board


class GpuAttributionTests(unittest.TestCase):
    def test_shared_cuda0_hint_does_not_hide_rank1_on_gpu1(self):
        def fake_smi(argv, **_):
            if argv[1].startswith("--query-gpu="):
                out = "0, GPU-a, 89, 13400, 16000, RTX\n1, GPU-b, 89, 13400, 16000, RTX\n"
            else:
                self.assertIn("used_memory", argv[1])
                out = ("572549, GPU-a, 12479\n572549, GPU-b, 262\n"
                       "572551, GPU-a, 262\n572551, GPU-b, 12455\n")
            return CompletedProcess(argv, 0, out, "")

        with patch("subprocess.run", side_effect=fake_smi):
            smi = board.nvidia_smi()
        jobs = board.live_jobs(smi, [{"pid": pid, "cmdline": "python train.py --device cuda:0", "started": 1}
                                      for pid in (572549, 572551)])
        self.assertEqual([[j["pid"] for j in jobs if board.on_gpu(j, gpu)] for gpu in (0, 1)],
                         [[572549], [572551]])
        self.assertEqual(jobs[1]["gpus"], [0, 1])
        self.assertEqual(smi["apps"][572551], {0: 262, 1: 12455})
        with patch.dict(board.DISPATCH, gpu=1, p1_attempt_globs=[]):
            self.assertIn("572551", board.p1_busy(jobs, {572549}, []))


class ExternalJobTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.queue = self.root / "queue.json"
        self.cfg = {**board.LIVE, "queue": str(self.queue)}
        self.now = datetime(2026, 11, 11, 1, 48).timestamp()
        self.args = Namespace(qaction="external", title="EX-42 rank test", gpu=[0, 1], priority=0,
                              start="01:40", end="04:00", owner="lead", pid=123,
                              log=str(self.root / "training.log"))

    def test_cli_records_only_existing_pid_and_duplicate_is_rejected(self):
        with patch.object(board, "external_process", return_value=("running", self.now - 600)), \
             patch.object(board, "require_linux_profile"), \
             patch.object(board, "queue_cmd", side_effect=lambda args, cfg: board._queue_cmd(args, cfg, self.now)):
            rc = board.main(["queue", "external", "--queue", str(self.queue), "--title", self.args.title,
                             "--gpu", "0", "--gpu", "1", "--priority", "0", "--pid", "123",
                             "--start", "01:40", "--end", "04:00", "--log", self.args.log])
            self.assertEqual(rc, 0)
        with patch.object(board, "external_process", return_value=("running", self.now - 600)):
            with self.assertRaisesRegex(ValueError, "already registered"):
                board.queue_cmd(self.args, self.cfg, self.now)
        items = board.read_queue(self.queue)["items"]
        self.assertEqual([(x["gpu"], x["state"], x["pid"], x["log"]) for x in items],
                         [(0, "실행", 123, self.args.log), (1, "실행", 123, self.args.log)])
        self.assertTrue(all(x["external"] and "argv" not in x and x["priority"] == 0 for x in items))

    def test_external_exit_or_reused_pid_is_done_without_assuming_success(self):
        for outcome in (("exited", None), ("running", 200)):
            item = {"id": 7, "state": "실행", "external": True, "pid": 123, "pid_started": 100}
            with patch.object(board, "external_process", return_value=outcome), \
                 patch.object(board, "result_path", side_effect=AssertionError("not a dispatcher wrapper")):
                self.assertTrue(board.settle(item, now=self.now))
            self.assertEqual((item["state"], item["done_at"], item["rc"]), ("끝", self.now, None))
        item = {"id": 7, "state": "실행", "external": True, "pid": 123, "pid_started": 100}
        with patch.object(board, "external_process", return_value=("unknown", None)):
            self.assertFalse(board.settle(item, now=self.now))
        self.assertEqual(item["state"], "실행")

    def test_board_marks_exit_even_without_dispatcher_and_does_not_write_queue(self):
        with patch.object(board, "external_process", return_value=("running", self.now - 600)):
            board.queue_cmd(self.args, self.cfg, self.now)
        before = self.queue.read_bytes()
        with patch.object(board, "external_process", return_value=("exited", None)), \
             patch.object(board, "current_training", return_value=None), \
             patch.object(board, "eval_attempts", return_value=[]), \
             patch.object(board, "stage_rows", return_value=[]), \
             patch.object(board, "watcher_pending", return_value=None), \
             patch.object(board, "c_layer_files", return_value=([], [])):
            snapshot = board.slow_data(self.cfg, procs=[])
        self.assertEqual([item["state"] for item in snapshot["queue"]], ["끝", "끝"])
        self.assertEqual(self.queue.read_bytes(), before)
