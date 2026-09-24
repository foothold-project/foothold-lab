# -*- coding: utf-8 -*-
"""1 시간마다 팀장에게 진행을 알린다 · **문제가 없어도 보낸다.**

분류: 운영
작성: 오흥재 · 2026-09-24
근거: 팀장 요청 (2026-09-24) · `_out/loop/tg.py` · `run_gap_train.ps1` 의 로그 형식
요지: 도는 학습의 진행률·ETA 와 GPU 를 한 통에 담아 보낸다.
      이상이 보이면 «곧바로» 보낸다.
상태: 초안
판: v1.0

왜 예약 작업인가
    2026-09-24 에 `nohup ... &` 로 띄운 대기 스크립트가 부모 셸이 정리될 때
    같이 죽었다. 조건이 다 맞았는데 아무도 확인하지 않았다.
    Windows 예약 작업은 세션·재부팅과 무관하다.

무엇을 보내나
    정상   한 시간마다 한 통. 판 수 · 진행률 · ETA · GPU
    이상   즉시. 프로세스가 사라졌거나 체크포인트가 30 분째 안 늘거나
           로그에 Traceback 이 있을 때

무엇을 «안» 보내나
    학습이 하나도 안 돌면 «조용히» 있는다. 할 말이 없는데 알림을 보내면
    팀장이 알림을 끈다.

돌리는 법
    python _out/loop/heartbeat.py            보낸다
    python _out/loop/heartbeat.py --dry-run  화면에만
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
LOGDIR = r"C:\isaac\IsaacLab\logs\gap_run_logs"
RUNDIR = r"C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_gap_nvidia"
STATE = os.path.join(HERE, "heartbeat-state.json")
sys.path.insert(0, HERE)

ITER = re.compile(r"Learning iteration\s+(\d+)/(\d+)")
ETA = re.compile(r"ETA:\s*([\d:]+)")


def running() -> list[dict]:
    """도는 학습. `--run_name` 으로 무엇인지 알아낸다."""
    out = []
    try:
        txt = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "ForEach-Object { if ($_.CommandLine -match '--run_name\\s+(\\S+)') "
             "{ \"$($_.ProcessId)|$($Matches[1])\" } }"],
            capture_output=True, text=True, timeout=45).stdout
    except Exception:                                          # noqa: BLE001
        return out
    for ln in txt.splitlines():
        if "|" in ln:
            pid, name = ln.strip().split("|", 1)
            out.append({"pid": int(pid), "name": name})
    return out


def progress(name: str) -> dict:
    """그 실행의 마지막 판 수와 ETA. 로그 꼬리만 읽는다."""
    hits = sorted(glob.glob(os.path.join(LOGDIR, "*%s.log" % name)))
    if not hits:
        return {}
    p = hits[-1]
    try:
        with io.open(p, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - 60000))
            tail = h.read().decode("utf-8", "replace")
    except OSError:
        return {}
    its = ITER.findall(tail)
    etas = ETA.findall(tail)
    bad = "Traceback" in tail or "RuntimeError" in tail
    d = {"log": p, "error": bad}
    if its:
        d["it"], d["total"] = int(its[-1][0]), int(its[-1][1])
    if etas:
        d["eta"] = etas[-1]
    return d


def stale_minutes(name: str):
    hits = sorted(glob.glob(os.path.join(RUNDIR, "*%s" % name)))
    if not hits:
        return None
    newest = None
    for f in glob.glob(os.path.join(hits[-1], "model_*.pt")):
        t = os.path.getmtime(f)
        newest = t if newest is None or t > newest else newest
    if newest is None:
        return None
    return (dt.datetime.now().timestamp() - newest) / 60.0


def gpu() -> list[str]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20).stdout
        return [l.strip() for l in out.splitlines() if l.strip()]
    except Exception:                                          # noqa: BLE001
        return []


def build() -> tuple[str, bool]:
    """(본문, 급한가). 본문이 비면 안 보낸다."""
    runs = running()
    if not runs:
        return ("", False)

    urgent = False
    lines = ["[학습 진행] %s" % dt.datetime.now().strftime("%m/%d %H:%M"), ""]
    for r in runs:
        pr = progress(r["name"])
        st = stale_minutes(r["name"])
        short = r["name"].replace("20260924_", "").replace("20260923_", "")
        if pr.get("it"):
            pct = 100.0 * pr["it"] / pr["total"]
            lines.append("%s" % short)
            lines.append("  %d / %d  (%.0f %%)%s"
                         % (pr["it"], pr["total"], pct,
                            "  ETA %s" % pr["eta"] if pr.get("eta") else ""))
        else:
            lines.append("%s  (판 수를 아직 못 읽음)" % short)
        if pr.get("error"):
            lines.append("  ** 로그에 오류 흔적이 있습니다 **")
            urgent = True
        if st is not None and st > 30:
            lines.append("  ** 마지막 체크포인트가 %d 분 전입니다 **" % st)
            urgent = True

    g = gpu()
    if g:
        lines += ["", "GPU"] + ["  " + x for x in g]
    if not urgent:
        lines += ["", "문제 없습니다."]
    return ("\n".join(lines), urgent)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    body, urgent = build()
    if not body:
        print("도는 학습이 없다. 안 보낸다")
        return 0
    if args.dry_run:
        print(body)
        return 0

    # 급하지 않으면 «한 시간에 한 번» 만 보낸다. 예약이 더 자주 깨워도 막는다.
    last = 0.0
    if os.path.isfile(STATE):
        try:
            with io.open(STATE, encoding="utf-8") as h:
                last = float(json.load(h).get("last", 0))
        except Exception:                                      # noqa: BLE001
            last = 0.0
    now = dt.datetime.now().timestamp()
    if not urgent and now - last < 3300:
        print("한 시간이 안 됐다. 안 보낸다")
        return 0

    from tg import send
    ok = send(body)
    with io.open(STATE, "w", encoding="utf-8") as h:
        h.write(json.dumps({"last": now, "urgent": urgent}))
    print("보냄:", ok, "· 급함:", urgent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
