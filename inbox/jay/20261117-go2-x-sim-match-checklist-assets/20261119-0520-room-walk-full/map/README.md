분류: 실기 원자료에서 뽑은 값 (방 걷기 2 차 · L2 위에서 본 지도 · 3D 점)
작성: Claude 세션 (오흥재 지시, go2-lx) · 2026-11-19 14:3x
근거: ai-lx01 거울 `/home/jay/data/go2x_raw/jetson_go2_diag/records/20261119-0520-room-walk-full/bag/bag_0.db3` · `../room_map_rosbags.py` (04:59 `room_map.py` 를 rosbags 로 옮긴 것)
요지: 05:20 녹화로도 위에서 본 지도를 만들었다. 다만 141 초에 Go2 본체 쪽 통신이 모두 끊겨 (로봇은 계속 걸음) 걸은 길이 5.12 m 뿐이다
상태: 1 차 그림 · SLAM 아님 (Go2 odom 그대로 쌓음)

# 방 걷기 2 차 (11/19 05:20) 지도

![위에서 본 지도](room_topview.png)

| 값 | 05:20 (이 폴더) | 04:59 (`../../20261119-0459-room-walk/`) |
|---|---|---|
| L2 점구름 장 (`/utlidar/cloud_deskewed`) | 2035 | 7016 |
| 걸은 길 · 시간 | 5.12 m · 140.9 초 | 20.75 m · 493.6 초 |
| 그림 범위 | 12.2 × 10.6 m | 12.4 × 14.1 m |
| 바닥 칸 · 장애물 칸 (5 cm) | 4257 · 1588 | 9546 · 4492 |
| 쌓은 점 · 5 cm 3D 칸 | 10,792,881 · 44,229 | 37,567,767 · 125,389 |

## 이 녹화의 L2 는 앞 141 초뿐 (확인됨 · 까닭 미확인)

bag 안 시각 (녹화 시작 기준): `/utlidar/cloud_deskewed` 0.0~141.1 초 · `/utlidar/cloud` 0.0~141.1 초 · `/utlidar/robot_odom` 0.0~146.8 초 (141.1 초 뒤로는 2.8 · 0.8 · 2.1 초 간격으로 몇 개만) · `/utlidar/imu` 0.0~147.8 초 · 깊이 `camera_info` 0.1~330.3 초.

`robot_odom` 으로 잰 순서: 앉음 0~63 초 (몸 z 0.048 m) · 일어섬 63.1 초 · 가만히 섬 ~99 초 · 걷기 99 초부터. 그래서 L2 지도에는 걷기 앞 약 42 초 (그중 1 초 평균 0.1 m/s 넘게 움직인 시간 약 21 초) 만 들어 있다.

끊긴 모양 (14:4x 조사 · 읽기만):

| 근거 | 본 것 |
|---|---|
| `monitor.csv` · `console.log` (Unitree SDK 로 따로 받는 감시) | `state_callbacks` 가 감시 시각 142.40 초 (감시가 녹화보다 약 1.3 초 먼저 켜져 bag 141.1 초와 같은 때로 보임) 에 70,703 에서 멈춤. 그 뒤 330 초 넘게 `state_age_ms` 만 늘어남 (마지막 줄 336,606 ms). `sport_callbacks` 도 42,124 에서 같이 멈춤 |
| 끊기기 직전 1 초 | SOC 15 % · 전압 27.5 V · 전류 1.5~2.4 A · `bms_status` 8 · reserve 0 · 최고 46 °C. 전압이 떨어지는 모양은 없음 |
| 카메라 영상 (`derived/color_full.mp4`) | 150 · 170 · 200 · 230 · 260 · 290 초 화면이 모두 다른 곳 (의자 다리 · 침대 밑 · 문간 · 매트) → 로봇은 141 초 뒤에도 290 초 무렵까지 걸었다 |
| `bag.log` | 녹화기 오류 없음 (끝까지 `Recording stopped` 정상). `/sportmodestate` 는 `unitree_go` 메시지 정의가 없어 처음부터 못 받음 (1520 줄 경고. `GO2X-JETSON-SETUP-1119.md` 7 절 「`/sportmodestate` 가 bag 에 안 들어간 까닭 미확인」 의 답) |
| 05:39 `uslam` 녹화 `console.log` | 「5 초 안에 lowstate 없음」 · 19 분 뒤에도 본체 쪽이 조용했다 |

읽은 뜻 (추정): 녹화기나 L2 하나의 문제가 아니라, **Go2 본체가 Jetson 쪽으로 보내던 모든 것이 한 순간에 끊겼다** (Unitree SDK 감시와 ROS 2 녹화 둘 다, 서로 다른 프로그램인데 같은 때). 로봇은 계속 걸었으므로 본체가 꺼진 것은 아니다. 후보: Jetson 과 본체 사이 내부 망이 끊김 · 본체가 낮은 배터리 (15 %) 에서 바깥으로 내보내기를 멈춤. 가르려면 Jetson 의 그 시각 커널 기록 (`journalctl -k` 에서 망 연결 끊김 줄) 과 다음 측정 때 끊김 순간의 `ip -s link` · 본체 주소 ping 이 필요하다 (안 함 · 이 기기에서 Jetson 호스트 키 확인이 안 돼 접속하지 않음).

## 만든 법

```
/home/jay/data/go2x_raw/.venv-rosbags/bin/python -I room_map_rosbags.py <bag 폴더> <출력 폴더>
```

- 04:59 `room_map.py` 와 같은 수치 (몸 둘레 0.6 m 밖 · 점 둘에 하나 · 걸은 길 둘레 5 m · 5 cm 칸 · 바닥 = 높이 아래 2 % · 장애물 = 0.15~1.8 m 점이 30 % 넘음).
- 옮긴 것을 답을 아는 입력으로 먼저 시험했다: 04:59 bag 에 돌리니 `room_map_info.json` 의 모든 수 (점구름 7016 · 쌓은 점 37,567,767 · 바닥 높이 · 범위 · 바닥 칸 9546 · 장애물 칸 4492 · 걸은 길) 가 원래와 같고, `room_grid.npz` 의 `top` · `path` · `origin` 은 비트까지 같다. 점 수 칸 70 개 (0.1 %) 만 점 하나씩 이웃 칸으로 갔다 (칸 경계 반올림 · 합계 같음).
- 덧붙임: 5 cm 3D 칸마다 점 평균 하나를 `room_points_5cm.npy` (float32 · N×3 · odom 틀 원래 z) 로 남긴다. 04:59 폴더의 같은 이름 파일도 이 스크립트로 다시 만든 것이다 (ai-lx01 의 05:19 판 68,843 점과는 줄인 방법이 달라 수가 다름).

## 3D 보기

[`../../../20261101-app/ROOM-POINTS-3D-1119.html`](../../../20261101-app/ROOM-POINTS-3D-1119.html): 두 녹화의 `room_points_5cm.npy` 를 바닥 기준 -0.2~2.5 m 만 골라 mm 정수로 페이지 안에 넣었다 (1.4 MB · 따로 읽는 파일 없음 · three.js 는 인터넷에서 받음). 만든 명령:

```
python -I room_points_html.py room_points_3d.template.html ../../20261101-app/ROOM-POINTS-3D-1119.html \
  "04:59 녹화=<04:59 map 폴더>" "05:20 녹화=<05:20 map 폴더>"
```

## 파일 · sha256

| 파일 | sha256 |
|---|---|
| `room_topview.png` | c3bf5377e2c26691929cc7bb36a01343dffd8b8f345948fafe435bd81192fe3d |
| `room_map_info.json` | 45204b0ef8bc43fc44f70d92db5a14a21bfffbca8da3d813da20af1a9edc9451 |
| `room_points_5cm.npy` (530 KB) | a8f5b1c21d0ed10b6dd92a73eb2cee71e96f60f26db9f87e02c7dbfb7ddd9ae2 |
| `../../20261119-0459-room-walk/room_points_5cm.npy` (1.5 MB) | f83a0d77750c4b5e839b7562c7f09b44c6c89bfb4128b88a90fcf4422e6e3b83 |

`room_grid.npz` 는 ai-lx01 `/home/jay/data/go2x_raw/jetson_go2_diag/records/20261119-0520-room-walk-full/map/` 에만 둔다 (04:59 판은 `/home/jay/data/go2x_raw/20261119-0459-room-walk/map_rosbags/`).
