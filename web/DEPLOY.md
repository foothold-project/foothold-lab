# 배포 방법

## 공개 주소와 배포원 (2026-09-08 실측)

**https://foothold-project.vercel.app**

| | |
|---|---|
| 배포원 | `foothold-project/foothold-site` 저장소의 `main` |
| 생성기 | 여기 (`05_deliverables/_build/`) |
| 배포 절차 | `python _build/build.py --skip-secure` -> `foothold-site` 로 복사됨 -> 그 저장소에 커밋·push -> Vercel 자동 배포 |

**아래 「Vercel 배포」 절은 이 볼트를 직접 붙이던 초기 설정입니다.** 지금은 `foothold-site` 가 배포원이고, 이 폴더에 push 해도 사이트는 바뀌지 않습니다. 초기 이력으로만 둡니다.

> 근거: 2026-09-08 에 `foothold-site` `e1aae85` 를 push 한 뒤 위 주소가 실제로 바뀌는 것을 확인했습니다. 주소가 두 저장소 어디에도 적혀 있지 않아 다른 세션이 못 찾았습니다 (철칙 2).

---

## Vercel 배포 (초기 설정 · 지금은 쓰지 않음)

1. https://vercel.com 접속 → **Add New… → Project**
2. GitHub 저장소(`MAI_UNIVERSE`) 연결
3. **Root Directory** 를 아래로 지정. 이게 핵심입니다
   ```
   03_PROJECTS/doyak-final/05_deliverables
   ```
4. **Framework Preset**: `Other`
5. **Build Command** / **Output Directory**: **비워둠** (빌드 없음)
6. Deploy

`vercel.json` 이 캐시 정책을 지정합니다.
`assets/` 는 1년 캐시(immutable), HTML 은 항상 최신을 받아옵니다.

### ⚠️ Root Directory 를 지정하지 않으면
저장소 루트가 배포되어 `index.html` 을 못 찾고,
**`0z_Inbox/` 의 민감 파일까지 공개 URL로 노출될 수 있습니다.** 반드시 지정하세요.

---

## 로컬 확인

```
python -m http.server 8899
```
→ http://localhost:8899

수정 후 새로고침이 안 먹으면 주소 뒤에 `?v=2` 를 붙이거나 `Ctrl+Shift+R`.

---

## 파일 구조 (자동 갱신 · 2026-08-05 기준)

| 파일 | 크기 |
|---|---|
| `index.html` | 15 KB |
| `encyclopedia.html` | 198 KB |
| `curriculum.html` | 191 KB |
| `setup.html` | 39 KB |
| `brief.html` | 21 KB |
| `team-intro.html` | 59 KB |
| `vercel.json` | 0 KB |
| `assets/` | 4,536 KB |
| **합계** | **4.9 MB** |

> `kickoff.html` 은 `team-intro.html` 로 병합됐습니다(6장). 단독 배포하지 않습니다.
> 배포는 `python _build/build.py --check` 한 줄로 합니다 — 볼트가 원본, 여기는 복사본입니다.

## PDF 저장

각 문서 **우측 상단 `PDF 저장`** 버튼 → 브라우저 인쇄 창 → 대상에서 **"PDF로 저장"** 선택.
`Ctrl+P` 로도 동일합니다.

| 문서 | 출력 |
|---|---|
| 프로젝트 킥오프 | **4페이지 · A4 가로** |
| 팀 소개 | **3페이지 · A4 가로** |
| 도메인 백과 | **48페이지 · A4 세로** (링크 URL이 각주로 노출됨) |
| 표지 | 2페이지 · A4 세로 |

버튼은 **데스크톱에만** 표시되고 **인쇄물에는 찍히지 않습니다.**

---

## 조작

| 대상 | 방법 |
|---|---|
| 슬라이드 넘기기 | `←` `→` `Space` · 하단 `‹ ›` · 모바일 스와이프 |
| 전체화면 | `F` 또는 하단 `전체화면` (데스크톱) |
| 표지로 | 슬라이드 하단 좌측 `← 표지` · 백과 좌측 목차 상단 `← 표지로` |
| 백과 목차 | 데스크톱은 좌측 고정 · 모바일은 좌측 상단 `☰` |

---

## 이미지 출처

`assets/` 이미지는 원저작자 표기를 조건으로 사용하며, 각 캡션 하단에 출처와 라이선스를 명기했습니다.

| 파일 | 출처 | 라이선스 |
|---|---|---|
| `muybridge-walk.gif` | Eadweard Muybridge (1878), Wikimedia Commons | Public Domain |
| `hildebrand-map.jpg` · `trot-force-geom.jpg` | eLife 2017;6:e29495 Fig 1 · Fig 3 | CC BY |
| `isaaclab-go2-rough.jpg` | NVIDIA Isaac Lab 공식 문서 | 출처 표기 |
| `elevation-map.jpg` · `unreliable-map.gif` | ETH Zürich RSL 프로젝트 페이지 | 출처 표기 |
| `vr-robo-pipeline.jpg` | VR-Robo 프로젝트 페이지 | 출처 표기 |
| `unitree-go2.jpg` | google-deepmind/mujoco_menagerie | BSD-3-Clause |

---

## 검증 이력 (2026-07-30)

| 항목 | 결과 |
|---|---|
| 내부 앵커 · 파일 링크 | 0 · 0 실패 |
| 외부 URL | 19/19 → 200 |
| HTML 태그 균형 | 4/4 일치 |
| CSS 중괄호 균형 | 73/73 · 183/183 · 167/167 · 132/132 |
| 반응형 실측 | 360 · 390 · 1366 · 1440 · 1920px |
| PDF 출력 | 페이지 수 · 방향 · 버튼 미노출 확인 |
| 이미지 | 8/8 로드 |

**검증하지 못한 것** — 실제 iOS Safari / Android Chrome 엔진(뷰포트 크기만 에뮬레이션),
실제 프린터 출력(PDF만 확인), Vercel 환경에서의 경로·캐시 동작.
