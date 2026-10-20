"""사슬 실행기 L0: 가짜 명령으로 의존 · GPU 배타 · 실패 · 재시도 · 막힘 · 알림 · 재시작 이어 가기 · 붙기(adopt)."""

import json
import os
import subprocess
import sys
import time

import pytest

from foothold_s2.chain import runner

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable


def py(code):
    return [PY, "-c", code]


def touch_cmd(path, delay=0.0, code=0, text="ok"):
    return py("import time,sys;time.sleep(%s);open(r'%s','w').write('%s');sys.exit(%d)" % (delay, path, text, code))


class Notes:
    def __init__(self):
        self.lines = []

    def __call__(self, cfg, text):
        self.lines.append(text)

        return "fake"


def make(tmp_path, jobs, **cfg):
    config = {"poll_s": 0.02, "start_gap_s": 0.0, "gpus": [0, 1], "jobs": jobs}
    config.update(cfg)
    notes = Notes()
    chain = runner.Chain(config, str(tmp_path / "state"), notifier=notes, sleep=time.sleep, repo_root=REPO)

    return chain, notes


def events(tmp_path):
    path = tmp_path / "state" / "chain_status.jsonl"

    return [json.loads(line) for line in open(path, encoding="utf-8")] if path.exists() else []


def kinds(tmp_path, job=None):
    return [e["event"] for e in events(tmp_path) if job is None or e["job"] == job]


def test_dependency_order_and_launched_first_evidence_done_are_recorded(tmp_path):
    a_out, b_out = tmp_path / "a.txt", tmp_path / "b.txt"
    jobs = [{"name": "A", "gpu": 0, "cmd": touch_cmd(a_out, 0.1), "done": {"outputs": [str(a_out)]}},
            {"name": "B", "gpu": 1, "depends_on": ["A"], "cmd": touch_cmd(b_out), "done": {"outputs": [str(b_out)]}}]
    chain, notes = make(tmp_path, jobs)
    assert chain.run() == 0
    ev = events(tmp_path)
    order = [(e["job"], e["event"]) for e in ev if e["event"] in ("launched", "done")]
    assert order == [("A", "launched"), ("A", "done"), ("B", "launched"), ("B", "done")]    # B 는 A 가 끝난 뒤에만
    assert "first_evidence" in kinds(tmp_path, "A")
    assert any("A done" in n for n in notes.lines) and any("B done" in n for n in notes.lines)
    assert chain.state["B"]["state"] == "done" and "chain_end" in kinds(tmp_path, "chain")


def test_same_gpu_jobs_never_overlap_and_any_gpu_picks_a_free_one(tmp_path):
    marks = tmp_path / "marks.txt"
    body = "import time;f=open(r'%s','a');f.write('S%%s\\n'%%1);f.flush();time.sleep(0.25);f.write('E\\n');f.close()" % marks
    jobs = [{"name": "X", "gpu": 0, "cmd": py(body)}, {"name": "Y", "gpu": 0, "cmd": py(body)}]
    chain, _ = make(tmp_path, jobs)
    chain.run()
    assert marks.read_text(encoding="utf-8").split() == ["S1", "E", "S1", "E"]                           # 겹치지 않았다
    # gpu 를 목록 · any 로 주면 비어 있는 장을 고른다
    chain2, _ = make(tmp_path / "t2", [{"name": "P", "gpu": 0, "cmd": py("import time;time.sleep(0.4)")},
                                       {"name": "Q", "gpu": "any", "cmd": py("pass")}])
    chain2.run()
    assert chain2.state["Q"]["gpu"] == 1 and chain2.state["P"]["gpu"] == 0


def test_failure_triggers_the_retry_command_once_and_then_succeeds(tmp_path):
    out = tmp_path / "ck.txt"
    jobs = [{"name": "T", "gpu": 0, "cmd": touch_cmd(tmp_path / "x.txt", 0, code=3),
             "retry": {"cmd": touch_cmd(out)}, "done": {"outputs": [str(out)]}}]
    chain, notes = make(tmp_path, jobs)
    assert chain.run() == 0
    core = [k for k in kinds(tmp_path, "T") if k in ("launched", "attempt_failed", "relaunched", "done")]
    assert core == ["launched", "attempt_failed", "relaunched", "done"]                 # 재시도는 한 번
    assert chain.state["T"]["attempt"] == 2 and chain.state["T"]["state"] == "done"
    assert any("attempt_failed" in n for n in notes.lines)


def test_second_failure_marks_failed_blocks_dependents_and_independent_jobs_still_run(tmp_path):
    ok = tmp_path / "ok.txt"
    jobs = [{"name": "F", "gpu": 0, "cmd": touch_cmd(tmp_path / "n.txt", 0, code=5),
             "retry": {"cmd": touch_cmd(tmp_path / "n2.txt", 0, code=6)}},
            {"name": "D", "gpu": 0, "depends_on": ["F"], "cmd": touch_cmd(tmp_path / "d.txt")},
            {"name": "E", "gpu": 0, "depends_on": ["D"], "cmd": touch_cmd(tmp_path / "e.txt")},
            {"name": "I", "gpu": 1, "cmd": touch_cmd(ok), "done": {"outputs": [str(ok)]}}]
    chain, notes = make(tmp_path, jobs)
    assert chain.run() == 1
    st = {n: chain.state[n]["state"] for n in chain.state}
    assert st == {"F": "failed", "D": "blocked", "E": "blocked", "I": "done"}
    assert not (tmp_path / "d.txt").exists()                                         # 막힌 작업은 띄우지 않았다
    assert any("F failed" in n for n in notes.lines) and sum(n.startswith(("[chain] D blocked", "[chain] E blocked")) for n in notes.lines) == 2


def test_retries_zero_fails_immediately_without_a_second_attempt(tmp_path):
    jobs = [{"name": "R", "gpu": 0, "retries": 0, "cmd": touch_cmd(tmp_path / "r.txt", 0, code=2)}]
    chain, _ = make(tmp_path, jobs)
    chain.run()
    assert chain.state["R"]["state"] == "failed" and chain.state["R"]["attempt"] == 1


def test_exit_zero_is_not_enough_missing_output_traceback_and_status_state_fail_the_job(tmp_path):
    # 산출물 없음
    chain, _ = make(tmp_path / "a", [{"name": "J", "gpu": 0, "retries": 0, "cmd": py("pass"),
                                      "done": {"outputs": [str(tmp_path / "never.pt")]}}])
    chain.run()
    assert chain.state["J"]["state"] == "failed"
    # 로그에 Traceback (종료 코드 0)
    chain, _ = make(tmp_path / "b", [{"name": "J", "gpu": 0, "retries": 0, "cmd": py("print('Traceback (most recent call last)')")}])
    # Traceback 검사는 done.no_traceback 또는 작업 로그가 기본이다
    chain.run()
    assert chain.state["J"]["state"] == "failed"
    # 상태 파일이 done 이 아니거나 iter 가 모자람
    status = tmp_path / "s.json"
    status.write_text(json.dumps({"state": "running", "iter": 7}))
    chain, _ = make(tmp_path / "c", [{"name": "J", "gpu": 0, "retries": 0, "cmd": py("pass"),
                                      "done": {"status_glob": str(status), "min_iter": 10}}])
    chain.run()
    assert chain.state["J"]["state"] == "failed"
    status.write_text(json.dumps({"state": "done", "iter": 10}))
    chain, _ = make(tmp_path / "d", [{"name": "J", "gpu": 0, "retries": 0, "cmd": py("pass"),
                                      "done": {"status_glob": str(status), "min_iter": 10}}])
    chain.run()
    assert chain.state["J"]["state"] == "done"


def test_adopt_watches_an_external_process_without_touching_it_and_judges_by_outputs(tmp_path):
    out = tmp_path / "model_5999.pt"
    child = subprocess.Popen(py("import time,sys;time.sleep(0.5);open(r'%s','w').write('m')" % out))
    jobs = [{"name": "train", "gpu": 0, "adopt": {"pid": child.pid}, "done": {"outputs": [str(out)]}},
            {"name": "after", "gpu": 0, "depends_on": ["train"], "cmd": touch_cmd(tmp_path / "after.txt")}]
    chain, _ = make(tmp_path, jobs)
    assert chain.state["train"]["state"] == "running" and chain.state["train"]["adopted"]
    assert chain.run() == 0
    assert chain.state["after"]["state"] == "done" and child.wait() == 0               # 붙은 프로세스를 죽이지 않았다


def test_adopted_job_that_dies_without_outputs_is_retried_with_the_resume_command(tmp_path):
    ckpt = tmp_path / "resumed.pt"
    child = subprocess.Popen(py("import sys;sys.exit(1)"))
    child.wait()
    jobs = [{"name": "train", "gpu": 0, "adopt": {"pid": child.pid}, "retry": {"cmd": touch_cmd(ckpt)},
             "done": {"outputs": [str(ckpt)]}}]
    chain, notes = make(tmp_path, jobs)
    assert chain.run() == 0
    assert "relaunched" in kinds(tmp_path, "train") and chain.state["train"]["attempt"] == 2


def test_restart_resumes_from_the_state_file_and_does_not_rerun_finished_jobs(tmp_path):
    a_out, b_out = tmp_path / "a.txt", tmp_path / "b.txt"
    jobs = [{"name": "A", "gpu": 0, "cmd": touch_cmd(a_out), "done": {"outputs": [str(a_out)]}},
            {"name": "B", "gpu": 0, "depends_on": ["A"], "cmd": touch_cmd(b_out, 0.3), "done": {"outputs": [str(b_out)]}}]
    chain, _ = make(tmp_path, jobs)

    while chain.state["B"]["state"] != "running":                                      # A 끝, B 가 도는 중에 실행기를 «죽인다»
        chain.step()
        time.sleep(0.02)

    stamp = a_out.stat().st_mtime
    chain2, _ = make(tmp_path, jobs)                                                  # 새 실행기 = 상태 파일에서 이어 감
    assert chain2.state["A"]["state"] == "done" and chain2.state["B"]["state"] == "running"
    assert chain2.run() == 0
    assert a_out.stat().st_mtime == stamp and chain2.state["B"]["state"] == "done"    # A 는 다시 돌지 않았다
    assert kinds(tmp_path, "A").count("launched") == 1


def test_unknown_dependency_and_duplicate_names_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        make(tmp_path / "a", [{"name": "A", "gpu": 0, "cmd": py("pass"), "depends_on": ["Z"]}])

    with pytest.raises(ValueError):
        make(tmp_path / "b", [{"name": "A", "gpu": 0, "cmd": py("pass")}, {"name": "A", "gpu": 1, "cmd": py("pass")}])


def test_glob_placeholder_resolves_to_the_newest_match_at_launch_time(tmp_path):
    (tmp_path / "m1.pt").write_text("1")
    time.sleep(0.05)
    (tmp_path / "m2.pt").write_text("2")
    assert runner.resolve_text("{glob:%s}" % (str(tmp_path) + "/m*.pt"), 0).endswith("m2.pt")
    assert runner.resolve_text("cuda:{gpu} {device}", 1) == "cuda:1 cuda:1"
    with pytest.raises(FileNotFoundError):
        runner.resolve_text("{glob:%s}" % (str(tmp_path) + "/none*.pt"), 0)


def _wait_for(path, n=1, timeout=10.0):
    t0 = time.time()

    while time.time() - t0 < timeout:
        if os.path.exists(path) and len(open(path, encoding="utf-8").read().splitlines()) >= n:
            return True

        time.sleep(0.05)

    return False


def test_default_notifier_runs_the_command_in_a_thread_and_logs_the_result(tmp_path):
    sink, nlog = tmp_path / "sink.txt", tmp_path / "notify.log"
    cfg = {"cmd": [PY, "-c", "import sys;open(r'%s','a').write(sys.argv[1]+chr(10))" % sink, "{text}"], "log": str(nlog)}
    assert runner.default_notifier(cfg, "[chain] A done") == "notify started"        # 기다리지 않고 돌려준다
    assert _wait_for(nlog) and _wait_for(sink)
    assert sink.read_text(encoding="utf-8").strip() == "[chain] A done" and "attempt 1 rc=0" in nlog.read_text(encoding="utf-8")
    assert runner.default_notifier(None, "x") == "no notifier"


def test_notifier_retries_when_the_prompt_is_busy_then_gives_up_and_never_raises(tmp_path):
    nlog = tmp_path / "notify.log"
    cfg = {"cmd": [PY, "-c", "import sys;sys.exit(4)"], "log": str(nlog), "retries": 2, "retry_gap_s": 0.05}
    runner.default_notifier(cfg, "[chain] busy")
    assert _wait_for(nlog, n=2)
    text = nlog.read_text(encoding="utf-8")
    assert "attempt 1 rc=4" in text and "attempt 2 rc=4" in text and "attempt 3" not in text
    cfg2 = {"cmd": ["no-such-binary-xyz", "{text}"], "log": str(tmp_path / "n2.log"), "retries": 1}
    runner.default_notifier(cfg2, "x")
    assert _wait_for(tmp_path / "n2.log") and "error" in (tmp_path / "n2.log").read_text(encoding="utf-8")


def test_stop_file_ends_the_runner_but_leaves_children_alone(tmp_path):
    jobs = [{"name": "A", "gpu": 0, "cmd": py("import time;time.sleep(2)")}]
    chain, _ = make(tmp_path, jobs)
    chain.step()
    pid = chain.state["A"]["pid"]
    (tmp_path / "state" / "chain.stop").write_text("x")
    assert chain.run() == 2 and runner.pid_alive(pid)
    time.sleep(2.3)


def test_globname_placeholder_gives_the_newest_directory_name_for_resume(tmp_path):
    (tmp_path / "run_a").mkdir()
    time.sleep(0.05)
    (tmp_path / "run_b").mkdir()
    assert runner.resolve_text("--load_run {globname:%s}" % (str(tmp_path) + "/run_*"), 0) == "--load_run run_b"


def test_recursive_glob_finds_nested_logs_for_the_traceback_check(tmp_path):
    nested = tmp_path / "root" / "p" / "axis1" / "run.log"
    nested.parent.mkdir(parents=True)
    nested.write_text("Traceback (most recent call last)")
    chain, _ = make(tmp_path / "c", [{"name": "J", "gpu": 0, "retries": 0, "cmd": py("pass"),
                                      "done": {"no_traceback": [str(tmp_path / "root") + "/**/run.log"]}}])
    chain.run()
    assert chain.state["J"]["state"] == "failed"


def test_after_waits_for_the_job_to_finish_but_not_for_its_success(tmp_path):
    out = tmp_path / "later.txt"
    jobs = [{"name": "R", "gpu": 0, "retries": 0, "cmd": touch_cmd(tmp_path / "r.txt", 0.2, code=4)},
            {"name": "L", "gpu": 1, "after": ["R"], "cmd": touch_cmd(out), "done": {"outputs": [str(out)]}}]
    chain, _ = make(tmp_path, jobs)
    assert chain.run() == 1                                                         # R 는 failed 이므로 종료 코드 1
    assert chain.state["R"]["state"] == "failed" and chain.state["L"]["state"] == "done"      # L 은 막히지 않고 R 뒤에 돌았다
    order = [(e["job"], e["event"]) for e in events(tmp_path) if e["event"] in ("launched", "failed", "done")]
    assert order.index(("R", "failed")) < order.index(("L", "launched"))
    # depends_on 이면 막힌다 (대조)
    chain2, _ = make(tmp_path / "t2", [{"name": "R", "gpu": 0, "retries": 0, "cmd": touch_cmd(tmp_path / "r2.txt", 0, code=4)},
                                       {"name": "L", "gpu": 1, "depends_on": ["R"], "cmd": py("pass")}])
    chain2.run()
    assert chain2.state["L"]["state"] == "blocked"


def test_after_is_validated_like_depends_on(tmp_path):
    with pytest.raises(ValueError):
        make(tmp_path, [{"name": "A", "gpu": 0, "cmd": py("pass"), "after": ["nope"]}])


def test_yaml_order_is_priority_when_two_ready_jobs_want_the_same_free_gpu(tmp_path):
    jobs = [{"name": "B", "gpu": 1, "cmd": py("import time;time.sleep(0.3)")},
            {"name": "A2", "gpu": "any", "cmd": py("pass")}]
    # 두 작업이 동시에 준비됨: B(gpu 1 고정)가 먼저 GPU 1 을 잡고, any 는 남은 GPU 0 을 받는다
    chain, _ = make(tmp_path, jobs, gpus=[1, 0])
    chain.run()
    assert chain.state["B"]["gpu"] == 1 and chain.state["A2"]["gpu"] == 0
    # 순서를 바꾸면 any 가 먼저 [1, 0] 목록의 첫 장(GPU 1)을 잡아 B 는 기다린다: 순서가 우선순위
    chain2, _ = make(tmp_path / "t2", [jobs[1], jobs[0]], gpus=[1, 0])
    chain2.run()
    assert chain2.state["A2"]["gpu"] == 1 and chain2.state["B"]["gpu"] == 1
    order = [e["job"] for e in events(tmp_path / "t2") if e["event"] == "launched"]
    assert order == ["A2", "B"]


def test_done_report_puts_result_keys_into_the_notification(tmp_path):
    result = tmp_path / "res.json"
    jobs = [{"name": "R", "gpu": 0, "retries": 0,
             "cmd": py("import json;json.dump({'verdict':'mismatch','ok':False},open(r'%s','w'))" % result),
             "done": {"outputs": [str(result)], "report": {"file": str(result), "keys": ["verdict"]}}}]
    chain, notes = make(tmp_path, jobs)
    assert chain.run() == 0
    assert any("R done" in n and "verdict=mismatch" in n for n in notes.lines)


def test_real_yaml_has_the_agreed_graph():
    cfg = runner.load_config(os.path.join(REPO, "foothold_s2", "chain", "chain_s1a_night.yaml"))
    jobs = {j["name"]: j for j in cfg["jobs"]}
    names = [j["name"] for j in cfg["jobs"]]
    assert jobs["scan_eval"]["after"] == ["repro_s0"] and "repro_s0" not in jobs["scan_eval"]["depends_on"]
    assert "repro_s0" not in jobs["blind_eval"].get("depends_on", []) and "repro_s0" not in jobs["blind_eval"].get("after", [])
    assert not [n for n in names if n.startswith("bf16")]                                  # bf16 네 작업은 이번 밤 사슬에서 뺐다
    assert names == ["scan_train", "blind_train", "repro_s0", "scan_eval", "v2_base_gate200", "blind_eval"]
    assert jobs["v2_base_gate200"]["depends_on"] == ["scan_eval"] and jobs["blind_eval"]["gpu"] == 1
    assert jobs["repro_s0"]["retries"] == 0 and jobs["repro_s0"]["done"]["report"]["keys"] == ["verdict"]
    assert jobs["scan_train"]["adopt"]["pid"] == 95784 and jobs["blind_train"]["adopt"]["pid"] == 89020
