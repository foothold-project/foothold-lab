분류: 실기 원자료에서 뽑은 값 · 영상 (방 걷기 2 차 · D435i 색 · 깊이 · 카메라 높이 · 각)
작성: Claude 세션 (오흥재 지시, lead-lx)
근거: Jetson `~/go2_diag/records/20261119-0520-room-walk-full/bag/bag_0.db3` (330.3 초 · 체크섬 대조로 ai-lx01 에 거울) · `go2x_cam_derive.py` (이 폴더)
요지: 선 자세 (매트 위) D435i 높이 0.3716 m · 아래로 38.59° · 옆 +1.89° · 앉음 0.1431 m · 33.35° · -1.94° · 색 · 깊이 영상 330 초
상태: 계산 끝 (11/19 06:33) · 매트 두께 · 맨바닥 · 줄자 확인은 11/19 낮 ai-lt01 에서

# 방 걷기 2 차 (11/19 05:20) · 카메라 높이 · 각 · 영상

보는 페이지: [`../../20261101-app/ROOM-MAP-1119.html`](../../20261101-app/ROOM-MAP-1119.html) (지도 만든 법 · 영상 · 각도 한 장에)

| 자세 (bag 기준 초) | 카메라 높이 | 아래로 숙인 각 | 옆 기울기 | 맞춘 프레임 | 잔차 |
|---|---|---|---|---|---|
| 선 자세 (68~98 s · 매트 위) | 0.3716 m | 38.59° | +1.89° | 816/816 | 3.5 mm |
| 앉음 (10~55 s) | 0.1431 m | 33.35° | -1.94° | 1229/1229 | 3.0 mm |

- 같은 때 SDK 몸 높이 (monitor.csv 중앙): 선 0.322 m · 앉음 0.069 m.
- 프레임 사이 흔들림 (p10~p90) 은 0.3 mm · 0.05° 아래. 같은 자리를 다시 재는 정도이지 절대 정확도가 아니다 (D435i 공장 보정 · 매트 두께 미측).
- 각은 바닥 평면 기준이다 (중력 기준 아님 · 바닥이 수평일 때만 같음).

## 파일

| 파일 | 무엇 |
|---|---|
| `color_full_web.mp4` | 색 영상 전체 330.3 초 · 640×480 · 30 fps · 9909 프레임 (원본을 crf 28 로 다시 줄임) |
| `depth_full_web.mp4` | 깊이 영상 전체 · turbo 색 0~4 m · 검정 = 값 없음 · 9909 프레임 (crf 30) |
| `floor_summary.json` | 창마다 높이 · 각 중앙 · p10 · p90 · 최소 · 최대 · 내부 파라미터 |
| `floor_overlay_standing_t083.00s.png` · `floor_overlay_sitting_t032.49s.png` | 색 · 깊이 · 바닥으로 잡힌 점 (초록) 확인 그림 |
| `still_color_t080s.png` 등 6 장 | 80 · 150 · 250 초 정지 화면 (색 · 깊이) |
| `go2x_cam_derive.py` | 쓴 스크립트 하나 (floor · media 두 명령) |
| `README-derived.txt` | 계산한 세션의 원래 설명 (방법 · 규약 · 한계 전부) |

원본 (ai-lx01 에만 · 저장소 밖):

| 원본 | sha256 |
|---|---|
| `/home/jay/data/go2x_raw/jetson_go2_diag/records/20261119-0520-room-walk-full/derived/color_full.mp4` (26 MB) | 006068fc07c3a470ed07f79a139bc4f4920f98b177251f7abc59d4f637eefaff |
| `/home/jay/data/go2x_raw/jetson_go2_diag/records/20261119-0520-room-walk-full/derived/depth_full.mp4` (85 MB) | 010cb8ac2e60e1c29b1ff83b6480218e1bd3cfc08836ea69dbac396460e8728e |
| `/home/jay/data/go2x_raw/jetson_go2_diag/records/20261119-0520-room-walk-full/bag/` (bag 원본) | Jetson 대조 0 차이 (06:2x) |

한계: 302.88 초에 색 4.3 초 · 깊이 3.9 초 녹화 끊김 (영상에 빨간 「stale」 로 보임). 깊이 프레임 9149 대 색 9772.
