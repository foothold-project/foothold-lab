> 분류: 가이드 · 실기 측정 절차
> 작성: Claude 세션 (오흥재 지시, go2-lx) · 2026-11-19
> 근거: [`GO2X-JETSON-SETUP-1119.md`](../../20261101-app/GO2X-JETSON-SETUP-1119.md) 8 절 · 이슈 #861 · Jetson `~/go2_diag/viewer` 스크립트 (ai-lx01 미러에서 읽음) · 11/19 05:20 녹화 `derived/`
> 요지: 11/19 실기 측정 8 절 표의 2 · 3 · 5 · 6 번을 누가 해도 같은 순서 · 같은 합격 줄 · 같은 파일 이름으로 하게 하는 절차서 묶음
> 상태: 초안 · 측정 전 (값 칸은 원자료가 오면 채운다) · 11/19 14:5x foothold-go2 PR #14 에서 옮김 (팀장 14:46: 측정 절차 · 시험 도구는 lab)

# 11/19 실기 측정 절차서

| 번호 | 측정 | 절차서 | 로봇 움직임 |
|---|---|---|---|
| 1 | 카메라 높이 · 각 (녹화 깊이로 계산) | 끝남 · 값은 [02](02-ruler-height.md) 의 비교표 | 없음 |
| 2 | 자로 잰 높이 (바닥→몸 중심 · 바닥→D435i 광학 중심) | [02-ruler-height.md](02-ruler-height.md) | 서기 · 앉기 (팀장 조이스틱) |
| 3 | Go2 자체 SLAM (`/uslam`) 지도 만들기 · 저장 · 다시 위치 찾기 | [03-uslam.md](03-uslam.md) | 걷기 (팀장 조이스틱) · SLAM 켜기 (팀장 · Unitree 앱) |
| 5 | 정책 깊이 입력: 정렬 깊이 대 원본 깊이 | [05-depth-input.md](05-depth-input.md) | 없음 (녹화만으로 판정 가능) |
| 6 | 깊이 안정성: 젠더 A/B/C · 5 분 · 1 초 정지 | [06-depth-stability.md](06-depth-stability.md) | 없음 (앉은 채) |

## 모든 절차에 공통

**로봇 명령.** 이 절차서의 어떤 줄도 로봇에 명령을 보내지 않는다. 서기 · 앉기 · 걷기 · SLAM 켜기는 「팀장 조이스틱 또는 팀장 동의」 라고 적혀 있고, AI 세션은 그 줄을 스스로 실행하지 않는다 (foothold-go2 `AGENTS.md` 5a). 여기 나오는 스크립트는 모두 받기만 한다 (감시 · 녹화 · 표시).

**시작 전 확인 (매번).**

| 확인 | 명령 (Jetson) | 합격 |
|---|---|---|
| 앱 agent · 다른 명령 프로그램이 꺼져 있다 (명령 주인 하나) | `systemctl --user is-active foothold-robot.service` · `ps -eo args \| grep -E "[f]oothold\|[l]owcmd"` | `inactive` 또는 `failed` · 줄 없음 |
| 배터리 · 온도 | 감시 15 초: `~/go2_diag/20261118-go2-readonly-boot-gate/build/go2_readonly_monitor <망 이름> 15 /tmp/pre.csv` | SOC 50 % 이상 · 관절 최고 50 °C 미만 · reserve nonzero 0 · errorlist 0 |
| 감시를 먼저 켠다 | 서기 전에 각 절차의 녹화 스크립트 (감시 포함) 를 먼저 켠다 | `monitor.csv` 줄 수가 늘어난다 (`wc -l` 두 번) |

**녹화 중 끊김 감시 (11/19 14:4x 덧붙임).** 05:20 녹화에서 141 초에 Go2 본체 쪽 (L2 · odom · IMU · lowstate) 이 한꺼번에 끊겼는데 녹화는 끝까지 「정상」 이라 아무도 몰랐다 (로봇은 계속 걸었고 카메라만 남음 · 까닭 미확인 · [`../20261119-0520-room-walk-full/map/README.md`](../20261119-0520-room-walk-full/map/README.md)). 그래서 녹화 스크립트 (`full_record.sh` · `uslam_record.sh`) 를 켠 뒤 **다른 터미널에서** 감시를 같이 켠다:

```
bash <이 폴더>/tools/watch_record.sh <녹화 스크립트가 찍은 폴더> <본체 쪽 망 이름> <녹화 초>
```

간격마다 `state_age_ms` (감시 `console.log`) 와 L2 · odom · 깊이 Hz 를 `watch.log` 에 적고, 끊기면 터미널에 「!! 끊김」 과 종소리, 그 순간 망 상태 (`ip -s link` · `ip neigh` · 커널 기록) 를 `watch_drop_<시각>.txt` 로 한 번 남긴다. 녹화는 멈추지 않는다. 끊김을 보면 사람이 걷기를 멈추게 하고 (팀장 조이스틱), 기록 폴더 이름과 시각을 적는다. ROS 쪽 Hz 확인은 Jetson 에서 아직 돌려 보지 않았다 (미확인 · 첫 녹화 때 `watch.log` 의 Hz 칸이 숫자로 차는지 본다).

멈춤 기준 (어느 절차든): 관절 60 °C 넘음 · reserve 0 아님 · 적색 점멸 · 이상한 소리 → 팀장이 조이스틱으로 앉힘 (L2+B). AI 는 「멈추십시오」 라고 알리기만 한다.

**하지 말 것.** Jetson 에서 `apt --fix-broken install` · `apt upgrade` 금지 (L4T 고정 묶음이 깨짐). `sudo` 와 비밀번호는 팀장이 친다. 원본 기록은 회수 · SHA-256 대조 뒤에도 팀장 동의 없이 지우지 않는다.

**회수 · 기록.** 원본 bag 은 크니 ai-lx01 `/home/jay/data/go2x_raw/` 에 두고 sha256 을 적는다. 작은 원자료 (CSV · 사진 · 요약) 는 이 폴더 아래 측정별 폴더에 PR 로 넣는다. `rs.log` · `console.log` 에는 장치 일련번호가 찍히므로 통째로 옮겨 적지 않는다 (필요한 줄만 `grep`).

**파일 이름 규칙.** Jetson `~/go2_diag/records/<YYYYMMDD-HHMM>-<측정 이름>/` (스크립트가 시각을 붙인다). 측정 이름은 각 절차서에 정해 둔다.

**Jetson 접속.** 주소 · 계정은 인수인계 문서 `inbox/jay/20261118-go2-x-ai-lx01-handoff.md` 에 있다 (여기 적지 않는다). 큰 녹화 회수는 랜선으로 (Wi-Fi + Tailscale 은 약 1.5 MB/초).
