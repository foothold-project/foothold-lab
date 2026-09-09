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
        # ★ 아래 출력 루프가 (파일, 이유) 튜플을 푼다. 여기서 문자열을 돌려주면
        #   ValueError 로 죽어 정작 «명부가 없다» 는 진단문이 화면에서 사라진다.
        return False, [(ROLES, '이 파일이 없다. 이름 목록의 정본이 없으면 검사할 수 없다.')], 0
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
    # ★ 명부가 없는 것은 «위반» 이 아니라 «검사 불능» 이다. 같은 화면으로
    #   내면 사람이 원인을 이름 쪽에서 찾는다. 여기서 먼저 가른다.
    if roster(root) is None:
        print('  [!] %s 가 없다.' % ROLES)
        print('      이름 목록의 정본이 없으면 이 검사는 성립하지 않는다.')
        print('      위반이 없는 것이 아니라 «검사하지 못한 것» 이다.')
        return 1
    ok, bad, seen = check(root)
    print('  작성자 표기 %d개 검사' % seen)
    # ★ 0개를 검사하고 «통과» 를 찍는 것이 이 관문의 가장 나쁜 실패다.
    #   실제로 첫 판이 re.M 을 빠뜨려 그렇게 돌았다. 관문이 대상에
    #   닿지 못한 것과 위반이 없는 것은 다른 사실이므로 소리 나게 한다.
    # ★ bad 가 이미 있으면 그것이 더 구체적인 이유다 (명부 없음 등).
    #   여기서 가로채면 진짜 원인이 «닿지 못했다» 로 덮인다.
    if seen == 0 and not bad:
        print('  [!] 한 건도 검사하지 못했다. 관문이 대상에 닿지 못한 것이다.')
        print('      «위반 없음» 이 아니라 «검사 실패» 다. 경로와 정규식을 의심한다.')
        return 1
    if ok:
        print('  없는 이름 없음')
        return 0
    print('  [!] 없는 이름 %d건' % len(bad))
    for rel, why in bad:
        print('      %s' % rel)
        print('        %s' % why)
    print('')
    # ★ 안내 문구의 순서가 중요하다. 「실재하는 사람인데 명부에 없으면
    #   ROLES.md 에 넣어라」를 앞세우면 관문이 스스로 푸는 법을 가르치는
    #   셈이 되고, 다음 세션이 자기가 지어낸 이름을 명부에 넣어 통과시킨다.
    print('  이 팀은 다섯 명이다. 명부에 없는 이름이 나왔다면 대개 «지어낸 것» 이다.')
    print('  세션은 사람 이름을 알 수 없다. 경로 별칭과 이메일 로컬파트를')
    print('  사람 이름으로 읽어 문서에 넣은 사고가 실제로 있었다 (2026-09-09).')
    print('')
    print('  모르면 이름 대신 직함으로 적는다 (팀장 · 멘토).')
    print('  ★ 명부를 늘려서 통과시키지 않는다.')
    print('    docs/ROLES.md 를 고치는 것은 새 팀원이 실제로 들어온 경우뿐이다.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
