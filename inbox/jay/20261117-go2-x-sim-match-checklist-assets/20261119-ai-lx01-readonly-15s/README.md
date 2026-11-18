> 분류: 실기 측정 원본
> 작성: Claude 세션 (오흥재 지시, lead-lx) · 2026-11-19
> 근거: `inbox/jay/20261118-go2-x-ai-lx01-handoff.md` 7 절 2 · 이슈 #861
> 요지: 숙소 이동 (11/18 22:00) 뒤 Damping 상태 15 초 receive-only: SOC 33 % · 앞 hip 34 °C · 최고 37 °C (RR hip) · reserve nonzero 0 · errorlist 0
> 상태: 측정 · 회수 · 대조 끝 (로봇 명령 없음 · Jetson 원본 지우지 않음)

# 20261119 ai-lx01 receive-only 15 초

| 칸 | 값 (console.log 첫 · 끝 줄) |
|---|---|
| SOC | 33 % (15 초 내내) |
| 모터 온도 | FR hip 34 °C · FL hip 34 °C · 최고 37 °C (RR hip) |
| reserve0 nonzero · errorlist | 0 · 0 |
| kp max · kd max · sport marker | 0.0 · 3.0 · 1001 (Damping 과 맞음) |
| state age · cmd age | 0.2~0.3 ms · 1.3~1.7 ms |
| 콜백 | state 7,518 · cmd 7,512 · sport 4,504 · error 0 · 표본 750 |

| 파일 | SHA-256 (Jetson 원본 = 회수 사본) |
|---|---|
| `console.log` | `782bf7091d3169a766eb655a745eafd0735ab14842e459a7e5f0d42f65e9485e` |
| `monitor.csv` | `3da009783c315383c2b751b292d34294de4bef95dd1635fb77d5ad87393fb62a` |

## 실행한 명령 (Jetson · 2026-11-19 00:5x KST)

```bash
cd /home/nvidia/go2_diag/20261118-go2-readonly-boot-gate
python3 verify_readonly_source.py          # receive-only source guard: PASS
./build/go2_readonly_monitor enP8p1s0 15 /home/nvidia/go2_diag/records/20261119-ai-lx01-readonly-15s/monitor.csv > .../console.log
```

같은 접속에서: `foothold-robot.service` failed · enabled · TCP 9539 · 9611 listener 없음. 비밀 문자열 검사 걸린 것 없음.
