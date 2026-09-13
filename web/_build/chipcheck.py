# -*- coding: utf-8 -*-
"""수를 적어 놓고 그만큼 안 그린 자리를 찾는다 (foothold-lab#156).

  왜 관문이 필요한가
    2026-09-03 실측: 연구 허브 출발선이 「후속 과제 8」 이라 적고 칩을 6개만
    그렸다. `for it in men[:6]` 과 `len(men)` 이 서로 다른 수를 봤다.
    떨어진 둘은 #66 rails · #65 gap 이고, 하필 아직 안 풀린 험지 둘이었다.

    이 결함이 오래 산 이유는 하나다. **아무 소리도 안 났다.** 빌드는 통과하고
    링크도 안 깨진다. 세어 보는 사람만 안다 (커널 원칙 2 · 조용한 실패).

  무엇을 보나
    「N」 이라 적은 머리와, 그 바로 뒤 목록이 실제로 그린 항목 수를 맞춰 본다.
    상한을 넘겨 안 그린 것이 있으면 목록 안에 「외 K건」 칩이 서 있어야 하고,
    그린 수 + K 가 N 과 같아야 한다. 잘린 것이 자기 존재를 주장하는지를 본다.

  ★ 이 규칙이 사는 자리를 다 센다 (커널 철칙 4)
    한 자리만 보면 나머지에서 조용히 무너진다. 지금 다섯 자리다.
    새 목록을 만들면 PAIRS 에 줄을 더한다.

  ★ 짝을 하나도 못 찾으면 실패다
    마크업이 바뀌어 정규식이 안 맞으면 이 관문은 «전부 통과» 를 찍으면서
    아무것도 안 지킨다. 빈 검사가 초록으로 끝나는 경로를 남기지 않는다.
"""
import io
import os
import re
import sys

# (설명, 머리 정규식 · 수는 group 1, 몸 목록의 class)
#
# ★ 2026-09-04: 「연구 · 후속 과제」 짝을 뺐다. 그 줄 자체가 없어졌다 (팀장 지적).
#   이름과 달리 후속 과제를 고르는 줄이 아니라, 이 문서를 참고 링크로 적은 열린
#   이슈를 긁어 오는 줄이었다. 험지의 후속은 아래 험지 표가 정본이다.
#   짝을 지우면서 그 자리를 표의 칸이 받는다 (맨 아래 「연구 · 험지 칸」).
PAIRS = [
    ('일정 · 모인 질문',
     r'모인 질문 (\d+)개</div><div class="w3p">', 'w3p'),
    ('일정 · 관련 문서',
     r'<div class="eh3">관련 문서 <span>(\d+)</span></div><div class="deep3">',
     'deep3'),
    ('연구 · 활동 묶음',
     r'<div class="eg3">[^<]*<span>(\d+)</span></div><div class="evs3">', 'evs3'),
    ('연구 · 외부 자료 조사',
     r'<div class="eh3">외부 자료 조사 (\d+)</div><div class="evs3">', 'evs3'),
    # 험지 표 아래 두 줄 (foothold-lab#179). 미분류는 «숨기지 않는다» 가
    # 규칙이라, 적은 수와 그린 칩 수가 어긋나면 그 규칙이 깨진 것이다.
    ('연구 · 험지 공통 문서',
     r'<div class="hk3b">공통 (\d+)</div><div class="fks3">', 'fks3'),
    ('연구 · 험지 미분류',
     r'<div class="hk3b">미분류 (\d+)</div><div class="fks3">', 'fks3'),
    # 험지 표의 칸 스무 개(지형 5 x 단계 4). 셋을 넘으면 「외 N건」 이 서야 한다.
    # data-n 은 그 칸이 «실제로 가진» 수다. 화면이 조용히 자르면 여기서 걸린다.
    ('연구 · 험지 칸',
     r'<div class="tkc3[a-z ]*" data-n="(\d+)"><i>[^<]*</i>', 'tkc3'),
]

MORE = re.compile(r'외 (\d+)건')
ANCHOR = re.compile(r'<a[\s>]')


def _body(text, start):
    """목록 여는 태그 다음부터 그 목록이 닫히는 데까지.

    이 목록들은 안에 `<div>` 를 두지 않는다. 두게 되면 이 셈이 틀리므로
    조용히 틀리는 대신 시끄럽게 알린다.
    """
    end = text.find('</div>', start)
    if end < 0:
        return None, '목록이 안 닫힌다'
    body = text[start:end]
    if '<div' in body:
        return None, '목록 안에 <div> 가 생겼다. 셈이 틀어진다'
    return body, ''


def scan_text(text, name):
    """이 문서에서 (설명, 적은 수, 그린 수, 외 K, 사유) 목록."""
    found = []
    for label, head, cls in PAIRS:
        for m in re.finditer(head, text):
            said = int(m.group(1))
            body, why = _body(text, m.end())
            if body is None:
                found.append((label, said, -1, 0, why))
                continue
            more = MORE.search(body)
            k = int(more.group(1)) if more else 0
            drawn = len(ANCHOR.findall(body)) - (1 if more else 0)
            found.append((label, said, drawn, k, ''))
    return found


def main(site):
    # ★ 2026-09-10. os.listdir 은 최상위만 본다. 하위 폴더(team-meang/)와
    #   assets/ 아래 페이지가 통째로 빠졌다. 도구 함정 문서의 B 부류다.
    #   배포 전수의 정본은 searchbox.public_pages 하나다.
    import searchbox
    #   public_pages 는 «준 목록» + assets 를 합친다. 빈 목록을 주면 assets 만
    #   본다. 실측: 그렇게 했더니 짝을 하나도 못 찾아 관문이 스스로 실패했다.
    #   («0개 검사하고 통과» 를 막아 둔 것이 내 회귀를 잡았다.)
    #   최상위 목록을 씨앗으로 주면 하위 폴더까지 함께 돈다.
    targets = sorted(searchbox.public_pages(site, sorted(os.listdir(site))))
    bad, seen = [], 0
    for f in targets:
        p = os.path.join(site, f)
        try:
            t = io.open(p, encoding='utf-8', errors='replace').read()
        except OSError as e:
            bad.append('%s: 못 읽었다 (%s)' % (f, e))
            continue
        for label, said, drawn, k, why in scan_text(t, f):
            seen += 1
            if why:
                bad.append('%s · %s: %s' % (f, label, why))
            elif drawn + k != said:
                bad.append('%s · %s: 「%d」이라 적고 %d개를 그렸다%s'
                           % (f, label, said, drawn,
                              (' (외 %d건 포함해도 %d)' % (k, drawn + k)) if k
                              else ' · 잘린 것을 말하는 칩이 없다'))
    if not seen:
        print('  [!] 셈할 짝을 하나도 못 찾았습니다. 마크업이 바뀌었는지 '
              'PAIRS 를 다시 보십시오. 빈 검사는 통과가 아닙니다.')
        return False
    for b in bad:
        print('  [!] %s' % b)
    print('  짝 %d곳 검사 · 어긋남 %d곳' % (seen, len(bad)))
    return not bad


def _kat():
    """★ 답을 아는 입력. 이 관문이 무엇을 잡고 무엇을 통과시키는지 못 박는다.

    ★ 2026-09-04: 예제를 「후속 과제」 에서 「공통」 으로 옮겼다. 그 줄이 화면에서
      없어졌으니, 없는 마크업으로 자기시험을 하면 이 관문은 자기가 살아 있다고
      믿으면서 실제로는 아무것도 안 지킬 수 있다. 예제는 늘 지금 쓰는 짝에서 뽑는다.
    """
    ok = ('<div class="hk3b">공통 2</div><div class="fks3">'
          '<a href="#">가</a><a href="#">나</a></div>')
    short = ('<div class="hk3b">공통 8</div><div class="fks3">'
             '<a href="#">가</a><a href="#">나</a></div>')
    tail = ('<div class="hk3b">공통 8</div><div class="fks3">'
            '<a href="#">가</a><a href="#">나</a>'
            '<a class="fk3 more" href="#"><b>외 6건</b></a></div>')
    nested = ('<div class="hk3b">공통 1</div><div class="fks3">'
              '<div><a href="#">가</a></div></div>')
    # 험지 표의 칸도 같은 규칙을 받는다 (foothold-lab#179 · 표 전환 2026-09-04).
    cell_ok = ('<div class="tkc3 on" data-n="3"><i>진단</i>'
               '<a href="#">가</a><a href="#">나</a><a href="#">다</a></div>')
    cell_cut = ('<div class="tkc3 on" data-n="7"><i>진단</i>'
                '<a href="#">가</a><a href="#">나</a><a href="#">다</a></div>')
    cell_more = ('<div class="tkc3 on" data-n="7"><i>진단</i>'
                 '<a href="#">가</a><a href="#">나</a><a href="#">다</a>'
                 '<a class="tkmr3 more" href="#"><b>외 4건</b></a></div>')
    cell_empty = '<div class="tkc3" data-n="0"><i>레시피</i></div>'
    cases = [
        ('수가 맞으면 통과', ok, 0),
        ('8이라 적고 2를 그리면 실패', short, 1),
        ('외 6건이 있으면 통과', tail, 0),
        ('목록에 div 가 생기면 실패', nested, 1),
        ('칸이 셋을 다 그리면 통과', cell_ok, 0),
        ('칸이 일곱 중 셋만 조용히 그리면 실패', cell_cut, 1),
        ('칸에 외 4건이 서면 통과', cell_more, 0),
        ('빈 칸은 통과', cell_empty, 0),
    ]
    for why, text, want in cases:
        got = sum(1 for _l, s, d, k, w in scan_text(text, 't')
                  if w or d + k != s)
        if got != want:
            return False, '%s: 어긋남 %d개를 기대했는데 %d개' % (why, want, got)
    for why, text in (('공통', ok), ('험지 칸', cell_ok),
                      ('빈 험지 칸', cell_empty)):
        if len(scan_text(text, 't')) != 1:
            return False, '%s 짝을 하나도 못 세었다' % why
    return True, ''


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) > 1 and sys.argv[1] != '--kat':
        sys.exit(0 if main(sys.argv[1]) else 1)
    good, why = _kat()
    print('자기시험 %s%s' % ('통과' if good else '실패', '' if good else ': ' + why))
    sys.exit(0 if good else 1)
