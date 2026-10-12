"""5판 CMD-R 절의 %%토큰%% 을 원자료에서 만든다 (lead · 10/13 밤).
원자료: _eval/out/cmdr_post.json (cmdr_post.py v3) · _eval/out/branch/cmdr_summary.json (관문 사건표 집계) ·
_eval/out/branch/cmdr_bundle_compare__cmdr_s1042_off_u4000__cmdr_s1042_on_u4000.json (두 갈래 시작 상태 대조)."""
import json
import os

EV = "C:/isaac/ext/go2_rl_robotlab/_eval/out"
MODELS = ["p20000", "off22000", "on22000", "off24000", "on24000"]
CELL_KO = {"stop03": "걷다 멈춤 (0.3 m/s → 0)", "fwd01": "앞 0.1 m/s", "fwd02": "앞 0.2 m/s"}


def _pct(v):
    return "" if v is None else f"{100 * v:.0f}"


def _d(p):
    if not p:
        return "아직 없음"
    return f"{100 * p['diff']:+.0f} [{100 * p['lo']:+.0f}, {100 * p['hi']:+.0f}]"


def build(post_path=None, summary_path=None, bundle_path=None):
    post = json.load(open(post_path or os.path.join(EV, "cmdr_post.json"), encoding="utf-8"))
    summ = json.load(open(summary_path or os.path.join(EV, "branch", "cmdr_summary.json"), encoding="utf-8"))
    bpath = bundle_path or os.path.join(EV, "branch", "cmdr_bundle_compare__cmdr_s1042_off_u4000__cmdr_s1042_on_u4000.json")
    t = {}
    t["cmdr_corner_off"] = f"{100 * summ['off']['reset_timeout']['both_planar_at_+bound']:.1f}"
    t["cmdr_corner_on"] = f"{100 * summ['on']['reset_timeout']['both_planar_at_+bound']:.1f}"
    if os.path.exists(bpath):
        b = json.load(open(bpath, encoding="utf-8"))
        t["cmdr_bundle_verdict"] = "같음 · 의도한 두 칸 (갈래 이름 · 시작 시각) 말고 다른 값 0" if b["verdict"] == "SAME" else \
            f"<b>다름</b> · {len(b['problems'])} 곳 (on 갈래 평가는 보류)"
    else:
        t["cmdr_bundle_verdict"] = "on 갈래 시작 전이라 아직 대조 안 함"
    rows, drows, seeds = [], [], set()
    for c in ["stop03", "fwd01", "fwd02"]:
        r = post["targets"].get(c, {})
        cells = []
        for m in MODELS:
            if m in r:
                cells.append(f"<td class=\"num\">{_pct(r[m]['rate'])} <span class=\"sub\">({r[m]['n']})</span></td>")
                seeds |= set(r[m]["seeds"])
            else:
                cells.append("<td class=\"num sub\">아직</td>")
        rows.append(f"<tr><td>{CELL_KO[c]}</td>{''.join(cells)}</tr>")
        drows.append(f"<tr><td>{CELL_KO[c]}</td><td class=\"num\">{_d(r.get('on_minus_off_22000'))}</td>"
                     f"<td class=\"num\">{_d(r.get('on_minus_off_24000'))}</td></tr>")
    t["cmdr_target_rows"] = "".join(rows)
    t["cmdr_diff_rows"] = "".join(drows)
    t["cmdr_seeds"] = " · ".join(str(s) for s in sorted(seeds)) if seeds else "(아직 없음)"
    srows = []
    for c, d in post["startup"].items():
        for m in MODELS:
            if m not in d:
                continue
            s = d[m]
            li = "" if s["lin_err_int_m_completed"] is None else f"{s['lin_err_int_m_completed']:.3f}"
            srows.append(f"<tr><td>{CELL_KO[c]} · {m}</td><td class=\"num\">{s['completed_1s']}/{s['n']}</td>"
                         f"<td class=\"num\">{s['early_fail_1s']}</td><td class=\"num\">{li}</td><td class=\"num\">{s['survive_5s']}/{s['n']}</td></tr>")
    t["cmdr_startup_rows"] = "".join(srows) or "<tr><td colspan=\"5\" class=\"sub\">아직 없음</td></tr>"
    st = []
    st.append(f"<li>유효한 평가 실행 <b>{post['n_valid_runs']}</b> 개 · 시작 상태가 짝이 안 맞아 뺀 것 {len(post['driver_pair_fail'])} · 검사에서 떨어진 것 {len(post['driver_invalid'])}.</li>")
    for u in ("22000", "24000"):
        pl = post["proposal_lines"].get(u)
        if pl:
            st.append(f"<li>{u}: 목표 세 칸의 on − off 평균 <b>{pl['target_mean_diff_pp']:+.1f} %p</b> (제안선 +10 %p {'넘음' if pl['meets_plus10'] else '못 넘음'} · 채택 판정 아님).</li>")
        else:
            st.append(f"<li>{u}: 두 갈래가 다 재지지 않아 아직 비교 없음.</li>")
    t["cmdr_status"] = "".join(st)
    return t
