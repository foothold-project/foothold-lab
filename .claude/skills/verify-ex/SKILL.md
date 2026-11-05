---
name: verify-ex
description: FOOTHOLD EX 학습 실행(EX-41 · EX-42 …)을 띄우고, 매 점검 · 250 경계 · 단계 끝 · 끝날 때 무엇을 어떤 명령으로 확인하는지 정한 검증 절차. 「EX 띄워」 「경계 보고」 「단계 끝」 「학습 점검」 「밤샘 감시」 때 쓴다. pstack create-verification-skill 틀(Launch · Doctor · Drive · Evidence · Cleanup)을 우리 실험에 맞춘 것.
---

# verify-ex · FOOTHOLD EX 실행 검증 절차

근거: `inbox/jay/20261104-ex41-restart/` 의 OVERNIGHT-CONTRACT · EX41R-INCIDENTS(사고 24 건) · EX41-RELAUNCH-GATE · EX41-250-LOG 규칙. 도구는 `D:/mai-wt/foothold-lab/lead-dispatch-measure/_out/tools/` (가지 lead/ex41-dispatch-on-measure). 파이썬은 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`(아래 PY).

## 1. Launch (띄우기) · 순서를 바꾸지 않는다

1. 출발 HEAD 가 push 됐는지(`git rev-parse HEAD origin/<branch>` 같음).
2. 깨끗한 새 사본: `GIT_LFS_SKIP_SMUDGE=1 git worktree add D:/mai-wt/foothold-lab/<ex>-launch-<sha> <sha>` · `git status --porcelain --untracked-files=no` 0 줄.
3. 정의 안 된 이름 0: `PY -m pyflakes foothold_s2/scripts foothold_s2/runners foothold_s2/curriculum foothold_s2/ex41_*.py foothold_s2/sensors | grep "undefined name"` 가 비어야 함(I17).
4. 승인 · 경계 파일이 승인 기준과 같은지 `git diff <승인 기준> HEAD -- foothold_s2/curriculum/*approvals.yaml *boundary.yaml`(예행 값이 섞이면 거절 · I20).
5. GPU0 비었는지 · `D:/mai-tmp/gpu/TRAINING_BUSY_GPU0` 없는지 · 예행 감시기 · 예행 대기열 항목이 없는지(`ops_check` I05 · I06).
6. 사본 잠금: `python _out/tools/ex41/lock_checkout.py lock <사본>` → `check` 가 `0 writable`.
7. 출발: `powershell -NoProfile -ExecutionPolicy Bypass -File _out/tools/ex41/launch_ex41r.ps1 -Checkout <사본>` 을 `Start-Process -WindowStyle Hidden` 으로. 이 스크립트가 학습과 밀기 감시기(push250)를 함께 띄운다(I04).
8. 2 분 안에: `train_start_status.json` state running · `ex41_start_readback.json` status verified · 부모 SHA · DR · 점수 감시 프로세스.
9. `ops_check`(아래 2) 전 항목 OK 를 본 뒤 텔레그램 「띄움」(`tg_send.py`).

## 2. Doctor (매 점검 · cron 7 · 27 · 47 분)

`PY _out/tools/ex41/ops_check.py <run_root>` — FAIL 은 그 회차 안에 고치고, WARN 은 처리하거나 까닭을 decisions.tsv 에. 점검 항목과 사고 번호는 스크립트 머리말. dispatcher 코드를 고쳤으면 루프 재시작(I08).

## 3. Drive · 250 경계마다

1. 학습 자동 숫자 보고(원문)는 텔레그램용이 아니다. lead 해석이 텔레그램으로 간다.
2. 점수 파일 `eval/scores/score_<N>_*.json` 이 생기면 `PY _out/tools/ex41/boundary_report.py <run_root> <N>`(rc 2 = 측정 공백 · 결과로 안 씀).
3. 열두 줄을 다 채운다(EX41-250-LOG 규칙 · 계약 3 절): 생존 · 추종 · 후진 · 옆 · 회전 · 계단 대칭 · 발 끌림 · 밀림(500 부터 `eval/push250/<6000+N>.json`) · 서기 · 학습 곡선 · 경계 적용(`ex41_application.jsonl` 의 N+1 행 · reason) · 측정 공백 · 학습률 · KL.
4. 판정: 판정선 0.15 · 평가 잡음 폭(M11 최대 0.0084) 안의 넘침은 「지켜봄」 · 한 경계 미달은 기록 후 다음 경계 재측정 · 두 번 연속이면 원인 가설과 손잡이 후보를 붙여 팀장 보고(D179) · 학습은 멈추지 않는다.
5. 경계 판단에 쓰이는 점수: 경계 n+1 은 m(n-250) 점수. 늦으면 `dr_hold_missing_evidence`(멈춤 한도 소비) — 점수가 다음 경계 전에 오는지 시각으로 셈.
6. 기록: `EX41R-250-LOG.md` 절 · decisions.tsv 한 줄 · #555 댓글 · 텔레그램 `PY _out/tools/ex41/tg_send.py <msg.txt>`(첫 줄 `[EX-` · 15 줄 이하 · `#555` 는 자동 URL).

## 4. Drive · 단계 끝마다

1. 단계 넘김 행(`stage_before → stage_after`)과 새 단계 DR · 명령 몫 · 지형을 읽고 텔레그램 「단계 넘김」.
2. 단계 끝 점수 직후 대기열 `D:/mai-tmp/gpu/queue.json` 에 P2(axis_v2 · w78_v2 · push_ladder) · P3(a_push_video · W57 39 · W80 12)가 올라왔는지 센다.
3. P2 단위가 45 분을 넘으며 P1 을 막으면 `ops_check` I24 · EX-42 부터는 w78 이 30 단위로 쪼개져 있어야 한다.
4. 영상은 「끝」 = 재생 목록 경로 + 전 프레임 검사 + lead 가 목록 항목 파일 존재를 직접 셈(I14) + 첫 편 장면을 lead 가 직접 봄.

## 5. Evidence

증거는 경로 · 커밋 · 줄 번호로만. 작업자 보고는 lead 가 파일로 다시 재기 전엔 사실로 옮기지 않는다. 결정마다 `decisions.tsv`(ts · phase · decision · why · evidence · result), 새 사고는 `EX41R-INCIDENTS.md` 에 막는 장치와 함께(다짐은 장치가 아니다).

## 6. Cleanup · 끝날 때

학습 rc · 마지막 저장본 SHA · 6000(또는 계획) 도달 · 밀기 감시기와 점수 감시기 종료 확인 · 사본 잠금 풀기는 다음 판이 쓸 때만 · 분석 보고서 git push · URL · 그림. lead 가 띄운 프로세스만 끈다(남의 것 · 원격 데스크톱 등은 팀장 승인).
