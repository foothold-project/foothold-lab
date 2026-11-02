"""CURRICULUM-GATES 의 「EX-42 지형 커리큘럼 정본 (D163)」 절을 대조한다.
단계 ID 열 개(E0 · E1 · E1F · E2 · E3 · E4 · E5 · M · E6a · E6b) · 단계마다 열두 행 · YAML 칸 표 · 예시 YAML(합 1.0 · 망각 방지 하한).
v0.10 부터: 축 계약(axis_id · allowed_diff_paths · donor) · §E.3.1 유지 항 표 · §E.6 반영 표 · 옛 문구(B1~B5 이전) 없음.
형식 검사 통과는 실행 정합성이 아니다.

사용: python -X utf8 ex42_canon_check.py [CURRICULUM-GATES.md]
종료 0 = 전부 · 1 = 어긋남(어느 칸).
"""
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
doc = Path(sys.argv[1]) if len(sys.argv) > 1 else here.parent / "20261026-experiments" / "CURRICULUM-GATES.md"
text = doc.read_bytes().decode("utf-8").replace("\r\n", "\n")
bad = 0
def ok(cond, label):
    global bad
    print(("ok  " if cond else "MISS") + " " + label)
    bad += 0 if cond else 1

STAGES = ["E0", "E1", "E1F", "E2", "E3", "E4", "E5", "M", "E6a", "E6b"]
ROWS = ["지형 종류", "레벨", "치수", "env 몫", "바꾸는 축 하나", "유지 칸", "망각 방지 몫", "승급 문턱", "최대 회차", "연장", "평가 칸", "영상"]
def cells(line):
    """표 한 줄의 칸 목록. 역슬래시로 이스케이프한 세로줄은 칸 안 글자다(E.3.1 의 절댓값 기호)."""
    return re.split(r"(?<!\\)\|", line.strip())[1:-1]

AXES = ("terrain_mesh_swap", "terrain_level_cap", "command_allocation", "terrain_exposure", "terrain_kind_level_cap", "map_off_probability", "posture_height", "posture_roll")

m0 = re.search(r"^## EX-42 지형 커리큘럼 정본 \(D163.*?$", text, re.M)
m1 = re.search(r"^## v0\.6c 이전 원문 보존", text, re.M)
if not (m0 and m1 and m1.start() > m0.start()):
    print("MISS 정본 절 머리 · 끝 없음"); sys.exit(1)
sec = text[m0.start(): m1.start()]
v010 = "### E.6 " in sec
ok("D163" in sec and "D158" in sec and "D159" in sec and "D160" in sec, "머리에 D163 · D158 · D159 · D160")

# E.1
e1 = re.search(r"^### E\.1 .*?(?=^### E\.2 )", sec, re.M | re.S)
ids = re.findall(r"^\| \*\*(E\d[a-zA-Z]*|M)\*\* \|", e1.group(0), re.M) if e1 else []
ok(ids == STAGES, f"E.1 단계 ID 열 개 순서 {ids}")

# E.2 단계표
e2 = re.search(r"^### E\.2 .*?(?=^### E\.3 )", sec, re.M | re.S)
blocks = dict(re.findall(r"^#### (E\d[a-zA-Z]*|M) [^\n]*\n(.*?)(?=^#### |\Z)", e2.group(0), re.M | re.S)) if e2 else {}
ok(sorted(blocks) == sorted(STAGES), f"E.2 단계표 열 개 {sorted(blocks)}")
for sid in STAGES:
    b = blocks.get(sid, "")
    rows = [(c[1].strip(), c[2].strip()) for c in (l.split("|") for l in b.splitlines() if l.startswith("| ")) if len(c) >= 4]
    rows = [r for r in rows if r[0] not in ("행", "---")]
    labels = [re.sub(r"\(.*?\)", "", r[0]).strip() for r in rows]
    ok(labels == ROWS, f"{sid} 열두 행 순서 {labels if labels != ROWS else ''}")
    ok(all(len(v) >= 2 for _, v in rows), f"{sid} 값 칸 비지 않음")
    ok(re.search(r"\| 최대 회차 \| [\d,]+", b) is not None, f"{sid} 최대 회차 숫자")

# E.3 · E.4
e3 = re.search(r"^### E\.3 .*?(?=^### E\.4 )", sec, re.M | re.S).group(0)
for kw in ("정지 10 · 후진 14 · 옆 7 + 7", "52", "60", "3/64", "0.03", "stop_training", "복원 13"):
    ok(kw in e3 or kw in sec, f"E.3 「{kw}」")
e4 = re.search(r"^### E\.4 .*?(?=^### E\.5 )", sec, re.M | re.S).group(0)
ok("| 칸 이름(YAML 경로) | 자료형 | 단위 | 기본값 |" in e4, "E.4 표 머리(칸 이름 · 자료형 · 단위 · 기본값)")
keys = ["`format`", "`env.num_envs`", "`stages[].boundary.kind`", "`stages[].terrain.exposure.<family>.<kind>.share`",
        "`stages[].terrain.floors.continuous_share_min`", "`promotion.window_episodes`", "`maintenance.judge_cells`", "`maintenance.on_fail.hold_exposure`",
        "`forgetting_watch.compare_to`", "`eval.every_updates`", "`video.per_kind_success`", "`boundary_file`"]
keys += (["`stages[].boundary.axis_id`", "`stages[].boundary.allowed_diff_paths`", "`stages[].boundary.donor`", "`stages[].rewards.height.weight`",
          "`stages[].terrain.preset.<family>`", "`stages[].terrain.kind_task.<kind>.command_set`", "`promotion.completion`", "`promotion.denominator`",
          "`maintenance.anchor`", "`maintenance.items[]`", "`maintenance.calibration.receipt`", "`maintenance.recovery.windows`",
          "`maintenance.learned_cells.min_episodes`", "`eval.sparse_off_role`", "`logging.map_mode`"] if v010 else ["`stages[].boundary.changed_axis`"])
for key in keys:
    ok(key in e4, f"E.4 칸 {key}")
ym = re.search(r"```yaml\n(.*?)```", e4, re.S)
ok(ym is not None, "E.4 예시 YAML 블록")
if ym:
    try:
        import yaml
        y = yaml.safe_load(ym.group(1))
        st = y["stages"][0]
        sh = st["shares"]; tot = sum(sh.values())
        ok(abs(tot - 1.0) < 1e-9, f"예시 shares 합 1.0 ({tot:.3f})")
        ok(sh["stand"] >= 0.10 and sh["reverse"] >= 0.14 and sh["side_left"] >= 0.07 and sh["side_right"] >= 0.07, "예시 망각 방지 하한(정지 · 후진 · 옆)")
        ex = sum(k["share"] for fam in st["terrain"]["exposure"].values() for k in fam.values())
        ok(abs((1 - ex) - 0.95) < 1e-9, f"예시 연속 몫 1 − Σexposure = 0.95 ({1-ex:.2f})")
        bd = st["boundary"]
        ok(bd["kind"] in ("S", "L+", "C", "K", "D", "M"), "예시 boundary.kind")
        if v010:
            ok(bd["axis_id"] in AXES, f"예시 axis_id 등록된 이름 {bd.get('axis_id')}")
            adp = bd["allowed_diff_paths"]
            ok(isinstance(adp, list) and len(adp) >= 1 and all(isinstance(p, str) and p.startswith("terrain.exposure") for p in adp), "예시 allowed_diff_paths 목록(exposure 경로)")
            ok(abs(sum(bd["donor"].values()) + ex) < 1e-9, f"예시 donor 합 = −Δshare ({sum(bd['donor'].values()):+.2f})")
            mt = y["maintenance"]
            ok(mt["anchor"] == "pre_drop_anchor" and mt["recovery"]["windows"] == 2 and mt["learned_cells"]["min_episodes"] == 32 and bool(mt["calibration"]["receipt"]), "예시 anchor · 회복 2 창 · learned_cells 32 · calibration 영수증")
            ok(set(st["terrain"]["preset"]) == {"A", "B", "C", "continuous"} and st["terrain"]["preset"]["A"] == "start_go2_v1", "예시 terrain.preset 네 묶음 · A = start_go2_v1")
            ok(list(st["terrain"]["kind_task"].values())[0]["command_set"] == ["forward_1.0", "flag"], "예시 kind_task command_set [forward_1.0, flag]")
            ok(y["eval"]["sparse_off_role"] == "record" and y["logging"]["map_mode"] == "assigned+consumed+eval", "예시 sparse OFF 기록 · 지도 모드 기록 셋")
            if "| v0.10 재확인(" in sec:   # v0.11
                ok({"error_rise_max_vxvy", "error_rise_max_wz", "distance_drop_frac_of_parent"} <= set(mt) and "error_rise_max" not in mt and "distance_ratio_min" not in mt, "예시 maintenance 키가 E.4 새 이름(옛 키 없음)")
                ok(y["forgetting_watch"]["comparator"] == "from_maintenance_items" and "tolerance" not in y["forgetting_watch"], "예시 forgetting_watch 는 항별 comparator 참조(별도 숫자 없음)")
                kt = list(st["terrain"]["kind_task"].values())[0]
                ok(abs(sum(kt["command_weights"].values()) - 1.0) < 1e-9 and set(kt["command_weights"]) == set(kt["command_set"]), "예시 command_weights 합 1 · command_set 과 같은 키")
                ok(mt["learned_cells"]["modes_required"][0] == "map_on_adaptive", "예시 learned_cells 는 배정 모드")
        else:
            ok(bd["changed_axis"].startswith("terrain.exposure"), "예시 boundary 축 하나")
        ok(y["maintenance"]["judge_cells"] == 26 and y["maintenance"]["record_cells"] == 13 and y["maintenance"]["on_fail"]["stop_training"] is False, "예시 26 · 13 · stop_training false")
        ok(y["promotion"]["success_min"] == 52 and y["promotion"]["survival_min"] == 60 and y["env"]["num_envs"] == 3072, "예시 52 · 60 · 3072")
    except ImportError:
        ok(False, "pyyaml 없음(예시 YAML 미검사)")
    except Exception as e:
        ok(False, f"예시 YAML 파싱 · 값 오류 {type(e).__name__}: {e}")

# v0.10 analyst 재검 B1~B5
if v010:
    pre = sec[: sec.index("### E.6 ")]
    for old in ("듬성은 깃발 열 없음", "복원 지도 입력 100 %", "0.133", "analyst PLAN 표", "changed_axis", "0.44 → 0.18", "두 줄 → 한 줄 폭 0.155", "레벨 식 **미정**"):
        ok(old not in pre, f"옛 문구 없음(E.6 앞): {old}")
    for kw in ("start_go2_v1", "0.554", "0.166", "`start_sheet.py:156`", "한 줄",                      # B1
               "axis_id", "allowed_diff_paths", "donor", "posture_height", "posture_roll", "경계 셋",       # B2
               "sparse_terrains.py:113~135", "command_set", "last_support_0.5s", "world_frame=True", "policy 실패",  # B3
               "정답 강제 해제", "False 는 PRED 전용이 아니다", "옆좌 · 옆우", "learned_cells", "forced_PRED",  # B4
               "skill_maintenance", "promotion_ready", "pre_drop_anchor", "parent_eval", "calibration.json", "64 → 61 → 58 → 55"):  # B5
        ok(kw in sec, f"B1~B5 「{kw}」")
    exit_sent = "START 네 종 L5 이상 · AME-2 · JEPLO 쉬운 종류 L3 이상 · 연속 L9 · 깃발 15 % · 유지표 통과(각각 두 창)"
    ok(exit_sent in e1.group(0) and exit_sent in blocks.get("E3", ""), "E3 exit 한 문장이 E.1 과 E.2 에 같게")
    e31 = re.search(r"^#### E\.3\.1 .*?(?=^### E\.4 )", sec, re.M | re.S)
    ok(e31 is not None, "§E.3.1 유지 항 표")
    if e31:
        hdr = [l for l in e31.group(0).splitlines() if l.startswith("| 항 |")]
        ok(len(hdr) == 1 and "comparator" in hdr[0] and "role" in hdr[0] and "on_missing" in hdr[0], "E.3.1 머리(comparator · role · on_missing)")
        items = [l for l in e31.group(0).splitlines() if l.startswith("| ") and not l.startswith("| 항 |") and not l.startswith("|---")]
        ok(len(items) == 10 and all(len(cells(l)) == 6 for l in items), f"E.3.1 유지 항 10 행 × 6 칸(이스케이프 세로줄은 칸 안 글자) ({len(items)})")
        ok(sum("judge" in l for l in items) >= 4 and sum("record" in l for l in items) >= 4, "E.3.1 judge · record 역할 둘 다")
        ok("2.5065" in e31.group(0) and "5.1106" in e31.group(0) and "실측" in e31.group(0), "E.3.1 투영 거리 재계산(실측)")
    e6 = sec[sec.index("### E.6 "):]
    rows6 = [l for l in e6.splitlines() if re.match(r"\| (B[1-5] |§[34] )", l)]
    ok(len(rows6) == 7 and all(len(cells(l)) == 5 for l in rows6), f"E.6 반영 표 7 행 × 5 칸 ({len(rows6)})")
    ok(all(len(cells(l)[2].strip()) >= 10 for l in rows6), "E.6 「고친 자리」 칸 비지 않음")
    if "| v0.10 재확인(" in sec:   # v0.11
        for old in ("두 줄 평균대 L0", "tolerance.survival", "전 구간 복원(D162)", "gt_adaptive"):
            ok(old not in pre, f"옛 문구 없음(v0.11): {old}")
        for kw in ("조건부 비율", "command_weights", "assigned_mode", "9.5", "초기 상태 사전 등록", "from_maintenance_items", "(preset, kind)"):
            ok(kw in sec, f"v0.11 「{kw}」")
        ok(any(l.startswith("| v0.10 재확인") for l in e6.splitlines()), "E.6 v0.10 재확인 행")
    if "| v0.11 재확인(" in sec:   # v0.12 · analyst REVIEW-EX42-v011-1103 막음 2
        for old in ("생존 · W57 · 부모 경보는 학습 종료 에피소드 창 64 개", "복원 100 ·", "| 창 64 |", "| 창 64 전체 |", "alive 스텝 중앙값 · 분모 = alive 스텝"):
            ok(old not in pre, f"옛 문구 없음(v0.12): {old}")
        ax = [l for l in sec.splitlines() if l.startswith("| 축 등록표 ")]
        ok(len(ax) == 1 and "`terrain.kind_task.*.command_weights.*`" in ax[0] and "`terrain.kind_task.*.command_set`" in ax[0], "B2 C 축에 command_set · command_weights 두 경로")
        ok("합 ≠ 1" in pre and "`maintenance.items[].source` 가 `fixed_eval` 이 아닌" in pre, "B2 · B5 파서 거절(가중치 합 · source)")
        src_rows = [l for l in sec.splitlines() if l.startswith("| `maintenance.items[].source` |")]
        ok(len(src_rows) == 1 and "`fixed_eval`" in src_rows[0] and "`train_episode_window`" in src_rows[0] and "`assigned_mode_cumulative`" in src_rows[0], "E.4 maintenance.items[].source 행(출처 enum 셋)")
        if e31:
            head = e31.group(0)
            ok(all(k in head for k in ("①", "②", "③", "alive_envs_at_end", "per_env", "kept 규칙")), "E.3.1 표본 출처 ①②③ · 생산자 필드 · kept 규칙")
            ph = [l for l in e31.group(0).splitlines() if l.startswith("| 보행 접촉 위상")]
            ok(len(ph) == 1 and all(k in ph[0] for k in ("FL→RR", "FR→RL", "R(", "주기", "undefined", "recompute.py:45~58", "> 1 N")), "B5 쌍 위상 행(쌍 · R · 주기 · undefined · 접촉 문턱)")
            surv = [l for l in e31.group(0).splitlines() if l.startswith("| 생존 26 칸") or l.startswith("| W57 ") or l.startswith("| 부모 대비")]
            ok(len(surv) == 3 and all("① 고정 평가 칸 64 env" in cells(l)[2] for l in surv), "B5 생존 · W57 · 부모 행 분모 = ① 고정 평가 칸")
        ok(any(l.startswith("| v0.11 재확인") for l in e6.splitlines()), "E.6 v0.11 재확인 행")

ok(chr(0x2014) not in sec, "em dash 없음(정본 절)")
for n, line in enumerate(sec.splitlines(), 1):
    if re.search(r"26 ?칸", line) and not re.search(r"복원|39|13 칸", line):
        ok(False, f"정본 절 {n} 행 「26 칸」 에 복원 기록 없음: {line[:50]}")
print(("ok" if bad == 0 else "FAIL") + f" 어긋남 {bad}")
sys.exit(0 if bad == 0 else 1)
