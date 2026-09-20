# -*- coding: utf-8 -*-
"""스크립트가 `hidden` 으로 숨긴다. 그 숨김을 CSS 가 이기지 않는가.

★ 2026-09-13 라이브 사고. 연구 허브의 거르개를 눌렀더니 주소는 `?fn=diagnosis`
  로 바뀌고 입구 표식도 켜졌는데 **목록이 한 줄도 안 줄었다.**

      스크립트가 끈 행        29
      껐는데 화면에 남은 행    29        <- 전부
      그 행의 display        grid

  스크립트는 제대로 돌았다. `el.hidden = true` 를 받쳐 주는 것은 브라우저
  «기본» 시트의 `[hidden]{display:none}` 하나뿐이고, 그것은 제작자가 쓴
  `.ev3{display:grid}` 한 줄에 진다. 특이도로 지는 것이 아니라 «출처» 로 진다.
  그래서 이 실패는 CSS 를 아무리 들여다봐도 충돌로 안 보인다.

왜 배포까지 왔나 (이것이 이 관문의 존재 이유다)
  만든 쪽은 눌러 보고 「진단 37 -> 8」 을 얻었다. 그 수는 **맞다.**
  `!c.hidden` 로 세면 정확히 8이다. 그런데 그것은 속성이지 화면이 아니다.
  나도 처음엔 링크를 세어 46/46 을 얻고 「안 줄었다」로 갈 뻔했다. 갈린 것은
  `getComputedStyle(e).display` 를 본 뒤였다. 커널 원칙 3 그대로다.

무엇을 요구하나
  스크립트가 hidden 으로 숨기는 페이지는 안전망 한 줄을 반드시 둔다.

      [hidden]{display:none!important}

  선택자 모양은 자유다. `.ev3[hidden],.evs3[hidden]{display:none!important}`
  도 받는다. **`!important` 만 반드시 있어야 한다.** 그것이 없으면 오늘 안
  겹치더라도 내일 누가 `display` 한 줄을 더하는 순간 조용히 무너진다.
  실제로 두 허브에 `.mclash[hidden]{display:none}` 이 있었는데, 대상이
  `.mclash` 하나뿐이라 `.ev3` 스물아홉 줄이 그 옆으로 새어 나갔다.

이 관문이 «재는 것이 아니라는» 점을 분명히 해 둔다
  빌드에는 브라우저가 없어서 「칠해졌는가」를 못 잰다. 이것은 렌더링 측정이
  아니라 **질 수 없게 만드는 구조 규칙**이다. 안전망이 있으면 어떤 제작자
  규칙도 hidden 을 못 이긴다. 추론과 실측을 섞지 않기 위해 적어 둔다.

화면에서 재는 자리는 따로 있다 (철칙 4 · 관문은 한 층위만 보면 안 된다)
  배포 뒤 브라우저에서 이 한 줄이 0 이어야 한다.

      [...document.querySelectorAll('[hidden]')]
        .filter(e => getComputedStyle(e).display !== 'none').length

  `Claude/os/tool-hazards.md` 에 적어 뒀다.

무엇을 안 보나
  이 빌드가 «안 만드는» 페이지. 갤러리는 다른 생성기 산출물이라 여기서 고칠
  수 없다. 사고 당일 그 둘을 화면에서 재 보니 새는 것이 0건이었다.
  정적 검사는 셋을 지목했는데 실제로 깨진 것은 하나였다. 그래서 이 관문의
  위반은 「깨졌다」가 아니라 「막을 보장이 없다」로 읽어야 맞다.

명부
  한 번에 못 고치는 부류는 명부로 연다. 명부는 면제가 아니다. 매 빌드에
  줄 수를 찍고, 늘어나면 막는다. 줄 수가 남은 일의 크기다.


★ 이 관문이 «못 잡는 것»
  - **렌더링을 안 잰다.** 빌드에 브라우저가 없다. 안전망이 있는지만 본다.
    화면에서 실제로 사라졌는지는 배포 뒤 이 한 줄이 0 이어야 안다.
      [...document.querySelectorAll('[hidden]')]
        .filter(e => getComputedStyle(e).display !== 'none').length
  - 이 빌드가 «안 만드는» 페이지는 안 본다. 갤러리가 그렇다.
  - `visibility` · `opacity` · 화면 밖으로 밀어내는 숨김은 안 본다.
    `hidden` 속성을 쓰는 자리만 본다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LEDGER = os.path.join(HERE, 'hiddencheck_grandfather.txt')

# 스크립트가 hidden 으로 숨기는 자리. `==` 는 비교라 뺀다.
USES = re.compile(
    r'\.hidden\s*=(?!=)'
    r'|setAttribute\(\s*[\'"]hidden[\'"]'
    r'|toggleAttribute\(\s*[\'"]hidden[\'"]')

# 안전망. 선택자 모양은 안 따지고 `!important` 만 본다.
NET = re.compile(r'\[hidden\][^{]*\{[^}]*display\s*:\s*none\s*!\s*important')

SCRIPT = re.compile(r'<script\b[^>]*>(.*?)</script>', re.S | re.I)
STYLE = re.compile(r'<style\b[^>]*>(.*?)</style>', re.S | re.I)


def hides(html):
    """스크립트 «안» 에서만 찾는다. 본문의 `hidden` 속성은 숨기는 행위가 아니다."""
    return sum(len(USES.findall(s)) for s in SCRIPT.findall(html))


def netted(html):
    """안전망이 있나. `<style>` 안만 본다."""
    return any(NET.search(s) for s in STYLE.findall(html))


def kat():
    """알려진 답으로 먼저 시험한다 (커널 원칙 1).

    이 관문이 제 일을 하는지는 «내가 답을 아는 입력» 으로만 알 수 있다.
    특히 4번. 본문에 `hidden` 속성이 박힌 것은 위반이 아니다. 그걸 잡으면
    관문이 헛울고, 한 번 헛울면 다음부터 아무도 안 본다.
    """
    S, T = '<style>%s</style>', '<script>%s</script>'
    cases = [
        ('숨기는데 안전망 없음',
         S % '.r{display:grid}' + T % 'a.hidden=!x', False),
        ('안전망이 generic',
         S % '.r{display:grid}[hidden]{display:none!important}'
         + T % 'a.hidden=!x', True),
        ('안전망이 특정 선택자 · important 있음',
         S % '.r[hidden],.g[hidden]{display:none!important}'
         + T % 'a.hidden=!x', True),
        ('안전망에 important 가 없음',
         S % '.mclash[hidden]{display:none}' + T % 'a.hidden=!x', False),
        ('본문 hidden 속성은 숨기는 «행위» 가 아니다',
         S % '.r{display:grid}' + '<div hidden></div>' + T % 'go()', True),
        ('setAttribute 로 숨김',
         S % '.r{display:grid}' + T % 'e.setAttribute("hidden","")', False),
        ('비교 `==` 는 숨김이 아니다',
         S % '.r{display:grid}' + T % 'if(a.hidden==1)go()', True),
        ('hidden 을 안 쓰고 display 로 숨김',
         S % '.r{display:grid}' + T % 'a.style.display="none"', True),
    ]
    bad = []
    for name, html, want in cases:
        got = (hides(html) == 0) or netted(html)
        if got != want:
            bad.append(name)
    return len(cases) - len(bad), len(cases), bad


def read_ledger():
    if not os.path.isfile(LEDGER):
        return set()
    out = set()
    for ln in io.open(LEDGER, encoding='utf-8'):
        ln = ln.strip()
        if ln and not ln.startswith('#'):
            out.add(ln)
    return out


def write_ledger(got):
    lines = [
        '# 스크립트가 hidden 으로 숨기는데 안전망 한 줄이 없는 페이지.',
        '# 고칠 한 줄:  [hidden]{display:none!important}',
        '#',
        '# 명부는 면제가 아니다. 이 줄 수가 남은 일의 크기다. 줄이면서 지운다.',
        '# 새로 생기면 빌드가 선다.',
        '',
    ]
    io.open(LEDGER, 'w', encoding='utf-8').write(
        '\n'.join(lines + sorted(got)) + '\n')


def main(vault=None, pages=None):
    import searchbox
    vault = vault or os.path.join(os.path.dirname(HERE))
    ok, tot, bad = kat()
    print('  자가검증 %d/%d %s' % (ok, tot, '통과' if not bad else bad))
    if bad:
        print('  [!] 이 관문 자체가 틀렸습니다. 고치기 전에는 결과를 못 믿습니다.')
        return False

    targets = searchbox.public_pages(vault, pages or [])
    found, seen = set(), 0
    for rel in targets:
        fp = os.path.join(vault, rel.replace('/', os.sep))
        if not os.path.isfile(fp):
            continue
        t = io.open(fp, encoding='utf-8', errors='replace').read()
        n = hides(t)
        if not n:
            continue
        seen += 1
        if not netted(t):
            found.add(rel)

    # ★ 「검사할 것이 없었다」와 「위반이 없었다」는 다른 사실이다 ([3.44]).
    if not targets:
        print('  [!] 공개 페이지를 한 장도 못 봤습니다. 검사가 헛돌았습니다')
        return False
    print('  공개 페이지 %d장 · 그중 스크립트가 hidden 으로 숨기는 것 %d장'
          % (len(targets), seen))

    old = read_ledger()
    new = found - old
    gone = old - found
    print('  안전망 없는 페이지 %d장 (명부 %d장)' % (len(found), len(old)))
    if gone:
        print('  고쳐진 것 %d장: %s' % (len(gone), ' · '.join(sorted(gone))))
        write_ledger(found)
    if new:
        print('  [!] 안전망 없이 hidden 으로 숨기는 페이지가 새로 생겼습니다')
        for rel in sorted(new):
            print('      %s' % rel)
        print('      el.hidden 은 브라우저 기본 시트라 제작자 CSS 의 display')
        print('      한 줄에 집니다. 아래를 그 페이지 <style> 에 넣으세요.')
        print('        [hidden]{display:none!important}')
        print('      명부(%s)에 적으면 통과하지만, 그건 빚입니다.'
              % os.path.basename(LEDGER))
        return False
    return True


if __name__ == '__main__':
    # ★ 손으로 돌릴 때 `pages` 를 안 주면 `public_pages` 가 씨앗이 없어 «1장» 만
    #   돌려준다. 그리고 이 관문은 그 1장을 보고 「통과」를 찍는다.
    #   실측: 처음 돌렸을 때 정확히 그랬다. 내가 막으려던 모양을 내가 했다.
    #   그래서 손으로 돌 때는 폴더를 직접 읽어 씨앗을 채운다.
    _v = os.path.dirname(HERE)
    sys.exit(0 if main(_v, sorted(os.listdir(_v))) else 1)
