# -*- coding: utf-8 -*-
"""손 관리 소스에서 «생성기 소유 블록» 만 걷어낸다 (mai-os#24 보완 · 일회성 이관 도구).

  왜
    독립 검수가 잡았다. `_src/index.base.html` 과 `_src/brief.base.html` 에
    생성기 소유 마커가 여덟 종 남아 있었다.
      brand:v1 · teamprofiles:v2 · search:v8 · home:v1 · status:v1 ·
      recent:v1 · stamp:v1 · dark:v1
    커밋 메시지와 page_overrides 메모는 «손 style 과 페이지 고유 script 만» 이라고
    선언했는데 사실이 아니었다.

  ★ 범위는 markercheck.OWNERS 가 정한다. 여기서 문자열 목록을 새로 만들지 않는다.
    같은 규칙을 두 자리에 적으면 갈라진다 (실제로 갈라져서 이 사고가 났다).

  ★ 이 스크립트는 «한 번만» 도는 이행 도구다. 빌드에 넣지 않는다.
    매 빌드 자동 관문은 handpages.check_source 이고, 그것은 «검사» 만 한다.
"""
import io
import os
import re
import sys

BUILD = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), '_build')


def _load_markercheck(build_dir):
    sys.path.insert(0, build_dir)
    import markercheck
    return markercheck


# 소유 블록을 지운 자리에 «슬롯» 을 남겨야 하는 것.
#   그 생성기들은 마커 사이만 교체할 뿐, 자기 힘으로 넣을 자리를 못 찾는다.
#   슬롯은 «여기에 넣어라» 는 자리 표시일 뿐 계산 결과(D-day · 제출 수 ·
#   최근 목록)를 한 글자도 담지 않는다.
#   나머지는 </head> · </body> 나 페이지 고유 앵커로 스스로 자리를 찾으므로
#   슬롯 없이 통째로 지운다. 실측으로 갈랐다 (2026-09-02).
NEEDS_SLOT = {'자기 참조': '<!--slot:status-->',
              '최근': '<!--slot:recent-->'}


def purify(text, mc):
    """소유 블록을 걷어낸 소스와 (이름, 블록 수, 지운 자수, 슬롯) 목록."""
    log = []
    for own in mc.OWNERS:
        sp = mc.spans(text, own)
        if not sp:
            continue
        gone = sum(b - a for a, b, _ in sp)
        slot = NEEDS_SLOT.get(own['이름'])
        if slot:
            if len(sp) > 1:
                text = mc.remove(text, sorted(sp)[1:])
                sp = mc.spans(text, own)
            a, b, _ok = sorted(sp)[0]
            text = text[:a] + slot + text[b:]
        else:
            text = mc.remove(text, sp)
        log.append((own['이름'], len(sp), gone, slot or ''))
    # 빈 줄이 남으면 다음 빌드의 tidy 가 또 손대므로 여기서 정리한다
    text = re.sub(r'\n[ \t]*(?:\n[ \t]*){2,}', '\n\n', text)
    return text, log


def main(build_dir, paths):
    mc = _load_markercheck(build_dir)
    import handpages
    ok = True
    for p in paths:
        t = io.open(p, encoding='utf-8').read()
        out, log = purify(t, mc)
        io.open(p, 'w', encoding='utf-8', newline='\n').write(out)
        print('%s  %d자 -> %d자' % (os.path.basename(p), len(t), len(out)))
        for name, n, gone, slot in log:
            print('    걷어냄 %-12s 블록 %d개 · %d자%s'
                  % (name, n, gone, ('  -> 슬롯 ' + slot) if slot else ''))
        # ★ 원칙 2. 스스로 «이제 깨끗한가» 를 주장한다
        left = handpages.check_source(out)
        if left:
            print('    [!] 아직 남았습니다: %s' % ' · '.join(left))
            ok = False
        else:
            print('    소스 잔재 0')
    return ok


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main(sys.argv[1], sys.argv[2:]) else 1)
