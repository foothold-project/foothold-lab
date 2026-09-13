# -*- coding: utf-8 -*-
"""WBS 를 웹에 도달시킨다 (#77 · W36 팀 목표 2번).

  xlsx 는 주간 리포트 워크플로가 git·이슈에서 자동 생성한다 (기기 무관).
  그런데 웹에는 「WBS 를 3층으로 짠다」는 설계 문서만 있고 **표 자체가 없었다.**
  여기서 xlsx 를 읽어 deliverable-wbs.html 의 마커 구역에 표로 넣는다.

  ★ deliverable-wbs.html 은 매 빌드 [1.896]에서 md 로 다시 생성되므로
    이 주입은 반드시 그 뒤에 돌아야 한다 (build.py 호출 순서가 보장).
"""
import datetime
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MARK_A, MARK_B = '<!--wbs:auto-->', '<!--/wbs:auto-->'
COLS = ['WBS', '작업 이름', '관문', '기간', '시작날짜', '예상 완료 날짜',
        '실제 완료 날짜', '계획율', '완료율', '담당자', '산출물', '저장소']
# 화면에 싣는 열만 고른다. 12열 전부는 좁은 화면에서 못 읽는다.
SHOW = ['WBS', '작업 이름', '관문', '예상 완료 날짜', '계획율', '완료율', '담당자']


def esc(s):
    # ★ 원자료(옛 이슈 제목이 든 xlsx)에 em dash 가 남아 있을 수 있다.
    #   경계에서 정화한다. 철칙 4: 관문은 한 층위만 보면 안 된다.
    return (str(s).replace('—', '·').replace('&', '&amp;')
            .replace('<', '&lt;').replace('>', '&gt;'))


def read(lab):
    import openpyxl
    p = os.path.join(lab, 'deliverables', 'plan', 'wbs.xlsx')
    if not os.path.isfile(p):
        return None, None, 'wbs.xlsx 가 없다'
    ws = openpyxl.load_workbook(p, data_only=True).active
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    head_i = next((i for i, r in enumerate(rows) if r and r[0] == 'WBS'), None)
    if head_i is None:
        return None, None, '머리행(WBS)을 못 찾았다'
    head = [str(c or '') for c in rows[head_i]]
    if head[:3] != COLS[:3]:
        return None, None, '열 구성이 달라졌다: %s' % head[:3]
    meta = {}
    for r in rows[:head_i]:
        for i in range(0, len(r) - 1, 2):
            if r[i]:
                meta[str(r[i])] = str(r[i + 1] or '')
    body = [r for r in rows[head_i + 1:] if r and r[0]]
    return meta, [dict(zip(head, [c if c is not None else '' for c in r]))
                  for r in body], ''


# ---- 그림 ----------------------------------------------------------------
#  팀장 8/31: 「단순 텍스트로 보여지고자 하는 것은 아니다. 외부 인원도 내부 인원도
#   이 프로젝트가 지금 이렇게 진행되고 있구나, 그리고 이게 진짜 실데이터와 실제
#   작업으로 진행되고 있는 과정이구나 를 명시적으로 보고 파악할 수 있어야 한다」
#  -> 그래서 셋을 그린다. 관문 타임라인(언제까지 무엇이) · 갈래별 막대(누가 어디를)
#     · 살아있음 증거(이 숫자가 어디서 왔는가). 65행 표는 그 아래로 접는다.
START = datetime.date(2026, 8, 6)
END = datetime.date(2026, 12, 11)
# ★ 관문 목록을 여기 박지 않는다 (2026-09-01).
#   build_wbs.GATES 에 9/4 기획발표가 빠져 있었고, 나는 그것을 그대로 베껴
#   왔다. 두 자리가 같은 값을 각자 들고 있으면 한쪽이 늦게 바뀐다.
#   이제 xlsx 행에서 «어떤 관문이 있고 마감이 언제인가» 를 읽는다.
#   build_wbs 가 마감일을 각 행의 «예상 완료 날짜» 로 넣어 주므로 그것이 원천이다.
def gates_of(body):
    seen = {}
    for r in body:
        g = str(r.get('관문', '')).strip()
        d = r.get('예상 완료 날짜')
        if not g or g in ('None', 'none'):
            continue
        if hasattr(d, 'year'):
            d = datetime.date(d.year, d.month, d.day)
        else:
            try:
                d = datetime.date.fromisoformat(str(d)[:10])
            except ValueError:
                continue
        if g not in seen or d > seen[g]:
            seen[g] = d
    return sorted(seen.items(), key=lambda kv: kv[1])
AREAS = ['A1 정책 학습', 'A2 지형·씬 제작', 'A3 평가', 'A4 트윈·렌더',
         'B1 항법', 'B2 인지', 'C1 기록', 'C2 운영']


def _done(r):
    return str(r.get('완료율', '')).rstrip('%') in ('100', '1.0', '1')


def _nogate(r):
    return str(r.get('관문', '')).strip() in ('', 'None', 'none')


def _today(meta):
    for k, v in meta.items():
        if '기준일' in str(k):
            try:
                return datetime.date.fromisoformat(str(v)[:10])
            except ValueError:
                pass
    for v in meta.values():
        try:
            return datetime.date.fromisoformat(str(v)[:10])
        except ValueError:
            pass
    return None


def gate_fig(meta, body):
    """관문 타임라인.

    ★ 두 뜻을 한 축에 싣지 않는다 (9/1 자가 지적).
      처음에는 달력 막대를 완료 비율만큼 칠했다. 그러면 가로축이 «시간» 인데
      칠은 «건수» 라서, 5/11 완료가 「8월 20일까지 진행됐다」로 읽힌다.
      캡션이 주장하는 것과 그림이 그리는 것이 달라진다.
      그래서 갈랐다. 왼쪽은 달력(언제까지), 오른쪽은 완료(얼마나).
    """
    today = _today(meta)
    span = float((END - START).days)
    cx0, cx1 = 214.0, 742.0          # 달력 구간
    px0, pw = 800.0, 104.0           # 완료 막대 (길이가 고정이라 서로 비교된다)

    def X(d):
        return cx0 + (cx1 - cx0) * ((d - START).days / span)

    rows = []
    for name, due in gates_of(body):
        rs = [r for r in body if str(r.get('관문', '')).strip() == name]
        rows.append((name, due, len(rs), sum(1 for r in rs if _done(r))))
    none_n = sum(1 for r in body if _nogate(r))

    h = 58 + len(rows) * 46 + 56
    o = ['<svg viewBox="0 0 980 %d" role="img" aria-label="관문 타임라인. 네 관문의 '
         '마감일과 관문별 완료 건수" style="width:100%%;height:auto;display:block">' % h]
    o.append('<text x="14" y="30" font-size="11" font-weight="800" letter-spacing="2.2" '
             'fill="var(--dim)">관문</text>')
    o.append('<text x="%.1f" y="30" font-size="11" font-weight="800" letter-spacing="2.2" '
             'fill="var(--dim)">달력</text>' % cx0)
    o.append('<text x="%.1f" y="30" font-size="11" font-weight="800" letter-spacing="2.2" '
             'fill="var(--dim)">완료</text>' % px0)

    m = datetime.date(2026, 9, 1)
    while m <= END:
        o.append('<line x1="%.1f" y1="38" x2="%.1f" y2="%d" stroke="var(--rule)"/>'
                 % (X(m), X(m), h - 34))
        o.append('<text x="%.1f" y="30" font-size="10.5" fill="var(--ink-3)">%d월</text>'
                 % (X(m) + 3, m.month))
        m = datetime.date(m.year + (m.month == 12), m.month % 12 + 1, 1)

    y = 58
    for name, due, n, dn in rows:
        left = ' · D%+d' % (due - today).days if today else ''
        o.append('<text x="14" y="%d" font-size="12.5" font-weight="800" fill="var(--ink)">'
                 '%s</text>' % (y + 13, esc(name)))
        o.append('<text x="14" y="%d" font-size="10.5" fill="var(--ink-3)">%s 마감%s</text>'
                 % (y + 29, due.strftime('%m/%d'), left))
        # 달력: 프로젝트 시작부터 이 관문 마감까지. 칠하지 않는다
        o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--ink-3)" '
                 'stroke-width="1.4"/>' % (X(START), y + 16, X(due), y + 16))
        o.append('<circle cx="%.1f" cy="%d" r="3" fill="var(--ink-3)"/>'
                 % (X(START), y + 16))
        o.append('<rect x="%.1f" y="%d" width="7" height="18" rx="2" fill="var(--note)"/>'
                 % (X(due) - 3.5, y + 7))
        # 완료: 길이가 고정된 막대. 네 관문이 같은 자로 비교된다
        o.append('<rect x="%.1f" y="%d" width="%.1f" height="18" rx="3" '
                 'fill="var(--paper-2)" stroke="var(--rule)"/>' % (px0, y + 7, pw))
        if n:
            if dn:
                o.append('<rect x="%.1f" y="%d" width="%.1f" height="18" rx="3" '
                         'fill="var(--dim-soft)" stroke="var(--dim)"/>'
                         % (px0, y + 7, pw * dn / float(n)))
            o.append('<text x="%.1f" y="%d" font-size="11.5" font-weight="750" '
                     'fill="var(--ink-2)" font-variant-numeric="tabular-nums">%d / %d'
                     '</text>' % (px0 + pw + 9, y + 20, dn, n))
        else:
            o.append('<text x="%.1f" y="%d" font-size="11" fill="var(--ink-3)">아직 없다'
                     '</text>' % (px0 + pw + 9, y + 20))
        y += 46

    if today and START <= today <= END:
        tx = X(today)
        o.append('<line x1="%.1f" y1="38" x2="%.1f" y2="%d" stroke="var(--ink)" '
                 'stroke-width="1.6" stroke-dasharray="4 3"/>' % (tx, tx, h - 34))
        o.append('<text x="%.1f" y="%d" font-size="11" font-weight="800" fill="var(--ink)" '
                 'text-anchor="middle">오늘 %s</text>'
                 % (tx, h - 32, today.strftime('%m/%d')))
    o.append('<text x="14" y="%d" font-size="10.5" fill="var(--ink-3)">가로 자리는 '
             '날짜다. 완료 막대는 날짜와 무관하게 건수 비율만 나타낸다%s</text>'
             % (h - 4, ' · 관문이 안 붙은 작업 %d건은 이 그림에 없다' % none_n
                if none_n else ''))
    o.append('</svg>')
    return ''.join(o)


def area_fig(body):
    """갈래별 막대. 여덟 갈래에 실제 작업이 얼마나 붙어 있는가."""
    st = []
    for a in AREAS:
        rs = [r for r in body if str(r.get('WBS', '')).strip() == a]
        st.append((a, len(rs), sum(1 for r in rs if _done(r))))
    un = [r for r in body if str(r.get('WBS', '')).strip() == '(미분류)']
    st.append(('(미분류)', len(un), sum(1 for r in un if _done(r))))
    mx = float(max([n for _, n, _ in st] + [1]))

    x0, x1 = 152.0, 880.0
    h = 40 + len(st) * 34 + 16
    o = ['<svg viewBox="0 0 980 %d" role="img" aria-label="작업 영역 여덟 갈래별 '
         '작업 건수와 완료 건수" style="width:100%%;height:auto;display:block">' % h]
    o.append('<text x="14" y="24" font-size="11" font-weight="800" letter-spacing="2.2" '
             'fill="var(--dim)">갈래</text>')
    o.append('<text x="%.1f" y="24" font-size="11" fill="var(--ink-3)">'
             '진한 칸이 닫힌 이슈다</text>' % x0)
    y = 40
    for name, n, dn in st:
        w = (x1 - x0) * n / mx
        o.append('<text x="14" y="%d" font-size="12" font-weight="%d" fill="var(--%s)">%s'
                 '</text>' % (y + 16, 750 if n else 500,
                              'ink' if n else 'ink-3', esc(name)))
        if n:
            o.append('<rect x="%.1f" y="%d" width="%.1f" height="22" rx="3" '
                     'fill="var(--paper-2)" stroke="var(--rule)"/>' % (x0, y, w))
            if dn:
                o.append('<rect x="%.1f" y="%d" width="%.1f" height="22" rx="3" '
                         'fill="var(--dim-soft)" stroke="var(--dim)"/>'
                         % (x0, y, w * dn / float(n)))
            o.append('<text x="%.1f" y="%d" font-size="11.5" fill="var(--ink-2)" '
                     'font-variant-numeric="tabular-nums">%d건 · %d 완료</text>'
                     % (x0 + w + 8, y + 16, n, dn))
        else:
            o.append('<text x="%.1f" y="%d" font-size="11.5" fill="var(--ink-3)">'
                     '아직 이슈가 없다</text>' % (x0, y + 16))
        y += 34
    o.append('</svg>')
    return ''.join(o)


def evidence(meta, body):
    """이 숫자가 어디서 왔는가. 그리고 무엇이 아직 안 맞는가."""
    n = len(body)
    un = sum(1 for r in body if str(r.get('WBS', '')).strip() == '(미분류)')
    ng = sum(1 for r in body if _nogate(r))
    doc = sum(1 for r in body if str(r.get('산출물', '')).strip() not in ('', 'None'))
    go2 = sum(1 for r in body if str(r.get('저장소', '')) == 'foothold-go2')
    who = {}
    for r in body:
        for p in str(r.get('담당자', '')).split(','):
            p = p.strip()
            if p and p != 'None':
                who[p] = who.get(p, 0) + 1
    top = sorted(who.items(), key=lambda kv: -kv[1])
    base = _today(meta)
    elapsed = ''
    for k, v in meta.items():
        if '경과' in str(k):
            elapsed = str(v)

    src = (
        '<h3>이 표는 손으로 쓴 것이 아니다</h3>'
        '<div class="tw"><table><thead><tr><th>단계</th><th>무엇이</th></tr></thead>'
        '<tbody>'
        '<tr><td>원천</td><td>GitHub 이슈 · <code>foothold-lab</code> 과 '
        '<code>foothold-go2</code> 두 저장소를 함께 읽는다</td></tr>'
        '<tr><td>1층 · 2층</td><td>작업 영역 여덟 갈래와 관문 넷은 사람이 정했다 '
        '(<code>docs/ROLES.md</code>)</td></tr>'
        '<tr><td>3층</td><td>세부 작업은 이슈에서 온다. 이슈 라벨이 갈래를, '
        '마일스톤이 관문을 정한다</td></tr>'
        '<tr><td>생성</td><td><code>tools/build_wbs.py</code> · 워크플로 «주간 리포트» 가 '
        '매주 월요일 09:00 KST 에 돌린다</td></tr>'
        '<tr><td>웹</td><td>빌드가 <code>wbs.xlsx</code> 를 읽어 이 자리에 붓는다. '
        '이 표를 손으로 고칠 수 없다</td></tr>'
        '<tr><td>기준일</td><td>%s%s</td></tr>'
        '</tbody></table></div>' % (
            base.isoformat() if base else '미상',
            ' · 기간 경과 %s (%s ~ %s)' % (elapsed, START.isoformat(), END.isoformat())
            if elapsed else ''))

    g = ['<h3>데이터가 솔직히 말하는 것</h3>',
         '<p>보기 좋게 고르지 않았다. 지금 이 숫자가 그대로다.</p>', '<ul class="tight">',
         '<li><b>완료율은 0% 아니면 100% 뿐이다.</b> 이슈가 닫혔는지만 보기 때문이다. '
         '진행 중인 작업의 «절반쯤» 을 아직 표현하지 못한다</li>']
    if un:
        g.append('<li><b>%d건(%d%%)은 갈래가 안 붙어 있다.</b> 분류 폼을 만들기 전에 연 '
                 '이슈들이다. 새 이슈는 폼이 강제한다</li>' % (un, round(un * 100.0 / n)))
    if ng:
        g.append('<li><b>%d건은 관문이 안 붙어 있다.</b> 위 타임라인에 나오지 않는다</li>' % ng)
    g.append('<li><b>산출물 경로가 붙은 행은 %d / %d 이다.</b> 나머지는 문서로 떨어지지 '
             '않는 작업이거나 아직 안 정했다</li>' % (doc, n))
    if top:
        g.append('<li><b>담당이 %s 에 %d건(%d%%) 몰려 있다.</b> 다음은 %s. 이 쏠림은 '
                 '실제다</li>' % (esc(top[0][0]), top[0][1], round(top[0][1] * 100.0 / n),
                                 ' · '.join('%s %d' % (esc(k), v) for k, v in top[1:4])))
    g.append('<li>저장소는 %d건이 <code>foothold-lab</code>, %d건이 '
             '<code>foothold-go2</code> 다</li>' % (n - go2, go2))
    g.append('</ul>')
    return src + ''.join(g)


def table(meta, body):
    idx = SHOW
    th = ''.join('<th>%s</th>' % esc(c) for c in idx)
    trs = []
    for r in body:
        top = not str(r['WBS'])[1:2].isdigit() or str(r.get('작업 이름', '')).startswith('[')
        tds = []
        for c in idx:
            v = r.get(c, '')
            if c in ('계획율', '완료율') and v != '':
                try:
                    v = '%d%%' % round(float(str(v).rstrip('%')) *
                                       (100 if float(str(v).rstrip('%')) <= 1 else 1))
                except ValueError:
                    pass
            if hasattr(v, 'strftime'):
                v = v.strftime('%m/%d')
            tds.append('<td>%s</td>' % esc(v))
        trs.append('<tr%s>%s</tr>' % (' class="wtop"' if top else '', ''.join(tds)))
    cap = ' · '.join('%s %s' % kv for kv in meta.items() if kv[1])
    css = (
        '<style>.wbs3 th{white-space:nowrap}.wbs3 .wtop td{font-weight:750;'
        'border-top:2px solid var(--rule)}.wbs3 td:nth-child(5),.wbs3 td:nth-child(6)'
        '{font-variant-numeric:tabular-nums;text-align:right}'
        '.wfig{margin:1.1rem 0 1.8rem}'
        '.wfold{margin:1.4rem 0 0;border:1px solid var(--rule);border-radius:7px;'
        'padding:.7rem .95rem;background:var(--paper-2)}'
        '.wfold>summary{cursor:pointer;font-weight:750;font-size:.92rem;color:var(--ink)}'
        '.wfold[open]>summary{margin-bottom:.7rem}.wfold+h2,.wfold+*{margin-top:2.4rem}'
        '.wfold{margin:1.4rem 0 2.2rem}</style>')
    head = (
        '<h2 id="wbs-live">지금의 WBS <span style="font-size:.7em;color:var(--ink-3)">'
        '%s</span></h2>'
        '<p class="lede">여덟 갈래 · 관문 넷 · 작업 %d건. 아래 그림은 이슈에서 방금 '
        '만들어진 것이고 사람이 손으로 고칠 수 없다.</p>' % (esc(cap), len(body)))
    fold = (
        '<details class="wfold"><summary>세부 작업 %d건을 표로 펼치기</summary>'
        '<div class="tw"><table class="wbs3"><thead><tr>%s</tr></thead>'
        '<tbody>%s</tbody></table></div></details>' % (len(body), th, ''.join(trs)))
    return '\n'.join([
        head, css,
        '<div class="wfig">' + gate_fig(meta, body) + '</div>',
        '<div class="wfig">' + area_fig(body) + '</div>',
        evidence(meta, body), fold])


def main(vault):
    import docs_pages
    lab = next((x for x in docs_pages.LAB_CANDIDATES
                if os.path.isdir(os.path.join(x, 'docs'))), None)
    p = os.path.join(vault, 'deliverable-wbs.html')
    if not (lab and os.path.isfile(p)):
        print('  [!] WBS: 대상 없음')
        return False
    meta, body, why = read(lab)
    if why:
        print('  [!] WBS 를 못 읽었다: %s' % why)
        return False
    # ★ 원칙 2: 빈 표를 조용히 내보내지 않는다
    if len(body) < 5:
        print('  [!] WBS 행이 %d개뿐이다. 주입 중단' % len(body))
        return False
    sec = MARK_A + '\n' + table(meta, body) + '\n' + MARK_B
    s = io.open(p, encoding='utf-8').read()
    s = re.sub(re.escape(MARK_A) + r'.*?' + re.escape(MARK_B), '', s, flags=re.S)
    m = re.search(r'<h2', s)                      # 본문 첫 절 앞 = 설계 설명보다 위
    pos = m.start() if m else s.find('</header>') + len('</header>')
    s = s[:pos] + sec + '\n\n' + s[pos:]
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
    print('  WBS 표 주입: %d행 · 열 %d (#77)' % (len(body), len(SHOW)))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main(os.path.dirname(HERE)) else 1)
