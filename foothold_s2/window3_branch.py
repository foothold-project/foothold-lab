"""창 3 분기표 입력 L · R · D 와 분기 판정, 창 판정 회전 층(기록 · 경고 · 멈춤) (SONNET-X25 W3-T6 · W3-P2). 순수 계산 + 파일 읽기, Kit 불필요.

기준 상수는 window3_criteria.py 에 있다(결과 전에 고정). 이 모듈은 상수를 바꾸지 않고 적용만 한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from foothold_s2 import window3_criteria as K


def spin_inputs(map_modes: dict, mode: str = "eval_pred") -> dict:
    """map_modes.json 에서 L(spin+1.2) · R(spin-1.2) 요추종 중앙값과 spin 생존 수."""
    m = map_modes["modes"][mode]

    return {"L": float(m["spin+1.2"]["yaw_follow_median"]), "R": float(m["spin-1.2"]["yaw_follow_median"]),
            "alive_L": int(m["spin+1.2"]["alive_envs_at_end"]), "alive_R": int(m["spin-1.2"]["alive_envs_at_end"]), "envs": int(map_modes["envs"])}


def rotation_layer(cur: dict, prev: dict | None = None) -> dict:
    """기록 · 경고 · 멈춤. cur · prev = spin_inputs 꼴. 멈춤이 있으면 level 멈춤, 경고만 있으면 경고, 아니면 통과."""
    L, R, envs = cur["L"], cur["R"], cur["envs"]
    lo, diff = min(L, R), abs(L - R)
    record = {"L": L, "R": R, "diff": diff, "weak_side": "R" if R < L else ("L" if L < R else "같음"), "alive_L": cur["alive_L"], "alive_R": cur["alive_R"], "envs": envs}
    warn, stop = [], []
    if lo < K.STOP_MIN_FOLLOW:
        stop.append(f"min(L, R) {lo:.2f} < {K.STOP_MIN_FOLLOW}")
    stop_surv = K.STOP_SURVIVAL_MIN * envs / K.SPIN_ENVS                      # 64 env 가 아니면 비율로 환산
    for side in ("L", "R"):
        if cur["alive_" + side] < stop_surv:
            stop.append(f"spin 생존 {side} {cur['alive_' + side]}/{envs} < {K.STOP_SURVIVAL_MIN}/{K.SPIN_ENVS}")
    if lo < K.WARN_MIN_FOLLOW:
        warn.append(f"min(L, R) {lo:.2f} < {K.WARN_MIN_FOLLOW}")
    if diff >= K.WARN_DIFF:
        warn.append(f"|L - R| {diff:.2f} >= {K.WARN_DIFF}")
    if prev is not None:
        for side in ("L", "R"):
            drop = prev["alive_" + side] / prev["envs"] - cur["alive_" + side] / envs
            if drop > K.WARN_SURVIVAL_DROP + 1e-12:
                warn.append(f"spin 생존 {side} 이전 창보다 {drop:.2f} 하락 > {K.WARN_SURVIVAL_DROP}")

    return {"record": record, "warn": warn, "stop": stop, "level": "멈춤" if stop else ("경고" if warn else "통과")}


RECOMMEND_NOTE = "분기 결과는 권고다. 창 3 기동은 팀장 승인 뒤. 문턱은 모두 [추정]."


def branch(L: float, R: float, D: float | None, D_other: float | None = None, d_status: str | None = None, d_other_status: str | None = None) -> dict:
    """v1.2.1 §2.3a 분기표 한 판. 검사 순서 D 붕괴 -> F(D 미측정) -> B -> C -> E(표 밖) -> A.
    D = 약한 방향 D(전체 구간, 추종 < 0.3 env 평균), D_other = 반대 방향 D(E 에서만 쓴다).
    d_status = "ok" | "missing"(probe 없음/실패) | "no_low_env"(probe 는 있으나 추종 < 0.3 인 남은 env 가 0). 생략하면 D 가 None 이면 missing.
    label: A · B · C · D · 멈춤 · «표 밖»(E 인데 D 가 없어 규칙이 없음, 판정 보류). B 기본이면 default_b=True."""
    lo, diff = min(L, R), abs(L - R)
    weak = lo < K.BRANCH_WEAK_MIN or diff >= K.BRANCH_DIFF_MIN
    status = d_status or ("ok" if D is not None else "missing")
    out = {"L": L, "R": R, "D": D, "D_other": D_other, "d_status": status, "weak": weak, "weak_side": "R" if R < L else ("L" if L < R else "같음"),
           "hit": [], "warn": [], "default_b": False, "via": None, "note": RECOMMEND_NOTE}

    def done(label, via=None):
        out["label"], out["via"] = label, via
        if label in "ABCD" and len(label) == 1:
            out["hit"] = [label]

        return out

    if L < K.BRANCH_COLLAPSE_MAX and R < K.BRANCH_COLLAPSE_MAX:
        return done("D", "붕괴")
    if weak:
        if D is None:                                                             # F
            if status == "no_low_env":
                out["warn"].append("D 를 셀 env(남고 추종 < 0.3)가 0 이다: D 가 아니라 회전 생존 쪽 문제. 멈춤")

                return done("멈춤", "F 추종 < 0.3 env 0")
            out["default_b"] = True
            out["warn"].append("D 미측정 · B 기본(한 번 다시 재고도 없을 때만. 영수증에 적고 §5 판정 때 D 를 잰다)")

            return done("B", "F B 기본")
        return done("B" if D >= K.BRANCH_D_C_MAX else "C", "D >= 0.3" if D >= K.BRANCH_D_C_MAX else "D < 0.3")        # 0.3 <= D < 0.5 도 B
    if lo >= K.BRANCH_STRONG_MIN and diff <= K.BRANCH_A_DIFF_MAX:
        return done("A", "강한 방향 둘")
    zero = lambda x, s: 0.0 if (x is None and s == "no_low_env") else x                 # E: 추종 < 0.3 env 가 없는 방향의 D 는 0(앉은 env 없음), 결측이 아니다 (lead 결정 10/25)
    ds = [x for x in (zero(D, status), zero(D_other, d_other_status)) if x is not None]                  # E: min 0.3~0.5 이고 차 < 0.25
    if len(ds) < 2:
        out["warn"].append("표 밖(E) 인데 두 방향 D 가 다 있지 않다: 규칙이 없어 판정 보류")

        return done("표 밖", "E D 없음")
    if max(ds) >= K.BRANCH_E_B_MIN:
        return done("B", "E max(D) >= 0.5")
    out["warn"].append("표 밖(E) -> A + 회전 층 경고 기록(처방 없음 · 창 3 = P0 또는 B 그대로)")

    return done("A", "E max(D) < 0.5")


def combine(branches: dict) -> dict:
    """두 판(이름 -> branch 결과)을 우선순위 D > B > C > A 로 합친다. A 는 둘 다 A 일 때만. 멈춤이 있으면 멈춤, «표 밖» 이 있으면 판정 보류. 결과는 권고."""
    labels = {k: v["label"] for k, v in branches.items()}
    base = {"per": labels, "note": RECOMMEND_NOTE, "default_b": [k for k, v in branches.items() if v.get("default_b")]}
    if "멈춤" in labels.values():
        return {"label": "멈춤", **base, "reason": "추종 < 0.3 env 가 없어 D 를 못 세는 판이 있다"}
    if "표 밖" in labels.values() and not ({"D", "B"} & set(labels.values())):          # 다른 판이 D · B 면 설계 우선순위(D > B > C > A)가 이미 정한다
        return {"label": "판정 보류", **base, "reason": "표 밖(E) 인데 D 가 없는 판이 있고, 다른 판이 D · B 도 아니다"}
    for b in K.BRANCH_PRIORITY:
        if b == "A":
            if all(lb == "A" for lb in labels.values()):
                return {"label": "A", **base}
        elif b in labels.values():
            return {"label": b, **base}

    return {"label": "판정 보류", **base, "reason": "A 와 다른 분기가 섞여 위 우선순위에 안 걸린다"}


def weak_direction_dwell(probe_folder, side: str) -> dict:
    """probe 폴더의 방향(side = 'R' 또는 'L') 시행들에서, 안 넘어졌고 추종 < 0.3 인 env 의 네 calf 최대 체류 평균.
    D(분기에 쓰는 값) = 전체 구간. 정체 구간 한정은 보조로만 적는다. 폴더나 기록이 없으면 status 'missing'."""
    from foothold_s2.eval import calf_band as C

    try:
        d = C.load(probe_folder)
    except (FileNotFoundError, KeyError) as e:
        return {"D": None, "status": "missing", "reason": f"{type(e).__name__}: {e}", "protocols": list(K.WEAK_PROTOCOLS[side])}
    whole, stalled, kept_n, fallen = [], [], 0, 0
    for p in K.WEAK_PROTOCOLS[side]:
        v = d["by_protocol"].get(p)
        if v is None or "dwell" not in v or "follow" not in v:
            return {"D": None, "status": "missing", "reason": f"{p} 시행 기록(wz · alive 포함)이 없다: {probe_folder}", "protocols": list(K.WEAK_PROTOCOLS[side])}
        k = v["kept"]
        kept_n += int(k.sum())
        fallen += int((~k).sum())
        low = k & (v["follow"] < K.BRANCH_LOW_FOLLOW)                             # NaN < x 는 False
        whole.extend(v["dwell"]["whole"][low].tolist())
        stalled.extend(v["dwell"]["stalled"][low].tolist())
    st = np.array(stalled, dtype=float)
    ok = ~np.isnan(st)
    info = {"n_low_env": len(whole), "n_kept": kept_n, "fallen": fallen, "trials_total": kept_n + fallen, "protocols": list(K.WEAK_PROTOCOLS[side]),
            "D_stalled_aux": float(st[ok].mean()) if ok.any() else None, "n_stalled_aux": int(ok.sum())}
    if not whole:
        return {"D": None, "status": "no_low_env", **info}

    return {"D": float(np.mean(whole)), "status": "ok", **info}


def check_inputs_match(mm: dict, probe_result: dict, prev_mm: dict) -> None:
    """같은 체크포인트 · 기대한 칸 배치 · 이전 창과 같은 평가 칸이 아니면 ValueError."""
    ck_m, ck_p = mm.get("checkpoint_sha256") or "", probe_result.get("checkpoint_sha256") or ""
    if not ck_m or ck_m != ck_p:
        raise ValueError(f"map_modes 와 probe 의 체크포인트 SHA 가 다르거나 없다: {ck_m[:12]!r} 대 {ck_p[:12]!r}")
    fm = ((mm.get("fixed_terrain") or {}).get("assignment_sha256") or "")
    fp = ((probe_result.get("fixed_terrain") or {}).get("assignment_sha256") or "")
    fv = ((prev_mm.get("fixed_terrain") or {}).get("assignment_sha256") or "")
    if not fm.startswith(K.EVAL64_FIXED_SHA12):
        raise ValueError(f"map_modes 칸 SHA {fm[:12]!r} 가 기대한 64 env 고정 칸 {K.EVAL64_FIXED_SHA12} 가 아니다")
    if not fp.startswith(K.PROBE16_FIXED_SHA12):
        raise ValueError(f"probe 칸 SHA {fp[:12]!r} 가 기대한 16 env 고정 칸 {K.PROBE16_FIXED_SHA12} 가 아니다")
    if fv != fm or prev_mm.get("envs") != mm.get("envs"):
        raise ValueError(f"이전 창 평가가 같은 칸이 아니다(비교 불가): {fv[:12]!r} 대 {fm[:12]!r}, envs {prev_mm.get('envs')} 대 {mm.get('envs')}")


def inputs_from_files(map_modes_json, probe_folder, prev_map_modes_json) -> dict:
    """prev_map_modes_json = 이전 창(부모 또는 직전 창)의 같은 평가 map_modes.json. 회전 층의 «생존 하락» 경고가 이것을 쓴다(필수)."""
    mm = json.loads(Path(map_modes_json).read_text(encoding="utf-8"))
    prev_mm = json.loads(Path(prev_map_modes_json).read_text(encoding="utf-8"))
    check_inputs_match(mm, json.loads((Path(probe_folder) / "probe_result.json").read_text(encoding="utf-8")), prev_mm)
    cur = spin_inputs(mm)
    prev = spin_inputs(prev_mm)
    side = "R" if cur["R"] < cur["L"] else "L"
    other = "L" if side == "R" else "R"
    dw, dw_o = weak_direction_dwell(probe_folder, side), weak_direction_dwell(probe_folder, other)
    # F: 약한 방향 D 가 없을 때 »한 번 다시 잰다« 는 사람이 하는 일이다. 코드는 status 를 그대로 남긴다.

    return {"spin": cur, "weak_side": side, "dwell": dw, "dwell_other": dw_o, "branch": branch(cur["L"], cur["R"], dw["D"], dw_o["D"], dw["status"], dw_o["status"]), "rotation_layer": rotation_layer(cur, prev), "prev_spin": prev,
            "criteria_sha256": K.criteria_sha256(), "checkpoint_iter": mm.get("checkpoint_iter"), "checkpoint_sha256": mm.get("checkpoint_sha256", "")[:12],
            "map_modes_fixed_sha": (mm.get("fixed_terrain") or {}).get("assignment_sha256")}


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 5 or (len(argv) - 1) % 4:
        raise SystemExit("usage: window3_branch <출력 json> <이름1> <map_modes.json 1> <probe 폴더 1> <이전 창 map_modes.json 1> [<이름2> <map_modes.json 2> <probe 폴더 2> <이전 창 map_modes.json 2> ...]  (이전 창 평가는 필수)")
    out_json, rest = argv[0], argv[1:]
    res = {rest[i]: inputs_from_files(rest[i + 1], rest[i + 2], rest[i + 3]) for i in range(0, len(rest), 4)}
    res_c = combine({k: v["branch"] for k, v in res.items()}) if len(res) > 1 else None
    Path(out_json).write_text(json.dumps({"판": res, "합침": res_c}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("창 3 분기 입력(미검증 집계, reviewer 확인 전). 기준 파일 SHA", K.criteria_sha256()[:12])
    print(RECOMMEND_NOTE)
    print("D = 약한 방향 시행에서 안 넘어졌고 추종 < 0.3 인 env 의 네 calf 최대 체류(전체 구간) 평균. 정체 구간 한정 값은 보조.")
    print("| 판 | iter | L(spin+1.2) | R(spin-1.2) | abs(L-R) | 약한 방향 | D(전체 구간) | 반대 방향 D | 보조: 정체 한정 D | D 를 센 env / 남은 / 전체 | spin 생존 L · R | 분기(권고) | 경로 | 회전 층 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    def f(x):
        return "미측정" if x is None else f"{x:.2f}"

    for name, v in res.items():
        s, d, o, b, r = v["spin"], v["dwell"], v["dwell_other"], v["branch"], v["rotation_layer"]
        print(f"| {name} | {v['checkpoint_iter']} | {s['L']:.2f} | {s['R']:.2f} | {abs(s['L'] - s['R']):.2f} | {v['weak_side']} | {f(d['D'])} ({d['status']}) | {f(o['D'])} ({o['status']}) | {f(d.get('D_stalled_aux'))} | "
              f"{d.get('n_low_env', '-')}/{d.get('n_kept', '-')}/{d.get('trials_total', '-')} | {s['alive_L']} · {s['alive_R']} /{s['envs']} | {b['label']}{' (B 기본)' if b['default_b'] else ''} | {b['via']} {b['warn'] or ''} | {r['level']} {r['stop'] or r['warn']} |")
    if res_c:
        print(f"\n합침(우선순위 D > B > C > A, 멈춤 우선): {res_c['label']} {res_c['per']} {res_c.get('reason', '')}")


if __name__ == "__main__":
    main()
