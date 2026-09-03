# 발표자료 도식 4종 검토본

> 분류: 계획
> 작성: 오흥재 · 2026-09-03 14:51
> 근거: 본인 노트 | 실측 | 공식 문서 | 미확인
> 요지: proposal.pdf에 도입할 후보 도식 4종과 근거 및 사용 조건을 정리한다.
> 상태: 초안
> 이슈: #118

이 폴더는 발표자료와 보고서에 바로 삽입하기 전 확인하는 SVG 원본과 PNG 미리보기다. 원본 수치가 없는 항목은 개념도로 표시했고, 서로 다른 판정 정의에서 나온 수치는 한 도식 안에서 섞지 않았다.

| 파일 | 쓰임 | 근거와 주의 |
|---|---|---|
| `01-difficulty-boundary.svg` | KPI를 성공률에서 난이도 경계 이동으로 바꾼 이유 | 개념도다. 실제 경계 측정 뒤 좌표만 교체한다 |
| `02-wbs-swimlane.svg` | 두 트랙과 다섯 관문의 관계 | 구조 검토본이다. 제작본은 `deliverables/plan/wbs.xlsx` 또는 생성 경로를 읽어 갱신한다 |
| `03-terrain-outcomes.svg` | 미경험 10종의 통과와 실패 양상 | `sim/eval/results/20260903-rough10-1.0mps/summary-thr1.5.csv`의 1,000판 결과 |
| `04-flat-trajectory-definition.svg` | 평지 10 m의 지표별 통과와 방향 판정 차이 | 10 m 관문 33/100과 에피소드 끝 2/100은 판정 시점이 다르다. 도입 전 원자료 정의를 확정한다 |

## 정본 연결

- [발표자료 제작 이슈 #118](https://github.com/foothold-project/foothold-lab/issues/118)
- `deliverables/plan/proposal.pdf`
- `docs/DECISIONS.md`
- `inbox/jay/20260902-기준선-재정립-HANDOFF.md`
- `inbox/jay/20260903-report-v2-개정안.md`
- `sim/eval/results/20260903-flat-10m/README.md`
- `sim/eval/results/20260903-rough10-1.0mps/summary-thr1.5.csv`

`확인됨` 10종 결과와 평지 생존·전진·속도 판정은 실행 결과에 근거한다. `미확인` 평지 방향 33/100과 2/100의 최종 발표 표기는 판정 시점과 실행 원본을 한 번 더 맞춰야 한다. `미측정` 난이도 경계 좌표는 후속 실험값으로 교체한다.
