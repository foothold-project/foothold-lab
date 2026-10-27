# 실행 카드 W12 · W13 · 원장 훅 · 범위 규칙 글 훅 · ponytail 한 쌍 시험

> 분류: 운영 의뢰 (mai-os)
> 작성: lead · 2026-10-28 02:2x (팀장 01:4x 「4번 · 5번도 진행」 · ponytail 은 한 쌍만 먼저, 우리 코드 과제로)
> 근거: mai-os `os/external-tools-ab/qa-20261027-2240.md` 5 · 6 · 7 절(super2 제안) · `WORKLIST.md` 규칙 4
> 요지: 팀장 원문이 기계로 쌓이게 하고, 범위 규칙 글이 세션마다 자동으로 들어가게 한다. ponytail 은 답을 아는 우리 코드 과제 하나로 켬 · 끔을 비교해 토큰 · 결과를 잰다
> 상태: 의뢰 · 원문은 mai-os(PRIVATE)에만 · foothold-lab(PUBLIC)에는 자리만

## W12 원장 · 규칙 글

- [x] R12-1 `UserPromptSubmit` 훅이 원문 · 시각 · 세션 이름 · 세션 ID 를 `~/.mai/ledger-spool/` 에 붙임(LLM 없음). 다른 세션이 보낸 글은 표시를 다르게
- [x] R12-2 (mai-ledger 첫 자동 실행 04:20:07 커밋 4f971f2) `wt/mai-os/ledger` worktree 에서 10 분마다 `ledger/` 만 커밋 · push, 키 모양 문자열 가림(가린 건수만 로그)
- [x] R12-3 10/26 이전 대화 기록(jsonl)에서 같은 모양으로 한 번 뽑아 넣음 (lead 의 W02 원장 초안이 이것을 입력으로 씀)
- [x] R12-4 하루 끝에 「foothold-lab `inbox/jay/20261028-plan/WORKLIST.md` 의 어느 W · R 에도 안 붙은 팀장 원문 줄」 목록을 뽑는 스크립트
- [x] R12-5 `os/rules/scope-discipline.md` + `SessionStart`(startup · resume · compact) · `SubagentStart` 훅 주입 + 주입 로그 + 하루 한 번 빠진 세션 알림
- [x] R12-6 답을 아는 확인: 새 세션 · compact 뒤 「범위 규칙 첫 줄을 그대로 옮겨라」 로 확인
- [x] R12-7 팀장이 승인해야 할 것(전역 설정 변경 · 예약 작업 등록)은 하기 전에 lead 창에 한 줄로 묻는다

## W13 ponytail 한 쌍 시험

- 과제(답을 아는 것): 계기판 v7 → v8 변경을 명세만 보고 구현. 정답 구현은 lead 의 `compose_25e_v2style8.py`, 시험 입력은 촬영본 세 개(걸으며 돌기 · 넘어진 듬성 판 · B1500). 명세는 `WORKLIST.md` R01-1 ~ R01-6.
- [x] R13-1 격리된 별도 clone 에 ponytail 설치(전역 `~/.claude` 무변경), 켬 판 · 끔 판을 같은 명세 · 같은 모델로
- [x] R13-2 잰 것: 토큰(입력 · 출력) · 바뀐 줄 수 · 고친 횟수 · 시험 통과(세 촬영본 렌더 · 프레임 수 · 에피소드 전환 · 화살표 안쪽) · 명세 밖 변경 수
- [x] R13-3 `limits_now.py` 를 시작 전 · 끝난 뒤 읽어 원문 그대로 적음
- [x] R13-4 결과와 「바로 도입 · 보류」 권고를 mai-os 문서로, lead 에 한 줄 보고

## 결과 (super2 보고 · lead 미재측)

- W13 끝 03:28 · mai-os `os/external-tools-ab/w13-ponytail-pair.md` (5182fa6) · 켬 대 끔: 줄 74 → 71 · 고친 횟수 2 → 1 · 턴 14 → 9 · 비용 약 $0.41 → $0.43 · 둘 다 시험 통과 · 권고 보류(한 쌍 차이 작음, 범위 규칙 글은 scope-discipline 으로 이미 들어감)
- W12: R12-2 · R12-3 push 끝(d0d7b5c, 팀장 super2 창 직접 허락) · R12-4 unlinked.md · R12-1 · R12-5 코드 끝(29d1f2e · 8484131), 전역 훅 셋 · 예약 작업은 팀장 답 대기(R12-7) · R12-6 은 훅 건 뒤
- W12 끝 04:21 (super2 보고 · lead 확인: settings.json 에 tools/ledger 훅 4 · schtasks mai-ledger 준비 · 백업 claude-settings-20261028-041004.json). 문서 mai-os os/ledger.md · os/session-messaging.md v2.2 (0040c1b)
