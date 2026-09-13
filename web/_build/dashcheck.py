# -*- coding: utf-8 -*-
"""em dash( ) 금지 검사: 배포 직전의 문체 관문.

  왜 코드인가
    팀장이 여러 번 지적했는데도 계속 들어갔다. «쓰지 말자»를 문서에만 적으면 안 지켜진다.
    이 문자는 «AI 가 쓴 글»의 표식처럼 읽힌다. 우리 문서는 사람이 읽는 기록이다.

  무엇을 대신 쓰나
    · 왼쪽이 문장으로 끝나면      →  마침표로 끊는다      «…된다. 그래서…»
    · 왼쪽이 명사·제목이면        →  콜론으로 잇는다      «전체 흐름: 무엇을 언제»
    · 표의 빈 칸                  →  «-»
    · 나열                        →  «·»

  en dash(–) 와 하이픈(-) 은 막지 않는다. 문제는 «: » 하나다.
"""
import io
import os
import re

# ★ 리터럴로 쓰지 않는다. 일괄 치환 도구가 자기 자신을 먹었다(2026-08-12).
#   그때 BAD 가 ': ' 이 되어 검사기가 «콜론 654개»를 잡았다. 이스케이프로 고정한다.
BAD = '\u2014'     # em dash (U+2014). 리터럴 금지 - 치환 도구가 먹는다

# 손대지 않는 것 (외부 원본·자동 생성물 중 우리 문체가 아닌 것)
SKIP = ()


def scan(site_dir, exts=('.html', '.md')):
    hits = []
    for root, dirs, files in os.walk(site_dir):
        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'assets')]
        for f in sorted(files):
            if not f.endswith(exts) or f in SKIP:
                continue
            p = os.path.join(root, f)
            try:
                t = io.open(p, encoding='utf-8', errors='replace').read()
            except Exception:
                continue
            n = t.count(BAD)
            if n:
                rel = os.path.relpath(p, site_dir)
                m = re.search(r'.{0,42}' + BAD + r'.{0,42}', t)
                sample = re.sub(r'<[^>]+>', ' ', m.group(0)) if m else ''
                sample = re.sub(r'\s+', ' ', sample).strip()
                hits.append((rel, n, sample))
    return hits


# 이슈 전수를 본다. 처음에 40 으로 뒀다가 놓쳤다. 최신 40개만 보면
# 번호가 낮은 이슈(#28)가 범위 밖이 되어 «없음» 이 찍힌다. 조용한 실패다.
def strip_code(md):
    """마크다운에서 «코드» 를 지운다. 울타리 블록과 인라인 코드 둘 다.

    ★ 2026-09-08. 이 규칙은 «문체» 규칙이다. 그런데 관문이 코드까지 세어서
      코드에 정당히 들어간 문자를 잡았다. #316 코멘트의 파이썬 한 줄이 그랬다.
        st = fv(it, 'Status') or '<em dash>'
      우리 코드에 실제로 그 글자가 들어 있어 그것을 인용한 것인데, 그러면
      «코드 이야기를 이슈에 못 쓰는» 상태가 된다. 규칙의 뜻이 아니다.

      느슨하게 만드는 것이 아니다. 산문에서는 그대로 막는다. 코드 블록 밖에
      한 글자라도 있으면 걸린다. 줄 수는 보존해 위치가 어긋나지 않게 한다.
    """
    def blank(m):
        return re.sub(r'[^\n]', ' ', m.group(0))
    md = re.sub(r'```.*?```', blank, md, flags=re.S)     # 울타리 블록
    md = re.sub(r'~~~.*?~~~', blank, md, flags=re.S)
    md = re.sub(r'`[^`\n]*`', blank, md)                 # 인라인 코드
    return md


def scan_issues(lab, limit=200):
    """GitHub 이슈 제목·본문·코멘트를 본다. [(어디, 개수, 보기)] · None = 검사 불가

    ★ 2026-08-28. 규칙은 「웹만이 아니라 이슈·PR·커밋·채팅 전부」인데
      (`AGENTS.md` §4-4) 관문은 `foothold-site` 의 html 만 봤다.
      그래서 문서·커밋·사이트는 전부 0인데 **이슈 코멘트 한 곳에서 뚫렸다.**
      규칙이 사는 자리를 세지 않고 관문을 한 곳에만 달면 이렇게 된다 (철칙 4).
    """
    import json
    import subprocess

    def _gh(args, timeout=90):
        r = subprocess.run(['gh'] + args, cwd=lab, capture_output=True,
                           text=True, encoding='utf-8', timeout=timeout)
        return json.loads(r.stdout or 'null') if r.returncode == 0 else None

    hits = []
    try:
        items = _gh(['issue', 'list', '--state', 'all', '--limit', str(limit),
                     '--json', 'number,title,body'])
        if items is None:
            return None
        # ★ 코멘트는 목록 호출로 못 가져온다. `gh issue list --json comments` 는
        #   **빈 배열을 조용히 돌려준다.** 오류도 안 난다.
        #   처음에 그렇게 짰다가 「이슈 em dash 없음」이 찍혔는데, 나는 #28 코멘트에
        #   있다는 걸 알고 있었다. 알려진 답과 어긋나서 잡았다 (커널 원칙 1·2).
        #   코멘트는 이슈마다 따로 받는다.
        nums = [it['number'] for it in items]
        comments = {}
        for num in nums:
            d = _gh(['issue', 'view', str(num), '--json', 'comments'], timeout=40)
            comments[num] = (d or {}).get('comments') or []
    except Exception:
        return None

    for it in items:
        num = it['number']
        parts = [('제목', it.get('title') or ''), ('본문', it.get('body') or '')]
        for k, c in enumerate(comments.get(num, []), 1):
            parts.append(('코멘트%d' % k, c.get('body') or ''))
        for where, text in parts:
            prose = strip_code(text)
            n = prose.count(BAD)
            if n:
                i = prose.index(BAD)
                hits.append(('#%d %s' % (num, where), n,
                             prose[max(0, i - 30):i + 32].replace(chr(10), ' ')))
    return hits


def report(site_dir, strict=True, lab=None):
    bad_issue = False
    if lab:
        ih = scan_issues(lab)
        if ih is None:
            print('  이슈 검사는 건너뜀 (gh 사용 불가)')
        elif ih:
            print('  🔴 이슈에 em dash %d곳' % len(ih))
            for where, n, sample in ih[:8]:
                print('     %-18s %2d개   …%s…' % (where, n, sample))
            print('     규칙은 웹만이 아니라 이슈·PR·커밋·채팅 전부입니다 (AGENTS §4-4).')
            bad_issue = strict
        else:
            print('  이슈 em dash 없음')

    hits = scan(site_dir)
    total = sum(n for _, n, _ in hits)
    if not hits:
        print('  em dash 없음')
        return not bad_issue
    print('  🔴 em dash( ) %d개 · 파일 %d개' % (total, len(hits)))
    for rel, n, sample in hits:
        print('     %-34s %3d개   …%s…' % (rel, n, sample[:70]))
    print('\n     대신: 문장 끝이면 «.» · 제목·명사면 «:» · 빈 칸이면 «-» · 나열이면 «·»')
    print('     (DESIGN-GUIDE.md 문체 규칙)')
    return (not strict) and (not bad_issue)


if __name__ == '__main__':
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.abspath(os.path.join(here, '.', '.', '.', '.', '.',
                                           '인공지능사관학교', 'foothold-site'))
    target = sys.argv[1] if len(sys.argv) > 1 else default
    sys.exit(0 if report(target) else 1)
