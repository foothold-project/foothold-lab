# -*- coding: utf-8 -*-
"""폐기된 사실이 웹으로 나가는 것을 막는다.

★ 2026-08-27 검수에서 나온 구조적 지적.

  옛 5갈래·옛 역할표는 `COLLAB.md` 를 고치자 사라졌는데
  `collab.html` 의 `foothold-rl` 한 줄은 **살아남았다.** 차이는 하나다.
  사라진 것은 md 에서 왔고, 남은 것은 **`collab_page.py` 에 박혀 있었다.**

  `metacheck` 는 문서를 검사한다. 그런데 사실은 문서에만 있는 것이 아니라
  **생성기(`_build/*.py`)와 손으로 관리하는 마스터 HTML** 에도 박혀 있다.
  거기 박힌 사실은 md 를 아무리 고쳐도 안 바뀐다.

  개별 문자열을 고치는 것으로 끝내면 다음 결정 때 같은 자리에서 재발한다.
  커널 2-2: **실수는 부류로 막는다.**

검사 대상
  1. `_build/*.py`      웹을 만드는 생성기
  2. 배포된 `*.html`    실제로 사람이 읽는 것 (태그·주석·script 를 걷어낸 텍스트)

검사 방식
  폐기된 어휘가 나오면 멈춘다. 다만 **「이건 폐기했다」고 설명하는 문장**은 통과시킨다.
  설명까지 막으면 결정의 내력을 적을 수 없다.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# (폐기된 어휘, 무엇으로 바뀌었나)
STALE = [
    ('foothold-rl', 'foothold-go2 (2026-08-27 개명)'),
    ('실기 전이', '트랙 B · 항법 (8/19 저수준 이전은 목표에서 제외)'),
    ('어느 갈래인가', '작업 영역'),
    ('어느 갈래의 일인가', '작업 영역'),
    ('9월 PoC', 'A-정책 9/12'),
    ('10월 MVP', 'MVP · 중간발표 9/30'),
    ('11월 QA', 'NAV · 실기 항법 11/7'),
    ('중간보고: 11월', 'NAV · 실기 항법 11/7'),
    ('검토 없이 바로 머지', '팀장이 확인하고 머지'),
    ('10MB 넘는', '100MB 넘는'),
    ('메타 4줄', '메타 5줄'),
    ('메타데이터 4줄', '메타데이터 5줄'),
    ('개인 구역', '개인 설정은 inbox/<이름>/AGENTS.md 또는 로컬'),
    ('두 줄이 있어야', '메타 5줄 (분류·작성·근거·요지·상태)'),
    ('작성 YYYY-MM-DD', '작성: 이름 · YYYY-MM-DD HH:MM'),
    ('다섯 갈래', '여덟 갈래 (작업 영역 8종)'),
    ('POLICY   ENV', '작업 영역 8갈래'),
    # 2026-08-27: 파인튜닝 계획의 병렬 갈래가 4개로 그려져 있었다.
    #   floating_ring 이 빠졌고, 근거로 「4종 cfg 내장」이 적혀 있었다(사실이 아님).
    ('레시피 1장» × 4', '레시피 1장 × 5 (실패 5종 · 5인)'),
    ('팀원 4인', '팀원 5인 (지형 1개씩)'),
    ('각 0.125', '신규 5종 각 0.1'),
    ('실패 4종', '실패 5종'),
    ('중간 MVP</b>10월', 'MVP · 중간발표 9/30'),
    ('MVP 10월', 'MVP · 중간발표 9/30'),
    # 2026-08-28: 최종 발표를 12/10 으로 적은 곳이 세 군데 있었다.
    #   정본은 12/11 (GitHub 마일스톤 · COLLAB · DECISIONS 08-27 · REPORT).
    ('12/10', 'FINAL · 최종발표 12/11'),
    ('12월 10일', 'FINAL · 최종발표 12월 11일'),
]

# 폐기를 «설명하는» 문장에 붙는 말. 이 중 하나가 같은 줄에 있으면 통과시킨다.
EXCUSE = ('폐기', '옛', '이전', '전에는', '바뀌', '개명', '아님', '였다', '있었다',
          '2026-08-27', '더 이상', '쓰지 않', '안 쓴', '정정', '개정', '금지',
          '사고', '재발', '어긋난', '위반', '나갔다', '없앴', '지웠', '막는다',
          '검사', '살아남', '사례', '남아 있', '한 줄이', '그때')

# ── 어휘가 아니라 «문장의 모양»으로 알아보는 면제 세 가지 ──────────────
#   개별 낱말을 EXCUSE 에 계속 밀어 넣는 것은 커널 2-2 가 경계하는 방식이다.
#   폐기를 «설명하는 문장»에는 되풀이되는 모양이 있고, 그 모양을 본다.
#
#   1) 취소선   ~~옛것~~        이미 폐기 표시가 붙어 있다 (DECISIONS.md 관례)
#   2) 화살표   옛것 -> 새것    이 줄 자체가 바뀐 기록이다
#   3) 인용부호 "옛것"          남이 한 말이나 채용공고 문구. 우리 규칙이 아니다
_STRIKE = re.compile(r'~~[^~]*~~')
_QUOTED = re.compile('"[^"]*"|' + chr(0x201C) + '[^' + chr(0x201D) + ']*' + chr(0x201D)
                     + '|' + chr(0xAB) + '[^' + chr(0xBB) + ']*' + chr(0xBB))
_ARROW = chr(0x2192)


def _shape_excused(line, word):
    for rx in (_STRIKE, _QUOTED):
        for m in rx.finditer(line):
            if word in m.group(0):
                return True
    return bool(re.search(re.escape(word) + r'[`\s]*(' + _ARROW + r'|->)', line))


# 그 시점을 그대로 적은 기록물. 고치면 기록이 아니라 위조가 된다.
RECORD_DIRS = ('meetings', 'digest')
# 날짜 공지도 기록물이다. 그날 보낸 말이라 지금 값으로 고치면 위조가 된다.
RECORD_MD = re.compile(r'notices[/\\]\d{4}-\d{2}-\d{2}\.md$')
RECORD_HTML = re.compile(r'^notice-\d{8}\.html$')


def _lab_root():
    import docs_pages
    for p in docs_pages.LAB_CANDIDATES:
        if os.path.isdir(os.path.join(p, 'docs')):
            return p
    return None

# 손으로 관리하는 마스터 HTML. 여기 박힌 사실은 md 를 고쳐도 안 바뀐다.
# automation.html 은 2026-08-27 에 md 생성으로 옮겼다. 남은 손 관리는 둘뿐.
# brief.html 도 손 관리다. 2026-08-27 까지 아무도 안 봐서 옛 「중간 MVP 10월」이
# 살아 있었다. 원본(_src)이 없는 페이지는 전부 여기 있어야 한다.
HAND_MASTERS = ('team-intro.html', 'setup.html', 'brief.html')


def _text_of_html(s):
    """사람이 실제로 읽는 텍스트만. 주석·script·style 은 뺀다."""
    s = re.sub(r'<!--.*?-->', ' ', s, flags=re.S)
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', s, flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))


def _hits(text, path, is_html):
    out = []
    for line_no, line in enumerate(text.split('\n'), 1):
        for word, better in STALE:
            if word not in line:
                continue
            if any(e in line for e in EXCUSE):
                continue                       # 폐기를 설명하는 문장
            if _shape_excused(line, word):
                continue                       # 취소선 · 화살표 · 인용
            out.append((path, line_no if not is_html else 0, word, better,
                        line.strip()[:70]))
    return out


def _kat():
    """★ 답을 아는 입력으로 검사기를 먼저 시험한다."""
    bad = _hits('저장소는 foothold-rl 이다.', 'x.py', False)
    if len(bad) != 1:
        return False, '폐기 어휘를 안 잡음'
    ok = _hits('foothold-rl 은 폐기했다. 지금은 foothold-go2 다.', 'x.py', False)
    if ok:
        return False, '폐기를 설명하는 문장을 잘못 잡음'
    for shape, why in (('~~foothold-rl~~ 개명함', '취소선'),
                       ('`foothold-rl` ' + _ARROW + ' `foothold-go2`', '화살표'),
                       ('공고에 "foothold-rl 경험자" 라고 적혀 있다', '인용')):
        if _hits(shape, 'x.md', False):
            return False, why + ' 을 잘못 잡음'
    if not _hits('foothold-rl 로 계속 간다', 'x.md', False):
        return False, '모양 면제가 너무 넓어 진짜 폐기 사실을 놓침'
    return True, ''


def main(site):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    found = []
    # 1) 생성기
    for f in sorted(os.listdir(HERE)):
        if not f.endswith('.py') or f == 'stalecheck.py':
            continue
        t = io.open(os.path.join(HERE, f), encoding='utf-8', newline=None).read()
        found += _hits(t, '_build/' + f, False)
    # 2) 손으로 관리하는 마스터
    for f in HAND_MASTERS:
        p = os.path.join(VAULT, f)
        if os.path.exists(p):
            t = _text_of_html(io.open(p, encoding='utf-8', newline=None).read())
            found += _hits(t, f + ' (손 관리 마스터)', True)
    # 3) lab 의 md 원본. 여기 남은 폐기 사실은 웹에 안 나가더라도 팀원이
    #    저장소에서 그대로 읽는다. 2026-08-27: COLLAB·inbox README 에 옛 「두 줄」
    #    규칙이 살아 있었고, 웹만 보던 검사는 그것을 못 잡았다.
    n_md = 0
    lab = _lab_root()
    if lab:
        for sub in ('docs', 'inbox', 'deliverables'):
            base = os.path.join(lab, sub)
            for dirpath, dirnames, names in os.walk(base):
                dirnames[:] = [d for d in dirnames
                               if d not in ('assets', '.git') + RECORD_DIRS]
                for f in sorted(names):
                    if not f.endswith('.md'):
                        continue
                    n_md += 1
                    rel = os.path.relpath(os.path.join(dirpath, f), lab)
                    if RECORD_MD.search(rel.replace(os.sep, '/')):
                        continue          # 그날 보낸 공지. 고치면 위조
                    found += _hits(io.open(os.path.join(dirpath, f), encoding='utf-8',
                                           newline=None).read(),
                                   'lab/' + rel.replace(os.sep, '/'), False)
        for f in ('AGENTS.md', 'README.md'):
            fp = os.path.join(lab, f)
            if os.path.isfile(fp):
                n_md += 1
                found += _hits(io.open(fp, encoding='utf-8', newline=None).read(),
                               'lab/' + f, False)

        # 3-1) 도식(SVG)의 글자. ★ 2026-08-27: 파인튜닝 계획의 병렬 갈래가
        #      «4개»로 그려져 있던 자리는 md 가 아니라 SVG 안이었다. assets 를
        #      통째로 건너뛰던 검사는 그림 속 글자를 한 번도 안 봤다.
        #      그림이 본문과 다른 말을 하면 읽는 사람은 그림을 믿는다.
        vis = os.path.join(lab, 'docs', 'assets', 'visual')
        if os.path.isdir(vis):
            for f in sorted(os.listdir(vis)):
                if not f.endswith('.svg'):
                    continue
                n_md += 1
                t = _text_of_html(io.open(os.path.join(vis, f), encoding='utf-8',
                                          newline=None).read())
                found += _hits(t, 'lab/docs/assets/visual/' + f + ' (도식)', True)

    # 4) 배포본이 실제로 보여주는 텍스트
    n_html = 0
    if site and os.path.isdir(site):
        for dirpath, dirnames, names in os.walk(site):
            dirnames[:] = [d for d in dirnames if d not in ('assets', '_build')]
            for f in sorted(names):
                if not f.endswith('.html'):
                    continue
                if RECORD_HTML.match(f):
                    continue              # 날짜 공지 = 기록물
                n_html += 1
                t = _text_of_html(io.open(os.path.join(dirpath, f),
                                          encoding='utf-8', newline=None).read())
                rel = os.path.relpath(os.path.join(dirpath, f), site)
                found += _hits(t, rel.replace(os.sep, '/'), True)

    print('  자가검증 통과 · 생성기 %d개 · lab 문서 %d개 · 배포 페이지 %d개 · 폐기 어휘 %d종'
          % (len([f for f in os.listdir(HERE) if f.endswith('.py')]),
             n_md, n_html, len(STALE)))
    # ★ 2026-09-10. 「검사할 것이 없었다」와 「위반이 없었다」는 다른 사실이다.
    #   빈 대상으로 돌려 보니 이 관문이 「0개 · 통과」를 찍고 성공을 돌려줬다.
    #   목록이 비는 순간 조용히 무력해진다. 그리고 목록은 실제로 빈다.
    if n_html == 0:
        print('  [!] 배포 페이지를 한 장도 못 봤습니다. 검사가 헛돌았습니다')
        return False
    if found:
        seen = set()
        for path, ln, word, better, snippet in found:
            key = (path, word)
            if key in seen:
                continue
            seen.add(key)
            where = '%s:%d' % (path, ln) if ln else path
            print('  ★ %-46s 「%s」 -> %s' % (where, word, better))
            print('      %s' % snippet)
        print('  폐기된 사실 %d곳' % len(seen))
        return False
    print('  폐기된 사실 없음')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import linkcheck
    sys.exit(0 if main(linkcheck._site()) else 1)
