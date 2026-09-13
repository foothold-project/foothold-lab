# -*- coding: utf-8 -*-
"""마크다운 링크 `[문구](경로.md)` 를 «웹의 진짜 페이지»로 잇는 한 곳.

★ 2026-08-27 검수에서 나온 것. 배포된 페이지 10개에 `[프로젝트 보고서](../REPORT.md)`
  같은 **마크다운 원문이 글자 그대로** 36곳 노출돼 있었다. 읽는 사람에게는
  깨진 글씨일 뿐이고, 눌러도 아무 일이 없다.

  원인은 하나다. `mdpage.inline()` 은 `http` 링크와 `.html` 링크만 처리하고
  `.md` 는 그냥 흘려보냈다. 그래서 게시기마다 자기 나름의 치환 규칙을 손으로
  적어 넣었는데(`docs_pages` 의 `research/*.md -> research-*.html`,
  `../REPORT.md -> project-report.html` …), **게시기마다 아는 규칙이 달랐다.**
  회의 기록은 REPORT 를 알고 현장 목록은 몰랐다.

  커널 2-2: 실수는 부류로 막는다. 「이 파일의 이 링크를 고친다」가 아니라
  **어디에 게시되는지 아는 곳을 하나로 만들고, 남은 원문이 있으면 빌드를 세운다.**

쓰는 곳
  - `mdpage.inline()` 이 `.md` 링크를 만나면 `resolve()` 에 묻는다.
  - `build.py` [3.65] 가 배포본을 훑어 원문이 남았는지 본다.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)

# lab 안 경로(소문자) -> 배포 파일. 게시기들이 실제로 쓰는 이름 규칙을 여기 모은다.
_MAP = {}
_BUILT = False


def _put(lab_rel, page):
    _MAP[lab_rel.lower().replace(os.sep, '/')] = page


def build(lab):
    """lab 저장소를 훑어 «어떤 md 가 어떤 html 로 나가는가» 를 만든다."""
    global _BUILT
    _MAP.clear()
    if not lab or not os.path.isdir(lab):
        _BUILT = True
        return _MAP

    docs = os.path.join(lab, 'docs')

    # 1) 폴더 규칙: 앞머리를 붙여 나간다
    for sub, prefix in (('research', 'research-'), ('digest', 'digest-'),
                        ('meetings', 'meeting-')):
        d = os.path.join(docs, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.md') or fn == 'README.md':
                continue
            # ★ 2026-08-28. 여기서 «게시되는가» 를 안 봤다. 그래서 상태가
            #   「폐기」 인 문서에도 주소를 만들어 줬고 결과가 죽은 링크였다.
            #   판정은 docs_pages.publishable() 하나만 쓴다.
            try:
                import docs_pages
                body = io.open(os.path.join(d, fn), encoding='utf-8',
                               newline=None).read()
                if not docs_pages.publishable(body)[0]:
                    continue
            except Exception:
                pass
            # ★ 2026-09-09 팀장 지적: 연구 허브에서 클릭하면 404.
            #   여기서 페이지 «이름» 을 소문자로 만들었는데 실제 파일을 쓰는
            #   docs_pages 는 `slug = fn[:-3]` 로 «대소문자를 보존» 한다.
            #   그래서 링크는 research-nvidia…, 파일은 research-NVIDIA… 였고
            #   Vercel 은 대소문자를 구분하므로 404 가 났다. 실측 1건.
            #   찾을 때 쓰는 _MAP «키» 는 그대로 소문자로 둔다 (대소문자 무시 조회).
            #   바꾸는 것은 «값», 즉 실제 파일 이름뿐이다.
            _put('docs/%s/%s' % (sub, fn), prefix + fn[:-3] + '.html')

    # 2) docs 바로 밑의 낱개 문서
    for fn in sorted(os.listdir(docs)) if os.path.isdir(docs) else []:
        if fn.startswith('FIELD-CHECK') and fn.endswith('.md'):
            _put('docs/' + fn, fn[:-3].lower() + '.html')
    for fn, page in (('COLLAB.md', 'collab.html'),
                     ('FLOW.md', 'flow.html'),
                     ('REPORT.md', 'project-report.html')):
        if os.path.isfile(os.path.join(docs, fn)):
            _put('docs/' + fn, page)

    # 3) 운영 문서 · 산출물 문서: 각 게시기가 가진 목록을 그대로 가져온다.
    #    여기서 베껴 적으면 목록이 둘로 갈라져 또 어긋난다.
    try:
        import ops_pages
        for rel, out, _eyebrow in ops_pages.DOCS:
            _put(rel, out)
    except Exception:
        pass
    try:
        import deliverables_docs as dd
        for rel, slug, _gate in dd.DOCS:
            _put(rel, dd.PREFIX + slug + '.html')
    except Exception:
        pass

    # 4) 볼트 문서 (lab 이 아니라 MAI_UNIVERSE 쪽)
    _put('02_team/SETUP_GUIDE.md', 'setup.html')
    _put('02_team/TEAM_ACCESS.md', 'team-access.html')
    _put('04_plan/PLAN.md', 'plan.html')

    _BUILT = True
    return _MAP


def resolve(target):
    """`../REPORT.md` · `research/foo.md#3` -> ('project-report.html#3' | '')

    출발 문서의 위치를 모르므로 **경로 꼬리**로 맞춘다. 꼬리가 여럿에 걸리면
    (어느 쪽인지 알 수 없으므로) 링크를 걸지 않는다. 죽은 링크보다 낫다.
    """
    if not _BUILT:
        return ''
    frag = ''
    if '#' in target:
        target, frag = target.split('#', 1)
        frag = '#' + frag
    t = target.lower().replace(os.sep, '/').lstrip('/')
    while t.startswith('../') or t.startswith('./'):
        t = t.split('/', 1)[1] if '/' in t else ''
    if not t.endswith('.md'):
        return ''
    hit = [v for k, v in _MAP.items() if k == t or k.endswith('/' + t)]
    if len(set(hit)) != 1:
        return ''
    return hit[0] + frag


# ── 배포본에 마크다운 원문이 남았는지 보는 관문 ──────────────────────────
_RAW = re.compile(r'\[([^\]\n]{1,80})\]\(([^)\s]{1,200})\)')


def _text_of(s):
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', s, flags=re.S)
    s = re.sub(r'<!--.*?-->', ' ', s, flags=re.S)
    return re.sub(r'<[^>]+>', ' ', s)


def _kat():
    """★ 답을 아는 입력으로 관문을 먼저 시험한다."""
    if len(_RAW.findall('보라 [문서](a.md) 그리고 [둘](b.md)')) != 2:
        return False, '원문 링크를 못 셈'
    if _RAW.findall('<a href="a.html">문서</a>'):
        return False, '정상 링크를 원문으로 오인'
    return True, ''


def gate(site):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    found = []
    n = 0
    for dirpath, dirnames, names in os.walk(site):
        dirnames[:] = [d for d in dirnames if d not in ('assets', '_build', '_src')]
        for f in sorted(names):
            if not f.endswith('.html'):
                continue
            n += 1
            txt = _text_of(io.open(os.path.join(dirpath, f), encoding='utf-8',
                                   newline=None).read())
            for label, tgt in _RAW.findall(txt):
                rel = os.path.relpath(os.path.join(dirpath, f), site)
                found.append((rel.replace(os.sep, '/'), label, tgt))
    print('  자가검증 통과 · 페이지 %d개 · 연결 규칙 %d개' % (n, len(_MAP)))
    # ★ 2026-09-10. 「검사할 것이 없었다」와 「위반이 없었다」는 다른 사실이다.
    #   빈 대상으로 돌려 보니 이 관문이 「0개 · 통과」를 찍고 성공을 돌려줬다.
    #   목록이 비는 순간 조용히 무력해진다. 그리고 목록은 실제로 빈다.
    if n == 0:
        print('  [!] 배포 페이지를 한 장도 못 봤습니다. 검사가 헛돌았습니다')
        return False
    if found:
        seen = set()
        for path, label, tgt in found:
            if path in seen:
                continue
            seen.add(path)
            print('  %-44s [%s](%s)' % (path, label[:24], tgt[:40]))
        print('  마크다운 원문이 글자로 노출 %d곳 (파일 %d개)' % (len(found), len(seen)))
        return False
    print('  마크다운 원문 노출 없음')
    return True
