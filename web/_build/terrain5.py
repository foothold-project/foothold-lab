# -*- coding: utf-8 -*-
"""Track A · 실패 험지 5종 카드의 «자료» 쪽 (foothold-lab#179).

  화면(HTML·CSS)은 hub3.terrain_html 이 그린다. 여기는 셋만 한다.
    1. 실측  summary-thr1.5.csv 한 장에서 성공 · 생존 · 전진을 읽는다.
            raw 열은 쓰지 않는다 (팀장 지시). 파일이 없으면 시끄럽게 말한다.
    2. 연결  이슈 다섯(#65~#69)의 본문 · 코멘트와, 그 번호를 언급하는
            inbox/ · docs/ 문서. hub3._mentions 와 같은 «번호가 키» 규칙이다.
    3. 분류  문서 · 코멘트 하나를 네 칸(진단 · 설계 · 레시피 · 결과)
            중 하나에 둔다. 못 가면 「미분류」다. 숨기지 않는다.

  분류 규칙 (팀장 확정 2026-09-03 · 칸 넷은 2026-09-04)
    카드 = 머리말 «이슈: #NN» 또는 본문의 «#NN» · «issues/NN» · «#65~#69» 범위.
    칸   = 머리말 «단계:» 가 있으면 그것. 없으면 제목(코멘트는 첫 머리글)에서
           가장 먼저 나오는 낱말. 「재분류 · 분류 변경 · 실패 모드」 도 진단이다.
    「가설」 칸은 없다. 머리말 «단계: 가설» 이든 제목의 「가설」 이든 설계로 보낸다.
    다섯 카드 전부에 붙는 문서(계획 정본 같은 것)는 «공통» 으로 한 번만 보인다.
    실패형: gap · stepping_stones 낙상형 / rails · pit · floating_ring 전진불능형.
    rails 는 화면에 「턱·장애물 극복」. key 는 괄호 병기 (9/2 멘토링 용어 지적).

  훑지 않는 것
    LEDGER · DECISIONS · FLOW 같은 원장과 notices · digest · ops 는 «모든 이슈를
    스치는» 문서라 험지 문서가 아니다. 여기까지 세면 미분류가 원장 사본이 된다.

  ★ 답을 아는 입력으로 먼저 시험한다 (커널 2-2 원칙 1). kat() 가 이슈 하나에
    가짜 문서 셋을 붙여 분류를 확인하고, 틀리면 hub3 가 빌드를 세운다.
"""
import csv
import io
import json
import os
import re
import subprocess
import sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

REPO = 'foothold-project/foothold-lab'
# ★ 2026-09-14. 정본으로 옮겼다.
#
#   전에는 `20260903-rough10-1.0mps/summary-thr1.5.csv` 를 읽었다. 그것은
#   **평가 규격 1** 의 값이다. 그 사이 정본이 규격 2 로 바뀌었는데 보드만
#   옛 자리를 보고 있었고, 그래서 같은 허브 안에서 숫자가 갈렸다.
#
#     보드         rails 4% 성공 · 85% 생존 · 2.64 m
#     벤치마크 문서  rails 8% 성공 · 82% 생존 · 2.70 m
#
#   읽는 사람은 어느 쪽을 믿어야 할지 모른다. **자리가 둘인데 한쪽만 고친**
#   그 부류다. 이 저장소에서 다섯 번째다.
CSV_REL = os.path.join('sim', 'eval', 'results', 'maindata-v1', 'baseline',
                       'unseen10', 'd0.5', 'v1', 'generalization_summary.csv')

# (이슈, key, 화면 이름, 실패형, 담당 예비값). 담당은 이슈 제목 끝 괄호에서 읽고
# 못 읽으면 이 값을 쓴다. 실패형은 팀장 확정값이라 코드에 둔다.
# 여섯째 칸은 «단서» 다. 카드 수치는 난이도 0.5 한 점에서 잰 값인데, 지형에
# 따라 다른 난이도에서 성격이 달라지는 것이 있다. 그럴 때만 한 줄 적는다.
TERRAINS = [
    (65, 'gap', '틈', '낙상형', '임석헌', ''),
    (66, 'rails', '턱·장애물 극복', '전진불능형', '맹라현', ''),
    (67, 'stepping_stones', '디딤돌', '낙상형', '오현민', ''),
    (68, 'pit', '구덩이', '전진불능형', '이민우', ''),
    # ★ 2026-09-10 (lab#388). 이 지형만 난이도 축의 뜻이 뒤집혀 있다.
    #   Isaac Lab 이 링 «높이» 만 부호를 뒤집어 보간한다 (mesh_terrains.py:623).
    #   난이도가 오르면 링이 낮아져 «몸통을 막는 가로막» 이 «낮은 허들» 이 된다.
    #   실측(카드와 같은 조건 · 1.0 m/s · 6초 · 100판): 0.5 까지 0% ·
    #   0.7 부터 2% · 0.8 에서 13%(최고) · 1.0 에서 4%. 머리 접촉 233 -> 20.
    #   ★ 처음에 「1.0 에서 28%」로 적었다가 고쳤다. 그 28% 는 속도 0.5 m/s
    #     값이고 카드의 다른 수치는 전부 1.0 m/s 다. 한 줄만 다른 조건이면
    #     읽는 사람은 같은 조건으로 읽는다.
    #     그래서 이 줄에는 숫자를 안 쓴다. 같은 조건에서도 최고점이 1.0 이
    #     아니라 0.8 이라 어느 한 숫자를 골라도 오해를 만든다. 성격이 바뀐다는
    #     사실만 남기고 수치는 원본 문서가 갖는다.
    #   「전진불능형」이 틀린 것이 아니라 0.5 에서만 그렇다.
    (69, 'floating_ring', '뜬 고리', '전진불능형', '오흥재',
     '난이도가 오르면 링이 낮아져 장애물의 «종류» 가 바뀐다. 이 줄의 수치는 그 성격이 바뀌기 «전» 값이다 (lab#388)'),
]
NUMS = frozenset(t[0] for t in TERRAINS)

STAGES = ['진단', '설계', '레시피', '결과']
# 진단 낱말 넷째 묶음(재측정 · 조건이 바뀌)은 팀장 2026-09-04 확정. 근거는 아래 §분류.
STAGE_WORDS = [('진단', ('진단', '재분류', '분류 변경', '실패 모드',
                         '재측정', '조건이 바뀌')),
               ('설계', ('설계', '가설')),
               ('레시피', ('레시피',)),
               ('결과', ('결과',))]
# 머리말 «단계:» 의 옛 이름. 「가설」 칸은 뺐다 (팀장 2026-09-04). 설계로 간다.
STAGE_ALIAS = {'가설': '설계'}

SKIP_DIRS = ('docs/notices', 'docs/digest', 'docs/ops', 'docs/schedule',
             'docs/assets')
SKIP_FILES = frozenset(['docs/LEDGER.md', 'docs/DECISIONS.md', 'docs/FLOW.md',
                        'docs/WORKFLOW.md', 'docs/AUTOMATION.md',
                        'docs/COLLAB.md', 'docs/QUESTIONS.md',
                        'docs/PRD-WEB.md', 'docs/DESIGN-GUIDE.md'])
SKIP_NAMES = frozenset(['README.md', 'AGENTS.md'])

# 험지 단계 표는 «실험» 계열 산출물을 담는다. 진단 · 설계 · 레시피 · 결과가
# 그 축이다. 회의록과 운영 안내는 다른 축인데, 이슈 번호를 언급했다는 이유로
# 끌려와 미분류 서랍만 채웠다(2026-09-04 실측: 미분류 둘 다 이 부류였다).
# 표에 실제로 들어간 문서 둘은 «분류: 실험» 이다.
SKIP_KINDS = frozenset(['회의록', '운영', '가이드'])

# GitHub 로그인 -> 화면 이름. 코멘트에는 문서 같은 «작성:» 머리말이 없어서
# 여기서만 이름을 안다. 못 찾으면 로그인을 그대로 쓴다 (빈칸으로 숨기지 않는다).
GH_NAME = {'vfxpedia': '오흥재'}

_ISSUE = {}
_COMMIT_WHEN = {}


# ── 1. 실측 ──────────────────────────────────────────────────────────
def parse_csv(text):
    """summary-thr1.5.csv 본문 -> {terrain: {success, survival, progress, n}}.
    success · survival 은 % 정수, progress 는 m. 열 이름이 바뀌면 KeyError 로 선다."""
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        out[r['terrain']] = {
            'success': int(round(float(r['overall_success_rate']) * 100)),
            'survival': int(round(float(r['survival_rate']) * 100)),
            'progress': float(r['mean_forward_progress_m']),
            'n': int(r['episodes']),
        }
    return out


def csv_rows(lab):
    p = os.path.join(lab, CSV_REL)
    if not os.path.isfile(p):
        print('  [!] 험지 실측 CSV 가 없다: %s' % p)
        return {}
    return parse_csv(io.open(p, encoding='utf-8').read())


# ── 2. 연결 ──────────────────────────────────────────────────────────
_NUM = re.compile(r'#(\d{1,4})(?!\d)(?:\s*~\s*#?(\d{1,4})(?!\d))?')
_URL = re.compile(r'issues/(\d{1,4})(?!\d)')


def mention_set(text):
    """본문이 언급하는 이슈 번호. «#65~#69» · «#65~69» 범위도 편다."""
    out = set()
    for m in _NUM.finditer(text or ''):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if b < a or b - a > 20:
            b = a
        out.update(range(a, b + 1))
    for m in _URL.finditer(text or ''):
        out.add(int(m.group(1)))
    return out


def owner_of(title, fallback):
    m = re.search(r'\(([^()]{2,8})\)\s*$', title or '')
    return m.group(1) if m else fallback


def issue_full(n):
    """이슈 하나의 본문 · 코멘트 · 상태. 닫힌 것도 읽는다. 실패하면 None 과 경고."""
    if n in _ISSUE:
        return _ISSUE[n]
    try:
        r = subprocess.run(
            ['gh', 'issue', 'view', str(n), '--repo', REPO, '--json',
             'number,title,state,body,comments,url'],
            capture_output=True, text=True, timeout=45, encoding='utf-8')
        it = json.loads(r.stdout) if r.returncode == 0 else None
        if it is None:
            print('  [!] #%d 를 못 읽었다: %s' % (n, (r.stderr or '')[:80]))
    except Exception as e:
        print('  [!] #%d 를 못 읽었다: %s' % (n, e))
        it = None
    _ISSUE[n] = it
    return it


# ── 3. 분류 ──────────────────────────────────────────────────────────
def clean(s):
    return re.sub(r'\s+', ' ', (s or '').replace('`', '').replace('**', '')).strip()


def stage_of(title, meta=None):
    """머리말 «단계:» 가 있으면 그것(가설 -> 설계). 없으면 제목에서 가장 먼저 나오는 낱말."""
    ex = ((meta or {}).get('단계') or '').strip()
    for old, s in STAGE_ALIAS.items():
        if ex.startswith(old):
            return s
    for s in STAGES:
        if ex.startswith(s):
            return s
    best = None
    for s, words in STAGE_WORDS:
        for w in words:
            i = (title or '').find(w)
            if i >= 0 and (best is None or i < best[0]):
                best = (i, s)
    return best[1] if best else ''


def comment_title(body):
    """코멘트의 첫 머리글. 없으면 첫 줄."""
    first = ''
    for line in (body or '').splitlines():
        t = line.strip()
        if not t:
            continue
        if t.startswith('#'):
            return clean(t.lstrip('#'))[:90]
        if not first:
            first = t
    return clean(first)[:90]


def head_meta(text, fields=('작성', '이슈', '단계', '요지', '출처', '분류')):
    """머리말 «> 이름: 값» 을 앞부분에서 읽는다. 문서와 코멘트가 같은 규칙이다."""
    m = {}
    for f in fields:
        hit = re.search(r'^>\s*%s\s*:\s*(.+)$' % f, (text or '')[:2500], re.M)
        if hit:
            m[f] = hit.group(1).strip()
    return m


def comment_stage(body):
    """코멘트의 칸. 문서와 같은 순서다: 머리말 «단계:» 가 있으면 그것, 없으면 제목.

    ★ 팀장 2026-09-04: 「분류를 사람이 손으로 하면 안 된다」. 문서에만 있던
      «> 단계: 진단» 머리말 규칙을 코멘트에도 연다. 앞으로 쓰는 코멘트는
      한 줄만 적으면 낱말 목록을 건드릴 필요가 없다.
    """
    return stage_of(comment_title(body), head_meta(body))


def gh_when(iso):
    """GitHub ISO(UTC) -> 화면용 «YYYY-MM-DD HH:MM» (KST).

    문서 머리말 시각은 한국 시각이다. 코멘트만 UTC 로 두면 같은 줄에 두 시간대가
    섞여 선후가 거꾸로 보인다. 여기서 +9 로 맞춘다.
    """
    import datetime
    if not iso:
        return ''
    try:
        t = datetime.datetime.strptime(iso[:19], '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return (iso or '')[:10]
    return (t + datetime.timedelta(hours=9)).strftime('%Y-%m-%d %H:%M')


def commit_when(lab, rel):
    """머리말에 «작성:» 이 아예 없을 때만 쓰는 대체값. 그 파일의 마지막 커밋 시각."""
    key = (lab, rel)
    if key in _COMMIT_WHEN:
        return _COMMIT_WHEN[key]
    out = ''
    try:
        r = subprocess.run(['git', '-C', lab, 'log', '-1', '--format=%cI',
                            '--', rel],
                           capture_output=True, text=True, timeout=20,
                           encoding='utf-8')
        if r.returncode == 0 and (r.stdout or '').strip():
            iso = r.stdout.strip()
            out = iso[:10] + ' ' + iso[11:16]
    except Exception as e:
        print('  [!] %s 커밋 시각을 못 읽었다: %s' % (rel, e))
    _COMMIT_WHEN[key] = out
    return out


_SRC_MD = re.compile(r'(inbox/[^\s`·|]+\.md)')


def classify_text(text):
    """문서 원문 -> (제목, 이슈 집합, 칸, 작성자, 시각, 원본). 파일을 안 열어도 되게 순수 함수."""
    import hub3
    m = head_meta(text)
    h1 = re.search(r'^#\s+(.+)$', text, re.M)
    title = clean(h1.group(1)) if h1 else ''
    # ★ 2026-09-09 팀장 지적: 「민우 pit 문서가 왜 라현이 지형인 rail 에 들어가 있냐」.
    #   원인은 여기였다. 머리말의 «이슈:» 와 본문 언급을 «합집합» 으로 묶었다.
    #   그런데 본문 언급은 소유가 아니라 «인용» 인 경우가 있다.
    #   실측: 20260908-pit-diagnosis.md 는 머리말에 이슈 #68(pit) 을 선언해 놓고
    #   본문 표에서 맹라현 님 rails(#66) 를 비교 대상으로 한 번 인용했다.
    #   그 한 번 때문에 pit 진단이 rails 줄에도 걸렸다.
    #   선언이 있으면 그것이 소유다. 인용은 소유가 아니다.
    #   선언이 없을 때만 본문에서 찾는다 (옛 문서 · 코멘트가 그렇다).
    declared = mention_set(m.get('이슈', ''))
    issues = declared or mention_set(text)
    who, when = hub3._who_when(m)

    # ★ 2026-09-13 팀장 3번째 지시: 「실패 지형 파인튜닝 실행 계획」이 rails 의
    #   «레시피» 칸에 들어가 있다. 그 문서는 rails 레시피가 아니다.
    #
    #   원인은 «공통» 판정이 **이슈 번호만** 세는 것이었다. 그 문서는 다섯
    #   지형을 이름으로 전부 다루는데(gap 9 · rails 13 · stepping_stones 5 ·
    #   pit 10 · floating_ring 7) 머리말 이슈는 `#59 #66` 뿐이라, 번호로는
    #   rails 하나만 맞고 그 행으로 갔다. 제목에 「레시피」가 있어 그 칸에 앉았다.
    #
    #   고치는 길 둘을 다 넣는다. 하나만 넣으면 다음 문서가 또 샌다.
    #     1. 문서가 «자기 자리를 선언» 할 수 있게 한다 (선언이 언제나 이긴다)
    #     2. 선언이 없어도 다섯 지형을 이름으로 다 다루면 공통으로 본다
    scope = (m.get('지형') or '').strip()
    named = {k for _n, k, _ko, _f, _o, _h in TERRAINS
             if re.search(r'(?<![A-Za-z_])%s(?![A-Za-z_])'
                           % re.escape(k), text)}
    common = (scope in ('공통', '전체', '다섯 지형')
              or (not scope and len(named) == len(TERRAINS)))

    return {'title': title, 'issues': issues, 'stage': stage_of(title, m),
            'who': who, 'when': when, 'scope': scope, 'common_by_text': common,
            'src': _SRC_MD.findall(m.get('출처', '')),
        'kind': (m.get('분류') or '').strip()}


def doc_records(lab):
    """inbox/ · docs/ 의 md 중 다섯 이슈 중 하나라도 언급하는 것."""
    import mdlinks
    out = []
    for root in ('inbox', 'docs'):
        base = os.path.join(lab, root)
        for d, dirs, files in os.walk(base):
            dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
            rel_d = os.path.relpath(d, lab).replace(os.sep, '/')
            if any(rel_d == s or rel_d.startswith(s + '/') for s in SKIP_DIRS):
                dirs[:] = []
                continue
            for f in sorted(files):
                if not f.endswith('.md') or f in SKIP_NAMES:
                    continue
                rel = (rel_d + '/' + f) if rel_d != '.' else f
                if rel in SKIP_FILES:
                    continue
                try:
                    text = io.open(os.path.join(d, f), encoding='utf-8',
                                   errors='replace').read()
                except OSError:
                    continue
                c = classify_text(text)
                hit = c['issues'] & NUMS
                if not hit:
                    continue
                if c['kind'] in SKIP_KINDS:
                    continue
                page = mdlinks.resolve(rel) if rel.startswith('docs/') else ''
                # 머리말에 «작성:» 이 아예 없을 때만 커밋 시각으로 대체한다.
                # 화면에서 시각이 통째로 빠지는 쪽이 더 나쁘다.
                if not c['when']:
                    c['when'] = commit_when(lab, rel)
                    c['whence'] = '커밋'
                c.update({
                    'kind': '문서',
                    'rel': rel,
                    'title': c['title'] or f,
                    'issues': hit,
                    'common': hit == NUMS or c.get('common_by_text'),
                    'href': page or ('https://github.com/%s/blob/main/%s'
                                     % (REPO, quote(rel))),
                    'published': bool(page),
                })
                out.append(c)
    return dedupe(out)


def dedupe(docs):
    """승격된 문서는 한 번만. docs/ 머리말 «출처» 가 가리키는 inbox 원본을 뺀다.

    ★ 팀장 지적 2026-09-04: RunPod 문서가 미분류에 «둘» 있었다. inbox 제출본과
      docs/ 승격본이 같은 글인데 둘 다 세어졌다. 어느 쪽을 뺄지는 손으로 고르지
      않는다. 승격본이 머리말에 원본 경로를 이미 적어 두므로 그것을 따른다.
    """
    promoted = set()
    for d in docs:
        if d['rel'].startswith('docs/'):
            promoted.update(d.get('src') or [])

    # ★ 2026-09-09 실측. 위 규칙만으로는 새는 것을 라이브에서 봤다.
    #   rails 카드에 「레일즈 진단」이, pit 카드에 「pit 진단」이 «둘씩» 있었다.
    #   승격본과 inbox 제출본이 나란히 걸렸다. 원인은 승격이 머리말에
    #   «> 출처: 제출 inbox/...» 를 «항상 적지는 않는» 데 있다. 실제로 그 두
    #   문서는 출처 줄이 없다. 규칙이 한 자리에만 있으면 그 자리가 비는 순간
    #   조용히 무너진다 (커널 철칙 4).
    #   그래서 «같은 글인가» 를 화면에 보이는 값으로 한 번 더 본다.
    #   제목 · 작성자 · 작성 시각이 셋 다 같고 한쪽이 승격본이면 같은 글이다.
    #   승격본을 남긴다. 독자는 GitHub 원문보다 사이트 페이지를 원한다.
    def _id(d):
        return (d.get('title') or '', d.get('who') or '', d.get('when') or '')

    ident = {_id(d) for d in docs
             if d['rel'].startswith('docs/') and all(_id(d))}
    for d in docs:
        if not d['rel'].startswith('docs/') and _id(d) in ident:
            promoted.add(d['rel'])

    return [d for d in docs if d['rel'] not in promoted]


def order(cards):
    """채운 칸이 많은 것이 앞. 같으면 전진이 긴 것(통과선에 가까운 것)이 앞."""
    cards.sort(key=lambda c: (-c['filled'], -((c['meas'] or {}).get('progress', 0.0))))
    return cards


def build_cards(lab):
    """(카드 목록, 공통 문서, 경고). 카드는 정렬돼 있다."""
    rows = csv_rows(lab)
    docs = doc_records(lab)
    cards, notes = [], []
    for no, key, ko, mode, fallback, note in TERRAINS:
        it = issue_full(no)
        cells = dict((s, []) for s in STAGES)
        loose = []
        for d in docs:
            if no not in d['issues'] or d['common']:
                continue
            item = {'kind': '문서', 'title': d['title'], 'href': d['href'],
                    'when': d['when'], 'who': d['who'], 'stage': d['stage'],
                    'whence': d.get('whence', '')}
            (cells[d['stage']] if d['stage'] else loose).append(item)
        if it:
            for c in it.get('comments') or []:
                t = comment_title(c.get('body'))
                s = comment_stage(c.get('body'))
                login = ((c.get('author') or {}).get('login') or '')
                item = {'kind': '코멘트', 'title': t, 'href': c.get('url', ''),
                        'when': gh_when(c.get('createdAt')),
                        'who': GH_NAME.get(login, login),
                        'stage': s}
                (cells[s] if s else loose).append(item)
        else:
            notes.append('#%d 이슈를 못 읽었다. 칸이 비어 보여도 «없다» 가 아니다' % no)
        meas = rows.get(key)
        if not meas:
            notes.append('%s 실측이 CSV 에 없다' % key)
        cards.append({
            'no': no, 'key': key, 'ko': ko, 'mode': mode,
            'note': note,
            'owner': owner_of(it['title'], fallback) if it else fallback,
            'url': (it or {}).get('url') or 'https://github.com/%s/issues/%d' % (REPO, no),
            'state': (it or {}).get('state', ''),
            'cells': cells, 'loose': loose, 'meas': meas,
            'filled': sum(1 for v in cells.values() if v),
        })
    common = [d for d in docs if d['common']]
    return order(cards), common, notes


# ── ★ 답을 아는 입력 ─────────────────────────────────────────────────
def kat():
    """이슈 #68 에 가짜 문서 셋(+둘)을 붙여 카드 · 칸 분류를 못 박는다."""
    # ★ 2026-09-10. 단서 칸에 «손으로 쓴 수치» 를 금지한다.
    #   실측 수치는 CSV 에서 파생되어 손으로 틀릴 수 없다. 그런데 이 칸은
    #   사람이 쓰는 문장이라 틀릴 수 있고 실제로 틀렸다.
    #   「1.0 에서 28%」를 박았는데 그 28% 는 속도 0.5 m/s 값이었다. 카드의
    #   다른 수치는 전부 1.0 m/s 라, 읽는 사람은 같은 조건으로 읽는다.
    #   게다가 같은 조건에서도 최고점은 1.0 이 아니라 0.8(13%)이라 어느 한
    #   숫자를 골라도 오해를 만든다.
    #   그래서 이 칸은 «성격» 만 적는다. 수치는 원본 문서가 갖는다.
    for _no, _key, _ko, _mode, _own, note in TERRAINS:
        if re.search(r'\d+(?:\.\d+)?\s*%', note or ''):
            return False, ('단서 칸에 손으로 쓴 수치가 있다: %s' % note[:40] +
                           ' | 수치는 CSV 파생이 아니면 못 믿는다')
    n = chr(10)
    d1 = '# 구덩이 진단: 왜 못 오르나' + n + '> 작성: 이민우 · 2026-09-03 10:00' + n + '> 이슈: #68' + n + '본문'
    d2 = '# 구덩이 스윕 설계' + n + '> 작성: 이민우 · 2026-09-03' + n + '근거 https://github.com/x/y/issues/68 참조'
    d3 = '# 아무 제목' + n + '> 단계: 레시피' + n + '이 글은 #68 에 붙는다'
    d4 = '# 회의 메모' + n + '#68 얘기를 했다'
    d5 = '# 계획 정본' + n + '실패 5종 파인튜닝 (#65~#69)'
    want = [(d1, {68}, '진단'), (d2, {68}, '설계'), (d3, {68}, '레시피'),
            (d4, {68}, ''), (d5, set(range(65, 70)), '')]
    for i, (txt, issues, stage) in enumerate(want, 1):
        c = classify_text(txt)
        if c['issues'] & NUMS != issues:
            return False, '문서 %d: 이슈 %s 를 기대했는데 %s' % (i, sorted(issues), sorted(c['issues']))
        if c['stage'] != stage:
            return False, '문서 %d: 칸 「%s」 를 기대했는데 「%s」' % (i, stage, c['stage'])
    if classify_text(d1)['who'] != '이민우' or classify_text(d1)['when'] != '2026-09-03 10:00':
        return False, '머리말 작성자 · 시각을 못 읽음'
    # 칸은 넷. 「가설」 은 머리말이든 제목이든 설계로 간다 (팀장 2026-09-04).
    if STAGES != ['진단', '설계', '레시피', '결과']:
        return False, '칸이 넷(진단 · 설계 · 레시피 · 결과)이 아니다: %s' % STAGES
    d6 = '# 구덩이 메모' + n + '> 단계: 가설' + n + '#68 에 붙는다'
    if classify_text(d6)['stage'] != '설계':
        return False, '「단계: 가설」 을 설계로 안 보냄: 「%s」' % classify_text(d6)['stage']
    if stage_of('구덩이 가설: 왜 못 오르나') != '설계':
        return False, '제목의 「가설」 을 설계로 안 보냄'
    if stage_of(comment_title('## 분류 변경 · `rails` 는 낙상형이 아니다')) != '진단':
        return False, '분류 변경 코멘트가 진단으로 안 감'
    # 팀장 2026-09-04 확정: 「조건이 바뀌었다 · 재측정 대기」 는 진단이다.
    # 그 코멘트가 스스로 숫자를 무르므로(재측정 대기) 결과 칸에 두면 화면이
    # 코멘트가 취소한 결론을 주장하게 된다. 조건이 바뀌어도 남는 것은
    # 실패형 판정과 물리 관문, 곧 진단이다.
    if stage_of(comment_title('## 조건이 바뀌었다 · 재측정 대기 (팀장 확정)')) != '진단':
        return False, '「조건이 바뀌었다 · 재측정 대기」 가 진단으로 안 감'
    if stage_of(comment_title('## 오늘 회의 메모')) != '':
        return False, '단계 낱말 없는 코멘트를 어딘가에 넣음'
    # 코멘트도 문서와 같은 머리말 규칙을 쓴다. 머리말이 제목을 이긴다.
    if comment_stage('## 진단 요약' + n + '> 단계: 레시피' + n + '본문') != '레시피':
        return False, '코멘트 머리말 «단계:» 가 제목을 못 이김'
    if comment_stage('## 그냥 메모') != '':
        return False, '머리말도 낱말도 없는 코멘트를 어딘가에 넣음'
    # UTC -> KST. 문서 시각과 같은 시간대여야 선후가 바로 보인다.
    if gh_when('2026-09-02T04:30:22Z') != '2026-09-02 13:30':
        return False, '코멘트 시각을 KST 로 못 맞춤: %s' % gh_when('2026-09-02T04:30:22Z')
    if gh_when('') != '':
        return False, '빈 시각을 뭔가로 만듦'
    # 승격된 문서는 한 번만. docs/ 의 «출처» 가 가리키는 inbox 원본을 뺀다.
    dd = dedupe([{'rel': 'inbox/oh/a.md', 'src': []},
                 {'rel': 'docs/guides/a.md', 'src': ['inbox/oh/a.md']},
                 {'rel': 'inbox/oh/b.md', 'src': []}])
    if [d['rel'] for d in dd] != ['docs/guides/a.md', 'inbox/oh/b.md']:
        return False, '승격 원본을 안 뺐다: %s' % [d['rel'] for d in dd]
    if classify_text('# x' + n + '> 출처: 제출 `inbox/oh/a.md` · PR #106 로 승격')['src'] != ['inbox/oh/a.md']:
        return False, '머리말 «출처» 에서 원본 경로를 못 읽음'
    # ★ 출처 줄이 «없는» 승격. 2026-09-09 에 라이브에서 실제로 본 모양이다.
    #   제목 · 작성자 · 시각이 같으면 같은 글이고, 승격본만 남아야 한다.
    same = {'title': 'pit 진단', 'who': '이민우', 'when': '2026-09-08 13:20'}
    dd = dedupe([dict(same, rel='inbox/lee/20260908-pit진단.md', src=[]),
                 dict(same, rel='docs/research/20260908-pit-diagnosis.md', src=[])])
    if [d['rel'] for d in dd] != ['docs/research/20260908-pit-diagnosis.md']:
        return False, '출처 줄 없는 승격의 원본을 안 뺐다: %s' % [d['rel'] for d in dd]
    # 그리고 «다른 글» 은 지우면 안 된다. 제목만 같고 사람이 다르면 남는다.
    dd = dedupe([{'rel': 'inbox/lee/x.md', 'title': '진단', 'who': '이민우',
                  'when': '2026-09-08 13:20', 'src': []},
                 {'rel': 'docs/research/y.md', 'title': '진단', 'who': '맹라현',
                  'when': '2026-09-08 13:20', 'src': []}])
    if len(dd) != 2:
        return False, '사람이 다른 글을 같은 글로 봤다: %s' % [d['rel'] for d in dd]
    # 시각이 비면 셋 다 같다고 볼 근거가 없다. 지우지 않는다.
    dd = dedupe([{'rel': 'inbox/lee/x.md', 'title': '진단', 'who': '이민우',
                  'when': '', 'src': []},
                 {'rel': 'docs/research/y.md', 'title': '진단', 'who': '이민우',
                  'when': '', 'src': []}])
    if len(dd) != 2:
        return False, '시각이 빈 것을 같은 글로 봤다: %s' % [d['rel'] for d in dd]
    if stage_of('진단 결과 요약') != '진단':
        return False, '먼저 나온 낱말이 아니라 다른 것을 골랐다'
    if mention_set('색 #123456 과 #66') != {66}:
        return False, 'hex 색을 이슈로 셌다'
    if owner_of('[작업] 실패 지형 pit: 진단 -> 레시피 (이민우)', '') != '이민우':
        return False, '이슈 제목 끝 괄호에서 담당을 못 읽음'
    rows = parse_csv('terrain,episodes,overall_success_rate,wilson_lo_pct,'
                     'wilson_hi_pct,survival_rate,progress_success_rate,'
                     'tracking_success_rate,direction_success_rate,'
                     'mean_forward_progress_m,mean_lateral_drift_m,'
                     'mean_peak_lateral_drift_m' + n +
                     'pit,100,0.03,1.0,8.5,0.97,0.15,0.03,1.0,1.5687,0.1757,0.2106')
    if rows.get('pit') != {'success': 3, 'survival': 97, 'progress': 1.5687, 'n': 100}:
        return False, 'CSV 를 잘못 읽음: %s' % rows.get('pit')
    # ★ 2026-09-14. 정본 CSV 는 열 구성이 다르다 (wilson 열이 없고 뒤에 여섯이 는다).
    #   읽는 자리를 옮겼으니 «그 모양» 으로도 시험한다. 옛 모양만 시험하면
    #   정본에서 열 이름이 바뀌어도 여기서는 통과한다.
    rows = parse_csv('terrain,episodes,overall_success_rate,survival_rate,'
                     'progress_success_rate,tracking_success_rate,'
                     'direction_success_rate,mean_forward_progress_m,'
                     'mean_lateral_drift_m,mean_velocity_mae_mps,'
                     'mean_episode_duration_s,mean_fall_time_s,'
                     'mean_reward_per_step' + n +
                     'rails,100,0.08,0.82,0.46,0.1,0.41,2.6970,0.2,0.3,5.0,1.0,0.5')
    if rows.get('rails') != {'success': 8, 'survival': 82, 'progress': 2.697,
                             'n': 100}:
        return False, '정본 CSV 모양을 잘못 읽음: %s' % rows.get('rails')
    # 실제 정본 파일이 그 자리에 있고 그 열을 갖고 있는가 (경로만 바꾸고
    # 파일이 없으면 보드가 조용히 빈다)
    import docs_pages as _dp
    for _lab in _dp.LAB_CANDIDATES:
        _p = os.path.join(_lab, CSV_REL)
        if os.path.isfile(_p):
            _r = parse_csv(io.open(_p, encoding='utf-8').read())
            if 'rails' not in _r:
                return False, '정본 CSV 에 rails 가 없다: %s' % _p
            break
    else:
        return False, '정본 CSV 를 못 찾았다: %s' % CSV_REL
    cards = [{'filled': 0, 'meas': {'progress': 0.9}},
             {'filled': 2, 'meas': {'progress': 0.5}},
             {'filled': 0, 'meas': {'progress': 1.5}},
             {'filled': 0, 'meas': None}]
    got = [(c['filled'], (c['meas'] or {}).get('progress')) for c in order(cards)]
    if got != [(2, 0.5), (0, 1.5), (0, 0.9), (0, None)]:
        return False, '정렬이 틀렸다: %s' % got
    return True, ''


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ok, why = kat()
    print('자기시험 %s%s' % ('통과' if ok else '실패', '' if ok else ': ' + why))
    if ok and len(sys.argv) > 1:
        import docs_pages
        import mdlinks
        lab = next(x for x in docs_pages.LAB_CANDIDATES
                   if os.path.isdir(os.path.join(x, 'docs')))
        mdlinks.build(lab)
        cards, common, notes = build_cards(lab)
        for c in cards:
            print('#%d %-15s %-6s %s  칸 %d  실측 %s' % (
                c['no'], c['key'], c['owner'], c['mode'], c['filled'], c['meas']))
            for s in STAGES:
                for it in c['cells'][s]:
                    print('    [%s] %s · %s · %s' % (s, it['kind'], it['title'][:50], it['href'][:70]))
            for it in c['loose']:
                print('    [미분류] %s · %s · %s' % (it['kind'], it['title'][:50], it['href'][:70]))
        for d in common:
            print('공통: %s · %s' % (d['title'][:50], d['href']))
        for w in notes:
            print('경고: ' + w)
    sys.exit(0 if ok else 1)
