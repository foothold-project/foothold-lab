# -*- coding: utf-8 -*-
"""문서 머리말의 «작성» 칸에 없는 사람 이름이 들어가는 것을 막는다.

왜 만들었나 (2026-09-09):

  하위 세션이 시스템 프롬프트의 사용자 이메일 `bangjae87@gmail.com` 에서
  `bangjae` 를 「방재」로 읽고 「혁」을 붙여 «없는 이름» 을 만들어 문서 셋의
  «> 작성:» 줄에 넣었다. 팀장이 직접 지적해서 알았다.

  같은 자리에서 코디네이터도 틀렸다. 확인 안 된 이름을 다른 문서에 적었다.
  둘 다 같은 이메일에서 같은 방식으로 유도했을 것이다.

  ★ 이것이 «구조» 인 이유. 세션은 사람 이름을 알 수 없는데 문서 형식이 그
    칸을 요구한다. 그러면 채운다. 규칙 문서만 두면 다음 세션이 그 문서를
    안 읽고 또 채운다. 그래서 관문으로 막는다.

  그리고 이 칸이 특히 나쁜 자리다. 머리말은 «누가 무엇을 근거로 썼는지
  나중에 대조하려고» 있다. 그 칸이 거짓이면 아래 모든 숫자의 신뢰가
  함께 무너진다.

무엇을 보는가:

  docs/ROLES.md 의 «### 이름» 목록을 정본으로 삼는다. 그 목록에 없는
  이름이 «> 작성:» 에 있으면 막는다.

  직함(팀장 · 멘토)과 자동 생성 표기는 통과시킨다. 사람 이름을 지어내는
  것을 막는 것이지 모든 표기를 강제하는 것이 아니다.
"""
import io
import os
import re
import sys

ROLES = os.path.join('docs', 'ROLES.md')

# 사람 이름이 아니어서 통과시키는 것. 늘어나면 규칙이 기준을 잘못 담은 것이다.
ALLOW = {
    '팀장', '멘토', '자동 수집', 'Claude site', 'Claude',
}

# 템플릿과 예시 파일. 여기 「홍길동」은 채우라는 뜻이다.
TEMPLATE = {
    'docs/WORKFLOW.md',
    'inbox/README.md',
}

# ★ re.M 이 없으면 «^» 가 파일 첫 줄만 본다. 머리말은 3~5행이라 한 건도
#   안 잡히고 관문은 «0개 검사 · 통과» 를 찍는다. 실제로 처음에 그렇게
#   만들었고 돌려 보고서야 알았다. 관문은 만든 뒤 반드시 돌려 봐야 한다.
AUTHOR = re.compile('^> 작성: *([^·\n]+)', re.M)
NAME = re.compile('^### ([가-힣]{2,4})$', re.M)


def roster(root='.'):
    """docs/ROLES.md 의 사람 이름. 이것이 정본이다."""
    p = os.path.join(root, ROLES)
    if not os.path.isfile(p):
        return None
    return set(NAME.findall(io.open(p, encoding='utf-8').read()))


def check(root='.'):
    names = roster(root)
    if names is None:
        return False, ['%s 를 못 읽었다. 이름 목록의 정본이 없으면 검사할 수 없다.' % ROLES], 0
    bad = []
    seen = 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__')]
        for f in sorted(files):
            if not f.endswith('.md'):
                continue
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            if rel in TEMPLATE:
                continue
            try:
                head = io.open(p, encoding='utf-8', errors='replace').read(1400)
            except Exception:
                continue
            m = AUTHOR.search(head)
            if not m:
                continue
            seen += 1
            who = m.group(1).strip()
            if not who:
                bad.append((rel, '«작성» 이 비었다'))
                continue
            if who in ALLOW or who in names:
                continue
            bad.append((rel, '«%s» 는 docs/ROLES.md 에 없는 이름이다' % who))
    return (not bad), bad, seen


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    ok, bad, seen = check(root)
    print('  작성자 표기 %d개 검사' % seen)
    if ok:
        print('  없는 이름 없음')
        return 0
    print('  [!] 없는 이름 %d건' % len(bad))
    for rel, why in bad:
        print('      %s' % rel)
        print('        %s' % why)
    print('')
    print('  사람 이름은 docs/ROLES.md 에 있는 것만 쓴다.')
    print('  없으면 직함으로 적는다 (팀장 · 멘토).')
    print('  ★ 지어내지 않는다. 틀리면 그 사람을 잘못 부르는 것이고,')
    print('    문서에 남으면 다음 사람이 그것을 옳은 것으로 읽는다.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
