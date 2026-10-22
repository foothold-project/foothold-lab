> 분류: 실험
> 작성: 오흥재 (luna 문서 반영) · 2026-10-22
> 근거: LEAD-HANDOFF-20261022.md §21·22 · #555 6342115176 · BASELINE-0811.md
> 요지: v2 설정을 처음부터 학습한 EX-24a는 START 본류가 아닌 scratch 진단 기준이다.
> 상태: 301 update 종료 보고 · 보행 결과 미측정 · 새 실행 없음

# EX-24a · v2 설정 처음부터 학습

## 가설과 결과 전 등록

> [선행] “EX-24a(v2 설정 처음부터).” [LEAD-HANDOFF-20261022.md §22](../20261019-design/LEAD-HANDOFF-20261022.md#22-기준선-정정과-오늘-밤-순서-2235)

v2 설정을 checkpoint 없이 처음부터 학습했을 때 811과 같은 update에서 자세 형성이 재현되는지 확인한다. 표준 rsl_rl의 v2 설정 점검이며 START 본류가 아니다.

## 설정

| 항목 | 기록 |
|---|---|
| 역할 | `[lead 결정]` v2 scratch 기준선 진단, EX-24b의 설정 부모. EX-23/25 START 본류에 속하지 않는다. |
| 설정 | `[lead 기록]` v2 설정 처음부터 학습, actor 높이 스캔 포함. 로그 위치는 `logs/rsl_rl/unitree_go2_gap_nvidia/` 아래 ex24a로 보고됐다. |
| 학습 범위 | `[lead 기록·handoff §22]` 300/301 update에서 종료. 소비 cfg·checkpoint 인자는 직접 재검증하지 않았다. |
| 평가 | `[선행·handoff §21]` v2 정책 형식은 `record_seq --policy v2 --checkpoint <model_N.pt>`로 별도 촬영. auto_watch·mid500_ck 직접 재사용 여부 미확인. |
| 체크포인트 | `scratch`라는 실험명과 설정 계보를 checkpoint 메타데이터 확인으로 대체하지 않는다. 실제 resume 값은 미확인이다. |

## 판정 · 결과 전 등록

811·v2 resumed policy·v2 scratch 학습 속도는 구분한다. `[실측·BASELINE-0811]` 같은 도구 기준 300회 몸 높이 0.19 m, 500회 0.32 m 상승·전진, 1000회 0.40 m와 대각 비율 0.97 trot다. 새 합격 수치를 추가하지 않는다.

## 결과

`[lead 기록·handoff §22]` 301 update 종료. 보행 위상·몸 높이·영상 판독 결과는 제공된 근거에서 확인되지 않아 미측정이다. 영상 없음 · 미확인.

## 다음

gait_table·영상·위상 자료가 결과 기록에 연결되면 811의 같은 회차와 비교한다. v2 scratch 결과를 EX-23/25 START 구조 성능으로 일반화하지 않는다.