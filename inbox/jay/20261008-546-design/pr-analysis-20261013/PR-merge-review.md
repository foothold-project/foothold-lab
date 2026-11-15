# PR #542 · #543 · #544 병합 검사 (규칙 · 관문 · 비밀값)

> 분류: 운영 (PR 병합 전 규칙 검사)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 17:55
> 근거: PR 원문 · 변경 파일 (커밋 28a4bef7 · ebdd4c63 · 0da5cecf, 10/13 `git ls-remote` 로 PR 머리 확인) · AGENTS.md 2 · 3 · 5 · 7 · 8절 · `.github/workflows/` 중 PR 과 main push 에 도는 것 · main 판 `.github/scripts/authorcheck.py` · `review_inbox.py` · `web/_build/stalecheck.py` 를 PR 파일에 직접 돌린 결과 · 저장소 병합 설정 (`gh api`)
> 요지: 셋 다 `inbox/<자기 폴더>/` 에만 쓰고 docs/ 를 안 건드리며, em dash 0 · 비밀값 0 · 100 MB 넘는 파일 0 · main 과 경로 충돌 0 이다. 규칙상 병합을 막는 것은 없다. #542 · #544 는 병합해도 된다. #543 은 팀장이 요청한 수정본이 안 왔고 내용이 사이트 현재 판과 어긋나 병합 시점을 팀장이 정해야 한다. 봇의 「em dash N개」 경고는 가운뎃점을 센 오검출이다
> 상태: 초안 (lead 검토 전) · 병합 · 댓글 하지 않았음

---

## 1. 무엇을 어떻게 검사했나

- PR 머리 커밋 셋은 로컬 저장소에 있어 `git show <커밋>:<경로>` 로 읽었다. 작업 트리 · 가지는 건드리지 않았다.
- 규칙 스크립트는 main 판을 썼다. 로컬 `origin/main` 은 fe2cfe9d 이고 원격 main 은 3a3c4369 로 두 커밋 앞서지만, 그 둘이 바꾼 파일은 `.cache/runpod-balance-state` · `docs/LEDGER.md` 뿐이라 검사 결과와 상관없다 (`gh api compare` 확인). PR 들의 갈래점 9dc69674 와 main 사이에 `.github/scripts/` · `docs/ROLES.md` 변경은 없다.
- 스크립트는 작업 폴더 밖 임시 사본 (`git archive` 로 풀어 놓은 PR 파일 + main 판 스크립트) 에서 `python -I -B` 로 돌렸다. 저장소에 파일 · `.pyc` 를 쓰지 않았다.
- 문자 검사는 U+2014 (em dash) · U+2013 (en dash) · U+2212 (빼기) · U+00B7 (가운뎃점) · 이모지를 따로 셌다.
- 비밀값 그물: 키 · 토큰 꼴 (`AKIA…` · `ghp_…` · `sk-…` · `hf_…` · 개인 키 머리) · `password|token|secret|api_key = 값` · 64자 hex · IP · 이메일 · 절대 경로 · 계정 이름 낱말. 이 그물에 안 걸리는 꼴은 못 잡는다 (전수 아님).

## 2. 한 표

| 항목 | #542 (이민우) | #543 (맹라현) | #544 (오현민) |
|---|---|---|---|
| 작성자 아이디 (WORKFLOW.md 88~91행 표) | lmw0207 | maengu86 | less82 |
| 쓴 곳 | `inbox/lee/` 3개 | `inbox/meang/` 1개 | `inbox/oh/` 22개 |
| 자기 폴더에만 썼나 (AGENTS 2절) | 예 | 예 | 예 |
| docs/ · 루트 · `.github/` | 안 건드림 | 안 건드림 | 안 건드림 |
| 줄 수 | +295 / -0 | +72 / -0 | +5,329 / -0 |
| 가장 큰 파일 | 89,816 B (PNG) | 5,882 B | 44,546 B (본문 md) |
| 100 MB 넘는 파일 (AGENTS 7절) | 0 | 0 | 0 |
| em dash U+2014 · 파일 | 0 | 0 | 0 (22개 전부) |
| en dash U+2013 · 파일 | 19 | 0 | 19 (FROZEN-CONFIG 2 · RESULT-goal1s 6 · RESULT-goal1u 3 · AUDIT-resume 8) |
| 이모지 | 🔴 9 · ★ 2 · ✕ 1 | 0 | 0 |
| em dash · PR 제목과 본문 | 0 | 0 | 0 |
| em dash · 커밋 메시지 | 0 | 0 | 0 (커밋 둘) |
| 봇 「em dash」 경고 | 233개 = 가운뎃점 233개 | 35개 = 35개 | 본문 426개 = 426개 · 첨부도 파일마다 같은 수 |
| authorcheck (main 판) | 통과 · 작성자 표기 4 · 위반 0 | 통과 · 18 · 0 | 통과 · 14 · 0 |
| review_inbox (main 판) | ok true · fixes 0 | ok false · 「`확인됨`/`추측`/`미측정` 표기 부여」 (막지 않음) | 본문 · README ok true · 첨부 md 8개 ok false (머리 5줄 없음 · 막지 않음) |
| stalecheck 폐기 어휘 23종 | 0 | 0 | 0 |
| 비밀값 | 0 | 0 | 0 |
| 비밀은 아니지만 드러난 것 | RunPod 작업 영역 이름 `/data/leeminwoo` (56 · 291행) | 없음 | 로컬 시험 주소 127.0.0.1 · 0.0.0.0 · 프로세스 번호 일부 (`adapter_pid` · `pgid`) |
| main 과 경로 충돌 | 0 | 0 | 0 |
| GitHub mergeable | UNKNOWN (GitHub 이 계산 안 함) | MERGEABLE · CLEAN | MERGEABLE · CLEAN |
| 가지 이름 (AGENTS 3절 `feature/작업명-이름`) | 맞음 `feature/wip-report-lee` | 맞음 `feature/20261007-wip-meang` | 다름 `inbox-oh-20261007-wip` (막지 않음) |
| PR 본문 꼬리말 「Generated with Claude Code」 | 있음 | 없음 | 있음 |
| 리뷰 · 승인 | 없음 | 팀장 코멘트 (보완 요청 10/8) | 없음 |
| 10/8 뒤 새 커밋 | 0 | 0 | 0 |

## 3. 빌드 관문에 걸릴 것

- PR 에 도는 워크플로는 셋이다: `authorcheck.yml` (md 가 바뀌면) · `inbox-pr-alert.yml` · `pr-notify.yml`. `sim-tests.yml` 은 `sim/**` 만 보므로 안 돈다.
- 사이트 빌드는 inbox 를 웹 페이지로 굽지 않는다 (`web/_build/docgraph.py` 54행 `SKIP_DIRS` 에 `inbox`). em dash 관문 `dashcheck.py` 는 구운 사이트만 보고, 22행 `BAD = '\u2014'` 하나만 막는다. 같은 파일 머리글이 「en dash 와 하이픈(-) 은 막지 않는다」 고 적는다 (원문 괄호 안의 en dash 글자는 이 문서 규칙 때문에 옮기지 않았다).
- inbox md 를 읽는 빌드 단계는 둘이다. `stalecheck.py` (184행부터 `docs` · `inbox` · `deliverables` 를 훑어 폐기 어휘가 있으면 실패) 와 `terrain5.py` (지형 이슈 #65~#69 를 언급하는 문서만 모음). PR 셋의 md 12개를 `stalecheck._hits` 에 직접 넣어 0 건을 확인했다 (자기시험 `_kat` 통과 뒤). PR 셋은 #65~#69 를 언급하지 않는다.
- 그래서 지금 병합해도 빌드는 안 깨질 것으로 본다. 위 단계는 `확인됨` 이고, 전체 빌드는 돌리지 않았다 `미확인`.
- 승격 (inbox → docs) 할 때 걸릴 것 (지금은 아님): 첨부 md 8개는 머리 5줄이 없다 (`metacheck`). 이모지를 막는 관문은 `web/_build` 에서 찾지 못했다 (grep 기준). 민우 12차 그림 제목 속 em dash 는 그림 속 글자라 어떤 문자 관문도 못 본다.

## 4. 병합하면 생기는 일

- `inbox-alert.yml` (main push · `inbox/**`): 바뀐 md (README.md 제외) 가 있으면 「[승격 검토] 첫 파일 이름」 이슈를 팀장에게 1건 배정하고 디스코드로 알린다. 같은 제목 이슈가 열려 있으면 새로 안 만들고 댓글만 단다. 병합에 외부 발송이 따라간다.
- 저장소 병합 설정 (`gh api repos/foothold-project/foothold-lab` 실측): squash 병합 메시지 = `COMMIT_MESSAGES`, 일반 병합 메시지 = `PR_TITLE`. 그래서 PR 본문의 「Generated with Claude Code」 꼬리말은 어느 방식으로도 main 기록에 들어가지 않는다. 커밋 메시지에는 `Co-Authored-By` 줄만 있다 (#542 · #544).
- #520 은 PR 들이 `Closes` 를 일부러 안 써서 자동으로 닫히지 않는다 (PR 본문에 까닭을 적음).
- `delete_branch_on_merge: false` 라 병합 뒤 가지는 남는다.

## 5. PR 별 판단

### PR #542 (이민우) · 병합 가능

- 규칙상 막는 것 없음. en dash 19 · 이모지는 inbox 에서 허용된다 (AGENTS 8절 「«손질 필요»가 나와도 제출은 됩니다」).
- 권고: 병합해도 된다. 까닭: #520 양식 9칸 · 자기 폴더 · 작성자 명부 일치 · 그림 상대경로 둘이 같은 폴더에 있음 · 내용이 10/7 기록물로 완결.
- 병합과 별개로 답할 것: PR 본문이 「원자료 · 영상 · 로그를 어떤 형태로 올려 둘지 정해 주시면 맞추겠다」 고 물었다 (본문 29행). §7 ③ (`initial_transform_timeout`) · ④ (지평과 창 2×2) 도 팀장 판단을 요청했다.

### PR #543 (맹라현) · 병합 시점은 팀장 판단

- 규칙상 막는 것 없음 (증거 표기 없음은 막지 않음).
- 걸리는 것 둘:
  1. 팀장이 10/8 코멘트로 「아래 내용을 9항에 추가해서 이 PR에 다시 올려 주세요」 (원본 자료 6항) 를 요청했고, 그 뒤 커밋이 없다. #545 의 시작 조건이 이 수정본이다.
  2. 보고서 내용 (하늘 · 색 · 질감 진행 중 · v1 하늘 화면 링크) 이 사이트 10/12~13 판 (SuperSplat 수정본이 기준 · 하늘 실험은 보관) 과 어긋난다 (ANALYSIS-members 2-5).
- 선택지: (가) 보류하고 수정본을 기다림 · 요청이 살아 있다는 신호가 분명함. (나) 지금 10/8 기록물로 병합하고, 원본 자료 위치 · 현재 판 요약은 새 PR 로 받음 · 기록은 남고 요청은 #545 로 이어 감.
- 기우는 쪽: 규칙상으로는 없다. (나) 를 고르면 「요청이 처리됐다」 로 읽히지 않게 PR 이나 #545 에 한 줄 남기는 것이 좋다 (`추정`).

### PR #544 (오현민) · 병합 가능

- 규칙상 막는 것 없음. 파일 22개 · 5,329줄로 가장 크지만 가장 큰 파일이 44,546 B 다. 첨부는 보고서가 인용하는 판정 요약 사본이다.
- 참고: README 와 커밋 메시지는 「경로·프로세스 번호·계정명·전체 해시를 가림」 이라 했는데, `go2mock-174129/result.json` 의 `adapter_pid` 와 `fault-suite-r3/fault.jsonl` 의 `pgid` · `GZ_PARTITION` 숫자가 남아 있다. 비밀값은 아니다 (프로세스 번호는 그 실행이 끝나면 의미가 없는 값).
- 권고: 병합해도 된다. 까닭: 요건 충족 · 첨부가 보고서의 근거 칸에 링크돼 있다.
- 읽을 때 주의: 10/12~13 에 앱이 공개 저장소 foothold-app 으로 옮겨 가는 중이라, 이 PR 은 「10/8 시점 기록」 이다 (ANALYSIS-members 3-4).

## 6. 덧붙여 찾은 것 (PR 밖 · 저장소 도구 · 손대지 않음)

1. **봇의 em dash 경고가 가운뎃점을 센다.** `.github/scripts/review_inbox.py` 88행과 187행이 `emdash = md.count('·')` 다. 그래서 규칙대로 가운뎃점을 쓴 제출에 「em dash 233개」 같은 경고가 달린다. 세 PR 의 봇 숫자가 각 파일의 가운뎃점 수와 정확히 같다 (위 2절). 규칙 (em dash 대신 가운뎃점) 과 반대로 안내하는 셈이다. 실제 em dash 를 찾으려면 `'\u2014'` 로 세야 한다 (`dashcheck.py` 22행처럼). 고치는 일은 이 작업 범위 밖이다.
2. **정본에 옛 관문 날짜가 남았다.** `docs/FLOW.md` 266~267행 · 399행이 「NAV 11/7 · FINAL 12/11」 이다. 10/12 일정 반영 커밋 fe2cfe9d 가 이 파일을 안 고쳤다.

## 7. 못 한 것

- 전체 사이트 빌드 (`web/_build/build.py`) 는 돌리지 않았다.
- #542 의 mergeable 은 GitHub 이 계산하지 않았다 (UNKNOWN). main 에 같은 경로가 없고 갈래점 뒤 main 이 `inbox/lee/` 를 안 바꿨으므로 충돌은 없을 것으로 본다 (`추정`).
- PNG 두 장 안의 글자는 눈으로만 봤다 (전수 검사 아님).
- 비밀값 그물은 정규식 꼴 기준이다. 그물 밖 꼴은 못 잡는다.
