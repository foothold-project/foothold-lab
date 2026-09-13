# -*- coding: utf-8 -*-
"""산출물 현황 페이지 + 표지 D-day 띠.

왜: 「우리가 무엇을 언제까지 내야 하는가」가 여러 문서에 흩어져 있어서 팀장도
찾는 데 오래 걸렸다. 표지에 상시로 띄워 찾을 일을 없앤다.

상태는 하드코딩하지 않는다. 각 산출물 md 의 «> 상태:» 한 줄이 진실이다.
빌드할 때마다 다시 읽으므로, 문서를 고치면 다음 배포에 그대로 반영된다.
"""
import datetime
import html as H
import io
import os
import re
import buildtime

# ★ 2026-09-02. 여기에 후보 표가 따로 있었다. 같은 규칙이 두 자리에 살면
#   한쪽을 고쳐도 다른 쪽이 옛 경로를 본다 (철칙 4). docs_pages 가 유일 원본이다.
#   같은 리스트 객체를 가리키므로 재현 모드의 restrict() 가 여기에도 먹는다.
from docs_pages import LAB_CANDIDATES

# (관문, 기한, 한 줄, [(lab 안 경로, 산출물 이름)])
GATES = [
    # 운영진 제출은 3종이다(docs/WORKFLOW.md). 앞의 셋이 그것이고 뒤는 부속이다.
    # 2026-09-04 정정: 여기가 기획서 «요약본» 과 초안 WBS 를 걸고 있었다. 낸 것은
    # proposal.md 와 wbs-official.md 인데 웹 페이지 자체가 없어서 걸 수도 없었다.
    # ★ 2026-09-05 팀장 지정 순서. 「관련성 순」이 아니라는 지적을 받고 바로잡았다.
    #   기획서 -> 요약 -> 브레인스토밍 -> WBS -> 역할과 책임 -> 발표 자료.
    #   제출 3종을 앞에 몰던 이전 순서는 팀장 지정과 달랐다. 지정이 이긴다.
    ('기획발표', datetime.date(2026, 9, 4), '운영진 제출 3종. 기획서 · 브레인스토밍 · WBS', [
        ('deliverables/plan/proposal.md', '프로젝트 기획서'),
        ('deliverables/plan/proposal-summary.md', '기획서 요약'),
        ('deliverables/plan/brainstorming.md', '브레인스토밍'),
        ('deliverables/plan/wbs-official.md', 'WBS'),
        ('deliverables/plan/roles-responsibilities.md', '역할과 책임'),
        ('deliverables/plan/proposal-deck.md', '발표 자료'),
    ]),
    ('A-정책', datetime.date(2026, 9, 12), '우리 지형으로 학습한 정책과 지표 세트', [
        ('deliverables/midterm/policy-metrics.md', '기준 정책 · 지표 세트'),
    ]),
    ('MVP · 중간발표', datetime.date(2026, 9, 30), '트랙 A 완결', [
        ('deliverables/midterm/generalization-report.md', '일반화 평가표'),
        ('deliverables/midterm/twin-render.md', '디지털 트윈 · 렌더 시연물'),
    ]),
    ('NAV · 실기 항법', datetime.date(2026, 11, 7), '조선대 단계 종료', [
        ('deliverables/final/nav-report.md', '실기 항법 검증 리포트'),
    ]),
    ('FINAL · 최종발표', datetime.date(2026, 12, 11), '지정 코스 자율주행 시연', [
        ('deliverables/final/final-report.md', '최종 실증결과 보고서'),
    ]),
]

CLS = {'대기': ('wait', '대기'), '초안': ('go', '진행중'),
       '검토중': ('go', '진행중'), '확정': ('done', '완료')}


def lab_root():
    for p in LAB_CANDIDATES:
        if os.path.isdir(p):
            return p
    return None


def read_item(lab, rel):
    """산출물 md 에서 상태·완료 기준·본문 분량을 읽는다."""
    p = os.path.join(lab, rel.replace('/', os.sep))
    if not os.path.isfile(p):
        return '대기', '', 0
    s = io.open(p, encoding='utf-8', newline=None).read()
    m = re.search(r'^>\s*상태:\s*(.+)$', s, re.M)
    state = m.group(1).strip() if m else '대기'
    if state not in CLS:
        state = '초안'
    # ★ 인용 블록이 파일 끝에서 끝나는 경우가 있어 «빈 줄» 만 보면 못 잡는다.
    #   실측: policy-metrics.md 는 마지막 줄이 완료 기준이라 「아직 없음」으로 나왔다.
    m = re.search(r'^>\s*\*\*완료 기준[^*]*\*\*:\s*(.+?)(?=\n>\s*\n|\n\n|\Z)',
                  s, re.M | re.S)
    dod = re.sub(r'\s*\n>\s*', ' ', m.group(1)).strip() if m else ''
    dod = re.sub(r'\s*마일스톤:.*$', '', dod).strip()   # 관문은 표에 이미 있다
    body = re.sub(r'^>.*$', '', s, flags=re.M)
    body = re.sub(r'^#.*$', '', body, flags=re.M)
    return state, dod, len(body.strip())


def today_kst():
    return (buildtime.now().astimezone(datetime.timezone.utc)
            + datetime.timedelta(hours=9)).date()


def build_rows(lab, today):
    out = []
    for name, due, note, items in GATES:
        rows = []
        for rel, label in items:
            state, dod, size = read_item(lab, rel)
            if state != '확정' and size < 400:
                state = '대기'          # 완료 기준만 든 더미
            rows.append((label, state, dod, rel))
        out.append((name, due, note, (due - today).days, rows))
    return out


def band_html(rows):
    """표지 맨 위 띠.

    팀장 확정(2026-08-26): 「MVP D-35, FINAL 107일 00:00:00 이런식으로」
    「MVP, FINAL 등에서 제출해야 하는 서류들 같이 보여주면서 카운팅」

    그래서 고정으로 MVP 와 FINAL 을 싣고, 그보다 임박한 관문이 따로 있으면
    맨 앞에 하나 더 붙인다. 급한 것을 표지에서 빼지 않는다.
    FINAL 은 언제나 초 단위로 흐른다. 마지막 날까지 남은 시간이 이 프로젝트의 축이다.
    """
    live = [r for r in rows if r[3] >= 0]
    if not live:
        return ''
    pick = [r for r in live if r[0].startswith('MVP') or r[0].startswith('FINAL')]
    nearest = live[0]
    if nearest not in pick:
        pick = [nearest] + pick
    cells = []
    for name, due, note, left, items in pick:
        done = sum(1 for _, st, _, _ in items if st == '확정')
        names = ' · '.join(l for l, _, _, _ in items[:3])
        if len(items) > 3:
            names += ' 외 %d' % (len(items) - 3)
        # ★ 2026-08-28 팀장 지적: 「디데이 제대로 카운팅 되는지」.
        #   전에는 FINAL 만 살아 있고 나머지는 빌드 순간의 숫자를 구워 넣었다.
        #   하루만 안 굽면 표지가 틀린 날짜를 말한다. 전부 살린다.
        #   빌드 값은 그대로 두어 자바스크립트가 없어도 대충은 맞게 보인다.
        if name.startswith('FINAL'):
            big = ('<span class="dd-live dd-sec" data-due="%s">%s일</span>'
                   % (due.isoformat(), left))
        else:
            big = ('<span class="dd-live" data-due="%s">%s</span>'
                   % (due.isoformat(), ('D-%s' % left) if left else '오늘'))
        cells.append(
            '<a class="dd-cell" href="deliverables.html">'
            '<span class="dd-name">%s</span>'
            '<span class="dd-num">%s</span>'
            '<span class="dd-sub">%s · 제출 %d/%d</span>'
            '<span class="dd-list">%s</span></a>'
            % (H.escape(name), big, due.strftime('%m월 %d일'),
               done, len(items), H.escape(names)))
    return ('<div class="dday" aria-label="다음 관문까지 남은 기간과 제출물">%s</div>'
            % ''.join(cells))


CSS = """
.dday{display:flex;gap:0;border:1px solid var(--rule);border-radius:10px;
  overflow:hidden;margin:0 0 18px;background:var(--card)}
.dday .dd-cell{flex:1;display:block;padding:12px 16px;text-decoration:none;
  color:inherit;border-right:1px solid var(--rule)}
.dday .dd-cell:last-child{border-right:0}
.dday .dd-cell:hover{background:var(--paper-2)}
.dday .dd-name{display:block;font-size:.76rem;letter-spacing:.04em;color:var(--ink-3)}
.dday .dd-num{display:block;font-size:1.5rem;font-weight:700;line-height:1.15;
  color:var(--dim-ink);font-variant-numeric:tabular-nums}
.dday .dd-sub{display:block;font-size:.76rem;color:var(--ink-2);margin-top:2px}
.dday .dd-list{display:block;font-size:.72rem;color:var(--ink-3);margin-top:5px;
  line-height:1.45}
@media (prefers-color-scheme:dark){.dday .dd-num{color:var(--dim)}}
:root[data-theme="dark"] .dday .dd-num{color:var(--dim)}
:root[data-theme="light"] .dday .dd-num{color:var(--dim-ink)}
@media(max-width:560px){.dday{flex-direction:column}
  .dday .dd-cell{border-right:0;border-bottom:1px solid var(--rule)}}
.dl-tbl{width:100%;border-collapse:collapse;margin:10px 0 26px}
.dl-tbl th,.dl-tbl td{border-bottom:1px solid var(--rule);padding:9px 10px;
  text-align:left;vertical-align:top;font-size:.92rem}
.dl-tbl th{color:var(--ink-3);font-weight:600;font-size:.8rem}
.st-wait,.st-go,.st-done{display:inline-block;padding:1px 8px;border-radius:999px;
  font-size:.76rem;font-weight:600;white-space:nowrap}
.st-wait{background:var(--paper-2);color:var(--ink-2);border:1px solid var(--rule)}
.st-go{background:var(--note-soft);color:var(--note-ink)}
.st-done{background:var(--dim-soft);color:var(--dim-ink)}
.gate-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-top:26px}
.gate-h .g-left{font-variant-numeric:tabular-nums;color:var(--ink-3);font-size:.88rem}
"""

JS = """
(function(){
  // ★ 이 script 는 .dday 블록보다 «앞» 에 들어간다 (표지 조립 순서 때문).
  //   그대로 querySelector 하면 null 이라 조용히 빠져나간다. 실제로 그랬다.
  function start(){
  // ★ 2026-08-28. 전에는 querySelector 로 «하나만» 잡아서 FINAL 만 살아 있었다.
  //   나머지 관문은 빌드 순간의 숫자가 그대로 굳어 있었고, 하루 지나면 틀렸다.
  var els=document.querySelectorAll('.dd-live'); if(!els.length) return;
  // ★ 2026-09-03. 전에는 마감까지 남은 «밀리초»를 floor 해서 날을 셌다.
  //   마감 기준시각이 그날 09:00 이라, 마감이 «내일» 이어도 남은 시간이 24시간
  //   미만이면 d=0 이 되고 d>0 가드에 걸려 「오늘」로 떨어졌다. 9/3 13:18 에
  //   기획발표(9/4)가 실제로 「오늘」로 떴다. dd-sec 도 같은 floor 탓에 달력
  //   차이보다 하루 적었다 (FINAL 이 99일인데 98일). 시간이 아니라 KST 달력
  //   «날짜»의 일련번호 차이를 센다. 값이 바뀌는 자리는 자정 하나뿐이다.
  function one(el){
    var due=el.getAttribute('data-due')||'', p=due.split('-'), now=new Date();
    var dueDay=Date.UTC(+p[0],+p[1]-1,+p[2])/86400000;
    var nowDay=Math.floor((now.getTime()+9*3600000)/86400000);
    var diff=dueDay-nowDay;
    if(diff<0){ el.textContent='지남'; return; }
    if(el.classList.contains('dd-sec')){
      // 일수는 달력 차이, 시:분:초는 지금처럼 마감시각까지 남은 시간이다.
      var ms=new Date(due+'T09:00:00+09:00')-now; if(ms<0) ms=0;
      var r=ms%86400000;
      var h=String(Math.floor(r/3600000)).padStart(2,'0');
      var m=String(Math.floor(r%3600000/60000)).padStart(2,'0');
      var s=String(Math.floor(r%60000/1000)).padStart(2,'0');
      el.textContent=diff+'일 '+h+':'+m+':'+s;
    }else{
      // 마감 날짜가 «오늘» 일 때만 오늘. 그 밖에는 자정에 한 칸씩 준다.
      el.textContent = diff>0 ? ('D-'+diff) : '오늘';
    }
  }
  function tick(){ for(var i=0;i<els.length;i++) one(els[i]); }
  tick(); setInterval(tick,1000);
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',start);
  }else{ start(); }
})();
"""


def body_html(rows):
    parts = []
    for name, due, note, left, items in rows:
        done = sum(1 for _, st, _, _ in items if st == '확정')
        when = ('<span class="dd-live" data-due="%s">%s</span>'
                % (due.isoformat(),
                   ('D-%d' % left) if left > 0 else ('오늘' if left == 0 else '지남')))
        parts.append('<div class="gate-h"><h2 style="margin:0">%s</h2>'
                     '<span class="g-left">%s · %s · 산출물 %d/%d</span></div>'
                     % (H.escape(name), due.strftime('%Y년 %m월 %d일'),
                        when, done, len(items)))
        parts.append('<p class="sub" style="margin:4px 0 0">%s</p>' % H.escape(note))
        parts.append('<table class="dl-tbl"><thead><tr>'
                     '<th style="width:28%">산출물</th><th style="width:11%">상태</th>'
                     '<th style="width:11%">제출본</th>'
                     '<th>완료 기준</th></tr></thead><tbody>')
        for label, state, dod, rel in items:
            cls, txt = CLS[state]
            cell = H.escape(dod) if dod else (
                '<span style="color:var(--ink-3)">아직 없음</span>')
            # 문서가 웹 페이지로 나와 있으면 제목에서 바로 열리게 한다.
            # md 만 남기고 웹에 안 붙이면 아무도 못 읽는다 (팀장 지적 2026-08-27).
            try:
                import deliverables_docs as dd
                href = dd.page_of(rel)
            except Exception:
                href = ''
            name = ('<a href="%s"><b>%s</b></a>' % (href, H.escape(label))) if href \
                else '<b>%s</b>' % H.escape(label)
            # 납품한 PDF 를 여기서 바로 연다. 2026-09-05 까지 사이트 전체에
            # PDF 링크가 0개였다. 문서는 웹으로 읽고 제출본은 원본 그대로 본다.
            try:
                web = dd.pdf_for(rel)
                pdf = ('<a href="%s" target="_blank" rel="noopener">PDF</a>'
                       % web[1]) if web else ''
            except Exception:
                pdf = ''
            try:
                pw = dd.presented_for(rel)
                if pw:
                    pdf += (' · <a href="%s" target="_blank" rel="noopener">'
                            'HTML</a>' % pw[1])
            except Exception:
                pass
            if not pdf:
                pdf = '<span style="color:var(--ink-3)">없음</span>'
            parts.append('<tr><td>%s</td>'
                         '<td><span class="st-%s">%s</span></td>'
                         '<td>%s</td><td>%s</td></tr>'
                         % (name, cls, txt, pdf, cell))
        parts.append('</tbody></table>')
    return '\n'.join(parts)
