# -*- coding: utf-8 -*-
"""산출물 문서(md)를 웹 페이지로 만든다.

★ 팀장 지적 (2026-08-27): 「우리가 문서화 한 것은 단순히 문서만을 남기라는 것이
  아니고 그 내용을 바탕으로 웹에 반영을 해야한다.」

  브레인스토밍·기획서·WBS 를 md 로만 써두고 웹 어디에서도 읽을 수 없는 상태였다.
  md 는 원고이고, 사람이 보는 것은 웹이고, 제출하는 것은 그 웹을 뽑은 PDF 다.
  이 단계가 그 사슬의 가운데를 잇는다.

    md (foothold-lab/deliverables) -> 웹 (deliverable-*.html) -> PDF (브라우저 인쇄)

  산출물 현황 페이지(deliverables.html)의 각 줄이 여기서 만든 페이지로 이어진다.
"""
import io
import os
import shutil
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import docs_pages
import mdpage

PREFIX = 'deliverable-'

# (lab 안 경로, 슬러그, 눈썹, 관문)
DOCS = [
    ('deliverables/plan/proposal.md', 'proposal', '기획발표 · 9월 4일'),
    ('deliverables/plan/brainstorming.md', 'brainstorming', '기획발표 · 9월 4일'),
    ('deliverables/plan/wbs-official.md', 'wbs-official', '기획발표 · 9월 4일'),
    ('deliverables/plan/roles-responsibilities.md', 'roles-responsibilities',
     '기획발표 · 9월 4일'),
    ('deliverables/plan/proposal-summary.md', 'proposal-summary', '기획발표 · 9월 4일'),
    ('deliverables/plan/proposal-deck.md', 'proposal-deck', '기획발표 · 9월 4일'),
    ('deliverables/plan/wbs.md', 'wbs', '기획발표 · 9월 4일'),
    ('deliverables/midterm/policy-metrics.md', 'policy-metrics', 'A-정책 · 9월 12일'),
    ('deliverables/midterm/generalization-report.md', 'generalization-report',
     'MVP 중간발표 · 9월 30일'),
    ('deliverables/midterm/twin-render.md', 'twin-render', 'MVP 중간발표 · 9월 30일'),
    ('deliverables/final/nav-report.md', 'nav-report', 'NAV 실기항법 · 11월 7일'),
    ('deliverables/final/final-report.md', 'final-report', 'FINAL 최종발표 · 12월 11일'),
    ('deliverables/logs/progress-log.md', 'progress-log', '진행 기록'),
    ('deliverables/logs/mentoring-log.md', 'mentoring-log', '진행 기록'),
]


def lab_root():
    for p in docs_pages.LAB_CANDIDATES:
        if os.path.isdir(os.path.join(p, 'deliverables')):
            return p
    return None


def meta_of(md):
    out = {}
    for f in ('분류', '작성', '근거', '요지', '상태'):
        m = re.search(r'^>\s*%s\s*:\s*(.+)$' % f, md, re.M)
        if m:
            out[f] = m.group(1).strip()
    return out


# 저자가 «제출본 제외» 로 감싼 구간. 운영진에 낸 PDF 에는 안 들어간 부분이다.
# 웹도 같은 것을 보여야 하므로 통째로 뺀다. 마커만 지우고 내용을 남기면
# 저자가 빼기로 한 것이 공개 사이트에 나간다. 2026-09-04 에 실제로 그럴 뻔했다.
# 산출물 md 는 PDF 를 염두에 두고 쓰여서 원시 HTML 이 섞인다. 웹으로 옮길 때
# 셋을 손본다. 그냥 두면 mdpage 가 전부 이스케이프해서 태그가 «글자로» 보인다.
#   <img src=..>            그림 문법으로 바꾼다. 그러면 그림 복사도 같이 걸린다
#   <div break-before>      PDF 쪽 나눔이다. 웹에는 뜻이 없다
#   <br>                    렌더 뒤에 되살린다 (mdpage 는 두 칸 개행을 안 받는다)
_IMGTAG = re.compile(r'<img\s+[^>]*?src="([^"]+)"[^>]*?>')
_ALT = re.compile(r'alt="([^"]*)"')
_PAGEBREAK = re.compile(r'<div[^>]*break-before[^>]*>\s*|</div>\s*')


def _webify(md):
    def one(m):
        alt = _ALT.search(m.group(0))
        return '![%s](%s)' % (alt.group(1) if alt else '', m.group(1))
    md = _IMGTAG.sub(one, md)
    return _PAGEBREAK.sub('', md)


_CUT = re.compile(r'<!--\s*제출본 제외\s*-->.*?<!--\s*/제출본 제외\s*-->', re.S)
_FIG = re.compile(r'!\[[^\]]*\]\((assets/[^)\s]+)\)')


def _copy_figs(md, srcdir):
    """문서가 참조하는 그림을 배포 폴더로 옮긴다.

    산출물 md 는 `assets/architecture.svg` 처럼 제 폴더 기준으로 그림을 건다.
    배포본에서 그 주소는 사이트 루트 기준이 되므로 파일이 그 자리에 있어야 한다.
    복사하지 않으면 관문 [2.5] 가 「가리키는데 파일이 없음」으로 배포를 세운다.
    2026-09-04: 본 기획서를 목록에 넣자 실제로 그 자리에서 멈췄다.
    """
    dst_dir = os.path.join(VAULT, 'assets')
    # ★ 2026-09-14. 그림마다 테마 짝(`x.dark.svg`)이 있다. 그것도 함께 옮긴다.
    #   안 옮기면 사이트가 다크로 갔을 때 브라우저가 없는 파일을 부른다.
    #   (이 함수가 사본만 보고 원본을 안 봐서, 내가 web/assets 를 고쳐 놓고
    #    빌드가 원본으로 덮어쓰는 것을 한 번 겪었다. 원본은 여기 srcdir 이다)
    want = set()
    for rel in set(_FIG.findall(md)):
        want.add(rel)
        if rel.endswith('.svg') and not rel.endswith('.dark.svg'):
            dk = rel[:-4] + '.dark.svg'
            if os.path.isfile(os.path.join(srcdir, dk.replace('/', os.sep))):
                want.add(dk)
    for rel in want:
        src = os.path.join(srcdir, rel.replace('/', os.sep))
        if not os.path.isfile(src):
            print('  [!] 산출물 그림이 없다: %s' % rel)
            continue
        dst = os.path.join(dst_dir, os.path.basename(rel))
        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)
        if (not os.path.exists(dst)
                or io.open(src, 'rb').read() != io.open(dst, 'rb').read()):
            shutil.copyfile(src, dst)
            print('  산출물 그림 복사: %s' % os.path.basename(rel))


# 납품한 PDF 를 함께 배포한다. lab 은 PRIVATE 이라 raw 링크가 열리지 않으므로
# 파일을 옮겨야 한다. 내용은 이미 같은 md 로 웹 페이지가 나가 있어서 새로 드러나는
# 것은 없다. 2026-09-05 팀장 지시 「우리가 deliverable 로 납품한 pdf 들은 어디 웹에
# 기재되었는지?」 · 그때까지 사이트 전체에 PDF 링크가 0개였다.
PDF_DIR = 'assets/deliverables'


def pdf_for(rel):
    """md 경로에 짝이 되는 PDF 가 lab 에 있으면 (원본경로, 배포주소) 를 돌려준다."""
    lab = lab_root()
    if not lab:
        return None
    src = os.path.join(lab, rel.replace('/', os.sep))[:-3] + '.pdf'
    if not os.path.isfile(src):
        return None
    return src, PDF_DIR + '/' + os.path.basename(src)


def presented_for(rel):
    """발표에서 실제로 튼 판. proposal-deck 처럼 -presented.html 이 있으면 함께 낸다.

    갱신되는 산출물과 «그날 튼 것» 은 다르다. 시간이 지나면 후자를 알 수 없게 되므로
    별도 파일로 고정해 두고 여기서 그것도 배포한다. 2026-09-05 팀장 지시.
    """
    lab = lab_root()
    if not lab:
        return None
    src = os.path.join(lab, rel.replace('/', os.sep))[:-3] + '-presented.html'
    if not os.path.isfile(src):
        return None
    return src, PDF_DIR + '/' + os.path.basename(src)


def copy_presented(rel):
    got = presented_for(rel)
    if not got:
        return None
    src, web = got
    dst = os.path.join(VAULT, web.replace('/', os.sep))
    d = os.path.dirname(dst)
    if not os.path.isdir(d):
        os.makedirs(d)
    if (not os.path.exists(dst)
            or io.open(src, 'rb').read() != io.open(dst, 'rb').read()):
        shutil.copyfile(src, dst)
        print('  발표본 복사: %s (%.1f MB)' % (os.path.basename(src),
                                            os.path.getsize(src) / 1e6))
    return web


def copy_pdf(rel):
    got = pdf_for(rel)
    if not got:
        return None
    src, web = got
    dst = os.path.join(VAULT, web.replace('/', os.sep))
    d = os.path.dirname(dst)
    if not os.path.isdir(d):
        os.makedirs(d)
    if (not os.path.exists(dst)
            or io.open(src, 'rb').read() != io.open(dst, 'rb').read()):
        shutil.copyfile(src, dst)
        print('  납품 PDF 복사: %s (%.0f KB)' % (os.path.basename(src),
                                              os.path.getsize(src) / 1024))
    return web


def build():
    lab = lab_root()
    if not lab:
        print('  [!] foothold-lab 을 못 찾음. 산출물 문서 게시 건너뜀')
        return []
    made, missing = [], []
    for rel, slug, gate in DOCS:
        src = os.path.join(lab, rel.replace('/', os.sep))
        if not os.path.isfile(src):
            missing.append(rel)
            continue
        md = io.open(src, encoding='utf-8', newline=None).read()
        md, cut = _CUT.subn('', md)
        if cut:
            print('  %s: 제출본 제외 구간 %d곳 뺌' % (slug, cut))
        md = _webify(md)
        _copy_figs(md, os.path.dirname(src))
        title = mdpage.h1(md)
        if title == '문서':
            missing.append('%s (h1 없음)' % rel)
            continue
        m = meta_of(md)
        body = docs_pages.chipify(
            mdpage.render(md.split('\n', 1)[1] if md.startswith('#') else md))
        body = body.replace('&lt;br&gt;', '<br>')
        web = copy_pdf(rel)
        pres = copy_presented(rel)
        rows = [('관문', gate),
                ('작성', m.get('작성', '미기재')),
                ('상태', m.get('상태', '미기재')),
                ('원본', 'foothold-lab / %s' % rel)]
        if web:
            rows.append(('제출본',
                         '<a href="%s" target="_blank" rel="noopener">PDF 새 탭에서 보기</a>' % web))
        if pres:
            rows.append(('발표본',
                         '<a href="%s" target="_blank" rel="noopener">2026-09-04 발표에서 튼 그대로</a>' % pres))
        out = PREFIX + slug + '.html'
        io.open(os.path.join(VAULT, out), 'w', encoding='utf-8', newline='\n').write(
            docs_pages.shell(title, '산출물 · %s' % gate, m.get('요지', ''), body,
                             rows, '산출물',
                             home_href='deliverables.html',
                             home_label='← 산출물 현황으로'))
        made.append((out, title, m.get('상태', '')))
    if missing:
        # 조용히 빠지지 않게 한다. 목록에 있는데 파일이 없으면 알린다.
        print('  [!] 원본이 없어 못 만든 것 %d개: %s'
              % (len(missing), ' · '.join(missing)))
    return made


def page_of(rel):
    """lab 안 경로 -> 웹 파일 이름. 없으면 빈 문자열."""
    for r, slug, _ in DOCS:
        if r == rel:
            return PREFIX + slug + '.html'
    return ''
