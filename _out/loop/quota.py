# -*- coding: utf-8 -*-
"""codex 한도·사용량 조회 · **읽기만 합니다.**

분류: 운영
작성: 오흥재 · 2026-09-23
근거: `codex app-server` 의 `account/rateLimits/read` · `account/usage/read` ·
      호출 순서는 4 차 감사(`AUDIT4-astra.md` 6 절)가 스키마에서 뽑아 준 것
요지: 주간 사용률·리셋 시각·리셋권 수를 잰다. **리셋권을 소비하지 않는다.**
상태: 초안
판: v1.0

리셋권을 왜 안 쓰는가
    `account/rateLimitResetCredit/consume` 는 이 파일에 «없다».
    리셋권은 팀장 것이고 사람이 결정한다. 자동으로 쓰면 되돌릴 수 없다.

왜 이 파일이 필요했나
    2026-09-23 에 내가 「내 토큰 사용량이나 주간 한도를 조회할 도구가 없다」고
    단정했다. **틀렸다.** 3 차 감사가 app-server 에 API 가 있다는 것을 찾았고,
    4 차 감사가 호출 순서를 알려 줬다. 내 첫 시도가 실패한 까닭은 인증이
    아니라 **첫 응답을 id 로 확인하기 전에 다음을 보내고 stdin 을 닫아서** 였다.

왜 shell=True 인가
    `codex` 는 npm shim(`codex.CMD`)이라 `subprocess` 가 직접 못 띄운다.
    `FileNotFoundError` 와 `WinError 193` 을 그래서 겪었다.

돌리는 법
    python _out/loop/quota.py              사람이 읽는 판
    python _out/loop/quota.py --json       기계가 읽는 판
    python _out/loop/quota.py --record 이름  측정 지점을 기록해 둔다
    python _out/loop/quota.py --since 이름   그 지점 이후 얼마나 썼는지
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import queue
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MARKS = os.path.join(HERE, "quota-marks.json")


def ask(timeout: float = 30.0) -> dict:
    """한도와 사용량을 한 번에 읽는다. 실패하면 까닭을 담아 돌려준다."""
    p = subprocess.Popen(
        "codex app-server", shell=True,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
        encoding="utf-8", errors="replace")
    q: "queue.Queue[tuple[str, str]]" = queue.Queue()
    for stream, tag in ((p.stdout, "out"), (p.stderr, "err")):
        threading.Thread(target=lambda s=stream, t=tag: [q.put((t, l.rstrip()))
                                                         for l in s],
                         daemon=True).start()

    def send(o):
        p.stdin.write(json.dumps(o) + "\n")
        p.stdin.flush()

    def wait(want_id, secs):
        """**순서가 아니라 id 로 짝짓는다.** 알림이 사이에 끼어든다."""
        end = time.time() + secs
        errs = []
        while time.time() < end:
            try:
                tag, ln = q.get(timeout=0.5)
            except queue.Empty:
                continue
            if tag == "err":
                errs.append(ln)
                continue
            try:
                m = json.loads(ln)
            except ValueError:
                continue
            if m.get("id") == want_id:
                return m, errs
        return None, errs

    out = {"at": dt.datetime.now().isoformat(timespec="seconds")}
    try:
        send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "lineage_usage_reader", "version": "1.0"},
            "capabilities": {"experimentalApi": True}}})
        init, errs = wait(1, timeout / 3)
        if not init or "result" not in init:
            out["error"] = "initialize 실패"
            out["stderr"] = errs[:5]
            return out

        send({"method": "initialized"})
        time.sleep(0.3)
        send({"id": 2, "method": "account/rateLimits/read",
              "params": {"excludeResetCreditDetails": True}})
        send({"id": 3, "method": "account/usage/read", "params": {}})
        rl, _ = wait(2, timeout / 3)
        us, _ = wait(3, timeout / 3)
    finally:
        try:
            p.terminate()
        except Exception:                                      # noqa: BLE001
            pass

    if rl and "result" in rl:
        r = rl["result"]
        pri = (r.get("rateLimits") or {}).get("primary") or {}
        out["used_percent"] = pri.get("usedPercent")
        out["window_mins"] = pri.get("windowDurationMins")
        out["resets_at"] = pri.get("resetsAt")
        if pri.get("resetsAt"):
            out["resets_at_local"] = dt.datetime.fromtimestamp(
                pri["resetsAt"]).isoformat(timespec="minutes")
        out["reset_credits"] = ((r.get("rateLimitResetCredits") or {})
                                .get("availableCount"))
        out["plan"] = (r.get("rateLimits") or {}).get("planType")
        # **null 을 0 으로 바꾸지 않는다.** 4 차 감사 지적이다.
        out["ordinary_usage_allowed"] = r.get("ordinaryUsageAllowed")
    else:
        out["error"] = "rateLimits 응답 없음"

    if us and "result" in us:
        buckets = us["result"].get("dailyUsageBuckets") or []
        out["daily"] = {b["startDate"]: b["tokens"] for b in buckets}
        out["lifetime_tokens"] = (us["result"].get("summary") or {}).get(
            "lifetimeTokens")
    return out


def load_marks() -> dict:
    if not os.path.isfile(MARKS):
        return {}
    try:
        with io.open(MARKS, encoding="utf-8") as h:
            return json.load(h)
    except Exception:                                          # noqa: BLE001
        return {}


def human(snap: dict, marks: dict, since: str | None) -> str:
    if snap.get("error"):
        return "조회 실패: %s\n%s" % (snap["error"],
                                  "\n".join(snap.get("stderr") or []))
    lines = []
    pct = snap.get("used_percent")
    lines.append("주간 사용   %s %%" % pct)
    if snap.get("resets_at_local"):
        left = (dt.datetime.fromisoformat(snap["resets_at_local"])
                - dt.datetime.now()).total_seconds() / 3600
        lines.append("리셋        %s  (%.1f 시간 뒤)"
                     % (snap["resets_at_local"], left))
    lines.append("리셋권      %s 장  («이 도구는 소비하지 않는다»)"
                 % snap.get("reset_credits"))
    lines.append("요금제      %s" % snap.get("plan"))
    lines.append("잰 때       %s" % snap.get("at"))

    daily = snap.get("daily") or {}
    if daily:
        recent = sorted(daily)[-5:]
        lines.append("")
        lines.append("최근 일별 토큰")
        for d in recent:
            lines.append("  %s  %s" % (d, format(daily[d], ",")))

    if since and since in marks:
        old = marks[since]
        lines.append("")
        lines.append("«%s» 이후" % since)
        lines.append("  그때 %s %% -> 지금 %s %%  (차이 %s %%p)"
                     % (old.get("used_percent"), pct,
                        (pct - old["used_percent"])
                        if pct is not None and old.get("used_percent") is not None
                        else "?"))
        lines.append("  그때 잰 시각 %s" % old.get("at"))
    elif since:
        lines.append("")
        lines.append("«%s» 이라는 측정 지점이 없다" % since)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--record", metavar="NAME",
                    help="지금 값을 이 이름으로 저장해 둔다")
    ap.add_argument("--since", metavar="NAME",
                    help="그 지점 이후 얼마나 썼는지 같이 보인다")
    args = ap.parse_args()

    snap = ask()
    marks = load_marks()

    if args.record and not snap.get("error"):
        marks[args.record] = snap
        with io.open(MARKS, "w", encoding="utf-8") as h:
            h.write(json.dumps(marks, ensure_ascii=False, indent=2) + "\n")

    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
    else:
        print(human(snap, marks, args.since))
        if args.record:
            print("\n측정 지점 «%s» 을 기록했다" % args.record)
    return 1 if snap.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
