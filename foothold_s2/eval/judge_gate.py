"""판정과 커리큘럼 관문 (JUDGE-SPEC v0.2 4 절 · J-T3 · J-T8 · J-T9). 순수 함수, Kit 없음.

입력은 `judge_stats.load_bundle` 이 만든 평가 묶음(최신 · 직전 · 기준 · 단계 시작). 출력은 상태 하나와 그 근거(`Verdict`)다.
상태 다섯: STOP · HOLD_NO_DATA · MAINTAIN_FAIL · NEW_TASK_PENDING · PASS.
  - STOP: 운영 중단(NaN · 비유한값 · 기동 실패 · 64 env 회전 생존 < 48 · 전진 유지 미달 · 어느 경우 Q < 0.12). 이어 가기 판에만. 회복 불가 판정이 아니다.
  - HOLD_NO_DATA: 파일 · 직전 평가 자료가 «없을» 때만. 관측된 낙상(kept 작음)은 여기 오지 않는다.
  - MAINTAIN_FAIL: 유지 조건(하락 · 넘어짐 · 전진 유지) 중 하나라도 최신 또는 직전이 미달.
  - NEW_TASK_PENDING: 유지는 되는데 새 과제 성공선 미달 또는 단계 체류(`min_stay`) 부족.
  - PASS: 둘 다 최신 + 직전 연속 통과.
동작(계속 · 보류 · 되돌림 · 멈춤)은 상태 열을 세는 소비자 `consume` · `Consumer` 가 정한다.
세 규칙: `judge_continue`(이어 가기 판, 회전 명령 과정), `judge_ratio`(지도 비율 단계 4.5), `judge_scratch`(처음부터 배우는 판 4.3: 유지선 · 멈춤선 없음).
문턱은 전부 `THRESHOLDS` 한 곳. 추정이며 승인 값이 아니다(결과를 본 뒤 넓히지 않는다).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

from foothold_s2.eval import judge_stats as S
from foothold_s2.eval import turn_probe_plan as P

STOP, HOLD_NO_DATA, MAINTAIN_FAIL, NEW_TASK_PENDING, PASS = "STOP", "HOLD_NO_DATA", "MAINTAIN_FAIL", "NEW_TASK_PENDING", "PASS"
STATES = (STOP, HOLD_NO_DATA, MAINTAIN_FAIL, NEW_TASK_PENDING, PASS)
CONTINUE, HOLD, REVERT, STOP_REPORT, EXPAND = "CONTINUE", "HOLD", "REVERT", "STOP_REPORT", "EXPAND"

ON_MODES = ("eval_gt", "eval_pred")
MASKED_MODES = ("probe_prop_only", "none")

THRESHOLDS = {
    "spec_version": S.SPEC_VERSION,
    # 회전 성공선(새 과제)
    "success_q": 0.6, "success_c": 0.6, "success_kept": 14, "success_neg": 0,
    "s3b_rot_survive_64": 54,
    # 걸으며 돌기(4.4): 명령 0.5/1.2 비례로 옮긴 추정
    "walk_q": 0.25, "walk_c": 0.6, "walk_kept": 14, "walk_fwd_frac": 0.8,
    # 유지 하락 허용
    "hold_drop_q": 0.20, "hold_rise_c": 0.25,
    # 넘어짐 허용
    "min_kept": 12, "rot_survive_64": 48, "fwd_survive_drop_64": 6,
    # 전진 유지 · 가림 전진
    "fwd_keep_frac_on": 0.90,
    "masked_fwd10_m": 4.592, "masked_fwd05_m": 2.310, "masked_survive_64": 60, "masked_start_frac": 0.8,
    "on_fwd10_m": 5.097, "on_survive_64": 54,
    "pred_over_gt_frac": 0.90,
    # 운영 중단선(이어 가기 판만)
    "stop_q": 0.12,
}


class JudgeConfigError(ValueError):
    """호출이 틀렸다(알 수 없는 단계 · 기준 묶음이 무효 등). 판정 상태가 아니라 코드 오류로 올린다."""


# ------------------------------------------------------------------ 결과 객체


@dataclass
class Verdict:
    state: str
    rule: str
    stage: str = ""
    mode: str = ""
    reasons: list = field(default_factory=list)              # 상태를 정한 근거 조건들 [{cond, case/cmd, window, value, limit}]
    detail: dict = field(default_factory=dict)               # 경우별 turn_valid · survival_ok 등
    inputs: dict = field(default_factory=dict)               # 입력 파일 SHA

    def to_dict(self) -> dict:
        return {"state": self.state, "rule": self.rule, "stage": self.stage, "mode": self.mode, "reasons": self.reasons, "detail": self.detail,
                "inputs": self.inputs, "thresholds": THRESHOLDS}

    def record_line(self) -> str:
        """J-T8: 한 줄 JSON. 같은 입력이면 같은 문자열(정렬 · 소수 6자리 · 시각 없음)."""
        return json.dumps(_norm(self.to_dict()), sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def record_sha256(self) -> str:
        return hashlib.sha256(self.record_line().encode("utf-8")).hexdigest()


def _norm(o):
    if isinstance(o, dict):
        return {str(k): _norm(v) for k, v in o.items()}

    if isinstance(o, (list, tuple)):
        return [_norm(v) for v in o]

    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 6)

    return o


def _cond(cond, value=None, limit=None, window=None, **kw):
    d = {"cond": cond}

    if value is not None:
        d["value"] = value

    if limit is not None:
        d["limit"] = limit

    if window is not None:
        d["window"] = window

    d.update(kw)

    return d


# ------------------------------------------------------------------ 묶음 읽기


def masked_mode(b):
    for m in MASKED_MODES:
        if b.get("map64") and m in b["map64"]:
            return m

    return None


def _turn(b, mode):
    return (b.get("turn") or {}).get(mode) or {}


def _map(b, mode):
    return ((b.get("map64") or {}).get(mode)) or {}


def has_turn_cases(b, mode, cases=S.SIX_CASES) -> bool:
    t = _turn(b, mode)

    return all(c in t for c in cases)


def has_map64(b, mode) -> bool:
    m = _map(b, mode)

    return all(c in m for c in S.MAP64_CMDS)


def fwd(b, mode):
    """(fwd1.0 m, fwd0.5 m, 전진 생존 최솟값 / 64). 생존은 두 전진 명령 중 작은 쪽(보수적)."""
    m = _map(b, mode)

    return m["fwd1.0"]["fwd_m"], m["fwd0.5"]["fwd_m"], min(m["fwd1.0"]["alive"], m["fwd0.5"]["alive"])


def rot_alive(b, mode):
    m = _map(b, mode)

    return min(m["spin+1.2"]["alive"], m["spin-1.2"]["alive"])


def case_status(s: dict, thr=THRESHOLDS) -> dict:
    """경우 하나의 두 사실을 따로 적는다: turn_valid(회전 통계가 평균을 낼 만한가) · survival_ok(생존 조건). 둘 다 kept 가 문턱 이상이어야 참이다."""
    ok = s["kept"] >= thr["min_kept"]

    return {"kept": s["kept"], "alive_end": s["alive_end"], "turn_valid": bool(ok and math.isfinite(s["Q"])), "survival_ok": bool(ok),
            "Q": s["Q"] if ok else None, "Q_raw": s["Q"], "C": s["C"] if ok else None, "n_ge06": s["n_ge06"], "n_neg": s["n_neg"]}


def case_table(b, mode, cases=S.SIX_CASES) -> dict:
    t = _turn(b, mode)

    return {c: case_status(t[c]) for c in cases if c in t}


# ------------------------------------------------------------------ 조건 모음


def _incomplete(b, mode, cases=S.SIX_CASES, need_map=True) -> list:
    out = []

    if b is None:
        return ["bundle"]

    if b.get("missing"):
        out.append("missing:" + ";".join(b.get("missing_what") or ["?"]))

    if not has_turn_cases(b, mode, cases):
        out.append("turn16/%s" % mode)

    if need_map and not has_map64(b, mode):
        out.append("map64/%s" % mode)

    return out


def forward_hold_broken(b, base, mode, thr=THRESHOLDS, window="latest") -> list:
    """전진 유지: 켬은 fwd1.0 >= 기준 x 0.90, 가림은 절대(4.592 · 2.310 · 생존 60/64). 둘 다 전진 생존이 기준보다 6/64 넘게 줄지 않음(켬만)."""
    out = []
    f10, f05, al = fwd(b, mode)

    if mode in ON_MODES:
        bf10, _bf05, bal = fwd(base, mode)

        if f10 < bf10 * thr["fwd_keep_frac_on"]:
            out.append(_cond("fwd_keep_on", f10, bf10 * thr["fwd_keep_frac_on"], window, cmd="fwd1.0"))

        for cmd in ("fwd0.5", "fwd1.0"):
            a, ba = _map(b, mode)[cmd]["alive"], _map(base, mode)[cmd]["alive"]

            if ba - a > thr["fwd_survive_drop_64"]:
                out.append(_cond("fwd_survive_drop", a, ba - thr["fwd_survive_drop_64"], window, cmd=cmd))
    else:
        if f10 < thr["masked_fwd10_m"]:
            out.append(_cond("masked_fwd10", f10, thr["masked_fwd10_m"], window, cmd="fwd1.0"))

        if f05 < thr["masked_fwd05_m"]:
            out.append(_cond("masked_fwd05", f05, thr["masked_fwd05_m"], window, cmd="fwd0.5"))

        if al < thr["masked_survive_64"]:
            out.append(_cond("masked_survive_64", al, thr["masked_survive_64"], window))

    return out


def maintain_broken(b, base, mode, thr=THRESHOLDS, window="latest") -> list:
    """이어 가기 판의 유지 조건(3 절): 유지 하락 허용 + 넘어짐 허용 + 전진 유지, 셋 모두. 깨진 조건 목록(비면 유지)."""
    out = []
    t, bt = _turn(b, mode), _turn(base, mode)

    for c in S.SIX_CASES:
        st = case_status(t[c], thr)

        if not st["survival_ok"]:
            out.append(_cond("survival_16", t[c]["kept"], thr["min_kept"], window, case=c, turn_valid=False, survival_ok=False))
            continue

        bs = case_status(bt[c], thr)

        if not bs["turn_valid"]:
            raise JudgeConfigError("기준 묶음의 %s 가 무효(kept %d < %d): 기준으로 쓸 수 없다" % (c, bt[c]["kept"], thr["min_kept"]))

        if t[c]["Q"] < bt[c]["Q"] - thr["hold_drop_q"]:
            out.append(_cond("drop_Q", t[c]["Q"], bt[c]["Q"] - thr["hold_drop_q"], window, case=c))

        if t[c]["C"] > bt[c]["C"] + thr["hold_rise_c"]:
            out.append(_cond("rise_C", t[c]["C"], bt[c]["C"] + thr["hold_rise_c"], window, case=c))

    if rot_alive(b, mode) < thr["rot_survive_64"]:
        out.append(_cond("rot_survive_64", rot_alive(b, mode), thr["rot_survive_64"], window))

    out += forward_hold_broken(b, base, mode, thr, window)

    return out


def operational_stop(b, base, mode, thr=THRESHOLDS) -> list:
    """이어 가기 판의 운영 중단선. 자료가 있는 만큼만 본다(없으면 HOLD_NO_DATA 로 넘어간다)."""
    out = []

    if b.get("launch_failed"):
        out.append(_cond("launch_failed"))

    if b.get("nonfinite"):
        out.append(_cond("nonfinite"))

    if _incomplete(b, mode):
        return out

    if rot_alive(b, mode) < thr["rot_survive_64"]:
        out.append(_cond("rot_survive_64", rot_alive(b, mode), thr["rot_survive_64"]))

    # 전진 유지 미달(켬 fwd1.0 < 기준 x 0.90, 가림 절대선)은 멈춤선. 켬의 «전진 생존이 기준보다 6/64 넘게 줄었다» 는 넘어짐 허용(유지 조건)이라 멈춤이 아니다
    out += [dict(c, cond="stop_" + c["cond"]) for c in forward_hold_broken(b, base, mode, thr) if c["cond"] != "fwd_survive_drop"]

    for c, s in _turn(b, mode).items():
        if c in S.SIX_CASES and case_status(s, thr)["turn_valid"] and s["Q"] < thr["stop_q"]:
            out.append(_cond("stop_q", s["Q"], thr["stop_q"], case=c))

    return out


# ------------------------------------------------------------------ 새 과제 성공선 (4.4)

STAGES = {
    "S1->S2a": {"needs": (), "check": "none", "precondition": "terrain_mark"},
    "S2a->S2b": {"needs": S.WALK_CASES, "check": "walk"},
    "S2b->S3": {"needs": S.WALK_CASES, "check": "walk"},
    "S3->S3b": {"needs": (), "check": "six"},
}


def _split_success(s, window, case, q_min, c_max, kept_min, name, **extra):
    """성공선의 성분을 따로 적는다(Q · C · kept · 반대 방향 env). 어느 성분이 깨졌는지가 보여야 한다."""
    out = []

    if s["Q"] < q_min:
        out.append(_cond(name + "_q", s["Q"], q_min, window, case=case, **extra))

    if s["C"] > c_max:
        out.append(_cond(name + "_c", s["C"], c_max, window, case=case, **extra))

    if s["kept"] < kept_min:
        out.append(_cond(name + "_kept", s["kept"], kept_min, window, case=case, **extra))

    if s["n_neg"] > 0:
        out.append(_cond(name + "_neg", s["n_neg"], 0, window, case=case, **extra))

    return out


def _success_six(b, mode, thr, window) -> list:
    out = []
    t = _turn(b, mode)

    for c in S.SIX_CASES:
        out += _split_success(t[c], window, c, thr["success_q"], thr["success_c"], thr["success_kept"], "success_six")

    if rot_alive(b, mode) < thr["s3b_rot_survive_64"]:
        out.append(_cond("s3b_rot_survive_64", rot_alive(b, mode), thr["s3b_rot_survive_64"], window))

    return out


def _success_walk(b, mode, thr, window) -> list:
    out = []
    t = _turn(b, mode)

    for c in S.WALK_CASES:
        s = t[c]
        out += _split_success(s, window, c, thr["walk_q"], thr["walk_c"], thr["walk_kept"], "success_walk")
        need_int = thr["walk_fwd_frac"] * P.PROTOCOLS[c]["cmd"][0] * P.RECORD_S

        if not s["vx_integral_kept_mean"] >= need_int:
            out.append(_cond("success_walk_vx", s["vx_integral_kept_mean"], need_int, window, case=c))

    return out


def new_task_broken(b, stage, mode, preconditions, thr=THRESHOLDS, window="latest") -> list:
    spec = STAGES[stage]

    if spec["check"] == "none":
        pre = spec.get("precondition")

        return [] if (preconditions or {}).get(pre) else [_cond("precondition", False, True, window, name=pre)]

    return _success_walk(b, mode, thr, window) if spec["check"] == "walk" else _success_six(b, mode, thr, window)


# ------------------------------------------------------------------ 판정: 이어 가기 판


def _inputs(**bundles) -> dict:
    return {k: dict(sorted((b.get("sources") or {}).items())) for k, b in bundles.items() if b is not None}


def judge_continue(latest, prev, base, stage, it_in_stage, min_stay, *, mode="eval_gt", preconditions=None, thr=THRESHOLDS) -> Verdict:
    """4.1 의사 코드. latest · prev · base 는 `load_bundle` 묶음(prev 는 None 가능). min_stay 는 호출자가 넣는다(함수 안에 고정값 없음)."""
    if stage not in STAGES:
        raise JudgeConfigError("알 수 없는 단계 %r (표: %s)" % (stage, list(STAGES)))

    needs = tuple(S.SIX_CASES) + tuple(STAGES[stage]["needs"])
    v = Verdict(state=PASS, rule="continue", stage=stage, mode=mode, inputs=_inputs(latest=latest, prev=prev, base=base))
    v.detail = {"cases": case_table(latest, mode, needs), "it_in_stage": it_in_stage, "min_stay": min_stay}
    stop = operational_stop(latest, base, mode, thr)

    if stop:
        v.state, v.reasons = STOP, stop

        return v

    inc = _incomplete(latest, mode, needs) + (["prev"] if prev is None else _incomplete(prev, mode, needs))

    if inc:
        v.state, v.reasons = HOLD_NO_DATA, [_cond("no_data", what=inc)]

        return v

    broken = maintain_broken(latest, base, mode, thr, "latest") + maintain_broken(prev, base, mode, thr, "prev")

    if broken:
        v.state, v.reasons = MAINTAIN_FAIL, broken

        return v

    pending = new_task_broken(latest, stage, mode, preconditions, thr, "latest") + new_task_broken(prev, stage, mode, preconditions, thr, "prev")

    if it_in_stage < min_stay:
        pending.insert(0, _cond("min_stay", it_in_stage, min_stay))

    if pending:
        v.state, v.reasons = NEW_TASK_PENDING, pending

        return v

    return v


# ------------------------------------------------------------------ 판정: 처음부터 배우는 판 (4.3)


def _kept_ok(b, mode, thr) -> dict:
    """16 env 여섯 경우가 모두 kept >= 12 인가. 자료가 없으면 known=False(달성으로 치지 않는다)."""
    t = _turn(b, mode)

    if not has_turn_cases(b, mode):
        return {"known": False, "ok": False, "short": []}

    short = [c for c in S.SIX_CASES if t[c]["kept"] < thr["min_kept"]]

    return {"known": True, "ok": not short, "short": short}


def scratch_progress(b, thr=THRESHOLDS) -> dict:
    """한 저장본의 진도 판독(기록용). 켬 · 가림 전진(64 env)과 16 env 생존(여섯 경우 kept >= 12)이 모두 되면 달성. 여섯 경우 Q 는 기록만(목표 아님). 멈춤 근거가 아니다."""
    out = {"on": None, "masked": None, "rotation": {}}

    if b is None or not b.get("map64"):
        return out

    if "eval_gt" in b["map64"] and has_map64(b, "eval_gt"):
        f10, f05, al = fwd(b, "eval_gt")
        k = _kept_ok(b, "eval_gt", thr)
        out["on"] = {"fwd10": f10, "fwd05": f05, "alive": al, "kept_ok": k["ok"], "kept_known": k["known"], "kept_short": k["short"],
                     "met": bool(f10 >= thr["on_fwd10_m"] and al >= thr["on_survive_64"] and k["ok"])}

    mm = masked_mode(b)

    if mm and has_map64(b, mm):
        f10, f05, al = fwd(b, mm)
        k = _kept_ok(b, mm, thr)
        out["masked"] = {"mode": mm, "fwd10": f10, "fwd05": f05, "alive": al, "kept_ok": k["ok"], "kept_known": k["known"], "kept_short": k["short"],
                         "met": bool(f10 >= thr["masked_fwd10_m"] and f05 >= thr["masked_fwd05_m"] and al >= thr["masked_survive_64"] and k["ok"])}

    for mode, cs in (b.get("turn") or {}).items():
        out["rotation"][mode] = {c: {"Q": s["Q"], "C": s["C"], "kept": s["kept"], "met": bool(s["kept"] >= thr["min_kept"] and s["Q"] >= thr["success_q"])} for c, s in cs.items()}

    return out


def judge_scratch(latest, prev, *, require=("on", "masked"), thr=THRESHOLDS) -> Verdict:
    """처음부터 배우는 판. 부모 유지선(0.20) · 운영 중단선(0.12 · 48/64 · 전진 0.90)을 걸지 않는다. MAINTAIN_FAIL 은 나오지 않는다.

    STOP: 기동 실패 · 비유한값 · 64 env 전진 생존 0 이 두 저장본 연속. PASS(= 달성): require 한 종류(켬 · 가림)가 최신 + 직전 모두 달성.
    그 밖에는 NEW_TASK_PENDING(= 달성 미달 · 계속 관찰), 직전 자료가 없으면 HOLD_NO_DATA.
    """
    v = Verdict(state=NEW_TASK_PENDING, rule="scratch", inputs=_inputs(latest=latest, prev=prev))
    pl, pp = scratch_progress(latest, thr), scratch_progress(prev, thr)
    v.detail = {"progress_latest": pl, "progress_prev": pp if prev is not None else None}

    if latest.get("launch_failed") or latest.get("nonfinite"):
        v.state, v.reasons = STOP, [_cond("launch_failed" if latest.get("launch_failed") else "nonfinite")]

        return v

    def zero_fwd(b):
        modes = [m for m in ("eval_gt", masked_mode(b)) if m and has_map64(b, m)]

        return bool(modes) and all(fwd(b, m)[2] == 0 for m in modes)

    if prev is not None and not prev.get("missing") and not latest.get("missing") and zero_fwd(latest) and zero_fwd(prev):
        v.state, v.reasons = STOP, [_cond("fwd_survive_zero_twice")]

        return v

    if latest.get("missing") or prev is None or prev.get("missing"):
        v.state, v.reasons = HOLD_NO_DATA, [_cond("no_data", what=(latest.get("missing_what") or []) + ([] if prev is not None else ["prev"]))]

        return v

    unmet = []

    for kind in require:
        for window, p in (("latest", pl), ("prev", pp)):
            if not (p.get(kind) and p[kind]["met"]):
                unmet.append(_cond("achievement_" + kind, window=window))

    if unmet:
        v.reasons = unmet

        return v

    v.state = PASS

    return v


# ------------------------------------------------------------------ 판정: 지도 비율 단계 (4.5)

RATIO_TRANSITIONS = ("a_to_b", "b_step", "b_to_c", "c_hold")


def _masked_turn_broken(b, mm, thr, window) -> list:
    out = []

    for c in S.SIX_CASES:
        k = _turn(b, mm)[c]["kept"]

        if k < thr["min_kept"]:
            out.append(_cond("masked_kept_16", k, thr["min_kept"], window, case=c))

    return out


def _masked_abs_broken(b, mm, thr, window) -> list:
    f10, f05, al = fwd(b, mm)
    out = []

    if f10 < thr["masked_fwd10_m"]:
        out.append(_cond("masked_fwd10", f10, thr["masked_fwd10_m"], window, cmd="fwd1.0"))

    if f05 < thr["masked_fwd05_m"]:
        out.append(_cond("masked_fwd05", f05, thr["masked_fwd05_m"], window, cmd="fwd0.5"))

    if al < thr["masked_survive_64"]:
        out.append(_cond("masked_survive_64", al, thr["masked_survive_64"], window))

    return out + _masked_turn_broken(b, mm, thr, window)


def _on_abs_broken(b, thr, window) -> list:
    f10, _f05, al = fwd(b, "eval_gt")
    out = []

    if f10 < thr["on_fwd10_m"]:
        out.append(_cond("on_fwd10", f10, thr["on_fwd10_m"], window))

    if al < thr["on_survive_64"]:
        out.append(_cond("on_survive_64", al, thr["on_survive_64"], window))

    return out


def _ratio_split(b, start, transition, thr, window):
    """(유지 조건 깨짐, 진입 조건 미달) 목록. 자료는 미리 확인되어 있어야 한다."""
    mm = masked_mode(b)

    if transition == "a_to_b":
        return [], _masked_abs_broken(b, mm, thr, window)

    if transition == "b_step":
        out = []
        f10, _f05, _al = fwd(b, mm)
        sf10, _sf05, _sal = fwd(start, masked_mode(start))

        if f10 < thr["masked_start_frac"] * sf10:
            out.append(_cond("masked_fwd10_vs_start", f10, thr["masked_start_frac"] * sf10, window, cmd="fwd1.0"))

        out += _masked_abs_broken(b, mm, thr, window)
        on10, _o, _a = fwd(b, "eval_gt")
        son10, _so, _sa = fwd(start, "eval_gt")

        if on10 < thr["fwd_keep_frac_on"] * son10:
            out.append(_cond("on_fwd10_vs_start", on10, thr["fwd_keep_frac_on"] * son10, window, cmd="fwd1.0"))

        return out, []

    if transition == "b_to_c":
        return _masked_abs_broken(b, mm, thr, window), _on_abs_broken(b, thr, window)

    out = _masked_abs_broken(b, mm, thr, window) + _on_abs_broken(b, thr, window)
    gt10, pr10 = fwd(b, "eval_gt")[0], fwd(b, "eval_pred")[0]

    if pr10 < thr["pred_over_gt_frac"] * gt10:
        out.append(_cond("pred_over_gt", pr10, thr["pred_over_gt_frac"] * gt10, window))

    return out, []


def judge_ratio(latest, prev, start, transition, it_in_stage, min_stay, *, thr=THRESHOLDS) -> Verdict:
    """지도 비율 단계의 관문(4.5). transition: a_to_b · b_step · b_to_c · c_hold.

    b_step 의 유지 조건: 가림 fwd1.0 >= 단계 시작 x 0.8 그리고 >= 4.592, fwd0.5 >= 2.310, 생존 >= 60/64, 16 env 가림 kept >= 12 모두, 켬 fwd1.0 >= 단계 시작 x 0.90.
    c_hold 는 절대 조건을 상속한다(상대 조건만이면 GT 0.5 m · PRED 0.5 m 도 통과한다). `start` 는 b_step 에서만 쓴다.
    """
    if transition not in RATIO_TRANSITIONS:
        raise JudgeConfigError("알 수 없는 전이 %r (표: %s)" % (transition, list(RATIO_TRANSITIONS)))

    v = Verdict(state=PASS, rule="ratio", stage=transition, inputs=_inputs(latest=latest, prev=prev, start=start))
    v.detail = {"it_in_stage": it_in_stage, "min_stay": min_stay}

    if latest.get("launch_failed") or latest.get("nonfinite"):
        v.state, v.reasons = STOP, [_cond("launch_failed" if latest.get("launch_failed") else "nonfinite")]

        return v

    def incomplete(b):
        if b is None:
            return ["bundle"]

        mm = masked_mode(b)
        out = list(b.get("missing_what") or [])

        if mm is None:
            return out + ["map64/masked"]

        for need in ((mm,) + (("eval_gt",) if transition != "a_to_b" else ()) + (("eval_pred",) if transition == "c_hold" else ())):
            if not has_map64(b, need):
                out.append("map64/" + need)

        if not has_turn_cases(b, mm):
            out.append("turn16/" + mm)

        return out

    need_start = transition == "b_step"
    inc = incomplete(latest) + (["prev"] if prev is None else incomplete(prev)) + (incomplete(start) if need_start else [])

    if inc:
        v.state, v.reasons = HOLD_NO_DATA, [_cond("no_data", what=inc)]

        return v

    maint, entry = [], []

    for window, b in (("latest", latest), ("prev", prev)):
        m, e = _ratio_split(b, start, transition, thr, window)
        maint += m
        entry += e

    if maint:
        v.state, v.reasons = MAINTAIN_FAIL, maint

        return v

    if it_in_stage < min_stay:
        entry.insert(0, _cond("min_stay", it_in_stage, min_stay))

    if entry:
        v.state, v.reasons = NEW_TASK_PENDING, entry

    return v


# ------------------------------------------------------------------ 소비자 (J-T9)


def consume(history, reverts_done: int = 0) -> str:
    """상태 열 -> 동작. 마지막 상태 기준: STOP -> 멈춤 · 보고, MAINTAIN_FAIL 두 번 연속 -> REVERT(이미 한 번 되돌렸으면 멈춤 · 보고),
    MAINTAIN_FAIL 한 번 -> 보류(같은 조건 한 창 더), PASS -> 한 축 확대, 그 밖 -> 계속."""
    h = list(history)

    if not h:
        return CONTINUE

    if h[-1] == STOP:
        return STOP_REPORT

    if h[-2:] == [MAINTAIN_FAIL, MAINTAIN_FAIL]:
        return STOP_REPORT if reverts_done >= 1 else REVERT

    if h[-1] == MAINTAIN_FAIL:
        return HOLD

    if h[-1] == PASS:
        return EXPAND

    return CONTINUE


class Consumer:
    """평가 사슬이 들고 있는 소비자. 상태를 하나씩 받아 동작을 돌려준다. 되돌림 횟수를 세고, 되돌림 · 확대 뒤에는 새 창이라 열을 비운다(회복을 두 저장본으로 다시 잰다)."""

    def __init__(self):
        self.history = []
        self.reverts = 0
        self.log = []

    def step(self, state: str) -> str:
        self.history.append(state)
        action = consume(self.history, self.reverts)
        self.log.append((state, action))

        if action == REVERT:
            self.reverts += 1
            self.history = []
        elif action == EXPAND:
            self.history = []

        return action
