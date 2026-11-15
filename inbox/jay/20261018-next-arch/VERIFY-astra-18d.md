비교 유효. b3 M1 대 b4 M2의 동일 누적 rollout 비교는 유지되며, 조각 계산의 손실·KL·clip·optimizer·증류 gradient는 아래 CPU 대조 범위에서 일치한다. bitwise 동일성과 GPU 성능은 미확인이고, 별개인 무인 큐의 2절 수정 요구는 유지한다.
> 분류: A/정책학습
> 작성: ASTRA · 2026-10-18
> 근거: b2·b3·b4 고정 코드 대조 · 실제 함수의 CPU 모의 반례·gradient·Adam 대조 · IsaacLab 실행 순서
> 요지: b4 accumulation의 비교 타당성은 확인 범위에서 유지되며, 큐의 실패 격리·마감 판정은 별도 미해결이다.
> 상태: 독립 검토 완료 · GPU·Kit·실제 Windows Job 동작 미확인

# ASTRA 18d · b3 P1 무인 큐 검토

## 1. 대상과 증거의 범위

- F = `C:/Users/AI-WS01/s2_lab/step1_18b_b3_frozen/`. 아래 상대 경로·행은 F 기준이다. 비교본은 `C:/Users/AI-WS01/s2_lab/step1_run_b2/`.
- `REPORT-step1-18b-b3.md`, `STEP1-B3-CHANGED-PY.txt`, 큐·runner·trainer·Job owner·발 cache 변경을 읽었다. `step1_queue.py`의 실제 b2 대비 텍스트 차이는 추가 255줄·삭제 131줄이다. 보고된 변경 줄 수와 계산 방식은 구분한다.
- 현재 `STEP1-18B-B3-SHA256SUMS.txt`의 **162항목 전부 원바이트 SHA256 일치**를 직접 확인했다. 목록 SHA는 `0ebeda0a833f069e8becf40c20985710c2f52bbbe609f415ce1e4081396def99`. lead의 157항목·CR 제거 검사는 이 확인과 동일한 계수라고 쓰지 않는다.
- 검토한 큐 SHA는 `e50588851fed9626f38e311ba2196172c8597d899d8c2af74d5f9802bf89f186`.
- lead의 unittest 29/29, undefined 0, 실제 launcher import 성공은 이번에 독립 재실행하지 않았다. 시험 코드는 읽었지만 그 보고를 실제 무인 종료의 증거로 확대하지 않는다. 실행 중인 두 GPU smoke 결과도 이번 판정에서 미확인이다.

## 2. 큐를 띄우기 전에 고칠 것

### 2.1 Job 생성·정리 실패가 arm 경계를 넘는다

**확인됨.** `step1_queue.py:386`의 `JobOwner(kernel)`은 arm별 `try`가 시작되는 393행 밖에 있다. M1 실행 뒤 M2의 Job 생성이 실패하면 공통 `finally:491`로 빠져 정상 M1까지 `stop_owned()` 한다. 자식 `launch()` 실패를 잡는 것만으로 시작 경로 전체가 격리되지는 않는다.

정리 경로도 같은 문제다. 467~477행의 예외 처리 안에서 `active_count`, `stop_owned`, `close`가 다시 실패할 수 있다. 공통 정리 492~501행에서도 첫 owner 정리 실패를 다음 owner까지 넘기지 않도록 잡지 않는다. 따라서 502행의 나머지 승인 실행 finish 처리와 506행의 결과 수합도 건너뛴다. `s2_job_owner.py:146,171,177,186`은 이 호출들이 실패할 수 있는 실제 경로다.

CPU에서 고정본 `run_live` 함수 자체를 AST로 추출해 실행했다. 파일·승인·스레드 풀·Job은 메모리 대역으로 바꾸고, 실제 프로세스는 만들거나 종료하지 않았다.

| 입력 | 직접 관찰한 결과 |
|---|---|
| 두 arm 정상 종료 | 두 finish, 예외 없음 |
| M2의 `launch()`만 실패 | M2 `launch_failure` finish, M1 정상 종료, M1 강제 중단 없음 |
| M1 기동 뒤 M2 owner 생성 실패 | **M1 stop 호출**, 두 finish 사유 `supervisor_exception`, 예외 전파 |
| 두 arm 기동 뒤 M1 조회 실패, 그 가족 종료도 실패 | M1 stop 두 차례, **M1 finish만 호출**, M2 정리·finish 누락, 예외 전파 |

마지막 모의 결과를 실제 Windows에서 자식이 영구 고아가 됐다는 증거로 쓰지는 않는다. 실제 감독기 프로세스가 종료하면 KILL_ON_JOB_CLOSE가 정상 형제까지 종료할 수 있다. 어느 경우든 요구한 형제 학습 유지와 실행별 finish 보장은 깨진다.

**최소 수정:** owner 생성부터 arm별 예외 범위에 넣고, 정리 실패는 해당 arm의 미해결 오류로 보존하면서 다른 owner의 감시·정리·finish를 계속하게 한다. 정리 성공을 확인하지 못한 가족을 정상 종료로 표시해서는 안 된다. 실패한 owner 처리를 이유로 공통 감독기 전체를 탈출시키지 않아야 한다. 위 정상 입력·두 예외 입력을 함께 확인하면 충분하며 새로운 GPU 승인 절차는 필요 없다.

lead 시험 `test_step1_cpu.py:239`는 모든 모의 자식의 `exit_code()`가 즉시 0인 상태에서 게시 오류를 넣는다. 게시 오류 처리의 유효한 시험이지만, owner 생성 실패·종료 API 실패·계속 학습 중인 형제의 생존은 그 시험의 증명 범위가 아니다.

### 2.2 trainer가 먼저 정상 마감하면 실패 영수증을 낸다

**확인됨.** trainer는 `step1_runtime.py:35`의 독립 시각 검사로 `hard_end - grace`에 도달한 update 경계에서 스스로 종료한다. runner 210~222행은 저장 후 빠져나오고, `scripts_rsl_rl/train_step1.py:379`는 `step1.end.json`에 `stop_reason`을 남긴다.

반면 큐 434~451행은 이미 종료된 자식에 대해서 STOP 파일이 있을 때만 종료 이유를 붙인다. trainer가 먼저 경계 저장·종료하고 큐가 그 뒤 첫 poll을 하면 STOP 파일 없이 `exit_code=0, reason=None`이 된다. 큐는 trainer 종료 기록을 읽지 않는다. 목표 update보다 이른 정상 마감 저장은 `_classify_finished:225~244`에서 `CHILD_EXIT`가 되고 `_finish_one:257`에서 MAI `failed`가 된다.

실제 분류 함수에 닫힌 `model_20003.pt`, 목표 추가 2,000 update, exit 0을 넣고 경로·SHA·stat만 메모리 대역으로 제공했다.

| 종료 이유 입력 | 판정 | finish |
|---|---|---|
| `None` | `CHILD_EXIT` | `failed` |
| `deadline` | `STOPPED_WITH_CHECKPOINT` | `aborted` |

첫 행이 발생하는 poll 순서는 코드상 가능하다. 이 시험은 실제 GPU에서 그 순서가 발생했다는 주장은 아니다. 잘 저장한 마감 종료를 실패로 보고하면 다음 재개와 실행 횟수 해석이 틀어진다.

**최소 수정:** 자식 종료 후 그 실행의 `step1.end.json`과 닫힌 checkpoint의 run ID·iteration·SHA를 대조해 경계 종료 사유를 수합한다. 정상 조기 종료와 감독기의 강제 종료를 구분해 기록하고 finish 상태에도 같은 사유를 사용한다. 단순히 마감 시간이 가까웠다는 이유로 임의의 비정상 종료까지 정상화하지 않는다. 이 수정은 학습 방법이나 허용 시간을 바꾸지 않는다.

## 3. 이번 변경에서 닫힌 부분과 남은 실측 한계

| 중점 | 판정·근거 |
|---|---|
| 18c 2.2 게시 오류 격리 | `emit:340~352`가 state·watch 예외를 각각 기록한다. `_finish_one:250~263`은 분류 실패에도 finish를 시도한다. 다만 Job 생성·정리 예외는 2.1처럼 아직 닫히지 않았다. |
| 18c 2.3 늦게 닫히는 저장본 | `latest_committed_checkpoint:201~212`와 매 poll 호출 416행으로 수정됐다. metrics보다 나중에 닫힌 `.pt`를 다시 찾고 `.pt.tmp`는 정규식에서 제외한다. 이전 iteration 검사 완료 표시 때문에 영구 누락되던 경로는 제거됐다. |
| 18c 2.4 STOP·마감·Job | trainer 경계 저장, 감독기 유예 후 가족 종료, 실행별 USD 경로와 실제 torch UUID 확인은 코드에 있다. 실제 Job 가족 종료·4096 env에서 유예 안에 update와 저장이 끝나는지는 미확인이다. 종료 판정에는 2.2가 남는다. |
| 18c 2.5 발 invalid 지연 | 코드상 수정됐다. 실제 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/manager_based_rl_env.py:201~208`은 counter 증가 → termination → reward 순서다. `foot_train_step1.py:100~106`이 termination에서 현 step 질의를 먼저 수행하고, 76행에서 invalid를 갱신한다. reward는 30행에서 같은 cache를 쓴다. |
| 부분 reset의 cache | `foot_train_step1.py:93~98`이 step과 전체 episode 벡터를 비교한다. reset된 env가 하나라도 있으면 이전 cache가 무효다. 부분 env만 재질의하는 최적화는 아니지만 이전 invalid를 한 step 늦게 읽던 오류는 해소됐다. 실제 raycast 정확도·처리 시간은 미확인이다. |
| 상태 파일 경쟁 | 큐 state와 watch 게시자는 이 구현에서 감독기 메인 흐름 하나다. SHA·finish worker는 결과 dict를 반환하고 메인 흐름이 합친다. 임시 파일 공유로 인한 내부 동시 쓰기 결함은 이번 코드에서 찾지 못했다. 외부 파일 잠금과 디스크 오류는 실측하지 않았다. |

현재 돌고 있는 b3 10-update smoke의 중단을 요구하는 판정은 아니다. 위 두 수정은 **P1 무인 큐**의 운영 경로에 대한 것이다. 기존에 닫힌 학습 설계나 별도 P2·평가를 다시 승인 조건으로 얹지 않는다. 코드·GPU·실행 프로세스·원자료·고정본은 변경하지 않았고 이 보고서만 새로 썼다.

## 4. 16:47 추가 사실과 M2 gradient accumulation

### 4.1 판정과 사실의 출처

**방향은 타당하다. 공통 4096 env·rollout·원래 미니배치 수를 유지하고, 미니배치 내부 계산만 조각내면 M1 대 M2의 학습량 비교를 유지할 수 있다. 다만 조각별 optimizer 갱신으로 바꾸면 다른 실험이다. sol의 수정 코드는 아직 검토하지 않았으므로 구현 등가성은 미확인이다.**

lead 16:47 보고: M1 4096 env·10 update 통과, 학습 0.42 s/update. M2 첫 update 학습 289.8 s, GPU 1 메모리 15.9/16.3 GB로 중단·HOLD. M1은 16:46부터 GPU 0에서 `launch_step1` 단독 P1, 추가 13,000 update·월요일 08:00 마감·500마다 저장. 이 수치와 현재 실행 상태는 로그·장치에서 독립 재측정하지 않았다. 이 보고만으로 M2 지연 원인을 VRAM 부족으로 확정하지 않는다. 첫 update 초기화 비용, 메모리 이동, 실제 연산 병목의 기여는 미확인이다.

이번 제안 때문에 진행 중인 M1을 중단하거나 처음부터 다시 돌릴 이유는 없다. 다만 단독 실행은 큐 2.1의 결함을 우회하는 것일 뿐, 그 실행의 마감·가족 종료가 검증됐다는 뜻은 아니다. 이전의 무인 큐 판정은 유지한다.

### 4.2 반드시 보존할 수학적·실행 조건

근거 A = `source/rsl_rl/rsl_rl/algorithms/moe_cts.py`, S = `source/rsl_rl/rsl_rl/storage/rollout_storage_cts.py`, M = `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py`.

| 항목 | 조각내기에서 유지할 조건·근거 |
|---|---|
| 데이터와 순서 | 같은 rollout, GAE·return·old log-prob·old mu/sigma, epoch 수, 원래 미니배치의 표본과 순서를 유지한다. 원래 teacher와 student를 따로 섞어 합치는 S:130~186의 경계를 보존한다. 조각마다 다시 표본을 뽑거나 teacher/student 경계를 혼동하면 안 된다. |
| 손실 가중치 | A:353~356의 surrogate는 **teacher 평균 + student 평균**이다. 조각 c의 teacher 합/Nt + student 합/Ns를 누적한다. value·entropy는 원래 전체 N의 평균이므로 각 조각 합/N이다. 마지막 짧은 조각도 실제 표본 수로 가중한다. 모든 손실을 조각 수로 나누거나 teacher/student를 합쳐 평균하면 원래 목적함수가 아니다. |
| optimizer 경계 | 원래 미니배치 시작에 `zero_grad` 한 번, 조각마다 가중한 loss의 backward, 모든 조각이 끝나면 전체 optimizer parameter의 norm clip 한 번, Adam step 한 번이다. A:388~406의 갱신 횟수·모멘트·weight decay를 유지한다. 조각별 clip·step·zero_grad는 금지다. 지도 encoder parameter도 기존 optimizer 목록 A:96~104 그대로 포함한다. |
| KL·학습률·조기 중단 | A:301~345의 teacher KL 평균, student KL 평균, 전체 KL 평균을 **원래 미니배치 전체**에서 계산한 뒤 lr과 early-stop을 한 번 결정한다. 조각 KL의 최댓값은 기존 `max(teacher 평균, student 평균)`과 다르다. prepass 또는 동일 파라미터에서 누적한 통계로 결정할 수 있다. 중단 결정이면 누적 gradient도 버리고 해당 미니배치를 step하지 않는다. |
| 정규화·스케줄 | advantage 정규화 A:233~234, 280~283은 기존 rollout 또는 원래 미니배치 기준을 유지한다. 조각별 mean/std는 안 된다. 관측 normalizer 갱신, warmup, curriculum, `step1_update_number`, `ppo_updates`는 조각 수만큼 증가시키지 않는다. AMP·dtype·loss 계수·clip 범위를 이 수정에 함께 바꾸지 않는다. |
| 계산 그래프 | sample 축만 나눈다. M2의 187개 격자·CNN·토큰 attention·공간 amax는 한 표본 안에서 그대로 계산한다. M:42~80에는 배치 통계 정규화가 없고 attention dropout은 0이어서 sample 분할이 구조상 가능하다. query latent의 detach와 student PPO 경로의 기존 no_grad 범위를 그대로 둔다. 매 조각 backward 후 그래프를 놓아야 메모리가 줄며 모든 그래프를 모아 마지막에 backward하면 목적을 달성하지 못한다. |
| CTS 증류 순서 | A:420~452의 student 증류는 PPO 루프 뒤 별도 optimizer로 수행하며 KL 중단 시 생략한다. 우선 PPO만 조각내고 이 경로는 그대로 두는 것이 범위에 맞다. 증류까지 나눈다면 아래 load-balance 예외를 해결해야 한다. |
| RNG·재개 | PPO의 `policy.act`도 sampling을 하므로 조각별 호출이 RNG 소비와 다음 rollout에 영향을 줄 수 있다. 동등성 대조에서는 저장한 행동의 log-prob 계산과 RNG 상태를 통제한다. 부동소수점 합산 순서까지 bitwise 동일하다고 약속하지 않는다. 조각 크기·코드 SHA·dtype·누적 방식은 실행 metadata에 남기고, 중단 재개 때 동일 설정을 복원한다. |

**이 코드에서 특히 놓치기 쉬운 반례 둘:** teacher loss 값 [1, 3, 5], student [10]이면 기존 surrogate는 3 + 10 = **13**이다. 합쳐 평균하면 **4.75**로 달라진다. 올바른 조각 가중 합은 다시 13이다. CPU 산술로 확인했다.

또 A:441~444의 load-balance는 `mean(gating_weights)`를 먼저 구한 뒤 target과의 차를 제곱한다. 조각별 load-balance loss 평균과 같지 않다. 두 조각의 expert usage가 각각 [1, 0], [0, 1]이면 전체 loss는 **0**, 조각 loss 평균은 **0.25**다. 증류를 나눠야 한다면 전체 usage로 원래 손실·gradient를 재현해야 하며, 단순 accumulation으로 해결됐다고 해서는 안 된다.

### 4.3 공통 checkpoint 비교의 정확한 단위

공통 4096 env와 rollout 길이 T가 같으면 추가 K rollout update의 수집량은 양쪽 모두 `4096 × T × K`다. M1이 먼저 끝나도 **양쪽에 실제 존재하는 동일 누적 K**에서 비교하면 된다. 같은 벽시계 시각의 M1 13,000 대 M2 500을 구조 우열 비교로 쓰지 않는다. 학습 효율과 시간·메모리 비용은 별도 지표다. 동일 평가 조건·episode 수·지형·명령·seed 묶음을 쓰고, 두 arm의 실제 PPO step 수와 KL 중단 횟수도 함께 보여준다. 정책별 KL에 따라 실제 step 수가 달라질 수 있으므로 같은 rollout 수를 같은 optimizer step 수라고 쓰지 않는다.

**500 배수의 파일 번호와 추가 학습 횟수는 구분해야 한다.** 현 runner는 it=20000 update를 수행한 뒤 `model_20000.pt`를 저장한다. 누적 추가 횟수는 `it - 20000 + 1`이다. 따라서 `model_20500.pt`는 추가 **501회**, `model_21000.pt`는 추가 **1001회**다. 양쪽 같은 파일 iteration을 비교하면 표본 예산은 맞지만 이를 500·1000회라고 라벨링하면 틀리다. 기존 M1 저장을 바꾸지 않고 파일 iteration·metadata의 실제 추가 횟수를 함께 기록하면 된다. 정확히 추가 500회 간격으로 새로 저장하려면 20499·20999 등에 해당하지만, 이 표기 문제 때문에 M1 재시작은 필요 없다. 근거: runner:113,205~207 및 큐:223,225.

고정된 공통 checkpoint 집합에서 비교하고 좋은 쪽의 서로 다른 시점을 골라 비교하지 않는다. 아직 한 seed의 중간 결과만 있다면 그 범위로 결론을 제한한다. 공통 checkpoint는 학습량을 맞추는 장치이지 다중 seed 일반화나 지도 효과의 독립 증명은 아니다.

### 4.4 sol 수정의 확인 범위

새 승인 단계를 추가하지 않는다. sol의 기존 CPU 시험에 **동일 초기 모델·optimizer·고정 rollout으로 미분할 대 분할의 손실, clip 전 gradient, clip 후 parameter, Adam 상태·step 수, KL·lr·중단 결정을 대조**하면 된다. teacher/student 비율이 다른 입력, 마지막 조각이 짧은 입력, KL 중단 입력을 포함한다. 수치 오차 허용치는 dtype에 맞춰 보고하고 임계값 근처에서 분기가 달라졌다면 숨기지 않는다. 이 확인 전에는 수정 방향의 타당성과 수정 코드의 등가성을 구분한다.

속도 개선 자체는 CPU 증거로 확인할 수 없다. GPU 실행을 맡은 lead가 실제 update 시간과 peak allocated/reserved·장치 메모리를 같은 측정 구간에서 확인해야 한다. `data=list(generator)`(A:260~261)는 조각내기 이후에도 전체 미니배치 사본을 잡고 있으므로 activation을 줄여도 전체 메모리 압박이 충분히 해소된다고 단정할 수 없다. 이번 ASTRA 작업에서는 GPU나 코드를 실행·수정하지 않았다.

## 5. 17:17 추가 의뢰 · b4 고정본 판정

이 절은 4절에서 아직 보지 못했던 b4 구현을 검토한 결과다. 이후 근거로 앞 절의 당시 미확인 상태를 소급 변경하지 않는다. 무인 큐와 학습 계산의 판정도 구분한다.

### 5.1 대상과 결론

B4 = `C:/Users/AI-WS01/s2_lab/step1_18b_b4_frozen/`. 아래 A·S는 각각 이 묶음의 `source/rsl_rl/rsl_rl/algorithms/moe_cts.py`, `source/rsl_rl/rsl_rl/storage/rollout_storage_cts.py`다.

`REPORT-step1-18b-b4.md` 전문과 b3 대비 Python 변경을 직접 읽었다. `STEP1-18B-B4-SHA256SUMS.txt`의 **167/167 원바이트 해시 일치**를 독립 확인했다. 목록 SHA는 `d6c328c1c8042adc20e818a6c8aeb408adfc045bfdaf2efc4628386480eee0a9`. lead의 38/38 전체 시험과 undefined 0은 이번에 재실행하지 않았고 아래의 좁은 CPU 대조를 직접 했다.

**M1 b3와 M2 b4의 공통 학습량 비교를 무효로 만드는 손실 가중·optimizer 횟수·shuffle 변경은 발견하지 못했다. 이 변경을 이유로 두 학습의 중단이나 M1 재시작을 요구하지 않는다.** 단, 구현 전체가 bitwise 동일하거나 10,000 update의 결과까지 같다는 의미는 아니다. 실제 GPU 실행·속도·메모리·완주는 미확인이다. M2 17:17 기동과 양쪽 10,000 update 상한은 lead 보고이며 독립 실측하지 않았다.

### 5.2 손실·KL·증류의 대조

| 확인 항목 | 판단·근거 |
|---|---|
| 유효 미니배치 손실 | A:604~632는 teacher·student별 `len(indices)/population`으로 surrogate를 합치고 value·entropy는 `len(indices)/full_total`로 합친다. 원래 teacher 평균 + student 평균과 전체 value·entropy 평균을 보존한다. 길이가 다른 조각에서도 같은 분모를 쓴다. |
| KL·LR·중단 | A:551~601은 파라미터 갱신 전 no-grad prepass로 teacher·student 전체 KL 합을 각각 구한다. 원래 미니배치의 전체 평균과 두 집단 평균의 max로 LR·중단을 한 번 결정한다. chunk별 threshold를 쓰지 않는다. 중단이면 PPO와 증류 모두 생략한다. |
| clip·Adam | A:604~647은 zero_grad 한 번, 조각별 backward, 원래 optimizer 전체 parameter clip 한 번, Adam step 한 번이다. 지도 encoder가 포함된 optimizer 등록도 유지된다. |
| 증류 gate 평균 | A:652~679는 **전체 student 미니배치의 gate 평균 u를 먼저 계산**한다. 목표 q, expert 수 E, 조각 비중 w에 대해 `w × mean(2 × detach(u-q) × 조각 gate 평균)`의 gradient를 누적한다. 그 합은 원래 `mean((u-q)^2)`의 gradient와 같다. prepass와 backward 사이에 student parameter step이 없고 이 MoE는 dropout·배치 통계 갱신을 하지 않아 현재 구조에서 유효하다. |
| 증류 값과 gradient 구분 | surrogate용 `balance_gradient`의 숫자 자체는 원래 loss 값이 아니다. b4는 이를 gradient에만 쓰고, 보고할 loss에는 원래 전체 `balance_value`를 넣는다. 이 구분도 맞다. latent loss는 student 표본 수로 가중하며 증류 optimizer clip·step은 원래 미니배치당 한 번이다. |
| 분할된 표본의 내부 구조 | M2의 187-token 공간 연산은 그대로이고 sample 축만 나뉜다. 지도 query detach와 teacher/student 계산 경로의 역할도 바뀌지 않았다. |

**독립 CPU 대조:** `isaac311-moects/python.exe -B`, CUDA 숨김, torch CPU thread 2. b3 `MoECTS.update` 원문을 AST에서 추출해 같은 초기 모델·optimizer·고정 rollout에 결합하고 b4 분할 경로와 비교했다. 파일을 고치지 않고 메모리에서만 실행했다. 16 env·rollout 2, teacher:student 12:4, 3 epoch·2 미니배치, chunk 요청 7로 길이가 다른 조각을 만들었다. 초기 shuffle seed는 90으로 동일하게 두었다. lead의 1 epoch·1 미니배치 대조를 그대로 반복한 것이 아니다.

| 입력 | PPO / 증류 Adam step 수 | clip 전 gradient 최대 절대 차 | 최종 parameter 최대 절대 차 | 결과 |
|---|---|---:|---:|---|
| 일반 다중 epoch·불균등 조각 | 양쪽 각각 6 / 6 | 2.623e-6 | 9.966e-8 | 일치 범위 |
| load-balance 계수 10으로 강화 | 양쪽 각각 6 / 6 | 2.623e-6 | 9.989e-8 | 일치 범위 |
| old mu에 +100, KL 상한 .001 | 양쪽 0 / 0 | 0 | 0 | PPO·증류 모두 미갱신 |

일반·강화 입력의 PPO Adam 상태 최대 절대 차는 2.608e-8, 증류 Adam 상태는 9.459e-10 이하였다. loss·KL·LR 등 반환 scalar 최대 절대 차는 1.044e-7 이하였다. clip 호출은 각 실행 12회로 PPO 6회·증류 6회였고, KL 거절 입력은 0회였다. 이 표는 작은 CPU 입력의 관찰값이며 GPU 오차 상한이 아니다.

검사 민감도도 확인했다. 고정 파일은 그대로 두고 메모리 사본에서 gate gradient 계수 **2를 1로 바꾼 변이**를 넣었더니 증류 clip 후 gradient 차 0.003191로 2e-5 기준을 넘었다. 올바른 코드만 통과시킨 관찰이 아니다. 다만 KL 경계 바로 옆에서의 GPU 반올림 분기, 실제 4096 env의 gradient는 미확인이다.

### 5.3 shuffle와 M1 경로

**shuffle 분포·횟수·epoch별 재사용 방식은 바뀌지 않았다.** b3 generator와 b4 `step1_index_batches`(S:201~216)는 teacher randperm 한 번, student randperm 한 번을 만들고 같은 index를 epoch마다 재사용한다. b4가 epoch마다 새 shuffle를 도입한 것이 아니다. S:218~223의 env-major flatten도 b3와 같은 순서다.

직접 같은 저장소·seed에서 2 미니배치 × 3 epoch의 6묶음을 대조했다. observations의 모든 필드, actions, old values, advantages, returns, old log-prob, old mu·sigma가 **모두 torch.equal**이고, shuffle 직후 RNG 상태도 같았다.

새 index 함수는 A:249의 **M2이면서 chunk size가 양수인 분기**만 사용한다. M1은 b4에서도 기존 `mini_batch_generator`와 전체 계산을 쓴다. 현재 GPU 0의 b3 M1에는 새 코드 자체가 적용되지 않는다. 공통 파일에 추가됐다는 이유만으로 M1의 학습 표본 방식까지 바뀌었다고 볼 수 없다.

단, **update 종료 뒤 RNG 상태는 세 CPU 입력 모두 달랐다.** 원래 PPO는 큰 집단별 `policy.act`로 사용하지 않는 행동까지 sampling하고, b4는 이를 조각별로 호출한다. KL 거절 시 b4 prepass는 sampling을 하지 않지만 b3는 KL 검사 전에 sampling한다. 따라서 동일 seed가 이후 행동·shuffle의 bitwise 같은 경로를 보장하지 않는다. 이것은 이번 고정 rollout의 손실·gradient 등가성을 깨지는 않지만, “encoder 외 모든 난수·경로까지 통제한 paired 학습”이라는 주장은 성립하지 않는다. 보고는 **동일 예산·설정의 확률적 학습 비교**로 하고, 평가는 별도 동일 seed·장면 묶음을 사용한다.

### 5.4 운영상 남는 성능 문제와 비교 범위

**성능상 고칠 가치가 있는 부분은 별도로 있다.** S:218~223의 `step1_sample_indices`는 매 호출마다 `transpose(0,1).flatten(0,1)`를 전체 rollout에 먼저 적용하고 그 뒤 index를 고른다. 비연속 env-major 변환의 flatten은 전체 복사를 만든다. CPU action tensor [2,16,12]에서 원본과 flatten 결과의 storage 주소가 다른 것을 직접 확인했다. “선택 index가 512 이하”인 기존 시험은 이 선행 전체 복사를 세지 않는다.

현재 4096×24, 미니배치 4, epoch 5, chunk 512이고 KL 중단이 없으면 PPO prepass·backward와 증류 두 pass·사후 KL에 표본 추출이 약 **5,762번** 호출된다. 관측 770 + 나머지 필드 40 = 810 float32/transition을 가정하면 반복 flatten 복사량의 단순 합은 update당 약 **1.67 TiB**다. 이는 코드 횟수 기반 추정이며 실측 VRAM peak·대역폭·소요 시간이 아니다. 모든 사본이 동시에 남는다는 뜻도 아니다.

수정한다면 전체 rollout을 한 번만 env-major로 만들어 재사용하거나, flat index를 env/time으로 환산해 필요한 sample만 직접 읽으면 된다. 같은 필드·순서 검사를 유지하면 수학적 학습 조건은 바꾸지 않는다. **이 비용은 성능 개선 항목이며 현재 비교를 무효화하거나 GPU를 멈춰야 한다는 근거는 아니다.** 실제 속도가 충분한지는 lead 실행 기록으로 판단할 일이다.

b4는 b3 대비 평가·watch 코드도 포함해 변경됐다. 평가에서는 양쪽 checkpoint에 **같은 고정 평가기·사례표**를 적용해야 한다. 서로의 패키지에 든 서로 다른 평가기로 결과를 만들어 비교하면 별도 혼입이 생긴다. M1·M2 공통 10,000 update 상한, 같은 누적 checkpoint 비교와 4.3의 파일 번호 오프셋 원칙은 그대로 적용한다. 초기 13,000 계획은 lead 최신 보고의 10,000 상한으로 대체해 기록한다. 이 검토는 큐 2절의 미해결 예외 경로를 고쳤다는 판정이 아니다.
