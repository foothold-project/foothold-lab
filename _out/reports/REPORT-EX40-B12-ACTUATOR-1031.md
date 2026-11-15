# EX-40 B12 actuator gain 기록 결합 수정

> 분류: A/정책학습
> 작성: scripter · 2026-10-31
> 근거: 고정본 b5bca3b5 · B12 실제 Kit run.log 236~239행 · CPU 반례 및 회귀 원출력
> 요지: 관절폭 8과 4의 기록용 표본을 각각 1차원으로 펼쳐 결합한다.
> 상태: CPU 확인됨 · Kit 재시도 미실행

## 실제 실패와 원인

원본 실행은 `C:/Users/AI-WS01/s2_lab/ex40_b12_20261031_b5b/receipts/ex40_b11/B_smoke_20261031_024253_1123474/run.log`에서 첫 reset에 실패했다. `foothold_s2/curriculum/ex40_dr_runtime.py:141`의 `torch.cat(samples)`가 폭 8인 hip/thigh 관절과 폭 4인 calf 관절을 기본 dim 0으로 결합하여 `Expected size 8 but got size 4`를 냈다. 학습 갱신과 저장본은 없었다.

Go2 관절 그룹은 `foothold_s2/robots/go2_cfg.py:12-14`와 `foothold_s2/robots/go2_params.py:13-15`의 hip/thigh 8개, calf 4개다. stiffness와 damping 표본이 모두 들어오므로 env 2개를 부분 reset하면 기록할 gain ratio는 `2 × (8 + 4) × 2 = 48`개다.

## 수정과 답을 아는 시험

`reset_actuator_gains`의 기록 직전에 그룹별 표본을 `reshape(-1)`한 뒤 결합한다. 물리 gain 설정, 표본값, `_record`의 집계 방식은 그대로다. 원함수에 3 env 중 2 env를 주는 CPU 반례를 먼저 실행했고, 수정 전에는 같은 예외로 2개 시험이 실패했다. [수정 전 원출력](EX40-B12-first-fail.txt): `FIRST_FAIL_RC=1`, `2 failed in 2.16s`.

수정 후 시험은 부분 reset 대상과 비대상, stiffness와 damping, scale 0과 0.5, 48개 표본의 count/min/max/mean, NaN 거절을 확인했다. 기존 DR과 B11 회귀를 포함한 한 묶음 [수정 후 원출력](EX40-B12-fixed-regression.txt)은 `REGRESSION_RC=0`, `36 passed in 7.24s`다. CPU에서 실제 함수 경로를 호출한 결과이며 Kit 검증을 대신하지 않는다.

## 파일과 SHA256

| 파일 | SHA256 |
|---|---|
| `foothold_s2/curriculum/ex40_dr_runtime.py` | `e3471eb5b66ad9a9eeac35663419654c4a70b01a24001cea9fa2140e1bc08db7` |
| `foothold_s2/tests/test_ex40_b12_actuator_width_cpu.py` | `0ceed1d46ddb28ce4d8dd9066a7c47ed38f2f6d1e15015ee17b1a94b68f566bc` |
| `_out/reports/EX40-B12-first-fail.txt` | `e1b7cc255ae67ef1dd36dec54b5fc88b2580eec47ff588572b73f7657b1a96e4` |
| `_out/reports/EX40-B12-fixed-regression.txt` | `9c2415f9a3412aacbd5ae0b798b6db8443eed1f6543dba0d59a6facfc2549319` |

새 시험 파일의 `ruff --select F`와 pyflakes는 0건이다. 기존 runtime 파일의 변경하지 않은 F401 2건은 남아 있다. 원본 고정본, Kit 로그, runner, 실행 중 사본은 수정하지 않았다. GPU와 Kit를 다시 실행하지 않았다.
