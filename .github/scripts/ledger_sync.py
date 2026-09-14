# -*- coding: utf-8 -*-
"""원장(docs/LEDGER.md)의 「열린 이슈 전수」 절을 GitHub 열린 이슈로 다시 쓴다.

  왜: 사람이 세어 적는 동안 같은 날 안에서도 수가 51 · 57 · 60 · 71 · 72 · 81 · 79 로
  흔들렸다 (#161). 빌드 관문 [3.8] 이 낡은 원장을 배포 중단으로 잡으므로, 손 갱신이
  늦는 순간 사이트 배포가 통째로 선다. 세는 일은 기계가 하고 사람은 판단만 한다.

  ★ 기계가 쓰는 자리와 사람이 쓰는 자리를 마커로 가른다.
    자동:  <!-- 자동:시작 · 열린 이슈 전수 --> ~ <!-- 자동:끝 · 열린 이슈 전수 -->
             절 제목의 날짜와 건수 · 「관문에 걸린 것」 표 · 「사람별로 열린 것」 표
             전부 GitHub 이 답을 갖고 있는 사실이다.
           <!-- 자동:최종갱신 --> 이 붙은 「최종 갱신」 한 줄
    사람: 「손이 오래 안 간 것」 「막고 있는 것」 두 표.
           «왜 남아 있나» «무엇을 막나» 는 판단이라 API 에 답이 없다.
           기계가 흉내 내면 그럴듯하고 틀린 문장이 남는다. 손대지 않는다.
           대신 그 표에 닫힌 이슈가 남아 있으면 경고만 띄운다 (사람이 다시 판단할 자리).

  ★ 조용한 실패를 만들지 않는다 (커널 원칙 2).
    열린 이슈가 0건이거나 · 마커가 없거나 · 만든 블록에 이슈 번호가 빠졌거나 ·
    em dash 가 섞였으면 **파일을 쓰지 않고** 0 이 아닌 코드로 죽는다.
    쓴 뒤에는 쓴 결과를 다시 읽어 열린 번호가 전부 있는지 스스로 대조한다.

  쓰는 법
    python3 .github/scripts/ledger_sync.py --issues open.json          # 갱신
    python3 .github/scripts/ledger_sync.py --issues open.json --check  # 대조만 (바꾸면 1)

  open.json = GitHub Issues API 응답 배열. PR 은 이 스크립트가 걸러낸다.
"""
import argparse
import datetime
import json
import os
import re
import sys

MARK_BEGIN = '<!-- 자동:시작 · 열린 이슈 전수 -->'
MARK_END = '<!-- 자동:끝 · 열린 이슈 전수 -->'
MARK_STAMP = '<!-- 자동:최종갱신 -->'

# GitHub 핸들 -> 사람 이름. .github/scripts/review_inbox.py 와 같은 표.
HANDLE_NAME = {
    'vfxpedia': '오흥재',
    'maengu86': '맹라현',
    'less82': '오현민',
    'lmw0207': '이민우',
    'IQ152': '임석헌',
}
# 사람 표의 줄 순서. 여기 없는 이름은 뒤에 가나다순으로 붙는다.
NAME_ORDER = ['오흥재', '맹라현', '오현민', '임석헌', '이민우']
LEAD = '오흥재'          # 이 사람 담당은 줄 안에 이름을 덧붙이지 않는다 (기본값이라)
TEAM_MIN = 3             # 담당이 셋 이상이면 개인이 아니라 「팀 공동」
TITLE_MAX = 34           # 표 칸이 벽이 되지 않게 자른다 (손으로 쓰던 딱지 길이에 맞췄다)

PROMO = '승격 검토'      # inbox 승격 검토 이슈는 제목 앞머리로 갈린다
NO_GATE = '관문 없음'
TEAM = '팀 공동'
NO_OWNER = '담당 없음'

# 원장 절 머리말. 기계가 다시 쓰는 자리라 여기 상수로 둔다.
PREAMBLE = [
    '> **이 절이 뼈대다.** 열린 이슈가 여기 없으면 이 문서가 지금을 안 담고 있는 것이고,',
    '> 빌드 관문 `[3.8]` 이 그것을 잡는다. 닫힌 이슈는 지운다.',
    '>',
    '> 이 블록은 `ledger-sync` 워크플로가 GitHub 열린 이슈에서 **다시 쓴다.** 손으로 고치지 않는다.',
    '> 아래 「손이 오래 안 간 것」 「막고 있는 것」 두 표는 판단이라 **사람 몫**이다 (마커 밖).',
]

# ★ 2026-09-14. 첫 항목이 `'·': '·'` 였다. 자기자신으로 바꾸니 아무것도 안 하고,
#   그런 다음 마지막 검사가 «· 가 남았다» 고 죽였다. `·` 는 우리가 **쓰는** 글자라
#   봉이 커밋된 날부터 한 번도 안 돌았다 (#346 의 진짜 원인).
#
#   원래 키는 em dash 였는데, 언젠가 em dash 일괄 치환이 **치환표 자체를**
#   고쳐 `—` 가 `·` 가 됐다. `artifact2md.py` 의 복구표에서도 같은 일이 있었다.
#   그래서 이제 **글자를 직접 안 적고 코드로 적는다.** 쓸어도 안 다친다.
DASHES = {'—': '·', '–': '·', '―': '·', '−': '-'}


def clean(text):
    """표 칸에 넣어도 안전한 한 줄로 만든다.

    em dash 는 전면 금지다 (관문 [3.5]). 이슈 제목에 섞여 들어오면 원장을 통해
    웹으로 새므로 여기서 끊는다. `|` 는 표 열을 깨뜨리므로 가운뎃점으로 바꾼다.
    """
    t = text or ''
    for bad, good in DASHES.items():
        t = t.replace(bad, good)
    t = t.replace('|', '·')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def short_title(title):
    """제목 앞머리 `[작업]` `[승격 검토]` 를 떼고 길면 자른다.

    자를 때 낱말 가운데를 끊지 않도록 한계 근처의 마지막 공백까지 물러선다.
    """
    t = clean(title)
    t = re.sub(r'^\[[^\]]{1,12}\]\s*', '', t)
    # 승격 검토 이슈는 제목이 전부 `inbox/…` 로 시작한다. 그 여섯 글자는 줄마다
    # 같아서 아무것도 알려주지 않으면서 뒤의 날짜와 주제를 잘라 먹는다.
    t = re.sub(r'^inbox/', '', t)
    if len(t) <= TITLE_MAX:
        return t
    cut = t[:TITLE_MAX - 1]
    sp = cut.rfind(' ')
    if sp >= TITLE_MAX - 9:
        cut = cut[:sp]
    return cut.rstrip(' ·,:(') + '…'


def is_pr(obj):
    return 'pull_request' in obj


def load_issues(path):
    """GitHub Issues API 응답을 읽어 PR 을 걸러낸다.

    `gh api --paginate --slurp` 는 «쪽의 배열» 을 준다 (`[[...], [...]]`).
    평평하게 펴는 일을 여기서 한다. 워크플로에서 jq 로 펴면 그 한 줄은
    러너에서만 돌아 여기서 시험할 수 없다. 시험할 수 없는 자리를 안 만든다.
    """
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, dict):          # 쪽 나눔이 없는 단일 응답 대비
        raw = [raw]
    if not isinstance(raw, list):
        die('이슈 JSON 이 배열이 아니다: %s' % path)
    if raw and all(isinstance(p, list) for p in raw):
        pages = len(raw)
        raw = [o for page in raw for o in page]
        sys.stderr.write('쪽 %d 개를 폈다\n' % pages)
    if not all(isinstance(o, dict) for o in raw):
        die('이슈 JSON 에 객체가 아닌 것이 섞였다: %s' % path)
    issues = [o for o in raw if not is_pr(o)]
    prs = len(raw) - len(issues)
    sys.stderr.write('읽음: 전체 %d · 이슈 %d · PR 제외 %d\n' % (len(raw), len(issues), prs))
    return issues


def gate_label(ms):
    """마일스톤 -> 「기획발표 9/4」 같은 관문 딱지."""
    title = clean(ms.get('title') or '')
    head = title.split(' · ')[0].strip() or title
    due = ms.get('due_on') or ''
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', due)
    if m:
        return '%s %d/%d' % (head, int(m.group(2)), int(m.group(3)))
    return head


def bucket_of(issue):
    """이 이슈가 들어갈 관문 줄의 (정렬키, 딱지)."""
    ms = issue.get('milestone')
    if ms:
        due = ms.get('due_on') or '9999-12-31'
        return ('1' + due + (ms.get('title') or ''), gate_label(ms))
    title = clean(issue.get('title') or '')
    if title.startswith('[%s]' % PROMO):
        return ('3', PROMO)
    return ('2', NO_GATE)


def owners(issue):
    """담당자 이름 목록. 셋 이상이면 팀 공동 한 줄로 접는다."""
    logins = [a.get('login') for a in (issue.get('assignees') or []) if a.get('login')]
    names = [HANDLE_NAME.get(x, x) for x in logins]
    if len(names) >= TEAM_MIN:
        return [TEAM]
    return names or [NO_OWNER]


def entry(issue):
    """관문 표 칸에 들어갈 한 조각: `#123 제목 (이름)`.

    제목에 이미 이름이 들어 있으면 덧붙이지 않는다. 안 그러면
    `#65 실패 지형 gap ... (임석헌) (임석헌)` 처럼 두 번 찍힌다 (시험에서 잡았다).
    """
    who = owners(issue)
    text = short_title(issue.get('title'))
    tail = ''
    if who == [NO_OWNER]:
        tail = ' (담당 없음)'
    elif len(who) == 1 and who[0] not in (LEAD, TEAM) and who[0] not in text:
        tail = ' (%s)' % who[0]
    return '#%d %s%s' % (issue['number'], text, tail)


def build_block(issues, today):
    """마커 사이에 들어갈 본문 전체를 만든다."""
    gates = {}
    for it in issues:
        key, label = bucket_of(it)
        gates.setdefault((key, label), []).append(it)

    lines = []
    lines.append('## 📋 열린 이슈 전수 (%s 기준 %d건)' % (today, len(issues)))
    lines.append('')
    lines.extend(PREAMBLE)
    lines.append('')
    lines.append('**관문에 걸린 것**')
    lines.append('')
    lines.append('| 관문 | 이슈 |')
    lines.append('|---|---|')
    for (key, label) in sorted(gates):
        rows = sorted(gates[(key, label)], key=lambda x: x['number'])
        cell = ' · '.join(entry(x) for x in rows)
        lines.append('| %s (%d) | %s |' % (label, len(rows), cell))

    people = {}
    for it in issues:
        for name in owners(it):
            people.setdefault(name, []).append(it['number'])

    def person_key(name):
        if name in NAME_ORDER:
            return (0, NAME_ORDER.index(name), '')
        if name in (TEAM, NO_OWNER):
            return (2, 0, name)
        return (1, 0, name)

    lines.append('')
    lines.append('**사람별로 열린 것**')
    lines.append('')
    lines.append('| 사람 | 건수 | 이슈 |')
    lines.append('|---|---|---|')
    for name in sorted(people, key=person_key):
        nums = sorted(set(people[name]))
        lines.append('| %s | %d | %s |' % (name, len(nums), ' '.join('#%d' % n for n in nums)))

    return '\n'.join(lines)


def splice(md, block):
    """마커 사이만 갈아 끼운다. 마커 밖은 한 글자도 건드리지 않는다."""
    b = md.find(MARK_BEGIN)
    e = md.find(MARK_END)
    if b < 0 or e < 0 or e < b:
        die('마커를 못 찾았다. `%s` 와 `%s` 가 원장에 있어야 한다.' % (MARK_BEGIN, MARK_END))
    head = md[:b + len(MARK_BEGIN)]
    tail = md[e:]
    return head + '\n' + block + '\n' + tail


def stamp(md, today, count):
    """「최종 갱신」 한 줄을 다시 쓴다. 마커가 붙은 줄만 대상이다."""
    # `\s*$` 를 쓰면 re.M 에서 \s 가 줄바꿈까지 먹어 뒤 빈 줄이 사라진다 (실측으로 잡았다).
    pat = re.compile(r'^> 최종 갱신: .*%s[ \t]*$' % re.escape(MARK_STAMP), re.M)
    if not pat.search(md):
        die('「최종 갱신」 줄에 %s 마커가 없다.' % MARK_STAMP)
    line = '> 최종 갱신: %s (열린 이슈 전수 %d건 · `ledger-sync` 자동 집계) %s' % (
        today, count, MARK_STAMP)
    return pat.sub(lambda _: line, md, count=1)


def human_part(md):
    """마커 끝부터 다음 `## ` 제목 전까지. 사람이 판단으로 쓰는 두 표가 사는 자리."""
    e = md.find(MARK_END)
    if e < 0:
        return ''
    rest = md[e + len(MARK_END):]
    m = re.search(r'^## ', rest, re.M)
    return rest[:m.start()] if m else rest


def warn_closed(md, open_numbers):
    """사람 표에 닫힌 이슈가 남았으면 알린다. 고치지는 않는다 (판단이 필요한 자리다)."""
    found = sorted({int(n) for n in re.findall(r'#(\d+)', human_part(md))})
    return [n for n in found if n not in open_numbers]


def die(msg):
    sys.stderr.write('실패: %s\n' % msg)
    raise SystemExit(1)


def note(msg):
    if os.environ.get('GITHUB_ACTIONS'):
        sys.stdout.write('::warning::%s\n' % msg)
    sys.stderr.write('주의: %s\n' % msg)


def kst_today():
    tz = datetime.timezone(datetime.timedelta(hours=9))
    return datetime.datetime.now(tz).strftime('%Y-%m-%d')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--issues', required=True, help='GitHub Issues API 응답 JSON')
    ap.add_argument('--ledger', default='docs/LEDGER.md')
    ap.add_argument('--today', default=None, help='기준일 (기본: KST 오늘)')
    ap.add_argument('--check', action='store_true', help='쓰지 않고 어긋나면 1 로 죽는다')
    args = ap.parse_args()

    today = args.today or kst_today()
    issues = load_issues(args.issues)

    # 조용한 실패 차단 ①: 0건이면 원장을 비우게 된다. 그럴 바엔 죽는다.
    if not issues:
        die('열린 이슈가 0건으로 읽혔다. 원장을 비우지 않는다 (토큰·권한·필터를 보라).')

    numbers = {int(x['number']) for x in issues}
    block = build_block(issues, today)

    # 조용한 실패 차단 ②: 만든 블록이 실제로 유의미한지 스스로 주장한다.
    in_block = {int(n) for n in re.findall(r'#(\d+)', block)}
    missing = sorted(numbers - in_block)
    if missing:
        die('만든 블록에 열린 이슈가 빠졌다: %s' % missing)
    for bad in DASHES:
        if bad in block:
            die('만든 블록에 금지 문자(%r)가 섞였다.' % bad)

    with open(args.ledger, encoding='utf-8') as f:
        before = f.read()

    after = stamp(splice(before, block), today, len(issues))

    # 조용한 실패 차단 ③: 쓰기 «직전» 결과물을 되읽어 대조한다.
    head = re.search(r'^## 📋 열린 이슈 전수 \((\d{4}-\d{2}-\d{2}) 기준 (\d+)건\)$', after, re.M)
    if not head or int(head.group(2)) != len(issues):
        die('절 제목의 건수가 실제 열린 이슈 수와 다르다.')

    for n in warn_closed(after, numbers):
        note('사람이 쓰는 표에 열려 있지 않은 #%d 가 남아 있다. 판단이 필요하니 직접 정리하라.' % n)

    if before == after:
        sys.stderr.write('변경 없음 (열린 이슈 %d건 · %s)\n' % (len(issues), today))
        print('changed=no')
        print('count=%d' % len(issues))
        return 0

    if args.check:
        sys.stderr.write('어긋남: 원장이 열린 이슈 %d건과 다르다.\n' % len(issues))
        return 1

    with open(args.ledger, 'w', encoding='utf-8', newline='\n') as f:
        f.write(after)
    sys.stderr.write('갱신: 열린 이슈 %d건 · %s\n' % (len(issues), today))
    print('changed=yes')
    print('count=%d' % len(issues))
    return 0


if __name__ == '__main__':
    sys.exit(main())
