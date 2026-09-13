# -*- coding: utf-8 -*-
"""lab 의 운영 문서를 웹으로.

★ 2026-08-27 감사 지적. `docs/WORKFLOW.md` 는 **스스로 「흐름의 정본」이라 선언**해
  놓고 웹 어디에도 없었다. 팀원은 `collab.html` 만 볼 수 있었고 거기엔 옛 규칙이
  있었다. 문서를 만들어 놓고 가리키지 않으면 없는 것과 같다.

  `docs_pages` 의 게시 대상은 `research/` `digest/` `meetings/` 뿐이라
  루트의 운영 문서들이 조용히 빠졌다. 이 단계가 그것을 메운다.
"""
import html as _H
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import docs_pages
import mdpage
import redact

# (lab 안 경로, 나갈 파일, 눈썹)
DOCS = [
    ('docs/WORKFLOW.md', 'workflow.html', 'Workflow · 이슈부터 머지까지'),
    ('docs/schedule/personal-plans.md', 'personal-plans.html', 'Schedule · 개인 계획'),
    ('docs/decisions/20260826-27-design-session.md', 'decisions-20260827.html',
     'Decisions · 설계 세션 기록'),
    # 2026-08-27 이관: 전에는 automation.html 을 손으로 고쳤고, 그래서 결정이
    #   바뀌어도 이 페이지만 낡은 채 남았다. 폐기된 저장소 이름과 옛 갈래가 살아 있었다.
    ('docs/AUTOMATION.md', 'automation.html', 'Automation · 자동화 지도'),
    # 2026-08-27 추가: 다른 문서 세 곳이 「우리 로봇의 단일 진실」이라며 이 문서를
    #   가리키는데 웹에는 없었다. 가리켜지는 문서가 없으면 그 링크는 글자일 뿐이다.
    ('docs/DECISIONS.md', 'decisions-log.html', 'Decisions · 결정 로그'),
    ('docs/ROBOT-SPEC.md', 'robot-spec.html', 'Spec · 우리 Go2 사양'),
    # 2026-08-28 신설 (#76): 문서 56개의 목적·상하위·최신성을 판정한 표.
    #   표지 노출 기준의 근거가 되므로 팀이 볼 수 있어야 한다.
    # 2026-08-28: 원장을 웹에. 「그거 어떻게 됐어?」의 답이 저장소 안에만 있으면
    #   팀원은 못 본다. 관문 [3.8] 이 이 문서의 최신성을 지킨다.
    # 2026-08-28: 역할 배치 정본. 덱 두 장이 여기서 생성되므로 «무엇이 정본인가»가
    #   팀에 보여야 한다. 안 보이면 또 덱을 손으로 고친다.
    ('docs/ROLES.md', 'roles.html', 'Roles · 누가 무엇을 맡나'),
    ('docs/LEDGER.md', 'ledger.html', 'Ledger · 모든 요청이 지금 어디 있나'),
    # 2026-08-29: 정보 모델 정본. 축이 무엇이고 새 문서가 어떻게 제자리에 서는가.
    ('docs/decisions/20260829-info-model.md', 'info-model.html',
     'Model · 문서를 무엇으로 가르나'),
    ('docs/decisions/20260829-research-hub-taxonomy.md', 'research-taxonomy.html',
     'Draft · 연구 허브 분류 기준 (검토중)'),
    ('docs/decisions/20260828-doc-graph.md', 'doc-graph.html',
     'Decisions · 문서 관계표'),
    # 2026-08-27 승격: 오현민의 ROS 2 학습자료 정리 (PR #63). 조선대 수업을
    #   슬라이드 복사가 아니라 「개념 -> 왜 -> 명령 -> 토큰별 뜻」으로 다시 짠 것이라
    #   그대로 실을 수 있다. 자료에서 옮긴 15주 표 한 절만 web:제외로 뺀다.
    # ★ PR #106 승격 (오현민 · 2026-09-01). 합류 시 보는 환경 구축 절차다.
    ('docs/guides/runpod-setup.md', 'runpod-setup.html',
     'Guide · RunPod Isaac Lab 환경 구축'),
    ('docs/guides/ros2-01-setup.md', 'ros2-01-setup.html',
     'Guide · ROS 2 개발환경 구축'),
    ('docs/guides/ros2-02-python.md', 'ros2-02-python.html',
     'Guide · ROS 2 Python 프로그래밍'),
    ('docs/guides/ros2-03-tf-rviz2.md', 'ros2-03-tf-rviz2.html',
     'Guide · ROS 2 TF 좌표계와 RViz2'),
]


# ★ 자동화 지도 그림 (팀장 9/1: 「글로만 써져 있다. 한눈에 보이는 그림이 있으면」)
#   md 에 원시 SVG 를 넣으면 mdpage 가 이스케이프해서 «글자» 로 나간다
#   (2026-09-01 실측: 배포본에 &lt;svg ... 가 그대로 보였다).
#   그래서 md 에는 «automap» 한 단어만 두고 여기서 갈아 끼운다.
#   docs_pages 의 flow6·loop 방식과 같다.
AUTOMAP = '''<div class="tw" style="margin:1.2rem 0 1.6rem">
<svg viewBox="0 0 980 430" role="img" aria-label="자동화 지도: 사람이 이슈를 열면 GitHub Actions 가 분류·기록·알림·배포를 이어 받는다" style="width:100%;height:auto;display:block">
<defs><marker id="ar" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="var(--ink-3)"/></marker></defs>
<text x="14" y="22" font-size="11" font-weight="800" letter-spacing="2.2" fill="var(--dim)">사람</text>
<rect x="14" y="34" width="176" height="86" rx="7" fill="var(--dim-soft)" stroke="var(--dim)"/>
<text x="30" y="60" font-size="14" font-weight="800" fill="var(--ink)">이슈를 연다</text>
<text x="30" y="80" font-size="11.5" fill="var(--ink-2)">폼에서 작업 영역과</text>
<text x="30" y="96" font-size="11.5" fill="var(--ink-2)">관문을 고른다</text>
<text x="30" y="112" font-size="10.5" fill="var(--ink-3)">여기까지가 사람 몫</text>
<rect x="14" y="140" width="176" height="70" rx="7" fill="var(--card)" stroke="var(--rule)"/>
<text x="30" y="164" font-size="13" font-weight="800" fill="var(--ink)">PR 을 올린다</text>
<text x="30" y="184" font-size="11.5" fill="var(--ink-2)">Closes #번호</text>
<text x="30" y="200" font-size="10.5" fill="var(--ink-3)">inbox 제출도 여기</text>
<rect x="14" y="230" width="176" height="86" rx="7" fill="var(--paper-2)" stroke="var(--rule)"/>
<text x="30" y="254" font-size="13" font-weight="800" fill="var(--ink)">이 PC 에서만</text>
<text x="30" y="274" font-size="11.5" fill="var(--ink-2)">웹 빌드 · 암호화</text>
<text x="30" y="290" font-size="11.5" fill="var(--ink-2)">화면 실측</text>
<text x="30" y="306" font-size="10.5" fill="var(--ink-3)">사람이 시작하는 일</text>
<line x1="196" y1="77" x2="288" y2="77" stroke="var(--ink-3)" stroke-width="1.2" marker-end="url(#ar)"/>
<line x1="196" y1="175" x2="288" y2="175" stroke="var(--ink-3)" stroke-width="1.2" marker-end="url(#ar)"/>
<text x="296" y="22" font-size="11" font-weight="800" letter-spacing="2.2" fill="var(--dim)">GITHUB ACTIONS · 기기와 무관</text>
<rect x="294" y="34" width="392" height="282" rx="8" fill="none" stroke="var(--rule)" stroke-dasharray="3 3"/>
<rect x="308" y="50" width="176" height="58" rx="6" fill="var(--card)" stroke="var(--rule)"/>
<text x="322" y="72" font-size="12.5" font-weight="800" fill="var(--ink)">분류</text>
<text x="322" y="90" font-size="10.5" fill="var(--ink-3)">issue-triage · issue-dates</text>
<rect x="496" y="50" width="176" height="58" rx="6" fill="var(--card)" stroke="var(--rule)"/>
<text x="510" y="72" font-size="12.5" font-weight="800" fill="var(--ink)">기록</text>
<text x="510" y="90" font-size="10.5" fill="var(--ink-3)">done-date · promote</text>
<rect x="308" y="124" width="176" height="58" rx="6" fill="var(--card)" stroke="var(--rule)"/>
<text x="322" y="146" font-size="12.5" font-weight="800" fill="var(--ink)">주간</text>
<text x="322" y="164" font-size="10.5" fill="var(--ink-3)">weekly-report + WBS</text>
<rect x="496" y="124" width="176" height="58" rx="6" fill="var(--card)" stroke="var(--rule)"/>
<text x="510" y="146" font-size="12.5" font-weight="800" fill="var(--ink)">감시</text>
<text x="510" y="164" font-size="10.5" fill="var(--ink-3)">lecture-watch · deadline</text>
<rect x="308" y="198" width="364" height="58" rx="6" fill="var(--note-soft)" stroke="var(--note)"/>
<text x="322" y="220" font-size="12.5" font-weight="800" fill="var(--ink)">RunPod 잔액 감시</text>
<text x="322" y="238" font-size="10.5" fill="var(--ink-2)">09:00 · 21:00 KST · 알림 $100 · 경고 $50 · 긴급 $20</text>
<rect x="308" y="272" width="364" height="30" rx="6" fill="var(--paper-2)" stroke="var(--rule)"/>
<text x="322" y="292" font-size="10.5" fill="var(--ink-3)">main-guard · 직접 push 를 감지하고 안내한다</text>
<line x1="692" y1="79" x2="784" y2="79" stroke="var(--ink-3)" stroke-width="1.2" marker-end="url(#ar)"/>
<line x1="692" y1="153" x2="784" y2="153" stroke="var(--ink-3)" stroke-width="1.2" marker-end="url(#ar)"/>
<line x1="692" y1="227" x2="784" y2="227" stroke="var(--note)" stroke-width="1.4" marker-end="url(#ar)"/>
<text x="792" y="22" font-size="11" font-weight="800" letter-spacing="2.2" fill="var(--dim)">도착</text>
<rect x="790" y="50" width="176" height="58" rx="6" fill="var(--dim-soft)" stroke="var(--dim)"/>
<text x="804" y="72" font-size="12.5" font-weight="800" fill="var(--ink)">프로젝트 보드</text>
<text x="804" y="90" font-size="10.5" fill="var(--ink-2)">라벨 · 관문 · 날짜</text>
<rect x="790" y="124" width="176" height="58" rx="6" fill="var(--card)" stroke="var(--rule)"/>
<text x="804" y="146" font-size="12.5" font-weight="800" fill="var(--ink)">웹 · Vercel</text>
<text x="804" y="164" font-size="10.5" fill="var(--ink-2)">허브 6 · 문서 90여 장</text>
<rect x="790" y="198" width="176" height="58" rx="6" fill="var(--note-soft)" stroke="var(--note)"/>
<text x="804" y="220" font-size="12.5" font-weight="800" fill="var(--ink)">디스코드 · 텔레그램</text>
<text x="804" y="238" font-size="10.5" fill="var(--ink-2)">공지 · resource 채널</text>
<line x1="102" y1="322" x2="102" y2="352" stroke="var(--ink-3)" stroke-width="1.2" stroke-dasharray="3 3" marker-end="url(#ar)"/>
<rect x="14" y="358" width="952" height="56" rx="7" fill="var(--paper-2)" stroke="var(--rule)"/>
<text x="30" y="380" font-size="12" font-weight="800" fill="var(--ink)">사람이 시작하는 셋은 이 PC 에 묶인다</text>
<text x="30" y="400" font-size="11" fill="var(--ink-2)">웹 빌드 · 암호화 자산 재생성 · Chrome 화면 실측. 시간에 맞춰 도는 일이 아니라 사람이 부르는 일이라 기기에 묶여도 된다.</text>
</svg></div>'''


def notice_list(lab, cur):
    """공지 페이지 아래 «지난 공지» 목록 (팀장 9/2).

    판 이력 표를 링크로 만드는 대신 목록을 둔다. 표는 남는데 내용이 사라지면
    죽은 링크가 되지만, 목록은 실제 파일을 가리키므로 안 죽는다.
    지금 보는 판은 링크 없이 표시만 한다.
    """
    d = os.path.join(lab, 'docs', 'notices')
    days = sorted((f[:-3] for f in os.listdir(d)
                   if re.match(r'^\d{4}-\d{2}-\d{2}\.md$', f)), reverse=True)
    if len(days) < 2:
        return ''
    li = []
    for day in days:
        md = io.open(os.path.join(d, day + '.md'),
                     encoding='utf-8', errors='replace').read()
        m = re.search(r'^>\s*요지:\s*(.+)$', md, re.M)
        gist = re.sub(r'\*\*|`', '', (m.group(1) if m else '')).strip()
        href = 'notice-%s.html' % day.replace('-', '')
        if day == cur:
            li.append('<div class="nl-row nl-cur"><b>%s</b><span>%s</span>'
                      '<i>지금 보는 공지</i></div>' % (day, _H.escape(gist[:70])))
        else:
            li.append('<a class="nl-row" href="%s"><b>%s</b><span>%s</span></a>'
                      % (href, day, _H.escape(gist[:70])))
    return (
        '<style>.nl{margin:2.6rem 0 0;border-top:1px solid var(--rule);padding-top:1.1rem}'
        '.nl>h2{font-size:1rem;font-weight:800;margin:0 0 .7rem}'
        '.nl-row{display:flex;gap:.9rem;align-items:baseline;padding:.5rem 0;'
        'border-bottom:1px solid var(--rule);text-decoration:none;color:inherit}'
        '.nl-row b{font-size:.78rem;font-weight:700;min-width:6.2rem;'
        'font-variant-numeric:tabular-nums}'
        '.nl-row span{font-size:.74rem;color:var(--ink-3);flex:1}'
        '.nl-row i{font-style:normal;font-size:.6rem;font-weight:800;'
        'letter-spacing:.1em;color:var(--dim)}'
        'a.nl-row:hover b{color:var(--dim)}</style>'
        '<div class="nl"><h2>지난 공지 %d개</h2>%s</div>' % (len(days), ''.join(li)))


def notice_pages(lab):
    """날짜 공지를 전부 게시 목록에 넣는다 (팀장 9/2).

    ★ 지금까지 `notices/latest.md` 하나를 덮어써서 이전 공지 원문이 없었다.
      「이전 공지가 궁금할 수도 있잖아」 · 맞다. 그리고 덮어쓰기라
      «파일은 그대론데 내용만 바뀌어» NEW 배지도 안 떴다.

      공지를 날짜 파일로 두면 셋이 한꺼번에 풀린다.
        이전 공지를 볼 수 있다 · 배지가 저절로 뜬다 · 목록이 곧 이력이다

      가장 최근 것은 `notice-latest.html` 로도 열린다. 기존 링크가 안 깨진다.
    """
    d = os.path.join(lab, 'docs', 'notices')
    if not os.path.isdir(d):
        return []
    days = sorted((f[:-3] for f in os.listdir(d)
                   if re.match(r'^\d{4}-\d{2}-\d{2}\.md$', f)), reverse=True)
    out = []
    for i, day in enumerate(days):
        rel = 'docs/notices/%s.md' % day
        out.append((rel, 'notice-%s.html' % day.replace('-', ''),
                    'Notice · %s 공지' % day))
        if i == 0:                      # 최신은 옛 주소로도 연다
            out.append((rel, 'notice-latest.html', 'Notice · 팀 공지'))
    return out


def lab_root():
    for p in docs_pages.LAB_CANDIDATES:
        if os.path.isdir(os.path.join(p, 'docs')):
            return p
    return None


def meta_of(md):
    out = {}
    for f in ('분류', '작성', '근거', '요지', '상태'):
        m = re.search(r'^>\s*%s\s*:\s*(.+)$' % f, md, re.M)
        if m:
            out[f] = m.group(1).strip()
    return out


def build():
    lab = lab_root()
    if not lab:
        print('  [!] foothold-lab 을 못 찾음. 운영 문서 게시 건너뜀')
        return []
    made, missing = [], []
    for rel, out, eyebrow in DOCS + notice_pages(lab):
        src = os.path.join(lab, rel.replace('/', os.sep))
        if not os.path.isfile(src):
            missing.append(rel)
            continue
        md = io.open(src, encoding='utf-8', newline=None).read()
        # 대외비 금액은 웹으로 나가기 «전에» 가린다. [4] 관문에 걸려 배포가
        # 멈추기 전에, 여기서 먼저 처리하고 «가렸다는 사실»을 화면에 적는다.
        md = redact.apply(md, 'foothold-lab / ' + rel)
        m = meta_of(md)
        title = mdpage.h1(md)
        if title == '문서':
            # 공지처럼 h1 이 없는 문서. 요지를 제목으로 쓴다.
            title = m.get('요지', out[:-5])
        body = docs_pages.chipify(
            mdpage.render(md.split('\n', 1)[1] if md.startswith('#') else md))
        # 마커를 그림으로. md 에 원시 SVG 를 두면 이스케이프돼 글자로 나간다
        body = re.sub(r'<p>(?:<span class="vlink">)?automap'
                      r'(?:</span>)?</p>', lambda _m: AUTOMAP, body)
        _nd = re.match(r'^docs/notices/(\d{4}-\d{2}-\d{2})\.md$', rel)
        if _nd:
            body += notice_list(lab, _nd.group(1))
        _v = docs_pages.ver_of(md)
        _is = docs_pages.issue_of(md)
        rows = ([('판', _v)] if _v else []) + \
               ([('이슈', _is)] if _is else []) + [('작성', m.get('작성', '미기재')),
                ('상태', m.get('상태', '미기재')),
                ('원본', 'foothold-lab / %s' % rel)]
        io.open(os.path.join(VAULT, out), 'w', encoding='utf-8', newline='\n').write(
            docs_pages.shell(title, eyebrow, m.get('요지', ''), body, rows, '운영'))
        made.append((out, title))
    if missing:
        print('  [!] 원본이 없어 못 만든 것: %s' % ' · '.join(missing))
    if not made:
        raise SystemExit('  [!] 운영 문서를 하나도 못 만들었습니다.')
    return made
