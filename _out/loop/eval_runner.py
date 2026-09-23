# -*- coding: utf-8 -*-
"""루프의 «거는» 절반 · 평가만 겁니다.

분류: 운영
작성: 오흥재 · 2026-09-23
근거: `20260921-v2ab` 의 `run_manifest.json` 48 개에서 읽은 실행 인자 ·
      `20260921-v2ab-axis2` 의 `probe_manifest.json` · `LOOP-RUNTIME.md` 8 절 5 번
요지: 학습이 끝난 판의 체크포인트 넷을 두 축으로 잰다.
      **학습은 절대 걸지 않는다.** 평가만 건다.
상태: 초안
판: v1.0

왜 평가만 거는가
    잘못 걸었을 때 잃는 것이 다르다. 학습은 세 시간이고 같은 이름의 결과가
    둘 생기면 어느 것이 무엇인지 알 수 없게 된다. 평가는 수 분이고
    같은 입력에서 같은 자리에 덮어쓸 뿐이다.

왜 축 1 은 cuda:1 이고 축 2 는 cuda:0 인가
    **`v2b` 를 잰 것과 같은 장치에 맞춘 것이다.** 실행 기록을 세어 보니
    `v2a` 평가 24 건이 전부 `cuda:0`, `v2b` 평가 24 건이 전부 `cuda:1` 이었다.
    무작위로 흩어진 것이 아니라 정책별로 갈려 있었다.
    지금 재는 `v2b-r` 과 `v2b-s` 는 **`v2b` 와 비교** 하므로 `v2b` 쪽에 맞춘다.
    평가 장치를 바꾸면 우리가 찾으려는 작은 차이에 변수가 하나 더 붙는다.

돌리는 법
    python _out/loop/eval_runner.py --dry-run     무엇을 돌릴지만 본다
    python _out/loop/eval_runner.py               실제로 돈다
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
STATE = os.path.join(HERE, "state.json")
LOG = os.path.join(HERE, "eval_runner.log")
LOCK = os.path.join(HERE, "eval_runner.lock")

PYTHON = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe"
CKPTS = (1500, 2000, 2500, 3000)

# 축 1 · 실행 기록에서 그대로 읽은 값. 속도마다 평가창이 다르다.
# 명령 거리 6 m 를 맞추려고 12 · 6 · 4 초다. 20 초는 인자 기본값이지 우리 값이 아니다.
AXIS1_SPEEDS = (
    ("0.5", "12.0"),
    ("1.0", "6.0"),
    ("1.5", "4.0"),
)
AXIS1_SETS = ("rough6", "unseen10")
AXIS1_DEVICE = "cuda:1"      # v2b 를 잰 장치
AXIS2_DEVICE = "cuda:0"

OUT_AXIS1 = "sim/eval/results/20260923-v2rs"
OUT_AXIS2 = "sim/eval/results/20260923-v2rs-axis2"

_log_lock = threading.Lock()


def log(msg: str) -> None:
    line = "%s  %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    with _log_lock:
        with io.open(LOG, "a", encoding="utf-8") as handle:
            handle.write(line)
        sys.stdout.write(line)
        sys.stdout.flush()


# --------------------------------------------------------------------------
# 학습이 «정말» 끝났는지


def training_done(run: dict) -> tuple[bool, str]:
    """(끝났나, 까닭). **파일 하나만 보고 끝났다고 하지 않는다.**

    프로세스가 살아 있는데 마지막 체크포인트가 있을 수도 있고(저장 직후),
    프로세스가 죽었는데 체크포인트가 없을 수도 있다(중간에 터짐).
    둘을 다 본다.
    """
    d = run_dir(run)
    if d is None:
        return (False, "실행 폴더를 못 찾는다")
    last = os.path.join(d, "model_%d.pt" % CKPTS[-1])
    if not os.path.isfile(last):
        return (False, "model_%d.pt 가 없다" % CKPTS[-1])
    if pid_alive(run.get("pid")):
        return (False, "PID %s 가 아직 살아 있다" % run.get("pid"))
    missing = [c for c in CKPTS
               if not os.path.isfile(os.path.join(d, "model_%d.pt" % c))]
    if missing:
        return (False, "체크포인트가 빈다: %s" % missing)
    return (True, "체크포인트 넷이 있고 프로세스가 끝났다")


def pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "if (Get-Process -Id %d -ErrorAction SilentlyContinue) "
             "{ 'yes' } else { 'no' }" % int(pid)],
            capture_output=True, text=True, timeout=30).stdout
        return "yes" in out
    except Exception as exc:                                   # noqa: BLE001
        log("PID 확인 실패 · 살아 있다고 «보수적으로» 본다: %s" % exc)
        return True


def run_dir(run: dict):
    pat = run.get("out_dir") or ""
    base, tail = os.path.split(pat)
    if "*" not in tail or not os.path.isdir(base):
        return base if os.path.isdir(base) else None
    suffix = tail.lstrip("*")
    hits = sorted(n for n in os.listdir(base) if n.endswith(suffix))
    return os.path.join(base, hits[-1]) if hits else None


# --------------------------------------------------------------------------
# 할 일 목록


def jobs_for(run: dict) -> list[dict]:
    d = run_dir(run)
    name = run["name"]
    out = []
    for c in CKPTS:
        ckpt = os.path.join(d, "model_%d.pt" % c).replace("\\", "/")
        tag = "%s-iter%d" % (name, c)
        for ts in AXIS1_SETS:
            for vx, dur in AXIS1_SPEEDS:
                odir = "%s/%s/%s/d0.5/v%s" % (OUT_AXIS1, tag, ts, vx)
                out.append({
                    "axis": 1, "tag": tag, "device": AXIS1_DEVICE, "out": odir,
                    "argv": ["sim/eval/eval_generalization.py",
                             "--checkpoint", ckpt,
                             "--terrain_set", ts, "--terrains", "all",
                             "--difficulty", "0.5",
                             "--episodes", "100", "--envs_per_terrain", "10",
                             "--command_vx", vx, "--eval_duration", dur,
                             "--min_progress_m", "3.0",
                             "--max_lateral_drift", "0.75",
                             "--seed", "42", "--headless",
                             "--device", AXIS1_DEVICE,
                             "--output_dir", odir],
                    "done_marker": odir + "/generalization_summary.csv",
                })
        odir2 = "%s/%s" % (OUT_AXIS2, tag)
        out.append({
            "axis": 2, "tag": tag, "device": AXIS2_DEVICE, "out": odir2,
            "argv": ["sim/eval/eval_command_response.py",
                     "--checkpoint", ckpt,
                     "--label", tag,
                     "--scenario", "all",
                     "--num_envs", "64",
                     "--seed", "42",
                     "--output_dir", odir2],
            "done_marker": odir2 + "/probe_manifest.json",
        })
    return out


# --------------------------------------------------------------------------
# 한 건 실행


def run_job(job: dict) -> int:
    odir = os.path.join(REPO, job["out"].replace("/", os.sep))
    os.makedirs(odir, exist_ok=True)

    argv = [PYTHON] + job["argv"]
    # 규칙 7 · 실행 명령을 결과 폴더에 «파일로» 남긴다.
    # 무엇으로 돌렸는지가 사람 기억에만 있으면 재현을 못 한다.
    with io.open(os.path.join(odir, "command.txt"), "w", encoding="utf-8") as h:
        h.write(" ".join('"%s"' % a if " " in a else a for a in argv) + "\n")
        h.write("# 걸린 때 %s\n" % dt.datetime.now().isoformat(timespec="seconds"))
        h.write("# 건 것 _out/loop/eval_runner.py\n")

    env = dict(os.environ)
    env["OMNI_KIT_ACCEPT_EULA"] = "YES"
    logfile = os.path.join(odir, "run.log")
    started = dt.datetime.now()
    with io.open(logfile, "w", encoding="utf-8", errors="replace") as h:
        proc = subprocess.Popen(argv, cwd=REPO, env=env,
                                stdout=h, stderr=subprocess.STDOUT)
        code = proc.wait()
    mins = (dt.datetime.now() - started).total_seconds() / 60
    ok = code == 0 and os.path.isfile(os.path.join(REPO, job["done_marker"]))
    log("  %s 축%d %s · %.1f 분 · exit=%d · %s"
        % (job["tag"], job["axis"], job["device"], mins, code,
           "산출물 있음" if ok else "«산출물 없음»"))
    return 0 if ok else 1


def worker(device: str, queue: list, results: dict) -> None:
    for job in queue:
        results[job["out"]] = run_job(job)


# --------------------------------------------------------------------------


def take_lock() -> bool:
    """두 번 도는 것을 막는다. 감시 스크립트가 10 분마다 깨우기 때문이다."""
    if os.path.isfile(LOCK):
        try:
            with io.open(LOCK, encoding="utf-8") as h:
                old = int((h.read().split() or ["0"])[0])
        except Exception:                                      # noqa: BLE001
            old = 0
        if old and pid_alive(old):
            log("이미 %d 번이 돌고 있다. 나온다" % old)
            return False
        log("죽은 잠금을 치운다 (PID %s)" % old)
    with io.open(LOCK, "w", encoding="utf-8") as h:
        h.write("%d %s\n" % (os.getpid(), dt.datetime.now().isoformat()))
    return True


def drop_lock() -> None:
    try:
        os.remove(LOCK)
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="무엇을 돌릴지만 적고 «아무것도 안 건다»")
    ap.add_argument("--force", action="store_true",
                    help="이미 산출물이 있어도 다시 돈다")
    ap.add_argument("--state", default=STATE,
                    help="다른 상태 파일로 시험할 때만 쓴다")
    args = ap.parse_args()

    with io.open(args.state, encoding="utf-8") as h:
        state = json.load(h)

    # 멈춤 사유가 있으면 아무것도 걸지 않는다. 4 차 감사 지적이다.
    # 사람이 정해야 하는 상태에서 기계가 계속 가면 그 멈춤이 무의미해진다.
    if state.get("halt_reason") and not args.dry_run:
        log("멈춤 사유가 있다. 아무것도 걸지 «않는다»: %s" % state["halt_reason"])
        return 0

    ready, waiting = [], []
    for run in state.get("running") or []:
        if (run.get("status") or "").strip() in ("죽음", "실패", "취소"):
            log("%s 는 %s 로 기록돼 있다. 평가하지 «않는다»"
                % (run["name"], run.get("status")))
            continue
        ok, why = training_done(run)
        (ready if ok else waiting).append((run, why))

    for run, why in waiting:
        log("%s 아직 · %s" % (run["name"], why))

    # **규칙을 고쳤다 (2026-09-23).** 처음에 「학습이 하나라도 돌면 평가 금지」로
    # 잡았는데 «근거 없이 과했다». 팀장이 지적했고 실측이 그것을 확인했다.
    #
    #   같은 시드 · 같은 장치의 두 학습이 «비트 동일» 하다 (최대차 0.000e+00).
    #   이웃이 있든 없든 결과가 같다. 곧 이웃 부하는 학습 결과를 «못 바꾼다».
    #
    # 그래서 막을 이유는 「학습 보호」가 아니라 **한 GPU 에 두 작업을 올리지
    # 않는 것** 하나다. 메모리와 처리량 때문이다.
    busy = {}
    for run, _why in waiting:
        dev = (run.get("gpu") or "").split()[0]
        if dev:
            busy[dev] = run["name"]
    if busy:
        log("학습이 쓰는 GPU: " + " · ".join("%s(%s)" % (d, n)
                                             for d, n in busy.items()))

    if not ready:
        log("평가할 것이 없다")
        return 0

    todo = []
    for run, why in ready:
        log("%s 준비됨 · %s" % (run["name"], why))
        for job in jobs_for(run):
            if not args.force and os.path.isfile(
                    os.path.join(REPO, job["done_marker"])):
                log("  건너뜀 (이미 있음) %s" % job["out"])
                continue
            if job["device"] in busy:
                log("  미룸 (%s 에서 %s 학습 중) %s"
                    % (job["device"], busy[job["device"]], job["out"]))
                continue
            todo.append(job)

    log("걸 것 %d 건 · 축1 %d · 축2 %d"
        % (len(todo), sum(1 for j in todo if j["axis"] == 1),
           sum(1 for j in todo if j["axis"] == 2)))

    if args.dry_run:
        for j in todo[:4]:
            log("  [예시] %s" % " ".join(j["argv"]))
        log("«--dry-run 이라 아무것도 안 걸었다»")
        return 0

    if not todo:
        return 0
    if not take_lock():
        return 0
    try:
        queues = {AXIS1_DEVICE: [j for j in todo if j["device"] == AXIS1_DEVICE],
                  AXIS2_DEVICE: [j for j in todo if j["device"] == AXIS2_DEVICE]}
        results: dict = {}
        threads = [threading.Thread(target=worker, args=(d, q, results))
                   for d, q in queues.items() if q]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        bad = [k for k, v in results.items() if v != 0]
        log("끝 · %d 건 중 실패 %d" % (len(results), len(bad)))
        for k in bad:
            log("  실패 · %s" % k)
        return 1 if bad else 0
    finally:
        drop_lock()


if __name__ == "__main__":
    sys.exit(main())
