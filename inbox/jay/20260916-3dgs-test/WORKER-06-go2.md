# 작업서 06 · 복원 지형 USD 위에서 Go2 보행 시험 (NVIDIA pt → foothold-v1)

> 분류: 계획
> 작성: 오흥재 · 2026-09-16 15:10
> 근거: RESEARCH-3dgs-terrain.md G5-3 · 2절 6단계 · 작업서 05 산출물 · `sim/eval/record_terrain_demo.py` · `sim/eval/gap_observations.py` · `sim/eval/probe_height_scan.py`
> 요지: 팀장이 지정한 셋(낙상 · 발 관통 · 높이 스캔 정상 여부)을 두 체크포인트에서 재고 짧은 영상을 남긴다. 체크포인트마다 관측 함수를 맞춘다
> 상태: 확정
> 판: v1.0
> 이슈: #430

워커 모델: `gpt-6-astra` · reasoning high (Isaac Lab 환경 설정 · 정책 로드 · 관측 호환 · 영상 기록)

선행 조건: `_out/mesh/ground.usd` 가 작업서 05 의 검사표를 통과했어야 한다. `_out/mesh/ground_stats.json` (높이 격자와 변환 행렬) 도 있어야 한다.

## 0. 자리와 경로

| 무엇 | 절대 경로 |
|---|---|
| 작업 폴더 | `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260916-3dgs-test/` |
| 스크립트 (새로 만든다) | 작업 폴더 `poc_go2_on_usd.py` |
| 지형 | `_out/mesh/ground.usd` (prim `/World/ground`) |
| 체크포인트 A | `C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt` (NVIDIA 사전학습 · 기본 `mdp.height_scan` 관측을 적용하는 후보) |
| 체크포인트 B | 저장소 `models/foothold-v1.pt` (규격 2 관측 · `height_scan_with_gap` offset 0.5 · miss_value 1.0 · `models/foothold-v1.env.yaml` 614 · 639~640행) |
| 산출물 | `_out/go2/<A|B>/trace.csv` · `summary.json` · `run.mp4` · `_out/go2/REPORT-06.md` |
| 파이썬 | `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe` |
| 참고 코드 (읽기만) | `sim/eval/record_terrain_demo.py` (import 순서 · AppLauncher · `UnitreeGo2RoughEnvCfg` 수정 · `OnPolicyRunner.load` · `get_inference_policy` · 카메라 녹화) · `sim/eval/generalization_env_cfg.py` 의 `apply_gap_aware_scan` · `sim/eval/gap_observations.py` · `sim/eval/probe_height_scan.py` · `sim/eval/metrics.py` (base contact 판정) |

환경 변수 `OMNI_KIT_ACCEPT_EULA=YES` · `KMP_DUPLICATE_LIB_OK=TRUE` 를 그 프로세스에만 준다. `--device` 는 `nvidia-smi` 로 사용량이 적은 GPU 를 골라 `cuda:<n>` 으로 준다. `CUDA_VISIBLE_DEVICES` 는 만지지 않는다.

## 1. 환경 설정 (둘 다 공통)

`UnitreeGo2RoughEnvCfg` 에서 출발해 다음만 바꾼다. 나머지는 기본값을 둔다.

| 항목 | 값 | 왜 |
|---|---|---|
| `scene.terrain.terrain_type` | `"usd"` · `usd_path` 는 위 USD · `prim_path="/World/ground"` · `terrain_generator=None` · `env_spacing=1.0` | G5-2 7 (usd 는 env_spacing 필수) |
| `scene.num_envs` | 4 | 원점 주변 1 m 격자에 넷. 궤적 중심이 원점이다 (작업서 04 의 변환) |
| `curriculum.terrain_levels` | `None` | usd 지형엔 커리큘럼이 없다 |
| `observations.policy.enable_corruption` | `False` | 평가 관행 |
| `scene.height_scanner.mesh_prim_paths` | `["/World/ground"]` | G5-2 5 |
| `commands.base_velocity.ranges` | lin_vel_x (0.5, 0.5) · lin_vel_y (0, 0) · ang_vel_z (0, 0) · heading 끔 | 0.5 m/s 직진 |
| `episode_length_s` | 12 | 0.5 m/s 로 6 m |
| 스폰 높이 | 원점 주변 지면 z 의 중앙값 + 0.42 m (`ground_stats.json` 격자에서 계산) | 관통 시작 방지. `events.reset_base` 의 pose 범위를 (0,0) 근처 ±0.3 m 로 줄인다 |

**B 에만**: 관측 `policy.height_scan` 의 `func` 를 `sim/eval/gap_observations.py` 의 `height_scan_with_gap` 으로 바꾸고 `params` 에 `offset=0.5` · `miss_value=1.0` 을 준다. 평가 하네스 `generalization_env_cfg.apply_gap_aware_scan` 이 하는 것과 같은 방식으로 한다 (그 함수를 읽고 같은 필드를 건드린다). **A 에는 기본 관측을 둔다.** 두 정책의 관측 차원(단일 관측 벡터 길이)을 로그에 적고 체크포인트의 입력 차원과 맞는지 확인한다. 안 맞으면 «호환 실패» 로 보고하고 멈춘다.

## 2. 재는 것 (스텝마다 `trace.csv` · 끝나면 `summary.json`)

| 열 | 정의 |
|---|---|
| `t` · `env` | 시각 · 환경 번호 |
| `base_x y z` · `base_roll pitch` | 몸통 위치 · 자세 |
| `fell` | base contact 종료가 일어난 스텝 (`metrics.py` 의 판정 방식과 같게) · 에피소드당 낙상 여부와 시각을 요약 |
| `foot_pen_<FL,FR,RL,RR>` | **대리 지표**: 발 링크 원점 z 에서 «그 xy 의 지면 높이(`ground_stats.json` 격자 보간)» 를 뺀 값에서 발 반지름 0.02 m 를 뺀 것. 음수가 관통 후보. 요약은 허용 오차 1 cm 를 넘는 스텝 수 · 최대 침투 깊이 · 이것이 대리 지표라는 문장 |
| `scan_finite` · `scan_min max median` | 187 광선 중 유한값 개수 · 관측값 분포 (`probe_height_scan.py` 방식). B 는 miss_value 로 바뀐 뒤 값과 바뀌기 전 유한 개수를 둘 다 |
| `progress_x` | 전진 거리 |

요약에는 에피소드 수 · 낙상 수 · 전진 거리 평균 · 발 관통 스텝 비율 · 스캔 유한값 비율 평균 · 벽시계 시간이 들어간다.

## 3. 영상

`record_terrain_demo.py` 의 카메라 녹화 방식을 빌려 A · B 각각 12 초 · 1280x720 · 30 fps 로 `run.mp4` 를 남긴다. 카메라는 원점을 향한 45 도 위 · 3 m 거리 고정. 녹화가 안 되면 수치만 남기고 «영상 미수행» 을 적는다. 영상은 gitignore 대상이라 저장소에 안 들어간다.

## 4. 통과 기준 (관문)

| 항목 | 기준 |
|---|---|
| 호환 | 두 정책 다 관측 차원이 맞아 로드 · 추론이 된다 (안 되면 실패로 보고) |
| 수치 | `trace.csv` · `summary.json` 이 A · B 둘 다 있다 |
| 판정 없음 | 낙상 · 관통 · 스캔 수치의 «좋고 나쁨» 은 이 작업서가 판정하지 않는다. 처음 재는 것이다. 있는 그대로 적는다 |

## 5. 하지 말 것

- 다른 프로세스를 죽이지 않는다. `CUDA_VISIBLE_DEVICES` 설정 금지. `sim/` · `docs/` · `.github/` · `C:/isaac/IsaacLab` 수정 금지 (읽기만). 새 패키지 설치 금지.
- `poc_go2_on_usd.py` · `_out/go2/` 밖의 저장소 파일을 만들거나 고치지 않는다. git 커밋 · 스테이징 금지.
- em dash(U+2014) 금지.

## 6. 보고서 형식 (`_out/go2/REPORT-06.md`)

```
# REPORT-06 · 복원 지형 위 Go2 보행 시험
## 환경   Isaac Sim · Isaac Lab · 체크포인트 sha256 둘 · GPU · 시작/끝 시각
## 설정   1절 표의 실제 적용값 · 관측 차원 A/B
## 명령   실제로 친 명령
## 결과   summary.json 둘을 표로 (낙상 · 전진 · 관통 대리 지표 · 스캔 유한값) · 영상 경로
## 문제   오류 원문 · 우회한 것 · 못 한 것
## 판정   4절 관문 항목별 통과/실패
```

`worker_done` 의 세 문장 요약에 A · B 의 낙상 수와 스캔 유한값 비율 · 통과/실패를 넣고 `--report-path` 에 이 보고서 경로를 준다.
