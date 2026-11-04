"""Known-input CPU checks for the GPU job board."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dispatch as board


@unittest.skipUnless(os.name == "nt", "Windows rename semantics")
class SharedReadTests(unittest.TestCase):
    """11/04 01:13 EX-41 died on os.replace PermissionError while a reader held the status file."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "train_start_status.json"
        self.target.write_text('{"iter": 1}', encoding="utf-8")

    def replace_with(self, text):
        tmp = self.target.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.target)

    def test_control_a_plain_open_reader_blocks_os_replace(self):
        with open(self.target, "rb"):
            with self.assertRaises(PermissionError):
                self.replace_with('{"iter": 2}')

    def test_windows_limit_even_a_share_delete_handle_blocks_replace_while_open(self):
        # Measured 11/04: MoveFileEx(REPLACE_EXISTING) is denied while ANY handle is open on the
        # target, FILE_SHARE_DELETE included. So the reader can only keep the window tiny; the
        # writer must retry (recommended for train_start.py).
        with board.open_shared(self.target) as fh:
            self.assertEqual(fh.read(), b'{"iter": 1}')
            with self.assertRaises(PermissionError):
                self.replace_with('{"iter": 2}')

    def test_read_shared_closes_before_returning_so_replace_right_after_works(self):
        self.assertEqual(board.read_json(self.target), {"iter": 1})
        self.replace_with('{"iter": 2}')
        self.assertEqual(board.read_json(self.target), {"iter": 2})

    def test_missing_file_is_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            board.read_shared_bytes(Path(self.temp.name) / "nope.json")

    def test_many_reads_during_replaces(self):
        for k in range(200):
            self.replace_with(json.dumps({"iter": k}))
            self.assertEqual(board.read_json(self.target)["iter"], k)


class CLayerCellTimeTests(unittest.TestCase):
    def test_hold_gaps_are_excluded_and_exhausted_counts_every_attempt(self):
        from datetime import datetime
        t0 = datetime(2026, 11, 3, 21, 0).timestamp()

        def row(cell, state, start_min, run_s, hold=False):
            start = t0 + start_min * 60
            return {"cell": cell, "at": start + run_s, "state": "ex41_slowdown_hold" if hold else state,
                    "before": {"time": datetime.fromtimestamp(start).isoformat(timespec="seconds")},
                    "queue_event": {"cell": cell, "state": state}}
        rows = [row("A", "complete", 0, 300),
                row("B", "pending", 6, 400, hold=True),     # then a 90-minute hold
                row("B", "exhausted", 100, 500),           # resumed: only its 500 s run counts
                {"cell": "B", "at": t0 + 9000, "state": "training_status_hold",
                 "before": {"time": datetime.fromtimestamp(t0 + 6000).isoformat()},
                 "queue_event": {"state": "only_cell_closed"}},  # a status check, not an attempt
                row("C", "pending", 110, 200)]             # not closed yet: not averaged
        self.assertAlmostEqual(board.c_layer_cell_seconds(rows), (300 + 400 + 500) / 2)
        many = [row(f"K{k}", "complete", 200 + k * 10, 60 * (k + 1)) for k in range(12)]
        self.assertAlmostEqual(board.c_layer_cell_seconds(many), sum(60 * (k + 1) for k in range(2, 12)) / 10)
        self.assertIsNone(board.c_layer_cell_seconds([]))


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


class LiveTests(unittest.TestCase):
    """Fake nvidia-smi and process lists shaped like the 11/03 machine."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "gpu").mkdir()
        (root / "gpu" / "TRAINING_BUSY_GPU0").write_text("{}", encoding="utf-8")
        (root / "gpu" / "idle_since.json").write_text("{}", encoding="utf-8")
        self.status_file = root / "train_start_status.json"
        self.status_file.write_text(json.dumps({"state": "running", "iter": 210, "tot_iter": 6500,
                                                "iter_s": 27.0}), encoding="utf-8")
        ledger = root / "q" / "loop.jsonl"
        ledger.parent.mkdir()
        ledger.write_text('{"at": 1793708753.9, "cell": "L4_gt", "queue_event": {"state": "pending", "attempts": 2}}\n',
                          encoding="utf-8")
        (root / "TRAINING_BUSY_GPU0").write_text(json.dumps({"pid": os.getpid(), "run": str(root)}),
                                                 encoding="utf-8")
        self.cfg = {"markers": [str(root / "gpu")], "ledgers": [str(ledger)],
                    "train_marker": str(root / "TRAINING_BUSY_GPU0"), "boundary": 250,
                    "idle_state": str(root / "idle.json"), "idle_util": 10}
        # Training shows on both GPUs (graphics context on the display GPU) but says cuda:0.
        self.smi = {"gpus": {0: {"util": 80, "mib": 12315}, 1: {"util": 2, "mib": 3000}},
                    "apps": {84424: {0, 1}, 5000: {1}}}
        self.procs = [
            {"pid": 84424, "started": 1793703275.0, "cmdline":
             "python.exe foothold_s2/scripts/train_start.py --headless --device=cuda:0"},
            {"pid": 74628, "started": 1793703563.0, "cmdline": "python.exe -m foothold_s2.ex41_score_watch --run-dir x"},
            {"pid": 77916, "started": 1793708000.0, "cmdline": "pythonw.exe D:/mai-tmp/lead/ex41_mirror_guard.py a b c"},
            {"pid": 9, "started": 1793700000.0, "cmdline": "python.exe some_other_tool.py"},
        ]

    def test_training_counts_on_its_cuda_device_only_and_gpu1_is_idle(self):
        out = board.live_status(self.smi, self.procs, self.cfg, now=1793710000.0)
        gpu0, rest = out.split("GPU1 ·")
        gpu1 = rest.split("감시")[0]
        self.assertIn("training · PID 84424", gpu0)
        self.assertNotIn("84424", gpu1)
        self.assertIn("쉼", gpu1)
        self.assertIn("사용 중", gpu0)
        self.assertIn("PID 74628 foothold_s2.ex41_score_watch", out)
        self.assertIn("PID 77916 ex41_mirror_guard.py", out)
        self.assertNotIn("some_other_tool", out)
        self.assertIn("210/6500", out)
        self.assertIn("다음 250 경계 250 회", out)
        self.assertIn("TRAINING_BUSY_GPU0", out)
        self.assertNotIn("idle_since", out)
        self.assertIn("L4_gt pending 시도 2", out)

    def test_idle_since_is_kept_until_busy_then_cleared(self):
        board.live_status(self.smi, self.procs, self.cfg, now=1000.0)
        board.live_status(self.smi, self.procs, self.cfg, now=2000.0)
        state = json.loads(Path(self.cfg["idle_state"]).read_text(encoding="utf-8"))
        self.assertEqual(state, {"0": None, "1": 1000.0})
        self.procs.append({"pid": 5000, "started": 1500.0, "cmdline": "python.exe c76_vis_loop.py 1"})
        board.live_status(self.smi, self.procs, self.cfg, now=3000.0)
        state = json.loads(Path(self.cfg["idle_state"]).read_text(encoding="utf-8"))
        self.assertIsNone(state["1"])

    def test_smi_failure_reports_unknown_not_idle(self):
        out = board.live_status({"gpus": {}, "apps": {}}, self.procs, self.cfg, now=1.0)
        self.assertIn("GPU 상태 미확인", out)
        self.assertNotIn("쉼", out)

    def test_missing_status_and_ledger_do_not_crash(self):
        self.status_file.unlink()
        self.cfg["ledgers"] = [self.cfg["ledgers"][0] + ".missing"]
        out = board.live_status(self.smi, self.procs, self.cfg, now=1.0)
        self.assertIn("학습 상태 파일 없음", out)
        self.assertIn("읽지 못함", out)


class BoardViewTests(LiveTests):
    """board: stage names from the real table shape, auto ETAs, queue edits, warnings."""

    def setUp(self):
        super().setUp()
        root = Path(self.temp.name)
        table = root / "table.yaml"
        table.write_text("stages:\n- id: S2a\n  start: {fixed_update: 0}\n- id: S2b\n  start: {fixed_update: 751}\n"
                         "- id: S2c\n  start: {fixed_update: 1751}\n", encoding="utf-8")
        self.cfg.update({"queue": str(root / "queue.json"), "stage_table": str(table), "parent_iter": 6000,
                         "stage_end": [750, 1750, 2750], "eval_root": str(root / "evalroot"),
                         "eval_minutes_assumed": 40, "stage_end_minutes_assumed": 120,
                         "c_layer_total_cells": 81})
        (root / "evalroot").mkdir()
        self.now = 1793710000.0

    def args(self, **kw):
        import argparse
        base = dict(qaction="add", title="t", priority=2, gpu=1, start=None, end=None, owner="lead", cond=None,
                    needs_approval=False,
                    id=None)
        base.update(kw)
        return argparse.Namespace(**base)

    def test_stage_range_and_cumulative_iteration(self):
        out = board.board(self.smi, self.procs, self.cfg, now=self.now)
        self.assertIn("EX-41 학습 · S2a (m6001~m6750)", out)
        self.assertIn("m6210 · 210/2750", out)
        self.status_file.write_text(json.dumps({"state": "running", "iter": 760, "iter_s": 27.0}), encoding="utf-8")
        self.assertIn("S2b (m6751~m7750)", board.board(self.smi, self.procs, self.cfg, now=self.now))

    def test_auto_eval_eta_from_iter_time_and_stage_end_chain(self):
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=160)
        eta250 = datetime_hm(self.now + (300 - 210) * 27.0)  # starts at the 300 save (manifest)
        row = next(l for l in out.splitlines() if "EX-41 250 경계 평가" in l)
        self.assertRegex(row, r"^\s+\d 대기\s+GPU1 P1\s+" + eta250)
        self.assertIn("EX-41 750 단계 끝 사슬", out)
        self.assertIn("가정 40 분", out)

    def test_measured_eval_length_replaces_assumption_and_running_eval_shows(self):
        d = Path(self.cfg["eval_root"]) / "model_250_abc"
        d.mkdir()
        (d / "attempt.json").write_text('{"state":"done","iteration":250}', encoding="utf-8")
        os.utime(d / "attempt.json", (self.now - 3000, self.now - 3000))
        (d / "score.json").write_text("{}", encoding="utf-8")
        e = Path(self.cfg["eval_root"]) / "model_500_def"
        e.mkdir()
        (e / "attempt.json").write_text('{"state":"running","iteration":500}', encoding="utf-8")
        out = board.board(self.smi, self.procs, self.cfg, now=self.now)
        self.assertIn("지난 1 회 실측 평균", out)
        first = next(l for l in out.splitlines() if l.startswith("  1 "))
        self.assertIn("실행", first)  # running rows come first
        self.assertIn("EX-41 500 경계 평가", first)

    def test_queue_add_move_done_roundtrip(self):
        self.assertEqual(board.queue_cmd(self.args(title="EX-42 Kit 예행", start="23:30"), self.cfg, self.now),
                         "added 1")
        board.queue_cmd(self.args(qaction="move", id=1, priority=1, gpu=None, start="01:00", end=None),
                        self.cfg, self.now)
        q = json.loads(Path(self.cfg["queue"]).read_text(encoding="utf-8"))
        self.assertEqual((q["items"][0]["priority"], q["format"]), (1, "foothold-gpu-queue/1"))
        row = next(l for l in board.board(self.smi, self.procs, self.cfg, now=self.now).splitlines()
                   if "EX-42 Kit 예행" in l)
        self.assertIn(" P1 ", row)
        board.queue_cmd(self.args(qaction="done", id=1), self.cfg, self.now)
        self.assertNotIn("EX-42 Kit 예행", board.board(self.smi, self.procs, self.cfg, now=self.now))
        with self.assertRaises(ValueError):
            board.queue_cmd(self.args(qaction="done", id=9), self.cfg, self.now)
        with self.assertRaises(ValueError):
            board.queue_cmd(self.args(priority=7), self.cfg, self.now)

    def test_warning_running_item_without_process_and_idle_gpu_with_ready_item(self):
        board.queue_cmd(self.args(title="ghost", gpu=0), self.cfg, self.now)
        board.queue_cmd(self.args(qaction="run", id=1), self.cfg, self.now)
        board.queue_cmd(self.args(title="ready now", gpu=1), self.cfg, self.now)
        out = board.board(self.smi, self.procs, self.cfg, now=self.now)
        self.assertNotIn("「ghost」 는 실행인데", out)  # training holds GPU0
        self.procs = [p for p in self.procs if p["pid"] != 84424]
        self.smi["gpus"][0]["util"] = 0
        out = board.board(self.smi, self.procs, self.cfg, now=self.now)
        self.assertIn("「ghost」 는 실행인데 GPU0 에 프로세스 없음", out)
        self.assertIn("GPU1 가", out)
        self.assertIn("시작 가능한 일 있음: ready now", out)

    def test_items_waiting_for_approval_are_not_startable(self):
        board.queue_cmd(self.args(title="EX-42 Kit 예행", cond="CPU 시험 끝 + 팀장 승인 뒤", needs_approval=True), self.cfg, self.now)
        board.queue_cmd(self.args(title="flagged", needs_approval=True), self.cfg, self.now)
        board.queue_cmd(self.args(title="waits other", cond="250 점수 대기", needs_approval=True), self.cfg, self.now)
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=160)
        warn = " ".join(l for l in out.splitlines() if l.startswith("경고"))
        for title in ("EX-42 Kit 예행", "flagged", "waits other"):
            self.assertNotIn(title, warn)
        self.assertIn("C층 남은 81/81 칸", warn)  # fixture C층 queue has no owner process: real stall
        board.queue_cmd(self.args(title="free job"), self.cfg, self.now)
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=160)
        self.assertIn("시작 가능한 일 있음: free job", out)
        self.assertNotIn("EX-42 Kit 예행 ·", out.split("시작 가능한 일 있음")[1].splitlines()[0])

    def test_c_layer_owner_alive_at_zero_percent_is_between_cells_until_5_minutes(self):
        board.queue_cmd(self.args(title="free job"), self.cfg, self.now)
        self.procs.append({"pid": 4100, "started": self.now - 60,
                           "cmdline": "python.exe D:/x/c_layer_gpu1_remainder.py run-remaining"})
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=120)
        self.assertNotIn("시작 가능한 일 있음", out)
        self.assertNotIn("주인 프로세스는 살아 있음", out)
        self.assertIn("Kit 시작 중 · 칸 사이", out)
        out = board.board(self.smi, self.procs, self.cfg, now=self.now + 301, width=160)
        self.assertIn("0 % 인데 C층 주인 프로세스는 살아 있음", out)
        self.assertIn("5 분 넘음", out)

    def test_condition_words_alone_never_gate(self):
        # 11/04 13:11: 「대기」 in a free-text condition kept six scripter units off an idle GPU1.
        item = {"state": "대기", "kind": "render", "argv": ["python", "x.py"], "gpu": 1,
                "condition": "저장본 대기 · 승인 문구 포함"}
        self.assertFalse(board.needs_approval(item))
        self.assertTrue(board.needs_approval(dict(item, needs_approval=True)))

    def test_launcher_column(self):
        board.queue_cmd(self.args(title="kit smoke", cond="팀장 승인 뒤", needs_approval=True), self.cfg, self.now)
        board.queue_cmd(self.args(title="hand job"), self.cfg, self.now)
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=140)
        row = lambda key: next(l for l in out.splitlines() if key in l and l.lstrip()[:1].isdigit())
        self.assertIn("승인 뒤", row("kit smoke"))
        self.assertIn(" 손 · lead ", row("hand job"))
        self.assertIn("score_watch 자동", row("250 경계 평가"))
        self.assertTrue(out.splitlines()[0])
        header = next(l for l in out.splitlines() if l.lstrip().startswith("#"))
        self.assertIn("띄움", header)

    def test_boundary_passed_without_eval_record_warns(self):
        self.status_file.write_text(json.dumps({"state": "running", "iter": 260, "iter_s": 27.0}), encoding="utf-8")
        out = board.board(self.smi, self.procs, self.cfg, now=self.now)
        self.assertNotIn("250 경계를 지났는데", out)  # 250..300: manifest not rewritten yet, not a fault
        self.assertIn("EX-41 250 경계 평가", out)      # and the 250 item stays listed
        self.status_file.write_text(json.dumps({"state": "running", "iter": 310, "iter_s": 27.0}), encoding="utf-8")
        self.assertIn("250 경계를 지났는데 평가 기록 없음", board.board(self.smi, self.procs, self.cfg, now=self.now))

    def test_pending_manifest_shows_next_save_in_state(self):
        Path(self.cfg["eval_root"], "watcher.stdout.log").write_text(
            '{"state": "pending", "iteration": 250, "reason": "manifest_not_committed"}\n', encoding="utf-8")
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=140)
        row = next(l for l in out.splitlines() if "EX-41 250 경계 평가" in l and l.lstrip()[:1].isdigit())
        self.assertIn("대기 · 다음 저장 " + datetime_hm(self.now + 90 * 27.0), row)
        self.assertIn("manifest 는 다음 저장(300) 때 갱신", out)
        self.assertEqual({screen_width(l) for l in out.splitlines() if l}, {140})

    def test_bad_queue_file_is_reported_not_swallowed(self):
        Path(self.cfg["queue"]).write_text('{"format":"other"}', encoding="utf-8")
        self.assertIn("대기열 파일 오류", board.board(self.smi, self.procs, self.cfg, now=self.now))


def datetime_hm(ts):
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def screen_width(line):
    """Independent of the module: ANSI stripped, East Asian W/F = 2 cells."""
    import re as _re
    import unicodedata as _u
    plain = _re.sub(r"\x1b\[[0-9;]*m", "", line)
    return sum(0 if _u.combining(c) else (2 if _u.east_asian_width(c) in "WF" else 1) for c in plain)


class LayoutTests(BoardViewTests):
    """Every line has the exact cell width at 120 and 100 columns (Korean = 2 cells)."""

    def crowded(self):
        long = "아주 긴 한글 작업 이름 " * 12
        for k in range(3):
            board.queue_cmd(self.args(title=f"{k} {long}", cond=long, start="23:59"), self.cfg, self.now)
        self.procs.append({"pid": 5000, "started": 1500.0,
                           "cmdline": "python.exe -m foothold_s2.eval.eval_map_modes_with_a_very_long_name --device=cuda:1"})

    def test_lines_have_exact_width_at_120_and_100_plain_and_color(self):
        self.crowded()
        for width in (120, 100):
            for color in (False, True):
                out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=width, color=color)
                widths = {screen_width(l) for l in out.splitlines() if l}
                self.assertEqual(widths, {width}, (width, color))
                if color:
                    self.assertIn("\x1b[32m", out)
                else:
                    self.assertNotIn("\x1b[", out)

    def test_two_boxes_side_by_side_and_stacked_below_100(self):
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=100)
        self.assertEqual(sum(l.count("┌─ GPU") for l in out.splitlines()), 2)
        self.assertTrue(any(l.count("┌─ GPU") == 2 for l in out.splitlines()))
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=90)
        self.assertFalse(any(l.count("┌─ GPU") == 2 for l in out.splitlines()))
        self.assertEqual({screen_width(l) for l in out.splitlines() if l}, {90})

    def test_cut_with_ellipsis_and_detail_moved_to_notes(self):
        self.crowded()
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=100)
        rows = [l for l in out.splitlines() if "아주 긴 한글" in l]
        self.assertTrue(rows and all(l.rstrip().endswith("…") for l in rows))
        notes = out.split("근거")[1]
        self.assertIn("대기열 1 · lead · 아주 긴 한글", notes)

    def test_cell_width_and_fit(self):
        self.assertEqual(board.cell_width("한글ab"), 6)
        self.assertEqual(board.cell_width("\x1b[32m실행\x1b[0m"), 4)
        self.assertEqual(board.fit("가나다라", 5), "가나…")
        self.assertEqual(board.cell_width(board.fit("가나다라", 5)), 5)
        self.assertEqual(board.fit("ab", 4, ">"), "  ab")

    def test_clock_marks_next_day(self):
        from datetime import datetime
        now = datetime(2026, 11, 3, 23, 0).timestamp()
        self.assertEqual(board.clock(datetime(2026, 11, 4, 1, 41).timestamp(), now), "01:41+1")
        self.assertEqual(board.clock(datetime(2026, 11, 3, 23, 30).timestamp(), now), "23:30")
        self.assertEqual(board.clock(None, now), "-")

    def test_box_end_time_shows_date_when_day_changes(self):
        from datetime import datetime
        now = datetime(2026, 11, 3, 23, 0).timestamp()
        self.assertEqual(board.when(datetime(2026, 11, 5, 11, 41).timestamp(), now), "11-05 11:41")
        self.assertEqual(board.when(datetime(2026, 11, 3, 23, 30).timestamp(), now), "23:30")
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=120)
        box_end = next(l for l in out.splitlines() if "예상 끝" in l and "로컬" in l)
        self.assertRegex(box_end, r"예상 끝 \d\d-\d\d \d\d:\d\d")
        self.assertNotRegex(box_end, r"\+\d")


class FakeKernel32:
    """GetConsoleMode / SetConsoleMode stand-in. `accept` False = console refuses VT."""

    def __init__(self, mode, accept=True, console=True):
        self.mode, self.accept, self.console, self.set_calls = mode, accept, console, []

    def GetStdHandle(self, n):
        return 7

    def GetConsoleMode(self, h, ref):
        if not self.console:
            return 0
        ref._obj.value = self.mode
        return 1

    def SetConsoleMode(self, h, mode):
        self.set_calls.append(mode)
        if self.accept:
            self.mode = mode
        return int(self.accept)


class FakeOut:
    def __init__(self, tty=True):
        self.parts, self.tty = [], tty

    def write(self, text):
        self.parts.append(text)

    def flush(self):
        pass

    def isatty(self):
        return self.tty

    def text(self):
        return "".join(self.parts)


class WatchTests(unittest.TestCase):
    def test_vt_is_turned_on_and_read_back(self):
        k = FakeKernel32(mode=0x0003)
        self.assertTrue(board.enable_vt(kernel32=k, isatty=lambda: True))
        self.assertEqual(k.set_calls, [0x0007])
        k = FakeKernel32(mode=0x0007)
        self.assertTrue(board.enable_vt(kernel32=k, isatty=lambda: True))
        self.assertEqual(k.set_calls, [])

    def test_vt_refused_or_no_console_or_pipe_is_false(self):
        self.assertFalse(board.enable_vt(kernel32=FakeKernel32(0x0003, accept=False), isatty=lambda: True))
        self.assertFalse(board.enable_vt(kernel32=FakeKernel32(0x0003, console=False), isatty=lambda: True))
        self.assertFalse(board.enable_vt(kernel32=FakeKernel32(0x0007), isatty=lambda: False))

    def test_frame_overwrites_in_place(self):
        f = board.frame("a\nb")
        self.assertEqual(f, "\x1b[H" + "a\x1b[K\n" + "b\x1b[K\n" + "\x1b[J")
        self.assertNotIn("\x1b[2J", f)  # no full clear: no flicker, no scroll

    def run_watch(self, vt, frames=3, interrupt=False):
        import argparse
        from unittest import mock
        args = argparse.Namespace(watch=0.01, slow_every=999, width=100, no_color=False)
        out = FakeOut()
        slow = {"procs": [], "train": None, "queue": [], "qerr": None, "attempts": [], "rows": [], "c_files": ([], []),
                "read_at": 0.0}
        smi = {"gpus": {0: {"util": 1, "mib": 1}, 1: {"util": 1, "mib": 1}}, "apps": {}}
        calls = {"slow": 0}

        def fake_slow(*a, **k):
            calls["slow"] += 1
            return dict(slow, read_at=board.datetime.now().timestamp())
        render = board.render_board
        def maybe_interrupt(*a, **k):
            if interrupt and len(out.parts) > 2:
                raise KeyboardInterrupt
            return render(*a, **k)
        with mock.patch.object(board, "enable_vt", lambda isatty=None: vt), \
             mock.patch.object(board, "slow_data", fake_slow), \
             mock.patch.object(board, "nvidia_smi", lambda: smi), \
             mock.patch.object(board, "render_board", maybe_interrupt), \
             mock.patch.object(board, "idle_update", lambda *a, **k: {}), \
             mock.patch.object(board, "read_shared_bytes",
                               mock.Mock(side_effect=AssertionError("1 s frame read a training file"))), \
             mock.patch("os.system") as cls:
            rc = board.watch(args, out=out, stop_after=frames)
        return rc, out.text(), calls["slow"], cls

    def test_watch_uses_alternate_screen_overwrites_and_restores(self):
        rc, text, slow_calls, cls = self.run_watch(vt=True)
        self.assertEqual(rc, 0)
        self.assertTrue(text.startswith(board.SCREEN_ENTER))
        self.assertTrue(text.endswith(board.SCREEN_LEAVE))
        self.assertEqual(text.count("\x1b[H"), 3)
        self.assertEqual(text.count("\x1b[J"), 3)
        self.assertNotIn("\x1b[2J", text)
        self.assertIn("· 0.01 초 · 프로세스 · 파일은 999 초마다", text)
        self.assertEqual(slow_calls, 1)  # heavy reads cached, not per frame
        cls.assert_not_called()

    def test_ctrl_c_restores_screen(self):
        rc, text, _, _ = self.run_watch(vt=True, frames=10, interrupt=True)
        self.assertEqual(rc, 0)
        self.assertTrue(text.endswith(board.SCREEN_LEAVE))

    def test_no_vt_falls_back_to_cls(self):
        rc, text, _, cls = self.run_watch(vt=False, frames=2)
        self.assertNotIn("\x1b[", text)
        self.assertEqual(cls.call_count, 2)

    def test_watch_default_interval_is_one_second(self):
        import io
        from contextlib import redirect_stderr
        p = []
        orig = board.watch
        try:
            board.watch = lambda args, **k: p.append(args) or 0
            board.main(["board", "--watch"])
        finally:
            board.watch = orig
        self.assertEqual((p[0].watch, p[0].slow_every), (1.0, 10.0))


class HeightTests(BoardViewTests):
    """Thirty C층 units + many items must still fit the terminal height, head first."""

    def crowd(self):
        for k in range(30):
            board.queue_cmd(self.args(title=f"C층 다음 칸 한 번(run-next) {k + 1}/30", priority=4), self.cfg, self.now)
        for k in range(12):
            board.queue_cmd(self.args(title=f"다른 일 {k}", priority=3, start="23:59"), self.cfg, self.now)

    def test_fits_height_40_and_30_with_boxes_and_table_head_on_screen(self):
        self.crowd()
        for h in (40, 30):
            out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=120, height=h).splitlines()
            self.assertLessEqual(len(out), h, h)
            head = out[:h]
            self.assertTrue(any("┌─ GPU0" in l for l in head))
            self.assertTrue(any("└" in l for l in head))
            self.assertTrue(any(l.lstrip().startswith("#") and "내용" in l for l in head))
            self.assertEqual({screen_width(l) for l in out if l}, {120})

    def test_c_layer_units_fold_into_one_row_and_table_is_capped(self):
        self.crowd()
        full = board.board(self.smi, self.procs, self.cfg, now=self.now, width=140, detail=True)
        rows = [l for l in full.splitlines() if l[:4].strip().isdigit() and " GPU" in l[:24]]
        self.assertEqual(sum("C층" in l for l in rows), 1)  # 30 units + summary -> one row
        self.assertIn("C층 남은 칸 81/81 · 지금 - · 다음", full)
        out = board.board(self.smi, self.procs, self.cfg, now=self.now, width=140, height=60)
        rows = [l for l in out.splitlines() if l[:4].strip().isdigit() and " GPU" in l[:24]]
        self.assertLessEqual(len(rows), 1 + board.TABLE_NEXT)
        self.assertIn("외 ", out)

    def test_notes_dropped_first_and_detail_shows_everything(self):
        self.crowd()
        small = board.board(self.smi, self.procs, self.cfg, now=self.now, width=120, height=30)
        self.assertNotIn("근거", small)
        full = board.board(self.smi, self.procs, self.cfg, now=self.now, width=120, detail=True)
        self.assertIn("근거", full)
        self.assertNotIn("외 ", full)

    def test_short_cell_names(self):
        self.assertEqual(board.short_cell("stepping_stones_low_L4_probe_prop_only"), "디딤돌 L4 끔")
        self.assertEqual(board.short_cell("pyramid_stairs_inv_L2_eval_pred"), "내림계단 L2 복원")
        self.assertEqual(board.short_cell(None), "-")


class DispatchTests(unittest.TestCase):
    """Fake GPU, fake processes, fake spawn: priority, yield, failure skip, training guard."""

    def setUp(self):
        from unittest import mock
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.root = root
        self.status = root / "train_start_status.json"
        self.status.write_text(json.dumps({"state": "running", "iter": 100, "iter_s": 27.0}), encoding="utf-8")
        (root / "TRAINING_BUSY_GPU0").write_text(json.dumps({"pid": os.getpid(), "run": str(root)}),
                                                 encoding="utf-8")
        self.cfg = dict(board.LIVE, queue=str(root / "queue.json"), train_marker=str(root / "TRAINING_BUSY_GPU0"))
        patch = mock.patch.dict(board.DISPATCH, {"results": str(root / "res"), "logs": str(root / "logs"),
                                                 "idle_log": str(root / "idle.jsonl"),
                                                 "state": str(root / "state.json"),
                                                 "p1_markers": [str(root / "PRIORITY_BUSY_GPU1")]})
        patch.start()
        self.addCleanup(patch.stop)
        self.smi = {"gpus": {0: {"util": 80, "mib": 1}, 1: {"util": 0, "mib": 1}}, "apps": {}}
        self.procs = [{"pid": 84424, "started": 1.0, "cmdline": "python train_start.py --device=cuda:0"}]
        self.spawned, self.notes, self.alive, self.late = [], [], set(), None

    def add(self, title, priority, kind="eval", argv=("python", "x.py"), **extra):
        q = board.read_queue(self.cfg["queue"])
        new = {"id": len(q["items"]) + 1, "title": title, "priority": priority, "gpu": 1, "start": None,
               "end": None, "owner": "t", "condition": "", "state": "대기", "kind": kind,
               "argv": list(argv) if argv else None, **extra}
        q["items"].append(new)
        board.write_queue(self.cfg["queue"], q)
        return new["id"]

    def spawn(self, item_id, log):
        pid = 5000 + item_id
        self.spawned.append(item_id)
        self.alive.add(pid)
        return pid

    def step(self, now=1000.0):
        return board.dispatch_step(self.cfg, now=now, smi=self.smi, procs=self.procs, spawn=self.spawn,
                                   notify=lambda s, b: self.notes.append(s),
                                   alive=lambda pid: pid in self.alive, fam=lambda pid: {pid} if pid in self.alive else set(),
                                   recheck=lambda ours: self.late)

    def items(self):
        return {i["id"]: i for i in board.read_queue(self.cfg["queue"])["items"]}

    def finish(self, item_id, rc, last_json=None):
        res = Path(board.DISPATCH["results"])
        res.mkdir(parents=True, exist_ok=True)
        (res / f"item_{item_id}.json").write_text(json.dumps({"rc": rc, "ended": 1.0, "last_json": last_json}),
                                                   encoding="utf-8")

    RUN_NEXT = ("python", "-m", "foothold_s2.eval.c_layer_gpu1_remainder", "run-next")

    def test_no_training_marker_frees_gpu1_dead_marker_holds_it(self):
        a = self.add("prep eval", 2)
        Path(self.cfg["train_marker"]).unlink()  # deliberate stop / prep time: marker removed
        self.assertEqual(self.step(now=1000.0)["action"], "launched")
        self.finish(a, 0)
        self.alive.discard(5000 + a)
        Path(self.cfg["train_marker"]).write_text(json.dumps({"pid": 99999999, "run": str(self.root)}),
                                                  encoding="utf-8")  # training process gone
        b = self.add("after crash", 2)
        r = self.step(now=1010.0)
        self.assertEqual(r["action"], "train_not_running")
        self.assertEqual(self.items()[b]["state"], "대기")

    def test_three_consecutive_failures_block_that_family_only(self):
        bad = ("python", "-m", "foothold_s2.eval.w78_video_consumer")
        ids = [self.add(f"clip {i}", 3, kind="render", argv=bad, state="실패", done_at=float(i + 1)) for i in range(3)]
        waiting = self.add("clip 4", 3, kind="render", argv=bad)
        other = self.add("other eval", 3, kind="eval", argv=("python", "-m", "foothold_s2.eval.eval_map_modes"))
        r = self.step(now=1000.0)
        self.assertEqual((r["action"], r.get("item")), ("launched", other))
        self.assertEqual(self.items()[waiting]["state"], "대기")
        self.assertTrue(any("3 회 연속 실패" in n for n in self.notes))
        it = board.read_queue(self.cfg["queue"])
        next(i for i in it["items"] if i["id"] == waiting)["fail_streak_ok"] = True
        board.write_queue(self.cfg["queue"], it)
        self.finish(other, 0)
        self.alive.discard(5000 + other)
        self.step(now=1005.0)
        self.assertEqual(self.step(now=1010.0).get("item"), waiting)

    def test_two_seed_wrapper_capture_is_done_not_a_yield(self):
        a = self.add("C76 2seed", 3, kind="render",
                     argv=("python", "D:/x/c_layer_gpu1_remainder_two_seed.py", "--cell", "c"))
        self.step(now=1000.0)
        self.finish(a, 0, {"cell": "c", "state": "pending", "event": "captured"})
        self.alive.discard(5000 + a)
        self.step(now=1005.0)
        self.assertEqual(self.items()[a]["state"], "끝")

    def test_no_training_releases_and_never_creates_group_holds(self):
        state = {"holds": {"c_layer": {"since": 1.0, "reason": "pending", "iter": 10}}}
        notes = []
        board.update_holds(state, [{"id": 1, "argv": ["python", "c_layer_gpu1_remainder", "run-next"],
                                    "last_yield": "pending"}], None, None, 2.0, lambda s, b: notes.append(s))
        self.assertEqual(state["holds"], {})
        self.assertTrue(any("재개" in n for n in notes))

    def test_cancel_marks_never_run_items_and_refuses_running(self):
        a = self.add("wrong args", 2)
        args = type("A", (), {"qaction": "cancel", "id": a, "reason": "push250 L0 only"})()
        self.assertEqual(board.queue_cmd(args, self.cfg, 1000.0), f"cancel {a}")
        self.assertEqual((self.items()[a]["state"], self.items()[a]["cancel_reason"]), ("취소", "push250 L0 only"))
        self.assertNotEqual(self.step(now=1001.0)["action"], "launched")
        b = self.add("running", 2, state="실행", pid=7)
        with self.assertRaises(ValueError):
            board.queue_cmd(type("A", (), {"qaction": "cancel", "id": b, "reason": "x"})(), self.cfg, 1002.0)

    def test_run_next_that_yielded_goes_back_to_the_queue(self):
        a = self.add("C층 다음 칸 1", 4, kind="render", argv=self.RUN_NEXT)
        self.step(now=1000.0)
        self.finish(a, 0, {"state": "yielded_to_higher_priority", "gate": {}})
        r = self.step(now=1005.0)
        it = self.items()[a]
        self.assertEqual((it["state"], it["yields"], it["last_yield"]), ("대기", 1, "yielded_to_higher_priority"))
        self.assertNotEqual(r["action"], "launched")  # waits requeue_after_s before trying again
        self.assertFalse(Path(board.DISPATCH["results"], f"item_{a}.json").exists())

    def test_run_next_hold_or_uncaptured_pending_requeues_captured_pending_is_done(self):
        a = self.add("C층 다음 칸 1", 4, kind="render", argv=self.RUN_NEXT)
        b = self.add("C층 다음 칸 2", 4, kind="render", argv=self.RUN_NEXT)
        c = self.add("C층 다음 칸 3", 4, kind="render", argv=self.RUN_NEXT)
        for item, last, want in ((a, {"state": "ex41_slowdown_hold"}, "대기"),
                                 (b, {"state": "pending", "queue_event": {"state": "pending", "event": "skipped"}}, "대기"),
                                 (c, {"state": "pending", "queue_event": {"state": "pending", "event": "captured"}}, "끝")):
            self.step(now=1000.0)
            self.assertEqual(self.spawned[-1], item)
            self.finish(item, 0, last)
            self.alive.discard(5000 + item)
            self.step(now=1001.0)
            it = self.items()[item]
            self.assertEqual(it["state"] if want == "끝" else (it["state"], it.get("yields")),
                             want if want == "끝" else ("대기", 1), item)
            if want == "대기":  # park it and lift the group hold so the next case runs
                q = board.read_queue(self.cfg["queue"])
                next(i for i in q["items"] if i["id"] == item)["state"] = "끝"
                board.write_queue(self.cfg["queue"], q)
                st = json.loads(Path(board.DISPATCH["state"]).read_text(encoding="utf-8"))
                st["holds"] = {}
                Path(board.DISPATCH["state"]).write_text(json.dumps(st), encoding="utf-8")

    def test_training_hold_holds_the_whole_c_layer_group_but_not_other_work(self):
        units = [self.add(f"C층 다음 칸 {k}", 4, kind="render", argv=self.RUN_NEXT) for k in range(5)]
        self.step(now=1000.0)
        self.finish(units[0], 0, {"state": "training_status_hold", "cell": "x"})
        self.alive.discard(5000 + units[0])
        # training died: status stays at iter 100
        for t in range(1001, 1200, 10):
            self.step(now=float(t))
        self.assertEqual(self.spawned, [units[0]])  # no burst of C층 launches
        holds = [n for n in self.notes if "보류" in n]
        self.assertEqual(len(holds), 1)
        other = self.add("baseline eval", 3)
        self.step(now=1300.0)
        self.assertEqual(self.spawned[-1], other)  # other kinds still go
        self.finish(other, 0)
        self.alive.discard(5000 + other)
        # training running again and 10+ updates further: resume, announced once
        self.status.write_text(json.dumps({"state": "running", "iter": 115, "iter_s": 27.0}), encoding="utf-8")
        self.step(now=1400.0)
        self.step(now=1500.0)
        self.assertEqual(sum("재개" in n for n in self.notes), 1)
        self.assertIn(self.spawned[-1], units)

    def test_launch_notices_are_batched_to_one_per_5_minutes(self):
        a = self.add("e1", 3)
        b = self.add("e2", 3)
        c = self.add("e3", 3)
        self.step(now=1000.0)
        for item, t in ((a, 1010.0), (b, 1020.0)):
            self.finish(item, 0)
            self.alive.discard(5000 + item)
            self.step(now=t)
        self.assertEqual(sum("띄움" in n for n in self.notes), 1)
        self.finish(c, 0)
        self.alive.discard(5000 + c)
        self.add("e4", 3)
        self.step(now=1400.0)
        self.assertEqual(sum("띄움" in n for n in self.notes), 2)

    def test_units_get_kit_eula_env_and_item_env_wins(self):
        env = board.unit_env({"env": {"TEMP": "D:/x", "PYTHONUTF8": "0"}}, {"PATH": "p"})
        self.assertEqual(env["OMNI_KIT_ACCEPT_EULA"], "YES")
        self.assertEqual(env["PYTHONUNBUFFERED"], "1")
        self.assertEqual((env["TEMP"], env["PYTHONUTF8"], env["PATH"]), ("D:/x", "0", "p"))
        self.assertEqual(board.unit_env({}, {})["PYTHONUTF8"], "1")

    def test_runwrap_child_sees_eula_env(self):
        import sys
        from unittest import mock
        d = Path(self.temp.name)
        board.write_queue(self.cfg["queue"], {"format": board.QUEUE_FORMAT, "items": [
            {"id": 1, "state": "실행", "cwd": str(d), "argv": [sys.executable, "-c",
             "import os, json; print(json.dumps({'eula': os.environ.get('OMNI_KIT_ACCEPT_EULA')}))"]}]})
        with mock.patch("builtins.print"):
            self.assertEqual(board.runwrap(1, self.cfg), 0)
        res = json.loads(Path(board.DISPATCH["results"], "item_1.json").read_text(encoding="utf-8"))
        self.assertEqual(res["last_json"], {"eula": "YES"})

    def test_no_new_unit_while_training_is_not_running(self):
        self.add("baseline eval", 3)
        for state in ("failed", "starting"):
            self.status.write_text(json.dumps({"state": state, "iter": 680, "iter_s": 27.0}), encoding="utf-8")
            r = self.step()
            self.assertEqual((r["action"], self.spawned), ("train_not_running", []), state)
        self.status.write_text(json.dumps({"state": "running", "iter": 690, "iter_s": 27.0}), encoding="utf-8")
        self.assertEqual(self.step()["action"], "launched")

    def test_non_run_next_rc0_is_done_even_with_pending_json(self):
        a = self.add("other eval", 3)
        self.step()
        self.finish(a, 0, {"state": "pending"})
        self.step()
        self.assertEqual(self.items()[a]["state"], "끝")

    def test_recheck_right_before_launch_yields(self):
        self.add("render cell", 4, kind="render")
        self.late = "marker:just-appeared"
        r = self.step()
        self.assertEqual((r["action"], self.spawned), ("yield_p1", []))
        self.assertIn("recheck", r["reason"])
        self.late = None
        self.assertEqual(self.step()["action"], "launched")

    def test_highest_priority_first_and_one_at_a_time(self):
        low = self.add("render cell", 4, kind="render")
        high = self.add("baseline eval", 3)
        self.assertEqual(self.step()["action"], "launched")
        self.assertEqual(self.spawned, [high])
        self.assertTrue(self.notes and self.notes[-1].startswith("[dispatcher] GPU1 띄움"))
        self.assertEqual(self.step()["action"], "busy_own")
        self.assertEqual(self.spawned, [high])
        self.finish(high, 0)
        self.assertEqual(self.step()["action"], "launched")
        self.assertEqual(self.spawned, [high, low])
        self.assertEqual(self.items()[high]["state"], "끝")

    def test_yields_to_p1_marker_and_foreign_gpu1_process_without_killing(self):
        a = self.add("render cell", 4, kind="render")
        Path(board.DISPATCH["p1_markers"][0]).write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        self.assertEqual(self.step()["action"], "yield_p1")
        Path(board.DISPATCH["p1_markers"][0]).unlink()
        self.procs.append({"pid": 777, "started": 1.0, "cmdline": "python -m foothold_s2.eval.eval_map_modes --device cuda:1"})
        r = self.step()
        self.assertEqual((r["action"], self.spawned), ("yield_p1", []))
        self.procs.pop()
        self.assertEqual(self.step()["action"], "launched")
        # P1 arrives while our unit runs: we do not start another, and never stop the running one.
        self.procs.append({"pid": 778, "started": 1.0, "cmdline": "python -m foothold_s2.eval.eval_map_modes --device cuda:1"})
        self.assertEqual(self.step()["action"], "busy_own")
        self.assertIn(5000 + a, self.alive)

    def test_failure_is_recorded_and_queue_moves_on(self):
        a = self.add("first", 3)
        b = self.add("second", 4, kind="render")
        self.step()
        self.finish(a, 7)
        self.assertEqual(self.step()["action"], "launched")
        it = self.items()
        self.assertEqual((it[a]["state"], it[a]["rc"]), ("실패", 7))
        self.assertEqual(self.spawned, [a, b])
        # wrapper died without a result: failed, next one goes
        c = self.add("third", 4, kind="probe")
        self.alive.discard(5000 + b)
        self.assertEqual(self.step()["action"], "launched")
        self.assertEqual(self.items()[b]["state"], "실패")
        self.assertEqual(self.spawned[-1], c)

    def test_done_files_must_exist(self):
        a = self.add("needs file", 3, done_files=[str(self.root / "out.json")])
        self.step()
        self.finish(a, 0)
        self.step()
        self.assertEqual(self.items()[a]["state"], "실패")

    def test_training_protection_blocks_new_units(self):
        for k in range(9):  # nine slow updates seen while there is nothing to start
            self.status.write_text(json.dumps({"state": "running", "iter": 100 + k, "iter_s": 30.5}), encoding="utf-8")
            self.step(now=1000.0 + k)
        self.add("render cell", 4, kind="render")
        self.status.write_text(json.dumps({"state": "running", "iter": 109, "iter_s": 30.5}), encoding="utf-8")
        r = self.step(now=1010.0)
        self.assertEqual(r["action"], "train_protect")
        self.assertEqual(self.spawned, [])
        for k in range(10):  # training recovers to 27 s: the unit may start again
            self.status.write_text(json.dumps({"state": "running", "iter": 110 + k, "iter_s": 27.0}), encoding="utf-8")
            r = self.step(now=1020.0 + k)
        self.assertEqual(self.spawned, [1])

    def test_training_kind_and_unapproved_and_waits_are_never_started(self):
        self.add("train", 0, kind="training")
        self.add("needs ok", 1, needs_approval=True)
        self.add("no command", 2, argv=None)
        self.add("lock held", 2, kind="render", wait_absent=[str(self.root / "gpu1_remainder.lock")])
        (self.root / "gpu1_remainder.lock").write_text("{}", encoding="utf-8")
        self.add("video pid", 2, kind="render", wait_pids=[4242])
        self.alive.add(4242)
        r = self.step()
        self.assertEqual((r["action"], self.spawned), ("nothing_to_fill", []))
        self.assertEqual(self.notes, ["[dispatcher] GPU1 채울 일 없음"])
        self.step(now=1100.0)
        self.assertEqual(len(self.notes), 1)  # at most once per 5 minutes
        self.step(now=1301.0)
        self.assertEqual(len(self.notes), 2)
        idle = [json.loads(l) for l in Path(board.DISPATCH["idle_log"]).read_text(encoding="utf-8").splitlines()]
        reasons = dict(map(tuple, idle[0]["waiting"]))
        self.assertTrue(reasons[1].startswith("kind_not_allowed"))
        self.assertEqual(reasons[2], "needs_approval")
        self.assertTrue(reasons[4].startswith("wait_absent"))
        self.assertEqual(reasons[5], "wait_pid:4242")
        self.alive.discard(4242)
        (self.root / "gpu1_remainder.lock").unlink()
        self.step(now=1400.0)
        self.assertEqual(self.spawned, [4])

    def test_queue_add_rejects_training_commands(self):
        import argparse
        a = argparse.Namespace(qaction="add", title="t", priority=2, gpu=1, start=None, end=None, owner="lead",
                               cond=None, needs_approval=False, kind=None, argv_json='["python","train.py"]',
                               cwd=None, wait_absent=[], wait_pid=[], done_file=[])
        with self.assertRaises(ValueError):
            board.queue_cmd(a, self.cfg, 1.0)


if __name__ == "__main__":
    unittest.main()
