"""5판 「밤사이 한 일」 표의 진행 칸을 로그에서 만든다 (lead · 10/13 아침).
원자료: _eval/out/branch/cmdr_s1042_{off,on}_u4000.log (학습 iteration) · result.json (갈래 끝) ·
        _eval/out/cmdr_eval_driver.json (평가 실행 기록)."""
import json
import os
import re
import time

EV = "C:/isaac/ext/go2_rl_robotlab/_eval/out"


def _iter(arm):
    p = os.path.join(EV, "branch", f"cmdr_s1042_{arm}_u4000.log")
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        f.seek(max(0, os.path.getsize(p) - 60000))
        tail = f.read().decode("utf-8", "replace")
    m = re.findall(r"Learning iteration (\d+)/(\d+)", tail)
    return (int(m[-1][0]), int(m[-1][1]) - 1) if m else None


def build():
    t = {}
    parts = []
    for arm, ko in (("off", "안 고친 갈래"), ("on", "고친 갈래")):
        done = os.path.exists(os.path.join(EV, "branch", f"cmdr_s1042_{arm}_u4000", "result.json"))
        it = _iter(arm)
        if done:
            parts.append(f"{ko} 끝 (24,000)")
        elif it:
            parts.append(f"{ko} {it[0]:,} / {it[1]:,}")
        else:
            parts.append(f"{ko} 시작 전")
    t["night_train"] = " · ".join(parts) + f" <span class=\"sub\">({time.strftime('%H:%M')} 기준)</span>"
    d = json.load(open(os.path.join(EV, "cmdr_eval_driver.json"), encoding="utf-8"))
    runs = d.get("runs", [])
    ok = sum(1 for r in runs if r.get("valid"))
    out = open(os.path.join(EV, "cmdr_eval_driver.out"), encoding="utf-8", errors="replace").read().splitlines()
    tp = [l[:5] for l in out if " tests passed " in l]
    t["night_eval"] = (f"v3.2 시험 통과 ({tp[-1] if tp else '?'}) · 유효한 실행 {ok} 개 (실행마다 100 판)"
                       + (f" · 무효 {len(runs) - ok}" if len(runs) - ok else "")
                       + f" <span class=\"sub\">({time.strftime('%H:%M')} 기준)</span>")
    return t


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
