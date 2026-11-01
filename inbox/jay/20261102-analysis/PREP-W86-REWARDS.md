> 분류: A/정책학습
> 작성: 오흥재 (analyst 정리) · 2026-11-02
> 근거: 팀장 W86 지시 · EX-40 2df419b0 · EX-41 설계 c48d9bc7 §5 · 아래 CPU 시험
> 요지: 지형 상대 스윙 · 회전 0 L1 · 걸림 및 0 가중 항의 계산 모듈을 준비했다. EX-40 실행에는 연결하지 않았다.
> 상태: 준비 코드 v0.1 · CPU 26 통과 · 독립 두 겹 검토 대기 · Kit 미실행

# W86 보상 준비와 실제 연결 때 남은 일

## 1. 결정과 제안을 구별한 소비 계약

기준은 EX-40 최종 코드 2df419b0이다. EX-41/W72 실행 구현은 아직 없다는 lead 답변을 따른다. 준비 파일은 `foothold_s2/rewards/w86.py`, `w86-preparation.yaml`이며 기존 환경의 import나 RewardManager에 등록하지 않았다. 현재 원장과 학습 사본은 바꾸지 않았다.

| 항 | 준비한 계산과 가중 | 결정 또는 제안 | 실제 연결 때 필요한 값 |
|---|---|---|---|
| 회전 0 L1 | `abs(wz_body)`에 가중 −0.5를 한 번 적용. `abs(cmd_wz)<1e-6`이고 heading이 꺼진 env | −0.5는 결정. 설계 §5.1의 식과 가중에 음수가 중복된 표기를 피함 | body 각속도 · 실제 명령 · heading 마스크 |
| 스윙 | 발 아래와 진행 방향 앞의 최고 지지면 + 0.08 m를 목표로 Spot 계열 지수식 | 0.08 m와 지형 대응은 지시. +0.5 · 분모 0.05 m² · tanh 배수 2는 v0.4 제안 및 Spot 참조 | 실제 collision mesh의 지면 z · 발 충돌 구의 바닥 z · 수평 발 속도 · 접촉 |
| 스윙 적용 범위 | 움직임 명령이 있고 공중에 있는 유효 발만. 적용 발이 없으면 0 | 정지 보상 충돌을 줄이는 **우리 제안**, 원문 Spot과 다름 | moving_command 정의와 접촉 문턱을 실행 설정에 명시 |
| 걸림 | 한 발이라도 `norm(Fxy)>4*abs(Fz)`이면 1, 가중 −1 | 식과 −1은 기존 START `core.py:23,93` 값. EX-41 적용은 제안 | 발 순서를 이름으로 확인한 힘. 모서리 충돌의 대리 지표이며 모서리 접촉 자체를 입증하지 않음 |
| 몸 · 허벅지 충돌 | 힘 norm >0.1 N인 body 개수, 각각 가중 0 | 미리 등록 · 지금 0. 문턱은 기존 core 값 | base/head와 thigh 이름 목록을 따로 저장, 양쪽 중복 합산 금지 |
| 무릎 토크 한계 근접 | `relu(abs(tau)/limit−0.9)^2` 합, 가중 0 | 0.9는 준비 제안 | calf별 실제 적용 토크와 actuator 한계. W78의 0.95 기록 문턱과 별개 |
| 관절 한계 근접 | hard limit에서 0.05 rad 안쪽 여유를 넘은 양의 제곱 합, 가중 0 | 0.05 rad는 제안 | 자산별 관절 한계와 이름, soft limit 벌점과 중복 여부 |
| 체공 | 첫 접촉에서 `(air_time−0.5)` 합, 이동 명령일 때만, 가중 0 | 0.5 s는 제안 | touchdown 직전 체공 시간 · first_contact, reset 이력 비움 |
| 미끄럼 | 접지 중 수평 속도 제곱 합, 가중 0 | 미리 등록 · 지금 0 | 정적 지형 기준 world 수평 속도, 움직이는 지면에서는 상대 속도 필요 |
| 부드러움 | 행동 2차 차분 제곱 합, 가중 0 | 기존 `core.action_smoothness_l2`, action rate와 구별 | 현재 · 직전 · 전전 행동, reset 이력 비움 |
| 에너지 | `sum(abs(tau*qd))`, 가중 0 | 기존 `core.joint_power` | 적용 토크 · 관절 속도 |

## 2. 지형 높이와 후진 · 횡이동

설계 v0.4 §5.6은 먼저 world z를 쓰자고 했지만, 후속 팀장 W86은 **발 앞 지형 높이에 따른 목표**를 지시했다. 그러므로 이 준비 모듈은 첫 판부터 지형 상대 높이를 쓴다. 평지 z=5 m여도 목표는 5.08 m이며 0.08 m world z로 끌어내리지 않는다(CPU 수직 이동 불변성 시험).

`ahead_points_body`는 발 위치에서 `v_xy + wz × r_foot` 방향으로 샘플을 제안한다. 후진이면 뒤, 횡이면 옆, 제자리 회전이면 발마다 다른 접선 방향이다. 길이 [0, 0.05, 0.10] m는 **미측정 제안**이다. 현재 `foot_scan_*`에서 최근접 값을 뽑는 코드나 이 위치에 새 광선을 쏘는 Kit adapter는 아직 없다. 실제 발 스윙 궤적과 명령 방향이 다를 수 있으므로 진행 방향 샘플이 장애물을 항상 포함한다는 주장은 하지 않는다.

필수 광선 하나라도 무한대/NaN이면 그 발의 목표가 무효다. 유한 0 placeholder와 valid=false를 함께 반환해 구멍을 0 m 지면으로 둔갑시키지 않는다. 소비기는 무효 수와 원인을 반드시 기록한다. 발 링크 중심과 충돌 구 바닥의 차이는 실제 자산 반지름으로 보정해야 하며 아직 미확인이다.

Spot 식의 `tanh(2*speed)`는 수평 속도가 0이면 높이 오차를 지운다. 우리 마스크를 넣어도 **공중에서 발을 멈춰 든 채 움직임 명령을 받으면 보상이 1**일 수 있다. 이는 RR 들기 해소나 발 끌림 해소가 보장되지 않는 이유다. Kit 연결 전 검토에서 속도 가중을 유지할지, 위상 목표로 바꿀지 판단할 것. 이 파일은 해당 효과를 실측했다고 주장하지 않는다. σ=0.05는 분모이며 다시 제곱하지 않는다.

## 3. W72와 W78 인계

`propose_weights`는 **제안 기록만** 만든다. 초기값 또는 직전 전체 가중을 입력받고 바뀌지 않은 항은 보존한다. `before/weights/reason/evidence`를 남기며, swing/stumble 이외 변경과 미리 등록한 0 항 활성화를 거절한다. 임시 범위 swing [0,0.5], stumble [−1,0]도 승인이 아닌 준비안이다. 성과를 받아 증감하는 판단식, 250 회 경계 적용, optimizer/체크포인트 상태와 원장 동기화는 W72 주인이 구현해야 한다. 지금 자동 가중이 된다고 부르면 틀리다.

W78 v2 준비 함수 `foot_metrics`는 발별 분자/분모를 반환한다. 접지 이동 프레임 중 발 바닥 높이 <0.02 m이고 수평 속도 >0.05 m/s인 비율을 접지 미끄럼/끌림 **대리 지표**로, 비접지 중 같은 조건을 낮은 스윙으로 구별한다. 두 문턱은 기록용 제안이며 승급 문턱이 아니다. 무효 프레임 수는 별도이고 분모에서 조용히 사라졌다고 해석하지 않는다. 완전한 스윙 주기마다 정점 높이 · 최소 여유 · 이동 거리 · touchdown과 발별 p05/p50/p95를 쌓는 집계기 및 NPZ 저장 연결은 아직 미구현이다. 계단 면/모서리에 닿았는지는 힘 비율만으로 분류할 수 없어 geometry/접촉 body 로그가 더 필요하다.

미리 등록 0 항의 측정은 RewardManager와 별도로 연결해야 한다. 0 가중이면 manager가 term을 건너뛸 수 있어 설정에 이름만 올려도 값이 기록된다는 보장은 없다. 살아 있는 원장 대신 이 준비 YAML에 「미리 등록 · 지금 0」을 명시했다.

## 4. 검증과 한계

`CUDA_VISIBLE_DEVICES=''`인 CPU에서 다음 명령을 실행했다. 새 W86 14 + 기존 core 12 = **26 passed in 2.18 s**. 최초 모듈 없음 실패 후 구현했고, 경계 가중 보존 시험은 수정 전 1 FAIL/13 PASS, 고친 뒤 통과했다. 이는 반례 검증이며 Kit 효과 검증이 아니다.

```text
C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -m pytest foothold_s2/tests/test_w86_preparation.py foothold_s2/tests/test_rewards.py -q
```

답을 아는 입력: yaw=0.2→cost0.2, heading/nonzero 명령→0, 지면0/앞턱0.2→목표0.28, 지면+5→목표+5, 누락 광선→무효, 후진/횡/회전 샘플 방향, 한 발 오차0.1→`exp(-0.01*tanh(2)/0.05)`, Fxy=4Fz→걸림0·5Fz→1, 한계와 토크 값, 충돌·체공·미끄럼·행동·에너지 계산, 0 항 활성화 거부, 이전 경계 가중 보존, YAML과 함수 가중 일치, 접지/비접지 분모 구별.

실행 연결이 없는 준비 산출의 완료이며, EX-41 기동 가능 판정은 아니다. reviewer 코드 검토와 verifier 독립 숫자 검토를 요청한다. 실제 자산 이름·발 바닥·센서 시각·관측 frame·항별 dt·중복항·reset·원장·W72·Kit 측정은 연결자가 확인해야 한다.

## 5. 원문

- EX-41 설계 c48d9bc7 `inbox/jay/20261101-ex41/DESIGN-EX41-STAGE2-draft.md` §5.1·5.6·5.8·5.11.
- Isaac Lab 설치본 `C:/isaac/IsaacLab/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/spot/mdp/rewards.py:182` 및 [공식 소스](https://github.com/isaac-sim/IsaacLab/blob/v2.3.2/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/spot/mdp/rewards.py).
- EX-40 2df419b0 `foothold_s2/rewards/core.py:67`·`:76`·`:88`·`:93`, `start_rewards.py:60`, `nvidia_go2_rewards.py`. 참조 계수는 처치 효과의 근거가 아니다.
