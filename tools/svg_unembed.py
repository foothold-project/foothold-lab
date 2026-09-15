# -*- coding: utf-8 -*-
"""SVG 안에 base64 로 박힌 그림을 «파일로» 빼낸다.

**왜.** 정본 페이지가 약 2 MB 였고 브라우저가 두 번 얼었다. 재 보니 그림이
1,843 KB 였고, 그중 둘이 SVG 인데 **파일의 95% 가 안에 박힌 PNG** 였다.

    eval-v2-reward-map.svg   263 KB   그중 base64 250 KB
    eval-v2-fig08.svg        262 KB   같음

벡터인 줄 알았는데 사진을 품고 있었다. 박혀 있으면 셋이 나쁘다.

  · 브라우저가 따로 캐시하지 못한다. 그림을 고칠 때마다 사진도 다시 받는다
  · base64 는 원본보다 33% 크다
  · 같은 사진이 여러 그림에 들어가면 그만큼 곱으로 늘어난다

빼내면 `<image href="...">` 가 되어 보통 그림처럼 캐시되고 lazy 도 먹는다.

**그림 자체는 안 건드린다.** 바이트를 그대로 꺼내 파일로 쓴다. 화질이
바뀌면 그건 다른 작업이다.
"""
import argparse
import base64
import hashlib
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
DEFAULT_DIR = os.path.join(LAB, 'docs', 'assets', 'visual')

EXT = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp',
       'image/gif': '.gif'}

# `xlink:href` 도 쓴다. 둘 다 받는다.
EMBED = re.compile(
    r'(?P<attr>(?:xlink:)?href)="data:(?P<mime>image/[a-z+]+);base64,'
    r'(?P<b64>[A-Za-z0-9+/=\s]+)"')


def unembed(text, out_dir, stem):
    """반환: (새 본문, [(파일명, 바이트수)]). 뺄 것이 없으면 (None, [])."""
    made = []

    def swap(m):
        mime = m.group('mime')
        ext = EXT.get(mime)
        if not ext:
            return m.group(0)                # 모르는 형식은 그대로 둔다
        raw = base64.b64decode(re.sub(r'\s+', '', m.group('b64')))
        # 이름은 «내용» 에서 만든다. 같은 그림이 여러 그림에 있으면 한 파일로
        # 모인다. 그러면 브라우저가 한 번만 받는다.
        # ★ 이름에 «문서 이름» 을 넣지 않는다. 실측: 같은 187 KB PNG 가
        #   `eval-v2-fig08` 과 `eval-v2-reward-map` 두 SVG 에 각각 박혀
        #   있었다. 문서 이름을 붙이면 같은 그림이 두 파일로 나뉘어
        #   브라우저가 두 번 받는다. 내용 해시만 쓰면 한 파일로 모인다.
        tag = hashlib.sha256(raw).hexdigest()[:12]
        name = 'embedded-%s%s' % (tag, ext)
        path = os.path.join(out_dir, name)
        if not os.path.isfile(path):
            io.open(path, 'wb').write(raw)
            made.append((name, len(raw)))
        return '%s="%s"' % (m.group('attr'), name)

    new = EMBED.sub(swap, text)
    return (new if new != text else None), made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=DEFAULT_DIR)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()

    if not os.path.isdir(a.dir):
        raise SystemExit('  [!] 폴더가 없습니다: %s' % a.dir)

    files = sorted(f for f in os.listdir(a.dir) if f.lower().endswith('.svg'))
    touched, saved, pulled = 0, 0, 0

    for f in files:
        p = os.path.join(a.dir, f)
        t = io.open(p, encoding='utf-8').read()
        if 'base64,' not in t:
            continue
        before = len(t.encode('utf-8'))
        new, made = unembed(t, a.dir, os.path.splitext(f)[0])
        if new is None:
            continue
        after = len(new.encode('utf-8'))
        touched += 1
        saved += before - after
        pulled += len(made)
        print('  %-28s %6.0f KB -> %5.0f KB · 뺀 그림 %d'
              % (f, before / 1024.0, after / 1024.0, len(made)))
        for n, sz in made:
            print('        %-34s %6.0f KB' % (n, sz / 1024.0))
        if a.write:
            io.open(p, 'w', encoding='utf-8', newline='\n').write(new)

    if not files:
        raise SystemExit('  [!] SVG 가 한 장도 없습니다. 통과로 안 읽습니다')

    print('  ---')
    print('  손댄 SVG %d장 · 뺀 그림 %d개 · SVG 에서 줄인 양 %.0f KB'
          % (touched, pulled, saved / 1024.0))
    if not a.write:
        print('  (--write 를 주면 씁니다)')


if __name__ == '__main__':
    main()
