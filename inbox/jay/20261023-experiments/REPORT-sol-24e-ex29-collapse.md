> 분류: 리서치
> 작성: sol · 2026-10-24
> 근거: EX29 고정 코드 d9517fb9, 학습 원자료, 네 평가 NPZ, EX23 저장 YAML 직접 대조
> 요지: 초기 실험은 정상 종료했지만 자세 실패가 초반부터 존재했고 90~124회 사이 급격히 지배적이 됐다. 행동 편향과 짧은 에피소드의 보상상 이득은 원인 후보이며 단일 원인은 미확정
> 상태: CPU 원자료 재계산 확인 · 새 Kit 실행 없음

# SOL-24e · EX29 초기 붕괴의 저장 기록 조사

`확인됨`: 아래 저장 원자료와 CPU 재집계. `가설`: 행동 편향 및 보상 유인과 최초 원인. 실험 문맥: [B500·EX29 200 기록](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6378262843).

## 판정

**확인됨.** EX29의 시작 상태 전체가 이미 뒤집혀 있던 것은 아니다. 학습 trace가 고정한 8개 환경의 update 0 첫 step은 모두 root z 0.400 m, 기울기 0°, episode 0이었다. 첫 rollout의 전 환경 `bad_orientation`은 0건이지만 update 1에 18건, 첫 10회 합계 739건, 첫 25회 합계 1,196건이다. 따라서 “90회부터 처음 실패했다”도 틀리다. 선택 8환경에서는 update 5 step 16의 한 종료 직전 기울기가 85.8°였고, 기록된 행동 최대 절댓값은 1.43이다. 전체 첫 실패의 환경별 root/action은 이 8환경 표본만으로 특정할 수 없다.

**확인됨.** update 50의 `Mean episode length` 876.48 step은 제어 dt 0.02초로 17.53초이고 `bad_orientation` 로그 비율은 0.2857이다. update 90에는 593.38 step과 0.2998, update 99에는 123.22 step과 0.8163, update 100에는 83.83 step과 0.8771, update 124에는 20.81 step과 0.9938, update 200에는 17.37 step과 0.9998이다. `step_evidence.jsonl`도 update 100~124에 `bad_orientation` 60,676건, update 175~199에 105,201건을 센다. 이는 하나의 episode를 센 값이 아니라 3072환경 × 24 step 안의 반복 종료 횟수이며 항목끼리 중복될 수 있다. 평균 지형 행은 update 50에 0.2136, 100에 0.0283, 149부터 0이다. 난도 상승 직후 붕괴한 형태가 아니다. 학습 로그의 episode 길이와 평가 결과는 서로 다른 측정이다. model 50의 동일 조건 GT/PRED 평가 자료는 이번에 확인하지 못했다.

**확인됨.** model 200 SHA `5977e6519d3d588a05822d9cba23f592139529fabb2bf357b485fb7fa0d3687b`의 네 `review_feet.npz`를 직접 다시 셌다. 평지 GT/PRED와 낮은 징검다리 GT/PRED는 각각 600 step, reset 34회, 모두 `bad_orientation` 단독 항목이다. 첫 reset은 네 경우 모두 step 16이고, 종료 직전 기록의 |roll| 평균은 1.451~1.454 rad, |pitch|는 0.057~0.061 rad이다. `roll`은 env.step 전 상태, 종료는 후 상태이므로 저장된 roll을 그대로 1.5 rad 종료 문턱과 대조하면 안 된다. GT/PRED map flag는 각각 실제로 참/거짓이고 관절 궤적도 완전히 같지 않다. 두 지도 선택과 두 지형 모두 옆으로 기우는 현상이다. 이것만으로 TR-Net 또는 지도 품질을 단독 원인으로 지목할 수 없다.

**유력한 가까운 기전, 인과 미확정.** 8환경 trace의 표집 행동에서 오른쪽 두 hip 평균과 왼쪽 두 hip 평균의 차는 첫 25회 평균 +0.061, update 100~124 +1.226, 200~224 +1.030 raw action 단위다. calf의 같은 차는 +0.032, +0.437, +1.255다. trace의 평균 pre-step roll도 +0.081에서 -0.261, -0.611 rad로 이동한다. model 200 평가에서는 거의 같은 부호의 큰 roll로 반복 종료한다. 행동 편향과 측면 자세 붕괴가 시간상 함께 나타난다는 증거다. trace 행동은 **wrapper clip·0.25 scale·지연·모터 적용 전**의 정책 표집값이며 토크나 실제 관절 목표는 저장되지 않았다. 원인을 특정 관절·PD·지도로 확정할 자료는 없다.

**가능한 학습 유인, 인과 미확정.** update 50의 평균 episode 보상은 -50.24, 길이 876.48 step이다. update 200은 -1.06, 길이 17.37 step이다. 두 몫은 각각 약 -0.057 및 -0.061 보상/step으로 비슷한데, 에피소드가 짧아져 누적 음수 보상의 크기가 줄었다. 저장된 `rewards` 목록에는 명시적 `bad_orientation`/종료 벌점 항이 없고, Isaac Lab은 종료를 계산한 다음 현재 step 보상을 계산하고 reset한다. 따라서 조기 종료가 벌점을 줄이는 편법일 **가능성**이 있다. PPO가 이 경로를 실제로 선택했는지 단일 실행만으로 증명되지 않으며, `Mean reward`와 `Mean episode length`는 logger의 이동 평균이다. A형 선속도 보상은 `min(v, cmd)`를 써 양의 명령에서 목표보다 빠른 속도를 벌하지 않는다. EX23의 B형 추종식과 다른 또 하나의 후보지만, 이 차이가 옆으로 쓰러짐을 낳았다고 확정할 수 없다.

## EX23 저장 설정과 EX29 실제 결선

원본은 EX23 `sonnet-code/logs/rsl_rl/foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/params/{env,agent}.yaml`와 EX29 `lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_topdown/2026-10-24_08-20-33_ex29-td-main/params/{env,agent}.yaml`이다. 각각의 실행 manifest HEAD는 `21ccae9d02b772e6397a7a8136a52f8e2aa6f635`와 `d9517fb9929f23e2bf5c0b51fe46a1b2df20f237`이다. EX29 manifest의 dirty diff는 0 byte다. 따라서 아래는 설정 차이이며, 원인 식별을 위한 한 변수 대조 실험이 아니다.

| 경로 | EX23 저장값 | EX29 저장값과 적용 확인 | 판단 |
|---|---|---|---|
| 출발 root·관절 | yaw ±3.14 rad, 관절 위치 배율 1.0 고정 | yaw 0, 관절 배율 0.5~1.5, `supported_spawn`이 실제 관절 FK를 읽어 XY만 지지 구간으로 이동. z는 기본 0.4 m를 보정하지 않음 (`s2_23f_topdown_cfg.py:62-74`, `s2_23f_spawn.py:41-60`, EX29 env.yaml:1433-1480) | 초기 8환경 pose는 직립이지만 첫 rollout의 root z는 일부 0.145 m까지 내려감. 무작위 관절 pose가 불안정성에 기여했는지는 미확인 |
| 행동·관절 순서 | `JointPositionAction`, scale 0.25, default offset, `clip_actions` 17 | 같은 `joint_names=.*`, `preserve_order=false`, scale·clip에 `DelayedJointPositionAction`을 더해 0~3 physics substep 지연 (`delayed_action.py:13-37`, env.yaml:1225-1236). trace 메타데이터는 로봇 관절 순서를 기록하지만 action slot→joint 대응의 별도 readback은 없음 | trace 8환경에서 raw |action|의 p99는 update 0에 2.52, 200에 4.53이며 >17 표본은 0. 실제 목표는 적용 순서상 `clamp(raw,±17) × 0.25 + default pose` 뒤 지연됨 (`vecenv_wrapper.py:153-154`, `joint_actions.py:169-199`). 실제 적용 목표·토크 readback은 미측정 |
| PD·모터 | DCMotor, hip/thigh 25/0.5 및 23.5 Nm, calf 25/0.5 및 45.43 Nm | 동일 명목 PD/한도에 TopDownDCMotor, startup gain ×0.9~1.1, PD 토크 ×motor strength 0.9~1.1 후 한도 clip (`s2_23f_motor.py:12-38`, env.yaml:263-293,1360-1420) | 선택 8환경 PhysX/actuator readback Kp 22.61~27.49, Kd 0.451~0.550, strength 0.921~1.093. 토크 clip 빈도 미측정 |
| 마찰·질량·COM | 로봇 material static 0.8/dynamic 0.6, startup base mass -1~+3 kg, 별도 COM randomization 없음 | material U(0.2,1.2), 64 bucket·dynamic≤static, mass -1~+2 kg, COM 각 ±0.05 m (`env.yaml:1260-1345`) | `robot_material_env_shape_3.npy` 전체 3072×27×3 PhysX readback은 static 0.2162~1.1811, dynamic 0.2162~1.1037; floor cfg 1.0/1.0 multiply이나 floor PhysX readback 미확인. 선택 8환경의 전체 19 body 질량 합 14.391~16.707 kg, COM xyz 범위 별도 trace. 해당 mass/COM은 update 0과 200에서 같아 startup 이후 새 변화 증거 없음 |
| 지형·커리큘럼 | 8×8 m 기존 연속 7종, mixed terrain·command range | 8×4 m 여섯 sparse 타입, `terrain_levels_s2(t_start=1000,t_end=8000,p_max=.9)`, command range 없음 (`env.yaml:102-223,1715-1724`) | 학습 실패가 진행할수록 쉬운 level 0에서 반복됨. 지형 유형별 전체 실패율은 미측정 |
| 지도·critic·정규화 | `force_gt=true`, `map_input=reconstruction`, `critic_mode=clean52`, empirical/actor/critic normalization 꺼짐 | `force_gt=false`, 같은 map input·critic과 정규화, depth delay 0 (`agent.yaml:1-68`) | AdaSmpl GT fraction은 update 0 1.00, 50 .796, 100 .924, 200 .871. PRED만 사용한 붕괴는 아님. 학생·teacher 개별 손실 효과는 미분리 |
| 보상·종료 | 대칭 B형 `track_lin_vel_xy_exp`, foot edge weight 0, scanner 기반 foot-below-ground | A형 `track_lin_vel_min_form` (`start_rewards.py:88-93`), foot edge weight -1과 tile mask, support-plane 기반 낙하 종료. bad_orientation 문턱 1.5 rad은 그대로 (`env.yaml:1498-1668`) | A식은 양의 목표 속도 초과를 벌하지 않는다. `Curriculum/penalty_on/foot_edge`는 사용 여부 스위치가 아니라 비영점 발생률 기록 (`penalty_log.py:1-57`). 종료 계산 뒤 보상 계산, 이어서 reset (`manager_based_rl_env.py:200-241`) |

`training_trace/conditions_*.npz`의 mass·COM은 `root_physx_view.get_masses/get_coms`로 읽은 **8개 선택 환경** 값이고, action delay·Kp/Kd/strength도 선택 환경의 update 시작 값이다 (`training_trace_bridge.py:65-93`). 초기와 update 100/200의 질량·COM 범위는 같았지만 지연은 reset 때 바뀐다. material `.npy`는 전체 로봇 shape readback이다. 바닥 PhysX 재질, 실제 접촉 마찰, 관절 목표·토크, 전 환경 mass/COM은 이 자료로 확인하지 못했다. 평가 `review.json`의 `actual_readback`도 한 평가 환경 값이며 학습 3072환경의 대용이 아니다.

## 첫 실패의 시간축과 소형 확인의 한계

학습 `training_trace`는 pre-env.step의 root·joint·policy action과 post-env.step의 reward·done을 한 행에 둔다 (`training_trace_bridge.py:103-127`, `train_trace.py:4-8`). 따라서 선택 8환경 update 5 step 16의 pre-step tilt 85.8°와 post-step 종료는 같은 transition이지만 종료 순간 각도 자체는 저장되지 않았다. `step_evidence`는 Isaac Lab termination manager의 `compute()` 직후, reset 전 각 항목을 센다 (`sol23f_runner.py:77-111`). `bad_orientation`의 실제 식은 `acos(-projected_gravity_b_z)>1.5`다 (설치 Isaac Lab `envs/mdp/terminations.py:51-60`). `manager_based_rl_env.py:200-241`에서 physics 뒤 종료→보상→reset→새 관측 순서가 확인된다. 자료를 post-reset 점프와 혼동하지 않았다.

기존 3072환경 10회 smoke는 종료 코드와 `model_9.pt` 저장을 확인했다. 그러나 그 로그 자체가 9회 시점 `bad_orientation` 비율 0.2002를 기록했고, EX29 본류도 10회 동안 739건을 기록했다. smoke는 경로·유한 학습·최종 저장을 확인했을 뿐, 장기 안정성·평가 flat/stone 12초·100회 이후 정책 붕괴를 관문으로 보지 않았다. 따라서 “10회 문제 없음”은 물리 성능 판정이 아니다.

## 집계 재현과 미확인

CPU로 `step_evidence.jsonl` 229행을 직접 합산한 [전 환경 update 표](EVIDENCE-sol-24e-ex29-global.csv), `training_trace/update_*.npz`의 선택 8환경 75개 update를 읽은 [표본 trace 표](EVIDENCE-sol-24e-ex29-trace8.csv), 감독기 `run.log`의 iteration 블록에서 태그를 뽑은 [학습 로그 표](EVIDENCE-sol-24e-ex29-runlog.csv), 네 `review_feet.npz`를 다시 센 [평가 표](EVIDENCE-sol-24e-ex29-eval.csv)를 둔다. trace의 tilt와 roll은 wxyz quaternion에서 CPU로 계산했다. `training_trace/coordinate_metadata.json`은 8환경 표본의 행동이 clip/지연 전이고 GRU hidden과 전체 물리 상태를 보존하지 않아 완전 재생이 불가능하다고 명시한다. 특정 reward 항, 초기 관절 randomization, material, motor, 지각 모델 중 **단독 원인**은 미확인이다. 첫 25회부터 자세 실패가 보이고, 90회 뒤 한쪽 자세·행동 편향과 빠른 종료가 동시에 커진다는 결론까지만 원자료로 지지된다.

원자료 SHA256: EX29 env.yaml `d8a639c573a3202e26e6e96048f3b997d19fd63a05691811eb0e3a3d2cc5a7f7`, agent.yaml `7a2ebf3d7a5910868d5e2a18530465ceb20b11bc64ecd2c8616211e92015cd1f`, material `.npy` `17c207ef3666ae0652ed188e9589bf190f7adf036dab11c6502235c85fe7e018`. EX23 env.yaml `3714375fc18ba07ccc204bc94454de1bdb10813949eab6c052187a31ae026c4b`, agent.yaml `1b9fd1e11008b31dc6966927ec944181e83883f5f62b3c6214bcf2a799b41023`. 실행 코드 예시 SHA256: `s2_23f_topdown_cfg.py` `bebf14d1eb555fa2da0891e151aa2281a304cfeebe9ca11d7b07441dc30b8d91`, `s2_23f_spawn.py` `64627cc563beb34df71474e7fc4e7bf850fc87934cc7cc02c284cf0e4faba51f`, `delayed_action.py` `8528cdf6cf1822ea8f436b7f19fd3d2246d6803f25fb9080a7867eb139671f33`, `s2_23f_motor.py` `6ca9456ca193e11b3667047adcf60daa5c8062e419c752ab96fe9f76c8775d47`.

통합 정정(lead_tmp, 10/24): 원 작성 커밋 `0451ce65`에서 EX23 지형을 8종으로 쓴 칸과 EX29 agent YAML 해시 오기를 원파일로 대조해 각각 활성 7종과 위 SHA로 고쳤다. 수치 CSV는 원 작성 바이트 그대로다.
