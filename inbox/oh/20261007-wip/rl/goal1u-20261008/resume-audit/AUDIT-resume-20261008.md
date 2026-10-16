# 이어학습(resume) 검수 - A(goal1sc)·B(goal1u) - 2026-10-08 학습 mentor (CPU·보존자료만, 새 실행 없음)

질문(현민님, root 경유): ① 300 update 만으로 악화될 수 있나 ② 이어학습 설정을 전 항목 검토했나 ③ 지난 adaptive LR 초기화 수정이 실제 런에 적용됐나.
도구: 기존 venv `Isaac-CV/20-sensor-scratch-20260929/.venv-test`(torch 2.14 cpu, rsl_rl 3.1.2 = Pod 와 같은 버전)를 읽기 전용으로 썼다. 설치·Pod 접속·GPU 는 없었다.
**한계:** 로컬에 S parent `model_3499.pt` 가 없다(Pod 는 Stopped). 그래서 parent↔A/B 가중치를 직접 비교하지 못했다. A/B 는 model_3500·3600·3700·3799 가 로컬에 있다.

## 결론 (직접 증거에 한정, 잘못된 resume 이 원인이라고 확정하지 않음)
1. **LR 보정은 실제 런에 적용됐다.** 근거 셋은 서로 독립이다.
   - 코드: `runner_hooks.py:112` `alg.learning_rate = optimizer.param_groups[0]["lr"]`. 이 파일은 S·T·A·B 사본에서 바이트가 같다.
   - learn() 전에 쓴 `resume_state.json`: `lr 1e-05`. 이 값은 보정 줄 직후의 `alg.learning_rate` 다. 보정이 없었다면 cfg 의 1e-3 이 찍혔을 것이다.
   - 실제 checkpoint: model_3500 의 Adam `step` 은 70020(= parent 70000 + 20)이고 param_group lr 은 5.0625e-5 다.
   - 첫 로그 lr 5.0625e-5 = 1e-5×1.5⁴ 관계는 **단독 증거로 쓰지 않는다.** 1e-3 에서 출발해 하한 1e-5 까지 내려간 뒤 4번 올라가도 같은 값이 나올 수 있다.
2. **옵티마이저와 정책은 복원됐고 6000 step 이 빠짐없이 돌았다.**
   - Adam step: 3500→70020, 3600→72020, 3700→74020, 3799→76000. 76000−70000 = 6000 = 300 it × 5 epoch × 4 minibatch.
   - rsl_rl 3.1.2 `ppo.update` 에는 KL 조기중단이 없다. 그래서 반복마다 정확히 20 step 이다.
   - std 는 init 1.0 으로 재초기화되지 않았다. model_3500 의 std 는 0.7198, S 마지막 로그는 0.7208 이다.
3. **설정은 S 와 같다.**
   - manifest `agent_cfg` 45항, `mix` 34항, `rewards` 18항, `goal_contract` 33항, `obs_dims`, `checks`, `terrain_seed`, `asset sha`: S 대비 차이 0 이다.
   - args 차이는 4개뿐이다: max_iterations 500→300, resume 경로, run_dir, walltime 0.75 h.
   - source_sha256 19/19 가 FREEZE 와 일치한다(A·B 모두).
4. **300 update 로 평가가 크게 바뀌는 것은 크기상 가능하다.** 다만 «악화의 원인»은 이 자료로 확정할 수 없다.
   - 같은 파이프라인의 S 는 r3 에서 500 update 만에 turn_safe 를 13→79% 로 바꿨다.
   - A/B 의 3500→3799 상대 가중치 변화: actor 11.3% / 11.7%, critic 8.9% / 8.8%, std 10.2% / 6.1%.
   - 학습 중 기록에는 resume 지점에서 끊김이 없다. S 때부터 이어진 추세만 보인다(§3 표).
     - action_std: S 0.53 → 0.72 → A 0.76
     - level_mean: 1.43 → 1.29 → A 1.24 / B 1.19
     - base_contact 종료: .008 → .016 → A .022
   - 학습 보상은 유지됐다: S3499 56.149 / A3799 56.275 / B3799 56.576. **학습 보상 유지 ≠ 평가 능력 유지.**
5. **가장 중요한 미검증 항목은 0-update 재현이다.**
   - parent 를 resume 으로 로드한 직후, update 0회에서 같은 동작·같은 평가가 나오는지 측정한 적이 없다.
   - 기존 smoke 5단계는 2 update 라서 이 질문에 답하지 못한다. 평가는 체크포인트 가중치만 읽고 resume 경로를 거치지 않는다. 따라서 S 평가(model_3499)와 A/B 평가(3799) 사이에는 «resume + 300 update» 가 섞여 있고, 둘을 분리하지 못했다.
   - 분리하려면 GPU 측정이 필요하다(새 승인 대상, 아래 §4).

## 1. 방향 검토
| 항목 | 내용 | 판정 |
|---|---|---|
| 질문의 위치 | A 의 큰 하락(turn_safe 79→39)이 «이어학습 자체» 때문인지, «resume 결함» 때문인지 가리는 것. 결과에 따라 다음 설계(이어학습 vs 처음부터·짧은 학습 + 체크포인트 선택)가 달라진다 | - |
| 이미 검증한 범위(사전검토 REVIEW 10-08) | parent sha, `[RESUME]` 줄(next_iter 3500 · lr 1e-5 · level 1.292 · hist), smoke 2 update 유한, 코드 diff. **LR 의 learn 중 경로, Adam step, 0-update 동등성은 검토하지 않았다** | 범위 한정 |
| 300 update 의 크기 | 300 × 4096 env × 24 step = 29,491,200 transition. 300 × 5 × 4 = 6000 optimizer.step(KL 조기중단 없음, Adam step 차로 실측). S 가 r3 에서 바뀐 것은 500 it = 10000 step 이었다 | 큰 변화가 가능한 규모 |
| 이어학습 drift 해석 | 단일 seed 다. drift·seed 변동·resume 효과가 분리되지 않았다 | 미분리 |

## 2. 코드·복원 검토 - 항목별
분류: **복원**(직접 증거) · **정상 재초기화**(S 의 resume 때도 같은 방식) · **복원 안 함**(연속 시뮬과 다름) · **미확인** · **설정 오류**(찾지 못함)

| 항목 | 근거 | 분류 |
|---|---|---|
| actor·critic·terrain encoder 가중치 | rsl_rl `load` → `policy.load_state_dict`. 반환이 참이어야 iter 가 바뀌는데 next_iter 3500 이다. state_dict 모듈은 actor·critic·std 셋(encoder 는 actor 안), 1,119,257 param | 복원(간접). parent 와 직접 대조는 **미측정**(parent 파일 없음) |
| std | model_3500 0.7198, S 마지막 로그 0.7208. init_noise_std 1.0 이 아님 | 복원 |
| Adam moment·step | step 70020 = 70000+20. 25개 state 모두 같은 step | 복원 |
| param_group lr | ckpt 3500 5.0625e-5 | 복원 |
| alg.learning_rate (adaptive 상태) | 보정 코드 + resume_state 1e-5 (learn 전) | 복원(보정 적용) |
| LR 범위 3500–3799 | A: max 5.766e-4 (it 3771), min 1e-5(6 it), 끝 1.709e-4. B: max 8.650e-4 (it 3513), min 1e-5(8 it), 끝 1.709e-4. S 3000–3499: max 8.650e-4 (it 3288), min 1e-5(16 it). 반복 사이 ×3.3 이상 급변 A 73회/300, B 66회/300, S 123회/500 - adaptive 스케줄의 평소 동작으로 S 와 같은 빈도 | 정상(S 범위 안) |
| clip 0.2 · KL 목표 0.01 · epoch 5 · minibatch 4 · γ .99 · λ .95 · entropy .01 · value 1.0 clipped · grad norm 1.0 · 24 step · obs norm False | manifest agent_cfg 45항이 S 와 같음 | 설정 오류 없음 |
| KL 원값·grad norm 원값 | metrics.jsonl 에 없다(loss 는 value_function·surrogate·entropy 뿐) | **측정 못함** |
| 지형 levels | lla_state → `terrain_levels` 복원, `env_origins` 재계산. resume_state level_mean 1.2917, hist [1385,918,1006,787] | 복원 |
| 지형 types | 저장값과 현재 배정이 다르면 RuntimeError 로 막는다(통과) | 일치 확인 |
| 커리큘럼 카운터 k_* 11종 | load_state_dict 가 복원 | 복원 |
| 마찰 mu | 저장은 하지만 load 에서 읽지 않는다. reset 마다 다시 뽑는 값이라 venv.reset() 으로 새로 뽑힌다 | 정상 재초기화 |
| 로봇 물리 상태·접촉·관측 이력 | `venv.reset()` 으로 전 env 리셋 | 복원 안 함(정상 재초기화, S 시작도 같음) |
| episode 길이 | `learn(init_at_random_ep_len=True)` 로 무작위. 첫 50 it 의 time_out .73·보상 41 은 S 시작(3010–3059: .74·44)과 같은 모양 | 정상 재초기화 |
| goal 명령 | reset 때 다시 뽑힌다. class 비율·mix 설정 34항이 S 와 같음 | 정상 재초기화 |
| 랜덤화·seed·RNG | seed 1(S 와 같음). RNG 상태는 저장·복원하지 않는다 → S 의 resume 시작과 같은 난수열로 다시 시작한다. A·B 의 it 3500 첫 로그는 61개 episode 항목 중 60개가 비트까지 같고 overspeed 보상만 다르다 → 초기화가 결정적이다 | 복원 안 함(재시드) |
| rollout storage·rewbuffer | 새로 만든다 | 정상 재초기화 |
| runner iter | +1 보정(3500 부터, model_3499 를 덮지 않음). metrics 3500..3799 300행, 빈칸 0 | 복원(보정 적용) |
| save·log·update hook 실제 호출 | checkpoints.jsonl 기록, 모든 ckpt infos 에 lla_state 존재, metrics 300행 | 호출됨 |
| 동결 source | manifest source_sha256 19/19 = FREEZE | 일치 |
| full physics snapshot | 저장·복원 기능이 없다 | 복원 안 함 |
| **0-update 동등성** | parent 를 resume 경로로 로드한 직후의 동작·평가가 S 평가와 같은지 | **미측정** |
| parent↔model_3500 가중치 차 | parent 파일이 로컬에 없다 | **미측정** |

## 3. 학습 중 추세 (50 it 창 평균, 원물 `train_windows.md`)
S 3450–3499 → A 3750–3799 / B 3750–3799:
- std: .719 → .762 / .753
- level_mean: 1.29 → 1.24 / 1.19
- base_contact: .0157 → .0224 / .0140
- 학습 보상(창 평균): 56.2 → 54.8 / 55.3

curriculum 의 survend 지표(turn·stop·low)는 resume 전후로 계단처럼 바뀌지 않았다. 다만 이 값들의 단위를 이 검수에서 재정의하지 않았으므로 해석은 하지 않는다.
참고: 평가 safe 의 발 조건은 FEET_MIN = 3 이다. 그래서 «한 발 들기 = safe 실패»가 아니다. turn_safe 하락을 RR 들기와 바로 연결하지 않는다.

## 4. 분리하려면 (GPU 필요 - 새 승인 대상, 자동 착수 없음)
- (a) parent 를 resume 경로로 로드하고 0 update 로 저장한 checkpoint 를 v2 평가해서 S 평가와 비교한다.
- (b) model_3500·3600·3700 을 v2 평가해서 하락이 언제 생겼는지 본다(체크포인트는 보존돼 있다).
- (c) seed 를 바꿔 A 를 반복해 drift 와 seed 변동을 분리한다.

## 원물
- 이 폴더: `ckpt_audit.py` · `ckpt_audit.out.txt` · `train_windows.md`
- `logs/pod/goal1u-results-20261008/{goal1sc,goal1u}-20261008-s1/train/` (metrics.jsonl · manifest.json · resume_state.json · model_*.pt)
- `logs/pod/goal1s-20261007-s1/train/` (metrics.jsonl · manifest.json)
- rsl_rl 원본: `.venv-test/lib/python3.12/site-packages/rsl_rl/runners/on_policy_runner.py:62-176,291-326` · `algorithms/ppo.py` (update 194행~, adaptive LR 280–292행, grad clip·optimizer.step 376–377행)
