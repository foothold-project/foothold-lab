# EX-39 A/B Kit 짧은 확인 준비

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · scripter 반영 · 2026-10-29
> 근거: 팀장 21:5x 결정, REVIEW-EX39-reviewer-1029, REVIEW-EX39-verifier-1029, EX-38 완료 저장본, 아래 CPU 시험
> 요지: EX-39 A/B를 각 2회 갱신 후 B 한 명령 평가까지 직렬 확인하는 Kit 스크립트와 실패 영수증을 준비했다.
> 상태: CPU 검증 완료 · Kit와 GPU는 미실행 · lead의 실제 확인 대기

## 시작을 막는 장치

- R6 · M15: 순수 CPU cfg 대역 시험은 실제 Kit 등록 증거가 아니다. 실제 env가 생성된 뒤 reward term, resolve된 관절과 발, 명령 비율을 `ex39_kit_probe.json`에 기록한다.
- R20 · M08: 실제 부모 SHA, 실제 학습 parser, 동일한 A/B 커밋을 시작 전에 검사한다. `run_ex39.sh`와 평가 module을 그대로 호출한다.
- R21: 10/30 15:00 KST는 마감 상한이다. 2회 갱신을 다 못 하면 완료로 표시하지 않는다.
- R24: 자식 종료 코드 외에 첫 update 로그, 최종 checkpoint SHA, 상태 파일, probe, 평가 JSON을 되읽어 PASS/FAIL을 한 파일에 쓴다.
- M02: 도는 학습 코드나 셸 스크립트를 고치지 않는다. 두 detached 작업 사본을 같은 새 커밋으로 고정한 뒤 lead가 실행한다.

## 실제 확인 순서

1. GPU 0에서 A의 기존 `run_ex39.sh` 경로를 `EX39_SMOKE_UPDATES=2`로 호출한다. 3072 env, 24 step, seed 42, EX-38 m3001 부모와 보상·지각·PPO는 본판과 같다. 출력은 `C:\Users\AI-WS01\s2_lab\basic_gait_runs\ex39a_kit_smoke\<시도 이름>\smoke` 아래다.
2. A 프로세스 종료 뒤 같은 GPU 0에서 B를 같은 방식으로 호출한다. 출력은 `ex39b_kit_smoke` 아래다. 두 판 모두 m3002와 m3003을 끝내고 `model_3003.pt`를 실제로 저장해야 한다. 본판의 m4502 상한은 별도 계획 칸에 유지한다.
3. B 저장본을 새 평가 프로세스에서 `eval_map_modes`의 `eval_pred / fwd0.5 / 8 env / 50 step` 한 칸으로 읽는다. 학습 B 설정으로 실제 command term을 만든 뒤 heading을 강제로 켜고, 고정 평가 명령 직전에 끈다. 매 step 전후 heading 비활성과 살아 있는 env의 명령 세 칸 불변을 확인한다. 정답 지도 사용은 0이어야 한다.

학습 env probe는 실제 reward_manager의 세 신규·기존 자세 term 및 기존 EX-38 네 계수와 lin_vel_z=0을 검사한다. `.*_foot`가 FL/FR/RL/RR 네 link, `.*_(thigh|calf)_joint`가 8 joint로 resolve되고 force tensor가 `(3072,4,3)`이어야 한다. 첫 8 보상 step 중 정지 슬롯의 네 발 접촉 평균이 양수인지 기록한다. 지형 L0~2의 실제 개수 합은 3072여야 한다. A heading은 0, B는 총 약 21%, 전진 슬롯 중 약 50%, 회전 슬롯 중 약 30%이고 전진 heading 목표와 첫 yaw가 맞아야 한다.

학습 저장이 끝난 뒤 명령 term의 RNG만 같은 seed로 초기화해 각 arm에서 명령만 두 번 재추출한다. 이는 물리 step이나 학습 rollout이 아니다. A/B의 두 재추출 slot 배열, B의 비-heading 명령, RNG state SHA가 같아야 한다. 실제 학습 중 reset 시점은 heading 처치로 달라질 수 있으므로 장기 명령 궤적 동일성 증거로 쓰지 않는다.

`ex39_kit_smoke.json`의 `A`, `B`, `paired_commands`, `eval_b`가 모두 PASS여야 전체 PASS다. 실패한 stage는 이유와 자식 코드를 남긴다. 이 스크립트는 본학습을 시작하지 않는다.

## lead가 실행할 한 줄

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' -m foothold_s2.ex39_kit_smoke --worktree-a C:/mai/wt/foothold-lab/scripter-ex39a --worktree-b C:/mai/wt/foothold-lab/scripter-ex39b --out C:/Users/AI-WS01/s2_lab/basic_gait_runs/ex39_kit_smoke_receipts/try01 --execute
```

실행 위치는 `C:/mai/wt/foothold-lab/scripter-ex39a`다. `--execute`를 빼면 CPU 출처 점검만 하고 Kit을 띄우지 않는다. 이미 쓴 `try01`은 재사용하지 않는다. 다음 시도는 `try02`처럼 새 이름을 준다. A/B는 GPU 0에서 직렬 실행해 화면 GPU 1을 점유하지 않는다.

## CPU 증거와 남은 확인

- `isaac311`: 관련 6개 시험 파일 37 PASS. 첫/반복 재추출 3072, 19, 1, 3072 env에서 slot, 비-heading 명령, RNG state가 일치한다. 같은 generator의 clock scatter 순서도 일치한다. 슬롯 조합 밖 `(1.0,0.5,0)`은 거절한다.
- 학습 parser는 실제 AST 선언에 smoke 인자를 넣어 `max_iterations=3004`와 부모 SHA를 확인했다. `pyflakes`는 수정된 순수 모듈 0건, `bash -n`과 `git diff --check` 통과. 기존 평가 스크립트의 오래된 미사용 import 경고는 이번 범위 밖이다.
- 실제 Kit env import, 완료 두 갱신, reward term resolve, 네 발 접촉, 평가 heading 강제 시험은 lead 실행 전이라 미확인이다. D29 처치 직후 300회와 재개 경계 30회 제외는 영수증/manifest 기록까지만 확인됐다. 판정 소비기 연결은 lead의 별도 작업이다.

코드 SHA는 `SHA256SUMS-EX39-kit-smoke.txt`에 있다. 이 보고서는 실행 허가가 아니라 확인 명령과 판독 계약이다.
