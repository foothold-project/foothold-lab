> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: Codex sol · 2026-10-23
> 근거: sonnet-code 7cab5223의 코드와 EX-11·12·19·23·25 저장 설정, 설치된 Isaac Lab 2.3.2 소스, START 원문, CPU 정답 입력
> 요지: 다섯 실험의 DR·행동 지연·지형 진행과 재개 상태를 실제 호출 경로에서 대조한다.
> 상태: 읽기 전용 감사 · Kit에서의 유효 접촉 계수와 새 DR의 학습 효과 미확인
> 판: v1.0

# SOL-23d · DR와 지형 진행 코드 감사

## 첫 결론

EX-11·12에서 EX-23·25로 갈 때 로봇 재질, 질량 범위, COM·PD·모터 세기 무작위화, 행동 지연, 지각 입력 또는 추정기 처치가 함께 바뀌었다. EX-19도 보상 계열이 다르다. 따라서 지금 관찰된 험지 결과에서 **낮은 마찰 하나를 원인으로 확정할 수 없다**. 지형 쪽도 이 다섯 판은 START의 듬성한 디딤점 진행이 아니라 같은 7종 연속 지형, 23열 구성이다. 근거는 아래 표의 실제 파일과 줄에 적었다.

## 저장 설정과 호출 경로 대조

기준은 읽기 전용 `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code` HEAD `7cab5223`이다. 저장 설정은 그 체크아웃의 `logs/rsl_rl/foothold_s2_x11/2026-10-22_01-33-36_ex11-est-zero`, `2026-10-22_01-34-08_ex12-est-learned`, `foothold_s2_x19/2026-10-22_18-27-36_ex19-dr-v2`, `foothold_s2_x23/2026-10-22_21-52-26_ex23-g1`, `2026-10-22_23-00-45_ex25-g0` 각각의 `params/env.yaml`과 `manifest.json`이다. 저장 YAML은 Python 전용 태그가 있어 `safe_load`는 실패한다. 해당 구간을 원문으로 대조했다.

| 항목 | EX-11·12 | EX-19 | EX-23·25 | 근거 |
|---|---|---|---|---|
| 로봇 몸체 static/dynamic 마찰 | 각각 0.2~1.2 난수, 64 bucket, `make_consistent=True` | static 0.8, dynamic 0.6 고정 | EX-19와 같음 | `foothold_s2/tasks/s1_env_cfg.py:123-127`, `s2_x19_cfg.py:20-24`, `s2_x23_cfg.py:20-24`, 각 `params/env.yaml`의 `events.physics_material` |
| 기본 몸체 질량 | 원 질량에 -1~+2 kg | -1~+3 kg | EX-19와 같음 | `s1_env_cfg.py:128-131`, `s2_x19_cfg.py:25-26`, `s2_x23_cfg.py:25-26`, 저장 YAML의 `add_base_mass` |
| COM·PD gain·모터 세기 | COM 각 축 ±0.05 m, gain과 모터 세기 각각 0.9~1.1 | 모두 해제 | 모두 해제 | `s1_env_cfg.py:132-145`, `s2_x19_cfg.py:27-29`, `s2_x23_cfg.py:27-29`, 저장 YAML의 null 세 칸 |
| 추가 행동 지연 | 0~15 ms를 reset 때 env별 선택 | 유지 | 해제, 기본 `JointPositionActionCfg` | `s1_env_cfg.py:77-80`, `delayed_action.py:13-43`, `s2_x23_cfg.py:29-30`, 저장 YAML의 `actions.joint_pos.class_type` |
| 지도·추정 처치 | 둘 다 지도 없음·`force_gt=False`; EX-11 추정기 zero, EX-12 learned | 지도 없음·zero | EX-23 복원 지도 경로·`force_gt=True`·learned, EX-25 지도 없음·`force_gt=False`·learned | 각 `manifest.json`의 `modes`, `tasks/agents/s2_x23_ppo_cfg.py:11-18`, `models/start_perception.py:215-232` |
| 보상 경로 | X11 START 표 | X19는 X16n의 NVIDIA 보상 계열 | X23는 X11 START 표 | `tasks/s2_env_cfg.py:96-113`, `tasks/s2_x19_cfg.py:12-18`, `tasks/s2_x23_cfg.py:1-8` |

DR 다섯 물리 이벤트는 `mode="startup"`이고 reset 이벤트는 base와 joint state에 별도로 있다 (`s1_env_cfg.py:123-158`). 설치된 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/envs/mdp/events.py:155-265`는 마찰 후보 bucket을 만들고 `make_consistent`일 때 dynamic을 static 이하로 제한한다. `manager_based_rl_env.py:135,235,362`는 startup, interval, reset 적용점을 구분한다. **마찰·질량 등은 에피소드마다 다시 뽑지 않고 새 환경 프로세스의 startup에서 뽑힌다.** EX-19·23·25의 고정 마찰 이벤트는 startup에서 같은 값으로 설정된다.

지형과 sim 재질에는 `friction_combine_mode="multiply"`, static/dynamic 1이 지정돼 있다 (`s1_env_cfg.py:47-50,193`). 로봇 쪽은 설치된 `isaaclab_assets/robots/unitree.py:140`의 `UNITREE_GO2_CFG`가 USD 자산을 가리키며 여기서 별도 combine mode를 명시하지 않는다. USD가 실제 authored material에 가진 모드와 PhysX의 접촉쌍 유효 마찰은 이 CPU 감사에서 확인하지 못했다. `0.8/0.6`을 유효 접촉 계수라고 부르지 않는다.

행동 지연은 제어 목표를 한 제어 주기 뒤로 미루는 큐가 아니다. `max_delay_substeps=round(0.015/0.005)=3`, reset에서 0~3을 뽑고, 20 ms 제어 주기의 네 물리 substep 중 앞 `d`개에 직전 목표를 적용한 후 새 목표로 바꾼다 (`delayed_action.py:16,22-36`). EX-23·25는 이 클래스가 없으므로 그 추가 지연이 없다. 설치된 Isaac의 기본 actuator·solver 지연까지 0이라는 주장은 아니다.

## 현재 지형 진행과 START 원문

`tasks/s2_env_cfg.py:99-111`의 X11은 `use_full_terrain()`을 비워 S1의 23열 연속 지형을 유지한다. X19와 X23, 그리고 X23 환경을 쓰는 EX-25도 이 경로다. `terrains/columns.py:14-33`의 7종 비율 0.10, 0.10, 0.08, 0.08, 0.04, 0.04, 0.02를 합 0.46으로 정규화해 23열에 고정 배치한다. 즉 계단 두 방향 각 5열, boxes와 random rough 각 4열, 경사 두 방향 각 2열, stage stairs 1열이다. `terrains/rough_go2_cfg.py:40-49`는 10행, 셀 8×8 m, generator seed 미지정이다. 저장 YAML의 `max_init_terrain_level: 2`가 첫 배치를 0~2행으로 제한한다. 설치된 `terrain_generator.py:240-263`은 열로 종류를 정하고 행 난도를 `(row+U[0,1])/10`으로 만든다. `terrain_importer.py:340-353`은 첫 행을 0~2에서 뽑고 env index로 열을 배정한다. 난수 mesh는 생성되지만 reset마다 지형 종류를 새로 뽑는 구조는 아니다.

리셋 때 `curriculum/terrain_levels_mixed.py:14-29`가 막 끝난 에피소드의 명령 합과 최대 이동 거리를 `rules.py:14-30`에 전달한다. 자유 명령의 승급은 최대 이동 거리 4 m 초과, 강등은 `0.5 × ||명령 합|| × 4 s × 0.9` 미만, XY 명령 합 0이면 유지다. 설치된 `terrain_importer.py:314-331`은 +1/-1행을 적용하고 최상위 초과는 난수 행으로 되돌린다. `commands/mixed_core.py:121-122,141-150`의 START 명령 가지는 범위 curriculum의 `vmax`를 읽지 않는다. `range_curriculum`을 저장하거나 갱신해도 이 판의 실제 명령 분포가 그 값대로 넓어지지는 않는다.

START 원문 로컬 `C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt:283-331`은 낮은 위치 난수의 징검다리와 보조 평지부터 높은 난수 징검다리, 평균대, stepping beam으로 진행하고 gap은 그 `p_advance` 진행에서 제외한다. 위 다섯 판에는 징검다리·평균대·gap 열과 이 종류 재배정이 없다. 따라서 START 명령·보상 일부를 적용한 판이라는 뜻과 START 지형 진행을 재현한 판이라는 뜻을 구분해야 한다.

## 체크포인트 재개에 DR 진행을 붙일 때

`scripts/train_start.py:114-130`은 새 `gym.make`로 환경을 만든 **뒤** `runner.load`를 호출한다. 따라서 새 프로세스의 startup DR은 복원 전 발동한다. `runners/start_runner.py:539-574,589-647` 저장에는 정책, 두 optimizer, 학습률, 지각망, AdaSmpl, 완료 갱신, 난수 상태, 지형 `terrain_levels/types`, 명령 범위가 있다. 몸체 material bucket 선택, 질량·COM·gain·motor 값, 행동 지연 env별 `delay`, 지형 `env_origins`는 명시 저장되지 않는다. 난수 상태도 새 환경을 만든 뒤 복원한다. 정확히 같은 물리 실현값과 궤적의 재현은 현재 저장 계약으로 증명할 수 없다. `terrain_levels/types`만 복원할 때 실제 `env_origins`가 새 환경 배치와 일치하는지도 확인이 필요하다.

새 DR 단계는 `startup` 이벤트 범위를 고른 뒤 환경을 만들거나, 살아 있는 환경에서 검증된 setter로 별도 적용해야 한다. 현재 `reset`은 자세·관절과 지연 선택만 다시 뽑으며, `interval` DR 이벤트는 이 다섯 판에 없다. 새 단계의 범위, 단계 번호, 적용 시각과 reset/interval 적용 여부를 체크포인트와 실행 영수증에 함께 저장하는 설계가 필요하다. 단지 cfg 범위만 바꾸고 `resume`하면 기존 물리 실현값과 새 실현값의 혼합 또는 새 startup 표본을 갖게 된다.

`start_runner.py:50,628-642`의 재개 검사는 `est_mode`와 `critic_mode`만 대조한다. `map_input`과 `force_gt`는 이 검사에 없다. 특히 `models/start_perception.py:228-232`의 `AdaSmpl.load_state_dict`는 저장된 `force_gt`를 복원하므로 EX-23의 정답 지도 고정 상태가 새 cfg의 복원 지도 설정으로 넘어갈 수 있다. `runner.pcfg`, 실제 `adasmpl.force_gt`, 지각망 입력과 정책 입력을 재개 직후 같은 영수증에서 대조해야 한다. EX-23의 진단 정답 지도를 실제 센서 지도 효과로 세지 않는다.

## CPU 정답 입력과 다음 기록

`CUDA_VISIBLE_DEVICES=-1`, 설치된 `isaac311` Python으로 실제 `curriculum.rules.judge_free`를 불러 세 사례를 검사했다. `(이동 5m, 명령합 [1,0])→승급 +1`, `(0.1m,[1,0])→강등 -1`, `(0.1m,[0,0])→유지 0`을 예측했고 실제 `[1,-1,0]`으로 PASS였다. `delayed_action.py`의 `sub<delay` 조건을 CPU에서 그대로 대입한 정답 입력은 `d=0`에서 새 목표 4회, `d=3`에서 옛 목표 3회 뒤 새 목표 1회로 PASS였다. 두 번째는 Isaac action 객체 실행이 아닌 조건식 대조다. `safe_load`가 저장 YAML의 Python 태그에서 실패한 것도 확인했다. 값을 임의 파서로 고쳐 읽지 않고 원문과 코드로 대조했다.

다음 학습 전후에 기록할 최소 항목은 다음과 같다. 이는 계측 제안이며 실행 승인이 아니다.

| 시점 | 기록 | 이유 |
|---|---|
| 환경 생성 직후 | 코드·cfg·부모 checkpoint SHA, DR 단계와 범위, startup 적용 전후의 env별 robot static/dynamic 마찰·질량·COM·gain·motor 실제 값과 bucket 빈도, terrain material combine mode | 설정 범위와 실제 물리 분포를 분리 |
| reset마다 표본 집계 | env별 새 지연 substep, reset 원인, terrain 행·열·종류, 명령 종류와 크기, 승급·강등·유지, 세부 빈도 | reset 시점 분포와 지형 노출 확인 |
| 갱신·저장 경계 | DR 단계·전환 기준·적용 시각, 완료 update, 각 지형 종류·행 노출 수와 성공 대용·추종·정체·종료 이유, 유효 접촉 마찰 확인 가능 여부 | 바뀐 조건과 성적의 시간 순서 보존 |
| 재개 직후 | 저장 단계와 새 cfg의 차이, 저장 `terrain_levels/types` 대 `env_origins`, 새 startup 물리 값, `pcfg.map_input`, `pcfg.force_gt`, `adasmpl.force_gt`, 실제 지도 입력 통계 | 조용한 DR 또는 정답 지도 누수 탐지 |

낮은 마찰의 단독 효과를 보려면 같은 부모, 명령·보상·지도·지연·질량 등을 고정하고 robot 마찰만 바꾼 대조가 필요하다. 현재 다섯 판은 그 대조가 아니다. 실제 유효 접촉 계수와 성능 인과는 미확인이다.
