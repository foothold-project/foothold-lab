> 분류: A/정책학습
> 작성: 오흥재 (lead · scripter 반영) · 2026-10-30 19:27
> 근거: REVIEW-EX40-v2-verifier-1030.md, ex40_v4_req.md, EX-40 v4 CPU 시험
> 요지: 일정 원점과 점수 승급 막음 둘을 고치고 정지 발 광선의 fault·간격 증거를 추가했다.
> 상태: CPU 20 PASS · pyflakes/ruff F 0 · Kit 미실행
> 판: v1.0

# EX-40 v4 CPU 수정 보고

## 범위와 출처

`0779d9d2`에서 만든 별도 사본 `C:/mai/wt/foothold-lab/scripter-ex40-v4`만 수정했다. GPU, Isaac, 학습, 실행 중 사본은 건드리지 않았다. 기존 verifier의 독립 CPU 반례는 H1에서 후속 단계 일정 재시작, H2에서 늦게 온 오래된 PASS와 오래된 캐시 PASS 및 `null` 점수의 중단을 보였다. 원자료는 `C:/mai/wt/foothold-lab/verifier-w56/_out/ex40-v2-review/probe.py`와 `REVIEW-EX40-v2-verifier-1030.md`다. 이 보고의 PASS는 새 코드의 CPU 시험이며 실제 Kit 합격이 아니다.

| 항목 | 수정 | 답을 아는 확인 |
|---|---|---|
| H1 | 최초 실제 B1 진입 회차를 별도 보존하고 후속 단계와 재개에서 같은 원점 사용 | fixed B1 m1501, m3001·4501·5501·6000 계수 0, B2 재개 m3002 계수 0, gate B1 m900 원점 900 |
| H2 | checkpoint 회차 기준 최신 FAIL/HOLD 우선, 캐시 PASS를 승급 직전에 점수 파일과 저장본 SHA로 재검사, 비객체 JSON은 HOLD 기록 | m900 FAIL 뒤 늦은 m500·750 PASS 거절, 750회 된 PASS 거절, 캐시 저장본 변조 거절, `null` 입력에서 학습 중단 없음 |
| M2 | episode 첫 step의 ±y·±yaw 집단을 고정하여 걸음·종료·발 접촉에 동일 적용 | 두 step 사이 방향과 위치 부호를 바꿔도 `[[2,1],[0,0],[0,0],[0,0]]` |
| M3 | 비정지 env는 비유한 광선·힘이 있어도 벌점 0, 정지 env는 해당 발만 0으로 제외 | inf hit, nan Fz, 이동 env nan 질량 입력에서 유한 벌점과 발별 fault 수 확인 |
| 정지 ramp | 정지→정지 명령 재표집이면 elapsed 보존, 이동→정지에서만 0으로 시작 | 0.4초 보존과 새 정지 0초 분리 |
| Kit 영수증 | update별 발 간격 p5/p50/p95, hit 유효 수, 발별 fault 수, hit z·지형 원점 z 표본을 `train_extra.jsonl`에 기록 | 전체 15 update 검사, 총 유효 hit 비율 ≥0.99, 평지 정지 표본 존재와 각 유효 갱신 p50 0~10 mm, 조작 반례 거절 |

Kit 짧은 확인은 기존 B1/B2/B3/T0의 3·6·9·12 진입과 `model_14.pt` 검사도 그대로 수행한다. 새 영수증에는 `stand_sensor_evidence=ex40-v4`가 있어 새 측정 관문을 켠다. v3 이전 영수증은 새 측정치를 만들어낸 것으로 다루지 않는다. 실제 지형 mesh hit, 평지 표본 수와 광선 유효 비율은 Kit에서 미확인이다. 광선은 발 yaw 기준 local x `−0.002 m`에서 쏘고 충돌구 중심은 full 발 자세로 계산하므로 pitch 60°에서 XY 차이가 1 mm다. 계단 경계에서 다른 면을 맞힐 수 있으며 geometry 자체는 이번에 바꾸지 않았다. 임의 자세의 수학적 상한은 4 mm이므로 2 mm를 보편 상한으로 주장하지 않는다.

## 변경 파일과 검증

코드: `foothold_s2/curriculum/continuous.py`, `foothold_s2/rewards/basic_gait_bundle.py`, `foothold_s2/commands/mixed_command.py`, `foothold_s2/commands/mixed_core.py`, `foothold_s2/scripts/train_sol23f_common.py`, `foothold_s2/runners/start_runner.py`, `foothold_s2/ex40_launch.py`, `foothold_s2/ex40_kit_smoke.py`. 시험: `foothold_s2/tests/test_w55_continuous_cpu.py`, `foothold_s2/tests/test_ex40_v4_cpu.py`. 카드: `inbox/jay/20261030-plan/CARD-EX40-1030.md`. 정확한 바이트 SHA는 `EX40-V4-SHA256SUMS.txt`에 있다.

`CUDA_VISIBLE_DEVICES=''`와 `isaac311-moects/python.exe -m pytest -q foothold_s2/tests/test_w55_continuous_cpu.py foothold_s2/tests/test_ex40_v4_cpu.py` 결과는 `20 passed in 3.62s`다. 바뀐 Python 10개에 대한 base Python `-m pyflakes` 종료 0, `ruff check --select F` 종료 0이다. Kit 시험과 GPU 측정은 하지 않았다.

## 남은 확인

lead가 새 고정본으로 Kit 짧은 확인을 실행해 실제 정지 발 광선 hit, 유효 비율과 평지 간격을 판독해야 한다. 실패하면 결과를 HOLD로 기록하고 원시 `train_extra.jsonl`과 실제 mesh를 대조한다. 승급 방식과 arm 결정은 이 CPU 수정으로 확정되지 않았다.

## 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-10-30 | verifier H1/H2와 M1~M3, 정지 ramp 후속 수정 및 CPU 증거 기록. |
