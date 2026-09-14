# -*- coding: utf-8 -*-
"""흩어진 «사람의 판단» 을 원장 하나로 모은다.

    docs/ops/doc-graph-overrides.json   판단 56건 + 근거 56건
    web/gallery 의 release.json         배포 한 줄 소개와 주의
    web/_build/terrain5.py 의 상수       지형 이름 · 실패형 · 담당 · 단서 · 이름표
    web/_build/terrain5.py 의 CSV_REL    보드가 읽는 실측 한 줄
        ->  docs/ops/research-catalog.json

**왜 모으나.** 같은 성격의 판단이 네 군데에 흩어져 있어서, 한 곳을 고치면
나머지가 조용히 낡는다. 2026-09-13 에 보드가 09-03 자료를 읽고 있는 것을
발견한 것이 그 예다. 코드에 박힌 값은 고칠 때 코드를 고쳐야 한다.

**무엇을 안 옮기나.** 제목 · 요약 · 작성자 · 작성 시각 · 본문 상태는 **원본이
정본**이다. 원장에는 «사람이 내린 판단» 과 «그 근거» 만 둔다. 원본에서 읽을
수 있는 것을 베껴 두면 그 사본이 반드시 낡는다.

**완료 조건은 왕복이다.** 원장에서 옛 모양을 다시 만들어 원본과 바이트로
같아야 한다. 그래야 「옮기면서 흘렸다」가 없다. `--verify` 가 그것을 한다.
"""
import argparse
import ast
import re
import csv
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)

OVERRIDES = os.path.join(LAB, 'docs', 'ops', 'doc-graph-overrides.json')
TERRAIN5 = os.path.join(LAB, 'web', '_build', 'terrain5.py')
OUT = os.path.join(LAB, 'docs', 'ops', 'research-catalog.json')

# 갤러리 원장은 지금 **배포본에만** 있다. `gallery_versions.py` 가 site 로
# 직접 쓰기 때문이다. 그래서 빌드가 「생성 목록에 없음」으로 보고 지운다
# (2026-09-13 에 실제로 report-v1.html 과 함께 사라졌다).
# 원장으로 옮기는 것이 그 고리를 끊는 일이므로, 지금은 거기서 읽어 온다.
GALLERY = os.environ.get('FOOTHOLD_GALLERY') or os.path.abspath(
    os.path.join(LAB, '..', 'foothold-site', 'gallery'))

SCHEMA = 'foothold-research-catalog/1'


# ── 읽기 ────────────────────────────────────────────────────────────

# ── 여섯 입구 ───────────────────────────────────────────────────────
#
# 「이런 글은 어디서 찾지」의 답이다. 기존 `purpose`(본PoC · PoC시험 …)는
# **그대로 둔다** · 다른 소비자가 읽는다. 이것은 «독자가 찾는 말» 로 만든
# 별도 축이고, 설계 문서 4절의 배정을 그대로 옮긴다.
GROUPS = [
    ('protocol', '평가 기준·재현', '어떻게 재고 어떻게 다시 돌리나'),
    ('result', '결과 보고', '돌려 보니 몇 %가 나왔나'),
    ('diagnosis', '진단·분석', '왜 실패하나'),
    ('plan', '계획·결정', '무엇을 고르고 버렸나'),
    ('tooling', '도구·운영', 'Isaac · ROS2 · 클라우드'),
    ('survey', '조사·비교', '남들은 어떻게 했나'),
]

# 문서 이름(확장자 뺀 것) -> 입구. 설계 4절 표 그대로.
FUNCTION = {
    'benchmark-repro-protocol': 'protocol',
    'benchmark-setup-lim': 'protocol',
    '20260909-eval-harness-diagram': 'protocol',
    '20260911-eval-protocol-v2': 'protocol',

    'training-benchmarks': 'result',
    'visual-evidence': 'result',
    'render-benchmarks': 'result',
    '20260903-default-1500iter-terrain-analysis': 'result',
    'NVIDIA공식체크포인트_속도단차교차평가분석': 'result',
    'pretrained-vs-model99-7terrain': 'result',
    'generalization-benchmark-10-terrains': 'result',

    '20260908-success-criteria-anatomy': 'diagnosis',
    '20260903-render-blackframe': 'diagnosis',
    '20260906-rails-speed-tracking-diagnosis': 'diagnosis',
    '20260907-go2-joint-limits': 'diagnosis',
    '20260908-pit-diagnosis': 'diagnosis',
    '20260909-head-contact-observation': 'diagnosis',
    'flat-straight-baseline-10m': 'diagnosis',
    'rails-diagnosis': 'diagnosis',

    'compute-resources': 'plan',
    'terrain-finetune-plan': 'plan',
    '20260903-rails-isaac-sweep-design': 'plan',
    'architecture-decision': 'plan',
    'terrain-rl-study-plan-0818': 'plan',
    '20260829-research-hub-taxonomy': 'plan',

    'terrain-guide-isaaclab': 'tooling',
    'runpod-team-ops': 'tooling',
    'omniverse-stack': 'tooling',
    'ros2-isaacsim-integration': 'tooling',
    'go2-rough-training': 'tooling',

    '20260908-go2-spec-sim-vs-real': 'survey',
    'nvidia-curriculum-alignment': 'survey',
    'role-map-careers': 'survey',
    'go2-pretrained-policies': 'survey',
    'cloud-gpu-options': 'survey',
    '20260904-rail-reward-literature': 'survey',
    '발보상-시간아니고높이아님': 'survey',
    '직진성-외부표준': 'survey',
    'robogauge-observation-mapping': 'survey',
}


DROPPED = {'rough-terrain-study-plan'}      # 상태가 «폐기» · 허브에 안 낸다


def resolved_functions():
    """문서 전수의 입구를 «정해서» 돌려준다. 손 배정 + 자동 규칙.

    자동 규칙(`door_of`)이 먼저 일하고 FUNCTION 은 그것이 틀렸을 때만
    끼어든다. 그래서 새 문서를 올려도 사람이 코드를 고칠 일이 없다.
    """
    out, auto = {}, []
    d = os.path.join(LAB, 'docs', 'research')
    for stem in research_docs():
        if stem in DROPPED:
            continue
        p = os.path.join(d, stem + '.md')
        try:
            txt = io.open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            txt = ''
        key = door_of(p, txt)
        if key:
            out[stem] = key
            if stem not in FUNCTION:
                auto.append((stem, key))
    # 연구 폴더 밖(결정 문서 등)에 배정된 것도 그대로 싣는다
    for stem, key in FUNCTION.items():
        out.setdefault(stem, key)
    return out, auto


def check_functions():
    """입구가 «끝내» 안 정해진 문서를 찾는다. **있으면 실패한다.**

    ★ 2026-09-14 에 뜻이 바뀌었다. 전에는 FUNCTION 에 손으로 안 적힌 것을
      전부 실패로 셌다. 그러면 팀원이 문서를 올릴 때마다 빌드가 서고 내가
      코드를 고쳐야 한다. 그건 자동화가 아니라 사람을 관문으로 쓴 것이다.

      이제는 자동 규칙이 먼저 정하고, 그것도 못 정한 것만 센다. 못 정하는
      경우는 머리 여섯 줄의 «분류:» 가 없고 제목에도 단서가 없을 때다.
      그때는 문서를 고치는 것이 맞다(`AGENTS.md` 문서 표준).
    """
    docs = set(research_docs()) - DROPPED
    got, _auto = resolved_functions()
    miss = sorted(d for d in docs if not got.get(d))
    ghost = sorted(k for k in FUNCTION
                   if k not in docs and not os.path.isfile(
                       os.path.join(LAB, 'docs', 'decisions', k + '.md')))
    return miss, ghost


# 분류(머리 여섯 줄의 «분류:») -> 입구. 새 문서가 올라오면 이것으로 «저절로»
# 정해진다. FUNCTION 에 손으로 적는 것은 **이 자동 규칙이 틀렸을 때만** 이다.
#
# ★ 2026-09-14. 이것이 없으면 팀원이 문서를 올릴 때마다 빌드가 서고 사람이
#   코드를 고쳐야 했다. 그건 자동화가 아니다. 시험으로 확인했다 ·
#   새 문서 하나를 넣자 「배정 없음」으로 관문이 섰다.
KIND_DOOR = {
    '실험': 'result',
    '리서치': 'survey',
    '조사': 'survey',
    '계획': 'plan',
    '결정': 'plan',
    '가이드': 'protocol',
    '운영': 'tooling',
    '현장': 'diagnosis',
    '회의록': 'plan',
}

# 제목·요지에 이 말이 있으면 그 입구가 «분류보다» 먼저다. 진단 문서가
# 「분류: 실험」으로 올라오는 일이 잦다.
TITLE_DOOR = [
    ('diagnosis', ('진단', '왜 실패', '원인', '분석')),
    ('protocol', ('프로토콜', '재현', '평가 기준', '하네스')),
    ('plan', ('계획', '설계', '로드맵')),
    ('tooling', ('설치', '구축', '환경', '운영')),
]


def door_of(path, text):
    """문서 하나의 입구를 정한다. 우선순위가 있다.

      1. 머리말의 «입구:» 선언        사람이 정한 것이 언제나 이긴다
      2. FUNCTION 손 배정             자동이 틀렸을 때 바로잡는 자리
      3. 제목·요지의 낱말
      4. 머리말의 «분류:»
      5. 그래도 모르면 '' (관문이 잡는다)
    """
    head = text[:1200]
    m = re.search(r'^>\s*입구:\s*([a-z]+)\s*$', head, re.M)
    if m and m.group(1) in {g[0] for g in GROUPS}:
        return m.group(1)

    stem = os.path.splitext(os.path.basename(path))[0]
    if stem in FUNCTION:
        return FUNCTION[stem]

    title = ''
    h1 = re.search(r'^#\s+(.+)$', head, re.M)
    if h1:
        title += h1.group(1)
    gist = re.search(r'^>\s*요지:\s*(.+)$', head, re.M)
    if gist:
        title += ' ' + gist.group(1)
    for key, words in TITLE_DOOR:
        if any(w in title for w in words):
            return key

    kind = re.search(r'^>\s*분류:\s*(\S+)', head, re.M)
    if kind:
        return KIND_DOOR.get(kind.group(1), '')
    return ''


def _door_selftest():
    """알려진 답으로 배정 규칙을 시험한다 (원칙 1).

    이 규칙은 정규식과 우선순위로 되어 있어 **조용히** 틀린다. 실제로
    단어 경계 기호가 제어문자로 박혀 규칙 하나가 한 번도 안 돈 적이 있다.
    그래서 쓰기 전에 내가 답을 아는 입력으로 한 번 돌린다.
    """
    def d(*lines):
        return chr(10).join(lines) + chr(10)

    cases = [
        ('a.md', d('# 왜 pit 에서 실패하나', '', '> 분류: 실험',
                   '> 요지: 원인을 본다'),
         'diagnosis', '제목이 분류를 이긴다'),
        ('b.md', d('# 클라우드 GPU 비교', '', '> 분류: 리서치',
                   '> 요지: 값과 성능'),
         'survey', '분류로 정한다'),
        ('c.md', d('# 무엇', '', '> 분류: 실험', '> 입구: tooling',
                   '> 요지: 아무거나'),
         'tooling', '문서 선언이 전부를 이긴다'),
        ('d.md', d('# 학습 성능 실측', '', '> 분류: 실험',
                   '> 요지: 몇 %가 나왔나'),
         'result', '분류 실험은 실측'),
        ('e.md', d('# 아무말', '', '> 요지: 단서 없음'),
         '', '못 정하면 빈 값 · 관문이 잡는다'),
    ]
    for name, txt, want, why in cases:
        got = door_of(name, txt)
        if got != want:
            return False, '%s -> %s (기대 %s · %s)' % (
                name, got or '없음', want or '없음', why)
    return True, '%d칸' % len(cases)

def research_docs():
    """docs/research 의 문서 이름 전수. 배정이 빠진 것을 찾으려고 센다."""
    d = os.path.join(LAB, 'docs', 'research')
    if not os.path.isdir(d):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(d)
                  if f.endswith('.md'))


def read_overrides():
    d = json.load(io.open(OVERRIDES, encoding='utf-8'))
    return d, d['docs']


def read_terrain_consts():
    """terrain5.py 를 «실행하지 않고» 상수만 읽는다.

    import 하면 그 모듈이 CSV 를 찾고 GitHub 를 부르려 든다. 원장을 만드는
    일에 그 부작용이 끼면 안 된다. 그래서 구문 나무에서 값만 꺼낸다.
    """
    tree = ast.parse(io.open(TERRAIN5, encoding='utf-8').read())
    want = {'TERRAINS', 'GH_NAME', 'STAGES', 'CSV_REL'}
    out = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id in want:
                try:
                    out[t.id] = ast.literal_eval(node.value)
                except ValueError:
                    pass                      # CSV_REL 은 os.path.join 이라 못 읽는다

    if 'CSV_REL' not in out:
        out['CSV_REL'] = ('sim/eval/results/20260903-rough10-1.0mps/'
                          'summary-thr1.5.csv')
    return out


RESULTS = os.path.join(LAB, 'sim', 'eval', 'results')

# 배포 판 -> 그 판을 낸 실측 폴더. 판이 늘면 여기 한 줄 늘린다.
RUN_FOLDER = {'v1': '20260911-v3-fixedscan'}


def _rates(run_dir, model, group, speed, diff):
    """한 조건의 지형별 성공률 %. 없으면 빈 것."""
    p = os.path.join(run_dir, model, group, 'runs',
                     '%s-d%s' % (speed, diff), 'generalization_summary.csv')
    if not os.path.isfile(p):
        return {}
    out = {}
    for r in csv.DictReader(io.open(p, encoding='utf-8')):
        out[r['terrain']] = float(r['overall_success_rate']) * 100.0
    return out


def _folder_by_sha(run_dir, speed, diff):
    """실측 폴더 이름 -> 그 폴더가 쓴 체크포인트 해시.

    **이름으로 맞추지 않는다.** 배포 원장은 정책을 `foothold-v1` 이라 부르고
    실측 폴더는 `B` 다. 이름을 손으로 이어 두면 다음 판에서 어긋난다.
    해시는 그 폴더가 «실제로 무엇을 돌렸는지» 이므로 틀릴 수 없다.
    """
    out = {}
    if not os.path.isdir(run_dir):
        return out
    for m in sorted(os.listdir(run_dir)):
        for group in ('unseen10', 'rough6'):
            p = os.path.join(run_dir, m, group, 'runs',
                             '%s-d%s' % (speed, diff), 'run_manifest.json')
            if not os.path.isfile(p):
                continue
            try:
                sha = json.load(io.open(p, encoding='utf-8')).get('policy_sha256')
            except (OSError, ValueError):
                sha = None
            if sha:
                out[sha] = m
            break
    return out


def measure_release(folder, main_model, difficulty, model_shas=None):
    """첫 화면에 낼 수치를 **실측에서 계산한다.**

    손으로 적지 않는다. 손으로 적으면 다음 배포에 반드시 낡고, 낡아도
    아무도 모른다. 원자료가 없으면 그 칸을 **비운다** (0 을 넣지 않는다).

    `14,400` 은 «어떤 성공률의 분모» 가 아니다. 난이도 0.5 성적표 전체의
    표본 수다. 한 칸의 분모는 100판이다. 그렇게 이름 붙인다.
    """
    run = os.path.join(RESULTS, folder)
    if not os.path.isdir(run):
        return None

    speed, diff = 'v1.0', str(difficulty or '0.5')
    out = {'speed_mps': 1.0, 'difficulty': float(diff), 'episodes_per_cell': 100}

    # 배포 원장의 모델 이름을 실측 폴더로 «해시로» 옮긴다.
    by_sha = _folder_by_sha(run, speed, diff)
    main_dir = (by_sha.get((model_shas or {}).get(main_model) or '')
                or (main_model if os.path.isdir(os.path.join(run, main_model))
                    else None))
    base_dir = by_sha.get((model_shas or {}).get('baseline') or '') or 'baseline'
    if not main_dir:
        print('  [!] 배포 모델 «%s» 의 실측 폴더를 못 찾았습니다. 첫 화면 수치를 비웁니다'
              % main_model)
        return out

    for group, key in (('unseen10', 'unseen'), ('rough6', 'known')):
        base = _rates(run, base_dir, group, speed, diff)
        main = _rates(run, main_dir, group, speed, diff)
        if not base or not main:
            continue
        ts = sorted(base)
        mb = sum(base[t] for t in ts) / len(ts)
        mm = sum(main.get(t, 0.0) for t in ts) / len(ts)
        out[key] = {
            'terrains': len(ts),
            'baseline_pct': round(mb, 1),
            'main_pct': round(mm, 1),
            'delta_pp': round(mm - mb, 1),
            'at_or_above': sum(1 for t in ts if main.get(t, 0.0) >= base[t]),
        }

    # 성적표 전체 표본. 난이도 0.5 의 모든 모델·속도·지형을 센다.
    total = 0
    for model in sorted(os.listdir(run)):
        runs = os.path.join(run, model)
        for group in ('unseen10', 'rough6'):
            d = os.path.join(runs, group, 'runs')
            if not os.path.isdir(d):
                continue
            for r in os.listdir(d):
                if not r.endswith('-d%s' % diff):
                    continue
                p = os.path.join(d, r, 'generalization_summary.csv')
                if os.path.isfile(p):
                    for row in csv.DictReader(io.open(p, encoding='utf-8')):
                        total += int(row['episodes'])
    if total:
        out['scorecard_episodes'] = total
    return out


def read_releases():
    """gallery/<판>/release.json 과 versions.json 을 읽는다."""
    out = []
    vpath = os.path.join(GALLERY, 'versions.json')

    if not os.path.isfile(vpath):
        return out

    index = json.load(io.open(vpath, encoding='utf-8'))

    for v in index.get('versions', []):
        folder = v.get('folder') or v.get('version')
        rel = {
            'id': v.get('version'),
            'folder': folder,
            'main_model': v.get('main_model'),
            'difficulty': v.get('difficulty'),
            'clips': v.get('clips'),
            'evaluations': v.get('evaluations'),
            'terrains': v.get('terrains'),
            'evaluated_at': v.get('evaluated_at'),
        }
        # 첫 화면 수치는 원자료에서 «계산한다». 사람이 안 적는다.
        m = measure_release(RUN_FOLDER.get(v.get('version'), ''),
                            v.get('main_model') or '', v.get('difficulty'),
                            v.get('models') or {})
        if m:
            rel['summary'] = m

        rpath = os.path.join(GALLERY, folder, 'release.json')

        if os.path.isfile(rpath):
            r = json.load(io.open(rpath, encoding='utf-8'))
            for k in ('headline', 'report', 'note'):
                if r.get(k):
                    rel[k] = r[k]
        out.append(rel)
    return out


# ── 쓰기 ────────────────────────────────────────────────────────────

def build():
    raw, docs = read_overrides()
    t = read_terrain_consts()

    documents = {}
    for path in sorted(docs):
        v = docs[path]
        rec = {'source': {'type': 'md', 'path': path}}

        # 옛 purpose 는 «그대로» 둔다. 새 분류(function)로 덮어쓰지 않는다.
        # docs_pages._front_picks() 등 다른 소비자가 이 값을 읽는다.
        rec['legacy_purpose'] = {'value': v['purpose'],
                                 'reason': v['purpose_reason']}
        rec['web_worthy'] = {'value': v['web_worthy'],
                             'reason': v['web_worthy_reason']}

        if 'areas' in v:
            rec['areas_override'] = {'value': v['areas'],
                                     'reason': v['areas_reason']}
        documents[path] = rec

    terrain_meta = []
    for issue, key, name, fail, owner, hint in t.get('TERRAINS', []):
        row = {'key': key, 'issue': issue, 'display': name,
               'failure_kind': fail, 'owner_fallback': owner}
        if hint:
            row['hint'] = hint
        terrain_meta.append(row)

    return {
        'schema': SCHEMA,
        '_설명': ('사람이 내린 판단과 그 근거를 모은 원장. 제목·요약·작성자·'
                  '작성 시각은 여기 두지 않는다. 원본이 정본이다.'),
        '_규칙': raw.get('_규칙', ''),
        '_규칙2': raw.get('_규칙2', ''),
        'documents': documents,
        'terrain_meta': terrain_meta,
        'stages': t.get('STAGES', []),
        'gh_names': t.get('GH_NAME', {}),
        'measurements': [{
            'id': 'board-legacy-20260903',
            'csv': t['CSV_REL'].replace(os.sep, '/'),
            'note': ('지형 보드가 지금 읽는 자료. 기준 정책(NVIDIA 공식 '
                     '사전학습본) · 1.0 m/s · 지형마다 100판. 난이도 인자가 '
                     '없고 빗나간 광선 처리도 manifest 에 없다. 방향 임계 '
                     '1.5 m 로 «재채점한» 표라 현재 규격(통과선에서 0.75 m)과 '
                     '같은 자로 잰 것이 아니다.'),
        }],
        'groups': [{'key': k, 'name': n, 'hint': h}
                   for k, n, h in GROUPS],
        'function': resolved_functions()[0],
        'releases': read_releases(),
    }


def write(obj, path):
    io.open(path, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(obj, ensure_ascii=False, indent=1) + '\n')


# ── 왕복 검증 ───────────────────────────────────────────────────────

def to_overrides(cat):
    """원장 -> 옛 overrides 모양. 이것이 원본과 같아야 한다."""
    docs = {}
    for path, rec in cat['documents'].items():
        v = {'purpose': rec['legacy_purpose']['value'],
             'purpose_reason': rec['legacy_purpose']['reason'],
             'web_worthy': rec['web_worthy']['value'],
             'web_worthy_reason': rec['web_worthy']['reason']}
        if 'areas_override' in rec:
            v['areas'] = rec['areas_override']['value']
            v['areas_reason'] = rec['areas_override']['reason']
        docs[path] = v
    return docs


def verify(cat):
    """원본과 왕복본을 «값으로» 댄다. 키 순서가 아니라 내용이 기준이다."""
    _, original = read_overrides()
    back = to_overrides(cat)
    bad = []

    miss = set(original) - set(back)
    extra = set(back) - set(original)
    for p in sorted(miss):
        bad.append('원장에 없다: ' + p)
    for p in sorted(extra):
        bad.append('원본에 없다: ' + p)

    for p in sorted(set(original) & set(back)):
        a, b = original[p], back[p]
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                bad.append('%s 의 «%s» 가 다르다' % (p, k))

    n_reason = sum(1 for r in cat['documents'].values()
                   if r['legacy_purpose']['reason'] and r['web_worthy']['reason'])
    return bad, len(original), n_reason


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='원장 파일을 쓴다')
    a = ap.parse_args()

    cat = build()
    bad, n, n_reason = verify(cat)

    miss, ghost = check_functions()
    if miss or ghost:
        print('  [!] 입구 배정이 안 맞습니다')
        for m in miss:
            print('      배정 없음: %s' % m)
        for g in ghost:
            print('      문서 없음: %s' % g)
        raise SystemExit(1)

    print('  문서 판단 %d건 · 근거가 둘 다 있는 것 %d건' % (n, n_reason))
    ok, why = _door_selftest()
    if not ok:
        print('  [!] 입구 배정 자기시험 실패: %s' % why)
        return False
    got_fn, auto_fn = resolved_functions()
    print('  입구 %d개 · 배정 %d개(손 %d · 자동 %d) · 누락 0 · 자기시험 %s'
          % (len(GROUPS), len(got_fn), len(got_fn) - len(auto_fn),
             len(auto_fn), why))
    print('  지형 %d · 단계 %d · 이름표 %d · 실측 %d · 배포 %d'
          % (len(cat['terrain_meta']), len(cat['stages']),
             len(cat['gh_names']), len(cat['measurements']),
             len(cat['releases'])))

    if bad:
        print('\n  [!] 왕복이 안 맞습니다 %d건' % len(bad))
        for b in bad[:20]:
            print('      ' + b)
        raise SystemExit(1)

    print('  왕복 일치 · 판단도 근거도 하나도 안 흘렸습니다')

    # 조용한 실패를 막는다. 비어 있으면 성공이라 하지 않는다.
    if n < 50 or n_reason < 50 or not cat['terrain_meta'] or not cat['releases']:
        raise SystemExit('  [!] 원장이 비어 있습니다. 성공으로 안 읽습니다')

    if a.write:
        write(cat, OUT)
        print('  씀: %s (%.1f KB)' % (os.path.relpath(OUT, LAB),
                                      os.path.getsize(OUT) / 1024.0))
    else:
        print('  (--write 를 주면 씁니다)')


if __name__ == '__main__':
    main()
