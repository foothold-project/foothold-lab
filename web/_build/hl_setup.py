# -*- coding: utf-8 -*-
"""setup.html 의 기존 코드 블록에 문법 강조를 다시 입힌다.

  setup.html 은 손으로 쓴 HTML 이라 <pre> 안에 이미 손으로 넣은 <span class="c"> 가 섞여 있다.
  그걸 걷어내고 원문을 복원한 뒤, hl.py 로 일관되게 다시 칠한다.

  ★ 언어를 못 알아보면 강조하지 않는다. 잘못 칠하느니 안 칠하는 게 낫다.
  ★ 원문이 한 글자라도 바뀌면 중단한다. 복사해서 실행하는 코드다.
"""
import io
import html as H
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hl

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'setup.html')


def guess(code, lbl):
    """블록의 언어를 추정한다. 확신이 없으면 '' (강조 안 함)."""
    if lbl.endswith('.py') or re.search(r'^\s*(import |from \w+ import|def |SCRIPT = )', code, re.M):
        return 'python'
    if re.search(r'(conda activate|\$env:|Get-\w+|Set-\w+|New-NetFirewallRule|Stop-Process|'
                 r'^\s*python .*--|nvidia-smi|winget|Add-WindowsCapability|Start-Service)',
                 code, re.M):
        return 'powershell'
    if re.search(r'^\s*(sudo |apt |ros2 |colcon |export |source |ssh )', code, re.M):
        return 'bash'
    if re.match(r'^\s*(pip|git|conda|python|curl) ', code):
        return 'powershell'                     # 이 문서의 셸은 PowerShell 이다
    return ''                                   # 출력·트리·에러 로그 → 그대로 둔다


# ─────────────────────────────────────────────────────────────────────────────
# 소유 범위. 이 짝마커 «사이» 만 이 생성기의 것이다 (markercheck.OWNERS 등록).
#
#   ★ 2026-09-03 setup 이관에서 신설. 전에는 마커가 하나도 없어서
#     · 어디까지가 생성물인지 아무도 몰랐고
#     · 소스 순수성 관문이 이 흔적을 못 봤다
#   이제 «먼저 원문으로 되돌리고 언제나 다시 칠한다». 건너뛰는 길이 없다.
#
#   ★ 범위는 <pre> 안의 강조 «뿐» 이다. 강조 CSS 는 이 생성기 것이 아니다.
#     실측 2026-09-03: setup.html 의 강조 규칙은 페이지 자신의 손 <style> 안에 있고,
#     hl_setup 의 CSS 주입은 판정 문자열('/* ── 코드 문법 강조 ──')이 그 손 CSS 와
#     겹쳐서 «단 한 번도 돈 적이 없다». 그러니 그 CSS 는 손 소스에 남는다.
#     주입 코드는 이번 이관에서 손대지 않는다. 별건으로 보고한다.
HL_A, HL_B = '<!--hl:v1-->', '<!--/hl:v1-->'

_HL_BLOCK = re.compile(re.escape(HL_A) + r'[\s\S]*?' + re.escape(HL_B))


def strip_own(s):
    """자기 소유 블록만 걷어낸다. 자기 범위 «밖» 은 한 글자도 건드리지 않는다.

    코드 블록은 지우는 게 아니라 «소스 모양으로 되돌린다». 그 안이 손으로 쓴 코드다.

    ★ 여기서 엔티티를 풀지 «않는다». 소스의 <pre> 는 &lt; 처럼 escape 된 상태로
      들어 있고, 푸는 것은 render_all 이 한 번만 한다. 여기서도 풀면 두 번 풀려
      &amp;lt; 같은 것이 &lt; 로 주저앉는다. 코드가 조용히 달라지는 길이다.
    """
    return _HL_BLOCK.sub(
        lambda m: re.sub(r'</?span[^>]*>', '', m.group(0)[len(HL_A):-len(HL_B)]), s)


def render_all(s):
    """소스 문자열을 받아 강조를 입힌 문자열을 돌려준다. 파일을 읽거나 쓰지 않는다.

    ★ 파일 입출력과 분리해야 자기시험이 «답을 아는 입력» 으로 이것을 부를 수 있다.
    """
    s = strip_own(s)                      # 언제나 깨끗한 판에서 시작한다
    out, done, skip = [], 0, 0

    for m in re.finditer(r'(<div class="cb"[^>]*>)([\s\S]*?)<pre>([\s\S]*?)</pre>', s):
        mid, pre = m.group(2), m.group(3)
        lbl_m = re.search(r'<div class="lbl">([^<]*)</div>', mid)
        lbl = lbl_m.group(1) if lbl_m else ''

        raw = H.unescape(re.sub(r'</?span[^>]*>', '', pre))    # 기존 강조 제거 + 원문 복원
        lang = guess(raw, lbl)
        if not lang:
            skip += 1
            continue
        new = hl.render(raw, lang)

        # ★ 원문 보존 + HTML 엔티티 무결성 확인: 강조가 코드를 바꾸면 안 된다.
        #   원문 대조만으로는 부족했다. 태그가 &#x27; 를 반으로 쪼개도 태그를 떼면
        #   원문이 복원돼 "통과"로 보이지만, 화면에는 &#x27; 가 글자로 찍힌다.
        bad = hl.verify(new, raw)
        if bad:
            raise SystemExit('[!] %s (%s)\n---\n%r' % (bad, lbl, raw[:200]))

        out.append((m.start(3), m.end(3), HL_A + new + HL_B))
        done += 1

    for a, b, new in sorted(out, reverse=True):
        s = s[:a] + new + s[b:]

    # 강조 CSS 주입 (한 번만) · 이 생성기의 소유 범위가 아니다. 손대지 않고 그대로 둔다.
    # ★ '.cb pre .k{' 로 판정하면 안 된다. 원래 문서에 이미 그 선택자가 있어서
    #   주입을 통째로 건너뛰고도 "CSS OK" 로 보였다. 우리만 쓰는 표식으로 판정한다.
    if '/* ── 코드 문법 강조 ──' not in s:
        s = s.replace('@media print{', hl.CSS.replace('@media print{',
                      '@media print{').split('@media print{')[0] + '\n@media print{', 1)
        # hl.CSS 의 인쇄 블록은 별도로 넣는다
        pr = hl.CSS.split('@media print{')[1].rsplit('}', 2)[0]
        s = s.replace('  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}',
                      pr.rstrip() + '\n  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}', 1)
    return s, done, skip


def _kat():
    """★ 답을 아는 입력. 이 생성기가 자기 범위만 건드리는지, 되풀이해도 같은지 본다."""
    hand = ('<html><head><style>/* ── 코드 문법 강조 ── */\n.cb pre .f{color:#f0c674}\n'
            '@media print{\n'
            '  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}\n}</style></head>'
            '<body><p>손으로 쓴 문장</p>'
            # ★ 엔티티를 일부러 넣는다. 두 번 풀리면 여기서 무너진다
            '<div class="cb"><div class="lbl">a.py</div>'
            '<pre>import os\nx = 1 if a &lt; b else 2\ns = &quot;&amp;lt;&quot;</pre></div>'
            '<div class="cb"><div class="lbl">출력</div><pre>hello world</pre></div>'
            '</body></html>')
    one, d1, s1 = render_all(hand)
    if d1 != 1 or s1 != 1:
        return False, '언어 판정이 예상과 다름 (강조 %d · 건너뜀 %d)' % (d1, s1)
    for tok in (HL_A, HL_B):
        if tok not in one:
            return False, '마커 %s 가 안 붙음' % tok
    if '손으로 쓴 문장' not in one:
        return False, '자기 범위 밖 본문이 사라짐'
    if one.count('hello world') != 1 or HL_A + 'hello world' in one:
        return False, '강조하지 않기로 한 블록을 건드림'
    # ★ 되풀이해도 같은가 (멱등). 이관은 «매번 소스에서» 만들지만, 배포본에 두 번
    #   돌아도 강조가 겹쳐 쌓이면 안 된다
    two, _d, _s = render_all(one)
    if two != one:
        return False, '두 번째 실행 결과가 다름 (멱등하지 않음)'
    three, _d, _s = render_all(two)
    if three != one:
        return False, '세 번째 실행 결과가 다름'
    # 걷어내면 손으로 쓴 것만 남는가 (자기 범위 밖 무손실)
    if strip_own(one) != hand:
        return False, '걷어낸 결과가 원래 손 소스와 다름'
    # 원문이 살아 있는가
    if 'import os' not in H.unescape(re.sub(r'<[^>]+>', '', one)):
        return False, '코드 원문이 사라짐'
    # 손 CSS 가 이미 있으면 CSS 를 새로 넣지 않는다 (중복 방지)
    if one.count('.cb pre .f{') != 1:
        return False, '강조 CSS 가 중복 주입됨'
    return True, ''


def main():
    ok, why = _kat()
    if not ok:
        raise SystemExit('[!] hl_setup 자기시험 실패: %s' % why)
    s = io.open(P, encoding='utf-8').read()
    s, done, skip = render_all(s)
    io.open(P, 'w', encoding='utf-8').write(s)
    ok = '/* ── 코드 문법 강조 ──' in s and '.cb pre .f{' in s
    print('  강조 %d블록 · 건너뜀 %d블록(출력·로그) · CSS %s'
          % (done, skip, 'OK' if ok else '★ 주입 안 됨'))
    if not ok:
        raise SystemExit('[!] 강조 CSS 가 주입되지 않았습니다')


if __name__ == '__main__':
    main()
