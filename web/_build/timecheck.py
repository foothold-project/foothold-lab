# -*- coding: utf-8 -*-
"""시간 입력이 `buildtime` 밖에서 새는지 본다 (mai-os#22 · 묶음 6.5).

  왜 관문이 필요한가
    시간 호출을 한 번 모아도 다음 생성기가 다시 `date.today()` 를 쓰면 재현이 깨진다.
    「모았다」가 아니라 「계속 모여 있는가」를 물어야 한다 (철칙 4).

  ★ 검사 대상은 «시간» 뿐이다
    datetime.now · datetime.utcnow · date.today · time.time
    getmtime · stat().st_mtime · PowerShell Get-Date

  ★ os.urandom 은 검사 대상이 아니다
    그것은 암호 난수이고 결정론화하면 AES-GCM 의 IV 유일성 요구를 깬다.
    오히려 `secure_docs.py` 에 **있어야** 한다. 사라지면 그것이 사고다.
    이 관문은 그 존재도 함께 확인한다.

  주석은 위반이 아니다
    「전에는 Get-Date 를 썼다」 같은 설명까지 잡으면 이력을 못 적는다.
    코드 줄만 본다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

OWNER = 'buildtime.py'          # 시간 입력을 소유하는 유일한 파일
TIME_CALLS = re.compile(
    r'datetime\.now\s*\(|datetime\.utcnow\s*\(|\bdate\.today\s*\(|'
    r'\btime\.time\s*\(|\bgetmtime\s*\(|\.st_mtime\b|Get-Date')

# 암호 난수는 여기 있어야 한다. 사라지면 알린다.
#   ★ 2026-09-02 (묶음 6.6). 암호화가 secure_docs 에서 enc_reuse 로 옮겨졌다.
#     관문이 옛 자리를 계속 보면 «있다» 고 말하면서 실제로는 아무것도 안 지킨다.
#     난수가 사는 자리를 옮기면 이 표도 함께 옮긴다.
CRYPTO_RANDOM = {'enc_reuse.py': ('os.urandom',)}


def _strip_comments(text):
    """주석과 문자열 리터럴을 지운다. 코드 줄만 남긴다.

    설명문에 적힌 «Get-Date» 를 위반으로 세면 이력을 못 적는다.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '#':
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        if c in '"\'':
            q3 = text[i:i + 3]
            if q3 in ('"""', "'''"):
                j = text.find(q3, i + 3)
                i = n if j < 0 else j + 3
                continue
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == chr(92) else 1
            i = j + 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def build_modules(root):
    """`build.py` 에서 import 로 «닿는» 모듈만. 빌드가 안 부르는 파일은 대상이 아니다.

    ★ 2026-09-09. 이 관문이 `livecheck.py` 의 시간 호출을 잡아 배포를 세웠다.
      그 파일은 배포 «뒤» 에 라이브가 올라갔는지 확인하는 도구다. 산출물을 한
      글자도 쓰지 않는다. 기다리는 데 쓰는 시계는 재현성과 무관하고, 오히려
      buildtime(빌드 내내 멈춰 있는 시계)로 바꾸면 영원히 기다리게 된다.

      그렇다고 이름을 적어 빼면(면제 목록) 그 목록이 낡는다. 이 저장소는 그런
      목록이 어떻게 썩는지 이미 여러 번 봤다.

      그래서 «빌드가 그 파일을 부르는가» 로 정한다. 나중에 누가 livecheck 를
      빌드에 import 하면 그 순간 다시 검사 대상이 된다. 스스로 갱신되는 규칙이다.
    """
    names = set(f for f in os.listdir(root) if f.endswith(".py"))
    seen, todo = set(), ['build.py']
    pat = re.compile(r'^\s*(?:import|from)\s+([A-Za-z_]\w*)', re.M)
    while todo:
        cur = todo.pop()
        if cur in seen:
            continue
        seen.add(cur)
        fp = os.path.join(root, cur)
        if not os.path.isfile(fp):
            continue
        src = io.open(fp, encoding='utf-8', errors='replace').read()
        for m in pat.finditer(src):
            nxt = m.group(1) + '.py'
            if nxt in names and nxt not in seen:
                todo.append(nxt)
    return seen


def scan(root=None):
    """(위반, 암호난수누락) 을 돌려준다."""
    root = root or HERE
    bad, missing = [], []
    reach = build_modules(root)
    for f in sorted(os.listdir(root)):
        if not f.endswith('.py') or f == OWNER:
            continue
        if f not in reach:
            continue          # 빌드가 안 부르는 파일. 산출물에 영향이 없다
        src = io.open(os.path.join(root, f), encoding='utf-8',
                      errors='replace').read()
        code = _strip_comments(src)
        for m in TIME_CALLS.finditer(code):
            line = code[:m.start()].count('\n') + 1
            bad.append('%s: %s (코드 줄에 시간 호출)' % (f, m.group(0)))
        for need in CRYPTO_RANDOM.get(f, ()):
            if need not in code:
                missing.append('%s: %s 가 사라졌습니다. 암호 난수는 있어야 합니다' % (f, need))
    return bad, missing


def _kat():
    """★ 답을 아는 입력."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        w = lambda n, t: io.open(os.path.join(d, n), 'w', encoding='utf-8').write(t)
        # ★ 2026-09-09. 검사 대상은 «빌드가 import 로 닿는» 모듈뿐이다.
        #   그래서 시험용 폴더에도 build.py 가 있어야 한다. 없으면 아무것도
        #   검사되지 않고 «위반 0» 이 나온다 (실제로 이 시험이 그렇게 실패해서
        #   범위를 좁힌 변경을 잡아 줬다).
        w('build.py', 'import clean\nimport commented\nimport dirty\n'
                      'import enc_reuse\n')
        w('buildtime.py', 'import datetime\ndef now(): return datetime.datetime.now()\n')
        w('clean.py', 'import buildtime\nx = buildtime.today()\n')
        w('commented.py', '# 전에는 Get-Date 를 썼다\ns = "date.today() 라고 적힌 글자"\n')
        w('dirty.py', 'import datetime\nx = datetime.date.today()\n')
        w('enc_reuse.py', 'import os\nnonce =os.urandom(12)\n')
        bad, miss = scan(d)
        names = [b.split(':')[0] for b in bad]
        if 'buildtime.py' in names:
            return False, '소유자 파일을 위반으로 잡음'
        if 'clean.py' in names:
            return False, 'buildtime 을 쓰는 파일을 위반으로 잡음'
        if 'commented.py' in names:
            return False, '주석·문자열을 위반으로 잡음'
        if 'dirty.py' not in names:
            return False, '진짜 시간 호출을 못 잡음'
        if miss:
            return False, 'os.urandom 이 있는데 누락으로 봄'
        # os.urandom 을 지우면 알려야 한다
        w('enc_reuse.py', 'import os\nnonce =b"fixed"\n')
        _bad, miss2 = scan(d)
        if not miss2:
            return False, 'os.urandom 이 사라졌는데 안 알림'
        # 빌드가 안 부르는 파일은 시간 호출이 있어도 대상이 아니다.
        # (배포 뒤에 도는 확인 도구가 그렇다. 산출물을 한 글자도 안 쓴다.)
        w('offbuild.py', 'import time\nx = time.time()\n')
        bad3, _m3 = scan(d)
        if any(b.startswith('offbuild.py') for b in bad3):
            return False, '빌드가 안 부르는 파일을 검사 대상으로 봄'
        # 그런데 빌드가 그것을 부르기 시작하면 그 순간부터 대상이다.
        w('build.py', 'import clean\nimport commented\nimport dirty\n'
                      'import enc_reuse\nimport offbuild\n')
        bad4, _m4 = scan(d)
        if not any(b.startswith('offbuild.py') for b in bad4):
            return False, '빌드가 부르기 시작했는데도 검사 대상이 아님'
    return True, ''


def main():
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    bad, missing = scan()
    if bad or missing:
        print('  🔴 시간 입력이 buildtime 밖에서 %d건' % len(bad))
        for b in bad[:10]:
            print('     ' + b)
        for m in missing:
            print('     ' + m)
        print('     시간은 buildtime.now/today/mtime 으로만 읽습니다')
        return False
    print('  자기시험 통과 · 시간 호출이 buildtime 한 곳에만 있습니다 · '
          '암호 난수 보존 확인')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
