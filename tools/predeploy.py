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

    # 7. 문단 폭 제한
    n += 1
    for name, t in (('hub', hub), ('프로토콜', proto), ('벤치마크', bench)):
        if re.search(r'max-width\s*:\s*\d+(\.\d+)?ch', t):
            bad.append('%s 에 문단 폭 제한이 남았습니다' % name)

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
        ('묶음 하나 지움', lambda s: s.replace('data-label="진단·분석"', '', 1)),
        ('옛 묶음 이름 되살림',
         lambda s: s.replace('data-label="조사·비교"',
                             'data-label="외부 자료 조사"', 1)),
        ('보드 출처 지움', lambda s: s.replace('maindata-v1', 'oldrun', 1)),
        ('em dash 넣음', lambda s: s.replace('<body', '<body data-x="—"', 1)),
    ]
    ok = 0
    for name, f in cases:
        s = f(orig)
        if s == orig:
            print('  [!] %-18s 주입 실패' % name)
            continue
        io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
        bad = []
        checks(out, bad)
        if bad:
            ok += 1
            print('  잡음   %-18s %s' % (name, bad[0][:52]))
        else:
            print('  [X]놓침 %-18s' % name)
    io.open(p, 'w', encoding='utf-8', newline='\n').write(orig)
    print('  %d/%d · 원본 되돌림' % (ok, len(cases)))
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
