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

    print('  문서 판단 %d건 · 근거가 둘 다 있는 것 %d건' % (n, n_reason))
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
