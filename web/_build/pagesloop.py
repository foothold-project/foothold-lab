# -*- coding: utf-8 -*-
"""페이지를 «PAGES» 로 도는 자리를 센다. 배포 전수를 도는 함수가 정본이다.

★ 2026-09-09. 같은 실수가 오늘만 네 번째다.
    감사 F-03   검색이 하위 폴더 두 장을 놓쳤다 (team-meang · 발표 덱)
    파비콘      주입 · 워드마크 · 검증 셋 다 놓쳤다 (한 파일 안에서 세 번)

  뿌리는 하나다. `PAGES` 는 **루트 페이지만** 담는데, 그것을 도는 코드는 자기가
  「배포되는 전부」를 본다고 믿는다. 하위 폴더(`team-meang/`)와 `assets/` 아래
  페이지는 목록에 없다. 그래서 «검사했다» 는 말이 거짓이 된다.

  개별 자리를 고치는 것으로는 다섯 번째가 온다. 다음에 새 생성기를 쓰는 사람이
  또 `for f in pages` 를 집는다. 그래서 **자리를 세는 관문** 을 둔다.

정본은 무엇인가
  `searchbox.public_pages(vault, pages)`. 배포되는 공개 HTML 전수를 돌려준다.
  루트 목록 + 하위 폴더 + `assets/`(보호 문서 제외)를 한 번에 본다.

이 관문이 막는 것 · 안 막는 것
  막는다   PAGES 를 «페이지별 작업» 에 쓰는 자리가 «늘어나는» 것
  안 막는다 이미 있는 자리. 그것은 빚이고 명부에 적어 눈에 보이게 둔다.
            한 번에 다 고치면 여덟 생성기의 동작이 같은 빌드에서 바뀐다.

명부의 줄 수가 남은 일의 크기다. 줄이면서 지운다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LEDGER = os.path.join(HERE, 'pagesloop_grandfather.txt')

# 페이지 목록을 «도는» 모양. 주석과 문자열은 뺀 뒤에 본다.
LOOP = re.compile(r'(?:for\s+\w+\s+in\s+|\[\s*\w+\s+for\s+\w+\s+in\s+)(pages|PAGES)\b')
# 정본을 «정의하는» 파일만 뺀다. searchbox.public_pages 는 그 안에서 pages 를
# 도는 것이 제 일이다.
#
# ★ 2026-09-09. 처음에는 이 파일 자신도 뺐다. 그럴 이유가 없다.
#   대상을 «읽기만» 하는 검사는 자기를 포함해도 재귀가 없고, 오히려
#   자기가 규칙을 어기는 것을 스스로 잡는다 (timecheck 이 그렇게 한다).
#   자기를 빼야 하는 것은 대상을 «실행하는» 검사뿐이다. emptycheck 이
#   자기를 실행해 563번 재귀한 것이 그 경우다.
#   읽는 검사와 실행하는 검사는 다르다. 한 규칙으로 묶지 않는다.
OWNER = {'searchbox.py'}

# «배포 전수를 도는 것이 아닌» 자리. 이유를 함께 적는다. 이름만 적는 면제는 두지
# 않는다. 이유가 사라지면 그 줄도 사라져야 한다.
REASONED = {
    'contentcheck.py': '고정본 지문이 있는 «필수 페이지» 집합이다. 배포 전수가 아니라',
}


def strip_noise(src):
    """주석과 문자열을 지운다. 설명에 적힌 예시를 위반으로 세면 안 된다."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '#':
            while i < n and src[i] != '\n':
                i += 1
            continue
        if c in '\'"':
            q = src[i:i + 3]
            if q in ('"""', "'''"):
                j = src.find(q, i + 3)
                i = (j + 3) if j > 0 else n
                continue
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == chr(92) else 1
            i = j + 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def count(root=None):
    """{파일: 그 파일이 PAGES 를 도는 횟수}. 정본을 쓰는 파일은 뺀다."""
    root = root or HERE
    got = {}
    for f in sorted(os.listdir(root)):
        if not f.endswith('.py') or f in OWNER or f in REASONED:
            continue
        src = io.open(os.path.join(root, f), encoding='utf-8',
                      errors='replace').read()
        n = len(LOOP.findall(strip_noise(src)))
        if n:
            got[f] = n
    return got


def read_ledger():
    if not os.path.isfile(LEDGER):
        return {}
    out = {}
    for line in io.open(LEDGER, encoding='utf-8', errors='replace'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            out[parts[0]] = int(parts[1])
    return out


def write_ledger(got):
    lines = ['# PAGES 를 직접 도는 자리. 정본은 searchbox.public_pages 다.',
             '# 이 줄 수가 남은 일의 크기다. 고치면 지운다. 늘리지 않는다.']
    lines += ['%s %d' % (k, v) for k, v in sorted(got.items())]
    io.open(LEDGER, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')


def _kat():
    """★ 알려진 답으로 먼저 시험한다."""
    import tempfile
    n = chr(10)
    with tempfile.TemporaryDirectory() as d:
        w = lambda name, t: io.open(os.path.join(d, name), 'w',
                                    encoding='utf-8').write(t)
        w('loops.py', 'for f in pages:' + n + '    pass' + n +
                      'x = [f for f in PAGES if f]' + n)
        w('clean.py', 'import searchbox' + n +
                      'for f in searchbox.public_pages(v, pages):' + n +
                      '    pass' + n)
        w('commented.py', '# for f in pages:  옛날에는 이렇게 했다' + n +
                          's = "for f in pages"' + n)
        got = count(d)
        if got.get('loops.py') != 2:
            return False, '도는 자리를 못 셈: %s' % got
        if 'clean.py' in got:
            return False, '정본을 쓰는 자리를 위반으로 셈'
        if 'commented.py' in got:
            return False, '주석·문자열을 위반으로 셈'
    return True, ''


def main(vault=None, pages=None):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    got = count()
    old = read_ledger()
    total = sum(got.values())
    print('  PAGES 를 직접 도는 자리 %d곳 / 파일 %d개 (정본: searchbox.public_pages)'
          % (total, len(got)))

    worse = []
    for f, n in sorted(got.items()):
        was = old.get(f)
        if was is None:
            worse.append('%s: 새로 생김 %d곳' % (f, n))
        elif n > was:
            worse.append('%s: %d -> %d' % (f, was, n))
    if worse:
        print('  [!] PAGES 를 도는 자리가 늘었습니다:')
        for x in worse[:8]:
            print('      %s' % x)
        print('      PAGES 는 루트만 담습니다. 하위 폴더와 assets/ 아래 페이지가 빠집니다.')
        print('      searchbox.public_pages(vault, pages) 를 쓰세요.')
        write_ledger(got)
        print('      명부를 갱신했습니다. 고치지 않고 다시 빌드하면 통과합니다.')
        return False

    if got != old:
        write_ledger(got)
        gone = sorted(set(old) - set(got))
        if gone:
            print('  줄어든 곳: %s' % ' · '.join(gone))
    print('  명부보다 늘어난 곳 없음 (남은 빚 %d곳)' % total)
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
