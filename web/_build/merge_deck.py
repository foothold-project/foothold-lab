# -*- coding: utf-8 -*-
"""킥오프 4장을 팀 소개 뒤에 붙여 한 문서(7장)로 만든다.

  왜: 발표 흐름이 "우리는 누구인가(3장) → 무엇을 어떻게 하는가(4장)"로 이어지고,
      대외 공유 시 링크를 한 번만 주면 된다.

  ★ 핵심 문제와 해법
    두 문서는 .eyebrow · h1 · h2 · .sub · .mark 같은 공통 선택자를 **다른 값으로** 쓴다
    (실측 43개 충돌). 그대로 합치면 뒤에 온 규칙이 앞 문서를 덮어써 레이아웃이 깨진다.
    그래서 킥오프 슬라이드에 data-deck="ko" 를 달고, 킥오프 CSS 전체를
    [data-deck="ko"] 로 범위를 좁혀 이관한다. 팀소개 쪽은 한 줄도 영향받지 않는다.

    전역 규칙(:root · html · body · #deck · #chrome · @page 등)은 이관하지 않는다.
    두 문서가 같은 뼈대를 쓰므로 팀소개 것을 그대로 쓰면 된다.
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
SRC = os.path.join(VAULT, '_src')
SCOPE = '[data-deck="ko"]'

# 이관하지 않는 전역 선택자 (팀소개 것을 그대로 쓴다)
GLOBAL = re.compile(r'^(:root|\*|html|body|#deck|#chrome|#bar|#fs|\.pdfbtn|\.backdrop|@page|@font-face)\b')


def sections(html):
    out, i = [], 0
    while True:
        a = html.find('<section class="slide', i)
        if a < 0:
            return out
        d, j = 0, a
        while True:
            m = re.compile(r'<(/?)section\b[^>]*>').search(html, j)
            if not m:
                return out
            d += -1 if m.group(1) else 1
            j = m.end()
            if d == 0:
                break
        out.append(html[a:j])
        i = j


def css_of(html):
    a, b = html.find('<style>'), html.find('</style>')
    return html[a + 7:b] if a >= 0 and b > a else ''


def strip_comments(css):
    """★ 범위 격리 전에 /* ... */ 주석을 반드시 제거한다.

       안 하면 주석 앞부분이 '선택자'로 잘못 잡혀
         [data-deck="ko"] 좌측 표를 그 안에서 ... */
       같은 깨진 CSS가 나오고, 그 지점부터 파싱이 무너져
       뒤따르는 규칙이 통째로 무시된다(실제로 겪음. 킥오프 3장 세로정렬 붕괴).
       원본 주석은 _src/kickoff.base.html 에 그대로 남는다."""
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def scope_sel(sel):
    """선택자 하나를 킥오프 범위로 좁힌다."""
    sel = sel.strip()
    if not sel or sel.startswith('/*'):
        return None
    if GLOBAL.match(sel):
        return None
    # .slide 자체를 가리키는 규칙은 섹션에 붙은 속성으로 대체
    if sel.startswith('.slide'):
        return SCOPE + sel[len('.slide'):]
    return SCOPE + ' ' + sel


def scope_block(css):
    """중괄호 블록 단위로 순회하며 선택자를 좁힌다. @media 는 안쪽만 좁힌다."""
    out, i, n = [], 0, len(css)
    while i < n:
        at = css.find('@', i)
        br = css.find('{', i)
        if br < 0:
            break
        if 0 <= at < br:                       # @media / @supports 등
            depth, j = 0, br
            while j < n:
                if css[j] == '{':
                    depth += 1
                elif css[j] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            head = css[at:br].strip()
            inner = scope_block(css[br + 1:j])
            if inner.strip() and not head.startswith('@page') and not head.startswith('@font-face'):
                out.append('%s{\n%s}\n' % (head, inner))
            i = j + 1
            continue
        # 일반 규칙
        end = css.find('}', br)
        if end < 0:
            break
        sels = [scope_sel(s) for s in css[i:br].split(',')]
        sels = [s for s in sels if s]
        body = css[br + 1:end].strip()
        if sels and body:
            out.append('%s{%s}\n' % (',\n'.join(sels), body))
        i = end + 1
    return ''.join(out)


def main():
    ti_src = os.path.join(SRC, 'team-intro.base.html')
    ko_src = os.path.join(SRC, 'kickoff.base.html')
    for base, live in [(ti_src, 'team-intro.html'), (ko_src, 'kickoff.html')]:
        if not os.path.exists(base):
            p = os.path.join(VAULT, live)
            if not os.path.exists(p):
                print('  [!] 원본 없음: %s' % live); return 1
            io.open(base, 'w', encoding='utf-8').write(io.open(p, encoding='utf-8').read())
            print('  원본 보존: _src/%s' % os.path.basename(base))

    import roles
    ti = roles.expand(io.open(ti_src, encoding='utf-8').read())
    if '<!--ROLES:deck-->' in ti:
        print('  [!] 역할 카드를 못 채웠습니다 (ROLES.md 를 못 읽음)'); return 1
    ko = io.open(ko_src, encoding='utf-8').read()

    # ★ 2026-08-27. kickoff.html 은 «원본을 처음 뜰 때의 씨앗»으로만 쓰이고
    #   그 뒤로는 한 번도 다시 안 만들어졌다. 그래서 _src 를 고쳐도 이 파일에는
    #   옛 마일스톤(W4·W9·W14·W18·W20)이 그대로 남아 있었다. 배포 대상이 아니라
    #   관문에도 안 걸렸다. 원본에서 다시 써서 갈라질 자리를 없앤다.
    io.open(os.path.join(VAULT, 'kickoff.html'), 'w', encoding='utf-8',
            newline='\n').write(ko)

    ti_secs, ko_secs = sections(ti), sections(ko)
    if len(ti_secs) != 3 or len(ko_secs) != 4:
        print('  [!] 슬라이드 수 이상 (팀소개 %d, 킥오프 %d)' % (len(ti_secs), len(ko_secs))); return 1

    # ★ 킥오프 1P 제외: 팀소개 1P와 44%, 2P와 43% 겹치는 축약본이다(PDF 실측).
    #    같은 FOOTHOLD 표지·슬로건·팀원 6칸이 두 번 나온다.
    ko_secs = ko_secs[1:]

    # 킥오프 슬라이드에 범위 표식을 달고 활성 표시를 뗀다
    ko_secs = [s.replace('<section class="slide on">', '<section class="slide" data-deck="ko">', 1)
                .replace('<section class="slide">', '<section class="slide" data-deck="ko">', 1)
               for s in ko_secs]

    scoped = scope_block(strip_comments(css_of(ko)))
    # 격리가 새지 않았는지 확인: 하나라도 새면 팀소개 레이아웃이 깨진다
    leak = [s for s in (m.group(2).strip() for m in re.finditer(r'(^|\n)([^{}\n]+)\{', scoped))
            if s and SCOPE not in s and not s.startswith('@')]
    if leak:
        print('  [!] 범위 격리를 벗어난 규칙 %d개: %s' % (len(leak), leak[:3]))
        return 1
    print('  격리 검사  : 새는 규칙 0개')
    # ── 병합 후 리듬 보정 ──
    # 팀소개 3장은 [eyebrow → h2 → sub → 그리드] 라 헤더가 약 27mm 를 먹는다.
    # 킥오프 2P(.p2)만 제목이 그리드 **안**에 있어 헤더가 10mm 뿐이고,
    # 그 결과 그리드가 17mm 더 커져 상단에 빈 띠가 생긴다(실측 183.7 vs 166.8mm).
    # 그리드를 그만큼 내려 6장의 세로 리듬을 맞춘다.
    rhythm = '''
/* 병합 후 세로 리듬 보정: 6장이 같은 높이에서 본문을 시작하게 한다 */
[data-deck="ko"] .p2{margin-top:1.7rem}
@media (max-width:820px){ [data-deck="ko"] .p2{margin-top:0} }
@media print{ [data-deck="ko"] .p2{margin-top:15mm} }
'''

    merged_css = (rhythm + '\n/* ═══════════ 킥오프 4장: 범위 격리 이관 ═══════════\n'
                  '   두 문서가 .eyebrow · h1 · h2 · .sub 등을 다른 값으로 쓰기 때문에\n'
                  '   (실측 43개 충돌) 그대로 합치면 팀소개 레이아웃이 깨진다.\n'
                  '   그래서 킥오프 규칙 전체를 [data-deck="ko"] 안으로 가둔다.\n'
                  '   전역 규칙(:root·html·body·#deck·#chrome)은 팀소개 것을 그대로 쓴다. */\n'
                  + scoped + '\n')

    out = ti.replace(ti_secs[-1], ti_secs[-1] + '\n\n' + '\n\n'.join(ko_secs), 1)
    out = out.replace('</style>', merged_css + '</style>', 1)
    out = re.sub(r'<title>[^<]*</title>',
                 '<title>팀 소개 · 프로젝트 킥오프: FOOTHOLD</title>', out, count=1)
    out = re.sub(r'(<meta name="description" content=")[^"]*(")',
                 r'\1팀 정체성·역할·협업 구조와 프로젝트 개요·20주 계획. 슬라이드 7장.\2', out, count=1)

    io.open(os.path.join(VAULT, 'team-intro.html'), 'w', encoding='utf-8').write(out)
    n = len(sections(out))
    print('  병합      : 팀소개 3장 + 킥오프 3장(1P 중복 제외) = %d장' % n)
    print('  범위 격리 : 킥오프 CSS %s bytes → [data-deck="ko"]' % format(len(scoped), ','))
    print('  크기      : %s bytes' % format(len(out), ','))
    return 0 if n == 6 else 1


if __name__ == '__main__':
    sys.exit(main())
