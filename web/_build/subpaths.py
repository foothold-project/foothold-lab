# -*- coding: utf-8 -*-
"""하위 폴더 페이지의 상대경로를 고친다.

★ 2026-08-27 감사에서 나온 것.
  `team-meang/index.html` 의 링크 12개가 전부 404 였다. 전역 상단바와 브랜드 자산이
  «최상위 기준» 경로로 주입되는데, 그 페이지는 한 단계 아래 폴더에 있다.
  사이트 전체 깨진 링크 12개가 전부 이 한 파일에서 나왔다.

  그런데도 아무도 몰랐다. `linkcheck.py` 가 `os.listdir` 로 **최상위만** 봤기 때문이다.
  8/26 에 「맹라현님 제출분을 올렸습니다」라고 공지까지 나간 페이지다.

  이 단계는 그 자리에서 고치고, linkcheck 는 하위 폴더까지 보도록 함께 고쳤다.
"""
import io
import os
import re

# href="X" / src="X" 에서 X 가 상대경로(프로토콜·앵커·절대경로 아님)인 것
ATTR = re.compile(r'(href|src)="(?!https?:|//|/|#|mailto:|data:)([^"]+)"')


def fix_page(path, root, depth):
    """root 에 있는 파일을 가리키는 상대경로 앞에 ../ 를 붙인다."""
    up = '../' * depth
    t = io.open(path, encoding='utf-8', newline=None).read()
    changed = []

    def one(m):
        attr, target = m.group(1), m.group(2)
        if target.startswith('../') or target.startswith('./'):
            return m.group(0)
        head = target.split('#', 1)[0].split('?', 1)[0]
        if not head:
            return m.group(0)
        # 자기 폴더 안에 있으면 그대로 둔다
        here = os.path.join(os.path.dirname(path), head)
        if os.path.exists(here):
            # ★ 2026-09-08 감사 F-07. 예외가 하나 있다. 이 페이지 이름이 곧
            #   index.html 이라, 루트 표지를 가리키는 «← 표지로» 가 자기 자신을
            #   가리키는 것으로 보였다. 실측: team-meang/index.html -> index.html#team
            #   이 자기 자신에 #team 이 없어 죽은 앵커가 됐다.
            #   추측으로 «표지 뜻이겠지» 하지 않는다. 앵커가 어느 쪽에 있는지 본다.
            anc = target.split('#', 1)[1] if '#' in target else ''
            if anc and os.path.abspath(here) == os.path.abspath(path):
                mine = io.open(path, encoding='utf-8', errors='replace').read()
                rootf = os.path.join(root, head)
                if ('id="%s"' % anc) not in mine and os.path.exists(rootf):
                    other = io.open(rootf, encoding='utf-8',
                                    errors='replace').read()
                    if ('id="%s"' % anc) in other:
                        changed.append(target)
                        return '%s="%s%s"' % (attr, up, target)
            return m.group(0)
        # 최상위에 있으면 ../ 를 붙인다
        if os.path.exists(os.path.join(root, head)):
            changed.append(target)
            return '%s="%s%s"' % (attr, up, target)
        return m.group(0)

    out = ATTR.sub(one, t)
    if out != t:
        io.open(path, 'w', encoding='utf-8', newline='\n').write(out)
    return changed


def main(site):
    """배포 폴더의 하위 폴더 html 을 전부 훑는다."""
    fixed = 0
    pages = 0
    for dirpath, dirnames, files in os.walk(site):
        dirnames[:] = [d for d in dirnames if d not in ('assets', '_build', '_src')]
        rel = os.path.relpath(dirpath, site)
        if rel == '.':
            continue
        depth = len(rel.replace(os.sep, '/').split('/'))
        for f in files:
            if not f.endswith('.html'):
                continue
            pages += 1
            ch = fix_page(os.path.join(dirpath, f), site, depth)
            if ch:
                fixed += 1
                print('  %s: 경로 %d개 보정 %s'
                      % (rel.replace(os.sep, '/') + '/' + f, len(ch), ch[:4]))
    if pages == 0:
        print('  하위 폴더 페이지 없음')
    elif fixed == 0:
        print('  하위 폴더 페이지 %d개 · 보정할 것 없음' % pages)
    return True
