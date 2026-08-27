# -*- coding: utf-8 -*-
"""주간 다이제스트 재료 모으기.

다이제스트는 「무엇을 알게 됐나」를 쓰는 문서다. 그건 판단이라 기계가 대신 못 쓴다.
그래서 이 스크립트는 **초안을 쓰지 않고 재료만 모은다.**

  모으는 것: 이번 주 머지된 PR · 닫힌 이슈 · 새로 생기거나 크게 바뀐 docs 문서
  내는 것:   docs/digest/YYYY-Www-material.md  (사람이 이걸 보고 다이제스트를 쓴다)

    python tools/digest_material.py                # 이번 주 (KST)
    python tools/digest_material.py --week 2026-W34

왜 초안을 자동으로 안 쓰는가: 「보상이 높다고 걷는 것이 아니다」 같은 문장은
커밋 목록에서 나오지 않는다. 기계가 흉내 내면 그럴듯하고 틀린 글이 남는다.
"""
import argparse
import datetime
import io
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

REPO = 'foothold-project/foothold-lab'
OUT_DIR = os.path.join('docs', 'digest')


def kst_today():
    return (datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(hours=9)).date()


def week_range(spec):
    """'2026-W34' 또는 None. 월요일부터 일요일까지를 돌려준다."""
    if spec:
        y, w = spec.split('-W')
        mon = datetime.date.fromisocalendar(int(y), int(w), 1)
    else:
        t = kst_today()
        mon = t - datetime.timedelta(days=t.weekday())
    return mon, mon + datetime.timedelta(days=6)


def gh_json(args):
    r = subprocess.run(['gh'] + args, capture_output=True, text=True,
                       encoding='utf-8')
    if r.returncode != 0:
        raise SystemExit('gh 실패: %s' % r.stderr[:200])
    return json.loads(r.stdout)


def git_lines(args):
    r = subprocess.run(['git'] + args, capture_output=True, text=True,
                       encoding='utf-8')
    return [l for l in (r.stdout or '').split('\n') if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week')
    a = ap.parse_args()
    mon, sun = week_range(a.week)
    tag = '%d-W%02d' % mon.isocalendar()[:2]
    since, until = mon.isoformat(), (sun + datetime.timedelta(days=1)).isoformat()

    prs = [p for p in gh_json(['pr', 'list', '-R', REPO, '--state', 'merged',
                               '--limit', '80', '--json',
                               'number,title,mergedAt,author'])
           if p.get('mergedAt') and since <= p['mergedAt'][:10] <= sun.isoformat()]
    issues = [i for i in gh_json(['issue', 'list', '-R', REPO, '--state', 'closed',
                                  '--limit', '120', '--json',
                                  'number,title,closedAt,labels'])
              if i.get('closedAt') and since <= i['closedAt'][:10] <= sun.isoformat()]

    added = git_lines(['log', '--since', since, '--until', until,
                       '--diff-filter=A', '--name-only', '--pretty=format:',
                       '--', 'docs/'])
    changed = git_lines(['log', '--since', since, '--until', until,
                         '--diff-filter=M', '--name-only', '--pretty=format:',
                         '--', 'docs/'])
    added = sorted(set(added))
    changed = sorted(set(changed) - set(added))
    commits = git_lines(['log', '--since', since, '--until', until,
                         '--pretty=format:%h %an %s'])

    if not (prs or issues or added or changed or commits):
        raise SystemExit('%s 에 아무 활동도 없습니다. 재료를 만들지 않습니다.' % tag)

    L = []
    L.append('# 다이제스트 재료: %s' % tag)
    L.append('')
    L.append('> 분류: 운영')
    L.append('> 작성: 자동 수집 · %s' % kst_today().isoformat())
    L.append('> 근거: 깃 이력')
    L.append('> 요지: %s ~ %s 의 활동 목록. 다이제스트를 쓰기 위한 재료다.'
             % (mon.isoformat(), sun.isoformat()))
    L.append('> 상태: 초안')
    L.append('')
    L.append('**이 파일은 다이제스트가 아니다.** 「무엇을 알게 됐나」는 사람이 쓴다.')
    L.append('아래에서 골라 `%s.md` 를 쓴 뒤 이 파일은 지운다.' % tag)
    L.append('')

    L.append('## 머지된 PR (%d건)' % len(prs))
    L.append('')
    if prs:
        for p in prs:
            L.append('- `#%d` %s  (%s)' % (p['number'], p['title'],
                                           p['author']['login']))
    else:
        L.append('없음')
    L.append('')

    L.append('## 닫힌 이슈 (%d건)' % len(issues))
    L.append('')
    if issues:
        for i in issues:
            area = next((x['name'] for x in i['labels']
                         if x['name'][:2] in ('A/', 'B/', 'C/')), '')
            L.append('- `#%d` %s%s' % (i['number'], i['title'],
                                       (' · %s' % area) if area else ''))
    else:
        L.append('없음')
    L.append('')

    L.append('## 새 문서 (%d개)' % len(added))
    L.append('')
    L.extend(['- `%s`' % f for f in added] or ['없음'])
    L.append('')

    L.append('## 고쳐진 문서 (%d개)' % len(changed))
    L.append('')
    L.extend(['- `%s`' % f for f in changed] or ['없음'])
    L.append('')

    L.append('## 커밋 (%d건)' % len(commits))
    L.append('')
    L.append('```')
    L.extend(commits[:60])
    if len(commits) > 60:
        L.append('... 외 %d건' % (len(commits) - 60))
    L.append('```')
    L.append('')

    L.append('## 다이제스트를 쓸 때')
    L.append('')
    L.append('| 규칙 | |')
    L.append('|---|---|')
    L.append('| 담는 것 | **무엇을 알게 됐나.** 무엇을 했나가 아니다 |')
    L.append('| 한 항목 | 한 문장 + 증거 링크 하나 |')
    L.append('| 분량 | 5분이면 이번 주 발견을 다 알 수 있게 |')
    L.append('| 안 담는 것 | 숫자 없는 진행 보고. 「열심히 했다」 |')

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, '%s-material.md' % tag)
    io.open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')

    back = io.open(path, encoding='utf-8').read()
    assert '# 다이제스트 재료' in back and len(back) > 300
    print('만들었습니다: %s' % path)
    print('  PR %d · 이슈 %d · 새 문서 %d · 고친 문서 %d · 커밋 %d'
          % (len(prs), len(issues), len(added), len(changed), len(commits)))


if __name__ == '__main__':
    main()
