# 압축 직전 인계

> 자동 생성 · 2026-10-07 18:35:15
> 방아쇠: "trigger":"auto"
> 이 파일은 PreCompact 훅이 씁니다. 압축 뒤 요약본만 받았으면 이것을 먼저 읽으십시오.

## 도는 학습

## 판마다 어디까지

| 판 | 마지막 iteration | 마지막 체크포인트 | 완주 | 오류 |
|---|---|---|---|---|
| `20260928_probe-det-g0` | 25 | 25 | 아니오 |  |
| `20260928_fs2-scratch-f01` | 4500 | 4500 | 예 |  |
| `20260928_fs1-scratch-f001` | 4500 | 4500 | 예 |  |
| `smoke_fromscratch` | 2 | 2 | 아니오 |  |
| `20260927_s42D-log-f01` | 1165 | 1150 | 아니오 |  |
| `20260927_s42C-log-f001` | 2677 | 2675 | 아니오 |  |
| `20260927_s42B-scalar-f01-noopt` | 2594 | 2575 | 아니오 | RuntimeError: normal expects all elements  |
| `20260927_s42A-scalar-f001-noopt` | 3000 | 3000 | 예 |  |
| `20260927_v2LG-log-feet01-s44_seed44_iter3000` | 2923 | 2900 | 아니오 | RuntimeError: normal expects all elements  |
| `20260927_v2L-logstd-s44_seed44_iter3000` | 3000 | 3000 | 예 |  |
| `20260927_v2Sc-scalar-s44_seed44_iter3000` | 2040 | 2025 | 아니오 | RuntimeError: normal expects all elements  |
| `20260927_v2L-logstd-s44_seed44_iter3000` | ? | 3000 | 예 |  |

## 예약 작업
- foothold-heartbeat : Ready
- foothold-loop-watchdog : Disabled
- FOOTHOLD-night : Ready
- FOOTHOLD-supervisor : Disabled

## 저장소
```
7e13247b 보드 정리: 열린 이슈 132건 판정표 (완료 45 · 폐기 28 · 진행 8 · 대기 51)
712019e1 merge: origin/main 을 받는다 · LEDGER 는 봇의 10-07 자동 집계(145건)를 쓴다
7ce368fc chore: 원장 열린 이슈 전수 자동 집계 (145건 · 2026-10-07)
513c2597 chore: RunPod 잔액 등급 갱신 (2026-10-07)
1b8bf561 chore: 원장 열린 이슈 전수 자동 집계 (145건 · 2026-10-06)

 M _out/loop/HANDOFF-precompact.md
 M docs/ops/doc-graph.json
 M docs/ops/versions.json
 M inbox/jay/20260927-methodology/DECISIONS-resume-vs-scratch.md
 M inbox/jay/20260929-mvp-presentation/STARRED-REPOS.md
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-assembled6-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-commands_end-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-commands_start-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-feedback_end-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-front6-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-joints_close-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-scan_done-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-sensors_end-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-side_grid6-v6d.png
 D inbox/jay/20260929-mvp-presentation/assets/go2-blender/go2-side_walk-v6d.png
```

## 열려 있는 결정

- `inbox/jay/20260927-methodology/DECISIONS-resume-vs-scratch.md` · 상태: 팀장 결정 대기
- `inbox/jay/20260927-methodology/QUESTIONS-20260927.md` · 팀장 물음 원본
- `_out/loop/supervisor.log` · 감독 스크립트 기록

## 2026-10-07 오후 · 보드 정리 (팀장 승인)
- gh 토큰에 project 스코프 추가(팀장 인증). 열린 이슈 148 → 35. 팀장 계정 132건을 읽기 전용 조사 4묶음으로 판정(판정표 `_out/board-audit/20261007-open-issues.md` · 7e13247b) 뒤 113건을 근거 댓글과 함께 닫음(완료 45 · 진행하지 않음 68). 닫힌 이슈는 전부 보드 Done.
- 남긴 팀장 이슈 19: In Progress #463 #505 #511 #515 #516 #520 · Todo #124 #350 #367 #374 #375 #376 #377 #378 #443 #469 #512 #513 #514. 남긴 기준: 지금 진행 중 · 돌고 있는 자동화의 결함 · 공개 문서의 틀린 주장 · 다음 평가에 쓸 평가 장치 · MVP 이후 새 과제.
- 팀원 이슈 16건은 손대지 않음(보고 #520 을 받은 뒤 본인이 갱신).
- 규칙(메모리 move-issues-on-the-board): 시작하면 In Progress · 끝나면 근거 댓글 · 닫기 · Done.
