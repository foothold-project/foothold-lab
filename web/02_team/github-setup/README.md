# foothold-project org 세팅 — 실행 절차

> 2026-08-06 작성. **사용자 클릭이 필요한 것과 파일로 준비된 것을 나눠 적었다.**
> 여기 워크플로 3종은 그대로 복사해 넣으면 도는 상태다.

---

## 0. 확인된 사실 (추측 아님)

| 사실 | 확인 방법 |
|---|---|
| **Vercel 무료 플랜도 GitHub org 레포를 배포한다** | [Vercel 공식 문서](https://vercel.com/docs/git/vercel-for-github) — 조건은 *"Owner 또는 repo 접근권 있는 Member"* 뿐. 요금제 언급 없음 |
| **Project 하나가 여러 레포를 담는다** | [GitHub 공식 문서](https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-items-in-your-project/adding-items-to-your-project) — *"add issues and pull requests from any organization"* |
| Default repository 는 **제한이 아니라 `#` 단축키 기본값** | 위와 같음 — 여러 레포 추가가 공식 지원되므로 제한일 수 없다 |
| 레포 Transfer 시 이슈·스타·히스토리·웹훅·시크릿 유지, 옛 URL 자동 리다이렉트 | [GitHub Transfer 문서](https://docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository) |

> ⚠️ 이전 세션에서 "org 레포는 Vercel 팀(유료) 필요"라고 적었던 것은 **커뮤니티 글 기반의 오답**이다.
> 공식 문서로 정정한다.

---

## 1. 레포 만들기 (사용자 · 약 5분)

https://github.com/orgs/foothold-project/repositories → **New repository**

| 레포 | 공개 | 용도 |
|---|---|---|
| `foothold-site` | Public | 배포용 정적 산출물 (지금 개인 레포에 있는 것) |
| `foothold-lab` | Private | 자료조사·리서치·`docs/`·실험 노트 |
| `foothold-rl` | Private | 실개발 (Isaac Lab 설정·학습 스크립트·배포) |

**site 옮기는 법 — Transfer 말고 그냥 밀어넣기.** 이 레포는 빌드 산출물 미러라 히스토리 보존 가치가 낮다.

```bash
cd 인공지능사관학교/foothold-site
git remote set-url origin https://github.com/foothold-project/foothold-site.git
git push -u origin main
```

그다음 **Vercel** → 프로젝트 → Settings → Git → Disconnect → 새 레포 연결.
(Vercel GitHub App 을 org 에 설치하라는 화면이 뜨면 승인하면 된다.)

> 로컬 작업 방식은 **안 바뀐다.** `doyak-final/05_deliverables` 에서 작업 → `build.py` 가
> `foothold-site` 폴더로 복사 → push. 바뀌는 건 그 폴더의 `origin` 주소 한 줄뿐이다.

---

## 2. 보드 세팅 (사용자 · 약 10분)

현재 보드: https://github.com/orgs/foothold-project/projects/1

### 2-1. 이름 바꾸기
`foothold-project-planning` → **`FOOTHOLD`** 를 권함.
보드는 레포 하나가 아니라 **프로젝트 전체**를 담으므로 레포 이름을 따라갈 이유가 없다.
Settings → Project name.

### 2-2. Default repository
Settings → Default repository → **`foothold-lab`**.
이건 *"보드에서 바로 새 이슈를 만들 때 어느 레포에 만들까"* 의 기본값일 뿐,
**다른 레포 이슈도 얼마든지 이 보드에 들어온다.** 각 레포에서 이슈 우측 `Projects` 로 붙이거나,
아래 워크플로가 자동으로 붙인다.

### 2-3. Iteration 필드 추가 (주간 리포트의 전제)
보드 → `+` (필드 추가) → **Iteration** → 이름 `Iteration`, 기간 **1 week**, 시작 월요일.

### 2-4. 마일스톤 마커
1. `foothold-lab` → Issues → Milestones → New milestone 3개
   - `9월 PoC · 프로토타입` (마감 2026-09-30)
   - `10월 MVP 구현` (마감 2026-10-31)
   - `11월 중간보고` (마감 2026-11-30)
2. WBS 로드맵 뷰 → 우측 **Markers** → **Milestones** 체크
   → 간트 위에 세로선으로 표시된다.

### 2-5. 내장 자동화 (Workflows 탭)
- **Item closed → Status: Done** 켜기
- **Auto-add to project** — 레포별로 켜면 새 이슈가 자동으로 보드에 올라온다

> **Track(A/B/C) 필드는 만들지 않는다.** 지난 제안을 철회한다 —
> 보스 지적대로 커리큘럼 구간은 *학습 계획*의 축이고 보드는 *실행*의 축이라,
> 필드를 만들어도 채우지 않게 된다. **안 채울 필드는 만들지 않는 게 낫다.**
> 필요해지면 그때 만든다.

---

## 3. 시크릿 등록 (사용자 · 약 5분)

org → Settings → Secrets and variables → Actions → **New organization secret**

| 이름 | 값 | 어디서 |
|---|---|---|
| `PROJECT_TOKEN` | classic PAT (scope: **project**, **repo**) | github.com/settings/tokens |
| `DISCORD_WEBHOOK` | 웹후크 URL | 디스코드 채널 → 설정 → 연동 → 웹후크 |

> ⚠️ `GITHUB_TOKEN`(자동 제공)으로는 **Projects v2 를 못 건드린다.** PAT 이 필요한 이유다.
> ⚠️ 웹후크 URL 은 비밀이다. 파일에 적지 말고 반드시 Secrets 로.

---

## 4. 워크플로 설치 (파일은 준비됨)

`workflows/` 의 3개를 각 레포 `.github/workflows/` 에 복사한다.

| 파일 | 하는 일 | 어디에 |
|---|---|---|
| `issue-dates.yml` | 이슈 열리면 보드에 추가 + **시작일=오늘 / 마감=+7일** 자동 기록 | 전 레포 |
| `discord-notify.yml` | 이슈 열림·닫힘, `docs/` 문서 push 를 디스코드로 | 전 레포 |
| `weekly-report.yml` | 월요일 09:00 지난주 보드를 요약해 디스코드 | **lab 하나만** |

### 실제 작업 흐름 (보스 정정안 그대로)

```
이슈 등록  →  보드에 자동 추가, 시작일=오늘 · 마감=+7일
              (길어질 것 같으면 사람이 end date 를 직접 늘린다)
       ↓
작업 후 커밋:  git commit -m "관측 설계 정리  Closes #12"
       ↓
main 에 push → GitHub 이 #12 를 닫음
       ↓
보드 Workflows: Item closed → Status = Done
       ↓
discord-notify: "✅ 완료 · 관측 설계 정리"
```

> `Closes #12` · `Fixes #12` 둘 다 동작한다. PR 본문에 써도 merge 시 닫힌다.

---

## 5. 아직 안 하는 것

| 항목 | 왜 |
|---|---|
| n8n 유튜브 자동 업로드 | Ep0 를 **손으로 한 번 올려본 뒤**. 안 해본 일을 자동화하면 틀린 걸 자동화한다 |
| 볼트 문서 대량 이관 | 새 문서부터 `foothold-lab/docs/` 에. 기존 것은 목록 합의 후 |
| `docs/` → 웹 자동 반영 파이프라인 | 레포가 생긴 뒤. `mdpage.py` 가 이미 있으므로 Actions 로 잇기만 하면 된다 |
