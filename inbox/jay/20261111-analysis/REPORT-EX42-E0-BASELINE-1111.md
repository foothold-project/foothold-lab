# EX-42 E0 부모 기준선 고정과 m250 CPU 재판정

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: 팀장 결정 decisions.tsv 416행 · A23 calibration SHA 1fa9db536a26f853bf43d31b3095faac59ce0c67b68f44425a9fb216d3537e3e · m250 저장 평가
> 요지: 부모 다섯 판의 기준값을 고정하고 저장된 m250을 새 GPU 실행 없이 다시 판정했다.
> 상태: CPU 재판정 완료 · 운영 원장 미변경

`실측` 근거는 원본 영수증과 CPU 재판정 영수증이다. 판정 코드의 이전 동작은 [EX-42 점수기 원본](https://github.com/foothold-project/foothold-lab/blob/4cc326c7/foothold_s2/ex42_score.py)에서 확인할 수 있다.

## 기준선과 문턱

- Calibration: `/home/jay/mai/tmp/scripter/ex42-a23-calibration/calibration.json`. SHA256 `1fa9db536a26f853bf43d31b3095faac59ce0c67b68f44425a9fb216d3537e3e`. seed 42 두 번과 43 · 44 · 45, A 연속 23열, 부모 m13000 SHA `20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768`.
- 기준선 파일: `foothold_s2/curriculum/ex42_e0_baseline_a23.json`. SHA256 `402c4a4a8f49a86565802114dcfa98a62ecfb59edb6a28433db5adc347a75c13`. 유효 숫자 1461개는 다섯 값의 중앙값으로 고정했고, 다섯 판 모두 결측인 39개는 결측으로 보존했다.
- q4 실측 한도: 생존 하락 6 env, vx/vy 오차 상승 0.05125124752521515 m/s, wz 오차 상승 0.05 rad/s. 발 끌림 120개 칸은 `max(부모 중앙값 × 0.25, 반복 폭 × 2)`로 각각 계산했다. 그 한도 범위는 0.006137179~0.151034168 m이다. 발 끌림은 E0에서 기록 전용이며 E2부터 판정한다.
- 승인 파일 SHA256 `c4c76916f8d126694c7c8c9be81430919d99cf09a27375379f727cc19c24f680`. `stage_zero.approval_sha256`와 같고 승인 파일은 수정하지 않았다. `ex42-prep.yaml`의 측정값은 갱신되어 새 plan SHA는 `5ddcc650e5510937ddab5e0594ab3248a0aa63b4e90f46a05ea802e0d0f8ccee`이다.

## m250 재판정

- 원본 평가: `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218/eval/scores/m250`. 원본 score SHA `8d645a1b95a595e1bab8737604bf3e1bb2a2a870e9494d4a520f65c099debd3e`, 원본 P1 SHA `f830bc2845442c5b92161e08aea52b2350808761a522f8c26e194915ea118ca7`. 기존 운영 영수증은 HOLD 그대로 보존했다.
- CPU 재측정은 map64 · stand · axis_v2의 파싱한 JSON 값이 원본 score와 모두 같을 때만 계속한다. 새 산출: `/home/jay/mai/tmp/scripter/ex42-e0-rejudge-m250-v3`. 새 score SHA `7c656fbb99a7be8d56819bf99d40c0a252d24e2136b6939f586ae60f54eb9bcb`, 새 P1 SHA `14040116fe6861d31a292399e918822afe3b36e5823af61b591ea83dadfdbea6`.
- 공식 새 기준 결과: **PASS**. 평가 지도 두 모드 26칸의 104개 생존 · vx · vy · wz 검사 모두 PASS. 끔 모드 13칸은 기록 전용 HOLD. 칸별 숫자와 문턱은 `/home/jay/mai/tmp/scripter/ex42-e0-rejudge-m250-v3/cells.csv` 및 `/home/jay/mai/tmp/scripter/ex42-e0-rejudge-m250-v3/ex42_score.json`에 있다.

| 검사 | 최대 불리한 차 | 한도 |
|---|---:|---:|
| 생존 | 1.000000 env | 6 env |
| vx | 0.013537 m/s | 0.051251 m/s |
| vy | 0.006261 m/s | 0.051251 m/s |
| wz | 0.004699 rad/s | 0.05 rad/s |

## 경계

- `command_projection` · 발별 접촉 · 보행 위상 · 발 끌림 · yaw 적분은 현재 단계에서 기록 전용이다. `parent_cumulative_drop`는 두 창 연속 자료가 없어 HOLD로 남는다. E0 전체 PASS는 26개 판정 칸에 한정한다.
- 부모 calibration 평가 코드 HEAD `d4e9a7bac76057aa37d55cb2a5f44d57a0f19628`와 m250 평가 코드 HEAD `187777e711490114c024536a55cb3a58862f6d7d`는 다르다. A23 고정 배정 · 메시 · 시드와 측정 필드를 대조했지만, 코드 차이에 따른 편향을 분리한 결과는 아니다.
- 운영 E0 점수 원장과 학습 중인 사본은 건드리지 않았다. 새 plan SHA의 점수를 운영 사슬에 채택하는 절차는 lead가 별도로 결정해야 한다. E1 이후 점수 규칙은 이 E0 판으로 자동 PASS시키지 않는다.
