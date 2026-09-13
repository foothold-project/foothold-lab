# -*- coding: utf-8 -*-
"""문서 페이지에 「이 글이 선 자리」를 붙인다.

★ 왜 (2026-08-29)

  온톨로지를 만들어 **참조 관계 85개**를 뽑아 놓고 **화면에 하나도 안 쓰고 있었다.**
  8/24 진단이 「구조를 생성할 메타데이터가 없다」고 했고, 이제 그 메타데이터가
  생겼는데 화면이 여전히 안 쓴다. 만들어 놓고 안 쓰는 것이 제일 아깝다.

  독자는 허브나 검색에서 **문서 하나에 곧바로 떨어진다.** 앞뒤 맥락 없이 도착한다.
  그때 필요한 것 둘이다.

    위 (parents)   이 글이 무엇을 근거로 삼았나
    아래 (children) 무엇이 이 글을 근거로 삼나

  둘 다 `doc-graph.json` 에 있고 매 빌드마다 다시 그려진다. 손 목록이 아니다.

무엇을 조심하나
  게시 안 되는 문서(폐기·web:skip)로 링크를 걸면 죽은 링크가 된다.
  `mdlinks.resolve()` 가 빈 값을 주면 **글자로만** 적는다.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

_G = None

CSS = """
.stand{border:1px solid var(--rule);border-radius:6px;
  background:var(--paper-2);padding:.7rem .9rem;margin:0 0 1.3rem;font-size:.8rem}
.stand .sh{font-size:.6rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;
  color:var(--dim);margin-bottom:.4rem}
.stand .sr{display:flex;gap:.5rem;align-items:baseline;margin:.22rem 0;flex-wrap:wrap}
.stand .sk{flex:none;font-size:.68rem;font-weight:800;color:var(--ink-3);min-width:5.6em}
.stand .sv a{color:inherit;text-decoration:none;border-bottom:1px solid var(--rule)}
.stand .sv a:hover{border-color:var(--dim);color:var(--dim)}
.stand .sv i{font-style:normal;color:var(--ink-3)}
"""


def _graph(lab):
    global _G
    if _G is not None:
        return _G
    _G = {}
    p = os.path.join(lab, 'docs', 'ops', 'doc-graph.json')
    if os.path.isfile(p):
        try:
            for d in json.load(io.open(p, encoding='utf-8')):
                _G[d['path']] = d
        except Exception:
            pass
    return _G


def _link(rel, g):
    """관계표 경로 -> 화면에 쓸 조각. 게시 안 된 것은 글자로만."""
    import mdlinks
    title = (g.get(rel) or {}).get('title') or os.path.basename(rel)[:-3]
    page = mdlinks.resolve('docs/' + rel)
    if page:
        return '<a href="%s">%s</a>' % (page, title)
    return '<i>%s</i>' % title


def block(doc_rel, lab, limit=4):
    """「이 글이 선 자리」 HTML. 관계가 없으면 빈 문자열."""
    g = _graph(lab)
    d = g.get(doc_rel)
    if not d:
        return ''
    up = [x for x in (d.get('parents') or []) if x in g][:limit]
    down = [x for x in (d.get('children') or []) if x in g][:limit]
    if not up and not down:
        return ''
    rows = []
    if up:
        rows.append('<div class="sr"><span class="sk">무엇을 근거로</span>'
                    '<span class="sv">%s</span></div>'
                    % ' · '.join(_link(x, g) for x in up))
    if down:
        n = len(d.get('children') or [])
        more = (' <i>외 %d</i>' % (n - len(down))) if n > len(down) else ''
        rows.append('<div class="sr"><span class="sk">이 글을 근거로</span>'
                    '<span class="sv">%s%s</span></div>'
                    % (' · '.join(_link(x, g) for x in down), more))
    return ('<div class="stand"><div class="sh">이 글이 선 자리</div>%s</div>'
            % ''.join(rows))


def _kat(lab):
    """★ 답을 아는 입력으로 먼저 시험한다."""
    g = _graph(lab)
    # 남들이 많이 인용하는 글은 「이 글을 근거로」가 있어야 한다
    for rel in ('REPORT.md', 'research/training-benchmarks.md'):
        if rel not in g:
            continue
        h = block(rel, lab)
        if not h:
            return False, '%s 는 관계가 있는데 빈 블록을 냈다' % rel
        if '이 글이 선 자리' not in h:
            return False, '머리글이 없다'
    # 없는 문서는 빈 문자열
    if block('없는문서.md', lab) != '':
        return False, '없는 문서에 블록을 만들었다'
    return True, ''


def main(lab=None):
    if lab is None:
        import docs_pages
        lab = next((p for p in docs_pages.LAB_CANDIDATES
                    if os.path.isdir(os.path.join(p, 'docs'))), None)
    if not lab:
        print('  [!] foothold-lab 을 못 찾음')
        return False
    ok, why = _kat(lab)
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    g = _graph(lab)
    have = sum(1 for r in g if block(r, lab))
    print('  관계가 있는 문서 %d / %d 장에 「이 글이 선 자리」를 붙입니다'
          % (have, len(g)))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(0 if main() else 1)
