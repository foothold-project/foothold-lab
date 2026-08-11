
# 웹 페이지 디자인 규칙 — 새 페이지를 만들 때 지켜야 하는 것

> 대상: foothold-site 에 올라가는 모든 페이지. 사람이든 세션이든 새 페이지를 만들면 이 문서를 따른다.
> 정본 토큰: `foothold-brand/tokens/foothold.tokens.json` — 웹의 CSS 변수 7종과 값이 일치함을 실측 확인(08-08).
> 빌드가 검사한다: `_build/brandvar.py`([1.75] 단계)가 `--brand` 변수 부재를 잡는다. 문서만으로는 지켜지지 않는다.

## 1. 색은 CSS 변수로만

```css
:root {
  --brand: #E85D2A;        /* 이하 7종은 brand tokens 과 동기 */
  --bg: …; --fg: …; --muted: …; --card: …; --line: …; --accent: …;
}
```
- 색상값을 본문 CSS 에 직접 쓰지 않는다. 변수를 안 거친 색은 다크모드에서 깨진다.
- 새 색이 필요하면 먼저 brand tokens 에 추가하고 변수로 내려받는다.

## 2. 다크모드 — 자동 감지 + 사용자 토글 (팀장 결정 08-09)

모든 새 페이지는 세 가지를 갖춘다:

1. `@media (prefers-color-scheme: dark)` — OS 설정 자동 감지 (기본값)
2. `:root[data-theme="dark"]` / `:root[data-theme="light"]` — 토글이 이기는 명시 오버라이드
3. 우측 상단 ☀️/🌙 토글 버튼 — 선택은 `localStorage("theme")` 에 저장, 페이지 간 공유

패턴 정본은 curriculum.html 의 `:root[data-theme]` 구현. 새 페이지는 이걸 복사해서 시작한다.

## 3. 구조물 표현

- **웹에 ASCII 아트 금지** (세션 규칙 2) — 구조도·흐름도는 SVG·이미지·표로. md 원문에는 무방.
- SVG 색도 CSS 변수를 쓴다(`fill="var(--brand)"`) — 다크 전환 시 그림도 따라온다.

## 4. 나가기 전 관문 (순서 고정)

빌드 파이프라인이 강제한다: 브랜드 변수 확인 → 사실 주장 검증(--verify) → 민감정보 검사 → 배포.
이 관문을 우회해 foothold-site 에 직접 커밋하지 않는다 — 다음 빌드가 덮어쓴다.
