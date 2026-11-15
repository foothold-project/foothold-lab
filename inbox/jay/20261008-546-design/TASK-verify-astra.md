# ASTRA-MVP 검증 의뢰: #546 논의 순서가 Track A · Bridge · Track B 를 한 시스템으로 닫는가

> 분류: 검증 의뢰
> 작성: 오흥재 · 2026-10-08
> 근거: 팀장 10/8 지시 (lead 세션 대화)
> 요지: lead 의 «논의 순서 제안» 대로 정하면 최종 Track A · Bridge(Digital Twin) · Track B 설계가 하나의 시스템으로 완료되는지, ASTRA-MVP 가 팀장과 앞서 정리한 방향 문서를 기준으로 검증한다
> 상태: 의뢰

## 팀장 물음 (원문)

「논의 순서에 따라서 진행하면 우리 최종 Track A - Bridge(Digital Twin) - Track B 까지 설계가 하나의 시스템으로 완료되는 것이 맞는가?」

## 읽을 것

**A. lead 가 만든 논의 자료** (검증 대상)

- `inbox/jay/20261008-546-design/discussion-546.html` · 논의 순서 일곱 칸과 B · C · A · D · E. 팀장이 보는 페이지와 같은 원본이다 (https://claude.ai/artifact/Wdanoqdaxf5StadmmtRsEr)
- `inbox/jay/20261008-546-design/BRIEF-abc.md` · 팀원 PR #542 · #543 · #544 사실층 (부록 R 에 원값)
- `inbox/jay/20261008-546-design/SURVEY-star-code.md` · 팀장 star 저장소 9개 코드 조사
- GitHub 이슈 #546 본문과 댓글 · 팀장 결정(10/8 21:06 댓글: 공개 무관 · 통합 문서는 B 결정 뒤 · AME-2 는 마지막 도입 · star 코드까지 보고 재설계 · 로컬 GPU 2장)

**B. ASTRA-MVP 가 팀장과 앞서 정리한 방향 문서** (기준)

목록은 네가 확정하라. lead 가 찾은 후보는 아래다. 빠진 문서가 있으면 넣고, 해당 없는 것은 빼라.

- `inbox/jay/20260929-mvp-presentation/SECTION-MAP.md` · 2.5 · 6.5 · 6.6절, 175~205행 (Track A · Digital Twin · Track B 의 역할과 병행)
- `inbox/jay/20260929-mvp-presentation/STORYBOARD.md` · 9장 · 28~34장
- `inbox/jay/20260929-mvp-presentation/USER-REQUIREMENTS-LOG.md`
- `docs/DECISIONS.md` 95행 · 8/19 두 트랙 합의
- 이슈 #512 · #513 · #514 · #515 · 팀장 10/6 이후 과제(보행 모델 · 앱과 전체 아키텍처 · 디지털 트윈 적용 · 덱 보강)

## 할 일

1. 기준 문서가 그린 **최종 시스템**을 구성 요소와 이음매로 펼친다. Track A 정책 · Digital Twin(Bridge) · Track B 항법 · 앱과 대시보드 · 실기 등. 항목마다 근거 파일:행.
2. lead 의 논의 순서 일곱 칸이 그 구성 요소와 이음매를 각각 다루는지 대조표로 만든다. 칸마다 「다룸 / 일부 / 안 다룸」과 근거.
3. 순서대로 다 정했을 때 설계가 한 시스템으로 닫히는지 판정한다: **닫힘 / 안 닫힘**. 안 닫히면 빠진 결정 · 빠진 칸 · 순서 문제를 구체적으로 적는다.
4. lead 자료의 사실 오류, 또는 기준 문서와 부딪히는 서술이 있으면 따로 적는다 (파일과 행).

## 규칙

- 읽기 전용이다. 기존 파일 수정 · 커밋 · push 를 하지 않는다. 이 체크아웃은 lead 와 같이 쓴다.
- 결과는 새 파일 하나: `inbox/jay/20261008-546-design/VERIFY-astra.md`. 머리 다섯 줄(분류 · 작성 · 근거 · 요지 · 상태)부터 쓴다.
- em dash 를 쓰지 않는다. 기술 용어는 원어(actor/critic 등), seed 는 「시드」.
- 근거 등급 `확인됨 / 추정 / 미확인` 을 구분한다. 안 연 것은 미확인이다.
- 권고는 판정과 근거를 적은 뒤에만 적는다. 계획은 팀장이 정한다.
- 끝나면 터미널에 파일 경로와 판정 한 줄을 남긴다.
