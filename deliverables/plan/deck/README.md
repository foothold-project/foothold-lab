# FOOTHOLD 기획발표 웹 덱

이 폴더는 9월 4일 기획발표 Phase 1 산출물이다. 브라우저에서 `index.html`을 파일로 직접 열면 서버나 외부 CDN 없이 11장 덱이 실행된다.

## 원본과 생성물

| 경로 | 역할 |
|---|---|
| `content/slides.json` | 11장의 문장, 근거 상태, 발표자 노트, 출처를 한 번만 관리하는 공통 원본 |
| `content/deck-data.json` | `wbs.xlsx`에서 생성한 동결 스냅샷. 생성일과 원본·내용 SHA-256 포함 |
| `build/generate_deck_data.py` | 표준 라이브러리의 `zipfile`과 XML 파서로 xlsx를 읽는 생성기 |
| `build/render_deck.py` | 공통 원본과 SVG를 한 파일에 넣는 HTML 렌더러 |
| `build/theme.css` · `build/deck.js` | 브랜드 토큰, 전체화면 전환, 다크 모드, 발표자 노트 기능 |
| `assets/*.svg` | 슬라이드별 차트와 도식 원본 |
| `index.html` | 렌더된 자립형 웹 덱. 직접 고치지 않고 다시 생성 |

## 다시 만드는 법

저장소 루트에서 아래 두 명령을 순서대로 실행한다.

```bash
python deliverables/plan/deck/build/generate_deck_data.py
python deliverables/plan/deck/build/render_deck.py
```

생성기는 `WBS` 시트에서 `관문`, `WBS`, `담당자`, `완료율`, `저장소`를 열 이름으로 찾는다. 필수 열이나 데이터 행이 없으면 멈추며 0건인 것처럼 계속하지 않는다. `구현 단계` 열이 없으면 `implementationStages.active`를 `false`로 남기고 구현 단계 막대를 만들지 않는다.

## 발표 조작

오른쪽 화살표와 왼쪽 화살표로 장을 넘긴다. `F`는 전체화면, `N`은 발표자 노트, 우측 상단 원형 버튼은 색상 모드 전환이다. 발표자 노트의 근거 상태는 `content/slides.json`의 `evidence`를 화면과 함께 읽으므로 같은 문구를 두 번 관리하지 않는다.

## 현재 제한

7번 장은 아직 재측정 데이터가 없어 축과 읽는 법만 표시한다. 8번 장은 이슈 #122에서 구현 단계를 정하기 전까지 단계 막대가 비활성이다. 1번과 11번 장에는 승인된 현장 사진과 최종 영상이 아직 없어 저작권 출처가 필요 없는 추상 SVG를 사용했다.
