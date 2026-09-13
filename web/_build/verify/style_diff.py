# -*- coding: utf-8 -*-
"""전환 전후 계산 스타일을 견준다 (mai-os#24 필수 관문).

  왜 계산 스타일인가
    CSS 문자열이 같다는 것은 화면이 같다는 뜻이 아니다. 어느 규칙이 이기는지,
    상속이 어떻게 되는지는 브라우저만 안다. 그래서 «브라우저가 계산한 값» 을 잰다.

  왜 스크린샷만으로는 안 되나
    OS 별 폰트 렌더링이 달라 픽셀 diff 는 늘 어긋난다. 그래서 수치 비교를
    필수 관문으로 두고, 스크린샷은 사람이 보는 보완 증거로 쓴다 (팀장 결정).

  허용 차이
    override 로 «바꾸기로 한» 것만 허용한다. 그 목록은 인자로 받는다.
    목록에 없는 차이가 하나라도 있으면 실패다.
"""
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, 'snap')


MIN_ELEMENTS = 30          # 이보다 적으면 비교가 무의미하다고 본다

# 스냅샷이 반드시 가져야 하는 것. 하나라도 없으면 «잰 적 없는 것» 이다
_META_INT = ('w', 'h', 'count')
_META_POSITIVE = ('w', 'h')        # 0 이하 창은 없다. 잰 적 없다는 뜻이다
_NEED_PROP = ('width', 'height', 'color', 'display', 'position')


def _finite_number(x):
    """진짜 «잰 수» 인가. bool 과 NaN·Infinity 를 걸러낸다.

    ★ 둘 다 조용히 새어든다 (2026-09-02 독립 검수 2차 지적).
      · 파이썬에서 bool 은 int 의 하위형이라 isinstance(True, int) 가 참이다.
        그래서 _box 가 [True, False, True, True] 여도 «숫자 4개» 로 보였다.
      · json.loads 는 아무 설정 없이 NaN·Infinity·-Infinity 토큰을 받는다.
        NaN 은 자기 자신과도 다르므로 «같은 것을 다르다» 고 만들고,
        양쪽 다 NaN 이면 오히려 차이로 세어져 판정을 뒤집는다.
      둘 다 «재지 않았다» 는 신호다. 수로 인정하지 않는다.
    """
    if isinstance(x, bool):
        return False
    if not isinstance(x, (int, float)):
        return False
    return math.isfinite(x)


def _schema_error(s):
    """스냅샷의 스키마와 «의미» 가 성한지. 성하면 None, 아니면 이유.

    모양만 보면 뜻이 없는 스냅샷이 통과한다. 값이 실제로 무엇을 말하는지까지 본다.
    """
    if not isinstance(s, dict):
        return '최상위가 사전이 아닙니다'
    for k in ('meta', 'el'):
        if k not in s:
            return '%s 가 없습니다' % k
    if not isinstance(s['meta'], dict) or not isinstance(s['el'], dict):
        return 'meta 나 el 이 사전이 아닙니다'
    for k in _META_INT:
        v = s['meta'].get(k)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            return 'meta.%s 가 음이 아닌 정수가 아닙니다 (%r)' % (k, v)
    for k in _META_POSITIVE:
        if s['meta'][k] <= 0:
            return ('meta.%s 가 0 이하입니다 (%r). 그런 창에서는 아무것도 잴 수 없습니다'
                    % (k, s['meta'][k]))
    th = s['meta'].get('theme')
    if not isinstance(th, str) or not th.strip():
        return ('meta.theme 가 비어 있습니다 (%r). 어느 테마로 쟀는지 모르면 '
                '견줄 자격이 없습니다' % (th,))
    for key, v in s['el'].items():
        if not isinstance(v, dict):
            return '%s 의 값이 사전이 아닙니다' % key
        miss = [p for p in _NEED_PROP if p not in v]
        if miss:
            return '%s 에 필수 속성이 없습니다: %s' % (key, ' '.join(miss))
        # ★ 있기만 하면 되는 게 아니다. null 이나 빈 문자열은 «못 쟀다» 는 뜻이고,
        #   양쪽이 똑같이 못 쟀으면 차이 0 으로 조용히 통과한다 (원칙 2).
        blank = [p for p in _NEED_PROP
                 if not isinstance(v[p], str) or not v[p].strip()]
        if blank:
            return ('%s 의 필수 속성이 비었거나 문자열이 아닙니다: %s'
                    % (key, ' '.join('%s=%r' % (p, v[p]) for p in blank)))
        box = v.get('_box')
        if not isinstance(box, list) or len(box) != 4:
            return '%s 의 _box 가 숫자 4개가 아닙니다' % key
        bad = [x for x in box if not _finite_number(x)]
        if bad:
            return ('%s 의 _box 에 잰 수가 아닌 값이 있습니다: %s'
                    % (key, ' '.join(repr(x) for x in bad)))
    return None


def _reject_constant(c):
    raise ValueError('스냅샷에 %s 가 들어 있습니다. 잰 값이 아닙니다' % c)


def load(name):
    p = os.path.join(SNAP, name + '.json')
    if not os.path.exists(p):
        return None
    # ★ json 은 아무 설정 없이 NaN·Infinity 토큰을 float 으로 받아들인다.
    #   파일 층위에서 한 번, 스키마 검사에서 또 한 번 막는다
    #   (철칙 4 · 관문은 한 층위만 보면 안 된다).
    return json.load(io.open(p, encoding='utf-8'), parse_constant=_reject_constant)


def compare(before, after, allow=()):
    """(차이목록, 요약). allow 는 '요소키/속성' 문자열의 집합."""
    a, b = before['el'], after['el']
    diffs = []
    for k in sorted(set(a) | set(b)):
        if k not in a:
            diffs.append((k, '(요소 없음)', '(생김)', '')); continue
        if k not in b:
            diffs.append((k, '(있음)', '(사라짐)', '')); continue
        for p in sorted(set(a[k]) | set(b[k])):
            va, vb = a[k].get(p), b[k].get(p)
            if va != vb:
                diffs.append((k, va, vb, p))
    kept = [d for d in diffs if ('%s/%s' % (d[0], d[3])) not in allow]
    return kept, {'요소': (len(a), len(b)), '전체차이': len(diffs), '허용밖': len(kept)}


def gate(before, after, allow=(), name=''):
    """필수 관문. 통과 조건 넷을 한 자리에서 본다."""
    ok = True
    if before is None or after is None:
        print('  [!] %s 스냅샷이 없습니다' % name)
        return False
    # 0) 스키마가 성한가 · 그리고 meta.count 가 «실제 요소 수» 와 맞는가
    #
    #    ★ 2026-09-02 독립 검수가 잡은 허점. 전에는 meta.count 만 보고
    #      「30개 넘으니 유의미하다」고 판정했다. el 이 비어 있는데 count 를
    #      40 이라고 적은 스냅샷을 넣으면 요소 (0,0) · 차이 0 으로 **통과**했다.
    #      대리 신호(자기가 적은 숫자)를 결과로 받은 것이다 (원칙 3).
    #      이제 실제로 센다.
    for lbl, s in (('이전', before), ('이후', after)):
        bad = _schema_error(s)
        if bad:
            print('  [!] %s %s 스냅샷 스키마가 틀렸습니다: %s' % (name, lbl, bad))
            return False
        real, said = len(s['el']), s['meta'].get('count')
        if real != said:
            print('  [!] %s %s 스냅샷의 meta.count(%s) 가 실제 요소 수(%d) 와 다릅니다'
                  % (name, lbl, said, real))
            return False
    # 1) 같은 «조건» 에서 잰 것인가. 아니면 비교 자체가 무의미하다
    for f in ('w', 'h'):
        if before['meta'][f] != after['meta'][f]:
            print('  [!] %s 뷰포트가 다릅니다 (%s: %s vs %s)'
                  % (name, f, before['meta'][f], after['meta'][f]))
            return False
    # ★ 테마가 다르면 색·배경이 통째로 달라진다. 그 차이를 이관 탓으로 읽으면
    #   틀린 결론이 나고, 반대로 «둘 다 다른 테마» 로 잰 것을 모르면 차이 0 이
    #   무엇도 증명하지 못한다 (2026-09-02 독립 검수 2차 지적).
    if before['meta']['theme'] != after['meta']['theme']:
        print('  [!] %s 테마가 다릅니다 (%r vs %r). 다른 테마끼리는 견줄 수 없습니다'
              % (name, before['meta']['theme'], after['meta']['theme']))
        return False
    # 2) 빈 style/media 껍데기 0
    if after['meta'].get('emptyStyle'):
        print('  🔴 %s 빈 style/media 껍데기 %d개' % (name, after['meta']['emptyStyle']))
        ok = False
    # 3) 비교가 유의미한 크기인가 (원칙 2: 빈 비교가 통과로 보이지 않게)
    #    ★ meta 가 아니라 «실제 el» 을 센다. 양쪽 다 본다
    for lbl, s in (('이전', before), ('이후', after)):
        if len(s['el']) < MIN_ELEMENTS:
            print('  [!] %s %s 스냅샷 요소가 %d개뿐입니다 (최소 %d). 비교가 무의미합니다'
                  % (name, lbl, len(s['el']), MIN_ELEMENTS))
            return False
    # 4) 허용 밖 차이 0
    kept, summary = compare(before, after, allow)
    print('  %-16s 요소 %s · 전체차이 %d · 허용밖 %d'
          % (name, summary['요소'], summary['전체차이'], summary['허용밖']))
    for k, va, vb, p in kept[:12]:
        print('     %s %s: %r -> %r' % (k, p, va, vb))
    if len(kept) > 12:
        print('     ... 외 %d건' % (len(kept) - 12))
    return ok and not kept


def _kat():
    """★ 답을 아는 입력. 이 비교기가 «다름» 을 진짜 잡는지 먼저 본다."""
    def el(w='100px'):
        return {'width': w, 'height': '10px', 'color': 'rgb(0, 0, 0)',
                'display': 'block', 'position': 'static', '_box': [0, 0, 100, 10]}
    base = {'meta': {'w': 1280, 'h': 900, 'count': 2, 'emptyStyle': 0, 'theme': 'light'},
            'el': {'div.a[0]': el(), 'div.b[0]': el('50px')}}

    def clone(f=None):
        import copy
        c = copy.deepcopy(base)
        if f:
            f(c)
        return c

    # 같으면 차이 0
    if compare(base, clone())[0]:
        return False, '같은 것을 다르다고 함'
    # 값이 바뀌면 잡는다
    d = compare(base, clone(lambda c: c['el']['div.a[0]'].update(width='120px')))[0]
    if len(d) != 1 or d[0][3] != 'width':
        return False, '값 변화를 못 잡음: %r' % (d,)
    # 허용 목록에 넣으면 통과
    d = compare(base, clone(lambda c: c['el']['div.a[0]'].update(width='120px')),
                allow={'div.a[0]/width'})[0]
    if d:
        return False, '허용한 차이를 여전히 잡음'
    # 요소가 사라지면 잡는다
    d = compare(base, clone(lambda c: c['el'].pop('div.b[0]')))[0]
    if len(d) != 1 or d[0][2] != '(사라짐)':
        return False, '사라진 요소를 못 잡음'
    # ★ 2026-09-02 독립 검수가 잡은 허점 세 가지
    #   ① 빈 el 인데 count 를 크게 적은 스냅샷
    forged = {'meta': {'w': 1280, 'h': 900, 'count': 40, 'emptyStyle': 0, 'theme': 'light'},
              'el': {}}
    if gate(forged, dict(forged), name='자기시험'):
        return False, '빈 el + 위조 count 를 통과시킴'
    #   ② count 가 실제 요소 수와 다른 스냅샷
    if gate(base, clone(lambda c: c['meta'].update(count=99)), name='자기시험'):
        return False, 'count 불일치를 통과시킴'
    #   ③ 스키마가 틀린 스냅샷
    def m(**kw):
        d = {'w': 1280, 'h': 900, 'count': 1, 'emptyStyle': 0, 'theme': 'light'}
        d.update(kw)
        return d
    broken_cases = [
        ('el 이 통째로 없음', {'meta': m(count=0)}),
        ('count 가 없음', {'meta': {'w': 1280, 'h': 900, 'theme': 'light'}, 'el': {}}),
        ('w 가 문자열', {'meta': m(w='1280', count=0), 'el': {}}),
        ('필수 속성 누락', {'meta': m(), 'el': {'x[0]': {'width': '1px'}}}),
        ('_box 가 2개', {'meta': m(), 'el': {'x[0]': dict(el(), _box=[0, 0])}}),
        # ── 아래 여덟은 2026-09-02 «2차» 지적에서 고정한 반례다 ──
        ('필수 CSS 값이 null', {'meta': m(), 'el': {'x[0]': dict(el(), color=None)}}),
        ('필수 CSS 값이 빈 문자열', {'meta': m(), 'el': {'x[0]': dict(el(), display='')}}),
        ('필수 CSS 값이 공백뿐', {'meta': m(), 'el': {'x[0]': dict(el(), position='   ')}}),
        ('필수 CSS 값이 수', {'meta': m(), 'el': {'x[0]': dict(el(), width=100)}}),
        ('_box 가 bool', {'meta': m(), 'el': {'x[0]': dict(el(), _box=[True, False, True, True])}}),
        ('_box 에 NaN', {'meta': m(), 'el': {'x[0]': dict(el(), _box=[0, 0, float('nan'), 10])}}),
        ('_box 에 Infinity', {'meta': m(), 'el': {'x[0]': dict(el(), _box=[0, 0, float('inf'), 10])}}),
        ('theme 이 없음', {'meta': {'w': 1280, 'h': 900, 'count': 0, 'emptyStyle': 0}, 'el': {}}),
        ('theme 이 빈 문자열', {'meta': m(count=0, theme=''), 'el': {}}),
        ('w 가 0', {'meta': m(w=0, count=0), 'el': {}}),
        ('h 가 0', {'meta': m(h=0, count=0), 'el': {}}),
    ]
    for why, bad in broken_cases:
        if _schema_error(bad) is None:
            return False, '스키마 검사가 놓침: %s' % why
        if gate(bad, bad, name='자기시험'):
            return False, '잘못된 스키마를 통과시킴: %s' % why
    #   ④ 요소가 적으면 «양쪽 다» 본다. 이전만 비어 있어도 막아야 한다
    big = {'meta': {'w': 1280, 'h': 900, 'count': MIN_ELEMENTS, 'emptyStyle': 0,
                    'theme': 'light'},
           'el': {'div.z[%d]' % i: el() for i in range(MIN_ELEMENTS)}}
    small = {'meta': {'w': 1280, 'h': 900, 'count': 2, 'emptyStyle': 0, 'theme': 'light'},
             'el': {'div.z[0]': el(), 'div.z[1]': el()}}
    if gate(small, big, name='자기시험'):
        return False, '이전이 표본뿐인데 통과시킴'
    if not gate(big, dict(big), name='자기시험'):
        return False, '성한 큰 스냅샷을 막음'
    # 껍데기가 있으면 관문이 선다
    if gate(base, clone(lambda c: c['meta'].update(emptyStyle=2)), name='자기시험'):
        return False, '빈 껍데기를 통과시킴'
    # 뷰포트가 다르면 비교를 거부한다
    if gate(base, clone(lambda c: c['meta'].update(w=390)), name='자기시험'):
        return False, '다른 뷰포트를 비교함'
    # ★ 테마가 다르면 거부한다. 양쪽 스키마는 멀쩡해서 스키마 검사로는 안 잡힌다
    import copy as _copy
    bigdark = _copy.deepcopy(big)
    bigdark['meta']['theme'] = 'dark'
    if gate(big, bigdark, name='자기시험'):
        return False, '테마가 다른 둘을 견줌'
    # ★ NaN 은 파일 층위에서도 막는다. json 은 기본값으로 그것을 받아들인다
    try:
        json.loads('{"meta": {"w": 1, "h": 1, "count": 0}, "el": {}}',
                   parse_constant=_reject_constant)
    except ValueError:
        return False, '성한 JSON 을 막음'
    try:
        json.loads('{"x": NaN}', parse_constant=_reject_constant)
        return False, 'NaN 을 파일 층위에서 통과시킴'
    except ValueError:
        pass
    try:
        json.loads('{"x": Infinity}', parse_constant=_reject_constant)
        return False, 'Infinity 를 파일 층위에서 통과시킴'
    except ValueError:
        pass

    return True, ''


def allow_for(page, config=None):
    """`page_overrides.json` 의 «허용» 을 읽어 비교기 열쇠 집합으로 만든다.

    ★ 2026-09-02 독립 검수 지적. 전에는 이 값을 «아무도 읽지 않았다».
      허용 목록이 정본이라고 적어 놓고 비교는 손으로 넘긴 집합으로 했다.
      그러면 목록을 채워도 관문이 달라지지 않는다. 이제 여기서 읽는다.

    허용의 열쇠는 '요소키/속성' 이다 (예: 'div.wrap[0]/maxWidth').
    """
    config = config or os.path.join(os.path.dirname(HERE), 'page_overrides.json')
    try:
        cfg = json.load(io.open(config, encoding='utf-8'))
    except Exception as e:
        print('  [!] page_overrides.json 을 못 읽었습니다: %s' % e)
        return None
    spec = (cfg.get('페이지') or {}).get(page)
    if spec is None:
        print('  [!] page_overrides.json 에 %s 가 없습니다' % page)
        return None
    return set(spec.get('허용') or {})


def _kat_allow():
    """★ 답을 아는 입력. 허용 목록을 «실제로» 읽는지 본다."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        cfg = os.path.join(d, 'cfg.json')
        io.open(cfg, 'w', encoding='utf-8').write(json.dumps(
            {'페이지': {'x.html': {'허용': {'div.a[0]/width': '이유'}},
                      'y.html': {'허용': {}}}}, ensure_ascii=False))
        if allow_for('x.html', cfg) != {'div.a[0]/width'}:
            return False, '허용 목록을 못 읽음'
        if allow_for('y.html', cfg) != set():
            return False, '빈 허용을 못 읽음'
        if allow_for('없는페이지.html', cfg) is not None:
            return False, '없는 페이지를 통과시킴'
    return True, ''


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ok, why = _kat()
    if ok:
        ok, why = _kat_allow()
    print('비교기 자기시험 %s%s' % ('통과' if ok else '실패', '' if ok else ': ' + why))
    if not ok:
        sys.exit(3)
    # 쓰는 법
    #   python style_diff.py <이전스냅> <이후스냅> <페이지이름>
    #   허용 목록은 page_overrides.json 에서 읽는다 (손으로 넘기지 않는다)
    if len(sys.argv) > 3:
        allow = allow_for(sys.argv[3])
        if allow is None:
            sys.exit(2)
        if allow:
            print('  허용 %d건 (page_overrides.json): %s' % (len(allow), ' '.join(sorted(allow))))
        good = gate(load(sys.argv[1]), load(sys.argv[2]), allow, sys.argv[2])
        sys.exit(0 if good else 1)
    if len(sys.argv) > 2:
        print('  [!] 페이지 이름을 주세요. 허용 목록을 읽을 수 없습니다')
        sys.exit(2)
