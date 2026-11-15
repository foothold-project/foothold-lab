# S1-a scan 학습 설정과 NVIDIA Go2 rough · v2 비교

> 분류: 리서치
> 작성: sol · 2026-10-21
> 근거: 설치 Isaac Lab 코드 · v2 및 S1-a 실행 YAML · 로컬 계산
> 요지: 세 학습 설정의 보상, 명령, 종료, 지형, 관측, 행동, PPO, DR 차이를 원문 행으로 대조한다.
> 상태: 확인됨 · 설정 차이. 정지 현상의 인과관계는 미확인

## 읽는 법과 원문

이 문서는 **실제 평가 결과로 원인을 확정하지 않는다.** 비교 단위는 설정 행이다. `예`는 S1-a 설정이 해당 기준과 다르다는 뜻이고, `아니요`는 이 행에서 대조한 값이 같다는 뜻이다. 0 가중치와 미사용 항은 설정 차이와 유효 보상 차이를 구분했다. A는 설치된 NVIDIA Go2 rough 학습 설정, B는 v2 실행 기록, S는 S1-a scan 실행 기록이다. B의 실행 YAML은 요청에 적힌 sonnet 사본이 아니라 원 실행 디렉터리인 `C:/isaac/IsaacLab/logs`에서 찾았다. [S 실행 상태](C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s1a/2026-10-20_16-59-25_s1a_scan/train_start_status.json)는 `iter=5999`, `tot_iter=6000`, `state=done`이다. 원인 진단에는 이 설정표와 별도로 실제 행동 및 명령 노출 기록이 필요하다.

`확인됨`: 아래 85개 설정 행은 설치 코드와 두 run의 YAML에서 대조했다. 설치 코드의 원 프로젝트는 [Isaac Lab](https://github.com/isaac-sim/IsaacLab)이다. 해당 링크는 프로젝트 식별용이며 실제 비교 근거는 아래 로컬 설치 경로와 실행 YAML이다. 네 실행 YAML의 SHA-256은 B env `a5ef31d626f8cabe850de37bae0aa26782e14e9db3ba61d678dd1210105323e7`, B agent `a8d9071bdc1dd3eb313b0442a760e22fea7704cb097067a637b1ddcbd30f12f0`, S env `d68611f46e209e69321ad4f0a1b38d9bff326c10fbb9ed6dd0de4489d9bda3eb`, S agent `bc1727aeae15c5492793e94128ac0342135bc598be70b62fd26b4a8f66e5cdc5`다.

각 행의 `근거`에서 약호 뒤 숫자는 아래 **전체 경로의 파일 행 번호**다. 따라서 `A0:235`는 `velocity_env_cfg.py:235`를 뜻한다. YAML에 없는 S 명령의 기본 매개변수는 `params: {}`인 [S0:1248]과 생성기 소스 S2를 함께 읽었다. 소스가 실행 뒤 바뀌었는지 독립 해시는 없으므로 이 부분은 **코드 근거**, YAML로 확정된 값과 구별한다.

| 약호 | 원문 경로 |
|---|---|
| A0 | `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/velocity_env_cfg.py` |
| A1 | `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/rough_env_cfg.py` |
| A2 | `C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/config/rough.py` |
| A3 | `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/agents/rsl_rl_ppo_cfg.py` |
| A4 | `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/mdp/curriculums.py` |
| A5 | `C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_generator.py` |
| A6 | `C:/isaac/IsaacLab/source/isaaclab_rl/isaaclab_rl/rsl_rl/rl_cfg.py` |
| B0 | `C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/env.yaml` |
| B1 | `C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/params/agent.yaml` |
| S0 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s1a/2026-10-20_16-59-25_s1a_scan/params/env.yaml` |
| S1 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s1a/2026-10-20_16-59-25_s1a_scan/params/agent.yaml` |
| S2 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/foothold_s2/commands/mixed_core.py` |
| S3 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/foothold_s2/commands/mixed_command.py` |
| S4 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/foothold_s2/curriculum/terrain_levels_mixed.py` |
| S5 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/foothold_s2/curriculum/rules.py` |
| S6 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/foothold_s2/tasks/mdp_extra.py` |
| S7 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/foothold_s2/rewards/start_rewards.py` |
| S8 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/foothold_s2/terrains/columns.py` |
| S9 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/foothold_s2/tasks/delayed_action.py` |

## 전체 대조표

### 보상

`std`는 추종 보상의 표준편차 매개변수다. `없음`은 항 자체가 없거나 `null`, `0`은 선언됐으나 가중치가 0이다. 같은 함수인데 설정 이름만 다른 경우 함수를 기준으로 정렬했다.

| ID · 항목 | A: NVIDIA rough | B: v2 | S: S1-a scan | A와 다름 | B와 다름 | 근거 |
|---|---|---|---|---|---|---|
| R01 · XY 선속도 추종 | `track_lin_vel_xy_exp` +1.5, std 0.5 | 같은 함수 +1.5, std 0.5 | `track_lin_vel` +1.5, std 0.5, B식 정확 추종 | 아니요 | 아니요 | A0:235, A1:56, B0:855, S0:982, S0:1249 |
| R02 · yaw 추종 | +0.75, std 0.5 | +0.75, std 0.5 | +0.5, std 0.5 | 예 | 예 | A0:238, A1:57, B0:861, S0:988 |
| R03 · 수직 선속도 L2 | -2.0 | -2.0 | -2.0 | 아니요 | 아니요 | A0:242, B0:867, S0:994 |
| R04 · 수평 각속도 L2 | -0.05 | -0.05 | -0.05 | 아니요 | 아니요 | A0:243, B0:871, S0:998 |
| R05 · 관절 토크 L2 | -0.0002 | -0.0002 | -0.00001 | 예 | 예 | A1:55, B0:875, S0:1006 |
| R06 · 관절 가속도 L2 | -2.5e-7 | -2.5e-7 | -2.5e-7 | 아니요 | 아니요 | A1:58, B0:879, S0:1022 |
| R07 · 행동 변화 L2 | -0.01 | -0.01 | -0.01 | 아니요 | 아니요 | A0:246, B0:883, S0:1010 |
| R08 · 발 공중 시간 | +0.01, 문턱 0.5, `.*_foot` | +0.1, 문턱 0.5, `.*_foot` | 없음 | 예 | 예 | A0:247, A1:52, A1:53, B0:887, S0:981 |
| R09 · 불필요 접촉 또는 충돌 | `undesired_contacts=null` | `undesired_contacts=null` | `collision` -10, base·thigh·head, 0.1 N | 예 | 예 | A1:54, B0:916, S0:1030, S0:1045, S0:1059 |
| R10 · 평탄 자세 L2 | 0 | 0 | -1.0 | 예 | 예 | A0:262, B0:917, S0:1002 |
| R11 · 관절 위치 한계 | 0 | 0 | 없음. **세 판 모두 보상 효과 0** | 예, 설정만 | 예, 설정만 | A0:263, B0:921, S0:981 |
| R12 · 행동 2차 변화 | 없음 | 없음 | `action_smoothness` -0.01 | 예 | 예 | A0:231, B0:854, S0:1014, S7:21 |
| R13 · 관절 일률 절댓값 | 없음 | 없음 | `joint_power` -2e-5 | 예 | 예 | A0:231, B0:854, S0:1018, S7:46 |
| R14 · 기본 관절각 편차 L2 | 없음 | 없음 | `joint_deviation` -0.01 | 예 | 예 | A0:231, B0:854, S0:1026, S7:53 |
| R15 · 발 걸림 | 없음 | 없음 | `stumble` -1.0, 수평 접촉력 > 수직의 4배 | 예 | 예 | A0:231, B0:854, S0:1061, S7:60 |
| R16 · 발 가장자리 | 없음 | 없음 | `foot_edge` 0. **S1에서 표가 없어 반환값도 0** | 예, 설정만 | 예, 설정만 | A0:231, B0:854, S0:1088, S0:1137, S7:67 |

### 명령 생성

| ID · 항목 | A: NVIDIA rough | B: v2 | S: S1-a scan | A와 다름 | B와 다름 | 근거 |
|---|---|---|---|---|---|---|
| C01 · 생성기와 분포 | `UniformVelocityCommand`: 각 축 구간 균등 | 동일 생성기, 전진 x만 | `MixedVelocityCommand`: 자유 env는 각 축 절댓값 균등·무작위 부호와 0 마스크, 깃발 env는 목표 방향 | 예 | 예 | A0:94, B0:990, S0:1233, S2:85, S2:187 |
| C02 · 재표집 | 10 s 고정 | 10 s 고정 | 4 s 고정 | 예 | 예 | A0:96, B0:993, S0:1235 |
| C03 · 자유 env 정지 추첨 | 0.02 | 0.10 | 0.10. 깃발 env에는 별도 정지 규칙 | 예 | 아니요 | A0:97, B0:1000, S2:33, S2:117 |
| C04 · 자유 x 범위 | [-1,1] | [0.4,1.5] | 시작 절댓값 [0,1], 양·음 무작위. 승급 상한 1.5 | 아니요, 초기 범위 | 예 | A0:103, B0:1003, S2:25, S2:87, S2:276 |
| C05 · 자유 y 범위 | [-1,1] | [0,0] | 시작 절댓값 [0,1], 양·음 무작위 | 아니요, 초기 범위 | 예 | A0:103, B0:1006, S2:27, S2:85 |
| C06 · 자유 yaw 범위 | [-1,1] | [-1,1] | [-2,2], heading 때 ±2 clip | 예 | 예 | A0:103, B0:1009, S2:28, S2:95, S2:102 |
| C07 · heading 선택 | 켬, 비율 1, 목표 [-π,π] | 켬, 비율 1, 목표 [-π,π] | 자유 env의 정지·spin 제외 뒤 1/3, 1000 update 후 5/12. 목표 [-π,π] | 예 | 예 | A0:98, B0:998, S2:35, S2:110 |
| C08 · heading 제어 이득 | 0.5 | 0.5 | 0.5 | 아니요 | 아니요 | A0:100, B0:999, S2:38 |
| C09 · 별도 제자리 회전 | 없음 | 없음 | 자유 env에서 1000 update 뒤 정지 제외 0.20 확률, 선속도 0 | 예 | 예 | A0:94, B0:991, S2:34, S2:118 |
| C10 · 축별 0 마스크 | 없음 | 없음 | x 0.9, y 0.75, yaw 0.5 유지 확률 | 예 | 예 | A0:94, B0:991, S2:29, S2:95 |
| C11 · 깃발 방식 | 없음 | 없음 | env 번호 5의 배수 약 20%, 4개 깃발, 접근 0.5 m, 끝에서 0 명령 | 예 | 예 | A0:94, B0:991, S0:1241, S3:38, S2:44, S2:205 |
| C12 · 깃발 속력·회전 | 해당 없음 | 해당 없음 | 속력 U[0,1.0], 0.3 미만 제자리 회전 ±1.2, 전진 yaw ±1 clip, backoff 확률 0 | 예 | 예 | A0:94, B0:991, S2:40, S2:187, S2:237 |
| C13 · 명령 범위 커리큘럼 | 없음 | 없음 | 추종 두 항이 각각 최대의 0.8 이상이면 자유 x/y 상한 +0.25, 깃발은 중앙 레벨 5 이상 추가 조건 | 예 | 예 | A0:277, B0:986, S0:1226, S4:63, S2:274 |
| C14 · 명령 난수 출처 | 환경 난수 흐름 | 환경 난수 흐름 | 별도 `torch.Generator(seed=0)` | 예 | 예 | A0:94, B0:991, S0:1240, S3:34 |

### 종료

| ID · 항목 | A | B | S | A와 다름 | B와 다름 | 근거 |
|---|---|---|---|---|---|---|
| T01 · 시간 상한 | 20 s, timeout | 20 s, timeout | 20 s, timeout | 아니요 | 아니요 | A0:270, A0:309, B0:853, B0:925, S0:980, S0:1139 |
| T02 · 몸통 접촉 | base 접촉 >1 N이면 종료 | 동일 | 없음 | 예 | 예 | A0:271, A1:61, B0:930, B0:956, S0:1138 |
| T03 · 자세 각도 | 없음 | 없음 | `bad_orientation`, 1.5 rad | 예 | 예 | A0:266, B0:925, S0:1143 |
| T04 · 발이 지면 아래 | 없음 | 없음 | 가까운 유효 광선의 지면보다 0.2 m 아래, 격자 밖 발 제외 | 예 | 예 | A0:266, B0:925, S0:1148, S0:1220, S6:14 |
| T05 · 원점 아래 낙하 | 없음 | 상대 원점 z < -3 m | 없음 | 아니요 | 예 | A0:266, B0:958, S0:1138 |

### 지형 및 난이도

아래 비율은 YAML의 **원시 가중치**다. S의 합은 0.46이고 생성기가 이를 합 1로 정규화해 23열에 고정 배치한다. 그러므로 `0.10`을 실제 출현 10%로 읽으면 틀린다. S의 실제 열 수는 계단 정·역 5·5, 상자·거친 높이장 4·4, 비탈 정·역 2·2, 단차 1이다. [A5:216-245], [S8:11-18], [S8:32-47]을 대조했다.

| ID · 항목 | A | B | S | A와 다름 | B와 다름 | 근거 |
|---|---|---|---|---|---|---|
| G01 · 정방향 계단 | 0.20 | 0.15 | 0.10, 정규화 뒤 5/23열 | 예 | 예 | A2:23, B0:209, S0:116, A5:237 |
| G02 · 역방향 계단 | 0.20 | 0.15 | 0.10, 5/23열 | 예 | 예 | A2:31, B0:223, S0:130, A5:237 |
| G03 · 상자 | 0.20 | 0.15 | 0.08, 4/23열 | 예 | 예 | A2:39, B0:237, S0:144, A5:237 |
| G04 · 무작위 거친 바닥 | 0.20 | 0.15 | 0.08, 4/23열 | 예 | 예 | A2:42, B0:250, S0:157, A5:237 |
| G05 · 정방향 비탈 | 0.10 | 0.10 | 0.04, 2/23열 | 예 | 예 | A2:45, B0:266, S0:173, A5:237 |
| G06 · 역방향 비탈 | 0.10 | 0.10 | 0.04, 2/23열 | 예 | 예 | A2:48, B0:282, S0:189, A5:237 |
| G07 · 고정 0.15 m 단차 | 없음 | 없음 | 0.02, 1/23열 | 예 | 예 | A2:21, B0:206, S0:203, S0:205, S0:211 |
| G08 · gap · rails | 없음 | 각각 0.10 | 없음 | 아니요 | 예 | A2:21, B0:296, B0:313, S0:113 |
| G09 · 행·열 | 10×20 | 10×20 | 10×23 | 예 | 예 | A2:15, B0:200, S0:107 |
| G10 · 첫 지형 레벨 상한 | 5 | 2 | 2 | 예 | 아니요 | A0:48, B0:352, S0:242 |
| G11 · 단계·크기·스캔 지형 크기 | 난도 [0,1], 8×8 m, 10행 | 같음 | 같음 | 아니요 | 아니요 | A2:12, A2:15, B0:195, B0:327, S0:102, S0:217 |
| G12 · 상자 높이·거친 잡음 | Go2 보정 후 상자 0.025~0.1 m, 잡음 0.01~0.06 m·간격 0.01 | 같음 | 같음 | 아니요 | 아니요 | A1:25, A1:26, A1:27, B0:243, B0:259, S0:150, S0:166 |
| G13 · 지형 승강 기준 | 현 위치에서 출발 원점까지 거리 >4 m 승급, 최종 명령×20 s의 절반 미만 강등 | 동일 설치 함수 | 에피소드 최대 이격 >4 m 승급, 명령 누적×4 s×0.5×0.9 미만 강등. 깃발은 통과 수와 보행 시간 비율 | 예 | 예 | A0:281, A4:45, B0:987, S0:1223, S4:14, S5:14, S5:29 |
| G14 · 지형 커리큘럼 사용 | 켬 | 켬 | 켬 | 아니요 | 아니요 | A0:322, B0:194, S0:101, S0:1223 |

### 관측과 센서

정책 차원은 Go2 관절 12, 행동 12, 17×11 스캐너 187을 기준으로 원문 term을 더해 계산했다. A/B = `3+3+3+3+12+12+12+187=235`. S = `3+3+3+12+12+12+187=232`. S critic = `3+3+3+12+12+12+3+4=52`. 스캐너 187은 S critic에 없다. 이는 YAML term 목록을 직접 합산한 값이며 런타임 텐서 shape 검사는 이 읽기 전용 조사 범위 밖이다.

| ID · 항목 | A | B | S | A와 다름 | B와 다름 | 근거 |
|---|---|---|---|---|---|---|
| O01 · 정책 차원 | 235 | 235 | 232 | 예 | 예 | A0:123, B0:546, B0:630, S0:511, S0:582 |
| O02 · 몸 선속도 관측 | 정책에 3열, 잡음 ±0.1 | 정책에 3열, 잡음 ±0.1 | 정책에서 빠짐. critic에만 3열 | 예 | 예 | A0:124, B0:546, S0:511, S0:681 |
| O03 · critic 관측 | 별도 critic 그룹 없음, 정책 그룹 사용 | 별도 critic 그룹 없음 | 52열, 정책 잡음 없음, 선속도 3·발 접촉 4 추가, height 없음 | 예 | 예 | A0:145, B0:539, S0:620, S0:681, S0:690 |
| O04 · 높이 함수 | 기본 `height_scan` | `height_scan_with_gap`, offset 0.5, miss 1.0 | 기본 `height_scan` | 아니요 | 예 | A0:134, B0:630, B0:656, S0:582 |
| O05 · 높이 격자·주기 | 17×11=187, 0.1 m, 0.02 s | 같음 | 같음 | 아니요 | 아니요 | A0:66, A0:318, B0:357, B0:374, S0:354, S0:371 |
| O06 · 높이 스케일·클립·잡음 | scale 없음, clip [-1,1], ±0.1 | 같음 | 같음 | 아니요 | 아니요 | A0:134, B0:659, B0:664, S0:609, S0:614 |
| O07 · 공유 관측 잡음 | 각속도 ±0.2, 중력 ±0.05, 관절각 ±0.01, 관절속도 ±1.5 | 같음 | 같음 | 아니요 | 아니요 | A0:125, A0:132, B0:559, B0:609, S0:511, S0:560 |
| O08 · 정책 오염 | 켬 | 켬 | 켬, critic은 끔 | 아니요 | 아니요 | A0:141, B0:543, S0:508, S0:623 |
| O09 · 접촉 센서 | 모든 링크, 3 프레임, air time 추적 | 같음 | 같음 | 아니요 | 아니요 | A0:74, B0:428, S0:425 |
| O10 · 그 밖의 관측 scale·clip | 명시 scale·clip 없음 | 같음 | 같음. 높이 clip은 O06에 별도 기록 | 아니요 | 아니요 | A0:123, B0:546, B0:629, S0:511, S0:581 |

### 행동, PPO 및 학습 범위

| ID · 항목 | A | B | S | A와 다름 | B와 다름 | 근거 |
|---|---|---|---|---|---|---|
| X01 · 관절 목표 배율 | 0.25, 기본 자세 offset | 0.25, 기본 자세 offset | 0.25, 기본 자세 offset | 아니요 | 아니요 | A1:30, B0:670, S0:722 |
| X02 · 행동 clip | runner·term 모두 `null` | runner·term 모두 `null` | runner·term 모두 `null` | 아니요 | 아니요 | A0:112, B0:675, B1:7, S0:727, S1:11 |
| X03 · 행동 지연 | 기본 JointPositionAction, 없음 | 기본 JointPositionAction, 없음 | DelayedJointPositionAction, reset마다 0~0.015 s | 예 | 예 | A0:112, B0:672, S0:724, S0:734, S9:16, S9:43 |
| P01 · rollout 길이 | 24 step/env | 24 | 24 | 아니요 | 아니요 | A3:13, B1:3, S1:3 |
| P02 · PPO epoch·mini batch | 5·4 | 5·4 | 5·4 | 아니요 | 아니요 | A3:30, A3:31, B1:36, S1:40 |
| P03 · learning rate | 0.001 | 0.0001 | 0.001 | 아니요 | 예 | A3:32, B1:38, S1:42 |
| P04 · actor·critic MLP | 각각 [512,256,128], ELU | 같음 | 같음 | 아니요 | 아니요 | A3:21, A3:23, B1:25, S1:29 |
| P05 · 정책 std·정규화 | std 1.0, actor·critic 정규화 끔 | 같음 | 같음 | 아니요 | 아니요 | A3:18, A3:19, B1:20, S1:24 |
| P06 · 할인·GAE | gamma 0.99, lambda 0.95 | 같음 | 같음 | 아니요 | 아니요 | A3:34, A3:35, B1:40, S1:44 |
| P07 · KL·스케줄 | desired KL 0.01, adaptive | 같음 | 같음 | 아니요 | 아니요 | A3:33, A3:36, B1:39, S1:43 |
| P08 · loss 계수·clip | entropy 0.01, value 1.0, PPO clip 0.2, clipped value | 같음 | 같음 | 아니요 | 아니요 | A3:26, A3:29, B1:42, B1:45, S1:46, S1:49 |
| P09 · gradient clip | 1.0 | 1.0 | 1.0 | 아니요 | 아니요 | A3:37, B1:44, S1:48 |
| P10 · 목표 update | 1500 | 3001 | 6000 | 예 | 예 | A3:14, B1:4, S1:4 |
| P11 · 저장 주기 | 50 | 25 | 100 | 예 | 예 | A3:15, B1:8, S1:12 |
| P12 · runner 재개 설정 | 기본 `resume=false` | `resume=true`, NVIDIA pretrained | `resume=false` | 아니요 | 예 | A3:12, A6:211, B1:14, S1:18 |

### Domain randomization 및 reset

| ID · 항목 | A | B | S | A와 다름 | B와 다름 | 근거 |
|---|---|---|---|---|---|---|
| D01 · 로봇 마찰 | static 0.8, dynamic 0.6 고정 | 같음 | static·dynamic 각각 0.2~1.2 무작위 | 예 | 예 | A0:154, B0:709, S0:762 |
| D02 · base 질량 추가 | [-1,3] kg | [-1,3] kg | [-1,2] kg | 예 | 예 | A1:34, B0:749, S0:803 |
| D03 · base COM | 끔 | 끔 | x/y/z 각각 ±0.05 m | 예 | 예 | A1:49, B0:757, S0:811, S0:837 |
| D04 · PD 이득 | 무작위화 없음 | 없음 | stiffness·damping 각각 0.9~1.1 배 | 예 | 예 | A0:149, B0:682, S0:851, S0:878 |
| D05 · 모터 세기 | 무작위화 없음 | 없음 | 0.9~1.1 배 | 예 | 예 | A0:149, B0:682, S0:889, S0:915, S6:32 |
| D06 · 관절 reset | 기본 자세 1.0배, 속도 0 | 같음 | 같음 | 아니요 | 아니요 | A1:37, B0:830, S0:958 |
| D07 · base 위치·yaw reset | x/y ±0.5 m, yaw ±3.14 | x ±0.1, y ±0.2 m, yaw ±0.05 | x/y ±0.5 m, yaw ±3.14 | 아니요 | 예 | A1:39, B0:797, S0:925 |
| D08 · base 속도 reset | 모든 축 0 | 모든 축 0 | 모든 축 0 | 아니요 | 아니요 | A1:40, B0:807, S0:935 |
| D09 · 주기적 밀기 | Go2 override로 끔 | 끔 | term 없음 | 아니요 | 아니요 | A1:33, B0:843, S0:735 |
| D10 · 외력·토크 reset | 범위 0인 term | 범위 0인 term | term 없음. 세 판 모두 실제 외력 0 | 예, 설정만 | 예, 설정만 | A0:186, B0:758, B0:784, S0:735 |
| D11 · 복원 계수 | 0 고정 | 0 고정 | 0 고정 | 아니요 | 아니요 | A0:161, B0:715, S0:768 |

## A · B 둘 다와 다른 설정

아래는 위 표에서 양쪽이 모두 `예`인 행의 집합이다. **설정 행 수는 45개**이며 독립적인 원인 45개를 뜻하지 않는다. R11·R16·D10은 설정상 차이지만 보상 또는 외력 효과가 0이다. P10·P11은 학습 길이·저장 빈도 차이로서 당장 서는 행동의 직접 원인으로 볼 근거가 없다.

| 범주 | 양쪽과 다른 행 | 수 |
|---|---|---:|
| 보상 | R02, R05, R08, R09, R10, R11, R12, R13, R14, R15, R16 | 11 |
| 명령 | C01, C02, C06, C07, C09, C10, C11, C12, C13, C14 | 10 |
| 종료 | T02, T03, T04 | 3 |
| 지형 | G01, G02, G03, G04, G05, G06, G07, G09, G13 | 9 |
| 관측 | O01, O02, O03 | 3 |
| 행동 | X03 | 1 |
| PPO 범위 | P10, P11 | 2 |
| DR | D01, D02, D03, D04, D05, D10 | 6 |
| 합계 |  | **45** |

### 원인 후보를 좁히는 다음 측정

거친 바닥에서의 정지를 이 표만으로 설명할 수 없다. 설정상 우선 확인할 수 있는 **가설**은 (1) 명령 샘플의 `stand`·`spin`·깃발 완료 후 0 명령 비율과 실제 정지 시각의 겹침, (2) 지형 23열의 원시 비율 정규화와 당시 level·terrain type, (3) 발 공중 시간 보상 제거와 자세·충돌 벌점의 활성 비율, (4) body 선속도 정책 관측 제거, (5) 자세/발 아래 종료와 episode 길이의 변화다. 각 가설은 정지 구간의 실제 command·terrain·reward·done 로그로 반증할 수 있다. 현재 이 문서는 그 로그를 재집계하지 않았다.

## 검증

- 원문: A는 설치 Isaac Lab 코드, B와 S는 각각 해당 run의 `params/env.yaml` 및 `agent.yaml`을 읽었다. 비교 대상이 `PLAY` cfg가 아님을 A1:73 이후로 확인했다.
- 계산: S 지형 원시 가중치 합 0.46, `23×(각 가중치/0.46)`은 5·5·4·4·2·2·1이다. A5:216-245의 정규화·열 배치와 대조했다.
- 미확인: 소스 S2·S3의 실행 당시 해시, 실제 관측 텐서 shape, 정지 사건의 시간별 명령·보상·종료 상관, A 원 체크포인트 초기화 실체. 현재 소스 설명을 실행 YAML 자체의 확정 증거로 바꾸지 않았다.
