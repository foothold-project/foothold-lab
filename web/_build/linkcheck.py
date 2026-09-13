# -*- coding: utf-8 -*-
"""깨진 내부 링크 관문.

  왜 관문인가:
    2026-08-26 점검에서 `research-visual-evidence.html -> training-benchmarks.html`
    죽은 링크가 발견됐다. docs/research/ 안에서 `research-` 접두사를 빼먹은 것이다.
    빌드가 md 를 웹으로 옮길 때 접두사를 붙이는데, 이미 `.html` 로 적어 두면
    그 변환을 건너뛴다. 눈으로는 멀쩡해 보이고 눌러야만 404 가 뜬다.

    같은 부류는 «규칙을 적어두면» 또 난다. 빌드가 막는다.

  검사 대상: 배포 폴더의 html 이 가리키는 같은 폴더 안 .html 링크.
    외부(http)·앵커(#)·하위경로(/)는 건너뛴다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)


def _site():
    import roots as _r
    for c in _r.site_candidates():
        if os.path.isdir(c):
            return c
    return None


LINK = re.compile(r'href="([^"#?:]+\.html)(?:[#?][^"]*)?"')

# ★ 2026-09-08 감사 F-07. 위 규칙은 «#뒤» 를 버린다. 그래서 문서는 있는데
#   그 안에 없는 절을 가리키는 링크를 아무도 안 봤다. 실측 2건이 나왔다.
#     research-visual-evidence -> research-training-benchmarks.html#5-3  (s1~s12 뿐)
#     team-meang/index.html    -> index.html#team  (하위 폴더라 자기 자신을 가리킴)
#   두 번째는 감사도 못 본 것이다. 감사는 루트 페이지만 훑었다.
#   문서가 있는지와 그 안에 그 절이 있는지는 다른 질문이다. 둘 다 본다.
ANCHOR = re.compile(r'href="([^"?:]*)#([^"]+)"')
HAS_ID = re.compile(r'\sid="([^"]+)"')
SCRIPTY = re.compile(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>', re.S | re.I)


def scan(site):
    """(깨진링크 목록, 검사한 페이지 수, 검사한 링크 수)

    ★ 2026-08-27: 예전에는 os.listdir 로 «최상위만» 봤고, 슬래시가 든 링크는
      아예 건너뛰었다. 그래서 team-meang/index.html 의 링크 12개가 전부 404 인 채
      배포됐고, 사이트의 깨진 링크가 사실상 그 한 파일에서 나왔는데도 관문은
      «깨진 링크 없음» 을 찍었다. 검사기가 안 보는 곳은 반드시 썩는다.
    """
    files = []
    for dirpath, dirnames, names in os.walk(site):
        dirnames[:] = [d for d in dirnames if d not in ('assets', '_build', '_src')]
        for n in names:
            if n.endswith('.html'):
                files.append(os.path.relpath(os.path.join(dirpath, n), site)
                             .replace(os.sep, '/'))
    exists = set(files)
    bad, seen = [], 0
    for f in sorted(files):
        base = os.path.dirname(f)
        t = io.open(os.path.join(site, f.replace('/', os.sep)),
                    encoding='utf-8', errors='replace').read()
        # HTML 주석 안의 href 는 링크가 아니다. 팀원이 남긴 메모를 죽은 링크로
        # 잡아 배포를 세운 적이 있다 (2026-08-27, team-meang 의 승격 메모).
        t = re.sub(r'<!--.*?-->', '', t, flags=re.S)
        for h in sorted(set(LINK.findall(t))):
            seen += 1
            # 링크는 그 페이지가 놓인 자리에서 푼다
            target = os.path.normpath(os.path.join(base, h)).replace(os.sep, '/')
            if target in exists:
                continue
            # assets/ 는 «페이지» 목록에서 뺐지만(위 os.walk), 그 밑에 html 을 둘
            # 수 있다. 발표본처럼 페이지가 아니라 «내려받는 산출물» 인 경우다.
            # 목록에 없다고 죽은 링크로 몰면 멀쩡한 파일이 배포를 세운다.
            # 2026-09-05: proposal-deck-presented.html 이 실제로 그랬다.
            if os.path.isfile(os.path.join(site, target.replace('/', os.sep))):
                continue
            bad.append((f, h))
    return bad, len(files), seen


def scan_anchors(site):
    """(깨진앵커 목록, 검사한 앵커 링크 수)

    href 의 «#뒤» 가 대상 문서 안에 실제로 있는지 본다. script·style 은 걷어낸다.
    걷어내지 않으면 검색 스크립트의 템플릿 문자열이 링크로 잡힌다 (실측 119건 오검).
    """
    files, ids = [], {}
    for dirpath, dirnames, names in os.walk(site):
        dirnames[:] = [d for d in dirnames if d in ('assets',) or d not in ('_build', '_src')]
        for n in names:
            if not n.endswith('.html'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, n), site).replace(os.sep, '/')
            files.append(rel)
            raw = io.open(os.path.join(dirpath, n), encoding='utf-8',
                          errors='replace').read()
            ids[rel] = set(HAS_ID.findall(raw))
    bad, seen = [], 0
    for f in sorted(files):
        base = os.path.dirname(f)
        raw = io.open(os.path.join(site, f.replace('/', os.sep)),
                      encoding='utf-8', errors='replace').read()
        t = SCRIPTY.sub(' ', re.sub(r'<!--.*?-->', '', raw, flags=re.S))
        for tgt, anc in sorted(set(ANCHOR.findall(t))):
            if tgt.startswith(('http://', 'https://', 'mailto:')):
                continue
            seen += 1
            path = f if not tgt else os.path.normpath(
                os.path.join(base, tgt)).replace(os.sep, '/')
            if path not in ids:
                continue                      # 문서 자체가 없는 것은 scan() 이 본다
            if anc not in ids[path]:
                bad.append((f, tgt + '#' + anc))
    return bad, seen


def _kat():
    """★ 답을 아는 입력으로 검사기를 먼저 시험한다 (커널 원칙 1).
    통과만 찍는 검사기는 검사기가 아니다."""
    import tempfile
    d = tempfile.mkdtemp()
    io.open(os.path.join(d, 'a.html'), 'w', encoding='utf-8').write(
        '<a href="b.html">ok</a><a href="nope.html">dead</a>'
        '<a href="https://x/y.html">ext</a><a href="sub/c.html">sub-ok</a>')
    io.open(os.path.join(d, 'b.html'), 'w', encoding='utf-8').write('hi')
    # 하위 폴더 페이지. 최상위를 가리키려면 ../ 가 있어야 한다.
    #   team-meang 사고를 그대로 재현해 검사기가 잡는지 본다.
    os.makedirs(os.path.join(d, 'sub'))
    io.open(os.path.join(d, 'sub', 'c.html'), 'w', encoding='utf-8').write(
        '<!-- 메모: href="ghost.html" 는 주석이라 링크가 아니다 -->'
        '<a href="../b.html">up-ok</a><a href="b.html">up-missing</a>')
    bad, np, nl = scan(d)
    got = sorted((f, h) for f, h in bad)
    ok = (got == [('a.html', 'nope.html'), ('sub/c.html', 'b.html')] and np == 3)
    import shutil
    shutil.rmtree(d, ignore_errors=True)
    return ok


def main(site=None):
    """site 를 주면 그것을 본다 (재현 빌드는 --out 으로 배포하므로).

    ★ 안 주면 예전처럼 스스로 찾는다. 배포 목적지를 «두 곳에서» 정하면
      한쪽을 바꿔도 다른 쪽이 옛 폴더를 보고 통과했다고 말한다 (철칙 4).
    """
    if not _kat():
        print('  [!] 링크 검사기 자기시험 실패. 중단.')
        return False
    site = site or _site()
    if not site:
        print('  [!] 배포 폴더를 못 찾음')
        return False
    bad, npages, nlinks = scan(site)
    if nlinks == 0:
        print('  [!] 검사한 링크가 0개다. 조용한 통과를 허용하지 않는다.')
        return False
    print('  자가검증 통과 · 페이지 %d · 내부 링크 %d개 검사' % (npages, nlinks))
    if bad:
        for f, h in bad:
            print('  ★ %s -> %s (없음)' % (f, h))
        print('  깨진 링크 %d개' % len(bad))
        return False
    abad, nanc = scan_anchors(site)
    print('  앵커 링크 %d개 검사 (#뒤가 대상 문서에 실제로 있는가)' % nanc)
    if abad:
        for f, h in abad:
            print('  ★ %s -> %s (그 절이 없음)' % (f, h))
        print('  깨진 앵커 %d개' % len(abad))
        return False
    print('  깨진 링크 없음 · 깨진 앵커 없음')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
