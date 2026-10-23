> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 (sol 분석 · lead_tmp 원자료 대조) · 2026-10-23
> 근거: lead_tmp RESULT-EX23-25 및 원본 NPZ, sonnet-code 7cab5223, 설치된 Isaac Lab 2.3.2, CPU 정답 입력
> 요지: 전진 관절·접촉 자료가 보폭에 관해 말할 수 있는 범위를 정하고 estimator 및 발 접선 속도 계측 계약을 제안한다.
> 상태: 읽기·CPU 분석 완료 · 보폭·미끄러짐 실측 불가 · 새 학습 승인 아님
> 판: v1.0

# SOL-23e · 관절 주기, estimator 51, 발 접선 속도

## 핵심 결론

`RESULT-EX23-25.md`와 `figs/ex23-25-lead-review/joint_comparison.png`, `analyze_saved.py:129-153`, `joints.csv`를 읽고, 스크립트가 가리키는 네 원본 NPZ를 별도로 열었다. EX11 model_1500, v2 model_3000, EX23·25 model_1500의 flat 기록은 모두 600표본, 0.02초 간격, 3~6초 명령 `[1,0,0]`이다. 그러나 EX25의 뒤 1.5초 실제 전진 속도는 **0.907 m/s**, 나머지는 약 **1.01 m/s**이다. 더구나 저장 항목에 발 XY와 접촉점 속도가 없다. 지금 자료로 관절 움직임의 크기와 접촉 전환 빈도는 말할 수 있지만 **실제 보폭이 짧은 총총걸음인가, 긴 걸음인가, 접촉 중 미끄러지는가의 순위는 매길 수 없다**.

원자료: `C:/Users/AI-WS01/s2_lab/videos/joint_1022/ex11_flat_feet.npz`, `v2_flat_feet.npz`, `C:/Users/AI-WS01/s2_lab/videos/mid500_1022/ex23r_1500/run_flat_feet.npz`, `ex25_1500/run_flat_feet.npz`. 모든 입력의 SHA와 발별 CPU 재계산 값은 [ROM-contact-sol-23e.csv](ROM-contact-sol-23e.csv)에 있다. `analyze_saved.py`의 관절 그림은 중앙값과 25~75 백분위이며, 아래 ROM은 같은 NPZ에서 직접 계산한 **95~5 백분위 차**다. ROM은 발의 전진 변위가 아니다.

| flat 3~6초 · 명령 1.0 | 실제 vx 후반 m/s | 네 thigh ROM, 도 | 네 calf ROM, 도 | 네 발 재접촉 주기 중앙값, 초 | 접촉 비율 FL/FR/RL/RR |
|---|---:|---|---|---|---|
| EX11 model_1500 | 1.014 | 77.4 / 57.7 / 36.1 / 47.0 | 47.6 / 43.1 / 41.0 / 43.4 | 0.40 / 0.40 / 0.44 / 0.80 | .68 / .39 / .89 / .90 |
| v2 model_3000 | 1.008 | 25.7 / 29.8 / 41.0 / 36.8 | 24.6 / 31.9 / 17.8 / 20.7 | 0.26 / 0.43 / 0.44 / 0.44 | .67 / .63 / .55 / .56 |
| EX23 model_1500 | 1.017 | 43.0 / 45.2 / 52.5 / 48.6 | 26.9 / 38.3 / 40.3 / 26.7 | .48 / .48 / .48 / .48 | .66 / .51 / .55 / .61 |
| EX25 model_1500 | .907 | 49.9 / 64.3 / 63.5 / 40.7 | 41.7 / 46.6 / 31.0 / 34.2 | .54 / .54 / .54 / .54 | .47 / .57 / .65 / .76 |

주기는 3초 안의 접촉 false→true 전환 사이 간격을 발마다 계산한 값이다. EX11 RR의 .80초와 v2 FL의 .26초처럼 발별 차이가 있어 한 숫자로 각 판의 보행 주기를 단정할 수 없다. EX11 뒤 발은 표본 대부분 접촉 상태이고 발 z의 95~5 백분위 차도 각 약 0.004m여서, rear touchdown 검출이 실제 swing을 대표하는지 의심스럽다. EX23의 `속도 × .48초`와 EX25의 `속도 × .54초`는 모두 약 .49m이지만 이는 **몸 이동 대용값**일 뿐 발의 착지 간 거리나 보폭이 아니다. 각기 다른 정책·훈련량·실제 속도·접촉 양상 위에 보폭 순위를 붙이지 않는다. 네 NPZ에는 `joint_pos`, `foot_z`, `foot_contact`, 몸 좌표 `vx`, `wz` 등은 있으나 발 XY·contact point·root XY·yaw 전체 궤적이 없다. `C:/Users/AI-WS01/s2_lab/record_seq.py:159-178,221-224`도 발의 z만 저장한다.

## START estimator 51 · 원문과 우리 구현

START 원문 로컬 `C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt:42-139`은 I-E estimator가 과거 고유감각과 재구성 높이 지도를 융합해 암묵 latent와 명시 속도·몸/발 주변 지형 표현을 내고, actor가 현재 45칸 고유감각과 이를 소비한다고 설명한다. 지도·속도·몸/발 높이의 보조 지도 학습과 PPO의 비대칭 구조도 원문이다. 아래 **51칸 분할과 층 폭·활성화·history 10·loss 축**은 이 Go2 구현의 구체화 또는 명시된 가정이며 원문에 있는 공식 코드 크기로 취급하지 않는다. `models/start_perception.py:1-15,26-64`가 공개 코드를 이식한 것이 아니라고 밝힌다.

| 구성·소비 | 실제 구현 | 출처 |
|---|---|---|
| 입력·시간 상태 | 현재 45칸, 과거 10×45 → MLP 256→128 → GRU 128. reset 때 hidden 0, 이력은 첫 관측으로 채움 | `models/start_perception.py:26-35,132-155,263-306` |
| 지도 가지 | `map_input=none`이면 CNN·TR-Net 없음, otherwise 32×16 지도를 CNN 1→32→64로 16×8 토큰 128개로 만듦. prop 토큰 1개와 transformer encoder 2층, head 1개. 토큰 위치·층수는 우리 가정 | `start_perception.py:55-60,135-166,255-258,301-315` |
| 51칸 | `z` 16, 몸 선속도 추정 `v` 3, 발 지도 latent `zf` 16, 몸 지도 latent `zb` 16 순서. actor 입력은 현재 45 + 51 = 96 | `start_perception.py:34-40,161-167,317-329`, `runners/start_runner.py:181-196` |
| 학습 | 현재 스텝 rollout에서 추정하고 PPO 입력에 고정, PPO update 후 별도 Adam으로 지각 sequence loss 갱신. 손실은 KL, 다음 관측, 실제 몸 속도, 몸/발 GT 지도, TR-Net 재구성. `zero`라도 지각망은 계속 계산·학습 | `start_runner.py:106-109,273-330,467-488`, `start_perception.py:349-394` |
| 처치 | EX11 `est_mode=zero`는 `_est_in`에서 actor의 51칸을 전부 0, EX12·23·25 `learned`는 추정 51칸을 그대로 넣음. 수집·PPO 입력·평가 `S2Policy`가 공통 `_ppo_obs`를 사용 | `start_runner.py:163-196,276-280`, `eval/adapters.py:425-435` |

`zero`는 추정기를 제거한 네트워크나 추정 손실을 끈 판이 아니다. EX11과 EX12는 같은 환경의 actor 소비 처치 대조다. EX23은 `force_gt=True`로 I-E에 정답 지도를 고정 공급하는 진단이고, EX25는 `map_input=none`이다. `AdaSmpl.sample`의 강제 정답 경로와 저장·복원은 `start_perception.py:215-232`에 있다. `sonnet-code 7cab5223`의 평가 `adapters.py:451-480`은 체크포인트에서 `map_input`은 복원하지만 `force_gt`를 새 runner cfg에 넣지 않는다. 또 `S2Policy.__init__:419-423`은 `use_gt`를 0으로 시작한다. EX23의 과거 평가가 학습 때 정답 지도를 소비했는지 별도 검증해야 하는 이유다. 현재 `s2_lab/record_seq.py:67-77`은 이를 수동 보정해 찍은 기록이며, 그 파일을 이번에 고치거나 재촬영하지 않았다.

## 발 XY 접선 속도 계측 계약

**현재 데이터:** 발별 `foot_z`, 정상 접촉력의 크기 `>1N` Boolean만 기록한다 (`record_seq.py:159-178`). 저장 NPZ에서 발 중심 XY, 발 링크 선속도, 접촉점 좌표, 지면 운동을 역산할 수 없다. 관절 FK로 몸 기준 발 위치를 추정할 수는 있어도 root의 world XY·yaw 시계열이 없고, 접촉점이나 지면 속도도 없다. 따라서 기존 자료의 미끄럼 수치는 **미측정**이다.

**정의:** 접촉 발 `i`의 world 접촉점 `p_i`, 발 링크 COM 위치 `c_i`, COM 선속도 `v_i`, 각속도 `ω_i`, 그 지면의 해당 점 속도 `v_ground(p_i)`를 같은 물리시각에 얻는다. `v_rel_xy = [v_i + ω_i × (p_i-c_i) - v_ground(p_i)]_{world,xy}`, `slip_speed=||v_rel_xy||` m/s이다. 정적 terrain mesh임이 확인된 장면에서는 `v_ground=0`이고, 움직이는 플랫폼은 실제 속도가 없으면 미확인으로 둔다. 접촉 유효 표본은 해당 발의 정상 `net_forces_w` norm이 1N 초과이고 해당 지면의 유효 `contact_pos_w`가 유한일 때뿐이다. 발 중심 속도 `||body_com_lin_vel_w - v_ground||xy`는 값싼 **대용 지표**로 분리 기록한다. 회전하는 발에서는 접촉점 속도와 다르다. `net_forces_w`는 정상력이며 마찰력을 측정했다고 쓰지 않는다 (`contact_sensor_data.py:75-108`).

설치된 Isaac Lab은 `articulation_data.py:940-965,1071-1080`에 COM 위치·선속도·각속도를 준다. `contact_sensor_data.py:28-45`의 `contact_pos_w`는 필터 대상별 **평균 접촉점**이며 현재 `s1_env_cfg.py:65`의 센서는 `track_contact_points=False`, 필터도 없다. 이를 켜려면 필터 prim과 sensor body의 one-to-many 조건, contact buffer 상한을 먼저 검증해야 한다 (`contact_sensor_cfg.py:23-72`, `contact_sensor.py:317-337`). 평균 접촉점은 복수 접촉점 각각의 slip 분포가 아니다. 필터가 지형과 실제로 결선되지 않으면 contact-point 지표를 생성하지 않고 대용값만 표시한다.

**채집 시각과 비용:** 평가에서는 `env.step` 뒤 같은 물리시각의 접촉력·pose·velocity를 읽고 episode/reset 경계를 분리한다. 20ms 제어 간격에서만 저장하면 5ms 물리 substep의 순간 미끄럼을 놓칠 수 있어 가능하면 5ms에서 집계한 평균·p95·최대·접촉 표본 수를 발별로 쓴다. 학습에서는 첫 진단에만 켜고, GPU에서 env별 유효 표본 합과 분위용 작은 누적값을 유지해 update 경계에만 CPU로 옮긴다. 3072 env×4발×3축×float32×50Hz의 **속도 텐서 한 벌만** 약 7.37MB/s에 해당한다. 접촉점 추적의 PhysX 비용과 VRAM 증가는 미측정이라 학습 전체에 상시 켜기 전에 별도 실측이 필요하다. 측정 코드를 actor 관측이나 보상에 넣는 것은 이번 제안 범위가 아니다.

**CPU 정답 입력:** `v_com=(1,0,0)`, `ω=(0,0,2)`, `p-c=(0,0.1,0)`, `v_ground=(0.3,0,0)`이면 접촉점 속도 `(0.8,0,0)`, 상대 접선 속도 **0.5m/s**다. 발 중심 대용값은 0.7m/s여서 다르다. 정상력 `[1.01,0.99]N`과 문턱 `>1N`에서는 첫 표본만 유효하다. CUDA를 숨긴 `isaac311` NumPy 정답 입력으로 두 결과를 확인했다. 추가 CPU 반례는 이동 지면을 0으로 취급한 경우, 발 중심을 접촉점으로 잘못 쓴 경우, reset 앞뒤를 한 접촉 구간으로 합친 경우, NaN 접촉점을 0으로 바꾼 경우를 각각 거절해야 한다.

## 팀장 제안 A/B의 해석 위험 · 실행 결정 아님

EX23 조건에서 scratch A의 0.8/0.6 고정과 B의 0.2~1.2만 바꾸고 두 판 모두 1501 update로 맞추는 안은 앞선 다중 처치보다 마찰 질문을 좁힌다. 다만 B의 `make_consistent=True`는 dynamic을 static 이하로 자르므로 두 마찰 성분이 독립 균등분포는 아니다. 설치된 `events.py:180-264`는 64개 재질 bucket을 생성 때 한 번 만들고 startup에서 각 shape에 bucket ID를 난수로 배정한다. 같은 seed와 예산만으로 두 판의 다른 DR 실현값·명령·지형 노출이 **표본별 동일**하다고 증명되지 않는다. 마찰 처치에 따른 궤적·reset 수가 갈라지면 뒤의 공통 RNG 소비도 달라질 수 있다. 원인 분리를 위해 다른 startup DR의 실제 값, 재질 bucket 표본, 지형 행·열, 명령 시퀀스, reset 수와 유효 경험량을 기록하고 처치 외 cfg diff를 검사해야 한다. 성능 비교는 동일 사전 등록 평가 조건과 반복 단위가 필요하다.

scratch라면 부모 checkpoint 없이 시작해 `force_gt` 재개 누수는 줄지만, EX23의 정답 지도 처치를 두 판에 똑같이 결선하고 evaluator에서도 실제 소비를 확인해야 한다. `runners/start_runner.py:628-647`은 재개 시 `est_mode`·`critic_mode`만 검사하며 AdaSmpl 저장 상태의 `force_gt`를 덮어 복원한다. 따라서 어느 판이든 EX23 checkpoint에서 이어 붙이는 것으로 scratch를 대체하면 처치와 출발 조건이 바뀐다. 새 학습, 실행 코드 변경, GPU·Kit 실행은 하지 않았다.


## lead_tmp 취합 확인

16행의 원본 SHA와 각7개 계산을 `check_joint_evidence_1023.py`로 독립 재계산하여 일치했다. 알려진 접촉 전환 입력2개도 통과했다. 원고의 접촉점 조건 `비유한`은 수식·NaN 거절 요구와 반대로 적힌 오타라 `유한`으로 정정했다. 경사면에서는 XY가 아니라 실제 접촉 법선에 수직인 접선 투영이 필요하다. 물리 API의 실제 Kit 소비·접촉점 추적 부하는 이번에 측정하지 않았다.
