"""PRIORITY_BUSY 표식 감시기. runner 우선순위 렌더 대기열이 이 파일을 본다.

돌고 있는 사슬 2판(ex35_eval_chain2.sh)은 고치지 않는다(bash 는 스크립트를 조금씩 읽는다).
대신 이 감시기가 chain2.log 의 마지막 줄을 읽어 저장본 평가 단계가 도는 동안만 표식을 만들고, 새 저장본을 기다리는 동안은 지운다.
표식 내용(JSON 한 줄): 시각 · 저장본 · 단계 · 사슬 bash PID 들 · 평가 python PID 들. 감시기 자신의 PID 도 적는다.
사슬이 죽으면 PID 가 모두 죽은 표식이 남을 수 있으므로 runner 는 죽은 PID 표식을 무시한다. 감시기도 사슬이 없으면 표식을 지운다.
"""
import argparse
import json
import os
import re
import subprocess
import time

GRACE_S = 45
TOP = "C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval"
LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) m(\d+) (\w+) (start|end)\b")


def pids(pattern):
    ps = "try { @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '%s' -and $_.ProcessId -ne %d } | ForEach-Object { $_.ProcessId }) -join ',' } catch { 'ERR' }" % (pattern, os.getpid())
    out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60).stdout.strip()

    if out == "ERR":
        return None

    return [int(x) for x in out.split(",") if x.strip().isdigit()]


def last_stage(log):
    last = None

    try:
        for ln in open(log, encoding="utf-8", errors="replace"):
            m = LINE.match(ln)

            if m:
                last = m.groups()
    except OSError:
        return None

    return last


def tick(top):
    marker = os.path.join(top, "PRIORITY_BUSY")
    chain = pids("ex35_eval_chain2\\.sh")
    st = last_stage(os.path.join(top, "chain2.log"))
    busy = bool(chain) and st is not None and (st[3] == "start" or time.time() - time.mktime(time.strptime(st[0], "%Y-%m-%d %H:%M:%S")) < GRACE_S)   # 단계 사이 틈(45 초)은 계속 바쁨

    if chain is None:                                   # 도구 오류: 있던 표식을 그대로 둔다
        return "keep"

    if not busy:
        if os.path.exists(marker):
            os.remove(marker)

        return "idle"

    child = pids("--device cuda:1( |$)") or []
    body = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "stage_start": st[0], "ckpt": "model_%s.pt" % st[1], "stage": st[2],
            "chain_pids": chain, "eval_pids": child, "watcher_pid": os.getpid()}
    tmp = marker + ".tmp"
    open(tmp, "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False) + "\n")
    os.replace(tmp, marker)

    return "busy"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", default=TOP)
    ap.add_argument("--poll", type=int, default=10)
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()

    while True:
        r = tick(a.top)

        if a.once:
            print(r)
            return

        time.sleep(a.poll)


if __name__ == "__main__":
    main()
