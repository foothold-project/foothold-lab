# -*- coding: utf-8 -*-
"""배포본의 영상이 우리 규격을 지키는지 본다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (고의 결함 주입 검출 시험 · `_selftest`)
요지: 썸네일 없는 영상은 폰에서 검정 네모로 뜬다. 새 영상이 와도 그것을 막는다

## 왜 있나

2026-09-13 에 팀장이 폰에서 「종합보고서에는 영상이 처음에 블랙으로 떠 있다」
고 잡았다. `report-v1` 을 고쳤다. 그런데 2026-09-14 에 전수로 세어 보니
**다른 문서 두 장의 영상 19개가 그대로였다.**

    report-v1                                   12개  poster 12
    research-generalization-benchmark-10-...    10개  poster  0
    research-visual-evidence                     9개  poster  0

한 자리만 고치고 「됐다」고 한 것이다. 그래서 **세는 자리를 여기 하나로 만든다.**

## 무엇을 보나

| 항목 | 왜 |
|---|---|
| `poster` | 없으면 첫 프레임을 그리는데 우리 렌더는 프레임 0 이 검정이다 (밝기 0.0 · 21개 전부) |
| 포스터 파일이 실제로 있나 | 링크만 멀쩡하고 파일이 없으면 똑같이 검정이다 |
| `playsinline` | 없으면 iOS 가 전체화면으로 가로챈다 |
| `muted` | 없으면 자동재생 정책에 막힌다 |
| `preload="metadata"` | 없으면 목록에서 영상 전체를 내려받는다 |
| `controls` | 없으면 폰에서 재생할 방법이 없다 |
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

NEED = ('controls', 'muted', 'playsinline')
VID = re.compile(r'<video\b[^>]*>')
DROP = re.compile(r'(?s)<style\b.*?</style>|<script\b.*?</script>')


def scan(out):
    """반환: (검사한 영상 수, [문제]). `out` 은 배포 폴더."""
    bad, n = [], 0
    for f in sorted(os.listdir(out)):
        if not f.endswith('.html'):
            continue
        t = DROP.sub(' ', io.open(os.path.join(out, f),
                                  encoding='utf-8', errors='replace').read())
        for tag in VID.findall(t):
            n += 1
            src = re.search(r'src="([^"]+)"', tag)
            src = src.group(1) if src else '(src 없음)'
            miss = [k for k in NEED if k not in tag]
            if 'preload=' not in tag:
                miss.append('preload')
            if 'poster=' not in tag:
                bad.append('%s · %s 에 썸네일(poster)이 없습니다' % (f, src[-46:]))
            else:
                p = re.search(r'poster="([^"?]+)', tag).group(1)
                fp = os.path.join(out, p.lstrip('/').replace('/', os.sep))
                if not os.path.isfile(fp):
                    bad.append('%s · 썸네일 파일이 없습니다: %s' % (f, p[-46:]))
            if miss:
                bad.append('%s · %s 에 %s 가 없습니다'
                           % (f, src[-40:], ' · '.join(miss)))
    return n, bad


def _selftest():
    """알려진 답. 망가진 태그를 넣으면 잡아야 한다."""
    import tempfile
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'v', 'posters'), exist_ok=True)
    io.open(os.path.join(d, 'v', 'posters', 'a.jpg'), 'w').write('x')
    cases = [
        ('온전한 것',
         '<video controls muted playsinline preload="metadata" '
         'poster="v/posters/a.jpg" src="v/a.mp4"></video>', 0),
        ('poster 없음',
         '<video controls muted playsinline preload="metadata" '
         'src="v/a.mp4"></video>', 1),
        ('poster 파일 없음',
         '<video controls muted playsinline preload="metadata" '
         'poster="v/posters/zz.jpg" src="v/a.mp4"></video>', 1),
        ('playsinline 없음',
         '<video controls muted preload="metadata" '
         'poster="v/posters/a.jpg" src="v/a.mp4"></video>', 1),
        ('script 안의 것은 안 센다',
         '<script>var s="<video src=\'x.mp4\'></video>"</script>', 0),
    ]
    ok = 0
    for name, html, want in cases:
        p = os.path.join(d, 'p.html')
        io.open(p, 'w', encoding='utf-8').write(html)
        _, bad = scan(d)
        got = (len(bad) == want)
        ok += got
        print('  %s %-22s 기대 %d · 결과 %d %s'
              % ('OK ' if got else '[X]', name, want, len(bad),
                 ('· ' + bad[0][:44]) if bad else ''))
    print('  %d/%d' % (ok, len(cases)))
    return ok == len(cases)


def main(out):
    print('[3.475] 영상 규격 검사 (썸네일 · 폰 재생 속성)')
    if not _selftest():
        print('  [!] 자기시험이 실패했습니다. 이 검사를 믿을 수 없습니다')
        return False
    n, bad = scan(out)
    print('  영상 %d개 검사' % n)
    if n == 0:
        print('  [!] 영상을 하나도 못 찾았습니다. 검사가 안 돈 것입니다')
        return False
    if bad:
        print('  [!] 어긋난 것 %d건' % len(bad))
        for b in bad[:12]:
            print('      ' + b)
        if len(bad) > 12:
            print('      ... %d건 더' % (len(bad) - 12))
        print('      썸네일은 `python tools/make_posters.py --write '
              'web/assets/video` 로 굽습니다')
        return False
    print('  영상 %d개 전부 썸네일과 폰 재생 속성을 갖췄습니다' % n)
    return True


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if _selftest() else 1)
    sys.exit(0 if main(sys.argv[1]) else 1)
