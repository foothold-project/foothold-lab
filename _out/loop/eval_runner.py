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

평가 장치는 결과를 바꾸지 «않는다» (2026-09-23 실측)
    처음에 「`v2b` 를 잰 장치에 맞춰야 한다」고 잡았는데 **근거 없이 조심한
    것이었다.** 팀장이 물었고 재 보니 아니었다.

    같은 체크포인트(`v2b` model_3000)를 `cuda:0` 에서 다시 평가해
    기존 `cuda:1` 결과와 견줬다. **48 칸 중 다른 칸이 0 개다.**

    까닭은 분명하다. 평가는 정책이 «고정» 이고 되먹임이 없다.
    학습은 자기가 만든 데이터로 자기를 고치는 고리라 아주 작은 차이가
    1000 판에 걸쳐 86 배로 증폭되지만, 평가에는 그런 증폭이 없다.

    그래서 장치 배정은 이제 **처리량만 보고 정한다.** 축 1 을 `cuda:1`,
    축 2 를 `cuda:0` 에 두는 것은 두 GPU 를 같이 쓰려는 것뿐이다.

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

# 어느 체크포인트를 평가하나.
#
# 기본은 v2 계보와 «같은 네 점» 이다. 판정 관문(`verdict.py:41`)이 이 넷을 보므로
# 기본값을 바꾸면 관문의 뜻이 바뀐다. 그래서 여기서 기본을 안 바꾼다.
#
# 처음부터 학습하는 판은 4500 까지 간다. 그 뒤쪽을 «보고용» 으로 더 재려면
# 환경 변수로 준다. 관문은 그대로 넷을 본다.
#
#     FOOTHOLD_EVAL_CKPTS=1500,2000,2500,3000,4500
#
# 근거: 2026-09-28 · 팀장 지시로 fs1·fs2 가 4500 판을 돈다. 박아 둔 넷만 보면
#       4500 이 평가되지 않는다 (`eval_runner.py` 옛 55 행).
def _ckpts_from_env():
    raw = os.environ.get("FOOTHOLD_EVAL_CKPTS", "").strip()
    if not raw:
        return (1500, 2000, 2500, 3000)
    try:
        vals = tuple(int(x) for x in raw.replace(" ", "").split(",") if x)
    except ValueError:
        raise SystemExit("FOOTHOLD_EVAL_CKPTS 를 못 읽었다: %r" % raw)
    if not vals:
        raise SystemExit("FOOTHOLD_EVAL_CKPTS 가 비었다")
    if sorted(vals) != list(vals):
        raise SystemExit("FOOTHOLD_EVAL_CKPTS 가 오름차순이 아니다: %r" % (vals,))
    return vals


CKPTS = _ckpts_from_env()

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


def running_trainers() -> dict:
    """**실제로 도는** 학습이 쓰는 장치 -> 실행 이름. 없으면 빈 딕셔너리.

    `--device` 를 읽는다. `--run_name` 이 있는 python 프로세스만 학습이다.
    평가에는 `--run_name` 이 없다.
    """
    out = {}
    try:
        txt = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "ForEach-Object { if ($_.CommandLine -match '--run_name\\s+(\\S+)') "
             "{ $n=$Matches[1]; $d='?'; "
             "if ($_.CommandLine -match '--device\\s+(\\S+)') { $d=$Matches[1] }; "
             "\"$d|$n\" } }"],
            capture_output=True, text=True, timeout=45).stdout
    except Exception as exc:                                   # noqa: BLE001
        # **못 읽으면 「바쁘다」고 «보수적으로» 본다.** 한 GPU 에 둘을 올리지 않는다.
        log("도는 학습을 못 읽었다. 두 GPU 를 «바쁘다» 고 본다: %s" % exc)
        return {"cuda:0": "확인 실패", "cuda:1": "확인 실패"}
    for ln in txt.splitlines():
        if "|" in ln:
            dev, name = ln.strip().split("|", 1)
            if dev.startswith("cuda"):
                out[dev] = name
    return out


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


def preflight(job: dict) -> str | None:
    """걸기 «전에» 막을 것. 없으면 None.

    2026-09-23 · 축 2 네 건을 띄웠다가 네 번 다 즉시 죽었다. 하네스 파일이
    이 브랜치에 «없었다» (PR #444 에만 있다). 프로세스를 띄워 보고 알 것이
    아니라 **걸기 전에** 알아야 한다. 3 차 감사의 1 단계 preflight 다.
    """
    script = os.path.join(REPO, job["argv"][0].replace("/", os.sep))
    if not os.path.isfile(script):
        return "하네스가 없다: %s" % job["argv"][0]
    ck = None
    for i, a in enumerate(job["argv"]):
        if a == "--checkpoint":
            ck = job["argv"][i + 1]
    if ck and not os.path.isfile(ck):
        return "체크포인트가 없다: %s" % ck
    return None


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
    # **장치를 손으로 정할 수 있게 한다 (2026-09-26).**
    # 한 GPU 에 예상 못 한 학습이 돌면 그 축이 «영구히» 미뤄진다.
    # 학습을 죽이는 것보다 빈 GPU 로 평가를 돌리는 것이 안전하다.
    # 평가 장치는 결과를 바꾸지 않는다 (48 칸 4800 행이 0 개 다름, 2026-09-23).
    ap.add_argument("--axis1-device", default=None,
                    help="축 1 을 이 장치에서 돈다 (예: cuda:0)")
    ap.add_argument("--axis2-device", default=None,
                    help="축 2 를 이 장치에서 돈다")
    args = ap.parse_args()

    # 전역 상수를 «바꿔서» jobs_for 가 그것을 쓰게 한다. 인자를 실어 나르지 않는다.
    global AXIS1_DEVICE, AXIS2_DEVICE
    if args.axis1_device:
        log("축 1 장치를 손으로 정했다: %s -> %s" % (AXIS1_DEVICE, args.axis1_device))
        AXIS1_DEVICE = args.axis1_device
    if args.axis2_device:
        log("축 2 장치를 손으로 정했다: %s -> %s" % (AXIS2_DEVICE, args.axis2_device))
        AXIS2_DEVICE = args.axis2_device

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
        # **「완료」인데 평가할 «까닭이 없는» 판 (2026-09-26).**
        # status 를 「취소」로 바꿔 막으면 사실이 아닌 상태가 기록에 남는다.
        # 그 판들은 취소된 것이 아니라 완료다. 까닭을 따로 적는다.
        if run.get("skip_eval"):
            log("%s 는 평가를 건너뛴다 · %s" % (run["name"], run["skip_eval"]))
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
    # **선언이 아니라 «실제로 도는 프로세스» 에서 읽는다 (2026-09-26).**
    #
    # 전에는 `waiting`(선언됐고 아직 안 끝난 판) 에서 만들었다. 그래서
    # 죽거나 «잘못 판정된» 판이 그 GPU 를 영구히 잠갔다. 2026-09-26 에
    # 축 1 48 건이 전부 「미룸」이 됐고, 원인은 완주한 판을 내 사슬이
    # 완주하지 않았다고 본 것이었다. 그리고 gpu 가 「미기재」인 옛 판이
    # busy["미기재"] 라는 쓰레기 칸을 만들었다.
    #
    # 선언은 틀릴 수 있고 프로세스는 틀리지 않는다.
    busy = running_trainers()
    if busy:
        log("학습이 «실제로» 쓰는 GPU: "
            + " · ".join("%s(%s)" % (d, n) for d, n in sorted(busy.items())))
    else:
        log("도는 학습이 없다. 두 GPU 를 다 쓴다")

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
            bad = preflight(job)
            if bad:
                log("  «걸지 않음» %s · %s" % (job["out"], bad))
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
