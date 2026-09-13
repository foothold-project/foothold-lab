# -*- coding: utf-8 -*-
"""브랜드 정본 자산을 웹에 적용  (빌드 [1.77] 단계)

  브랜드 바이블 §5 의 두 가지 강제 사항을 기계가 지키게 한다.
    · 워드마크는 **살아있는 시스템 폰트로 대체하면 안 된다**. 정본 SVG 경로만 쓴다.
      (사이트 히어로는 그동안 그냥 텍스트 "FOOTHOLD" 였다.)
    · 기하를 손대지 않는다. 정본 파일의 path 를 그대로 심고 viewBox 를 보존한다.
      비율(승인된 실루엣 7.841215388)은 우리가 계산하지 않는다. 원본을 안 건드리면 유지된다.

  색: 정본은 ink(#161c26)/reverse(#e9e7e1) 두 벌로 배포된다. 그 두 값은 우리 --ink 토큰의
      라이트/다크 값과 정확히 같다(실측). 그래서 fill 을 var(--ink) 로 두면
      **두 정본 색을 모두 재현**하면서 테마 전환에 따라온다. 색 외의 변형은 하지 않는다.

  파비콘: 사이트에는 아예 없었다. 정본 favicon 을 전 페이지에 건다. 새 페이지도 자동으로 얻는다.

  브랜드 레포가 없으면 경고만 하고 통과한다(빌드가 남의 레포에 인질이 되지 않게).
"""
import hashlib, io, os, re, shutil

MARK = '<!--brand:v1-->'

CANDIDATES = [
    r"C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-brand",
    os.path.expanduser(r"~\Desktop\jay\인공지능사관학교\foothold-brand"),
    os.path.expanduser(r"~\OneDrive\Desktop\인공지능사관학교\foothold-brand"),
]

# 사이트로 내보낼 정본 자산 (브랜드 레포 기준 경로)
ASSETS = {
    'foothold-favicon.svg':       'assets/logo/v1/foothold-favicon.svg',
    'foothold-symbol-brand.svg':  'assets/logo/v1/foothold-symbol-brand.svg',
    'foothold-wordmark-ink.svg':  'assets/logo/v1/foothold-wordmark-ink.svg',
    'foothold-wordmark-reverse.svg': 'assets/logo/v1/foothold-wordmark-reverse.svg',
}

FAVICON = ('<link rel="icon" type="image/svg+xml" href="assets/brand/foothold-favicon.svg">'
           '<link rel="mask-icon" href="assets/brand/foothold-symbol-brand.svg" color="#0e7a6e">')


def find_brand():
    for p in CANDIDATES:
        if os.path.isdir(p):
            return p
    return None


def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()[:12]


def copy_assets(brand, vault):
    out = os.path.join(vault, 'assets', 'brand')
    os.makedirs(out, exist_ok=True)
    got = {}
    for name, rel in ASSETS.items():
        src = os.path.join(brand, rel.replace('/', os.sep))
        if not os.path.exists(src):
            print('  [!] 정본 없음: %s' % rel)
            continue
        shutil.copy(src, os.path.join(out, name))
        got[name] = sha(src)
    return got


def wordmark_svg(brand):
    """정본 워드마크의 기하를 그대로 가져오되 fill 만 토큰으로 구동."""
    src = os.path.join(brand, 'assets', 'logo', 'v1', 'foothold-wordmark-ink.svg')
    if not os.path.exists(src):
        return None
    s = io.open(src, encoding='utf-8').read()
    vb = re.search(r'viewBox="([^"]+)"', s)
    body = s[s.index('>', s.index('<svg')) + 1:s.rindex('</svg>')]
    body = re.sub(r'<title\b.*?</title>|<desc\b.*?</desc>', '', body, flags=re.S)
    body = body.replace('fill="#161c26"', 'fill="var(--ink)"')      # 정본 두 벌(ink/reverse)과 동치
    return ('<svg class="wm" viewBox="%s" role="img" aria-label="FOOTHOLD" '
            'xmlns="http://www.w3.org/2000/svg">%s</svg>' % (vb.group(1), body))


def inject_favicon(path, prefix=''):
    """prefix 는 그 페이지에서 사이트 뿌리로 가는 길이다 (하위 폴더면 ../).

    ★ 2026-09-09. 발표 덱(assets/deliverables/…)만 파비콘이 없었다.
      주입기가 PAGES 를 돌았는데 그 목록은 «루트만» 담는다. 검색이 같은
      이유로 두 장을 놓쳤던 그 자리다 (감사 F-03). 여기도 같았다.
      그리고 주소가 상대경로라, 하위 폴더 페이지에 그대로 넣으면
      assets/deliverables/assets/brand/… 을 찾아 404 가 된다.
    """
    s = io.open(path, encoding='utf-8').read()
    if MARK in s:
        return False
    if '</head>' not in s:
        return False
    tag = FAVICON.replace('href="assets/', 'href="%sassets/' % prefix)
    s = s.replace('</head>', MARK + tag + '\n</head>', 1)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    return True


def inject_wordmark(path, svg):
    """라이브 텍스트 워드마크를 정본 SVG 로 교체 (표지·슬라이드 어디든).

    폭은 원래 .name 이 쓰던 font-size 를 그대로 받아 em 으로 환산한다. 
    페이지마다 크기가 다른데(표지 4.2rem, 슬라이드 4rem·3.2rem) 한 값으로 박으면
    어느 한쪽이 반드시 어긋난다. 워드마크 종횡비 6.49 : 1 을 곱해 글자 크기에 맞춘다.
    """
    s = io.open(path, encoding='utf-8').read()
    if 'class="wm"' in s:
        return False
    old = '<span class="name">FOOTHOLD</span>'
    if old not in s:
        return False
    css = ('<style>.mark .wm{display:block;height:auto;'
           # .name 의 font-size 를 상속받아 그 6.2배 폭 (대문자 높이 기준 광학 보정 포함)
           'width:calc(var(--wm-size,3.4rem) * 6.2);max-width:100%}'
           '.mark{align-items:center}'
           '@media print{.mark .wm{width:calc(var(--wm-size,2.3rem) * 6.2)}}</style>')
    s = s.replace(old, svg, 1).replace('</head>', css + '\n</head>', 1)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    return True


def verify_favicon(vault, pages):
    """파비콘 주소가 «그 페이지에서» 열리는 경로인가.

    ★ 2026-09-09. 파일에 favicon 글자가 있는 것과 그 주소가 404 가 아닌 것은
      다른 사실이다. 하위 폴더 페이지에 루트용 상대주소가 들어가면
      /team-meang/assets/brand/… 을 찾아 404 가 되는데, 화면에는 아무 표시도
      없고 파일 검사는 통과한다. 조용한 실패다.

      ★ 검사 대상은 «배포본» 이다. [3.55] 는 배포본에서만 상대경로를 고치므로
      볼트를 보면 영원히 틀린 답이 나온다. 고치는 자리와 보는 자리가 같아야 한다.
      상대경로를 보정하는 단계가 빌드 뒤쪽에 있으므로 이 검사도 그 뒤에서
      해야 한다. 앞에서 하면 멀쩡한 것을 위반으로 잡는다.
    """
    import searchbox
    wrong, seen = [], 0
    for f in sorted(searchbox.public_pages(vault, pages)):
        p = os.path.join(vault, f)
        if not os.path.exists(p):
            continue
        seen += 1
        s = io.open(p, encoding='utf-8').read()
        m = re.search(r'href="([^"]*foothold-favicon[^"]*)"', s)
        if not m:
            wrong.append('%s -> 파비콘 없음' % f)
            continue
        want = '../' * f.count('/') + 'assets/brand/foothold-favicon.svg'
        if m.group(1).split('?')[0] != want:
            wrong.append('%s -> %s (%s 여야 한다)' % (f, m.group(1), want))
    if wrong:
        print('  [!] 파비콘 주소가 그 페이지에서 안 열립니다:')
        for w in wrong[:6]:
            print('      %s' % w)
        return False
    # ★ 2026-09-09. 「대상에 닿지 못한 것」과 「위반이 없는 것」은 다른 사실인데
    #   같은 «통과» 를 내고 있었다. 빈 볼트로 돌려 보고 알았다.
    #   관문이 0개를 검사하고 통과하면, 목록이 비는 순간 조용히 무력해진다.
    if seen == 0:
        print('  [!] 공개 페이지를 한 장도 못 봤습니다. 검사가 헛돌았습니다')
        return False
    print('  공개 %d장 · 파비콘 주소 전부 그 페이지 기준으로 열립니다' % seen)
    return True

def main(vault, pages, strict=False):
    """strict=True 면 파비콘 «주소가 그 페이지에서 열리는가» 까지 본다.

    ★ 이 검사는 늦게 해야 한다. 하위 폴더 페이지의 상대주소를 고치는 단계가
      뒤에 있어서, 이른 자리에서 보면 멀쩡한 것을 위반으로 잡는다.
      실측: team-meang/index.html 이 [1.87] 시점엔 루트용 주소를 갖고 있다가
      뒤 단계에서 ../ 로 고쳐진다.
    """
    brand = find_brand()
    if not brand:
        print('  [!] foothold-brand 클론 없음. 브랜드 자산 적용 건너뜀')
        return True
    got = copy_assets(brand, vault)
    print('  정본 자산 %d개 복사 (sha: %s)'
          % (len(got), ' '.join('%s=%s' % (k.split('-')[-1][:6], v[:6]) for k, v in got.items())))

    # ★ 파비콘은 «배포되는 공개 HTML 전수» 가 대상이다. PAGES 는 루트만 담는다.
    #   단일 정본은 searchbox.public_pages 다. 두 벌로 적지 않는다.
    import searchbox
    targets = sorted(searchbox.public_pages(vault, pages))
    n = 0
    for f in targets:
        p = os.path.join(vault, f)
        if not os.path.exists(p):
            continue
        depth = f.count('/')
        if inject_favicon(p, '../' * depth):
            n += 1
    print('  파비콘 주입 %d개 페이지 (공개 %d장 중)' % (n, len(targets)))

    # ★ 2026-09-10. 파비콘과 같은 사각지대였다. pages 는 루트만 담는다.
    #   주입 · 워드마크 · 검증 셋이 한 파일 안에서 같은 실수를 하고 있었고,
    #   파비콘 하나만 고쳐 두면 나머지 둘에서 똑같이 새어 나간다.
    wm_targets = targets
    svg = wordmark_svg(brand)
    if svg:
        done = [f for f in wm_targets
                if os.path.exists(os.path.join(vault, f))
                and inject_wordmark(os.path.join(vault, f), svg)]
        print('  워드마크 → 정본 SVG 교체 %d개 %s' % (len(done), done or ''))

    # 라이브 텍스트 워드마크가 남아 있으면 브랜드 규정 위반(바이블 §5)
    left = [f for f in wm_targets
            if os.path.exists(os.path.join(vault, f))
            and '<span class="name">FOOTHOLD</span>' in io.open(
                os.path.join(vault, f), encoding='utf-8').read()]
    if left:
        print('  [!] 라이브 텍스트 워드마크가 남음: %s' % ', '.join(left))
        return False

    # 검증: 실제로 박혔는가
    # ★ 2026-09-09. 여기도 pages(루트만) 를 돌고 있었다. 이 파일에서만 세 번째다
    #   (주입 · 워드마크 · 검증). 그래서 발표 덱이 파비콘 없이 나갔고 검증도
    #   그것을 못 봤다. 주입과 검증이 같은 목록을 봐야 의미가 있다.
    #   주소 «깊이» 도 본다. 하위 폴더에 루트용 상대주소를 넣으면 404 가 되고,
    #   404 인 파비콘은 없는 것과 같은데 파일에는 글자가 있어 통과한다.
    import searchbox
    bad, wrong = [], []
    for f in sorted(searchbox.public_pages(vault, pages)):
        p = os.path.join(vault, f)
        if not os.path.exists(p):
            continue
        s = io.open(p, encoding='utf-8').read()
        m = re.search(r'href="([^"]*foothold-favicon[^"]*)"', s)
        if not m:
            bad.append(f)
            continue
        want = '../' * f.count('/') + 'assets/brand/foothold-favicon.svg'
        if m.group(1).split('?')[0] != want:
            wrong.append('%s -> %s (%s 여야 한다)' % (f, m.group(1), want))
    if bad:
        print('  [!] 파비콘 누락: %s' % ', '.join(bad))
        return False
    if wrong and strict:
        print('  [!] 파비콘 주소가 그 페이지에서 안 열립니다:')
        for w in wrong[:6]:
            print('      %s' % w)
        return False
    return True
