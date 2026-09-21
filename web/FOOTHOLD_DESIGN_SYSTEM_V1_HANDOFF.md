# FOOTHOLD Design System v1 Handoff

작성 목적: Claude Code와 Codex가 같은 작업을 중복하거나 서로의 파일을 꼬이게 만들지 않도록, 현재 `DESIGN.md`의 역할을 보존한 채 `FOOTHOLD Design System v1`를 별도 브랜드 레이어로 정의하기 위한 협업 기준 문서.

대상 `DESIGN.md`: [`_build/DESIGN.md`](./_build/DESIGN.md)  
절대 경로: `C:\Users\<사용자>\OneDrive\Desktop\인공지능사관학교\MAI_UNIVERSE\03_PROJECTS\doyak-final\05_deliverables\_build\DESIGN.md`

참고 범위: 업로드된 `DESIGN.md`에 대해 이전 논의에서 추출된 내용과 라인 범위를 기준으로 정리했다. Claude Code 세션에서는 실제 원본 파일을 열어 라인 범위를 한 번 더 대조한 뒤 반영하는 것을 권장한다.

## 전문가 관점

이 문서는 다음 네 가지 관점을 결합해 작성했다.

1. 브랜드 시스템 디렉터
2. 정보 디자인·과학 커뮤니케이션 디자이너
3. 디자인 시스템 아키텍트
4. 프론트엔드·크로스미디어 제작 시스템 아키텍트

---

## 1. 현재 `DESIGN.md`의 역할과 강점

`DESIGN.md`는 완성된 브랜드 바이블이라기보다, 현재 웹 산출물에서 실제로 지켜지고 있는 규칙과 운영 원칙을 기록한 문서에 가깝다 (`DESIGN.md` L1-L9).

핵심 강점은 다음과 같다.

- 현재 웹페이지의 실운영 규칙을 이미 문서화하고 있다.
- `Warm Paper + Ink + Teal/Amber/Red` 중심의 색 체계가 명확하다 (`DESIGN.md` L30-L42).
- 색을 장식이 아니라 의미로 사용한다. 예: 채택/정상, 주의/미확인, 실패/금지 (`DESIGN.md` L46-L51).
- 접근성 문제를 실측으로 다루고 있고, soft 배경 위 대비 이슈까지 기록되어 있다 (`DESIGN.md` L88-L97).
- 32px 그리드와 정보 계층 사고방식이 이미 잡혀 있다 (`DESIGN.md` L144-L150).
- 단일 원본, 빌드 검증, PDF/모바일 실측, 민감정보 검사까지 포함한 운영 철학이 강하다 (`DESIGN.md` L297-L329).
- 출처·근거 등급 같은 정보 신뢰성 규칙도 포함하고 있어, 향후 브랜드 태도로 확장할 가치가 있다 (`DESIGN.md` L357-L378).

정리하면, `DESIGN.md`는 버릴 문서가 아니라 **FOOTHOLD Web Implementation Standards / Visual Identity v0의 핵심 기반 문서**다.

---

## 2. 유지해야 할 것

아래 항목은 현재 단계에서 바꾸기보다 보존하는 것이 맞다.

- `Warm Paper` 계열 배경과 `Ink` 중심의 기본 명도 구조
- `Teal`, `Amber`, `Red`를 의미 기반으로 사용하는 접근
- 정보 위계가 분명한 라이트 테크니컬 에디토리얼 톤
- 32px 기반 레이아웃 사고방식
- 단일 원본, 빌드 검증, 렌더링 실측, 민감정보 검사 원칙
- “페이지/컴포넌트 단위 임의 장식”보다 “규칙 기반 일관성”을 우선하는 태도
- 웹과 PDF를 함께 고려하는 구현 철학

즉, 방향은 “전면 교체”가 아니라 **통제된 진화**여야 한다.

---

## 3. 수정 또는 확장이 필요한 부분과 이유

### 3-1. 브랜드색과 상태색의 역할 분리

현재 `--dim`은 브랜드 대표색이면서 동시에 정상/채택/정답 상태를 뜻하는 역할까지 겸하고 있다. 이 구조는 웹 문서에서는 편리하지만, 포스터·PPT·후드티·스티커·README Hero까지 확장되면 의미 충돌이 생길 수 있다.

권장 방향:

- 개념상 `brand.primary`와 `state.adopted`를 분리한다.
- 초기에는 같은 HEX를 참조해도 되지만, 이름과 역할은 분리한다.
- 기존 `--dim`은 즉시 삭제하지 말고 점진적으로 alias 처리한다.

근거: 현재 색상 정의와 의미 구조 (`DESIGN.md` L30-L42, L46-L51).

### 3-2. 토큰 구조의 승격

현재는 값 중심 정의에 가깝다. 앞으로는 다음 3층 구조가 필요하다.

- Primitive Tokens: raw color/spacing/radius/typography scale
- Semantic Tokens: brand, adopted, note, stop, surface, caption
- Component Tokens: card, badge, panel, hero, diagram node, chart

이 구조가 없으면 웹, Figma, SVG, 발표자료에서 같은 개념이 서로 다른 이름으로 분기될 위험이 크다.

### 3-3. `:root` 복사 운영의 개선

현재 새 페이지마다 `:root` 블록을 복사하는 방식은 누락 방지에는 좋지만, 장기적으로는 값 중복과 drift를 만든다 (`DESIGN.md` L53-L60).

권장 방향:

- `foothold.tokens.json`을 원본으로 둔다.
- CSS는 생성물로 관리한다.
- 웹 페이지는 생성된 CSS를 참조하거나 빌드 시 주입한다.

### 3-4. 접근성 추가 보정

기존 문서가 이미 대비 이슈를 실측하고 있다는 점은 강점이다. 다만 이 원칙을 브랜드 시스템에도 승격해야 한다. 특히 작은 캡션, 출처, soft 배경 위 텍스트는 계속 검토가 필요하다 (`DESIGN.md` L88-L97).

### 3-5. 브랜드 표현 계층의 확장

현재 시스템은 문서 UI에는 강하지만, 다음에는 아직 약하다.

- Hero visual
- 대표 로봇 일러스트
- Sim-to-Real 다이어그램
- 발표 첫 장
- GitHub/README social preview
- 굿즈용 단색/축약 자산

즉, `DESIGN.md`는 구현 규칙으로는 충분히 강하지만, 브랜드 전반을 다루는 상위 레이어는 아직 별도로 필요하다.

---

## 4. `DESIGN.md`를 훼손하지 않고 `FOOTHOLD Design System v1`를 별도 브랜드 레이어로 정의하는 제안

핵심 원칙은 간단하다.

- `DESIGN.md`는 **웹 구현 및 운영 기준 문서**로 유지한다.
- `FOOTHOLD Design System v1`는 **브랜드 레이어**로 별도 정의한다.
- 새 시스템이 `DESIGN.md`를 덮어쓰지 않고, 필요한 부분만 참조·보완한다.

권장 역할 분리:

- `DESIGN.md`
  - 웹 구현 규칙
  - CSS namespace
  - 접근성 규칙
  - PDF/모바일 검증
  - 빌드/배포/보안 체크
- `FOOTHOLD Design System v1`
  - 브랜드 목적과 메시지
  - 로고 시스템
  - 컬러 체계
  - 타이포그래피
  - 아이콘/일러스트/도식 문법
  - 매체별 변형 규칙
  - Master Board/Figma/SVG/토큰 체계

즉, `DESIGN.md`를 대체하는 것이 아니라 **상위 브랜드 레이어를 추가**하는 방식이 맞다.

---

## 5. 권장 저장소 / 브랜드 트리 구조

```text
brand/
├─ BRAND_BIBLE.md
├─ VOICE_AND_MESSAGE.md
├─ MASTER_BOARD_SPEC.md
├─ tokens/
│  ├─ foothold.tokens.json
│  ├─ foothold.tokens.css
│  ├─ foothold.tokens.md
│  └─ CHANGELOG.md
├─ assets/
│  ├─ logo/
│  │  ├─ foothold-symbol.svg
│  │  ├─ foothold-wordmark.svg
│  │  └─ foothold-lockup.svg
│  ├─ icons/
│  ├─ illustration/
│  ├─ diagrams/
│  └─ exports/
├─ figma/
│  ├─ FIGMA_FILE_LINK.md
│  ├─ VARIABLES_MAPPING.md
│  └─ MASTER_BOARD_STRUCTURE.md
└─ templates/
   ├─ poster/
   ├─ presentation/
   ├─ github/
   ├─ readme/
   └─ social/

web/
└─ ...existing implementation...

05_deliverables/
└─ DESIGN.md
```

저장소 구조가 이미 다르다면, 중요한 것은 경로 이름보다 역할 분리다.

---

## 6. 파일 중복·충돌을 막기 위한 Source-of-Truth 규칙

아래 규칙은 반드시 고정하는 것을 권장한다.

1. 컬러/간격/반경/타이포의 원본은 `brand/tokens/foothold.tokens.json` 하나만 둔다.
2. `foothold.tokens.css`는 생성물로 취급하고 수동 수정하지 않는다.
3. `DESIGN.md`에는 토큰 전체를 다시 복사하지 않는다. 필요하면 “canonical token file 참조”만 남긴다.
4. SVG는 원본 자산, PNG/PDF는 export로 취급한다.
5. Figma Master Board는 시각 조합의 원본이지, 토큰의 최종 원본은 아니다.
6. 웹 구현에서 임의 색을 추가하지 않는다. 새 색은 먼저 토큰에 등록한 뒤 사용한다.
7. 기존 변수명을 바꿀 때는 alias와 deprecation 기간을 둔다. 바로 삭제하지 않는다.
8. 브랜드 메시지 문구는 `VOICE_AND_MESSAGE.md`를 기준으로 한다.
9. README, PPT, Poster용 파생 산출물은 직접 수정본을 늘리기보다 템플릿/토큰/원본 SVG를 통해 관리한다.

---

## 7. 권장 작업 흐름

### Phase A. Claude Code 중심 웹 반영

- 실제 `DESIGN.md` 원본 확인
- 문서 내 절대 문장 중 수정이 필요한 부분 정리
- `--dim` 등 역할 충돌 변수의 alias 전략 설계
- 접근성 및 contrast 보정
- 현재 웹 UI에 필요한 최소한의 구조 개선 반영

### Phase B. 웹 기준선 고정

- “현재 웹에서 채택된 v0.1 기준”을 정리
- 변경 이유와 영향 범위를 기록
- 토큰 이름 변경/추가 여부를 잠정 확정

### Phase C. Codex 중심 브랜드 트리 작업

- `brand/` 트리 생성
- `BRAND_BIBLE.md` 작성
- `foothold.tokens.json` 초안 생성
- `foothold.tokens.css` 생성 파이프라인 구성
- 로고/SVG/다이어그램 자산 정리
- Master Board 모듈 정의

### Phase D. Figma / Master Board

- Figma Variables와 토큰 매핑
- Visual Master Board 제작
- Hero / Diagram / Team / Evidence / Roadmap 모듈 배치
- 16:9, A3, README Hero 등으로 파생

### Phase E. 재반영

- 필요한 토큰 수정 사항만 웹으로 역반영
- 웹과 브랜드 문서의 drift 여부 점검

정리하면:

- Claude Code는 **웹 구현과 `DESIGN.md` 보완**
- Codex는 **brand tree / token / SVG / Figma / master board**

로 역할을 나누는 것이 가장 안전하다.

---

## 8. Claude Code 전문가 세션에 전달할 명시적 핸드오프 지시

아래 지시문을 그대로 전달해도 된다.

1. 현재 `DESIGN.md`는 폐기 대상이 아니라 `FOOTHOLD Web Implementation Standards / Visual Identity v0`로 유지한다.
2. 다만 이 문서를 최종 브랜드 바이블로 고정하지 말고, `FOOTHOLD Design System v1`를 별도 브랜드 레이어로 정의하는 방향을 기준으로 검토한다.
3. 특히 아래 항목은 `DESIGN.md`에서 보완 또는 수정 후보로 검토한다.
   - 브랜드색과 상태색 역할 분리
   - `--dim` 명명 개선 및 alias 전략
   - 토큰 원본 파일 분리 가능성
   - `:root` 복사 운영의 장기 대안
   - 접근성 보정의 시스템화
4. 반대로 아래 항목은 유지 우선으로 본다.
   - Warm Paper + Ink 중심 명도 구조
   - Teal/Amber/Red의 의미 기반 사용
   - 32px grid 사고방식
   - 단일 원본/빌드 검증/실측/보안 검사 철학
5. 실제 원본 `DESIGN.md`를 열고, 현재 문서에 적힌 라인 범위 참조가 맞는지 확인한 뒤 반영한다.
6. 웹 반영 단계에서는 브랜드 전체를 한 번에 확장하지 말고, 현재 사이트 품질을 해치지 않는 범위에서 v0.1 기준선을 먼저 안정화한다.
7. Codex가 후속으로 `brand/` 트리, 토큰, SVG, Figma Master Board를 구축할 수 있도록 파일 경로와 naming을 정리해 둔다.

---

## 9. 다음 단계 체크리스트

### 바로 할 일

- [ ] Claude Code에서 실제 `DESIGN.md` 원본 열기 및 라인 범위 대조
- [ ] `DESIGN.md` 내 “절대 금지/절대 고정” 문구 중 완화가 필요한 부분 표시
- [ ] `--dim` alias 전략 초안 수립
- [ ] 접근성 보정 대상 목록 작성
- [ ] 웹 구현 기준선(v0.1) 확정

### 그 다음 할 일

- [ ] `brand/` 트리 생성
- [ ] `BRAND_BIBLE.md` 초안 작성
- [ ] `VOICE_AND_MESSAGE.md`에 핵심 문구 확정
- [ ] `foothold.tokens.json` 초안 작성
- [ ] `foothold.tokens.css` 생성 규칙 정의
- [ ] 로고/워드마크/SVG 자산 정리
- [ ] Figma Variables 매핑
- [ ] Visual Master Board 제작

### 최종 목표

- [ ] Website
- [ ] PPT
- [ ] Poster
- [ ] GitHub / README
- [ ] Paper figure
- [ ] Portfolio
- [ ] Roll-up banner
- [ ] Sticker / Hoodie

모든 산출물이 하나의 브랜드 시스템에서 파생되도록 정리한다.

---

## 최종 판단

가장 좋은 선택은 기존 디자인을 버리거나 그대로 고정하는 것이 아니다.

**현재 `DESIGN.md`의 운영 철학과 시각 자산은 보존하되, 브랜드와 상태를 분리하고 토큰 구조·접근성·브랜드 표현 계층을 확장한 `FOOTHOLD Design System v1`를 별도 레이어로 정의하는 것**이 최선이다.

이 방식이면 Claude Code는 웹 품질과 구현 안정성을 지키고, Codex는 장기적으로 재사용 가능한 brand tree, token system, SVG asset, Figma Master Board를 구축할 수 있다.
