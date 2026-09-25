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
# watchdog 과 «같은» 모양을 쓴다. 2026-09-24 에 앞 꼬리를 빼먹어
# 첫 줄을 놓친 적이 있다.
GPU_ROW = re.compile(r"^(?:GPU\s+)?(\d+),\s*(\d+)\s*%,\s*(\d+)\s*MiB$")


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


def evals() -> dict:
    """도는 평가와 산출물 진행. **학습이 없어도 이것은 본다.**

    2026-09-25 · heartbeat 가 `--run_name` 있는 프로세스만 세서 평가를
    «못 봤다». 평가 56 건이 한 시간 반 돌고 끝나도 알림이 없었다.
    팀장이 손으로 물어야 알았다.
    """
    out = {"procs": 0, "runs": {}}
    try:
        txt = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "ForEach-Object { if ($_.CommandLine -match "
             "'eval_(generalization|command_response)') { 'E' } }"],
            capture_output=True, text=True, timeout=45).stdout
        out["procs"] = sum(1 for l in txt.splitlines() if l.strip() == "E")
    except Exception:                                          # noqa: BLE001
        pass

    # 상태 파일에 «완료» 로 적힌 판마다 산출물을 센다.
    try:
        with io.open(os.path.join(HERE, "state.json"), encoding="utf-8") as h:
            state = json.load(h)
    except Exception:                                          # noqa: BLE001
        return out
    a1root = os.path.join(REPO, "sim", "eval", "results", "20260923-v2rs")
    a2root = os.path.join(REPO, "sim", "eval", "results", "20260923-v2rs-axis2")
    for r in state.get("running") or []:
        if (r.get("status") or "").strip() != "완료":
            continue
        nm = r.get("name") or ""
        a1 = len(glob.glob(os.path.join(a1root, "%s-iter*" % nm, "*", "d0.5",
                                        "*", "generalization_summary.csv")))
        a2 = len(glob.glob(os.path.join(a2root, "%s-iter*" % nm,
                                        "probe_manifest.json")))
        if a1 or a2:
            out["runs"][nm] = (a1, a2)
    return out


def gpu() -> list[str]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20).stdout
        return [l.strip() for l in out.splitlines() if l.strip()]
    except Exception:                                          # noqa: BLE001
        return []


def idle_with_work(runs, ev) -> str:
    """**GPU 가 비었는데 할 일이 남았는가.** 비면 빈 문자열.

    2026-09-25 · v2g 와 v2n 이 밤새 끝났는데 평가가 안 걸렸고 GPU 둘이
    놀았다. 알림이 «학습만» 봐서 아무 말이 없었다. 이 칸이 그 자리다.
    """
    if runs or ev.get("procs"):
        return ""                      # 뭔가 돌고 있다
    g = gpu()
    busy = 0
    for row in g:
        m = GPU_ROW.match(row.strip())
        if m and (int(m.group(2)) > 20 or int(m.group(3)) > 2000):
            busy += 1
    if busy:
        return ""
    # 아무것도 안 돌고 GPU 도 비었다. 할 일이 남았나.
    pending = [nm for nm, (a1, a2) in (ev.get("runs") or {}).items()
               if a1 < 24 or a2 < 4]
    if pending:
        return ("평가가 덜 끝났는데 아무것도 안 돕니다: "
                + " · ".join(sorted(pending)))
    return "GPU 둘이 비었고 도는 것이 «하나도» 없습니다"


def already_told() -> set:
    """이미 「끝났다」고 알린 판. **도배를 막는다.**"""
    try:
        with io.open(STATE, encoding="utf-8") as h:
            return set(json.load(h).get("eval_done_told") or [])
    except Exception:                                          # noqa: BLE001
        return set()


def build() -> tuple[str, bool, list]:
    """(본문, 급한가, 새로 끝난 판 목록). 본문이 비면 안 보낸다."""
    runs = running()
    ev = evals()
    told = already_told()
    fresh = []
    # **학습이 없어도 평가가 있으면 보낸다.** 여기가 조용해서 사람이 손으로 물었다.
    if not runs and not ev["procs"] and not ev["runs"]:
        return ("", False, [])

    urgent = False
    lines = ["[진행] %s" % dt.datetime.now().strftime("%m/%d %H:%M"), ""]
    if not runs:
        lines.append("도는 학습 없음")
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

    # 평가 절 · 끝난 것과 도는 것을 나눠 적는다
    if ev["runs"] or ev["procs"]:
        lines += ["", "평가  (도는 프로세스 %d 개)" % ev["procs"]]
        for nm, (a1, a2) in sorted(ev["runs"].items()):
            done = (a1 >= 24 and a2 >= 4)
            mark = ""
            if done:
                mark = "   << 끝났다 (새로)" if nm not in told else "   << 끝남"
            lines.append("  %-18s 축1 %2d/24  축2 %d/4%s"
                         % (nm, a1, a2, mark))
            # **새로 끝난 평가만 «급함» 으로 올린다.** 다음 칸이 판정이기 때문이다.
            # 이미 알린 것을 매번 급함으로 하면 20 분마다 알림이 온다.
            if done and nm not in told:
                urgent = True
                fresh.append(nm)

    # **GPU 가 놀면 알린다.** 팀장이 「GPU 가 놀지 않게」를 여러 번 지시했다.
    idle = idle_with_work(runs, ev)
    if idle:
        lines += ["", "** %s **" % idle]
        urgent = True
        fresh.append("GPU 유휴")

    g = gpu()
    if g:
        lines += ["", "GPU"] + ["  " + x for x in g]
    if not urgent:
        lines += ["", "문제 없습니다."]
    if fresh:
        lines += ["", "**평가가 끝났습니다. 다음 칸은 판정입니다** · "
                      + " · ".join(fresh)]
    return ("\n".join(lines), urgent, fresh)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    body, urgent, fresh = build()
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
    # **급하지 않으면 여섯 시간에 한 번만.** 팀장 지시 (2026-09-25) ·
    # 「달라진 점이 없거나 굳이 보고하지 않아도 되면 안 해도 된다」.
    # 알릴 일은 급함으로 즉시 나가므로 이 줄이 정보를 막지 않는다.
    if not urgent and now - last < 21600:
        print("급한 일이 없고 여섯 시간이 안 됐다. 안 보낸다")
        return 0

    from tg import send
    ok = send(body)
    with io.open(STATE, "w", encoding="utf-8") as h:
        h.write(json.dumps({"last": now, "urgent": urgent,
                            "eval_done_told": sorted(already_told() | set(fresh))},
                           ensure_ascii=False))
    print("보냄:", ok, "· 급함:", urgent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
