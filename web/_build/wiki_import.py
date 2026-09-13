# -*- coding: utf-8 -*-
"""foothold-wiki 흡수 1단계 (#72): rl · nav · cv · ros2 4쪽을 본문 무손실 이식.

  왜 이 방식인가 (결정 20260830-hub-v3 §3)
    wiki 는 잘 짜인 완결 HTML 이다 (오현민 작성). md 로 변환하면 표·코드·단계
    구조가 깨질 위험이 있어, 1단계는 **본문을 그대로** 가져오고 겉(상단바·테마)만
    우리 것을 입힌다. 2단계(md 정본화 · docs/guides 승격)는 원저자가 한다 (#72).

  무엇을 바꾸나
    · rail(자체 내비) 제거 -> 전역 상단바는 hubgen 이 주입한다
    · CDN 폰트 링크 제거 (자체 호스팅 원칙) · style.css 는 인라인
    · em dash 전면 정화 (철칙 3 · 원문에 다수 실측)
    · 머리에 출처 띠: 작성 오현민 · 원본 foothold-wiki · md 정본화 예정
"""
import io
import os
import re
import sys
import urllib.request

import buildtime

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
BASE = 'https://foothold-wiki.vercel.app/'

# (wiki 파일, 우리 파일, 제목, 한 줄) — 제목·설명은 ia.VAULT_PAGE 와 일치해야 한다
PAGES = [
    ('ros2', 'tech-ros2-ref.html', 'ROS 2 레퍼런스',
     '큰 그림 · 통신 4형제 · rclpy · 패키지 · 디버깅. 1~3편의 심화 레퍼런스'),
    ('rl', 'tech-rl.html', '시뮬레이션 RL 레퍼런스',
     'Isaac Lab 선택 근거 · 험지 RL 표준 레시피 · 핵심 논문 5편'),
    ('nav', 'tech-slam-nav.html', 'SLAM · Nav2 레퍼런스',
     'Go2 와 ROS 2 연동 · SLAM 2D 메인 · Nav2 차동구동 설정'),
    ('cv', 'tech-cv.html', '컴퓨터 비전 교재',
     '이미지의 정체부터 YOLO 실측 · ROS 2 이미지 파이프라인까지 12절'),
]

CACHE = os.path.join(os.path.expanduser('~'), '.claude', 'cache', 'wiki-import')

# 정본 문서 페이지(docs_pages)의 치수. 여기 값을 지어내지 않고 실측에서 가져왔다.
BODY_SCALE = (
    # ★ 특이도 (팀장 9/1 실측 · 두 번 헛짚은 뒤 잡은 것)
    #   1) 처음엔 `main X` 로 썼다. wiki 는 `.card p` 처럼 «클래스» 로 쓰므로
    #      원소 선택자는 늘 진다. -> <main> 에 .fh-doc 를 붙여 같은 층으로 올렸다.
    #   2) 값은 «정본 문서(research-training-benchmarks) 렌더 실측» 이다.
    #      정본은 html 16px 위에서 body 15px 로 서고, 실효 px 로 본문 15 ·
    #      td 13.12 · code 13.5 · pre 12.16 을 낸다. 그 숫자를 그대로 쓴다.
    #      (rem 으로 옮겨 적으면 root 가 다른 페이지에서 또 갈라진다)
    '.fh-doc{font-size:15px;line-height:1.75;color:var(--ink)}'
    '.fh-doc p,.fh-doc li,.fh-doc .lede{font-size:15px;line-height:1.75}'
    '.fh-doc .why,.fh-doc .lede,.fh-doc .cmd .why{color:var(--ink-2)}'
    '.fh-doc h1,.fh-doc .hero h1{font-size:32px;font-weight:800;'
    'letter-spacing:-.02em;line-height:1.25}'
    '.fh-doc h2{font-size:20.48px;font-weight:800;line-height:1.75;'
    'margin:2.2rem 0 .7rem;padding-bottom:.35rem;border-bottom:1px solid var(--rule)}'
    '.fh-doc h3{font-size:16px;font-weight:800;line-height:1.75;margin:1.4rem 0 .5rem}'
    '.fh-doc h4{font-size:15px;font-weight:700;margin:1.1rem 0 .4rem}'
    '.fh-doc h5{font-size:13.5px;font-weight:700;margin:1rem 0 .35rem}'
    '.fh-doc .hero,.fh-doc .card,.fh-doc .box,.fh-doc .panel,.fh-doc .call,'
    '.fh-doc .stamp{border-radius:8px;border:1px solid var(--rule);'
    'background:var(--card)}'
    '.fh-doc table{border-collapse:collapse;width:100%}'
    '.fh-doc th,.fh-doc td{font-size:13.12px;line-height:1.75;'
    'border-bottom:1px solid var(--rule);padding:.5rem .7rem;text-align:left}'
    '.fh-doc th{font-weight:700;color:var(--ink-2)}'
    '.fh-doc code,.fh-doc kbd{font-family:ui-monospace,Consolas,monospace;'
    'font-size:13.5px;background:var(--paper-2);border-radius:3px;padding:0 .25em}'
    '.fh-doc pre{font-size:12.16px;line-height:1.7;background:var(--paper-2);'
    'border:1px solid var(--rule);border-radius:8px;padding:.9rem 1rem;'
    'overflow-x:auto}'
    '.fh-doc pre code{font-size:inherit;background:none;padding:0}'
    # ★ 9/1 화면 실측 (팀장 「여전히 tech 가 디자인 시스템과 안 맞는다」).
    #   앞서 나는 «치수» 만 재고 «생김새» 를 안 봤다. 글자 크기는 맞았는데
    #   화면은 딴 문서였다. 정본과 나란히 놓고 본 차이 넷을 여기서 덮는다.
    #   ① 히어로가 큰 카드 박스 (정본은 박스가 없다)
    #   ② h2 번호가 <span class="n"> 로 강조색 (정본은 «0. 세 줄» 처럼 조용하다)
    #   ③ 표 머리가 대문자 + 2px 밑줄 (정본은 그냥 소문자 1px)
    #   ④ 히어로 안 lede 가 본문보다 크다
    '.fh-doc .hero{background:none;border:0;border-radius:0;padding:0;'
    'margin:0 0 2.2rem;overflow:visible}'
    '.fh-doc .hero .eyebrow{font-size:.66rem;font-weight:800;letter-spacing:.16em;'
    'text-transform:uppercase;color:var(--dim);display:block;margin-bottom:.4rem}'
    '.fh-doc h2 .n{color:var(--ink-3);font-weight:700;margin-right:.42rem;'
    'font-size:1em;letter-spacing:0}'
    '.fh-doc h2 .n::after{content:"."}'
    '.fh-doc th{text-transform:none;letter-spacing:0;font-size:13.12px;'
    'color:var(--ink-2);border-bottom:1px solid var(--rule);white-space:normal;'
    'padding:.5rem .7rem;background:none}'
    '.fh-doc h2{border-top:0}'
    '.fh-doc a{color:var(--dim)}'
)


# ★ 팀장 지시 9/1: 「명령어는 bash 는 bash 스타일, python 은 python 스타일로
#   문법 강조하고 클립보드로 복사할 수 있게」. 정본 문서에는 이미 있는 부품이라
#   같은 CSS·스크립트를 이식본에도 싣는다 (새로 만들지 않는다).
CODEBLOCK = (
    '<style id="fh-cb">'
    '.cb{margin:1rem 0;border:1px solid var(--rule);background:#0f141b;'
    'border-radius:8px;overflow:hidden}'
    '.cb-h{display:flex;align-items:center;gap:.5rem;padding:.3rem .6rem;'
    'background:#1a212b;border-bottom:1px solid #2b323d;font-size:.62rem;'
    'font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#7d8693}'
    '.cb-h .copy{margin-left:auto;background:#232b36;border:1px solid #39424f;'
    'color:#c8cfd8;font-family:inherit;font-size:.62rem;font-weight:800;'
    'letter-spacing:.06em;padding:.16rem .5rem;border-radius:3px;cursor:pointer;'
    'transition:.14s}'
    '.cb-h .copy:hover{background:var(--dim);border-color:var(--dim);color:#fff}'
    '.cb-h .copy.done{background:#1b6b4a;border-color:#1b6b4a;color:#fff}'
    '.fh-doc .cb pre{margin:0;padding:.75rem .85rem;overflow-x:auto;'
    'color:#dfe4ea;background:none;border:0;border-radius:0;'
    "font-family:'Consolas','D2Coding',ui-monospace,monospace;"
    'font-size:12.16px;line-height:1.7}'
    '.cb pre .c{color:#6f7a88}'
    '</style>'
    '<script id="fh-cb-js">document.addEventListener("click",function(e){'
    'var b=e.target.closest&&e.target.closest(".copy");if(!b)return;'
    'var w=b.closest(".cb");var t=w&&w.querySelector("pre");'
    'if(!t)return;navigator.clipboard.writeText(t.innerText).then(function(){'
    'var o=b.textContent;b.textContent="\ubcf5\uc0ac\ub428";'
    'b.classList.add("done");setTimeout(function(){b.textContent=o;'
    'b.classList.remove("done")},1400)})});</script>')


_COPY_BTN = ('<button class="copy" type="button" '
             'aria-label="복사">복사</button>')


def codeblocks(body):
    """이식 본문의 <pre><code> 를 정본과 같은 코드 블록으로 바꾼다.

    ★ 팀장 지시 9/1: 「명령어는 bash 는 bash 스타일, python 은 python 스타일로
      문법 강조하고 클립보드 복사가 되게」. 정본 문서(md 경로)는 mdpage 가
      이미 그렇게 만든다. 이식본만 맨 <pre> 라 갈라져 있었다.
      같은 부품(hl.render + 복사 버튼 + .cb 틀)을 여기서도 쓴다.
    """
    import html as _H
    import hl as _hl

    def one(m):
        attrs, inner = m.group(1), m.group(2)
        lang = ''
        mm = re.search(r'(?:language-|lang-)([a-z0-9+#]+)', attrs or '')
        if mm:
            lang = mm.group(1)
        txt = _H.unescape(re.sub(r'<[^>]+>', '', inner))
        if not lang:
            # 언어 표기가 없으면 첫 줄로 짐작한다. 틀려도 강조만 안 될 뿐이다.
            head = txt.strip().split('\n')[0]
            # ★ 9/1 실측 정정: `$` 는 bash 프롬프트다. PowerShell 은 `PS>` 다.
            #   먼저 판이 `$ sudo apt ...` 를 PowerShell 로 잡아 ros2 문서 28개가
            #   전부 틀린 라벨을 달았다. 프롬프트 기호를 떼고 «명령» 을 본다.
            head = re.sub(r'^\s*[$#>]\s+', '', head)
            if re.match(r'^\s*(PS[ >]|Get-|Set-|New-|Remove-|Invoke-|conda |'
                        r'nvcc |nvidia-smi.exe)', head):
                lang = 'powershell'
            elif re.match(r'^\s*(sudo |apt |apt-get |cd |ls |export |source |'
                          r'ros2 |colcon |rosdep |pip |pip3 |python3 |git |'
                          r'docker |bash |sh |chmod |mkdir |echo |curl |wget |'
                          r'nvidia-smi|make |cmake )', head):
                lang = 'bash'
            elif re.match(r'^\s*(import |from |def |class |print\(|@|if __name__)',
                          head):
                lang = 'python'
        return ('<div class="cb"><div class="cb-h">%s%s</div><pre>%s</pre></div>'
                % (_H.escape(_hl.label(lang)), _COPY_BTN,
                   _hl.render(txt.rstrip('\n'), lang)))

    body = re.sub(r'<pre[^>]*>\s*<code([^>]*)>([\s\S]*?)</code>\s*</pre>',
                  one, body)

    # ★ 9/1 실측: rl · nav 는 <pre> 없이 <code> 만 쓴다 (블록 3개 · 8개).
    #   여러 줄이면 블록으로 본다. 한 줄짜리 인라인 코드는 그대로 둔다.
    def maybe(m):
        if '\n' not in m.group(2).strip():
            return m.group(0)
        return one(m)

    return re.sub(r'<code([^>]*)>([\s\S]*?)</code>', maybe, body)


def clean(t):
    """em dash 정화. 문장 부호 역할에 맞게."""
    t = t.replace(' — ', ' · ').replace('—', '·')
    return t


def strip_wiki_chrome(body):
    """원본 wiki 의 «이전/다음» 띠와 wiki 푸터를 걷어낸다.

    ★ 팀장 9/1 재지적: 「아직도 tech 쪽 문서들 수정이 안 되어 있네」.
      맞다. 링크를 «푸는» 것만 했고 띠와 푸터 자체는 안 지웠다. 그래서
      화면에는 링크 없는 «이전» 글자와 「FOOTHOLD 팀 위키 · 조사 기준일」
      푸터가 우리 푸터 위에 하나 더 있었다. 푸터가 두 줄로 보이던 원인이다.

      우리 사이트에는 전역바와 우리 푸터가 있다. 남의 사이트 목차 띠가
      그 위에 겹칠 이유가 없다.
    """
    n0 = body.count('class="pagerow"') + body.count('<footer')
    body = re.sub(r'<div class="pagerow">[\s\S]*?</div>\s*', '', body)
    body = re.sub(r'<footer[^>]*>[\s\S]*?</footer>\s*', '', body)
    left = body.count('class="pagerow"') + body.count('<footer')
    return body, n0 - left, left


def fetch(name):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name)
    # 로컬 캐시 우선. 원격이 죽어도 빌드는 돈다 (기존 이식분 유지).
    try:
        with urllib.request.urlopen(BASE + name, timeout=20) as r:
            t = r.read().decode('utf-8')
        io.open(p, 'w', encoding='utf-8', newline='\n').write(t)
        return t
    except Exception as e:
        if os.path.isfile(p):
            print('  [!] wiki 원격 실패, 캐시 사용: %s' % name)
            return io.open(p, encoding='utf-8').read()
        raise RuntimeError('wiki %s 를 못 가져옴: %s' % (name, e))


def _cut(src, start):
    """start 의 여는 중괄호부터 짝이 맞는 닫는 중괄호까지 잘라 돌려준다.

    ★ 9/1 두 번째 시도. 첫 시도는 «부족한 } 를 끝에 붙이기» 였는데, 개수만
      맞고 «닫는 자리» 가 틀려 규칙들이 여전히 미디어 안에 갇혔다.
      개수를 세는 것과 자리를 맞추는 것은 다른 일이다. 정규식으로는
      중첩을 못 센다. 그래서 스캐너로 바꾼다.
    """
    i = src.find('{', start)
    if i < 0:
        return None
    d = 0
    for k in range(i, len(src)):
        if src[k] == '{':
            d += 1
        elif src[k] == '}':
            d -= 1
            if d == 0:
                return src[start:k + 1]
    return None


def _blocks(src):
    """토큰 블록을 중첩까지 세면서 뽑는다. 미디어 블록은 통째로."""
    out = []
    for m in re.finditer(
            r'(?:^|\})\s*(@media[^{]*prefers-color-scheme[^{]*|'
            r':root(?:\[data-theme="[a-z]+"\])?|'
            r'html\[data-theme="[a-z]+"\])\s*\{', src):
        seg = _cut(src, m.start(1))
        if not seg:
            continue
        if '--' not in seg:          # 토큰이 없는 블록은 버린다
            continue
        if seg not in out:
            out.append(seg)
    return out


def _balance(css):
    """중괄호를 맞춘다. 모자라면 채우고, 남으면 잘라낸 뒤 알린다.

    ★ 9/1 근본 원인 (팀장이 네 번 지적한 «테마가 로고만 바뀐다»).
      아래 정규식이 `@media (prefers-color-scheme:dark){ :root{...} }` 를 뽑을 때
      바깥 `}` 를 «옵션(}? 로)» 으로 뒀다. 그래서 미디어 블록이 «열린 채» 실렸고,
      그 뒤의 html[data-theme="light"] · [dark] 규칙이 전부 그 안에 갇혔다.
      OS 가 다크면 미디어가 켜져 규칙이 살아나 «잘 된다» 로 보이고,
      OS 가 라이트면 통째로 죽어 배경이 안 바뀐다. 내 Chrome 이 다크라
      나는 계속 «고쳤다» 고 말했다 (원칙 3 을 정면으로 어겼다).
    """
    d = 0
    for ch in css:
        if ch == '{':
            d += 1
        elif ch == '}':
            d -= 1
    if d > 0:
        print('  [!] 브랜드 토큰 중괄호 %d개 모자람. 채운다' % d)
        css += '}' * d
    elif d < 0:
        print('  [!] 브랜드 토큰 중괄호 %d개 남음' % -d)
    return css


def brand_tokens():
    """우리 브랜드 토큰을 정본(research.html)에서 그대로 뽑는다. 손 복사 금지.

    ★ 팀장 지적 (2026-08-30): 이식 페이지가 wiki 팔레트로 남아 브랜드가 아니었다.
      wiki 는 토큰 이름이 다르다(--bg·--brand vs --paper·--dim). 값만 바꾸면
      또 갈라지니, 우리 토큰 블록을 통째로 싣고 wiki 이름을 우리 이름에 «연결»한다.
    """
    # 6KB 만 읽다가 html[data-theme] 블록(38KB 지점)을 놓쳤다. 전체를 읽는다.
    src = io.open(os.path.join(VAULT, 'research.html'),
                  encoding='utf-8', errors='replace').read()
    # ★ 9/1 다섯째 겹: 스캐너에 HTML 전체를 줬더니 선택자에 마크업이 섞여
    #   기준 팔레트(:root 의 --paper)를 통째로 놓쳤다. CSS 만 준다.
    css = '\n'.join(re.findall(r'<style[^>]*>([\s\S]*?)</style>', src))
    blocks = _blocks(css)
    bridge = (':root{--bg:var(--paper);--panel:var(--card);--sub:var(--ink-3);'
              '--line:var(--rule);--brand:var(--dim);--brand-ink:var(--dim-ink,#0b3d2e);'
              '--brand-soft:var(--dim-soft);--brand-line:var(--dim);'
              '--accent:var(--note);--accent-soft:var(--note-soft);'
              '--code:var(--paper-2);--shadow:none}'
              "body{font-family:'Pretendard','Malgun Gothic','Segoe UI',"
              'system-ui,sans-serif;background:var(--paper);color:var(--ink)}')
    return _balance('\n'.join(blocks)) + '\n' + bridge


def rescale(css):
    """수입한 wiki CSS 의 글자 크기를 우리 척도로 옮긴다.

    ★ 팀장 9/2: 「4번, 트랙 A 1, 트랙 B 1·2 문서는 우리 컬러 시스템(폰트)을
      가져가지 않은 것 같다」. 맞다. 실측하니 이렇다.

        정본 (md 생성 3쪽)   h1 32 · h2 20.48 · h3 16 · 본문 15 · b 15
        wiki 이식 4쪽        b · span · strong · a 가 13px  (254곳)

      본문 크기를 «클래스마다» 잡으면 새 클래스가 나올 때마다 또 어긋난다.
      수입하는 순간 **표에 없는 크기를 우리 값으로 옮긴다.** 한 자리에서 끝난다.

      코드·표·주석 상자는 원래 작아야 하므로 그 선택자는 건드리지 않는다.
    """
    keep = re.compile(r'(?:^|[\s,>+~])(?:pre|code|table|thead|tbody|th|td)\b'
                      r'|\.cb\b|\.anno\b|\.hl\b|\.tw\b')
    # 우리 척도. 왼쪽이 wiki 값, 오른쪽이 우리 값
    table = {'13px': '15px', '13.5px': '15px', '14px': '15px',
             '12px': '12.16px', '11.5px': '11.68px', '10.5px': '10.56px',
             '15.5px': '15px', '17px': '16px'}
    out, n = [], 0
    for block in re.split(r'(?<=\})', css):
        sel = block.split('{')[0]
        if not block.strip() or keep.search(sel):
            out.append(block)
            continue

        def sub(m, _n=[0]):
            v = table.get(m.group(1))
            if not v:
                return m.group(0)
            _n[0] += 1
            return 'font-size:' + v

        new = re.sub(r'font-size:\s*([\d.]+px)', sub, block)
        if new != block:
            n += 1
        out.append(new)
    return ''.join(out), n


def style():
    css = fetch('style.css')
    # 겉(레일·본문 배치·wiki 자체 토큰) 규칙은 걷어낸다. 본문 구조 규칙만 남긴다.
    out, skip = [], 0
    for block in re.split(r'(?<=\})', css):
        sel = block.split('{')[0].strip()
        if re.match(r'^(html|body|:root|\.rail\b|\.rail |\.brand|\.pages|\.tagline|'
                    r'\.toc|#themeBtn|\.layout)', sel):
            skip += 1
            continue
        # ★ 브랜드 정합 (팀장 지적 2026-08-31 · BRAND_BIBLE: no gradients/shadows).
        #   장식 선언만 걷어낸다. 구조 규칙은 남는다.
        if 'gradient' in block or 'box-shadow' in block:
            block = re.sub(r'[^;{}]*(?:gradient|box-shadow)[^;}]*;?', '', block)
            skip += 1
        # ★ 둥근 상자 위/왼쪽의 두꺼운 «강조 바» 는 철칙 3 이 금지한 형태다
        #   (팀장 8/31: 「위쪽, 왼쪽에 바 형태로 AI Slop 이 싫었던 거뿐」).
        #   구분은 면(background)과 테두리 «색» 으로 한다. 바 선언만 뺀다.
        # ★ 9/1 정정: 처음엔 border-radius 가 있는 것만 봤다. wiki 의 `.subtoc a`
        #   는 각진 상자라 통째로 빠져나갔다. 바는 모서리와 무관하다 (brandcheck
        #   와 같은 판정: «면이나 테두리를 가진 상자» 위의 위/왼쪽 바).
        if re.search(r'background(?:-color)?\s*:|border\s*:\s*[\d.]+px', block)                 and re.search(r'border-(?:top|left):\s*(?:[2-9]|\d\d|\d\.\d)px',
                              block):
            block = re.sub(
                r'[^;{}]*border-(?:top|left):\s*[\d.]+px[^;}]*;?', '', block)
            skip += 1
        out.append(block)
    # 팀장 9/2: 「코드 부분 컬러 디자인 안 했다」. 맞다. 토큰은 306개 붙었는데
    #   전부 같은 색이었다. 여기가 원본 wiki 의 style.css 만 쓰고 hl.CSS(색 정의)를
    #   안 넣었기 때문이다. .c 하나만 있던 것은 wiki 원본에 우연히 있던 규칙이다.
    #   색이 다른지 안 재고 «토큰 수» 만 보고 통과로 셌다 (원칙 3).
    import hl as _hl2
    _colors = _hl2.CSS.replace('<style>', '').replace('</style>', '')
    # 표에 없는 글자 크기를 우리 척도로 옮긴다 (팀장 9/2)
    _rescaled, _nr = rescale(''.join(out))
    out = [_rescaled]
    if _nr:
        print('  글자 크기 %d개 규칙을 우리 척도로 옮겼습니다' % _nr)
    return clean(''.join(out)) + chr(10) + brand_tokens() + chr(10) + _colors, skip


def main():
    css, skipped = style()
    made = []
    for src, dst, title, lede in PAGES:
        t = fetch(src + '.html')
        m = re.search(r'<main[^>]*>(.*)</main>', t, re.S)
        if not m:
            print('  [!] %s: <main> 이 없다. 건너뜀' % src)
            continue
        body = clean(m.group(1))
        # 남의 사이트 목차 띠와 푸터를 걷어낸다 (팀장 9/1 재지적)
        body, _n_strip, _left = strip_wiki_chrome(body)
        if _left:
            print('  [!] %s: wiki 띠·푸터 %d개가 안 지워졌다. 이식 중단'
                  % (src, _left))
            continue

        # 원문 링크는 wiki 내부 상호참조 -> 이식된 이름으로 바꾼다
        for s2, d2, _t2, _l2 in PAGES:
            body = body.replace('href="%s.html"' % s2, 'href="%s"' % d2)
        # ★ 이름을 나열하면 늘 빠진다 (learn-errors · learn-ros2 를 놓쳐 죽은 링크 2개).
        #   이식한 것만 화이트리스트로 두고, 나머지 wiki 내부 링크는 전부 원본으로.
        ours = {d2 for _s2, d2, _t2, _l2 in PAGES}

        def _ext(m):
            href = m.group(1)
            if href.split('#')[0] in ours:
                return m.group(0)
            # ★ 팀장 지적 9/1: 「하단에 foothold-wiki 로 연결된 내비 정리하라고
            #   했냐 안 했냐」. 맞다. 나는 죽은 링크를 피하려고 «원본 wiki 로
            #   내보냈다». 그건 우리 사이트에서 남의 사이트로 나가는 문이다.
            #   아직 이식 안 된 것은 링크를 «풀어» 글자로만 남긴다.
            #   이식되면 위 화이트리스트에 들어와 자동으로 링크가 산다 (#72).
            return 'data-unported="%s"' % href

        body = re.sub(r'href="([a-z0-9][a-z0-9._-]*\.html(?:#[^"]*)?)"', _ext, body)
        # 링크 껍데기를 벗긴다 (글자는 남긴다)
        body = re.sub(r'<a[^>]*data-unported="[^"]*"[^>]*>([\s\S]*?)</a>',
                      r'\1', body)
        body = codeblocks(body)
        n_h2 = len(re.findall(r'<h2', body))
        # ★ 원칙 2: 내용이 얇아졌으면 소리를 낸다. 원문 h2 수와 대조.
        n_src = len(re.findall(r'<h2', t))
        if n_h2 < n_src:
            print('  [!] %s: 절 %d/%d 만 남음. 이식 중단' % (src, n_h2, n_src))
            continue
        page = (
            '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>%s · FOOTHOLD</title>\n'
            '<script>try{var t=localStorage.getItem("theme");'
            'if(t)document.documentElement.dataset.theme=t;'
            'else if(matchMedia("(prefers-color-scheme: dark)").matches)'
            'document.documentElement.dataset.theme="dark"}catch(e){}</script>\n'
            '<style>%s\nmain{max-width:1040px;margin:0 auto;padding:1.5rem 1.4rem 4rem}'
            '.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%%}'
            '.tw table{min-width:max-content}'
            # ★ 2026-09-08 감사 F-04. 이식본은 upstream CSS 를 그대로 싣는데
            #   거기에 overflow-wrap 짝이 없다. 360px 에서 긴 명령·파라미터 이름
            #   (qos_overrides.* 같은 것)이 안 끊겨 페이지가 126px 늘어났다.
            #   본문 요소에만 건다. pre 와 표는 .tw 안에서 스스로 스크롤한다.
            # ★ 2026-09-09 라이브 실측. 위 목록으로는 샜다. tech-* 넉 장이
            #   390px 에서 가로로 30px 밀렸고, 범인은 .hero 안의 «nav/perception/»
            #   같은 경로였다. div 라서 목록 어디에도 안 걸렸다.
            #   요소를 나열하는 규칙은 다음 마크업에서 또 샌다. overflow-wrap 은
            #   상속되므로 범위에 한 번 걸고, 코드만 되돌린다.
            #   (pre·code 는 .tw 안에서 스스로 가로 스크롤한다. 거기서 아무 데나
            #    끊으면 명령을 잘못 읽게 된다.)
            'main{overflow-wrap:anywhere;word-break:keep-all}'
            'main pre,main code,main kbd,main samp{overflow-wrap:normal;word-break:normal}'
            # ★ 2026-09-09. 줄바꿈을 다 고쳤는데도 tech-* 넉 장이 390px 에서
            #   여전히 30px 밀렸다. 원소를 하나씩 숨겨 좁히니 범인은 글자가
            #   아니라 .hero::after 였다. 240px 짜리 장식이 right:-60px 로
            #   놓여 있다. 넓은 화면에선 여백이 삼키지만 좁은 화면에선
            #   페이지를 민다. 자식 상자는 전부 폭 안에 있어 «넘치는 원소가
            #   없다» 고 보였다. 의사요소는 children 에 안 잡힌다.
            #   좁은 화면에서만 잘라낸다. 넓은 화면의 생김새는 그대로 둔다.
            # 명시도를 맞춘다. 위 .fh-doc .hero 규칙이 overflow:visible 을 갖고 있어
            #   main .hero (0,1,1) 로는 진다. 실측: 규칙이 파싱은 됐는데 안 먹었다.
            '@media (max-width:640px){main.fh-doc .hero{overflow:hidden}}'
            '</style>\n</head>\n<body>\n'
            '<main class="fh-doc">\n'
            '<p style="font-size:.74rem;color:var(--ink-3,#8b949e);border:1px dashed '
            'var(--rule,#30363d);border-radius:7px;padding:.55rem .9rem">'
            # ★ 2026-09-08. 날짜가 없었다. 문서 표준은 「작성: 이름 · YYYY-MM-DD HH:MM」
            #   인데 이 넉 장만 이름까지였다. 이식본이라 «작성» 시각은 우리 것이
            #   아니므로, 우리가 아는 사실인 «이식» 시각을 적는다. 매 빌드마다
            #   원본을 다시 가져오므로 이 값이 곧 본문의 나이다.
            '작성 오현민 · foothold-wiki 에서 이식 (#72 1단계) · 이식 %s · '
            '고칠 것이 있으면 이슈로. md 정본화(2단계)가 남아 있다</p>\n'
            '%s\n</main>\n</body>\n</html>\n'
            % (title, css, buildtime.stamp(), body))
        # ★ 본문 규격을 정본 문서 페이지에 맞춘다 (팀장 9/1 실측:
        #   본문 11.84px vs 정본 16px · h1 38 vs 32 · 카드 반경 20 vs 8).
        #   BODY_SCALE 은 % 를 담고 있어 포맷 문자열 «안» 에 두면 안 된다.
        #   포맷이 끝난 뒤 style 닫기 직전에 끼운다.
        page = page.replace('</style>', BODY_SCALE + '</style>', 1)
        page = page.replace('</head>', CODEBLOCK + '</head>', 1)
        io.open(os.path.join(VAULT, dst), 'w', encoding='utf-8',
                newline='\n').write(page)
        made.append((dst, title, n_h2))
    if len(made) < len(PAGES):
        print('  [!] %d/%d 만 이식됨' % (len(made), len(PAGES)))
        return False
    print('  wiki 이식 %d쪽 (겉 규칙 %d개 제거): %s'
          % (len(made), skipped,
             ' · '.join('%s %d절' % (t, n) for _d, t, n in made)))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
