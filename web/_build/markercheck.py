# -*- coding: utf-8 -*-
"""주입 블록의 «소유 마커» 가 성한지 전수 검사한다 (mai-os#24 · 빌드 [1.32]).

  왜 생겼나 (2026-09-02 실제 사고)
    `newbadge` 의 옛 판 제거가 `<!--newbadge:vN-->[\\s\\S]*?</script>` 였다.
    표식만 남고 블록이 없는 페이지에서는 «다음 </script>» 까지 지우는데,
    그것이 본문 한참 아래의 남의 스크립트였다.
    brief 이관에서 실제로 터져 **본문 18,000자가 사라졌다.**
    55,294자 페이지가 11,042자가 되어 `</head>` 조차 없어졌다.
    오류도 경고도 없었다 (원칙 2).

    한 생성기를 고치는 것으로는 부족하다. **짝 없는 마커를 가진 어느 페이지에서든**
    같은 일이 난다. 그래서 전 페이지를 여기서 센다 (철칙 4).

  네 가지를 본다 (팀장 지정)
    1. 소유 마커 시작·끝 불일치
    2. 동일 소유 블록 중복
    3. 시작 마커만 남은 경우
    4. 제거 전후 «자기 소유 블록 바깥» 내용 변경

  ★ 4번은 생성기의 제거 함수를 실제로 돌려서 본다. 블록 범위는 이 파일이
    «구조로» 따로 구한다. 제거 함수의 정규식을 그대로 베끼면 같은 눈먼 지점을
    공유해 관문 구실을 못 한다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)


def _tag_span(t, i, tag):
    """t[i:] 가 <tag ...> 로 시작하면 </tag> 까지의 끝 위치. 아니면 -1."""
    m = re.compile(r'\s*<%s\b[^>]*>' % tag).match(t, i)
    if not m:
        return -1
    j = t.find('</%s>' % tag, m.end())
    return -1 if j < 0 else j + len('</%s>' % tag)


def _block_after_marker(t, start, mark, cap, term='</script>', keep=True):
    """마커 뒤 «자기 블록» 의 끝 위치. 못 찾으면 -1 (= 마커만 남음).

    ★ 2026-09-02 정정. 처음에는 «마커 뒤에 style, script 가 «바로» 붙는가» 로
      봤다가 성한 블록을 고아로 잘못 신고했다. 실제 블록에는 그 사이에
      테마 버튼 같은 것이 낀다 (덱 2장에서 오탐).
      그래서 «태그 순서» 가 아니라 «지문과 종결자» 로 본다.
      지문 = 이 소유자만 쓰는 글자 · 종결자 = </script> · 한계 = 블록 최대 길이.
    """
    # ★ 종결자는 소유자마다 다르다. 파비콘 블록에는 </script> 가 아예 없고
    #   `<link>` 두 개로 끝난다. 기본값으로 보면 한참 아래(23,599자) 남의
    #   스크립트를 끝으로 잡고 한계를 넘겨 «고아» 로 잘못 신고한다
    #   (실측 54장 오탐, 2026-09-02).
    if hasattr(term, 'match'):
        m = term.match(t, start)
        return -1 if not m else m.end()
    j = t.find(term, start)
    if j < 0:
        return -1
    end = j + len(term) if keep else j
    span = t[start:end]
    if len(span) > cap:
        return -1
    if mark and mark not in span:
        return -1
    return end


# 소유자 표. 새 주입기가 생기면 여기 한 줄 넣는다.
#   짝마커: 시작·끝 주석이 있는 것 · 조각: 마커 뒤 지문·종결자로 범위가 정해지는 것
#
# ★ 이 표는 «두 방향» 으로 쓰인다 (2026-09-02 · 독립 검수 지적).
#     배포본에서는 이 블록들이 **있어야** 한다 -> markercheck [3.462]
#     손 관리 소스에서는 이 블록들이 **없어야** 한다 -> handpages.check_source
#   두 곳이 각자 문자열 목록을 들면 반드시 갈라진다. 실제로 갈라졌다.
#   handpages 의 목록이 brand:v1 · teamprofiles:v2 · search:v8 · home:v1 ·
#   status:v1 · recent:v1 · stamp:v1 · dark:v1 여덟을 몰라, 생성기 소유 블록이
#   그대로 든 소스를 «순수하다» 고 통과시켰다. 그래서 정본을 여기 하나로 둔다.
OWNERS = [
    {'이름': '전역바',    '종류': '짝', '시작': '<!--gnav:v1-->', '끝': '<!--/gnav:v1-->',
     '주인': 'hubgen'},
    # ★ 2026-09-03 · setup 이관에서 추가. hl_setup 은 마커 없이 손 코드 «안» 을
    #   직접 고쳐 왔다. 그래서 어디까지가 자기 것인지 아무도 몰랐고, 소스 순수성
    #   관문도 그 흔적을 못 봤다. 이제 자기 범위를 짝마커로 선언한다.
    {'이름': '코드 강조',   '종류': '짝', '시작': '<!--hl:v1-->', '끝': '<!--/hl:v1-->',
     '주인': 'hl_setup', '여러벌': True},
    {'이름': '표지',      '종류': '짝', '시작': '<!--home:v1-->', '끝': '<!--/home:v1-->',
     '주인': 'hubgen'},
    {'이름': 'NEW 배지',  '종류': '조각', '시작': re.compile(r'<!--newbadge:v\d+-->'),
     '지문': 'span.fh-new', '한계': 6000, '제거': ('newbadge', 'strip_old'),
     '주인': 'newbadge', '보기': '<!--newbadge:v7-->'},
    {'이름': '다크 토글',  '종류': '짝', '시작': '<!--dark:v1-->', '끝': '<!--/dark:v1-->',
     '앞블록': '<style>html[data-theme', '제거': ('darkmode', 'strip_old'),
     '주인': 'darkmode'},
    # ★ 2026-09-02 추가. 아래 여섯은 표에 없어서 소스 오염을 못 잡았다.
    #   각 소유는 구현에서 확인했다 (marker 정의 · 주입 · 제거 경로).
    {'이름': '파비콘',    '종류': '조각', '시작': re.compile(r'<!--brand:v\d+-->'),
     '지문': 'rel="icon"', '한계': 3000,
     # 마커 뒤에 붙는 <link> 들이 곧 블록이다. </script> 도 </head> 도 아니다
     '종결': re.compile(r'(?:\s*<link\b[^>]*>)+'),
     '주인': 'brandmark', '보기': '<!--brand:v1-->'},
    {'이름': '팀 프로필',  '종류': '짝', '시작': '<!--teamprofiles:v2-->',
     '끝': '<!--/teamprofiles-->', '주인': 'teamprofiles'},
    {'이름': '검색',      '종류': '조각', '시작': re.compile(r'<!--search:v\d+-->'),
     '지문': 'fh-so', '한계': 20000, '주인': 'searchbox', '보기': '<!--search:v8-->'},
    {'이름': '자기 참조',  '종류': '짝', '시작': '<!--status:v1-->', '끝': '<!--/status:v1-->',
     '주인': 'selfclaim'},
    {'이름': '최근',      '종류': '짝', '시작': '<!--recent:v1-->', '끝': '<!--/recent:v1-->',
     '주인': 'recent'},
    {'이름': '판 띠',     '종류': '짝', '시작': '<!--stamp:v1-->', '끝': '<!--/stamp:v1-->',
     '주인': 'stamp'},
    {'이름': 'ia-css',   '종류': 'id', '태그': 'style', 'id': 'ia-css', '주인': 'hubgen'},
    {'이름': 'stamp-css', '종류': 'id', '태그': 'style', 'id': 'stamp-css', '주인': 'stamp'},
    {'이름': '테마 부트',  '종류': 'id', '태그': 'script', 'id': 'fh-theme-boot',
     '주인': 'hubgen'},
]


# ★ 슬롯. 소유 마커와 «다른 표식» 이다 (2026-09-02 팀장 결정).
#   슬롯 = 손 관리 소스가 «생성기야 여기에 넣어라» 고 선언하는 자리.
#          계산 결과(D-day · 제출 수 · 최근 목록)는 한 글자도 담지 않는다.
#   소유 마커 = 생성물에만 있는 것.
#   관문은 둘을 반대로 판정한다.
#          소스   슬롯 합법 · 소유 마커 불법
#          배포본 소유 마커 합법 · 슬롯은 «안 쓰인 것» 이므로 불법
SLOTS = [
    ('최근 슬롯', re.compile(r'<!--slot:recent-->'), 'recent'),
    ('상태 슬롯', re.compile(r'<!--slot:status-->'), 'selfclaim'),
]
SLOT_ANY = re.compile(r'<!--slot:[a-z-]+-->')


def leftover_slots(t):
    """배포본에 남은 슬롯. 생성기가 안 채웠다는 뜻이므로 있으면 안 된다."""
    return sorted(set(SLOT_ANY.findall(t)))


def source_markers():
    """손 관리 «소스» 에 있으면 안 되는 마커·표식 목록. (이름, 정규식).

    (이름, 정규식, 답을 아는 보기) 를 돌려준다. 보기가 있어야 자기시험이 «표가 늘면
    시험도 저절로 는다» 를 지킬 수 있다.

    ★ 정본은 위 OWNERS 하나다. 여기서 파생만 한다.
      handpages 가 자기 문자열 목록을 따로 들면 표가 갈라진다.
      실제로 갈라져서 여덟 마커를 통째로 놓쳤다 (2026-09-02 독립 검수).
    """
    out = []
    for o in OWNERS:
        if o['종류'] == 'id':
            pat = re.compile(r'<%s\b[^>]*\bid="%s"' % (o['태그'], o['id']))
            sample = '<%s id="%s">' % (o['태그'], o['id'])
        else:
            s = o['시작']
            pat = s if hasattr(s, 'search') else re.compile(re.escape(s))
            sample = o.get('보기') or (s if isinstance(s, str) else '')
        out.append((o['이름'], pat, sample))
    return out


def spans(t, own):
    """이 소유자의 블록 범위 목록. (시작, 끝, 완결여부)."""
    out = []
    if own['종류'] == '짝':
        s, e = own['시작'], own['끝']
        i = 0
        while True:
            a = t.find(s, i)
            if a < 0:
                break
            b = t.find(e, a + len(s))
            if b < 0:
                out.append((a, a + len(s), False))       # 시작만 남음
                i = a + len(s)
            else:
                # ★ 소유자에 따라 «마커 앞» 도 자기 블록이다 (darkmode 의 토큰 블록).
                start = a
                pre = own.get('앞블록')
                if pre:
                    k = t.rfind(pre, i, a)
                    if k >= 0:
                        e2 = t.find('</style>', k)
                        if 0 <= e2 < a and not t[e2 + len('</style>'):a].strip():
                            start = k
                out.append((start, b + len(e), True))
                i = b + len(e)
    elif own['종류'] == '조각':
        for m in own['시작'].finditer(t):
            end = _block_after_marker(t, m.end(), own.get('지문'),
                                      own.get('한계', 6000),
                                      own.get('종결', '</script>'),
                                      own.get('종결포함', True))
            if end < 0:
                out.append((m.start(), m.end(), False))
                continue
            # ★ 소유자에 따라 «마커 앞» 도 자기 블록이다.
            #   darkmode 는 토큰 <style>html[data-theme...] 을 마커 바로 앞에 두고
            #   제거할 때 함께 지운다. 관문이 그것을 모르면 정상 동작을
            #   «바깥을 1228자 건드림» 으로 잘못 신고한다 (덱 2장에서 겪었다).
            start = m.start()
            pre = own.get('앞블록')
            if pre:
                k = t.rfind(pre, 0, start)
                if k >= 0:
                    e = t.find('</style>', k)
                    if 0 <= e < start and not t[e + len('</style>'):start].strip():
                        start = k
            out.append((start, end, True))
    else:                                                # id 기반
        pat = re.compile(r'<%s\b[^>]*\bid="%s"[^>]*>' % (own['태그'], own['id']))
        for m in pat.finditer(t):
            j = t.find('</%s>' % own['태그'], m.end())
            out.append((m.start(), m.start() + len(m.group(0)), False) if j < 0
                       else (m.start(), j + len(own['태그']) + 3, True))
    return out


def remove(t, sp):
    """범위 목록을 뒤에서부터 지운다.

    ★ 뒤따르는 공백까지 함께 지운다. 제거 함수들이 정규식 끝에 `\s*` 를 두어
      공백을 함께 먹기 때문이다. 이것을 안 맞추면 «1자 차이» 가 209건 중
      절반으로 나와 진짜 사고를 가린다 (실측).
    """
    for a, b, _ok in sorted(sp, reverse=True):
        j = b
        while j < len(t) and t[j].isspace():
            j += 1
        t = t[:a] + t[j:]
    return t


def check_page(t, name=''):
    """이 페이지의 문제 목록."""
    bad = []
    for s in leftover_slots(t):
        bad.append('%s: 슬롯 %s 가 안 채워졌습니다 (생성기가 자기 자리를 비웠습니다)'
                   % (name, s))
    for own in OWNERS:
        sp = spans(t, own)
        if not sp:
            continue
        # 3) 시작 마커만 남은 경우
        for a, b, ok in sp:
            if not ok:
                bad.append('%s: %s 시작 마커만 남았습니다 (블록이 없습니다)'
                           % (name, own['이름']))
        # 2) 동일 소유 블록 중복
        #   ★ «여러벌» 로 선언한 주인은 예외다 (2026-09-03 · setup 이관).
        #     코드 강조는 코드 블록마다 하나씩 붙는 것이 정상이다. 한 벌을 강요하면
        #     정상 상태가 관문에 걸린다. 예외는 표에 «명시» 해야만 열린다.
        if len(sp) > 1 and not own.get('여러벌'):
            bad.append('%s: %s 블록이 %d개 있습니다 (한 벌이어야 합니다)'
                       % (name, own['이름'], len(sp)))
        # 1) 시작·끝 개수 불일치
        if own['종류'] == '짝':
            n_a, n_b = t.count(own['시작']), t.count(own['끝'])
            if n_a != n_b:
                bad.append('%s: %s 시작 %d개 · 끝 %d개 (짝이 안 맞습니다)'
                           % (name, own['이름'], n_a, n_b))
        # 5) 배포본에 슬롯이 남아 있으면 생성기가 자기 자리를 안 채운 것이다
        #    (조용한 실패다. 화면에서는 그냥 그 절이 없다)
        # 4) 제거 함수가 «자기 블록 바깥» 을 건드리는가
        mod = own.get('제거')
        if mod:
            fn = _stripper(*mod)
            if fn:
                # 성한 블록은 지우고, 짝 없는 마커는 «마커만» 떼는 것이 옳다.
                #   제거 함수가 그렇게 하는지를 본다. 더 지우면 남의 것을 먹은 것이다.
                want = remove(t, sp)
                got = fn(t)
                if got != want:
                    bad.append('%s: %s 제거가 자기 블록 바깥을 %d자 건드립니다'
                               % (name, own['이름'], abs(len(want) - len(got))))
    return bad


def _stripper(modname, fname):
    try:
        sys.path.insert(0, HERE)
        m = __import__(modname)
        return getattr(m, fname, None)
    except Exception:
        return None


def _kat_patterns():
    """★ 소유자 표의 정규식에 제어문자가 박혔는지 본다.

    커널 사례 목록의 그 부류다. heredoc 이 `\b` 를 먹어 **백스페이스(0x08)** 가
    정규식에 들어가면 매치가 조용히 실패한다. 오류는 안 난다.
    실제로 파비콘 종결자가 그렇게 박혀 54장이 «고아» 로 오탐됐다 (2026-09-02).
    """
    for o in OWNERS:
        for key in ('시작', '종결'):
            v = o.get(key)
            src = v.pattern if hasattr(v, 'pattern') else (v if isinstance(v, str) else '')
            bad = [hex(ord(c)) for c in src if ord(c) < 32]
            if bad:
                return False, '%s 의 %s 에 제어문자 %s' % (o['이름'], key, ' '.join(bad))
        for key in ('끝', '지문', '앞블록', '보기'):
            v = o.get(key)
            if isinstance(v, str) and any(ord(c) < 32 for c in v):
                return False, '%s 의 %s 에 제어문자' % (o['이름'], key)
    return True, ''


def _kat():
    """★ 답을 아는 입력."""
    ok, why = _kat_patterns()
    if not ok:
        return False, why
    body = '<p>본문</p><script>남의것</script>'
    good = ('<!--gnav:v1--><nav>x</nav><!--/gnav:v1-->' + body)
    if check_page(good, 'g'):
        return False, '성한 페이지를 문제로 봄: %r' % check_page(good, 'g')
    # 1) 짝 불일치 · 3) 시작만 남음
    r = check_page('<!--gnav:v1--><nav>x</nav>' + body, 'g')
    if not any('시작 마커만' in x for x in r):
        return False, '시작만 남은 것을 못 잡음'
    if not any('짝이 안 맞' in x for x in r):
        return False, '짝 불일치를 못 잡음'
    # 2) 중복
    two = ('<!--gnav:v1--><nav>1</nav><!--/gnav:v1-->'
           '<!--gnav:v1--><nav>2</nav><!--/gnav:v1-->' + body)
    if not any('2개 있습니다' in x for x in check_page(two, 'g')):
        return False, '중복을 못 잡음'
    # ★ «여러벌» 로 선언한 주인은 여러 개여도 통과해야 한다. 그리고 선언하지 않은
    #   주인은 여전히 걸려야 한다. 예외가 전역으로 새면 중복 검사가 죽는다.
    many = ('<pre><!--hl:v1-->a<!--/hl:v1--></pre>'
            '<pre><!--hl:v1-->b<!--/hl:v1--></pre>'
            '<pre><!--hl:v1-->c<!--/hl:v1--></pre>' + body)
    if any('블록이' in x and '코드 강조' in x for x in check_page(many, 'g')):
        return False, '여러벌 주인을 중복으로 잡음'
    if not any('2개 있습니다' in x for x in check_page(two, 'g')):
        return False, '여러벌 예외가 다른 주인에게까지 샘'
    # id 기반
    if not any('시작 마커만' in x for x in check_page('<style id="ia-css">x', 'g')):
        return False, '닫히지 않은 id 블록을 못 잡음'
    if check_page('<style id="ia-css">x</style>' + body, 'g'):
        return False, '성한 id 블록을 문제로 봄'
    # 4) 바깥을 먹는 제거 함수를 잡는가 (일부러 나쁜 함수를 넣어 본다)
    own = {'이름': '시험', '종류': '조각',
           '시작': re.compile(r'<!--t:v1-->'), '지문': 'a{b:c}', '한계': 6000,
           '제거': None}
    src = '<!--t:v1--><style>a{b:c}</style><script>mine</script>' + body
    sp = spans(src, own)
    if len(sp) != 1 or not sp[0][2]:
        return False, '조각 블록 범위를 못 구함'
    if remove(src, sp) != body:
        return False, '조각 블록 제거가 어긋남'
    # 사이에 버튼이 끼어도 완결로 봐야 한다 (덱 2장 오탐에서 배웠다)
    mid = ('<!--t:v1--><style>a{b:c}</style><button id="themeBtn">t</button>'
           '<script>mine</script>' + body)
    sp3 = spans(mid, own)
    if not sp3[0][2]:
        return False, '사이에 버튼이 끼면 고아로 잘못 봄'
    if remove(mid, sp3) != body:
        return False, '버튼 낀 블록 제거가 어긋남'
    # 앞블록도 자기 것으로 세는가
    own2 = dict(own); own2['앞블록'] = '<style>pre'
    pre_src = '<style>pre{a:b}</style><!--t:v1--><style>a{b:c}</style><script>m</script>' + body
    sp4 = spans(pre_src, own2)
    if remove(pre_src, sp4) != body:
        return False, '앞블록을 자기 것으로 못 셈: %r' % remove(pre_src, sp4)[:60]
    # 마커가 고아면 앞블록은 건드리지 않는다
    orphan = '<style>pre{a:b}</style><!--t:v1-->' + body
    if remove(orphan, spans(orphan, own2)) != '<style>pre{a:b}</style>' + body:
        return False, '고아 마커에서 앞블록을 지웠다'
    # 지문이 없으면 내 블록이 아니다
    other = '<!--t:v1--><p>남의 것</p><script>남</script>' + body
    if spans(other, own)[0][2]:
        return False, '지문이 없는데 내 블록으로 봄'
    # 슬롯 · 배포본에 남으면 잡고, 없으면 조용하다
    if not any('슬롯' in x for x in check_page('<p>x</p><!--slot:recent-->', 'g')):
        return False, '안 채워진 슬롯을 못 잡음'
    if any('슬롯' in x for x in check_page('<p>x</p>', 'g')):
        return False, '슬롯이 없는데 있다고 함'
    # 마커만 있으면 «완결 아님» 이어야 한다
    sp2 = spans('<!--t:v1-->' + body, own)
    if sp2[0][2]:
        return False, '마커만 있는데 완결로 봄'
    return True, ''


def main(target=None):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    target = target or VAULT
    bad, n = [], 0
    for f in sorted(os.listdir(target)):
        if not f.endswith('.html'):
            continue
        n += 1
        bad += check_page(io.open(os.path.join(target, f), encoding='utf-8',
                                  errors='replace').read(), f)
    if n < 5:
        print('  [!] 검사한 페이지가 %d장뿐입니다. 검사가 무의미합니다' % n)
        return False
    if bad:
        print('  🔴 소유 마커 이상 %d건 (%d장 검사)' % (len(bad), n))
        for b in bad[:15]:
            print('     ' + b)
        if len(bad) > 15:
            print('     ... 외 %d건' % (len(bad) - 15))
        print('     짝 없는 마커는 제거 정규식이 남의 본문을 먹는 자리입니다')
        return False
    print('  자기시험 통과 · %d장 · 소유자 %d종 · 마커 이상 없음'
          % (n, len(OWNERS)))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else None) else 1)
