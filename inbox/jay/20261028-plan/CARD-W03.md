# 실행 카드 W03 · 세 정본 같은 조건 평가 · 촬영 · manifest

> 분류: 실행 카드
> 작성: lead · 2026-10-28 02:2x (팀장 01:4x 「3번 진행」)
> 근거: `WORKLIST.md` W03 · `20261027-experiments/CARD-EVAL-FLAG-BASELINE.md` 3 · 5 절(정본 경로 · manifest 칸) · `impl-turncases/logs/{sb10_eval,ex35_eval,map_err_main_x27n}/`
> 요지: B1500 · S-B10 m1500 · EX-35 m2000 셋을 같은 평가 코드 · 같은 GPU · 같은 시드로 다시 재서 한 표에 놓는다. 이미 있는 값이라도 코드 head 가 다르면 다시 잰다. 학습은 하지 않는다
> 상태: 의뢰 · 평가 · 촬영은 빈 GPU 라 승인 불필요 · 새 학습 금지

## 범위

- 정본(이 순서로): B1500 → S-B10 m1500(sha 4d987818) → EX-35 m2000(sha eba0fbdd, 정본 아님 · 팀장 검토 전). 경로는 CARD-EVAL-FLAG-BASELINE 3 절.
- 평가 묶음: S-B10 · EX-35 에 이미 돌린 묶음 그대로.
  - turn16 (16 env, 지도 eval_gt · eval_pred · probe_prop_only, 회전 여섯 경우 + 걸으며 돌기)
  - map64 (64 env, 같은 세 지도 모드, fwd0.5 · fwd1.0 · 제자리 회전 · 걸으며 돌기)
  - 연속 7 종 × L0~2 · L3 · L6 · L9 (X27n 식, 복원 오차 칸 포함)
  - 듬성 5 종 × L0 (sparse50)
- 흔들림 폭: turn16 · map64 를 정본마다 두 번 재서 같은 칸의 차이를 같이 적는다.
- 촬영(GPU1, 평가와 겹치지 않게): 정본마다 (연속 7 + 듬성 5) × 레벨(L0~2 · L3 · L6 · L9, 듬성은 L0 부터) × eval_gt, fwd1.0 18 s. 고르는 규칙은 결과 전에 고정: 각 (종류, 레벨) 에서 성공 env 중 가장 작은 번호 1 · 실패 env 중 가장 작은 번호 1. B1500 부터.
- 기록기는 lead 사본 `runner-26a/.../record_25e_x27.py`(hide_others · walk_turn 포함)를 쓴다. 합성은 W07 에서 v8 로 하므로 여기서는 촬영만.

## R (끝 보고에 R 마다 근거 경로)

- [ ] R03-1 세 정본 × 평가 묶음 전 칸 결과 파일 · rc 0 · 같은 코드 head · GPU · 시드(run_identity)
- [ ] R03-2 turn16 · map64 두 번 측정의 칸별 차이 표
- [ ] R03-3 세 정본 나란히 놓은 표(md + json), 생성 스크립트가 원자료에서 만든 것(손 숫자 0)
- [ ] R03-4 manifest 정본마다 하나(CARD-EVAL-FLAG-BASELINE 5 절 칸 전부, 빈 칸 0)
- [ ] R03-5 촬영 목록(고르는 규칙 · env 번호 · 판정 성분) 과 촬영본 전부의 review.done
- [ ] R03-6 촬영본 전 프레임 검사(검정 · 정지 · 대상 로봇 한 대)
- [ ] R03-7 GPU 가 논 구간과 이유
- [x] R03-8 (03:34 끝 · `impl-turncases/logs/w03_noise_off/r0308_compare.md` · 끔 3 회 폭 최대 0.044 대 켬 2 회 0.027 → 흔들림의 주 원인은 잡음 아님. 그러나 끔(cuda:1) 회전 Q 수준이 켬(cuda:0)보다 크게 낮음: right_then_left 0.26 대 0.86) (02:37 추가 · GPU1 · 촬영 전) 관측 잡음 끔 반복: S-B10 m1500 한 저장본을 turn16 eval_gt 를 잡음 끔(enable_corruption = False)으로 3 회. 잡음 켬 반복 폭(Q 0.100 · kept 3)과 견줘 흔들림 중 잡음 몫을 잰다(GATE-v3 §10 결정 8, 약 15 분 가정). 평가 코드 사본에서만 바꾸고 W03 본 묶음은 잡음 켬 그대로

- [ ] R03-9 (03:35 추가) 잡음 켬 · cuda:1 turn16 eval_gt 1 회로 R03-8 의 수준 차가 잡음 때문인지 GPU 때문인지 가름

## 지킬 것

- Codex 세션에 넘기지 않는다. 새 학습을 띄우지 않는다. 남의 프로세스를 끄지 않는다(필요하면 lead 에 묻는다).
- 판정 규칙 · 문턱은 바꾸지 않는다(GATE 는 W05 에서 따로).
