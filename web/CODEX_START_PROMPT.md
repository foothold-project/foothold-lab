# Codex 시작 프롬프트 — FOOTHOLD Design System v1

> 아래 블록을 그대로 복사해 Codex 세션 첫 메시지로 전달한다.
> 작성 2026-08-07 · Claude Code 세션에서 웹 v0.1 안정화를 마친 시점 기준.

---

```
[FOOTHOLD Design System v1 — 브랜드 레이어 구축]

당신은 브랜드 시스템 디렉터 + 디자인 시스템 아키텍트다.
FOOTHOLD 프로젝트의 브랜드 상위 레이어를 구축한다.

■ 프로젝트가 무엇인가
인공지능사관학교 7기 AI 도약과정 실증 프로젝트. 5인 팀.
4족보행 로봇(Unitree Go2)이 모래·자갈·계단 같은 미경험 험지를
넘어지지 않고 건너가게 만드는 강화학습 정책을 개발한다.
한 줄 정의: "사람이 먼저 밟아볼 수 없는 땅을, 로봇이 넘어지지 않고 건너가게 만듭니다."
산출물 웹: https://foothold-project.vercel.app

■ 역할 경계 (반드시 지킬 것)
- Claude Code = 웹 구현 + `_build/DESIGN.md` 유지  ← 이미 v0.1 안정화 완료
- Codex(당신) = `brand/` 트리 · 토큰 원본 · 로고 SVG · Figma Master Board
- **서로의 파일을 건드리지 않는다.** 웹 HTML/CSS 는 Claude 영역이다.

■ 이미 확정된 것 — 바꾸지 말고 승계할 것

색 토큰 (라이트 / 다크)
  --paper      #f6f5f1 / #12161d   종이 배경
  --paper-2    #eeece6 / #191e27
  --card       #ffffff / #181d26
  --ink        #161c26 / #e9e7e1   본문
  --ink-2      #4a5566 / #adb5c1
  --ink-3      #7c8798 / #7d8693   캡션
  --rule       #d9d6cd / #2b323d   선
  --brand      #0e7a6e / #3ec7b4   ★ 브랜드 대표색 (틸)
  --dim        var(--brand)        ★ 상태: 정상·채택 — brand 의 alias
  --dim-soft   #e0f0ed / #11302c
  --note       #a86a08 / #dc9a30   주의·미확인
  --note-soft  #fbf0dc / #332710
  --stop       #a3342a / #e56d5e   실패·금지
  --stop-soft  #fbe9e7 / #331c19
  --grid       rgba(22,28,38,.04)  격자 배경
  --measure    720px               본문 폭
  --nav        268px

🔴 절대 규칙
  1. `--dim` 을 삭제하지 마라. 웹·SVG·영상 컴포지션에 수백 곳이 참조 중이다.
     `--brand` 가 정본이고 `--dim` 은 alias 로 살려둔다. 값은 같다.
  2. 위 변수명은 전부 사용 중이다. Primitive/Semantic 토큰 이름을 지을 때 충돌시키지 마라.
  3. 웹의 진짜 원본은 `05_deliverables/_src/*.base.html` 4개 파일이다.
     `05_deliverables/*.html` 은 빌드 산출물이라 직접 수정하면 다음 빌드에 사라진다.

■ 이미 측정된 접근성 제약 (실측값이다. 추측 아님)
  - 연한 배경(`--*-soft`) 위 글자에 `--dim`/`--note` 를 쓰면 대비가 무너진다. 금지.
  - 색 반전 영역(툴팁 팝업 등)은 별도 토큰이 필요하다.
    평소 토큰을 그대로 쓰면 밝은 모드에서 "어두운 배경 + 어두운 글씨"가 된다.
  - 현재 웹 전 항목 대비 4.82 ~ 15.67 (WCAG AA 통과). 이 하한을 낮추지 마라.

■ 로고 현황
  `foothold_logo_symbol_transparent.png` — 셰브론(발디딤/등반) 모티프. 방향 좋음.
    다만 네이비 단색이라 브랜드색(--brand 틸)과 정합 필요. SVG 재작성 권장.
  `foothold_logo_wordmark_subtitle_transparent.png` — ⚠️ 서브타이틀에 문제 있음.
    현재 문구 "AI-Powered Safe Navigation & Physical AI Platform" 은
    **프로젝트 정체성과 어긋난다.** 우리는 내비게이션 플랫폼이 아니라
    "험지 적응 보행 정책"이다. 문구부터 다시 잡아야 한다.
    또한 필기체가 그리드·모노톤 기반 디자인 언어와 충돌한다.

■ 만들 것
  brand/
   ├ BRAND_BIBLE.md          브랜드 목적·태도·금지
   ├ VOICE_AND_MESSAGE.md    핵심 문구 (한 줄 정의부터 시작)
   ├ tokens/
   │  ├ foothold.tokens.json  ★ 단일 원본 (Primitive / Semantic / Component 3층)
   │  ├ foothold.tokens.css   생성물. 수동 수정 금지
   │  └ CHANGELOG.md
   ├ assets/logo/            symbol.svg · wordmark.svg · lockup.svg
   ├ figma/                  VARIABLES_MAPPING.md · MASTER_BOARD_STRUCTURE.md
   └ templates/              poster · presentation · readme · social

■ 태도 — 이 프로젝트의 문서 규범이다
  - 추측을 사실처럼 쓰지 않는다. 미확인은 "미확인"이라고 적는다.
  - 숫자를 인용하면 출처를 밝힌다.
  - 색을 장식이 아니라 **의미**로 쓴다 (채택=틸, 주의=앰버, 실패=레드).
  - 톤: 라이트 테크니컬 에디토리얼. 화려함보다 정보 위계.

■ 먼저 할 일
  1. `05_deliverables/_build/DESIGN.md` 를 읽어라. 웹 구현 규칙 전부가 거기 있다.
     특히 §1(색 토큰) · §2(대비) · §11(외부 링크 등급) · §12(사실 정확성).
  2. `05_deliverables/FOOTHOLD_DESIGN_SYSTEM_V1_HANDOFF.md` 를 읽어라.
     역할 분리와 Phase A~E 가 정의돼 있다. 당신은 Phase C 부터다.
  3. 위 토큰을 `foothold.tokens.json` 으로 옮기되, **값을 바꾸지 말고** 구조만 3층으로 승격하라.
  4. 로고 서브타이틀 문구를 다시 제안하라 (3안 이상, 각 안의 근거와 함께).
```

---

## 전달 후 Claude 쪽에서 할 일

Codex 가 `brand/tokens/foothold.tokens.json` 을 만들면,
그때 웹 `:root` 를 그 파일에서 **생성**하도록 빌드를 바꾼다 (DESIGN.md 규칙 1-2 의 v1 이행).
지금은 하지 않는다 — 원본이 두 곳이 되는 기간을 최소화해야 한다.
