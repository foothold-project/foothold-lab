# -*- coding: utf-8 -*-
"""표지에 「최근 올라온 것」 다섯을 띄운다.

★ 왜 (2026-08-29)

  팀장 지적. 「메인에 최근 업로드된 5개 문서를 빠르게 확인 가능하게 한 것 좋았는데
  왜 반영 안 했어」

  맞다. 표지에는 「연구 기록」 최신 3편만 있었고 그것도 **연구 문서만**이었다.
  회의록이 올라와도, 가이드가 올라와도, 결정이 기록돼도 표지는 모른다.
  팀원이 「내가 올린 게 반영됐나」를 보러 오는데 그 답이 없다.

  **문서 종류를 안 가리고 최근 다섯을 띄운다.**

날짜를 어디서 얻나
  `newbadge.first_added()`. 공개 저장소에서 그 파일이 **처음 추가된 날**이다.
  회의록만 예외로 파일명의 회의 날짜를 쓴다(지난 회의를 뒤늦게 올려도
  「오늘 등록」이 되지 않게). 그 규칙을 여기서 다시 만들지 않고 그대로 빌린다.

무엇을 빼나
  표지 자신 · 허브 · 목록 페이지. 「최근 올라온 것」이 아니라 늘 있는 것들이다.
"""
import io
import os
import re
import sys
import buildtime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MARK_A, MARK_B = '<!--recent:v1-->', '<!--/recent:v1-->'

# ★ 2026-09-02 (mai-os#24). 슬롯은 소유 마커와 다른 표식이다.
#   슬롯 = 손 관리 소스가 «여기에 넣어라» 고 선언하는 자리. 목록은 없다.
#   소유 마커 = 생성물에만 있는 것. 소스에 있으면 오염이다.
SLOT = '<!--slot:recent-->'

# 늘 있는 것. 「최근 올라온 것」이 아니다.
SKIP = ('index.html', 'research.html', 'vercel.json')
# ★ 팀장 컨펌 9/1: 소개는 «새 소식» 이 아니다.
#   「최근 올라온 것」 이 답하는 질문은 «내가 마지막으로 본 뒤 뭐가 바뀌었나» 다.
#   팀원 프로필과 팀 인트로는 늘 있어야 하는 상설 페이지라 여기 뜨면 안 된다.
#   (실제로 늦게 올린 오래된 정보가 표지 맨 앞에 왔다.)
#   파일 예외 목록을 만들지 않는다. 예외는 썩는다. 접두어 규칙이라 팀원이
#   늘어도 손댈 것이 없다. 이 페이지들의 정문은 기획 허브의 «팀» 절이다.
SKIP_PREFIX = ('hub-', 'team-')

# CSS 는 `hubgen.CSS` (id="ia-css") 안에 있다. 스타일이 두 자리에 있으면 갈라진다.


def _title(path):
    t = io.open(path, encoding='utf-8', newline=None, errors='replace').read()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', t, re.S)
    if not m:
        m = re.search(r'<title>([^<·]+)', t)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', m.group(1))).strip() if m else path


def today_iso():
    import datetime
    return buildtime.today().isoformat()


def pick(vault, site, assigned, limit=5):
    """[(파일, 날짜, 허브키, 제목)] 최신순.

    ★ 배포 대상만 본다. `assigned` 에 없는 파일은 사이트로 나가지 않으므로
      목록에 넣으면 죽은 링크가 된다.
    ★ git 에 아직 없는 파일(= 이번 배포로 처음 나가는 것)은 오늘로 본다.
      건너뛰면 «막 올린 것이 최근 목록에 없는» 정반대 결과가 된다.
    """
    import newbadge
    now = today_iso()
    rows = []
    for f in sorted(assigned):
        if not f.endswith('.html') or f in SKIP or f.startswith(SKIP_PREFIX):
            continue
        if assigned[f][0].startswith('_'):
            continue                       # 띠·바로가기는 늘 있는 것
        if not os.path.isfile(os.path.join(vault, f)):
            continue
        d = newbadge.first_added(site, f) or now
        rows.append((f, d, assigned[f][0], _title(os.path.join(vault, f))))
    rows.sort(key=lambda r: (r[1], r[0]), reverse=True)
    return rows[:limit]


def block(vault, site, assigned, today=None, limit=5):
    import ia
    today = today or today_iso()
    names = {k: ko for k, ko, _en, _f, _l in ia.HUBS}
    rows = pick(vault, site, assigned, limit)
    if not rows:
        return ''
    out = []
    for f, d, hub, title in rows:
        # ★ 9/1 팀장 실측: 「눌러서 들어갔다 나왔는데 NEW 가 안 없어진다」.
        #   여기가 원인이다. NEW 를 «글자로 박아» 뒀으니 배지 시스템이 손댈
        #   수가 없었다. 배지에 넘긴다: data-added 만 달면 newbadge 가
        #   «등록 7일 이내 + 아직 안 본 것» 을 스스로 판정하고, 한 번 열면 끈다.
        out.append('<a class="rcard" data-added="%s" href="%s">'
                   '<span class="rd">%s</span>'
                   '<span class="rk">%s</span>'
                   '<span class="rt">%s</span></a>'
                   % (d, f, d[5:].replace('-', '/'),
                      names.get(hub, '문서'), title))
    return (MARK_A +
            '\n<h2 class="sec">최근 올라온 것 <span class="en">Recent</span></h2>\n'
            '<p class="lede" style="margin:-2px 0 12px;font-size:.82rem;'
            'color:var(--ink-3)">종류를 가리지 않고 최근 %d개. '
            '내가 올린 것이 반영됐는지 여기서 본다.</p>\n'
            '<div class="recent">%s</div>\n' % (len(rows), ''.join(out))
            + MARK_B)


def _kat(vault, site, assigned):
    """★ 원칙 1. 답을 아는 입력으로 도구를 먼저 시험한다.

    여기서 답을 아는 것 셋이다.
      · 회의록은 파일명 날짜를 쓴다 (newbadge 의 예외를 그대로 빌렸는지)
      · 허브·표지는 목록에 들어오면 안 된다
      · 최신순으로 내려가야 한다
    """
    rows = pick(vault, site, assigned, limit=5)
    if len(rows) < 3:
        return False, '최근 문서를 %d개밖에 못 골랐다' % len(rows)
    for f, d, _h, _t in rows:
        if f in SKIP or f.startswith(SKIP_PREFIX):
            return False, '늘 있는 것(%s)이 목록에 들었다' % f
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', d or ''):
            return False, '%s 의 날짜가 이상하다: %r' % (f, d)
    ds = [r[1] for r in rows]
    if ds != sorted(ds, reverse=True):
        return False, '최신순이 아니다: %s' % ds
    m = next((r for r in rows if r[0].startswith('meeting-')), None)
    if m and m[1] != '%s-%s-%s' % re.match(r'meeting-(\d{4})(\d{2})(\d{2})-',
                                           m[0]).groups():
        return False, '회의록 날짜가 파일명과 다르다 (%s -> %s)' % (m[0], m[1])
    return True, ''


def inject(vault, site, assigned, today=None):
    """표지의 「현재 상태」 절 바로 다음에 넣는다."""
    ok, why = _kat(vault, site, assigned)
    if not ok:
        print('  [!] 최근 올라온 것 자기시험 실패: %s' % why)
        return False
    p = os.path.join(vault, 'index.html')
    if not os.path.isfile(p):
        return False
    s = io.open(p, encoding='utf-8', newline=None).read()
    sec = block(vault, site, assigned, today)
    if not sec:
        print('  [!] 최근 문서를 못 골랐습니다')
        return False
    if MARK_A in s and MARK_B in s:
        a, b = s.index(MARK_A), s.index(MARK_B) + len(MARK_B)
        if s[a:b] == sec:
            print('  최근 올라온 것: 그대로')
            return True
        s = s[:a] + sec + s[b:]
    else:
        # ★ 「연구 기록」 h2 앞이 아니라 그것을 감싼 «마커 앞» 이다 (2026-08-29).
        #   h2 앞에 넣으면 `<!--research:auto-->` 마커 안으로 들어가, 다음 빌드가
        #   그 절을 다시 그릴 때 이 블록째 지워진다. 실측으로 잡았다.
        # 슬롯이 있으면 그 자리를 «대체» 한다. 첫 빌드부터 여기서 만든다
        if SLOT in s:
            s = s.replace(SLOT, sec, 1)
            io.open(p, 'w', encoding='utf-8', newline=chr(10)).write(s)
            n = sec.count('<a href=')
            print('  최근 올라온 것 %d개 (슬롯에서 생성)' % n)
            return True
        anchor = next((a for a in ('<!--research:auto-->',
                                   '<h2 class="sec">연구 기록') if a in s), None)
        if not anchor:
            print('  [!] 표지에 삽입 지점을 못 찾음')
            return False
        i = s.index(anchor)
        s = s[:i] + sec + '\n\n' + s[i:]
    io.open(p, 'w', encoding='utf-8', newline=chr(10)).write(s)
    n = sec.count('<a href=')
    print('  최근 올라온 것 %d개 주입' % n)
    return True
