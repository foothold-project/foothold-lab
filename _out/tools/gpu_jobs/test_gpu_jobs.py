"""Known-input CPU checks for the GPU job board."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gpu_jobs as board


def job(name, priority, gpu, state="대기", executable=True):
    return {"id": name, "priority": priority, "gpu": gpu,
            "command": f"fake command {name}", "owner_session": "CPU test",
            "preemptible": priority >= 2, "state": state,
            "started_at": None, "ended_at": None, "output_path": "temp",
            "executable": executable}


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.marker = self.root / "PRIORITY_BUSY"
        self.chain = self.root / "chain.log"
        self.render = self.root / "render.json"
        self.config = {"sources": {"priority_busy": str(self.marker),
                                   "chain_log": str(self.chain), "render_state": str(self.render)},
                       "jobs": [job("train", 0, 0, "실행"),
                                job("judge", 1, 1, "실행"),
                                job("seed43", 3, 1), job("render", 4, 1)]}
        self.chain.write_text("2026-10-27 02:00:00 m1750 core start\n", encoding="utf-8")
        self.render.write_text('{"state":"waiting","current_job":"capture-1","pending":["capture-1"]}', encoding="utf-8")
        self.marker.write_text(json.dumps({"watcher_pid": os.getpid()}), encoding="utf-8")

    def live(self):
        return board.live_sources(self.config)

    def test_p1_active_blocks_p3_and_p4(self):
        live = self.live()
        self.assertTrue(live["marker"]["present"])
        self.assertEqual(board.admission(self.config, "seed43", live), (False, "higher_active:judge"))
        self.assertEqual(board.admission(self.config, "render", live), (False, "higher_active:judge"))

    def test_p1_checkpoint_wait_allows_p3_before_p4(self):
        self.marker.unlink()
        self.chain.write_text("2026-10-27 02:01:00 새 저장본 대기\n", encoding="utf-8")
        live = self.live()
        self.assertEqual(board.admission(self.config, "seed43", live), (True, "eligible_next_unit"))
        self.assertEqual(board.admission(self.config, "render", live), (False, "higher_waiting:seed43"))

    def test_unarmed_p3_does_not_starve_p4_in_checkpoint_gap(self):
        self.config["jobs"][2]["executable"] = False
        self.marker.unlink()
        self.chain.write_text("다음 저장본 대기\n", encoding="utf-8")
        self.assertEqual(board.admission(self.config, "render", self.live()),
                         (True, "eligible_next_unit"))
        self.marker.write_text(json.dumps({"watcher_pid": os.getpid()}), encoding="utf-8")
        self.assertFalse(board.admission(self.config, "render", self.live())[0])

    def test_running_render_finishes_one_item_then_yields(self):
        self.marker.unlink()
        self.chain.write_text("새 저장본 대기\n", encoding="utf-8")
        self.render.write_text('{"state":"running","current_job":"capture-1"}', encoding="utf-8")
        self.assertEqual(board.admission(self.config, "seed43", self.live()),
                         (False, "finish_current_render_item_then_yield"))
        self.render.write_text('{"state":"waiting","current_job":"capture-2"}', encoding="utf-8")
        self.assertTrue(board.admission(self.config, "seed43", self.live())[0])

    def test_p1_returns_before_next_p3_item(self):
        self.marker.unlink()
        self.chain.write_text("다음 체크포인트 대기\n", encoding="utf-8")
        self.assertTrue(board.admission(self.config, "seed43", self.live())[0])
        self.marker.write_text(json.dumps({"watcher_pid": os.getpid()}), encoding="utf-8")
        self.chain.write_text("2026-10-27 02:02:00 m1800 core start\n", encoding="utf-8")
        self.assertFalse(board.admission(self.config, "seed43", self.live())[0])

    def test_unarmed_seed_and_bad_marker_fail_closed(self):
        self.config["jobs"][2]["executable"] = False
        self.assertEqual(board.admission(self.config, "seed43", self.live()), (False, "unarmed_command"))
        self.marker.write_text("not json", encoding="utf-8")
        self.assertTrue(self.live()["marker"]["present"])

    def test_stale_pid_does_not_count_and_identity_is_pinned(self):
        self.marker.write_text('{"watcher_pid":2147483647}', encoding="utf-8")
        self.assertEqual(self.live()["marker"]["reason"], "stale_pids")
        self.assertEqual(board.pid_state({"pid": os.getpid(), "pid_create_time": 1}), "pid_reused")

    def test_status_shows_both_gpus_and_next_job(self):
        output = board.status(self.config, self.live())
        for token in ("GPU0", "GPU1", "P0 train", "P1 judge", "P3 seed43", "P4 render", "current=capture-1"):
            self.assertIn(token, output)


if __name__ == "__main__":
    unittest.main()
