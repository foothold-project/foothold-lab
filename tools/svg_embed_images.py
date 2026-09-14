# -*- coding: utf-8 -*-
"""SVG 안의 «바깥 그림 파일» 을 data: URI 로 심는다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (라이브 화면에서 로봇이 빠진 것을 팀장이 잡음)
요지: `<img>` 로 불린 SVG 는 바깥 자원을 못 불러온다. 파일 안에 넣어야 그려진다

## 왜 있나

2026-09-14 팀장 지적: 「`보상 몸이 어디에 걸리나` 이거 그림 로봇 빠진거 안보이냐?」

맞았다. `eval-v2-fig08.svg` 안에 이렇게 들어 있었다.

    <image x="0" y="52" width="380" height="300" href="embedded-3d60e41890a7.png"/>

**브라우저는 `<img src="...svg">` 로 불린 SVG 안에서 바깥 자원을 안 불러온다.**
보안 규칙이고 오류도 안 낸다. 그 자리는 그냥 빈 채로 그려진다.

내가 이것을 못 본 까닭이 명확하다. **SVG 를 브라우저에서 «직접 열어» 보고
「로봇이 보인다」고 했다.** 직접 열면 문서라서 바깥 자원을 불러온다.
페이지에서는 `<img>` 라 안 불러온다. **같은 파일이 두 자리에서 다르게 보인다.**

## 무엇을 하나

`<image href="파일.png">` 를 그 파일의 base64 data: URI 로 바꾼다.
파일이 커지지만 «보이는 것» 이 먼저다.

## 쓰는 법

    python tools/svg_embed_images.py <svg 폴더>            보여주기만
    python tools/svg_embed_images.py --write <svg 폴더>
    python tools/svg_embed_images.py --check <svg 폴더>    관문 (바깥 참조가 있으면 실패)
"""
import base64
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

MIME = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.gif': 'image/gif', '.webp': 'image/webp'}
EXT = re.compile(r'<(image|use)\b[^>]*?(?:xlink:)?href="([^"]+)"', re.I)


def outside(text):
    """바깥 자원을 가리키는 참조 목록. `data:` 와 `#조각` 은 뺀다."""
    out = []
    for m in EXT.finditer(text):
        h = m.group(2)
        if h.startswith(('data:', '#')):
            continue
        out.append((m.group(1), h))
    return out


def embed(text, base):
    """바꾼 글, [(참조, 결과)]."""
    log = []

    def sub(m):
        whole, tag, href = m.group(0), m.group(1), m.group(2)
        if href.startswith(('data:', '#')):
            return whole
        p = os.path.join(base, href.split('?')[0].replace('/', os.sep))
        ext = os.path.splitext(p)[1].lower()
        if not os.path.isfile(p) or ext not in MIME:
            log.append((href, '못 심음 (파일 없음 또는 모르는 형식)'))
            return whole
        raw = io.open(p, 'rb').read()
        uri = 'data:%s;base64,%s' % (MIME[ext],
                                     base64.b64encode(raw).decode('ascii'))
        log.append((href, '심음 %.0f KB' % (len(raw) / 1024)))
        return whole.replace(href, uri)

    return EXT.sub(sub, text), log


def check(root, say=print):
    bad = 0
    n = 0
    for f in sorted(os.listdir(root)):
        if not f.endswith('.svg'):
            continue
        n += 1
        t = io.open(os.path.join(root, f), encoding='utf-8').read()
        ext = outside(t)
        if ext:
            bad += 1
            say('      [!] %s 가 바깥 자원을 가리킵니다: %s'
                % (f, ' · '.join('%s -> %s' % (a, b[:40]) for a, b in ext)))
    say('  SVG %d장 검사 · 바깥 자원을 가리키는 것 %d장' % (n, bad))
    if bad:
        say('      `<img>` 로 불린 SVG 는 바깥 자원을 안 불러옵니다 (그 자리가 빕니다)')
        say('      `python tools/svg_embed_images.py --write <폴더>` 로 심으십시오')
    return bad == 0


def _selftest():
    """알려진 답."""
    import tempfile
    d = tempfile.mkdtemp()
    png = (b'\x89PNG\r\n\x1a\n' + b'\x00' * 20)
    io.open(os.path.join(d, 'a.png'), 'wb').write(png)
    cases = [
        ('바깥 png', '<svg><image href="a.png"/></svg>', 1, True),
        ('data URI', '<svg><image href="data:image/png;base64,AA"/></svg>', 0, False),
        ('조각 참조', '<svg><use href="#g1"/></svg>', 0, False),
        ('없음', '<svg><rect/></svg>', 0, False),
    ]
    ok = 0
    for name, svg, want, should in cases:
        got = len(outside(svg))
        new, log = embed(svg, d)
        did = ('base64' in new) and should
        good = (got == want) and (did == should)
        ok += good
        print('  %s %-10s 바깥참조 %d (기대 %d) · 심음 %s'
              % ('OK ' if good else '[X]', name, got, want, did))
    print('  %d/%d' % (ok, len(cases)))
    return ok == len(cases)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--selftest' in sys.argv:
        return 0 if _selftest() else 1
    if not args:
        print('  쓰는 법: python tools/svg_embed_images.py [--write|--check] <폴더>')
        return 2
    root = args[0]
    if '--check' in sys.argv:
        return 0 if check(root) else 1
    write = '--write' in sys.argv
    n = 0
    for f in sorted(os.listdir(root)):
        if not f.endswith('.svg'):
            continue
        p = os.path.join(root, f)
        t = io.open(p, encoding='utf-8').read()
        if not outside(t):
            continue
        new, log = embed(t, root)
        for href, how in log:
            print('  %-28s %-34s %s' % (f, href[:34], how))
        if write and new != t:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(new)
            back = io.open(p, encoding='utf-8').read()
            left = outside(back)
            if left:
                print('      [!] 아직 바깥 참조가 남았습니다: %s' % left)
            else:
                print('      %s 크기 %.0f KB' % (f, len(back) / 1024))
        n += 1
    print('  바깥 자원을 가진 SVG %d장%s'
          % (n, '' if write else '   (--write 를 줘야 씁니다)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
