# 평지 대군 주행 본 촬영

> 분류: 실험
> 작성: jay · 2026-09-03 20:50
> 근거: 실측
> 요지: 평지에서 4096마리와 1024마리 Go2 대열을 세 카메라로 20초간 촬영했다.
> 상태: 확정
> 판: v1.0
> 이슈: #99

## 촬영 조건

정책은 NVIDIA 공식 체크포인트를 썼다. SHA-256은 `f2aa77bf0349c10ec2a00071162e37123d0cf80f3447c3989c17a618e1b24ad2`다 `확인됨`.
두 컷 모두 평지 · 20초 · 50 fps · 1920 x 1080 · 명령 속도 1.0 m/s · seed 42다.
초기 흔들림은 `spawn_xy_range_m=0.1` · `yaw_range_deg=5.0` · `joint_pos_scale=0.05`로 매니페스트와 같다 `확인됨`.
`env_origins`는 스크립트에서 직접 계산했으며 여섯 실행의 최대 대조 오차는 모두 0 m다 `확인됨`.

| 컷 | 마릿수 | 대열 | 간격 | 명목 크기 | 원점 중심 간 거리 |
|---|---:|---:|---:|---:|---:|
| A · 대군 | 4096 | 128 x 32 | 2.5 m | 320 x 80 m | 317.5 x 77.5 m |
| B · 흩어짐 | 1024 | 64 x 16 | 3.0 m | 192 x 48 m | 189 x 45 m |

## 카메라

수평 화각은 모두 60도다. 좌표는 `(x, y, z)` m이며 대열 중심을 원점으로 삼았다.

| 컷 | 카메라 | eye | target | 보여 주는 것 |
|---|---|---|---|---|
| A | chase | `(-53.75, 0, 3)` | `(-20.75, 0, 0.45)` | 4096마리 대열의 규모와 20초 뒤 흩어진 배열 |
| A | topdown | `(9, 0, 281.891)` | `(10, 0, 0)` | 전체 대열과 주황색 10 m 선 앞뒤 분포 |
| A | front | `(98.75, 0, 2)` | `(46.75, 0, 0.45)` | 도착 방향에서 다가오는 전열의 짧은 컷 |
| B | chase | `(-37.5, 0, 3)` | `(-4.5, 0, 0.45)` | 1024마리가 초기 대열에서 흩어지는 변화 |
| B | topdown | `(9, 0, 170.607)` | `(10, 0, 0)` | 전체 대열과 주황색 10 m 선 앞뒤 분포 |
| B | front | `(82.5, 0, 2)` | `(30.5, 0, 0.45)` | 도착 방향에서 다가오는 전열의 짧은 컷 |

## 영상과 실측 시간

`recording`은 1,000프레임 기록 구간이다. `process`는 Kit 기동 · 환경 생성 · 정책 로드 · 예열 · 기록을 합한 전체 실행 시간이다.

| 영상 | 프레임당 렌더 | recording | process |
|---|---:|---:|---:|
| `flat_army_A_4096_chase.mp4` | 0.0351초 | 65.7초 | 104.9초 |
| `flat_army_A_4096_topdown.mp4` | 0.0345초 | 65.0초 | 104.2초 |
| `flat_army_A_4096_front.mp4` | 0.0330초 | 62.9초 | 104.2초 |
| `flat_army_B_1024_chase.mp4` | 0.0241초 | 50.8초 | 70.0초 |
| `flat_army_B_1024_topdown.mp4` | 0.0242초 | 51.0초 | 70.7초 |
| `flat_army_B_1024_front.mp4` | 0.0234초 | 49.8초 | 69.2초 |
| 합계 |  | 345.2초 | 523.1초 |

전체 프로세스 합계는 8분 43.1초다 `확인됨`. 사전 외삽 52분 0초보다 43분 16.9초 짧았다.
사전 값은 256마리 벤치마크 시간을 마릿수에 선형 비례시켰지만, 본 촬영의 렌더 시간이 그렇게 늘지 않았다.

## 프레임 전수 검사

`python sim/eval/inspect_flat_army.py sim/eval/results/20260903-flat-army`로 MP4를 전부 디코딩했다.
각 프레임을 회색조 `float32`로 바꾸고 평균이 10 미만인 프레임을 검정으로 셌다.

| 영상 | 디코딩 | 검정 | 교대 | 최소 평균 밝기 | 판정 |
|---|---:|---:|---|---:|---|
| A · chase | 1000 | 0 | false | 85.988 | 통과 |
| A · topdown | 1000 | 0 | false | 44.904 | 통과 |
| A · front | 1000 | 0 | false | 153.120 | 통과 |
| B · chase | 1000 | 0 | false | 83.631 | 통과 |
| B · topdown | 1000 | 0 | false | 48.833 | 통과 |
| B · front | 1000 | 0 | false | 152.517 | 통과 |

총 6,000프레임에서 검정 0장 · 교대 false다 `확인됨`.
각 영상의 처음 · 중간 · 마지막 프레임 18장을 `previews/`에 저장해 눈으로 확인했다.
여섯 영상 모두 로봇과 평지가 화면 안에 있고, topdown 두 영상에는 주황색 10 m 선이 보인다 `확인됨`.

## 실행 명령 전문

먼저 PowerShell에서 환경 변수를 둔다.

```powershell
$env:OMNI_KIT_ACCEPT_EULA='YES'
```

아래 여섯 명령을 저장소 루트에서 실행했다.

```powershell
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army --cut A --view chase --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army --cut A --view topdown --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army --cut A --view front --num_envs 4096 --columns 128 --rows 32 --spacing 2.5 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army --cut B --view chase --num_envs 1024 --columns 64 --rows 16 --spacing 3.0 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army --cut B --view topdown --num_envs 1024 --columns 64 --rows 16 --spacing 3.0 --headless --device cuda:0
C:\Users\AI-WS01\anaconda3\envs\isaac311\python.exe sim/eval/record_flat_army.py --checkpoint C:/isaac/IsaacLab/.pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt --output_dir sim/eval/results/20260903-flat-army --cut B --view front --num_envs 1024 --columns 64 --rows 16 --spacing 3.0 --headless --device cuda:0
python sim/eval/inspect_flat_army.py sim/eval/results/20260903-flat-army
```

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| **v1.0** | 2026-09-03 | A · B 본 촬영과 전수 검사 | #99 |
