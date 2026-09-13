# -*- coding: utf-8 -*-
"""문서 관계표를 매 빌드마다 다시 만든다.

★ 왜 (2026-08-29)

  팀장이 물었다. 「온톨로지 문서도 지금 문서 기준으로 되어 있잖아.
  이 문서도 앞으로 지속적으로 관계 등 업데이트가 자동으로 되어야지」

  맞다. `doc-graph.json` 은 8/28 **한 시점의 사진**이었다. 새 문서가 들어오면
  그 사진에 안 찍힌다. 오늘 하루 걷어낸 「손 관리 마스터」와 같은 부류다.
  누수 방지 장치가 스스로 누수된 원장(`ledgercheck`)과 같은 이야기다.

  그래서 **매 빌드마다 문서를 다시 훑어 그린다.**

무엇이 자동이고 무엇이 사람인가

  자동으로 나오는 것 (문서를 읽으면 나온다)
    kind      머리의 `분류:` 줄. 팀 규칙상 이미 적는다
    areas     `areas.py` 가 본문에서 판정. 정본은 ROLES.md 8갈래 표
    parents   본문의 md 링크. 「무엇을 근거로 삼나」
    children  parents 를 뒤집은 것
    stale     `stalecheck` 어휘로 훑는다

  규칙으로 «제안» 하되 사람이 이길 수 있는 것
    purpose      머리의 `근거:` 줄이 거의 결정한다 (실측: 공식->자료조사 100%,
                 본인·팀·전사->운영 100%). **다만 `근거: 실측` 15장은 갈린다.**
                 그중 `kind=실험` 7장은 규칙으로 못 가른다. 사람이 정한다
    web_worthy   노출 가치는 판단이다. 인용 수와 낡음으로 «제안» 만 한다

  사람 판정은 `docs/ops/doc-graph-overrides.json` 에 있고 **자동보다 이긴다.**
  규칙과 사람 값이 어긋나면 조용히 덮지 않고 **어긋났다고 보고**한다.
  새 문서는 override 가 없어도 된다. 규칙이 값을 낸다.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# `근거:` 줄의 첫 낱말 -> purpose. 56장 실측에서 나온 상관이다.
#   공식 11/11 · 조선대 3/3 · 본인 8/8 · 팀 8/8 · 전사 2/2 · 음성 3/3 · 현장 2/2
BY_EVIDENCE = {
    '공식': '자료조사', '조선대': '자료조사',
    '본인': '운영', '팀': '운영', '팀원': '운영', '팀장': '운영',
    '전사': '운영', '음성': '운영', '현장': '운영', 'MOSS': '운영',
    '코드': 'PoC시험',
}
# `근거: 실측` 이면서 `분류:` 가 실험이 아니면 운영이다 (8/8 맞음)
MEASURED_NOT_EXPERIMENT = '운영'

SKIP_DIRS = ('.git', 'inbox', 'node_modules')


def _walk(root):
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in sorted(fs):
            if f.endswith('.md'):
                yield os.path.join(d, f)


def _head(text, name):
    m = re.search(r'^>\s*%s\s*:\s*(.+)$' % name, text, re.M)
    return m.group(1).strip() if m else ''


def _issues(text):
    """머리의 «> 이슈: #94» 에서 번호만. 온톨로지가 «이 문서의 뿌리» 를 안다 (#111).

    팀장 9/1: 「온톨로지 문서가 각 문서간의 관계를 파악하고 있는 것이니까
      거기에 어떤 이슈로 만들어진 문서인지 기재되어 있으면 근거로써 좋겠다」
    관계표가 지금까지 «문서 -> 문서» 만 봤다. 이슈를 담으면 «논의 -> 문서» 가 선다.
    """
    m = re.search(r'^>\s*이슈\s*:\s*(.+)$', text, re.M)
    return re.findall(r'#(\d{1,4})', m.group(1)) if m else []


def _links(text):
    """본문이 가리키는 md. 「무엇을 근거로 삼나」."""
    out = []
    for m in re.finditer(r'\]\((?!https?://)([A-Za-z0-9._/-]+\.md)', text):
        out.append(m.group(1))
    return out


def _resolve(src_rel, target, known):
    """상대 링크를 docs 기준 경로로. 못 찾으면 None."""
    base = os.path.dirname(src_rel)
    p = os.path.normpath(os.path.join(base, target)).replace(os.sep, '/')
    return p if p in known else None


def _judgements(root):
    """사람이 내린 판단을 읽는다. **원장이 먼저다.**

    2026-09-13 에 `docs/ops/research-catalog.json` 으로 모았다. 전까지는
    `doc-graph-overrides.json` 이었고, 같은 성격의 판단이 그 파일 · 배포
    `release.json` · `terrain5.py` 상수 세 군데에 흩어져 있었다. 한 곳을
    고치면 나머지가 조용히 낡는 구조였다.

    **옮기면서 아무것도 안 흘렸다는 것은 왕복으로 증명한다** (`tools/
    build_research_catalog.py --verify`). 그래서 이 함수가 돌려주는 모양은
    옛 것과 «완전히 같다». 부르는 쪽은 바뀐 줄 모른다.

    옛 파일은 아직 지우지 않았다. 다른 기기·옛 체크아웃에서 부를 수 있다.
    원장이 있으면 그쪽이 이긴다.
    """
    cat = os.path.join(root, 'ops', 'research-catalog.json')
    if os.path.isfile(cat):
        docs = json.load(io.open(cat, encoding='utf-8')).get('documents', {})
        out = {}
        for path, rec in docs.items():
            lp, ww = rec.get('legacy_purpose') or {}, rec.get('web_worthy') or {}
            v = {}
            if lp.get('value'):
                v['purpose'] = lp['value']
                v['purpose_reason'] = lp.get('reason', '')
            if ww.get('value'):
                v['web_worthy'] = ww['value']
                v['web_worthy_reason'] = ww.get('reason', '')
            ao = rec.get('areas_override')
            if ao and ao.get('value'):
                v['areas'] = ao['value']
                v['areas_reason'] = ao.get('reason', '')
            out[path] = v
        return out

    old = os.path.join(root, 'ops', 'doc-graph-overrides.json')
    if os.path.isfile(old):
        return json.load(io.open(old, encoding='utf-8')).get('docs', {})
    return {}


def build(lab):
    root = os.path.join(lab, 'docs')
    import areas
    voc = areas.vocab(lab)

    texts = {}
    for full in _walk(root):
        rel = os.path.relpath(full, root).replace(os.sep, '/')
        texts[rel] = io.open(full, encoding='utf-8', newline=None,
                             errors='replace').read()

    ov = _judgements(root)

    docs, drift, unsure = {}, [], []
    for rel, t in texts.items():
        kind = _head(t, '분류') or ''
        ev = (_head(t, '근거') or '').split()
        ev0 = ev[0] if ev else ''
        title = (re.search(r'^#\s+(.+)$', t, re.M) or [None, rel])[1]

        # purpose: 규칙 제안
        if ev0 in BY_EVIDENCE:
            auto_p = BY_EVIDENCE[ev0]
        elif ev0 == '실측':
            auto_p = None if kind == '실험' else MEASURED_NOT_EXPERIMENT
        else:
            auto_p = None

        a, _sc, why, sure = areas.judge(t, voc)
        docs[rel] = {
            'path': rel, 'title': title.strip(), 'kind': kind,
            'evidence': ev0,
            'issues': _issues(t),
            'areas': a, 'areas_sure': sure,
            'areas_why': ('근거 낱말 ' + ' '.join(why)) if a else '신호 없음',
            'purpose': auto_p, 'purpose_src': 'auto' if auto_p else '확인 필요',
            'parents': [], 'children': [],
        }
        if not sure:
            unsure.append(rel + ' (작업 영역)')

    # 참조 관계
    for rel, t in texts.items():
        for tgt in _links(t):
            r = _resolve(rel, tgt, docs)
            if r and r != rel:
                if r not in docs[rel]['parents']:
                    docs[rel]['parents'].append(r)
                if rel not in docs[r]['children']:
                    docs[r]['children'].append(rel)

    # 사람 판정이 이긴다. 어긋나면 보고한다.
    for rel, d in docs.items():
        o = ov.get(rel)
        if not o:
            if d['purpose'] is None:
                unsure.append(rel + ' (활동)')
            d['web_worthy'] = _propose_worth(d)
            d['web_worthy_src'] = 'auto'
            continue
        if o.get('purpose'):
            if d['purpose'] and d['purpose'] != o['purpose']:
                drift.append('%s: 활동 규칙=%s 사람=%s'
                             % (rel, d['purpose'], o['purpose']))
            d['purpose'] = o['purpose']
            d['purpose_src'] = 'human'
            d['purpose_reason'] = o.get('purpose_reason', '')
        # ★ 2026-08-29. 작업 영역도 사람이 이길 수 있어야 한다.
        #   영역은 «허브 묶음» 을 정하는 축인데 정정 경로가 없었다. 그래서
        #   협업 규칙이 「기록 · 발표 · 대외보고」에, 프로젝트 전체 흐름이
        #   「정책을 어떻게 학습시키나」에 앉아 있어도 고칠 방법이 없었다 (실측).
        if o.get('areas'):
            if d['areas'] and d['areas'][0] != o['areas'][0]:
                drift.append('%s: 영역 규칙=%s 사람=%s'
                             % (rel, d['areas'][0], o['areas'][0]))
            d['areas'] = o['areas']
            d['areas_sure'] = True
            d['areas_why'] = o.get('areas_reason', '사람 판정')
        if o.get('web_worthy'):
            d['web_worthy'] = o['web_worthy']
            d['web_worthy_src'] = 'human'
            d['web_worthy_reason'] = o.get('web_worthy_reason', '')
        else:
            d['web_worthy'] = _propose_worth(d)
            d['web_worthy_src'] = 'auto'

    return sorted(docs.values(), key=lambda d: d['path']), drift, unsure


def _propose_worth(d):
    """노출 가치 제안. 판단이므로 «제안» 이고 사람이 뒤집을 수 있다.

    남들이 많이 가리키는 글은 앞에 둘 값이 있다. 아무도 안 가리키고
    자기도 아무것도 안 가리키면 뒤로 간다.
    """
    n = len(d['children'])
    if n >= 4:
        return '높음'
    if n >= 1 or d['parents']:
        return '보통'
    return '낮음'


def main(lab=None, write=True):
    if lab is None:
        import docs_pages
        lab = next((p for p in docs_pages.LAB_CANDIDATES
                    if os.path.isdir(os.path.join(p, 'docs'))), None)
    if not lab:
        print('  [!] foothold-lab 을 못 찾음')
        return False

    out = os.path.join(lab, 'docs', 'ops', 'doc-graph.json')
    old = []
    if os.path.isfile(out):
        old = json.load(io.open(out, encoding='utf-8'))
    docs, drift, unsure = build(lab)

    known = {d['path'] for d in old}
    new = [d['path'] for d in docs if d['path'] not in known]
    gone = [p for p in known if p not in {d['path'] for d in docs}]

    if write:
        io.open(out, 'w', encoding='utf-8', newline=chr(10)).write(
            json.dumps(docs, ensure_ascii=False, indent=1))

    edges = sum(len(d['parents']) for d in docs)
    withi = sum(1 for d in docs if d.get('issues'))
    print('  문서 %d장 · 참조 %d개 · 새로 들어옴 %d · 빠짐 %d'
          % (len(docs), edges, len(new), len(gone)))
    print('  출처 이슈가 적힌 문서 %d / %d (#111 · 나머지는 아직 «> 이슈:» 가 없다)'
          % (withi, len(docs)))
    for p in new[:6]:
        print('     + %s' % p)
    for p in gone[:6]:
        print('     - %s' % p)
    if unsure:
        print('  확인 필요 %d건: %s' % (len(unsure), ' · '.join(unsure[:4])))
    for x in drift[:6]:
        print('  ★ %s' % x)
    if drift:
        print('    규칙과 사람 판정이 어긋납니다. 사람 값을 썼습니다.')
        print('    규칙이 맞으면 doc-graph-overrides.json 에서 그 줄을 지우십시오.')
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
