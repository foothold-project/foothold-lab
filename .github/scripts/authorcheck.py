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

★ 이 관문이 «못 잡는 것» (DESIGN.md §13-3 · 2026-09-19)

  - **도구·역할 이름이 실재하는지는 안 본다.** 「Codex」·「Claude」를 다른
    말과 함께 적어도(예: 「오흥재 지시 Codex」) 통과시킨다. 그 토큰이 문자열
    «안에» 있으면 된다. 그 도구가 정말 그 작업을 했는지는 사람이 판단한다.
  - **「OOO 워커」 꼴의 직함도 통과시킨다.** 팀장 · 멘토와 같은 대우다.
    실재하지 않는 «역할» 을 지어내는 것까지는 못 막는다.
  - **문장 하나가 통째로 적힌 경우는 걸러 내지 «못한다».** 「작성:」 뒤에
    쉼표 없는 긴 설명이 오면 그 전체가 «이름» 으로 잡혀 위반으로 뜬다.
    그런 것은 이름 문제가 아니라 그 문서 머리말이 규격을 안 지킨 것이라
    관문이 대신 못 고친다. 명부(`authorcheck_grandfather.txt`)로 열어
    두고, 근본 고침은 그 문서를 쓴 사람이 한다.

  실측 (2026-09-19). 정확히 등록된 문자열일 때만 통과시켰더니, 같은
  도구를 문맥과 함께 적은 변형 열둘이 «없는 사람 이름» 으로 잡혔다.
  지어낸 사람 이름이 아니라 도구 이름인데, 이 관문이 스스로 「직함·자동
  생성 표기는 통과」라 적어 두고도 exact match 라 그 약속을 못 지켰다.
  그 대가로 팀원 PR 다섯 건이 막혀 있었다 (#384 #429 #433 #446 #448).
"""
import io
import os
import re
import sys

ROLES = os.path.join('docs', 'ROLES.md')
LEDGER = 'authorcheck_grandfather.txt'  # .github/scripts/ 안

# 사람 이름이 아니어서 통과시키는 것. 늘어나면 규칙이 기준을 잘못 담은 것이다.
ALLOW = {
    '팀장', '멘토', '자동 수집', 'Claude site', 'Claude',
}

# 도구 이름. 문맥과 «함께» 적혀도(예: 「오흥재 지시 Codex」) 이 토큰이
# 문자열 안에 있으면 통과시킨다. 부분일치라 넓어 보이지만, 지어낸 사람
# 이름은 ROLES.md 다섯 명 중 하나거나 이 토큰을 안 쓴다.
TOOL_TOKENS = ('Codex', 'Claude')

# 「OOO 워커」 꼴 직함. 팀장·멘토와 같은 대우다.
ROLE_SUFFIX = ('워커',)

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


def is_allowed(who):
    """사람 이름이 아니라서 통과시킬 값인가. 실재하는 팀원 이름은 여기서 안 본다."""
    if who in ALLOW:
        return True
    if any(t in who for t in TOOL_TOKENS):
        return True
    if any(who.endswith(s) for s in ROLE_SUFFIX):
        return True
    return False


def _selftest():
    """알려진 답으로 먼저 시험한다 (커널 원칙 1). 실제로 잡았던 사고를 다시 넣는다.

    2026-09-09 「방재혁」(지어낸 사람 이름)은 여전히 «막혀야» 한다.
    2026-09-19 도구 변형과 워커 직함은 «통과해야» 한다.
    """
    cases = [
        ('방재혁', False), ('임석헌', False),  # 사람 이름은 roster() 로 따로 가른다
        ('Codex', True), ('오흥재 지시 Codex', True),
        ('오흥재 작업을 위한 Codex', True),
        ('Claude', True), ('Claude 세션 (오흥재 지시)', True), ('Claude main', True),
        ('키비주얼 설계 워커', True), ('제작 설계 워커', True),
        ('팀장', True), ('멘토', True),
    ]
    bad = [w for w, want in cases if is_allowed(w) != want]
    if bad:
        print('  [!] 자기시험 실패: %s' % ', '.join(bad))
        return False
    print('  자가검증 %d/%d 통과' % (len(cases), len(cases)))
    return True


def _ledger_path(root):
    return os.path.join(root, '.github', 'scripts', LEDGER)


def read_ledger(root):
    p = _ledger_path(root)
    if not os.path.isfile(p):
        return set()
    return {ln.strip() for ln in io.open(p, encoding='utf-8')
            if ln.strip() and not ln.startswith('#')}


def write_ledger(root, rels):
    head = [
        '# 작성자 표기가 ROLES.md 에 없는데 «문장 하나» 라 이 관문이 이름으로',
        '# 못 가르는 파일 (DESIGN.md §13-3 의 «못 잡는 것» 참고).',
        '#',
        '# 명부는 면제가 아니다. 이 줄 수가 남은 일의 크기다.',
        '# 새로 생기면 CI 가 선다. docs/ROLES.md 를 고치지 않는다.',
        '',
    ]
    io.open(_ledger_path(root), 'w', encoding='utf-8').write(
        '\n'.join(head + sorted(rels)) + '\n')


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
            if is_allowed(who) or who in names:
                continue
            bad.append((rel, '«%s» 는 docs/ROLES.md 에 없는 이름이다' % who))
    return (not bad), bad, seen


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    if not _selftest():
        print('  [!] 이 관문 자체가 틀렸습니다. 결과를 믿지 마십시오.')
        return 1
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

    found = {rel for rel, _why in bad}
    reason = dict(bad)
    old = read_ledger(root)
    new = found - old
    gone = old - found
    if gone:
        print('  고쳐진 것 %d건: %s' % (len(gone), ' · '.join(sorted(gone))))
        write_ledger(root, found)

    if ok:
        print('  없는 이름 없음 (명부 %d건)' % len(found))
        return 0

    if not new:
        # ★ 전부 명부에 이미 있는 것이면 «빚은 그대로지만 새로 생기지 않았다».
        #   §13-1: 기존 위반은 명부에 적고 시작해 늘어날 때만 막는다.
        print('  없는 이름 %d건 · 전부 명부에 이미 있습니다 (새 위반 없음)' % len(found))
        for rel in sorted(found):
            print('      %s' % rel)
            print('        %s' % reason[rel])
        return 0

    print('  [!] 없는 이름이 «새로» 생겼습니다 (%d건 · 명부 %d건 중)' % (len(new), len(found)))
    for rel in sorted(new):
        print('      %s' % rel)
        print('        %s' % reason[rel])
    if found - new:
        print('  (이미 명부에 있던 것 %d건은 생략)' % len(found - new))
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
