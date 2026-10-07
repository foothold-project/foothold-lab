# 압축 직전 인계

> 자동 생성 · 2026-10-07 21:24:40
> 방아쇠: "trigger":"manual"
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
- foothold-heartbeat : Disabled
- foothold-loop-watchdog : Disabled
- FOOTHOLD-night : Disabled
- FOOTHOLD-supervisor : Disabled

## 저장소
```
dcaf656a 핸드오프: FOOTHOLD-night 예약 작업 끔 · #468 근거 보강
77de7850 핸드오프: 보드 안내 공지 발송 · heartbeat 예약 작업 끔
e1253cc4 핸드오프: 보드 정리 부수 효과와 원장 복구
27e7eff6 핸드오프: 보드 정리 결과 (열린 이슈 148 → 35)
7e13247b 보드 정리: 열린 이슈 132건 판정표 (완료 45 · 폐기 28 · 진행 8 · 대기 51)

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
- 부수 효과 실측: 디스코드 알림 113건(닫힘마다 「완료 · 제목」 · not planned 68건도 「완료」 표기) · ledger-sync 113회 성공 0(사람 표의 닫힌 번호 경고가 GITHUB_OUTPUT 을 깸) → PR #525 로 사람 표 정리 · 수동 실행 성공 · 원장 35건. 스크립트 결함과 알림 문구는 super 에 넘김. 팀원 배정 이슈 11건(#28 #65 #66 #67 #68 #78 #79 #81 #82 #83 #84)도 닫혔다.
- 10/7 저녁: 보드 정리 안내 공지(docs/notices/2026-10-07-board.md · PR #527)를 팀장 확인 뒤 디스코드 발송. 텔레그램 「[진행] 도는 학습 없음」 발신처 = Windows 예약 작업 foothold-heartbeat(_out/loop/heartbeat.py · 20분마다 · 9/24 lead 가 만듦) → 팀장 지시로 Disable. 다시 켜려면 `Enable-ScheduledTask -TaskName foothold-heartbeat`. FOOTHOLD-night(night.sh)는 Ready 지만 9/30 01:03 이후 다음 실행 예정 없음.
- FOOTHOLD-night 도 팀장 지시로 Disable(10/7). 9/28 에 만든 무인 학습 파이프라인(scratch vs resume · fs1 @cuda:0 · fs2 @cuda:1 · 10분마다 한 단계 · 2일 반복). 9/28 14:23 회차 1 로 끝냈고 회차 2 는 장치 효과 0(121 파일 동일)이라 뺐다고 night.log 에 있다. #468 에 근거 보강 댓글.
- 10/7 밤: Star 정리 두 파일을 mai-os `research/starred-repos/`(7c58181)로 옮기고 lab 에서 지움(#529 · facbe25e). super #530(#526 수정 · ledger-sync 출력 허용 목록 · 디스코드 닫힘 사유 구분) 은 팀장 컨펌 대기 · lead 는 머지 안 함.
- #511 담당 = lead(팀장 10/7). 팀장이 NAS `\100.80.160.84\foothold` 를 N: 로 붙임(비지속 · 재부팅하면 `net use` 다시). 1단계 끝: 영상 345개 · 580.5 MiB → `N:/media/site` · sha256 전수 일치 2회(d26adbfd · PLAN v0.2 · 단위 MB→MiB 정정). 다음 = 2단계 서빙 경로(A Funnel: 관리 화면 nodeAttr · HTTPS 인증서 · MagicDNS 필요 · 대역폭 제한 문서상 있음 / B Cloudflare: 도메인 없음) 팀장 결정.
- #524 닫음(머지 안 함). 정리본 `docs/research/20261007-ame2-go2-v1-v6.md`(#532 · 163e0dae). 숫자 전부 일치 · v6 은 정면 목표 + 1500회 거리 승급 두 요인 · 판마다 평가 규약 다름. 사이트 배포는 안 함(Vercel 저장소 가득 · 배포 시점 팀장 결정). #520 임석헌 칸 미체크(팀장 판단).
- #519 라현 문서는 inbox 에만 있어 웹에 없음(사이트는 docs/ 승격분만 게시). docs/research 승격 여부 팀장 답 대기.
