# -*- coding: utf-8 -*-
"""사이트 문구 ↔ brand VOICE_AND_MESSAGE 정본 대조  (빌드 [1.79] 단계)

  색을 tokencheck 가 지키듯, **문구는 여기가 지킨다.**

  검사 두 가지
    ① 상태 라벨 강제: `TARGET VISION` 등급 문구(북극성)는 브랜드 규정상
       "Every use must carry the state label TARGET VISION". 그 문구가 페이지에 있는데
       라벨이 없으면 **배포를 멈춘다.** 아직 달성하지 않은 것을 달성한 것처럼 보이게 하는 건
       브랜드 위반이자 사실 왜곡이다(BRAND_BIBLE §6 evidence rules).
    ② 승인 문구 표류 감지. APPROVED 문구를 거의 그대로 쓰면서 글자만 살짝 다른 경우를 잡는다.
       (예: "4족 보행 로봇용 …" vs 승인 "4족 보행 로봇을 위한 …")
       완전히 다른 문장은 건드리지 않는다. 본문 카피까지 정본으로 강제하지는 않는다.

  브랜드 레포가 없거나 표를 못 읽으면 경고만 하고 통과한다.
"""
import io, os, re

CANDIDATES = [
    r"C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-brand\VOICE_AND_MESSAGE.md",
    os.path.expanduser(r"~\Desktop\jay\인공지능사관학교\foothold-brand\VOICE_AND_MESSAGE.md"),
    os.path.expanduser(r"~\OneDrive\Desktop\인공지능사관학교\foothold-brand\VOICE_AND_MESSAGE.md"),
]

STATE_LABEL = 'target vision'          # 페이지에 이 라벨이 보이면 상태 표기가 된 것


def load_rows():
    """메시지 아키텍처 표 → [(layer, text, state)]"""
    src = next((p for p in CANDIDATES if os.path.exists(p)), None)
    if not src:
        return None, []
    md = io.open(src, encoding='utf-8').read()
    m = re.search(r'##\s*4\.\s*Message architecture(.*?)(?:\n##\s|\Z)', md, re.S)
    if not m:
        return src, []
    rows = []
    for line in m.group(1).split('\n'):
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) >= 4 and cells[0] not in ('Layer', '---') and not set(cells[0]) <= set('- '):
            rows.append((cells[0], cells[2], cells[3].upper()))
    return src, rows


def norm(t):
    """비교용 정규화: 태그·공백·꾸밈을 걷어낸다."""
    t = re.sub(r'<[^>]+>', '', t)
    return re.sub(r'[\s·,.\u200b]+', '', t)


def main(vault, pages):
    src, rows = load_rows()
    if not rows:
        print('  [!] VOICE_AND_MESSAGE 정본을 읽지 못함. 문구 대조 건너뜀')
        return True

    vision = [t for _, t, st in rows if 'TARGET' in st]
    approved = [(l, t) for l, t, st in rows if st == 'APPROVED']
    problems = []

    # ★ 2026-09-10. PAGES 는 루트 페이지만 담는다. 하위 폴더(team-meang/)와
    #   assets/ 아래 페이지가 빠져 「검사했다」가 거짓이 된다.
    #   오늘 그 부류로 넷을 봤다 (감사 F-03 · 파비콘 주입·워드마크·검증).
    #   배포 전수의 정본은 searchbox.public_pages 하나다.
    import searchbox
    for f in sorted(searchbox.public_pages(vault, pages)):
        p = os.path.join(vault, f)
        if not os.path.exists(p):
            continue
        raw = io.open(p, encoding='utf-8').read()
        flat = norm(raw)

        # ① 지향 문구를 쓰면서 상태 라벨이 없으면 중단
        for v in vision:
            if norm(v) in flat and STATE_LABEL not in raw.lower():
                problems.append('%s: 북극성 문구를 쓰면서 상태 라벨(TARGET VISION)이 없음' % f)

        # ② 승인 문구 표류 (거의 같은데 다른 것만)
        for layer, t in approved:
            n = norm(t)
            if len(n) < 12 or n in flat:
                continue
            head = n[:14]
            if head in flat:                       # 앞부분이 같은데 전체가 다르다 = 표류 의심
                problems.append('%s: "%s" 문구가 정본과 다름: 정본 「%s」' % (f, layer, t[:46]))

    if problems:
        print('  ★ 브랜드 문구 규정 위반 %d건' % len(problems))
        for x in problems:
            print('     %s' % x)
        return False
    print('  정본: VOICE_AND_MESSAGE.md · 지향 문구 %d · 승인 문구 %d: 위반 없음'
          % (len(vision), len(approved)))
    return True
