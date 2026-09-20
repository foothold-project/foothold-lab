# -*- coding: utf-8 -*-
"""대외비 금액을 웹으로 내보내기 «전에» 가린다.

★ 2026-08-27. 결정 로그(`docs/DECISIONS.md`)를 웹에 올리려는데 [4] 관문이
  대여 금액 두 개를 잡아 배포를 세웠다. 관문이 제 일을 한 것이다.

  그런데 여기서 고를 수 있는 길이 둘이다.
    (a) 그 문서를 웹에 안 올린다  -> 「결정 로그는 공개」라는 결정을 어긴다
    (b) 금액만 가리고 올린다      -> 결정은 지키고 금액은 지킨다
  (b) 를 택한다. 대신 **가린 사실을 화면에 적는다.** 조용히 지우면 읽는 사람은
  거기 무엇이 있었는지도 모른다.

  금액 패턴은 여기서 새로 쓰지 않고 **`scan.py` 의 것을 그대로 쓴다.**
  목록이 둘로 갈라지면 한쪽만 고쳐지고, 그게 다음 유출이다.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 꺾쇠(`<>`)를 쓰면 마크다운 렌더러가 태그로 보고 삼킨다. 낫표를 쓴다.
MASK = '「금액 대외비」'

# ── 절 단위 제외: 남의 저작물에서 옮긴 대목 ──────────────────────────────
#   ★ 2026-08-27. 오현민의 ROS 2 노트(PR #63) 3편 §9 는 조선대 자료의 15주
#     커리큘럼 표를 옮긴 것이다. 팀 안에서는 쓸 값이 있지만 «저작권상 외부
#     유출 금지» 라 공개 웹에는 못 싣는다.
#
#     금액처럼 «낱말을 가리는» 방식으로는 안 된다. 표 전체가 남의 것이다.
#     그래서 원본 md 에 표시를 달아 **절 단위로 들어낸다.**
#     들어냈다는 사실은 반드시 화면에 남긴다 (조용히 지우면 읽는 사람은
#     거기 무엇이 있었는지도 모른다).
WEB_A, WEB_B = '<!--web:제외-->', '<!--/web:제외-->'
_WEB_NOTE = ('> **이 절은 공개 웹에 싣지 않습니다.** 남의 저작물(조선대 강의 자료)에서\n'
             '> 옮긴 대목이라 외부 공개 조건에 걸립니다. **내용은 저장소 원본**\n'
             '> (`%s`)**에 그대로 있습니다.** 팀 안에서는 평소대로 씁니다.')


def _money_rx():
    import scan
    for name, pat in list(scan.BLOCK) + list(scan.WARN):
        if name == '계약 금액':
            return re.compile(pat)
    raise SystemExit('  [!] scan.py 에 「계약 금액」 규칙이 없습니다. redact 를 믿을 수 없습니다.')


def _kat():
    """★ 답을 아는 입력으로 먼저 시험한다."""
    rx = _money_rx()
    for s, want in (('옵션1(월35, 아무대 내)', True),
                    ('월 250만원', True),
                    ('2026년 8월 13일 방문', False),
                    ('월 2회 공유 세션', False)):
        got = bool(rx.search(s))
        if got != want:
            return False, '「%s」 를 %s 로 봄' % (s, '금액' if got else '금액 아님')

    # 절 제외도 답을 아는 입력으로 시험한다.
    doc = 'A\n' + WEB_A + '\n남의 표\n' + WEB_B + '\nB\n'
    cut = drop_web_only(doc, 'kat.md', quiet=True)
    if '남의 표' in cut:
        return False, '제외 표시 안의 내용이 그대로 남음'
    if '공개 웹에 싣지 않습니다' not in cut:
        return False, '들어냈다는 표시가 화면에 안 남음'
    if 'A' not in cut or 'B' not in cut:
        return False, '제외 표시 «밖»의 내용까지 지움'
    if drop_web_only('표시 없는 문서', 'kat.md', quiet=True) != '표시 없는 문서':
        return False, '표시가 없는 문서를 건드림'
    return True, ''


def drop_web_only(md, where='', quiet=False):
    """`<!--web:제외-->` 로 감싼 절을 들어내고, 들어냈다고 화면에 적는다."""
    if WEB_A not in md:
        return md
    out, n_cut = [], 0
    rest = md
    while WEB_A in rest:
        head, rest = rest.split(WEB_A, 1)
        if WEB_B not in rest:
            raise SystemExit('  [!] %s: %s 는 있는데 %s 가 없습니다.'
                             % (where, WEB_A, WEB_B))
        _cut, rest = rest.split(WEB_B, 1)
        out.append(head + '\n' + (_WEB_NOTE % (where or '저장소 원본')) + '\n')
        n_cut += 1
    out.append(rest)
    if not quiet:
        print('  [웹제외] %s: 절 %d개' % (where or 'md', n_cut))
    return ''.join(out)


def _allowed_values():
    """★ 2026-08-28. 「이건 괜찮다」를 두 곳에서 관리하지 않는다.

    `scan.py` 의 ALLOW 가 유일한 원본이다. 전에는 redact 가 그것을 모른 채
    가려 버려서, 팀장이 「문제 없다」고 한 RunPod 공개 요금까지 화면에서
    사라졌다. 관문이 통과시키는 값을 게시기가 지우면 둘이 싸운다.
    """
    import scan
    return [v for r, v, _, _ in scan.ALLOW if r == '계약 금액']


def apply(md, where=''):
    """md 원문에서 금액을 가리고 웹제외 절을 들어낸다. 한 일을 소리 내어 알린다."""
    ok, why = _kat()
    if not ok:
        raise SystemExit('  [!] redact 자기시험 실패: %s' % why)
    md = drop_web_only(md, where)
    rx = _money_rx()
    allow = _allowed_values()
    hits = [h for h in rx.findall(md) if not any(a in h for a in allow)]
    if not hits:
        return md

    def _mask(m):
        got = m.group(0)
        if any(a in got for a in allow):
            return got                  # 허용된 값은 그대로 둔다 (scan.ALLOW 가 원본)
        return MASK

    out = rx.sub(_mask, md)
    # 「월 250만원」은 앞 대안이 「월 100만」까지만 먹어 「원」이 남는다. 꼬리를 턴다.
    out = re.sub(re.escape(MASK) + r'\s*원', MASK, out)
    note = ('> **이 페이지에서 가린 것**: 계약·대여 **금액 %d곳**. 팀 내부에서는 저장소의\n'
            '> 원본(`%s`)에 그대로 남아 있습니다. 금액은 상대가 있는 정보라 공개하지 않습니다.'
            % (len(hits), where or '원본 md'))
    # 메타 5줄 바로 뒤(첫 빈 줄 다음)에 알림을 끼운다. 뒤에 빈 줄을 둬야
    # 다음 블록(표·인용)이 이 인용문에 딸려 들어가지 않는다.
    lines = out.split('\n')
    for i, l in enumerate(lines):
        if i > 3 and not l.strip():
            lines[i + 1:i + 1] = ['', note, '']
            break
    else:
        lines += ['', note, '']
    print('  [가림] %s: 금액 %d곳' % (where or 'md', len(hits)))
    return '\n'.join(lines)
