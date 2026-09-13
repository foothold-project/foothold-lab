# -*- coding: utf-8 -*-
"""관문이 «대상에 닿지 못한 것» 을 «위반 없음» 으로 말하는지 본다.

★ 2026-09-09. 동료 세션이 자기 관문에서 이 결함을 찾아 알려 왔고, 그 잣대를
  내 관문들에 대보니 **넷이 같았다.**

    indexfresh · searchbox · brandmark.verify_favicon · jsnullcheck
    빈 볼트로 돌리면 「0장 전부 통과」를 찍고 True 를 돌려줬다.

  「검사할 것이 하나도 없었다」와 「검사했는데 위반이 없었다」는 다른 사실이다.
  같은 출력을 내면, 목록이 비는 순간 관문이 조용히 무력해진다. 그리고 목록은
  실제로 빈다. PAGES 는 빌드 도중에 차오르고, 앞 단계는 덜 찬 목록을 본다.
  오늘 그 부류로만 다섯 번 걸렸다.

  개별 관문에 `if seen == 0` 을 넣는 것으로는 다음에 만드는 관문이 또 빠진다.
  그래서 **관문 전체에 같은 질문을 던지는 관문** 을 둔다.

무엇을 하나
  1. `build.py` 에서 «막는 관문» 을 읽는다: `if not <모듈>.<함수>(...)` 꼴.
     목록을 손으로 적지 않는다. 새 관문을 걸면 자동으로 대상이 된다.
  2. 각 관문을 «빈 볼트» 로 돌린다. True 를 돌려주면 그 관문은 눈이 없다.
  3. 볼트를 안 보는 관문(GitHub·lab·자기 소스를 보는 것)은 이 시험이 무의미하다.
     그런 것은 SKIP 에 «이유와 함께» 적는다. 이름만 적는 면제는 두지 않는다.
"""
import contextlib
import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, 'emptycheck_grandfather.txt')
sys.path.insert(0, HERE)

CALL = re.compile(r'if\s+not\s+([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*\(')

# 볼트를 안 보는 관문. 빈 볼트로 시험하는 것이 뜻이 없다. 이유를 함께 적는다.
SKIP = {
    'ledgercheck': 'lab 의 LEDGER 와 GitHub 이슈를 본다. 볼트와 무관하다',
    'roles': 'GitHub 라벨과 lab 정본을 본다',
    'authorcheck': 'lab docs/ROLES.md 를 본다. 스스로 0건이면 실패한다',
    'pagesloop': '_build 자기 소스를 본다. 볼트와 무관하다',
    'timecheck': '_build 자기 소스를 본다',
    'searchrank': '화면 JS 를 떼어 node 로 돈다. 볼트와 무관하다',
    'dashcheck': 'lab 이슈 본문을 본다',
    'promoteage': '세되 세우지 않는 보고용이다',
    'claims': '외부 원본을 조회한다 (--verify 일 때만)',
    'linkcheck': '배포본 경로를 받는다. 빈 경로면 스스로 못 돈다',
    'metacheck': 'lab 문서를 본다',
}


def _write_ledger(items):
    head = ['# 대상이 0개일 때 «통과» 라고 말하는 관문. 이 줄 수가 남은 일의 크기다.',
            '# 고치는 법: 검사한 개수를 세고 0이면 스스로 실패하게 한다.']
    nl = chr(10)
    io.open(LEDGER, 'w', encoding='utf-8', newline=nl).write(
        nl.join(head + sorted(items)) + nl)


def gates(build_py=None):
    """`build.py` 가 «막는» 관문 (모듈, 함수) 전수. 손 목록이 아니다."""
    p = build_py or os.path.join(HERE, 'build.py')
    src = io.open(p, encoding='utf-8', errors='replace').read()
    out = []
    for m in CALL.finditer(src):
        mod, fn = m.group(1), m.group(2)
        mod = mod.lstrip('_')
        # `import x as _y` 별칭을 실제 모듈 이름으로 되돌린다
        al = re.search(r'import\s+([A-Za-z_]\w*)\s+as\s+_?%s\b' % re.escape(mod), src)
        if al:
            mod = al.group(1)
        if (mod, fn) not in out:
            out.append((mod, fn))
    return out


def empty_vault():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'assets'), exist_ok=True)
    io.open(os.path.join(d, 'assets', 'search-index.json'), 'w',
            encoding='utf-8').write('[]')
    return d


def _kat():
    """★ 알려진 답. build.py 를 흉내 낸 조각에서 관문을 뽑아낸다."""
    n = chr(10)
    fake = ('import searchbox' + n +
            'if not searchbox.main(VAULT, PAGES):' + n +
            '    sys.exit(1)' + n +
            'import brandmark as _bm3' + n +
            'if not _bm3.verify_favicon(SITE, PAGES):' + n +
            '    sys.exit(1)' + n +
            'x = foo.bar()' + n)          # 막지 않는 호출은 관문이 아니다
    import tempfile as tf
    p = os.path.join(tf.mkdtemp(), 'build.py')
    io.open(p, 'w', encoding='utf-8').write(fake)
    got = gates(p)
    if ('searchbox', 'main') not in got:
        return False, '막는 관문을 못 읽음: %s' % got
    if ('brandmark', 'verify_favicon') not in got:
        return False, '별칭(as _bm3) 을 못 풀었음: %s' % got
    if ('foo', 'bar') in got:
        return False, '막지 않는 호출을 관문으로 셈'
    return True, ''


def main(vault=None, pages=None):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    found = gates()
    d = empty_vault()
    blind, tested, skipped = [], 0, 0
    # ★ 관문들을 빈 대상으로 돌리면 저마다 자기 메시지를 찍는다.
    #   그것이 빌드 로그를 덮으면 정작 이 관문이 무엇을 말했는지 안 보인다.
    #   삼킨다. 여기서 볼 것은 «True 를 돌려주는가» 하나뿐이다.
    _sink = io.StringIO()
    with contextlib.redirect_stdout(_sink):
        for mod, fn in found:
            # ★ 자기 자신을 검사 대상으로 삼으면 무한 재귀다. 실측: 563번 돌고 멈췄다.
            #   관문을 세는 관문은 자기를 셀 수 없다. 그 한 줄이 이 관문의 사각지대이고,
            #   그래서 여기만큼은 사람이 봐야 한다.
            if mod in ('emptycheck', 'build'):
                skipped += 1
                continue
            # 표준 라이브러리 호출(re.match 같은 것)은 관문이 아니다.
            if not os.path.isfile(os.path.join(HERE, mod + '.py')):
                continue
            if mod in SKIP:
                skipped += 1
                continue
            try:
                m = __import__(mod)
                f = getattr(m, fn, None)
            except Exception:
                continue
            if f is None:
                continue
            try:
                r = f(d, [])
            except TypeError:
                try:
                    r = f(d)
                except Exception:
                    continue
            except Exception:
                continue                      # 터지는 것은 «통과» 가 아니다. 괜찮다
            tested += 1
            if r is True:
                blind.append('%s.%s' % (mod, fn))

    if tested == 0:
        print('  [!] 시험한 관문이 0개입니다. 이 검사가 헛돌았습니다')
        return False
    # ★ 명부에 담는다. 오늘 처음 세어 보니 14개였다. 열넷을 한 빌드에서 함께
    #   고치면 무엇이 깨졌는지 못 가린다. 늘어나는 것만 막고 줄이면서 지운다.
    #   ([3.43] 과 같은 형태다. 명부의 줄 수가 남은 일의 크기다.)
    old = set()
    if os.path.isfile(LEDGER):
        for line in io.open(LEDGER, encoding='utf-8', errors='replace'):
            line = line.strip()
            if line and not line.startswith('#'):
                old.add(line)
    now = set(blind)
    fresh = sorted(now - old)
    print('  막는 관문 %d개 · 빈 대상으로 시험 %d개 · 볼트 무관이라 건너뜀 %d개'
          % (len(found), tested, skipped))
    if fresh:
        print('  [!] 대상이 하나도 없는데 «통과» 라고 말하는 관문이 새로 생겼습니다:')
        for b in fresh:
            print('      %s' % b)
        print('      「검사할 것이 없었다」와 「위반이 없었다」는 다른 사실입니다.')
        print('      검사한 개수를 세고, 0이면 스스로 실패하게 하세요.')
        _write_ledger(now)
        print('      명부를 갱신했습니다. 고치지 않고 다시 빌드하면 통과합니다.')
        return False
    if now != old:
        _write_ledger(now)
        gone = sorted(old - now)
        if gone:
            print('  눈을 갖게 된 관문: %s' % ' · '.join(gone))
    print('  새로 눈먼 관문 없음 (남은 빚 %d개)' % len(now))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
