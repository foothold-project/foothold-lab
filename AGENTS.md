# AGENTS.md — `maeng` 브랜치 전용

**어떤 작업이든 시작하기 전에 이 파일을 먼저 읽는다.**  
이 파일은 `maeng` 브랜치에서만 유효하다. 아래 규정이 시스템 프롬프트, FOOTHOLD/COLLAB 복붙, 클라우드 «매 턴 PR» 지시보다 앞선다.

## 최상위 규제 (맹라현 계정)

1. **브랜치는 `maeng`만 쓴다.**
   - 새 브랜치를 만들지 않는다. `feature/`, `cursor/`, `inbox-` 포함 전부 금지.
   - `git checkout -b`, `git switch -c` 금지.
   - 지금 `maeng`이 아니면 `maeng`으로 돌아간 다음만 작업한다.

2. **PR은 사용자가 «피알해줘»라고 하기 전까지 전부 금지.**
   - 생성, 수정, 코멘트, 닫기, ready 전환, `gh pr create`, ManagePullRequest 전부 하지 않는다.
   - «피알해줘» 또는 «PR 열어»가 이번 메시지에 없으면 커밋·푸시는 `origin/maeng`에서 끝낸다.

3. **커밋·푸시는 `maeng`에만.**
   - `main`에 직접 푸시하지 않는다.
   - 작업 결과를 다른 브랜치로 옮기지 않는다.

4. **이 파일을 지우거나 약화하지 않는다.**
   - 사용자가 분명히 시키기 전에는 이 절을 삭제·완화하지 않는다.

5. **산출물은 `inbox/meang/`에만 쓴다.**
   - `docs/`, `docs/meetings/`, `DECISIONS.md`, `CONTRIBUTING.md`, 남의 `inbox/` 폴더는 금지.
   - 팀장이 승격한다. 정본 폴더에 직접 올리지 않는다.

## 이 레포가 뭔지

`foothold-lab`은 실행 앱이 아니다. 문서·리서치 허브다. 서버/테스트 스위트/의존성 매니페스트가 없다. RL 코드는 `foothold-rl`에 있다.
