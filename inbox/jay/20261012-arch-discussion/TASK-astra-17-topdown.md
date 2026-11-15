> 분류: A/정책학습 · ASTRA 의뢰 17 · Top-down 설계 반박 검증
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 17:24
> 근거: DESIGN-topdown-20261013.md · 팀장 10/13 17시대 지시 둘
> 요지: 팀장 관찰 (student 는 딛은 결과로 지형을 짐작) 을 출발점으로 다시 쓴 실험 사다리와 오늘 밤 GPU 배정이 맞는지 반박 검증해 달라
> 상태: 의뢰

# ASTRA 17 · Top-down 설계 반박 검증

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. lead 의 판단이 옳다고 가정하지 마십시오. 동의할 때도 근거를 대고, 틀린 곳은 틀렸다고 적어 주십시오.

## 읽을 것

1. `inbox/jay/20261012-arch-discussion/DESIGN-topdown-20261013.md` (이번 검증 대상)
2. `inbox/jay/20261012-arch-discussion/PLAN-next-after-astra11.md` · `VERIFY-astra-11.md` · `DESIGN-astra-12-common-eval.md` (당신의 이전 판단)
3. `C:/isaac/ext/go2_rl_robotlab/_eval/UNSEEN-E12.md` (미경험 10 종 결과) · E1 `C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/params/env.yaml`
4. CMD-R 마감 결과: `inbox/jay/20261008-546-design/eval-cmdr-morning/handover-1635/v10/` 의 `cmdr_post.json` 과 #546 댓글 6141124930
5. `C:/isaac/ext/go2_rl_robotlab/_eval/branch/night_20261013_cmdr1043.sh` (오늘 밤 GPU 0 후보)
6. `models/foothold-v2.json`
7. 필요하면 `inbox/jay/20261013-go2-app-study/APP-PLAN-facts.md` (앱 명령 요구)

## 물음

설계 문서 6 절의 일곱 물음에 답해 주십시오. 덧붙여 아래 셋도 봐 주십시오.

- **S2 를 Windows 에서 앞당기는 변경.** 구현 위험을 줄이는 이득과, OS 가 다른 숫자가 섞일 위험 가운데 어느 쪽이 큰지 판단해 주십시오. 섞이지 않게 하려면 무엇을 기록해야 하는지도 적어 주십시오.
- **A/B 학습 분포.** gap · 징검다리를 연습시키면서 「미경험」 주장을 지키려면, 평가 전용 생성기와 치수 범위를 어떻게 잡아야 하는지 제안해 주십시오.
- **오늘 밤 설계가 틀렸을 때.** 아침에 무엇이 남아 있어야 「밤새 GPU 를 돌린 값」 이 있는지 적어 주십시오 (산출물 · 판정 · 버릴 것).

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17.md` 한 파일로만 남겨 주십시오.
- 첫 줄은 한 문장 판정입니다 (그대로 진행 · 고쳐서 진행 · 멈춤 가운데 하나와 이유).
- 표기: 확인됨 (원문 · 기록 직접 대조) · 추정 · 미확인.

## 지킬 것

- 기존 파일 · 코드를 고치지 말고, 학습 · 평가 · GPU 작업을 하지 마십시오.
- `C:/isaac/ext/go2_rl_robotlab/_eval/out` 과 동결 폴더 (`handover_*` · `handover-1635`) 는 읽기만 합니다.
- 커밋 · push 를 하지 마십시오.
- em dash 를 쓰지 마십시오.
