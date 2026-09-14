# -*- coding: utf-8 -*-
"""허브 여섯의 v3 렌더러. 결정 = lab `docs/decisions/20260830-hub-v3.md`.

  화면의 주어는 문서가 아니라 상태다. 합격 기준 하나:
  **이 화면을 보고, 팀장에게 묻지 않고 다음 행동을 할 수 있는가.**

  허브마다 지배하는 축이 다르므로 뼈대도 다르다. 한 틀로 여섯을 찍으면
  「세로 나열」이 된다 (철칙 3 위반 · 팀장 지적 2026-08-30).

  일정   시간      이번 주([주간] 이슈) -> 관문 다섯(같은 골격) -> WBS·기록
  연구   근거 출처  출발선(열린 이슈가 걸린 실측) -> 실패 험지 5종 카드(#179)
                   -> 잰 것(본PoC 먼저) -> 읽은 것
  회의   시간·자리  타임라인 + 자리 필터 칩 (자리는 렌즈, 쪼개지 않는다)
  기획   안/밖     밖 3 크게 · 안 3 줄
  기술   순서      01->02->03 경로 (번호가 순서인 유일한 자리)
  파이프라인 상황   합류 -> 매일 -> 투고
"""
import io
import json
import os
import re
import subprocess
import sys
import buildtime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

BOARD = 'https://github.com/orgs/foothold-project/projects/1'

_LAB = None
_ISSUES = None
_GRAPH = None


def lab():
    global _LAB
    if _LAB is None:
        import docs_pages
        _LAB = next((x for x in docs_pages.LAB_CANDIDATES
                     if os.path.isdir(os.path.join(x, 'docs'))), '')
    return _LAB


def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def meta(path, fields=('분류', '작성', '근거', '요지', '상태', '판', '자리',
                       '담당', '언제 보나', '차례', '결론', '지위')):
    try:
        t = io.open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return {}
    o = {}
    for f in fields:
        m = re.search(r'^>\s*%s\s*:\s*(.+)$' % f, t[:2500], re.M)
        if m:
            o[f] = m.group(1).strip()
    m = re.search(r'^#\s+(.+)$', t, re.M)
    o['제목'] = m.group(1).strip() if m else os.path.basename(path)
    return o


def issues():
    """열린 이슈 전부. 한 번만 부른다. 실패하면 시끄럽게 알리고 빈 목록."""
    global _ISSUES
    if _ISSUES is not None:
        return _ISSUES
    try:
        r = subprocess.run(
            ['gh', 'issue', 'list', '--state', 'open', '--limit', '100',
             '--json', 'number,title,body,labels',
             '--repo', 'foothold-project/foothold-lab'],
            capture_output=True, text=True, timeout=45, encoding='utf-8')
        _ISSUES = json.loads(r.stdout) if r.returncode == 0 else []
        if r.returncode != 0:
            print('  [!] 이슈를 못 읽었다: %s' % (r.stderr or '')[:80])
    except Exception as e:
        print('  [!] 이슈를 못 읽었다: %s' % e)
        _ISSUES = []
    return _ISSUES


def graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = {}
        p = os.path.join(lab(), 'docs', 'ops', 'doc-graph.json')
        if os.path.isfile(p):
            try:
                for d in json.load(io.open(p, encoding='utf-8')):
                    _GRAPH[d['path']] = d
            except Exception:
                pass
    return _GRAPH


def added(site, page):
    import newbadge
    return newbadge.first_added(site, page) or ''


def ev_short(s):
    s = (s or '').split('(')[0].strip()
    for k in ('실측', '공식', '코드', '본인', '팀', '현장', '조선대', '전사', '음성'):
        if s.startswith(k):
            return k
    return s[:4] or '미상'


def _who_when(m):
    """머리말 «작성: 이름 · 2026-08-27 11:20» 에서 (이름, 날짜시각).

    ★ 팀장 지적 (8/31): 「년월일 시간」 을 다 쓰라고 했는데 월/일만 넣었다.
      시각까지 있으면 같은 날 여러 건의 선후가 보인다.
    """
    raw = (m.get('작성') or '').strip()
    if not raw:
        return '', ''
    parts = [x.strip() for x in raw.split('·')]
    who = parts[0] if parts else ''
    when = ''
    for x in parts[1:]:
        d = re.search(r'(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{2}):(\d{2}))?', x)
        if d:
            when = '%s-%s-%s' % (d.group(1), d.group(2), d.group(3))
            if d.group(4):
                when += ' %s:%s' % (d.group(4), d.group(5))
            break
    return who, when


def _newest_first(m):
    """카드 정렬 열쇠. `sorted(..., key=_newest_first, reverse=True)` 로 쓴다.

    ★ 2026-09-14 팀장 지적: 「연구 허브 날짜가 뒤죽박죽이다. 최신 글이 맨 위로」.
      맞다. 카드를 내는 자리가 둘인데 **둘 다 날짜로 안 세고 있었다.**

        실측 카드  파일 «경로» 순 (`x[2]`). 날짜와 아무 상관이 없다
        조사 카드  머리말 `작성` 통문자열 순. 그 값이 「이름 · 날짜」 라서
                   «이름» 이 먼저 걸린다. 그래서 저자별로 뭉치고 날짜가 되감긴다

      실측 (배포본 hub-research.html · 묶음 8개): 여섯 묶음이 뒤죽박죽,
      두 묶음이 오름차순. 내림차순인 묶음은 하나도 없었다.

      날짜가 없는 문서는 빈 문자열이라 `reverse=True` 에서 «맨 아래» 로 간다.
      같은 날짜면 제목으로 가른다 (빌드마다 순서가 흔들리지 않게).
    """
    return (_who_when(m)[1], m.get('제목', ''))

def _gist(m, limit=None):
    """카드에 실을 「요지」. 마크다운을 글자로 내보내지 않는다.

    ★ 2026-09-14 팀장 지적 계열. 머리말 `요지:` 에는 `**굵게**` 가 들어 있다.
      `esc()` 로만 감싸면 화면에 별표가 그대로 뜬다. 라이브에서 2곳이었다.

      카드는 한 줄짜리라 태그를 넣지 않고 **문법만 벗긴다.** 굵게 표시가
      필요하면 본문에서 본다.

      자리가 셋이다 (실측 카드 · 조사 카드 · 그래프 카드). 한쪽만 고치면
      또 갈라지므로 여기 하나로 모은다.
    """
    s = (m.get('요지') or '').strip()
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)     # **굵게**
    s = re.sub(r'(?<!\w)__([^_]+)__(?!\w)', r'\1', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)           # `코드`
    s = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', s)  # [글자](주소)
    s = re.sub(r'\s+', ' ', s).strip()
    if limit and len(s) > limit:
        s = s[:limit]
    return s

AREA_HUE = {'A/정책학습': 'a1', 'A/평가': 'a2', 'A/지형씬제작': 'a3',
            'A/트윈렌더': 'a4', 'B/항법': 'b1', 'B/인지': 'b2',
            'C/기록': 'c1', 'C/운영': 'c2'}


def _thumb(page):
    """문서에 대표 이미지가 있으면 오른쪽에 작게. 없으면 아무것도 안 낸다.

    ★ 팀장 제안 (8/31): 「썸네일 보여줄 것 있으면 콘텐츠 맨 우측에」.
      지어내지 않는다. 그 페이지가 실제로 가진 첫 이미지만 쓴다.
    """
    import hubgen
    p = os.path.join(hubgen.VAULT, page)
    if not os.path.isfile(p):
        return ''
    try:
        t = io.open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''
    m = re.search(r'<img[^>]+src="(assets/[^"]+\.(?:png|jpg|jpeg|webp|svg))"', t)
    if not m:
        return ''
    return '<span class="eth3"><img src="%s" alt="" loading="lazy"></span>' % m.group(1)


def num_in(s):
    m = re.search(r'(\d+(?:\.\d+)?\s*(?:%|초|종|개|배|시간|fps))', s or '')
    return m.group(1) if m else ''


# ── 칩 상한 ─────────────────────────────────────────────────────────
# ★ 2026-09-03 신설 (foothold-lab#156). 라벨은 전체 수를 적는데 목록은 상한까지만
#   그리면, 화면이 «8» 이라 말하고 «6» 을 보여준다. 상한에 걸린 항목은 아무
#   흔적 없이 사라진다 (커널 원칙 2 · 조용한 실패).
#
#   실측 2026-09-03 배포본: 연구 허브 출발선이 「후속 과제 8」 옆에 칩 6개였고
#   떨어진 둘이 #66 rails · #65 gap 이었다. 하필 아직 안 풀린 험지 둘이다.
#
#   고치는 법은 상한을 없애는 것이 아니다. 이슈가 서른 개 걸린 문서에서 카드가
#   무너진다. 상한을 이름 있는 값으로 올려 두고, 넘으면 «남은 수를 말하는 칩» 을
#   붙여 전체 목록으로 보낸다. 잘린 것이 화면에서 자기 존재를 주장한다.
CHIP_MAX = 12

LAB_ISSUES = 'https://github.com/foothold-project/foothold-lab/issues'


def _q(s):
    import urllib.parse
    return urllib.parse.quote(str(s), safe='')


def issue_search(*terms):
    """열린 이슈를 그 낱말로 찾는 주소. 「외 N건」 칩이 여기로 보낸다."""
    return '%s?q=%s' % (LAB_ISSUES,
                        '+'.join(['is%3Aissue', 'is%3Aopen']
                                 + [_q(t) for t in terms if t]))


def more_chip(total, drawn, href, cls='fk3'):
    """상한에 걸려 안 그린 수를 «말하는» 칩. 안 걸렸으면 빈 문자열.

    ★ 답을 아는 입력 (`_kat`): total=8 drawn=8 이면 '' 이어야 하고,
      total=20 drawn=12 이면 「외 8건」 이어야 한다. 여기가 틀리면 화면이
      다시 조용히 거짓말한다.
    """
    left = int(total) - int(drawn)
    if left <= 0:
        return ''
    return ('<a class="%s more" href="%s" target="_blank" rel="noopener">'
            '<b>외 %d건</b></a>' % (cls, href, left))


# ── 멘토링 ──────────────────────────────────────────────────────────
# ★ 팀장 확정 2026-09-01. 이번 주부터 고정 일정.
#   조선대  금요일 14:00~18:00
#   박철제  월 · 수요일 15:00~18:00 (운영진과 협의 중 · 우리 쪽 확정치)
#   weekday(): 월0 화1 수2 목3 금4
MENTORS = [
    ('조선대', 'mentor:조선대', (4,), '금 14~18'),
    ('박철제', 'mentor:박철제', (0, 2), '월·수 15~18'),
]

# ★ 관문과 멘토링이 같은 날 겹치면 화면에서 말해 준다 (팀장 확정 9/1).
#   9/4 은 오전에 기획발표, 오후 14~18 에 조선대 멘토링이다. 날짜만 보고
#   「그날은 발표만 있다」고 생각하면 오후 일정을 놓친다.
CLASH = {'2026-09-04': '오전 기획발표 · 오후 조선대 멘토링. 같은 날이다'}


def _labels(it):
    return {l.get('name', '') for l in (it.get('labels') or [])}


def _next_day(today, days):
    """오늘 기준 가장 가까운 해당 요일까지 남은 날. 오늘이면 0."""
    return min((d - today.weekday()) % 7 for d in days)


def _wd_attr(days):
    """MENTORS 의 요일을 브라우저로 실어 보내는 자리. 유일한 원본은 그 표다."""
    return ','.join(str(int(d)) for d in sorted(days))


def _clashes_of(days):
    """이 멘토의 요일에 걸린 겹침 안내만 [(날짜, 문구)] 로. 요일이 다르면 뺀다."""
    import datetime
    out = []
    for day in sorted(CLASH):
        d = datetime.date(*[int(x) for x in day.split('-')])
        if d.weekday() in days:
            out.append((day, CLASH[day]))
    return out


# ★ 2026-09-03 신설 (foothold-lab#155). 멘토링 D-day 가 빌드 순간의 숫자로
#   굳어 있었다. 같은 페이지의 관문(기획발표 · MVP · FINAL)은 `dd-live` 로
#   브라우저가 다시 세는데, 멘토링만 그 배선이 없었다.
#
#   그것이 왜 사고인가. `foothold-site` 에는 예약 빌드가 없다. 사람이 다시
#   올릴 때까지 화면은 「D-1」 에서 멈춘다. 9/4 가 지나도 D-1 이고, 다음 주
#   금요일 회차는 영영 안 잡힌다. 매주 반복하는 일정에 «마감 날짜» 를 하나
#   구워 넣은 것이 애초에 틀린 모양이었다.
#
#   ★ 요일을 이 스크립트에 박지 않는다. MENTORS 표가 data-wd 로 실어 보낸
#     것만 읽는다. 요일이 바뀌면 표 한 곳만 고친다 (커널 철칙 4).
#   ★ 겹침 안내도 함께 살린다. D-day 만 살리고 안내를 굳혀 두면 9/5 에
#     「D-6」 옆에 「같은 날이다」가 남는다. 고치면서 새 거짓말을 심는 꼴이다.
MENTOR_JS = """<script id="mentor-dday">
(function(){
  /* 매주 반복이라 마감 «날짜» 가 없다. 요일이 데이터다.
     값이 바뀌는 자리는 KST 자정 하나뿐이라 달력 «날짜» 의 일련번호로 센다.
     (관문 dd-live 가 2026-09-03 에 밀리초 floor 로 하루를 잃은 것과 같은 함정) */
  function kday(){ return Math.floor((Date.now()+9*3600000)/86400000); }
  function kwd(d){ return ((d+3)%7+7)%7; }   /* 1970-01-01 = 목 = 3 · 월 화 수 목 금 토 일 순서로 0 부터 6 */
  function iso(d){ return new Date(d*86400000).toISOString().slice(0,10); }
  function gap(el,t){
    var raw=(el.getAttribute('data-wd')||'').split(','), best=-1, i, w, g;
    for(i=0;i<raw.length;i++){
      w=parseInt(raw[i],10); if(isNaN(w)) continue;
      g=((w-kwd(t))%7+7)%7;
      if(best<0||g<best) best=g;
    }
    return best;
  }
  function tick(){
    var t=kday(), i, g, els;
    els=document.querySelectorAll('.mdd');
    for(i=0;i<els.length;i++){
      g=gap(els[i],t); if(g<0) continue;
      els[i].textContent = g===0 ? '오늘' : ('D-'+g);
    }
    els=document.querySelectorAll('.mclash');
    for(i=0;i<els.length;i++){
      g=gap(els[i],t);
      els[i].hidden = (g<0) || (iso(t+g)!==els[i].getAttribute('data-on'));
    }
  }
  function start(){ tick(); setInterval(tick,1000); }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',start);
  }else{ start(); }
})();
</script>"""


def _mentoring_card():
    """멘토별 D-day + 그 멘토에게 물을 질문 (#96).

    ★ 9/1 실측으로 고친 것. 이전 판은 셋을 못 했다.
      ① 카드 제목이 «조선대» 로 하드코딩돼 박철제 멘토링이 아예 안 보였다
      ② D-day 를 금요일 하나로만 셌다
      ③ 템플릿 본문에 «(박철제 | 조선대)» 를 쓰게 해 놨는데 화면은 «제목» 만
         읽었다. 본문에 적은 구분이 화면에 도달하지 않는 구조였다
      -> 구분을 «라벨» 로 옮긴다. 팀원은 템플릿에서 라벨만 고르면 되고,
         화면은 라벨을 읽는다. 사람이 지키는 규칙 대신 기계가 읽는 자리로.

    ★ 9/3 실측으로 고친 것 (#155 · #156).
      ④ D-day 가 빌드 시점 값으로 굳어 다음 회차로 안 넘어갔다 -> `mdd` 로 살린다
      ⑤ 질문 목록이 상한 6 에 걸린 것을 조용히 버렸다 -> 「외 N건」 으로 말한다
    """
    import datetime
    today = buildtime.today()
    qs = [it for it in issues() if it['title'].startswith('[멘토링질문]')]
    out = []
    for name, lab, days, when in MENTORS:
        mine = [it for it in qs if lab in _labels(it)]
        dd = _next_day(today, days)
        wd = _wd_attr(days)
        body = ''.join(
            '<a class="w3p-q" href="https://github.com/foothold-project/'
            'foothold-lab/issues/%d">%s <i>#%d</i></a>'
            % (it['number'],
               esc(re.sub(r'^\[멘토링질문\]\s*', '', it['title'])[:30]),
               it['number'])
            for it in mine[:CHIP_MAX])
        # 상한에 걸린 질문도 자기 존재를 주장한다. 「모인 질문 N개」와 목록이
        # 서로 다른 수를 말하면 안 된다 (#156 과 같은 부류다).
        body += more_chip(len(mine), min(len(mine), CHIP_MAX),
                          issue_search('label:' + lab), cls='w3p-q')
        sub = ('모인 질문 %d개' % len(mine)) if mine else (
            '모인 질문 없음 · 이슈 템플릿 「멘토링 질문」 + 라벨 <code>%s</code>' % lab)
        out.append(
            '<div class="w3"><div class="w3h">%s 멘토링'
            '<span class="w3b mdd" data-wd="%s" style="border-color:var(--note);'
            'color:var(--note)">%s</span></div>'
            '<div class="w3sub">%s · %s</div>%s</div>'
            % (esc(name), wd, ('오늘' if dd == 0 else 'D-%d' % dd),
               esc(when), sub,
               ('<div class="w3p">%s</div>' % body) if body else ''))
        # 겹침 안내는 «다음 회차가 그 날일 때만» 선다. 판정은 브라우저가 한다.
        # 빌드 값도 같이 맞춰 둬서 스크립트가 없어도 대충은 맞게 보인다.
        for day, text in _clashes_of(days):
            on = (today + datetime.timedelta(days=dd)).isoformat() == day
            out.append(
                '<div class="w3sub mclash" data-wd="%s" data-on="%s"%s'
                ' style="color:var(--note)">%s</div>'
                % (wd, day, '' if on else ' hidden', esc(text)))
    # 라벨이 아직 안 붙은 질문은 떨어뜨리지 않고 따로 알린다 (조용한 실패 금지)
    tagged = {it['number'] for _n, l, _d, _w in MENTORS
              for it in qs if l in _labels(it)}
    orphan = [it for it in qs if it['number'] not in tagged]
    if orphan:
        out.append(
            '<div class="w3"><div class="w3h">멘토 미지정</div>'
            '<div class="w3sub">질문 %d개에 <code>mentor:</code> 라벨이 없다. '
            '어느 멘토에게 물을지 붙여야 위 목록에 선다</div></div>' % len(orphan))
    return ''.join(out) + MENTOR_JS


def week_section():
    """[주간] 이슈에서 이번 주 · 차주를 만든다. 유입: 제목의 W번호."""
    wk = {}
    for it in issues():
        m = re.match(r'\[주간\]\s*(W\d+)\s*(.+)', it['title'])
        if m:
            wk.setdefault(m.group(1), []).append((m.group(2).strip(), it))
    if not wk:
        return ('<div class="w3"><div class="w3h">이번 주</div>'
                '<div class="w3sub">주간 이슈를 못 읽었다. '
                '<a href="%s">프로젝트 보드</a>에서 확인.</div></div>' % BOARD)
    # ★ 팀장 정정 (8/31): 지난 주가 아니라 «차주» 다.
    #   「앞으로 차주에 뭘 집중하나」가 필요해서 만든 칸이다. 뒤를 보는 칸이 아니다.
    #   차주 이슈가 아직 없으면 «아직 안 열림» 을 말하고 만들 자리를 알려 준다.
    import datetime
    weeks = sorted(wk)
    cur = weeks[-1]
    nxt = 'W%d' % (int(cur[1:]) + 1)
    out = []
    for n, wknum in enumerate((cur, nxt)):
        if wknum not in wk:
            out.append(
                '<div class="w3 dim"><div class="w3h">차주 · %s</div>'
                '<div class="w3sub">아직 안 열렸다. 일요일에 이슈 템플릿 '
                '「주간 팀 목표」로 연다. 열리면 여기에 저절로 뜬다.'
                '<br><a href="https://github.com/foothold-project/foothold-lab/'
                'issues/new?template=weekly-team.md">지금 열기</a></div></div>'
                % wknum)
            continue
        team, people = None, []
        for rest, it in wk[wknum]:
            if rest.startswith('팀 목표'):
                team = (rest, it)
            else:
                people.append((rest.replace('개인 목표', '').strip(), it))
        label = '이번 주' if n == 0 else '차주'
        parts = ['<div class="w3%s"><div class="w3h">%s · %s'
                 '<a class="w3b" href="%s">프로젝트 보드</a></div>'
                 % ('' if n == 0 else ' dim', label, wknum, BOARD)]
        if team:
            goals = re.findall(r'^\|\s*\d+\s*\|\s*\*{0,2}([^|*]+)',
                               team[1]['body'], re.M)
            done = len(re.findall(r'- \[x\]', team[1]['body']))
            todo = len(re.findall(r'- \[ \]', team[1]['body']))
            parts.append(
                '<a class="w3t" href="https://github.com/foothold-project/'
                'foothold-lab/issues/%d"><b>%s</b><span>%s</span>'
                '<span class="w3done">끝났다는 기준 %d / %d</span></a>'
                % (team[1]['number'], esc(team[0]),
                   esc(' · '.join(g.strip() for g in goals[:3]))
                   + (' 외 %d' % (len(goals) - 3) if len(goals) > 3 else ''),
                   done, done + todo))
        if people:
            parts.append('<div class="w3p">%s</div>' % ''.join(
                '<a href="https://github.com/foothold-project/foothold-lab/'
                'issues/%d">%s <i>#%d</i></a>' % (it['number'], esc(nm),
                                                  it['number'])
                for nm, it in sorted(people)))
        parts.append('</div>')
        out.append(''.join(parts))
    return '<div class="wks">%s</div>' % ''.join(out)


def schedule_html(site):
    import deliverables_page as dlv
    rows = dlv.build_rows(lab(), dlv.today_kst())
    out = [week_section(), _mentoring_card(), '<div class="g3s">']
    for name, due, note, dday, items in rows:
        if dday < 0:
            continue
        chips = []
        for label, state, _dod, rel in items:
            m = meta(os.path.join(lab(), *rel.split('/')))
            own = (m.get('담당') or '').split('·')[0].strip()
            slug = rel.rsplit('/', 1)[-1][:-3]
            cls = {'초안': 'draft', '검토중': 'draft', '확정': 'done'}.get(state, 'wait')
            chips.append(
                '<a class="c3 %s" href="deliverable-%s.html"><b>%s</b>%s'
                '<span>%s</span></a>'
                % (cls, slug, esc(label),
                   ('<i>%s</i>' % esc(own)) if own else '', esc(state)))
        st = {}
        for _l, s, _d, _r in items:
            st[s] = st.get(s, 0) + 1
        tally = (('%d장 전부 %s' % (len(items), list(st)[0]))
                 if len(st) == 1 and items else
                 ' · '.join('%s %d' % kv for kv in st.items()) or '걸린 문서 없음')
        out.append(
            '<div class="g3%s"><div class="g3l"><span class="g3d">D-%d</span>'
            '<span class="g3n">%s</span><span class="g3u">%d월 %d일</span></div>'
            '<div class="g3r"><div class="g3t">%s</div>'
            '<div class="chips3">%s</div></div></div>'
            % (' near' if dday <= 7 else '', dday, esc(name),
               due.month, due.day, esc(tally), ''.join(chips)))
    out.append('</div>')
    # ★ 팀장 지적 (8/31): 「더 깊이」가 너무 작아 안 보인다. 카드로 올린다.
    deep = [('산출물 현황', '제출 산출물 · 상태 한눈에', 'deliverables.html'),
            ('진행 현황', '올린 것이 지금 어디 있나', 'ledger.html'),
            ('WBS', '3층 분해 · 계획율과 완료율', 'deliverable-wbs.html'),
            ('개인 계획', '팀원이 스스로 세운 것', 'personal-plans.html'),
            ('프로젝트 설계도', '흐름 · 퀘스트 · 결정 안건', 'plan.html'),
            ('진행일지', '무엇을 언제 했는가', 'deliverable-progress-log.html'),
            ('멘토링 일지', '무엇을 받았고 무엇을 반영했나',
             'deliverable-mentoring-log.html')]
    out.append('<div class="eh3">관련 문서 <span>%d</span></div>'
               '<div class="deep3">%s</div>'
               % (len(deep), ''.join(
                   '<a class="dp3" href="%s"><b>%s</b><span>%s</span></a>'
                   % (h, t, d) for t, d, h in deep)))
    return ''.join(out)


# ── 연구 ────────────────────────────────────────────────────────────
def _research_docs():
    """(rel, meta, page, 관계) 목록. 게시된 것만."""
    import mdlinks
    out = []
    root = os.path.join(lab(), 'docs', 'research')
    for f in sorted(os.listdir(root) if os.path.isdir(root) else []):
        if not f.endswith('.md'):
            continue
        rel = 'research/' + f
        page = mdlinks.resolve('docs/' + rel)
        if not page:
            continue
        out.append((rel, meta(os.path.join(root, f)), page,
                    graph().get(rel) or {}))
    return out


def _mentions(page, mdname):
    """이 문서의 주소나 파일명을 본문에 적은 열린 이슈들. «후속 과제» 가 아니다.

    ★ 팀장 지적 2026-09-04: 이름과 동작이 달랐다. 이 함수는 후속 과제를 고르지
      않는다. 참고 링크로 주소를 적기만 해도 걸린다. 실제로 #123(공개 문서 금액
      표기)과 #100(평가 지표)이 그렇게 걸려, 실측의 후속인 양 화면에 섰다.
      그래서 출발선 카드의 「후속 과제」 칩 줄을 통째로 없앴다. 이 실측의 후속은
      바로 아래 험지 표가 정본이고, 거기 다섯 지형이 단계별로 서 있다.
      남은 쓰임은 하나다. **어느 실측을 출발선으로 세울지 고르는 점수.**
      이 목록을 화면에 그대로 내는 코드를 다시 만들지 말 것.

    ★ 이슈는 배포 주소로 링크하는데 Vercel cleanUrls 라 `.html` 이 없다
      (실측: #69 가 `/research-generalization-benchmark-10-terrains` 로 링크).
      확장자를 뗀 이름으로 맞춘다.
    """
    stem = page[:-5] if page.endswith('.html') else page
    hit = []
    for it in issues():
        body = (it.get('body') or '') + ' ' + it['title']
        if stem in body or mdname in body:
            hit.append(it)
    return hit


def _tk_by(it):
    """칸·칩 아래 줄: «문서 · 작성자 · YYYY-MM-DD HH:MM».

    ★ 팀장 지적 2026-09-04: 같은 페이지에서 「본 PoC」 는 「오흥재 · 2026-08-09 14:19」
      인데 험지 칩은 「문서 · 09-03」 뿐이었다. 한 화면에 형식이 둘이면 어느 쪽이
      기준인지 알 수 없다. 여기를 긴 쪽에 맞춘다.
      작성자 · 시각은 문서 머리말 «작성:» 에서, 코멘트는 GitHub 작성자와 작성 시각
      (KST 로 맞춘 것)에서 온다. 둘 다 terrain5 가 채워 온다.
    """
    bits = [it['kind']]
    if it.get('who'):
        bits.append(it['who'])
    if it.get('when'):
        bits.append(it['when'] + ('(커밋)' if it.get('whence') == '커밋' else ''))
    return ' · '.join(bits)


def _tk_link(it, cut=44):
    """칸 안의 문서 · 코멘트 한 줄. 전체 제목은 title 속성에 남긴다."""
    return ('<a href="%s" title="%s"><b>%s</b><i>%s</i></a>'
            % (esc(it['href']), esc(it['title']), esc(it['title'][:cut]),
               esc(_tk_by(it))))


def _tk_short(title, cut=34):
    """칩에 들어갈 짧은 제목. 끝 괄호를 떼고, 앞 절이 충분히 길면 ':' 앞까지.
    출발선 칩과 같은 규칙(태그 제거 -> 첫 ':' 앞)이다. 날짜 중간에서 잘리지 않는다."""
    t = re.sub(r'\s*\([^()]*\)\s*$', '', title or '').strip()
    head = t.split(':')[0].strip()
    if len(head) >= 6:
        t = head
    return t[:cut]


def _tk_chip(it, where):
    """카드 아래 줄의 칩. fk3 부품 그대로. span 은 어느 카드의 것인지."""
    return ('<a class="fk3 tkp3" href="%s" title="%s"><b>%s</b><span>%s</span>'
            '<i>%s</i></a>'
            % (esc(it['href']), esc(it['title']), esc(_tk_short(it['title'])),
               esc(where), esc(_tk_by(it))))


# 한 칸에 보일 문서 수의 상한. 넘으면 「외 N건」 칩이 이슈로 보낸다.
# 조용히 자르지 않는다 (#156 과 같은 부류 · 관문 [3.47] 이 data-n 으로 센다).
CELL_MAX = 3


def _tk_cell(stage, items, href):
    """표 한 칸. «진단» 열의 rails 칸 같은 것.

    셋까지 보이고 넘으면 「외 N건」 이 그 지형 이슈로 보낸다. 적은 수(data-n)와
    그린 수가 어긋나면 관문 [3.47] 이 배포를 세운다 (chipcheck PAIRS).
    빈 칸도 자리를 지킨다. 비어 있다는 것이 «진단은 다 찼는데 레시피는 비었다» 를
    가로로 읽히게 하는 정보다.
    """
    shown = items[:CELL_MAX]
    body = ''.join(_tk_link(it) for it in shown)
    body += more_chip(len(items), len(shown), href, cls='tkmr3')
    # 빈 칸은 비었다고 «말한다». 점선만 남기면 무엇이 들어올 자리인지 알 수 없다.
    # 일정 페이지의 「모인 질문 없음 · 이슈 템플릿 …」 과 같은 뜻이다.
    if not items:
        body = '<span class="tke3">아직 없다</span>'
    return ('<div class="tkc3%s" data-n="%d"><i>%s</i>%s</div>'
            % (' on' if items else '', len(items), stage, body))


def _tk_kat():
    """★ 답을 아는 입력. 칸이 조용히 자르지 않는지, 관문이 그것을 세는지 못 박는다.

    오늘 데이터는 어느 칸도 셋을 안 넘는다. 그래서 상한 경로는 실제 배포에서
    한 번도 안 돌고, 그대로 두면 «틀린 채로 아무 소리도 안 나는» 코드가 된다
    (커널 원칙 2). 여기서 일곱 개를 넣어 강제로 돌린다.
    """
    import chipcheck
    fake = [{'href': '#%d' % i, 'title': '문서 %d' % i, 'kind': '문서',
             'who': '오흥재', 'when': '2026-09-04 10:00'} for i in range(7)]
    three = _tk_cell('진단', fake[:3], 'ISSUE')
    if three.count('<a ') != 3 or '외 ' in three or 'data-n="3"' not in three:
        return False, '셋은 그대로 다 보여야 한다: %s' % three[:120]
    many = _tk_cell('진단', fake, 'ISSUE')
    if many.count('<a ') != 4 or '외 4건' not in many or 'data-n="7"' not in many:
        return False, '일곱이면 셋 + 「외 4건」 이어야 한다: %s' % many[:160]
    empty = _tk_cell('레시피', [], 'ISSUE')
    if '<a ' in empty or 'data-n="0"' not in empty or ' on"' in empty:
        return False, '빈 칸이 비어 보이지 않는다: %s' % empty[:120]
    # ★ 관문이 이 마크업을 실제로 세는가 (철칙 4: 규칙이 사는 자리를 다 센다).
    #   여기가 빠지면 chipcheck 는 통과를 찍으면서 이 절을 안 본다.
    for name, cell, said in (('셋', three, 3), ('일곱', many, 7),
                             ('빈 칸', empty, 0)):
        got = chipcheck.scan_text(cell, 'tk')
        if len(got) != 1:
            return False, '관문이 %s 칸을 짝으로 못 셌다 (PAIRS 를 보라)' % name
        _l, n, drawn, k, why = got[0]
        if why or n != said or drawn + k != said:
            return False, ('관문이 %s 칸을 %s 로 읽었다'
                           % (name, (n, drawn, k, why)))
    return True, ''


def terrain_html():
    """Track A · 실패 험지 5종 (foothold-lab#179). 자료 · 분류는 terrain5, 화면은 여기.

    행 다섯 = 지형, 열 넷 = 단계인 표다 (팀장 2026-09-04 · 5열 카드를 접었다).
    카드였을 때는 문서가 몰린 rails 의 키에 다섯이 전부 맞춰져, 빈 카드 넷이
    rails 만큼 세로로 늘어나 화면을 먹었다. 표는 세로 길이가 지형 수에만
    비례하고, 「진단은 다 찼는데 레시피는 비었다」 가 가로로 한 번에 읽힌다.

    행 머리 = 지형 이름(내부 key 병기) · 실패 양상 · 담당과 이슈 번호 · 실측 셋.
    실패형은 토큰 색으로만 가른다 (낙상형 --stop · 전진불능형 --note).
    순서는 그대로 뜻이다: 채운 칸이 많은 지형이 위. 좁은 화면에서는 지형별로
    접혀 행 머리 아래 네 칸이 2x2 로 선다.

    절 머리의 조건은 험지 실측의 것이다: 6초 · 통과선 3 m · 1.0 m/s · 방향 임계 1.5 m
    (lab sim/eval/results/20260903-rough10-1.0mps/README.md §5-1 · §10).
    20초 · 10 m 는 평지 기준선이지 험지가 아니다 (README §6).

    ★ 자기시험을 먼저 돌린다. 가짜 문서 셋이 엉뚱한 칸에 가거나, 칸이 조용히
      자르면 배포를 세운다.
    """
    import terrain5 as t5
    ok, why = t5.kat()
    if not ok:
        print('  [!] 험지 분류 자기시험 실패: %s. 배포를 중단합니다.' % why)
        sys.exit(1)
    ok, why = _tk_kat()
    if not ok:
        print('  [!] 험지 표 자기시험 실패: %s. 배포를 중단합니다.' % why)
        sys.exit(1)
    cards, common, notes = t5.build_cards(lab())
    # 같은 글이 여러 지형 칸에 반복되면 표가 「어느 지형이 얼마나 갔나」를 못 보여준다.
    # 2026-09-04 실측: 코멘트 하나가 다섯 행 전부에 글자까지 똑같이 들어가 행 높이를
    # 들쭉날쭉하게 만들고, 실제 진행(문서 둘)을 그 반복 밑에 묻었다.
    # 세 지형 이상에 걸린 것은 지형별 사정이 아니라 «전체 사정» 이므로 위로 올린다.
    seen = {}
    for c in cards:
        for s in t5.STAGES:
            for it in c['cells'][s]:
                seen.setdefault((s, it['title']), []).append(it)
    wide = {k: v for k, v in seen.items() if len(v) >= 3}
    for c in cards:
        for s in t5.STAGES:
            c['cells'][s] = [it for it in c['cells'][s]
                             if (s, it['title']) not in wide]
    wide_notes = ['%s · %s 칸 · %s' % (v[0]['title'], s,
                                       '다섯 지형 모두' if len(v) == len(cards)
                                       else '%d개 지형' % len(v))
                  for (s, _t), v in sorted(wide.items())]
    if len(cards) != len(t5.TERRAINS):
        print('  [!] 험지 행이 %d개다. 다섯이어야 한다.' % len(cards))
        sys.exit(1)

    # ★ 2026-09-13. 보드를 접는다. 다섯 칸 요약만 항상 보인다.
    #
    #   실측: 이 보드가 첫 문서 카드 위 1,263px 중 **601px** 을 먹고 있었다.
    #   절반이다. 그래서 「연구 허브에 왔는데 문서가 안 보인다」가 됐다.
    #
    #   없애지는 않는다. 이 보드는 팀의 주된 작업 단위다. 담당자가 자기
    #   지형을 찾는 길을 끊으면 안 된다. 그래서 **지형·담당·성적 다섯 칸은
    #   접혀도 보이고**, 칸을 누르면 그 행이 열린다.
    #
    #   접기는 `<details>` 로 한다. 자바스크립트가 없어도 열리고, 키보드와
    #   화면 낭독기가 그대로 쓴다. 직접 주소(`#terrain-gap`)와 뒤로 가기는
    #   아래 작은 스크립트가 맡는다.
    summary = []
    for c in cards:
        m = c['meas']
        summary.append(
            '<a class="tkpin3" href="#terrain-%s" data-tk="%s">'
            '<b>%s</b><span class="tkcm3">%s</span>'
            '<span class="tkco3">%s</span></a>'
            % (c['key'], c['key'], esc(c['ko']),
               ('%d%%' % m['success']) if m else '실측 없음',
               esc(c['owner'])))

    out = ['<div class="eh3">Track A · 실패 험지 5종 <span>행 = 지형 · 열 = 단계 · '
           '실측 = 6초 · 통과선 3 m · 1.0 m/s · <b>난이도 0.5</b> · 방향 임계 1.5 m · 지형당 100판'
           '</span></div>',
           '<div class="tkcs3">%s</div>' % ''.join(summary),
           '<details class="tkd3" id="terrain-board"><summary class="tkds3">'
           '지형별 진행 보드 <span>진단 · 설계 · 레시피 · 결과</span></summary>',
           '<p class="tkl3">칸은 이슈에 달린 문서와 코멘트가 채운다. 머리말에 '
           '「단계: 진단」 처럼 적으면 그 칸, 없으면 제목의 낱말로 고른다(「가설」은 '
           '설계). 한 칸에 셋까지 보이고 넘으면 「외 N건」. 어느 칸에도 못 간 것은 '
           '아래 「미분류」에 그대로 있다. 채운 칸이 많은 지형이 위다.</p>',
           # ★ 2026-09-14 신설. 수치가 «어디서 온 것인가» 를 화면에 적는다.
           #   보드가 2026-09-03(평가 규격 1) CSV 를 읽고 있었는데 그 사실이
           #   화면 어디에도 없었다. 그래서 같은 허브 안에서 보드와 문서의
           #   숫자가 갈렸는데도 오래 안 들켰다. 출처를 코드에서 뽑아 적으면
           #   다음에 자리를 옮겨도 설명이 따라온다.
           '<p class="tkl3">아래 성공률 · 생존율 · 전진 평균은 <b>%s</b> 에서 '
           '읽는다. 정본 조건은 난이도 0.5 · 1.0 m/s · 지형마다 100 에피소드다 '
           '(<a href="research-20260911-eval-protocol-v2.html">평가 프로토콜 v2</a>).'
           '</p>' % esc(t5.CSV_REL.replace(os.sep, '/'))]
    for w in notes:
        out.append('<div class="tkx3">%s</div>' % esc(w))
    for w in wide_notes:
        out.append('<div class="tkall3">%s</div>' % esc(w))
    out.append('<div class="tkw3"><div class="tks3">'
               '<div class="tkhh3">지형</div>'
               + ''.join('<div class="tkhs3">%s</div>' % s for s in t5.STAGES))
    for c in cards:
        m = c['meas']
        meas = (('<span><b>%d</b><i>%% 성공</i></span>'
                 '<span><b>%d</b><i>%% 생존</i></span>'
                 '<span><b>%.2f</b><i>m 전진 평균</i></span>')
                % (m['success'], m['survival'], m['progress'])
                if m else '<span class="tkx3">실측 없음</span>')
        # 행 머리는 두 줄이다. «이름 · 실패 양상 · 담당과 이슈» / «실측 셋».
        # 넷을 각자 제 줄에 세웠더니 행 머리가 140px 이 됐고(실측 2026-09-04),
        # 문서 하나뿐인 행 넷이 그 키를 따라갔다. 표로 바꾼 뜻이 거기서 사라진다.
        out.append(
            '<div class="tkrow3 %s" id="terrain-%s"><div class="tkr3">'
            '<div class="tkn3"><b class="tkt3">%s <i>(%s)</i></b>'
            '<u class="tkf3">%s</u>'
            '<a class="tko3" href="%s">#%d · %s%s</a></div>'
            '<div class="tkm3">%s</div>%s'
            '</div>%s</div>'
            % ('fall' if c['mode'] == '낙상형' else 'stall', c['key'],
               c['key'], esc(c['ko']), c['mode'], esc(c['url']), c['no'],
               esc(c['owner']), ' · 닫힘' if c['state'] == 'CLOSED' else '',
               meas,
               # 단서는 있는 지형에만 붙는다. 지금은 floating_ring 하나다.
               ('<div class="tkq3">%s</div>' % esc(c['note'])
                if c.get('note') else ''),
               ''.join(_tk_cell(s, c['cells'][s], c['url']) for s in t5.STAGES)))
    out.append('</div></div>')

    # 표 아래 두 줄. 「공통」 = 다섯 지형 전부에 붙는 문서(계획 정본 같은 것).
    # 「미분류」 = 행은 정해졌는데 칸을 못 정한 문서 · 코멘트.
    chips = [_tk_chip(d, '공통') for d in common]
    out.append('<div class="hk3b">공통 %d</div>' % len(chips)
               + ('<div class="fks3">%s</div>' % ''.join(chips) if chips
                  else '<div class="tkl3">지금은 없다</div>'))
    # 미분류는 «아직 칸을 못 정한 것» 이다. 없으면 절 자체를 안 낸다 (팀장 2026-09-04).
    # 「지금은 없다」 한 줄이 남아 있으면 빈 서랍이 화면을 차지한다.
    chips = [_tk_chip(it, c['ko']) for c in cards for it in c['loose']]
    if chips:
        out.append('<div class="hk3b">미분류 %d</div>'
                   '<div class="fks3">%s</div>' % (len(chips), ''.join(chips)))

    # 접기 닫기. 「공통」·「미분류」도 보드 안이다. 접힌 상태에서도 건수는
    # 요약 줄이 아니라 여기 그대로 있고, 열면 「외 N건」까지 그대로 나온다.
    out.append('</details>')

    # 직접 진입과 뒤로 가기. 자바스크립트가 없어도 페이지는 그대로 읽힌다.
    #   · 주소에 `#terrain-gap` 이 있으면 보드를 열고 그 행으로 간다
    #   · 다섯 칸 중 하나를 누르면 열고, 주소를 남긴다 (뒤로 가면 돌아온다)
    #   · 보드를 손으로 열고 닫은 것은 주소를 더럽히지 않게 replaceState 로만
    out.append(
        '<script>(function(){'
        'var b=document.getElementById("terrain-board");if(!b)return;'
        'function open(id){b.open=true;'
        'var r=id&&document.getElementById(id);'
        'if(r){r.classList.add("tkhit3");'
        'setTimeout(function(){r.scrollIntoView({block:"center"});},30);'
        'setTimeout(function(){r.classList.remove("tkhit3");},2400);}}'
        'function fromHash(){var h=location.hash.slice(1);'
        'if(h&&h.indexOf("terrain-")===0)open(h);}'
        'fromHash();window.addEventListener("hashchange",fromHash);'
        'Array.prototype.forEach.call('
        'document.querySelectorAll(".tkpin3[data-tk]"),function(a){'
        'a.addEventListener("click",function(e){e.preventDefault();'
        'var id="terrain-"+a.getAttribute("data-tk");'
        'history.pushState(null,"","#"+id);open(id);});});'
        'b.addEventListener("toggle",function(){'
        # 지형 칸을 눌러 온 것이면 그 주소를 «덮지 않는다». 덮으면
        # `#terrain-gap` 이 `#terrain-board` 가 되어 공유한 주소가
        # 엉뚱한 데로 간다 (실측: 눌러 보고 잡았다).
        'if(location.hash.indexOf("#terrain-")===0'
        '&&location.hash!=="#terrain-board")return;'
        'try{history.replaceState(null,"",'
        'b.open?location.pathname+location.search+"#terrain-board"'
        ':location.pathname+location.search);}catch(e){}});'
        '}());</script>')
    return ''.join(out)


def catalog():
    """연구 원장. 사람이 내린 판단과 배포 사실이 여기 있다.

    2026-09-13 에 네 군데 흩어진 것을 모았다 (`tools/build_research_catalog.py`).
    없으면 빈 것을 준다. **없다고 빌드를 죽이지 않는다** 다른 기기·옛
    체크아웃에서도 페이지는 나와야 한다. 대신 그 자리를 «비운다».
    """
    root = lab()
    if not root:
        return {}
    p = os.path.join(root, 'docs', 'ops', 'research-catalog.json')
    if not os.path.isfile(p):
        return {}
    try:
        d = json.load(io.open(p, encoding='utf-8'))
    except Exception as e:
        print('  [!] 연구 원장을 못 읽었습니다: %s' % e)
        return {}
    return _with_live_doors(d, root)


def _with_live_doors(d, root):
    """원장의 입구 배정을 «지금 폴더에 있는 문서» 기준으로 다시 채운다.

    ★ 2026-09-14. 여기가 승격 사슬의 마지막 끊긴 칸이었다.

      팀장이 `[승격 검토]` 이슈에 `/승격` 한 마디를 치면 워크플로가 문서를
      `docs/research/` 로 옮긴다. 거기까지는 자동이다. 그런데 허브가 입구를
      읽는 곳은 **커밋된 `research-catalog.json`** 이고, 그 파일은 빌드가
      다시 만들지 않는다. 그래서 옮겨진 문서는 어느 입구에도 안 들어가고,
      **팀원에게는 「PR 머지됐는데 웹에 없다」로 보인다.**

      원장 생성기를 손으로 돌려야만 이어졌다. 사람을 관문으로 쓴 것이다.

    규칙은 **한 곳에만** 둔다. `door_of` 를 여기에 베껴 쓰면 두 자리가 되고,
    그 부류로 이미 네 번 당했다 (md2site/docs_pages · ia.HUBS/gnav · eg3/eh3 ·
    docs assets/web assets). 그래서 생성기 모듈을 **불러다 쓴다.**

    못 불러오면 조용히 원장 그대로 쓴다. 다른 기기·옛 체크아웃에서도 페이지는
    나와야 한다.
    """
    tools = os.path.join(root, 'tools')
    if not os.path.isdir(tools):
        return d
    if tools not in sys.path:
        sys.path.insert(0, tools)
    try:
        import build_research_catalog as _brc
        live, auto = _brc.resolved_functions()
    except Exception as e:
        print('  [!] 입구 자동 배정을 못 돌렸습니다 (원장 그대로 씁니다): %s'
              % str(e)[:70])
        return d
    old = d.get('function') or {}
    if live != old:
        added = sorted(set(live) - set(old))
        moved = sorted(k for k in live if k in old and live[k] != old[k])
        gone = sorted(set(old) - set(live))
        bits = []
        if added:
            bits.append('새로 %d건(%s)' % (len(added), ' · '.join(added[:3])))
        if moved:
            bits.append('바뀜 %d건' % len(moved))
        if gone:
            bits.append('사라짐 %d건' % len(gone))
        print('  원장 입구 배정이 지금과 다릅니다 · %s' % ' · '.join(bits))
        print('    화면에는 지금 것을 씁니다. 원장 파일도 맞추려면:')
        print('    python tools/build_research_catalog.py --write')
    d = dict(d)
    d['function'] = live
    return d


def _fn_of(rel):
    """문서 경로 -> 입구 열쇠. 원장이 정한다. 없으면 빈 문자열."""
    name = rel.rsplit('/', 1)[-1]
    if name.endswith('.md'):
        name = name[:-3]
    return (catalog().get('function') or {}).get(name, '')


def _doors(docs, skip=()):
    """목업의 둘째 영역 · 여섯 입구.

    「이런 글은 어디서 찾지」의 답이다. 누르면 **목록에 거르개가 걸린다** ·
    다른 쪽으로 보내지 않는다. 큰 카드 여섯이 아니라 짧은 단추다. 크게
    만들면 그만큼 첫 문서 카드가 밀린다 (실측: 얹기만 해도 PC +128px).

    건수는 **지금 화면에 있는 문서로 센다.** 원장에 배정이 있어도 그 문서가
    허브에 안 나오면 0 이다. 안 그러면 눌렀는데 빈 목록이 나온다.
    """
    cat = catalog()
    groups = cat.get('groups') or []
    fn = cat.get('function') or {}
    if not groups:
        return ''

    # ★ 2026-09-13. 목록에 «카드로 나오는 것» 만 센다.
    #   출발선 문서는 위 카드로 따로 서고 목록에는 안 들어간다. 그것까지
    #   세면 「결과 보고 7」인데 눌러서 6장이 나온다. 건수가 거짓말을 한다.
    skip = set(skip)
    here = {}
    for rel, _m, _page, _g in docs:
        if rel in skip:
            continue
        key = _fn_of(rel)
        if key:
            here[key] = here.get(key, 0) + 1

    out = []
    for g in groups:
        n = here.get(g['key'], 0)
        out.append('<a href="?fn=%s" data-fn="%s"><span class="dnm3">%s</span>'
                   '<span class="dex3">%s</span><span class="dct3">%d</span></a>'
                   % (esc(g['key']), esc(g['key']), esc(g['name']),
                      esc(g.get('hint') or ''), n))
    # 거르개. **자바스크립트가 없어도 목록은 그대로 다 보인다.**
    # 숨기는 일만 스크립트가 한다. 안 돌면 «전부 보임» 이지 «빈 화면» 이 아니다.
    #
    #   · 같은 축 안에서는 여러 개를 고를 수 있다 (OR)
    #   · 주소에 남긴다 `?fn=diagnosis,plan` · 뒤로 가면 돌아온다
    #   · 걸러서 비면 «없다» 고 말하고 해제 단추를 준다. 목록을 숨기지 않는다
    #   · 묶음 제목의 건수도 함께 줄인다. 안 그러면 「진단 8」인데 3장만 보인다
    js = (
        '<script>(function(){function go(){'
        'var N=document.querySelector(".dr3");if(!N)return;'
        'var cards=[].slice.call(document.querySelectorAll(".ev3[data-fn]"));'
        'var groups=[].slice.call('
        'document.querySelectorAll("[data-label]"));'
        'var empty=document.createElement("div");'
        'empty.className="dnone3";empty.hidden=true;'
        'empty.appendChild(document.createTextNode('
        '"이 조건에 맞는 문서가 없습니다. "));'
        'var clr=document.createElement("button");clr.type="button";'
        'clr.className="dclr3";clr.textContent="전체 보기";'
        'empty.appendChild(clr);'
        'N.parentNode.insertBefore(empty,N.nextSibling);'
        'function sel(){var q=new URLSearchParams(location.search).get("fn");'
        'return q?q.split(",").filter(Boolean):[];}'
        'function apply(push){var s=sel();var on=s.length>0;var shown=0;'
        'cards.forEach(function(c){'
        'var hit=!on||s.indexOf(c.getAttribute("data-fn"))>=0;'
        'c.hidden=!hit;if(hit)shown++;});'
        'groups.forEach(function(g){var box=g.nextElementSibling;'
        'if(!box)return;var vis=[].slice.call(box.querySelectorAll(".ev3"))'
        '.filter(function(c){return !c.hidden;}).length;'
        'g.hidden=vis===0;box.hidden=vis===0;'
        'var t=g.getAttribute("data-label");'
        'if(t!==null)g.textContent=t+" "+vis;});'
        'empty.hidden=shown>0;'
        '[].slice.call(N.querySelectorAll("a[data-fn]")).forEach(function(a){'
        'a.setAttribute("aria-pressed",s.indexOf(a.getAttribute("data-fn"))>=0'
        '?"true":"false");});'
        'if(push){var u=location.pathname+(s.length?"?fn="+s.join(","):"");'
        'history.pushState(null,"",u);}}'
        'N.addEventListener("click",function(e){'
        'var a=e.target.closest?e.target.closest("a[data-fn]"):null;'
        'if(!a)return;e.preventDefault();'
        'var k=a.getAttribute("data-fn"),s=sel(),i=s.indexOf(k);'
        'if(i>=0)s.splice(i,1);else s.push(k);'
        'var u=location.pathname+(s.length?"?fn="+s.join(","):"");'
        'history.pushState(null,"",u);apply(false);});'
        'empty.addEventListener("click",function(e){'
        'if(!e.target.classList.contains("dclr3"))return;'
        'history.pushState(null,"",location.pathname);apply(false);});'
        'window.addEventListener("popstate",function(){apply(false);});'
        'apply(false);}'
        # ★ 문서 목록은 이 스크립트 «뒤» 에 온다. 바로 돌면 카드가 0장이라
        #   「이 조건에 맞는 문서가 없습니다」가 아무것도 안 걸렀는데 뜬다.
        #   실측: 화면을 찍어 보고 잡았다. 문자열 검사로는 안 잡혔다.
        'if(document.readyState==="loading")'
        'document.addEventListener("DOMContentLoaded",go);else go();'
        '}());</script>')
    # ★ `<nav>` 로 쓰면 안 된다. 전역 규칙 하나가 이렇게 걸려 있다.
    #
    #     nav:not(.gnav), aside { height: calc(100vh - var(--navh)) !important }
    #
    #   그래서 이 여섯 단추가 «화면 높이만큼» 늘어났다 (실측: 입구 하나가
    #   1,273px · 첫 문서 카드가 561 -> 3,404 로 밀렸다). `!important` 라
    #   내 규칙으로는 못 이긴다. 태그를 바꾸는 것이 맞다.
    #   길잡이 구실은 `role`+`aria-label` 로 남긴다.
    return ('<div class="eh3">무엇을 찾으시나요 <span>누르면 아래 목록이 '
            '걸러진다</span></div>'
            '<div class="dr3" role="navigation" aria-label="문서 분류">%s</div>%s'
            % (''.join(out), js))


def _release_block():
    """목업의 첫 영역 · 「지금 어디까지 왔나」.

    들어온 사람이 **맨 처음 보는 것**이다. 이 프로젝트가 무엇을 이뤘는지를
    한 덩이로 말한다. 출발선(그때의 문제)은 바로 아래 붙는다.

    **수치를 여기 손으로 적지 않는다.** 원장이 원자료에서 계산한 것을 읽는다
    (`tools/build_research_catalog.py` 의 `measure_release`). 손으로 적으면
    다음 배포에 반드시 낡고, 낡아도 아무도 모른다.

    원장이 없거나 수치가 없으면 **그 칸을 안 그린다.** 빈 칸이나 「미정」을
    그리면 그것이 사실처럼 읽힌다.
    """
    rels = (catalog().get('releases') or [])
    if not rels:
        return ''
    r = rels[-1]
    s = r.get('summary') or {}
    un, kn = s.get('unseen'), s.get('known')
    if not un:
        return ''

    when = (r.get('evaluated_at') or '')[:10]
    cond = '난이도 %s · %s m/s · 칸당 %d판' % (
        s.get('difficulty', '?'), s.get('speed_mps', '?'),
        s.get('episodes_per_cell', 100))

    # 한 문장. 두 무리를 한 번에 말한다.
    lead = ('미경험 험지 <b>%d종</b>에서 기준선보다 <b>%.1f %%p</b> 높습니다.'
            % (un['terrains'], un['delta_pp']))
    if kn:
        lead += (' 기존 험지 %d종은 <b>%d종 전부</b> 기준선 이상입니다.'
                 % (kn['terrains'], kn['at_or_above']))

    cells = [('미경험 %d종 · 종합' % un['terrains'],
              '%.0f <i>→</i> %.0f<i>%%</i>' % (un['baseline_pct'], un['main_pct']),
              cond)]
    if kn:
        cells.append(('기존 %d종 · 종합' % kn['terrains'],
                      '%.0f <i>→</i> %.0f<i>%%</i>' % (kn['baseline_pct'], kn['main_pct']),
                      '같은 조건 · %d칸' % kn['terrains']))
    if s.get('scorecard_episodes'):
        cells.append(('성적표 표본',
                      '%s<i>판</i>' % format(s['scorecard_episodes'], ','),
                      '한 칸의 분모는 %d판이다' % s.get('episodes_per_cell', 100)))
    if r.get('clips'):
        cells.append(('평가 영상', '%d<i>컷</i>' % r['clips'],
                      '평가 칸 %d개 전부' % (r.get('evaluations') or r['clips'])))

    grid = ''.join(
        '<div class="rv3"><div class="rvk3">%s</div>'
        '<div class="rvn3">%s</div><div class="rvs3">%s</div></div>'
        % (esc(k), v, esc(note)) for k, v, note in cells)

    # 바로가기. 원장이 가리키는 곳만 낸다. 없는 링크를 만들지 않는다.
    go = []
    if r.get('report'):
        go.append((r['report'], '종합보고서', '무엇이 얼마나 나아졌나'))
    go.append(('/gallery/', '평가 영상 갤러리', '눈으로 보기'))
    go.append(('/research-20260911-eval-protocol-v2.html',
               '현재 평가 해설', '무엇을 어떻게 재나'))
    links = ''.join(
        '<a class="rg3" href="%s"><b>%s</b><span>%s</span></a>' % (esc(h), esc(n), esc(d))
        for h, n, d in go)

    return ('<section class="rel3"><div class="rk3">지금 어디까지 왔나'
            '<span class="rkm3">%s%s</span></div>'
            '<p class="rl3">%s</p>'
            '<div class="rvs">%s</div>'
            '<div class="rgs3">%s</div></section>'
            % (esc(r.get('main_model') or ''),
               (' · 평가 %s · 판 %s' % (when, r.get('id'))) if when else '',
               lead, grid, links))


def research_html(site):
    docs = _research_docs()
    meas = [d for d in docs if ev_short(d[1].get('근거')) == '실측']
    read = [d for d in docs if ev_short(d[1].get('근거')) != '실측']

    # 출발선 = 열린 이슈가 가장 많이 걸린 실측. 손으로 고르지 않는다.
    # ★ 이 점수는 «고르는» 데만 쓴다. 화면에 목록으로 내지 않는다 (_mentions 주석).
    scored = []
    for rel, m, page, g in meas:
        men = _mentions(page, rel.rsplit('/', 1)[-1])
        scored.append((len(men), len(g.get('children') or []), rel, m, page, men))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    hero = scored[0] if scored else None

    # ★ 2026-09-10. 출발선 «위» 의 띠. 「먼저 읽을 것」.
    #   왜 출발선을 안 쓰나: 출발선은 «열린 이슈가 가장 많이 걸린 실측» 을
    #   자동으로 뽑는 자리다. 손으로 고르지 않으려고 그렇게 만들었다.
    #   평가 프로토콜 같은 «기준» 문서는 실측이 아니라 성격이 다르다.
    #   그 자리를 차지하면 두 뜻이 섞이고, 자동 선정을 끄면 다음에 또 끈다.
    #   성격이 다른 것은 다른 자리에 둔다.
    #
    #   고르는 방법: 문서가 스스로 «> 지위: 먼저 읽을 것» 을 선언한다.
    #   파일 이름을 여기 적지 않는다. 적으면 그 이름이 바뀌는 날 조용히 사라진다.
    parts = []
    first3 = [d for d in docs if '먼저 읽을' in (d[1].get('지위') or '')]
    if len(first3) > 1:
        print('  [!] 「먼저 읽을 것」을 선언한 문서가 %d개다. 하나여야 한다: %s'
              % (len(first3), ' · '.join(d[0] for d in first3)))
        sys.exit(1)
    if first3:
        rel, m, page, _g = first3[0]
        parts.append(
            '<a class="fr3" href="%s">'
            '<span class="fk3">먼저 읽을 것</span>'
            '<b class="ft3">%s</b>'
            '<span class="fs3">%s</span></a>'
            % (esc(page), esc(m.get('제목') or m.get('요지') or rel),
               esc(_gist(m))))
    parts.append(_release_block())

    if hero:
        _n, _c, rel, m, page, _men = hero
        # ★ v3.1: 출발선은 문서 제목이 아니라 «결론 문장» 이다 (목업 2판 확정).
        #   머리말 «결론» 이 있으면 그것을 크게, 숫자 표현은 더 크게. 없으면 제목.
        concl = esc(m.get('결론') or m.get('제목', ''))
        concl = re.sub(r'(\d+\s*종\s*중\s*\d+\s*종|\d+(?:\.\d+)?\s*%)',
                       r'<b>\1</b>', concl, count=1)
        # ★ 팀장 확정 2026-09-04: 「후속 과제」 칩 줄을 없앤다. 그 줄은 이 실측을
        #   참고 링크로 적은 이슈를 긁어 왔을 뿐 후속이 아니었다 (#123 · #100).
        #   후속은 바로 아래 절이다. 카드에는 그리로 보내는 한 줄만 남긴다.
        #
        # ★ 2026-09-13: 출발선 «옆에» 지금 배포 결과를 붙인다.
        #   전에는 출발선만 있었다. 들어온 사람이 「이 팀이 무슨 문제를 풀고
        #   있나」는 알았지만 「그래서 지금 어디까지 왔나」는 한참 스크롤해야
        #   나왔다. 둘은 같은 이야기의 앞뒤라 붙여 놓아야 뜻이 산다.
        #
        #   설계 초안은 출발선을 «없애고» 배포 요약으로 바꾸는 것이었다.
        #   그러면 「왜 그 다섯 지형인가」라는 문제 정의가 사라진다. 배포
        #   요약은 «결과» 이지 «문제» 가 아니다. 그래서 대체가 아니라 합친다.
        #   높이는 늘리지 않는다. 두 덩이를 쌓지 않고 한 덩이 안에 넣는다.
        parts.append(
            '<div class="hero3"><div class="hk3">출발선 · 그때의 문제</div>'
            '<a class="ht3" href="%s">%s</a><div class="hd3">%s</div>'
            '<div class="hn3">실패한 다섯 지형은 아래에서 하나씩 본다</div></div>'
            % (page, concl, esc(m.get('제목', ''))))

    # ★ Track A · 실패 험지 5종 (foothold-lab#179). 출발선 바로 아래, 그 실측이
    #   낳은 다섯 지형의 «지금 어디까지» 다. 전용 페이지가 아니라 허브의 절이다.
    parts.append(terrain_html())

    # 여섯 입구는 «문서 목록 바로 위» 다. 찾는 말과 목록이 붙어 있어야
    # 누르고 나서 무엇이 걸러졌는지 눈에 들어온다.
    parts.append(_doors(docs, skip=[hero[2]] if hero else []))

    # ★ v3.1: 활동이 «보이는 묶음» 이다. 정렬만으로는 분류가 안 보인다 (팀장 지적).
    # ★ 2026-09-13. 묶음을 옛 `purpose` 에서 **여섯 입구** 로 바꾼다.
    #
    #   실측: `purpose` 로 묶으면 37장 중 **14장이 「분류 안 된 것」** 에
    #   떨어졌다. 가장 큰 묶음이 「분류 안 된 것」이면 그 분류는 안 서는 것이다.
    #   그 값은 자동 규칙이 evidence·kind 로 추정하던 것이라 새 문서가 들어올
    #   때마다 빈칸이 늘었다.
    #
    #   입구는 원장이 **39장 전수** 를 배정했고 누락이 있으면 빌드가 선다
    #   (`tools/build_research_catalog.py` 의 `check_functions`).
    #   위 거르개가 쓰는 축과 **같은 축** 이라, 누른 입구와 묶음 제목이 맞는다.
    #
    #   옛 `purpose` 는 안 지운다. `docs_pages._front_picks()` 등이 읽는다.
    #   화면에서 «묶는 기준» 으로만 안 쓴다.
    cat = catalog()
    PO = [(g['key'], g['name']) for g in (cat.get('groups') or [])]
    rest = list(scored[1:]) if hero else list(scored)
    bag = {}
    for it in rest:
        bag.setdefault(_fn_of(it[2]) or '', []).append(it)
    for key, label in PO + [(k, k or '입구가 안 정해진 것')
                            for k in sorted(bag) if k not in dict(PO)]:
        rows = []
        for _n2, _c2, rel, m, page, _m2 in sorted(
                bag.get(key, []), key=lambda x: _newest_first(x[3]),
                reverse=True):
            g = graph().get(rel) or {}
            n = num_in((m.get('결론') or '') + ' ' + m.get('요지', ''))
            ar = ' '.join('<u class="ar-%s">%s</u>'
                          % (AREA_HUE.get(a, 'x'), esc(a))
                          for a in (g.get('areas') or [])[:2])
            who, when = _who_when(m)
            rows.append(
                '<a class="ev3" data-fn="%s" href="%s"><span class="ex3">%02d</span>'
                '<span class="en3">%s</span>'
                '<span class="eb3"><b>%s</b><span>%s</span>'
                '<span class="em3">%s %s</span></span>%s</a>'
                % (esc(_fn_of(rel)), page, len(rows) + 1, esc(n) or '·',
                   esc(m.get('제목', '')),
                   esc(_gist(m, 70)),
                   esc('%s · %s' % (who, when) if who else when), ar,
                   _thumb(page)))
        if rows:
            # `data-label` 은 거르개가 건수를 다시 쓸 때 쓴다. 글자에서
            # 숫자를 떼어내려 하면 묶음 이름에 숫자가 들어간 날 깨진다.
            parts.append('<div class="eg3" data-label="%s">%s <span>%d</span></div>'
                         '<div class="evs3">%s</div>'
                         % (esc(label), label, len(rows), ''.join(rows)))

    # ★ 팀장 지적 (8/31): 「누가 언제 조사했는지」가 안 보이고 제목도 잘렸다.
    #   실측 카드와 같은 줄 구조로 통일한다. 근거 · 제목 · 요지 · 작성자 · 날짜.
    # ★ 2026-09-09 팀장 지적: 「외부 자료 조사가 아닌데 거기 들어간 문서가 많다.
    #   Track A MVP 를 위해 우리가 올린 보고서들 아니냐」. 맞다.
    #   이 통은 «실측이 아닌 것 전부» 였다 (read = ev != '실측'). 그래서
    #   우리 코드를 뜯어본 것(근거: 코드)과 우리 계획 노트(근거: 본인)까지
    #   외부 자료로 묶였다. 실측 9 · 공식 12 · 코드 1 · 본인 2 · 표기미비 1.
    #   「무엇이 아니다」로 묶지 않고 «근거 종류» 로 가른다.
    #   표기가 어긋난 것은 숨기지 말고 그 이름으로 드러낸다. 그래야 고쳐진다.
    # ★ 2026-09-13 팀장 확정: 목록을 «한 기준» 으로 묶는다.
    #
    #   전에는 위쪽(실측)이 여섯 입구로, 아래쪽(조사)이 «출처»(공식·코드·본인)로
    #   묶였다. 그래서 「도구·운영」을 눌렀는데 묶음 제목이 「외부 자료 조사」로
    #   나왔다. 클릭한 이름과 제목이 달라 읽는 사람이 멈춘다.
    #
    #   출처는 **카드 왼쪽 표식**(`실측`·`조사`·`코드`)에 이미 있다. 목록을
    #   묶는 축까지 그것으로 쓸 이유가 없다. 찾는 사람이 쓰는 말은 «무슨 글인가»
    #   이지 «어디서 났나» 가 아니다.
    #
    #   설계 문서의 「출처와 확실성은 다른 축」은 그대로다. 축이 다른 것과
    #   «목록을 묶는 기준» 은 다른 문제다. 거르개는 두 축을 다 둔다.
    cat2 = catalog()
    READ_GROUPS = [(g['key'], g['name']) for g in (cat2.get('groups') or [])]
    known = dict(READ_GROUPS)
    bins = {}
    for d in read:
        bins.setdefault(_fn_of(d[0]) or '', []).append(d)
    order = [(k, known[k]) for k, _ in READ_GROUPS if k in bins] + \
            [(k, '입구가 안 정해진 것') for k in sorted(bins) if k not in known]
    for key, label in order:
        reads, _i = '', 0
        for _rel, m, page, _g in sorted(
                bins[key], key=lambda x: _newest_first(x[1]), reverse=True):
            who, when = _who_when(m)
            _i += 1
            # ★ 카드를 내는 자리가 «둘» 이다. 위(실측)와 여기(조사).
            #   처음에 위만 고쳐서 조사 문서 16장이 입구 표식을 못 받았고,
            #   거르개를 눌렀을 때 그 16장이 통째로 사라졌다. 규칙을 만들면
            #   그 규칙이 사는 «다른 자리» 를 먼저 센다 (철칙 4).
            reads += ('<a class="ev3" data-fn="%s" href="%s">'
                      '<span class="ex3">%02d</span>'
                      '<span class="en3 src s-%s">%s</span>'
                      '<span class="eb3"><b>%s</b><span>%s</span>'
                      '<span class="em3">%s</span></span>%s</a>'
                      % (esc(_fn_of(_rel)), page, _i, ev_short(m.get('근거')),
                         esc(ev_short(m.get('근거'))),
                         esc(m.get('제목', '')), esc(_gist(m, 78)),
                         esc('%s · %s' % (who, when) if who else when),
                         _thumb(page)))
        # ★ 조사 절 제목은 `.eh3` 라 거르개가 «못 봤다». 걸렀더니 카드 5장이
        #   제목 없이 떠 있었다 (실측 `?fn=tooling`). 클래스가 다르다고 규칙을
        #   따로 만들면 또 어긋난다. **같은 표식** 을 달아 한 규칙으로 다룬다.
        parts.append(
            '<div class="eh3" data-label="%s">%s %d</div>'
            '<div class="evs3">%s</div>'
            % (esc(label), label, len(bins[key]), reads))
    return ''.join(parts)


# ── 회의 ────────────────────────────────────────────────────────────
SEATMAP = {'팀내부': ('팀', 's-team'), '멘토링': ('멘토', 's-mentor'),
           '운영진': ('운영', 's-ops'), '조선대': ('조선대', 's-chosun'),
           '결정': ('결정', 's-ops'), '현장': ('현장', 's-chosun')}


def _entry_date(fname, v):
    m = re.search(r'(\d{8})', fname)
    if m:
        d = m.group(1)
        return d[:4] + '-' + d[4:6] + '-' + d[6:]
    m = re.search(r'-(\d{2})(\d{2})\.html$', fname)
    if m:
        return '2026-%s-%s' % (m.group(1), m.group(2))
    m = re.search(r'(\d{4}-\d{2}-\d{2})', (v[4] if len(v) > 4 else '') or '')
    return m.group(1) if m else ''


def meeting_html(site, assigned=None):
    """타임라인 + 자리 필터.

    ★ v3.2 (팀장 실측 2026-08-31): 필터가 전혀 안 움직였다.
      버튼 data-seat 에 CSS 클래스(s-mentor)를 박아 카드(멘토링)와 영원히
      못 만났다. 그리고 회의 허브 배정 12장 중 4장(결정 로그 · 8/27 결정 ·
      현장 2)이 타임라인에 아예 없었다. 배정에서 그린다. 손 목록이 아니다.
    """
    rows, pinned = [], None
    for f, v in sorted((assigned or {}).items()):
        if v[0] != 'meeting':
            continue
        if f == 'decisions-log.html':
            pinned = (f, v)
            continue
        # 자리는 배정 묶음(v[1])에 이미 들어 있다 (ia 가 md 자리로 묶었다)
        seat = {'팀 내부에서 정한 것': '팀내부', '멘토에게 받은 것': '멘토링',
                '운영진과 맞춘 것': '운영진', '조선대와 맞춘 것': '조선대',
                '무엇을 정했나': '결정', '현장 기록': '현장'}.get(v[1], '팀내부')
        rows.append((_entry_date(f, v), seat, f, v))
    out_rows = [(d, seat or '팀내부', f, v) for d, seat, f, v in rows]
    out_rows.sort(key=lambda x: x[0], reverse=True)
    cnt = {}
    for _d, seat, _f, _v in out_rows:
        cnt[seat] = cnt.get(seat, 0) + 1
    chips = ['<button class="mf on" data-seat="">전체 <i>%d</i></button>'
             % len(out_rows)]
    for name in ('팀내부', '멘토링', '운영진', '조선대', '결정', '현장'):
        if cnt.get(name):
            chips.append('<button class="mf" data-seat="%s">%s <i>%d</i></button>'
                         % (name, name, cnt[name]))
    top = ''
    if pinned:
        pf, pv = pinned
        top = ('<a class="w3t" style="display:block;border:1px solid var(--rule);'
               'border-radius:8px;padding:.7rem 1rem;margin-bottom:1rem" href="%s">'
               '<b>%s</b><span style="display:block;font-size:.73rem;'
               'color:var(--ink-3)">%s · 누적 기록이라 시간축 밖에 둔다</span></a>'
               % (pf, esc(pv[2]), esc(pv[3])))
    tl = []
    for i, (d, seat, f, v) in enumerate(out_rows):
        ko, cls = SEATMAP.get(seat, ('팀', 's-team'))
        tl.append(
            '<a class="tl3%s" data-seat="%s" href="%s"><span class="tld3">%s</span>'
            '<span class="seat3 %s">%s</span><span class="tlb3">'
            '<span class="tlt3">%s</span>%s</span></a>'
            % ('' if i < 3 else ' old', esc(seat), f,
               d[5:].replace('-', '/') if d else '', cls, ko,
               esc(v[3] or v[2]),
               ('<span class="tls3">%s</span>' % esc(v[2])) if i < 3 else ''))
    js = ('<script>document.querySelectorAll(".mf").forEach(function(b){'
          'b.onclick=function(){'
          'document.querySelectorAll(".mf").forEach(function(x){x.classList.remove("on")});'
          'b.classList.add("on");var s=b.dataset.seat;'
          'document.querySelectorAll("a[data-seat]").forEach(function(t){'
          't.style.display=(!s||t.dataset.seat===s)?"":"none"});};});</script>')
    return ('%s<div class="mfs">%s</div><div class="tlw3">%s</div>%s'
            % (top, ''.join(chips), ''.join(tl), js))


# ── 기획 ────────────────────────────────────────────────────────────
PROPOSAL_OUT = [('읽는 문서', '프로젝트 보고서', '한 장으로 보는 전체 계획',
                 'project-report.html'),
                ('띄우는 화면', '프로젝트 소개 덱', '전체화면 발표용',
                 'pitch.html'),
                ('건네는 한 장', '프로젝트 브리핑', '외부에 짧게 설명할 때',
                 'brief.html')]
PROPOSAL_IN = [('프로젝트 전체 흐름', '두 트랙으로 무엇을 어떤 순서로 하는가 (PRD §3)',
            'flow.html'),
           ('역할 배치', '작업 영역 8갈래와 주담당 · 덱이 여기서 생성된다',
            'roles.html'),
           ('팀 소개 · 킥오프', '팀과 역할', 'team-intro.html')]

# ★ 9/1 팀장 지적: 「기획 내부 문서에 오흥재 나만 있을 필요가 있냐」.
#   맞다. 여기 한 사람만 하드코딩돼 있었다. 오늘 넷이 되면서 이름을 다 넣으면
#   다섯 줄이 되는데 그건 더 나쁘다. 사람은 «한 줄» 로 묶는다.
#   개인 페이지로 들어가는 정문은 「팀 소개 · 킥오프」 다 (원래 설계).
PEOPLE = [('오흥재', 'team-lead.html'), ('임석헌', 'team-lim.html'),
          ('맹라현', 'team-meang/index.html'), ('오현민', 'team-oh.html'),
          ('이민우', 'team-lee.html')]

# ★ 팀장 9/1: 「main 으로 영역을 나눴지만 그래도 함께 나눠서 진행하고 있다.
#   각자가 각자로써도 돋보이면서 누락되지 않는 그림」
#   research-terrain-finetune-plan 대로 실패 지형 5종을 다섯이 하나씩 맡는다.
#   그래서 두 층으로 세운다. 왼쪽은 각자(포지션), 오른쪽은 함께(맡은 지형).
#   포지션은 ROLES.md 정본이 채워지면 거기서 온다. 아직 본인 확인 전인 것은
#   비워 두고 메인 역할을 쓴다. 지어 붙이지 않는다 (멘토: 허위 키워드 금지).
TERRAIN = {'임석헌': ('gap', 65), '맹라현': ('rails', 66),
           '오현민': ('stepping_stones', 67), '이민우': ('pit', 68),
           '오흥재': ('floating_ring', 69)}


def team_html():
    """기획 허브의 팀 절. 두 층으로 읽힌다."""
    try:
        import roles
        _areas, people = roles.load()
    except Exception:
        people = None
    by = {p['name']: p for p in (people or [])}
    rows = []
    for n, h in PEOPLE:
        if not os.path.isfile(os.path.join(VAULT_OF(), h)):
            continue
        p = by.get(n, {})
        lead = p.get('대표') == '예'
        pos = re.sub(r'\*\*|`', '', p.get('포지션', '') or '')
        what = pos or re.sub(r'\*\*|`', '',
                             p.get('메인 역할') or p.get('한 줄', ''))
        t = TERRAIN.get(n)
        tag = ('<span class="tmg3">실패 지형 <b>%s</b></span>' % esc(t[0])) if t else ''
        area = ' · '.join(x.strip().strip('`').split('/')[-1]
                         for x in (p.get('갈래', '') or '').split('·') if x.strip())
        rows.append('<a class="ir3 tmr3" href="%s"><b>%s%s</b>'
                    '<span class="tmw3"%s>%s</span>'
                    '<span class="tma3">%s</span>%s</a>'
                    % (h, esc(n), ' <i>팀장</i>' if lead else '',
                       ' data-pos="1"' if pos else '', esc(what),
                       esc(area), tag))
    if not rows:
        return ''
    return ('<div class="ph3">팀 <span class="phn3">각자 맡은 축 · 함께 나눈 '
            '실패 지형 5종</span></div><div class="irs3">%s</div>' % ''.join(rows))


def proposal_html(site):
    outw, inw = PROPOSAL_OUT, PROPOSAL_IN
    a = ''.join(
        '<a class="pc3" href="%s"><span class="pk3">%s</span><b>%s</b>'
        '<span>%s</span></a>' % (h, k, t, d) for k, t, d, h in outw)
    b = ''.join('<a class="ir3" href="%s"><b>%s</b><span>%s</span></a>'
                % (h, t, d) for t, d, h in inw)

    return ('<div class="ph3">대외 산출물</div>'
            '<div class="pcs3">%s</div>'
            '<div class="ph3">내부 문서</div><div class="irs3">%s</div>'
            '%s' % (a, b, team_html()))


# ── 기술 ────────────────────────────────────────────────────────────
# 경로 순서. 파일이 ia.VAULT_PAGE(tech) 에 있어야 화면에 선다 (여기만 고치면 안 됨).
#   번호는 묶음 «안» 의 배우는 순서다. 트랙 A 와 B 는 병렬이라 묶음이 갈린다.
TECH_ORDER = ['ros2-01-setup.html', 'ros2-02-python.html',
              'ros2-03-tf-rviz2.html', 'tech-ros2-ref.html',
              'tech-rl.html', 'tech-slam-nav.html', 'tech-cv.html']


def tech_html(site):
    import ia
    entries = [(f, v[1], v[2]) for f, v in ia.VAULT_PAGE.items()
               if v[0] == 'tech' and os.path.isfile(os.path.join(VAULT_OF(), f))]
    entries.sort(key=lambda x: (TECH_ORDER.index(x[0])
                                if x[0] in TECH_ORDER else 99, x[0]))
    groups = {}
    for f, t, d in entries:
        g = ia.VAULT_GROUP.get('tech', {}).get(f, '그 밖')
        groups.setdefault(g, []).append((f, t, d))
    out = ''
    for g in ('ROS 2 기초', '트랙 A · 시뮬 학습', '트랙 B · 실기 항법', '그 밖'):
        rows = groups.get(g)
        if not rows:
            continue
        s = ''
        for i, (f, t, d) in enumerate(rows):
            s += ('<div class="st3"><span class="sn3">%02d</span>'
                  '<a class="sb3" href="%s"><b>%s</b><span>%s</span></a></div>'
                  % (i + 1, f, esc(t), esc(d)))
            if i < len(rows) - 1:
                s += '<div class="jt3"></div>'
        out += ('<div class="eh3" style="margin-top:1.6rem">%s '
                '<span>%d편</span></div><div class="pt3">%s</div>'
                % (g, len(rows), s))
    # ★ 팀장 지적 (8/31): 「확장 예정 방향성 좋아, 근데 위치가 애매하긴 하지?
    #   미리 만들어놓던가, 이슈에 등록해서 채우는 방향으로 하던가」.
    #   -> 바닥에 떠 있던 한 문장을 «같은 목록의 마지막 묶음» 으로 올린다.
    #   경로가 이어진다는 뜻이 위치로 드러나고, 각 줄은 추적 이슈로 간다.
    # 세 편 모두 #97 이 추적한다 (팀장 지시대로 이슈로 등록해 채운다)
    soon = [('Isaac Lab 실전', '학습 루프를 직접 돌리는 편. 사전 측정 #90 · 추적 #97',
             ISSUE % 97),
            ('MuJoCo', '가벼운 사전 측정용. 레일즈 스윕 설계 #90 · 추적 #97',
             ISSUE % 97),
            ('Omniverse', '트윈·렌더 도구 계통. 도구 백과 #6 에서 기획 · 추적 #97',
             ISSUE % 97)]
    ss = ''
    for i, (t, d, href) in enumerate(soon):
        ss += ('<div class="st3 soon"><span class="sn3">%02d</span>'
               '<a class="sb3" href="%s" target="_blank" rel="noopener">'
               '<b>%s</b><span>%s</span></a></div>' % (i + 1, href, esc(t),
                                                       esc(d)))
        if i < len(soon) - 1:
            ss += '<div class="jt3"></div>'
    return (out +
            '<div class="eh3" style="margin-top:1.6rem">확장 예정 '
            '<span>%d편 · 이슈로 채운다</span></div>'
            '<div class="pt3">%s</div>'
            '<div class="soon3">lab 문서는 머리말 «차례»로, 볼트 페이지는 '
            'TECH_ORDER 로 경로에 선다. 학습자료·커리큘럼 병합은 #72 2단계.</div>'
            % (len(soon), ss))


ISSUE = 'https://github.com/foothold-project/foothold-lab/issues/%d'


def VAULT_OF():
    import hubgen
    return hubgen.VAULT


# ── 파이프라인 ──────────────────────────────────────────────────────
# 볼트 생성 페이지는 md 머리말이 없어 여기 손 배치. lab md 는 «언제 보나»가 이긴다.
WHEN_PAGE = {
    '합류': [('setup.html', '개발환경 구축', '팀 공통 세팅'),
             ('team-access.html', '워크스테이션 접속', '원격 접속과 운영'),
             # ★ PR #106 승격 (오현민). 학습을 RunPod 으로 돌리기로 했으니(#94)
             #   합류 시 보는 것이 하나 늘었다.
             ('runpod-setup.html', 'RunPod Isaac Lab 환경',
              '볼륨 · 템플릿 · 첫 실행. 마운트는 /data'),
             ],
    '매일': [('workflow.html', '작업 흐름', '이슈부터 머지까지 한 장'),
             ('collab.html', 'FOOTHOLD 협업 규칙', '브랜치 · 보드 · 문서 규칙'),
             ('automation.html', '자동화 지도', '무엇이 자동이고 무엇이 사람인가')],
    '투고': [('info-model.html', '정보 모델', '내 글이 어디로 가나'),
             ('doc-graph.html', '문서 관계표', '무엇이 무엇의 상위인가'),
             ('research-taxonomy.html', '연구 허브 분류 기준', '검토중')],
}
WHEN_TITLE = [('합류', '합류 시', '오늘 합류했다. 손을 움직이려면 무엇부터.'),
              ('매일', '상시 참조', '이슈를 열고 PR 을 올릴 때 펴 놓는 것.'),
              ('투고', '문서 투고 시', '내 글이 어디로 가는가.')]


def pipeline_html(site):
    # lab md 의 «언제 보나» 가 있으면 그 절로 합류한다 (유입 규칙)
    extra = {}
    root = os.path.join(lab(), 'docs')
    import mdlinks
    for f in sorted(os.listdir(root)):
        if not f.endswith('.md'):
            continue
        m = meta(os.path.join(root, f), fields=('언제 보나', '요지'))
        w = m.get('언제 보나', '').split('|')[0].strip()
        if w in ('합류', '매일', '투고'):
            page = mdlinks.resolve('docs/' + f)
            if page:
                extra.setdefault(w, []).append(
                    (page, m.get('제목', f), m.get('요지', '')[:40]))
    out = ''
    for key, title, desc in WHEN_TITLE:
        items = WHEN_PAGE.get(key, []) + extra.get(key, [])
        rows = ''.join('<a class="wr3" href="%s"><b>%s</b><span>%s</span></a>'
                       % (h, esc(t), esc(d)) for h, t, d in items)
        out += ('<div class="ws3"><div class="wt3">%s</div>'
                '<div class="wd3">%s</div>%s</div>' % (title, desc, rows))
    return '<div class="wns3">%s</div>' % out


# ── 표지 타일 상태줄: 산문 금지, 코드가 계산한다 ─────────────────────
def state_lines():
    import deliverables_page as dlv
    out = {}
    try:
        rows = [r for r in dlv.build_rows(lab(), dlv.today_kst()) if r[3] >= 0]
        near = min(rows, key=lambda r: r[3])
        st = {}
        for _l, s, _d, _r in near[4]:
            st[s] = st.get(s, 0) + 1
        tal = ('걸린 %d장 전부 %s' % (len(near[4]), list(st)[0])
               if len(st) == 1 and near[4] else
               ' · '.join('%s %d' % kv for kv in st.items()))
        out['schedule'] = ('D-%d %s · %s' % (near[3], near[0], tal), near[3] <= 7)
    except Exception:
        out['schedule'] = ('관문 다섯', False)
    docs = _research_docs()
    meas = [d for d in docs if ev_short(d[1].get('근거')) == '실측']
    out['research'] = ('실측 %d · 조사 %d · 출발선이 맨 위'
                       % (len(meas), len(docs) - len(meas)), False)
    root = os.path.join(lab(), 'docs', 'meetings')
    ms = sorted([f for f in os.listdir(root)
                 if re.match(r'\d{8}-', f)], reverse=True) if os.path.isdir(root) else []
    if ms:
        m = meta(os.path.join(root, ms[0]))
        out['meeting'] = ('최근 %s/%s · %s'
                          % (ms[0][4:6], ms[0][6:8],
                             (m.get('요지') or m.get('제목', ''))[:24]), False)
    else:
        out['meeting'] = ('회의 기록', False)
    # ★ 팀장 지적 (8/31): 「죽어있는 글」 금지. 산문 상태줄을 계산으로.
    _out = len(PROPOSAL_OUT)
    _in = len(PROPOSAL_IN)
    _drafts = 0
    try:
        import deliverables_page as _d2
        _drafts = sum(1 for r in _d2.build_rows(lab(), _d2.today_kst())
                      for it in r[4] if it[1] in ('초안', '검토중'))
    except Exception:
        pass
    out['proposal'] = ('밖으로 %d · 안으로 %d · 제출 초안 %d' % (_out, _in, _drafts),
                       False)
    import ia as _ia
    _nt = sum(1 for v in _ia.VAULT_PAGE.values() if v[0] == 'tech')
    out['tech'] = ('경로 %d편 · 기초 4 + 트랙 A·B' % _nt, False)
    _wn = sum(len(v) for v in WHEN_PAGE.values())
    out['pipeline'] = ('규칙 %d장 · 합류 · 매일 · 투고' % _wn, False)
    return out


CSS = '''<style id="hub3-css">
/* ★ PRD §4-2 부품 한 벌 (팀장 지적 «허브 넘어갈 때마다 틀어진다» · 실측:
   카드 반경 7/8/9/10px 4종 · 절 머리글 5종 · 패딩 16종).
   부품 사양을 토큰으로 두고 모든 허브가 이것만 참조한다. 방언 금지. */
:root{
  --p-radius:8px;          /* 카드 반경 한 값 */
  --p-radius-chip:99px;    /* 칩만 예외 (알약) */
  --p-radius-tag:3px;      /* 작은 딱지 */
  --p-pad:.85rem 1.05rem;  /* 카드 안쪽 */
  --p-pad-chip:.26rem .7rem;
  --p-head:.72rem;         /* 절 머리글 크기 */
  --p-head-ls:.08em;
  --p-title:.9rem;         /* 카드 제목 */
  --p-body:.75rem;         /* 카드 설명 */
  --p-meta:.68rem;         /* 메타 */
  --p-gap:.5rem;
}
/* 부품 1-b: 머리글 줄 (제목 + 우측 액션). 부품 통합 때 .w3h 가 flex 를
   잃어 「프로젝트 보드」 칩이 제목에 딱 붙었다 (팀장 스크린샷 8/31).
   머리글이면서 «오른쪽에 무언가 붙는» 것은 이 부품이다. */
.w3h,.mfs{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
.w3h>:last-child{margin-left:auto}
.w3h{font-size:.95rem!important;font-weight:830}
/* 부품 1: 절 머리글 */
.eh3,.eg3,.ph3,.rh3,.w3h,.wt3{font-size:var(--p-head);font-weight:800;
  letter-spacing:var(--p-head-ls);color:var(--ink-2,var(--ink-3));
  border-bottom:1px solid var(--rule);padding-bottom:.3rem;margin:1.4rem 0 .5rem}
.eh3:first-child,.ph3:first-child,.w3h{margin-top:0}
.eh3 span,.ph3 span,.eg3 span,.wt3 span{font-weight:600;letter-spacing:0;
  color:var(--ink-3)}
.eg3{color:var(--dim)}
/* ★ 8/31 실측: 셸의 기본 `a{color:link;text-decoration:underline}` 가 이겨
   기획 카드가 파란 밑줄로 떴다. 부품 링크는 스스로 색을 껐다고 «명시» 한다.
   (부품이 셸에 기대면 페이지마다 달라진다) */
#hub3 a,.w3 a,.hero3 a,.pc3,.sb3,.c3,.fk3,.ir3,.dp3,.ev3,.rr3,.tl3,.wr3,
.w3t,.w3p a,.w3p-q,.ht3{color:inherit;text-decoration:none}
.pc3 *,.sb3 *,.dp3 *,.ir3 *,.ev3 *,.rr3 *{text-decoration:none}
/* 부품 2: 카드 */
.w3,.hero3,.pc3,.sb3,.g3,.c3,.fk3,.tile{border:1px solid var(--rule);
  border-radius:var(--p-radius);background:var(--card)}
.w3,.hero3,.pc3,.sb3,.g3{padding:var(--p-pad)}
.pc3:hover,.sb3:hover,.fk3:hover{border-color:var(--dim)}
/* 부품 3: 칩 */
.c3,.fk3,.mf,.w3p a{border-radius:var(--p-radius-chip);
  padding:var(--p-pad-chip);font-size:var(--p-body)}
.rk3,.rdk,.seat3,.em3 u{border-radius:var(--p-radius-tag)}
/* 부품 6: 관문 띠 (PRD §4-2) · 왼쪽 D-day 열 9.5rem.
   부품 통합 때 이 규칙이 지워져 세로로 늘어졌다 (실측 8/31). */
.g3,.g3.near{display:grid;grid-template-columns:9.5rem 1fr;gap:1rem;
  align-items:start}
.g3.near{border-color:var(--note,#d29922)}
.g3l{display:flex;flex-direction:column}
.g3n{font-size:.82rem;font-weight:800;margin-top:.12rem}
.g3u{font-size:var(--p-meta);color:var(--ink-3)}
.g3t{font-size:var(--p-meta);font-weight:800;color:var(--ink-3);margin-bottom:.42rem}
.g3.near .g3t,.g3.near .g3d{color:var(--note,#d29922)}
.c3{display:inline-flex;align-items:baseline;gap:.45rem;text-decoration:none;
  color:inherit;background:var(--paper)}
.c3 b{font-size:.77rem;font-weight:700}
.c3 i{font-style:normal;font-size:.66rem;color:var(--dim);font-weight:700}
.c3 span{font-size:.6rem;font-weight:800;color:var(--ink-3)}
.c3.draft{border-color:var(--note,#d29922)}
.c3.draft span{color:var(--note,#d29922)}
.c3.done{border-color:var(--dim)}
.c3.done span{color:var(--dim)}
@media (max-width:640px){.g3,.g3.near{grid-template-columns:1fr;gap:.5rem}}

/* ★ 간격 실측 (팀장 8/31): 멘토링 카드와 관문 띠가 간격 0 으로 붙었다.
   w3 는 절(section) 단위 카드다. 아래 여백을 부품 사양으로 준다. */
.w3{margin-bottom:1.1rem}
.wks .w3{margin-bottom:0}
.g3s{margin-top:0}
/* 일정: 주간 2단 · 관련 문서 카드 */
.wks{display:grid;grid-template-columns:1fr 1fr;gap:var(--p-gap);margin:0 0 .6rem}
.wks .w3.dim{opacity:.62}
.w3sub{font-size:var(--p-body);color:var(--ink-3);margin-top:.3rem}
.w3done{display:block;font-size:var(--p-meta);color:var(--dim);font-weight:700;
  margin-top:.25rem}
.w3p-q{font-size:var(--p-body);color:inherit;text-decoration:none;
  border:1px solid var(--rule);border-radius:var(--p-radius-chip);
  padding:var(--p-pad-chip);display:inline-block;margin:.15rem .2rem 0 0}
.deep3{display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));
  gap:var(--p-gap)}
.dp3{display:block;text-decoration:none;color:inherit;border:1px solid var(--rule);
  border-radius:var(--p-radius);background:var(--card);padding:.7rem .9rem}
.dp3:hover{border-color:var(--dim)}
.dp3 b{font-size:var(--p-title);font-weight:780;display:block}
.dp3 span{font-size:var(--p-body);color:var(--ink-3)}
@media (max-width:760px){.wks{grid-template-columns:1fr}}
/* 부품 4: 큰 숫자 (D-day · 실측치 공용) */
.g3d,.en3{font-weight:850;font-variant-numeric:tabular-nums;line-height:1.1}
.g3d{font-size:1.4rem}
.en3{font-size:1rem;color:var(--dim);text-align:right}
/* ★ 근거 태그도 색으로 (팀장 9/1). 공식=밖에서 온 것 · 코드=코드에서 확인 ·
   본인=내 노트. 갈래 색과 겹치지 않게 «채도 낮은 계열» 로 둔다. */
.en3.src{font-size:.6rem;font-weight:800;white-space:nowrap;letter-spacing:.04em;
  color:var(--ink-3)}
.en3.src.s-공식{color:#1b6b8f}
.en3.src.s-코드{color:#5a6a2a}
.en3.src.s-본인{color:#8a4a7a}
.en3.src.s-팀{color:#4a5566}
.en3.src.s-현장{color:#a86a08}
.en3.src.s-조선대{color:#a3342a}
/* 넘버링 · 썸네일 · 갈래 색 (팀장 8/31) */
/* ★ 실측 (2026-09-01): 넘버·썸네일을 더하면서 자식이 4개가 됐는데 격자 선언이
   앞의 것을 덮지 못해 본문이 세로로 뭉갰다. 4열을 명시하고 auto 를 마지막에. */
.ev3{display:grid!important;grid-template-columns:2.2rem 5.4rem minmax(0,1fr) auto!important;
  gap:.7rem;align-items:start}
.ev3 .eb3{min-width:0}
.ex3{font-family:ui-monospace,Consolas,monospace;font-size:.68rem;font-weight:800;
  color:var(--ink-3);text-align:right;padding-top:.15rem}
.eth3{flex:none;width:4.6rem;height:3rem;overflow:hidden;border-radius:4px;
  background:var(--paper-2);align-self:center}
.eth3 img{width:100%;height:100%;object-fit:cover;display:block}
.em3 u{text-decoration:none;border:1px solid var(--rule);border-radius:3px;
  padding:0 .3rem;margin-right:.25rem;font-size:.95em}
.em3 u.ar-a1{color:#0e7a6e;border-color:#0e7a6e}
.em3 u.ar-a2{color:#1b6b8f;border-color:#1b6b8f}
.em3 u.ar-a3{color:#7a5a10;border-color:#7a5a10}
.em3 u.ar-a4{color:#8a4a7a;border-color:#8a4a7a}
.em3 u.ar-b1{color:#a3342a;border-color:#a3342a}
.em3 u.ar-b2{color:#a86a08;border-color:#a86a08}
.em3 u.ar-c1{color:#4a5566;border-color:#4a5566}
.em3 u.ar-c2{color:#5a6a2a;border-color:#5a6a2a}
@media (max-width:760px){/* ★ 2026-09-13. 데스크톱 선언에만 !important 가 있어 여기가 «졌다».
   실측: 휴대폰에서 카드 본문 폭이 156px 이었다. 번호·수치 열이
   데스크톱 폭 그대로 자리를 먹은 것이다. 같은 무게로 맞춘다 */
.ev3{grid-template-columns:1.8rem 3.4rem minmax(0,1fr) auto!important}
.ev3{grid-template-columns:1.8rem 3.4rem 1fr}
  .eth3{display:none}}


.w3b{margin-left:auto;font-size:.68rem;font-weight:800;color:var(--dim);
 text-decoration:none;border:1px solid var(--dim);border-radius:99px;padding:.12rem .6rem}
/* 매주 회차를 브라우저가 다시 세는 D-day (#155). 값이 바뀌는 자리라
   폭이 흔들리지 않게 고정폭 숫자를 쓴다. 관문 dd-live 와 같은 처리다. */
.mdd{font-variant-numeric:tabular-nums}
.w3t{display:block;text-decoration:none;color:inherit;margin:.55rem 0 0}
.w3t b{font-size:.85rem;font-weight:780;display:block}
.w3t span{font-size:.73rem;color:var(--ink-3)}
.w3p{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.6rem}
.w3p a{font-size:.72rem;font-weight:700;color:inherit;text-decoration:none;
 border:1px solid var(--rule);border-radius:99px;padding:.2rem .65rem}
.w3p a:hover{border-color:var(--dim)}
.w3p a i{font-style:normal;color:var(--ink-3);font-size:.62rem}
.w3empty{font-size:.78rem;color:var(--ink-3);margin-top:.4rem}
.g3s{display:grid;gap:.5rem}

.g3.near{border-color:var(--note,#d29922);background:var(--card)}
.g3l{display:flex;flex-direction:column}

.g3n{font-size:.82rem;font-weight:800;margin-top:.1rem}
.g3u{font-size:.68rem;color:var(--ink-3)}
.g3t{font-size:.7rem;font-weight:800;color:var(--ink-3);margin-bottom:.42rem}
.g3.near .g3t{color:var(--note,#d29922)}
.chips3{display:flex;flex-wrap:wrap;gap:.4rem}

.c3 b{font-size:.77rem;font-weight:700}
.c3 i{font-style:normal;font-size:.66rem;color:var(--dim);font-weight:700}
.c3 span{font-size:.6rem;font-weight:800;color:var(--ink-3)}
.c3.draft{border-color:var(--note,#d29922)}
.c3.draft span{color:var(--note,#d29922)}
.c3.done{border-color:var(--dim)}.c3.done span{color:var(--dim)}
.ref3{margin-top:1rem;display:flex;flex-wrap:wrap;gap:.35rem .8rem;
 align-items:baseline;border-top:1px dashed var(--rule);padding-top:.7rem}

.ref3 a{font-size:.74rem;color:var(--ink-2,var(--ink-3));text-decoration:none;
 border-bottom:1px solid var(--rule)}
.ref3 a:hover{color:var(--dim);border-color:var(--dim)}

.hk3{font-size:.62rem;font-weight:800;letter-spacing:.14em;color:var(--dim)}
.ht3{display:block;font-size:1.25rem;font-weight:850;letter-spacing:-.01em;
 margin:.3rem 0 .1rem;line-height:1.35;color:inherit;text-decoration:none}
.ht3:hover{color:var(--dim)}
.hd3{font-size:.8rem;color:var(--ink-3)}
/* 첫 영역 · 「지금 어디까지 왔나」 (2026-09-13 · 목업 확정본).
   들어온 사람이 맨 처음 보는 덩이다. 수치는 원장이 실측에서 계산한다.
   PC 에서 넉 줄이 한 줄에 서고, 좁아지면 둘씩 접힌다 */
.rel3{border:1px solid var(--rule);border-radius:var(--p-radius,10px);
 padding:var(--p-pad);margin:0 0 .7rem;background:var(--paper-2,transparent)}
.rk3{display:flex;flex-wrap:wrap;align-items:baseline;gap:.5rem;
 font-size:.62rem;font-weight:800;letter-spacing:.14em;color:var(--dim)}
.rkm3{font-size:.62rem;font-weight:700;letter-spacing:.04em;color:var(--ink-3)}
.rl3{margin:.45rem 0 .8rem;font-size:.92rem;font-weight:650;line-height:1.55;
 color:var(--ink);word-break:keep-all}
.rl3 b{font-weight:850;color:var(--dim)}
.rvs{display:grid;gap:.5rem;grid-template-columns:repeat(4,1fr)}
@media(max-width:760px){.rvs{grid-template-columns:repeat(2,1fr)}}
.rv3{border-top:2px solid var(--rule);padding-top:.4rem;min-width:0}
.rvk3{font-size:.64rem;font-weight:700;color:var(--ink-3);
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rvn3{font-size:1.34rem;font-weight:850;letter-spacing:-.02em;color:var(--ink);
 line-height:1.25;font-variant-numeric:tabular-nums;margin:.1rem 0}
.rvn3 i{font-style:normal;font-size:.58em;font-weight:800;color:var(--dim)}
.rvs3{font-size:.62rem;color:var(--ink-3);line-height:1.4;word-break:keep-all}
.rgs3{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.8rem}
.rg3{display:inline-flex;flex-direction:column;gap:.1rem;padding:.4rem .65rem;
 border:1px solid var(--rule);border-radius:var(--p-radius-tag,6px);
 background:var(--paper);color:inherit;text-decoration:none}
.rg3:hover{border-color:var(--dim)}
.rg3 b{font-size:.74rem;font-weight:800}
.rg3 span{font-size:.62rem;color:var(--ink-3)}

/* 둘째 영역 · 여섯 입구. 「이런 글은 어디서 찾지」의 답이다.
   큰 카드 여섯이 아니라 «누르면 목록이 걸러지는» 단추다. 크게 만들면
   첫 문서 카드가 그만큼 밀린다 (실측: 얹기만 해도 PC +128px) */
.dr3{display:grid;gap:.4rem;grid-template-columns:repeat(6,1fr);margin:0 0 .9rem}
@media(max-width:1100px){.dr3{grid-template-columns:repeat(3,1fr)}}
@media(max-width:760px){.dr3{grid-template-columns:repeat(2,1fr)}}
@media(max-width:420px){.dr3{grid-template-columns:1fr}}
.dr3 a{display:flex;align-items:baseline;gap:.4rem;padding:.45rem .6rem;
 border:1px solid var(--rule);border-radius:var(--p-radius-tag,6px);
 color:inherit;text-decoration:none;min-width:0}
.dr3 a:hover{border-color:var(--dim)}
.dnm3{font-size:.76rem;font-weight:800;white-space:nowrap}
/* 설명은 «자리가 있을 때만» 보인다. 여섯을 한 줄에 놓으면 칸이 좁아
   이름이 먼저 잘린다. 이름과 건수는 끝까지 남기고 설명부터 접는다.
   찾는 사람에게 필요한 것은 이름이지 설명이 아니다 */
.dex3{flex:1 1 auto;min-width:0;font-size:.64rem;color:var(--ink-3);
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(min-width:1101px){.dex3{display:none}}
@media(max-width:520px){.dex3{display:none}}
.dct3{flex:0 0 auto;font-size:.66rem;font-weight:850;color:var(--dim);
 font-variant-numeric:tabular-nums}
/* 고른 입구. 색만으로 알리지 않는다 (테두리도 함께 굵어진다) */
.dr3 a[aria-pressed="true"]{border-color:var(--dim);border-width:2px;
 padding:calc(.45rem - 1px) calc(.6rem - 1px);background:var(--paper)}
.dr3 a[aria-pressed="true"] .dnm3{color:var(--dim)}
/* ★ 2026-09-13. `el.hidden` 만으로는 «안 사라진다».
   브라우저 기본 시트의 `[hidden]{display:none}` 은 «태그 선택자» 수준이라
   우리 `.ev3{display:grid}` 한 줄에 진다. 명세대로다.

   실측 (라이브 `?fn=diagnosis`): 속성이 hidden 인 카드 29장 · 화면에서
   실제로 사라진 카드 **0장** · 37장이 전부 보였다. 거르개를 눌러도
   아무것도 안 걸러진 것이다.

   내 시험이 이것을 놓친 까닭도 같다. `!c.hidden` 을 셌다. **그건 내가 넣은
   속성이지 사람이 보는 화면이 아니다.** 세어야 하는 것은
   `getComputedStyle(e).display` 다 (커널 원칙 3).

   그래서 숨김을 «우리 규칙으로» 못 박는다. */
[hidden]{display:none!important}

/* 걸러서 아무것도 안 남았을 때. 목록을 숨기지 않고 «없다» 고 말한다 */
.dnone3{margin:0 0 .9rem;padding:.7rem .8rem;border:1px dashed var(--rule);
 border-radius:var(--p-radius-tag,6px);font-size:.76rem;color:var(--ink-3)}
.dclr3{margin-left:.3rem;font:inherit;font-weight:800;color:var(--dim);
 background:none;border:0;border-bottom:1px solid var(--dim);cursor:pointer;
 padding:0}

/* 출발선 카드가 아래 험지 표로 보내는 한 줄. 「후속 과제」 칩 줄을 대신한다
   (팀장 2026-09-04). 칩이 아니라 문장이다. 여기서 세지 않는다 */
.hn3{display:block;font-size:.74rem;color:var(--dim);font-weight:700;
 margin-top:.7rem}
.hn3::before{content:'↓ ';font-weight:800}
.hk3b{font-size:.64rem;font-weight:800;letter-spacing:.1em;color:var(--ink-3);
 margin:.9rem 0 .45rem}
.fks3{display:flex;flex-wrap:wrap;gap:.4rem}

.fk3:hover{border-color:var(--dim)}
.fk3 b{font-size:.74rem;font-weight:720}
.fk3 i{font-style:normal;font-size:.62rem;color:var(--ink-3)}




.fk3 span{font-size:.68rem;color:var(--cool,#539bf5);font-weight:700}
/* 상한을 넘어 안 그린 것을 «말하는» 칩 (#156). 같은 줄에 서되 항목처럼
   읽히면 안 되므로 테두리를 점선으로 두어 «여기 더 있다» 만 뜻하게 한다. */
.fk3.more,.w3p a.more{border-style:dashed;color:var(--ink-3)}
.fk3.more b,.w3p a.more b{font-weight:700}
/* 겹침 안내는 다음 회차가 그 날일 때만 선다 (#155). 스크립트가 hidden 을
   토글하므로 규칙을 명시해 둔다. 사용자 에이전트 기본값에 기대지 않는다. */
.mclash[hidden]{display:none}
.ht3 b{color:var(--dim);font-size:1.15em}
.evs3{display:grid;gap:.3rem}
.ev3{display:grid;grid-template-columns:5.4rem 1fr;gap:.9rem;align-items:baseline;
 text-decoration:none;color:inherit;padding:.4rem .2rem;border-bottom:1px solid var(--rule)}
.ev3:hover{background:var(--card)}

.eb3 b{font-size:.82rem;font-weight:750;display:block}
.eb3>span>span:first-of-type{font-size:.71rem;color:var(--ink-3)}
.eb3 span{display:block}
.em3{font-size:.62rem;color:var(--ink-3);margin-top:.15rem}
.em3 u{text-decoration:none;border:1px solid var(--rule);border-radius:3px;
 padding:0 .3rem;margin-right:.25rem}
.rrs3{display:grid;grid-template-columns:repeat(auto-fill,minmax(20rem,1fr));
 gap:.05rem .9rem}
.rr3{display:flex;gap:.55rem;align-items:baseline;text-decoration:none;color:inherit;
 padding:.26rem 0}
.rr3:hover .rr3 b{color:var(--dim)}

.rr3 b{font-size:.76rem;font-weight:650;color:var(--ink-2,var(--ink-3));
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mfs{display:flex;flex-wrap:wrap;gap:.4rem;margin:0 0 1rem}

.mf i{font-style:normal;font-weight:700;opacity:.7}
.mf.on{color:var(--dim);border-color:var(--dim)}
.tlw3{display:block;border-left:2px solid var(--rule);padding-left:1.1rem;
 margin-left:.4rem}
.tl3,.tl3.old{position:relative;padding-bottom:1rem;display:flex;gap:.6rem;
 align-items:baseline;flex-wrap:wrap;text-decoration:none;color:inherit}
.tl3::before{content:'';position:absolute;left:-1.47rem;top:.4rem;width:.55rem;
 height:.55rem;border-radius:99px;background:var(--dim)}
.tl3.old{padding-bottom:.55rem}
.tl3.old::before{background:var(--rule)}
.tld3{font-size:.68rem;font-weight:800;color:var(--ink-3);
 font-variant-numeric:tabular-nums;flex:none}

.s-mentor{color:var(--cool,#539bf5);border-color:var(--cool,#539bf5)}
.s-ops{color:var(--note,#d29922);border-color:var(--note,#d29922)}
.s-chosun{color:#f0883e;border-color:#f0883e}
.tlb3{flex:1;min-width:14rem}
.tlt3{font-size:.95rem;font-weight:780;line-height:1.45;display:block}
.tl3.old .tlt3{font-size:.78rem;font-weight:650;color:var(--ink-2,var(--ink-3))}
.tls3{font-size:.68rem;color:var(--ink-3);display:block}

/* ★ 8/31 실측: 부품 통합 정규식이 결합 선택자를 반쯤 먹어 이 아래 규칙이
   통째로 죽었다. 기획 카드가 인라인으로 뭉개진 원인. 복구. */
.pcs3+.ph3,.irs3+.ph3{margin-top:1.6rem}
.pcs3{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));
 gap:var(--p-gap)}
.pc3{display:flex;flex-direction:column;gap:.25rem;min-height:7rem}
.pc3:hover{border-color:var(--dim)}
.pk3{font-size:.58rem;font-weight:800;letter-spacing:.14em;color:var(--dim)}
.pc3 b{font-size:1.02rem;font-weight:830}
.pc3 span{font-size:.74rem;color:var(--ink-3)}
.irs3{display:grid;gap:.1rem}
.ir3{display:flex;gap:.9rem;align-items:baseline;text-decoration:none;color:inherit;
 padding:.3rem .2rem;border-bottom:1px solid var(--rule)}
.ir3 b{font-size:.78rem;font-weight:700;min-width:9rem}
.ir3 span{font-size:.71rem;color:var(--ink-3)}
/* ★ 팀장 지적 (8/31): PC 에서 카드가 왼쪽 절반만 쓰고 오른쪽이 비었다.
   ROS 2 기초 4편이면 2x2 로. 모바일에서는 한 줄로 흐른다. */
.pt3{display:grid;grid-template-columns:1fr 1fr;gap:.6rem 1.1rem;max-width:none}
.pt3 .jt3{display:none}
@media (max-width:760px){.pt3{grid-template-columns:1fr}}
.st3{display:grid;grid-template-columns:2.3rem 1fr;gap:.8rem;align-items:center}
/* 사람 한 줄. 이름 다섯을 카드로 늘어놓지 않는다 (팀장 9/1) */
.tmr3 b{min-width:9rem;display:inline-flex;align-items:baseline;gap:.4rem}
.tmr3 b i{font-style:normal;font-size:.6rem;font-weight:800;letter-spacing:.1em;
  color:var(--dim);background:var(--dim-soft);padding:.08rem .3rem;border-radius:3px}
.tmr3 .tmg3{margin-left:auto;padding-left:1rem;font-size:.63rem;letter-spacing:.06em;
  color:var(--ink-3);white-space:nowrap;text-transform:uppercase}
.tmr3>span:not(.tmg3){flex:1}
.tmr3 .tmw3[data-pos]{color:var(--ink);font-weight:650}
.tmr3 .tmg3 b{font-weight:750;color:var(--ink-2)}
.tmr3 .tma3{font-size:.63rem;letter-spacing:.06em;color:var(--dim);
  white-space:nowrap;padding:0 .9rem;text-transform:uppercase}
/* ★ 2026-09-08 팀장 지적: 모바일에서 이 줄이 잘린다.
   실측(390px 뷰포트 · 같은 출처 iframe · 높이 30000 으로 스크롤바 제거):
   다섯 줄 모두 609px · body scrollWidth 633. 네 번째 칸(담당 실패 지형)이
   화면 밖으로 나가 아예 안 보였다. 원인은 nowrap 둘(.tmg3 · .tma3)과 b 의
   min-width:9rem 이 겹쳐 접힐 자리가 없던 것이다.
   좁은 화면에서만 줄바꿈을 허용하고 최소폭을 푼다. 넓은 화면은 그대로 둔다. */
@media (max-width:560px){
  .tmr3{flex-wrap:wrap;gap:.15rem .6rem}
  .tmr3 b{min-width:0;flex:0 0 100%}
  .tmr3>span:not(.tmg3){flex:1 1 auto;min-width:0}
  .tmr3 .tmg3{margin-left:0;padding-left:0;white-space:normal}
  .tmr3 .tma3{padding:0;white-space:normal}
}
.phn3{font-size:.62rem;font-weight:600;letter-spacing:0;color:var(--ink-3);
  text-transform:none;margin-left:.5rem}
/* 예정 줄: 같은 자리에 서되 «아직 없다» 가 보이게. 번호는 비고, 글은 옅다 */
.st3.soon .sn3{opacity:.45}
.st3.soon .sb3 b{color:var(--ink-2);font-weight:700}
.st3.soon .sb3{border-style:dashed}
.st3.soon .sb3 b::after{content:' 예정';font-size:.62rem;font-weight:800;letter-spacing:.08em;color:var(--ink-3);margin-left:.4rem;vertical-align:.08em}
.sn3{font-family:ui-monospace,Consolas,monospace;font-size:.95rem;font-weight:850;
 color:var(--dim);border:2px solid var(--dim);border-radius:99px;width:2.2rem;
 height:2.2rem;display:grid;place-items:center}

.sb3:hover{border-color:var(--dim)}
.sb3 b{font-size:.9rem;font-weight:780;display:block}
.sb3 span{font-size:.71rem;color:var(--ink-3)}
.jt3{width:2px;height:.9rem;background:var(--rule);margin-left:1.1rem}
.soon3{margin-top:1.2rem;font-size:.73rem;color:var(--ink-3);
 border:1px dashed var(--rule);border-radius:var(--p-radius);padding:.6rem .9rem;max-width:31rem}
.wns3{display:grid;gap:1.3rem}

.wd3{font-size:.74rem;color:var(--ink-3);margin:.25rem 0 .3rem}
.wr3{display:flex;gap:.9rem;align-items:baseline;text-decoration:none;color:inherit;
 padding:.3rem .2rem}
.wr3:hover{background:var(--card)}
.wr3 b{font-size:.8rem;font-weight:720;min-width:10.5rem}
.wr3 span{font-size:.71rem;color:var(--ink-3)}
/* ★ Track A · 실패 험지 5종 (foothold-lab#179). 행 = 지형 · 열 = 단계인 표다.
   색은 실패형 토큰만: 낙상형 --stop · 전진불능형 --note.
   ★ 팀장 2026-09-04 (3차): 5열 카드를 접었다. 카드일 때는 grid-auto-rows:1fr 가
   다섯을 rails 의 키에 맞춰, 문서 하나뿐인 카드 넷이 rails 만큼 늘어났다
   (실측 585px). 표는 한 행의 키가 그 행의 가장 긴 칸까지만 간다.
   그래서 세로 길이가 지형 수에만 비례하고, 「진단 열은 다 찼는데 레시피 열은
   비었다」 가 가로로 한 번에 읽힌다. 카드 배치로는 그 비교가 안 됐다. */
/* 접힌 보드의 요약 줄. 지형 · 성적 · 담당 다섯 칸은 «접혀도» 보인다.
   담당자가 자기 지형으로 가는 길이 목록 길이에 안 묶이게 (2026-09-13) */
.tkcs3{display:flex;flex-wrap:wrap;gap:.4rem;margin:.15rem 0 .6rem}
.tkpin3{display:inline-flex;align-items:baseline;gap:.4rem;
 padding:.34rem .6rem;border:1px solid var(--rule);border-radius:999px;
 background:var(--paper-2,transparent);color:inherit;text-decoration:none;
 font-size:.72rem;line-height:1.2}
.tkpin3:hover{border-color:var(--dim)}
.tkpin3 b{font-weight:800}
.tkcm3{font-weight:850;color:var(--dim);font-variant-numeric:tabular-nums}
.tkco3{color:var(--ink-3);font-weight:600}

/* 보드 자체는 접는다. 펼치기 전 601px 을 먹고 있었다 (실측) */
.tkd3{margin:0 0 .9rem}
.tkds3{cursor:pointer;list-style:none;display:flex;align-items:baseline;
 gap:.5rem;padding:.45rem .1rem;font-size:.74rem;font-weight:800;
 color:var(--ink-2,var(--ink-3));border-top:1px solid var(--rule);
 border-bottom:1px solid var(--rule)}
.tkds3::-webkit-details-marker{display:none}
.tkds3::before{content:'▸';font-size:.8em;color:var(--dim);font-weight:900}
.tkd3[open]>.tkds3::before{content:'▾'}
.tkds3 span{font-weight:600;color:var(--ink-3);font-size:.68rem}
.tkds3:hover{color:var(--dim)}
/* 직접 주소로 들어온 행을 잠깐 표시한다. 색만 바꾸고 자리는 안 바꾼다 */
.tkhit3{outline:2px solid var(--dim);outline-offset:2px}
@media(prefers-reduced-motion:no-preference){
 .tkhit3{transition:outline-color .3s}}

.tkw3{display:block;overflow-x:auto;margin:0 0 .9rem}
.tks3{display:grid;grid-template-columns:minmax(12rem,1.3fr) repeat(4,minmax(0,1fr));
 gap:.3rem;align-items:stretch;min-width:0}
/* 열 머리. 표 맨 윗줄에 한 번만 선다. 칸마다 단계 이름을 되풀이하지 않는다 */
.tkhh3,.tkhs3{font-size:.6rem;font-weight:800;letter-spacing:.12em;
 color:var(--dim);padding:0 .4rem .25rem;border-bottom:1px solid var(--rule)}
.tkhh3{color:var(--ink-3)}
/* 한 지형의 다섯 조각(행 머리 + 칸 넷)을 묶는다. 넓은 화면에서는 묶음이 사라져
   부모 표의 한 행이 되고, 좁은 화면에서는 이 묶음이 그대로 접히는 단위가 된다 */
.tkrow3{display:contents}
/* 행 높이를 고르게 잡는다. 칸에 든 개수가 달라도 표가 흔들리지 않는다.
   2026-09-04 팀장 지시: 틀이 유동적이라 고정으로 깔끔하게. */
.tks3 .tkr3,.tks3 .tkc3{min-height:5.6rem}
/* 행 머리는 사방 1px 로 두른다. 왼쪽만 굵은 «강조 바» 는 금지다
   (DESIGN-GUIDE · brandcheck 가 센다). 색은 테두리 전체로 말한다.
   ★ 두 줄로 눕힌다. 이름 · 실패 양상 · 담당 · 실측 셋을 각자 제 줄에 세웠더니
   행 머리가 140px 이 되고(실측 2026-09-04), 문서 하나뿐인 행 넷이 그 키를
   따라갔다. 카드일 때 rails 가 하던 일을 행 머리가 대신하게 된 셈이다. */
.tkr3{border:1px solid var(--rule);background:var(--card);
 border-radius:var(--p-radius-tag);padding:.32rem .45rem;
 display:flex;flex-direction:column;justify-content:center;gap:.15rem;min-width:0}
.tkrow3.fall .tkr3{border-color:var(--stop)}
.tkrow3.stall .tkr3{border-color:var(--note)}
.tkn3{display:flex;align-items:baseline;gap:.35rem;flex-wrap:wrap}
.tkt3{font-size:.79rem;font-weight:830;line-height:1.3}
.tkt3 i{font-style:normal;font-weight:600;color:var(--ink-3);font-size:.8em}
.tkf3{text-decoration:none;font-size:.57rem;font-weight:800;letter-spacing:.04em;
 border:1px solid;border-radius:var(--p-radius-tag);padding:0 .3rem;
 white-space:nowrap}
.tkrow3.fall .tkf3{color:var(--stop);border-color:var(--stop)}
.tkrow3.stall .tkf3{color:var(--note);border-color:var(--note)}
.tko3{font-size:.62rem;font-weight:700;color:var(--ink-3)!important;
 text-decoration:none;white-space:nowrap}
.tko3:hover{color:var(--dim)!important}
.tkm3{display:flex;align-items:baseline;gap:.4rem;flex-wrap:wrap;line-height:1.35}
.tkm3 span{display:inline-flex;align-items:baseline;gap:.15rem;white-space:nowrap}
.tkm3 b{font-size:.76rem;font-weight:850;font-variant-numeric:tabular-nums}
.tkm3 i{font-style:normal;font-size:.57rem;color:var(--ink-3)}
.fr3{display:flex;align-items:baseline;gap:.55rem;flex-wrap:wrap;
  margin:0 0 .7rem;padding:.55rem .85rem;border:1px solid var(--rule);
  border-left:3px solid var(--accent);border-radius:7px;
  text-decoration:none;color:inherit;background:var(--paper-2)}
.fr3:hover{border-color:var(--accent)}
.fk3{font-size:.6rem;font-weight:800;letter-spacing:.06em;color:var(--accent);
  white-space:nowrap}
.ft3{font-size:.86rem;font-weight:800}
.fs3{font-size:.68rem;color:var(--ink-3);flex:1 1 14rem;min-width:0}
@media (max-width:640px){.fr3{gap:.3rem}}
.tkq3{margin-top:.25rem;font-size:.58rem;line-height:1.45;color:var(--ink-3);max-width:22rem}
/* 빈 칸은 지우지 않는다. 옅은 점선으로 자리를 지켜야 「여기가 비었다」 가 보인다 */
.tkc3{border:1px dashed var(--rule);border-radius:var(--p-radius-tag);padding:.35rem .45rem;
 min-height:2.4rem;display:flex;flex-direction:column;gap:.25rem;min-width:0;opacity:.8}
.tkc3.on{border-style:solid;border-color:var(--dim);background:var(--paper);opacity:1}
/* 빈 칸은 행 높이만큼 늘어나지 않는다. 문서 셋이 든 칸이 그 행을 167px 로
   만들면(실측) 빈 칸은 그만한 투명 상자가 되어 오히려 아무것도 안 보인다.
   위쪽에 작은 점선으로 서면 「여기가 비었다」 가 눈에 잡힌다 */
.tkc3:not(.on){align-self:stretch;display:flex;flex-direction:column;gap:.25rem}
.tkc3:not(.on)>i{display:block;color:var(--ink-3);opacity:.75}
.tke3{font-size:var(--p-body);color:var(--ink-3);opacity:.6}
/* 단계 이름은 열 머리가 말한다. 접힌 화면에서만 칸이 스스로 말한다 */
.tkc3>i{display:none;font-style:normal;font-size:.6rem;font-weight:800;
 letter-spacing:.08em;color:var(--dim)}
.tkc3 a{display:block;font-size:var(--p-body);line-height:1.35;color:inherit;
 text-decoration:none;min-width:0}
.tkc3 a b{font-weight:680;display:-webkit-box;-webkit-line-clamp:2;
 -webkit-box-orient:vertical;overflow:hidden}
.tkc3 a i{font-style:normal;font-size:.6rem;color:var(--ink-3)}
.tkc3 a:hover b{color:var(--dim)}
/* 「외 N건」. 잘린 것이 자기 존재를 주장하는 자리다 (#156) */
.tkmr3{font-weight:800;color:var(--dim)!important}
.tkmr3 b{font-size:.66rem;letter-spacing:.04em}
.tkl3{font-size:var(--p-body);color:var(--ink-3);margin:.15rem 0 .7rem}
.tkx3{font-size:var(--p-body);color:var(--stop);font-weight:700}
/* 여러 지형에 똑같이 걸린 것. 경고가 아니라 «전체 사정» 이라 색을 가른다. */
.tkall3{font-size:var(--p-body);color:var(--ink-2);border-left:3px solid var(--dim);
  padding:.15rem 0 .15rem .55rem;margin:0 0 .5rem}
.tkp3 span,.tkp3 i{margin-left:.35rem}
/* 좁아지면 지형별로 접는다. 열 머리를 접고, 행 머리 아래 네 칸이 2x2 로 선다.
   이때만 칸이 제 단계 이름을 스스로 말한다 */
@media (max-width:820px){
 .tkhh3,.tkhs3{display:none}
 .tks3{grid-template-columns:1fr;gap:.7rem}
 .tkrow3{display:grid;grid-template-columns:1fr 1fr;gap:.3rem;
  border:1px solid var(--rule);border-radius:var(--p-radius);padding:.45rem}
 .tkrow3.fall{border-color:var(--stop)}
 .tkrow3.stall{border-color:var(--note)}
 .tkr3{grid-column:1/-1;border:0;background:none;padding:.1rem .1rem .3rem}
 .tkc3>i{display:block}
}
@media (max-width:460px){.tkrow3{grid-template-columns:1fr}}
@media (max-width:640px){
 
 .ev3{grid-template-columns:4rem 1fr}
 .rr3 b{white-space:normal}
}
</style>'''

RENDER = [('schedule', schedule_html), ('research', research_html),
          ('meeting', meeting_html), ('proposal', proposal_html),
          ('tech', tech_html), ('pipeline', pipeline_html)]


def build(assigned, vault, shell, site):
    """여섯 허브를 v3 뼈대로 쓴다. hubgen.main 이 부른다."""
    import ia
    made = []
    fns = dict(RENDER)
    for key, ko, en, fname, lede in ia.HUBS:
        body_fn = fns.get(key)
        if not body_fn:
            continue
        n = sum(1 for v in assigned.values() if v[0] == key)
        body = ('<h1>%s <span style="font-size:.6em;color:var(--ink-3);'
                'font-weight:600">%s</span></h1>\n<p class="lede">%s</p>\n%s%s'
                % (ko, en, lede, CSS,
                   body_fn(site, assigned) if key == 'meeting'
                   else body_fn(site)))
        io.open(os.path.join(vault, fname), 'w', encoding='utf-8',
                newline='\n').write(shell(ko, body, key))
        made.append((fname, ko, n))
    return made
