# -*- coding: utf-8 -*-
"""배포 «전» 에 산출 폴더를 훑어 팀장이 지적한 것들이 실제로 고쳐졌는지 본다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (고의 결함 주입 검출 시험 · `--selftest`)

## 왜 있나

2026-09-13 에 팀장이 열두 가지를 지적했다. 하나씩 고칠 때마다 「됐습니다」라고
보고했는데, **손으로 확인한 것이라 다음 빌드에서 되살아나도 몰랐다.**

실제로 그런 일이 있었다. 지형 보드가 옛 규격 CSV 를 읽는 것을 고쳤는데,
그 사실을 화면 어디에도 안 적어 두어 다시 벌어져도 안 보였다.

그래서 **지적받은 것 하나하나를 산출물에서 다시 센다.**

## 쓰는 법

    python tools/predeploy.py <산출폴더>
    python tools/predeploy.py --selftest

`verify_live.py` 와 겹치지 않는다. 저쪽은 **배포된 사이트**를 받아서 보고,
이쪽은 **배포하기 전 산출 폴더**를 본다. 겹치는 검사는 두지 않는다.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')


def read(out, name):
    p = os.path.join(out, name)
    if not os.path.isfile(p):
        return None
    return io.open(p, encoding='utf-8', errors='replace').read()


def board_of(hub):
    m = re.search(r'(?s)id="terrain-board".*?</details>', hub)
    return m.group(0) if m else ''


def checks(out, bad):
    """반환: 검사한 항목 수."""
    n = 0
    hub = read(out, 'hub-research.html')
    proto = read(out, 'research-20260911-eval-protocol-v2.html')
    bench = read(out, 'research-generalization-benchmark-10-terrains.html')
    for name, t in (('hub-research', hub),
                    ('프로토콜', proto), ('벤치마크', bench)):
        n += 1
        if t is None:
            bad.append('%s 페이지가 산출물에 없습니다' % name)
    if hub is None or proto is None or bench is None:
        return n

    # 1. 목록이 «한 기준» 으로 묶였나 (여섯 입구)
    n += 1
    labs = set(re.findall(r'data-label="([^"]*)"', hub))
    if len(labs) != 6:
        bad.append('묶음 제목이 %d종입니다 (여섯 입구여야 합니다): %s'
                   % (len(labs), ' · '.join(sorted(labs))))
    n += 1
    if '외부 자료 조사' in hub:
        bad.append('옛 묶음 이름 «외부 자료 조사» 가 남았습니다')

    # 3. 전역바에 갤러리 (전수)
    n += 1
    miss = [f for f in sorted(os.listdir(out)) if f.endswith('.html')
            and '<!--gnav:v1-->' in (read(out, f) or '')
            and '>갤러리<' not in (read(out, f) or '')]
    if miss:
        bad.append('전역바에 갤러리가 빠진 페이지 %d장: %s'
                   % (len(miss), ' '.join(miss[:3])))

    # 6. rails 레시피 칸에 파인튜닝 계획이 없나
    #    ★ 위치를 «보드 기준» 으로 잡는다. 전체 페이지에 인덱싱하면 창이
    #      어긋나 거짓 실패가 난다. 실제로 그렇게 한 번 틀렸다.
    b = board_of(hub)
    n += 1
    if not b:
        bad.append('지형 보드를 못 찾았습니다')
    else:
        for m in re.finditer('파인튜닝', b):
            if 'tkp3' not in b[max(0, m.start() - 300):m.start()]:
                bad.append('파인튜닝 계획이 «공통 칩» 밖에 있습니다 '
                           '(레시피 칸에 들어간 것일 수 있습니다)')
                break

    # 보드가 정본 실측을 읽나
    n += 1
    if b and 'maindata-v1' not in b:
        bad.append('지형 보드가 수치 출처를 안 밝힙니다 (정본이 아닐 수 있습니다)')

    # 7. 문단 폭 제한.
    #    ★ 판정은 빌드 관문 `widthcheck` 를 «그대로 빌려 쓴다». 처음엔 여기에
    #      정규식을 따로 적었는데, 그것이 `/* 폭허용: */` 예외 표기를 몰라
    #      빌드가 0곳이라 한 것을 여기서 3건으로 셌다. 같은 규칙을 두 곳에
    #      따로 적으면 반드시 갈라진다 (오늘 이 부류만 여러 번 봤다).
    n += 1
    try:
        _here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(os.path.dirname(_here), 'web', '_build'))
        import widthcheck as _wc
        for name, t in (('hub', hub), ('프로토콜', proto), ('벤치마크', bench)):
            got = _wc.scan_text(t, name)
            if got:
                bad.append('%s 에 문단 폭 제한이 %d곳 남았습니다: %s'
                           % (name, len(got), got[0][1][:60]))
    except Exception as e:
        bad.append('문단 폭 검사를 못 돌렸습니다: %s' % str(e)[:60])

    # 12. 프로토콜 페이지의 전역바 활성 항목
    n += 1
    g = re.search(r'(?s)<!--gnav:v1-->(.*?)<!--/gnav:v1-->', proto)
    on = re.findall(r'class="[^"]*\bon\b[^"]*"[^>]*>([^<]+)<', g.group(1)) if g else []
    if on != ['연구']:
        bad.append('프로토콜 페이지 전역바 활성이 %s 입니다 (연구여야 합니다)' % on)

    # 11. 두 문서가 허브에서 찾아지나
    n += 1
    for key, label in (('research-20260911-eval-protocol-v2', '프로토콜'),
                       ('research-generalization-benchmark-10', '벤치마크')):
        if key not in hub:
            bad.append('연구 허브에서 %s 문서로 가는 길이 없습니다' % label)

    # em dash
    n += 1
    for name, t in (('hub', hub), ('프로토콜', proto), ('벤치마크', bench)):
        if '—' in t:
            bad.append('%s 에 em dash 가 %d개 있습니다' % (name, t.count('—')))

    # ── 좁은 화면 ──────────────────────────────────────────────
    # ★ 2026-09-14. 팀장이 폰에서 표가 뭉개지는 것을 잡았다. 나는 1568 px 에서만
    #   재고 「됐다」고 보고했다. 두 번 그랬다 (갤러리 거르개 · 이 표).
    #
    #   진짜 폭 측정은 브라우저가 있어야 한다. 여기서는 **그 사고를 만든 구조**
    #   를 본다. 규칙 판정은 `tablefix.blocky` 를 그대로 빌려 쓴다 · 문자열을
    #   찾는 대신 «표를 겨눈 규칙인가» 를 파싱해서 본다.
    n += 1
    try:
        _here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(os.path.dirname(_here), 'web', '_build'))
        import tablefix as _tf
        squash = []
        for f in sorted(os.listdir(out)):
            if not f.endswith('.html'):
                continue
            for sel, body in _tf.blocky(read(out, f) or ''):
                squash.append('%s: %s{%s}' % (f, sel[:40], body[:40]))
        if squash:
            bad.append('표를 짜부라뜨리는 규칙 %d곳: %s'
                       % (len(squash), ' · '.join(squash[:2])))
    except Exception as e:
        bad.append('표 규칙 검사를 못 돌렸습니다: %s' % str(e)[:60])

    # 표를 «펴는» 규칙이 살아 있나.
    #
    # ★ 이것은 «구조 검사» 다. 진짜 폭은 브라우저만 잴 수 있고, 그 실측은
    #   아래 숫자로 남겨 뒀다 (iframe 390/430/768/1280 px · 표 69개):
    #     머리말 2줄 이상 17개 -> 0개 · 짧은 토큰 쪼개짐 6건 -> 0건
    #   여기서 막는 것은 «그 규칙이 사라지거나 뒤집히는 것» 이다. 실제로
    #   2026-08-28 에 `min-width:420px` 이 들어간 뒤 `searchbox` 의
    #   `min-width:0` 이 그것을 조용히 무력화했고 17일간 아무도 못 봤다.
    #
    #   문자열을 찾지 않고 «선언» 을 파싱한다. 주석 안의 같은 글자에 속지
    #   않으려고 먼저 주석을 걷어낸다.
    n += 1
    css = ''
    for f in sorted(os.listdir(out)):
        if f.endswith('.css'):
            css += read(out, f) or ''
    if not css:
        css = proto
    bare = re.sub(r'/\*.*?\*/', ' ', css, flags=re.S)

    def decl(sel_re, prop):
        """`sel{...}` 를 찾아 그 안의 prop 값을 돌려준다 (마지막 선언이 이긴다)."""
        hit = None
        for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', bare):
            if not re.search(sel_re, m.group(1)):
                continue
            for d in m.group(2).split(';'):
                if ':' not in d:
                    continue
                k, v = d.split(':', 1)
                if k.strip() == prop:
                    hit = v.strip()
        return hit

    mw = decl(r'(?:^|[\s,>+~])table(?![\w.-])', 'min-width')
    if mw is None:
        bad.append('표에 min-width 선언이 없습니다 (좁은 화면에서 짜부라집니다)')
    elif mw != 'max-content':
        bad.append('표의 min-width 가 «%s» 입니다 (max-content 여야 합니다)' % mw)
    # ★ anywhere 는 «마지막이 이긴다» 로 보면 안 된다. 뒤에 좁은 셀렉터로
    #   `normal` 을 덮어 두면 앞의 anywhere 가 가려져 검사를 빠져나간다.
    #   실제로 첫 판이 그래서 repro-m 의 anywhere 를 못 잡았다. 우리는 이 값을
    #   표에서 «아예 안 쓰기로» 했으니 어느 규칙에 있든 잡는다.
    ow = []
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', bare):
        if not re.search(r'(?:^|[\s,>+~])(?:th|td)(?![\w.-])', m.group(1)):
            continue
        for d in m.group(2).split(';'):
            k, _, v = d.partition(':')
            if k.strip() == 'overflow-wrap' and v.strip() == 'anywhere':
                ow.append(m.group(1).strip()[:40])
    if ow:
        bad.append('칸에 overflow-wrap:anywhere 가 %d곳 있습니다 (%s) '
                   '· min-content 를 한 글자로 무너뜨려 「100」이 1/0/0 이 됩니다'
                   % (len(ow), ' · '.join(ow[:2])))

    # 파비콘. ★ 2026-09-14 팀장 확인 요청: 「파비콘 없어진 거 아니지?」
    #   한 장만 보면 안 된다. **전수** 로 세고, 가리키는 파일이 실제로 있는지와
    #   그 파일이 «그림인지» 까지 본다. 빈 SVG 도 링크는 멀쩡해 보인다.
    n += 1
    noicon, dead, empty = [], [], []
    for f in sorted(os.listdir(out)):
        if not f.endswith('.html'):
            continue
        t = read(out, f) or ''
        links = re.findall(r'<link[^>]*rel="[^"]*\bicon\b[^"]*"[^>]*>', t)
        if not links:
            noicon.append(f)
            continue
        for L in links:
            m = re.search(r'href="([^"]+)"', L)
            if not m:
                dead.append((f, L[:40]))
                continue
            rel = m.group(1).split('?')[0].lstrip('/')
            p = os.path.join(out, rel.replace('/', os.sep))
            if not os.path.isfile(p):
                dead.append((f, m.group(1)))
            elif rel.endswith('.svg'):
                s = io.open(p, encoding='utf-8', errors='replace').read()
                if '<svg' not in s or not re.search(
                        r'<(path|circle|rect|polygon|ellipse|use)', s):
                    empty.append(rel)
    if noicon:
        bad.append('파비콘 링크가 없는 페이지 %d장: %s'
                   % (len(noicon), ' '.join(noicon[:3])))
    if dead:
        bad.append('파비콘이 없는 파일을 가리킵니다: %s'
                   % ' '.join('%s -> %s' % d for d in dead[:3]))
    if empty:
        bad.append('파비콘 SVG 에 그림이 없습니다: %s'
                   % ' '.join(sorted(set(empty))[:3]))
    return n


def selftest(out):
    """알려진 답. 산출물을 고의로 망가뜨리면 잡아야 한다."""
    hub = read(out, 'hub-research.html')
    if hub is None:
        print('  [!] 자기시험을 못 돌립니다 (산출물 없음)')
        return False
    p = os.path.join(out, 'hub-research.html')
    orig = hub
    cases = [
        # ★ 한 곳만 지우면 안 된다. 「진단·분석」은 두 자리에 붙어 있어서
        #   하나를 지워도 «묶음 6종» 은 그대로다. 즉 이 시험이 아무것도 안
        #   재고 있었다. 기준선 대조를 넣고 나서야 [X]놓침 으로 드러났다.
        ('묶음 하나 지움', lambda s: s.replace('data-label="진단·분석"', '')),
        ('옛 묶음 이름 되살림',
         lambda s: s.replace('data-label="조사·비교"',
                             'data-label="외부 자료 조사"', 1)),
        ('보드 출처 지움', lambda s: s.replace('maindata-v1', 'oldrun', 1)),
        ('em dash 넣음', lambda s: s.replace('<body', '<body data-x="—"', 1)),
    ]
    # ★ 기준선을 먼저 잰다. 이것이 없으면 «원래 나던 오류» 가 주입한 결함을
    #   가려 4/4 로 찍힌다. 실제로 그랬다: report-v1 파비콘 오류가 늘 나고
    #   있어서 「묶음 하나 지움」이 안 잡혀도 통과로 읽혔다. 관문이 무엇을
    #   근거로 통과했는지 대지 못하면 그 관문은 아직 시험되지 않은 것이다.
    # ★ 이 시험은 «대상 폴더의 진짜 파일» 을 고쳤다 되돌린다. 되돌림이
    #   빠지면 배포본이 오염된 채 남는다. 실제로 2026-09-14 에 그랬다:
    #   편집하다 되돌림 줄을 함께 지웠고, 두 번 돌린 시험이 배포 트리에
    #   `data-x="—"` 를 박아 두었는데 아무 오류도 안 났다.
    #   그래서 finally 로 되돌리고, 되돌린 뒤 «바이트로» 대조한다.
    base = []
    checks(out, base)
    base = set(base)
    if base:
        print('  기준선 오류 %d건 (이것들은 안 센다): %s'
              % (len(base), (' · '.join(sorted(base)))[:66]))
    ok = 0
    try:
        for name, f in cases:
            s = f(orig)
            if s == orig:
                print('  [!] %-18s 주입 실패' % name)
                continue
            io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
            bad = []
            checks(out, bad)
            fresh = [x for x in bad if x not in base]   # «새로» 생긴 것만 센다
            if fresh:
                ok += 1
                print('  잡음   %-18s %s' % (name, fresh[0][:52]))
            else:
                print('  [X]놓침 %-18s (기준선 밖 새 오류 없음)' % name)
    finally:
        io.open(p, 'w', encoding='utf-8', newline='\n').write(orig)
        back = io.open(p, encoding='utf-8').read()
        if back != orig:
            print('  [!!] 되돌림 실패. %s 가 원본과 다릅니다' % p)
            return False
        print('  원본 되돌림 확인 (바이트 일치)')
    print('  %d/%d' % (ok, len(cases)))
    return ok == len(cases)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = os.path.abspath(args[0]) if args else None
    if not out or not os.path.isdir(out):
        print('  쓰는 법: python tools/predeploy.py <산출폴더> [--selftest]')
        return 2
    print('  대상 %s' % out)
    if '--selftest' in sys.argv:
        return 0 if selftest(out) else 1
    bad = []
    n = checks(out, bad)
    print('  검사 %d항목' % n)
    if n < 8:
        print('  [!] 검사한 것이 너무 적습니다. 통과로 안 읽습니다')
        return 1
    if bad:
        print('  [!] 어긋난 것 %d건' % len(bad))
        for x in bad:
            print('      ' + x)
        return 1
    print('  팀장이 지적한 항목이 전부 산출물에 반영돼 있습니다')
    return 0


if __name__ == '__main__':
    sys.exit(main())
