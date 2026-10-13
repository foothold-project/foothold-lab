다른 안: 첫 S2 A/B는 student encoder를 전 구간 실제 고정하고, W=50·r=0.1은 별도 미세조정 pilot 후보로 분리하며, 현재의 smoke 전환 기준과 `r=0` 구현을 그대로 채택하지 않는다.

> 분류: A/정책학습 · ASTRA 17f-2 검증
> 작성: 오흥재 (ASTRA 검증 작성) · 2026-10-14
> 근거: TASK-astra-17f2-s2-encoder.md (4ead327e) · VERIFY-astra-17d.md §6.3 · VERIFY-astra-17f.md §5 · DESIGN-s2-ab-v1.md §6 · S2 판 2 사본과 로컬 코드 · E1 설정 · 부모 PPO 구현
> 요지: PPO iteration 단위는 적절하지만 W50·r0.1의 효과 근거는 없고, lr 0은 현재 구현에서 실제 encoder 고정과 다르다. 첫 비교의 해석을 좁히고 smoke와 최종 평가를 분리한다.
> 상태: 설계 검토 완료 · 코드 정적 확인 · 신규 학습·성능 실측 없음 · S2 기동 승인 아님

# ASTRA 17f-2 · encoder 고정과 지도 입력 A/B

표기: **확인됨**은 이번에 읽은 코드·설정 또는 명시한 계산, **추정**은 설계 권고, **미확인**은 실측하지 않은 효과다. 17f의 CPU 시험은 선행 검증이며 이번에 재실행한 시험이 아니다.

## 1. 의뢰 네 물음의 답

| 물음 | 판정 |
|---|---|
| W 단위 | PPO iteration을 채택하되 부모 번호와 분리한 S2 지역 번호로 정의한다. 실제 optimizer step·환경 transition 수도 함께 기록한다. |
| W50·r0.1 | 탐색용 후보로는 가능하지만 첫 A/B의 검증된 기본값으로 채택할 근거가 없다. 첫 비교는 student encoder 전 구간 고정을 권고한다. |
| smoke와 대안 | 현재는 사전 등록이 충분하지 않다. 측정 대상·주기·표본·명령별 성공 정의·두 군 공동 전환·재시작·독립 평가가 빠졌다. cosine 0.9는 성능 손상의 입증 기준이 아니다. |
| 공정성과 v2 설명 | 두 군에 같은 규칙을 적용해야 한다. B−A는 그 규칙 아래 actor의 이상적 지도 입력 효과다. B−v2 전체 차이를 지도 효과로 부르는 것은 틀리다. |

**추정 · 권고 이유:** 제한된 첫 실험에서 답할 것은 ‘기존 몸 감각 표현을 유지하면서, 같은 희소 지형을 연습할 때 actor에 이상적 지도를 더 주면 무엇이 달라지는가’다. 사전학습 표현까지 동시에 바꾸면 해석할 경로가 늘어난다. 전 구간 고정이 최고 성능을 보장해서가 아니라, 첫 물음의 범위를 명확하게 만들기 때문에 권고한다. 시간이 충분해도 이 둘의 질문은 분리하는 편이 낫다.

## 2. 단위와 수치: 산술이 맞는 것과 효과가 입증된 것은 다르다

### 2.1 PPO iteration은 적절하다

**확인됨:** E1 `params/agent.yaml`은 rollout 24 step, PPO 5 epoch, minibatch 4개다. 이 설정을 유지하고 한 minibatch당 해당 PPO optimizer를 한 번 갱신하면 iteration당 20 step, W50은 1,000 step이다. PPO가 수집과 여러 epoch의 최적화를 번갈아 수행한다는 뜻과 맞는다. 다만 이것은 모든 PPO 구현에 보편적인 상수가 아니며, 부모 CTS의 별도 encoder optimizer까지 합한 횟수도 아니다. [PPO 원 논문](https://arxiv.org/abs/1707.06347)

등록할 정의는 다음과 같다.

- `s2_update_index=0`은 S2 첫 rollout의 PPO 갱신이다. W50이면 0~49 갱신 동안 고정하고, 50부터 해제한다. 그 iteration의 첫 minibatch 전에 상태를 바꾼다.
- 부모 checkpoint의 iteration 20,000을 이 번호로 그대로 넘기면 첫 갱신부터 고정이 풀린다. 부모 runner의 `current_learning_iteration`/checkpoint `iter`를 그대로 재사용하지 않는다.
- 중단·재개 시 완료한 S2 갱신 수, 다음 번호, optimizer·LR 상태와 난수 상태를 보존한다. 재개할 때 W를 다시 시작하거나 건너뛰면 다른 실험이다.
- iteration당 rollout 길이·환경 수·epoch·minibatch·gradient accumulation·갱신 생략 여부를 고정한다. 이들이 바뀌면 같은 W라도 수집량이나 최적화량이 달라진다.

optimizer step 단위는 epoch·minibatch 수를 바꾸면서도 사전학습 부분을 몇 번 갱신하지 않을지 통제할 때 더 직접적이다. 그러나 그것만 고정하면 경험한 지형의 양이 달라질 수 있다. 이번처럼 학습 예산과 설정이 iteration에 맞춰져 있으면 iteration을 주 단위로 쓰고, 실제 step·transition·경과 시간을 같이 남기면 된다.

### 2.2 W50의 근거

**확인됨 · 조건부 산술:** 50/2,000=2.5%, 50×20=1,000이다. 환경 수가 8,192라면 W50 동안 수집량은 50×24×8,192=9,830,400 transition이다. S2 환경 수를 확인하지 않고 이 값을 실제 S2 수집량으로 쓰면 안 된다. iteration당 5초라는 가정이면 250초, 약 4분 10초다. **S2의 5초/iteration은 미확인이다.**

이 산술은 actor·critic이 새 분포에 충분히 맞춰지는 시점이 50이라는 근거가 아니다. 전체 transition 수가 많아도 희소 지형의 접근·접촉·회피·추락이 충분히 일어났는지는 별도다. 17f의 ‘15% 배정과 15% 조우는 다르다’는 조건도 유지한다.

**lead 문구 수정:** ‘너무 길면 A와 B가 encoder를 못 쓰는 조건’은 틀렸다. 고정한 encoder도 매 순간 450차원 몸 상태 이력에서 latent를 계산한다. 제한되는 것은 **표현의 추가 학습**이지 encoder의 사용이 아니다. map encoder, actor와 critic은 여전히 학습할 수 있다.

지도에서 actor로 가는 새 열이 0으로 초기화되어 첫 역전파에서 map encoder gradient가 막히는 것은 맞다. 그러나 새 열이 바뀌면 이후 gradient가 전달될 수 있다. 이 구조 자체가 1,000번의 optimizer 갱신을 기다려야 한다는 근거는 아니다.

### 2.3 r0.1의 근거

**확인됨:** 부모 설정의 actor LR와 student encoder LR는 각각 0.001이지만 encoder는 재구성·분산 관련 손실로 별도 학습됐다. 17f에서 확인한 부모 마지막 actor LR는 약 0.000170859375였으며 그 0.1배는 약 0.0000170859375다. 이번에 checkpoint를 다시 불러 재측정하지는 않았다.

**미확인:** 이 0.1배가 새 PPO 손실에서 표현 손상을 막거나 최종 지도 활용을 돕는지는 모른다. 부모와 다른 손실·gradient 규모, 새 Adam moment, adaptive LR, gradient clipping이 함께 작동한다. 작은 명목 LR가 작은 latent 변화나 작은 action KL을 보장하지 않는다. ‘미세조정 관행’은 후보를 만드는 이유이지 이 로봇의 안전 구간을 정하는 증거가 아니다.

따라서 W50·r0.1을 ‘합리적 탐색 후보’라고 적는 것은 가능하다. ‘안전한 출발값’이나 ‘고정 후 적응이 보장된 값’이라고 쓰면 근거를 넘어선다. 더 좋은 특정 W·r 수치를 새로 제시할 자료도 없다.

## 3. 대안 r=0에는 현재 코드상 결함이 있다

### 3.1 lr 0과 실제 고정은 다르다

**확인됨 · 정적 경로:** `night-tools-20261013/s2/s2_policy.py:282~295`에서 `is_frozen()`은 `update_index < W`만 본다. W가 끝나면 `requires_grad_(True)`를 적용하고, r=0일 때는 optimizer의 encoder LR만 0으로 둔다. 즉 W50·r0은 update 50부터 encoder gradient를 다시 계산한다.

`test_s2.py:465,697`은 전체 `pol.parameters()`를 한꺼번에 `clip_grad_norm_`에 넣는다. 이 방식에서는 LR가 0인 encoder도 gradient가 존재하면 전체 norm에 들어간다. PyTorch는 이 norm을 모든 해당 gradient를 이어 붙인 것처럼 계산한다. [공식 gradient clipping 설명](https://docs.pytorch.org/docs/2.14/generated/torch.nn.utils.clip_grad_norm_.html)

간단한 계산 반례가 있다. actor gradient norm이 3, encoder가 4, clipping 한도가 1이면 전체 norm은 5이고 actor gradient는 약 0.6이 된다. encoder가 실제로 고정되어 gradient가 없으면 actor만 norm 3이므로 약 1이 된다. 이것은 **gradient 차이의 계산**이며 이번에 돌린 학습 시험이 아니다. Adam의 정규화가 있으므로 곧바로 ‘actor 파라미터 이동이 40% 작다’고 환산해서도 안 된다. 그래도 LR 0인 부분이 나머지 학습 계산에 들어오지 않는다는 주장은 성립하지 않는다.

Adam 역시 gradient가 있는 파라미터의 step·moment를 갱신할 수 있다. `grad=None`으로 건너뛰는 것과 LR를 0으로 두는 것은 같지 않다. [공식 Adam 설명](https://docs.pytorch.org/docs/2.14/generated/torch.optim.Adam.html)

**필요한 의미:** 전 구간 고정은 student encoder의 `requires_grad=False`, 잔여 gradient 없음, 해당 optimizer 상태의 진전 없음, 고정 입력에서 latent와 가중치 불변으로 확인해야 한다. optimizer에서 제외하거나 정확하게 건너뛰는 구현이 필요하다. ‘encoder 파라미터 delta=0’ 하나만 확인하면 이 결함을 놓친다. 별도 full-freeze 상태를 두는 편이 명확하며, W를 전체 예산 이상으로 두는 방식은 종료 번호와 재개·연장 시점까지 맞아야 한다.

### 3.2 학습기 연결에서 비율을 덮어쓸 수 있다

**확인됨 · 부모 코드:** `source/rsl_rl/rsl_rl/algorithms/moe_cts.py:278~311`은 minibatch KL에 따라 LR를 조정한 뒤 **모든 optimizer param group에 같은 LR를 쓴다.** 이를 S2에 그대로 연결하면 r0.1도 r0도 깨질 수 있다. `EncoderSchedule.apply()` 주석은 adaptive LR 변경 때마다 다시 부르라고 명시하지만, 주석이 실제 호출을 보장하지는 않는다.

**미확인:** 완성된 S2 학습 루프에서 이 경로가 잘못 연결됐다고 실측한 것은 아니다. 연결할 때 LR 변경 뒤, optimizer step 전의 각 group LR와 freeze 상태를 확인해야 한다는 뜻이다. 학습기를 아직 확인하지 않은 상태에서 ‘r=0이면 끝까지 고정’이라고 승인할 수 없다.

## 4. 첫 실험의 권고안과 내 이전 의견의 정정

**추정 · 권고안:** 부모 E1 student encoder를 첫 S2 A/B의 전 구간 실제 고정한다. 지도 encoder·확장 actor·critic·std는 등록한 동일 규칙으로 학습한다. A는 지도와 mask가 상수, B는 이상적 height·mask이며 나머지 설계는 같게 둔다. 부모 몸 감각 표현까지 바꿔야 지도를 쓸 수 있는 것은 아니다.

이 선택의 한계도 결과에 붙여야 한다.

- B가 A보다 좋아지면 ‘고정된 부모 몸 감각 표현에 지도를 추가한 이 학습 조건에서 개선’이라고 말할 수 있다.
- 차이가 없으면 ‘이 조건에서 효과를 확인하지 못함’이다. 표현 고정·지도 encoding·연습량·지형 조우 부족 등이 병목일 수 있으므로 ‘지도가 쓸모없다’는 결론은 틀리다.
- full freeze가 최고 성능이나 가장 안정적인 정책을 보장하지 않는다. actor·critic·std는 움직이므로 encoder 고정만으로 평지 보행 보존도 보장되지 않는다.

그다음 필요할 때 **별도 질문**으로 W50·r0.1의 표현 적응 A/B를 진행할 수 있다. 이 값이 최적이라는 뜻은 아니다. 단계적 해제나 부모 latent anchor 손실도 가능하지만, 어느 층을 언제 풀지 또는 anchor 계수·입력 분포를 추가로 정해야 한다. anchor를 붙이면 ‘PPO만’이라는 손실 정의도 달라진다. 첫 지도 정보 비교에 지금 더할 이유는 약하다.

**내 17d §6.3·17f §5도 같은 기준으로 정정한다.** 짧게 고정한 뒤 낮은 LR로 푸는 방식은 위험을 줄여볼 후보였고, 필요한 정답 순서로 입증한 것이 아니다. 17f의 W3·r0.25 CPU 시험은 일정 구현을 시험한 값이며 W50·r0.1의 효과를 검증하지 않았다. ‘처음 W 뒤 반드시 해제’를 기본 설계처럼 받아들일 여지를 만든 것은 내 권고의 한계다. 이번에는 질문을 좁힌 전 구간 고정을 먼저 권고한다. 이것 역시 실측 우월성 주장이 아니다.

## 5. smoke: 지표 목록은 괜찮지만 판정 절차가 부족하다

### 5.1 무엇을 재는지부터 고정해야 한다

| 항목 | 반드시 구분할 것 |
|---|---|
| 고정 관측 묶음 | 부모와 A/B에 같은 450차원 이력·45차원 single obs·해당 지도·명령을 넣는다. 평지뿐 아니라 틈 접근·접촉·경계와 다양한 명령을 포함한다. 무작위 입력/0 입력 시험은 입력 경로 시험이지 행동 보존 시험이 아니다. |
| latent cosine | 평균뿐 아니라 하위 분위수와 상황별 분포를 남긴다. 같은 입력에서 고정 구간 latent가 변하면 구현 문제다. 해제 후 낮은 cosine만으로 행동 손상이라고 판단하지 않는다. |
| action KL | 부모 분포와 현재 분포 중 KL 방향, 12관절 합인지 평균인지, std 처리와 입력 corpus를 고정한다. 평균·상위 꼬리와 action/target 차를 본다. rollout의 old policy와 current policy 사이 PPO KL과 부모 대비 KL을 섞지 않는다. |
| expert entropy | 이 모델은 soft gating이다. sample별 weight entropy와 평균 사용 weight의 entropy를 나눠 보고, 8개 weight 분포를 남긴다. argmax 선택 횟수만 세면 실제 혼합을 놓친다. |
| gradient | clipping 전·후, encoder·map encoder·actor·critic 묶음별 norm과 실제 group LR를 구분한다. encoder 고정 때 `grad=None`·상태 불변까지 확인한다. |
| value | critic 입력·value·return·advantage 유한성뿐 아니라 틈 조우에서 value와 return 차이를 본다. 부모 critic을 복사했다고 희소 지형 value가 맞는 것은 아니다. |
| 평지 명령 | 전진·횡이동·후진·회전·정지의 등록된 칸, 속도, 시간, 성공 정의, deterministic/stochastic 정책, 평가 seed·표본 수를 정한다. 전체 평균 하나로 명령별 퇴행을 감추지 않는다. |

**확인됨:** 부모 `networks/moe.py:160~168`은 softmax weight와 8개 expert 출력을 가중합한다. 하나의 expert만 고르는 구조가 아니다. 평균 sample entropy가 낮아도 각 sample이 서로 다른 expert를 쓰면 전체 사용은 균등할 수 있고, 그 반대도 따로 봐야 한다. 균등 사용 자체를 성공 기준으로 강제할 이유도 없다.

고정 corpus는 같은 상태에서 함수가 바뀌는지를 본다. 새 정책이 실제로 방문하는 상태가 바뀌는 문제는 on-policy 기록에서 따로 본다. 둘을 섞으면 표현 변화와 상태 분포 변화를 구별하기 어렵다.

### 5.2 cosine 0.9와 평지 −10%p를 자동 전환 기준으로 쓰지 않는다

**판단:** cosine 평균 0.9에는 성능 보존을 보장하는 근거가 없다. 드문 위험 상태의 표현이 바뀌어도 평균은 높을 수 있다. 반대로 latent 좌표가 회전하고 actor가 보상하면 cosine은 낮아져도 행동은 유지될 수 있다. 따라서 이 값은 탐색 경고선으로 등록할 수는 있어도, 단독으로 ‘표현 붕괴’와 r0 전환을 판정할 증거가 아니다.

평지 −10%p는 허용 퇴행 폭이라는 **의사결정 값**으로 사전 선택할 수 있다. 그러나 현재는 표본 수·신뢰구간·명령별 판정이 없어 측정 변동과 퇴행을 구분하지 못한다. 부모와 같은 초기조건·seed로 짝지어 차이와 불확실성을 보고, 부족한 표본은 ‘미확인’으로 둔다. 한 학습 seed의 환경 수만 늘려 학습 seed 간 재현성까지 확보했다고 말하지 않는다. 필요한 표본 수는 분산·짝의 불일치율과 허용 오차에 달려 있어 여기서 근거 없는 개수를 제시하지 않는다.

또한 encoder가 고정된 첫 50 iteration 안에 평지가 이미 나빠지면 원인을 encoder 해제 탓으로 돌릴 수 없다. actor·critic 변화, 명령·입력 오류를 먼저 봐야 한다. 이때 ‘r0로 바꾸면 해결’이라는 대안의 인과 근거도 없다.

### 5.3 사전 등록에 더할 최소 항목

첫 실험을 전 구간 고정으로 정하면 결과 뒤 freeze 방식을 고르는 분기는 없어진다. 그래도 smoke는 필요하다. 기능 확인과 성능 판정을 분리한다.

1. **실행 무결성:** 입력 시점·reset·지도 저장, 부모 초기 동치, 고정 가중치·latent·grad·Adam 상태, group LR, NaN/Inf를 본다. 구현 위반은 중단 사유다. 앞선 17f의 센서·학습 연결 관문은 그대로 남는다.
2. **고정된 측정 일정:** 초기·마지막과 중간 checkpoint 시점을 미리 정한다. W50 pilot이면 경계 49/50 전후도 포함한다. ‘100 iteration 안에 한 번이라도’를 쓰려면 검사 빈도까지 정해야 한다. 검사 횟수가 늘면 잡음에 의한 경보도 늘어난다.
3. **표현·행동 진단:** cosine·KL·expert·gradient는 원인 진단용으로 보존한다. 확인되지 않은 수치를 성능 안전 인증으로 바꾸지 않는다. 평지와 희소 지형에 무엇이 좋아지고 나빠졌는지 각각 기록한다.
4. **두 군 공동 규칙:** W50·r0.1 pilot을 별도로 한다면 어느 한 군이 등록한 실패 기준에 걸려도 같은 후보 설정의 A/B를 함께 재검토한다. A만 r0, B만 r0.1로 최종 비교하면 지도 입력과 학습 규칙이 함께 바뀐다.
5. **전환과 재시작:** 대안으로 바꿀 때 양쪽 모두 같은 부모에서 optimizer·일정·난수 초기화 규칙을 맞춰 새로 시작한다. 실패한 pilot 끝 가중치에 freeze만 걸면 부모에서 시작한 r0와 같지 않다. pilot 시도 수·실패·선택 이유도 남긴다.
6. **평가 분리:** pilot용 학습/eval seed와 최종 평가 묶음을 분리한다. pilot을 보고 프로토콜을 정할 수는 있지만 그 자료를 최종 독립 검증처럼 재사용하지 않는다. 최종 B−A를 보고 유리한 W·r 또는 checkpoint를 고르지 않는다.

100 iteration은 2,000 iteration의 안정성을 보장하지 않는다. W50 pilot에서는 해제 후 50 iteration만 관찰한다. 제안한 짧은 기록은 경로 연결과 초기 이상을 찾는 데는 유용하지만, 나머지 장기 퇴행 여부는 미확인이다.

## 6. A/B 공정성과 v2 대비 설명

**같게 둘 것:** 부모 checkpoint·초기 공유 가중치·지도 encoder 초기화, 모델 용량, 새 optimizer 선택, freeze/해제 규칙, 학습 예산, 지형 생성과 명령 분포·reset·종료·보상·잡음, privileged critic, 평가 칸과 seed 묶음. A에는 실제 mask를 우회 제공하지 않는다. 실제 희소 지형 조우 횟수와 누락·고장도 두 군 모두 공개한다.

같은 adaptive LR **규칙**을 쓰더라도 두 군의 KL이 달라져 실제 LR 경로가 달라질 수 있다. 그것 자체가 불공정은 아니다. 지도 효과의 학습 과정 중 일부일 수 있다. 반면 B 성적을 보고 B만 LR를 유리하게 조정하면 비교가 달라진다. 동일 난수 시작도 이후 상태 궤적의 동일함을 보장하지 않는다.

| 비교 | 말할 수 있는 범위 |
|---|---|
| S2 B−A | 고정한 학습 절차·분포·명령 조건에서 actor에 이상적 지도 정보를 제공한 효과. 두 군 모두 지형 정보가 든 critic으로 학습하므로 ‘지도 정보를 전혀 쓰지 않는 정책과 비교’라고 말하지 않는다. |
| S2 A−E1 부모 | 희소 지형 연습·PPO 후속학습·모방 경로 제거·새 optimizer 등 변경을 함께 적용한 차이. 어느 하나의 순수 효과는 아니다. |
| S2 B−v2 | 구조·관측·연습량·명령 규약 등이 다른 전체 시스템의 결과 차이. 같은 평가 세계·조건·입력 정합성이 먼저 필요하며, 지도만의 기여는 B−A로 별도 제시한다. |

첫 실험 결과의 정직한 제목은 ‘고정된 E1 몸 감각 표현에서 이상적 지도 입력을 더한 A/B’다. 이후 encoder 해제를 시험한다면 별도 조건으로 적는다. 승률만 높이고 명령 준수·평지·다른 지형을 잃었다면 얻은 것과 잃은 것을 함께 적는다. 이번 검토에서 어느 쪽이 좋아질지는 **미확인**이다.

## 7. 근거 경로와 수행 범위

- 의뢰: [TASK-astra-17f2-s2-encoder.md](TASK-astra-17f2-s2-encoder.md), SHA256 `0e334d9c446a72e3326cfebb548ead62a86a6a38d5f9d0c5cd20e6ad29751537`.
- 선행 판단: [VERIFY-astra-17d.md](VERIFY-astra-17d.md) §6.3, [VERIFY-astra-17f.md](VERIFY-astra-17f.md) §5, [DESIGN-s2-ab-v1.md](DESIGN-s2-ab-v1.md) §6. 설계 1~5절은 옛 판이며 6절의 수정 의미를 우선했다.
- S2 고정 사본: [s2_policy.py](night-tools-20261013/s2/s2_policy.py), [test_s2.py](night-tools-20261013/s2/test_s2.py), [SHA256SUMS.txt](night-tools-20261013/s2/SHA256SUMS.txt). policy SHA256 `6352a7f35ef77984b103c5c7eeca533e542a25d7d1207bcc334797bdc9c732f1`은 이번에 읽은 `C:/isaac/ext/go2_rl_robotlab/_eval/s2/s2_policy.py`와 동일했다.
- E1 설정: `C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/params/agent.yaml`.
- PPO·MoE·재개 구현: `C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/` 아래 `algorithms/moe_cts.py:278~311`, `networks/moe.py:160~168`, `runners/on_policy_runner_cts.py:108~136,278`.

이번 의뢰에서는 코드·설정·문서를 읽고 해시와 산술을 대조했다. 신규 optimizer 갱신 시험, GPU·Isaac·학습·평가, 코드 수정, 운영 파일·출력·STOP·잠금·registry 변경, 커밋·push를 하지 않았다. `r0`의 clipping 문제는 정적 경로와 계산으로 제시했으며 S2 실학습에서 측정한 장애로 과장하지 않았다. 이 문서의 완성은 실험 기동 관문 통과를 뜻하지 않는다.
