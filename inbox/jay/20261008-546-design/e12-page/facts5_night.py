"""5판 「밤사이 한 일」 표의 진행 칸을 로그에서 만든다 (lead · 10/13 아침).
원자료: _eval/out/branch/cmdr_s1042_{off,on}_u4000.log (학습 iteration) · result.json (갈래 끝) ·
        _eval/out/cmdr_eval_driver.json (평가 실행 기록)."""
import glob
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
    # 10/13 16:40: the v3.7 pair ended; say when, how many runs, and which freeze the tables come from
    o37 = os.path.join(EV, "cmdr_eval_driver_v37.out")
    ends = [l[:8] for l in open(o37, encoding="utf-8", errors="replace").read().splitlines() if " END complete=" in l] if os.path.exists(o37) else []
    g0 = json.load(open(os.path.join(EV, "cmdr_eval_driver_g0.json"), encoding="utf-8"))
    ok0 = sum(1 for r in g0.get("runs", []) if r.get("valid"))
    hs = sorted(glob.glob(os.path.join(EV, "handover_*", "manifest.json")))
    man = json.load(open(hs[-1], encoding="utf-8")) if hs else {}
    t["night_eval"] = ((f"끝 ({ends[-1][:5]}) · " if ends else "")
                       + f"유효한 실행 GPU 1 {ok} · GPU 0 다시 재기 {ok0} (실행마다 100 판)"
                       + (f" · 무효 {len(runs) - ok}" if len(runs) - ok else "")
                       + (f" · 마감 동결 {man['finished'][11:16]} ({man['valid_runs']} 실행 · {man['status']})" if man.get("finished") else "")
                       + f" <span class=\"sub\">({time.strftime('%H:%M')} 기준)</span>")
    t["night_astra"] = "16m 통과 (이 판의 숫자 · 출처)"
    return t


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
