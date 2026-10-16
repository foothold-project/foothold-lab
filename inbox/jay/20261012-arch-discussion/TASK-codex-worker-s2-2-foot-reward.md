> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2-2 발 디딤 자리 보상 `feet_center_any9_v1` CPU 구현 (step15, ASTRA 17ag 사양 반영 판)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 19:49
> 근거: `VERIFY-astra-17ag.md` 1~2절(사양 · 높이 출처 · 필요한 CPU 증거) · 3절(2×2 비교 틀과 혼입) · 6절(가중치 · 판독) · `S2-2-DESIGN.md` · 팀장 승인 10/16 11:00 (발 디딤 보상 사용). 이전 판(10/16 11:15)은 이 문서로 대체한다
> 요지: MARG 의 feet center 를 참고한 우리 사양을 순수 텐서 함수와 선택 가능한 연결로 만든다. 이름은 `feet_center_any9_v1`(MARG 원본 복제 아님). 학습 지형 · stumble · 돌 크기는 같이 바꾸지 않는다(열이 「발 디딤 보상」이 아니게 되므로). Kit 에서 발 광선이 실제로 맞는지는 별도 학습 0 단회로 확인한다(이번 작업은 그 단회의 계약까지)
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다)

# sol 작업서: S2-2 `feet_center_any9_v1` (step15)

## 0. 지킬 것

step14 와 같다. 새 사본 `codexE/s2_step15/` (step14 의 B 묶음을 복사해 시작; step14 · 저장소 · `_eval` 은 읽기만). `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`. 정상 먼저, 변이는 지정 첫 FAIL. 정상 PASS 와 변이 단계 선행 PASS 를 합쳐 쓰지 않는다. 해시 목록 CR 없이. em dash 금지. 바꿀 수 있는 것은 새 파일과 `reward_variant` 연결부뿐이며 기본값 `none` 에서 step14 와 환경 구성이 **바이트 단위로 같은 dict** 여야 한다.

## 1. 사양 (ASTRA 17ag 1.2절을 옮긴 것, 다르게 읽히면 17ag 원문이 이긴다)

- 입력: 같은 시점의 발 충돌구 중심 위치 `p_f [N,4,3]` (m), 지형 mesh 하향 광선의 hit 높이 `H [N,4,9]` (m), query 상태, 발 접촉력 `F [N,4,3]` (N). 출력: 환경마다 스칼라 비용 `C [N]`. actor 의 187칸 지도나 복원 지도는 보상 입력으로 쓰지 않는다.
- 발별 수평 3×3 표본 `{-0.05, 0, +0.05} m × {-0.05, 0, +0.05} m`, 첫 판은 **world XY 격자** 고정(발 roll/pitch 에 따라 광선이 기울지 않는다).
- 기준 `z_ref = p_f,z - 0.022 m` (설치된 Go2 URDF 발 충돌구 반지름 0.022 m; 발 링크 원점과 충돌구 중심을 혼동하지 않는다: FL 충돌구는 링크 좌표 `(-0.002, 0, 0)`; 다른 발도 collision transform 에서 읽는다).
- `b_fj = 1[H_fj < z_ref - 0.20 m]` (월드 높이 -0.2 와 직접 비교하지 않는다: 평행 이동 불변). 정상 질의의 no-hit 는 깊은 공백으로, NaN · 잘못된 mesh · 오래된 버퍼를 공백으로 처리하지 않는다.
- `u_f = any(b_fj, j ∈ Type2 상하좌우 네 점)`, `v_f = any(b_fj, j ∈ Type3 대각 네 점)`, `c_f = 1[F_f,z > 1 N]` (제안값; 매 제어 시점의 지지 접촉이지 first-contact 이벤트가 아님).
- `C_f = c_f × (u_f + 2 v_f)`. 중앙점도 공백인 채 접촉했다면 `C_f = 3 c_f` 로 두고 중앙 불일치를 별도 카운터로 남긴다. `C = Σ_f C_f`, 범위 `[0,12]`. RewardManager 에는 **양의 비용 함수와 음의 가중치 -0.01** 을 넘긴다(함수 안에서 음수를 곱하지 않는다, dt 도 넣지 않는다: 매니저가 곱한다).
- 한계(보고서에 그대로): 20 cm 보다 얕은 낙차 · 얇은 균열 · 작은 구멍은 탐지하지 못하고 9점 사이 공백도 놓친다. gap · stones 두 지형에 한정해 시작한다.

## 2. 만들 것

1. 순수 텐서 함수 `s2_foot_reward.py` 와 ASTRA 17ag 2절이 요구한 CPU 증거: 평면 비용 0 · cardinal 만 위험인 지지발 1 · diagonal 만 2 · 둘 다 3 · swing 0 · 네 발 최댓값 12 · 동일 좌표 전체를 z 로 평행 이동해도 비용 같음 · 20 cm 경계 양쪽 · 1 N 접촉 경계 · 정상 no-hit 와 NaN / 부분 inf / 범위 초과 분리 · 네 발 permutation · 비동기 env reset · stale frame 거부. **같은 함수로 정답을 만들고 그 함수가 맞다고 시험하지 않는다**: 작은 알려진 삼각형 mesh 와 3×3 hit 의 손계산 결과를 정답표로 쓴다.
2. 발 광선 질의 연결 `s2_foot_query.py`: RayCaster 네 센서(논리) 또는 36점 묶음 질의(구현 선택), `cfg.offset.pos` 의 +20 m 가 광선 시작점에 이미 들어가고 `data.pos_w` 는 view 와 `_offset` 에서 나온다는 사실(`ray_caster.py:220,242` 부근)을 반영: 발 높이나 접지 높이에 +20 m 를 더하지 않고, 시작점 · hit 를 각각 저장, 반복 갱신으로 시작점이 누적 이동하지 않는지 검사, query 범위는 해당 타일 표면과 -1 m 구멍 바닥 포함(`max_distance` 부족 · 타일 밖 · mesh 로드 실패는 공백이 아님), pose · force · hit 를 같은 제어 단계에서 캡처, reset 에서 env 별 episode ID 와 frame ID 갱신. 센서가 시작점이 reset 에서 시계 0 으로 돌아가는 것을 과거 episode 의 정상 진행으로 착각하지 않는다.
3. 선택 연결: 요청의 `reward_variant` ∈ {`none`, `feet_center_any9_v1`}. 기본 `none`. 켜져 있을 때만 RewTerm 과 발 센서가 환경 구성에 더해지고 가중치 -0.01 · 점 간격은 요청에서 읽는다(기본값 없음). critic 관측은 **그대로 둔다**(보상 있는 열에서만 critic 에 추가하면 또 다른 요인). 시험: `none` 일 때 구성 동일, 켠 구성에서 actor / student 입력 shape 와 critic 관측 불변, 보상 항 목록에 이 항만 추가.
4. 실제 구성된 reward manager 의 항 이름 · 가중치 목록을 신규 실행의 영수증에 저장하는 필드(상속 · override 뒤의 최종값; 17ag 6.1절). 현재 RewardsCfg 와 E1 `params/env.yaml` 이 15항으로 일치한다는 사실과 대조.
5. **Kit 단회 계약** `S2-FOOT-KIT-CHECK.md` (실행하지 않는다): N ≤ 8, 최대 300 control step(50 Hz 라면 물리 6 초 상한), 학습 · optimizer 0, 알려진 평면 · 직선 절벽 · 대각 절벽 · 유한 깊이 구멍 · 동일 장면의 다른 높이 / 위치 · 지지 · swing · reset 포함. 실제 hit XY/Z · 접촉력 · body ID · mesh 경로 · frame / episode ID · raw C 와 weighted reward 를 남김. 기하 오차 허용치는 meter 기준으로 먼저 고정하고 경계선의 수치 불안정 점은 별도 분류. A3.4 감독기 계약 방식을 재사용할 수 있는지 판단해 적는다.
6. 5~10 update 판독 기준 문서화(17ag 6.2절): 즉시 결함 · 과대 기여 의심(`Σ|r_center| / Σ r_tracking`, 분모 0 구간 별도 보고) · 동결 보행 의심(reward-off 대조 대비 진행 20 % 이상 감소 + touchdown 감소 + 2초 이상 저속 정체 증가) · 가짜 개선 방지. 진단 제안 기준이지 자동 연장 · 재시도 규칙이 아님.

## 3. 끝나면

`REPORT-s2-step15.md` (코드 위치 · 시험 수 · 변이 CAUGHT/전체 · 첫 실패 · 미확인: 실제 Kit 발 광선 응답, 실제 USD collision 발 형상), `S2-STEP15-SHA256SUMS.txt`, #550 댓글 초안(미게시). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
