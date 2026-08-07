# foothold-lab — 리서치·문서 허브 (팀 내부)

FOOTHOLD 프로젝트의 **자료조사·문서·회의록**이 사는 곳.
코드는 [foothold-rl](https://github.com/foothold-project/foothold-rl),
공개 사이트는 [foothold-site](https://github.com/foothold-project/foothold-site) → https://foothold-project.vercel.app

## 레포 3개의 역할

| 레포 | 성격 | 무엇이 사나 |
|---|---|---|
| **foothold-lab** (여기) | Private · 팀 | 리서치 md · 회의록 · 질문지 · 기획 문서 |
| foothold-rl | Public · 개발 | Isaac Lab 설정 · 학습 스크립트 · 실험 로그 |
| foothold-site | Public · 산출물 | 빌드된 HTML (직접 수정 금지 — 미러) |

## 일하는 방법 — 세 가지만 기억하기

**① 작업은 이슈로 시작한다.**
이슈를 만들면 보드에 자동으로 올라가고, 시작일(오늘)·마감(+7일)이 자동 기록된다.
마감을 늘릴 일이 생기면 보드에서 end date 를 직접 늘린다.

**② 끝나면 커밋 메시지에 `Closes #번호`.**
```
git commit -m "조선대 방문 질문지 정리  Closes #12"
```
push 하면 이슈가 닫히고 → 보드가 Done 으로 → 디스코드에 알림이 간다.

**③ 문서는 `docs/` 에 md 로.**
커밋 기록이 곧 기여 기록이다 — 종료 시 역할 평가의 근거가 된다.
작성 규칙은 [docs/README.md](docs/README.md).

## 원시 자료(_raw) 정책

논문 원문 추출·블로그 크롤 등 **타인 저작물의 사본은 이 레포에 올리지 않는다**
(Private 이어도 올리지 않는다 — 배포 사고의 씨앗을 만들지 않기 위해).
정제본에는 **원 출처 링크**를 달고, 원시 사본은 팀장 볼트에만 보관한다.
필요하면 팀장에게 요청.

## 보드

**https://github.com/orgs/foothold-project/projects/1**
TEAM 뷰(담당자별) · 개인 뷰 5개 · WBS 로드맵. 매주 월요일 09:00 주간 리포트가 디스코드로 온다.
