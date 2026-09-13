# -*- coding: utf-8 -*-
"""코드 블록 문법 강조: 외부 라이브러리 없이, 우리가 실제로 쓰는 3개 언어만.

  왜 만드나. 팀원이 복사해서 그대로 실행하는 코드다.
  전부 같은 색이면 **명령과 인자와 경로가 구분되지 않아** 눈으로 검증할 수 없다.
  실제 PowerShell/Python 창에서 보이는 색과 비슷하게 맞춰, 화면과 문서를 오갈 때
  같은 것을 같게 보이게 한다.

  ⚠️ 외부 CDN 금지(사이트 제약)이므로 highlight.js 류를 쓰지 않는다.
     완전한 파서가 아니라 **읽기 보조**가 목적이다. 오탐이 나도 코드가 깨지지 않게
     항상 HTML 이스케이프를 먼저 하고, 그 위에 span 만 씌운다.

  지원: powershell · python · bash · text(강조 없음)
"""
import html as H
import re

# ── 토큰 종류 → CSS 클래스 ──
#   k=키워드 · f=명령/함수 · s=문자열 · n=숫자 · v=변수 · c=주석 · o=연산자/플래그
PS_CMDLETS = (
    # 별칭도 넣는다. 팀원이 실제로 치는 건 Set-Location 이 아니라 cd 다
    'cd|ls|dir|cls|cat|type|where|mkdir|rm|cp|mv|conda|pip|python|git|nvidia-smi|curl|ssh|scp|tailscale|winget|choco|code|'
    'Get-Process|Get-ChildItem|Get-Content|Get-Command|Get-Service|Get-WindowsCapability|'
    'Set-Content|Set-Location|Set-Service|Add-WindowsCapability|Start-Service|Stop-Process|'
    'Stop-Service|New-Item|New-NetFirewallRule|Remove-Item|Select-Object|Where-Object|'
    'ForEach-Object|Measure-Object|Test-Path|Out-File|Write-Host|Invoke-WebRequest|'
    'Copy-Item|Move-Item|Expand-Archive|Resolve-Path|Restart-Computer'
)
PS_KEYWORDS = (
    'if|else|elseif|foreach|for|while|do|function|param|return|try|catch|finally|'
    'switch|break|continue|in|not|and|or'
)

PY_KEYWORDS = (
    'False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|'
    'except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|'
    'return|try|while|with|yield|self'
)
PY_BUILTINS = (
    'print|len|range|list|dict|set|tuple|int|float|str|bool|open|enumerate|zip|map|'
    'filter|sorted|sum|min|max|abs|type|isinstance|super|getattr|setattr|hasattr'
)

SH_CMDS = (
    'cd|ls|cat|echo|grep|sed|awk|mkdir|rm|cp|mv|chmod|chown|export|source|sudo|apt|'
    'apt-get|pip|python|python3|git|curl|wget|ssh|scp|ros2|colcon|conda|docker|make|'
    'systemctl|nvidia-smi|tailscale'
)


def _protect(text):
    """이스케이프 먼저. 이후 모든 치환은 이스케이프된 문자열 위에서만 한다."""
    return H.escape(text)


ENTITY = re.compile(r'&(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);')


def _spans(text, rules):
    """겹치지 않게 토큰을 씌운다.

       ★ 앞에서부터 순차 치환하면 방금 넣은 <span class="k"> 의 'class' 가
         다음 규칙에 다시 잡힌다. 그래서 **위치를 먼저 모으고 뒤에서 앞으로** 씌운다.
         (용어 툴팁에서 같은 실수를 이미 한 번 했다. enrich.py 주석 참고)

       ★ HTML 엔티티는 **쪼개면 안 된다.** 주석 규칙 `#[^\\n]*` 이
         `&#x27;` 안의 `#` 을 물어서 `&` 와 `#x27;` 사이에 태그가 끼었고,
         브라우저에 `&#x27;` 가 글자 그대로 찍혔다(2026-08-05 실측).
         그래서 엔티티 구간을 **먼저 점유**해 어떤 규칙도 그 안을 건드리지 못하게 한다."""
    marks = []
    taken = []
    ents = [m.span() for m in ENTITY.finditer(text)]

    def free(a, b):
        return all(b <= x or a >= y for x, y in taken)

    def crosses_entity(a, b):
        """엔티티를 **반만** 덮는 매치만 버린다.
           통째로 덮는 건 괜찮다. 문자열 &quot;YES&quot; 는 엔티티를 포함해야 정상이다.
           (처음엔 엔티티를 taken 에 선점시켰다가 문자열 강조가 통째로 사라졌다.)"""
        return any(a < y and b > x and not (a <= x and b >= y) for x, y in ents)

    for cls, pat in rules:
        for m in re.finditer(pat, text):
            a, b = m.span(m.lastindex or 0)
            if crosses_entity(a, b):
                continue
            if free(a, b):
                taken.append((a, b))
                marks.append((a, b, cls))
    for a, b, cls in sorted(marks, reverse=True):
        text = text[:a] + '<span class="%s">%s</span>' % (cls, text[a:b]) + text[b:]
    return text


def verify(rendered, original):
    """강조 결과가 안전한지 확인한다. (a) 원문이 그대로인가 (b) 엔티티가 안 쪼개졌나"""
    plain = re.sub(r'</?span[^>]*>', '', rendered)
    if H.unescape(plain) != original:
        return '원문이 변형됨'
    # 태그로 쪼개진 엔티티 찾기: 유효한 엔티티가 아닌 & 가 남아 있으면 깨진 것
    for m in re.finditer(r'&', plain):
        if not ENTITY.match(plain, m.start()):
            return '엔티티가 쪼개짐 (%r 부근)' % plain[max(0, m.start() - 25):m.start() + 25]
    return None


def powershell(t):
    return _spans(t, [
        ('c',  r'#[^\n]*'),
        ('s',  r'&quot;(?:[^&]|&(?!quot;))*&quot;|&#x27;[^&#]*&#x27;'),
        ('v',  r'\$(?:env:)?[A-Za-z_][A-Za-z0-9_:]*'),
        ('f',  r'\b(?:%s)\b' % PS_CMDLETS),
        ('k',  r'\b(?:%s)\b' % PS_KEYWORDS),
        ('o',  r'(?<![\w-])-{1,2}[A-Za-z][A-Za-z0-9_-]*'),
        ('n',  r'\b\d+(?:\.\d+)*\b'),
    ])


def python(t):
    return _spans(t, [
        ('c',  r'#[^\n]*'),
        ('s',  r'&quot;&quot;&quot;[\s\S]*?&quot;&quot;&quot;'
               r'|&quot;(?:[^&\n]|&(?!quot;))*&quot;'
               r'|&#x27;(?:[^&\n]|&(?!#x27;))*&#x27;'),
        ('f',  r'\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()'),
        ('k',  r'\b(?:%s)\b' % PY_KEYWORDS),
        ('b',  r'\b(?:%s)\b' % PY_BUILTINS),
        ('n',  r'\b\d+(?:\.\d+)*\b'),
    ])


SH_SUB = (
    'install|update|upgrade|remove|purge|list|show|run|build|create|launch|'
    'record|play|call|send_goal|get|set|dump|load|clone|commit|push|pull|'
    'checkout|status|add|init|activate|node|topic|service|action|param|'
    'interface|pkg|bag|graph|console|echo|info|start|stop|enable|restart'
)


def bash(t):
    """★ 9/1 팀장 재지적: ros2 레퍼런스만 색이 거의 없다.

    실측: 블록당 색 토큰이 1~3개, 7개 블록은 0개였다 (cv 는 블록당 약 10개).
    원인은 프롬프트다. 명령 규칙이 «줄 처음 또는 | && ; 뒤» 만 봤는데
    이 문서의 줄은 전부 «$ » 로 시작한다. 그래서 첫 명령이 통째로 안 잡혔다.
    프롬프트를 건너뛰고, 프롬프트 자체도 옅게 칠한다.
    부속 명령(apt 뒤의 install)과 이어붙임(&& | > >>)도 잡는다.
    """
    return _spans(t, [
        ('c',  r'#[^\n]*'),
        ('s',  r'&quot;(?:[^&\n]|&(?!quot;))*&quot;|&#x27;[^&#\n]*&#x27;'),
        ('v',  r'\$\{?[A-Za-z_][A-Za-z0-9_]*\}?'),
        # 프롬프트. 붙여 넣을 때 빼야 하는 글자라 옅게 구분한다
        ('o',  r'(?:^|\n)[ \t]*[$#>](?= )'),
        # 명령. 프롬프트 · 파이프 · && · ; 뒤 어디서든
        ('f',  r'(?:^|\n|\||&amp;&amp;|;)[ \t]*(?:[$#>][ \t]+)?([a-z][a-z0-9_.-]*)'),
        # 부속 명령. apt install · ros2 topic list · git commit
        ('k',  r'(?<=[a-z0-9]) +(?:%s)(?![a-zA-Z0-9_-])' % SH_SUB),
        ('o',  r'(?<![\w-])-{1,2}[A-Za-z][A-Za-z0-9_-]*'),
        # 이어붙임 · 파이프 · 리다이렉트
        ('o',  r'&amp;&amp;|\|\||&gt;&gt;|&gt;|\|'),
        ('n',  r'\b\d+(?:\.\d+)*\b'),
    ])

LANGS = {
    'powershell': powershell, 'ps1': powershell, 'pwsh': powershell,
    'python': python, 'py': python,
    'bash': bash, 'sh': bash, 'shell': bash, 'console': bash,
}

# 화면 라벨: 팀원이 "어느 창에 붙여야 하나"를 바로 알게
LABEL = {
    'powershell': 'PowerShell', 'ps1': 'PowerShell', 'pwsh': 'PowerShell',
    'python': 'Python', 'py': 'Python',
    'bash': 'Bash / 우분투', 'sh': 'Bash', 'shell': 'Bash', 'console': '터미널',
    'text': '출력', '': '출력',
}


def render(code, lang=''):
    """raw 코드 → 이스케이프 + 강조된 HTML. 실패하면 이스케이프만 해서 돌려준다."""
    esc = _protect(code)
    fn = LANGS.get((lang or '').lower())
    if not fn:
        return esc
    try:
        return fn(esc)
    except Exception:
        return esc                       # 강조가 실패해도 코드는 반드시 보여야 한다


def label(lang):
    return LABEL.get((lang or '').lower(), (lang or 'text').upper())


CSS = r"""
/* ── 코드 문법 강조 ──
   실제 PowerShell / Python 창의 색감에 맞췄다. 화면과 문서를 오갈 때 같은 것이 같게 보이게. */
.cb pre .c{color:#6f7a88;font-style:italic}   /* 주석 */
.cb pre .k{color:#5eb0ef;font-weight:700}     /* 키워드 */
.cb pre .f{color:#f0c674}                     /* 명령 · 함수 */
.cb pre .b{color:#c39ac9}                     /* 파이썬 내장 */
.cb pre .s{color:#9ece6a}                     /* 문자열 */
.cb pre .n{color:#e59f6a}                     /* 숫자 */
.cb pre .v{color:#7ee0d0}                     /* 변수 */
.cb pre .o{color:#a9b4c2}                     /* 플래그 · 옵션 */
@media print{
  /* 종이에서는 색이 안 나올 수 있다. 굵기·기울기로도 구분되게 */
  .cb pre .c{color:#777!important;font-style:italic}
  .cb pre .k,.cb pre .f{color:#000!important;font-weight:700}
  .cb pre .s{color:#2a6b2a!important}
  .cb pre .n,.cb pre .v,.cb pre .o,.cb pre .b{color:#333!important}
}
"""
