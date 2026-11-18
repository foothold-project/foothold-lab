> 분류: 실기 측정 원본 회수
> 작성: Claude 세션 (오흥재 지시, lead-lx) · 2026-11-19
> 근거: `inbox/jay/20261118-go2-x-ai-lx01-handoff.md` 6 · 7 절 · 이슈 #861
> 요지: 2026-11-18 충전 전 receive-only 15 초 기록 원본 세 파일을 Jetson 에서 회수했고 전체 SHA-256 이 Jetson 원본 · 11/18 기록 앞부분과 같다
> 상태: 회수 · 대조 끝 (Jetson 원본은 지우지 않음)

# 20261118 priority read-only prestand 원본

| 파일 | SHA-256 (Jetson 원본 = 회수 사본) | 11/18 기록 앞부분 |
|---|---|---|
| `monitor.csv` | `c41328d7fe0c8eca8debeebe8d918fef1eff8d10d71ccf5a422d38b8e19e0b74` | `c41328d7` |
| `console.log` | `1b039cfe163856b73efb6215ae16be22340912f045e4c5d60f42184f720e6564` | `1b039cfe` |
| `summary.json` | `6c7d1a1a9c19c09d5ca46e3dc17fd3c622b230b940520752702402fb9775185a` | `6c7d1a1a` |

## 실행한 명령 (ai-lx01 · 2026-11-19 00:5x KST · 직결 · 로봇 명령 없음)

```bash
ssh -i ~/.ssh/id_ed25519_go2x nvidia@<Jetson 직결 주소> 'sha256sum /home/nvidia/go2_diag/records/20261118-priority-readonly-prestand/*'
scp -i ~/.ssh/id_ed25519_go2x nvidia@<Jetson 직결 주소>:/home/nvidia/go2_diag/records/20261118-priority-readonly-prestand/{console.log,monitor.csv,summary.json} .
sha256sum console.log monitor.csv summary.json
```

- 비밀번호 · token · 개인키 · serial 문자열 검사: 걸린 것 없음 (`grep -i password|passwd|token|secret|serial|BEGIN .*KEY`).
- 같은 접속에서 읽은 Jetson 상태: `foothold-robot.service` = failed · enabled (11/18 감사와 같음) · TCP 9539 · 9611 listener 없음 · foothold APP 프로세스 없음.
