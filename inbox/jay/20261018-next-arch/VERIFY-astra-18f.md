설계는 타당하나 AME-2 공식 정책 재현이 아니라 공식 encoder 폭을 E1에 이식한 변형이며, 새 M2는 chunk 512부터 실측하는 것이 타당하다.
> 분류: A/정책학습
> 작성: ASTRA · 2026-10-18
> 근거: ame2_minimal @8beb9a688d67882828019583f7d5a78e3517f233 원문 · b4 고정 코드 · 아래 연산량 산술
> 요지: 160차원 연결은 가능하지만 입력 의미·decoder·계산량이 달라 공식 재현이나 attention 단독 효과로 해석할 수 없다
> 상태: 설계 자문 완료 · b6 구현 및 실제 속도·최대 메모리 미확인

## 1. 공식 코드와 일치하는 것과 다른 것

확인한 정본은 `C:/Users/AI-WS01/s2_lab/_research_repos/ame2_minimal/`이다. 이하 `AME2_models.py`는 그 아래 `rsl_rl/rsl_rl/models/`, `ame2_modules.py`는 `rsl_rl/rsl_rl/modules/`를 뜻한다.

- **층 폭은 맞다.** 점 FC 3→16, 높이 CNN 1→8→48의 5×5·padding 2, 결합 64→96, global 96→64→64 후 점 방향 max, prop 77→512→512→128, query 192→512→512→96, MHA 96·32 heads. 단, 공식 prop 입력 차원은 관측에서 추론하며 **77이 공식 고정값은 아니다**. FC는 xyz 모두, CNN은 높이만 받는다. ELU 위치와 마지막 선형층 뒤 활성화 없음도 보존해야 한다. 근거: `AME2_models.py:41–85,151–172`, `ame2_modules.py:20–46`.
- **latent32+single_obs45는 우리 쪽 변형이다.** 공식은 `teacher_prop`을 받는다. 특히 E1 teacher latent는 지형이 포함된 critic 관측에서 나오므로 이 77개 전체를 순수 몸 상태라고 부르면 틀린다. student latent와 의미도 같다고 보장되지 않는다. query로 보낼 latent를 detach하면 추가 gradient 경로를 막지만, 포함된 정보를 없애지는 않는다. 근거: b4 `source/rsl_rl/rsl_rl/modules/actor_critic_moe_cts.py:138–157,274–295,318–337`; 공식 `AME2_models.py:145–171`.
- **공식 decoder와 다르다.** 공식은 `[attn96, prop128, global64]`의 288차원 전체를 512→512→행동으로 보낸다. 제안은 prop128 직접 출력을 제외한 160차원을 기존 77차원에 붙여 E1 actor 237 입력으로 보낸다. query에는 prop128이 남지만 최종 경로는 공식과 다르다. E1 보존을 위한 의도적인 이식으로는 타당하다. 근거: `AME2_models.py:85,121–123`.
- 공개 저장소 README는 G1 teacher 중심 minimal release다. 이를 원 논문의 전체 학습 체계나 실제 Go2 적용 재현으로 확대해서 부르면 안 된다.

## 2. 새 160열을 0으로 시작해도 배우는가

**배울 수 있다. 첫 backward부터 encoder가 배우는 것은 아니다.** 첫 층을 `h=W_old x+W_new zφ+b`로 쓰면, `W_new=0`에서 `∂L/∂φ=0`이지만 `∂L/∂W_new=δzφᵀ`는 일반적으로 0이 아니다. 첫 optimizer step으로 새 연결이 열린 다음 backward부터 encoder gradient가 생긴다. 여러 minibatch가 있으므로 첫 PPO update 전체가 정지하는 것은 아니다. 이는 수식 판정이며 b6에서 직접 측정한 결과는 아니다.

encoder와 heads를 서로 다른 무작위 가중치로 초기화하면 새 연결 열의 0 초기화만으로 영구 대칭이 생기지는 않는다. encoder까지 전부 0으로 만들거나, 별도의 0 gate와 0 연결을 동시에 곱하면 학습이 막힐 수 있다. optimizer 등록, student 경로의 지도 계산이 no_grad 밖인지도 유지해야 한다.

E1 보존은 **유한한 지도 출력에서 초기 행동**에 한정된다. NaN×0은 NaN이고, 갱신 후 보행 보존은 보장되지 않는다. b4의 기존 77열과 새 열을 별도 linear로 계산하는 방식도 유지해야 초기 GEMM 변경에 따른 오차를 피할 수 있다(`actor_critic_moe_cts.py:284–295`). 160개 특성이 동일 분산·독립이라는 가정이면 새 연결 gradient의 전체 크기는 16개 때보다 약 √10 커질 수 있으나 실제 값은 미확인이다. feature RMS, 새 연결·encoder gradient, 행동 KL을 보아야 한다. b6 CPU 확인은 초기 행동 일치와 두 번의 갱신에서 연결 gradient 및 이후 encoder gradient가 실제 생기는지를 구분하면 된다.

## 3. M1(16) 대 M2(160)를 어떻게 부를 것인가

**「각자 논문 크기」만으로는 부정확하다.** MARG의 elevation MLP 폭 128→64→16은 맞지만 논문은 ReLU이고 b4 기본 설정은 ELU다. M2 역시 공개 encoder 폭을 따를 뿐 입력·decoder·격자·임무가 다르다. 근거: [MARG IV-A](https://arxiv.org/html/2509.20036v2), b4 `actor_critic_moe_cts.py:98,165`, 위 공식 코드.

권장 표현은 **「공통 E1에 MARG 층 폭의 16차원 MLP와 AME-2 공개 구현 층 폭의 160차원 지형 표현을 이식한 비교」**다. 용량·출력 폭·계산량을 맞춘 attention 대 MLP의 인과 비교는 아니다. 이 두 설계의 실용 성능 비교는 가능하다. attention이 다음 디딤점에 모인다는 것은 결과로 확인해야 하며 구조만으로 보장되지 않는다. 작은 기존 M2와 새 M2는 별도 모델로 기록하고 학습 곡선을 하나의 연속 실험으로 합치지 않는다.

## 4. 4096 env의 메모리·속도 위험

187점, xyz FC·높이 CNN, query 한 개 기준으로 encoder 순전파의 선형·합성곱·attention MAC을 합하면 작은 b4는 약 **2.962 M**, 제안은 **9.183 M**, 약 **3.10배**다. 제안 encoder 파라미터는 약 **842,752개**이며 E1 actor 추가 열은 제외했다. 이는 CPU 산술값으로 backward·활성화·softmax·복사·커널 효율을 제외한다. **학습 시간이 3.10배라는 뜻은 아니다.** 기존 35~43초/update도 lead 보고이며 이번 자문에서 독립 실측하지 않았다.

주요 위험은 파라미터보다 activation이다. CNN 마지막 채널은 16→48로 3배, local/KV 폭은 64→96으로 1.5배다. attention score가 물질화되면 heads 4→32로 해당 텐서는 8배다. 단, query 한 개의 cross-attention이므로 187×187 self-attention으로 계산하면 과장이다. chunk 2048에서 teacher가 1536개라면 local96 텐서 하나만 FP32 약 105 MiB이고, 여러 중간값·gradient·workspace가 더 필요하다. 총 peak GB와 초/update는 미확인이다.

공식 `ame2_modules.py:7–17`은 head dimension 3인 32-head 구성에서 Blackwell·bf16 fused backward 장애를 기록하고 `SDPBackend.MATH`를 사용한다. 이는 **그 환경의 보고**이며 우리 장비에서 장애를 재현했다는 뜻은 아니다. b6에서 backend·dtype을 확인해야 한다. 이 변경과 AMP 도입을 한꺼번에 섞지 않는 것이 낫다.

**4096 env는 유지하되 새 큰 M2는 chunk 512에서 짧은 실제 peak·시간을 보고 1024, 여유가 있으면 2048로 조정하는 것을 권고한다.** 18e의 2048 권고는 작은 b4에 대한 것이므로 새 구조에 자동 승계하지 않는다. 짧은 실행은 기존 실행 권한 안에서 진행할 사안이며 별도 승인 관문을 제안하는 것이 아니다. 10000 update의 일정은 새 구조 실측 전 확정할 수 없다.

## b6 도착 시 코드 대조

위 구조와 gradient 경로에 더해 **93→237 입력을 load·저장·재개·최종 평가까지 arm별로 처리하는지** 확인한다. b4 `load_e1_weights`에는 `+16`이 하드코딩돼 있다(`actor_critic_moe_cts.py:308`). 초기 forward만 통과해도 끝의 저장·재개에서 실패할 수 있으므로 확인 대상이다. 현재 b6를 검토하거나 실행 승인한 상태는 아니다. 코드·GPU·프로세스·기존 자료는 수정하지 않았다.
