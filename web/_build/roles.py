# -*- coding: utf-8 -*-
"""역할 배치를 정본 하나에서 만들고, 어긋난 곳을 잡는다.

★ 2026-08-28. 8/27 에 작업 영역을 5갈래에서 8갈래로 바꿨다.
  GitHub 라벨은 바꿨고 `COLLAB.md` 표도 바꿨다. **그런데 발표 덱 두 장은
  그대로였다.** 팀 소개와 피치가 8/13 의 옛 5분야를 여전히 보여주고 있었다.

  원인은 부주의가 아니라 구조다. 손으로 관리하는 마스터가 셋이면 셋 다 고쳐야
  하는데, 셋 다 고쳤는지 확인해 주는 것이 아무것도 없었다. 커널 철칙 4.

무엇을 하나
  1. `docs/ROLES.md` 를 읽어 덱 두 장의 역할 카드를 **생성**한다
     (`<!--ROLES:deck-->` · `<!--ROLES:pitch-->` 자리에 넣는다)
  2. 관문: 8갈래가 `ROLES.md` · `COLLAB.md` · GitHub 라벨 셋에서 같은가
  3. 관문: 폐기한 옛 5분야 이름이 게시물에 남아 있지 않은가

왜 3번도 보나
  1번이 생성으로 바뀌어도 **덱이 아닌 곳**(요약 페이지·다른 덱)에 손으로 적힌
  옛 이름이 남을 수 있다. 한 층위만 보면 나머지 층위에서 조용히 무너진다.
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 8/13 에 정하고 8/27 에 폐기한 이름. 어디에도 남으면 안 된다.
DEAD = ('PM · Digital Twin', 'Policy · RL', 'Scene · Visualization',
        'Environment · Infra', 'Perception · Data')

FIELDS = ('갈래', '포지션', '대표', '한 줄', '메인 역할', '보유 강점', '협업 스타일', '피치 한 줄')


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _md_inline(s):
    """**굵게** -> <b>, `코드` -> <code>. 이스케이프 먼저 한다."""
    s = _esc(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s


def _lab():
    import docs_pages
    for p in docs_pages.LAB_CANDIDATES:
        if os.path.isdir(os.path.join(p, 'docs')):
            return p
    return None


# ── 읽기 ───────────────────────────────────────────────────────────────

def parse(md):
    """(areas, people). areas = 8갈래 표, people = 사람별 항목."""
    areas = []
    for m in re.finditer(r'^\|\s*`([ABC]/[^`]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|',
                         md, re.M):
        areas.append({
            'key': m.group(1).strip(),
            'what': m.group(2).strip(),
            'lead': m.group(3).replace('**', '').strip(),
            'sub': m.group(4).strip(),
            'dir': m.group(5).strip().strip('`'),
        })

    people = []
    body = md.split('## 2. 사람별 배치와 강점', 1)
    if len(body) == 2:
        for blk in re.split(r'^### ', body[1], flags=re.M)[1:]:
            lines = blk.strip().split('\n')
            p = {'name': lines[0].strip()}
            for ln in lines[1:]:
                m = re.match(r'^-\s*([^:]+):\s*(.+)', ln.strip())
                if m and m.group(1).strip() in FIELDS:
                    p[m.group(1).strip()] = m.group(2).strip()
            if len(p) > 1:
                people.append(p)
    return areas, people


def load():
    lab = _lab()
    if not lab:
        return None, None
    p = os.path.join(lab, 'docs', 'ROLES.md')
    if not os.path.isfile(p):
        return None, None
    return parse(io.open(p, encoding='utf-8', newline=None).read())


# ── 만들기 ─────────────────────────────────────────────────────────────

def deck_cards(people):
    """팀 소개 덱 R&R 장. .role 카드."""
    out = []
    for p in people:
        ext = p.get('갈래', '') == '없음'
        cls = 'role lead' if p.get('대표') == '예' else 'role'
        if ext:
            cls = 'role" style="border-style:dashed'
        # 역따옴표를 쓰지 않는다. <code> 가 되면 한글이 고정폭으로 튀고
        # rtag 는 대문자·자간 라벨이라 모양이 어긋난다 (피치 카드와 동일 표기).
        tag = ('External · 조달 계획' if ext
               else ' · '.join(a.strip().strip('`')
                               for a in p.get('갈래', '').split('·')))
        style = ' style="color:var(--note)"' if ext else ''
        out.append(
            '    <div class="%s">\n'
            '      <div class="rtag"%s>%s</div>\n'
            '      <div class="rname">%s</div>\n'
            '      <div class="rrole">%s</div>\n'
            '      <dl>\n'
            '        <dt>%s</dt><dd>%s</dd>\n'
            '        <dt>%s</dt><dd>%s</dd>\n'
            '        <dt>협업 스타일</dt><dd>%s</dd>\n'
            '      </dl>\n'
            '    </div>' % (
                cls, style, _md_inline(tag), _esc(p['name']),
                _md_inline(p.get('한 줄', '')),
                '확보 대상' if ext else '메인 역할',
                _md_inline(p.get('메인 역할', '')),
                '왜 외부인가' if ext else '보유 강점',
                _md_inline(p.get('보유 강점', '')),
                _md_inline(p.get('협업 스타일', ''))))
    return '\n\n'.join(out)


def pitch_cards(people):
    """피치 덱 Team 장. .card 6칸 + 멘토 자리."""
    out = []
    for p in people:
        ext = p.get('갈래', '') == '없음'
        tag = ('External · 조달' if ext
               else ' · '.join(a.strip().strip('`') for a in p.get('갈래', '').split('·')))
        out.append(
            '    <div class="card"><div class="k">%s</div><div class="t">%s</div>\n'
            '      <div class="d">%s</div></div>' % (
                _esc(tag), _esc(p['name']), _md_inline(p.get('피치 한 줄', ''))))
    out.append(
        '    <div class="card" style="border-color:var(--brand)">'
        '<div class="k">6th Member · 전담 멘토</div>'
        '<div class="t">현직 전문가 (8/20 합류)</div>\n'
        '      <div class="d">매일 오후 15~18시 협업. 현장의 기준으로 우리 실험과 '
        '코드를 검증받는다.</div></div>')
    return '\n'.join(out)


def expand(html, people=None):
    """마커를 실제 카드로 바꾼다. 마커가 없으면 그대로 돌려준다."""
    if people is None:
        _, people = load()
    if not people:
        return html
    html = html.replace('<!--ROLES:deck-->', deck_cards(people))
    html = html.replace('<!--ROLES:pitch-->', pitch_cards(people))
    return html


# ── 관문 ───────────────────────────────────────────────────────────────

def _gh_labels(lab):
    try:
        r = subprocess.run(['gh', 'label', 'list', '--limit', '80', '--json', 'name'],
                           cwd=lab, capture_output=True, text=True,
                           encoding='utf-8', timeout=30)
        if r.returncode != 0:
            return None
        import json
        return {x['name'] for x in json.loads(r.stdout or '[]')
                if re.match(r'^[ABC]/', x['name'])}
    except Exception:
        return None


def _kat():
    """★ 답을 아는 입력으로 먼저 시험한다."""
    n = chr(10)
    sample = ('| 갈래 | 무엇 | 주담당 | 부담당 | 폴더 |' + n +
              '|---|---|---|---|---|' + n +
              '| `A/시험` | 하는 일 | **홍길동** | 김철수 | `x/` |' + n + n +
              '## 2. 사람별 배치와 강점' + n + n +
              '### 홍길동' + n +
              '- 갈래: `A/시험`' + n +
              '- 대표: 예' + n +
              '- 한 줄: 한 줄 설명' + n +
              '- 메인 역할: **굵은** 역할' + n +
              '- 보유 강점: 강점' + n +
              '- 협업 스타일: 스타일' + n +
              '- 피치 한 줄: 피치' + n)
    areas, people = parse(sample)
    if len(areas) != 1 or areas[0]['lead'] != '홍길동':
        return False, '표를 못 읽음'
    if len(people) != 1 or people[0].get('메인 역할') != '**굵은** 역할':
        return False, '사람 항목을 못 읽음'
    card = deck_cards(people)
    if '<b>굵은</b>' not in card:
        return False, '굵게가 <b> 로 안 바뀜'
    if 'role lead' not in card:
        return False, '대표 카드를 못 알아봄'
    # 마커가 없는 글은 손대지 않아야 한다
    if expand('<p>그대로</p>', people) != '<p>그대로</p>':
        return False, '마커 없는 글을 건드림'
    if '<b>' not in expand('<!--ROLES:deck-->', people):
        return False, '마커를 안 바꿈'
    return True, ''


def main(vault=None):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    lab = _lab()
    areas, people = load()
    if not areas or not people:
        print('  [!] ROLES.md 를 못 읽었습니다')
        return False
    print('  정본 ROLES.md · 갈래 %d개 · 사람 %d명' % (len(areas), len(people)))

    bad = False
    keys = {a['key'] for a in areas}

    # 1) COLLAB.md 표와 대조
    cp = os.path.join(lab, 'docs', 'COLLAB.md')
    if os.path.isfile(cp):
        ct = io.open(cp, encoding='utf-8', newline=None).read()
        ck = set(re.findall(r'\|\s*`([ABC]/[^`]+)`\s*\|', ct))
        if ck and ck != keys:
            print('  ★ COLLAB 표가 정본과 다릅니다. 정본에만: %s · COLLAB에만: %s'
                  % (sorted(keys - ck) or '없음', sorted(ck - keys) or '없음'))
            bad = True
        else:
            for a in areas:
                m = re.search(r'\|\s*`%s`\s*\|\s*\*?\*?([^|*]+)' % re.escape(a['key']), ct)
                if m and m.group(1).strip() != a['lead']:
                    print('  ★ `%s` 주담당이 다릅니다. 정본 %s · COLLAB %s'
                          % (a['key'], a['lead'], m.group(1).strip()))
                    bad = True

    # 2) GitHub 라벨과 대조
    gl = _gh_labels(lab)
    if gl is None:
        print('  라벨 대조는 건너뜀 (gh 사용 불가)')
    elif gl != keys:
        print('  ★ GitHub 라벨이 정본과 다릅니다. 정본에만: %s · 라벨에만: %s'
              % (sorted(keys - gl) or '없음', sorted(gl - keys) or '없음'))
        bad = True

    # 3) 폐기한 옛 이름이 게시물에 남았는가 (덱 밖까지 본다)
    #    다만 「이것은 옛 이름이다」라고 «설명하는» 문장은 통과시킨다.
    #    폐기 사실을 기록으로 남기는 것까지 막으면 철칙 2 와 부딪힌다.
    #    판정은 stalecheck 가 이미 갖고 있으므로 거기 것을 쓴다 (규칙을 둘로 안 만든다).
    if vault:
        import stalecheck
        hit = []
        for f in sorted(os.listdir(vault)):
            if not f.endswith('.html'):
                continue
            t = io.open(os.path.join(vault, f), encoding='utf-8', newline=None).read()
            for line in t.split(chr(10)):
                for d in DEAD:
                    if d not in line:
                        continue
                    if any(e in line for e in stalecheck.EXCUSE):
                        continue
                    if stalecheck._shape_excused(line, d):
                        continue
                    hit.append('%s(%s)' % (f, d))
        if hit:
            print('  ★ 폐기한 옛 5분야가 %d곳에 남아 있습니다: %s'
                  % (len(hit), ' · '.join(hit[:6])))
            bad = True

    if bad:
        print('    정본은 docs/ROLES.md 입니다. 거기를 고치면 덱은 따라옵니다.')
        return False
    print('  정본 · COLLAB · 라벨 · 게시물 네 곳이 같습니다')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    v = os.path.dirname(HERE)
    sys.exit(0 if main(v) else 1)
