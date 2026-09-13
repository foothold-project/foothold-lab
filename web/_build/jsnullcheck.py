# -*- coding: utf-8 -*-
"""없는 요소를 방어 없이 만지는 스크립트를 잡는다 (빌드 [1.8992] 단계).

  왜 이게 관문인가
    2026-09-08 감사에서 공통 스크립트 예외가 나왔다. 부류는 하나다.
    **주입기는 모든 페이지에 같은 스크립트를 넣는데, 그 스크립트가 만지는
    요소는 페이지마다 있기도 없기도 하다.**

      pdfBtn  무방비 리스너 108장 · 버튼 8장  -> 100장에서 로드 즉시 예외
      prog    참조 99장 · 요소 1장           -> 98장에서 스크롤할 때 예외

    앞의 것은 페이지가 열리는 순간 죽어 «뒤따르는 스크립트가 통째로 멈춘다».
    그래서 「검색이 되니 이 페이지는 정상」이라고 판정할 수 없다.
    뒤의 것은 스크롤하기 전까지 멀쩡해 보인다. 감사가 런타임 예외를 1건만
    관측한 이유이고, 정적으로는 98장이 안고 있었다. **조용한 실패다.**

  판정
    `getElementById('X')` 바로 뒤에 점(.)이 붙어 속성에 접근하는데
    그 페이지에 `id="X"` 가 없으면 잡는다.
    `var e = getElementById('X') || ...` 처럼 변수로 받아 검사하는 형태는
    점이 바로 붙지 않으므로 걸리지 않는다. 그것이 올바른 작성법이다.
"""
import io
import os
import re

# getElementById('X') 다음에 곧바로 . 이 오는 것만 본다 (무방비 접근)
DIRECT = re.compile(r"""getElementById\(\s*(['"])([\w:.-]+)\1\s*\)\s*\.""")


def check_file(path):
    s = io.open(path, encoding='utf-8', errors='replace').read()
    bad = []
    for m in DIRECT.finditer(s):
        eid = m.group(2)
        if ('id="%s"' % eid) in s or ("id='%s'" % eid) in s:
            continue
        line = s[:m.start()].count('\n') + 1
        bad.append((line, eid))
    # 같은 id 를 여러 번 만져도 한 번만 센다
    seen, out = set(), []
    for line, eid in bad:
        if eid in seen:
            continue
        seen.add(eid)
        out.append((line, eid))
    return out


def _kat():
    """알려진 답으로 먼저 시험한다."""
    import tempfile
    d = tempfile.mkdtemp()
    bad = os.path.join(d, 'bad.html')
    good = os.path.join(d, 'good.html')
    io.open(bad, 'w', encoding='utf-8').write(
        "<html><body><script>document.getElementById('nope').style.width='1px';"
        "</script></body></html>")
    io.open(good, 'w', encoding='utf-8').write(
        "<html><body><b id=\"yes\"></b><script>"
        "document.getElementById('yes').style.width='1px';"
        "var e=document.getElementById('maybe')||null;if(e)e.focus();"
        "</script></body></html>")
    if not check_file(bad):
        return False, '없는 요소를 만지는데 못 잡았다'
    if check_file(good):
        return False, '있는 요소와 방어된 접근을 잘못 잡았다 (과탐)'
    return True, ''


def main(vault, pages):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    seen, bad = 0, []
    for f in sorted(set(pages)):
        p = os.path.join(vault, f)
        if not f.endswith('.html') or not os.path.exists(p):
            continue
        seen += 1
        for line, eid in check_file(p):
            bad.append('%s:%d  없는 요소 #%s 를 방어 없이 만진다' % (f, line, eid))
    if bad:
        print('  검사 %d장 · ★ 없는 요소를 만지는 스크립트 %d건' % (seen, len(bad)))
        for b in bad[:12]:
            print('     %s' % b)
        if len(bad) > 12:
            print('     … 외 %d건' % (len(bad) - 12))
        return False
    # ★ 2026-09-09. 「대상에 닿지 못한 것」과 「위반이 없는 것」은 다른 사실인데
    #   같은 «통과» 를 내고 있었다. 빈 볼트로 돌려 보고 알았다.
    #   관문이 0개를 검사하고 통과하면, 목록이 비는 순간 조용히 무력해진다.
    if seen == 0:
        print('  [!] 페이지를 한 장도 못 봤습니다. 검사가 헛돌았습니다')
        return False
    print('  자기시험 통과 · 검사 %d장 · 없는 요소를 만지는 스크립트 0건' % seen)
    return True
