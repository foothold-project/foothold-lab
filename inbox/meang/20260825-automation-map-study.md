작성 2026-08-25
요지: 자동화 지도 페이지를 lab 워크플로 16개와 대조해, 제출부터 게시까지 무엇이 자동이고 무엇이 사람인지 정리한다.

# 자동화 지도 공부: 페이지 주장과 lab 워크플로 대조

페이지: [자동화 지도](https://foothold-project.vercel.app/automation.html) (`확인됨`, HTTP 200, `/automation` 도 같은 본문).
규칙 원문: [협업 규칙 5절](https://foothold-project.vercel.app/collab.html) (`확인됨`, HTTP 200).
보드: [FOOTHOLD 프로젝트 보드](https://github.com/orgs/foothold-project/projects/1) (`확인됨`, HTTP 200).

이 문서는 페이지를 외운 것이 아니다. `origin/main`의 `.github/workflows/` 16개와 `.github/scripts/review_inbox.py`를 읽고, `gh workflow list` · `gh run list` · 라벨 API · 스크립트 실행으로 맞춰 본 기록이다.

## 1. 팀원이 하는 일

페이지 마지막 표와 YAML이 같다 `확인됨`.

| 하고 싶은 것 | 하면 되는 것 |
|---|---|
| 무엇을 할지 알린다 | 이슈 템플릿 «작업» |
| 모르는 것이 있다 | 이슈 템플릿 «리서치» |
| 막혔다 | 이슈 템플릿 «막힘 · 오류» |
| 결과물을 낸다 | `inbox/본인폴더/`에 넣고 브랜치 → PR |
| 누가 뭘 하나 본다 | 보드. 이슈를 열면 `issue-dates.yml`이 올린다 |

main에 직접 push하지 않는다. 무료 플랜 비공개 저장소는 브랜치 보호를 못 건다. `main-guard.yml` 주석에 `POST /rulesets` → 403 실측이 적혀 있다 `확인됨`(파일 주석). 그래서 막지 않고, 팀장·봇이 아닌 사람이 main에 밀면 디스코드로 보이게 한다.

## 2. 제출부터 게시: 일곱 칸

페이지 ①~⑦을 워크플로 파일에 대응한다. 화살표 그림은 그리지 않는다.

| 칸 | 누가 | 실제 파일 | 언제 도나 |
|---|---|---|---|
| ① 브랜치에 커밋하고 PR | 사람 | 없음 | 팀원이 연다. 초안(draft)이면 아래 알림이 안 온다 |
| ② 즉시 알림 | 자동 | `inbox-pr-alert.yml`, `pr-notify.yml` | PR `opened` · `reopened` · `ready_for_review`. inbox 파일 있으면 전자가 디스코드+텔레그램. inbox가 아니면 후자가 텔레그램 |
| ③ 자동 검토 | 자동 | `review_inbox.py` (PR 알림 안에서 실행) | 연구 문서 · 자기소개 · 개인사이트(자산)를 가른다. 결과를 팀장 텔레그램으로 |
| ④ 머지 | 사람 | `merge-on-comment.yml` | GitHub에서 머지하거나, 팀장(`vfxpedia`)만 PR에 `/머지`. 스쿼시 + 브랜치 삭제 |
| ⑤ 머지 직후 | 자동 | `inbox-alert.yml`, `merge-notify.yml` | inbox가 main에 들어오면 `[승격 검토]` 이슈. 팀 디스코드·텔레그램에 «무엇이 반영됐는지» |
| ⑥ 승격 판단 | 사람 | `promote.yml` | 팀장이 승격 검토 이슈에 `/승격`. 보류·반려는 이슈를 닫거나 코멘트 |
| ⑦ 웹 게시 | 반자동 | lab Actions 아님 | `/승격`이 `docs/research/`로 복사하면, 다음 사이트 빌드가 HTML을 만든다. 빌드 자체는 이 저장소 워크플로가 아니다 `확인됨`(SESSION-HANDOFF: 로컬 볼트 빌드) |

2026-08-24 이전에는 ②③이 머지 뒤에만 울렸다고 페이지가 말한다. YAML 주석도 같다. 구멍 사례로 임석헌 PR #40 (제출 13:59, 알림은 머지 직후 15:00)을 적었다 `확인됨`(주석). 검증용 PR #42 (`test/inbox-pr-alert-verify`, 2026-08-24, CLOSED)가 그 수정의 흔적이다 `확인됨`(`gh pr list`).

핵심: 승격 검토 이슈는 PR 시점에는 만들지 않는다. `inbox-pr-alert.yml` 주석 그대로다. 큐가 두 번 생기면 안 되어서, 머지 후 `inbox-alert.yml`만 만든다 `확인됨`.

## 3. 자동 검토가 보는 것

`origin/main`의 `review_inbox.py`를 읽었다 `확인됨`. 종류를 먼저 가른다.

| 종류 | 판정 기준 | 제안 경로 |
|---|---|---|
| 연구 문서 (기본 md) | h1 · 증거 표기 · 원 출처 링크 · em dash/글자 도식 없음 | `docs/research/<slug>.md` |
| 자기소개 | 개인정보 없음 · em dash 없음. 증거·출처는 요구하지 않음 | `02_team/profiles/<slug>.md` |
| 자산 (html·이미지 등) | 텍스트면 개인정보만. 이진 파일에서 죽지 않게 try/except | 팀장이 배치 |

자기소개로 치는 이름: 파일명이 `lead` · `lim` · `meang` · `lee` · `oh` 이거나, 경로에 `profile` · `intro` · `소개` · `프로필`이 들어 있을 때.

개인정보 정규식은 휴대전화 · 유선전화 · 주민등록번호 · 상세 주소다. 값은 이 문서에 적지 않는다.

페이지가 말한 «종류를 가려 기준을 다르게»는 이 스크립트다 `확인됨`. 보완 커밋을 같은 PR에 자동으로 올리는 2단계는 YAML에 없다. 페이지 10절 그대로, 판정까지는 기계이고 문장 보완은 팀장 세션이다 `확인됨`(페이지 + 워크플로에 보완 job 없음).

## 4. 이슈로 일을 나눈다

템플릿 세 개: `01-task.yml`(라벨 `task`) · `02-research.yml`(라벨 `research`) · `03-bug.yml`.
지금 라벨 `research`가 있다 `확인됨`(`gh api .../labels/research`). 페이지의 «2026-08-25에 고쳤다»는 이력은 내가 실패 로그를 다시 보지는 못했다 `미측정`.

이슈가 열리면 같이 도는 것:

| 무엇 | 파일 | 트리거 |
|---|---|---|
| 보드 등록 · 담당자=만든 사람 · start=오늘 · end=+7일 | `issue-dates.yml` | issues opened/reopened |
| 갈래 부모 밑에 매달기 | `subissue-link.yml` | issues opened/edited. 본문 드롭다운의 갈래 |
| 디스코드 (열림·닫힘) | `discord-notify.yml` | issues opened/closed, 그리고 main push |
| 실적 종료일 | `done-date.yml` | issues closed |
| 마감 지난 것만 호출 | `deadline-alert.yml` | 평일 09:00 KST. 없으면 침묵 |
| 주간 리포트 | `weekly-report.yml` | 월요일 09:00 KST |

`Closes #번호`가 커밋이나 PR 본문에 있어야 이슈가 닫히고, 그 닫힘이 보드·실적일·디스코드를 건다. `discord-notify.yml` 주석 그대로다 `확인됨`.

## 5. 스케줄 · 그 밖에 저절로 도는 것

cron은 YAML 숫자와 KST 환산을 내가 맞춰 봤다 `확인됨`.

| 무엇 | cron (UTC) | KST | 파일 |
|---|---|---|---|
| 마감 알림 | `0 0 * * 1-5` | 평일 09:00 | `deadline-alert.yml` |
| 주간 리포트 | `0 0 * * 1` | 월요일 09:00 | `weekly-report.yml` |
| 조선대 강의 자료 감시 | `0 1,7 * * *` | 매일 10:00 · 16:00 | `lecture-watch.yml` |
| 공지 발송 | 없음 | 팀장이 Actions에서 실행 | `notice.yml` (보내기 전 em dash 관문) |
| main 직접 push 감시 | push to main | 그때 | `main-guard.yml` (vfxpedia·봇은 건너뜀) |

강의 감시 대상 저장소 `slihump/ros2_lecture`는 공개 저장소로 존재한다 `확인됨`. 알림까지만 자동이다. 자료실 암호는 팀장 PC에만 있다고 페이지·YAML 주석이 같다. 강의 파일 목록은 이 문서에 옮기지 않는다 (저작물).

페이지 03절 «주간 다이제스트 · 일요일 21시»에 해당하는 cron은 lab YAML에 없다 `확인됨`(검색: digest/일요일/21시는 COLLAB 설명뿐). `docs/digest/`에 쌓인다고 COLLAB는 말한다. 그 시각에 누가 돌리는지는 이 저장소만으로는 모른다 `미측정`.

페이지 03절 «사이트 게시»도 lab Actions가 아니다. `/승격` 이후 로컬 빌드다 `확인됨`.

페이지에 없는 워크플로: `project-views.yml`(보드 뷰 정리). 16개 중 하나다 `확인됨`(`gh workflow list` 16행).

## 6. 아직 자동이 아닌 것

페이지 04절과 YAML이 맞다 `확인됨`.

| 무엇 | 왜 |
|---|---|
| 머지 | 내용 판단. `/머지`는 실행만 대신한다. 팀장 코멘트만 받는다 |
| 승격 | 같은 이유. `/승격`도 팀장만 (`promote.yml`의 `vfxpedia` 가드) |
| 자료실 업로드 | 암호가 팀장 PC에만 있다 |
| 회의록의 «결정이 뭐였나» | 전사는 별도. 이 레포 워크플로가 회의록을 쓰지 않는다 |
| 코드가 옳은지 | `review_inbox.py`는 형식만 본다 |

## 7. 브랜치 · 머지된 브랜치 삭제

| 저장소 | 규칙 (COLLAB + 페이지) |
|---|---|
| lab | 팀원 브랜치 → PR. 이름 `feature/작업명-이름`. 이슈 번호는 이름에 넣지 않는다 |
| rl | `feature/작업명-이름` → PR `dev` → 검증 후 `main` |
| site · brand | 직접 커밋하지 않는다 |

`/머지`는 `gh pr merge --squash --delete-branch`다 `확인됨`. GitHub UI 머지에서 브랜치가 지워지는지는 저장소 설정이라 이 토큰으로 못 봤다 `미측정`.

## 8. 내가 돌려서 나온 것

저장소 시크릿(디스코드·텔레그램)은 없어서 알림 전송 자체는 실행하지 못했다. 아래는 로컬·공개 API로 돌린 결과다.

`gh workflow list --repo foothold-project/foothold-lab` → 활성 워크플로 16개. 이름: 마감 알림, 디스코드 알림, 실적 종료일 기록, inbox 제출 감지, inbox 제출 감지 (PR), 이슈 등록 시 자동 처리, 조선대 강의 자료 감시, main 직접 push 감시, 머지 반영 알림, 코멘트로 머지, 공지 발송, PR 알림, 보드 뷰 정리, 승격, 갈래별 sub-issue 연결, 주간 리포트.

`gh run list` 최근 예 (2026-08-25 UTC):

| 결론 | 워크플로 | 메모 |
|---|---|---|
| success | 머지 반영 알림 · 디스코드 알림 | main push 때 실제로 돌았다 |
| skipped | main 직접 push 감시 | 팀장 push라 `if:`가 건너뜀. 가드가 살아 있다는 뜻 |
| skipped | 승격 · 코멘트로 머지 | 이슈/PR 코멘트가 `/승격`·`/머지`가 아니라서 조건 미충족 |
| success | 이슈 등록 시 자동 처리 · 갈래별 sub-issue 연결 | `[승격 검토] inbox/meang/20260818-...` 이슈가 열릴 때 |

`gh api repos/foothold-project/foothold-lab/labels/research` → `{"name":"research","description":"답을 모르는 질문 · 조사"}`.

`python3 .github/scripts/review_inbox.py inbox/meang/20260825-automation-map-study.md` 결과 (커밋 직전, 이 파일 자체):

| 항목 | 값 |
|---|---|
| kind | research |
| ok | true |
| h1 · 증거 · 링크 · 금지요소 | 모두 true |
| 증거 표기 개수 | 25 |
| 출처 링크 개수 | 3 |
| 제안 경로 | `docs/research/automation-map-study.md` |
| fixes | 없음 |

같은 실행에서 em dash 0 · 박스 문자 0 · 164줄. `확인됨`

## 9. 확인하지 못한 것

| 무엇 | 왜 |
|---|---|
| 이슈 목록 · 이슈 생성 | `gh issue list` GraphQL 403, REST issues 403. 이 환경 토큰은 이슈를 못 연다 |
| 브랜치 보호 설정 | protection API 403 |
| 디스코드·텔레그램이 실제로 도착하는지 | 시크릿 없음. 워크플로 성공만 봄 |
| 주간 다이제스트 일요일 21시 | lab cron 없음 |
| 리서치 템플릿이 예전에 실패했는지 | 라벨은 지금 있다. 실패 로그는 못 봄 |
| UI 머지 시 브랜치 자동 삭제 | `/머지` 경로만 YAML로 확인 |
| 사이트 빌드 시각 | 볼트 로컬. 이 레포 밖 |

이슈를 못 열어서 이 제출의 커밋/PR에 `Closes #번호`를 달 번호가 없다. 규칙상 있어야 하는 줄이다. 숨기지 않는다.
