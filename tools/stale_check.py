# -*- coding: utf-8 -*-
"""페이지가 「지금」이라고 말하는 것이 진짜 지금인지 잰다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-15 02:40
> 근거: 실측 (배포본 141장 · 본문에서 「이번 주 Wxx」 「최종 갱신」 「D-n」 을 뽑아 오늘과 대조)
> 요지: 자동화가 「성공」이어도 화면이 옛 상태를 말하면 그것이 결함이다
> 상태: 확정

## 팀장 지적 (2026-09-15)

> 자동화 시스템을 우리가 갖춰놨다고 했는대도 불구하고 업데이트가 안되어있고
> 죽어있는 문서가 되어있다는 점이 문제야.

맞다. 우리 관문은 **「자동화가 돌았나」** 만 봤다. 그것은 대리 신호다.
결과는 **「화면이 지금을 말하나」** 다. 실제로 재 보니 이렇게 어긋나 있었다.

    일정 허브     「이번 주 W36」          오늘 W38 · 2주 뒤짐
    일정 허브     MVP 「D-16」            오늘 D-15 · 빌드 때 박혀 매일 틀려짐
    결정 로그     「이번 주 W35」          3주 뒤짐
    백과          「최종 갱신 2026-07-30」 47일 전

전부 오류 0건으로 배포됐다.

## 무엇을 재나

페이지가 스스로 주장하는 «지금» 만 본다. 세 가지다.

    이번 주 Wxx      오늘의 ISO 주차와 같아야 한다
    D-n              오늘 기준으로 그 날짜까지의 날수와 같아야 한다
    최종 갱신 날짜    너무 오래면 알린다 (막지는 않는다 · 기록 문서는 오래된 것이 맞다)

**날짜가 옛것인 문서 전부를 잡으려는 것이 아니다.** 회의록은 오래된 것이 맞다.
「지금」이라고 «말한» 자리만 본다.

## 이 관문이 «못» 보는 자리

이 검사는 **정적 HTML** 을 읽는다. 그런데 D-day 는 브라우저가 다시 센다.
그래서 **관문이 보는 값과 사람이 보는 값이 다르다.**

2026-09-15 에 실제로 그랬다. 정적 값은 D-15 로 맞아서 관문이 통과시켰는데,
화면에는 D-14 가 떴다. 내 JS 가 마감일을 `+09:00` 으로 파싱해 UTC 로 하루
앞이 되었고, 현재 시각은 KST 로 민 일련번호라 **기준이 다른 둘을 뺀** 것이다.

그래서 `dday_js_matches()` 로 **같은 계산을 파이썬으로도 해 본다.** 두 값이
어긋나면 브라우저 쪽 식이 틀린 것이다. 브라우저를 띄우지 않고도 잡힌다.
"""
import datetime
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)

_TAG = re.compile(r'(?s)<(script|style)\b.*?</\1>|<[^>]+>')
_WEEK = re.compile(r'(이번\s*주|금주|현재\s*주)[^0-9W]{0,6}W(\d{2})')
_DDAY = re.compile(r'D-(\d{1,3})[^0-9]{0,40}?(\d{1,2})\s*월\s*(\d{1,2})\s*일')
# ★ 2026-09-16. 「최신」 하나로 잡았더니 setup.html 의
#   「「최신」이라는 게 안정판이 아닙니다 · 2026-08-05 릴리스 목록 조회」를
#   갱신일로 읽었다. 그날 조회한 «기록» 이지 지금을 말한 것이 아니다.
#   배포 전수로 세어 넓은 패턴만 잡는 것이 그 한 곳뿐이라 좁혔다.
_UPD = re.compile(r'(최종 갱신|마지막 갱신|최신 갱신|갱신일)'
                  r'[^\n]{0,24}?(20\d\d)[-./](\d{1,2})[-./](\d{1,2})')

STALE_DAYS = 21          # 「최종 갱신」이 이보다 오래면 알린다


def text_of(path):
    raw = io.open(path, encoding='utf-8', errors='ignore').read()
    return re.sub(r'\s+', ' ', _TAG.sub(' ', raw))


_NEAR_DATE = re.compile(r'(\d{1,2})\s*[-/월]\s*(\d{1,2})')

# 브라우저가 D-day 를 다시 세는 식. 여기서 뽑아 파이썬으로 똑같이 돌려 본다.
_JS_DUE = re.compile(r"Date\.parse\(due\+'T00:00:00(Z|\+09:00)'\)")
_JS_NOW = re.compile(r'Date\.now\(\)\s*\+\s*9\s*\*\s*3600000')


def dday_js_matches(site, today):
    """브라우저 쪽 D-day 식이 달력 빼기와 같은 답을 내나.

    관문은 정적 HTML 을 읽는데 사람은 JS 결과를 본다. 두 층이 다르면
    관문이 통과시켜도 화면은 틀린다. 실제로 하루를 잃은 적이 있다.
    브라우저를 안 띄우고, **식의 기준이 맞는지**로 본다.
    """
    bad = []
    for name in sorted(os.listdir(site)):
        if not name.endswith('.html'):
            continue
        raw = io.open(os.path.join(site, name), encoding='utf-8',
                      errors='ignore').read()
        if 'data-due=' not in raw:
            continue
        m_due, m_now = _JS_DUE.search(raw), _JS_NOW.search(raw)
        if not (m_due and m_now):
            continue
        # 현재 시각은 KST 로 «민» 일련번호다. 마감일도 같은 공간에서 읽어야
        # 한다. `+09:00` 을 붙이면 UTC 로 하루 앞이 되어 하루를 잃는다.
        if m_due.group(1) != 'Z':
            bad.append('%s · 마감일을 %s 로 읽어 하루를 잃습니다'
                       % (name, m_due.group(1)))
    return bad


# ★ 2026-09-16 신설. 정적 D-day 를 «미리 그려둔 자리» 로 볼 수 있나.
#   페이지가 data-due 를 들고 JS 로 다시 세면 사람은 언제나 맞는 수를 본다.
#   그 자리를 「낡았다」고 막으면 빌드한 다음 날부터 매일 실패한다.
#   식이 틀렸는지는 dday_js_matches() 가 따로 잡으므로 눈이 머는 것이 아니다.
def dday_is_live(raw):
    """이 페이지가 D-day 를 열 때마다 다시 세나."""
    return bool('data-due=' in raw and _JS_DUE.search(raw) and _JS_NOW.search(raw))


def _is_record(t, pos, week, year, look=90):
    """그 「이번 주 Wxx」가 «그날의 기록» 인가.

    결정 로그는 `| 08-28 | ... 이번 주 = W35 ...` 처럼 쓴다. 거기서 「이번 주」는
    **그 줄의 날짜 기준** 이지 오늘 기준이 아니다. 앞쪽 가까이에 날짜가 있고
    그 날짜의 주차가 적힌 주차와 같으면 기록으로 본다.
    """
    head = t[max(0, pos - look):pos]
    for m in _NEAR_DATE.finditer(head):
        try:
            d = datetime.date(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            continue
        if d.isocalendar()[1] == week:
            return True
    return False


def findings(path, today):
    """이 페이지가 「지금」을 잘못 말하는 자리들. (심각도, 말) 목록."""
    raw = io.open(path, encoding='utf-8', errors='ignore').read()
    t = re.sub(r'\s+', ' ', _TAG.sub(' ', raw))
    live = dday_is_live(raw)
    out = []
    nw = today.isocalendar()[1]

    for m in _WEEK.finditer(t):
        w = int(m.group(2))
        if w == nw:
            continue
        # ★ 2026-09-15. 첫 판이 오탐을 냈다. 결정 로그의
        #   「08-28 | 주차 기준은 ISO 월요일 시작. 이번 주 = W35 (8/24~8/30)」
        #   는 **그날 정한 것의 기록**이지 지금 주장이 아니다.
        #   앞쪽에 날짜가 있고 그 날짜의 주차와 맞으면 기록으로 본다.
        if _is_record(t, m.start(), w, today.year):
            continue
        out.append(('막음', '「%s W%02d」 인데 오늘은 W%02d (%d주 뒤짐)'
                    % (m.group(1), w, nw, nw - w)))

    for m in _DDAY.finditer(t):
        said = int(m.group(1))
        try:
            d = datetime.date(today.year, int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        real = (d - today).days
        if real >= 0 and said != real and not live:
            out.append(('막음', '「D-%d」(%d월 %d일) 인데 오늘 기준 D-%d'
                        % (said, d.month, d.day, real)))

    for m in _UPD.finditer(t):
        try:
            d = datetime.date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
        except ValueError:
            continue
        age = (today - d).days
        if age >= STALE_DAYS:
            out.append(('알림', '「%s %s」 %d일 전' % (m.group(1), d, age)))

    return out


def _selftest():
    """관문 자신을 먼저 시험한다. 없는 결함을 만들어 잡히는지 본다."""
    import tempfile
    import shutil
    today = datetime.date(2026, 9, 15)          # W38
    root = tempfile.mkdtemp(prefix='stale-')
    try:
        cases = [
            ('ok-week.html', '<p>이번 주 · W38 입니다</p>', 0),
            ('bad-week.html', '<p>이번 주 · W36 입니다</p>', 1),
            ('ok-dday.html', '<p>D-15 MVP 9월 30일</p>', 0),
            ('bad-dday.html', '<p>D-16 MVP 9월 30일</p>', 1),
            ('bad-upd.html', '<p>최종 갱신 2026-07-30</p>', 1),
            # ★ 그날 조회한 기록은 갱신일이 아니다 (setup.html 오탐)
            ('rel-list.html',
             '<p>「최신」이라는 게 안정판이 아닙니다. 2026-08-05 '
             '릴리스 목록 조회 결과입니다.</p>', 0),
            ('upd-word.html', '<p>갱신일 2026-07-30</p>', 1),
            # ★ 브라우저가 다시 세는 D-day 는 정적 값이 낡아도 넘긴다.
            #   그러나 다시 안 세는 페이지는 «여전히» 잡는다.
            #   한쪽만 시험하면 관문을 눈멀게 해도 통과한다.
            ('live-dday.html',
             '<p data-due="2026-09-30">D-16 MVP 9월 30일</p>'
             + "<script>var d=Date.parse(due+'T00:00:00Z');var n=Date.now()+9*3600000;</script>", 0),
            ('dead-dday.html', '<p>D-16 MVP 9월 30일</p>', 1),
            ('ok-upd.html', '<p>최종 갱신 2026-09-14</p>', 0),
            # 기록 문서의 옛 날짜는 「지금」을 말한 것이 아니다
            ('record.html', '<p>2026-08-09 회의록. 그날 정한 것</p>', 0),
            # 스크립트 안의 글자는 화면이 아니다
            ('script.html', '<script>var s="이번 주 W36"</script><p>정상</p>', 0),
            # ★ 그날의 기록. 앞의 날짜(08-28)의 주차가 W35 라 맞는 말이다
            ('record-week.html',
             '<td>08-28</td><td>주차 기준은 ISO 월요일 시작. 이번 주 = W35 (8/24~8/30)</td>',
             0),
            # 날짜가 있어도 그 날짜의 주차와 «안 맞으면» 기록이 아니다
            ('wrong-week.html', '<td>09-14</td><td>이번 주 W30 입니다</td>', 1),
        ]
        bad = []
        for name, html, want in cases:
            p = os.path.join(root, name)
            io.open(p, 'w', encoding='utf-8').write(html)
            got = len(findings(p, today))
            if got != want:
                bad.append('%s (기대 %d · 결과 %d)' % (name, want, got))
        if bad:
            print('  [!] 자기시험 실패: %s' % ' · '.join(bad))
            return False
        print('  자기시험 %d/%d 통과 (주차 · D-day · 갱신일 · 기록문서 제외 · 스크립트 제외)'
              % (len(cases), len(cases)))
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check(site, today=None):
    today = today or datetime.date.today()
    rows = []
    for name in sorted(os.listdir(site)):
        if not name.endswith('.html'):
            continue
        f = findings(os.path.join(site, name), today)
        if f:
            rows.append((name, f))

    # 브라우저가 다시 세는 D-day 의 «식» 도 본다. 정적 값만 보면 못 잡는다.
    js_bad = dday_js_matches(site, today)
    for msg in js_bad:
        rows.append((msg.split(' · ')[0], [('막음', msg.split(' · ', 1)[1])]))

    block = [(n, f) for n, f in rows if any(s == '막음' for s, _ in f)]
    warn = [(n, f) for n, f in rows if n not in {b[0] for b in block}]

    print('  오늘 %s (W%02d) 기준 · 「지금」을 말하는 자리를 다시 잼'
          % (today, today.isocalendar()[1]))
    print('  어긋난 페이지 %d장 (막음 %d · 알림 %d)'
          % (len(rows), len(block), len(warn)))

    for n, f in block:
        for sev, msg in f:
            if sev == '막음':
                print('     [X] %-34s %s' % (n, msg))
    for n, f in warn:
        for sev, msg in f:
            print('     [!] %-34s %s' % (n, msg))

    return not block


if __name__ == '__main__':
    if not _selftest():
        raise SystemExit(1)
    site = (sys.argv[1] if len(sys.argv) > 1 else
            os.path.join(LAB, '..', 'foothold-site'))
    raise SystemExit(0 if check(os.path.abspath(site)) else 1)
