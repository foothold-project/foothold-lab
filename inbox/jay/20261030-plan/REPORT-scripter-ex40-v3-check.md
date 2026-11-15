> 분류: A/정책학습
> 작성: 오흥재 (lead · scripter 반영) · 2026-10-30
> 근거: EX-40 B Kit smoke 원본 영수증·run.log·저장 env.yaml, S-B10 저장 env.yaml, 결정 8
> 요지: 지형 승급 세계 좌표 차이를 좁게 확인하고 기존 Kit 산출을 재검사했다.
> 상태: B smoke 확인기 PASS · 직접 ray hit 유효 개수 미기록
> 판: v1.0

# EX-40 B Kit smoke 확인기 재검사

## 원인과 수정

원본 확인기는 S-B10과 EX-40의 `curriculum` 전체가 같아야 한다고 요구했다. 저장 설정의 실제 차이는 `curriculum.terrain_levels.params`뿐이다. S-B10은 `{}`이고 EX-40은 `{mask_new_task: false, world_frame: true}`다. 결정 8에 따라 EX-40 값을 유지했다.

새 확인기는 S-B10 저장 설정을 복사해 이 두 값만 기대값으로 바꾼 뒤 `curriculum` 전체를 비교한다. 두 값 또는 그 밖의 curriculum 항목이 다르면 실패한다. 새 기동 영수증과 카드에는 `S-B10 대비 의도된 차이 1: 지형 승급 판정 세계 좌표(결정 8)`를 기록한다. 기존 실제 기동 영수증은 수정하지 않았다. 재검사 산출인 `kit_check.json`에 이 차이와 원본 영수증·run.log·확인기 SHA가 남는다.

## 기존 Kit 산출 재검사

입력: `C:\Users\AI-WS01\s2_lab\ex40\v2ray_kit_smoke_20261030_lead1\receipts\ex40\B_smoke_20261030_185321_1089100\launch_receipt.json`와 같은 폴더의 `run.log`, `rc.txt`의 rc 0. 새 학습이나 Kit 실행 없이 같은 폴더에 `kit_check.json`을 썼다.

| 확인 항목 | 결과 | 근거 |
|---|---|---|
| 단계 진입 | PASS | B0=0, B1=3, B2=6, B3=9, T0=12 |
| 자연 reset 뒤 채택 | PASS | B1 727, B2 614, B3 377, T0 242 env. 명령·지도 실제 소비 영수증과 대조 |
| 보상 등록·가중치 | PASS | 저장 `params/env.yaml`의 B0 계수와 단계 표를 비교. `train_extra.jsonl` 정지 칸에 `ex40_stand_gap`·`ex40_stand_load` 유한 값 기록 |
| 발 ray 설정 | 확인 | 저장 `params/env.yaml`의 네 `ex40_support_{0..3}` 모두 `ray_alignment: yaw` |
| 발 ray 실제 hit 유효 개수 | 미확인 | 개별 `ray_hits_w` 유효 개수는 저장되지 않음. 정지 보상의 유한 값은 간접 증거일 뿐 |
| 질량 | 확인 | `realized_physics.json` masses shape `[3072,19]`, min 0.001, max 9.921 kg. 개별 몸 질량 합계는 이 검사에서 독립 재계산하지 않음 |
| 종료와 저장본 | PASS | rc 0, Traceback 0, `train_start_status.json` done iter 14, `model_14.pt` SHA `2bb560e68afa22f1d487871df36495d0d3b96ba807cf0252f343daae9ead5551` |

`kit_check.json`의 PASS는 현재 확인기가 기록된 단계·소비·설정·저장본을 확인했다는 뜻이다. 광선 hit의 지형별 유효성이나 장기 학습 성능 판정은 포함하지 않는다.

## CPU 시험과 해시

`isaac311-moects/python.exe -m pytest foothold_s2/tests/test_w55_continuous_cpu.py -q`: 11 passed. 알려진 정상 입력과 `world_frame=false`, `mask_new_task=true`, curriculum 추가 키 세 변이는 각각 지정 실패로 확인했다. `pyflakes`, `ruff check --select F`, `py_compile`, `git diff --check`는 바뀐 Python 파일에 오류 0건이다. 변경 코드·시험·카드·이 보고서의 SHA 목록은 `EX40-V3-SHA256SUMS.txt`에 있다.
