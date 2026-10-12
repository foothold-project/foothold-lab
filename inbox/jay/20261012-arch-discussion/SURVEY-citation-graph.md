> 분류: 조사 (사실 수집 · 설계 판단 없음)
> 작성: 오흥재 (lead 하위 조사 · Claude 작성) · 2026-10-13 01:46
> 근거: arXiv HTML 전문 62편 내려받음 (여섯 편 포함, 판은 표의 「판」 열, 2026-10-13 로컬에서 텍스트로 바꿔 읽음) · Semantic Scholar Graph API `paper/arXiv:<id>/citations` (여섯 편 + 1~5회차 논문 36편, 2026-10-13 조회) · Google Scholar 「cited by」 첫 쪽 3건 (Zhang 2311.10484 · START · MARG) · arXiv API 제목 · id 검색 · WebSearch 24회 (standard)
> 요지: 여섯 편 밖에서 방법 42개(사족 41 · 휴머노이드 참고 1)의 방법 · 실험 절을 읽었고, 그중 배포되는 관절 정책이 외부 센서로 지형을 보면서 gap 또는 디딤돌 성공률을 시행 수와 함께 본문 · 표에 적은 것은 8개다 (DELTA · WTR · PUMA · CTS-MoE · DAWN · Robot Parkour Learning · SoloParkour · Parkour in the Wild). Go2 실기 또는 Isaac Lab 학습이라는 조건에 겹치면서 gap 숫자가 있는 것은 CTS-MoE (Isaac Lab, Go1) · DAWN (Isaac Lab, Go1) · TACL (Go2 배포, 숫자는 teacher) · REAL (Go2) 넷이고, Go2 로 디딤돌 RL 을 재현한 보고 하나 (Akizhanov et al.) 는 12 cm 보다 작은 돌을 학습하지 못했다고 적는다.
> 상태: 초안 · 팀장 · lead · ASTRA 논의 전

# 인용 그래프 조사: 여섯 편 바깥의 gap · 디딤돌 · 지각 보행 방법

이 문서는 사실만 모은다. 어느 방법을 쓰자는 판단과 권고는 적지 않는다(lead 몫).
여섯 편(AME-2 · MARG · START · JEPLO · MoE-CTS · HiPAN)은 [PAPERS-architecture.md](PAPERS-architecture.md) 에 있다. 여기서는 되풀이하지 않고, 이번 조사 중 새로 드러난 사실만 3절에 따로 적는다.
GitHub 저장소는 다른 조사 몫이다. 여기의 「코드」 열은 **논문 본문 · arXiv 주석에 적힌 링크**만 옮겼고 링크 안을 열어 보지 않았다.

## 읽는 법

- 근거 등급: `논문 확인 (절 · 표 · 그림)` · `초록만` · `미확인`. 표 칸에 등급이 없으면 그 행의 근거 등급(마지막 열)을 따른다.
- 「본표」(1절)에는 방법 절과 실험 절을 읽은 것만 넣었다. 제목이나 초록만 본 것은 5절 「제목만 본 후보」로 보냈다.
- 「관절 정책이 지형을 본다」의 뜻은 PAPERS 문서와 같다: **관절 목표(또는 토크)를 내는 배포 정책**의 입력에 외부 센서에서 온 지형 정보가 들어가는가. 학습 중 teacher · critic 만 보는 경우는 「보지 않는다」로 센다. 계층 구조에서 상위 계획기만 지도를 보고 관절 정책은 발자국 목표만 받는 경우는 「직접 보지 않음」으로 따로 적는다.
- 「숫자」 칸은 본문 · 표에 **인쇄된 숫자**만 옮겼다. 그림의 선 · 막대를 눈으로 읽은 값은 없다(그림에만 있으면 「그림」이라고만 적음).
- 「시행」은 그 숫자를 만든 시행 수를 본문이 적은 대로 옮겼다. 본문에 없으면 「미기재」.
- 판: arXiv `html/<id>` 가 내준 최신판. 게재: 그 논문 주석 · 본문, 또는 다른 논문 참고문헌 표기(그 경우 「참고문헌 표기」라고 적음). 둘 다 없으면 「표기 없음」.
- 숫자 표기: 범위는 `~`, 음수는 `-`.

---

## 요약 (논의에 걸리는 사실)

1. **본표 42행** (사족 41 · 휴머노이드 참고 1). 관절 정책이 지형 정보를 입력으로 받는 사족 RL 33개(1-A 21 · 1-B 12), 계층 · 모델 기반이라 관절 정책이 지도를 직접 보지 않는 것 6개(1-C, DTC 는 발 → 목표 선 위 높이 표본만 봄), gap · 돌이 없는 참고 3개(1-D). 1-A · 1-B 33개 중 실기 지형이 mocap · 미리 만든 지도인 것 2개(Zhang · Shi), 실기가 없는 것 4개(Footmap · Multi-view · Acrobotics · ES-Parkour). D435 계열 depth 를 배포 센서로 쓴 것이 가장 많다(WTR · PUMA · CTS-MoE · DAWN · WMP · KiVi · REAL · REDACT · StairMaster · PIE · Robot Parkour Learning · Extreme Parkour · Agarwal 등).
2. **배포 관절 정책이 지형을 보고 + gap · 디딤돌 성공률을 시행 수와 함께 적은 것 8개**:
   DELTA (실기 7코스 x 3회 = 21/21, 시뮬 1000 episode: Gaps 99.7 · Stepping Stones 99.5 %) ·
   WTR (실기 각 5회: 디딤돌 76.3 % 1.0 · gap 0.7 m 1.0, 시뮬 500회) ·
   PUMA (실기 각 10회: 1.2 m gap(벽 이용) 1.0 · 디딤돌 1.0, 시뮬 1000회 98.7 %) ·
   CTS-MoE (시뮬 명령 3종 x 15 episode: gap 0.05~0.50 m 성공 98.3 % vs 같은 구조 blind 40.3 %) ·
   DAWN (시뮬 3 시드 x 100: gap 10~90 cm 97.2 %, 실기 실외 70 cm gap 10회 중 60 %) ·
   Robot Parkour Learning (시뮬 100 x 3 시드 leap 80 %, 실기 0.6 m gap 10회 80 %) ·
   SoloParkour (실기 2 시드 x 10회: 35 cm gap 70 %) ·
   Parkour in the Wild (시뮬 1000 rollout: stepping stones 98.8 %, 처음 보는 gap-climb 82.0 %).
3. 위 8개에 들지 못한 주요 사유: 실기 지도가 mocap · 미리 만든 지도(Zhang 2311.10484 실기 8/10 · 5/5, Kim 2506.02835, Shi 2310.04675), 숫자가 그림에만 있음(AME-1 · Extreme Parkour 실기 · WMP 실기 · Agarwal 실기 · ANYmal Parkour · APT-RL), 숫자가 teacher(GT 높이)의 것(TACL), 계층 · 모델 기반(DTC 실기 0.1 m gap 10/10 · 0.6 m gap 4개 연속 4/4 는 숫자가 있으나 관절 정책이 지도를 직접 보지 않음).
4. **우리 구조(CTS · MoE · Isaac Lab)와 가장 가까운 것은 CTS-MoE (2606.19633)**: Isaac Lab + RSL-RL, CTS 단일 단계, student 가 depth CNN + GRU, actor 가 dense MoE (expert 6), 과제별 value head. 같은 파이프라인에서 student 를 blind 로 바꾸고 MoE 도 뺀 판(Blind CTS)은 gap 성공 40.3 %, student curriculum 최고 수준 3.95 / 6 (perceptive 판은 6.0, teacher 는 네 판 모두 6.0). `논문 확인 (Table 3 · Table 10)`
5. **Go2 로 디딤돌 RL 을 재현한 기록**: Akizhanov et al. (2407.11788, L4DC 2025) 이 Zhang et al. (risky terrains) 를 Isaac Lab 에서 ANYmal-D 로 재현 확인한 뒤 Go2 로 옮겼고, 「12 cm 보다 작은 돌은 학습하지 못했다」 · 「학습에서 본 것보다 작은 돌은 못 건넌다」고 적는다. `논문 확인 (4.3 절)`
6. **명령 체계**: gap · 디딤돌 숫자를 낸 방법 중 다수가 순수 속도 추종이 아니다. 목표 위치형(Zhang · Parkour in the Wild · ANYmal Parkour · Foot ToF · Kim), waypoint · 자율 heading(Extreme Parkour 계열 다수 · TACL · REAL · MoE parkour Go2), gap 과제만 전진 + waypoint 근접 보상(CTS-MoE), 전진만(Robot Parkour Learning · WTR/START 횡 0). 국소 속도 명령이면 디딤돌을 피해 도는 보상 꼼수가 생겼다는 보고가 있다(Footmap, 「global velocity tracking」 으로 대응). Light-Loco-Parkour(휴머노이드)는 「처음부터 학습하면 디딤돌 앞에서 멈춘다」고 적는다.
7. **저속 명령 평가**: Footmap 이 디딤돌 성공률을 0.1(또는 0.2)~1.0 m/s 로 나눠 보고하고(값은 Fig. 5 c), 본문에 「0.3 m/s 에서 기준선 대비 near 80 % improvement」라고 적는다(%p 인지 상대값인지 본문 불명확). 다른 본표 방법은 대부분 0.5~1.5 m/s 고정 명령으로 평가했다.
8. **Go2 실기 방법**: TACL(배포만, 숫자 부록) · MoE parkour Go2(32 cm 상자 10/10) · REDACT(hurdle · 통나무) · REAL(시뮬 gap SR 0.28) · StairMaster(구멍 계단 37° 30회 중 93.33 %) · PGTT(내장 L1 LiDAR, 계단만) · Layered MPC(모델 기반, 5절). Go2 시뮬만: Multi-view(Isaac Gym) · Akizhanov(MuJoCo). **Isaac Lab 학습**: CTS-MoE · DAWN · KiVi · Akizhanov 의 RL 재현.
9. **논문에 코드 링크가 있는 본표 방법**은 42개 중 5개뿐이다: Multi-view(anonymous.4open.science) · MoE parkour Go2(osf.io) · PGTT(GitHub) · Resource-constrained(GitHub) · Coholich(개인 페이지 「code」). 프로젝트 페이지만 있는 것 19개(REAL 은 「will be released」), 데이터 · 보충자료 링크만 3개(AME-1 · APT-RL 의 Zenodo 는 그림 재현 데이터, Acrobotics 는 Google Drive 보충자료), 링크 없음 15개.
10. **여섯 편보다 새 것**(JEPLO 2026-09-14 이후 v1): SABER(09-18) · REDACT(09-21) · DAWN(09-24). 2026 년 v1 전체로 넓히면 PUMA · ADAPT · LF2WB · REAL · Footmap · MoE parkour Go2 · CTS-MoE · Foot ToF · SWAP · StairMaster · APT-RL · TACL · DELTA 를 더해 16개.

---

## 1. 본표

열 설명. **판**: 읽은 arXiv 판. **지형을 보나**: 배포 관절 정책 기준. **명령**: 정책이 받는 명령. **학습 gap · 돌**: 학습 지형에 gap · 디딤돌이 있고 치수가 본문에 있으면 그 범위. **숫자**: gap · 디딤돌 성공률(본문 · 표 인쇄값) · 시뮬/실기 · 시행. **코드**: 논문 본문 · 주석에 적힌 것.

### 1-A. 사족 RL · 관절 정책이 지형 정보를 입력으로 받는다 · gap 또는 디딤돌에 대한 숫자가 본문 · 표에 인쇄됨 (성공률이 아닌 지표 포함)

| 방법 · 판 | 게재 | 로봇 · 시뮬 | 배포 센서 → 지형 표현 | 학습 단계 | 명령 | 학습 gap · 돌 | 숫자 (출처 · 시뮬/실기 · 시행) | 코드 | 근거 |
|---|---|---|---|---|---|---|---|---|---|
| DELTA 2608.22033v1 | ICRA 2027 제출 (주석) | RAIBO2 · RaiSim | D430 앞뒤 2대 → 41x25 지도 (2.0 x 1.2 m) → deformable attention 토큰 | 1 (PPO, 지도 encoder 함께) | 속도 (평가 v_x 1.0, ω U(-0.5, 0.5)) | Gaps · Stepping Stones · Grid Stones, stage 1~10, 치수 없음 | Table II 시뮬 1000 ep: Gaps 99.7 · 돌 99.5 · grid 98.5. Table V 처음 보는 혼합 코스 4개 평균 96.6 (AME 26.0). 실기 7코스 x 3회 21/21 (gap 10~20 cm, 15 cm 돌) | 없음 | 논문 확인 (II · III · Table II~VI) |
| WTR 2409.15692v2 | 표기 없음 | Lite3 · Isaac Gym | D435i 10 Hz → TR-Net 재구성 지도 (뒤 0.5 ~ 앞 1.1 m, 폭 0.8 m, 5 cm) | 1 (AdaSmpl) | 전진 [0, 1.5], 횡 0, 0 이면 yaw [-1.2, 1.2] | 돌 0.5→0.2 m, 틈 x 0.175→0.25 · y 0.1→0.175, gap 0.1→0.7 m, beam 0.175 | Table III 실기 각 5회: 디딤돌 76.3 % 1.0 · beam 0.2 m 0.8 · stepping beams 58.8 % 1.0 · gap 0.7 m 1.0. Table IV 시뮬 최고 수준 500회: 돌 0.99 · gap 0.98 | 없음 | 논문 확인 (II · III · 부록 A~D) |
| PUMA 2601.15995v2 | RA-L (본문 채택 2026-06-25) | Lite3 · Isaac Gym | D435i 10 Hz → estimator (depth CNN + 이력 → attention → GRU) → 앞발 foothold prior (거리 2 + heading 2) + latent 64 | 1 (PAS 로 GT foothold → 예측 전환, multi-critic) | 속도 (평가 1.5 m/s 고정) | wall-assisted gap · surmounting · 디딤돌, 치수 표 없음 | Table II 시뮬 1000회: 돌 98.7 · 벽 gap 60° 98.6 · 80° 96.2 (PIE 67.3 · 45.6 · 12.1). Fig. 5 실기 각 10회: 1.2 m gap + 벽 60°/80° 1.0/1.0, 디딤돌(0.5~0.8 m, 높이차 0~0.4 m) 1.0 | 프로젝트 페이지 | 논문 확인 (III · IV · Table II~IV) |
| CTS-MoE 2606.19633v1 | 표기 없음 | Go1 · **Isaac Lab** | D435i (약 30° 하향) → depth CNN [16, 32, 64] + GRU 256 → latent 32 → MoE router · expert | 1 (CTS: teacher 0.85 · student 0.15 env) | 속도 과제 v_x [-1, 1] · v_y [-0.5, 0.5] · ω [-0.8, 0.8]. gap · 장애물 과제는 v_x [0, 1] + waypoint 근접 보상 | gap 0.05~0.50 m · 장애물 0.05~0.50 m, 6 수준 | Table 3 시뮬 (명령 3종 x 15 ep): Gaps 98.3 · CTS-Single(depth) 69.0 · Blind CTS-MoE 40.0 · Blind CTS 40.3. 실기 과제당 10회 (그림) | 프로젝트 페이지 | 논문 확인 (4 · 5 · 부록 A~C) |
| DAWN 2609.29092v1 | 표기 없음 | Go1 · **Isaac Lab** | D435i raw (내장 필터 끔) 64x64 → RSSM world model latent | 1 (WMP 구조 + denoising · contrastive 학습 신호) | 속도 (범위 본문 미확인) | gap 10~90 cm (5 수준), step 10~54 cm | Table II 시뮬 3 시드 x 100: Gap 97.2 (Blind 26.2 · Extreme Parkour 83.5 · WMP 88.6 · Oracle 98.8). 실기 난이도마다 10회: 실외 70 cm gap DAWN 60 % · WMP 30 % (본문) | 프로젝트 페이지 | 논문 확인 (IV · Table II) |
| Robot Parkour Learning 2309.05665v2 | CoRL 2023 (주석) | A1 · Go1 · IsaacGym | D435 48x64 → CNN + GRU (증류 student) | 3 (soft-dynamics RL → hard RL → DAgger 증류) | 목표 속력 약 1 m/s 전진 | leap gap 학습 [0.2, 0.8] · 시험 [0.3, 0.9] m | Table 2 시뮬 100회 x 3 시드: Leap 80 %. 실기 10회: 0.60 m gap 80 % (본문) | 프로젝트 페이지 | 논문 확인 (3 · 4 · Table 1~2) |
| SoloParkour 2409.13678v1 | CoRL 2024 (주석) | Solo-12 · IsaacGym | D405 48x48 → ConvNet + GRU | 2 (privileged PPO+CaT → depth off-policy RL, privileged 경험 버퍼) | x-y 속도 | leap(gap) 등 4종, 치수 그림 | Table 1 실기 2 시드 x 10회: leap(35 cm gap) 70 % · step 85 · crawl 100 | 프로젝트 페이지 | 논문 확인 (3 · 4 · Table 1) |
| Parkour in the Wild 2505.11164v1 | IJRR 2026 (참고문헌 표기) | ANYmal-D · 시뮬레이터 이름 본문 없음 | D435i 4대 48x32 → CNN + LSTM | 3 (expert 9개 RL → DAgger 증류 → RL fine-tune) | 목표 위치 · heading · 시간 | stepping stones · beams · jump · gap-climb(처음 보는 지형), 치수 본문 없음 | Table 4 시뮬 1000 rollout: Stepping stones 98.8 · Beams 99.5 · Gap-climb(미학습) 82.0 · Down-stones(미학습) 54.4 → 재 fine-tune 92.4 | 없음 | 논문 확인 (2 · 3 · Table 4) |
| Zhang et al. Risky Terrains 2311.10484v2 | IROS 2024 (주석) | ANYmal-D · Isaac Gym | **실기 지도는 mocap + GT** → 25x16 heightmap 7 cm | 2 (generalist → specialist fine-tune) | 목표 위치 · heading | Stones-Everywhere 수준 0/5/9: 돌 92/52/20 cm · 틈 8/18/26 · 높이 1/6/10 · sparsity 15.4/44.8/81.1 % | Table II 실기: Stones-2Rows 성공 8/10 (생존 10/10) · Balance-Beams 5/5. 시뮬 Fig. 7 (3 시드 x 1000, 그림) | 없음 | 논문 확인 (II · III · IV · V · 부록) |
| AME-1 He et al. 2506.09588v1 | Science Robotics 2025 (참고문헌 표기) | ANYmal-D (+ GR-1) · 이름 본문 없음 | ANYmal: onboard elevation mapping → 26x16x3 점 → CNN + MHA (d 64, head 16) | 2 (base 지형 완전 지각 → fine-tune 지형 + 잡음) | 속도 (범위 없음) | grid stones · grid stones small (최소 12 cm) · narrow beams (최소 15 cm) · gaps · pits 등 10 수준, 치수 표 없음 | 본문: DTC 대비 +26.5 %p, Zhang 대비 +77.3 %p. DTC 는 20x20 · 12x12 돌 · 15 cm beam 에서 20 % 미만. 장애물 parkour 100 % (시행 미기재). 지형별 값은 Fig. 6 | Zenodo (그림 데이터) | 논문 확인 (Results · Methods · 보충 Methods) |
| Footmap Hwang et al. 2604.02744v1 | 표기 없음 | A1 · Isaac Gym (legged_gym) · **실기 없음** | 시뮬 GT heightmap 17x11 (0.1 m) + 발 위치 map (FK) → CNN + MHA | 1 | 「global velocity tracking」 (세계 좌표 속도 표본 → 로봇 좌표) | stones 수준 0/9: 돌 92/40 cm · 틈 2.5/20 · shift 0/10 · 높이 1/10. OOD: gaps · pits · small stones 등 | Table IV 시뮬 (수준마다 1000 robot, 1.0 m/s): 전체 77.0 % (Attn 64.2). 본문: 돌 수준 8 에서 약 80 % vs 기준선 약 0 %. 0.3 m/s 에서 「near 80 % improvement」 (Fig. 5) | 프로젝트 페이지 (주석) | 논문 확인 (III · IV · V · VI · 부록) |
| Foot ToF Fan et al. 2606.31912v2 | IROS 2026 (주석) | ANYmal-D · Isaac Gym | 발마다 ToF 4x4 (지도 없음) → LSTM 정책 | 2 (돌 위주 + 낮은 열화 → 어려운 수준 + 열화) | 목표 위치 | 돌 · gap 위주, 치수 본문 없음 | 시뮬 1000 run (돌 80 % + gap 20 %): odometry 잡음 0 → 400 % 에서 「success rate drop ... is 51.7 % to 24.3 %」 (집계 지도 흉내판 대 ToF 판의 하락폭으로 읽히나 해석 `미확인`, 값은 Fig. 6). 실기 gap 최대 60 cm · 20x20 cm 돌, 시행 미기재 | 프로젝트 사이트 | 논문 확인 (II · III · IV) |
| TACL 2608.16164v1 | 표기 없음 | Extreme Parkour 정책 구조 · Isaac Gym · 배포 **Go2 + D435i** | 숫자는 teacher (GT height map). 배포 student 는 depth (Extreme Parkour 파이프라인) | curriculum 방법 (teacher RL → depth 증류) | waypoint → 속도 명령 | Extreme Parkour 코드의 gaps 10 수준 | 본문 시뮬 (최고 수준, 지형 8 x 50 rollout): gap HCL-E 5k epoch 78 % → 최종 30 %, TACL 24 → 96 %. 실기 결과는 부록 (본문 없음) | 없음 | 논문 확인 (3 · 4) |
| Extreme Parkour 2309.14341v1 | ICRA 2024 (참고문헌 표기) | A1 · 이름 본문 없음 | D435 58x87 → convnet + GRU latent + heading 예측 | 2 (scandots RL + ROA → DAgger, heading 증류) | 속력 + 정책이 정하는 heading (waypoint 로 학습) | ramps · gaps · hurdles · steps, 치수 표 없음 | Table 2 시뮬 256 robot: Gap MXD 0.96 (성공률 아님). 실기 Fig. 7 지형·난이도마다 5회 (그림). 실기 0.8 m gap (본문) | 프로젝트 페이지 | 논문 확인 (3 · 4) |
| Agarwal et al. Egocentric Vision 2211.07638v1 | CoRL 2022 (주석) | A1 · IsaacGym | D435 (디딤돌 · gap 은 위쪽 카메라로 따로 증류) → convnet + GRU | 2 (scandots RL → DAgger) | (v_x, ω_z) | 디딤돌 · gap 포함, 치수 표 본문 없음 | Table 1 시뮬: 디딤돌 평균 x 이동 18.83 / 20.72 (Noisy 지도 1.09 · Blind 1.02). 실기: gap 26 cm 까지 100 % · 어려운 디딤돌 94 % (본문, 시행 수는 Fig. 4) | 프로젝트 페이지 | 논문 확인 (2 · 3 · 4) |
| WMP 2409.16784v1 | ICRA 2025 (참고문헌 표기) | A1 · Isaac Gym | D435i 64x64 → RSSM h_t | 1 | (v_x, v_y, ω_z) | gap 0~90 cm 등 6 지형 | Table I 시뮬 100 traj: gap return 32.37 (teacher 32.80 · student 27.07 · blind 9.80). 실기 Fig. 6 10회 (그림), 85 cm gap 통과 (본문) | 프로젝트 페이지 | 논문 확인 (IV · V) |
| REAL 2603.17653v1 | 표기 없음 | **Go2** · Isaac Gym | D435i → FiLM Mamba (10 프레임) | 2 (teacher → student, BC · RL gating) | Extreme Parkour 식 목표 | Extreme Parkour 지형 정의 그대로 | Table I 시뮬 (시행 미기재): Gaps SR REAL 0.28 · SoloParkour 0.36 · Extreme Parkour 0.10. 실기 gap 숫자 없음 | 「will be released」 | 논문 확인 (III · IV · Table I) |
| NVM 2304.01201v1 | CVPR 2023 (주석) | A1 · 이름 미확인 | 앞 depth → 3D feature volume (SE(3) 정렬) | 2 (privileged → BC) | 미확인 | Stages (gap) · Stones 등 | Table 2 시뮬 640 ep: Stones 성공 teacher 70.6 · LocoTransformer 0.9 · NVM 행은 HTML 에서 잘림 (traversing 47.4 만 확인). 실기 Table 4 5회 이동 거리 | 프로젝트 페이지 | 논문 확인 (4 · Table 2 · 4) |
| LF2WB 2603.03138v1 | 학회 표기 미확인 | Lite3 · Isaac Gym | 앞 RealSense 10 Hz → delta-rule recurrent 기억 (후진 시 사용) | 1 | 전진 10 s → 후진 10 s (고정 과제) | 높은 단 · gap · 조합 (최대 치수 본문 일부) | Table I 시뮬 (난이도 0.2~0.8, 시행 미기재): P1 90.1/86.9/81.7/75.0 % (LSTM 57.1~25.7). 실기 0.6 m gap 후진 (시행 미기재) | 없음 | 논문 확인 (III · IV · Table I) |
| PIE 2408.13740v3 | RA-L 2024 (주석 · 참고문헌 표기) | Lite3 · Isaac Gym | D435i → depth CNN + proprio → transformer → GRU → heightmap latent · foot clearance · v̂ | 1 | 본문 「Lateral velocity [0, 1.5]」 · yaw [-1.2, 1.2] | gap 최대 1 m, 디딤돌 없음 | Table III 시뮬 평균 종료 수준 gap 9.9 / 10 (지형마다 40 묶음 x 100 robot, 성공률 아님). 실기 Fig. 4 수준별 10회 (그림) | 없음 | 논문 확인 (III · IV) |
| Shi et al. Terrain-Aware 2310.04675v2 | 표기 없음 | 자체 Max · PyBullet | **실기 mocap + 오프라인 지도** → 발 주변 원형 높이 표본 | 1 (PMTG 계열) | 이동 방향 | 디딤돌 gap 최대 25 cm (시뮬) | Table I 시뮬 최대 이동 거리 (6 방향 x 3회, 성공률 아님). 실기 gap 8.5~25.5 cm (시행 미기재) | 없음 | 논문 확인 (III · IV) |

### 1-B. 사족 RL · 관절 정책이 지형 정보를 입력으로 받는다 · gap · 디딤돌 숫자가 본문 · 표에 없음 (그림뿐이거나 다른 지형만)

| 방법 · 판 | 게재 | 로봇 · 시뮬 | 배포 센서 → 지형 표현 | 학습 단계 | 명령 | gap · 돌 관련 | 숫자 | 코드 | 근거 |
|---|---|---|---|---|---|---|---|---|---|
| Acrobotics 2509.02727v2 | 본문 표기 없음 (S2 venue 「Towards Autonomous Robot...」, 잘린 표기) | ANYmal · Isaac Gym · **실기 없음** | 시뮬 elevation map 34x31 (1.6 x 1 m) → CNN 32 + proprio 이력 10 → MLP | 1 (평지 1k iter 사전학습 뒤 20k iter) | 속력 [0.4, 0.8] + oracle heading 2개 | gap 0.1~1.0 m (20 수준) | 지형별 성공 확률 Fig. 3 (그림). Table 2 변형 Barkour 완주 99.61 % (30회, gap 없는 코스). 같은 조건 Extreme Parkour teacher 0.00 | Google Drive 보충자료 | 논문 확인 (3 · 4) |
| ES-Parkour 2503.09985v2 | 표기 없음 (S2 venue IEEE 국제학회, 이름 잘림) | 로봇 미확인 · IsaacGym · **실기 없음** | 시뮬 event camera (depth → event 변환) → spiking ResNet-18 + GRU → spiking MLP | 2 (Extreme Parkour 식 ANN teacher → SNN student 증류 + 상호작용) | Extreme Parkour 식 | gaps · steps · hurdles · parkour | 시나리오 4개 성공률 Fig. 5 (그림) | 없음 | 논문 확인 (II · III) |
| ANYmal Parkour 2306.14874v1 | Science Robotics 2024 (참고문헌 표기) | ANYmal-D · 이름 본문 없음 | RealSense 6 + Velodyne → 학습형 voxel 재구성 → 2.5D elevation map | 3 모듈 (기술 정책 5 · navigation · perception) | 목표 위치 · heading · 시간 | jump 기술: 상자 사이 gap 최대 1 m | 기술별 성능 Fig. 4 (그림) | 없음 | 논문 확인 (II · IV) |
| SF-TIM 2408.00486v2 | IROS 2025 (주석) | Lite3 · X30 · Isaac Gym | LiDAR + Fast-LIO2 + EKF 200 Hz → elevation map (측정) + 상상 추정 | 1 | v_x · v_y · ω_z (gap · platform 지형은 전진) | gap 폭 0.2 + 0.035 l m (Lite3, l = 0~9) | Table V 시뮬 platform L6/L9 (gap 단독 없음). 실기 Lite3 40 cm gap 2회 연속 (Fig. 6) | 프로젝트 페이지 | 논문 확인 (III · IV) |
| KiVi 2509.23650v3 | IROS 2026 (참고문헌 표기) | Lite3 · **Isaac Lab** | D435i → visuospatial latent 20 (MemTransformer) + kinesthetic 31 | 1 | 속도 | gaps (자체 지형), 치수 그림 | Table III 실기 각 5회: high platform · 장애물 · 풀 · 카메라 가림 5/5. gap 숫자 없음 | 없음 | 논문 확인 (III · IV) |
| SWAP 2606.19928v1 | 표기 없음 | Apollo (72 kg) · Isaac Gym | depth → 대칭 equivariant RSSM latent | 1 | 속도 (상한 3.0 m/s 까지 curriculum) | gap 최대 3.0 m, 디딤돌 없음 (저자 한계로 명시) | 시뮬 Fig. 3 점마다 1500 trial (그림). 실기 2.13 m gap (시행 미기재) | 프로젝트 페이지 | 논문 확인 (III-D · IV) |
| APT-RL 2607.13579v1 | Science Robotics 2026 (주석 · S2) | KAIST HOUND · Isaac Gym | depth CNN 32 + 2D LiDAR 45 bin → GRU (student). 토크 = TO 학습 decoder + PD 잔차 | 3 (TVAE 사전학습 → RL → 지각 증류) | v_x [-1, 7] · v_y [-1, 1] · heading | 디딤돌 · gap 포함, 치수 보충자료 | Fig. 8 시뮬 100 agent x 10 (그림). 실기 디딤돌 · gap 통과 (시행 미기재) | Zenodo (데이터 · 그림 코드) | 논문 확인 (2 · 4) |
| StairMaster 2606.25765v2 | 표기 없음 | **Go2** · Isaac Gym | D435 10 Hz → cross-attention + spatial LSTM | 3 (teacher → 증류 → PPO fine-tune) | 속도 | 구멍 뚫린 계단 (디딤판 사이 빈 공간) 최대 55° | Table 3 실기 계단마다 30회: 37° 93.33 % · 55° 63.33 % (Extreme Parkour 0 · Go2 내장 RL 46.67 / 0) | 프로젝트 페이지 | 논문 확인 (Method · Experiments) |
| Multi-view depth 2511.22744v1 | 표기 없음 | **Go2** · Isaac Gym · 실기 없음 | 자기 D435i + 외부 시점 depth → CNN + GRU | 2 (Extreme Parkour 틀) | waypoint + 속력 | Extreme Parkour 지형 | Table 2 (256 run x 25 지형, 4종 혼합): 자기 시점만 TSR 61.02 %. gap 단독 없음 | anonymous.4open.science | 논문 확인 (3 · 4) |
| MoE parkour Go2 2604.19344v1 | 표기 없음 | **Go2** · Isaac Gym | D435f 15 Hz → GRU 512 student | 2 (Extreme Parkour 틀, actor MoE top-4/16) | v_x U(0.3, 0.8) + heading | Extreme Parkour 지형 | Table III 실기: 32 cm 상자 MoE 10/10. gap 없음 | osf.io | 논문 확인 (III · IV) |
| REDACT 2609.25450v1 | 표기 없음 | **Go2** · Isaac Gym | D435i → residual encoder + consensus gate + GRU | 2 (multi-query teacher → student) | Extreme Parkour 식 | Extreme Parkour 지형 | 시뮬 4 지형 혼합 SR (gap 단독 없음). Table IV 실기 hurdle 5/5 · pillar hurdle 5/5 · 통나무 7/10 | 프로젝트 페이지 | 논문 확인 (III · IV) |
| SABER 2609.21572v2 | 표기 없음 | Unitree B2 · mjlab | LiDAR 3 + 분할 → 41x21 [x, y, z, 금지비용] → cross-attention + 발 거리 bias | 1 | 속도 (조이스틱) | 의미 디딤돌 (일부 돌 금지) | Table III 시뮬 5 지형 x 256 x 10: 금지 접촉 1.04 / ep · success 0.908. gap · 돌 성공률 따로 없음 | 프로젝트 페이지 | 논문 확인 (III · IV) |

### 1-C. 계층 · 모델 기반 (관절 정책이 지도를 직접 보지 않거나 RL 이 관절을 직접 내지 않음)

| 방법 · 판 | 게재 | 로봇 · 시뮬 | 구조 | 관절 쪽이 받는 지형 정보 | gap · 돌 숫자 | 코드 | 근거 |
|---|---|---|---|---|---|---|---|
| DTC 2309.15462v2 | Science Robotics 2024 (참고문헌 표기) | ANYmal C · D · 이름 본문 없음 | elevation mapping + TAMOLS 궤적 최적화 + RL tracking 정책 | foothold xy · 목표 관절각 · 현재 발 → 목표 선 위 height scan | 실기: 0.1 m gap 10/10 · 0.6 m gap 4개 연속 4/4 · 1.8 m beam 4/4 · 0.2 m 돌 2 m 구간 10회 통과 | 없음 | 논문 확인 (Results · Methods) |
| Kim et al. High-speed discrete terrain 2506.02835v1 | Science Robotics 2025 (journal_ref) | Raibo · RaiSim | 표본 기반 foothold planner + RL tracker (CVAE 지형 생성기와 경쟁 학습) | 다음 2개 foothold 목표 벡터 (지도는 planner 만, 실기는 미리 얻은 지도 + Vicon) | 실기 1.3 m gap, 돌 위 4 m/s. 실패 요인 시험 각 5회 5/5 | 없음 | 논문 확인 (전문) |
| Agile Continuous Jumping 2409.10923v2 | ICRA 2025 (참고문헌 표기) | Go1 · IsaacGym | depth → heightmap predictor → RL motion policy (보행 주파수 · 발 잔차 · 몸 속도) → 모델 기반 저수준 | 몸 · 발 기준 궤적 (RL 은 관절을 직접 안 냄) | 실기 gap 80 cm · 14계단 4.5 s. 실기 4 지형 중 3개 100 %, 1개 20 % (시행 미기재) | 프로젝트 페이지 | 논문 확인 (III~VIII) |
| Learning to Jump from Pixels 2110.15344v1 | CoRL 2021 (주석) | Mini Cheetah · PyBullet | depth RL 고수준 → MPC + WBIC | 몸 궤적 · 접촉 일정 | 실기 depth 로 16 cm, mocap + GT 지도로 26 cm (본문). 시뮬 Table 1 | 프로젝트 사이트 | 논문 확인 (전문 grep + 실험) |
| Coholich et al. HRL value optimization 2506.20036v1 | 표기 없음 | Aliengo · Isaac Gym · 실기 없음 | LLP (PMTG, 발 주변 scan) + HLP (LLP value 위 최적화) | 발자국 목표 + 발 주변 scan (시뮬 GT) | Fig. 4~6 (각 5 rollout, 그림) | 개인 페이지 「code」 | 논문 확인 (전문) |
| Akizhanov et al. Feasible transitions 2407.11788v2 | L4DC 2025 (참고문헌 표기) | Go2 · MuJoCo (RL 재현은 Isaac Lab) | MCTS 접촉 계획 + NMPC + 학습 분류기 | 해당 없음 (모델 기반) | 돌 7~9.7 cm, 환경당 100회 (Fig. 3, 그림). Go2 RL 재현 서술은 요약 5번 | 없음 | 논문 확인 (2~4) |

### 1-D. 참고 (지각은 있으나 gap · 디딤돌 없음)

| 방법 · 판 | 게재 | 사실 | 근거 |
|---|---|---|---|
| PGTT 2510.18348v2 | 표기 없음 | **Go2 실기**, 내장 **L1 LiDAR + Point-LIO** → elevation map → 11x9 heightmap (1.1 x 0.9 m). MuJoCo MJX, **RTX 5070 1장**. 계단 (2~9 cm 위주) · discrete obstacles 만. 시뮬 1000 robot x 5 시드 계단 성공 83.4 %. 코드 GitHub (NtagkasAlex/phase_guided_terrain_traversal) | 논문 확인 (초록 · III · IV) |
| Resource-constrained quadrupeds 2505.12537v2 | ICRA 2025 (주석) | 개조 Go1, D435 + Flexx2 ToF + VIO, GPU elevation mapping 2.5 cm → 77점. Isaac Gym 60k iter 15 h. 30 cm 계단만. 코드 GitHub (ETH-PBL/elmap-rl-controller) | 논문 확인 (III · IV) |
| ADAPT 2603.16328v1 (휴머노이드) | 표기 없음 | G1, Mid-360 + Fast-LIO2 + elevation mapping, 수평 고도 + 수직 거리 지도, 감지 반경을 정책이 고름. Isaac Gym. hurdle · beam · gate 등, gap · 디딤돌 숫자 없음 | 논문 확인 (III · IV) |

---

## 2. 방법별 상세

항목 순서는 고정이다: 판 · 게재 / 로봇 / 배포 센서 / 관절 정책이 지형을 보나 / 지형 표현 / 학습 단계 / 명령 / 시뮬 / 학습 gap · 돌 / 숫자 / 코드 / Go2 / 재구현에 빠진 것. 각 항목 끝 괄호는 근거 절이다. 로봇이 Go2 가 아니면 「Go2: 아니오」는 생략했다(1절 로봇 열). 「재구현에 빠진 것」은 이 절 끝 표에 모았다.

### DELTA (Park, Jung, Hwangbo · KAIST)
- 2608.22033v1 (2026-08-22) · ICRA 2027 제출 (주석). 로봇 RAIBO2 실기.
- 배포 센서: RealSense D430 앞 · 뒤 2대, 로봇 중심 2.0 x 1.2 m 지도를 41x25 격자로. NaN 채움 · spike 제거 외에 학습형 재구성 · inpainting 없음. Jetson AGX Orin, TensorRT 100 Hz. 지도 융합(odometry) 방식은 본문에 없음. (III-F)
- 지형을 본다: 예. 지도 HxWx3 (x, y, z) → DELTA encoder: proprio 로 만든 query 가 표본 위치를 예측(offset) → 3x3 scout patch 로 위치 보정 → 9x9 patch 를 중심 3x3 · 주변으로 나눠 gate → multi-head cross-attention, L 3 · D 64 · head 4 · K 8. encoder 비용이 지도 해상도와 무관. (II · Table I)
- 학습: 단일 단계 PPO, encoder · actor [256, 128] · critic [512, 256, 128] 함께, actor 는 잡음 관측 · critic 은 깨끗한 관측을 같은 encoder 로. RaiSim, 200 env, 에피소드 4.0 s, 시뮬 400 Hz · 정책 100 Hz, 30000 iteration, RTX 4060. (II-C · III-A)
- 명령: 속도. 평가 v_x 1.0 m/s, ω_z U(-0.5, 0.5). 학습 범위는 본문에 없다. (III-B)
- 지형: 연속 5종 + 이산 3종 (Gaps · Stepping Stones · Grid Stones), env 마다 stage 1~10, 2연속 성공 승급 · 3연속 실패 강등, stage 10 에서 20 % 로 1 로 · 나머지 6~10 재표본, 성적 기반 지형 표본 비율. 치수는 없다(fine-grained 돌은 반경 절반). (II-C · Fig. 3)
- 숫자: Table II 시뮬 (5 고정 시드 x 200 = 1000 episode, stage 10, 3.2 m): DELTA Gaps 99.7 · Stepping Stones 99.5 · Grid Stones 98.5 · 연속 평균 94.6, AME 99.8 · 98.1 · 95.7 · 95.4, MLP 85.4 · 79.9 · 81.2 · 80.8. 90 % 지속 도달 iteration DELTA 2210 ± 160 vs AME 8890 ± 1475 (5 학습 시드). Table III fine-grained 돌: DELTA 84.0 (26x16) · 95.9 (41x25), AME 65.7 · 68.0. Table V 처음 보는 혼합 코스 4개 (평가 전용 타원 구멍 · 곡선 gap 포함): DELTA 평균 96.6, AME 26.0, MLP 3.5. 실기: 7코스 x 3회 21/21 (gap 2개 · 3개 · 15x15 cm 돌 · 복합 4), gap 10~20 cm, 돌 간격 15 cm. (III · Table II~V · Fig. 5)
- 코드: 없음. Go2: 아니오.
- 재구현에 빠진 것: 보상 항목 · 가중치(「RAIBO2 틀 [23] 을 따름」, [23] 은 Research Square 프리프린트), PPO 설정, 명령 학습 범위, gap · 돌 수준별 치수, 실기 지도 융합 방식. `논문 확인`

### WTR · Walking with Terrain Reconstruction (Yu et al. · ZJU)
- 2409.15692v2 (2025-03-03). 게재 표기 없음. 로봇 DEEP Robotics Lite3 실기.
- **START (2512.13153, 여섯 편 중 하나)와의 관계**: 1저자 · 교신저자 · 연구비 번호가 같고, 실기 표의 숫자가 같다(WTR Table III Proposed = START Table II: 디딤돌 1.0 · beam 0.8 · stepping beams 1.0 · gap 1.0, 그 밖의 ablation 열도 같은 값). START 참고문헌 41개에 WTR 은 없다. 같은 연구의 앞선 arXiv 판으로 보이지만 `미확인 (추정)`. 지형 깊이처럼 값이 다른 곳도 있다(START [0.2, 0.7] m · WTR [0.3, 0.7] m).
- WTR v2 에는 PAPERS 문서가 START v1 에 「없음」이라고 적은 값들이 있다: proprio 이력 H1 = 10, Table V 층 크기 전부(depth CNN [32, 64, 64] kernel [7, 7, 3, 3] stride [4, 4, 2, 2] · MLP [64, 64] · GRU 1층 128 · rough decoder MLP [128, 256] · proprio encoder MLP [256, 128] + GRU 128 · heightmap CNN [32, 64] · self-attention [256, 256] token 64 head 1 · 추정 MLP [64, 128] · actor · critic [512, 256, 128] ELU), 지형 치수(부록 B), feet edge 거리 [2.5, 5.0] cm · 계수 [1.0, 0.5]. 이 값이 START 와 같은지는 `미확인`. (II · 부록 A~D)
- 배포 센서: 머리 D435i 10 Hz, Jetson Orin NX TensorRT, 행동 50 Hz. 지형을 본다: 예(재구성 지도 → CNN → transformer 융합). (III-A · II-A)
- 학습: 단일 단계 + AdaSmpl(GT 지도를 확률 tanh(CV(R)) 로 대신 넣음), terrain progressive curriculum. Isaac Gym. (II)
- 명령: 전진 [0, 1.5], 횡 0, 0.3 미만은 0, 0 일 때 yaw [-1.2, 1.2]. (II-C)
- 지형(부록 B): 돌 0.5→0.2 m, 틈 x 0.175→0.25 · y 0.1→0.175 m, 돌 · 줄 위치 무작위 0→0.48 x 틈, balance beam 최소 0.175 m, stepping beams 폭 0.15 · 틈 0.275 m, gap 0.1→0.7 m, 깊이 [0.3, 0.7] m, 높이 ±5 cm.
- 숫자: Table III 실기 각 5회 (위). Table IV 시뮬 최고 수준 500회: 돌 0.99 · beam 1.00 · stepping beams 0.98 · gap 0.98 (발 주변 지도 추정을 뺀 판 0.90 · 0.95 · 0.92 · 0.98). Table II 재구성 MAE: 돌 5.21 cm · gap 2.39 cm.
- 코드: 없음. Go2: 아니오.
- 재구현에 빠진 것: PPO 설정, DR 값, p_max · T_start · T_end, AdaSmpl CV 창, 에피소드 길이. `논문 확인`

### PUMA (Wang et al. · ZJU · TeleAI)
- 2601.15995v2 (2026-07-13) · RA-L (본문: 2026-06-25 채택). 로봇 Lite3 실기 (RK3588, 50 Hz, PD 20 / 0.5).
- 배포 센서 D435i 10 Hz. 지형을 본다: 예. PIE 식 estimator(depth CNN + proprio 이력 → self-attention → GRU → MLP head)가 앞발 두 개의 foothold prior f = (왼 · 오른 앞발에서 목표 foothold 까지 거리, 현재 · 다음 foothold 방향 heading 오차), 속도 v̂, latent 64 를 내고 actor 가 받는다. (III-B)
- foothold 후보는 지형 기하 anchor(돌 중심 · 벽면) + 1 m 간격 보간, 가장자리 d_safe 이내 제외. 운동학 가능성 검사는 하지 않는다. (III-A)
- 학습: 단일 단계 asymmetric AC, PAS (GT prior → 예측, p_t = 1 - cos(πt / 2T)), multi-critic 3그룹(task 3 · foothold 1.5 · reg 1.0). Isaac Gym 2048 env, RTX 4090, Warp depth 렌더. (III · IV-A)
- 명령: 속도 추종 + foothold 보상. 평가 1.5 m/s 고정. 학습 범위 본문에 없음.
- 지형: Wall-assisted Gap · Surmounting · Stepping Stones, 치수 표 없음.
- 숫자: 위 본표. ablation: foothold prior 없이 돌 69.6 · 벽 gap 60° 54.7.
- 코드: 프로젝트 페이지(puma-parkour.github.io). Go2: 아니오.
- 재구현에 빠진 것: 지형 치수, d_safe · ε · T, 층 크기, 명령 범위. 실기 디딤돌이 0.5~0.8 m 로 크다(Lite3 기준). `논문 확인`

### CTS-MoE (Affonso et al. · UIUC · USP)
- 2606.19633v1 (2026-06-17). 게재 표기 없음. 로봇 Go1 실기 (머리 D435i 약 30° 하향, Jetson Xavier NX 50 Hz, Kp 28 · Kd 0.65, 2차 저역통과 12 Hz). (부록 C)
- 시뮬: **Isaac Lab + RSL-RL 수정판**, A40 4장 15000 iteration 약 72 h. (5)
- 구조: CTS 단일 단계. teacher encoder = privileged MLP [512, 256] + heightmap MLP [512, 256] → LN 32. student encoder = proprio 이력 MLP [512, 256] + depth CNN [16, 32, 64] → GRU 256 → LN 32. env 비율 teacher 0.85 · student 0.15, student 는 distillation loss 로만 학습. actor = dense MoE (expert E = 6, router MLP [512, 256], expert [512, 256, 128]), 입력 z ⊕ proprio. critic = 과제마다 value head (N 개, [512, 256, 128]), PopArt 과제별 return 정규화, 과제별 advantage 정규화. router 손실(균형 2e-3 · entropy 5e-4 · logit 1e-5). 과제 ID 는 보상 · critic 선택에만 쓰고 배포 routing 은 지각으로만. (4 · 부록 A · B Table 6 · 8)
- 지형을 본다: 예(student depth latent 가 router 와 expert 에 들어감).
- 명령: 속도 과제 v_x [-1, 1] · v_y [-0.5, 0.5] · ω_z [-0.8, 0.8]. gap · 장애물 과제는 v_x [0, 1] 전진만 + 명령에서 투영한 waypoint 근접 보상(속도 추종 대신). 평가 v_x ∈ {0.5, 0.75, 1.0}, ω 0. (부록 B · 5)
- 보상 Table 7 (과제별 가중 전부), PPO Table 8 (clip 0.2 · lr 1e-3 · γ 0.99 · λ 0.95 · KL 0.01 · epoch 5 · mini-batch 4 · entropy 0.005).
- 지형 Table 9: 계단 0.02~0.22 m, **gap 0.05~0.50 m**, 장애물 0.05~0.50 m, 7x6 격자 · 8x8 m patch · 6 수준, 성공 시 80 % 승급 · 20 % 무작위 하향, 실패 시 강등(10 % 기본으로). 처음 보는 지형 rough · slope.
- 숫자: Table 3 (명령 3종 x 15 episode 평균, 난이도 6 수준을 어떻게 묶었는지 본문 불명확): Gaps 98.3 · 69.0 (CTS-Single, depth) · 40.0 (Blind CTS-MoE) · 40.3 (Blind CTS). Climb Up 87.0 · 76.7 · 63.3 · 78.0. Table 2 추적 오차 η, gap 4~5 수준 0.32 vs blind CTS 0.99. Table 10 curriculum 최고 수준(6 만점) Cross Gap student: 6.00 · 6.00 · 4.15 · 3.95 (teacher 는 모두 6.00). 실기 과제당 10회 (Fig. 5, 숫자 본문 없음).
- 코드: 프로젝트 페이지(cts-moe.github.io). Go2: 아니오(Go1). Isaac Lab: 예.
- 재구현에 빠진 것: 관측 표(Table 4)는 이번에 읽지 않았다(`미확인`), depth 해상도 · FoV, DR 값은 「[29] 를 따름」. `논문 확인`

### DAWN (2609.29092)
- 2609.29092v1 (2026-09-24). 게재 표기 없음. 로봇 Go1 실기 (D435i 내장 필터 전부 끔 · raw depth, Jetson NX).
- 시뮬 **Isaac Lab** 4096 env, 50 Hz, depth 64x64 를 0.1 s 마다. (IV-A)
- 구조: WMP(아래) 의 RSSM world model 과 정책 학습 절차는 그대로 두고 학습 신호만 바꿈: 잡음 depth 입력에 깨끗한 depth 재구성 목표(denoising) + contrastive 정렬. D435i 잡음 모델(Gaussian σ 0.01 m, 가장자리 dropout P_max 0.6, 먼 거리 입자 r_p 0.003). (III · IV-A)
- 지형을 본다: 예(world model latent). 명령: 속도 추종(TE 보고), 범위 본문 미확인.
- 지형 4종 x 5 수준: slope 6~22° · stair 6~18 cm · **gap 10~90 cm** · step 10~54 cm.
- 숫자: Table II (3 시드 x 100 episode, 수준 평균, 잡음 x 1.0): Gap Blind 26.2 · Extreme Parkour 83.5 · WMP 88.6 · WMP + 잡음 93.7 · DAWN 97.2 · Oracle 98.8. 실기(난이도마다 10회): 실내는 세 방법 비슷(가장 어려운 70 cm gap 에서 90 %), 실외 70 cm gap DAWN 60 % · WMP + 잡음 40 % · WMP 30 %. (IV-B · IV-H)
- 코드: 프로젝트 페이지(dawn-parkour.github.io). Go2: 아니오. Isaac Lab: 예.
- 재구현에 빠진 것: 층 크기 · PPO (WMP 참조), 명령 범위, gap 수준 개별값. `논문 확인`

### Robot Parkour Learning (Zhuang et al.)
- 2309.05665v2 · CoRL 2023 (주석). A1 · Go1 실기, D435, Jetson NX, depth 48x64 10 Hz, 정책 50 Hz, Kp 50 · Kd 1, 토크 25 Nm 제한. IsaacGym. (3.3 · 4)
- 학습: 기술별 GRU 정책 5개(privileged 시각 = 장애물까지 거리 · 높이 · 폭 · 종류 one-hot, + 물리)를 soft dynamics(관통 허용) RL 로 pre-train → hard dynamics fine-tune → DAgger 로 depth CNN + GRU 단일 정책. 배포 정책이 depth 를 본다. (3.1 · 3.2)
- 명령: 목표 속력 약 1 m/s (방향 · 정지 명령 없음).
- 지형: leap gap 학습 [0.2, 0.8] · 시험 [0.3, 0.9] m (Table 1). 디딤돌 없음.
- 숫자: Table 2 시뮬 (100회 x 3 시드, 시험 범위): Leap 80 %, Blind 0 %, MLP 1 %. 실기 10회: 0.60 m gap 80 % (4.2).
- 코드: 프로젝트 페이지. Go2: 아니오.
- 재구현에 빠진 것: 하이퍼파라미터는 보충자료(본문 없음). `논문 확인`

### SoloParkour (Chane-Sane et al.)
- 2409.13678v1 · CoRL 2024 (주석). Solo-12 실기, Raspberry Pi 5, RealSense D405 48x48 30 Hz. IsaacGym, RTX 4090 20 h 미만.
- 학습: stage 1 heightmap + 천장 높이 privileged PPO + CaT(constraints as terminations) → stage 2 depth 정책을 DDPG 계열 off-policy RL(RLPD, REDQ)로, privileged 경험 버퍼와 온라인 버퍼를 반씩, critic 은 privileged. 증류(DAgger) 대신 RL. (3.2)
- 명령: x-y 속도(방향 진행 · 속도 상한 보상).
- 숫자: Table 1 실기 (2 학습 시드 x 장애물당 10회): step 85 % · leap 70 % (35 cm gap, 몸길이 78 %) · crawl 100 %. 시뮬 Fig. 4 (4 시드, 그림): leap 에서 DAgger · BC 보다 높다(본문).
- 코드: 프로젝트 페이지. 재구현에 빠진 것: 지형 치수(그림), 보상 세부. `논문 확인`

### Parkour in the Wild (Rudin, He, Aurand, Hutter)
- 2505.11164v1 · IJRR 2026 (JEPLO · REDACT 참고문헌 표기). ANYmal-D 실기, D435i 4대(앞 2 · 뒤 2) depth 48x32, onboard CPU 50 Hz, LiDAR · 외부 센서 안 씀. (2 · 3.6)
- 학습: expert 9개(walk, climb, climb down, jump, tables, rock pile, low wall, beams, stepping stones; elevation map 입력, 기술마다 curriculum · 보상 따로) → DAgger 로 depth CNN + LSTM student → RL fine-tune(정책 동결 상태로 critic 먼저 학습, 실제 잔해 3D scan 지형 추가). 배포 정책이 depth 를 본다. (2.1~2.3)
- 명령: 목표 위치 · heading · 남은 시간.
- 숫자: Table 4 시뮬 1000 rollout (최대 난이도 90 %): π_RL Stepping stones 98.8 · Beams 99.5 · Jump 98.0 · Gap-climb (처음 보는 지형) 82.0 · Down-stones (처음 보는) 54.4 → 그 지형으로 다시 fine-tune 92.4. 증류만 한 π_D 는 stepping stones 73.0 · gap-climb 10.2. 저자 한계: Beams · Stepping stones 에서 헛디딘 뒤 빨리 회복하는 경향(정밀도 부족). (3.1 · 4.3)
- 코드: 없음. 시뮬레이터 이름 본문 없음. AME-2 비교 기준 [48].
- 재구현에 빠진 것: expert 9개의 개별 보상 · curriculum, 지형 치수. `논문 확인`

### Zhang et al. · Learning Agile Locomotion on Risky Terrains
- 2311.10484v2 · IROS 2024 (주석). ANYmal-D 실기. Isaac Gym, 4096 env, 48 step/iter, actor · critic MLP (512, 256, 128), heightmap 25x16 · 7 cm. (II · 부록 Table V)
- 배포: 실기 지형 · 상태를 **mocap + GT 지도**로 줌(저자가 지각을 다루지 않는다고 명시). 정책은 지도를 본다. (I · V)
- 명령: 목표 위치 + heading (navigation 형식). 속도 추종 판은 level 4(sparsity 약 40 %) 이후 90 % 미만(본문).
- 학습: generalist(Stones-Everywhere 8000 iter) → specialist fine-tune(Stones-2Rows 2000 · Balance-Beams 3000 · Stepping-Beams 1000). RND curiosity · 대칭 augmentation · 완화된 curriculum. (II · IV-C)
- 지형: 본표의 Table I 값. 숫자: 본표. 5 cm odometry drift 에 넘어질 수 있다(본문).
- 코드: 없음. Go2: 아니오. Go2 재현 기록은 Akizhanov et al. (요약 5번).
- 재구현에 빠진 것: Stones-2Rows 등 specialist 지형 치수, 실기 지각 경로. `논문 확인`

### AME-1 · Attention-Based Map Encoding (He et al.)
- 2506.09588v1 (2025-06-11, 「peer review 전 원고」 주석) · Science Robotics 10(105) eadv3604, 2025 (AME-2 · DELTA 참고문헌 표기). ANYmal-D + Fourier GR-1 실기.
- 배포: ANYmal-D 는 onboard elevation mapping(Miki GPU)을 Jetson 에서, 정책은 i7 CPU. GR-1 은 mocap + 미리 만든 지형 mesh ray-casting. 센서 기종은 본문에 없다. (Deployment)
- 지형을 본다: 예. map scan LxWx3 (ANYmal 26x16, GR-1 17x11) → CNN 2층(kernel 5, 16 → d-3) + 좌표 → 점별 특징, proprio 선형층 → query, MHA(d 64, head 16).
- 학습: 2단계(base 지형 완전 지각 18000 epoch → fine-tune 지형 + 잡음 · drift 3600 epoch), 4096 env, A100 6일. teacher-student 가 아니라 같은 정책 미세조정. PPO Table S1 (batch 24x4096, mini-batch 8x4096, epoch 5, clip 0.2, entropy 0.005/0.002, γ 0.99, λ 0.95, KL 0.01). 보상 Table 2 (14항). (Methods · 보충)
- 명령: 속도 추종(범위 본문 없음). 지형: 본표. 숫자: 본표(지형별 값은 Fig. 6).
- 코드: 없음(Zenodo 14499786 은 그림 재현 데이터). AME-2 는 이 설계를 바탕으로 한다(AME-2 본문).
- 재구현에 빠진 것: ANYmal 격자 간격, 수준별 치수, 명령 범위, 시뮬레이터 이름. `논문 확인`

### Footmap (Hwang et al. · U. Tokyo)
- 2604.02744v1 (2026-04-03). 게재 표기 없음. A1 모델 시뮬만(legged_gym · Isaac Gym, 4096 env, RTX 4090 약 25 h). sim-to-sim: Gazebo A1 + Ouster OS1-128 + elevation_mapping 으로 20 cm gap · 20 cm 계단 (Fig. 10, 시행 미기재). 실기 없음. (IV · VII)
- 정책 입력: proprio 48 (선속도 포함) + GT heightmap 1.0 x 1.6 m · 0.1 m (17x11) + 발 위치 map(발마다 Gaussian, w 10 · σ 0.1, 배포는 FK) → CNN + MHA (AME-1 구조, d 64). 단일 정책. (III-A · III-B)
- 명령: 「global velocity tracking」. 국소 속도 명령이면 디딤돌을 피해 출발 단 안에서 원을 그리는 보상 꼼수가 생겼다고 보고(Fig. 9). (III-D · VI-C)
- 보상 Table II + CoP 안정 보상(지지 다각형 경계까지 최소 거리). PPO Table VIII, DR Table VII (heightmap drift ±0.05 m).
- 지형: 본표. 숫자: 본표. 안정 보상 ablation Table V: 없음 74.6 · CoM 73.7 · CP 66.8 · CoP 77.0.
- 코드: 프로젝트 페이지(mhwang003.github.io/footmaplocomotion, arXiv 주석). 코드 여부 `미확인`.
- 재구현에 빠진 것: 명령 범위, 수준 0 · 9 외 치수, 실기 경로. `논문 확인`

### Foot ToF · Learning Locomotion on Discrete Terrain via Minimal Proximity Sensing (Fan et al. · ETH)
- 2606.31912v2 · IROS 2026 (주석). ANYmal-D 실기, 발마다 VL53L5CX ToF (4x4, 45° x 45°, 60 Hz, 지연 20~60 ms). Isaac Gym, LSTM 정책, PPO. (II)
- 지형을 본다: 예, 다만 지도가 아니라 발 아래 근거리 16칸 x 4 발. 명령: 목표 위치(거리 · 방향). 보상은 프로젝트 사이트 보충자료(본문 없음).
- 학습 2단계(돌 위주 + 낮은 센서 열화 → 어려운 수준 + 계단 · beam · pyramid + 열화 상향).
- 숫자: 본표. 실기 평균 속도 0.52 m/s.
- 코드: 프로젝트 사이트. 재구현에 빠진 것: 보상, 지형 치수, 발 센서 하드웨어. `논문 확인`

### TACL · Trajectory-Level Automatic Curriculum Learning (Liu et al. · BIGAI)
- 2608.16164v1 (2026-08-17). 게재 표기 없음. 정책 구조 · 보상은 Extreme Parkour teacher 단계 그대로. 차이는 학습 과제 출처: 지도 위 waypoint 궤적을 CVAE + 난이도 evaluator + MH-MCMC 로 생성. Isaac Gym. (3 · 4.1)
- 배포: Extreme Parkour 파이프라인으로 depth student 증류 → **Unitree Go2 + D435i**. 실기 세부 · 결과는 부록이며 본문에 숫자가 없다. (4.1)
- 숫자(시뮬, teacher 단계, GT height): Map_HCL (Extreme Parkour 코드로 만든 steps · gaps · parkour · hurdles 10 수준) 최고 수준, 지형 8개 x 50 rollout: HCL-E(원래 손 curriculum) gap 5k epoch 78 % → 최종 30 %, TACL 24 → 96 %. 4 지형 평균 HCL-E 65.75 → TACL 84.25 %. (4.2)
- 사실로서의 요점: 같은 절차 · 다른 시드로 만든 시험 지형에서, 손으로 짠 curriculum + 고정 waypoint 판은 학습이 길어질수록 gap 성공률이 떨어졌다고 보고.
- 코드: 없음. Go2: 배포만. 재구현에 빠진 것: 부록(하이퍼파라미터 · 실기). `논문 확인`

### Extreme Parkour (Cheng et al. · CMU)
- 2309.14341v1 · ICRA 2024 (참고문헌 표기). A1 실기, D435 머리 10 ± 2 Hz → 58x87, Jetson NX (depth 10 Hz · 정책 50 Hz, depth latency 0.08 s 고정). 3090 1장 20 h 미만. 시뮬레이터 이름 본문에 없음. (4.1)
- 학습: phase 1 RL (proprio + scandots + waypoint heading + walk flag + 속력 명령, ROA 로 환경 추정) → phase 2 DAgger depth convnet-GRU student, heading 도 예측 (예측과 oracle 차가 0.6 rad 안이면 예측을 관측). (3.2 · 3.3)
- 명령: 속력 + 정책이 정하는 heading. 보상: world frame 내적 추종 min(<v, d_w>, v_cmd), 가장자리 5 cm 안 발 접촉 벌점. (3.1)
- 숫자: 본표. 이 계열을 Go2 로 옮기거나 Go2 에서 비교 기준으로 쓴 논문이 여럿이다(Multi-view · MoE parkour Go2 · REDACT · REAL · TACL 배포 · StairMaster 비교). 기준선으로 다시 돌린 숫자는 논문마다 크게 다르다: DAWN 시뮬 gap 83.5 %, REAL 시뮬 gap SR 0.10, PUMA 시뮬(teacher) 디딤돌 81.1 · 벽 gap 60° 77.2 %, Multi-view 시뮬 4지형 혼합 TSR 61.02 %, Acrobotics(ANYmal) 변형 Barkour 0.00, StairMaster 실기 구멍 계단 0 %. 설정이 서로 달라 직접 비교할 수 없다(대조 안 함).
- 코드: 논문은 프로젝트 페이지만. `논문 확인`

### Agarwal et al. · Legged Locomotion in Challenging Terrains using Egocentric Vision
- 2211.07638v1 · CoRL 2022 oral (주석). A1 실기, D435 (앞; 디딤돌 · gap 실험은 위쪽 카메라로 따로 증류), UPboard + Jetson NX 50 Hz. IsaacGym · legged_gym. (3)
- 학습: phase 1 scandots RL (monolithic GRU 또는 RMA) → phase 2 DAgger depth (convnet + GRU). 명령 (v_x, ω_z). (2)
- 숫자: 본표. 코드: 프로젝트 페이지. 재구현에 빠진 것: 보상 세부(부록 B), 실기 시행 수(그림). `논문 확인`

### WMP · World Model-based Perception (Lai et al.)
- 2409.16784v1 · ICRA 2025 (참고문헌 표기). A1 실기, D435i 60 Hz → 64x64, world model 0.1 s 간격, Jetson NX. legged_gym · Isaac Gym 4096 env. (IV-C · V-C)
- 학습: 단일 단계. RSSM(depth CNN + proprio MLP, GRU) 재구성 + KL, 정책은 proprio + sg(h_t), critic 은 scandots 등 privileged. AMP style 보상. 명령 (v_x, v_y, ω_z), waypoint 없음.
- 지형: slope 0~36° · stair 5~21 cm · gap 0~90 cm · climb 0~54 · tilt · crawl. 숫자: 본표. DAWN 이 이 구조를 그대로 쓴다.
- 코드: 프로젝트 페이지. `논문 확인`

### REAL (Go2)
- 2603.17653v1 (2026-03-18). 게재 표기 없음. **Go2 실기**, D435i 앞, onboard Jetson, C++/ONNX, 추론 13.1 ms. Isaac Gym, RTX 4080 약 30 h. 지형 · 난이도는 Extreme Parkour 정의 그대로. (IV-A)
- 구조: cross-modal teacher → student (FiLM 조절 Mamba, 10 프레임 이력) 증류, stage II 에서 BC 와 RL 손실을 일관성 기반 gating 으로 섞음. 물리 기반 Bayesian(Kalman) 속도 추정. (III)
- 숫자: 본표. gap 에서는 REAL(0.28)이 SoloParkour 재현(0.36)보다 낮다. 1 m 시야 가림 시험 Table IV. 실기는 높은 단 · 흩어진 상자 · 가파른 계단(Fig. 6, 시행 미기재), gap 실기 없음.
- 코드: 「will be released」 (jialonglong.github.io/REAL_wb). `논문 확인`

### NVM · Neural Volumetric Memory (Yang et al.)
- 2304.01201v1 · CVPR 2023 highlight (주석). Unitree A1 실기(본문 1장 · 부록), 앞 depth 하나. 2단계(privileged elevation map + GT 속도 teacher → BC), student 는 depth 이력을 3D feature volume 으로 바꾸고 pose encoder 로 SE(3) 정렬 + novel-view 자기지도 손실. (3 · 4)
- 숫자: 본표. HTML 변환에서 Table 2 의 NVM 행이 잘려 성공률을 확인하지 못했다(`미확인`). 실기 Table 4 의 단 사이 간격 단위가 HTML 에서 빠졌다.
- 코드: 프로젝트 페이지. `논문 확인 (일부 미확인)`

### LF2WB · Look Forward to Walk Backward
- 2603.03138v1 (2026-03-03). Lite3 실기 (RK3588, 앞 RealSense 10 Hz, 50 Hz). Isaac Gym. 단일 단계: delta-rule 선택 갱신 recurrent 기억(DeltaNet 계열) estimator + asymmetric AC. 보상 · DR · PPO 는 「[7] 을 그대로 따름」. (II · III)
- 명령: 전진 10 s 후 후진 10 s (고정 과제). 앞 카메라만으로 후진할 때 gap 을 기억에서 읽는다.
- 숫자: 본표. 실기 0.6 m 단 · 0.6 m gap · 조합 약 8 m 후진(시행 미기재).
- 코드: 없음. `논문 확인`

### PIE (Luo et al. · ZJU)
- 2408.13740v3 · RA-L 2024. Lite3 실기 (D435i 10 Hz, RK3588 onboard, 50 Hz). Isaac Gym 4096 env, Warp, 10000 iter 20 h 미만 RTX 4090. (III-C · IV-A)
- 단일 단계: actor [o_t, v̂, foot clearance ĥ^f, heightmap latent z^m, z]. estimator = depth CNN (H2 = 2) + proprio MLP (H1 = 10) → 공유 transformer → GRU. 손실 KL + MSE(o_{t+1}) + MSE(heightmap) + MSE(v) + MSE(h^f). PUMA · WTR 는 이 estimator 를 바탕으로 한다고 적고, KiVi 는 이와 비슷한 구조를 비교 기준(w/o Kin.)으로 쓴다. (III-B)
- 명령: 본문 「Lateral velocity [0.0, 1.5] m/s」(원문 그대로) · yaw [-1.2, 1.2].
- 지형: gap 최대 1 m, step · hurdle 0.75 m, stairs 0.25 m. 디딤돌 없음. 숫자: 본표.
- 코드: 없음. `논문 확인`

### ANYmal Parkour (Hoeller et al.)
- 2306.14874v1 · Science Robotics 9(88) 2024 (참고문헌 표기). ANYmal-D 실기, RealSense 6대 + Velodyne Puck, perception 은 Jetson Orin.
- 구조: perception(점군 → voxel encoder-decoder, 4 m / 12.5 cm + 2 m / 6.25 cm, 약 45 GB GPU 메모리) → locomotion 기술 정책 5개(입력 proprio + 재구성 점군에서 만든 2.5D elevation map + 위치 · heading · 시간 명령, map 을 최대 7.5 cm 이동해 교란) → navigation 정책(5 Hz, 기술 선택 + 국소 명령). jump 기술: 상자 사이 gap 최대 1 m curriculum. (IV-B)
- 숫자: 기술별 성능은 Fig. 4 (그림). 코드: 없음. `논문 확인`

### SF-TIM
- 2408.00486v2 · IROS 2025 (주석). Lite3 · X30 실기, LiDAR + Fast-LIO2 (10 Hz) + EKF 200 Hz → elevation map. 정책이 elevation map 측정과 DreamWaQ 식 상상(o_{t+1} · 높이 추정)을 함께 본다. 증류 없음, Isaac Gym 4096 env · GPU 5.7 GB · iter 1.1 s. (III · Table III)
- 명령 v_x · v_y · ω_z (gap · platform 지형은 전진만). gap 폭 Lite3 0.2 + 0.035 l m · X30 0.2 + 0.06 l m (l = 0~9). 숫자: 본표. 코드: 프로젝트 페이지. `논문 확인`

### KiVi
- 2509.23650v3 (2026-06-20) · IROS 2026 (REDACT 참고문헌 표기). Lite3 실기 (D435i 10 Hz, Jetson Orin NX Super). **Isaac Sim · Isaac Lab** 4096 env, 12000 iter 약 8 h RTX 4090. (III-C · IV)
- 단일 단계 asymmetric AC: actor = proprio 45 + kinesthetic latent 31 (이력 10 → 선속도 · 접촉력 명시 추정 + VAE z 20) + visuospatial latent 20 (depth + MemTransformer → 주변 고도 · 발 높이 표본 추정). gaps 지형 포함(치수 Fig. 3 G). 숫자: 본표(gap 숫자 없음). 코드: 없음. `논문 확인`

### SWAP
- 2606.19928v1 (2026-06-18). Apollo 사족(72 kg) 실기. Isaac Gym 6000 env + Warp, RTX 4090 약 10 h. WMP 계열 RSSM 을 반사 대칭 equivariant 로, actor equivariant · critic invariant. 속도 명령 상한을 curriculum 으로 3.0 m/s 까지. box 최대 1.9 m · gap 최대 3.0 m. 디딤돌은 한계로 명시. 카메라 기종은 본문에서 찾지 못했다(`미확인`). 숫자: 본표. 코드: 프로젝트 페이지. `논문 확인`

### APT-RL (KAIST HOUND)
- 2607.13579v1 · Science Robotics 2026 (주석 · S2). HOUND 실기. Isaac Gym. 2D 궤적 최적화 대량 데이터 → TVAE 잠재공간 + gait 별 토크 decoder → RL 정책이 latent action 16 + auxiliary action 12 (PD 잔차, Kp 80 · Kd 2) + gait 선택(2 Hz) → student 증류(depth CNN 32 + 2D LiDAR 45 bin → GRU, DAgger). 정책 teacher 의 지형 입력은 elevation map MLP. (4)
- 명령 v_x [-1, 7] · v_y [-1, 1] · heading [-1.4, 1.4] (2 m/s 넘으면 v_y 0). 지형에 stepping stones · gap 포함, 치수 보충자료. 숫자: Fig. 8 (그림). 실기 1.1 km 도심 · 0.34 km 숲 · 최고 6 m/s.
- 코드: Zenodo 20645964 (데이터 · 그림 생성 코드). `논문 확인`

### StairMaster (Go2)
- 2606.25765v2 (2026-07-29). **Go2 실기**, D435 10 Hz, Jetson Orin NX onboard 50 Hz, Kp 40 · Kd 1. Isaac Gym RTX 4090.
- 3단계: teacher(proprio + privileged heightmap, PPO) → student 증류(MSE; depth + proprio cross-attention + spatial-aware LSTM) → student PPO fine-tune. depth 잡음 모델(공간 · 센서 artifact, disparity, 진동). 보상: 3D waypoint 능동 시점(pitch) · hollow gap 운동학 벌점 · stair edge 벌점 · foothold. 명령: 속도. 지형: 디딤판 사이가 빈 계단, 최대 55°.
- 숫자: 본표 (depth 잡음 모델 없이 50.00 / 16.67 %).
- 코드: 프로젝트 페이지(sivan666666.github.io/StairMaster). `논문 확인`

### Multi-view depth (Rahem & Suleiman)
- 2511.22744v1. **Go2** 모델 시뮬만 (Isaac Gym, sim 200 Hz · 정책 50 Hz · depth 10 Hz). Extreme Parkour 틀(teacher scandots + ROA → DAgger student). student 는 자기 D435i 시점 + 외부(드론 가정) 시점 depth (87x58). 지형은 Extreme Parkour curriculum. 숫자: 본표. 코드: anonymous.4open.science/r/multiview-parkour-6FB8. `논문 확인`

### MoE parkour Go2 (Quadruped Parkour Learning: Sparsely Gated MoE with Visual Input)
- 2604.19344v1. **Go2 실기**, D435f 23° 하향 마운트, depth 15 Hz onboard 발행 · 정책은 외부 RTX 2060. Isaac Gym + legged_gym 수정판. Extreme Parkour 틀: phase 1 scandots MLP (128, 64, 32) + ROA → phase 2 depth GRU 512. actor 512 → MoE (top-4 / 16, 단순 행렬 expert) → 256, 256. v_x U(0.3, 0.8). 숫자: 본표 (MLP Large 5/10 · XL 9/10). 코드: osf.io (본문: 카메라 마운트가 공개 저장소에 있음). `논문 확인`

### REDACT
- 2609.25450v1 (2026-09-21). **Go2 실기** (Jetson Orin Nano, D435i 10 Hz, actor 50 Hz). Isaac Gym, L4, 15000 iter. Extreme Parkour 지형 · 보상 · DR 그대로. teacher multi-query cross-attention(entropy · overlap · slow 정규화) → student residual depth encoder + 24 cell 예측 + consensus gate(깨끗한 rollout 으로 conformal 99 % 문턱) + FSQ + GRU. 숫자: 본표. 하이퍼파라미터는 「project page 에 제공 예정」. `논문 확인`

### SABER
- 2609.21572v2. Unitree B2 실기 (LiDAR 3 + DLO + elevation_mapping_cupy + YOLO 분할 → 41x21 지도). 학습 mjlab, 4096 env, 23k iter, H200 약 34 h. 정책이 [x, y, z, 금지비용] 셀 토큰을 cross-attention 으로 보고, 발까지 거리에 따른 signed bias 를 attention logit 에 더한다. 의미 디딤돌(돌 사이 gap + 일부 돌 금지). 숫자: 본표. 코드: 프로젝트 페이지. `논문 확인`

### Acrobotics (4회차)
- 2509.02727v2 (2025-09-02 v1). ANYmal 시뮬만 (Isaac Gym, 1024 env, RTX 3060 약 4 h). actor · critic MLP (512, 256, 128), 행동 표준편차 상한 1.0. 입력: proprio 51 (선속도 · 각속도 · roll pitch · oracle heading 2 · 속력 명령 · 관절 · 이전 행동 · 발 접촉) + elevation map 34x31 점 (1.6 x 1 m, 앞으로 약간 이동) → CNN 32 + 이력 10 → CNN 20. (3 · 3.1)
- 지형 8종 20 수준 (Table 1): steps 0.1~0.8 · boxes 0.1~1.0 · stairs · **gaps 0.1~1.0 m** · inclined boxes · slopes · weave poles. 승급: 기대 거리 80 % 이상, 강등 40 % 미만. (3.2)
- 숫자: 지형별 성공 확률은 Fig. 3 (그림). 본문: 「95 % 난이도에서 climbing up 외 모든 장애물 약 90 % 이상」, gap 은 elevation map 앞쪽 범위(약 90 cm)에서 성능이 떨어진다고 서술. Table 2 변형 Barkour 완주 99.61 % (30회, ANYmal), 같은 반복 수의 Extreme Parkour teacher 0.00.
- 코드: Google Drive 보충자료(보상 구조 · 모델별 결과). `논문 확인`

### ES-Parkour (4회차)
- 2503.09985v2 (2025-03-13 v1). 시뮬만 (IsaacGym, student 학습 32 env, 3090 약 30 h). Extreme Parkour 식 ANN teacher(scandots · 목표 yaw) → spiking ResNet-18 + GRU + spiking MLP [512, 256, 128] student 로 증류(MSE 행동 + yaw), 입력은 depth 에서 만든 시뮬 event 영상 10 Hz. 지형 gaps · steps · hurdles · parkour. 숫자는 Fig. 5 (그림). 로봇 기종은 본문에서 찾지 못했다(`미확인`). 코드 링크 없음. `논문 확인`

### Shi et al. · Terrain-Aware Quadrupedal Locomotion via RL
- 2310.04675v2. 자체 로봇 Max 실기 (지형 정보는 mocap + 오프라인 지도), PyBullet. PMTG 계열(TG 주파수 · 발 높이 조정 + 관절 잔차 12), LSTM. 입력: 방향 명령 + proprio + 발마다 반경 0/3/6/10 cm 원 위 1/6/8/10 점 높이. foot terrain 보상(높이차 큰 곳 디딤 -1). 숫자: 본표. 코드: 없음. `논문 확인`

### DTC · Deep Tracking Control (Jenelten et al.)
- 2309.15462v2 · Science Robotics 9(86) 2024 (참고문헌 표기). ANYmal C (D435 4대 또는 Bpearl 2대) · ANYmal D (D435 8대). elevation mapping(Jetson) + TAMOLS(CPU, 약 400 Hz) + RL tracking 정책 50 Hz.
- 정책 관측: proprio + 계획기 출력(foothold xy · 착지 시 목표 관절각 · 접촉 상태 · 남은 phase 시간) + 현재 발 → 목표 foothold 선을 따라 뽑은 height scan + 참조 twist. 학습 4096 env, 90000 epoch(약 2주, 1일이면 배포 가능), 12 지형 x 10 수준. trot 고정. (Methods)
- 숫자: 본표. foothold 추적 오차 2.3 cm. AME-1 은 DTC 가 20x20 · 12x12 돌 · 15 cm beam 에서 20 % 미만이라고 보고(계획기가 작은 면을 디딜 수 없다고 판단). 코드: 없음. `논문 확인`

### Kim et al. · High-speed control and navigation on complex and discrete terrain (KAIST)
- 2506.02835v1 · Science Robotics 10(102) eads6192, 2025. Raibo 실기. RaiSim 300 env, 4.2 s, 2 ms · 10 ms.
- planner: 표본 → 성능 · spike · 충돌 filter(충돌 경계 MLP) → 후보 8개 physics rollout. tracker: proprio · 이력 · 다음 2 foothold 목표 벡터 · 경과 시간 · GRU 추정 선속도. 학습 지형은 연속 돌 10개, CVAE 지형 생성기가 tracker 성적(평균 9.3/10 돌)에 맞춰 난이도를 올린다. 실기 지각 없음(미리 얻은 지도 + Vicon; 이유: 고속 drift · 가림). 숫자: 본표 + 시뮬 지도 높이 오차 -5~12 cm 에서 90 % 이상(300 rollout). 코드: 없음. `논문 확인`

### Agile Continuous Jumping in Discontinuous Terrains (Yang et al.)
- 2409.10923v2 · ICRA 2025 (참고문헌 표기). Go1 실기, D435i, 외부 Mac Mini 추론. IsaacGym (저수준 제어기 PyTorch GPU 구현), PPO 8000 step 약 7 h + heightmap predictor DAgger 약 1 h. depth → heightmap predictor(CNN 3층 + GRU) → RL motion policy → 모델 기반 저수준. heightmap 무작위 이동(수평 ±8 · 수직 ±5 cm)이 실기 이전에 중요(ablation, 14계단 5회). 숫자: 본표. 코드: 프로젝트 페이지. `논문 확인`

### Learning to Jump from Pixels (Margolis et al.)
- 2110.15344v1 · CoRL 2021. Mini Cheetah 실기, D435 앞. PyBullet. depth RL 고수준(heightmap expert → depth BC, RNN) → MPC + WBIC. gap world. 숫자: 본표 + 시뮬 비제약 gait 66 cm. `논문 확인 (실험 절 · 본문 grep)`

### Coholich et al. · HRL and Value Optimization
- 2506.20036v1. Aliengo 시뮬만(Isaac Gym 4000 env x 100 step x 750 iter). LLP: PMTG 행동 15 + 발 주변 scan 관측, 발자국 xy 목표(trot). HLP: 학습 없이 LLP value 위 grid search(R 5 · B 15 cm) + gradient ascent 5회, 방향 항 κ 50. 지형: infill 80~100 % · 높이 0~10 cm. 숫자: 본표. 80 % infill 에서 전진 거리는 end-to-end 보다 짧다(본문). 코드: 개인 페이지(내용 `미확인`). `논문 확인`

### Akizhanov et al. · Learning feasible transitions for efficient contact planning
- 2407.11788v2 · L4DC 2025 (AME-2 참고문헌 [5]). Go2 모델, MuJoCo, 시뮬만. MCTS 접촉 계획 + whole-body NMPC + 학습 feasibility classifier · state predictor · target adjustment. 돌 7~9.7 cm. Go2 RL 재현 서술(요약 5번)은 4.3 절. `논문 확인`

### 재구현에 빠진 것 (논문만 보고 만들 때)

이번 읽기에서 본문 · 표에서 찾지 못한 것이다. 보충자료나 참조 논문에 있을 수 있다(그 경우 `미확인`). 「따로 필요」는 논문이 쓴 하드웨어 · 외부 모듈이다.

| 방법 | 본문에 없던 값 | 따로 필요 |
|---|---|---|
| DELTA | 보상 항목 · 가중치(RAIBO2 틀 참조), PPO 설정, 명령 학습 범위, gap · 돌 수준별 치수, 실기 지도 융합 방식 | 앞 · 뒤 depth 2대 |
| WTR | PPO 설정, DR 값, p_max · T_start · T_end, AdaSmpl CV 창, 에피소드 길이 | 없음 |
| PUMA | 지형 치수, d_safe · ε · PAS T, 층 크기, 명령 범위 | foothold anchor 생성 규칙 구현 |
| CTS-MoE | 관측 표(Table 4, 이번에 안 읽음), depth 해상도 · FoV, DR 값(「[29] 를 따름」) | 없음 |
| DAWN | 층 크기 · PPO(WMP 참조), 명령 범위, gap 5 수준 개별값 | 없음 |
| Robot Parkour Learning | 하이퍼파라미터 · 보상 계수 α(보충자료) | 기술별 privileged 시각 정보 정의 |
| SoloParkour | 지형 치수(그림), 보상 세부 | off-policy RL 구현(RLPD · REDQ) |
| Parkour in the Wild | expert 9개 각각의 보상 · curriculum, 지형 치수, 시뮬레이터 이름 | depth 4대, 실제 잔해 3D scan |
| Zhang risky | specialist 지형 치수 | 실기 지각 경로 없음(mocap) |
| AME-1 | 지도 격자 간격, 수준별 치수, 명령 범위, 시뮬레이터 이름 | onboard elevation mapping |
| Footmap | 명령 범위, 수준 0 · 9 외 치수 | 실기 경로 없음 |
| Foot ToF | 보상(프로젝트 사이트), 지형 치수 | 발 ToF 센서 하드웨어 |
| TACL | 하이퍼파라미터 · 실기 결과(부록) | Extreme Parkour 코드 기반 |
| Extreme Parkour | 지형 치수, 정규화 보상([4] 참조), 시뮬레이터 이름 | 없음 |
| Agarwal | 보상 세부(부록 B), 지형 치수 | 위쪽 카메라(디딤돌 · gap 실험) |
| WMP | 층 크기, 명령 범위 | 없음 |
| REAL | 명령 형식 세부, 시행 수 | 코드 미공개 |
| NVM | 명령, HTML 에서 빠진 표 값 | 없음 |
| LF2WB | 보상 · DR · PPO(「[7] 을 그대로」) | 없음 |
| PIE | 층 크기, PPO, 수준별 치수(최대만) | 없음 |
| Shi | 실기 지각 경로 | mocap · 오프라인 지도 |
| Acrobotics | 보상(보충자료) | 실기 없음 |
| ES-Parkour | 로봇 기종, teacher 세부 | event camera, 실기 없음 |
| ANYmal Parkour | 관측 · 보상(보충 S1 · S2) | depth 6 + LiDAR, 학습형 재구성 모듈(약 45 GB GPU 메모리) |
| SF-TIM | 층 크기 등(이번에 확인 안 함, `미확인`) | LiDAR + Fast-LIO2 + EKF |
| KiVi | 지형 치수(그림), 명령 범위 | 없음 |
| SWAP | 카메라 기종, 보상, 층 크기 | 없음 |
| APT-RL | 지형 · 보상 · 하이퍼파라미터(보충자료) | 2D 궤적 최적화 데이터 생성기, 2D LiDAR |
| StairMaster | 보상 가중치, 층 크기(`미확인`) | 없음 |
| Multi-view | (코드 링크 있음) | 외부 시점 카메라 |
| MoE parkour Go2 | 지형 치수(Extreme Parkour 따름) | 없음 |
| REDACT | 하이퍼파라미터(「project page 에 제공 예정」) | 없음 |
| SABER | mjlab 기본값 의존 부분 | LiDAR 3대, 의미 분할 모델 |
| DTC | TAMOLS 설정 · 보충자료 | 궤적 최적화 계획기(CPU) |
| Kim | planner 세부 · CVAE 구조(보충) | 실기 mocap · 미리 얻은 지도 |
| Agile Continuous Jumping | 저수준 최적 제어기 세부 | Go1 sysID |
| Jump from Pixels | MPC + WBIC | Mini Cheetah 제어 스택 |
| Coholich | (개인 페이지 코드) | 실기 없음 |
| Akizhanov | (모델 기반) | NMPC · MCTS |

---

## 3. 이미 다룬 여섯 편 (가리킴만, 이번에 새로 드러난 사실)

여섯 편 각각의 구조 · 숫자는 [PAPERS-architecture.md](PAPERS-architecture.md) 1~6절. 이번 조사에서 그 문서에 없던 사실만 적는다.

| 논문 | 새로 드러난 사실 | 근거 |
|---|---|---|
| START 2512.13153 | 게재지: IEEE RA-L 11(2), pp. 2194~2201 (JEPLO 참고문헌 [28] 표기). 같은 1저자의 앞선 arXiv 판으로 보이는 WTR 2409.15692v2 부록에 층 크기 · H1 · 지형 치수가 있다(2절 WTR). | JEPLO 참고문헌 · WTR 본문 |
| MARG 2509.20036 | 게재지: IEEE T-RO 2025 (AME-2 참고문헌 [23] · S2 venue). | 참고문헌 표기 |
| AME-2 2601.08485 | S2 venue 표기 IEEE T-RO. 앞선 설계 AME-1 (2506.09588, Science Robotics 2025) 은 2절. DELTA 의 처음 보는 혼합 코스 비교에서 「AME」(AME-1 식 dense encoder, DELTA 저자 구현)는 평균 26.0 % 였다 | S2 · DELTA Table V |
| MoE-CTS 2602.00678 | S2 상 인용 6건 중 지각 사족 보행 방법은 CTS-MoE(2606.19633, 2절)와 JEPLO(여섯 편 중 하나) 둘이다. 나머지는 내비게이션(TAME-Nav) · 휴머노이드 · 열 안전. | S2 citations |
| JEPLO 2609.15770 | S2 상 인용 0건 (2026-10-13). | S2 citations |
| HiPAN 2604.26504 | S2 상 인용 3건, 모두 내비게이션 · 개관. | S2 citations |

---

## 4. 회차 기록

판정: 「새 관련 방법」 = 사족(또는 사족에 바로 옮길 수 있는) 보행 방법으로, 지형 지각이 정책 · 계획에 들어가고 gap · 디딤돌 · parkour · 희소 발판을 다루며, 방법 · 실험 절을 읽을 수 있는 것. 휴머노이드 전용 · 내비게이션 · 저널 전용(본문 못 읽음)은 5절로.

| 회차 | 출처 | 새 관련 방법 (본표에 들어간 것) |
|---|---|---|
| 1 | 여섯 편의 related work · 참고문헌 전부(뒤로) · S2 citations of 여섯 편(앞으로; MoE-CTS 는 429 로 실패해 2회차 묶음에서 받음) · WebSearch 14회 | Zhang risky · AME-1 · DTC · Extreme Parkour · Robot Parkour Learning · Agarwal · PIE · WTR · ANYmal Parkour · Parkour in the Wild · WMP · SoloParkour · Agile Continuous Jumping · Jump from Pixels · Shi · NVM · SF-TIM · KiVi · DELTA · PUMA · Footmap · Foot ToF · SWAP · TACL · StairMaster · Multi-view · MoE parkour Go2 · REDACT · SABER · Akizhanov · (참고) ADAPT · PGTT · Resource-constrained (33) |
| 2 | 1회차 논문의 참고문헌(DELTA · PUMA · REDACT 등) · S2 citations 15편(1회차 13편 + Kim + MoE-CTS 재시도) · WebSearch 4회 | Kim et al. (DELTA · PUMA 참고문헌) · Coholich (PUMA 참고문헌) · CTS-MoE (AME-1 · MoE-CTS 앞으로) · APT-RL · DAWN · LF2WB · REAL (7) |
| 3 | 내려받은 60편 참고문헌 전체 집계(키워드에 걸린 제목 204개) · S2 citations of 2회차 논문 등 9편 · Google Scholar cited-by 첫 쪽(Zhang · START · MARG) · WebSearch 3회(저널 전용 3편) | 0. 새로 나온 것은 휴머노이드(Deep Whole-body Parkour 등), blind 계층(2509.20635), rough 고속 curriculum(2601.17428), 2020 년 시뮬 LiDAR 다지형(2011.05513), 저널 전용(CATR · MGDP · Multi-layer elevation map)뿐 |
| 4 | S2 citations of 많이 인용된 1회차 논문 11편(Extreme Parkour 417 · Robot Parkour Learning 344 · Agarwal 364 · ANYmal Parkour 477 · Miki 2022 1000 (상한) · SoloParkour 35 · NVM 97 · SF-TIM 9 · KiVi 9 · Multi-view 1 · MoE parkour Go2 1 건) → 앞 회차에 없던 1319건 중 키워드 · 사족 필터 65건 → arXiv 판 있는 11건 초록 | Acrobotics · ES-Parkour (2). 둘 다 시뮬만 · gap 숫자는 그림뿐 |
| 5 | Acrobotics · ES-Parkour 의 참고문헌 · S2 citations | 0 (참고문헌은 모두 앞 회차에 있던 것 + Barkour benchmark, 인용 2건은 내비게이션 · 휴머노이드) |
| 6 | WebSearch 3회(새 문구: 희소 지형 attention 2026 · Go2 gap Isaac Lab 2026 · beam · 디딤돌 저속 명령 2026) + 결과에 나온 미확인 학회 논문 1건(RSS 2026 p028) 확인 | 0 (모두 앞 회차에 있던 것이거나 휴머노이드: RSS 2026 p028 = Mind Your Steps) |

5 · 6회차가 연속으로 새 관련 방법 0 이라 멈췄다. 이 판정은 「키워드 필터 + 초록」 그물코에 걸린 범위 안에서다(6절).

### 4회차에서 걸렀지만 본표에 넣지 않은 것 (초록 기준)

- MulDP 2609.03984 (사족 parkour 내비게이션, 확산 정책이 속도 명령을 냄; 관절 정책 아님) · CART 2604.14344 (상위 제어기, 비포장 지형 적응) · LoComposition 2606.15896 (에너지 · 제약 분리, 지각으로 에너지 조절; gap · 돌 서술 없음) · Motion Priors Reimagined 2505.16084 (동물 모방 저수준 + 목표 조건 상위 잔차, 시뮬) · GenTe 2504.09997 (지형 생성, 이족) · Quality-Diversity 지형 생성 2506.01362 (제어기 약점 찾는 지형 생성, 사족 · 이족 시뮬) · Guided RL Omnidirectional 3D Jumping 2507.16481 (점프) · LatentMimic 2604.16440 (모방 스타일 + 지형 적응).
- arXiv 판 없음(제목만): Vision-based terrain-aware quadruped locomotion via dual monocular depth fusion (Biomimetic Intelligence 2026) · Parkour Learning for Quadrupeds via Terrain-Conditional AMP (Applied Sciences 2026) · Quadruped robot foothold intelligence for safe locomotion on hazardous terrain (Scientific Reports 2026) · MoTL: Modality-Balanced Terrain-Aware Locomotion Learning (T-ASE 2026) · Motion Control for Quadruped Robots on Stepped Terrains Based on Depth Vision and RL (2025 학회) · Learning to Exploit Leg Odometry Enables Terrain-Aware Quadrupedal Locomotion (IROS 2025) · OmniNet (RA-L 2025).

---

## 5. 제목만 본 후보 (방법 · 실험 절을 읽지 않음)

### 5-A. 사족 · 지각 · gap · 돌 관련, 본문을 못 읽음

| 제목 | 식별 | 못 읽은 이유 · 아는 것 | 등급 |
|---|---|---|---|
| CATR: Confidence-Aware Terrain Reconstruction for Vision-Based Quadruped Locomotion | RA-L 2026, arXiv 없음 (S2 · Google Scholar), Sui et al. | arXiv 판 없음. S2 상 DTC · PIE · WMP · Kim · AME-1 · MARG · AME-2 를 인용 | 제목만 |
| MGDP: Mastering a Generalized Depth Perception Model for Quadruped Locomotion | Advanced Science 2026 (S2 · Google Scholar, HKU) | arXiv 판 없음. 검색 요약: Warp depth, depth + height map contrastive, 단일 단계 · 증류 없음 | 초록만 (검색 요약, 원문 미확인) |
| Learning Autonomous and Safe Quadruped Traversal of Complex Terrains Using Multi-Layer Elevation Maps | RA-L 10(10) 2025, Chen et al. (HKU, JEPLO 참고문헌 [6]) | arXiv 판 못 찾음. 검색 요약: Go1, 다층 elevation map, 기술 증류 · 전환 | 초록만 (검색 요약) |
| Agile Motion Control of Quadruped Robots on Unstructured Terrain Based on 3D Composite Perception and Depth Camera Characteristics | J. Bionic Engineering 2026 (S2) | arXiv 없음 | 제목만 |
| Perceptive Locomotion and Navigation for Quadruped Robots via Depth-Based Representation | IEEE T-ASE 2026 (S2) | arXiv 없음 | 제목만 |
| SURF-Loco: Mastering Complex Industrial Terrains with 3D Surfel-based RL | 2026 학회 (S2 · Google Scholar) | arXiv 없음 | 제목만 |
| ATG: Adaptive Teacher Guidance RL for Quadruped Precise and Robust Locomotion | AIM 2026 (S2, Zhang risky 인용) | arXiv 없음 | 제목만 |
| A hierarchical multi-encoder fusion architecture for robust quadrupedal locomotion | Int. J. Advanced Robotic Systems 2026 (S2) | arXiv 없음 | 제목만 |
| Learning to traverse challenging terrain using vision and forward kinematics | IROS 2025 (S2) | arXiv 못 찾음 | 제목만 |
| Learning Policy-Dependent Traversability for Terrain-Aware Quadruped Navigation | T-ASE 2026 (S2) | 내비게이션 | 제목만 |
| Perception-Semantic Alignment and Offline Distillation for Vision-Guided Quadruped Locomotion | 2026 학회 (S2) | arXiv 없음 | 제목만 |
| Learning Perception-based Quadrupedal Locomotion on Highly Inclined Industrial Staircases | 2026 (S2) | 계단 | 제목만 |
| DeFM: Learning Foundation Representations from Depth for Robotics | 2601.18923 | depth 표현 사전학습 | 제목만 |
| TAME-Nav: Temporal Asymmetric MoE Distillation for Agile and Versatile Robot Navigation | 2610.12877 (MoE-CTS 인용) | 내비게이션 | 제목만 |
| VIP-Loco | 2603.14345 | Go1 · Cassie · TronA1-W 시뮬만, depth + 내부 모델 + 계획. gap 은 return 만(Table II), 성공률 그림. 실험 절 일부만 읽음 | 일부 읽음 |
| Perceptive Platform Adaptive (MorAL+ / PPAL) | 2606.25179 | ANYmal 실기, flat · rough · 계단. 「critic 에만 지각을 준 판이 지각 잡음에서 actor 까지 준 판보다 안정」. gap 없음 | 초록 · 실험 grep |
| Locomotion on Constrained Footholds via Layered Architectures and MPC | 2506.09979v2 (Humanoids 2025) | 모델 기반, Go2 실기에서 큰 타일 사이 작은 블록 3개를 디디며 통과(Fig. 5, 시행 미기재) | 초록 · 실험 grep |
| Predictive Safety Curricula | 2609.37070 | ANYmal-D Isaac Lab rough curriculum, gap 없음 | 초록 |
| Sampling Strategies for Robust Universal Quadrupedal Locomotion | 2510.07094 | 형태 · PD 이득 표본, gap 없음 | 초록 |
| Scaling Rough Terrain Locomotion with Automatic Curriculum RL | 2601.17428 | ANYmal-D 고속 rough, gap 없음 | 초록 |
| Learning Terrain-Specialized Policies for Adaptive Locomotion | 2509.20635 (ICAR 2025) | blind 계층, 시뮬만 | 초록 |
| Zero-Shot Terrain Generalization for Visual Locomotion Policies | 2011.05513 | 2020, 시뮬 LiDAR 원자료 · 13 환경 | 초록 |
| Vision-aided Dynamic Quadrupedal Locomotion on Discrete Terrain using Motion Libraries | 2110.00891 (ICRA 2022) | 모델 기반 hybrid | 제목만 |
| Neural Scene Representation for Locomotion on Structured Terrain | Hoeller 2022 (RA-L) | 지도 재구성 | 제목만 |
| Learning robust perceptive locomotion for quadrupedal robots in the wild | 2201.08117 (Miki 2022) | gap · 디딤돌 실험 없음 (본문 grep 으로 확인) | 제목 · grep |
| Learning quadrupedal locomotion over challenging terrain (Lee 2020) · DreamWaQ · RMA · HIMLoco · CTS · MoE-Loco | 여러 참고문헌 | blind 기초 | 제목만 |
| LocoTransformer · Visual-locomotion (Yu 2021) · Learning visual locomotion with cross-modal supervision · ViNL · Coupling vision and proprioception for navigation | 여러 참고문헌 | 2021~2023 시각 보행 | 제목만 |
| RLOC · DeepGait · GLiDE · TAMOLS · ViTAL · Perceptive locomotion through NMPC · Online foothold optimization · Continuous jumping on stepping stones via TO/MPC | 여러 참고문헌 | 모델 기반 · 계층 | 제목만 |
| Learning to walk in confined spaces using 3D representation · Resilient legged local navigation · ABS · Advanced skills (Rudin 2022) · Learning to walk by steering | 여러 참고문헌 | 3D · 내비게이션 | 제목만 |
| LucidSim · Vision-guided quadrupedal locomotion with multi-modal delay randomization · TERT (terrain transformer) · Visual CPG-RL · Expanding the horizon (perception-aware MPC) | 3회차 참고문헌 집계 | 2022~2024, 이번 회차에서 열지 않음 | 제목만 |
| RENet (RA-L 2025) · LocoMamba · Vision-proprioception fusion with Mamba2 · LocoFormer | S2 · 참고문헌 | 지각 강건성 · 구조 | 제목만 |
| UEREBot · Learning Agile Navigation in Crowded Environments · SCAN-Planner · MASH · GUIDE | S2 · Google Scholar | 내비게이션 · 속도 | 제목만 |
| Barkour: Benchmarking animal-level agility with quadruped robots | Acrobotics 참고문헌 [3] | 사족 민첩성 벤치마크 (Acrobotics 가 변형해 씀) | 제목만 |
| 4회차 초록 · 저널 전용 목록 | 4절 「4회차에서 걸렀지만」 | 그 목록 참조 | 초록 · 제목 |

### 5-B. 휴머노이드 (사족이 아니라 본표에서 뺌)

- 일부 읽음: ADAPT 2603.16328 (1-D) · Light-Loco-Parkour 2608.02653 (「처음부터 학습하면 디딤돌 앞에서 멈춘다 → 명령 속도 띠 안이면 보상하는 velocity-slack bonus」, Isaac Lab) · TTT-Parkour 2602.02331 (실측 지형 재구성 후 test-time 미세조정, 「사전학습 정책은 절차 지형과 비슷한 시험 지형에서도 대부분 실패」) · ParkourFormer 2605.25782 (G1, MuJoCo).
- 제목만: BeamDojo 2502.10363 · DPL 2510.07152 · Gallant 2511.14625 · PIM 2411.14386 · VB-Com 2502.14814 · Humanoid Parkour Learning · Hiking in the Wild 2601.07718 · Walk the PLANC 2601.06286 · MARCH 2606.10288 · Echo in the Steps 2609.28960 · FootQuery 2609.21447 · World-Model-Augmented Visual Locomotion on Foothold-Constrained Terrain 2609.02542 · Learning Agile Perceptive Traversal of Sparse 3D Structures 2608.29769 · Global-Local Attention Decomposition (GLAD) 2606.00637 · TAGA 2606.05880 · SOLO 2608.26583 · SSR 2605.30770 · UniPoint 2609.23666 · CReF 2603.29452 · Deep Whole-body Parkour 2601.07701 · Perceptive Humanoid Parkour (motion matching) 2602.15827 · RPL 2602.03002 · Mind Your Steps 2606.08253 · Omnidirectional Humanoid Locomotion on Stairs 2603.07928 · GuideWalk 2606.10449 · T-GMP 2606.06944 · What the Elevation Map Cannot See 2610.07396.

### 5-C. 제외 (주제 밖)

- Vision-Based End-to-End Learning for UAV Traversal of Irregular Gaps 2604.02779 (드론, gap 검색에 걸림).
- LocoWM 2609.39179 (Go2-W 바퀴다리, 짐 안정화).
- Quadruped robot traversing 3D complex environments with limited perception 2404.18225 (Go2, proprio 만, gap 없음).
- Neverwhere Visual Parkour Benchmark 2609.16443 (평가 환경: 3DGS 장면 60개 넘게 · MuJoCo · 코드 공개, gap · 돌 전용 아님).

---

## 6. 못 본 것

- **그림 안의 숫자**: AME-1 Fig. 6 · Zhang Fig. 7 · 8 · Extreme Parkour Fig. 7 · Agarwal Fig. 4 · WMP Fig. 6 · PIE Fig. 4 · ANYmal Parkour Fig. 4 · SoloParkour Fig. 4 · Footmap Fig. 5 · Foot ToF Fig. 6 · CTS-MoE Fig. 5 · APT-RL Fig. 8 · SWAP Fig. 3 · Coholich Fig. 4~6 · Akizhanov Fig. 3. 그림 파일을 열지 않았다.
- **보충자료 · 부록**: DTC · Kim · AME-1 영상 · APT-RL · Foot ToF 보상(프로젝트 사이트) · TACL 부록(실기 결과) · Robot Parkour Learning 하이퍼파라미터 · CTS-MoE Table 4 (관측 표). 각 논문의 영상은 하나도 보지 않았다.
- **본문을 못 연 것**: CATR · MGDP · Multi-layer elevation map (arXiv 판 없음, 출판사 페이지 시도 안 함). 5-A 의 저널 전용 항목 전부.
- **HTML 변환 손실**: NVM Table 2 의 NVM 행, NVM Table 4 단위. LaTeXML 수식은 alttext 로만 읽었다.
- **인용 그래프의 그물코**: Semantic Scholar 는 논문당 최대 1000건(쪽 100건)까지만 받았고(Miki 2022 는 1000건에서 잘림, 그 뒤는 안 봄) 제목 키워드(stepping · stone · foothold · gap · parkour · terrain · perceptive · elevation · depth · vision · lidar · discrete · jump · risky · beam · rough · locomotion) + 2025 년 이후로 걸렀다. 키워드에 안 걸리는 제목의 관련 논문은 빠졌을 수 있다. Google Scholar 는 cited-by 첫 쪽(10건)만, 세 편에 대해서만 봤다(Zhang 은 2026 년 필터). S2 가 venue · arXiv id 를 비운 항목은 제목으로만 판단했다.
- **WebSearch 결과 요약**: 검색 도구가 붙인 요약문은 근거로 쓰지 않았다. MGDP · Multi-layer elevation map 의 「초록만」 칸은 검색 요약이므로 원문 확인 전이다.
- **재현 숫자 대조**: Extreme Parkour 를 기준선으로 다시 돌린 논문들(2절 Extreme Parkour 항목의 여섯 숫자)의 설정 차이는 대조하지 않았다.
- **같은 방법의 판 차이**: WTR v1 · v2, START 와 WTR, AME-1 arXiv v1 과 Science Robotics 출판본, KiVi v1~v3 의 차이를 대조하지 않았다. 읽은 판만 적었다.
- **아무것도 실행하지 않았다**. GPU 사용 없음.
