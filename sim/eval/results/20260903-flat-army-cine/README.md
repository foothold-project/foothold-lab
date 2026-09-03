# 평지 대군 영화적 카메라 촬영

> 분류: 실험
> 작성: jay · 2026-09-03 22:34
> 근거: 실측
> 요지: 평지에서 4096마리 Go2 대열을 움직이는 카메라 4종으로 각각 20초간 촬영했다.
> 상태: 확정
> 판: v1.0
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

수평 화각은 모두 60도다. 좌표는 `(x, y, z)` m이며 대열 중심을 원점으로 한다.
진행률 `s`는 첫 프레임의 0.0부터 마지막 프레임의 1.0까지 프레임마다 갱신했다.
아래 시작과 끝 좌표는 정의된 경로를 계산한 값이다 `확인됨`. 지시된 카메라 좌표를 조정하지 않았다.

| 카메라 | 시작 eye | 끝 eye | 시작 target | 끝 target | 보여 주는 것 |
|---|---|---|---|---|---|
| dolly | `(-46.75, 0, 0.5)` | `(9, 0, 281.891)` | `(-28.75, 0, 0.4)` | `(10, 0, 0)` | 후미 저공에서 시작해 전체 대열을 드러내는 달리 아웃 |
| aisle | `(-35, 0, 0.45)` | `(-15, 0, 0.45)` | `(-20, 0, 0.35)` | `(0, 0, 0.35)` | 로봇과 같은 속도로 대열 사이 통로를 흐르는 저공 추적 |
| macro | `(-35, 0, 0.22)` | `(-15, 0, 0.22)` | `(-32, 0, 0.18)` | `(-12, 0, 0.18)` | 발 높이에서 가까이 보는 통로 추적 |
| hero | `(64.75, 0, 0.6)` | `(64.75, 0, 0.6)` | `(42.75, 0, 0.45)` | `(58.75, 0, 0.45)` | 고정된 정면 저공 카메라로 다가오는 전열 |

## 영상과 실측 시간

`recording`은 1,000프레임 기록 구간이다. `process`는 Kit 기동 · 환경 생성 · 정책 로드 · 예열 · 기록을 합한 전체 실행 시간이다.

| 영상 | 프레임당 렌더 | recording | process |
|---|---:|---:|---:|
| `flat_army_A_4096_dolly.mp4` | 0.0361초 | 66.8초 | 105.7초 |
| `flat_army_A_4096_aisle.mp4` | 0.0355초 | 65.9초 | 103.4초 |
| `flat_army_A_4096_macro.mp4` | 0.0365초 | 67.6초 | 104.4초 |
| `flat_army_A_4096_hero.mp4` | 0.0366초 | 67.4초 | 104.6초 |
| 합계 |  | 267.7초 | 418.2초 |

전체 프로세스 합계는 6분 58.2초다 `확인됨`.

## 프레임 전수 검사

`python sim/eval/inspect_flat_army.py sim/eval/results/20260903-flat-army-cine`로 MP4를 전부 디코딩했다.
각 프레임을 회색조 `float32`로 바꾸고 평균값 10 미만인 프레임을 검정으로 셌다.

| 영상 | 디코드 | 검정 | 교대 | 최소 평균 밝기 | 판정 |
|---|---:|---:|---|---:|---|
| A · dolly | 1000 | 0 | false | 27.526 | 통과 |
| A · aisle | 1000 | 0 | false | 97.073 | 통과 |
| A · macro | 1000 | 0 | false | 92.838 | 통과 |
| A · hero | 1000 | 0 | false | 154.782 | 통과 |

총 4,000프레임에서 검정 0 · 교대 false다 `확인됨`.
각 영상의 0 · 250 · 500 · 750 · 999번 프레임, 총 20장을 `previews/`에 저장했다 `확인됨`.

## 실행 명령 전문

먼저 PowerShell에서 환경 변수를 뒀다.

```powershell
$env:OMNI_KIT_ACCEPT_EULA='YES'
```

아래 네 명령을 저장소 루트에서 실행했다.

```powershell
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view dolly --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view aisle --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view macro --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army-cine --cut A --view hero --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
python sim/eval/inspect_flat_army.py sim/eval/results/20260903-flat-army-cine
```

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| **v1.0** | 2026-09-03 | 움직이는 카메라 4종으로 A컷 촬영과 전수 검사 | #99 |
