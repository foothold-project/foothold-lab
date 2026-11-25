> 분류: 운영 · 실기 Go2 X
> 작성: Claude 세션 (오흥재 지시, app-lx) · 2026-11-25 12:22 · 올림 lead-lx
> 근거: foothold-app #472 runner.env.example · #475 REMOTE.md · Jetson runner.env (비밀값 없음 · 변수 셋)
> 요지: Jetson runner.env 갈아 끼우기 · 리모컨 조작 정본 · 오늘 바뀐 것
> 상태: 확정 (팀장 12:22 「Discord 공지 해라」)

**[Go2 X 실기] Jetson 실행기 설정 갈아 끼우기 · 리모컨 조작 정리 (11/25)**

1. runner.env 갈아 끼우기
- 아래 파일 내용을 그대로 Jetson `~/foothold-policy-1122/runner.env` 에 넣고 `chmod 600` 하세요. 비밀값은 없습니다.
- 그 뒤 Go2 를 껐다 켜면 자동으로 적용됩니다.
```
FH_GO2_DIRECT_ENABLED=1
FH_GO2_DIRECT_NIC=enP8p1s0
RUNNER_ARGS=--folder ../policy/start-m15500-app --mode off --nic enP8p1s0 --live --armed-by-remote --trace-dir ../trace --stop-mode sit --fwd-max 1.2 --status 5 --debug-est ../policy/start-m15500-debug-est
```
- 예시 원본: foothold-app `apps/agent/installer/policy-runner/runner.env.example`

2. 리모컨 (START C++ 실행기)

| 조합 | 하는 일 |
|---|---|
| 위 + start | 순정 → START 모드로 서기 |
| L2 + A | START 중 앉기 |
| L2 + A (앉은 상태) | 바로 서서 START 정책 (약 4 초) |
| L2 + B | 비상: 즉시 힘 빼기 |
| start + 왼쪽 / 오른쪽 | 앉은 뒤 순정 free walk / Classic 으로 넘김 |
| 아래 + start | AME-2 자리 (지금은 알림만) |

- 속도: 전진은 끝까지 밀면 1.2 m/s 이고 제곱 곡선이라 반만 밀면 0.3 입니다. 후진 1.3 · 옆 0.8 · 회전 1.5 rad/s.
- 자세한 값 (섞인 명령의 상한, 가감속): `apps/agent/runner_cpp/REMOTE.md`

3. 오늘 바뀐 것
- 앉은 상태에서 L2+A 를 누르면 접기 없이 바로 섭니다. 일어서는 중에 다시 눌러도 앉지 않습니다.
- Go2 를 켜면 C++ 실행기가 본체 선이 붙기를 기다렸다가 저절로 켜집니다 (약 19 초).
- 기록 상한이 4 GB 로 늘었습니다. 2 GB 가 넘으면 ai-lx01 이 자동으로 백업합니다.
