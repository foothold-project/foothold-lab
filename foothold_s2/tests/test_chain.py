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
    prio = {n: jobs[n].get("priority", 5) for n in names}
    assert all(prio[n] == 9 for n in names if n.startswith("bf16") or n == "agenda_J4")                  # bf16 은 빈 틈만
    assert all(prio[n] == 1 for n in ("scan_train", "blind_train", "repro_s0", "scan_eval", "v2_base_gate200", "blind_eval", "agenda_J1"))
    assert prio["s1b_train"] == 2 and jobs["s1b_train"]["require_file"].endswith("s1a_verdict_pass.json")
    assert jobs["s1b_train"]["cmd"][:2] == ["bash", "foothold_s2/run_s1b.sh"] and jobs["s1b_train"]["gpu"] == 0   # lead 10/21 14:3x: S1a-v1.1 종료로 S1-a blind 로 되돌림
    assert jobs["s1b_train"]["depends_on"] == ["blind_train"]
    assert jobs["c1_scan_train"]["adopt"]["pid"] > 0 and jobs["c2_blind_train"]["adopt"]["pid"] > 0           # 원인 시험 두 판(adopt)
    assert jobs["c1_scan_train"]["gpu"] == 0 and jobs["c2_blind_train"]["gpu"] == 1
    assert not [n for n in jobs if "v11" in n]                                                              # Rx1(S1a-v1.1) 작업은 사슬에서 뺐다 (팀장 「멈춰」)
    assert jobs["s1b_train"]["done"]["min_iter"] == 8999 and "run_s1b.sh" in " ".join(jobs["s1b_train"]["retry"]["cmd"])
    assert jobs["bf16_B_bf16kl_mb256"]["depends_on"] == ["blind_eval", "snapshot_bf16"] and jobs["bf16_B_bf16kl_mb256"]["gpu"] == 1
    assert jobs["bf16_A_fp32_mb128"]["depends_on"] == ["v2_base_gate200", "snapshot_bf16"] and jobs["bf16_A_fp32_mb128"]["gpu"] == 0
    assert jobs["bf16_A2_fp32_mb128_seed43"]["depends_on"] == ["blind_eval", "snapshot_bf16"] and jobs["bf16_A2_fp32_mb128_seed43"]["gpu"] == "any"
    assert jobs["bf16_stamp"]["depends_on"] == ["bf16_A_fp32_mb128", "bf16_B_bf16kl_mb256", "bf16_A2_fp32_mb128_seed43"]
    assert jobs["bf16_compare"]["depends_on"] == ["bf16_stamp"] and "--require_stamps" in jobs["bf16_compare"]["cmd"]
    assert jobs["bf16_compare"]["accept_rc"] == [0, 1] and "gpu" not in jobs["bf16_stamp"] and "gpu" not in jobs["snapshot_bf16"]
    assert all(jobs[n]["repo"].endswith("snap_bf16") for n in ("bf16_A_fp32_mb128", "bf16_B_bf16kl_mb256", "bf16_A2_fp32_mb128_seed43"))
    assert jobs["snapshot_bf16"]["priority"] == 0 and "snap_bf16/logs/rsl_rl/foothold_s2" in jobs["bf16_A_fp32_mb128"]["done"]["status_glob"]
    assert "gpu" not in jobs["agenda_J1"] and "gpu" not in jobs["agenda_J4"] and "gpu" not in jobs["bf16_compare"]
    assert jobs["agenda_J1"]["depends_on"] == ["scan_eval", "blind_eval"] and jobs["agenda_J4"]["depends_on"] == ["bf16_compare"]
    assert jobs["v2_base_gate200"]["depends_on"] == ["scan_eval"] and jobs["blind_eval"]["gpu"] == 1
    for n in ("bf16_B_bf16kl_mb256", "bf16_A_fp32_mb128", "bf16_A2_fp32_mb128_seed43", "bf16_compare"):
        assert len(jobs[n]["require_any_file"]) == 2 and all("s1a_verdict_" in r for r in jobs[n]["require_any_file"])
        assert jobs[n]["require_any_file"][0].endswith("s1a_verdict_pass.json") and jobs[n]["require_any_file"][1].endswith("s1a_verdict_fail.json")
    assert "require_any_file" not in jobs["s1b_train"] and jobs["s1b_train"]["require_file"].endswith("s1a_verdict_pass.json")
    assert not [t for t in str(cfg).split("${")[1:]]                                                    # 풀리지 않은 변수 없음
    assert jobs["repro_s0"]["retries"] == 0 and jobs["repro_s0"]["done"]["report"]["keys"] == ["verdict", "ok"]
    assert jobs["scan_train"]["adopt"]["pid"] == 95784 and jobs["blind_train"]["adopt"]["pid"] == 89020


def launched_order(tmp_path):
    return [e["job"] for e in events(tmp_path) if e["event"] == "launched"]


def test_priority_a_ready_high_priority_job_goes_before_a_low_one_listed_first(tmp_path):
    jobs = [{"name": "LOW", "gpu": "any", "priority": 9, "cmd": py("import time;time.sleep(0.2)")},
            {"name": "HIGH", "gpu": "any", "priority": 1, "cmd": py("import time;time.sleep(0.2)")}]
    chain, _ = make(tmp_path, jobs, gpus=[0])
    chain.run()
    assert launched_order(tmp_path) == ["HIGH", "LOW"]                       # 한 장뿐: priority 가 작은 것이 먼저


def test_priority_a_low_job_uses_a_free_gpu_only_while_the_high_job_cannot_launch(tmp_path):
    marks = tmp_path / "high_started.txt"
    jobs = [{"name": "GATE", "gpu": 0, "priority": 1, "cmd": py("import time;time.sleep(0.5)")},
            {"name": "HIGH", "gpu": 0, "priority": 1, "depends_on": ["GATE"], "cmd": touch_cmd(marks, 0.0)},
            {"name": "LOW", "gpu": "any", "priority": 9, "cmd": py("import time;time.sleep(0.2)")}]
    chain, _ = make(tmp_path, jobs, gpus=[0, 1])
    chain.run()
    st = chain.state
    assert st["LOW"]["gpu"] == 1                                              # HIGH 는 앞 작업을 기다리고 GPU 0 은 GATE 가 쥠: LOW 는 빈 GPU 1 을 썼다
    assert launched_order(tmp_path) == ["GATE", "LOW", "HIGH"] or launched_order(tmp_path)[0] == "GATE"
    assert st["HIGH"]["state"] == "done" and st["LOW"]["state"] == "done"


def test_priority_low_job_never_waits_in_front_of_a_ready_high_job_for_the_same_gpu(tmp_path):
    jobs = [{"name": "LOW", "gpu": 0, "priority": 9, "cmd": py("pass")},
            {"name": "HIGH", "gpu": 0, "priority": 1, "cmd": py("pass")}]
    chain, _ = make(tmp_path, jobs, gpus=[0])
    chain.run()
    assert launched_order(tmp_path) == ["HIGH", "LOW"]


def test_require_file_holds_the_job_until_the_file_exists(tmp_path):
    flag = tmp_path / "verdict.json"
    out = tmp_path / "out.txt"
    jobs = [{"name": "S1B", "gpu": 0, "require_file": str(flag), "cmd": touch_cmd(out), "done": {"outputs": [str(out)]}}]
    chain, _ = make(tmp_path, jobs)

    for _ in range(5):
        chain.step()
        time.sleep(0.03)

    assert chain.state["S1B"]["state"] == "pending" and not out.exists()       # 파일이 없으면 띄우지 않는다
    assert not chain.finished()
    flag.write_text("{}", encoding="utf-8")
    assert chain.run() == 0 and chain.state["S1B"]["state"] == "done"


def test_job_without_gpu_runs_while_all_gpus_are_busy_and_holds_none(tmp_path):
    out = tmp_path / "agenda.txt"
    jobs = [{"name": "TRAIN", "gpu": 0, "cmd": py("import time;time.sleep(0.6)")},
            {"name": "TRAIN2", "gpu": 1, "cmd": py("import time;time.sleep(0.6)")},
            {"name": "AGENDA", "cmd": touch_cmd(out), "done": {"outputs": [str(out)]}},
            {"name": "NEXT", "gpu": 0, "depends_on": ["AGENDA"], "cmd": py("pass")}]
    chain, _ = make(tmp_path, jobs)
    chain.run()
    ev = [(e["job"], e["event"]) for e in events(tmp_path)]
    assert ev.index(("AGENDA", "launched")) < ev.index(("TRAIN", "done"))        # 두 장이 다 차 있어도 바로 돈다
    assert chain.state["AGENDA"].get("gpu") is None and chain.state["AGENDA"]["state"] == "done"
    assert chain.state["NEXT"]["state"] == "done"


def test_empty_cmd_fails_loudly_instead_of_running_nothing(tmp_path):
    chain, notes = make(tmp_path, [{"name": "S1B", "gpu": 0, "cmd": []}])
    assert chain.run() == 1 and chain.state["S1B"]["state"] == "failed"
    assert any("cmd 가 비어" in n for n in notes.lines)


def test_vars_are_substituted_everywhere_with_env_override_and_unresolved_is_an_error(tmp_path, monkeypatch):
    path = tmp_path / "c.yaml"
    path.write_text("vars:\n  ROOT: /data/foothold\n  OUT: ${ROOT}/out\njobs:\n  - name: A\n    gpu: 0\n    cmd: [echo, ${OUT}/x]\n",
                    encoding="utf-8")
    cfg = runner.load_config(str(path))
    assert cfg["jobs"][0]["cmd"] == ["echo", "/data/foothold/out/x"]
    monkeypatch.setenv("CHAIN_ROOT", "D:/other")
    assert runner.load_config(str(path))["jobs"][0]["cmd"] == ["echo", "D:/other/out/x"]
    path.write_text("vars:\n  ROOT: /r\njobs:\n  - name: A\n    gpu: 0\n    cmd: [echo, ${NOPE}]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        runner.load_config(str(path))


def _git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo)] + list(args)).decode().strip()


def _mini_repo(tmp_path):
    repo = tmp_path / "orig"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "foothold_s2").mkdir()
    (repo / "foothold_s2" / "m.py").write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")

    return repo


def test_snapshot_pins_the_commit_and_ignores_later_edits(tmp_path):
    from foothold_s2.chain import snapshot

    repo = _mini_repo(tmp_path)
    sha = snapshot.make_snapshot(str(repo), str(tmp_path / "snap"))
    assert (tmp_path / "snap" / "SNAPSHOT_HEAD.txt").read_text(encoding="utf-8").strip() == sha
    (repo / "foothold_s2" / "m.py").write_text("X = 2\n", encoding="utf-8")                 # 원본이 바뀌어도
    _git(repo, "commit", "-aqm", "c2")
    assert (tmp_path / "snap" / "foothold_s2" / "m.py").read_text(encoding="utf-8").strip() == "X = 1"   # 사본은 그대로
    assert snapshot.make_snapshot(str(repo), str(tmp_path / "snap"), rev=sha) == sha                    # 다시 불러도 같은 사본
    with pytest.raises(RuntimeError):
        snapshot.make_snapshot(str(repo), str(tmp_path / "snap"), rev="HEAD")                           # 다른 rev 를 요구하면 오류


def _run_dir(tmp_path, name, env_extra="", agent_extra="", seed=1):
    d = tmp_path / name
    (d / "params").mkdir(parents=True)
    (d / "params" / "env.yaml").write_text("scene:\n  num_envs: 3072\nseed: %d\nlog_dir: /x/%s\n%s" % (seed, name, env_extra), encoding="utf-8")
    (d / "params" / "agent.yaml").write_text("algorithm:\n  lr: 0.001\nseed: %d\nrun_name: %s\nperception:\n  microbatch_envs: %d\n  kl_fp32: true\n%s"
                                             % (seed, name, 128 if "A" in name else 256, agent_extra), encoding="utf-8")

    return str(d)


def test_snapshot_with_paths_checks_out_only_those_folders(tmp_path):
    from foothold_s2.chain import snapshot

    repo = _mini_repo(tmp_path)
    (repo / "big").mkdir()
    (repo / "big" / "video.bin").write_text("x" * 100, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "big")
    snapshot.make_snapshot(str(repo), str(tmp_path / "snap_sparse"), paths=["foothold_s2"])
    assert (tmp_path / "snap_sparse" / "foothold_s2" / "m.py").exists() and not (tmp_path / "snap_sparse" / "big").exists()


def test_stamps_ignore_per_run_values_but_catch_real_code_or_cfg_differences(tmp_path):
    from foothold_s2.chain import stamp

    repo = _mini_repo(tmp_path)
    a, b, a2 = (_run_dir(tmp_path, "runA", seed=42), _run_dir(tmp_path, "runB", seed=42), _run_dir(tmp_path, "runA2", seed=43))

    for d in (a, b, a2):
        stamp.write_stamp(d, str(repo))

    chk = stamp.compare_stamps({"A": a, "B": b, "A2": a2})
    assert chk["comparable"], chk["reason"]                                                    # seed · 로그 폴더 · perception 덮어쓰기는 달라도 된다
    # env cfg 가 다르다 -> 코드 다름
    c = _run_dir(tmp_path, "runC", env_extra="extra_term: 1\n")
    stamp.write_stamp(c, str(repo))
    chk2 = stamp.compare_stamps({"A": a, "B": b, "C": c})
    assert not chk2["comparable"] and "env_sha" in chk2["reason"]
    # git HEAD 가 다르다
    (repo / "foothold_s2" / "m.py").write_text("X = 9\n", encoding="utf-8")
    _git(repo, "commit", "-aqm", "c2")
    d_ = _run_dir(tmp_path, "runD", seed=42)
    stamp.write_stamp(d_, str(repo))
    chk3 = stamp.compare_stamps({"A": a, "D": d_})
    assert not chk3["comparable"] and "git_head" in chk3["reason"]
    # 스탬프 없음
    e = _run_dir(tmp_path, "runE")
    assert "스탬프 없음" in stamp.compare_stamps({"A": a, "E": e})["reason"]


def test_compare_curves_refuses_to_judge_when_the_code_differs(tmp_path, monkeypatch):
    import json as _json
    from foothold_s2.chain import stamp
    from foothold_s2.scripts import compare_curves

    repo = _mini_repo(tmp_path)
    a, b = _run_dir(tmp_path, "runA", seed=42), _run_dir(tmp_path, "runB", seed=42)
    stamp.write_stamp(a, str(repo))
    (repo / "foothold_s2" / "m.py").write_text("X = 3\n", encoding="utf-8")
    _git(repo, "commit", "-aqm", "c2")
    stamp.write_stamp(b, str(repo))
    out = tmp_path / "res.json"
    monkeypatch.setattr(sys, "argv", ["compare_curves", "--a", a, "--b", b, "--out", str(out), "--require_stamps"])
    assert compare_curves.main() == 0                                                        # 판정하지 않고 정상 종료
    res = _json.load(open(out, encoding="utf-8"))
    assert res["verdict"] == "판정 불가 · 코드 다름" and "git_head" in res["reason"] and "metrics" not in res


def test_accept_rc_lets_a_tool_exit_one_as_a_legitimate_result_and_job_repo_sets_cwd_and_pythonpath(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", REPO)                       # 사본에는 foothold_s2 가 없으니 래퍼는 원래 경로로 뜬다(실제 사본은 전체 저장소)
    out = tmp_path / "res.txt"
    snap = tmp_path / "snap"
    snap.mkdir()
    body = "import os,sys;open(r'%s','w').write(os.getcwd()+'|'+os.environ['PYTHONPATH'].split(os.pathsep)[0]);sys.exit(1)" % out
    jobs = [{"name": "CMP", "repo": str(snap), "retries": 0, "accept_rc": [0, 1], "cmd": py(body), "done": {"outputs": [str(out)]}},
            {"name": "AFTER", "depends_on": ["CMP"], "cmd": py("pass")}]
    chain, _ = make(tmp_path, jobs)
    assert chain.run() == 0 and chain.state["AFTER"]["state"] == "done"                      # 종료 코드 1 이어도 막히지 않았다
    cwd, pp = out.read_text(encoding="utf-8").split("|")
    assert os.path.samefile(cwd, snap) and os.path.samefile(pp, snap)
    chain2, _ = make(tmp_path / "t2", [{"name": "X", "retries": 0, "cmd": py("import sys;sys.exit(1)")}])
    chain2.run()
    assert chain2.state["X"]["state"] == "failed"                                            # accept_rc 가 없으면 1 은 실패


def test_skip_if_done_does_not_rerun_a_job_whose_result_already_exists(tmp_path):
    out = tmp_path / "result.json"
    out.write_text("{}", encoding="utf-8")
    marker = tmp_path / "ran.txt"
    jobs = [{"name": "R", "gpu": 0, "skip_if_done": True, "cmd": touch_cmd(marker), "done": {"outputs": [str(out)]}},
            {"name": "N", "depends_on": ["R"], "cmd": py("pass")}]
    chain, _ = make(tmp_path, jobs)
    assert chain.run() == 0 and not marker.exists()                           # R 은 돌지 않았고
    assert chain.state["R"]["skipped"] and chain.state["N"]["state"] == "done"    # 뒤 작업은 이어졌다
    assert "skipped" in kinds(tmp_path, "R") and "launched" not in kinds(tmp_path, "R")
    out.unlink()                                                              # 결과가 없으면 돈다
    chain2, _ = make(tmp_path / "t2", [{"name": "R", "gpu": 0, "skip_if_done": True, "retries": 0,
                                        "cmd": touch_cmd(out), "done": {"outputs": [str(out)]}}])
    chain2.run()
    assert chain2.state["R"]["state"] == "done" and not chain2.state["R"].get("skipped")


def test_require_any_file_needs_just_one_of_the_files(tmp_path):
    f1, f2, out = tmp_path / "pass.json", tmp_path / "fail.json", tmp_path / "out.txt"
    jobs = [{"name": "BF", "gpu": 0, "require_any_file": [str(f1), str(f2)], "cmd": touch_cmd(out), "done": {"outputs": [str(out)]}}]
    chain, _ = make(tmp_path, jobs)

    for _ in range(4):
        chain.step()
        time.sleep(0.03)

    assert chain.state["BF"]["state"] == "pending"                                    # 둘 다 없으면 대기
    f2.write_text("{}", encoding="utf-8")                                             # 실패 파일만 있어도 풀린다
    assert chain.run() == 0 and chain.state["BF"]["state"] == "done"
    chain2, _ = make(tmp_path / "t2", [{"name": "BF", "gpu": 0, "require_any_file": [str(f1), str(tmp_path / "none.json")],
                                        "cmd": touch_cmd(tmp_path / "o2.txt")}])
    chain2.step()
    assert chain2.state["BF"]["state"] == "pending"


def _write_yaml(path, jobs_yaml):
    path.write_text("poll_s: 0.02\nstart_gap_s: 0\ngpus: [0, 1]\njobs:\n" + jobs_yaml, encoding="utf-8")


def test_yaml_edit_is_picked_up_by_a_running_chain_for_pending_jobs_only(tmp_path):
    cfgp = tmp_path / "c.yaml"
    out_b, out_c = tmp_path / "b.txt", tmp_path / "c.txt"
    sleep_cmd = '[%r, "-c", "import time;time.sleep(0.6)"]' % PY
    _write_yaml(cfgp, "  - name: A\n    gpu: 0\n    cmd: %s\n  - name: B\n    gpu: 0\n    depends_on: [A]\n    cmd: [%r, \"-c\", \"pass\"]\n    require_file: %s\n"
                % (sleep_cmd, PY, (tmp_path / "go.flag").as_posix()))
    cfg = runner.load_config(str(cfgp))
    chain = runner.Chain(cfg, str(tmp_path / "state"), notifier=Notes(), repo_root=REPO)
    chain.config_path = str(cfgp)
    chain._cfg_mtime = os.path.getmtime(cfgp)
    chain.step()
    assert chain.state["A"]["state"] == "running"
    time.sleep(0.05)
    # 편집: B 의 명령을 바꾸고(B 는 아직 pending), 새 작업 C 를 더하고, 돌고 있는 A 의 정의도 건드려 본다
    _write_yaml(cfgp, "  - name: A\n    gpu: 0\n    cmd: [%r, \"-c\", \"print('changed')\"]\n  - name: B\n    gpu: 0\n    depends_on: [A]\n    cmd: %s\n"
                      "  - name: C\n    gpu: 1\n    depends_on: [B]\n    cmd: [%r, \"-c\", \"pass\"]\n" % (PY, '[%r, "-c", "open(r\'%s\',\'w\').write(\'b\')"]' % (PY, out_b.as_posix()), PY))
    os.utime(cfgp, (time.time() + 5, time.time() + 5))
    chain.step()
    assert "reloaded" in [e["event"] for e in events(tmp_path)]
    assert chain.jobs["B"]["cmd"][-1].startswith("open(") and "require_file" not in chain.jobs["B"]           # pending 인 B 는 새 정의
    assert "C" in chain.jobs and chain.state["C"]["state"] == "pending"                                       # 새 작업이 더해졌다
    assert chain.jobs["A"]["cmd"][-1] != "print('changed')"                                                   # 돌고 있는 A 는 그대로
    assert chain.run() == 0 and out_b.exists()                                                               # 바뀐 B 가 돌고 C 가 이어졌다
    assert chain.state["C"]["state"] == "done"


def test_a_broken_yaml_edit_keeps_the_old_config_and_reports(tmp_path):
    cfgp = tmp_path / "c.yaml"
    _write_yaml(cfgp, "  - name: A\n    gpu: 0\n    cmd: [%r, \"-c\", \"pass\"]\n" % PY)
    chain = runner.Chain(runner.load_config(str(cfgp)), str(tmp_path / "state"), notifier=Notes(), repo_root=REPO)
    chain.config_path = str(cfgp)
    chain._cfg_mtime = os.path.getmtime(cfgp)
    _write_yaml(cfgp, "  - name: A\n    gpu: 0\n    depends_on: [ZZZ]\n    cmd: [x]\n")                         # 모르는 앞 작업
    os.utime(cfgp, (time.time() + 5, time.time() + 5))
    chain.reload_if_changed()
    assert "reload_failed" in [e["event"] for e in events(tmp_path)] and "depends_on" not in chain.jobs["A"]


def test_adopt_job_added_by_yaml_reload_attaches_instead_of_being_launched_by_cmd(tmp_path):
    """다시 읽기로 더해진 adopt 작업이 cmd 로 띄워지려다 «cmd 가 비어 있다» 로 실패하던 일(10/21 09:19)을 막는다."""
    cfg_path = tmp_path / "chain.yaml"
    out = tmp_path / "model.pt"
    child = subprocess.Popen(py("import time;time.sleep(1.5);open(r'%s','w').write('m')" % str(out).replace("\\", "/")))
    first = "poll_s: 0.02\nstart_gap_s: 0\ngpus: [0, 1]\njobs:\n  - name: A\n    gpu: 0\n    cmd: [%s]\n" % ", ".join(
        '"%s"' % c.replace("\\", "/") for c in touch_cmd(tmp_path / "a.txt"))
    cfg_path.write_text(first, encoding="utf-8")
    chain = runner.Chain(runner.load_config(str(cfg_path)), str(tmp_path / "state"), notifier=Notes(), sleep=time.sleep, repo_root=REPO)
    chain.config_path = str(cfg_path)
    chain._cfg_mtime = os.path.getmtime(str(cfg_path))
    second = first + ("  - name: T\n    gpu: 1\n    adopt: {pid: %d}\n    done:\n      outputs: [\"%s\"]\n"
                      "  - name: E\n    gpu: 1\n    depends_on: [T]\n    cmd: [%s]\n") % (
        child.pid, str(out).replace("\\", "/"), ", ".join('"%s"' % c.replace("\\", "/") for c in touch_cmd(tmp_path / "e.txt")))
    time.sleep(0.05)
    cfg_path.write_text(second, encoding="utf-8")
    os.utime(str(cfg_path), (time.time() + 5, time.time() + 5))
    chain.step()
    assert chain.state["T"]["state"] == "running" and chain.state["T"]["adopted"] and chain.state["T"]["pid"] == child.pid
    assert "failed" not in kinds(tmp_path, "T")
    assert chain.run() == 0
    assert chain.state["T"]["state"] == "done" and chain.state["E"]["state"] == "done" and child.wait() == 0


def test_reset_file_puts_a_failed_job_and_its_blocked_followers_back_to_pending_without_a_restart(tmp_path):
    flag = tmp_path / "ok.txt"
    ok = py("import sys,os;sys.exit(0 if os.path.exists(r'%s') else 1)" % str(flag).replace("\\", "/"))
    jobs = [{"name": "A", "gpu": 0, "cmd": ok, "retries": 0},
            {"name": "B", "gpu": 0, "depends_on": ["A"], "cmd": touch_cmd(tmp_path / "b.txt"), "done": {"outputs": [str(tmp_path / "b.txt")]}},
            {"name": "C", "gpu": 1, "cmd": py("import time;time.sleep(5)"), "retries": 0}]
    chain, _ = make(tmp_path, jobs)

    for _ in range(40):
        chain.step()
        time.sleep(0.03)

        if chain.state["A"]["state"] == "failed":
            break

    chain.step()
    assert chain.state["A"]["state"] == "failed" and chain.state["B"]["state"] == "blocked"
    flag.write_text("x", encoding="utf-8")                                              # 이제 A 는 성공할 수 있다
    (tmp_path / "state" / "chain.reset").write_text("A, nope" + chr(10) + "C" + chr(10), encoding="utf-8")
    chain.step()
    assert not (tmp_path / "state" / "chain.reset").exists()                                # 읽은 파일은 지운다
    assert chain.state["A"]["state"] in ("pending", "running", "done") and chain.state["B"]["state"] in ("pending", "running", "done")
    detail = [e["detail"] for e in events(tmp_path) if e["event"] == "reset"][-1]
    assert "모르는 이름 nope" in detail and "A" in detail and "B" in detail
    assert chain.state["C"]["state"] == "running" and "C" in detail.split("돌고 있어 건너뜀")[-1]     # 돌고 있는 작업은 건드리지 않는다
    for _ in range(200):
        chain.step()
        time.sleep(0.03)

        if chain.state["B"]["state"] == "done":
            break

    assert chain.state["A"]["state"] == "done" and chain.state["B"]["state"] == "done"


def test_cancelled_jobs_are_never_relaunched_or_retried_and_block_their_followers(tmp_path):
    """사람이 멈춘 판을 사슬이 «재시도» 로 되살린 사고(10/21 14:38)를 막는다: cancel 표시 파일 · yaml cancelled 둘 다."""
    child = subprocess.Popen(py("import time;time.sleep(0.4)"))
    relaunch = tmp_path / "relaunched.txt"
    jobs = [{"name": "T", "gpu": 0, "adopt": {"pid": child.pid}, "retry": {"cmd": touch_cmd(relaunch)}, "done": {"outputs": [str(tmp_path / "never.pt")]}},
            {"name": "E", "gpu": 0, "depends_on": ["T"], "cmd": touch_cmd(tmp_path / "e.txt")},
            {"name": "Y", "gpu": 1, "cmd": touch_cmd(tmp_path / "y.txt"), "cancelled": True},
            {"name": "Z", "gpu": 1, "depends_on": ["Y"], "cmd": touch_cmd(tmp_path / "z.txt")}]
    chain, _ = make(tmp_path, jobs)
    (tmp_path / "state" / "cancel").mkdir(parents=True)
    (tmp_path / "state" / "cancel" / "T").write_text("x", encoding="utf-8")                     # 파일 방식
    assert chain.run() == 1                                                                      # 취소 · 막힘만 있고 done 아닌 것이 있어 1
    assert chain.state["T"]["state"] == "cancelled" and chain.state["Y"]["state"] == "cancelled"  # 돌고 있던 T 는 끝나자 취소로, yaml 방식 Y 는 안 띄움
    assert chain.state["E"]["state"] == "blocked" and chain.state["Z"]["state"] == "blocked"
    assert not relaunch.exists() and not (tmp_path / "y.txt").exists() and not (tmp_path / "e.txt").exists()
    assert "relaunched" not in kinds(tmp_path, "T") and "launched" not in kinds(tmp_path, "Y")


def make_tg(tmp_path, jobs, fail_first=0, **cfg):
    sent = []
    state = {"fails": fail_first}

    def sender(text):
        if state["fails"] > 0:
            state["fails"] -= 1

            return False

        sent.append(text)

        return True

    config = {"poll_s": 0.02, "start_gap_s": 0.0, "gpus": [0, 1], "jobs": jobs}
    config.update(cfg)
    chain = runner.Chain(config, str(tmp_path / "state"), notifier=Notes(), sleep=time.sleep, repo_root=REPO, tg_sender=sender)

    return chain, sent


def test_telegram_message_has_title_purpose_next_escapes_html_and_retries_without_real_sending(tmp_path):
    out = tmp_path / "a.txt"
    jobs = [{"name": "A", "gpu": 0, "cmd": touch_cmd(out), "done": {"outputs": [str(out)]}, "max_iterations": 1501,
             "title": "G0 <열린> 진단 & 비교", "purpose": "a < b & c > d 를 본다", "next": "통과 -> 영상, 미통과 -> 원인"}]
    chain, sent = make_tg(tmp_path, jobs, fail_first=2)                                 # 처음 두 번은 보내기 실패
    assert chain.run() == 0
    chain._tg_flush()
    chain._tg_flush()
    chain._tg_flush()
    texts = "\n".join(sent)
    assert "[FOOTHOLD 실험] 띄움 G0 &lt;열린&gt; 진단 &amp; 비교" in texts                      # 이스케이프
    assert "목적: a &lt; b &amp; c &gt; d 를 본다" in texts and "다음: 통과 -&gt; 영상, 미통과 -&gt; 원인" in texts
    assert "GPU 0 · 시작 " in texts and "진행 ?/1501" in texts
    assert texts.index("띄움") < texts.index("끝")                                       # 순서 유지 · 실패한 것도 결국 간다
    assert "[FOOTHOLD 실험] 끝 " in texts and not chain.tg_queue


def test_telegram_gives_up_after_the_attempt_limit_and_job_without_title_sends_nothing(tmp_path):
    out = tmp_path / "a.txt"
    jobs = [{"name": "A", "gpu": 0, "cmd": touch_cmd(out), "title": "t", "purpose": "p", "next": "n"},
            {"name": "B", "gpu": 1, "cmd": touch_cmd(tmp_path / "b.txt")}]
    chain, sent = make_tg(tmp_path, jobs, fail_first=10 ** 6)
    chain.run()

    for _ in range(runner.TG_MAX_ATTEMPTS + 2):
        chain._tg_flush()

    assert not sent and not chain.tg_queue and "tg_dropped" in kinds(tmp_path, "chain")
    chain2, sent2 = make_tg(tmp_path / "x", jobs)
    chain2.run()
    chain2._tg_flush()
    assert all("B" not in m.split("\n")[0] for m in sent2) and all("실험]" in m for m in sent2)


def test_guard_diag_jobs_must_declare_at_most_1501_iterations_and_long_training_needs_an_approval_file(tmp_path):
    flag = tmp_path / "ran.txt"
    jobs = [{"name": "diag-ok", "gpu": 0, "cmd": touch_cmd(tmp_path / "ok.txt") + ["--max_iterations", "1501"], "retries": 0},
            {"name": "diag-long", "gpu": 1, "cmd": touch_cmd(tmp_path / "long.txt") + ["--max_iterations", "3000"], "retries": 0},
            {"name": "diag-unknown", "gpu": 0, "cmd": touch_cmd(tmp_path / "unk.txt"), "retries": 0},
            {"name": "main-9000", "gpu": 1, "cmd": touch_cmd(flag), "max_iterations": 9000, "retries": 0}]
    chain, _ = make(tmp_path, jobs)

    for _ in range(40):
        chain.step()
        time.sleep(0.03)

    assert chain.state["diag-ok"]["state"] == "done"
    assert chain.state["diag-long"]["state"] == "blocked" and chain.state["diag-unknown"]["state"] == "blocked"      # 3000 회 · 회차 모름
    assert not (tmp_path / "long.txt").exists() and not (tmp_path / "unk.txt").exists()
    assert chain.state["main-9000"]["state"] == "pending" and not flag.exists()                                    # 승인 파일 없음 → 안 띄움
    assert kinds(tmp_path, "main-9000").count("guard_wait") == 1                                                    # 알림은 한 번만
    approvals = tmp_path / "state" / "approvals"
    approvals.mkdir(parents=True)
    (approvals / "main-9000.json").write_text(json.dumps({"design_commit": "abc", "approved_by": "팀장"}), encoding="utf-8")   # time 이 없다
    chain.step()
    assert chain.state["main-9000"]["state"] == "pending"
    (approvals / "main-9000.json").write_text(json.dumps({"design_commit": "abc", "approved_by": "팀장", "time": "10/21 16:00"}), encoding="utf-8")

    for _ in range(40):
        chain.step()
        time.sleep(0.03)

        if chain.state["main-9000"]["state"] == "done":
            break

    assert flag.exists() and chain.state["main-9000"]["state"] in ("running", "done")


def test_guard_verdict_file_without_the_required_fields_is_ignored_and_reported_once(tmp_path):
    verdict = tmp_path / "s1a_verdict_pass.json"
    out = tmp_path / "s1b.txt"
    jobs = [{"name": "S1B", "gpu": 0, "cmd": touch_cmd(out), "require_file": str(verdict).replace("\\", "/"), "retries": 0}]
    chain, _ = make(tmp_path, jobs)
    verdict.write_text(json.dumps({"verdict": "pass", "video_paths": ["a.mp4"]}), encoding="utf-8")                 # 칸이 모자람
    for _ in range(6):
        chain.step()
        time.sleep(0.03)

    assert chain.state["S1B"]["state"] == "pending" and not out.exists()
    assert kinds(tmp_path, "chain").count("verdict_invalid") == 1
    verdict.write_text(json.dumps({"verdict": "pass", "video_paths": ["a.mp4"], "watched_by": "lead", "checklist": {"a": 1},
                                   "card_path": "EXP-X.md"}), encoding="utf-8")

    for _ in range(40):
        chain.step()
        time.sleep(0.03)

        if chain.state["S1B"]["state"] == "done":
            break

    assert out.exists()
