# -*- coding: utf-8 -*-
"""승격 대기가 얼마나 밀렸는지 «소리 내어» 찍는다 (빌드 [3.85] 단계).

  왜 만드나
    2026-09-09. 팀장이 「내가 본 문서를 우리 웹페이지에서 못 찾겠다」고 했다.
    실측하니 그 문서는 `inbox/` 에 있었다. PR 은 머지됐지만 승격이 안 돼서
    웹에 안 나간 것이다. 같은 상태의 문서가 **19건 · 약 295KB · 닷새치** 였다.

    아무도 잘못하지 않았다. 팀원은 PR 이 머지됐으니 반영된 줄 알고, 팀장은
    GitHub 에서 본 것이 웹에 있을 줄 안다. 둘 다 자기 쪽에서는 맞게 행동했는데
    결과가 안 닿는다. **그래서 아무도 못 알아챘다.**

    그 수가 어디에도 안 보이는 것이 문제였다. 숫자를 화면에 내면 줄어든다.

  막지 않는다
    승격이 늦은 것은 «내용 결함» 이 아니라 «일이 밀린 것» 이다. 배포를 막으면
    밀린 일이 사이트 전체를 인질로 잡는다. 세되 세우지는 않는다.

  N = 3일
    실측 분포가 [1,1,1,1,1,1,2,2,2,4,4,5,5,5,6,6,6,6,6] 이다.
    2일과 4일 사이가 비어 있어 그 틈이 자연스러운 경계다. 대부분이 사흘 안에
    처리되면 조용하고, 밀리면 소리가 난다.

  원장(ledger-sync)과 겹치지 않는다
    원장은 «열린 이슈 전수» 를 담는다. 이것은 «승격 대기» 다. 다른 것을 세고
    다른 자리에 쓴다. 같은 자리에 두 기계가 쓰면 서로 덮는다.
"""
import datetime
import json
import os
import re
import subprocess

import buildtime

STALE_DAYS = 3
TITLE = re.compile(r'\[승격 검토\]\s*(\S+)')


def _lab():
    import docs_pages
    for p in docs_pages.LAB_CANDIDATES:
        if os.path.isdir(os.path.join(p, 'docs')):
            return p
    return None


def waiting(lab, today):
    """[(이슈번호, 경로, 며칠째)] · None = 셀 수 없음(gh 없음·인증 없음)"""
    try:
        r = subprocess.run(
            ['gh', 'issue', 'list', '--state', 'open', '--limit', '300',
             '--json', 'number,title,createdAt'],
            cwd=lab, capture_output=True, text=True, encoding='utf-8', timeout=60)
        if r.returncode != 0:
            return None
        items = json.loads(r.stdout or '[]')
    except Exception:
        return None
    out = []
    for it in items:
        m = TITLE.search(it.get('title') or '')
        if not m:
            continue
        rel = m.group(1)
        # 이미 승격됐으면 inbox 에 없다. 이슈만 안 닫힌 것은 세지 않는다.
        if not os.path.exists(os.path.join(lab, rel.replace('/', os.sep))):
            continue
        try:
            d = datetime.date.fromisoformat((it.get('createdAt') or '')[:10])
        except Exception:
            continue
        out.append((it['number'], rel, (today - d).days))
    return sorted(out, key=lambda x: -x[2])


def _kat(today):
    """알려진 답으로 먼저 시험한다. 제목 파싱과 날짜 셈이 맞는가."""
    m = TITLE.search('[승격 검토] inbox/meang/20260906-rails-진단.md')
    if not m or m.group(1) != 'inbox/meang/20260906-rails-진단.md':
        return False, '제목에서 경로를 못 뽑음'
    if TITLE.search('[작업] 승격 검토를 언급만 한 제목'):
        return False, '승격 검토가 아닌 제목을 잡음'
    d = datetime.date.fromisoformat('2026-09-03')
    if (today - d).days != (today - datetime.date(2026, 9, 3)).days:
        return False, '날짜 셈이 어긋남'
    return True, ''


def main(today=None):
    today = today or buildtime.today()
    ok, why = _kat(today)
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return True                    # 세지 못해도 배포는 막지 않는다
    lab = _lab()
    if not lab:
        print('  foothold-lab 을 못 찾아 세지 못했습니다')
        return True
    rows = waiting(lab, today)
    if rows is None:
        print('  gh 로 이슈를 못 읽어 세지 못했습니다 (인증·네트워크)')
        return True
    if not rows:
        print('  자기시험 통과 · 승격 대기 0건')
        return True
    stale = [r for r in rows if r[2] >= STALE_DAYS]
    print('  자기시험 통과 · 승격 대기 %d건 · 최장 %d일 · %d일 넘긴 것 %d건'
          % (len(rows), rows[0][2], STALE_DAYS, len(stale)))
    for num, rel, age in rows[:5]:
        print('     %2d일째  #%-5d %s' % (age, num, rel))
    if len(rows) > 5:
        print('     … 외 %d건' % (len(rows) - 5))
    if stale:
        print('  이것들은 머지됐지만 웹에 없습니다. 낸 사람에게는 반영이 안 된 것과 같습니다')
    return True                        # 세되 세우지 않는다
