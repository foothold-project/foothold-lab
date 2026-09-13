# -*- coding: utf-8 -*-
"""손 관리 페이지의 «내용» 이 이관에서 살아남았는지 본다 (mai-os#24 · 빌드 [0.65]).

  왜 계산 스타일 관문만으로는 부족한가
    style_diff 는 «화면이 같은가» 를 본다. 그것은 글자가 바뀌어도 통과한다.
    문단 하나가 통째로 사라지면 요소 수가 줄어 잡히지만, 코드 한 줄이 바뀌거나
    링크 주소가 달라지거나 제목 글자가 틀어지면 상자 크기가 같아 «차이 0» 이 된다.
    이관의 진짜 위험은 그쪽이다. 복사해서 실행하는 코드가 조용히 변질되는 것.

  두 기준을 «함께» 쓴다 (팀장 결정 2026-09-03)
    ① 손으로 쓴 것 (본문·코드·링크·제목)
         이관 «직전 고정본» 에서 뽑아 둔 지문과 대조한다. 삭제와 변질을 잡는다.
    ② 생성·주입된 값
         낡은 출력을 정답으로 삼지 «않는다». 실제 정본 입력에서 기대값을 따로
         계산해 대조한다. 그래야 옛 출력이 틀렸을 때 그 틀림을 물려받지 않는다.

  ★ 이 관문은 «다르다» 고만 말한다. 문서를 고치지 않는다.
    기존 내용이 틀렸더라도 여기서 새로 쓰지 않는다. 사람에게 보고한다.
"""
import hashlib
import html as H
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
FIXTURE = os.path.join(HERE, 'content_fixtures')


# ── 손으로 쓴 것을 뽑아내는 규칙 ──────────────────────────────────────────────
#   생성기 소유 블록은 먼저 걷어낸 뒤에 뽑는다. 그래야 생성물의 변화가
#   «손 내용이 변질됐다» 는 거짓 경보를 만들지 않는다.

def _strip_owned(s):
    """생성기 소유 블록을 걷어낸 문자열. 정본은 markercheck.OWNERS 하나다.

    ★ 두 부류를 갈라야 한다 (2026-09-03 · 자기시험이 잡았다).
      · «대신 넣는» 블록 (전역바·판 띠 등) 은 통째로 지운다. 손 내용이 아니다.
      · «덧칠하는» 블록 (코드 강조) 은 지우면 «손으로 쓴 코드까지» 없어진다.
        그것은 지우지 말고 원문으로 되돌린다.
      한 줄로 뭉뚱그리면 코드 지문이 통째로 비어 버린다.
    """
    sys.path.insert(0, HERE)
    import hl_setup
    import markercheck
    s = hl_setup.strip_own(s)              # 덧칠은 «되돌린다»
    for o in markercheck.OWNERS:
        if o['종류'] != '짝' or o.get('주인') == 'hl_setup':
            continue
        a = o['시작'] if isinstance(o['시작'], str) else None
        if a is None:
            continue
        s = re.sub(re.escape(a) + r'[\s\S]*?' + re.escape(o['끝']), '', s)
    return s


def _text(fragment):
    """태그를 걷고 공백을 하나로 눌러 «사람이 읽는 글자» 만 남긴다."""
    t = re.sub(r'<[^>]+>', '', fragment)
    return re.sub(r'\s+', ' ', H.unescape(t)).strip()


def headings(s):
    """제목. (수준, 글자) 목록."""
    out = []
    for m in re.finditer(r'<h([1-6])\b[^>]*>([\s\S]*?)</h\1>', s):
        t = _text(m.group(2))
        if t:
            out.append('h%s:%s' % (m.group(1), t))
    return out


def codes(s):
    """코드 블록의 «원문». 강조 태그를 떼고 엔티티를 되돌린 실제 실행 문자열.

    ★ 이것이 가장 중요한 항목이다. 사람이 복사해서 그대로 실행한다.
      한 글자만 달라져도 남의 컴퓨터에서 다른 일이 벌어진다.
    """
    out = []
    for m in re.finditer(r'<pre\b[^>]*>([\s\S]*?)</pre>', s):
        raw = H.unescape(re.sub(r'<[^>]+>', '', m.group(1)))
        out.append(raw)
    return out


def links(s):
    """링크 주소. 순서까지 본다."""
    return re.findall(r'<a\b[^>]*\bhref="([^"]*)"', s)


def paragraphs(s):
    """본문 문단·항목·표 칸의 글자."""
    out = []
    for tag in ('p', 'li', 'td', 'th', 'summary', 'blockquote'):
        for m in re.finditer(r'<%s\b[^>]*>([\s\S]*?)</%s>' % (tag, tag), s):
            t = _text(m.group(1))
            if t:
                out.append(t)
    return out


PARTS = (('제목', headings), ('코드', codes), ('링크', links), ('본문', paragraphs))


def fingerprint(html):
    """손으로 쓴 내용의 지문. 생성기 소유 블록은 뺀 뒤에 뽑는다."""
    s = _strip_owned(html)
    fp = {}
    for name, fn in PARTS:
        items = fn(s)
        fp[name] = {
            '수': len(items),
            '해시': hashlib.sha256('\x00'.join(items).encode('utf-8')).hexdigest(),
            '항목해시': [hashlib.sha256(x.encode('utf-8')).hexdigest()[:16] for x in items],
        }
    return fp


def compare_fingerprint(before, after):
    """(문제 목록). 비면 통과."""
    bad = []
    for name, _fn in PARTS:
        b, a = before.get(name), after.get(name)
        if b is None or a is None:
            bad.append('%s 지문이 없습니다' % name)
            continue
        if b['해시'] == a['해시']:
            continue
        if b['수'] != a['수']:
            bad.append('%s 개수가 %d -> %d 로 달라졌습니다' % (name, b['수'], a['수']))
        lost = [h for h in b['항목해시'] if h not in a['항목해시']]
        got = [h for h in a['항목해시'] if h not in b['항목해시']]
        if lost:
            bad.append('%s %d건이 사라지거나 변질됐습니다 (%s)'
                       % (name, len(lost), ' '.join(lost[:4])))
        if got and not lost:
            bad.append('%s %d건이 새로 생겼습니다 (%s)'
                       % (name, len(got), ' '.join(got[:4])))
        if not lost and not got and b['수'] == a['수']:
            bad.append('%s 의 «순서» 가 달라졌습니다' % name)
    return bad


# ── 생성·주입된 값은 정본 입력에서 기대값을 «따로» 만든다 ─────────────────────

# 이 관문이 «반드시» 봐야 하는 페이지. 고정본이나 파일이 없으면 실패한다.
#
#   ★ 2026-09-03 독립 중간검수 지적. 전에는 고정본 폴더가 비면 pages 가 빈 목록이
#     되어 «검사할 페이지 없음» 을 찍고 True 를 돌려줬다. 관문이 조용히 사라지는
#     길이다 (원칙 2 · 조용한 실패를 소리 나게). 필수 목록으로 그 길을 막는다.
#     이번 이관 범위인 setup 만 필수로 둔다. 나머지 페이지로 넓히지 않는다.
REQUIRED = ('setup.html',)


def source_codes(page, vault=None):
    """정본 «입력» 인 소스에서 코드 원문을 읽는다. 출력에서 베끼지 않는다.

    page_overrides.json 이 어느 소스에서 왔는지 알고 있다. 그것을 따라간다.
    """
    vault = vault or VAULT
    cfg = json.load(io.open(os.path.join(HERE, 'page_overrides.json'), encoding='utf-8'))
    spec = (cfg.get('페이지') or {}).get(page)
    if not spec:
        return None
    src = os.path.join(vault, *spec['소스'].split('/'))
    if not os.path.exists(src):
        # 산출 폴더에는 _src 가 없다. 볼트 쪽에서 찾는다
        src = os.path.join(VAULT, *spec['소스'].split('/'))
    if not os.path.exists(src):
        return None
    return codes(io.open(src, encoding='utf-8').read())


def check_injected(html, page, vault=None):
    """생성·주입된 값이 «정본 입력» 과 맞는지. (문제 목록).

    ★ 무엇을 검증하고 무엇을 안 하는지 분명히 해 둔다 (2026-09-03 검수 지적).
      검증한다 · 코드 강조. 이 이관 범위에서 값이 만들어지는 유일한 자리다.
                 강조를 벗긴 원문이 소스의 대응 <pre> 와 «문자 단위로» 같아야 한다.
      검증하지 않는다 · gnav · search · stamp · 파비콘의 «내용». 짝과 자리만 본다.
                 그것들의 내용 정확성은 이번 범위가 아니며 미검증으로 보고한다.
    """
    sys.path.insert(0, HERE)
    import hl
    import hl_setup
    import markercheck
    bad = []

    # 1) 강조된 코드가 «소스 원문» 을 그대로 담고 있는가 (정본 입력과 직접 대조)
    painted = [re.sub(r'</?span[^>]*>', '', m.group(1)) for m in
               re.finditer(re.escape(hl_setup.HL_A) + r'([\s\S]*?)' + re.escape(hl_setup.HL_B),
                           html)]
    for p in painted:
        for e in re.finditer(r'&', p):
            if not hl.ENTITY.match(p, e.start()):
                bad.append('강조가 엔티티를 쪼갰습니다 (%r 부근)'
                           % p[max(0, e.start() - 20):e.start() + 20])
                break
    src_codes = source_codes(page, vault)
    if src_codes is None:
        if painted:
            bad.append('소스를 찾을 수 없어 강조 원문을 정본과 대조하지 못했습니다')
    else:
        out_codes = codes(html)
        if len(out_codes) != len(src_codes):
            bad.append('코드 블록 수가 소스와 다릅니다 (소스 %d · 산출 %d)'
                       % (len(src_codes), len(out_codes)))
        else:
            for i, (a, b) in enumerate(zip(src_codes, out_codes)):
                if a != b:
                    bad.append('%d번째 코드가 소스 원문과 다릅니다 (소스 %d자 · 산출 %d자)'
                               % (i + 1, len(a), len(b)))

    # 2) 짝마커가 짝이 맞는가 · 이것은 «자리» 검사이지 내용 검증이 아니다
    for o in markercheck.OWNERS:
        if o['종류'] != '짝' or not isinstance(o['시작'], str):
            continue
        na, nb = html.count(o['시작']), html.count(o['끝'])
        if na != nb:
            bad.append('마커:%s 의 짝이 안 맞습니다 (시작 %d · 끝 %d)' % (o['이름'], na, nb))

    # 3) 안 채워진 슬롯이 남았는가
    left = re.findall(r'<!--slot:[a-z-]+-->', html)
    if left:
        bad.append('안 채워진 슬롯이 남았습니다: %s' % ' '.join(sorted(set(left))))
    return bad


# ── 고정본 다루기 ────────────────────────────────────────────────────────────

def fixture_path(page):
    return os.path.join(FIXTURE, page.replace('.html', '') + '.json')


def save_fixture(page, html, note=''):
    """이관 «직전» 고정본에서 지문을 떠 둔다. 한 번만 한다."""
    os.makedirs(FIXTURE, exist_ok=True)
    fp = fingerprint(html)
    data = {'페이지': page, '메모': note,
            '고정본_sha256': hashlib.sha256(html.encode('utf-8')).hexdigest(),
            '지문': fp}
    io.open(fixture_path(page), 'w', encoding='utf-8', newline='\n').write(
        json.dumps(data, ensure_ascii=False, indent=1) + '\n')
    return data


def load_fixture(page):
    p = fixture_path(page)
    if not os.path.exists(p):
        return None
    return json.load(io.open(p, encoding='utf-8'))


def check(page, html, vault=None):
    """한 페이지 판정. (통과여부, 문제목록, 요약)."""
    fx = load_fixture(page)
    if fx is None:
        return None, ['고정본 지문이 없습니다: %s' % fixture_path(page)], {}
    now = fingerprint(html)
    bad = compare_fingerprint(fx['지문'], now)
    bad += check_injected(html, page, vault)
    summary = dict((n, now[n]['수']) for n, _f in PARTS)
    return (not bad), bad, summary


# ── 자기시험 ────────────────────────────────────────────────────────────────

_SAMPLE = ('<html><body>'
           '<h1>설치 안내</h1>'
           '<h2>사전 준비</h2>'
           '<p>먼저 파이썬을 설치합니다.</p>'
           '<ul><li>윈도우 11</li><li>RTX 4090</li></ul>'
           '<div class="cb"><pre>pip install torch==2.4.0</pre></div>'
           '<div class="cb"><pre>ros2 run demo talker</pre></div>'
           '<p>자세한 것은 <a href="https://docs.ros.org/">공식 문서</a>를 보세요.</p>'
           '<a href="setup.html">이 문서</a>'
           '<table><tr><th>항목</th><td>값</td></tr></table>'
           '</body></html>')


def _kat():
    """★ 답을 아는 입력. «실제로 실패를 잡는가» 를 본다.

    관문이 통과만 시키면 관문이 아니다. 음성 시험이 본체다.
    """
    base = fingerprint(_SAMPLE)
    if base['코드']['수'] != 2:
        return False, '코드 블록을 %d개로 셈 (2 여야 함)' % base['코드']['수']
    if base['제목']['수'] != 2:
        return False, '제목을 %d개로 셈' % base['제목']['수']
    if base['링크']['수'] != 2:
        return False, '링크를 %d개로 셈' % base['링크']['수']

    # 같으면 통과한다
    if compare_fingerprint(base, fingerprint(_SAMPLE)):
        return False, '같은 문서를 다르다고 함'

    # ── 음성 시험. 하나라도 통과하면 관문이 없는 것이다 ──
    cases = [
        ('본문 한 문단 삭제', _SAMPLE.replace('<p>먼저 파이썬을 설치합니다.</p>', '')),
        ('본문 글자 변질', _SAMPLE.replace('먼저 파이썬을 설치합니다', '먼저 파이썬을 지웁니다')),
        ('코드 버전 변질', _SAMPLE.replace('torch==2.4.0', 'torch==2.5.0')),
        ('코드 한 글자 변질', _SAMPLE.replace('ros2 run demo talker', 'ros2 run demo talkor')),
        ('코드 블록 삭제', _SAMPLE.replace('<div class="cb"><pre>ros2 run demo talker</pre></div>', '')),
        ('링크 주소 변경', _SAMPLE.replace('https://docs.ros.org/', 'https://evil.example/')),
        ('링크 삭제', _SAMPLE.replace('<a href="setup.html">이 문서</a>', '이 문서')),
        ('제목 글자 변질', _SAMPLE.replace('<h2>사전 준비</h2>', '<h2>사전준비</h2>')),
        ('제목 수준 변경', _SAMPLE.replace('<h2>사전 준비</h2>', '<h3>사전 준비</h3>')),
        ('표 칸 삭제', _SAMPLE.replace('<td>값</td>', '')),
        ('목록 항목 삭제', _SAMPLE.replace('<li>RTX 4090</li>', '')),
    ]
    for why, broken in cases:
        if not compare_fingerprint(base, fingerprint(broken)):
            return False, '음성 시험을 통과시킴: %s' % why

    # 순서가 바뀌어도 잡는가 (해시 집합은 같고 순서만 다른 경우)
    swapped = _SAMPLE.replace(
        '<div class="cb"><pre>pip install torch==2.4.0</pre></div>'
        '<div class="cb"><pre>ros2 run demo talker</pre></div>',
        '<div class="cb"><pre>ros2 run demo talker</pre></div>'
        '<div class="cb"><pre>pip install torch==2.4.0</pre></div>')
    if not compare_fingerprint(base, fingerprint(swapped)):
        return False, '순서가 바뀐 것을 통과시킴'

    # 생성기 소유 블록이 «달라져도» 손 지문은 흔들리지 않아야 한다
    owned_a = _SAMPLE.replace('</body>', '<!--gnav:v1--><nav>가</nav><!--/gnav:v1--></body>')
    owned_b = _SAMPLE.replace('</body>', '<!--gnav:v1--><nav>완전히 다른 것</nav><!--/gnav:v1--></body>')
    if compare_fingerprint(fingerprint(owned_a), fingerprint(owned_b)):
        return False, '생성기 소유 블록 변화를 손 내용 변질로 오인함'
    if compare_fingerprint(base, fingerprint(owned_a)):
        return False, '생성기 블록이 붙었다고 손 내용이 달라졌다고 함'

    # 안 채워진 슬롯을 잡는가
    if not check_injected(_SAMPLE + '<!--slot:recent-->', 'x.html'):
        return False, '안 채워진 슬롯을 통과시킴'

    # ★ 강조가 «덧칠» 된 뒤에도 코드 지문이 그대로여야 한다.
    #   소스(민코드)와 배포본(강조됨)은 같은 코드로 읽혀야 한다. 이걸 놓치면
    #   코드 지문이 통째로 비어 «항상 통과» 하는 관문이 된다 (실제로 그럴 뻔했다).
    import hl_setup
    painted, _d, _s = hl_setup.render_all(_SAMPLE)
    if compare_fingerprint(base, fingerprint(painted)):
        return False, '강조를 입혔더니 손 지문이 달라짐'
    if fingerprint(painted)['코드']['수'] != 2:
        return False, '강조 뒤 코드 블록을 %d개로 셈' % fingerprint(painted)['코드']['수']
    # 강조된 판에서도 코드 «변질» 은 여전히 잡아야 한다
    bad_painted, _d, _s = hl_setup.render_all(_SAMPLE.replace('torch==2.4.0', 'torch==2.5.0'))
    if not compare_fingerprint(base, fingerprint(bad_painted)):
        return False, '강조된 판에서 코드 변질을 놓침'

    # ★ 2026-09-03 독립 중간검수 지적 ① · 고정본이 없으면 «조용히 통과» 하면 안 된다
    import tempfile
    global FIXTURE
    keep = FIXTURE
    try:
        with tempfile.TemporaryDirectory() as d:
            FIXTURE = d                      # 고정본이 하나도 없는 상태를 만든다
            buf = io.StringIO()
            old_out, sys.stdout = sys.stdout, buf
            try:
                got = run(vault=os.devnull)     # ★ main 이 아니라 run. main 은 나를 부른다
            finally:
                sys.stdout = old_out
            if got:
                return False, '고정본이 없는데 통과시킴 (빈 통과)'
            if '고정본 지문이 없습니다' not in buf.getvalue():
                return False, '빈 통과를 막았지만 이유를 말하지 않음'
    finally:
        FIXTURE = keep

    # ★ 지적 ② · 강조 원문이 «소스» 와 다르면 잡아야 한다.
    #   짝마커만 세는 것으로는 절대 못 잡는 부류다.
    painted_ok, _d, _s = hl_setup.render_all(_SAMPLE)
    tampered = painted_ok.replace('2.4.0', '2.5.0', 1)
    if tampered == painted_ok:
        return False, '시험 준비 실패 (강조본에 바꿀 자리가 없음)'
    src2 = codes(_SAMPLE)
    out2 = codes(tampered)
    if src2 == out2:
        return False, '강조본 변조가 코드 원문에 반영되지 않음 (시험 무효)'
    return True, ''


def run(vault=None, pages=None):
    """검사 본체. 자기시험을 부르지 «않는다» (시험이 이것을 부르므로)."""
    vault = vault or VAULT
    if pages is None:
        have = ([os.path.basename(p)[:-5] + '.html' for p in sorted(os.listdir(FIXTURE))]
                if os.path.isdir(FIXTURE) else [])
        # ★ 필수는 «있으면 본다» 가 아니라 «없으면 선다» 다. 빈 통과를 막는다
        pages = sorted(set(have) | set(REQUIRED))
    allok = True
    for need in REQUIRED:
        if load_fixture(need) is None:
            print('  [!] 필수 페이지 %s 의 고정본 지문이 없습니다: %s'
                  % (need, fixture_path(need)))
            print('      이관 «직전» 고정본에서 떠 두어야 합니다. 지금 떠서 채우면')
            print('      이관 후 상태를 정답으로 삼는 것이라 검사가 무의미해집니다')
            allok = False
    for page in pages:
        p = os.path.join(vault, page)
        if not os.path.exists(p):
            print('  [!] %s 가 없습니다' % page)
            allok = False
            continue
        good, bad, summary = check(page, io.open(p, encoding='utf-8').read(), vault)
        if good:
            print('  %-14s 제목 %d · 코드 %d · 링크 %d · 본문 %d · 보존 확인'
                  % (page, summary['제목'], summary['코드'], summary['링크'], summary['본문']))
        else:
            allok = False
            print('  🔴 %s 내용이 달라졌습니다' % page)
            for b in bad:
                print('      %s' % b)
    return allok


def main(vault=None, pages=None):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    return run(vault, pages)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--selftest' in sys.argv:
        ok, why = _kat()
        print('내용 관문 자기시험 %s%s' % ('통과' if ok else '실패', '' if ok else ': ' + why))
        sys.exit(0 if ok else 1)
    sys.exit(0 if main() else 1)
