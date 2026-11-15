> 분류: A/정책학습 · Codex Worker(sol) 작업서 · S2 「지도 실험」 학습 연결 2 단계 후보 (CPU 전용 · 학습 기동 아님)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 02:35
> 근거: 팀장 10/15 새벽 「권고대로」 (지도 실험을 1 순위로, 틈 · 징검다리 연습은 그 안에 같이) · `night-tools-20261013/s2/README-s2-step1.md` (특히 3 · 8 절) · `DESIGN-s2-ab-v1.md` 6 절 · `VERIFY-astra-17f2.md` · `VERIFY-astra-17f.md` 5 절 · `VERIFY-astra-17d.md` 6 절 · `s2-terrain-probe/PROBE-sparse-terrain.md`
> 요지: 1 단계(지도 입력 · 정책 · optimizer 통제 · 시험 14 개 · 변이 69 개)는 끝났다. 2 단계는 학습 루프에 붙이는 일이다. 목표는 GPU 에서 짧은 smoke 와 A/B 학습을 ASTRA 허용 아래 띄울 수 있는 CPU 검증 후보를 만드는 것이다. 이 작업서는 기동 허용이 아니다
> 상태: 의뢰 (CPU 전용 · `_eval` 은 읽기만 · GPU · Isaac 실행 금지)

# Codex Worker 작업서 · S2 지도 실험 학습 연결 (2 단계)

## 0. 왜 하는가 (맨 위 목표)

Go2 가 처음 보는 틈과 징검다리를 건너게 하려면 무엇이 필요한지 가린다. 지금 student 는 바닥을 못 보고 걷는다. 이 실험은 「같은 틈 · 징검다리 연습에서, 바닥 높이 지도를 주면 얼마나 달라지나」 를 한 번에 하나만 바꿔 잰다. A 는 지도 입력이 상수(정보 없음), B 는 시뮬 이상적 지도. 팀장은 MoE-CTS 구조 자체가 이 목표에 못 미칠 수 있다고 의심하고 있고, 이 실험의 결과가 「구조를 바꿀지」 를 가르는 첫 근거다. 그래서 빨리 GPU 에 올릴 수 있어야 한다. 팀장 원칙: GPU 는 놀면 안 된다.

## 1. 규칙

- 앞 작업서(`TASK-codex-worker-1043-eval-fix*.md`) 0 절의 규칙을 그대로 따른다: 커밋 금지 · 삭제 금지 · GPU · Isaac 실행 금지 · `CUDA_VISIBLE_DEVICES=-1` · `_eval` 과 `C:/isaac/ext/go2_rl_robotlab/source` 쓰기 금지(읽기만) · 정직한 보고 · em dash 금지.
- **부모 파일(`moe_cts.py` · `on_policy_runner_cts.py` · `actor_critic_moe_cts.py` 등)을 고치지 않는다.** 새 파일로 만든다. 부모의 어느 줄을 따라 하고 어느 줄을 일부러 뺐는지 대응표를 보고서에 둔다.
- 팀장 / ASTRA 결정 값(첫 A/B 의 `encoder_mode` 최종 확정 · W · r · 환경 수 · iteration 수 · 중단 기준 · 지형 비율 최종값)은 **제안으로만** 적고 코드에 고정하지 않는다(인자 필수, 기본값 없음). 1 단계의 「기본값 없음」 규칙 그대로.
- 시험으로 못 재는 것은 미확인으로 적는다. 가짜 환경으로 통과한 것을 실제 Isaac 통과로 쓰지 않는다.
- 변이는 정상 소스에서 같은 시험이 먼저 통과하고 지정한 시험이 의도한 라벨로 실패할 때만 CAUGHT. 입력 변조와 코드 변이를 따로 센다.
- 먼저 `night-tools-20261013/s2/` 의 1 단계 파일을 `codexE/s2_step2/base_step1/` 로 복사하고 `SHA256SUMS.txt` 와 대조한다(불일치면 멈추고 보고). 새 코드는 `codexE/s2_step2/` 에 둔다.
- Codex 주간 한도가 22 % 다. 같은 문서를 되풀이해 읽지 말고, 컨텍스트 압축이 오면 `codexE/HANDOFF.md` 와 이 작업서를 읽고 이어 간다. **중간에 멈추지 말고 끝까지.**

## 2. 만들 것

1. **알고리즘 `s2_ppo.py`:** PPO 손실만 쓰는 S2 갱신. 부모의 teacher / student 나눔(`teacher_env_ratio 0.75`)과 재구성 손실 · 별도 encoder optimizer 를 뺀다. README 3 절의 갱신 규약(`begin_update` → epoch × minibatch 에서 `enforce_groups` 와 clip(`trainable_params`) → `end_update`)을 코드로 옮긴다. adaptive lr 은 부모 줄(moe_cts.py 278~311)과 같은 규칙을 따르되 두 군에 같게.
2. **러너 `s2_runner.py`:** (가) rollout 저장소가 지도(height 187 + mask 187)를 관측 시점 그대로 저장하고 모든 minibatch · bootstrap 에서 같은 시점의 지도를 쓰는지 (나) reset 뒤 이전 episode 지도가 섞이지 않는지 (다) `RunValidityGate` 를 rollout 마다 update 전에 걸고, 지도 · critic · value · return · advantage 유한성 · 고장 횟수 · 폐기량 · 중단 원인을 두 군 모두 기록 (라) update 마다 rollout 길이 · 환경 수 · epoch · minibatch · step 수를 고정하고 기록하며 step 수 == epoch × minibatch 를 확인 (마) 저장 · 재개: 정책 · `ctl.state_dict()` · optimizer · 난수 상태(torch CPU · CUDA · numpy · python) · 환경 설정 해시. 갱신 도중 저장 거절. 다른 규칙으로 재개하면 오류 (바) A 와 B 가 같은 코드 경로를 쓰고 지도 입력만 다름.
3. **지도 공급 `s2_env_adapter.py`:** Isaac 를 import 하지 않는 인터페이스(프로토콜)와, 실제 Isaac Lab RayCaster(`height_scanner` 의 `pos_w` · `ray_hits_w`)를 읽어 `s2_map_obs.height_and_mask` 로 넘기는 얇은 어댑터. 어댑터는 이번에 실행하지 않는다. 훈련 모드에서 `strict=True` 로 거는 자리와, 광선 순서 · yaw 정렬 · 20 m offset 을 다시 더하지 않는 규칙(1 단계 4 절)을 주석이 아니라 시험 가능한 함수로. 실제 Isaac 에서만 확인 가능한 항목은 「Isaac 접속 시험 목록」 으로 따로 적는다.
4. **희소 지형 겹침 `s2_terrain_overlay.py` (또는 설정 파일):** `PROBE-sparse-terrain.md` 의 실제 생성 지형 기하를 읽고 gap · 징검다리를 연습 지형에 넣는 설정 덮어쓰기. 부모 설정 파일은 고치지 않는다. 15 % 배정이 15 % 조우가 아니므로 접근 · 통과 · 회피 · 추락 · 정체 횟수 기록 훅을 같이 만든다(로그 필드 목록). 최종 비율은 제안으로만.
5. **smoke 사전 등록 초안 `S2-SMOKE-PREREG-draft.md`:** README 8.2 의 1 ~ 6 (실행 무결성 · 측정 일정 · 표현 · 행동 진단 · 두 군 공동 규칙 · 전환과 재시작 · 평가 분리) 각각에 대해 「필요한 값 · 제안 · 누가 결정하나(lead 측정 / 팀장 / ASTRA)」 표. 결과를 보기 전에 정해야 하는 값에 별표.
6. **기동 스크립트 초안 `night_s2_smoke_draft.sh` (실행 금지):** 기존 `night_20261013_cmdr1043_v3.sh` · `branch_run.py` · isaac_slot v3 · gpu_guard · usd_isolate 의 연쇄 패턴을 그대로 따르는 초안. 승인 json 관문 · 한 번에 하나만 · 마감 · STOP 파일 자리 포함. 어떤 줄이 어떤 기존 도구의 어떤 검사를 거치는지 표로.

## 3. 시험 (CPU · 가짜 환경)

알려진 답을 손으로 적고 판다: (a) 가짜 환경으로 rollout 을 만들어 지도가 모든 minibatch · bootstrap 에서 보존되는지 (b) reset 격리 (c) A 에서 실제 지형을 바꿔도 정책 입력이 바뀌지 않는지(정보 차단) (d) B 에서는 바뀌는지 (e) 저장 · 재개 비트 동일(난수 포함) (f) 고장 관문이 NaN · 센서 고장 rollout 을 무효로 하는지 (g) step 수 확인 (h) 두 군이 같은 규칙을 쓰는지. 1 단계 시험 14 개와 변이 69 개가 그대로 통과하는지 회귀도 같은 묶음에서. 묶음 실행기 `run_all_s2_step2.py` 와 새 run-id 증거 폴더.

## 4. 보고

`codexE/REPORT-s2-step2.md`: 머리 다섯 줄 · 격리 단언(`_eval` 과 부모 쓰기 0) · 파일 해시 · 부모 줄 대응표 · 항목 1 ~ 6 별 「만든 것 · 시험 이름 · 정상 로그 · 반례 위치 · 변이 want 일치」 · 시험이 못 보는 것(실제 Isaac · RayCaster · GPU · 시간당 iteration · VRAM) · Isaac 접속 시험 목록 · 팀장 / ASTRA 결정이 필요한 값 목록 · **lead 가 바로 ASTRA 에 넘길 수 있게 묻고 싶은 질문 5 개**. 끝나면 `ISSUE-550-s2-step2-comment.md` 짧은 요약. 저장소 사본 · 커밋 · #550 댓글은 lead 가 한다. 완료를 SendMessage 로 알리지 말고 보고서 위치만 마지막 메시지로 적는다.
