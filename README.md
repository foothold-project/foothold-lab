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

## 일하는 방법 — 네 단계

> 손으로 하는 건 **①의 빈칸 채우기**와 **③의 `Closes #번호`** 뿐이다. 나머지는 자동이다.

```
① 일을 시작할 때 — 레포에서 이슈를 만든다
     문서·조사 → foothold-lab      코드·실험 → foothold-rl
     템플릿을 고르고 빈칸을 채운다 (특히 "끝났다는 기준")
          │
          ▼  여기서부터 자동
     보드 등록 · 담당자=나 · 시작일=오늘 · 마감=+7일 · 디스코드 "새 작업"

② 일하는 동안 — 보드를 본다
     개인 뷰(내 이름 탭)에 내 것만 뜬다
     오래 걸릴 것 같으면 end date 를 직접 늘린다

③ 끝낼 때 — 커밋 메시지에 이슈 번호를 쓴다
     git commit -m "조선대 질문지 정리  Closes #12"
          │
          ▼  push 하면 자동
     이슈 닫힘 → 보드 Done → 디스코드 "완료"

④ 월요일 아침 — 지난주 요약이 디스코드로 온다 (자동)
```

**새 이슈 만들기** —
[lab (문서·조사)](https://github.com/foothold-project/foothold-lab/issues/new/choose) ·
[rl (코드·실험)](https://github.com/foothold-project/foothold-rl/issues/new/choose) ·
[보드 보기](https://github.com/orgs/foothold-project/projects/1)

### 구조 — 이슈는 레포에 살고, 보드는 그것을 모아 보여준다

```
   [ 레포 = 서랍 ]                    [ 보드 = 상황판 ]
  foothold-lab   ─┐
  foothold-rl    ─┼─ 이슈를 만들면 ─▶  org > Projects > FOOTHOLD
  foothold-site  ─┘                    한 곳에 모여 보인다
```

> ⚠️ **이슈는 레포에서 만든다.** 보드에서 `+ Add item` 에 바로 타이핑하면
> **초안(draft)** 이 되는데, 레포에 존재하지 않아서 자동화가 하나도 안 돈다
> (담당자·날짜·알림·`Closes #번호` 전부 불가).
> 이미 만든 초안은 `⋯ → Convert to issue` 로 진짜 이슈로 바꿀 수 있다.
> 보드 상단의 **"Create new issue"** 버튼은 진짜 이슈를 만드니 그건 괜찮다.

### 왜 이렇게 하나

바빠서 현황판을 안 채우게 되는 걸 막으려는 것이기도 하지만, 더 큰 이유가 있다.
**이 기록이 프로젝트가 끝난 뒤 우리가 무엇을 했는지 증명하는 유일한 자료**가 된다 —
누가 무엇을 얼마나 했는지, 어떤 판단을 언제 왜 내렸는지가 남는다.
그때 가서 기억으로 복원할 수는 없다.

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
