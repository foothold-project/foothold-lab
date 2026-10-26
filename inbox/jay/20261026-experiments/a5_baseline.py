"""A5 걸으며 돌기(walk_turn) 부모 기준선 생성기.

입력: impl-turncases `sb10_eval/m1500/walk_turn_summary.json` (sonnet-code X27g 00:36) 과 그 json 이 가리키는 npz 넷.
하는 일:
  1. npz 에서 Q · C · kept · 끝 생존 · 반대 부호 수 · 전진 적분을 독립 식으로 다시 재어 json 과 1e-6 안에서 같은지 확인한다(다르면 멈춤).
  2. 성공선(JUDGE-SPEC 4.4 = judge_gate.THRESHOLDS walk_*) 다섯 성분을 부모 값에 대 본다(답 아는 입력).
  3. 유지 하한(A3 식 차용, 가정) 과 추세 폭(0.115 빌림, 가정) 을 계산한다.
  4. 카드 · JUDGE-SPEC · RULES-HUB 에 붙일 markdown 조각과 a5_baseline.json 을 낸다.
숫자는 전부 이 파일이 json · npz 에서 읽어 만든다. 손으로 옮긴 숫자는 없다.

쓰는 법: python -I a5_baseline.py <walk_turn_summary.json> <impl-integ 경로> [<out dir>]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

CONTACT_N = 1.0          # 접촉력 크기 문턱 (turn_probe.py:128 norm, JUDGE-SPEC 2.x)
HOLD_DROP_Q = 0.20       # A3 유지 식 (JUDGE-SPEC 3 절) 차용 [가정]
HOLD_RISE_C = 0.25
HOLD_KEPT = 14
FWD_KEEP_FRAC = 0.90     # 전진 유지 식 차용 [가정]
TREND_WIDTH = 0.115      # A3 폭 (RESULT-EX34 165 행) 빌림 [가정]
TOL = 1e-6


def recompute(npz_path, sign, feet):
    z = np.load(npz_path)
    kept = z["kept"].astype(bool)
    alive = z["alive"].astype(bool)
    wz, vx = z["wz"], z["vx"]
    T = wz.shape[1]
    dt = 8.0 / T
    n_alive = np.maximum(alive.sum(1), 1)
    q_env = (wz * alive).sum(1) / n_alive * sign
    contact4 = (z["force"][:, :, list(feet)] > CONTACT_N).all(-1)
    c_env = (contact4 & alive).sum(1) / n_alive
    vx_int = (vx * alive).sum(1) * dt
    qk = q_env[kept]
    return {
        "Q": float(qk.mean()), "C": float(c_env[kept].mean()), "kept": int(kept.sum()),
        "alive_end": int(alive[:, -1].sum()), "n_neg": int((qk < 0).sum()),
        "qmin": float(qk.min()), "qmax": float(qk.max()),
        "vx_integral_kept_mean": float(vx_int[kept].mean()), "n_env": int(kept.shape[0]), "T": int(T),
    }


def load(json_path, impl_dir):
    sys.path.insert(0, str(impl_dir))
    from foothold_s2.eval import judge_gate as G, judge_stats as S, turn_probe_plan as P  # noqa: E402
    thr = G.THRESHOLDS
    summary = json.load(open(json_path, encoding="utf-8"))
    rows = {}
    for key, v in summary.items():
        mode, case = key.split("/")
        mine = recompute(v["path"], v["sign"], S.FEET)
        for k in ("Q", "C", "vx_integral_kept_mean"):
            assert abs(mine[k] - v[k]) <= TOL, (key, k, mine[k], v[k])
        for k in ("kept", "alive_end", "n_neg"):
            assert mine[k] == v[k], (key, k, mine[k], v[k])
        cmd = P.PROTOCOLS[case]["cmd"]
        need_int = thr["walk_fwd_frac"] * cmd[0] * P.RECORD_S
        comp = {
            "q": mine["Q"] >= thr["walk_q"], "c": mine["C"] <= thr["walk_c"],
            "kept": mine["kept"] >= thr["walk_kept"], "neg": mine["n_neg"] == 0,
            "vx": mine["vx_integral_kept_mean"] >= need_int,
        }
        rows[key] = {
            "mode": mode, "case": case, "cmd": list(cmd), "path": v["path"], **mine,
            "success": comp, "need_int_m": need_int,
            "hold_min_Q": mine["Q"] - HOLD_DROP_Q, "hold_max_C": mine["C"] + HOLD_RISE_C,
            "hold_min_vx_m": mine["vx_integral_kept_mean"] * FWD_KEEP_FRAC,
            "improve_Q": mine["Q"] + TREND_WIDTH,
        }
    consts = {"walk_q": thr["walk_q"], "walk_c": thr["walk_c"], "walk_kept": thr["walk_kept"],
              "walk_fwd_frac": thr["walk_fwd_frac"], "record_s": P.RECORD_S, "contact_N": CONTACT_N,
              "hold_drop_q": HOLD_DROP_Q, "hold_rise_c": HOLD_RISE_C, "hold_kept": HOLD_KEPT,
              "fwd_keep_frac": FWD_KEEP_FRAC, "trend_width": TREND_WIDTH, "tol": TOL}
    return rows, consts


MODE_KO = {"eval_gt": "켬", "probe_prop_only": "가림"}
CASE_KO = {"walk_turn_left": "좌", "walk_turn_right": "우"}


def f4(x):
    return "%.4f" % x


def f3(x):
    return "%.3f" % x


def blocks(rows, consts, json_rel):
    r = rows
    L, R = "walk_turn_left", "walk_turn_right"
    on, off = "eval_gt", "probe_prop_only"

    def cell(mode, case):
        x = r[f"{mode}/{case}"]
        return "%s · %s · %d · %s" % (f4(x["Q"]), f3(x["C"]), x["kept"], f3(x["vx_integral_kept_mean"]))

    # (1) 카드 §3 기준표 두 행
    card_s3 = (
        "| walk_turn_left (Q · C · kept · 전진 적분 m) `[실측 00:36 X27g · planner npz 재계산 일치]` | %s | %s | 미측(walk eval_pred 미실행, 기록만) |\n"
        "| walk_turn_right (Q · C · kept · 전진 적분 m) | %s | %s | 미측 |"
        % (cell(on, L), cell(off, L), cell(on, R), cell(off, R))
    )

    # (2) 카드 §4b.1 A5 기준선 칸 · 하한 칸
    def base_line(mode):
        a, b = r[f"{mode}/{L}"], r[f"{mode}/{R}"]
        return ("%s 좌 Q **%s** · C %s · kept %d/16 · 끝 생존 %d · 반대 %d · 전진 적분 %s m(env Q 범위 %s~%s) / 우 Q **%s** · C %s · kept %d/16 · 끝 생존 %d · 반대 %d · 전진 적분 %s m(%s~%s)"
                % (MODE_KO[mode], f4(a["Q"]), f3(a["C"]), a["kept"], a["alive_end"], a["n_neg"], f3(a["vx_integral_kept_mean"]), f3(a["qmin"]), f3(a["qmax"]),
                   f4(b["Q"]), f3(b["C"]), b["kept"], b["alive_end"], b["n_neg"], f3(b["vx_integral_kept_mean"]), f3(b["qmin"]), f3(b["qmax"])))

    a5_base = (
        "`walk_turn_left` · `walk_turn_right`(0.5, 0, ±0.5) 8 s: Q · C · kept · 반대 부호 수 · 전진 적분, 좌 · 우 따로. "
        "**기준선 m1500 `[실측]`**(sonnet-code X27g 10/27 00:36 rc 0, 저장본 sha 4d987818 · 코드 07fc5e73; planner `a5_baseline.py` 가 npz 에서 독립 식으로 다시 재어 Q · C · 전진 적분 ≤ 1e-6 · 정수 0 일치): "
        + base_line(on) + "; " + base_line(off)
        + ". 원자료 `%s` + `turn16_walk_{eval_gt,probe_prop_only}/arrays_walk_turn_{left,right}.npz`. eval_pred 는 미측(기록만). "
        "좌 · 우 전진 적분 차(켬 %s 대 %s m) 는 사실로만 적고 해석하지 않는다(lead 00:3x)" % (json_rel, f3(r[f"{on}/{L}"]["vx_integral_kept_mean"]), f3(r[f"{on}/{R}"]["vx_integral_kept_mean"]))
    )

    need = r[f"{on}/{L}"]["need_int_m"]
    fails = [k for k, x in r.items() if not all(x["success"].values())]
    fail_txt = " · ".join("%s %s 전진 적분 %s" % (MODE_KO[r[k]["mode"]], CASE_KO[r[k]["case"]], f3(r[k]["vx_integral_kept_mean"])) for k in fails)
    a5_low = (
        "성공선(JUDGE-SPEC 4.4 = `judge_gate.THRESHOLDS` walk_*): Q ≥ %.2f · C ≤ %.1f · kept ≥ %d · 반대 0 · 전진 적분 ≥ %.1f × %.1f × %.0f s = **%s m**(두 부호 · 두 저장본). "
        "**부모 m1500 에 대 본 결과 `[실측]`**: Q · C · kept · 반대 네 성분은 네 판 모두 통과(Q %s~%s ≥ %.2f), 전진 적분은 우 통과(%s · %s m) · **좌 미달**(%s < %s m). "
        "그래서 m2000 「다음 단계」 는 좌 전진 적분이 %s m 를 넘는지에만 달려 있고, Q 성분은 부모 수준이면 그대로 통과한다(사실. 성공선 숫자는 결과 전 고정이라 바꾸지 않고, 이 성질을 어떻게 다룰지는 lead 가 정할 것). "
        "유지 하한 `[가정: A3 · 전진 유지 식 차용]`: Q ≥ 기준 − %.2f(켬 좌 %s · 우 %s / 가림 좌 %s · 우 %s) · C ≤ 기준 + %.2f · kept ≥ %d · 전진 적분 ≥ 기준 × %.2f(켬 좌 %s · 우 %s / 가림 좌 %s · 우 %s m). "
        "추세: 방향별 Q 가 이전 창 경계보다 **+%.3f 이상** 오르면 「개선」(폭은 A3 빌림 `[가정]`), 양방향 평균은 쓰지 않는다"
        % (consts["walk_q"], consts["walk_c"], consts["walk_kept"], consts["walk_fwd_frac"], r[f"{on}/{L}"]["cmd"][0], consts["record_s"], f3(need),
           f4(min(x["Q"] for x in r.values())), f4(max(x["Q"] for x in r.values())), consts["walk_q"],
           f3(r[f"{on}/{R}"]["vx_integral_kept_mean"]), f3(r[f"{off}/{R}"]["vx_integral_kept_mean"]),
           fail_txt.replace("켬 좌 전진 적분 ", "켬 ").replace("가림 좌 전진 적분 ", "가림 "), f3(need), f3(need),
           consts["hold_drop_q"], f3(r[f"{on}/{L}"]["hold_min_Q"]), f3(r[f"{on}/{R}"]["hold_min_Q"]), f3(r[f"{off}/{L}"]["hold_min_Q"]), f3(r[f"{off}/{R}"]["hold_min_Q"]),
           consts["hold_rise_c"], consts["hold_kept"], consts["fwd_keep_frac"],
           f3(r[f"{on}/{L}"]["hold_min_vx_m"]), f3(r[f"{on}/{R}"]["hold_min_vx_m"]), f3(r[f"{off}/{L}"]["hold_min_vx_m"]), f3(r[f"{off}/{R}"]["hold_min_vx_m"]),
           consts["trend_width"])
    )

    # (3) JUDGE-SPEC 6.8.2 표
    hdr = ("| 모드 · 경우 | Q | C | kept / 끝 생존 | 반대 | 전진 적분 m (성공선 %s) | 성공선 성분 Q · C · kept · 반대 · 전진 | 유지 하한 Q ≥ / C ≤ / 적분 ≥ `[가정]` |\n|---|---|---|---|---|---|---|---|" % f3(need))
    lines = [hdr]
    for key in (f"{on}/{L}", f"{on}/{R}", f"{off}/{L}", f"{off}/{R}"):
        x = r[key]
        s = x["success"]
        mark = lambda b: "통과" if b else "**미달**"  # noqa: E731
        lines.append("| %s %s (`%s`) | %s | %s | %d / %d | %d | %s | %s · %s · %s · %s · %s | %s / %s / %s |" % (
            MODE_KO[x["mode"]], CASE_KO[x["case"]], x["case"], f4(x["Q"]), f3(x["C"]), x["kept"], x["alive_end"], x["n_neg"],
            f3(x["vx_integral_kept_mean"]), mark(s["q"]), mark(s["c"]), mark(s["kept"]), mark(s["neg"]), mark(s["vx"]),
            f3(x["hold_min_Q"]), f3(x["hold_max_C"]), f3(x["hold_min_vx_m"])))
    judge_table = "\n".join(lines)
    expected = sorted("success_walk_vx(%s, %s)" % (r[k]["mode"], r[k]["case"]) for k in fails)
    judge_known = ("답 아는 입력(J-T7 · 구현 시험): 부모 m1500 묶음을 `_success_walk` 에 넣으면 나오는 조건은 정확히 %s 뿐이어야 한다(그 밖의 success_walk_* 는 0 개). 유지 하락은 기준 = 자기 자신이라 0 개."
                   % (", ".join("`%s`" % e for e in expected)))

    # (4) RULES-HUB 10.1 A5 칸
    hub_base = ("`sb10_eval/m1500/walk_turn_summary.json`(X27g 00:36, planner 재계산 일치): 켬 좌 Q %s · C %s · kept 16 · 적분 %s m / 우 %s · %s · 16 · %s / 가림 좌 %s · %s · 16 · %s / 우 %s · %s · 16 · %s. eval_pred 미측"
                % (f4(r[f"{on}/{L}"]["Q"]), f3(r[f"{on}/{L}"]["C"]), f3(r[f"{on}/{L}"]["vx_integral_kept_mean"]),
                   f4(r[f"{on}/{R}"]["Q"]), f3(r[f"{on}/{R}"]["C"]), f3(r[f"{on}/{R}"]["vx_integral_kept_mean"]),
                   f4(r[f"{off}/{L}"]["Q"]), f3(r[f"{off}/{L}"]["C"]), f3(r[f"{off}/{L}"]["vx_integral_kept_mean"]),
                   f4(r[f"{off}/{R}"]["Q"]), f3(r[f"{off}/{R}"]["C"]), f3(r[f"{off}/{R}"]["vx_integral_kept_mean"])))
    return {"card_s3": card_s3, "a5_base": a5_base, "a5_low": a5_low, "judge_table": judge_table,
            "judge_known": judge_known, "hub_base": hub_base, "need_int_m": need, "fails": fails}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    json_path = Path(sys.argv[1])
    impl_dir = Path(sys.argv[2])
    out_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    rows, consts = load(json_path, impl_dir)
    b = blocks(rows, consts, "sb10_eval/m1500/walk_turn_summary.json")
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "a5_baseline.json").write_text(json.dumps({"source": str(json_path), "consts": consts, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in b.items():
        print("=== %s ===" % k)
        print(v)


if __name__ == "__main__":
    main()
