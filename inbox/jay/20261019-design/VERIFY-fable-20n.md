> 분류: A/정책학습 · 검증 (fable 20n · rl 지각 코드가 스스로 정한 가정 13 개 대 START 원문)
> 작성: fable 세션 · lead 의뢰 20n · 10/20 11:5x
> 근거: rl 커밋 7f6b327c · ff03e2d5(브랜치 feature/s2-perception-rl · 작업 트리 C:/mai/wt/foothold-lab/rl) `foothold_s2/models/start_perception.py` · `runners/perception_replay.py` · `runners/start_runner.py` · `sensors/depth_aug.py` · `scripts/start_gate.py` · START 2512.13153v1.txt 42 · 84~86 · 116~120 · 132 · 134 · 169 · 185~217 · 221 행 · 선행 2409.15692v2.txt 95 · 305 · 331 · 339~353 · 355 행 · 선행 PDF 8 쪽 Fig. 8(PyMuPDF 로 렌더해 직접 봄) · LocoTransformer 2107.03996(ar5iv 본문) · Isaac Lab 2.3.2 `utils/buffers/circular_buffer.py` 137~139 · Go2 `rsl_rl_ppo_cfg.py` 19~20 · rsl_rl(anaconda isaac311) `algorithms/ppo.py` 156~192 · `modules/actor_critic.py` 148~183 · `networks/normalization.py` 43~60 행
> 요지: 13 개 중 **원문과 다른 것 1**(② U-Net 마지막 층: 선행 Fig. 8 은 3×3 conv 블록, 코드는 1×1) · **원문에 있는 것 2**(⑤ KL 차원 합 = 식 3 정의 · ⑦ 수집 때 z 표집 = Reparam) · 나머지 10 은 원문에 없음(가정(rl) 유지). ④ 는 원문엔 없으나 선행이 융합의 출처로 인용한 LocoTransformer(모달리티별 평균) 와 다름(참고). 가정 목록은 12 §12 · 13 §10, 12 §6.1 통합 관문 행에 edge 보상 「s2_env_cfg 대기」
> 상태: 완료 · 미커밋(lead 커밋) · 코드 · 학습 · GPU 없음

# VERIFY-fable-20n · rl 지각 가정 13 개 대 START 원문

## 1. 판정 요약

| # | 가정(rl) | 판정 | 원문 행 |
|---|---|---|---|
| ① | CNN 활성화 ELU | 원문에 없음 | 선행 Table V 범례 355 행: CNN 에 활성화 칸 없음 |
| ② | U-Net 마지막 1×1 conv | **원문(그림)과 다름** | 선행 Fig. 8: 마지막 「1」 블록도 녹색 = Conv k3 s1 p1 (+ReLU 범례) |
| ③ | 지도 토큰 학습 위치 임베딩 | 원문에 없음 | START 132 · 선행 95 행(공간 추론 문장만) · LocoTransformer 본문도 기재 없음 |
| ④ | prop 토큰 자리 출력만 heads 로 | 원문에 없음(인용 출처와 다름, 참고) | 선행 Table V 339 행 · LocoTransformer 는 모달리티별 평균 → 결합 → MLP |
| ⑤ | KL 차원 합 · 배치 평균 | 합은 **원문에 있음** · 배치 평균 없음 | START 116 행 식 3 |
| ⑥ | p 초기 1.0 · 2 개 미만 유지 · 모분산 | 원문에 없음 | START 193~199 행 식 5(초기값 · 표본 수 · 분산 정의 없음). 모분산은 12 §9 기대값과 일치 |
| ⑦ | 수집 z 표집 · 배포 평균 | 표집은 **원문에 있음** · 배포 평균 없음 | START 118~120 행 · 선행 Table V 341 행 Reparam |
| ⑧ | 리셋 첫 스텝 이력 · 프레임 현재 값으로 채움 | 원문에 없음 | 선행 95 행 H1 = 10 만. Isaac Lab CircularBuffer 137~139 행과 같은 꼴(확인) |
| ⑨ | 이력 10 × 45 재생 버퍼 저장 | 원문에 없음 | 재생 버퍼 자체가 원문에 없음(START 42 · 221 행) |
| ⑩ | L_TR 모든 스텝 | 원문에 없음 | START 169 행 식 4(주기 미기재). 주의 사항 12 §12 |
| ⑪ | 정규화 통계 이번 스텝 입력으로 갱신 | 원문에 없음 | 원문에 정규화 없음. 관문 cfg 는 꺼짐(start_gate.py 165 · Go2 cfg 19~20 행) |
| ⑫ | 관문 H^f base z 기준 | 원문에 없음 | START 84~86 · 134 행(기준 높이 미기재) |
| ⑬ | 증강 순서 · 매끈한 잡음 · 도형 3~18 화소 | 원문에 없음 | START 에 깊이 증강 없음(221 행). 11 §2.1 JEPLO 값과 순서 · 채움값 일치 |

## 2. 원문과 다른 것 (lead 보고)

| # | 코드 | 원문 | 어느 쪽이 맞나 · 권고 |
|---|---|---|---|
| ② | `models/start_perception.py` 101 행 `nn.Conv2d(16, 1, 1)` (1×1 · 활성화 없음) | 선행 2409.15692v2 PDF 8 쪽 Fig. 8: 채널 열 16,16 / 32,32 / 64,64 / 64→32,32 / 32→16,16 / **1**. 마지막 「1」 블록이 녹색이고 범례의 녹색은 「Conv with RELU (k=3, s=1, p=1)」 하나뿐. 1×1 블록 · 범례 없음 | 커널은 원문 그림이 맞다 → **3×3 s1 p1 로 바꿀 것 권고**(파라미터 16 → 144, 성능 차는 미확인). 마지막 ReLU 는 범례대로면 있으나 12 §3 의 h = z_hit − z_base 는 바닥이 음수라 ReLU 를 두면 전부 0 이 된다 → 「활성화 없음」 은 **가정** 으로 유지(ASTRA 19g 68 행도 「마지막 출력 활성화 불명확」). lead 결정 뒤 12 §3 Refine decoder 행 · 코드 함께 |
| ④ (참고) | 163 행 `self.attn(seq)[:, 0]` prop 토큰 자리만 | START · 선행 본문엔 없음. 선행 Table V 「Tf. Enc. [15]」 가 가리키는 LocoTransformer 2107.03996 은 「같은 모달리티 토큰의 평균 → 결합 → projection head MLP」 | 원문 기준으로는 가정 유지. 출처대로 하려면 prop 출력 + 지도 토큰 128 개 평균 → 결합(128) → Linear heads. 둘 다 Table V 의 z_tf = L(SA(·)) 에 맞는다. lead 판단 |

## 3. 반영한 자리 (미커밋)

- `12-PERCEPTION.md` §6.1 통합 관문 행: edge 보상 연결 칸 「s2_env_cfg 대기」 + rl 첫 실행 기록(미재측) · 새 절 §12 가정 목록 11 항(①②③④⑤⑥⑧⑨⑩⑫⑬) · 상태 줄 stamp
- `13-POLICY.md` 새 절 §10 가정 목록 2 항(⑦⑪) · 상태 줄 stamp
- 11 §2.1(격자 6 · 반폭 3~18 화소)은 lead 가 준 범위(12 · 13) 밖이라 안 건드림 · 12 §12 ⑬ 에 메모

## 4. 기록 (13 개 밖 · 판정 아님)

- `runners/start_runner.py` 213 행 compute_returns 에 actor 추정 51 을 0 으로 넣음 → 설치 `ppo.py` 187~189 행은 `evaluate` 만, `actor_critic.py` 162~165 행은 critic 묶음만 읽으므로 무해(확인).
- Table V 의 z_tf = L(SA) 뒤 L(z_tf) 두 Linear 를 코드는 `heads` 하나로(163~164 행). 비선형 없는 두 Linear 는 하나와 같다(z_tf 폭 미기재라 rank 만 다를 수 있음).
- Map CNN 2 층째 활성화 없음(141 행): Table V 에 CNN 활성화 칸이 없고 토큰이 바로 attention 으로 간다. 기록만.
- `AdaSmpl.update` 는 iteration 당 끝난 에피소드만 쓴다(12 §5 창 가정). 3072 env × 24 스텝 / 에피소드 약 1,000 스텝 ≈ 74 개 → count < 2 는 사실상 시작 직후뿐(계산).
- ff03e2d5 뒤 rl 커밋 9d0d8caa · fdb3974d 는 `scripts/start_gate.py` · `train_start.py` · 결과 json 둘만 바꿈(`git diff --stat`). 13 개는 그대로.
- rl 의 관문 결과(traceback 0 · 두 손실 · reset 2 · 복원 차 0.0 · p_smpl 0.272)는 커밋된 json 을 읽은 것이고 **미재측**.
- 코드 · 학습 · GPU · 커밋 없음.
