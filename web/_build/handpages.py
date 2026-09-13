# -*- coding: utf-8 -*-
"""손 관리 페이지를 «소스에서» 새로 만든다 (mai-os#24 · 빌드 [0.6]).

  왜
    brief · index · setup 은 손으로 쓴 원본인데 빌드가 그 파일 «안에» 주입해 왔다.
    소스와 생성물이 한 파일에 섞이니 주입물이 쌓여도 아무도 못 봤다.
    실측: 빈 CSS 껍데기 77개(빌드마다 +1) · 옛 부트 스크립트 27개.

    이제 손으로 고칠 자리는 `_src/<이름>.base.html` 하나다.
    빌드는 매번 그 소스를 복사한 뒤 주입한다. 그래서
      · 주입물이 쌓일 수 없다 (매번 깨끗한 판에서 시작한다)
      · 「소스만으로 결과가 재현되는가」를 물을 수 있다

  정본은 `page_overrides.json` 이다
    어느 페이지가 어느 소스에서 오는지, 왜 override 하는지, 무엇을 허용하는지가
    거기 있다. 사람이 두 곳에 같은 값을 적지 않는다 (철칙 4).

  ★ 이 단계는 모든 주입기보다 «먼저» 돌아야 한다. 나중에 돌면 그 빌드의
    주입물을 통째로 지운다. build.py 의 [0.6] 자리가 그래서 맨 앞이다.
"""
import io
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
CONFIG = os.path.join(HERE, 'page_overrides.json')

# 마커가 «없는» 주입 흔적. 마커가 있는 것은 markercheck.OWNERS 가 정본이다.
#
# ★ 2026-09-02 독립 검수 지적. 전에는 여기에 문자열 목록을 따로 들었고,
#   그 목록이 brand:v1 · teamprofiles:v2 · search:v8 · home:v1 · status:v1 ·
#   recent:v1 · stamp:v1 · dark:v1 여덟을 몰랐다. 그래서 생성기 소유 블록이
#   그대로 든 소스를 «순수하다» 고 통과시켰다.
#
#   같은 규칙을 두 자리에 적으면 반드시 갈라진다 (커널 철칙 4).
#   그래서 마커 목록은 markercheck.OWNERS 에서 «파생» 만 한다.
#   아래 표에는 «마커가 없어서 파생할 수 없는 것» 만 남긴다.
NO_MARKER_RESIDUE = [
    ('판 띠 본문',    re.compile(r'<div class="bstamp"')),
    ('테마 부트 본문', re.compile(r'try\{var _t=localStorage')),
    ('NEW 배지 CSS', re.compile(r'span\.fh-new\{')),
    ('빈 껍데기',     re.compile(r'<style[^>]*>\s*(?:@[a-zA-Z-]+[^{};]*\{\s*\}\s*)+\s*</style>')),
]


def residue_rules():
    """(이름, 정규식, 보기) 전체. 마커는 소유자 표에서 파생하고 나머지만 여기 것을 쓴다."""
    import markercheck
    return (markercheck.source_markers()
            + [(n, p, '') for n, p in NO_MARKER_RESIDUE])


def load(path=None):
    return json.load(io.open(path or CONFIG, encoding='utf-8'))


def check_source(text):
    """소스에 주입 흔적이 남았는지. 남았으면 이름 목록을 돌려준다."""
    return [n for n, p, _s in residue_rules() if p.search(text)]


def apply(vault=None, config=None):
    """실제 일. 자기시험은 부르지 않는다 (시험이 이것을 부르므로)."""
    vault = vault or VAULT
    try:
        cfg = load(config)
    except Exception as e:
        print('  [!] page_overrides.json 을 못 읽었습니다: %s' % e)
        return False
    pages = cfg.get('페이지') or {}
    if not pages:
        print('  손 관리 페이지 등록 없음 (건너뜀)')
        return True
    done = []
    for page in sorted(pages):
        spec = pages[page]
        src = os.path.join(vault, *spec['소스'].split('/'))
        if not os.path.exists(src):
            print('  [!] %s 의 소스가 없습니다: %s' % (page, spec['소스']))
            return False
        t = io.open(src, encoding='utf-8').read()
        bad = check_source(t)
        if bad:
            print('  [!] %s 소스에 주입 흔적이 남았습니다: %s' % (spec['소스'], ' · '.join(bad)))
            print('      소스는 손으로 쓴 것만 담습니다. 주입은 빌드가 합니다')
            return False
        io.open(os.path.join(vault, page), 'w', encoding='utf-8',
                newline='\n').write(t)
        done.append('%s <- %s' % (page, os.path.basename(src)))
    print('  %d장 소스에서 생성: %s' % (len(done), ' · '.join(done)))
    return True


def _kat():
    """★ 답을 아는 입력."""
    import tempfile
    if check_source('<p>깨끗한 소스</p><style>.a{b:c}</style>'):
        return False, '깨끗한 소스를 오염으로 봄'
    # ★ 소유자 표의 «모든» 마커를 하나씩 시험한다. 표가 늘면 시험도 저절로 는다.
    #   전에는 여기에 손으로 고른 다섯 개만 있어서 여덟을 놓쳤다.
    import markercheck
    for name, _pat, sample in markercheck.source_markers():
        if not sample:
            return False, '소유자 표에 답을 아는 보기가 없다: %s' % name
        if not check_source('<p>본문</p>' + sample + '<p>더</p>'):
            return False, '소유자 표의 마커를 못 잡음: %s (%r)' % (name, sample)
    for probe in ('<script>try{var _t=localStorage.x}catch(e){}</script>',
                  '<style>@media print{}</style>',
                  '<div class="bstamp">x</div>',
                  '<style>span.fh-new{a:b}</style>'):
        if not check_source(probe):
            return False, '마커 없는 흔적을 못 잡음: %r' % probe
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, '_src'))
        io.open(os.path.join(d, '_src', 'x.base.html'), 'w',
                encoding='utf-8').write('<p>소스</p>')
        cfgp = os.path.join(d, 'cfg.json')
        io.open(cfgp, 'w', encoding='utf-8').write(json.dumps(
            {'페이지': {'x.html': {'소스': '_src/x.base.html', '목적': 't',
                                 '이슈': 'i', '허용': {}}}}, ensure_ascii=False))
        if not apply(d, cfgp):
            return False, '정상 소스에서 생성 실패'
        if io.open(os.path.join(d, 'x.html'), encoding='utf-8').read() != '<p>소스</p>':
            return False, '생성 결과가 소스와 다름'
        # 오염된 소스는 막아야 한다
        io.open(os.path.join(d, '_src', 'x.base.html'), 'w',
                encoding='utf-8').write('<p>소스</p><!--gnav:v1-->')
        if apply(d, cfgp):
            return False, '오염된 소스를 통과시킴'
        # 소스가 없으면 막아야 한다
        os.remove(os.path.join(d, '_src', 'x.base.html'))
        if apply(d, cfgp):
            return False, '소스가 없는데 통과시킴'
    return True, ''


def main(vault=None, config=None):
    """빌드가 부르는 자리. 답을 아는 시험을 먼저 돌린 뒤 실제 일을 한다.

    ★ 시험의 출력은 삼킨다. 빌드 로그에 임시 파일 이름이 섞이면
      진짜 결과를 못 읽는다 (실측: x.html <- x.base.html 이 섞여 나왔다).
    """
    import contextlib, io as _io
    with contextlib.redirect_stdout(_io.StringIO()):
        ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    return apply(vault, config)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ok, why = _kat()
    print('자기시험 %s%s' % ('통과' if ok else '실패', '' if ok else ': ' + why))
    sys.exit(0 if ok else 1)
