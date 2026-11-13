# EX-42 E1 경계 자동 판정

> 분류: A/평가
> 작성: scripter-lx · 2026-11-13
> 근거: ex42_score.json · G1/G1b 원자료 · 구간 영수증 · 규칙 aa1f2dba · bdf2bb30
> 요지: 출발점 대비와 직전 경계 대비를 재고, 결측은 결측으로 둔다.
> 상태: CPU 집계 · 조정 제안은 미실행

| 경계 | 전체 점수 | 유지 | 옆 S (출발점 · 직전 증감) | 느린 전진 F1 | 느린 회전 P1 | 두 번 하락 | 큰 하락 | 부작용 | 명령 · 보상 제안 |
|---|---|---|---|---|---|---|---|---|---|
| m250 | FAIL | PASS | 0.760 (0.024 · 미측) | 0.036 | 0.734 | 0 | 0 | 0 | PARTIAL · not_applicable |
| m500 | FAIL | PASS | 0.738 (0.003 · -0.022) | 0.053 | 0.735 | 0 | 9 | 0 | PARTIAL · not_applicable |
| m750 | FAIL | PASS | 0.799 (0.064 · 0.061) | 0.001 | 0.740 | 6 | 6 | 0 | FROZEN · PROPOSED_DRAFT |
| m1000 | FAIL | PASS | 0.778 (0.043 · -0.020) | 0.019 | 0.755 | 17 | 3 | 0 | FROZEN · PROPOSED_DRAFT |
| m1250 | FAIL | PASS | 0.786 (0.051 · 0.008) | -0.015 | 0.690 | 2 | 20 | 0 | FROZEN · PROPOSED_DRAFT |
| m1500 | FAIL | PASS | 0.689 (-0.047 · -0.098) | 0.002 | 0.718 | 14 | 9 | 0 | FROZEN · PROPOSED_DRAFT |
| m1750 | FAIL | PASS | 0.731 (-0.004 · 0.042) | -0.004 | 0.745 | 18 | 15 | 0 | FROZEN · PROPOSED_DRAFT |
| m2000 | FAIL | PASS | 0.715 (-0.021 · -0.016) | 0.077 | 0.746 | 6 | 8 | 0 | FROZEN · PROPOSED_DRAFT |

V는 3시드 경계 자료가 없어 미측정이다. 현재 경계별 반복 폭도 없어 폭 급증 깃발은 미측정이다.
G1이 brief에 없는 경계는 같은 저장본 SHA의 형제 map_modes.json을 재집계했다.
유지 칸은 전체 점수와 구분해 maintenance_judgement를 읽었다.
큰 하락 >0.05, 반복 폭 급증 >2배는 경보 표시에만 쓰는 가정이며 승인된 조정 문턱이 아니다.
보상 규칙 bdf2bb30은 초안이다. JSON은 제안이며 학습 설정을 바꾸지 않는다.
## 재현 경로

입력은 `/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150/eval/scores/m<N>/ex42_score.json`, 같은 실행 폴더의 `segment_commands_b<N>.json` 및 `segment_rewards_b<N>_rank{0,1}.json`, `/home/jay/data/foothold/s2_lab/hipan_g1_20261112/briefs/m<N>_L{0,5}.json`이다. 원자료와 영수증 SHA는 출력 JSON의 `source` 칸에 있다.

```bash
python3 -m foothold_s2.tools.ex42_boundary_autojudge \
  --score-root /home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150/eval/scores \
  --brief-root /home/jay/data/foothold/s2_lab/hipan_g1_20261112/briefs \
  --adjust-root /home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150 \
  --out /home/jay/mai/tmp/scripter/boundary-1113/actual
```

산출은 `boundary_judgment.json` (경계별 숫자와 제안), `boundary_metrics.csv` (모든 지표의 출발점 및 직전 경계 차), `boundary_alarms.csv` (깃발별 지표), `REPORT.md`이다. 영수증 누락이나 신원 불일치는 예외로 멈춘다. 이 도구는 조정 값을 쓰거나 학습을 기동하지 않는다.

## 판정의 범위

- 경계별 3시드 V가 없으므로 명령 S1 후보도 안전 확인 전 `PARTIAL`이다. 반복 폭 급증 여부는 현재 모두 미측정이다.
- m500부터 큰 하락 경보가 있다. 두 경계 연속 하락 경보는 m750부터 켜진다. 각각의 지표와 차이는 CSV에 기록했다. 경보용 0.05와 2배는 가정이며 승인된 설정 변경 문턱과 구분한다.
- m750 이후 보상 L1 후보는 `bdf2bb30` 초안의 제안이다. 실제 보상 변경이 없었던 경계들에서 부작용 깃발은 0이다. 안전 판단을 위한 지형 레벨 Z는 미측정이다.
- 전체 `ex42_score.json` 판정 FAIL과 유지 항목 PASS를 각각 표시했다. 따라서 이 표를 E1 통과 판정으로 읽을 수 없다.
