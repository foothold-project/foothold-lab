"""EX-35 창 경계 판정 소비기 (카드 v0.9 4b.1 · 4b.5 · 4b.6, JUDGE-SPEC v0.13). 순수 파이썬, Kit 없음, 평가 폴더를 읽기만 한다.

입력: 최신 저장본 폴더(예 m2000) 와 직전 저장본 폴더(m1950) -- `ex35_eval_chain2.sh` 가 만든 `m<N>/` 이고 4b.5 필수 칸이 모두 있어야 한다.
  m<N>/turn16_{eval_gt,probe_prop_only}/arrays_*.npz (여섯 + walk_turn 둘 + 전진 걸음) · turn16_eval_pred/ · map64/map_modes.json(켬 · 가림) ·
  map64_eval_pred/map_modes.json · hardlevel/{L6,L9}/map_modes.json · checkpoint_sha256.txt
기준선: 부모 m1500 원자료(`sb10_eval/m1500`, `hardlevel/sb10_L{6,9}`, walk 는 `turn16_walk_*`). A11 판독표는 lead 가 채운 JSON(스키마는 `A11_KEYS`).
출력: 갈래 하나(CONTINUE · NEXT_STAGE · STOP · HOLD · HOLD_NO_DATA), 진리표 행 번호, 저장본별 상태, 축별 값 · 기준선 · 하한 · 통과 표(JSON + markdown).
저장본 하나의 상태는 `ex35_gate.judge_ex35`(공용 판정 + 카드 3 절) 에 창 판정만의 유지 조건(A2 eval_pred · L6 · L9, A5 걸으며 돌기 유지 하한)을 더해 정한다. 새 문턱은 만들지 않았다(카드 4b.1 숫자 그대로).
계산하지 않는 축(경고 축, 멈춤 조건 아님 -- 카드 4b.6): A1 보행 위상, A7 기울기, A8 접촉 링크 속도, A9 학습 곡선. 표에는 「미계산」 으로 적는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

from foothold_s2.eval import ex35_gate as X
from foothold_s2.eval import ex35_window_axes as AX
from foothold_s2.eval import judge_gate as G
from foothold_s2.eval import judge_stats as S

BASE_DEFAULT = "C:/mai/wt/foothold-lab/impl-turncases/logs/sb10_eval/m1500"
HARD_DEFAULT = "C:/mai/wt/foothold-lab/impl-turncases/logs/hardlevel"
MODES_TURN = ("eval_gt", "probe_prop_only")
CASES8 = tuple(S.SIX_CASES) + tuple(S.WALK_CASES)
A11_KEYS = ("reader", "time", "checkpoint_sha256", "cmp_video", "solo_video", "a1_figures_seen", "all_frames_checked", "items")
A11_ITEMS = ("1", "2", "3", "4", "5")

WIN = {                                         # 카드 4b.1 의 숫자만. 새 문턱 없음
    "pred_fwd10_frac": 0.90,                    # A2: eval_pred fwd1.0 >= 기준 x 0.90 (5.417 x 0.90 = 4.875)
    "hard_fwd10_frac": 0.90, "hard_survive_drop": 6,   # A2: L6 · L9 fwd1.0 >= 기준 x 0.90 · 생존 >= 기준 - 6
    "walk_drop_q": 0.20, "walk_rise_c": 0.25, "walk_kept": 14, "walk_vx_frac": 0.90,   # A5 유지 하한(카드: 가정, A3 식 차용)
    "trend_rise_q": 0.115,                      # A5 추세 개선 경계(카드: 가정 = A3 폭)
    "flat_windows": 2,                          # 4b.2 평평 = 연속 2 창 개선 없음
    "ceiling_iter": 3000,                       # 4b.2 상한 m3000
    "recompute_tol": 1e-6,                      # A12
}


# ------------------------------------------------------------------ 읽기


def _iter_of(d) -> int:
    m = re.fullmatch(r"m(\d+)", Path(d).name)

    return int(m.group(1)) if m else -1


def _sha_file(path) -> str:
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)

    return h.hexdigest()


def required_files(d, base=False) -> list:
    """4b.5 필수 칸 중 «파일이 있어야 하는 것» 의 상대 경로 목록(저장본 폴더 아래)."""
    d = Path(d)
    out = ["map64/map_modes.json", "map64_eval_pred/map_modes.json", "hardlevel/L6/map_modes.json", "hardlevel/L9/map_modes.json", "checkpoint_sha256.txt"]

    for mode in ("eval_gt", "probe_prop_only", "eval_pred"):
        out.append("turn16_%s/probe_result.json" % mode)                    # 평가가 도는 중이면 npz 는 있어도 이 파일은 아직 없다

        for c in tuple(CASES8) + AX.FWD:                                   # 여섯 + 걸으며 돌기 둘 + 전진 걸음 둘(A1 · A7 · A8 의 입력)
            out.append("turn16_%s/arrays_%s.npz" % (mode, c))

    return out


def content_missing(d) -> list:
    """파일은 있어도 안에 명령 칸이 빠진 것(예: L9 에 fwd0.5 가 없음)을 결측으로 센다."""
    d = Path(d)
    out = []
    want = {"map64/map_modes.json": ("eval_gt", "probe_prop_only"), "map64_eval_pred/map_modes.json": ("eval_pred",),
            "hardlevel/L6/map_modes.json": ("eval_gt", "probe_prop_only"), "hardlevel/L9/map_modes.json": ("eval_gt", "probe_prop_only")}

    for rel, modes in want.items():
        p = d / rel

        if not p.is_file():
            continue

        try:
            j = json.loads(p.read_text(encoding="utf-8"))["modes"]
        except Exception:                                                                       # noqa: BLE001
            out.append(rel + ": 읽을 수 없음")
            continue

        cmds = S.MAP64_CMDS if rel.startswith("map64") else ("fwd1.0", "fwd0.5")

        for m in modes:
            for c in cmds:
                if c not in (j.get(m) or {}):
                    out.append("%s: %s/%s 없음" % (rel, m, c))

    return out


def missing_inputs(d) -> list:
    d = Path(d)
    miss = [f for f in required_files(d) if not (d / f).is_file()] + content_missing(d)
    lst = d / "inputs_list.txt"

    if lst.is_file():                                                  # 사슬이 적은 MISSING 줄도 결측으로 센다(파일 존재 검사와 겹치면 한 번만)
        for ln in lst.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.startswith("MISSING"):
                f = ln.split(None, 1)[1].strip()

                if f != "ex35_verdict.json" and f not in miss and not (d / f).is_file():
                    miss.append(f)

    return miss


def load_ckpt(d) -> dict:
    """한 저장본 폴더 -> 판정 묶음(켬 · 가림 + 추가 모드). 빠진 파일이 있으면 missing 에 적고 가능한 만큼만 읽는다."""
    d = Path(d)
    b = S.load_bundle("m%d" % _iter_of(d), {m: d / ("turn16_" + m) for m in MODES_TURN}, d / "map64" / "map_modes.json", cases=CASES8)
    ext = {"dir": str(d), "iter": _iter_of(d), "hard": {}, "pred_turn": {}}
    p = d / "map64_eval_pred" / "map_modes.json"

    if p.is_file():
        m = S.read_map64(p)
        b["map64"] = dict(b.get("map64") or {}, **{"eval_pred": m["modes"]["eval_pred"]})
        b["sources"]["map64_eval_pred"] = m["sha256"]

    for L in ("L6", "L9"):
        q = d / "hardlevel" / L / "map_modes.json"

        if q.is_file():
            ext["hard"][L] = S.read_map64(q, strict=False)

    pt = d / "turn16_eval_pred"

    if pt.is_dir():
        ext["pred_turn"] = S.read_turn_dir(pt, CASES8)

    sh = d / "checkpoint_sha256.txt"
    ext["ckpt_sha_txt"] = sh.read_text(encoding="utf-8", errors="replace").split()[0] if sh.is_file() else None
    ext["ckpt_path_txt"] = " ".join(sh.read_text(encoding="utf-8", errors="replace").split()[1:]).lstrip("*") if sh.is_file() else None
    b["ext"] = ext

    return b


def load_base(base=BASE_DEFAULT, hard=HARD_DEFAULT) -> dict:
    base, hard = Path(base), Path(hard)
    b = S.load_bundle("m1500", {m: base / ("turn16_" + m) for m in MODES_TURN}, base / "map64" / "map_modes.json")
    walk = {m: S.read_turn_dir(base / ("turn16_walk_" + m), S.WALK_CASES) for m in MODES_TURN}

    for m in MODES_TURN:
        b["turn"][m] = dict(b["turn"][m], **walk[m])

    ext = {"hard": {}, "pred_turn": {}}

    for L in ("L6", "L9"):
        ext["hard"][L] = S.read_map64(hard / ("sb10_" + L) / "map64" / "map_modes.json", strict=False)

    pt = base / "turn16_eval_pred"

    if pt.is_dir():
        ext["pred_turn"] = S.read_turn_dir(pt, S.SIX_CASES)

    b["ext"] = ext

    return b


# ------------------------------------------------------------------ 창 판정만의 유지 조건


def window_extra_broken(b, base, w=WIN) -> list:
    """judge_ex35 가 보지 않는 4b.1 하한: A2 eval_pred / L6 / L9, A5 걸으며 돌기 유지(켬 · 가림 각각)."""
    out = []
    pm = (b.get("map64") or {}).get("eval_pred")
    bpm = (base.get("map64") or {}).get("eval_pred")

    if pm and bpm:
        lim = bpm["fwd1.0"]["fwd_m"] * w["pred_fwd10_frac"]

        if not pm["fwd1.0"]["fwd_m"] >= lim:
            out.append(G._cond("ex35w_pred_fwd10", pm["fwd1.0"]["fwd_m"], lim, "latest", mode="eval_pred", cmd="fwd1.0"))

    for L, bh in base["ext"]["hard"].items():
        h = b["ext"]["hard"].get(L)

        if h is None:
            continue

        for mode in MODES_TURN:
            v, bv = h["modes"][mode]["fwd1.0"], bh["modes"][mode]["fwd1.0"]

            if not v["fwd_m"] >= bv["fwd_m"] * w["hard_fwd10_frac"]:
                out.append(G._cond("ex35w_%s_fwd10" % L, v["fwd_m"], bv["fwd_m"] * w["hard_fwd10_frac"], "latest", mode=mode))

            if v["alive"] < bv["alive"] - w["hard_survive_drop"]:
                out.append(G._cond("ex35w_%s_survive" % L, v["alive"], bv["alive"] - w["hard_survive_drop"], "latest", mode=mode))

    for mode in MODES_TURN:
        for c in S.WALK_CASES:
            s, bs = G._turn(b, mode).get(c), G._turn(base, mode).get(c)

            if s is None or bs is None:
                continue

            if not s["Q"] >= bs["Q"] - w["walk_drop_q"]:
                out.append(G._cond("ex35w_walk_q", s["Q"], bs["Q"] - w["walk_drop_q"], "latest", mode=mode, case=c))

            if not s["C"] <= bs["C"] + w["walk_rise_c"]:
                out.append(G._cond("ex35w_walk_c", s["C"], bs["C"] + w["walk_rise_c"], "latest", mode=mode, case=c))

            if s["kept"] < w["walk_kept"]:
                out.append(G._cond("ex35w_walk_kept", s["kept"], w["walk_kept"], "latest", mode=mode, case=c))

            if not s["vx_integral_kept_mean"] >= bs["vx_integral_kept_mean"] * w["walk_vx_frac"]:
                out.append(G._cond("ex35w_walk_vx", s["vx_integral_kept_mean"], bs["vx_integral_kept_mean"] * w["walk_vx_frac"], "latest", mode=mode, case=c))

    return out


def ckpt_state(b, base, it_in_stage, min_stay=500) -> G.Verdict:
    """저장본 하나의 상태. judge_ex35 가 PASS · PENDING 이어도 창 판정 유지 조건이 깨지면 MAINTAIN_FAIL."""
    v = X.judge_ex35(b, base, it_in_stage, min_stay)
    v.rule = "ex35_window"

    if v.state in (G.PASS, G.NEW_TASK_PENDING):
        extra = window_extra_broken(b, base)

        if extra:
            v.state, v.reasons = G.MAINTAIN_FAIL, extra + list(v.reasons)

    return v


# ------------------------------------------------------------------ A12 재현 (독립 식)


def recompute_turn(npz, case) -> dict:
    """judge_stats.turn_stats 와 다르게 짠 Q · C · kept (환경별 루프). 일치 확인용."""
    z = np.load(npz)
    alive, wz, force, kept_in = z["alive"], z["wz"], z["force"], z["kept"]
    sign = 1.0 if S.P.PROTOCOLS[case]["cmd"][2] > 0 else -1.0
    qs, cs = [], []

    for e in range(alive.shape[0]):
        if not kept_in[e]:
            continue

        a = alive[e]

        if not a.any():
            continue

        qs.append(sign * float(np.mean(wz[e][a])))
        cs.append(float(np.mean((force[e][:, list(S.FEET)] > S.CONTACT_N).all(axis=1)[a])))

    return {"kept": len(qs), "Q": float(np.mean(qs)) if qs else float("nan"), "C": float(np.mean(cs)) if cs else float("nan")}


def recompute_vx_integral(npz) -> float:
    """독립 식: kept env 의 (살아 있는 스텝 vx 합 / 200 Hz) 평균(m). judge_stats.turn_stats 의 vx_integral_kept_mean 과 같은 정의, 다른 계산."""
    z = np.load(npz)
    tot, n = 0.0, 0

    for e in range(z["alive"].shape[0]):
        if z["kept"][e] and z["alive"][e].any():
            tot += float(np.sum(z["vx"][e][z["alive"][e]])) / S.HZ
            n += 1

    return tot / n if n else float("nan")


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reproduce_check(d, b, base_hard_assignment=None, tol=WIN["recompute_tol"], dist_tol=1e-3) -> dict:
    """A12 (카드 4b.1): Q · C <= 1e-6, 거리 <= 1e-3 m, 정수 0, 지형 해시, 저장본 sha256, eval_seed 42. 하나라도 어긋나거나 «확인 못 함» 이면 ok 가 아니다
    (파일 · 기록이 없는 것을 통과로 치지 않는다). 독립 식이 없는 것(64 env 거리)은 not_independent 에 적고, 판정에서 막을지는 호출자(require_map64_recompute)가 정한다."""
    d = Path(d)
    bad, notes = [], []
    n = 0

    for mode in MODES_TURN + ("eval_pred",):
        for c in CASES8:
            p = d / ("turn16_" + mode) / ("arrays_%s.npz" % c)
            s = (G._turn(b, mode) if mode != "eval_pred" else b["ext"].get("pred_turn") or {}).get(c)

            if not p.is_file() or s is None:
                bad.append({"cond": "no_input", "file": str(p)})
                continue

            r = recompute_turn(p, c)
            vx = recompute_vx_integral(p)
            n += 1

            if r["kept"] != s["kept"] or abs(r["Q"] - s["Q"]) > tol or abs(r["C"] - s["C"]) > tol:
                if not (r["kept"] == 0 == s["kept"]):
                    bad.append({"mode": mode, "case": c, "recomputed": r, "judge": {k: s[k] for k in ("kept", "Q", "C")}})

            if not abs(vx - s["vx_integral_kept_mean"]) <= dist_tol:
                bad.append({"cond": "distance", "mode": mode, "case": c, "recomputed": vx, "judge": s["vx_integral_kept_mean"]})

    ext = b["ext"]
    sha_txt, pth = ext.get("ckpt_sha_txt"), ext.get("ckpt_path_txt")
    sha_ok = None

    if not sha_txt or not pth or not Path(pth).is_file():
        bad.append({"cond": "checkpoint_sha256", "why": "저장본 파일을 찾을 수 없어 sha256 을 다시 계산하지 못했다(미확인은 통과가 아니다)", "file": pth})
    else:
        sha_ok = _sha_file(pth) == sha_txt

        if not sha_ok:
            bad.append({"cond": "checkpoint_sha256", "file": pth})

    maps = [("map64", d / "map64" / "map_modes.json", S.MAP64_SHA), ("map64_eval_pred", d / "map64_eval_pred" / "map_modes.json", S.MAP64_SHA)]

    for L in ("L6", "L9"):
        maps.append(("hardlevel/" + L, d / "hardlevel" / L / "map_modes.json", (base_hard_assignment or {}).get(L)))

    for name, p, want in maps:
        if not p.is_file():
            bad.append({"cond": "no_input", "file": str(p)})
            continue

        j = _json(p)
        got = (j.get("fixed_terrain") or {}).get("assignment_sha256")

        if j.get("eval_seed") != 42:
            bad.append({"cond": "eval_seed", "file": name, "value": j.get("eval_seed"), "want": 42})

        if want is None or got != want:
            bad.append({"cond": "terrain_hash", "file": name, "value": (got or "")[:12], "want": (want or "")[:12] or "기준 없음"})

        if sha_txt and j.get("checkpoint_sha256") != sha_txt:
            bad.append({"cond": "map_checkpoint_sha256", "file": name, "value": str(j.get("checkpoint_sha256"))[:12], "want": sha_txt[:12]})

    for mode in MODES_TURN + ("eval_pred",):
        pj = d / ("turn16_" + mode) / "probe_result.json"

        if not pj.is_file():
            bad.append({"cond": "no_input", "file": str(pj)})
            continue

        j = _json(pj)
        got = (j.get("fixed_terrain") or {}).get("assignment_sha256") or ""

        if not got.startswith(S.PROBE16_SHA12):
            bad.append({"cond": "terrain_hash", "file": "turn16_" + mode, "value": got[:12], "want": S.PROBE16_SHA12})

        if sha_txt and j.get("checkpoint_sha256") != sha_txt:
            bad.append({"cond": "turn_checkpoint_sha256", "file": "turn16_" + mode, "value": str(j.get("checkpoint_sha256"))[:12], "want": sha_txt[:12]})

    notes.append("turn16 의 eval_seed: turn_probe 는 시드 인자가 없고 probe_result.json 에도 기록이 없다(기본 고정). 지형 해시 7f49a1e9 와 저장본 sha 로만 대조")

    return {"checked_cases": n, "mismatch": bad, "checkpoint_sha_matches_file": sha_ok, "checkpoint_file": pth, "ok": not bad, "notes": notes,
            "not_independent": ["64 env 거리 · 생존(map64 · eval_pred · L6 · L9): 환경별 자료(npz)가 없어 독립 식이 없다. 평가 JSON 값을 그대로 쓴다"]}


# ------------------------------------------------------------------ A11


def read_a11(path, ckpt_sha) -> dict:
    """lead 가 채운 판독 JSON. 없음 · 형식 틀림 · 머리 칸 비어 있음 · 저장본 sha 다름 -> 미기입. 다섯 항목 모두 「없음」 이면 clear, 「있음」 이 하나라도 있으면 flagged."""
    if not path or not Path(path).is_file():
        return {"state": "unfilled", "why": "A11 판독 파일 없음"}

    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:                                                                      # noqa: BLE001
        return {"state": "unfilled", "why": "읽을 수 없음: %s" % e}

    empty = [k for k in A11_KEYS if d.get(k) in (None, "", {}, [])]
    items = d.get("items") or {}
    bad_items = [k for k in A11_ITEMS if items.get(k) not in ("있음", "없음")]

    if empty or bad_items:
        return {"state": "unfilled", "why": "빈 칸 %s · 항목 %s 미기입" % (empty, bad_items)}

    for k in ("cmp_video", "solo_video"):
        if not (isinstance(d[k], dict) and d[k].get("path") and d[k].get("sha256")):
            return {"state": "unfilled", "why": "%s 에 path · sha256 가 없다" % k}

    if d["a1_figures_seen"] is not True or d["all_frames_checked"] is not True:
        return {"state": "unfilled", "why": "A1 그림 확인 또는 전 프레임 검수가 true 가 아님"}

    if ckpt_sha and d["checkpoint_sha256"] != ckpt_sha:
        return {"state": "unfilled", "why": "판독 저장본 sha256 이 이번 저장본과 다름(이전 판독 재사용 금지)"}

    for k in ("cmp_video", "solo_video"):
        vp = Path(d[k]["path"])

        if not vp.is_file():
            return {"state": "unfilled", "why": "%s 영상 파일이 없다: %s" % (k, d[k]["path"])}

        if _sha_file(vp) != d[k]["sha256"]:
            return {"state": "unfilled", "why": "%s 영상 sha256 이 파일과 다르다" % k}

    yes = [k for k in A11_ITEMS if items[k] == "있음"]

    return {"state": "flagged" if yes else "clear", "yes": yes, "reader": d["reader"], "time": d["time"]}


# ------------------------------------------------------------------ 추세 · 진리표


def a5_q(b) -> dict:
    t = G._turn(b, "eval_gt")

    return {"left": t["walk_turn_left"]["Q"], "right": t["walk_turn_right"]["Q"]} if all(c in t for c in S.WALK_CASES) else {}


def trend(latest_q: dict, prev_window: dict | None, w=WIN) -> dict:
    """이전 창 경계(prev_window json 의 a5_q) 대비 방향별 Q 증가. 어느 한 방향이라도 +0.115 이상이면 개선(양방향 평균은 쓰지 않는다).
    개선 없음 연속 창 수 no_improve_streak 는 이전 창의 값에 이어 센다. 이전 창이 없으면 추세 없음(streak 0, flat False)."""
    if not prev_window or not prev_window.get("a5_q"):
        return {"has_prev": False, "delta": {}, "improved": None, "no_improve_streak": 0, "flat": False}

    pq = prev_window["a5_q"]
    delta = {k: latest_q[k] - pq[k] for k in ("left", "right") if k in latest_q and k in pq}
    improved = any(v >= w["trend_rise_q"] for v in delta.values())
    streak = 0 if improved else int(prev_window.get("no_improve_streak", 0)) + 1

    return {"has_prev": True, "delta": delta, "improved": improved, "no_improve_streak": streak, "flat": streak >= w["flat_windows"]}


def truth_table(prev_state, latest_state, ctx) -> dict:
    """카드 4b.6 의 열한 행. ctx: trend_missing(문자열 또는 빈) · input_missing(list) · same_sha · iter_increasing · stop(bool) · a12_ok · a11 · at_ceiling · flat. 위에서부터 먼저 맞는 행."""
    if ctx["input_missing"] or ctx["same_sha"] or not ctx["iter_increasing"] or G.HOLD_NO_DATA in (prev_state, latest_state) or ctx.get("trend_missing"):
        why = ctx.get("trend_missing") or "필수 칸 결측 · 같은 sha · 회차 비증가 · 읽기 실패"

        return {"row": 1, "branch": "HOLD_NO_DATA", "action": "판정 불가 = 연장 불가 · 보고(통과 아님): %s" % why}

    if ctx["stop"]:
        return {"row": 2, "branch": "STOP", "action": "저장본 보존 · 보고 (STOP 상태 또는 비유한값 NaN · inf)"}

    if not ctx["a12_ok"]:
        return {"row": 3, "branch": "STOP", "action": "재현 불일치 또는 독립 재계산 미측 · 보고(코드 · 자료 문제)"}

    if ctx["a11"]["state"] != "clear":
        return {"row": 4, "branch": "STOP", "action": "A11 판독표 「있음」 또는 미기입 · 멈춤 · 보고(%s)" % (ctx["a11"].get("why") or "있음 %s" % ctx["a11"].get("yes"))}

    if ctx["at_ceiling"]:
        return {"row": 5, "branch": "STOP", "action": "m3000 상한 · 보고(예산 끝)"}

    act = G.consume([prev_state, latest_state])

    if act == G.REVERT:
        return {"row": 6, "branch": "STOP", "action": "REVERT: 유지 실패 연속 두 저장본 · 멈춤, 되돌림 판은 사람이 띄움"}

    if latest_state == G.MAINTAIN_FAIL:
        return {"row": 7, "branch": "HOLD", "action": "같은 조건 한 창(250 회) 더 · 기록 + lead 알림"}

    if prev_state == G.MAINTAIN_FAIL:
        return {"row": 8, "branch": "CONTINUE", "action": "HOLD 해소 · 같은 조건 계속(실패 셈 리셋)"}

    if act == G.EXPAND:
        return {"row": 9, "branch": "NEXT_STAGE", "action": "EXPAND: 다음 카드(EX-36)가 없으면 멈춤 · 보고(성과 보존)"}

    if latest_state == G.NEW_TASK_PENDING and ctx["flat"]:
        return {"row": 11, "branch": "STOP", "action": "평평(연속 2 창 개선 없음) · 멈춤 · 보고"}

    return {"row": 10, "branch": "CONTINUE", "action": "같은 조건으로 250 회 연장 · 추세 기록"}


# ------------------------------------------------------------------ 축별 표


def _row(axis, name, v, base, limit, op, **kw):
    ok = None

    if limit is not None and v is not None:
        ok = bool(v >= limit) if op == ">=" else bool(v <= limit)

    return dict(axis=axis, metric=name, value=v, baseline=base, limit=limit, op=op, ok=ok, **kw)


def axes_rows(b, base, w=WIN) -> list:
    """한 저장본의 축별 값 · 기준선 · 하한 · 통과. 하한은 카드 4b.1 의 식 그대로(켬: 기준 x 0.90 …, 가림: 절대)."""
    T, E = G.THRESHOLDS, X.EX35_EXTRA
    rows = []
    f10, f05, al = G.fwd(b, "eval_gt")
    bf10, bf05, bal = G.fwd(base, "eval_gt")
    rows += [_row("A2", "켬 L0~2 fwd1.0 (m)", f10, bf10, bf10 * T["fwd_keep_frac_on"], ">="), _row("A2", "켬 L0~2 fwd0.5 (m)", f05, bf05, bf05 * E["on_fwd05_frac"], ">="),
             _row("A2", "켬 전진 생존", al, bal, E["on_survive_58"], ">=")]
    mf10, mf05, mal = G.fwd(b, "probe_prop_only")
    bmf10, bmf05, bmal = G.fwd(base, "probe_prop_only")
    rows += [_row("A2", "가림 L0~2 fwd1.0 (m)", mf10, bmf10, T["masked_fwd10_m"], ">="), _row("A2", "가림 L0~2 fwd0.5 (m)", mf05, bmf05, T["masked_fwd05_m"], ">="),
             _row("A2", "가림 전진 생존", mal, bmal, T["masked_survive_64"], ">=")]
    pm, bpm = (b.get("map64") or {}).get("eval_pred"), (base.get("map64") or {}).get("eval_pred")

    if pm and bpm:
        rows.append(_row("A2/A10", "eval_pred L0~2 fwd1.0 (m)", pm["fwd1.0"]["fwd_m"], bpm["fwd1.0"]["fwd_m"], bpm["fwd1.0"]["fwd_m"] * w["pred_fwd10_frac"], ">="))
        rows.append(_row("A10", "eval_pred L0~2 fwd0.5 (m, 기록)", pm["fwd0.5"]["fwd_m"], bpm["fwd0.5"]["fwd_m"], None, ">="))

    for L in ("L6", "L9"):
        h, bh = b["ext"]["hard"].get(L), base["ext"]["hard"].get(L)

        if not (h and bh):
            continue

        for mode, nm in (("eval_gt", "켬"), ("probe_prop_only", "가림")):
            v, bv = h["modes"][mode]["fwd1.0"], bh["modes"][mode]["fwd1.0"]
            rows.append(_row("A2", "%s %s fwd1.0 (m)" % (nm, L), v["fwd_m"], bv["fwd_m"], bv["fwd_m"] * w["hard_fwd10_frac"], ">="))
            rows.append(_row("A2", "%s %s fwd1.0 생존" % (nm, L), v["alive"], bv["alive"], bv["alive"] - w["hard_survive_drop"], ">="))

    for mode, nm in (("eval_gt", "켬"), ("probe_prop_only", "가림")):
        t, bt = G._turn(b, mode), G._turn(base, mode)

        for c in S.SIX_CASES:
            if c not in t or c not in bt:
                continue

            lim = (bt[c]["Q"] - T["hold_drop_q"], bt[c]["C"] + T["hold_rise_c"]) if mode == "eval_gt" else (None, None)
            rows += [_row("A3", "%s %s Q" % (nm, c), t[c]["Q"], bt[c]["Q"], lim[0], ">=", note="" if mode == "eval_gt" else "가림은 기록(카드 3 절 문턱은 켬)"),
                     _row("A3", "%s %s C" % (nm, c), t[c]["C"], bt[c]["C"], lim[1], "<="),
                     _row("A6", "%s %s kept" % (nm, c), t[c]["kept"], bt[c]["kept"], X.EX35_THR["min_kept"] if mode == "eval_gt" else None, ">=")]

        for c in S.WALK_CASES:
            if c not in t or c not in bt:
                continue

            s, bs = t[c], bt[c]
            need = T["walk_fwd_frac"] * S.P.PROTOCOLS[c]["cmd"][0] * S.P.RECORD_S
            rows += [_row("A5", "%s %s Q (유지)" % (nm, c), s["Q"], bs["Q"], bs["Q"] - w["walk_drop_q"], ">="), _row("A5", "%s %s Q (성공선)" % (nm, c), s["Q"], bs["Q"], T["walk_q"], ">="),
                     _row("A5", "%s %s C (유지)" % (nm, c), s["C"], bs["C"], bs["C"] + w["walk_rise_c"], "<="), _row("A5", "%s %s kept" % (nm, c), s["kept"], bs["kept"], w["walk_kept"], ">="),
                     _row("A5", "%s %s 반대 부호 env" % (nm, c), s["n_neg"], bs["n_neg"], 0, "<="),
                     _row("A5", "%s %s 전진 적분 (유지, m)" % (nm, c), s["vx_integral_kept_mean"], bs["vx_integral_kept_mean"], bs["vx_integral_kept_mean"] * w["walk_vx_frac"], ">="),
                     _row("A5", "%s %s 전진 적분 (성공선, m)" % (nm, c), s["vx_integral_kept_mean"], bs["vx_integral_kept_mean"], need, ">=")]

    for cmd, nm in (("spin+1.2", "좌"), ("spin-1.2", "우")):
        v, bv = G._map(b, "eval_gt")[cmd], G._map(base, "eval_gt")[cmd]
        rows.append(_row("A4", "켬 spin %s 추종" % nm, v["yaw_follow"], bv["yaw_follow"], max(bv["yaw_follow"] - E["spin_follow_drop"], E["spin_follow_floor"]), ">="))
        rows.append(_row("A4/A6", "켬 spin %s 생존" % nm, v["alive"], bv["alive"], E["spin_survive_64"], ">="))

    pt, bpt = b["ext"].get("pred_turn") or {}, base["ext"].get("pred_turn") or {}

    for c in S.SIX_CASES:
        if c in pt and c in bpt:
            rows.append(_row("A10", "eval_pred 16 env %s Q (기록)" % c, pt[c]["Q"], bpt[c]["Q"], None, ">="))

    return rows


def extra_rows(e) -> list:
    """A1 · A7 · A8 · A9 줄(axes_extra 의 결과). A1 은 기록, A7 · A8 · A9 는 경고(멈춤 조건 아님)."""
    rows = []

    for mode, nm in (("eval_gt", "켬"), ("probe_prop_only", "가림")):
        cur, base = e["a7a8"][mode], e["base_a7a8"][mode]
        rows += [_row("A7", "%s 회전 6 기울기 평균 중앙값 (deg, 경고)" % nm, cur["rot_tilt_mean_med"], base["rot_tilt_mean_med"], AX.A7_WARN["rot_mean_med"], "<="),
                 _row("A7", "%s 회전 6 기울기 p95 중앙값 (deg, 경고)" % nm, cur["rot_tilt_p95_med"], base["rot_tilt_p95_med"], AX.A7_WARN["rot_p95_med"], "<="),
                 _row("A8", "%s 회전 6 접촉 링크 속도 평균 중앙값 (m/s, 경고)" % nm, cur["rot_slip_mean_med"], base["rot_slip_mean_med"], AX.A8_WARN["rot_mean_med"], "<="),
                 _row("A8", "%s 회전 6 접촉 링크 속도 p95 중앙값 (m/s, 경고)" % nm, cur["rot_slip_p95_med"], base["rot_slip_p95_med"], AX.A8_WARN["rot_p95_med"], "<=")]

        for c in AX.FWD:
            rows += [_row("A7", "%s %s 기울기 평균 (deg, 경고)" % (nm, c), cur["fwd"][c]["tilt_mean_deg"], base["fwd"][c]["tilt_mean_deg"], base["fwd"][c]["tilt_mean_deg"] + AX.A7_WARN["fwd_plus_deg"], "<="),
                     _row("A8", "%s %s 접촉 링크 속도 평균 (m/s, 경고)" % (nm, c), cur["fwd"][c]["slip_mean"], base["fwd"][c]["slip_mean"], base["fwd"][c]["slip_mean"] * AX.A8_WARN["fwd_mult"], "<="),
                     _row("A1", "%s %s 대각 쌍 위상 (deg, 기록)" % (nm, c), e["a1"][mode][c]["deg"], None, None, ">="),
                     _row("A1", "%s %s 위상 집중도 R (기록)" % (nm, c), e["a1"][mode][c]["R"], None, None, ">=")]

    for t, v in e["a9"]["tags"].items():
        lim = AX.A9_WARN.get(t)
        rows.append(_row("A9", "%s 창 평균 (경고)" % t, v["mean"], None, lim[1] if lim else None, "<=" if (lim and lim[0] == ">") else ">="))

    return rows


# ------------------------------------------------------------------ 본체


def prev_window_problem(n_l, prev_window):
    """평평 판정(4b.2)에는 이전 창 경계의 출력이 필요하다. 첫 창(m2000 이하)은 추세가 없는 게 정상. m2250 이상에서 이전 창 json 이 없거나 회차가 맞지 않으면 문제 문구."""
    if n_l < 2250:
        return ""

    if not prev_window:
        return "최신이 m%d 인데 --prev-window(이전 창 경계 m%d 의 출력 json) 가 없다: 평평 판정을 할 수 없다" % (n_l, n_l - 250)

    if prev_window.get("latest_iter") != n_l - 250 or not prev_window.get("a5_q"):
        return "--prev-window 가 m%s 의 것이다(필요: m%d, a5_q 포함)" % (prev_window.get("latest_iter"), n_l - 250)

    return ""


def axes_extra(d, n, train_dir, base_dir) -> dict:
    """A1 · A7 · A8 · A9 와 필수 원자료 유한성. 자료가 없으면 AxisInputError (호출자가 HOLD_NO_DATA 로 올린다)."""
    out = {"nonfinite": AX.finite_scan(d, tuple(CASES8) + AX.FWD), "a7a8": {}, "a1": {}, "base_a7a8": {}}

    for mode in AX.MODES:
        out["a7a8"][mode] = AX.tilt_slip_axes(d, mode)
        out["base_a7a8"][mode] = AX.tilt_slip_axes(base_dir, mode)
        out["a1"][mode] = AX.gait_phase_axis(d, mode)

    if not train_dir:
        raise AX.AxisInputError("A9 학습 곡선: --train-dir(학습 폴더, tfevents) 가 없다")

    out["a9"] = AX.curve_axis(train_dir, n)
    out["warnings"] = []

    for mode in AX.MODES:
        out["warnings"] += [dict(w, mode=mode) for w in AX.a7_a8_warnings(out["a7a8"][mode], out["base_a7a8"][mode])]

    out["warnings"] += [dict(w, axis="A9") for w in out["a9"]["warnings"]]

    return out


def judge_window(latest_dir, prev_dir, *, base_dir=BASE_DEFAULT, hard_dir=HARD_DEFAULT, a11=None, prev_window=None, allow_map64_unmeasured=False, train_dir=None) -> dict:
    ld, pd = Path(latest_dir), Path(prev_dir)
    n_l, n_p = _iter_of(ld), _iter_of(pd)
    miss = {"latest": missing_inputs(ld), "prev": missing_inputs(pd)}
    base = load_base(base_dir, hard_dir)
    base_hard = {L: (h.get("assignment_sha256") or _json(Path(hard_dir) / ("sb10_" + L) / "map64" / "map_modes.json").get("fixed_terrain", {}).get("assignment_sha256")) for L, h in base["ext"]["hard"].items()}
    res = {"latest_iter": n_l, "prev_iter": n_p, "missing_inputs": miss, "thresholds": {"window": WIN, "ex35_extra": X.EX35_EXTRA}, "base": {"dir": str(base_dir), "hard": str(hard_dir)}}
    out_states, bundles, read_fail, ex = {}, {}, {"latest": None, "prev": None}, {}

    for tag, d, n in (("prev", pd, n_p), ("latest", ld, n_l)):
        if miss[tag]:                                                            # 평가가 도는 중이거나 반쯤 쓰인 폴더: 읽지 않고 판정 불가
            bundles[tag] = None
            out_states[tag] = {"state": G.HOLD_NO_DATA, "reasons": [G._cond("no_data", what=miss[tag])], "iter": n}
            continue

        try:
            b = load_ckpt(d)
            bundles[tag] = b
            ex[tag] = axes_extra(d, n, train_dir, base_dir)
            v = ckpt_state(b, base, n - 1500)
            out_states[tag] = {"state": v.state, "reasons": v.reasons, "iter": n}
        except Exception as e:                                                                  # noqa: BLE001  (읽기 실패 · 축 자료 없음은 판정 불가로, 예외로 죽지 않는다)
            bundles.setdefault(tag, None)
            read_fail[tag] = "%s: %s" % (type(e).__name__, e)
            out_states[tag] = {"state": G.HOLD_NO_DATA, "reasons": [G._cond("read_failed", read_fail[tag])], "iter": n}

    res["states"] = out_states
    res["read_failed"] = read_fail
    ls, ps = out_states["latest"]["state"], out_states["prev"]["state"]
    bl, bp = bundles.get("latest"), bundles.get("prev")
    shal, shap = (bl["ext"]["ckpt_sha_txt"] if bl else None), (bp["ext"]["ckpt_sha_txt"] if bp else None)
    a12 = {}

    for tag, d, b in (("latest", ld, bl), ("prev", pd, bp)):
        try:
            a12[tag] = reproduce_check(d, b, base_hard) if b else {"ok": False, "why": "입력 결측 또는 읽기 실패"}
        except Exception as e:                                                                  # noqa: BLE001
            a12[tag] = {"ok": False, "why": "%s: %s" % (type(e).__name__, e)}

    a11d = read_a11(a11, shal)
    lq = a5_q(bl) if bl and ls != G.HOLD_NO_DATA else {}
    tr = trend(lq, prev_window) if lq else {"has_prev": False, "delta": {}, "improved": None, "no_improve_streak": 0, "flat": False}
    prob = prev_window_problem(n_l, prev_window)
    a12_ok = bool(a12["latest"].get("ok") and a12["prev"].get("ok"))
    a12_note = ""

    if not allow_map64_unmeasured:                                                  # 카드 A12: 64 env 거리 · 생존의 독립 재계산. 환경별 자료가 없으면 통과가 아니다
        a12_note = "64 env 거리 · 생존의 독립 재계산이 없다(환경별 자료 없음): A12 미측 = 통과 아님"
        a12_ok = False

    nonfin = {t: (ex[t]["nonfinite"] if t in ex else []) for t in ("latest", "prev")}
    nf_curve = {t: (ex[t]["a9"]["nonfinite_tags"] if t in ex else []) for t in ("latest", "prev")}
    nonfinite_any = any(nonfin.values()) or any(nf_curve.values())
    res["nonfinite"] = {"raw": nonfin, "curve": nf_curve}
    res["a12_note"] = a12_note
    res["extra_axes"] = {t: ex.get(t) for t in ("latest", "prev")}
    res["warnings"] = {t: (ex[t]["warnings"] if t in ex else []) for t in ("latest", "prev")}
    ctx = {"input_missing": miss["latest"] + miss["prev"], "same_sha": bool(shal and shal == shap), "iter_increasing": n_l > n_p >= 0,
           "stop": G.STOP in (ls, ps) or nonfinite_any, "a12_ok": a12_ok, "a11": a11d, "trend_missing": prob,
           "at_ceiling": n_l >= WIN["ceiling_iter"], "flat": tr["flat"]}
    res["context"] = {k: v for k, v in ctx.items() if k != "a11"}
    res["a11"] = a11d
    res["a12"] = a12
    res["trend"] = tr
    res["a5_q"] = lq
    res["no_improve_streak"] = tr["no_improve_streak"]
    res["decision"] = truth_table(ps, ls, ctx)
    res["branch"] = res["decision"]["branch"]
    res["axes"] = {"latest": axes_rows(bl, base) + (extra_rows(ex["latest"]) if "latest" in ex else []) if bl and ls != G.HOLD_NO_DATA else [],
                   "prev": axes_rows(bp, base) + (extra_rows(ex["prev"]) if "prev" in ex else []) if bp and ps != G.HOLD_NO_DATA else []}

    return res


def _fmt(v):
    if v is None:
        return "-"

    if isinstance(v, float):
        return "NaN" if not math.isfinite(v) else ("%.4f" % v)

    return str(v)


def to_markdown(r) -> str:
    L = ["# EX-35 창 경계 판정 m%s (직전 m%s)" % (r["latest_iter"], r["prev_iter"]), "",
         "- 갈래: **%s** (진리표 %d 행) -- %s" % (r["branch"], r["decision"]["row"], r["decision"]["action"]),
         "- 상태: 직전 %s · 최신 %s" % (r["states"]["prev"]["state"], r["states"]["latest"]["state"]),
         "- 입력 결측: 최신 %s · 직전 %s" % (r["missing_inputs"]["latest"] or "없음", r["missing_inputs"]["prev"] or "없음"),
         "- A11: %s · A12: 최신 %s 직전 %s" % (r["a11"], r["a12"]["latest"].get("ok"), r["a12"]["prev"].get("ok")),
         "- A5 추세: %s" % r["trend"], ""]

    for tag in ("latest", "prev"):
        if r["states"][tag]["reasons"]:
            L.append("- %s 상태 근거: %s" % (tag, json.dumps(r["states"][tag]["reasons"], ensure_ascii=False)[:900]))

    L += ["", "| 축 | 지표 | 최신 | 최신 통과 | 직전 | 직전 통과 | 기준선 m1500 | 하한 |", "|---|---|---|---|---|---|---|---|"]
    prev = {(x["axis"], x["metric"]): x for x in r["axes"]["prev"]}

    for x in r["axes"]["latest"]:
        p = prev.get((x["axis"], x["metric"]), {})
        lim = ("%s %s" % (x["op"], _fmt(x["limit"]))) if x["limit"] is not None else "-"
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (x["axis"], x["metric"], _fmt(x["value"]), {True: "통과", False: "미달", None: "-"}[x["ok"]], _fmt(p.get("value")),
                                                          {True: "통과", False: "미달", None: "-"}[p.get("ok")], _fmt(x["baseline"]), lim))

    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EX-35 창 경계 판정 소비기(카드 v0.9 4b.6)")
    ap.add_argument("--latest-dir", required=True)
    ap.add_argument("--prev-dir", required=True)
    ap.add_argument("--base-dir", default=BASE_DEFAULT)
    ap.add_argument("--hard-dir", default=HARD_DEFAULT)
    ap.add_argument("--a11", default=None, help="lead 가 채운 판독 JSON")
    ap.add_argument("--prev-window", default=None, help="이전 창 경계의 출력 json(추세 · 평평 셈). 최신이 m2250 이상이면 필수(없으면 HOLD_NO_DATA)")
    ap.add_argument("--allow-map64-unmeasured", action="store_true", help="64 env 거리 · 생존에 독립 재계산이 없어도 A12 를 막지 않는다(기본: 막음. 카드 A12 예외를 승인받았을 때만)")
    ap.add_argument("--train-dir", default=None, help="학습 폴더(tfevents). A9 학습 곡선 계산에 필요, 없으면 HOLD_NO_DATA")
    ap.add_argument("--out-prefix", required=True, help="<prefix>.json 과 <prefix>.md 를 쓴다")
    a = ap.parse_args(argv)
    pw = json.loads(Path(a.prev_window).read_text(encoding="utf-8")) if a.prev_window else None
    r = judge_window(a.latest_dir, a.prev_dir, base_dir=a.base_dir, hard_dir=a.hard_dir, a11=a.a11, prev_window=pw, allow_map64_unmeasured=a.allow_map64_unmeasured, train_dir=a.train_dir)
    Path(a.out_prefix + ".json").write_text(json.dumps(r, ensure_ascii=False, indent=1, sort_keys=True, default=str), encoding="utf-8")
    Path(a.out_prefix + ".md").write_text(to_markdown(r), encoding="utf-8")
    print(json.dumps({"branch": r["branch"], "row": r["decision"]["row"], "states": {k: v["state"] for k, v in r["states"].items()}}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
