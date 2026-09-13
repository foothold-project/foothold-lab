# -*- coding: utf-8 -*-
"""Markdown 원문 → 문서형 HTML 페이지.

  왜 만드나. setup.html 은 SETUP_GUIDE.md 를 **손으로 옮겨** 만든 페이지다.
  원문이 바뀔 때마다 양쪽을 따로 고쳐야 하고, 한 번만 잊으면 웹이 거짓말을 한다.
  새 페이지부터는 **md 를 읽어 생성**한다. 그러면 갈라질 수가 없다.

  지원 문법: 우리 문서가 실제로 쓰는 것만
    # ~ ####  ·  표  ·  ``` 코드  ·  > 인용  ·  - / 1. 목록  ·  --- 구분선
    **굵게**  ·  `코드`  ·  [문구](주소)  ·  [[문서]](설명) → 회색 칩
  지원 안 하는 것은 그대로 통과시킨다(깨지지 않게).

  디자인은 setup.html 과 같은 토큰을 쓴다 (DESIGN.md §1).
"""
import html as H
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hl
import mdlinks

# ────────────────────────── 인라인 ──────────────────────────

_COPY_BTN = ('<button class="copy" type="button" '
             'aria-label="복사">복사</button>')

# 볼트 문서 → 배포된 페이지. 여기 없는 이름은 링크를 걸지 않는다(죽은 링크 금지).
VAULT_PAGES = {
    'SETUP_GUIDE': 'setup.html',
    'TEAM_ACCESS': 'team-access.html',
}
LABELS = {
    'SETUP_GUIDE': '개발환경 구축 가이드',
    'TEAM_ACCESS': '팀원 사용 가이드',
}

# 그림을 찾을 곳. 빌드가 도는 자리(web/)가 기준이다.
SVG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _svg_inline(src):
    """페이지 토큰을 쓰는 SVG 를 본문에 넣을 수 있게 읽어 온다.

    토큰을 안 쓰면 `<img>` 로 두는 편이 낫다. 브라우저가 따로 받아 캐시하고
    본문이 가벼워진다. **토큰을 쓸 때만** 인라인한다.

    못 읽으면 `None` 을 준다. 부르는 쪽이 `<img>` 로 돌아간다. 그림이 통째로
    사라지는 것보다는 낫다.
    """
    if src.startswith(('http://', 'https://', '//', 'data:')):
        return None
    path = os.path.join(SVG_ROOT, src.replace('/', os.sep))
    if not os.path.isfile(path):
        return None
    try:
        t = io.open(path, encoding='utf-8').read()
    except OSError:
        return None
    if 'var(--' not in t:
        return None                      # 토큰을 안 쓰면 그대로 img 로 둔다
    i = t.find('<svg')
    if i < 0:
        return None
    t = t[i:]
    # 본문에 들어가므로 문서용 속성은 뗀다. 두 번 선언되면 접근성 나무가 흐려진다.
    t = re.sub(r'\sxmlns(:\w+)?="[^"]*"', '', t, count=2)
    # id 충돌을 막는다. 한 페이지에 도해가 열세 장이면 marker id 가 부딪힌다.
    tag = 's%d' % (abs(hash(src)) % 100000)
    t = re.sub(r'\bid="([^"]+)"', lambda m: 'id="%s-%s"' % (tag, m.group(1)), t)
    t = re.sub(r'url\(#([^)]+)\)', lambda m: 'url(#%s-%s)' % (tag, m.group(1)), t)
    return t


def inline(t):
    """줄 안쪽 서식. 순서가 중요하다. 코드(`)를 먼저 빼내야 그 안의 * 가 안 먹는다."""
    slots = []

    def stash(m):
        slots.append('<code>%s</code>' % H.escape(m.group(1)))
        return '\x00%d\x00' % (len(slots) - 1)

    t = re.sub(r'`([^`]+)`', stash, t)
    # ★ 2026-09-09. HTML 주석은 «안 보이라고» 쓰는 것이다. 그런데 여기서
    #   통째로 이스케이프되어 화면에 글자로 나갔다.
    #   실측: LEDGER.md 의 자동화 표식 <!-- 자동:최종갱신 --> 이 원장 페이지에
    #   그대로 찍혔고 완비 관문이 「원시 HTML 이 글자로 샜다」로 배포를 세웠다.
    #   문서를 쓴 사람 탓이 아니다. 주석은 원래 안 보이는 것이 맞다.
    #   코드 블록은 위에서 이미 빼냈으므로 여기서 지워도 코드 예시는 안전하다.
    t = re.sub(r'<!--.*?-->', '', t, flags=re.S)
    # ★ 2026-09-10. 표 «칸 안의 줄바꿈» 은 마크다운에 문법이 없어 <br> 로 쓴다.
    #   그게 표준 표기이고 lab 문서가 실제로 그렇게 쓴다(terrain-finetune-plan).
    #   그런데 여기서 통째로 이스케이프되어 화면에 «&lt;br&gt;» 이 글자로 찍혔고
    #   완비 관문이 「원시 HTML 이 글자로 샜다」로 배포를 세웠다.
    #   문서를 쓴 사람 탓이 아니다. 렌더러가 그 표기를 지원해야 한다.
    #   다만 «아무 태그나» 통과시키지 않는다. 정확히 <br> 하나만 자리를 빼두고
    #   나머지는 그대로 이스케이프한다. HTML 을 열어 주는 것이 아니다.
    t = re.sub(r'<br\s*/?>', '\x00BRSLOT\x00', t, flags=re.I)
    t = H.escape(t)
    t = t.replace('\x00BRSLOT\x00', '<br>')

    # ★ 2026-09-13. `<https://…>` 는 markdown 의 «자동 링크» 문법이다.
    #   안 다루면 위에서 이스케이프되어 꺾쇠가 화면에 글자로 남는다.
    #   실측: 라이브 `notice-20260912` 에 주소 셋이 꺾쇠째 나왔다.
    #   `tools/md2site.py` 는 이미 다루고 있었다. **같은 결함이 두 렌더러 중
    #   한쪽에만 고쳐져 있었다.** 고칠 때 다른 자리를 안 센 것이다 (철칙 4).
    #   ★ 여기서 한 번 더 틀렸다. 경고를 없애려고 `[^\\s&]` 로 백슬래시를
    #     늘렸더니 그것이 「역슬래시·s·& 가 아닌 것」이 되어 **`https` 의 `s`
    #     에서 막혔다.** 경고는 사라지고 규칙은 한 번도 안 돌았다.
    #     조용히 안 도는 정규식이 이 저장소의 단골이다. 그래서 아래 _selftest
    #     가 이 줄을 «알려진 답» 으로 매번 시험한다.
    t = re.sub(r'&lt;(https?://[^\s&]+?)&gt;',
               lambda m: '<a href="%s" target="_blank" rel="noopener">%s</a>'
               % (m.group(1), m.group(1)), t)

    # [[문서]]: 볼트 내부 링크. 우리 사이트에 같은 문서가 있으면 **진짜 링크로** 바꾼다.
    # 없으면 회색 칩으로만 남긴다 (죽은 링크를 만들지 않는다).
    def vault(m):
        name, desc = m.group(1), (m.group(2) or '')
        page = VAULT_PAGES.get(name)
        if page:
            return '<a href="%s">%s</a>%s' % (page, H.escape(LABELS.get(name, name)),
                                              ' <span class="vlink">%s</span>' % desc if desc else '')
        return '<span class="vlink">%s%s</span>' % (name, '<i>%s</i>' % desc if desc else '')

    t = re.sub(r'\[\[([^\]]+)\]\](?:\(([^)]*)\))?', vault, t)

    # ![alt](경로): 이미지. **링크 규칙보다 먼저** 처리해야 한다(안 그러면 [alt](..) 로 먹힌다).
    #   왜 넣었나. 이게 없어서 «시각 증거» 페이지에 이미지가 글자 그대로 나갔다(2026-08-12).
    #   md 는 docs/research/ 기준이라 경로가 ../assets/... 인데, 웹 페이지는 루트에 놓이므로
    #   앞의 ../ 를 떼어 assets/... 로 바꾼다.
    def _img(m):
        alt, src = m.group(1), m.group(2)
        src = re.sub(r'^(\.\./)+', '', src)
        cap = ('<figcaption>%s</figcaption>' % alt) if alt.strip() else ''
        # YouTube 링크는 임베드로. 남의 저작물(예: Unitree 공식 홍보 영상)은 파일 재호스팅이
        # 저작권 문제라서, 공식 채널 스트리밍 임베드가 «재생되면서 합법»인 유일한 경로다.
        yt = re.match(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{6,})', src)
        if yt:
            return ('<figure class="mdimg mdvid"><iframe '
                    'src="https://www.youtube-nocookie.com/embed/%s" title="%s" '
                    'style="width:100%%;aspect-ratio:16/9;border:0;display:block" '
                    'loading="lazy" allow="fullscreen" allowfullscreen></iframe>%s</figure>'
                    % (yt.group(1), H.escape(alt), cap))
        # 영상도 같은 문법으로 받는다. 링크만 적어두면 아무도 안 눌러본다.
        # 페이지에서 바로 재생되어야 «본다»가 된다.
        if src.lower().endswith(('.mp4', '.webm', '.mov')):
            return ('<figure class="mdimg mdvid">'
                    '<video controls muted playsinline preload="metadata" src="%s"></video>'
                    '%s</figure>' % (src, cap))
        # ★ 2026-09-13. 토큰을 쓰는 SVG 를 «본문에 넣는» 길도 해 봤다.
        #   색은 살지만 셋이 나빠졌다.
        #     · 정본 한 장이 167 KB -> 869 KB
        #     · 검색 색인에 도해 안 «좌표와 글자» 가 들어가 검색이 흐려진다
        #     · 빌드가 10분을 넘겼다
        #   그래서 `<img>` 로 두고 **SVG 파일 자체를 자립시킨다**
        #   (`tools/svg_selfcontained.py`). 파일 안에 팔레트를 넣으면
        #   격리 문서여도 색이 산다.
        return ('<figure class="mdimg"><img src="%s" alt="%s" loading="lazy">%s</figure>'
                % (src, alt, cap))

    t = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)\)', _img, t)
    t = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
    # 사이트 내부 상대 링크: 같은 폴더의 다른 문서로 이어준다 (죽은 링크는 만들지 않는다)
    t = re.sub(r'\[([^\]]+)\]\((?!https?://)([A-Za-z0-9._/-]+\.html(?:#[\w-]+)?)\)',
               r'<a href="\2">\1</a>', t)

    # .md 링크: 그 문서가 웹에 게시돼 있으면 «진짜 링크»로, 아니면 «글자»로.
    #   2026-08-27 이전에는 여기서 아무것도 안 해서 `[문구](경로.md)` 가
    #   마크다운 원문 그대로 화면에 나갔다. 배포본 10개 · 36곳.
    def _mdlink(m):
        label, target = m.group(1), m.group(2)
        page = mdlinks.resolve(target)
        if page:
            return '<a href="%s">%s</a>' % (page, label)
        return '<span class="vlink">%s<i>%s</i></span>' % (label, H.escape(target))

    t = re.sub(r'\[([^\]]+)\]\((?!https?://)([A-Za-z0-9._/#-]+\.md(?:#[\w.-]+)?)\)',
               _mdlink, t)

    # ★ 2026-09-09. 바로 위에서 «.md 만» 처리했다. 그래서 웹에 없는 다른 파일을
    #   가리키는 링크는 여전히 원문 그대로 화면에 나갔다. 실측:
    #     [`sim/eval/render_capture.py`](../../sim/eval/render_capture.py)
    #   2026-08-27 에 고친 것과 «같은 부류» 인데 확장자만 다르다. 확장자를 하나씩
    #   더하면 다음번에 또 다른 것이 샌다. 여기까지 살아남은 링크는 전부
    #   «웹에 없는 대상» 이므로 부류로 막는다. 글자는 살리고 주소는 옅게 보인다.
    t = re.sub(r'\[([^\]\n]+)\]\((?!https?://|#)([^)\s]+)\)',
               lambda m: '<span class="vlink">%s<i>%s</i></span>'
               % (m.group(1), H.escape(m.group(2))), t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<![*\w])\*([^*\n]+)\*(?!\*)', r'<i>\1</i>', t)
    t = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', t)
    for i, s in enumerate(slots):
        t = t.replace('\x00%d\x00' % i, s)
    return t


def _cell(t):
    return inline(t.strip())


def _cells(row):
    r"""표 한 줄을 칸으로 쪼갠다. `|` 를 글자로 쓴 칸을 깨뜨리지 않는다.

    ★ 2026-08-27 팀장 지적: 「일부 표 틀어진 거」.
      오현민의 ROS 2 노트 1편에 이런 줄이 있었다.

          | `\|` | 파이프. 앞 명령의 출력을 뒤 명령의 입력으로 넘김 |

      **오현민이 맞게 쓴 것이다.** 마크다운에서 표 안의 `|` 는 `\|` 로 적는다.
      깨뜨린 쪽은 우리 렌더러였다. `row.split('|')` 로 무조건 쪼개서
      2칸짜리 표에 3칸이 들어갔고, 그 줄만 어긋난 채 웹에 나갔다.

      고치는 방식이 중요하다. 그 한 줄을 손보면 다음에 누가 또 `|` 를 쓸 때
      똑같이 깨진다. **쪼개는 규칙 자체를 고친다** (커널 2-2: 부류로 막는다).

      두 가지를 함께 지킨다.
        1) `\|`  -> 칸 구분이 아니다. 글자 `|` 로 되돌린다
        2) `` `a|b` `` -> 코드 안의 `|` 도 칸 구분이 아니다
    """
    # ★ 2026-09-09. 백틱이 «홀수» 면 코드 스팬으로 치지 않는다.
    #   한 줄 안에서 열리고 안 닫힌 백틱은 거의 언제나 오타다. 그것을 코드
    #   시작으로 믿으면 뒤에 오는 | 가 전부 코드 안으로 먹혀 칸이 통째로 사라진다.
    #   실측: decisions/20260828-doc-graph.md 의 네 줄이 그랬다. 원문은
    #   `NAV · 실기 항 에서 끊겨 있었고 3칸 표가 2칸으로 렌더돼 「성격」 열이
    #   화면에서 사라졌다. 오류도 안 났다. 조용히 내용만 없어지는 부류다.
    #   짝이 안 맞으면 백틱을 글자로 보고 칸이라도 지킨다.
    code_ok = (row.count('`') % 2 == 0)
    out, buf, i, tick = [], [], 0, False
    while i < len(row):
        c = row[i]
        if c == '\\' and i + 1 < len(row) and row[i + 1] == '|':
            buf.append('|')                 # 글자로 쓴 파이프
            i += 2
            continue
        if c == '`' and code_ok:
            tick = not tick                 # 코드 스팬 안팎
        if c == '|' and not tick:
            out.append(''.join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    out.append(''.join(buf))
    # 양 끝의 빈 칸(줄 앞뒤의 `|`)을 떤다
    if out and not out[0].strip():
        out = out[1:]
    if out and not out[-1].strip():
        out = out[:-1]
    return out


def _kat_cells():
    """★ 답을 아는 입력으로 쪼개는 규칙을 먼저 시험한다."""
    cases = [
        ('| a | b |', ['a', 'b']),
        ('| `\\|` | 파이프 |', ['`|`', '파이프']),          # 실제로 깨졌던 줄
        ('| `a|b` | 코드 안 |', ['`a|b`', '코드 안']),      # 코드 스팬 안의 |
        ('| a | b | c |', ['a', 'b', 'c']),
    ]
    for row, want in cases:
        got = [c.strip() for c in _cells(row.strip().strip())]
        if got != want:
            return False, '%r -> %r (기대 %r)' % (row, got, want)
    return True, ''


# ────────────────────────── raw HTML 통과 ──────────────────────────
#
# ★ 2026-09-03. 여기가 없어서 브레인스토밍 정본의 인라인 SVG 두 장이
#   글자로 노출됐고 [3.45] 브랜드 관문이 토큰밖 hex 를 19 에서 99 로 셌다.
#   변환기가 못 다루는 것을 «본문» 으로 흘려보내면 화면에 소스가 찍힌다.
#
#   임의 HTML 을 열지 않는다. 여는 것은 둘뿐이다.
#     <svg> ... </svg>   도식. 그대로 통과
#     <!-- ... -->       표식 줄. 지운다 (제출본 제외 마커 등)
#   그 밖의 태그는 지금까지처럼 이스케이프된다.

_SVG_OPEN = re.compile(r'^\s*<svg[\s>]')
_HTML_COMMENT = re.compile(r'^\s*<!--.*-->\s*$')
# 통과시키더라도 실행되는 것은 막는다. 도식에 script 나 이벤트 핸들러가 있을 이유가 없다.
_SVG_UNSAFE = re.compile(r'<\s*script|\son[a-z]+\s*=|javascript:', re.I)

# ★ 도식이 hex 를 그대로 들고 있으면 다크에서 안 따라온다. 밝은 종이색 상자가
#   어두운 화면에 그대로 남는다. 그래서 통과시킬 때 브랜드 hex 를 토큰 참조로 바꾼다.
#   md 원본은 안 건드린다. PDF 파이프라인이 그 원본을 쓰기 때문이다.
#   여기 없는 hex 는 그대로 남고 브랜드 관문이 잡는다. 규칙을 넓히지 않는다.
#   출처 = team_access.py 의 :root (밝은 판)
_SVG_TOKEN = {
    '#f6f5f1': 'var(--paper)',    '#eeece6': 'var(--paper-2)',
    '#161c26': 'var(--ink)',      '#4a5566': 'var(--ink-2)',
    '#7c8798': 'var(--ink-3)',    '#d9d6cd': 'var(--rule)',
    '#0e7a6e': 'var(--dim)',      '#e0f0ed': 'var(--dim-soft)',
    '#0b6459': 'var(--dim-ink)',  '#a86a08': 'var(--note)',
    '#fbf0dc': 'var(--note-soft)', '#8a5600': 'var(--note-ink)',
    '#a3342a': 'var(--stop)',     '#fbe9e7': 'var(--stop-soft)',
    # 흰 글씨는 진한 면 위에 얹힌 것이다. 다크에서 그 면이 밝아지므로
    # 종이색을 따라가야 대비가 산다.
    '#ffffff': 'var(--paper)',
}
_SVG_HEX = re.compile(r'#[0-9a-fA-F]{6}')


def _svg_tokenize(block):
    return _SVG_HEX.sub(lambda m: _SVG_TOKEN.get(m.group(0).lower(), m.group(0)), block)


def _svg_block(lines, i, n):
    """<svg> 블록을 통째로 떼어 낸다. 못 떼면 (None, i) 를 준다.

    닫는 태그가 없으면 통과시키지 않는다. 반쪽짜리를 흘리면 그 뒤 문서가
    통째로 SVG 안으로 빨려 들어가 조용히 사라진다.
    """
    # ★ 2026-09-10. 표 칸 줄바꿈 <br> 은 렌더하고 그 밖의 태그는 이스케이프한다.
    if inline("가<br>나") != "가<br>나":
        return False, "표 칸 줄바꿈 <br> 이 글자로 샌다: %r" % inline("가<br>나")
    if "<script>" in inline("<script>x</script>"):
        return False, "<br> 말고 다른 태그까지 열렸다"
    j = i
    while j < n and '</svg>' not in lines[j]:
        j += 1
    if j >= n:
        return None, i
    block = '\n'.join(lines[i:j + 1])
    if _SVG_UNSAFE.search(block):
        return None, i
    return _svg_tokenize(block), j + 1


# ────────────────────────── 블록 ──────────────────────────

def render(md):
    lines = md.split('\n')
    out, i, n = [], 0, len(lines)
    sec = 0

    while i < n:
        L = lines[i]

        # ── 인라인 SVG (도식) ──
        if _SVG_OPEN.match(L):
            block, j = _svg_block(lines, i, n)
            if block is not None:
                # 넓은 도식이 본문을 옆으로 밀지 않게 자기 상자 안에서 스크롤한다.
                out.append('<figure class="mdsvg">%s</figure>' % block)
                i = j
                continue
            # 닫는 태그가 없거나 안전하지 않으면 지금까지처럼 본문으로 떨어뜨린다.

        # ── 표식 주석 줄 ──
        if _HTML_COMMENT.match(L):
            i += 1
            continue

        # ── 코드 블록 ──
        if L.startswith('```'):
            lang = L[3:].strip()
            body, i = [], i + 1
            while i < n and not lines[i].startswith('```'):
                body.append(lines[i]); i += 1
            i += 1
            # ★ 강조는 hl.py 가 한다. 이스케이프를 먼저 하고 그 위에 span 만 씌우므로
            #   오탐이 나도 코드 자체는 절대 깨지지 않는다.
            out.append('<div class="cb"><div class="cb-h">%s%s</div><pre>%s</pre></div>'
                       % (H.escape(hl.label(lang)), _COPY_BTN,
                          hl.render('\n'.join(body), lang)))
            continue

        # ── 표 ──
        if L.strip().startswith('|') and i + 1 < n and re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):
            head = _cells(L.strip())
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append(_cells(lines[i].strip()))
                i += 1
            # 칸 수가 머리와 다르면 채우거나 남는 것을 마지막 칸에 붙인다.
            # 이렇게 하면 «표가 어긋나 보이는» 일이 없다. 내용도 안 사라진다.
            w = len(head)
            fixed = []
            for r in rows:
                if len(r) < w:
                    r = r + [''] * (w - len(r))
                elif len(r) > w:
                    r = r[:w - 1] + [' | '.join(r[w - 1:])]
                fixed.append(r)
            out.append('<div class="tw"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                       % (''.join('<th>%s</th>' % _cell(c) for c in head),
                          ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % _cell(c) for c in r)
                                  for r in fixed)))
            continue

        # ── 인용 ──
        if L.startswith('>'):
            body = []
            while i < n and lines[i].startswith('>'):
                body.append(lines[i][1:].lstrip()); i += 1
            out.append('<blockquote>%s</blockquote>' % _para('\n'.join(body)))
            continue

        # ── 제목 ──
        m = re.match(r'^(#{1,4})\s+(.*)$', L)
        if m:
            lv, txt = len(m.group(1)), m.group(2).strip()
            if lv == 1:
                out.append('<!--H1:%s-->' % txt)              # 표지에서 따로 쓴다
            elif lv == 2:
                sec += 1
                # ★ 2026-09-08 감사 F-07. 절 id 를 순번(sN)으로만 달았더니 원본이
                #   쓴 «사람 번호» 가 사라졌다. md 안의 [평가 파이프라인](…#5-3)
                #   은 «## 5-3.» 절을 정확히 가리키는데 웹에서는 죽은 앵커가 됐다.
                #   링크가 틀린 게 아니라 우리가 번호를 버린 것이다.
                #   제목 앞 번호(5 · 5-3 · 5.3)를 두 번째 앵커로 함께 단다.
                num = re.match(r'\s*([0-9]+(?:[-.][0-9]+)*)\s*[.·]?\s', txt)
                extra = ''
                if num:
                    nid = num.group(1)
                    if nid != 's%d' % sec:
                        extra = '<span id="%s"></span>' % nid
                out.append('<section id="s%d">%s<h2>%s</h2>'
                           % (sec, extra, inline(txt)))
                out.append('\x01')                             # 섹션 닫기 표시용
            else:
                out.append('<h%d>%s</h%d>' % (lv, inline(txt), lv))
            i += 1
            continue

        # ── 구분선 ──
        if re.match(r'^\s*---+\s*$', L):
            i += 1
            continue

        # ── 목록 ──
        if re.match(r'^\s*([-*]|\d+\.)\s+', L):
            ordered = bool(re.match(r'^\s*\d+\.\s', L))
            items, base = [], len(L) - len(L.lstrip())
            while i < n and (re.match(r'^\s*([-*]|\d+\.)\s+', lines[i])
                             or (lines[i].strip() and lines[i].startswith(' ' * (base + 2)))):
                if re.match(r'^\s*([-*]|\d+\.)\s+', lines[i]):
                    ind = len(lines[i]) - len(lines[i].lstrip())
                    txt = re.sub(r'^\s*([-*]|\d+\.)\s+', '', lines[i])
                    items.append((ind, txt))
                elif items:                                     # 이어지는 줄
                    items[-1] = (items[-1][0], items[-1][1] + ' ' + lines[i].strip())
                i += 1
            out.append(_list(items, base, ordered))
            continue

        # ── 문단 ──
        if L.strip():
            body = []
            while i < n and lines[i].strip() and not re.match(
                    r'^\s*(#{1,4}\s|```|>|\||[-*]\s|\d+\.\s|---+\s*$)', lines[i]):
                body.append(lines[i]); i += 1
            out.append('<p>%s</p>' % inline(' '.join(body)))
            continue

        i += 1

    # 섹션 닫기: <section 이 새로 열리기 직전에 </section> 을 넣고, 마지막 것은 끝에서 닫는다
    joined = '\n'.join(out).replace('\x01\n', '').replace('\x01', '')
    joined = re.sub(r'(?<!\A)(<section id="s)', r'</section>\n\1', joined)
    if '<section' in joined:
        joined += '\n</section>'
    return joined


def _list(items, base, ordered):
    tag = 'ol' if ordered else 'ul'
    buf, depth = ['<%s>' % tag], base
    for ind, txt in items:
        if ind > depth:
            buf.append('<ul>'); depth = ind
        while ind < depth:
            buf.append('</ul>'); depth -= 2
        buf.append('<li>%s</li>' % inline(txt))
    while depth > base:
        buf.append('</ul>'); depth -= 2
    buf.append('</%s>' % tag)
    return ''.join(buf)


def _para(t):
    """인용 안쪽: 표도 목록도 들어올 수 있다."""
    if re.search(r'^\s*\|', t, re.M):
        return render(t)
    return '\n'.join('<p>%s</p>' % inline(x) for x in t.split('\n\n') if x.strip())


def h1(md):
    m = re.search(r'^#\s+(.*)$', md, re.M)
    return m.group(1).strip() if m else '문서'


def _selftest():
    """알려진 답으로 이 렌더러의 «조용히 안 도는» 규칙을 시험한다.

    2026-09-13 에 자동 링크 규칙이 두 번 안 돌았다. 한 번은 아예 없어서,
    한 번은 경고를 없애려다 정규식을 깨뜨려서. **둘 다 오류를 안 냈다.**
    화면에 꺾쇠가 남았을 뿐이고 그것을 팀장이 봤다.

    그래서 규칙마다 «이렇게 넣으면 이렇게 나와야 한다» 를 못 박는다.
    반환: (통과 여부, [틀린 것])
    """
    bad = []

    def want(src, must_have, must_not, why):
        out = render(src)
        for s in must_have:
            if s not in out:
                bad.append('%s · 있어야 할 것이 없다: %s' % (why, s[:40]))
        for s in must_not:
            if s in out:
                bad.append('%s · 없어야 할 것이 있다: %s' % (why, s[:40]))

    url = 'https://foothold-project.vercel.app/x.html'
    want('<' + url + '>', ['href="' + url + '"'], ['&lt;http'], '자동 링크')
    want('`<' + url + '>` 는 코드', ['<code>'], ['href="' + url + '"'],
         '코드 안의 꺾쇠는 그대로')
    want('[이름](' + url + ')', ['href="' + url + '"', '이름'], ['&lt;http'],
         '보통 링크')
    want('![그림](../assets/visual/a.svg)', ['<img', 'assets/visual/a.svg'],
         ['<svg'], '토큰 없는 그림은 img')
    want('**굵게**', ['<b>굵게</b>'], [], '굵게')
    want('a<br>b', ['<br>'], ['&lt;br&gt;'], '표 안 줄바꿈')
    return (not bad), bad


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ok, why = _selftest()
    print('  자기시험 통과 (규칙 6)' if ok else '  자기시험 실패 %d건' % len(why))
    for w in why:
        print('      ' + w)
    sys.exit(0 if ok else 1)
