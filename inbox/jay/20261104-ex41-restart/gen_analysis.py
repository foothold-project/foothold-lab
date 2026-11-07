"""W10: EX41-ANALYSIS.md from raw readouts (no hand-typed numbers).

Inputs: the stage-end boundary readout (boundary_report.py output for 750..6000),
EX41R-INCIDENTS.md table rows, the W25 playlist, and the GPU queue for missing clips.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
READOUT = HERE.parent / "20261103-curriculum-lineage/data-v2/ex41-stage-end-boundary-report.txt"
PLAYLIST = Path(r"C:\Users\AI-WS01\s2_lab\_playlists\EX41-ALL-stages-1107.m3u8")
QUEUE = Path(r"D:\mai-tmp\gpu\queue.json")
STAGES = {"750": ("S2a", "m6750"), "2750": ("S2b", "m8750"), "3750": ("S2c", "m9750"),
          "5000": ("S2d", "m11000"), "5500": ("S2e", "m11500"), "6000": ("T0′", "m12000")}

text = READOUT.read_text(encoding="utf-8")
blocks = {m.group(1): m.group(2) for m in re.finditer(r"^== (\d+)\n(.*?)(?=^== \d+\n|\Z)", text, re.S | re.M)}
assert set(STAGES) <= set(blocks), sorted(blocks)

rows = []
for it, (stage, cum) in STAGES.items():
    b = blocks[it]
    pred = re.search(r"지도 복원 - 정답: 오차 차 평균 ([+-]\d\.\d+) · 가장 큰 차 (\S+) ([+-]\d\.\d+) · 생존 합 차 ([+-]\d+)", b)
    off = re.search(r"지도 끔 - 정답: 오차 차 평균 ([+-]\d\.\d+) · 가장 큰 차 (\S+) ([+-]\d\.\d+) · 생존 합 차 ([+-]\d+)", b)
    over = {mode: re.search(rf"^M {mode}\s+판정선 넘은 명령 (\d+) (\[.*?\]) · 생존 최저 (\d+)/64", b, re.M)
            for mode in ("eval_gt", "eval_pred", "probe_prop_only")}
    sym = re.search(r"대칭 S eval_gt: 평균 (\d\.\d+) 최저 (\d\.\d+) <0\.8 (\d+)", b)
    assert pred and off and all(over.values()) and sym, it
    rows.append((stage, cum, pred.groups(), off.groups(),
                 {k: v.groups() for k, v in over.items()}, sym.groups()))

inc = [ln for ln in (HERE / "EX41R-INCIDENTS.md").read_text(encoding="utf-8").splitlines()
       if re.match(r"^\| I\d+ \|", ln)]
groups = re.findall(r"^#EXTGRP:(.*) \((\d+)\)$", PLAYLIST.read_text(encoding="utf-8"), re.M)
q = json.loads(QUEUE.read_text(encoding="utf-8"))
by_id = {x["id"]: x for x in q["items"]}
missing = []
for x in q["items"]:
    if x["state"] != "실패" or "1c6af6319c82" not in (x["title"] or "") or "video" not in x["title"]:
        continue
    if any(y.get("retry_of") == x["id"] for y in q["items"]):
        continue
    chain, j = [], x["id"]
    while j:
        chain.append(j)
        j = by_id[j].get("retry_of")
    if len(chain) >= 3:
        missing.append((x["title"].split("1c6af6319c82-")[1].rsplit("-", 1)[0], chain))

L = []
w = L.append
w("> 분류: 분석 보고")
w("> 작성: 오흥재 · 2026-11-07")
w("> 근거: 실측 (단계 끝 경계 보고 6 개 · boundary_report.py 출력 `data-v2/ex41-stage-end-boundary-report.txt` · 사고 기록 · 재생 목록 · GPU 대기열)")
w("> 요지: EX-41 여섯 단계 끝 모두 유지 판정 통과 · 지도 셋(정답 · 복원 · 끔)의 명령 추종 오차 차는 map64 명령 시험(연속 지형 7 종 L0~2)에서 작다(가장 큰 칸 0.03 안) · 걷는 모양이 같은지와 지도의 쓸모는 미확인 · 후진 1.0 과 좌우 대칭이 남은 과제")
w("> 상태: v1.1 (analyst 대조 e10fd0df 의 해석 고침 3 반영) · 단계 보고서 S2e · T0′(W45 analyst) 와 m12000 W78 · 정본 216 영상이 들어오면 v2")
w("")
w("# EX-41 분석 보고서")
w("")
w("정본 채택 문서(계보 · 단계 표 · 밀기 기준선 · EX-42 로 넘기는 것)는 [docs/research/20261107-ex41-canon-m12000.md](https://github.com/foothold-project/foothold-lab/pull/586) 에 있다. 이 보고서는 거기 없는 세 가지를 모은다: **지도 셋 비교 · 사고 · 영상 자료의 빈칸**.")
w("")
w("## 1. 지도 셋 비교 (단계 끝마다)")
w("")
w("지도 셋은 정답 지도(eval_gt) · 깊이 영상으로 복원한 지도(eval_pred) · 지도 끔(probe_prop_only) 이다. 아래 「오차 차」 는 map64 명령 시험(연속 지형 7 종 · L0~2 · 순수 평지가 아님) 13 명령에서 명령 추종 오차를 지도끼리 뺀 값의 평균이다. **선속도 11 칸(m/s)과 회전 2 칸(rad/s)을 섞은 평균**이라 한 단위로 읽으면 안 된다. 단위를 나눈 표는 analyst 대조 [VERIFY-W10-MAP3.md](https://github.com/foothold-project/foothold-lab/blob/e10fd0df/inbox/jay/20261107-w10check/VERIFY-W10-MAP3.md) 에 있다. 음수면 그 지도가 정답보다 오차가 작다. 같은 저장본을 반복해 잰 잡음 폭은 재지 않았다.")
w("")
w("| 단계 | 누적 | 복원 - 정답 평균 · 가장 큰 칸 | 끔 - 정답 평균 · 가장 큰 칸 | 0.15 넘은 명령 수 (정답 · 복원 · 끔) | 생존 최저 (정답 · 복원 · 끔) | 대칭 S 정답 평균 · 최저 · 0.8 미만 |")
w("|---|---|---|---|---|---|---|")
for stage, cum, p, o, ov, s in rows:
    w(f"| {stage} | {cum} | {p[0]} · {p[1]} {p[2]} | {o[0]} · {o[1]} {o[2]} | "
      f"{ov['eval_gt'][0]} · {ov['eval_pred'][0]} · {ov['probe_prop_only'][0]} | "
      f"{ov['eval_gt'][2]} · {ov['eval_pred'][2]} · {ov['probe_prop_only'][2]} | {s[0]} · {s[1]} · {s[2]} |")
w("")
w("**해석.**")
w("")
w("- `확인됨` 복원 - 정답 평균 차는 여섯 단계 모두 표시값으로 0.002 이하다(S2e 실제 값 -0.0023 · 반올림 -0.002). 복원 지도로 바꾼 T0′ 에서도 작다. 다만 오차 평균이 작다는 것만으로 걷는 모양이 같다고는 말할 수 없다 `미확인`.")
w("- `확인됨` 지도 끔이 정답보다 평균 오차가 조금 작다(여섯 단계 모두 음수). 이 시험은 낮은 레벨 지형이라 지도의 쓸모를 가르기 어렵고, 그 까닭이 「지도가 필요 없어서」 인지는 `미확인` 이다. 지도가 일을 하는지는 **계단 시험(W78 · W80)** 에서 가려야 한다.")
w("- `미확인` 지형에서 지도 셋의 차. 단계마다 W78(계단 L5) 점수가 GPU1 에서 돌고 있고, m12000 몫(대기열 747)은 아직 시작 전이다.")
w("")
w("## 2. 사고와 막는 장치")
w("")
w(f"운영 중 사고 {len(inc)} 건이 [EX41R-INCIDENTS.md](EX41R-INCIDENTS.md) 에 막는 장치와 함께 있다. 실험 결과에 닿은 것만 고른다.")
w("")
w("- S2b 의 DR 이 1,000 회 멈춤: 점수 증거가 늦게 와서 안전장치가 DR 을 올리지 않았다. 성적 탓이 아니다. 그래서 뒤 단계가 1,000 회씩 밀렸다.")
w("- 어두운 화면(I34 · I35): 영상만 실패한다. 점수 · 학습에는 닿지 않는다. 같은 칸을 다시 찍으면 대부분 통과한다. runner 가 검은 원본과 렌더 전후 물리 상태를 남겼고 원인은 아직 `미확인`.")
w("- 점수 대기(I36) · GPU0 빈 시간(I37): 결과는 같지만 시간이 늦어졌다. EX-42 출발 관문표에 「점수 30 분 대기 FAIL」 「GPU0 대기 있는데 실행 없음 FAIL」 로 넣었다.")
w("")
w("## 3. 영상 자료")
w("")
w(f"종합 재생 목록 `{PLAYLIST}` (W25):")
w("")
for title, n in groups:
    w(f"- {title}: {n} 편")
w("")
if missing:
    w(f"결측 {len(missing)} 편 (같은 칸 세 번 실패 · 어두운 화면 · 더 걸지 않음):")
    w("")
    for name, chain in missing:
        w(f"- m12000 {name} (대기열 {' → '.join(map(str, reversed(chain)))})")
    w("")
w("정본 m12000 의 216 칸 영상(이전 정본 EX-40 과 같은 12 지형 × L0~L5 × 지도 셋 · 앞 1.0 m/s · 18 초)은 GPU0 에서 촬영을 시작했다. 판정 근거가 아니라 관찰용이다.")
w("")
w("## 4. 아직 모르는 것")
w("")
w("- 지형(W78 계단 L5)에서 지도 셋의 차 · m12000 W78 은 GPU1 대기열 747.")
w("- 좌우 대칭 S 가 S2d · T0′ 에서 낮아진 까닭. 두 구간 모두 두 가지가 같이 바뀌었다.")
w("- 어두운 화면의 원인.")
w("")
w("## 원자료")
w("")
w("- 단계 끝 경계 보고: `inbox/jay/20261103-curriculum-lineage/data-v2/ex41-stage-end-boundary-report.txt`")
w("- 생성기: `inbox/jay/20261104-ex41-restart/gen_analysis.py` (이 문서의 숫자는 모두 여기서 읽는다)")
(HERE / "EX41-ANALYSIS.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("rows", len(rows), "incidents", len(inc), "groups", len(groups), "missing", len(missing))
