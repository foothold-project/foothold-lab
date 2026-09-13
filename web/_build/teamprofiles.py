# -*- coding: utf-8 -*-
"""팀원 개인 소개 페이지 + 표지 «팀» 카드에서 그 페이지로 링크.

  왜 이렇게 하나 (팀장 지시, 2026-08-24):
    처음엔 표지에서 카드를 펼치는(<details>) 방식으로 만들었다. 팀장이
    «펼치기 말고 개인 페이지로 넘어가는 방향»으로 바꾸라고 했다. 개인 소개는
    각자가 자기 방식으로 표현하는 것이라 표지에 접어 넣기보다 자기 페이지를
    갖는 것이 맞다.

  원본 두 갈래 (팀원이 고른다)
    1. 마크다운  02_team/profiles/{슬러그}.md
       → 사이트 공통 문서 틀에 얹어 team-{슬러그}.html 로 생성한다.
    2. 통째로 만든 사이트  02_team/profiles/{슬러그}/index.html (+ css·이미지)
       → 그 폴더를 team-{슬러그}/ 로 그대로 복사한다. 본인이 만든 모양을 지킨다.

  프로필이 없는 사람의 카드는 링크를 걸지 않는다. 죽은 링크를 만들지 않는다.

  ★ 이 단계는 관문·주입 단계보다 «앞»에서 돌아야 한다. 생성된 페이지도
    다크모드·파비콘·문체 검사·검색 색인을 받아야 하기 때문이다.
"""
import io
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdpage

MARK_A = '<!--teamprofiles:v2-->'
MARK_B = '<!--/teamprofiles-->'

# 이름 → 슬러그. inbox 폴더 이름과 맞춘다(팀원이 헷갈리지 않게).
SLUG = {
    '오흥재': 'lead',
    '임석헌': 'lim',
    '맹라현': 'meang',
    '이민우': 'lee',
    '오현민': 'oh',
}

CSS = MARK_A + '''<style>
.team .tm .n a{color:inherit;text-decoration:none;border-bottom:1px solid var(--rule)}
.team .tm .n a:hover{border-bottom-color:var(--dim);color:var(--dim)}
.team .tm .more{margin-top:.5rem;font-size:.66rem;font-weight:800;letter-spacing:.02em;
  color:var(--dim)}
.team .tm .more a{color:inherit;text-decoration:none}
.team .tm .more a:hover{text-decoration:underline}
</style>''' + MARK_B


def _sources(vault):
    """{슬러그: ('md', 경로)} 또는 {슬러그: ('site', 폴더)}"""
    root = os.path.join(__import__('roots').proj(), '02_team', 'profiles')
    out = {}
    if not os.path.isdir(root):
        return out, root
    for e in sorted(os.listdir(root)):
        p = os.path.join(root, e)
        if e == 'README.md':
            continue
        if e.endswith('.md') and os.path.isfile(p):
            if io.open(p, encoding='utf-8').read().strip():
                out[e[:-3]] = ('md', p)
        elif os.path.isdir(p) and os.path.exists(os.path.join(p, 'index.html')):
            out[e] = ('site', p)
    return out, root


def _name_of(slug):
    for k, v in SLUG.items():
        if v == slug:
            return k
    return slug


def _role_of(vault, name):
    """표지 카드에서 역할·한 줄 강점을 읽어 개인 페이지 머리말에 쓴다."""
    t = io.open(os.path.join(vault, 'index.html'), encoding='utf-8').read()
    m = re.search(r'<div class="r">([^<]*)</div><div class="n">(?:<a[^>]*>)?'
                  + re.escape(name) + r'(?:</a>)?</div>\s*<div class="s">(.*?)</div>', t, re.S)
    if not m:
        return '', ''
    return m.group(1).strip(), re.sub(r'<br\s*/?>', ' · ', m.group(2)).strip()


def main(vault, pages=None):
    idx = os.path.join(vault, 'index.html')
    if not os.path.exists(idx):
        print('  index.html 없음, 건너뜀')
        return True, []

    srcs, root = _sources(vault)
    made = []
    import docs_pages

    for slug, (kind, path) in sorted(srcs.items()):
        name = _name_of(slug)
        role, strength = _role_of(vault, name)
        if kind == 'md':
            md = io.open(path, encoding='utf-8').read().strip()
            md = re.sub(r'\A#\s+[^\n]*\n+', '', md)          # 카드에 이름이 이미 있다
            body = mdpage.render(md)
            lede = strength or '팀원 소개'
            html = docs_pages.shell(
                name, 'Team · 팀원 소개', lede, body,
                [('역할', role or '-'), ('팀', 'FOOTHOLD')],
                'Team · %s' % name,
                home_href='index.html#team', home_label='← 표지로')
            # 증거 범례(확인됨·추측·미측정)는 연구 문서용이다. 자기소개에는 뜻이 없다.
            html = re.sub(r'\s*<div class="evlegend">.*?</div>\n', '\n', html, flags=re.S)
            out = 'team-%s.html' % slug
            io.open(os.path.join(vault, out), 'w', encoding='utf-8', newline='\n').write(html)
            made.append(out)
        else:
            # 본인이 만든 사이트를 그대로 옮긴다. 손대지 않는다.
            dst = os.path.join(vault, 'team-%s' % slug)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(path, dst)
            made.append('team-%s' % slug)

    # 표지 카드: 이름을 링크로 + «소개 보기 →»
    t = io.open(idx, encoding='utf-8').read()
    t = re.sub(re.escape(MARK_A) + r'.*?' + re.escape(MARK_B), '', t, flags=re.S)
    # v1 (펼치기) 잔재 제거
    t = re.sub(r'<!--teamprofiles:v1-->.*?<!--/teamprofiles-->', '', t, flags=re.S)
    if '</head>' in t:
        t = t.replace('</head>', CSS + '</head>', 1)

    m = re.search(r'<div class="team">(.*?)\n</div>', t, re.S)
    if not m:
        print('  [!] 표지 팀 섹션을 찾지 못했습니다.')
        return False, []
    block = m.group(1)

    # v1 의 <details> 판을 원래 div 로 되돌린다
    block = re.sub(
        r'<details class="tm([^"]*?)(?: has-bio)?"[^>]*>\s*<summary>(.*?)</summary>.*?</details>',
        lambda x: '<div class="tm%s">%s</div>' % (x.group(1), x.group(2)),
        block, flags=re.S)
    # 이전 실행이 남긴 링크·«소개 보기» 제거 (평문 이름으로 되돌림)
    block = re.sub(r'<div class="n"><a href="[^"]*">([^<]*)</a></div>',
                   r'<div class="n">\1</div>', block)
    block = re.sub(r'\s*<div class="more">.*?</div>', '', block, flags=re.S)

    linked = []
    for name, slug in SLUG.items():
        if slug not in srcs:
            continue
        href = ('team-%s/index.html' % slug) if srcs[slug][0] == 'site' else ('team-%s.html' % slug)
        old = '<div class="n">%s</div>' % name
        if old not in block:
            print('  [!] 카드에서 %s 을 찾지 못했습니다.' % name)
            continue
        block = block.replace(old, '<div class="n"><a href="%s">%s</a></div>' % (href, name), 1)
        linked.append((name, slug, href))

    # 각 카드 끝에 «소개 보기 →» 를 붙인다 (카드 경계는 태그를 세어 찾는다)
    for name, slug, href in linked:
        block = _append_more(block, name, href)

    t = t[:m.start(1)] + block + t[m.end(1):]
    io.open(idx, 'w', encoding='utf-8', newline='\n').write(t)

    if pages is not None:
        for f in made:
            if f not in pages:
                pages.append(f)

    miss = [n for n in SLUG if SLUG[n] not in srcs]
    print('  개인 페이지 %d개 생성 (%s)'
          % (len(made), ', '.join('%s→%s' % (n, h) for n, _, h in linked) or '없음'))
    if miss:
        print('  아직 없음: %s   ← %s' % (', '.join(miss), root))
    return True, made


def _append_more(block, name, href):
    """이름이 든 카드의 닫는 </div> 직전에 «소개 보기» 를 넣는다."""
    key = '<div class="n"><a href="%s">%s</a></div>' % (href, name)
    k = block.find(key)
    if k < 0:
        return block
    s = block.rfind('<div class="tm', 0, k)
    if s < 0:
        return block
    gt = block.index('>', s)
    depth, j = 1, gt + 1
    while depth and j < len(block):
        nd = block.find('<div', j)
        cd = block.find('</div>', j)
        if cd < 0:
            break
        if 0 <= nd < cd:
            depth += 1
            j = nd + 4
        else:
            depth -= 1
            j = cd + 6
    ins = j - 6                                        # 카드의 닫는 </div> 앞
    more = '\n    <div class="more"><a href="%s">소개 보기 →</a></div>' % href
    return block[:ins] + more + block[ins:]
