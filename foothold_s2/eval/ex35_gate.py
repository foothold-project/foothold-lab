"""EX-35 저장본 판정 소비 경로 (EXP-EX35-SB10-cmd-S2a.md 3 절, verifier 막음 1). 순수 함수, Kit 없음.

공용 `judge_gate.judge_continue` 는 켬(eval_gt) 한 모드만 보고 카드 3 절의 네 묶음을 빠뜨린다:
  (1) 제자리 회전 여섯 경우 kept >= 14 (공용 기본은 12),
  (2) 켬 fwd0.5 >= 부모 x 0.90 (공용은 fwd1.0 만),
  (3) 64 env 회전 추종(yaw_follow) 좌 >= max(부모 - 0.20, 0.10), 우도 같게, 각 방향 생존 >= 48,
  (4) 가림(probe_prop_only) 전진 유지: fwd1.0 >= 4.592 · fwd0.5 >= 2.310 · 생존 >= 60.
이 모듈의 `judge_ex35` 가 공용 판정을 부른 뒤 위 조건을 더해 상태를 정한다. 기준값(부모)은 원자료 JSON 의 값을 반올림 없이 읽고 문턱은 곱셈 결과 그대로 쓴다(2.471 대 2.472).
상태 이름 · 연속 소비(`judge_gate.consume`)는 공용과 같다. 문턱은 카드가 적은 추정이며 결과를 본 뒤 넓히지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys

from foothold_s2.eval import judge_gate as G
from foothold_s2.eval import judge_stats as S

EX35_EXTRA = {
    "min_kept": 14,                    # 카드 3 절: 돌 때 16 중 14 생존(팀장 16:0x 바닥)
    "on_fwd05_frac": 0.90,             # 켬 fwd0.5 >= 부모 x 0.90
    "on_survive_58": 58,               # 켬 전진 생존 >= 64 - 6
    "spin_follow_drop": 0.20, "spin_follow_floor": 0.10, "spin_survive_64": 48,
}
EX35_THR = {**G.THRESHOLDS, "min_kept": EX35_EXTRA["min_kept"]}
MASKED_LIVE = ("probe_prop_only", "none")


def _follow(b, mode, cmd):
    return G._map(b, mode)[cmd]["yaw_follow"]


def ex35_extra_broken(latest, base, window="latest", extra=EX35_EXTRA, thr=EX35_THR) -> list:
    """공용 판정이 보지 않는 카드 3 절 조건 중 깨진 것의 목록(비면 유지). 켬 모드는 eval_gt, 가림 모드는 latest 안의 probe_prop_only/none."""
    out = []
    on = "eval_gt"
    f10, f05, al = G.fwd(latest, on)
    _bf10, bf05, _bal = G.fwd(base, on)

    if f05 < bf05 * extra["on_fwd05_frac"]:
        out.append(G._cond("ex35_fwd05_keep_on", f05, bf05 * extra["on_fwd05_frac"], window, cmd="fwd0.5"))

    if al < extra["on_survive_58"]:
        out.append(G._cond("ex35_on_survive_64", al, extra["on_survive_58"], window))

    for cmd, name in (("spin+1.2", "left"), ("spin-1.2", "right")):
        lim = max(_follow(base, on, cmd) - extra["spin_follow_drop"], extra["spin_follow_floor"])
        v = _follow(latest, on, cmd)

        if not v >= lim:                                                      # NaN 도 미달
            out.append(G._cond("ex35_spin_follow_" + name, v, lim, window, cmd=cmd))

        a = G._map(latest, on)[cmd]["alive"]

        if a < extra["spin_survive_64"]:
            out.append(G._cond("ex35_spin_survive_" + name, a, extra["spin_survive_64"], window, cmd=cmd))

    mm = G.masked_mode(latest)

    if mm is not None:
        out += [dict(c, cond="ex35_" + c["cond"]) for c in G.forward_hold_broken(latest, base, mm, thr, window)]

    return out


def judge_ex35(latest, base, it_in_stage, min_stay, *, stage="S2a->S2b", preconditions=None, thr=EX35_THR) -> G.Verdict:
    """저장본 하나의 EX-35 판정. 공용 `judge_continue`(켬, kept 14) + 카드 3 절 네 묶음. 가림 자료가 없으면 HOLD_NO_DATA."""
    v = G.judge_continue(latest, None, base, stage, it_in_stage, min_stay, mode="eval_gt", preconditions=preconditions, thr=thr)
    v.rule = "ex35"

    if v.state in (G.STOP, G.HOLD_NO_DATA):
        return v
    mm = G.masked_mode(latest)

    if mm is None or not G.has_map64(latest, mm):
        v.state, v.reasons = G.HOLD_NO_DATA, [G._cond("no_data", what=["map64/masked"])]

        return v
    extra = ex35_extra_broken(latest, base, "latest", thr=thr)

    if extra:
        v.state, v.reasons = G.MAINTAIN_FAIL, extra + list(v.reasons)

    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EX-35 저장본 판정(카드 3 절). 평가 폴더 둘(최신 · 부모)을 읽어 상태 하나를 JSON 으로 낸다.")
    ap.add_argument("--latest-turn", nargs="+", required=True, metavar="MODE=DIR", help="예: eval_gt=<turn16_eval_gt> probe_prop_only=<turn16_probe_prop_only>")
    ap.add_argument("--latest-map64", required=True)
    ap.add_argument("--base-turn", nargs="+", required=True, metavar="MODE=DIR")
    ap.add_argument("--base-map64", required=True)
    ap.add_argument("--it-in-stage", type=int, required=True)
    ap.add_argument("--min-stay", type=int, default=500)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    kv = lambda items: {k: v for k, v in (i.split("=", 1) for i in items)}
    latest = S.load_bundle("latest", kv(a.latest_turn), a.latest_map64, cases=S.SIX_CASES + S.WALK_CASES)
    base = S.load_bundle("parent", kv(a.base_turn), a.base_map64)
    v = judge_ex35(latest, base, a.it_in_stage, a.min_stay)
    text = json.dumps(v.to_dict(), ensure_ascii=False, indent=1, sort_keys=True)

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
