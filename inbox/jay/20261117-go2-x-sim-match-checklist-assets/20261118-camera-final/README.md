# D435i 몸통 기준 35° 최종 고정과 Classic 주행 유지성

2026-11-18 D435i 가속도를 depth 광학좌표로 변환하고 Go2 `rt/lowstate` projected gravity와 비교해 카메라의 몸통 기준 상대 하향 pitch를 측정했다. 카메라 위치나 바닥 거리 없이 중력 방향 두 개를 맞추므로 몸통의 순간 pitch/roll과 바닥 기준 높이에 의존하지 않는다. 정지 상태에서만 판정하며 이동 가속도가 섞인 구간은 상대각 정본으로 쓰지 않는다.

## 최종 체결 직후

| 측정 | 상대 하향각 | 몸통 pitch | 몸통 roll |
|---|---:|---:|---:|
| pre-1 | 35.069° | -0.291° | -0.077° |
| pre-2 | 35.072° | -0.305° | -0.096° |
| pre-3 | 35.062° | -0.302° | -0.085° |
| 평균 / 모집단 표준편차 | **35.068° / 0.004°** | | |

사용자 실측 광학 중심 높이는 약 0.420 m였다. 몸통이 거의 수평이라 앞선 몸통 pitch 약 +2.5~3° 상태에서의 0.395 m보다 높아졌다. 높이는 상대각 계산에 사용하지 않는다.

## Classic ㅁ자 주행

사용자는 제자리 회전 뒤 좌회전 방향으로 교실 ㅁ자 코스를 한 바퀴 돌아 출발점에 왔고, 방향을 바꿔 우회전 방향으로 한 바퀴 돈 뒤 정지했다. 180초 기록 중 관절 속도/각속도 활동 proxy는 약 15.18~122.38초, 106.9초였다.

- `ang_z` 양의 누적: +931.9°.
- `ang_z` 음의 누적: -883.7°.
- 순 적분: +48.2°. 두 회전 방향이 모두 충분히 포함됐지만 이를 정확한 경로 yaw 정본으로 쓰지는 않는다.
- Depth: 5,365 frames / 179.974 s / 평균 29.810 fps.
- 평균 zero ratio 10.127%, 0.2~3.0 m 밖 또는 무효 11.179%.
- 최고 모터 온도 56°C(RL hip), 시작·종료 모두 56°C. `reserve[0]` nonzero 표본 0, errorlist 메시지 0.
- 배터리 SOC 74%→72%, 순정 lowcmd 최대 `kp=30`, `kd=1`, sport marker 2010.

약 10초 부근에는 system-wide 입력 정지가 한 번 있었다. DDS state/cmd/sport age가 약 1초까지 함께 증가했고 Depth arrival도 최대 1,045 ms 멈췄다. Depth frame number는 `287→0`으로 한 번 reset됐고 device timestamp 간격은 약 1,130 ms였다. 이후 forward gap 없이 frame 0부터 5,106까지 이어졌다. 기존 `depth_walk_capture`의 `frame_number_gaps=0`은 감소/reset을 세지 않으므로 이 기록을 프레임 손실 0으로 판정하면 안 된다. 이 현상은 브라켓 유지 판정과 분리해 D435i/Jetson 장시간 운영 관문에 남긴다.

## 주행 직후

| 측정 | 상대 하향각 | 몸통 pitch | 몸통 roll |
|---|---:|---:|---:|
| post-1 | 34.995° | -0.256° | +0.601° |
| post-2 | 35.023° | -0.311° | +0.635° |
| post-3 | 35.051° | -0.322° | +0.609° |
| 평균 / 모집단 표준편차 | **35.023° / 0.023°** | | |

주행 전후 평균 변화는 **-0.045°**이고 두 판 모두 목표 35°의 ±0.1° 안이다. 이 Classic 좌·우 ㅁ자 주행에 대해서는 브라켓 단기 유지성을 통과로 판정한다. 장기 반복 운용과 충격 뒤에는 witness mark와 상대각을 다시 확인한다.

## 파일

- `pre/`, `post/`: D435i accel과 Go2 state 독립 5초 측정 3회씩. CSV gzip.
- `walk/depth_walk.csv.gz`: 프레임별 도착 간격·frame number·zero/outside ratio.
- `walk/state.csv.gz`: 50 Hz projected gravity·각속도·관절 상태·순정 lowcmd.
- `walk/monitor.csv.gz`, `monitor-summary.json`: 온도·reserve·lost·lowcmd·message age.
- `tools/relative_pitch_live.cpp`: 실시간 D435i↔Go2 상대각 GUI. receive-only이며 publisher나 motion client를 만들지 않는다.

비밀번호와 D435i serial은 기록하지 않았다.
