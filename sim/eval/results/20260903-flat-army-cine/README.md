# 평지 대군 영화적 카메라 촬영

> 분류: 실험
> 작성: 오흥재 · 2026-09-03 22:34
> 근거: 실측
> 요지: 평지에서 4096마리 Go2 대열을 카메라 10종으로 각각 20초간 촬영했다.
> 상태: 확정
> 판: v1.2
> 이슈: #99

## 촬영 조건

정책은 NVIDIA 공식 체크포인트를 썼다. SHA-256은 `f2aa77bf0349c10ec2a00071162e37123d0cf80f3447c3989c17a618e1b24ad2`로 `확인됨`.
[Isaac Lab 환경 목록](https://isaac-sim.github.io/IsaacLab/main/source/overview/environments)에서 `Isaac-Velocity-Rough-Unitree-Go2-v0`와 RSL-RL 지원을 확인했다.
네 영상 모두 평지 · 20초 · 50 fps · 1920 x 1080 · 명령 속도 1.0 m/s · seed 42다.
초기 흔들림은 `spawn_xy_range_m=0.1` · `yaw_range_deg=5.0` · `joint_pos_scale=0.05`로 매니페스트와 같다 `확인됨`.
`env_origins`는 스크립트가 직접 계산해 재설정했으며 사전 배열과의 최대 좌표 오차는 네 촬영 모두 0 m다 `확인됨`.
촬영 전 `cuda:0`의 사용 메모리는 0 MiB였고, 네 촬영 모두 `cuda:0`에서 실행했다 `확인됨`.

| 컷 | 마릿수 | 대열 | 간격 | 명목 크기 | 원점 중심 간 거리 |
|---|---:|---:|---:|---:|---:|
| A · 대군 | 4096 | 128 x 32 | 2.5 m | 320 x 80 m | 317.5 x 77.5 m |

## 카메라

1차 네 컷의 수평 화각은 60도다. 좌표는 `(x, y, z)` m이며 대열 중심을 원점으로 한다.
진행률 `s`는 첫 프레임의 0.0부터 마지막 프레임의 1.0까지 프레임마다 갱신했다.
아래 시작과 끝 좌표는 정의된 경로를 계산한 값이다 `확인됨`. 지시된 카메라 좌표를 조정하지 않았다.

| 카메라 | 시작 eye | 끝 eye | 시작 target | 끝 target | 수평 화각 | 게이트 | 보여 주는 것 |
|---|---|---|---|---|---:|---|---|
| dolly | `(-46.75, 0, 0.5)` | `(9, 0, 281.891)` | `(-28.75, 0, 0.4)` | `(10, 0, 0)` | 60도 | on | 후미 저공에서 시작해 전체 대열을 드러내는 달리 아웃 |
| aisle | `(-35, 0, 0.45)` | `(-15, 0, 0.45)` | `(-20, 0, 0.35)` | `(0, 0, 0.35)` | 60도 | on | 로봇과 같은 속도로 대열 사이 통로를 흐르는 저공 추적 |
| macro | `(-35, 0, 0.22)` | `(-15, 0, 0.22)` | `(-32, 0, 0.18)` | `(-12, 0, 0.18)` | 60도 | on | 발 높이에서 가까이 보는 통로 추적 |
| hero | `(64.75, 0, 0.6)` | `(64.75, 0, 0.6)` | `(42.75, 0, 0.45)` | `(58.75, 0, 0.45)` | 60도 | on | 고정된 정면 저공 카메라로 다가오는 전열 |
| lead | `(45.75, 0, 0.55)` | `(65.75, 0, 0.55)` | `(31.75, 0, 0.40)` | `(51.75, 0, 0.40)` | 45.000001도 | off | 전열 7 m 앞에서 같은 속도로 물러나는 정면 추적 |
| foot | `(-35, 0, 0.13)` | `(-15, 0, 0.13)` | `(-32, 1.25, 0.20)` | `(-12, 1.25, 0.20)` | 16.000000도 | off | 발 높이 아래에서 한 열을 겨누는 망원 근접 촬영 |
| side | `(5, 0, 0.30)` | `(5, 0, 0.30)` | `(5, 14, 0.28)` | `(5, 14, 0.28)` | 35.000000도 | off | 고정 카메라 앞을 대군이 가로지르는 측면 촬영 |
| orbit | `(-31.5, -6.062, 1.1)` | `(-11.5, 6.062, 1.1)` | `(-35, 0, 0.35)` | `(-15, 0, 0.35)` | 50.000001도 | off | 대군과 전진하며 120도 선회하는 촬영 |
| rise | `(10, 0, 1.2)` | `(10, 0, 281.891)` | `(10, 0, 0)` | `(10, 0, 0)` | 60.000001도 | on | 10 m 선 위에서 중심을 유지하며 수직 상승 |
| underfoot | `(25, 0, 0.07)` | `(25, 0, 0.07)` | `(5, 0, 0.40)` | `(5, 0, 0.40)` | 60.000001도 | off | 지면 7 cm 고정 카메라로 다가오는 대군을 올려다봄 |

## 2차 · 외부 영상 도구용 소스 플레이트

2차 여섯 컷은 군더더기를 줄이고 단순한 카메라 움직임을 쓰도록 촬영했다. 모두 `cuda:0`에서 실행했으며 지시된 좌표를 조정하지 않았다 `확인됨`.
화각은 첫 프레임 직전에 한 번 설정하고, 첫 프레임과 마지막 프레임 직후에 카메라 프림의 `horizontalAperture`와 `focalLength`를 되읽어 계산했다. 여섯 컷 모두 처음과 마지막 실측값이 같아 `set_camera_view` 뒤에도 화각이 유지됐다 `확인됨`.

| 컷 | 지시 화각 | 첫 프레임 실측 | 마지막 프레임 실측 | 지시값과 차이 |
|---|---:|---:|---:|---:|
| lead | 45도 | 45.000001도 | 45.000001도 | +0.000001도 |
| foot | 16도 | 16.000000도 | 16.000000도 | +0.000000도 |
| side | 35도 | 35.000000도 | 35.000000도 | -0.000000도 |
| orbit | 50도 | 50.000001도 | 50.000001도 | +0.000001도 |
| rise | 60도 | 60.000001도 | 60.000001도 | +0.000001도 |
| underfoot | 60도 | 60.000001도 | 60.000001도 | +0.000001도 |

## 영상과 실측 시간

`recording`은 1,000프레임 기록 구간이다. `process`는 Kit 기동 · 환경 생성 · 정책 로드 · 예열 · 기록을 합한 전체 실행 시간이다.

| 영상 | 프레임당 렌더 | recording | process |
|---|---:|---:|---:|
| `flat_army_A_4096_dolly.mp4` | 0.0361초 | 66.8초 | 105.7초 |
| `flat_army_A_4096_aisle.mp4` | 0.0355초 | 65.9초 | 103.4초 |
| `flat_army_A_4096_macro.mp4` | 0.0365초 | 67.6초 | 104.4초 |
| `flat_army_A_4096_hero.mp4` | 0.0366초 | 67.4초 | 104.6초 |
| `flat_army_A_4096_lead.mp4` | 0.0387초 | 71.9초 | 110.7초 |
| `flat_army_A_4096_foot.mp4` | 0.0414초 | 77.8초 | 120.3초 |
| `flat_army_A_4096_side.mp4` | 0.0379초 | 71.6초 | 111.7초 |
| `flat_army_A_4096_orbit.mp4` | 0.0420초 | 77.3초 | 120.0초 |
| `flat_army_A_4096_rise.mp4` | 0.0410초 | 75.8초 | 115.9초 |
| `flat_army_A_4096_underfoot.mp4` | 0.0371초 | 70.4초 | 112.1초 |
| 1차 합계 |  | 267.7초 | 418.2초 |
| 2차 합계 |  | 444.8초 | 690.9초 |

2차 여섯 컷의 전체 프로세스 합계는 11분 30.9초다 `확인됨`.

## 프레임 전수 검사

`python sim/eval/inspect_flat_army.py sim/eval/results/20260903-flat-army-cine`로 MP4를 전부 디코딩했다.
각 프레임을 회색조 `float32`로 바꾸고 평균값 10 미만인 프레임을 검정으로 셌다.

| 영상 | 디코드 | 검정 | 교대 | 최소 평균 밝기 | 판정 |
|---|---:|---:|---|---:|---|
| A · dolly | 1000 | 0 | false | 27.526 | 통과 |
| A · aisle | 1000 | 0 | false | 97.073 | 통과 |
| A · macro | 1000 | 0 | false | 92.838 | 통과 |
| A · hero | 1000 | 0 | false | 154.782 | 통과 |
| A · lead | 1000 | 0 | false | 156.259 | 통과 |
| A · foot | 1000 | 0 | false | 123.913 | 통과 |
| A · side | 1000 | 0 | false | 115.807 | 통과 |
| A · orbit | 1000 | 0 | false | 87.465 | 통과 |
| A · rise | 1000 | 0 | false | 48.563 | 통과 |
| A · underfoot | 1000 | 0 | false | 151.275 | 통과 |

총 10,000프레임에서 검정 0 · 교대 false다 `확인됨`.
2차 각 영상의 0 · 250 · 500 · 750 · 999번 프레임, 총 30장을 `previews/`에 저장하고 직접 확인했다 `확인됨`. `foot`은 다리가 화면 가까이를 지나지만 지면이나 몸체에 파묻히지 않아 망원 발 근접 소재로 쓸 수 있다. `underfoot`은 지면 비중이 크지만 다가오는 전열과 몸체가 계속 보여 초저공 정면 소재로 쓸 수 있다.

## 실행 명령 전문

먼저 PowerShell에서 환경 변수를 뒀다.

```powershell
$env:OMNI_KIT_ACCEPT_EULA='YES'
```

아래 열 명령을 저장소 루트에서 실행했다.

```powershell
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view dolly --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view aisle --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view macro --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view hero --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view lead --hfov 45 --gate off --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view foot --hfov 16 --gate off --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view side --hfov 35 --gate off --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view orbit --hfov 50 --gate off --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view rise --hfov 60 --gate on --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view underfoot --hfov 60 --gate off --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
python sim/eval/inspect_flat_army.py sim/eval/results/20260903-flat-army-cine
```

## 2차에서 막힌 것과 푼 방법

화각 인자를 넣은 뒤 촬영이 서지 않았다. 원인이 두 겹이었고 한 겹만 고쳐서는 안 풀렸다.
다음에 같은 자리에서 막히지 않도록 과정을 남긴다.

### 증상

`lead` 를 2026-09-03 22:57 에 시작했는데 26분이 지나도록 MP4 가 한 장도 안 나왔다.
1차 `dolly` 는 같은 GPU, 같은 4096체에서 기동 38.95초 · 전체 105.72초였다.

### 원인이 아니었던 것

밖에서 잰 값으로 후보를 지웠다.

| 확인한 것 | 실측 | 결론 |
|---|---|---|
| GPU 사용률 | cuda:0 이 0 퍼센트, 프로세스는 CPU 3~5코어 사용 | GPU 일에 도달하지 못한 상태다 |
| 시스템 메모리 | 255 GB 중 142 GB 여유 | 메모리 압박이 아니다 |
| OptiX 셰이더 캐시 | `optix7cache.db-wal` 이 기동 직후 이래 변화 없음 | 셰이더 재컴파일이 아니다 |
| Kit 로그 | `omni.kit.app.log` 가 기동 11초 시점 이후 조용함 | 임포트까지는 정상이었다 |

처음에는 렌더 루프가 매 프레임 `set_hfov` 로 USD 에 쓰는 것을 의심했다.
그것을 없애도 증상이 그대로였다. 옳은 수정이었지만 원인은 아니었다.

### 대조 실험이 범위를 좁혔다

추측을 멈추고 1차 커밋 `222f272` 의 스크립트를 분리 worktree 에 두고 `dolly` 를 그대로 다시 찍었다.

| | environment | recording | process |
|---|---:|---:|---:|
| 1차 코드 · cuda:0 · dolly | 23.35초 | 70.06초 | 110.24초 |
| 2차 코드 · cuda:0 · lead | 정지 | 없음 | 없음 |

같은 GPU · 같은 마릿수 · 같은 인자다. 환경 요인이 아니라 2차 변경분이 원인임이 확정됐다.
그리고 환경 생성보다 앞에서 새로 실행되는 차이는 두 줄뿐이었다.

### 첫째 겹 · 옴니버스 모듈을 최상단에서 임포트했다

```python
import omni.usd                 # 모듈 최상단에 두면 안 된다
from pxr import UsdGeom
```

Isaac Sim 은 `AppLauncher` 가 확장 시스템을 세우기 전에 옴니버스 모듈을 임포트하면
준비되지 않은 USD 라이브러리를 물고, 그 뒤 환경 생성이 무한정 늘어진다.
**해결은 지연 임포트다.** 두 줄을 `read_hfov` 와 `set_hfov` 함수 안으로 옮겼다.

### 둘째 겹 · 기본 카메라가 session layer 에 있다

지연 임포트만으로는 첫 `focalLength` 쓰기에서 다시 정체됐다.
`/OmniverseKit_Persp` 는 session layer 에 있어 속성을 직접 `Set` 하면 안 된다.

**해결은 두 가지를 같이 쓴 것이다.**

- `omni.usd.set_prop_val` 로 값을 넣는다
- 그 동안 뷰포트 갱신을 잠시 끈다

### 결과

`environment_creation_and_reset` 이 21.90 ~ 25.23초로 돌아왔다. 1차 23.35초와 같은 대역이다.

### 곁가지로 확인된 것

`set_camera_view` 를 매 프레임 불러도 **화각은 초기화되지 않는다** `확인됨`.
여섯 컷 모두 첫 프레임과 마지막 프레임의 되읽은 화각 차이가 0.000001도 이하였다.
그래서 화각은 첫 프레임에 한 번만 걸면 되고, 매 프레임 다시 걸 필요가 없다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| **v1.2** | 2026-09-04 | 2차에서 막힌 원인과 해결 기록 | #99 |
| **v1.1** | 2026-09-04 | 소스 플레이트 6컷 추가와 화각·게이트 인자 | #99 |
| **v1.0** | 2026-09-03 | 움직이는 카메라 4종으로 A컷 촬영과 전수 검사 | #99 |
