"""Answer-known cases: each 11/04-05 incident state must FAIL or WARN in ops_check."""
import json
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ops_check  # noqa: E402

RUN = Path("C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522")
RUN_W = "C:\\Users\\AI-WS01\\s2_lab\\ex41_main_20261104_235522"


class P:
    def __init__(self, ct=0.0, pid=1):
        self.info = {"create_time": ct}
        self.pid = pid


def procs(push=True, stray=False, loop_ct=9e12):
    out = [(P(), f"python train_start.py --ex41_log_root={RUN_W}\\main\\x"),
           (P(), f"python -m foothold_s2.ex41_score_watch --run-dir {RUN_W}\\main\\x"),
           (P(loop_ct), "python D:/x/_out/tools/gpu_jobs/dispatch.py dispatch")]
    if push:
        out.append((P(), f"python -m foothold_s2.eval.ex41_push250_watch --run-dir {RUN_W}\\main\\x"))
    if stray:
        out.append((P(), "python -m foothold_s2.ex41_score_watch --run-dir D:\\mai-tmp\\runner\\s2_lab\\ex41_rehearsal_1"))
    return out


def levels(rows):
    return {name: level for level, name, _ in rows}


def q(*items):
    return {"items": list(items)}


def test_clean_state_has_no_fail(tmp_path):
    with mock.patch.object(ops_check, "P1_MARKER", tmp_path / "none"):
        rows = ops_check.check(RUN, now=1e9, procs=procs(), queue=q(*[{"id": i, "priority": 4, "state": "대기"} for i in range(5)]))
    assert not [r for r in rows if r[0] == "FAIL"], rows


def test_missing_push_watcher_fails(tmp_path):          # I04
    with mock.patch.object(ops_check, "P1_MARKER", tmp_path / "none"):
        lv = levels(ops_check.check(RUN, procs=procs(push=False), queue=q()))
    assert lv["I04 push_watch"] == "FAIL"


def test_stray_rehearsal_watcher_fails(tmp_path):       # I05
    with mock.patch.object(ops_check, "P1_MARKER", tmp_path / "none"):
        lv = levels(ops_check.check(RUN, procs=procs(stray=True), queue=q()))
    assert lv["I05 stray_watch"] == "FAIL"


def test_rehearsal_queue_item_fails(tmp_path):          # I06
    with mock.patch.object(ops_check, "P1_MARKER", tmp_path / "none"):
        lv = levels(ops_check.check(RUN, procs=procs(), queue=q({"id": 387, "title": "REHEARSAL-ex41-stage-6", "state": "대기"})))
    assert lv["I06 rehearsal_items"] == "FAIL"


def test_stale_dispatcher_code_warns(tmp_path):         # I08
    with mock.patch.object(ops_check, "P1_MARKER", tmp_path / "none"):
        lv = levels(ops_check.check(RUN, procs=procs(loop_ct=0.0), queue=q()))
    assert lv["I08 dispatcher_code"] == "WARN"


def test_marker_idle_and_dead_owner_fail(tmp_path):     # I11
    m = tmp_path / "PRIORITY_BUSY_GPU1"
    m.write_text(json.dumps({"pid": 999999, "job": "EX-41-push250-D171"}), encoding="utf-8")
    import os
    os.utime(m, (0, 0))
    with mock.patch.object(ops_check, "P1_MARKER", m):
        lv = levels(ops_check.check(RUN, now=31 * 60, procs=procs(), queue=q(), util=2400))
    assert lv["I11 marker_owner"] == "FAIL" and lv["I11 marker_idle"] == "FAIL"


def test_p4_low_water_warns(tmp_path):                  # I15
    with mock.patch.object(ops_check, "P1_MARKER", tmp_path / "none"):
        lv = levels(ops_check.check(RUN, procs=procs(), queue=q({"id": 1, "priority": 4, "state": "대기"})))
    assert lv["I15 gpu1_depth"] == "WARN"


def test_parked_items_do_not_count_as_filler(tmp_path):  # I15 · I26
    parked = [{"id": i, "priority": 3, "state": "대기", "start": 2e9} for i in range(48)]
    with mock.patch.object(ops_check, "P1_MARKER", tmp_path / "none"):
        lv = levels(ops_check.check(RUN, now=1e9, procs=procs(), queue=q(*parked)))
    assert lv["I15 gpu1_depth"] == "WARN"


def test_late_score_near_boundary_warns():              # I29
    lv = ops_check.next_boundary_score(RUN, 0, it=2480, scores=["score_2000_x.json"])
    assert lv[0] == "WARN", lv                          # 2501 needs m2250 · 10 min left
    assert ops_check.next_boundary_score(RUN, 0, it=2480, scores=["score_2250_x.json"])[0] == "OK"
    assert ops_check.next_boundary_score(RUN, 0, it=2300, scores=[])[0] == "OK"   # 94 min left


def test_p1_behind_long_unit_warns(tmp_path):           # I24
    m = tmp_path / "PRIORITY_BUSY_GPU1"
    m.write_text(json.dumps({"pid": __import__("os").getpid(), "job": "EX-41-push250-D171"}), encoding="utf-8")
    with mock.patch.object(ops_check, "P1_MARKER", m):
        lv = levels(ops_check.check(RUN, now=10_000, procs=procs(), util=9000,
                                    queue=q({"id": 412, "priority": 2, "state": "실행", "run_at": 10_000 - 77 * 60})))
    assert lv["I24 p1_behind_long_unit"] == "WARN"


def test_marker_low_memory_but_fresh_child_ok(tmp_path):   # I11 · 11/06 push ladder between cells
    m = tmp_path / "PRIORITY_BUSY_GPU1"
    m.write_text(json.dumps({"pid": 4242, "job": "ex41_evaluation_push_ladder"}), encoding="utf-8")
    import os
    os.utime(m, (0, 0))
    with mock.patch.object(ops_check, "P1_MARKER", m),          mock.patch.object(ops_check, "_owner_recent_child", return_value=True):
        lv = levels(ops_check.check(RUN, now=31 * 60, procs=procs(), queue=q(), util=2400))
    assert lv["I11 marker_idle"] == "OK"
    with mock.patch.object(ops_check, "P1_MARKER", m),          mock.patch.object(ops_check, "_owner_recent_child", return_value=False):
        lv = levels(ops_check.check(RUN, now=31 * 60, procs=procs(), queue=q(), util=2400))
    assert lv["I11 marker_idle"] == "FAIL"


def test_worklist_overdue_without_evidence_fails(tmp_path):   # W · 팀장 11/06 17:2x
    w = tmp_path / "WORKLIST.tsv"
    ev = tmp_path / "done.md"
    w.write_text("id\tsource\tpriority\tdue\towner\tevidence\tstatus\twhat\n"
                 f"A\tx\tP1\tat:2026-11-06T10:00\tlead\t{ev}\topen\tstage report\n"
                 f"B\tx\tP0\titer:6000\tlead\t{ev}::marker\topen\tfinal score\n"
                 "C\tx\tP3\t-\tlead\t-\topen\toptional\n", encoding="utf-8")
    import datetime
    now = datetime.datetime(2026, 11, 6, 11, 0).timestamp()
    lv = {b: a for a, b, _ in ops_check.worklist(w, now, 5990)}
    assert lv["W A"] == "FAIL" and lv["W B"] == "WARN" and "W C" not in lv
    lv = {b: a for a, b, _ in ops_check.worklist(w, now, 6000)}
    assert lv["W B"] == "FAIL"
    ev.write_text("marker", encoding="utf-8")       # evidence arrives -> asks to close, no FAIL
    lv = {b: a for a, b, _ in ops_check.worklist(w, now, 6000)}
    assert lv["W A"] == "WARN" and lv["W B"] == "WARN"


def test_train_absent_ok_only_after_final_checkpoint(tmp_path):
    no_train = [x for x in procs() if "train_start.py" not in x[1]]
    run = tmp_path / "run"
    (run / "main" / "x").mkdir(parents=True)
    assert levels(ops_check.check(run, procs=no_train, queue=q()))["train"] == "FAIL"
    (run / "main" / "x" / f"model_{ops_check.FINAL_ITER}.pt").write_bytes(b"x")
    assert levels(ops_check.check(run, procs=no_train, queue=q()))["train"] == "OK"


def test_gpu0_waiting_without_running_fails_after_training():
    no_train = [x for x in procs() if "train_start.py" not in x[1]]
    stuck = q({"id": 1, "gpu": 0, "state": "대기"})
    assert levels(ops_check.check(RUN, procs=no_train, queue=stuck))["I35 gpu0_idle"] == "FAIL"
    moving = q({"id": 1, "gpu": 0, "state": "대기"}, {"id": 2, "gpu": 0, "state": "실행"})
    assert levels(ops_check.check(RUN, procs=no_train, queue=moving))["I35 gpu0_idle"] == "OK"


def test_i36_running_eval_with_recent_output_is_ok(tmp_path):
    run = tmp_path / 'run'
    output = run / 'eval' / 'score-watch' / 'model_100_x' / 'stage_end_auxiliary_eval'
    output.mkdir(parents=True)
    recent = output / 'progress.json'
    recent.write_text('{}', encoding='utf-8')
    now = recent.stat().st_mtime + 10
    job = {'id': 555, 'kind': 'eval', 'owner': 'ex41_score_watch', 'state': '실행',
           'run_at': now - 3600, 'pid': 99, 'argv': ['--out', str(output)]}
    assert ops_check.score_attempt_wait(run, now, [], [job],
                                        cpu_delta=lambda pid: 0)[0] == 'OK'


def test_i36_running_eval_stalled_for_30_minutes_fails(tmp_path):
    run = tmp_path / 'run'
    job = {'id': 555, 'kind': 'eval', 'owner': 'ex41_score_watch', 'state': '실행',
           'run_at': 1000, 'pid': 99, 'argv': ['--out', str(run / 'eval' / 'missing')]}
    level, name, detail = ops_check.score_attempt_wait(run, 1000 + 31 * 60, [], [job],
                                                       cpu_delta=lambda pid: 0.0)
    assert (level, name) == ('FAIL', 'I36 score_wait') and 'queue 555' in detail
    assert ops_check.score_attempt_wait(run, 1000 + 31 * 60, [], [job],
                                        cpu_delta=lambda pid: 0.2)[0] == 'OK'


def test_i36_new_eval_is_not_stalled(tmp_path):
    run = tmp_path / 'run'
    job = {'id': 555, 'kind': 'eval', 'owner': 'ex41_score_watch', 'state': '실행',
           'run_at': 1000, 'pid': 99, 'argv': ['--out', str(run / 'eval' / 'missing')]}
    assert ops_check.score_attempt_wait(run, 1000 + 5 * 60, [], [job],
                                        cpu_delta=lambda pid: 0.0)[0] == 'OK'


def test_i36_score_watch_attempt_without_output_fails(tmp_path):
    run = tmp_path / 'run'
    receipt = run / 'eval' / 'score-watch' / 'model_6000_x' / 'attempt.json'
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({'state': 'running', 'iteration': 6000,
                                   'source': str(receipt.parent / 'evaluation')}), encoding='utf-8')
    os.utime(receipt, (1000, 1000))
    owner = P(pid=77)
    procs_now = [(owner, f'python -m foothold_s2.ex41_score_watch --run-dir {run}')]
    level, name, detail = ops_check.score_attempt_wait(run, 1000 + 31 * 60, procs_now, [],
                                                       cpu_delta=lambda pid: 0.0)
    assert (level, name) == ('FAIL', 'I36 score_wait') and 'attempt m6000' in detail


def test_i36_check_calls_guard_for_running_queue_job(tmp_path):
    run = tmp_path / 'run'
    job = {'id': 555, 'kind': 'eval', 'owner': 'ex41_score_watch', 'state': '실행',
           'run_at': 1000, 'pid': 99, 'argv': ['--out', str(run / 'eval' / 'missing')]}
    with mock.patch.object(ops_check, 'P1_MARKER', tmp_path / 'none'), \
         mock.patch.object(ops_check, 'DISPATCH', Path(__file__).resolve()), \
         mock.patch.object(ops_check, '_cpu_tree_delta', return_value=0.0):
        rows = ops_check.check(run, now=1000 + 31 * 60, procs=procs(), queue=q(job))
    assert levels(rows)['I36 score_wait'] == 'FAIL'
