# -*- coding: utf-8 -*-
"""배포된 사이트를 **실제로 받아서** 검사한다.

**왜 있나 (2026-09-13).** 나는 오늘 「고쳤습니다」를 세 번 보고했고 세 번 다
라이브에서는 안 고쳐져 있었다. 로컬에서 고치고, 커밋을 안 했거나, 커밋하고
push 를 안 했거나, push 하고 배포를 안 했다. 팀장이 페이지를 열어 잡았다.

`200` 은 결과가 아니다. 파일이 열려도 **색이 검정이면 안 고쳐진 것**이다.
그래서 이 검사는 「받아진다」가 아니라 **「사람이 보는 것이 맞는가」**를 묻는다.

    python tools/verify_live.py
    python tools/verify_live.py --base http://127.0.0.1:8899   # 배포 전 미리

통과하면 종료 0, 하나라도 어긋나면 **1 과 함께 무엇이 왜 틀렸는지** 찍는다.
검사할 것이 0건이면 그것도 실패다. 조용히 통과하는 길을 안 남긴다.
"""
import argparse
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://foothold-project.vercel.app'

# 팀장이 실제로 여는 쪽. 여기가 맞아야 «문제 없다» 고 말할 수 있다.
PAGES = [
    'research-20260911-eval-protocol-v2',
    'research-generalization-benchmark-10-terrains',
    'hub-research',
    'index.html',
    'notice-20260912',
]

TOKEN_RE = re.compile(r'var\(\s*(--[a-z0-9-]+)', re.I)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'foothold-verify'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, ''
    except OSError as e:
        return 0, str(e)


def check_hub(t, bad):
    """연구 허브가 «목업대로» 서 있는가. 개수를 센다.

    있는지만 보면 안 된다. 입구가 하나만 나와도 「있다」가 되고, 수치가 빈
    칸이어도 「있다」가 된다. 그래서 **몇 개인지**를 본다.
    """
    n = 0

    n += 1
    doors = len(re.findall(r'class="tkpin3"|<a href="\?fn=', t))
    if len(re.findall(r'<a href="\?fn=', t)) != 6:
        bad.append('여섯 입구가 %d개입니다'
                   % len(re.findall(r'<a href="\?fn=', t)))

    n += 1
    if len(re.findall(r'class="rv3"', t)) < 4:
        bad.append('배포 수치가 %d칸입니다 (넷이어야 합니다)'
                   % len(re.findall(r'class="rv3"', t)))

    # 칸이 «있는지» 만 보면 빈 칸도 통과한다. 숫자가 들었는지 본다.
    n += 1
    nums = re.findall(r'class="rvn3">(.*?)</div>', t, re.S)
    hollow = [i for i, v in enumerate(nums) if not re.search(r'\d', v)]
    if not nums:
        bad.append('배포 수치 칸에 값이 하나도 없습니다')
    elif hollow:
        bad.append('배포 수치 %d칸이 숫자 없이 비어 있습니다' % len(hollow))

    n += 1
    if 'class="rel3"' not in t:
        bad.append('「지금 어디까지 왔나」 블록이 없습니다')

    # 거르개가 «실제로 도는가». 링크만 있고 스크립트가 없으면 눌러도
    # 아무 일이 안 난다. 그 상태로 배포한 적이 있다.
    n += 1
    if 'data-fn' not in t or 'popstate' not in t:
        bad.append('입구를 눌러도 목록이 안 걸러집니다 (거르개 스크립트 없음)')

    # ★ 2026-09-13. 거르개 스크립트가 «언제» 도는지가 중요하다.
    #   문서 목록은 그 스크립트보다 «뒤» 에 온다. 바로 돌면 카드가 0장이라
    #   「이 조건에 맞는 문서가 없습니다」가 아무것도 안 걸렀는데 뜬다.
    #   실측: 화면을 찍어 보고서야 잡았다. 개수 검사는 통과했다.
    #   ★ 처음엔 페이지 «전체» 에서 DOMContentLoaded 를 찾았다. 그런데 테마
    #     초기화 스크립트에 그 낱말이 이미 있어서 **검사가 그냥 통과했다.**
    #     거르개 스크립트 «안» 만 봐야 한다. 넓게 찾는 검사는 늘 이렇게 샌다.
    n += 1
    blk = re.search(r'<script>\(function\(\)\{[^<]*?\.dr3[^<]*?</script>', t, re.S)
    if 'data-fn' in t:
        if not blk:
            bad.append('거르개 스크립트를 못 찾았습니다')
        elif 'DOMContentLoaded' not in blk.group(0):
            bad.append('거르개가 문서 목록보다 «먼저» 돕니다. 첫 화면에 '
                       '「문서가 없습니다」가 뜹니다')

    # 표식이 «몇 장인가» 만 보면 안 된다. 한 입구가 통째로 0장이어도
    # 총합은 커 보인다. 실측: 카드를 내는 자리가 둘인데 하나만 고쳐서
    # 조사 문서 16장이 표식 없이 나갔고, 거르면 그 16장이 사라졌다.
    n += 1
    tagged = re.findall(r'class="ev3" data-fn="([a-z]*)"', t)
    cards = len(re.findall(r'<a class="ev3"', t))
    blank = sum(1 for x in tagged if not x)
    if blank or len(tagged) != cards:
        bad.append('입구 표식 없는 카드가 %d장입니다 (카드 %d · 표식 %d)'
                   % (blank + cards - len(tagged), cards, len(tagged) - blank))

    n += 1
    per = {}
    for x in tagged:
        if x:
            per[x] = per.get(x, 0) + 1
    doors_in_nav = re.findall(r'<a href="\?fn=([a-z]+)"', t)
    empty = [d for d in doors_in_nav if not per.get(d)]
    if empty:
        bad.append('누르면 «빈 목록» 이 나오는 입구가 있습니다: %s'
                   % ' '.join(empty))

    # ★ 2026-09-13. 입구에 적힌 수와 «실제로 나오는 카드 수» 가 같아야 한다.
    #   실측: 출발선 문서를 건수에는 넣고 목록에는 안 넣어, 「결과 보고 7」을
    #   눌러도 6장이 나왔다. 숫자가 거짓말을 하면 나머지도 못 믿는다.
    n += 1
    shown = dict(re.findall(
        r'<a href="\?fn=([a-z]+)"[^>]*>.*?class="dct3">(\d+)<', t, re.S))
    for k, v in shown.items():
        if per.get(k, 0) != int(v):
            bad.append('입구 «%s» 가 %s라고 적혀 있는데 카드는 %d장입니다'
                       % (k, v, per.get(k, 0)))

    n += 1
    if 'id="terrain-board"' not in t:
        bad.append('지형 보드 접기가 없습니다')

    # ★ 2026-09-13. 「분류 안 된 것」이 최대 묶음이면 그 분류는 «안 서는» 것이다.
    #   실측: 옛 purpose 로 묶었더니 37장 중 14장이 거기 떨어졌다. 거르개로
    #   「진단·분석」을 눌렀는데 묶음 제목이 「분류 안 된 것」으로 나왔다.
    # ★ 2026-09-13. 카드를 담는 절이 둘이고 제목 클래스가 다르다
    #   (`.eg3` 실측 · `.eh3` 조사). 거르개가 한쪽만 봐서, 「도구·운영」을
    #   걸렀더니 카드 5장이 **제목 없이** 떠 있었다.
    #   클래스를 나열하지 않고 **같은 표식**(`data-label`)으로 묶었는지 본다.
    n += 1
    boxes = len(re.findall(r'class="evs3"', t))
    labels = len(re.findall(r'data-label="', t))
    if boxes and labels < boxes:
        bad.append('카드 묶음 %d개 중 %d개만 제목에 표식이 있습니다. '
                   '거르면 제목 없는 카드가 남습니다' % (boxes, labels))

    n += 1
    for lab in re.findall(r'data-label="([^"]*)"', t):
        if '분류 안 된' in lab or '입구가 안 정해진' in lab or lab.strip() in ('', 'None'):
            bad.append('묶음 제목이 «%s» 입니다. 배정이 빠진 문서가 있습니다' % lab)

    # ★ 2026-09-13. `el.hidden` 은 **혼자서 안 숨긴다.**
    #   브라우저 기본 시트의 `[hidden]{display:none}` 은 태그 선택자 수준이라
    #   `.ev3{display:grid}` 한 줄에 진다.
    #   실측 (라이브): 속성 hidden 29장 · 화면에서 사라진 것 0장.
    #   거르개를 눌러도 아무것도 안 걸러졌는데 내 시험은 통과했다.
    #   `!c.hidden` 을 셌기 때문이다. 그건 «내가 넣은 속성» 이지 화면이 아니다.
    n += 1
    if 'hidden' in t and not re.search(r'\[hidden\]\s*\{[^}]*display\s*:\s*none'
                                       r'\s*!important', t):
        bad.append('숨김을 el.hidden 에만 맡겼습니다. `[hidden]{display:none'
                   '!important}` 가 없으면 «걸러도 안 사라집니다»')

    # ★ 2026-09-13. 「있는가」만 세면 **화면이 망가져도 통과한다.**
    #   실측: 여섯 입구를 `<nav>` 로 만들었더니 전역 규칙
    #   `nav:not(.gnav){height:calc(100vh - …)!important}` 에 걸려 입구 하나가
    #   1,273px 이 됐고 첫 문서 카드가 561 -> 3,404 로 밀렸다.
    #   검사는 다 통과했다. 개수만 봤기 때문이다.
    #   그래서 **높이를 만드는 태그**를 쓰지 않았는지 여기서 본다.
    #   진짜 치수는 브라우저로 재야 하지만, 이 한 줄이 그 사고를 막는다.
    n += 1
    doors_block = re.search(r'<(nav|div)[^>]*class="dr3"', t)
    if doors_block and doors_block.group(1) == 'nav':
        bad.append('입구를 <nav> 로 냈습니다. 전역 규칙이 화면 높이를 강제해 '
                   '입구가 1,200px 로 늘어납니다')

    n += 1
    for cls in ('rel3', 'tkcs3', 'dr3'):
        m = re.search(r'<(nav|aside)[^>]*class="[^"]*\b%s\b' % cls, t)
        if m:
            bad.append('%s 를 <%s> 로 냈습니다 (같은 전역 규칙에 걸립니다)'
                       % (cls, m.group(1)))
    return n


def check_bench(t, bad):
    """일반화 벤치마크 문서가 «정본 판» 으로 나갔는가.

    ★ 2026-09-14 신설. 이 문서를 여섯 판에 걸쳐 고쳤는데 라이브 검사 대상에
      없었다. 가장 많이 바뀐 것이 검사 밖에 있으면 검사의 뜻이 없다.

    숫자 대조는 `tools/check_doc_numbers.py` 가 원자료로 한다. 여기서는
    **배포본이 그 판인가** 와 **고쳐 놓고 되살아나는 것** 만 본다.
    """
    n = 0
    body = re.sub(r'(?s)<(script|style)\b.*?</\1>', '', t)
    txt = re.sub(r'<[^>]+>', ' ', body)

    # ★ 판 이력은 «무엇을 지웠는지» 를 설명하느라 지운 말을 인용한다.
    #   그 줄까지 보면 고칠수록 위반이 는다. 실측: 이 검사를 만들자마자
    #   v2.5 이력의 「정책 파일도 다르며를 지웠다」가 위반으로 잡혔다.
    #   아래 검사는 **본문만** 본다.
    main = txt.split('판 이력')[0]

    # 머리말의 «판» 만 본다. 판 이력 표에는 옛 판 번호가 다 들어 있어서
    # 전체를 보면 v2.0 으로 되돌려도 통과한다. 실측으로 확인했다.
    n += 1
    head = main.split('## 1.')[0]
    if not re.search(r'판:\s*v2\.[6-9]|판:\s*v[3-9]\.', head):
        bad.append('벤치마크 문서가 옛 판입니다 (머리말이 v2.6 이상이어야 합니다)')

    # 물린 «주장» 이 되살아났나. 여섯 판에 걸쳐 하나씩 뺀 것들이다.
    #
    # ★ 낱말만 찾으면 안 된다. 본문은 「실패를 «지형 자체의 성질» 로 단정할
    #   수도 없다」처럼 **그 말을 부정하면서** 쓴다. 낱말 검사는 그것을 위반으로
    #   잡는다. 그래서 «단정하는 모양» 을 정규식으로 잡는다.
    for pat, label, why in [
            (r'같은 정책 체크포인트(?!.{0,30}(?:아니|없|미확인))',
             '같은 정책 체크포인트', '두 측정의 정책 동일성은 미확인이다'),
            (r'정책 파일도 다르(?!.{0,30}(?:아니|없|미확인))',
             '정책 파일도 다르다', '다르다고도 확정할 수 없다'),
            (r'지형 자체의 성질(?!.{0,40}(?:단정할 수도 없|단정할 수 없|아니))',
             '지형 자체의 성질', '조건을 분리하지 못해 단정할 수 없다'),
            (r'전진불능형 \(floating_ring · rails · pit\)',
             '전진불능형에 rails 포함', 'rails 는 빠졌다'),
            (r'일일 청구', '일일 청구액', '청구액은 공개 문서에 안 적는다')]:
        n += 1
        if re.search(pat, main):
            bad.append('벤치마크 문서에 «%s» 가 되살아났습니다 (%s)' % (label, why))

    # 실패 다섯과 통과 다섯이 다 실려 있나
    n += 1
    miss = [x for x in ('stepping_stones', 'gap', 'pit', 'rails', 'floating_ring',
                        'wave', 'star', 'repeated_boxes', 'repeated_cylinders',
                        'discrete_obstacles') if x not in txt]
    if miss:
        bad.append('벤치마크 문서에 빠진 지형: %s' % ' '.join(miss))

    n += 1
    if '평가 영상 갤러리' not in txt or '/gallery/' not in t:
        bad.append('벤치마크 문서에서 갤러리로 가는 길이 없습니다')
    return n


def check_page(base, name, bad):
    # 배포본은 확장자 없는 주소를 쓰고(호스트가 이어 준다) 로컬 정적 서버는
    # 파일 이름 그대로다. 배포 «전» 에 같은 검사를 돌리려면 둘 다 봐야 한다.
    code, t = get('%s/%s' % (base, name))
    if code != 200 and not name.endswith('.html'):
        code, t = get('%s/%s.html' % (base, name))
    if code != 200:
        bad.append('%s 가 안 열립니다 (%s)' % (name, code))
        return 0

    checks = 0
    if name == 'hub-research':
        checks += check_hub(t, bad)
    if name == 'research-generalization-benchmark-10-terrains':
        checks += check_bench(t, bad)

    # 1. 고쳐 놓고 되살아나는 것들. 전부 «본문 글자» 로 본다.
    text = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
    text = re.sub(r'<[^>]+>', ' ', text)
    checks += 1
    if re.search(r'&lt;https?://|<https?://[^\s>]+>', text):
        bad.append('%s 에 주소가 꺾쇠째 글자로 나옵니다' % name)

    checks += 1
    if re.search(r'^\s*분류:\s', text[:400], re.M):
        bad.append('%s 에 문서 머리말이 본문으로 샙니다' % name)

    # 2. 전역바와 테마. 없으면 어두운 화면에서 글자가 안 보인다.
    checks += 1
    if 'gnav' not in t:
        bad.append('%s 에 전역바가 없습니다' % name)
    checks += 1
    if 'fh-theme-boot' not in t:
        bad.append('%s 에 테마 초기화가 없습니다' % name)

    # 3. 도해. **이것이 오늘 검정으로 나온 자리다.**
    for src in set(re.findall(r'<img[^>]+src="([^"?]+\.svg)', t)):
        if 'brand' in src or 'favicon' in src:
            continue
        checks += 1
        scode, stext = get('%s/%s' % (base, src.lstrip('/')))
        if scode != 200:
            bad.append('%s 의 도해 %s 가 안 열립니다 (%s)' % (name, src, scode))
            continue

        head = stext[:600]
        if 'width=' not in head:
            bad.append('%s 에 width 가 없어 <img> 안에서 납작해집니다' % src)

        used = set(TOKEN_RE.findall(stext))
        if used:
            # 파일 «안» 에 그 토큰이 정의돼 있어야 한다. 격리 문서라
            # 페이지 변수가 안 닿는다. 없으면 전부 검정이 된다.
            declared = set(re.findall(r'(--[a-z0-9-]+)\s*:', stext, re.I))
            missing = sorted(used - declared)
            if missing:
                bad.append('%s 가 토큰 %d개를 쓰는데 파일 안에 정의가 없습니다 '
                           '(검정으로 나옵니다): %s'
                           % (src, len(missing), ' '.join(missing[:5])))
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=BASE)
    a = ap.parse_args()
    base = a.base.rstrip('/')

    print('  검사 대상: %s' % base)
    bad, total = [], 0
    for p in PAGES:
        n = check_page(base, p, bad)
        total += n
        print('    %-42s 검사 %d항목' % (p, n))

    print()
    if total == 0:
        raise SystemExit('  [!] 검사한 것이 0건입니다. 통과로 안 읽습니다')

    if bad:
        print('  [!] 어긋난 것 %d건' % len(bad))
        for b in bad:
            print('      ' + b)
        raise SystemExit(1)

    print('  %d항목 전부 통과. 사람이 보는 층위에서 확인했습니다.' % total)


if __name__ == '__main__':
    main()
