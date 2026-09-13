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


def check_functions():
    """배정이 빠진 문서를 찾는다. **빠지면 실패한다.**

    새 연구 문서를 올렸는데 입구를 안 정하면 허브에서 «어느 서랍에도»
    안 들어간다. 조용히 사라지는데 아무도 모른다. 그래서 센다.
    """
    docs = set(research_docs()) - DROPPED
    miss = sorted(docs - set(FUNCTION))
    ghost = sorted(k for k in FUNCTION
                   if k not in docs and not os.path.isfile(
                       os.path.join(LAB, 'docs', 'decisions', k + '.md')))
    return miss, ghost


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
        'function': dict(FUNCTION),
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
    print('  입구 %d개 · 배정 %d개 · 누락 0' % (len(GROUPS), len(FUNCTION)))
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
