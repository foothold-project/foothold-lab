# FOOTHOLD 워드마크 대군 부감 촬영

> 분류: 실험
> 작성: 오흥재 · 2026-09-04 08:56
> 근거: 실측
> 요지: 정본 FOOTHOLD 워드마크 안에 배치한 Go2 4,096마리를 고정 부감으로 20초간 촬영했다.
> 상태: 확정
> 판: v1.0
> 이슈: #99

## 촬영 조건

정책은 NVIDIA 공식 체크포인트다. SHA-256은 `f2aa77bf0349c10ec2a00071162e37123d0cf80f3447c3989c17a618e1b24ad2`로 `확인됨`이다.
[Isaac Lab 환경 목록](https://isaac-sim.github.io/IsaacLab/main/source/overview/environments)에서 `Isaac-Velocity-Rough-Unitree-Go2-v0`와 RSL-RL 지원을 확인했다.
영상은 평지 · 20초 · 50 fps · 1920 x 1080 · 명령 속도 1.0 m/s · seed 42 · `cuda:0` 조건이다.
초기 흔들림은 `spawn_xy_range_m=0.1` · `yaw_range_deg=5.0` · `joint_pos_scale=0.05`로 기존 촬영과 같다 `확인됨`.

좌표는 `sim/eval/wordmark_origins_4096.csv`의 `x_m,y_m` 4,096행을 읽어 z=0으로 만들었다.
`raw.scene.terrain.env_origins`에 넣고 `raw.reset()` 뒤 되읽은 최대 대조 오차는 0.0 m다 `확인됨`.
생성기 `sim/eval/make_wordmark_origins.py`는 foothold-brand의 정본 SVG를 그대로 래스터라이즈해 글자 내부 좌표를 얻는다.
SVG 경로 데이터를 옮겨 적지 않았으며 seed 42로 재현된다.

| 대형 | 자리 수 | 간격 파라미터 | 월드 x 범위 · 깊이 | 월드 y 범위 · 폭 | 최근접 이웃 최소 · 중앙값 | 0.70 m 미만 쌍 |
|---|---:|---:|---|---|---|---:|
| FOOTHOLD 정본 워드마크 | 4,096 | 1.4942 m | -24.86 ~ 24.70 m · 49.56 m | -201.66 ~ 197.38 m · 399.04 m | 0.978 m · 1.277 m | 0 |

위 수치는 CSV 전수 계산으로 `확인됨`이다. 촬영 명령의 `--columns 128 --rows 32 --spacing 2.5`는 기존 인자 검증을 통과시키기 위한 값이며, `--origins_csv`가 있으므로 실제 대형 좌표에는 쓰이지 않는다.

## 카메라

카메라는 정지 부감이며 게이트는 껐다. 화각은 첫 프레임 직전과 마지막 프레임 직후에 카메라 프림의 `horizontalAperture`와 `focalLength`를 되읽어 계산했다.

| view | eye | target | 수평 화각 처음 · 끝 | 게이트 |
|---|---|---|---:|---|
| formation | `(-1.0, 0.0, 927.988)` m | `(0.0, 0.0, 0.0)` m | 60.000000665° · 60.000000665° | off |

최종 높이 927.988 m는 엔딩 타이틀 워드마크와 화면 크기와 위치를 맞추기 위해 역산했다.
대형 폭 실측 399.044663 m와 타이틀 폭 715 px, 화면 폭 1920 px, 수평 화각 60°를 사용하면 `399.044663 / (2 × tan(30°) × (715 / 1920)) = 927.999 m`이며 적용값과 0.011 m 차이다 `확인됨`.

완전 수직 부감에서 `eye.x == target.x`이면 up 벡터가 정의되지 않아 화면이 90° 돌아갔다 `확인됨`.
기존 topdown과 같이 eye.x를 target.x보다 1 m 앞에 두어 특이점을 피했다.
첫 진단 높이 366.362 m에서 이 기울기는 0.156°였고, 최종 높이 927.988 m에서는 0.062°다.
또 이 부감에서 화면 가로는 월드 -y 방향이다.
생성기에서 y 부호를 뒤집지 않으면 글자가 좌우 반전됐으므로 `wy = -(px - 중심) × scale`로 만들었다 `확인됨`.

## 영상과 실측 시간

`recording`은 1,000프레임 기록 구간이다. `process`는 Kit 기동 · 환경 생성 · 정책 로드 · 예열 · 기록을 합한 전체 실행 시간이다.

| 영상 | 프레임당 렌더 평균 | recording | process |
|---|---:|---:|---:|
| `flat_army_F_4096_formation.mp4` | 0.03857초 | 71.612초 | 113.255초 |

## 프레임 전수 검사

`python sim/eval/inspect_flat_army.py sim/eval/results/20260904-flat-army-formation`로 MP4 전체를 디코드했다.
각 프레임을 회색조 `float32`로 바꾸고 평균값 10 미만을 검정으로 판정했다.

| 영상 | 디코드 | 검정 | 교대 | 최소 평균 밝기 | 판정 |
|---|---:|---:|---|---:|---|
| F · formation | 1,000 | 0 | false | 37.456 | 통과 |

프리뷰는 0 · 50 · 150 · 500 · 999번 다섯 장을 `previews/`에 저장했다.
0번과 50번을 직접 확인했으며 두 장 모두 왼쪽에서 오른쪽으로 `FOOTHOLD`라고 읽히고 좌우와 위아래가 뒤집히지 않았다 `확인됨`.

## 2차 촬영에서 막힌 것과 푼 방법

옴니버스 모듈을 모듈 최상단에서 임포트하면 `AppLauncher`가 확장 시스템을 띄우기 전이라 환경 생성이 정체됐다.
`omni.usd`, `pxr.UsdGeom`, `omni.kit.viewport.utility`를 사용하는 함수 안에서만 지연 임포트해 풀었다.

기본 카메라 프림은 session layer에 있다.
`focalLength` 속성에 직접 `Set`하면 정체됐으므로 `omni.usd.set_prop_val`로 값을 넣고 그동안 뷰포트 갱신을 잠시 껐다.
첫 프레임과 마지막 프레임의 실측 화각이 같아 설정이 유지된 것을 확인했다.

완전 수직 부감은 up 벡터 특이점 때문에 90° 회전했고, 1 m의 x 오프셋으로 풀었다.
그 카메라의 화면 가로가 월드 -y 방향인 것도 프리뷰에서 확인해 생성기의 y 부호를 뒤집었다.

## 실행 명령 전문

먼저 PowerShell에서 환경 변수를 지정한다.

```powershell
$env:OMNI_KIT_ACCEPT_EULA='YES'
```

저장소 루트에서 아래 명령을 실행했다.

```powershell
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260904-flat-army-formation --cut F --view formation --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --origins_csv sim/eval/wordmark_origins_4096.csv --gate off --headless --device cuda:0
python sim/eval/inspect_flat_army.py sim/eval/results/20260904-flat-army-formation
```

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| **v1.0** | 2026-09-04 | FOOTHOLD 워드마크 대군 촬영과 전수 검사 | #99 |
