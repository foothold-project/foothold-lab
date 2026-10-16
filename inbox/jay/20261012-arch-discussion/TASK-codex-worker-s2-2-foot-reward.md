> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2-2 발 디딤 자리 보상 CPU 구현 (step10)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 11:05
> 근거: `S2-2-DESIGN.md` · `ROADMAP-20261016.md` (팀장 승인 10/16 11:00) · `night-tools-20261013/s2_step8/` 와 sol 의 step9 · ASTRA 17ag 가 식을 닫기 전까지 식의 값은 `UNDECIDED`
> 요지: step9 가 끝나면 보낸다. 발 디딤 보상의 틀(순수 텐서 함수, 선택 가능한 RewTerm, 기본값에서 step9 와 같은 동작)과 정답을 아는 시험을 CPU 에서 만든다. 식의 값은 ASTRA 판정 후에 채운다
> 상태: 작업 지시 (step9 보고 뒤 발송 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다)

# sol 작업서: S2-2 발 디딤 보상 (step10)

## 0. 지킬 것

step9 와 같다. GPU · Isaac · `_eval` 슬롯 · 기존 코드 · 원자료를 건드리지 않는다. `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`. 새 사본 `codexE/s2_step10/` (step9 를 복사해 시작하되 `s2_step9/` 와 저장소는 고치지 않는다). 정상 먼저, 변이는 지정 첫 FAIL. em dash 금지. 첫 실패도 보고서에. 바꿔야 하는 이유가 step9 의 실행 의미 · 입력 검사 · Job/잠금/격리에 닿으면 막힌 줄만 적고 멈춘다.

## 1. 먼저 읽고 보고할 것 (코드 변경 없음)

1. E1 부모 실행 폴더의 `params/env.yaml` 의 보상 항(이름 · 가중치 · params)이 `C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/tasks/go2/env_cfg.py:347~435` 의 `RewardsCfg` 14항과 같은지. 다르면 항별 차이표.
2. 지도 센서(`env_cfg.py:65~79`)와 `s2_env_config_17v.py` 가 발 몸체(FL/FR/RL/RR_foot)에 센서를 붙일 수 있는 자리가 어디인지(`FOOT_LINK_NAME` · prim 경로). 센서를 더하는 가장 작은 변경 지점.
3. `mdp/rewards.py` 의 `feet_stumble` (305행) 과 `feet_regulation` 의 입력이 어디서 오는지.

## 2. 만들 것

1. **순수 텐서 함수** `s2_foot_reward.py`: 입력 `foot_ray_z[N, 4, K]` (발마다 K점의 지면 높이, 월드 z), `foot_z[N, 4]`, `in_contact[N, 4]` (발 접촉 여부), 출력 `penalty[N]`. 식의 모양(가장자리 점 수 n 에 대한 단조 함수, 접촉 발만 계산, 점 높이가 `foot_z - edge_drop` 보다 낮으면 가장자리)은 **ASTRA 17ag 가 닫기 전까지 인자로 열어 둔다**. 값은 `UNDECIDED`, 호출하면 거절.
2. **선택 가능한 연결:** 요청 JSON 의 필드 `reward_variant` ∈ {`none`, `feet_center`}. 기본값 `none` 이고 이때 환경 구성이 step9 와 **바이트 단위로 같은 dict** 가 나와야 한다(시험으로 증명). `feet_center` 일 때만 RewTerm 과 발 센서가 구성에 더해지고, 가중치 · 점 간격은 요청에서 읽는다. 기본값이 없다.
3. **정답을 아는 시험(CPU):** 평평한 발 아래 = 0 · 9점 중 일부가 가장자리 = 가장자리 점 수에 맞게 단조 증가 · 공중 발은 0 · 네 발 중 한 발만 가장자리일 때 그 발만 반영 · 환경별 독립(한 env 의 값이 다른 env 로 새지 않음) · NaN 입력은 거절 · `reward_variant=none` 일 때 step9 와 구성 동일.
4. **변이:** 가장자리 판정 부등호 뒤집기, 접촉 마스크 제거, 발 축 합 대신 최대, env 축 섞기, 기본값을 `feet_center` 로 바꾸기. 각각 지정 첫 FAIL 로 잡히는지.
5. 깨끗한 복사본 `-I` 로 전체 회귀(step9 시험 파일 전부 + 새 것). 정상 PASS 수와 변이 CAUGHT/전체를 구분.

## 3. 끝나면

`REPORT-s2-step10.md` (1절 답 · 바뀐 파일 · 시험 수 · 첫 실패 · 미확인), `S2-STEP10-SHA256SUMS.txt`, #550 댓글 초안(미게시). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
