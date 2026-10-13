> 분류: A/정책학습 · S2 「이상적 지도 입력 비교」 A/B 입력 경로 1 단계 판 3 · 코드와 CPU 시험 (학습 · Isaac · GPU 실행 없음)
> 작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 판 1 2026-10-13 19:35 · 판 2 2026-10-13 23:47 · 판 3 2026-10-14 01:10
> 근거: foothold-lab `inbox/jay/20261012-arch-discussion/VERIFY-astra-17f2.md` 2.1 · 3.1 · 3.2 · 4 · 5.1 · 5.3 · `VERIFY-astra-17f.md` 5 절 · `DESIGN-s2-ab-v1.md` 6 절 (위 1 ~ 5 절과 다르면 6 절) · `VERIFY-astra-17d.md` 6.1 ~ 6.4 · `source/rsl_rl/rsl_rl/algorithms/moe_cts.py` 93 ~ 101 · 278 ~ 311 · 365 ~ 366 · 411 · `runners/on_policy_runner_cts.py` 108 · 140 · 173 · 278 · E1 `params/agent.yaml` · `params/env.yaml` · IsaacLab (판 2 와 같음)
> 요지: ASTRA 17f-2 반영. student encoder 고정을 `encoder_mode` (기본값 없음) 로 나눠 `full_freeze` 는 requires_grad False · optimizer 에 없음 · 어떤 번호에서도 안 풀림으로 하고, `schedule` 은 r 0 을 받지 않는다. S2 갱신 번호를 control 이 0 부터 세며 부모 20000 · runner 번호를 거절하고 저장 · 재개를 둔다. adaptive lr 덮어쓰기 뒤 `enforce_groups` 가 group lr 을 다시 맞추고 고정 상태를 확인하며 step 전 hook 이 그 호출을 강제한다. clipping 은 `trainable_params`. 시험 T1 ~ T14 는 14/14 PASS (292 칸) · 변이 68 개 + 관문 자체 1 개 ALL CAUGHT 69/69 (1 차 68/69 · q28 놓침 · 시험을 고친 뒤)
> 상태: CPU 시험 · 변이까지. S2 학습 기동은 보류. 학습 루프 연결 · smoke 사전 등록 (17f-2 5.3 의 1 ~ 6) · 17f 의 센서 · 학습 연결 관문은 하지 않았다 (8 절)

# S2 A/B 입력 경로 1 단계 · 판 3

표기: **확인됨** = 이 폴더의 시험을 돌려 잼 · **소스 확인** = 코드를 열어 읽음 (실행은 안 함) · **미확인** = 재지 않음.

## 1. 판 2 에서 바뀐 것 (판 3)

| 판 2 (2026-10-13 23:47 · ASTRA 17f-2 가 검토한 판) | 판 3 | 까닭 (17f-2 절) |
|---|---|---|
| `EncoderSchedule(W, r)` 하나. 전 구간 고정을 하려면 W 를 크게 두거나 W 뒤 r 0 | **`encoder_mode` 를 기본값 없이 받는다.** `full_freeze`: student encoder 의 requires_grad False · optimizer 에 아예 넣지 않음 · `is_frozen` 이 어떤 번호에서도 True · W · r 을 넘기면 TypeError. `schedule`: 판 2 의 W · r 규칙 (둘 다 필수) | 3.1 「별도 full-freeze 상태를 두는 편이 명확」 · 4 절 첫 A/B 는 전 구간 고정 |
| r 0 을 받음 (W 뒤 requires_grad True · lr 만 0) | **`schedule` 은 r > 0 만 받는다** (r 0 은 ValueError · 끝까지 고정은 `full_freeze`) | 3.1: r 0 은 gradient 가 계산되어 clip norm 에 섞이고 Adam 상태가 진행된다 |
| update 번호를 학습기가 넘기고 control 은 그 수만 셈. 단위 미등록 | **S2 갱신 번호를 control 이 센다.** `begin_update(k, base_lr)` 는 `k == 완료 수` 일 때만 받는다 (부모 iter 20000 · 부모를 읽은 runner 의 `current_learning_iteration` · 재개한 runner 의 되돌아간 번호 · 건너뜀 · 되풀이 · bool · float · tensor 는 오류). 단위는 `ppo_iteration` (rollout 한 번 뒤 PPO update 한 번) 으로 적어 저장한다. 고정 상태는 `begin_update` 에서만 바뀐다 (그 update 의 첫 minibatch 전) | 2.1 등록 정의 |
| 저장 · 재개 없음 | **`state_dict()` / `load_state_dict()`**: 완료 갱신 수 · 다음 번호 · optimizer 상태 (깊은 복사) · base lr · group lr · 규칙 (mode · W · r) · 누적 step 수. 갱신 도중 저장은 거절. 다른 규칙으로 읽으면 ValueError (다른 실험) | 2.1 「중단 · 재개 시 ... 보존」 |
| `apply()` 주석이 「adaptive lr 이 바뀔 때마다 다시 부르라」 고만 적음 | **`enforce_groups(optimizer, base_lr)`**: group lr 을 규칙대로 다시 쓰고 (encoder 묶음 0 또는 r x base · 나머지 base) 고정 상태 (requires_grad · grad None · Adam 상태 없음 · optimizer 구성) 를 확인해 어긋나면 `S2ControlError`. 그리고 **optimizer step 전 hook** 이 step 마다 enforce 가 불렸고 그 뒤 바뀐 것이 없는지 다시 본다 | 3.2 「주석이 실제 호출을 보장하지는 않는다」 |
| 시험이 `clip_grad_norm_(pol.parameters())` | **`trainable_params(policy)`** (requires_grad 켜진 것만) 로 clip | 3.1 반례 (actor 3 · encoder 4 · 한도 1) |
| T9 가 「encoder 매개변수 비트 불변」 으로 고정을 봄 | **T11**: 가중치 바이트 sha256 · 고정 입력 latent 비트 · step 마다 grad None · Adam 상태 없음 · optimizer 에 없음을 함께 보고, 판 2 의 r 0 꼴이 delta 0 인데도 이 칸들에 걸리는 반례를 같은 시험에 둔다 | 3.1 마지막 문단 · 5.3 의 1 |

판 2 의 파일 일곱 개 (코드 · 시험 · 변이 · README · 기록) 는 `v2/` 에 그대로 두었다. 저장소 사본 `inbox/jay/20261012-arch-discussion/night-tools-20261013/s2/SHA256SUMS.txt` 다섯 줄과 `v2/` 의 sha256 이 모두 같다 (`sha256sum -c` OK 5/5). 판 1 은 `v1/` 그대로.

`s2_map_obs.py` 는 판 2 와 같다 (sha256 `cf055286…961f348b`). 지도 입력 의미 (4 절) 는 바뀌지 않았다.

## 2. 파일

| 파일 | 행 | 하는 일 |
|---|---|---|
| `s2_map_obs.py` | 192 | 판 2 그대로. `classify_rays` · `height_and_mask` · `map_obs` · `MapFaults` · `MapObsFault` · `RunValidityGate` |
| `s2_policy.py` | 630 | E1 20000 CPU strict 적재 · `S2MapActorCritic` · **`EncoderControl`** (mode · 번호 · `begin_update` · `enforce_groups` · step 전 hook · `end_update` · `audit` · `state_dict` · `load_state_dict`) · **`trainable_params`** · `make_optimizer` (encoder_mode 필수) · `critic_check` · 오류 형 `S2ControlError` · `S2IndexError` |
| `test_s2.py` | 1289 | T1 ~ T14. 기대값은 손으로. T7 은 맨 마지막 |
| `mutate_s2.py` | 316 | 변이 68 개 + 관문 자체 1 개. 바꿀 문자열이 원본에 정확히 한 번 있는지 먼저 본다. 임시 사본 폴더의 부모는 `S2_MUT_TMPDIR` |
| `test_s2.log` · `mutate_s2.log` | | 마지막 실행 기록 |
| `v1/` · `v2/` | | 판 1 · 판 2 사본 (고치지 않음 · import 하지 않음) |

```
cd C:/isaac/ext/go2_rl_robotlab/_eval/s2
CUDA_VISIBLE_DEVICES=-1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I test_s2.py      # 약 7 초
CUDA_VISIBLE_DEVICES=-1 S2_MUT_TMPDIR=<임시 폴더> C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I mutate_s2.py    # 약 9 분 (사본 70 번)
```

## 3. 학습기에 붙일 때의 규약 (판 3 · 아직 붙이지 않음)

```
opt, ctl = make_optimizer(policy, lr0, encoder_mode="full_freeze")      # 또는 "schedule", encoder_freeze_updates=W, encoder_lr_ratio=r
# 재개라면: policy.load_state_dict(저장 정책) · make_optimizer(같은 규칙) · ctl.load_state_dict(저장 control) · lr = ctl.base_lr
for k in range(ctl.next_update_index, 끝):      # k = S2 지역 번호. runner 의 it · 부모 iter 를 쓰지 않는다
    rollout 수집
    frozen = ctl.begin_update(k, lr)              # 첫 minibatch 전 · 고정 상태를 바꾸는 유일한 자리
    for 각 epoch · minibatch:
        forward · KL · lr = adaptive(lr)          # 부모 꼴이면 모든 group lr 을 lr 로 덮어씀 (moe_cts.py 310 ~ 311)
        optimizer.zero_grad() · loss.backward()
        clip_grad_norm_(trainable_params(policy), max_grad_norm)
        ctl.enforce_groups(opt, lr)               # group lr 다시 맞춤 · 고정 상태 확인 · 어긋나면 S2ControlError
        opt.step()                                # step 전 hook: enforce 없이 · enforce 뒤 바뀐 step 은 S2ControlError
    ctl.end_update(k)                             # optimizer step 이 0 번이면 S2ControlError
    저장할 때: {"policy": policy.state_dict(), "s2_control": ctl.state_dict()}   # 갱신 사이에서만
```

`enforce_groups` 는 lr 만 고치고 고정 상태는 고치지 않는다. 이 자리에서는 forward · backward 가 이미 지나가 requires_grad 를 바꿔도 늦기 때문이다. 고정 상태가 어긋나 있으면 멈춘다.

## 4. 지도 입력의 의미 (판 2 그대로 · 확인됨)

| 광선 | height | mask | 고장 |
|---|---|---|---|
| 센서 정상 · hit xyz 유한 | clip(센서 z − hit z − 0.5, −1, 1) | 1 | 아님 |
| 센서 정상 · hit xyz 모두 +inf (raycast_mesh 의 안 맞음) | 1 | 0 | 아님 (정상 miss) |
| 센서 정상 · hit 에 NaN · −inf · 일부 좌표만 inf | 0 (자리표시) | 0 | ray packet 고장 |
| 센서 위치에 NaN · inf | 0 (그 env 의 187 칸 모두) | 0 | 센서 고장 (env 하나로 셈 · packet 쪽에 두 번 세지 않음) |

자세한 것은 판 2 README (`v2/README-s2-step1.md` 3 절) 와 같다. 「센서 z」 는 RayCaster `data.pos_w` 의 z 이고 offset (0, 0, 20) 은 `ray_starts` 에만 더해진다.

## 5. 시험 T1 ~ T14 (확인됨 · 14/14 PASS · 292 칸 · 약 7 초)

T1 ~ T8 · T10 은 판 2 와 같은 기대값이다 (T5 · T7 은 판 3 API 로 부르는 줄만 바뀜: `begin_update` · `enforce_groups` · `end_update` · `trainable_params`). 칸 수와 손으로 적은 기대값은 판 2 README 4 절과 같다.

| 시험 | 칸 | 판 3 에서 보는 것 |
|---|---|---|
| T1 · T2 · T3 · T4 · T5 · T6 · T8 · T10 | 11 · 9 · 27 · 18 · 27 · 9 · 31 · 12 | 판 2 와 같음 |
| T9 schedule | 34 | 판 2 의 고정 구간 시험을 판 3 API 로. W · r 기본값은 「안 넘김」 표시뿐 · schedule 에 W · r 없으면 TypeError · None TypeError · 음수 · 정수 아님 · bool · NaN · inf ValueError · **r 0 ValueError** · 인자 오류는 정책을 건드리기 전에 남. W 3 · r 0.25 (시험 값): update 0 ~ 2 고정 · 3 부터 encoder lr 4.271484375000002e-05 (손 계산) · 첫 encoder 걸음 r x lr 이하 · encoder Adam step 1 · actor 4 |
| T11 full_freeze | 31 | 아래 |
| T12 S2 갱신 번호 · 재개 | 37 | 아래 |
| T13 group lr · hook | 25 | 아래 |
| T14 clipping | 9 | 아래 |
| T7 부모 보존 (맨 마지막) | 12 | 체크포인트 sha256 `c8951b79…f47e8` 시험 전 · 후 같음 |

**T11 (full_freeze):** `make_optimizer` · `EncoderControl` 의 `encoder_mode` 기본값 없음 · 없이 부르면 TypeError · 모르는 mode ValueError · full_freeze 에 W · r (50 · 0.1 · 둘 다 · None · 0.0) 을 넘기면 TypeError. optimizer group 이 `map_encoder · actor · critic · std` (student_encoder 없음) · encoder 16 매개변수 중 optimizer 에 든 것 0 · encoder 밖 매개변수는 모두 한 번씩. `is_frozen` 이 0 · 1 · 49 · 50 · 51 · 1999 · 2000 · 20000 · 10⁹ 모두 True. 시작 latent 가 부모 student encoder latent 와 비트 동일 · 시작 encoder 가중치 바이트가 파일과 같음. 부모 꼴 adaptive lr · 모든 group 덮어쓰기를 넣은 update 3 번 (step 12 번) 동안 step 마다 encoder grad None · requires_grad False · Adam 상태 없음 · 묶음 없음. 뒤에 encoder 가중치 바이트 sha256 그대로 · 고정 입력 latent 비트 동일 · optimizer state 항목 수 == encoder 밖 매개변수 수 · Adam step 12 · actor · map encoder · critic · std 는 움직임 · lr 이 실제로 바뀜 (덮어쓰기 길이 돌았음). **반례:** 판 2 의 「W 뒤 r 0」 꼴 (encoder 가 optimizer 에 lr 0 · requires_grad True · 전체 clip) 을 같은 횟수 돌리면 encoder 가중치 바이트는 그대로지만 (delta 0 만 보면 통과) encoder grad 가 계산되고 Adam step 이 12 로 진행된다. 이 반례가 위 칸들에서 걸린다는 것을 시험이 직접 확인한다. 시험 밖 일회 확인 (판 3 작업 중 · 스크립트는 작업 임시 폴더 · 시험 파일에 없음): `v2/s2_policy.py` 원본의 `make_optimizer(W 1, r 0)` 으로 3 update 를 돌리면 update 1 부터 encoder requires_grad True · grad norm 약 25 · Adam 상태 16/16 · 가중치 그대로였다 (17f-2 3.1 의 정적 지적을 판 2 코드로 잼).

**T12 (S2 갱신 번호 · 재개):** runner 번호 규칙을 소스에서 대조 (`start_it = self.current_learning_iteration` · 끝난 it 를 적음 · 저장 iter · 재개 때 저장 iter 로). 새 control 에 `begin_update(20000)` · 부모를 읽은 runner 의 번호 (20000) · 첫 번호 1 은 `S2IndexError` · False · 0.0 · tensor 는 TypeError · 거절된 호출은 상태를 안 바꿈. update 도중 다시 시작 · 저장 · 다른 번호로 끝냄은 `S2IndexError` · step 없이 끝내면 `S2ControlError`. W 50 이면 0 · 1 · 48 · 49 고정 · 50 · 51 · 1999 해제. **재개 (full_freeze · schedule W 3 · r 0.25 각각):** 끊김 없는 5 update (step 20) 와 「2 update 뒤 저장 (저장 dict 를 메모리에 둔 채 원래 학습을 이어 감) · torch.save · torch.load(weights_only=True) · 새 정책에 읽고 make_optimizer · load_state_dict · 3 update」 를 견준다. 재개 직후 다음 번호 2 · lr 이 저장 값 · runner 가 되돌린 번호 1 · W 를 다시 시작하는 0 · 건너뛴 3 은 `S2IndexError`. 끝에서 정책 매개변수 · optimizer 상태 (step · exp_avg · exp_avg_sq) 가 비트 동일 · group lr · base lr · 완료 수 5 · step 20 같음. schedule 은 저장 때 encoder Adam 상태 없음 · update 2 의 모든 minibatch 고정 · **update 3 의 첫 minibatch 부터 해제** (grad 있음 · requires_grad True · encoder lr = 0.25 x base) · 첫 minibatch 고정 [T T T F F] · encoder Adam step 8. 다른 규칙 (full_freeze 저장을 schedule 에 · W 3 저장을 W 4 에) 으로 읽으면 ValueError · 다음 번호 != 완료 수 인 저장 ValueError.

**T13 (group lr 덮어쓰기 · hook):** 부모 `moe_cts.py` 에서 「모든 param group 에 같은 lr」 · adaptive 규칙 (1.5 배 · 상하한) · clip 줄을 정규식으로 찾아 시험의 흉내와 같은지 본다. schedule W 1 · r 0.1: 고정 중 부모 꼴 덮어쓰기가 encoder lr 을 0 에서 base 로 바꾸고 `audit` 이 그 하나를 잡음 · `enforce_groups` 가 0 으로 되돌림 (`{"student_encoder": (base, 0.0)}`). 해제 뒤 adaptive lr 1.5 배 (0.0002562890625000001 · 손 계산) 와 덮어쓰기 뒤 encoder 2.5628906250000014e-05 (= 0.1 x 0.0002562890625000001 · 손 계산) · 나머지 0.0002562890625000001. enforce 뒤 덮어쓰기 · enforce 없는 연속 step · update 밖 step · update 밖 enforce 는 `S2ControlError` · 막힌 step 은 세지 않음. full_freeze: 덮어쓰기가 encoder 에 닿지 않음 (고칠 것 없음). **위반 다섯을 하나씩 주입:** encoder 매개변수를 actor 묶음에 끼움 · encoder requires_grad True · 고정 encoder 에 남은 grad · encoder 의 Adam 상태 · encoder 밖 매개변수 requires_grad False. 각각 `audit` 문제가 정확히 1 개이고 `enforce_groups` 가 예외. base_lr NaN · inf · 0 · 음수 ValueError · bool · tensor TypeError (group lr 안 바뀜) · 묶이지 않은 optimizer (같은 묶음 · 같은 lr 로 만든 쌍둥이라 audit 은 통과하는 꼴 · 묶음이 다른 것) 예외 · 되돌린 뒤 통과 (관문이 늘 예외인 것이 아님).

**T14 (clipping):** full_freeze 의 `trainable_params` 에 encoder 없음 (전체 − 16) · optimizer 매개변수와 같음 · 실제 역전파에서 encoder grad None · clip norm 이 encoder 밖 손 계산 norm 과 같음 (상대 1e-5). **17f-2 3.1 반례를 숫자로:** encoder 밖 grad norm 3 · encoder 4 · 한도 1 에서 판 2 방식 (encoder requires_grad True · `pol.parameters()` 로 clip) 은 전체 norm 5 · clip 뒤 encoder 밖 **0.600001**, 판 3 방식 (full_freeze · `trainable_params`) 은 clip norm 3 · encoder 밖 **1.000000** · 남은 encoder grad (norm 4) 는 안 건드림 · encoder grad None 일 때도 1. 실제 역전파 한 minibatch: r 0 꼴은 encoder norm 6.0e+01 이 생겨 clip 전체 norm 이 커지고 (encoder 밖 norm 2.0e+02 는 두 꼴이 같음), 한도 1 에서 encoder 밖 배율이 판 2 0.0047 · 판 3 0.0049. 이것은 gradient 계산이며 학습 결과가 아니다 (17f-2 3.1 의 단서 그대로 · Adam 정규화가 있어 파라미터 이동 비율로 옮기지 않는다).

## 6. 변이 (확인됨 · ALL CAUGHT 69/69)

변이 없는 사본이 먼저 14/14 PASS 인지 보고 (BASELINE), 원본 세 파일 sha256 을 시작 · 끝에 대조했다 (같음 · 복구 확인 줄 「원본 sha256 시작 == 끝: True」). 실제 FAIL 과 사유는 `mutate_s2.log` (변이 68 개 + 관문 자체 1 개 · 약 9 분).

**경과 (숨기지 않음):** 1 차 실행은 68/69 였다. q28 (「묶인 optimizer 인가」 확인을 뺌) 을 놓쳤다. T13 이 넘긴 남의 optimizer 가 묶음 구성이 달라 `audit` 이 먼저 거절했기 때문에, 그 확인이 실제로 가르는 칸이 없었다. 같은 묶음 · 같은 lr 로 만든 쌍둥이 optimizer (audit 은 통과하는 꼴) 를 넘기는 칸을 더하고 다시 돌려 69/69 가 되었다. 또 판 2 의 사유 추출이 시험 제목 속 「: 」 에서 잘려 제목만 보였으므로, 「k/n 칸 실패」 나 예외 부분을 꺼내도록 고친 뒤 한 번 더 돌렸다 (69/69 · 이 기록이 `mutate_s2.log`).

**잡힌 방식 (판 3 변이 · 기대 시험의 사유):** 칸 실패로 잡힌 것: p02 · p04 · q03 · q04 · q05 · q07 · q10 · q11 · q24 · q25 · q30 · q14 · q15 · q16 · q17 · q18 · q27 · q28 · q29 · q20 · q21. 코드 안의 다른 관문이 예외를 내서 잡힌 것: p03 · p05 · q01 (만들 때 audit) · q06 · q08 · q12 · q23 · q26 (번호 · 진행 상태 검사) · q09 (재개 직후 group lr 대조) · q13 · q22 (step 전 hook) · q19 (step 이 세어지지 않아 end_update 예외). p01 은 T9 시험 코드의 `opt.state[p]["step"]` 에서 KeyError 로 잡혔다 (해제가 늦어 encoder Adam 상태가 없음 · T12 · T13 도 FAIL).

| 묶음 | id | 망가뜨린 것 | 기대 시험 |
|---|---|---|---|
| 판 1 · 판 2 지도 · 정책 | m01 ~ m20 · m14b · n01 ~ n10 · p06 ~ p08 | 판 2 README 5 절과 같음 (바꿀 문자열 그대로) | T1 · T2 · T3 · T4 · T5 · T6 · T7 · T8 · T10 |
| 판 2 고정 구간 (판 3 문자열) | p01 · p02 · p03 · p04 · p05 | 고정 구간 하나 더 김 · r 안 곱함 · requires_grad 안 끔 (lr 0 으로만 고정 · full_freeze 도 같은 줄) · W · r 기본값 · 만들 때 규칙 안 걺 | T9 |
| 전 구간 고정 | q01 · q03 · q04 · q05 | full_freeze 가 encoder 를 optimizer 에 넣음 · 번호 50 에서 풀림 · W · r 을 말없이 받음 · encoder_mode 기본값 | T11 |
| S2 갱신 번호 · 재개 | q06 · q07 · q08 · q09 · q10 · q11 · q12 · q23 · q24 · q25 · q26 · q30 | 다음 번호 검사 뺌 · 상태 변경 한 update 늦음 · 완료 수 안 셈 · 재개 때 optimizer 상태 · lr · 완료 수 안 되돌림 · 다른 규칙 받음 · step 없는 update 를 완료로 · 도중 저장 · 겹친 시작 · 번호 형 검사 뺌 · 저장이 깊은 복사 아님 | T12 |
| group lr · 고정 확인 · hook | q13 · q14 · q15 · q16 · q17 · q18 · q19 · q22 · q27 · q28 · q29 | enforce 가 lr 을 안 고침 · grad None · optimizer 소속 · requires_grad · Adam 상태 · group lr 확인을 하나씩 뺌 · hook 안 걺 · base_lr 검사 뺌 · enforce 한 번이 뒤 step 을 다 통과 · 다른 optimizer 받음 · encoder 밖 requires_grad 확인 뺌 | T13 |
| clipping · r 0 | q20 · q21 | trainable_params 가 encoder 까지 · schedule 이 r 0 을 받음 | T14 · T9 |
| 관문 자체 | g01 | T7 sha256 기대값만 틀리게 (파일은 안 건드림) | T7 |

q02 는 없다 (full_freeze 의 requires_grad 를 켜는 변이는 p03 과 같은 줄이라 p03 하나로 둔다).

## 7. 설계와 다르게 한 곳 · 해석한 곳

판 2 의 1 ~ 4 · 7 항 (actor 첫 층 두 장 · A 상수 관문 · 정상 miss 표현 · 고장 자리표시 · RunValidityGate 입력) 은 그대로다. 판 3 에서 더한 해석:

1. **`schedule` 에서 r 0 을 거절한다.** 의뢰문은 「W · r 은 schedule 에서만」 이라고 했고 r 0 금지는 적지 않았다. 17f-2 3.1 이 r 0 을 실제 고정이 아니라고 했으므로 받지 않게 했다. W 0 · r > 0 (고정 없음) 은 받는다 (T5 · T7 이 W 0 · r 1 을 쓴다 · 등록 값 아님).
2. **step 전 hook 을 더했다.** 의뢰문은 `enforce_groups` 한 함수만 요구했다. 함수만 두면 학습기가 부르지 않아도 모르므로 (17f-2 3.2 의 「주석이 호출을 보장하지 않는다」), optimizer 에 step 전 hook 을 걸어 step 마다 enforce 가 앞에 있었는지와 그 뒤 바뀐 것이 없는지를 본다. 결과로 이 optimizer 는 `begin_update ~ end_update` 밖에서 step 할 수 없다.
3. **`enforce_groups` 는 lr 만 고치고 고정 상태는 확인만 한다** (3 절 끝 문단). 「다시 맞추고 확인」 을 이렇게 나눴다.
4. **step 없는 update 를 끝내면 오류.** 17f-2 2.1 「갱신 생략 여부를 고정」 을 「생략 금지」 로 좁혔다. update 마다 step 이 epoch x minibatch 수와 같은지는 보지 않는다 (8 절).
5. **번호의 「부모 20000 · runner 번호 거절」 은 「다음 번호와 같아야 함」 하나로 한다.** 값만으로는 출처를 가릴 수 없다. 새 runner (부모를 읽지 않음) 의 it 0, 1, 2 … 는 S2 번호와 우연히 같아 받아진다. 부모를 읽은 runner (20000) 와 재개한 runner (마지막 완료 번호로 되돌아감) 는 걸린다.
6. **재개 저장에 난수 상태가 없다.** 17f-2 2.1 은 난수 상태 보존도 적었다. CPU 시험으로 CUDA · Isaac 환경 난수를 잴 수 없어 넣지 않았다 (8 절).
7. **schedule 에서 풀린 encoder 는 actor 와 같은 clip 묶음에 든다** (`trainable_params`). 부모는 encoder 를 따로 clip 했다 (`moe_cts.py` 411). schedule 을 쓸 때 등록할 선택이다 (첫 A/B 는 full_freeze 라 해당 없음).
8. **시험의 update 는 epoch 2 x minibatch 2 = 4 step** (E1 은 5 x 4 = 20). 번호 · 재개 · 덮어쓰기 경로를 보는 시험 값이다.
9. **시험 값 W 3 · r 0.25 · W 1 · r 0.1 은 등록 값이 아니다.** W 50 은 `is_frozen` 의 경계 (49 / 50) 만 본다.
10. 판 2 시험 머리의 「PPO 손실 297 ~ 334」 를 실제 줄 313 ~ 335 로 고쳤다.

## 8. 아직 안 된 것 (빠짐없이)

### 8.1 학습 루프 연결 (하나도 안 됨)

- S2 알고리즘 · runner 를 짓지 않았다. 부모 `MoECTS.update` 의 teacher · student 나눔 (`teacher_env_ratio` 0.75) · 두 번째 loop 의 student encoder 재구성 손실 · 별도 encoder optimizer 를 빼야 한다. 3 절 규약은 시험 흉내 (`s2_update`) 로만 돌았다.
- 지도 입력이 관측 시점과 함께 rollout 저장소 · 모든 minibatch · bootstrap 에 보존되는지, reset 뒤 이전 episode 지도가 섞이지 않는지 (17f 5 절). 미확인.
- `RunValidityGate` 를 rollout 마다 update 전에 거는 자리 · 지도 · critic · value · return · advantage 를 실제로 넣는 연결 · 고장 횟수 · 폐기량 · 중단 원인을 두 군 모두 기록. 미구현. `height_and_mask` · `map_obs` 의 기본값은 여전히 `strict=False`.
- runner 저장 · 재개에 `ctl.state_dict()` 를 함께 넣는 연결. CPU 에서 control · 정책 · optimizer 의 재개 동치만 확인했다.
- 난수 상태 (torch CPU · CUDA · numpy · python · Isaac 환경) 저장 · 복원. 미구현.
- update 마다 rollout 길이 · 환경 수 · epoch · minibatch · gradient accumulation 을 고정하고 기록하는 것. control 은 누적 step 수와 「step 0 번 금지」 만 본다. step 수 == epoch x minibatch 확인은 없다.
- adaptive lr 이 두 군에서 다른 경로를 가는 것 (17f-2 6 절: 불공정은 아님) 의 기록. 미구현.
- 0 초기화 동치 · 고정 동치의 GPU 확인 · multi-GPU (`reduce_parameters` 는 grad 가 None 이 아닌 매개변수만 모음) 경로. 미확인.

### 8.2 smoke 사전 등록 (17f-2 5.3 의 1 ~ 6 · 등록 문서 없음)

1. **실행 무결성:** CPU 함수 수준에서 고정 가중치 · latent · grad · Adam 상태 · group lr 을 T11 ~ T13 이 본다. 입력 시점 · reset · 지도 저장 · 부모 초기 동치의 GPU 확인 · 학습 중 NaN/Inf 중단은 연결 전이라 안 됨. 17f 의 센서 · 학습 연결 관문 (8.3) 은 그대로 남는다.
2. **고정된 측정 일정:** 초기 · 마지막 · 중간 checkpoint 시점 · (pilot 이면) 49 / 50 전후 · 검사 빈도. 등록 안 됨.
3. **표현 · 행동 진단:** 고정 관측 묶음 (평지 · 틈 접근 · 접촉 · 경계 · 다양한 명령) · latent cosine 의 하위 분위수와 상황별 분포 · action KL (방향 · 12 관절 합/평균 · std 처리 · corpus) · expert weight 의 sample 별 entropy 와 평균 사용 entropy · 8 weight 분포 · clipping 전후 묶음별 gradient norm 과 실제 group lr · 틈 조우에서 value 와 return 차이. 코드 없음 (17f-2 5.1 표의 항목 전부).
4. **두 군 공동 규칙:** 코드는 두 군에 같은 함수 · 같은 규칙을 쓰게 되어 있으나, 「한 군이 실패 기준에 걸리면 같은 후보의 A/B 를 함께 재검토」 하는 등록은 없다.
5. **전환과 재시작:** `load_state_dict` 는 다른 규칙의 재개를 거절하고, 새 규칙은 부모에서 `make_optimizer` 로 새로 시작해야 한다. pilot 시도 수 · 실패 · 선택 이유 기록 틀은 없다.
6. **평가 분리:** pilot 용 학습 / eval 시드와 최종 평가 묶음 분리 · 최종 B−A 를 보고 W · r · checkpoint 를 고르지 않는 규칙. 등록 안 됨.

그 밖에 17f-2 5.2: cosine 0.9 · 평지 −10%p 를 자동 전환 기준으로 쓰지 않는 것, 표본 수 · 신뢰구간 · 명령별 판정, 고정 구간 안의 평지 퇴행을 해제 탓으로 돌리지 않는 것. 등록 안 됨.

### 8.3 17f 의 센서 · 학습 연결 관문 (17f 5 절 · 판 3 에서 바뀐 것만 표시)

- 실제 collision mesh 의 평지 · 단차 · 빈 공간에서 hit · 광선 순서 · 갱신 시각 · reset 직후 값. 미확인 (판 2 와 같음).
- 정상 miss 가 물리적 구멍인지 mesh 누락 · 범위 밖 · 센서 지연인지 가르기 · 유한한 두 깊은 바닥이 clip 으로 같아지는 것. 미확인.
- 학습 연결: 지도 시점 보존 (8.1) · teacher / reconstruction 경로 제거 (8.1) 는 안 됨. **optimizer 중복 · 누락 · frozen encoder 의 grad / state · adaptive lr 변경 때 비 유지 · 저장 · 복원 뒤 같은 출력** 은 판 3 에서 CPU 로 확인 (T11 ~ T13 · T12 재개 비트 동일). 실제 학습기에서는 미확인.
- 고장 관문 호출 (8.1). 미구현.
- 공정성 · 퇴행 기준 등록 (8.2). 안 됨.
- critic: 정상 miss 를 −2.5 로 읽는 부모 critic 의 gap value 편향 · advantage 분포. 미확인 (판 2 와 같음). A 도 privileged critic 의 학습 신호를 받는다.

### 8.4 정하지 않은 것 (등록 대상)

첫 A/B 의 `encoder_mode` (17f-2 4 절 권고는 full_freeze) · schedule 을 별도 pilot 으로 할 때 W · r · clip 묶음 · 중단 기준 · S2 환경 수 · iteration 수 · iteration 당 시간 (17f-2 2.2 의 5 초 / iteration 은 미확인).
