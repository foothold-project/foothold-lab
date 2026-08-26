# -*- coding: utf-8 -*-
"""inbox 제출물 자동 검토: 승격 조건을 기계가 판정하고 승격안을 만든다.

  판정은 docs/README.md 의 승격 조건 그대로다.
    h1 제목 · 증거 표기 · 원 출처 링크 · 웹 금지 요소(ASCII 도식·em dash)
    + 메타데이터 4줄 (2026-08-26 추가)
  통과 여부와 무관하게 **무엇을 고쳐야 하는지**를 문장으로 돌려준다.
  사람이 파일을 열어보지 않고도 승격 여부를 정할 수 있게 하는 것이 목적이다.

  ★ 2026-08-26 메타데이터 검사 추가.
    8/25 에 문서 표준(분류·작성·근거·요지)을 정하고 빌드 관문(metacheck)까지
    세웠는데, **팀원 제출 경로에는 그 검사가 없었다.** 그래서 표준 밖 문서가
    그대로 통과해 웹까지 갔고, 「본인 학습 계획」이 「회의록」으로 올라갔다.
    관문은 사람이 지나는 모든 문에 있어야 한다. 한 문만 열려 있으면 그리로 샌다.

  출력: JSON (stdout)  { files: [ {path, title, lede, checks{}, ok, slug, dest, fixes[] } ] }
"""
import io, json, os, re, sys

# 문서 표준 (05_deliverables/_build/metacheck.py 와 같은 목록을 쓴다)
KINDS = ('회의록', '리서치', '실험', '계획', '결정', '운영', '현장', '가이드')
WRITER = re.compile(r'^\s*(.+?)\s*[·]\s*(20\d{2}-\d{2}-\d{2})\s*$')


def meta_of(md):
    """머리 메타 4~5줄을 읽는다. 없으면 빈 값."""
    out = {}
    for f in ('분류', '작성', '근거', '요지', '상태'):
        m = re.search(r'^>\s*%s\s*:\s*(.+)$' % f, md, re.M)
        if m:
            out[f] = m.group(1).strip()
    return out


def paste_block(meta, author, today):
    """PR 코멘트에 그대로 붙일 머리 다섯 줄.

    기계가 아는 것(작성자·날짜·상태)은 채우고, 내용을 읽어야 아는 것
    (분류·근거·요지)은 고르라고 남긴다. 설명하는 것보다 완성본을 주는 편이 빠르다.
    """
    def keep(f, default):
        v = (meta or {}).get(f)
        return v if v else default
    return chr(10).join([
        '> 분류: %s' % keep('분류', '리서치'),
        '> 작성: %s' % keep('작성', '%s · %s' % (author or '이름', today)),
        '> 근거: %s' % keep('근거', '공식 문서'),
        '> 요지: %s' % keep('요지', '(한 줄로 이 문서가 말하는 것)'),
        '> 상태: %s' % keep('상태', '초안'),
    ])


def review(path):
    md = io.open(path, encoding='utf-8').read()
    title = None
    m = re.search(r'^#\s+(.+)$', md, re.M)
    if m:
        title = m.group(1).strip()
    meta = meta_of(md)
    lede = meta.get('요지', '')
    if not lede:
        m = re.search(r'^>?\s*요지:\s*(.+)$', md, re.M)
        lede = m.group(1).strip() if m else ''
    lede = lede[:120]

    evidence = len(re.findall(r'`(확인됨|검증됨|실측|추측|가설|미측정|미확인|코드확인)`', md))
    links = len(set(re.findall(r'https?://[^\s)]+', md)))
    ascii_art = len(re.findall(r'[─-╿▀-▟]', md))
    emdash = md.count('—')

    missing = [f for f in ('분류', '작성', '근거', '요지', '상태') if not meta.get(f)]
    kind_ok = meta.get('분류') in KINDS if meta.get('분류') else False
    writer_ok = bool(WRITER.match(meta['작성'])) if meta.get('작성') else False

    checks = {
        'h1 제목': bool(title),
        '메타데이터 5줄': not missing,
        '분류가 정해진 값': kind_ok,
        '작성자·날짜 형식': writer_ok,
        '증거 표기': evidence > 0,
        '원 출처 링크': links > 0,
        '웹 금지 요소 없음': ascii_art < 3 and emdash == 0,
    }
    fixes = []
    if not checks['h1 제목']:
        fixes.append('맨 위에 `# 제목` 추가')
    if missing:
        fixes.append('머리에 메타 5줄 추가 (빠짐: %s). 예) > 분류: 리서치'
                     % ' · '.join(missing))
    elif not kind_ok:
        fixes.append('분류를 다음 중 하나로: %s (지금 「%s」)'
                     % (' · '.join(KINDS), meta.get('분류')))
    if meta.get('작성') and not writer_ok:
        fixes.append('작성은 «이름 · YYYY-MM-DD» 형식으로 (지금 「%s」)' % meta['작성'])
    if not checks['증거 표기']:
        fixes.append('`확인됨`/`추측`/`미측정` 표기 부여')
    if not checks['원 출처 링크']:
        fixes.append('참고한 원 출처 링크 추가')
    if ascii_art >= 3:
        fixes.append('선으로 그린 도식 %d자를 표로 변환' % ascii_art)
    if emdash:
        fixes.append('em dash %d개 제거' % emdash)

    slug = re.sub(r'^\d{8}[-_]', '', os.path.basename(path)[:-3])
    slug = re.sub(r'[^a-z0-9-]+', '-', slug.lower()).strip('-') or 'submission'
    # 문서 표준의 «분류»를 함께 돌려준다. 「본인 학습 계획」이 「회의록」으로
    # 올라간 사고가 있었으므로, 팀장이 알림만 보고도 분류가 내용과 맞는지
    # 볼 수 있어야 한다.
    # ★ 키 이름은 doc_kind 다. 'kind' 는 파일 종류(research/profile/asset)라
    #   아래에서 덮어쓴다. 같은 이름을 쓰면 조용히 사라진다(실제로 그랬다).
    return {
        'path': path, 'title': title or '(제목 없음)', 'lede': lede,
        'doc_kind': meta.get('분류') or '(분류 없음)',
        'writer': meta.get('작성') or '(작성 없음)',
        'lines': md.count('\n') + 1, 'bytes': len(md.encode('utf-8')),
        'evidence': evidence, 'links': links,
        'checks': checks, 'ok': all(checks.values()),
        'slug': slug, 'dest': 'docs/research/%s.md' % slug, 'fixes': fixes,
        'block': paste_block(meta, os.environ.get('PR_AUTHOR', ''),
                             os.environ.get('TODAY', '')) if missing or not meta.get('상태') else '',
    }


# ── 제출물 종류를 먼저 가른다 ────────────────────────────────────────────
#   연구 문서 기준(증거 표기·원 출처 링크)을 자기소개나 개인 사이트에 들이대면
#   멀쩡한 제출물을 «손질 필요»로 잘못 판정한다. 이진 파일(이미지)에는 아예
#   죽어서 텔레그램 보고 자체가 안 갔다. (2026-08-24)

PROFILE_SLUGS = ('lead', 'lim', 'meang', 'lee', 'oh')

# 공개 페이지로 나가는 것이므로 개인정보를 기계가 먼저 훑는다.
PII = [
    (r'01[016789][-\s]?\d{3,4}[-\s]?\d{4}', '휴대전화번호'),
    (r'\b0\d{1,2}[-\s]\d{3,4}[-\s]\d{4}\b', '유선전화번호'),
    (r'\b\d{6}[-\s]?[1-4]\d{6}\b', '주민등록번호'),
    (r'(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)'
     r'\S{0,20}(시|군|구)\S{0,30}(로|길)\s?\d', '상세 주소'),
]

TEXTY = ('.md', '.txt', '.html', '.htm', '.css', '.js', '.json',
         '.svg', '.csv', '.yml', '.yaml')


def scan_pii(text):
    return [label for pat, label in PII if re.search(pat, text)]


def is_profile(path):
    b = os.path.basename(path)
    if b.endswith('.md') and b[:-3] in PROFILE_SLUGS:
        return True
    low = path.lower()
    return any(k in low for k in ('profile', 'intro', '소개', '프로필'))


def review_profile(path):
    """자기소개: 연구 기준을 적용하지 않는다. 볼 것은 개인정보와 문체뿐이다."""
    md = io.open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'^#\s+(.+)$', md, re.M)
    pii = scan_pii(md)
    emdash = md.count('—')
    checks = {'개인정보 없음': not pii, 'em dash 없음': emdash == 0}
    fixes = []
    if pii:
        fixes.append('공개 페이지입니다. %s 를 지워주세요' % ' · '.join(pii))
    if emdash:
        fixes.append('em dash %d개 제거' % emdash)
    slug = os.path.basename(path)[:-3].lower()
    return {
        'path': path, 'kind': 'profile',
        'title': (m.group(1).strip() if m else os.path.basename(path)),
        'lede': '팀원 자기소개', 'lines': md.count('\n') + 1,
        'bytes': len(md.encode('utf-8')), 'evidence': 0, 'links': 0,
        'checks': checks, 'ok': all(checks.values()),
        'slug': slug, 'dest': '02_team/profiles/%s.md' % slug, 'fixes': fixes,
    }


def review_asset(path):
    """마크다운이 아닌 것(개인 사이트의 html·css, 이미지). 이진 파일에 죽지 않는다."""
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)
    checks, fixes = {}, []
    if ext in TEXTY:
        txt = io.open(path, encoding='utf-8', errors='replace').read()
        pii = scan_pii(txt)
        checks = {'개인정보 없음': not pii}
        if pii:
            fixes.append('공개됩니다. %s 를 지워주세요' % ' · '.join(pii))
    return {
        'path': path, 'kind': 'asset',
        'title': os.path.basename(path),
        'lede': '%s · %.1fKB' % (ext or '확장자 없음', size / 1024.0),
        'lines': 0, 'bytes': size, 'evidence': 0, 'links': 0,
        'checks': checks, 'ok': all(checks.values()) if checks else True,
        'slug': '', 'dest': '(개인 페이지 자산 · 팀장이 배치)', 'fixes': fixes,
    }


def review_any(path):
    if not path.endswith('.md'):
        return review_asset(path)
    if is_profile(path):
        return review_profile(path)
    r = review(path)
    r['kind'] = 'research'
    return r


if __name__ == '__main__':
    out = []
    for p in sys.argv[1:]:
        if not os.path.exists(p):
            continue
        try:
            out.append(review_any(p))
        except Exception as e:          # 한 파일이 죽어도 나머지는 보고한다
            out.append({'path': p, 'kind': 'error', 'title': os.path.basename(p),
                        'lede': '', 'lines': 0, 'bytes': 0, 'evidence': 0,
                        'links': 0, 'checks': {}, 'ok': False, 'slug': '',
                        'dest': '', 'fixes': ['자동 검토 실패: %s' % str(e)[:80]]})
    print(json.dumps({'files': out}, ensure_ascii=False))
