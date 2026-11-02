"""SONNET-X25h: run_sb_eval.sh 의 TASK · MODES, B1500 기준선 실행기, 죽은 학습을 알아채는 사슬(post_train_eval2.sh). CPU 만, Kit 없음."""

import os
import shutil
import subprocess
import time

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "foothold_s2/eval"
RUN_SH, CHAIN2_SH, BASE_SH = EVAL / "run_sb_eval.sh", EVAL / "post_train_eval2.sh", EVAL / "baseline_b1500.sh"
BASH = r"C:\Program Files\Git\bin\bash.exe"
SB_ID, B_ID = "FootholdS2-Go2-S2-SB-v0", "FootholdS2-Go2-S2-23f-B-v0"


_SPAWNED = []


def _spawn(cmd, **kw):
    """Popen 한 뒤 목록에 올린다. 시험이 끝나면 아래 fixture 가 자식 셸까지 통째로 끈다(Git Bash 는 런처 아래 진짜 bash 를 두어, 런처만 죽이면 진짜 bash 가 고아로 남는다)."""
    proc = subprocess.Popen(cmd, **kw)
    _SPAWNED.append(proc)

    return proc


@pytest.fixture(autouse=True)
def _kill_spawned_shells():
    yield
    while _SPAWNED:
        proc = _SPAWNED.pop()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=60)
        try:
            proc.wait(timeout=15)
        except Exception:
            pass


def _bash(path):
    p = str(path).replace("\\", "/")

    return "/" + p[0].lower() + p[2:] if len(p) > 1 and p[1] == ":" else p


def _tree(tmp_path, script, stub_name, stub_body):
    d = tmp_path / "foothold_s2" / "eval"
    d.mkdir(parents=True)
    shutil.copy(script, d / script.name)
    (d / stub_name).write_text(stub_body, encoding="utf-8", newline="\n")

    return d / script.name


KIT_STUB = (
    '#!/usr/bin/env bash\nOUT="$1"; shift\nmkdir -p "$OUT"\n'
    'echo "$MODULE $*" >> "$(dirname "$OUT")/kit_calls.txt"\n'
    'echo TURNPROBE_DONE > "$OUT/run.log"\necho {} > "$OUT/map_modes.json"\n'
)
RUN_STUB = '#!/usr/bin/env bash\nmkdir -p "$3"\necho "$2 task=${TASK:-} modes=[$MODES]" >> "$(dirname "$3")/calls.txt"\necho "map64 rc=0" > "$3/rc.txt"\n'


def test_run_sb_eval_uses_task_and_modes_from_the_environment(tmp_path):
    sh = _tree(tmp_path, RUN_SH, "run_kit.sh", KIT_STUB)
    ck = tmp_path / "model_1500.pt"
    ck.write_bytes(b"x")
    subprocess.run([BASH, _bash(sh), "cuda:0", _bash(ck), _bash(tmp_path / "out_default")], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    calls = (tmp_path / "out_default" / "kit_calls.txt").read_text(encoding="utf-8").splitlines()

    assert len(calls) == 4 and all(SB_ID in c for c in calls)                       # S-B task, turn16 세 모드 + map64 한 번
    assert "--map-mode eval_gt" in calls[0] and "--map-mode probe_prop_only" in calls[1]
    assert "--map-mode eval_pred" in calls[2] and "--modes eval_gt,probe_prop_only,eval_pred" in calls[3]
    assert "--command-suite extended" in calls[3]
    out2 = tmp_path / "out_b"
    env = dict(os.environ, TASK=B_ID, MODES="eval_gt probe_prop_only eval_pred")
    subprocess.run([BASH, _bash(sh), "cuda:0", _bash(ck), _bash(out2)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60, env=env)
    calls = (out2 / "kit_calls.txt").read_text(encoding="utf-8").splitlines()

    assert len(calls) == 4 and all(B_ID in c and SB_ID not in c for c in calls)
    assert "--map-mode eval_pred" in calls[2] and "--modes eval_gt,probe_prop_only,eval_pred" in calls[3]
    assert (out2 / "turn16_eval_pred").is_dir() and "없음" not in (out2 / "rc.txt").read_text(encoding="utf-8")


def _args(sh, ck, out, rc_file, log):
    return [BASH, _bash(sh), "cuda:1", _bash(ck), _bash(out), _bash(rc_file), _bash(log)]


def test_scripts_shape():
    s = CHAIN2_SH.read_text(encoding="utf-8")

    for p in (CHAIN2_SH, BASE_SH):
        assert b"\r" not in p.read_bytes()
        assert subprocess.run([BASH, "-n", str(p)], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30).returncode == 0
    for must in ("TRAIN_DEAD", "DEAD_SECONDS", "seq 100 100 1500", "seq 50 100 1450", "MODES_1500", "train_dead=", 'TRAIN_LOG="$5"', "catch { 'ERR' }", "0) return 1", "*) return 0"):
        assert must in s, must
    assert "[/\\" not in s                                                          # 역슬래시 문자 모임은 셸 따옴표에서 깨져 정규식 오류가 되었다
    assert "\ncd " not in s and "\ncd " not in BASE_SH.read_text(encoding="utf-8")


def test_the_real_process_probe_counts_a_live_python_and_survives_a_bad_regex():
    """실제 powershell 로 센다: 이 시험 자신이 python.exe 이므로 'python' 은 1 이상, 없는 이름은 정확히 0, 깨진 정규식은 ERR(= 죽음으로 읽지 않음)."""
    def count(pattern):
        cmd = "try { @(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match '%s' }).Count } catch { 'ERR' }" % pattern

        return subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60).stdout.strip()

    assert int(count("python")) >= 1 and count("ZZ_no_such_process_ZZ") == "0" and count("a[b") == "ERR"


def test_chain2_dead_training_without_rc_evaluates_saved_checkpoints_and_ends(tmp_path):
    sh = _tree(tmp_path, CHAIN2_SH, "run_sb_eval.sh", RUN_STUB)
    ck = tmp_path / "ck"
    ck.mkdir()
    for n in (50, 100, 1500):
        (ck / ("model_%d.pt" % n)).write_bytes(b"x")
    log = tmp_path / "run.log"
    log.write_text("x", encoding="utf-8")
    os.utime(log, (1700000000, 1700000000))                                         # 오래전에 멈춘 로그
    out = tmp_path / "out"
    env = dict(os.environ, POLL_SECONDS="1", DEAD_SECONDS="60", TRAIN_PROC_PATTERN="ZZ_no_such_process_ZZ")
    subprocess.run(_args(sh, ck, out, tmp_path / "no_rc.txt", log), capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=90, env=env)
    chain = (out / "chain.log").read_text(encoding="utf-8")
    done = (out / "DONE").read_text(encoding="utf-8")
    calls = (out / "calls.txt").read_text(encoding="utf-8").splitlines()

    assert "TRAIN_DEAD" in chain and done.startswith("DONE ok=3") and "train_dead=1" in done
    assert [Path(c.split()[0]).name for c in calls] == ["model_100.pt", "model_1500.pt", "model_50.pt"]
    assert "modes=[eval_gt probe_prop_only eval_pred]" in calls[1] and "modes=[eval_gt probe_prop_only]" in calls[0]       # m1500 에만 배포 모드를 더한다


def test_chain2_keeps_waiting_while_a_training_python_is_alive_even_if_the_log_is_old(tmp_path):
    sh = _tree(tmp_path, CHAIN2_SH, "run_sb_eval.sh", RUN_STUB)
    ck = tmp_path / "ck"
    ck.mkdir()
    (ck / "model_100.pt").write_bytes(b"x")
    log = tmp_path / "run.log"
    log.write_text("x", encoding="utf-8")
    os.utime(log, (1700000000, 1700000000))
    out, rc_file = tmp_path / "out", tmp_path / "rc.txt"
    env = dict(os.environ, POLL_SECONDS="1", DEAD_SECONDS="60", TRAIN_PROC_PATTERN="python")      # 이 시험 자신이 python.exe 라서 「학습 python 있음」
    proc = _spawn(_args(sh, ck, out, rc_file, log), stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, env=env)
    time.sleep(8)

    assert proc.poll() is None and "TRAIN_DEAD" not in (out / "chain.log").read_text(encoding="utf-8")
    rc_file.write_text("rc=0\n", encoding="utf-8")
    proc.communicate(timeout=60)

    assert "train_dead=0" in (out / "DONE").read_text(encoding="utf-8")


def test_chain2_fresh_log_is_never_dead_even_without_a_python(tmp_path):
    sh = _tree(tmp_path, CHAIN2_SH, "run_sb_eval.sh", RUN_STUB)
    ck = tmp_path / "ck"
    ck.mkdir()
    log = tmp_path / "run.log"
    log.write_text("x", encoding="utf-8")                                            # 방금 쓴 로그
    out, rc_file = tmp_path / "out", tmp_path / "rc.txt"
    env = dict(os.environ, POLL_SECONDS="1", DEAD_SECONDS="600", TRAIN_PROC_PATTERN="ZZ_no_such_process_ZZ")
    proc = _spawn(_args(sh, ck, out, rc_file, log), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, text=True, env=env)
    time.sleep(4)

    assert proc.poll() is None                                                  # 정리는 fixture 가 자식 셸까지 한다

    assert "TRAIN_DEAD" not in (out / "chain.log").read_text(encoding="utf-8")


def test_baseline_b1500_waits_then_measures_task_b_twice_with_three_modes(tmp_path):
    sh = _tree(tmp_path, BASE_SH, "run_sb_eval.sh", RUN_STUB)
    ck = tmp_path / "b1500.pt"
    ck.write_bytes(b"x")
    out, rc_file = tmp_path / "out", tmp_path / "wait_rc.txt"
    env = dict(os.environ, POLL_SECONDS="1", B_CK=_bash(ck))
    proc = _spawn([BASH, _bash(sh), "cuda:0", _bash(out), _bash(rc_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, env=env)
    time.sleep(3)

    assert proc.poll() is None and not (out / "calls.txt").exists()
    rc_file.write_text("rc=0\n", encoding="utf-8")
    proc.communicate(timeout=60)
    calls = (out / "calls.txt").read_text(encoding="utf-8").splitlines()

    assert len(calls) == 2 and all("task=%s" % B_ID in c and "modes=[eval_gt probe_prop_only eval_pred]" in c for c in calls)
    assert (out / "rep1" / "CHAIN_ITEM_DONE").exists() and (out / "rep2" / "CHAIN_ITEM_DONE").exists() and (out / "DONE").read_text(encoding="utf-8").startswith("DONE ok=2 fail=0")
