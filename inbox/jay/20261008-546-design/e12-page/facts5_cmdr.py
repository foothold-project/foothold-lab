"""5판 CMD-R 절의 %%토큰%% 을 원자료에서 만든다 (lead · 10/13).
원자료: _eval/out/cmdr_post.json (cmdr_post_v6.py · schema "cmdr_post v6") · _eval/out/branch/cmdr_summary.json (관문 사건표 집계) ·
_eval/out/branch/cmdr_bundle_compare__cmdr_s1042_off_u4000__cmdr_s1042_on_u4000.json (두 갈래 시작 상태 대조).
판정선 (팀장 확정 2(c) · VERIFY-astra-7 60 줄 · ASTRA 15 6.1): 세 칸 모두 95 % 구간 하한 > 0 이고 세 칸 같은 무게 평균 +10 %p 이상이면 「개선」.
칸마다의 구간은 서술이고 판정이 아니다. (v16 의 「칸마다 판정 · 세 칸 평균으로 쓰지 않는다 (ASTRA 15 6.1)」 는 규칙을 잘못 옮긴 것이라 철회 · 10/13 10:02)
v7 (ASTRA 16e 4): 「다 재진」 은 필요한 판 수를 다 채운 칸만 · 비교 없음의 원인을 짐작하지 않음 · 속도 오차는 상대 (+10 %) / 절대 (허용 오차의 10 %) 를
구분 · 시드별 값에 시드 번호 · 구형 인증 실행 수를 보임 · 학습 상태는 result.json 에서 읽음.
v6 (ASTRA 16c): 다른 판 집계는 읽지 않는다 · 판 수 · 시드는 집계에서 읽는다 (적어 넣지 않음) · 다시 잰 칸은 n 과 시드를 붙인다 ·
「퇴행 방지 조건 충족 (통과율 · MAE)」 은 그 둘만 뜻한다 · 기본 계약은 모든 측정 칸을 펼쳐 보인다."""
import json
import os
import time

EV = "C:/isaac/ext/go2_rl_robotlab/_eval/out"
SCHEMA = "cmdr_post v7"
MODELS = ["p20000", "off22000", "on22000", "off24000", "on24000"]
TARGETS = ["stop03", "fwd01", "fwd02"]
CELL_KO = {"stop03": "걷다 멈춤 (0.3 m/s → 0)", "fwd01": "앞 0.1 m/s", "fwd02": "앞 0.2 m/s", "stand": "서 있기", "fwd03": "앞 0.3 m/s",
           "fwd05": "앞 0.5 m/s", "back03": "뒤 0.3 m/s", "left03": "왼쪽 0.3 m/s", "right03": "오른쪽 0.3 m/s", "yawL05": "왼쪽 회전 0.5 rad/s",
           "yawR05": "오른쪽 회전 0.5 rad/s"}
FAM_KO = {"flat": "평지", "obstacles": "장애물", "rough_slope": "거친 경사", "slope_up": "오르막", "slope_down": "내리막",
          "stairs_up": "계단 오름", "stairs_down": "계단 내림", "wave": "물결"}
OK_LABEL, BAD_LABEL = "퇴행 방지 조건 충족 (통과율 · MAE)", "퇴행 방지 조건 미충족"


def _pct(v):
    return "" if v is None else f"{100 * v:.0f}"


def _d(p):
    if not p:
        return "아직 없음"
    return f"{100 * p['diff']:+.1f} [{100 * p['lo']:+.1f}, {100 * p['hi']:+.1f}] <span class=\"sub\">({p['n']} 쌍)</span>"


def _seeds(r):
    return sorted(int(x) for x in r.get("per_seed", {}))


AXIS_KO = {"vx": "앞 속도", "vy": "옆 속도", "wz": "회전 속도"}


def _mae_txt(k, v):
    """the MAE line in words: relative (+10 % of the control) or absolute (10 % of the axis tolerance when the control is 0)."""
    if v.get("line") == "abs":
        return f"{AXIS_KO.get(k, k)} 오차가 절대 한도 {v['limit']:.3f} 를 넘음 (대조 오차 0)"
    return f"{AXIS_KO.get(k, k)} 오차 10 % 넘게 커짐"


def _mae_row(ms):
    """regression-row MAE wording: each over axis with its line kind, each missing axis with its shortfall (arm, seed, finite n)."""
    parts = [_mae_txt(k, v) for k, v in ms.get("lines", {}).items()]
    for k in ms.get("missing", []):
        short = ms.get("short", {}).get(k, [])
        where = ", ".join(f"{x['arm']} 시드 {x['seed']} 유한 {x['finite']}/100" for x in short)
        parts.append(f"{AXIS_KO.get(k, k)} 오차 결측 ({where or '판정 보류'})")
    return " · ".join(parts) or "계약선 안"


def _cellname(k):
    fam, cell, noise = k.split("/")
    return f"{FAM_KO[fam]} · {CELL_KO.get(cell, cell)}{'' if noise == 'on' else ' · noise 끔'}"


def build(post_path=None, summary_path=None, bundle_path=None):
    pp = post_path or os.path.join(EV, "cmdr_post.json")
    post = json.load(open(pp, encoding="utf-8"))
    summ = json.load(open(summary_path or os.path.join(EV, "branch", "cmdr_summary.json"), encoding="utf-8"))
    bpath = bundle_path or os.path.join(EV, "branch", "cmdr_bundle_compare__cmdr_s1042_off_u4000__cmdr_s1042_on_u4000.json")
    t = {}
    t["cmdr_corner_off"] = f"{100 * summ['off']['reset_timeout']['both_planar_at_+bound']:.1f}"
    t["cmdr_corner_on"] = f"{100 * summ['on']['reset_timeout']['both_planar_at_+bound']:.1f}"
    if os.path.exists(bpath):
        b = json.load(open(bpath, encoding="utf-8"))
        ko_diff = {"meta.args.cmdr": "CMD-R 켜고 끔", "meta.args.tag": "갈래 이름", "meta.t_start": "시작 시각"}
        dp = [ko_diff.get(x, x) for x in b.get("diff_paths", [])]
        arr = b.get("arrays", {})
        same_arr = sum(1 for v in arr.values() if v == "same")
        t["cmdr_bundle_verdict"] = (f"같음 · 다른 칸은 의도한 {len(dp)} 개 ({' · '.join(dp)}) 뿐이고, 명령 · 관절 · 지형 레벨 · 위치 · "
                                    f"난수 상태 등 배열 {same_arr} / {len(arr)} 개가 같음") if b["verdict"] == "SAME" else \
            f"<b>다름</b> · {len(b['problems'])} 곳 (on 갈래 평가는 보류)"
    else:
        t["cmdr_bundle_verdict"] = "on 갈래 시작 전이라 아직 대조 안 함"
    asof = post.get("as_of", "")[11:16] or time.strftime("%H:%M", time.localtime(os.path.getmtime(pp)))
    tr = []
    for arm, lab in (("off", "안 고친 갈래"), ("on", "고친 갈래")):
        try:
            r = json.load(open(os.path.join(EV, "branch", f"cmdr_s1042_{arm}_u4000", "result.json"), encoding="utf-8"))
            ok = r["final_state"]["where"] == "end" and r["final_state"]["label_next"] == 24000
            tr.append(f"{lab} {r['meta']['t_end'][11:16]} 끝 (24,000)" if ok else f"{lab} 결과 파일이 끝 상태가 아님")
        except FileNotFoundError:
            tr.append(f"{lab} 아직 학습 중 ({time.strftime('%H:%M')} 확인)")
    t["cmdr_train_status"] = " · ".join(tr)
    if post.get("schema") != SCHEMA:  # 16c 5: an older aggregate is not read as if it were this one
        msg = f"집계 판 불일치 (읽은 판: {post.get('schema', '이전 판')}) · 새 판 ({SCHEMA}) 집계를 기다림"
        for k in ("cmdr_target_rows", "cmdr_diff_rows", "cmdr_startup_rows", "cmdr_reg_rows"):
            t[k] = f"<tr><td colspan=\"7\" class=\"sub\">{msg}</td></tr>"
        t.update(cmdr_seeds="(집계 대기)", cmdr_status=f"<li>{msg}.</li>", cmdr_reg_summary=msg, cmdr_contract=msg, cmdr_contract_detail="",
                 cmdr_offarm="")
        return t
    rows, drows, seeds = [], [], set()
    for c in TARGETS:
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
    st = [f"<li>{asof} 집계 ({SCHEMA}) · 유효한 평가 실행 <b>{post['n_valid_runs']}</b> 개 · 시작 상태가 짝이 안 맞아 뺀 것 {len(post['driver_pair_fail'])} · "
          f"검사에서 떨어진 것 {len(post['driver_invalid'])} · 인증이 안 맞아 뺀 것 {len(post.get('auth_fail', []))} · "
          f"그중 구형 (v3.2) 인증 {post.get('legacy_stamps', 0)} 개 (출력 해시 없이 pins · checkpoint 로 묶임 · 이번 집계 때 읽은 바이트의 해시는 기록).</li>"]
    for u in ("22000", "24000"):
        tv = post["target_verdict"][u]
        cells = [(c, post["targets"].get(c, {}).get(f"on_minus_off_{u}")) for c in TARGETS]
        when = "중간 관찰" if u == "22000" else "최종 비교"
        parts = []
        for c, p in cells:
            if not p:
                parts.append(f"{CELL_KO[c]} 아직 비교 없음 (0 쌍)")
                continue
            d, lo, hi = 100 * p["diff"], 100 * p["lo"], 100 * p["hi"]
            mae = "".join(f" · {_mae_txt(k, v)}" for k, v in p.get("mae", {}).items() if v.get("worse_than_line"))
            ps = " · ".join(f"{k} {100 * v:+.0f}" for k, v in sorted(p.get("per_seed", {}).items(), key=lambda kv: int(kv[0])))
            parts.append(f"{CELL_KO[c]} <b>{d:+.1f} %p</b> [{lo:+.1f}, {hi:+.1f}] ({p['n']} 쌍 · {tv['cells'][c]}{mae} · 시드별 {ps})")
        head = f"<li>{u} ({when} · on − off · 같은 판끼리 짝): "
        if not tv.get("complete"):
            miss = ", ".join(f"{CELL_KO[c]} {v}" for c, v in tv["seeds_missing"].items() if v) or "없음"
            tail = f". 세 칸이 다섯 시드 500 쌍을 다 채우기 전이라 <b>결합 판정 보류</b> (빠진 시드: {miss}).</li>"
        else:
            low = "예" if tv["all_low_above_0"] else "아니오"
            ge = "이상 충족" if tv["mean_ge_10"] else "못 미침"
            if u == "22000":
                tail = (f". 판정선에 대 보면 세 칸 모두 구간 하한 0 위: {low} · 세 칸 평균 <b>{tv['mean_pp']:+.1f} %p</b> (+10 %p {ge}). "
                        f"중간 관찰이라 판정으로 쓰지 않습니다.</li>")
            else:
                tail = (f". 세 칸 모두 구간 하한 0 위: {low} · 세 칸 평균 <b>{tv['mean_pp']:+.1f} %p</b> (+10 %p {ge}) → 이번 1042 의 24,000 비교에서 사전 개선선 "
                        f"<b>{'충족' if tv['verdict'] == '개선' else '미충족'}</b>. 미충족은 「효과 없음」 의 증명이 아닙니다. 채택 여부는 퇴행 방지 조건과 기본 계약의 "
                        f"확인 상태를 모두 본 뒤 팀장이 정합니다.</li>")
        st.append(head + " · ".join(parts) + tail)
    t["cmdr_status"] = "".join(st)
    # 24,000 다른 칸 퇴행 (통과율 · 속도 오차 · 둘을 합친 퇴행 방지 조건을 따로 · 선별 비해당도 미확인이면 보인다)
    reg = post.get("regression_24000", {})
    covr = post.get("regression_coverage", {"planned": 99, "measured": len(reg)})
    if reg:
        by = {}
        for r in reg.values():
            by[r["overall"]] = by.get(r["overall"], 0) + 1
        t["cmdr_reg_summary"] = (f"계획 {covr['planned']} 칸 가운데 on · off 24,000 비교가 있는 칸 {covr['measured']} (그중 필요한 판 수를 다 채운 칸 {covr.get('done', 0)}) · "
                                 + " · ".join(f"{k} {by[k]}" for k in (BAD_LABEL, "미확인", OK_LABEL) if by.get(k)))
        order = {BAD_LABEL: 0, "미확인": 1, OK_LABEL: 2}
        rows, hidden = [], 0
        for k, r in sorted(reg.items(), key=lambda kv: (order.get(kv[1]["overall"], 1), kv[0])):
            if r["overall"] == OK_LABEL:
                hidden += 1
                continue
            sc = "" if "screen_diff" not in r else f"{100 * r['screen_diff']:+.0f} [{100 * r['screen_lo']:+.1f}, {100 * r['screen_hi']:+.1f}]"
            if "lo" in r:
                sd = _seeds(r)
                tag = "" if sd == [1000, 1001, 1002, 1003, 1004] else " · <b>수집 중</b>"
                n5 = f"{100 * r['diff']:+.1f} [{100 * r['lo']:+.1f}, {100 * r['hi']:+.1f}] <span class=\"sub\">({r['n']} 판 · 시드 {', '.join(map(str, sd))}{tag})</span>"
            elif r.get("seeds_have"):
                n5 = f"<span class=\"sub\">수집 중 · 시드 {', '.join(map(str, r['seeds_have']))}</span>"
            else:
                n5 = ""
            nw = r.get("new400") or {}
            n4 = "" if not nw else f"{100 * nw['diff']:+.1f} [{100 * nw['lo']:+.1f}, {100 * nw['hi']:+.1f}] <span class=\"sub\">({nw['n']} 판)</span>"
            rows.append(f"<tr><td>{_cellname(k)}</td><td class=\"num\">{sc}</td><td class=\"num\">{n5}</td><td class=\"num\">{n4}</td>"
                        f"<td>{r['pass_status']}</td><td>{_mae_row(r['mae'])}</td><td>{r['overall']}</td></tr>")
        if hidden:
            rows.append(f"<tr><td colspan=\"7\" class=\"sub\">「{OK_LABEL}」 인 {hidden} 칸은 줄였습니다 (통과율 구간 아래 끝이 −5 %p 이상이고 속도 오차가 계약선 안). "
                        f"기본 계약과 학습 시드 반복은 이 조건에 들어 있지 않습니다.</td></tr>")
        t["cmdr_reg_rows"] = "".join(rows)
    else:
        t["cmdr_reg_summary"] = (f"현재 유효한 on · off 24,000 비교 없음 (인증이 안 맞아 뺀 실행 {len(post.get('auth_fail', []))} · "
                                 f"계획 {covr['planned']} 칸)")
        t["cmdr_reg_rows"] = "<tr><td colspan=\"7\" class=\"sub\">아직 없음</td></tr>"
    con = post.get("contract_24000", {})
    cl, det = [], []
    for m, lab in (("off24000", "안 고친 갈래"), ("on24000", "고친 갈래")):
        c = con.get(m)
        if c and c["n_cells"]:
            cl.append(f"{lab}: 계획 {c['planned']} 칸 중 {c['n_cells']} 칸 잼 · 생존 95 % 아래 {len(c['surv_below'])} 칸 · 명령 통과 90 % 아래 {len(c['pass_below'])} 칸")
            trs = "".join(f"<tr><td>{_cellname(k)}</td><td class=\"num\">{v['surv_k']}/{v['n']} [{100 * v['surv_ci'][0]:.0f}, {100 * v['surv_ci'][1]:.0f}]</td>"
                          f"<td class=\"num\">{v['pass_k']}/{v['n']} [{100 * v['pass_ci'][0]:.0f}, {100 * v['pass_ci'][1]:.0f}]</td>"
                          f"<td>{'' if v['surv_ok'] else '생존 선 아래 '}{'' if v['pass_ok'] else '통과 선 아래'}</td></tr>" for k, v in c["cells"].items())
            det.append(f"<details><summary>{lab} 24,000 · 잰 {c['n_cells']} 칸 모두 (생존 · 명령 통과 k/n [Wilson 95 %])</summary>"
                       f"<div class=\"tbl\"><table class=\"def\"><thead><tr><th>칸</th><th>생존</th><th>명령 통과</th><th>선 아래</th></tr></thead>"
                       f"<tbody>{trs}</tbody></table></div><p class=\"sub\">아직 안 잰 칸 {len(c['unmeasured'])} 개.</p></details>")
    t["cmdr_contract"] = (" · ".join(cl) + " (시드 1000 · 칸마다 100 판 · 점추정, 칸마다 구간은 아래 펼침 표)") if cl else "아직 없음"
    t["cmdr_contract_detail"] = "".join(det)
    # 안 고친 갈래 (E1 20,000 에서 넓힌 범위 그대로 이어 학습) 의 목표 칸 · 관찰만 (원인 주장 없음) · 판 수는 집계에서
    tg = post["targets"]

    def r_(c, m):
        v = tg.get(c, {}).get(m)
        return f"{100 * v['rate']:.0f} % ({v['n']} 판)" if v else "아직"
    if "off22000" in tg.get("stop03", {}):
        t["cmdr_offarm"] = (f" 지금까지 잰 값: 평지 · noise 켬 걷다 멈춤은 부모 {r_('stop03', 'p20000')} → 22,000 {r_('stop03', 'off22000')} → 24,000 {r_('stop03', 'off24000')}, "
                            f"앞 0.1 m/s 는 {r_('fwd01', 'p20000')} → {r_('fwd01', 'off22000')} → {r_('fwd01', 'off24000')} 입니다 ({asof} 집계). "
                            f"이 한 갈래에서는 이어 학습만으로 멈춤이 돌아오지 않았습니다. 학습 시드 하나의 관찰이고 원인은 말하지 않습니다.")
    else:
        t["cmdr_offarm"] = ""
    return t
