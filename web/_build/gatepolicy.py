# -*- coding: utf-8 -*-
"""관문이 «무엇을 안 막는가» 를 적어 두었는가 (DESIGN.md §13-3).

★ 2026-09-18 팀장 확정. 9/14 에 하루 동안 관문이 여섯 늘었고, 기준이 제각각으로
  자라고 있었다. 정책 셋이 §13 에 있고 이 관문은 그중 셋째만 본다.

왜 이것이 관문이어야 하나
  §13 을 문서로만 적으면 다음 사람이 안 읽는다. 이 저장소가 그것을 여러 번
  겪었다 (DESIGN.md §11 「문서에 규칙이 있어도 새 컴포넌트에 옮겨 적지 않으면
  그대로 재발한다」). 그래서 «적었는가» 만이라도 기계가 본다.

무엇을 보나
  `build.py` 가 부르는 검사 모듈의 «파일 첫머리 설명» 에 아래 표식이 있는가.

      못 잡는 것:     /  안 잡는 것:  /  못 보는 것:  /  안 보는 것:

  표식 뒤에 한 줄이라도 있으면 통과다.

★ 이 관문이 «못 잡는 것»
  - **적힌 내용이 맞는지는 못 본다.** 「없음」 한 줄이면 통과한다. 그건 사람이
    읽고 판단한다. 기계가 할 수 있는 것은 «빈칸으로 두지 못하게» 하는 것뿐이다.
  - `build.py` 안에 직접 쓰인 검사(모듈을 안 부르는 것)는 못 본다. 모듈 단위로
    센다. 그 자리는 §13 을 사람이 지켜야 한다.
  - 관문이 «막을지 알릴지»(§13-2)는 못 본다. 그 판단에는 「이 결함이 되돌릴 수
    있는가」가 필요하고, 그건 코드에 안 적혀 있다.

명부 (§13-1)
  켜는 날 안 적혀 있던 모듈은 `gatepolicy_grandfather.txt` 에 담는다.
  **새로 생기는 관문만 막는다.** 명부의 줄 수가 남은 일의 크기다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, 'gatepolicy_grandfather.txt')

# 「무엇을 안 막는가」를 적는 표식. 말투를 강제하지 않는다.
MARKS = ('못 잡는 것', '안 잡는 것', '못 보는 것', '안 보는 것',
         '못 막는 것', '안 막는 것')

# `build.py` 가 검사로 부르는 모듈. 이름이 아니라 «부르는 모양» 으로 찾는다.
CALL = re.compile(r'if not (\w+)\.(\w+)\(')

# 검사가 아닌 것. 생성·주입은 §13 의 대상이 아니다 (실패하면 서는 게 옳다).
NOT_A_GATE = {
    'build', 'buildtime', 'hubgen', 'wiki_import', 'mdpage', 'searchbox',
    'stamp', 'docs_pages', 'hub3', 'ia', 'roots', 'scan',
}


def declares(text):
    """설명 첫머리에 «안 막는 것» 이 적혀 있나. 표식 뒤에 내용이 있어야 한다."""
    for mk in MARKS:
        i = text.find(mk)
        if i < 0:
            continue
        tail = text[i + len(mk):i + len(mk) + 400]
        # 표식 줄과 그 다음 줄들에서 «글자» 를 찾는다. 표식만 있고 비면 안 된다.
        # ★ 첫 판은 남은 글자 수만 셌다가 «닫는 따옴표» 를 내용으로 세어 빈
        #   표식을 통과시켰다. 자기시험이 잡았다. 글자·숫자만 센다.
        body = tail.split('"""')[0].split("'''")[0]
        real = [c for c in body if c.isalnum()]
        if len(real) >= 2:
            return True
    return False


def gate_modules(root):
    """`build.py` 에서 «검사로 불리는» 모듈 이름을 뽑는다."""
    p = os.path.join(root, 'build.py')
    src = io.open(p, encoding='utf-8', errors='replace').read()
    out = set()
    for mod, _fn in CALL.findall(src):
        if mod in NOT_A_GATE or mod.startswith('_'):
            continue
        if os.path.isfile(os.path.join(root, mod + '.py')):
            out.add(mod)
    return sorted(out)


def _selftest():
    """알려진 답으로 먼저 시험한다 (커널 원칙 1)."""
    cases = [
        ('표식 뒤에 내용이 있다',
         '"""무엇을 본다.\n\n못 잡는 것: 적힌 내용이 맞는지.\n"""', True),
        ('표식만 있고 비었다', '"""무엇을 본다.\n\n못 잡는 것:\n"""', False),
        ('표식이 없다', '"""무엇을 본다. 그냥 설명만 있다."""', False),
        ('다른 말투도 받는다',
         '"""설명.\n\n★ 이 관문이 «안 보는 것»\n  - 남의 저장소\n"""', True),
        ('본문 한가운데 있어도 받는다',
         '"""긴 설명이 먼저 나오고\n여러 줄 뒤에\n못 보는 것 · 실행 기록이 없는 사실\n"""', True),
    ]
    bad = [n for n, t, want in cases if declares(t) is not want]
    if bad:
        print('  [!] 자기시험 실패: %s' % ' · '.join(bad))
        return False
    print('  자가검증 %d/%d 통과' % (len(cases), len(cases)))
    return True


def read_ledger():
    if not os.path.isfile(LEDGER):
        return set()
    return {ln.strip() for ln in io.open(LEDGER, encoding='utf-8')
            if ln.strip() and not ln.startswith('#')}


def write_ledger(got):
    head = [
        '# 「무엇을 안 막는가」가 아직 안 적힌 관문 (DESIGN.md §13-3).',
        '#',
        '# 명부는 면제가 아니다. 이 줄 수가 남은 일의 크기다.',
        '# 새로 생기는 관문은 명부에 못 들어간다. 적고 만들어야 한다.',
        '',
    ]
    io.open(LEDGER, 'w', encoding='utf-8').write(
        '\n'.join(head + sorted(got)) + '\n')


def main(root=None):
    if not _selftest():
        print('  [!] 이 관문 자체가 틀렸습니다. 결과를 믿지 마십시오')
        return False
    root = root or HERE

    mods = gate_modules(root)
    # ★ 「검사할 것이 없었다」와 「위반이 없었다」는 다른 사실이다 ([3.44])
    if not mods:
        print('  [!] 검사 모듈을 한 개도 못 찾았습니다. 검사가 헛돌았습니다')
        return False

    missing = set()
    for m in mods:
        t = io.open(os.path.join(root, m + '.py'),
                    encoding='utf-8', errors='replace').read(4000)
        if not declares(t):
            missing.add(m + '.py')

    old = read_ledger()
    new = missing - old
    gone = old - missing
    print('  검사 모듈 %d개 · 「안 막는 것」을 적은 것 %d개 (명부 %d)'
          % (len(mods), len(mods) - len(missing), len(old)))
    if gone:
        print('  적어 넣은 것 %d개: %s' % (len(gone), ' · '.join(sorted(gone))))
        write_ledger(missing)
    if new:
        print('  [!] 「무엇을 안 막는가」가 없는 관문이 새로 생겼습니다')
        for m in sorted(new):
            print('      %s' % m)
        print('      그 모듈 첫머리 설명에 아래 표식으로 한 줄 적으십시오.')
        print('        ★ 이 관문이 «못 잡는 것»')
        print('      까닭은 DESIGN.md §13-3 에 있습니다. 안 적으면 다음 사람이')
        print('      이 관문을 안전망으로 착각합니다.')
        return False
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
