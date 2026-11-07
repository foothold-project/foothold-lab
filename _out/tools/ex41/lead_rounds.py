"""lead 10-minute round (팀장 11/07 12:1x 「10 분마다 체크 · 누락 없게」).

One command shows every thing the lead must act on, so a round cannot skip a worker:
  - each worker window: busy or idle, idle since when, the last report line it printed
  - each worker's open WORKLIST rows (an idle worker with open rows = lead must send the next step)
  - GPU0 / GPU1: running item, next waiting item (empty = lead must fill)
  - canon 216 (W48) pending cells without a retry item (calls canon_retry.py)
Exit code 1 when anything needs the lead (ACT lines), 0 otherwise.
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ORCA = r"C:\Users\AI-WS01\AppData\Local\Programs\orca\resources\bin"
WORKERS = {  # owner name in WORKLIST -> terminal handle prefix
    "runner": "term_b53e5aa0",
    "scripter": "term_564a8102",
    "analyst": "term_00bfa97f",
    "super2": "term_8792b227",
}
WORKLIST = Path("D:/mai-wt/foothold-lab/lead-worklist-1103/inbox/jay/20261104-ex41-restart/WORKLIST.tsv")
QUEUE = Path("D:/mai-tmp/gpu/queue.json")
BUSY = re.compile(r"Working \(|esc to interrupt|Running…|Polishing…|Fluttering…|Cogitat|Crunch|Churn|·\s*\(\d+[ms]")
REPORT = re.compile(r"\[(runner|scripter|analyst|super2)\][^\n]{0,160}|끝 ·[^\n]{0,160}|lead 검토 대기[^\n]{0,80}")
DONE_AT = re.compile(r"(Worked for [^•]+• [0-9:]+ ?[AP]M|done 오전 [0-9:]+|done 오후 [0-9:]+)")


def orca(*args: str) -> dict:
    env = dict(os.environ, PATH=os.environ.get("PATH", "") + os.pathsep + ORCA)
    r = subprocess.run(["orca", *args, "--json"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, shell=False)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": r.stderr[-300:]}


def handles() -> dict[str, str]:
    d = orca("terminal", "list")
    rows = (d.get("result") or {}).get("terminals") or []
    out = {}
    for t in rows:
        h = t.get("handle") or t.get("id") or ""
        for name, prefix in WORKERS.items():
            if h.startswith(prefix):
                out[name] = h
    return out


def read_tail(handle: str) -> list[str]:
    d = orca("terminal", "read", "--terminal", handle)
    t = ((d.get("result") or {}).get("terminal") or {}).get("tail") or []
    return [x.rstrip() for x in t if x.strip()]


def main() -> int:
    acts = []
    rows = list(csv.DictReader(WORKLIST.open(encoding="utf-8"), delimiter="\t"))
    open_by = {}
    for r in rows:
        if r.get("status") == "open":
            open_by.setdefault(r["owner"], []).append(f"{r['id']} {r['priority']} {r['due']}")
    hs = handles()
    box = orca("orchestration", "inbox", "--limit", "200")
    msgs = (box.get("result") or {}).get("messages") or []
    sent = {name: [m.get("subject", "") for m in msgs if (m.get("from") or "").startswith(prefix)]
            for name, prefix in WORKERS.items()}
    print("== 작업자")
    for name in WORKERS:
        h = hs.get(name)
        if not h:
            print(f"{name:8s} 창 없음")
            acts.append(f"ACT {name}: 창 핸들 없음")
            continue
        tail = read_tail(h)
        text = "\n".join(tail)
        busy = bool(BUSY.search("\n".join(tail[-8:])))
        rep = REPORT.findall(text)
        done = DONE_AT.findall(text)
        ctx = re.findall(r"Context (\d+)% left", text)
        last = (rep[-1] if rep else (tail[-10] if len(tail) > 10 else ""))[:150]
        mine = open_by.get(name, [])
        state = "일하는 중" if busy else "쉼"
        print(f"{name:8s} {state} · 마지막 끝 {done[-1] if done else '-'} · 컨텍스트 {ctx[-1] + '%' if ctx else '-'} · 열린 일 {len(mine)} {mine}")
        print(f"         마지막 보고: {last}")
        print(f"         받은편지함 최근: {sent[name][0][:90] if sent[name] else '없음(최근 200 통)'}")
        # A report printed in the window but never sent is the 11:25 runner miss (I41).
        win_reports = re.findall(r"\[" + name + r"\] (?:끝|막힘|질문)[^\n]{0,50}", text)
        key = win_reports[-1][:24] if win_reports else ""
        if key and not any(key in s for s in sent[name]):
            acts.append(f"ACT {name}: 창의 보고 「{win_reports[-1][:60]}」 가 받은편지함에 없음 · 창 보고를 읽고 처리 · 작업자에 송신 규칙 다시")
        if not busy:
            acts.append(f"ACT {name}: 쉼 · 마지막 보고 읽고 다음 단계 보냈는지 확인 · 열린 일 {mine}")
        if ctx and int(ctx[-1]) <= 10:
            acts.append(f"ACT {name}: 컨텍스트 {ctx[-1]}% · 쉬는 때 /compact")
    print("== GPU")
    q = json.loads(QUEUE.read_text(encoding="utf-8"))["items"]
    for g in (0, 1):
        run = [x for x in q if x.get("gpu") == g and x.get("state") == "실행"]
        wait = sorted((x for x in q if x.get("gpu") == g and x.get("state") == "대기"),
                      key=lambda x: (x.get("priority", 9), x["id"]))
        print(f"GPU{g} 지금 {[ (x['id'], (x['title'] or '')[:50]) for x in run]} · 다음 {[(x['id'], (x['title'] or '')[:40]) for x in wait[:2]]} · 대기 {len(wait)}")
        if not run and not wait:
            acts.append(f"ACT GPU{g}: 비었음 · 이 회차 안에 채움")
        elif len(wait) == 0:
            acts.append(f"ACT GPU{g}: 다음 일 없음 · 지금 일 끝나기 전에 걸기")
    print("== 정본 216")
    r = subprocess.run([sys.executable, r"C:\Users\AI-WS01\.claude\jobs\781698cc\tmp\canon_retry.py"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.strip())
    if "retry 0" not in r.stdout:
        acts.append("ACT W48: 재시도 없는 pending 칸 · canon_retry.py --queue")
    print("== 할 일")
    print("\n".join(acts) if acts else "없음")
    return 1 if acts else 0


if __name__ == "__main__":
    raise SystemExit(main())
