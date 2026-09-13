# -*- coding: utf-8 -*-
"""문서 «작성자» 가 실재하는 사람인가. 지어낸 이름이 웹으로 나가는 것을 막는다.

★ 2026-09-09. 하위 세션이 없는 사람 이름으로 문서 넷을 올렸다. 출처는 그 세션의
  시스템 프롬프트에 있던 이메일 주소였고, 로컬파트를 사람 이름처럼 읽었다.
  세션은 이름을 알 수 없다. 「작성자를 적으라」고 하면 지어낸다.
  lab 은 PR 관문으로 막았다. 그런데 **site 는 lab 문서를 읽어 웹에 올린다.**
  승격 경로로 들어온 문서는 그 PR 관문을 통과한 적이 없을 수 있다 (철칙 4).

무엇을 정본으로 보나
  lab `docs/ROLES.md` 의 `### 이름`. 사람 명부는 거기 하나다.

무엇을 보나 · 그리고 «무엇을 안 보나»
  문서 «머리말» 의 `> 작성:` 한 줄만 본다.
  본문에 나오는 같은 모양은 안 본다. 실측: WORKFLOW.md 는 머리말 표준을 설명하며
  코드블록 안에 `> 작성: 홍길동` 예시를 담고 있다. 그것을 잡으면 규격 문서를
  고치라고 하는 셈이고, 관문이 한 번 헛울면 다음부터 무시된다.

★ 만들 때 조심한 것 (동료 세션이 겪은 그대로)
  `^` 를 `re.M` 없이 쓰면 파일 «첫 줄» 만 본다. 머리말은 3~5행에 있어서 한 건도
  안 잡히고 「0개 검사 · 통과」가 찍힌다. 그래서 이 관문은 **검사한 개수를 항상
  출력한다.** 0이 나오면 그 자체가 신호다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 사람이 아닌 작성자. 기계가 만든 문서는 사람 이름이 없는 것이 옳다.
NOT_PERSON = {'자동 수집', '자동수집', '봇', 'github-actions'}

WROTE = re.compile(r'^>\s*작성:\s*([^·\n]+?)\s*(?:·|$)', re.M)
FENCE = re.compile(r'^```', re.M)
NAME_HEAD = re.compile(r'^###\s+([가-힣]{2,4})\s*$', re.M)


def roster(roles_text):
    """`### 이름` 중 «사람 이름 모양» 만. 「옛 5갈래는 왜 버렸나」 같은 절은 뺀다."""
    return {m.group(1) for m in NAME_HEAD.finditer(roles_text)}


def front_matter(text):
    """머리말만 떼어 낸다. 코드블록과 본문은 안 본다.

    머리말은 첫 `## ` 앞에 있고, 코드블록 안에 있으면 예시다.
    """
    end = text.find('\n## ')
    head = text[:end if end > 0 else len(text)]
    # 코드블록을 통째로 지운다 (짝이 안 맞으면 그 뒤를 전부 버린다)
    parts = FENCE.split(head)
    return ''.join(parts[0::2])


def author_of(text):
    """머리말의 작성자 이름. 없으면 None."""
    m = WROTE.search(front_matter(text))
    return m.group(1).strip() if m else None


def _kat():
    """★ 알려진 답. 동료 세션이 밟은 지뢰(re.M 누락)를 여기서 밟아 본다."""
    n = chr(10)
    doc = ('# 제목' + n + '' + n +
           '> 분류: 리서치' + n +
           '> 작성: 맹라현 · 2026-09-09 10:00' + n +
           '> 근거: 실측' + n + n +
           '## 1. 본문' + n +
           '```' + n +
           '> 작성: 홍길동 · 2026-08-27' + n +
           '```' + n)
    if author_of(doc) != '맹라현':
        return False, '머리말 작성자를 못 읽음 (re.M 없이 ^ 를 쓰면 이렇게 된다): %r' % author_of(doc)

    # 코드블록 «안» 의 예시는 잡으면 안 된다. 머리말에도 예시가 들어간 문서가 있다.
    ex = ('# 규격' + n + n +
          '> 분류: 가이드' + n +
          '> 작성: 오흥재 · 2026-08-27' + n + n +
          '```' + n +
          '> 작성: 홍길동 · 2026-08-27' + n +
          '```' + n)
    if author_of(ex) != '오흥재':
        return False, '코드블록 예시를 작성자로 읽음: %r' % author_of(ex)

    if author_of('# 제목' + n + '본문뿐') is not None:
        return False, '없는 작성자를 있다고 함'

    r = roster('### 오흥재' + n + '### 옛 5갈래는 왜 버렸나' + n + '### 맹라현' + n)
    if r != {'오흥재', '맹라현'}:
        return False, '명부를 잘못 읽음: %s' % sorted(r)
    return True, ''


def _lab():
    import docs_pages
    for p in docs_pages.LAB_CANDIDATES:
        if os.path.isdir(os.path.join(p, 'docs')):
            return p
    return None


def main(vault=None, pages=None):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    lab = _lab()
    if not lab:
        print('  [!] foothold-lab 을 못 찾음. 작성자 검사 건너뜀')
        return True
    rp = os.path.join(lab, 'docs', 'ROLES.md')
    if not os.path.isfile(rp):
        print('  [!] docs/ROLES.md 가 없습니다. 사람 명부가 없으면 검사할 수 없습니다')
        return False
    people = roster(io.open(rp, encoding='utf-8', errors='replace').read())
    if not people:
        print('  [!] ROLES.md 에서 사람 이름을 하나도 못 읽었습니다')
        return False

    seen, bad, blank = 0, [], []
    base = os.path.join(lab, 'docs')
    for r, dirs, fs in os.walk(base):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
        for f in sorted(fs):
            if not f.endswith('.md'):
                continue
            rel = os.path.relpath(os.path.join(r, f), lab).replace(os.sep, '/')
            t = io.open(os.path.join(r, f), encoding='utf-8',
                        errors='replace').read()
            who = author_of(t)
            if who is None:
                continue
            seen += 1
            if not who:
                blank.append(rel)
            elif who not in people and who not in NOT_PERSON:
                bad.append('%s -> %s' % (rel, who))

    # ★ 검사 «개수» 를 항상 찍는다. 0이면 정규식이 아무것도 못 본 것이다.
    print('  사람 명부 %d명 (%s) · 작성자 줄 %d개 검사'
          % (len(people), ' · '.join(sorted(people)), seen))
    if seen == 0:
        print('  [!] 작성자 줄을 하나도 못 찾았습니다. 검사가 헛돌고 있습니다')
        return False
    if blank:
        print('  [!] 작성자가 비었습니다: %s' % ' · '.join(blank[:6]))
        return False
    if bad:
        print('  [!] 명부에 없는 이름으로 올라온 문서:')
        for b in bad[:8]:
            print('      %s' % b)
        print('      이 팀은 다섯 명입니다. 명부에 없는 이름이 나왔다면'
              ' 대개 «지어낸 것» 입니다.')
        print('      세션은 사람 이름을 알 수 없습니다. 경로 별칭·이메일 로컬파트를'
              ' 이름으로 읽은 사고가 실제로 있었습니다.')
        print('      모르면 이름 대신 직함으로 적으십시오. 명부를 늘려서 통과시키지'
              ' 마십시오.')
        print('      새 팀원이 실제로 들어온 경우에만 docs/ROLES.md 를 먼저 고칩니다.')
        return False
    print('  명부에 없는 이름 없음')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
