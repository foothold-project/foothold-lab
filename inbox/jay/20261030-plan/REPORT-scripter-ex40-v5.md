> 분류: A/정책학습
> 작성: 오흥재 (lead · scripter 반영) · 2026-10-30 19:47
> 근거: lead의 v4 Kit B smoke, REVIEW-EX40-v4-verifier-1030.md, 설치 소스와 CPU 반례
> 요지: 발별 분위수와 7종 지형 관문을 고치고 동률 gate, 영수증 무결성, 독립 보상 마스크를 닫았다.
> 상태: CPU 24 PASS · pyflakes/ruff F 0 · v5 Kit 미실행
> 판: v1.0

# EX-40 v5 좁은 수정 보고

## 실제 실패와 수정 경계

v4 Kit B smoke 원자료 `C:/Users/AI-WS01/s2_lab/ex40/v4_kit_smoke_20261030_lead1/smoke/EX-40-B-kit-smoke_20261030_193122_133436/train_extra.jsonl`의 15갱신을 CPU로 읽었다. 첫 갱신 정지 발 hit는 29848/29848, 마지막은 26644/26644로 모두 유효했다. `flat_columns=[]`가 15줄 모두 같았다. v4의 네 발 p50이 매 줄 똑같은 것은 `gap[valid[:, i]]`가 한 발 열이 아니라 선택된 행의 네 발을 전부 읽은 오류다. 기존 값 0.004~0.03 mm를 발별 간격 증거로 사용하지 않는다. S-B10 원 설정의 7종 지형에는 `flat` 열이 없어 평지 표본 관문은 구조적으로 통과할 수 없다.

별도 사본 `C:/mai/wt/foothold-lab/scripter-ex40-v5`는 `21f84657`에서 갈라졌다. 학습 중 사본, Kit 원자료, GPU 프로세스는 건드리지 않았다.

| 항목 | 바뀐 계약 | CPU 반례 |
|---|---|---|
| 발별 p5/p50/p95 | `gap[:, foot][valid[:, foot]]`만 사용. hit와 gap은 유한하지만 Fz가 비유한인 발의 gap 통계도 남긴다. | 네 발 1·2·3·4 mm의 각 분위수가 서로 다름. 한 발 NaN이어도 다른 세 발은 유한. |
| v5 Kit 관문 | 평지 열을 요구하지 않는다. 15갱신 전체 정지 발 hit 비율 ≥0.99, 네 발 각각의 갱신별 유효 p50 0~10 mm, 각 발의 전체 유효 표본 존재를 확인한다. | 실제와 같은 `flat_columns=[]` 합성 양성, hit 0.98·발 p50 11 mm 거절. |
| 영수증 무결성 | `stand_sensor_evidence=ex40-v5` 필수. valid≤total, 발별 hit 유효 수 합=valid, 발별 gap 유효 수와 분위수 일치, 유한·순서, 표본의 발·행·z 차 유한성을 검사한다. smoke의 Fz/gap 비유한 수는 0이어야 한다. | 마커 제거, valid>total, 발별 수 과장, 빈 hit 표본, NaN 분위수, 비유한 fault 수 조작 거절. 전체 `check()` 경로에서도 마커·발별 수 조작을 거절. |
| 동률 gate | 같은 checkpoint 회차·created_at의 상충 FAIL/HOLD는 PASS를 취소하고 HOLD 기록. | m500·750 PASS 캐시 뒤 m750 같은 시각 FAIL 또는 HOLD 추가 시 B0 유지. |
| 정지 벌점 | gap 항은 유한 gap만, load 항은 유한 Fz만 사용한다. 한 항의 결손이 다른 항을 지우지 않는다. | 첫 발 gap 55 mm·Fz NaN이면 gap 벌점 유지, 둘째 발 gap NaN·Fz 0이면 load 벌점 유지. |

기존 v4 Kit 파일에는 발별 정확한 p50과 새 발별 유효 수가 저장되지 않아 사후에 v5 합격으로 재분류할 수 없다. lead가 같은 3·6·9·12 단계와 `model_14.pt` 종료를 포함한 v5 Kit 짧은 확인을 다시 수행해야 한다. hit 비율과 interval은 v5의 새 `train_extra.jsonl`에서 판독한다. Kit 재확인 전에는 v5 PASS라고 하지 않는다.

## 검증과 산출

`CUDA_VISIBLE_DEVICES=''`로 `isaac311-moects/python.exe -m pytest -q foothold_s2/tests/test_w55_continuous_cpu.py foothold_s2/tests/test_ex40_v4_cpu.py -p no:cacheprovider`를 실행해 `24 passed in 3.99s`를 얻었다. 세 지정 반례는 수정 전 3 FAIL, 수정 후 PASS였다. 바뀐 Python 6개에 `python -m pyflakes`와 `ruff check --select F`가 모두 종료 0, `git diff --check` 종료 0이다. GPU와 Isaac은 실행하지 않았다.

변경: `foothold_s2/rewards/basic_gait_bundle.py`, `curriculum/continuous.py`, `ex40_kit_smoke.py`, `ex40_launch.py`, `tests/test_w55_continuous_cpu.py`, `tests/test_ex40_v4_cpu.py`, 카드. 바이트 해시는 `EX40-V5-SHA256SUMS.txt`에 기록한다. v4 고정본은 수정하지 않았다.

## 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-10-30 | Kit v4 실측과 verifier 추가 반례를 v5 CPU 코드·카드·검사기로 반영. |
