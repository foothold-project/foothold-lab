# EX-40 v6 확인기 좁은 수정

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · scripter 반영 · 2026-10-30 20:06
> 근거: verifier V5-H1 반례 · d559c82b · lead v5 Kit 영수증
> 요지: 발별 정상 hit와 유한 gap의 표본 수 일치를 갱신마다 확인한다
> 상태: CPU 재현 및 실제 v5 영수증 재판독 완료 · Kit 재실행 없음

## 변경

- 새 사본 `C:/mai/wt/foothold-lab/scripter-ex40-v6`을 `d559c82b`에서 분리했다. 실행 중인 사본과 생산 코드 `basic_gait_bundle.py`는 수정하지 않았다.
- `foothold_s2/ex40_kit_smoke.py`의 `_check_stand_sensor`에서 기존 비유한 gap 수 0 확인 뒤, 발별 `gap_valid_count_by_foot == hit_valid_count_by_foot`를 15개 갱신 각각에 요구한다. 새 성능 문턱을 만들지 않고 생산 코드의 계수 관계를 확인한다.
- 검증자의 `zero_gap_count_with_all_finite_hits.jsonl`을 시험 fixture로 번들 안에 복사하고 SHA256을 고정했다. 외부 검증 사본을 읽지 않아도 재현된다.
- fixture 줄바꿈을 LF로 고정해 Git 보관본과 작업 사본의 바이트 및 SHA가 같게 했다.

## 답을 아는 입력과 실제 자료

| 입력 | 결과 |
|---|---|
| v5 확인기에 유한 hit 1, gap 비유한 0, gap count 0, 분위수 null을 한 갱신에 넣음 | 지정 첫 FAIL: `DID NOT RAISE ValueError` |
| v6 동일 입력 | 기대 거절 `gap valid count differs from finite hits` |
| v6 관련 CPU 시험 | 25 passed in 4.27s |
| v5 Kit 완료 영수증을 v6 `check()`로 재판독 | PASS, 15 updates, hit ratio 1.0, 발별 gap 표본 각 109076 |

실제 영수증: `C:/Users/AI-WS01/s2_lab/ex40/v5_kit_smoke_20261030_lead1/receipts/ex40/B_smoke_20261030_195150_1093510`.
새 결과: 같은 폴더의 `kit_check_v6.json`, SHA256 `7bfacd2e5d024135cb1898ee368f3a5577e208b34e4c4809279bdbd3a469be44`.
기존 `kit_check.json` SHA256은 재판독 전후 `aee80da2c856990a83c6ff05b6b99e614ff347ae2af4d86c950a61c84deaa68d`로 동일하다.

## 검증 범위

`CUDA_VISIBLE_DEVICES=''`와 `isaac311-moects` Python으로 두 관련 시험 파일을 실행했다. `pyflakes`와 `ruff check --select F`는 모두 0건, `git diff --check`도 통과했다. 학습과 Kit은 실행하지 않았다. 개별 3072 env 광선 원자료는 영수증에 없어, 이번 PASS는 저장된 갱신별 집계와 확인기 계약에 대한 판독이다.
