> 분류: A/정책학습 · 실기 연결 설계 초안 (50 S1-x · 42 T0 · 팀장 10/20 N-1)
> 작성: sonnet-code 세션 (10/20 오후), lead 의뢰 SC-6
> 근거: 공식 저장소 얕은 clone 읽기(unitree_mujoco 1eb6642 · unitree_sdk2 d1abf00 · unitree_sdk2_python 814556d · unitree_rl_lab 4960b84) · 설계 23 §4 · 31 §5 · 42 §1 · pip 휠 목록 조회(설치 안 함)
> 요지: 공식 경로(Isaac Lab → unitree_mujoco sim2sim → ctrl --network eth0 sim2real)는 C++ unitree_sdk2 가 Ubuntu 20.04 전제라 이 Windows 에서는 안 돌고, WSL2 Ubuntu-24.04 에서 도는지는 미확인이다. 우리 정책 노드는 파이썬으로 짜서 DDS(rt/lowcmd · rt/lowstate) 한 겹만 갈아 끼우면 MuJoCo 와 실기에서 같은 코드가 된다. 눈 없는 S1-blind 만 이 길로 실기에 올릴 수 있고 base_lin_vel 을 쓰는 NVIDIA · v2 는 sim2sim 확인용이다
> 상태: 초안 · lead 검토 전 · 실행한 것 없음(조사와 설계만)

# 정책 노드 설계 초안 (policy_node)

## 1. 「이 Windows 에서 도는가」 판정

| 구성 | 요구 | 판정 | 근거 |
|---|---|---|---|
| unitree_mujoco C++ 시뮬 (`simulate`) | unitree_sdk2 C++ 설치(cmake · `sudo make install`), libyaml-cpp · boost · glfw | **Linux 필요** | unitree_mujoco README 설치 절, unitree_sdk2 README 「OS (Ubuntu 20.04 LTS)」, CMake 에 Windows 분기 없음(grep 0). 이 기기는 MSVC 없음(메모리 ws-3dgs-toolchain-limits) |
| unitree_rl_lab `deploy/robots/go2` (`go2_ctrl`) | 위와 같음 + ONNX Runtime, 가상 FSM(Passive → FixStand → Velocity) | **Linux 필요** | README Deploy 절. 읽는 것은 `policy_dir/params/deploy.yaml` · `exported/policy.onnx` |
| unitree_mujoco 파이썬 시뮬 (`simulate_python`) | unitree_sdk2_python(`cyclonedds==0.10.2` 고정), mujoco, pygame | **Windows 는 막힘으로 보임(미확인)**, Linux 가능 | isaac311(py3.11) 에서 `pip download cyclonedds==0.10.2/0.10.5 --only-binary` 모두 실패(Windows 이진 휠은 11.0.1 만 있음), 소스 빌드는 cmake · C 컴파일러 필요. mujoco 3.16.0 은 cp311 win_amd64 휠이 있다. 11.0.1 이 unitree IDL(0.10.2 기준)과 호환되는지는 **미확인** |
| unitree_sdk2_python 자체 | CRC | Windows 도 가능 | `utils/crc.py` 가 Linux 가 아니면 파이썬 구현(`_crc_py`)으로 간다. 단 `utils/timerfd.py` 는 리눅스 전용 |
| MuJoCo 파이썬 시뮬 자체 | `mujoco` 휠 | Windows 가능 | 위 휠 목록 |
| WSL2 Ubuntu-24.04 | 이 기기에 `Ubuntu-24.04`(WSL2, 정지 상태) 가 이미 있음 | **sim2sim 은 여기가 현실적**. 단 sim2real(eth0)은 WSL 네트워크(미러드 모드 여부) 때문에 **미확인**, 어차피 Linux 이전(10/22 뒤) 이후 본선 |

**결론**: 「Windows 네이티브 불가(미확인 하나 포함), Linux 필요」. 지금 당장 sim2sim 을 하려면 **WSL2 Ubuntu-24.04 에서 파이썬 경로(cyclonedds 0.10.2 manylinux 휠 + mujoco)** 가 가장 싸다. 실행 전 lead 확인이 필요한 것: (a) WSL 에 pip 설치(cyclonedds · mujoco · unitree_sdk2_python 을 clone 한 곳에서 `pip install -e`), (b) 예제 실행, (c) 외부 DDS 를 로컬(`lo`)에서만 쓸 것.

## 2. 공식 구조에서 가져올 것

- DDS 토픽: `rt/lowcmd`(우리가 쓴다) · `rt/lowstate`(우리가 읽는다) · `rt/sportmodestate`(실기에서 sport 서비스를 끄면 못 읽는다. MuJoCo 는 분석용으로 계속 낸다: unitree_mujoco README 노트).
- 모터 번호는 실기와 같다(README 노트). Go2 SDK 순서는 `FR(hip thigh calf), FL, RR, RL`(unitree_rl_lab `unitree.py` 의 `joint_sdk_names`), Isaac 관절 순서와 **다르다**. 공식은 학습 때 `export_deploy_cfg` 가 `joint_ids_map` 을 써서 `params/deploy.yaml` 로 넘긴다 → 우리도 같은 파일 한 벌을 학습 쪽에서 내보내야 한다(§4).
- 공식 상태기계: Passive(모터 `mode 1` · kd 3, 힘 빼기) → FixStand(보간으로 서기: `qs` 0 → 1.36/−2.65 → 0.8/−1.5, kp 60/80/80 · kd 5/4/4) → Velocity(정책). Velocity 중 `bad_orientation(1.0)` 이면 Passive 로 떨어진다(`State_RLBase.cpp`). **우리 기본 자세는 달라서**(§4) FixStand 의 목표 자세는 우리 값을 쓴다.
- 공식 C++ 관측 목록은 `base_ang_vel · projected_gravity · joint_pos(_rel) · joint_vel_rel · last_action · velocity_commands · gait_phase`, history_length 지원. **`base_lin_vel` 과 높이 스캔은 없다.** 즉 공식 배포 경로에 올릴 수 있는 정책은 눈 없는 정책뿐이다.

## 3. 노드 구조

```
 입력 (앱 · 조이스틱 · 키보드 어댑터)          정책 노드 (policy_node, 파이썬)                 DDS 어댑터 (갈아 끼움)
 vx vy wz  STOP  deadman  mode  ─────────►  명령 정리기 (31 §5)                              ┌ MuJoCo: unitree_mujoco (domain 1, lo)
                                               │  clip · 지형 등급 · 후진 시간 제한           └ 실기:  Go2 (domain 0, eth0)
                                               ▼
   rt/lowstate ◄─────────────────────────  관측 조립 (Isaac 과 같은 순서 · 스케일)  → 정책(onnx 또는 torch) 50 Hz
                                               │ 행동 a (12)
                                               ▼
                                          목표 q = default + scale * a   (필요하면 지연 버퍼)
                                               │ 
   rt/lowcmd ◄──── 500 Hz LowCmd 루프 (q, dq=0, tau=0, kp, kd, CRC) ◄── 최신 q 목표를 보간 없이 유지
```

- **두 스레드**: 정책 스레드 50 Hz(20 ms) 가 목표 `q` 를 만든다. LowCmd 스레드 500 Hz 가 가장 최근 목표를 계속 보낸다(정책이 늦으면 직전 값을 유지, 0.3 s 넘게 늦으면 §5 의 감시). Windows 에서는 `timerfd` 가 없어서 두 루프의 정밀 타이머는 `time.perf_counter` 기반 대기로 바꿔야 한다(Linux 이전 뒤에는 `timerfd`).
- **DDS 어댑터 인터페이스** (이것만 갈아 끼운다): `read_lowstate() -> {q[12], dq[12], tau[12], imu quat/gyro, foot_force[4], wireless_remote}`, `write_lowcmd(q, kp, kd, mode)`, `read_sportmodestate()`(MuJoCo 에서만, 실기에서는 `None`). 어댑터가 모터 번호 ↔ Isaac 관절 순서 변환(`joint_ids_map`)과 CRC 를 맡는다.
- 정책 호출은 `torch` 또는 `onnxruntime`. rsl_rl 체크포인트는 Isaac Lab 의 `export_policy_as_onnx` 로 한 번 내보내고 **원본 `.pt` 와 같은 입력에서 같은 출력인지(1e-5)** 를 시험한다.

## 4. Isaac 과 같은 관측 · 행동 계약 (학습 쪽이 `deploy.yaml` 로 내보낸다)

S1-blind 기준(우리 env, `foothold_s2/tasks/s1_env_cfg.py`):

| 항목 | 값 |
|---|---|
| o_t 45 | `base_ang_vel`(3, 몸 틀) · `projected_gravity`(3) · `velocity_commands`(3) · `joint_pos_rel`(12, 기본 자세 뺀 값) · `joint_vel_rel`(12) · `last_action`(12). 순서 · 배열이 이 순서 그대로여야 함 |
| 입력 | blind 는 o_t 11 스텝(현재 + 이력 10)을 이어 붙인 495. scan 판(232)은 높이 스캔이 있어 **실기 불가** |
| 행동 | 목표 `q = default + 0.25 * a`, 관절 12 개 Isaac 순서 → SDK 순서로 변환 |
| 기본 자세 | Isaac Lab Go2: hip FL/RL +0.1 · FR/RR −0.1, thigh 앞 0.8 · 뒤 1.0, calf −1.5. 공식 FixStand 의 0.0/0.8/−1.5 와 **다르다**. 반드시 우리 `default_joint_pos` 를 쓴다 |
| 게인 | 학습 때 kp 25 · kd 0.5(`go2_params.py`). LowCmd 에도 같은 값을 보낸다 |
| 토크 한계 | hip · thigh 23.5 N·m, calf 45.43 N·m(`go2_params.py`). 실기는 제조사 한계가 우선 |
| 지연 | 학습에 0~15 ms 행동 지연이 있다(`delayed_action.py`). 실기 지연 측정 값은 별도 이어 학습(42) |
| 센서 | `base_lin_vel` 은 **S1-blind 정책에 없음**(critic 에만). 따라서 sport mode 상태가 없는 실기 저수준 모드에서도 입력이 만들어진다 |

내보낼 파일: `params/deploy.yaml`(공식 형식을 따른다: `joint_ids_map` · `step_dt` · `stiffness` · `damping` · `default_joint_pos` · `commands.base_velocity.ranges` · `actions` · `observations`) + `exported/policy.onnx`. 형식은 공식 `export_deploy_cfg.py` 와 같게 두면 나중에 공식 C++ ctrl 로도 읽을 수 있다(우리 history · 이력 지원 여부는 공식 `observation_manager.h` 에 `history_length` 가 있어 가능해 보이나 **미확인**).

## 5. 안전 상태기계 (23 §4 · 42 §1 · 31 §5)

| 상태 | 동작 | 전이 |
|---|---|---|
| PASSIVE | kp 0 · kd 3(공식 Passive), 힘을 뺀다 | 시작 시. `stand` 명령 → FIXSTAND |
| FIXSTAND | 우리 기본 자세로 보간(공식 `ts: [0, 1, 2]` 와 같이 2 초) | 서기 완료 + 자세 정상 → POLICY. 실패 → PASSIVE |
| POLICY | 50 Hz 정책, 500 Hz LowCmd. 명령 정리기 통과한 명령만 | STOP · deadman · 관측 이상 · 자세 이상(`bad_orientation` 1.0 rad) → HOLD |
| HOLD(STOP 래치) | 정책에 세 칸 0 을 계속 줘 서기 유지(후보 ①, 정지 env 로 학습됨, 14 §3). **자동 재개 없음**, 사람이 해제해야 POLICY 로 | 10/10 안정이 H42-3 기준. 불안정 · 30 s 넘게 지속 → SPORT |
| SPORT | 정책을 끊고 sport mode(StandUp) 로 복귀(후보 ②) | 실기 전용. 시뮬에는 없다 |
| DAMP | 힘 빼고 앉기(후보 ③). **평지 판정일 때만**(계단 · 듬성한 지형 위에서 바로 빼면 넘어짐, APPROVED H) | |

- **deadman 0.3 s**: 명령이 0.3 s 끊기면 명령을 0 으로 하고 HOLD 후보 경보. **heartbeat 1.0 s** 끊기면 STOP 래치(23 §4).
- **STOP 은 모든 것을 멈춘다**: 명령 0 + 잠금 + 자동 재개 없음. 앱에서 STOP 이 오면 LowCmd 루프는 계속 돌되 목표를 «현재 목표 유지»로 바꾼다.
- **정책 프로세스가 죽음**: 어댑터가 0.3 s 안에 감지 → DAMP 가 아니라 제조사 정지(모터 유지) 우선(23 §4 가정). 별도 감시 프로세스가 `rt/lowcmd` 수신 중단을 본다.
- **리모컨 우선권**: LowCmd 모드에서 리모컨 입력의 효과는 SDK 로 확인되지 않았다(42 첫 주 확인, **미확인**). T0 에서 실기 순정 모드 상태로 `wireless_remote` 만 읽어서 확인.
- **명령 정리기(31 §5)**: 이어진 지형은 학습 범위 clip(vx ±1.5 · vy ±1.0 · wz ±2.0). 듬성한 지형은 vy ±0.2(가정) · 후진 −0.3 이내 + 연속 2 s · 누적 0.6 m 넘으면 0 · 회전 이동 중 ±1.0 · 제자리 ±1.2. 지형 판정은 12 문서 재구성 지도(S2 이후)에서 나오며, **S1-blind 에는 지도가 없으므로 지형 등급을 외부(앱)가 알려 주거나 보수적으로 「듬성한」 규칙을 쓴다**.

## 6. 첫 확인 대상: MuJoCo 에서 서고 걷는가

1. **환경**: WSL2 Ubuntu-24.04, `pip install cyclonedds==0.10.2 mujoco numpy pygame`, `unitree_sdk2_python` 을 clone 한 곳에서 `pip install -e .`, `unitree_mujoco/simulate_python/unitree_mujoco.py` 를 `DOMAIN_ID 1 · INTERFACE lo` 로. 실행 전 lead 확인 필요.
2. **서기 확인(정책 없이)**: 정책 노드의 PASSIVE → FIXSTAND 만으로 MuJoCo Go2 가 서는지, 우리 기본 자세로 서 있는지(발 높이 · 몸 높이 0.27~0.34 m).
3. **정책 걷기 확인**: S1-blind 10 update 체크포인트는 걷지 못하므로 의미 없음 → **정식 S1 학습 체크포인트가 나온 뒤**. 그 전 대리 확인으로 **NVIDIA · v2 체크포인트**를 쓴다. 단 둘 다 `base_lin_vel` 과 높이 스캔을 입력으로 쓰므로(S0 분석), MuJoCo 에서는 `rt/sportmodestate` 의 속도와 **평지에서의 0 높이 스캔(모든 값 0)** 을 넣는 sim2sim 확인일 뿐이고 실기로 가는 길이 아니다. 판정은 「전진 0.5 m/s 로 10 초간 넘어지지 않고 앞으로 간다」 정도의 느슨한 것.
4. MuJoCo 와 Isaac 의 물리 차이(마찰 · 접촉 모델 · 관절 마찰 · 모터 모델)로 걸음이 달라지는 것은 sim2sim 의 목적이다. 안 걷는다고 정책 결함으로 읽지 않는다. 일치를 요구하는 것은 **관측 · 행동 계약**(§4)이다: 같은 입력(관절 상태 · IMU · 명령)을 Isaac 쪽 함수에 넣은 값과 노드의 관측 벡터가 1e-6 으로 같음을 L0 로 시험한다.

## 7. 시험 계획 (L0 는 DDS 없이)

| 시험 | 기대 |
|---|---|
| 관측 조립 | 기록한 `(q, dq, imu, cmd, last_action)` 로 노드의 관측 벡터를 만들고 Isaac env 의 같은 상태 관측과 1e-5 |
| 관절 순서 변환 | SDK ↔ Isaac 순열이 되돌림으로 항등. 이름으로 맞췄을 때 왼 · 오 · 앞 · 뒤가 뒤바뀌지 않음(negative control: 순열을 틀리게 하면 걸림) |
| 행동 → 목표 | `a = 0` 이면 목표가 기본 자세, 스케일 0.25 |
| 명령 정리기 | 31 §5 표의 경계값(후진 −0.31 → −0.3, 연속 후진 2.01 s 에서 0, 누적 0.61 m 에서 0 등) |
| STOP 래치 | STOP 입력 뒤 정리기 출력 0, 해제 전에는 어떤 명령도 통과하지 않음, 해제 뒤에도 자동 재개 없음 |
| deadman · hb | 시뮬 시계로 0.3 s · 1.0 s 에 정확히(±0.1 s) 동작(H42-4) |
| ONNX 내보내기 | `.pt` 와 같은 입력에서 같은 출력(1e-5) |

## 8. 열린 것

- WSL2 에서 cyclonedds 0.10.2 휠이 깔리는지 · `unitree_mujoco` 파이썬 시뮬이 도는지: **미확인**(실행 전 lead 확인).
- sim2real 네트워크(WSL 미러드 vs Linux 이전 뒤): 미확인.
- 리모컨 우선권, sport mode 복귀 방법, 정책 프로세스 죽음 감지: 42 첫 주 · 23 §4 대로 미확인.
- 공식 C++ ctrl 이 우리 history 입력(495)을 읽는지: 미확인.
- 지형 등급 입력(앱 또는 지도): S1-blind 에서는 외부 입력 가정.
