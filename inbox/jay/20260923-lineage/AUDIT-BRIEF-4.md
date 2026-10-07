# 4 차 감사 브리프 · 진행 방향 점검

> 모델: `gpt-6-astra` · 웹검색 불필요
> 의뢰: 오흥재 · 2026-09-23
> 산출: `inbox/jay/20260923-lineage/AUDIT4-astra.md` 한 파일

## 무엇을 봐 달라는 것인가

3 차 감사(`AUDIT3-astra.md`)를 받고 팀장이 방향을 승인했습니다. **집행하기 전에 「이 방향으로 가도 큰 문제가 없는지」만 확인해 주십시오.** 전면 재감사가 아닙니다.

**3 차 감사는 당신이 냈습니다. 그러니 그 권고를 다시 확인해 달라고 하면 자기 확인이 됩니다.** 그래서 묻는 것은 **그 뒤에 제가 «새로» 한 것과 «새로 나온 사실»** 입니다.

## 3 차 이후에 벌어진 것

```
1  [0-b] v2b-s 가 학습 중 죽었다 (3 차 감사 중에 일어났고 당신도 확인했다)
2  내가 tfevents 로 원인을 진단했다. 아래 3 절
3  팀장 승인으로 «같은 시드 43» 으로 재시도를 걸었다 (v2b-s2)
4  codex app-server 로 한도 조회를 시도했다. 아래 5 절
5  텔레그램 발송기를 만들었다 (_out/loop/tg.py) · 아직 한 통도 안 보냈다
```

## 읽을 것

```
_out/loop/state.json                        현재 상태와 incidents
_out/loop/watchdog.py · eval_runner.py · verdict.py · tg.py
C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_gap_nvidia\
  2026-09-23_14-42-37_..._v2b-s_...   (죽은 판의 tfevents)
  2026-09-23_14-42-33_..._v2b-r_...   (살아 있는 판)
  2026-09-21_11-03-28_..._v2b_...     (부모)
C:\isaac\IsaacLab\logs\gap_run_logs\20260923_17*_v2b-s2_*.log  (재시도)
C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\rsl_rl\algorithms\ppo.py
inbox/jay/20260923-lineage/AUDIT3-astra.md   (당신의 3 차 감사)
```

## 물을 것 다섯

### 1. 죽은 원인에 대한 제 진단이 맞습니까

제가 tfevents 에서 읽은 것입니다. **원자료로 확인해 주십시오.**

```
Policy/mean_noise_std   전 구간 0.537 ~ 0.622 · 마지막 0.5516
Train/mean_reward       마지막까지 27 ~ 30
Train/mean_episode_length  마지막까지 970 ~ 995
Loss/value_function     1576 에 0.028 -> 1577 에 0.92 -> 1586 에 1.3e7 -> 1662 에 inf
Loss/learning_rate      발산 시작 시점에 «최저» 1e-5 · 1661 부터 0.01 (상한)
```

제가 내린 결론은 이렇습니다.

```
가치 함수(critic)가 1577 부터 발산했다
정책의 행동은 마지막까지 정상이었다 (보상·에피소드 길이가 근거)
ppo.py:104 의 Adam 하나가 policy.parameters() 전체를 갱신하고
ppo.py:313 이 손실을 하나로 합치므로, critic 의 inf 가 NaN 기울기가 되어
std 파라미터까지 오염시켰다
std 는 양수 보정 없이 날것으로 학습되는 값이라 NaN 이 되면 Normal() 이 거부한다
```

**틀린 곳이 있습니까.** 특히 이 셋을 봐 주십시오.

```
「std 가 줄어서 터졌다」를 제가 «반증했다» 고 말해도 됩니까
학습률 0.01 이 «원인이 아니라 결과» 라는 제 말이 맞습니까
critic 발산의 «뿌리» 를 이 자료로 말할 수 있습니까, 아니면 미확인입니까
```

### 2. 같은 시드로 재시도한 판단이 타당합니까

같은 시드 43 으로 다시 걸었습니다. 제 근거는 「또 죽으면 시드의 성질이고, 완주하면 무작위 사건이며 후자가 더 큰 발견」이었습니다.

**이 추론에 구멍이 있습니까.** 그리고 **재시도가 1577 근처를 지날 때 무엇을 봐야 합니까.**

`v2b-s2` 가 살아 있다면 그 tfevents 를 읽어 지금 어디까지 왔고 가치 손실이 어떤지 적어 주십시오.

### 3. 다음에 만들 것이 당신이 제시한 순서와 맞습니까

당신의 9 절 순서 1~3 을 제가 이렇게 잡았습니다.

```
1 단계  실패 보존 · 입력 고정 · preflight
   v2b-s 실행 폴더와 로그를 «건드리지 않고» 보존한다
   실행마다 (학습 config SHA · 체크포인트 SHA · 평가 규격 판 · 코드 커밋)을 적는다
   없으면 «시작하지 않는다»

2 단계  원장 · 원자적 소유권 · attempt별 출력
   SQLite 파일 하나. 표는 runs · attempts · jobs · events · outbox
   소유권은 UPDATE ... WHERE owner IS NULL 의 «영향 행 수» 로 정한다
   PID 텍스트 잠금을 버린다
   출력은 attempt 폴더마다 새로 만들고 검증 뒤 completion.json 을 원자적으로 확정한다

3 단계  완전성 검사와 채점 수정
   기대 집합을 «선언» 한다 (지형집합 x 지형 x 속도 x 체크포인트, 축 2 의 정확한 9 키)
   집합 일치 · 분모 · 유한수 · 중복 · 필수 원자료 · 체크포인트 SHA 를 검사한다
   INVALID / FAIL / PASS 로 나누고 INVALID 는 분기 입력 금지
   candidate 를 base_gates_met 로 이름을 바꾼다
   verdict.py:310 의 「배포본보다 나쁘지 않다」를
   「이 비교 규칙에서 하락을 검출하지 못했다」로 고친다
   3 차 감사의 반례 넷을 «전부 거부» 하고 v2a/v2b 수치는 그대로 재현하는 시험을 붙인다
```

**빠진 것이 있습니까. 순서가 틀린 곳이 있습니까.** 특히 **1 단계와 2 단계 사이에 있어야 하는데 없는 것**이 있으면 짚어 주십시오.

### 4. SQLite 표 설계에 결함이 있습니까

```
runs      run_id · branch · task · seed · device · config_sha · ckpt_sha ·
          code_commit · state · created · updated
attempts  attempt_id · run_id · n · out_dir(절대경로) · pid · pid_start_time ·
          state · exit_code · started · ended
jobs      job_id · attempt_id · kind(train|axis1|axis2|video|verify) ·
          idempotency_key · owner_token · lease_until · state · out_dir
events    seq · run_id · kind · payload · at        (추가만 · 수정 없음)
outbox    id · run_id · event_seq · channel · body · state · tries · sent_at
```

`state` 값은 `STARTING · RUNNING · SUCCEEDED · FAILED · STALLED · UNKNOWN · INVALID` 로 잡았습니다.

**이 설계로 3 차 감사의 P0 셋이 실제로 막힙니까.** 막히지 않는 것이 있으면 어디입니까.

### 5. 한도 조회 · 제가 어디까지 왔는지

당신이 `account/rateLimits/read` · `account/usage/read` · `account/rateLimitResetCredit/consume` 가 있다고 알려 주셨습니다. 제가 시도한 결과입니다.

```
codex app-server proxy         소켓 연결 거부 (os error 10050)
                               소켓 경로가 Orca 런타임 홈 아래에 있다
codex app-server (stdio 직접)   initialize 는 «성공» 했다
                               userAgent 와 codexHome 이 돌아왔다
account/rateLimits/read        아직 응답을 못 받았다. 핸드셰이크 순서를 못 맞춘 것 같다
```

**올바른 호출 순서와 파라미터를 알려 주십시오.** 그리고 **읽기 전용 조회만** 하십시오. **`rateLimitResetCredit/consume` 는 절대 부르지 마십시오.** 리셋권은 팀장 것입니다.

응답을 받으면 **값 자체가 아니라 «필드 이름과 구조»** 를 적어 주십시오. 그래야 제가 파서를 만듭니다.

## 마지막으로

**이 방향으로 가면 안 되는 이유**가 있으면 그것을 먼저 적어 주십시오. 「대체로 괜찮다」로 시작하지 마십시오. 우리가 낸 잘못은 전부 다른 세션이 잡았습니다.

## 형식

```
표기   확인됨 / 실측 / 판단 / 미확인
       「확인됨」은 파일과 행을 답니다

금지   제 문서의 문장을 근거로 쓰는 것
       코드를 고치는 것 (이번엔 감사만 합니다)
       리셋권 소비
```

산출은 `inbox/jay/20260923-lineage/AUDIT4-astra.md` 한 파일입니다. 머리에 `분류 · 작성 · 근거 · 요지 · 상태 · 판` 을 답니다. em dash 를 쓰지 마십시오. 기술 용어는 원어로 씁니다 (actor · critic · seed 를 「배우」「비평자」「씨앗」으로 옮기지 마십시오).
