# -*- coding: utf-8 -*-
"""lab 문서 → 웹 자동 게시  (빌드 [1.78] 단계)

  ★ 이 단계의 목적: WS 세션이 `foothold-lab/docs/research/` 에 문서를 올리면
    **아무도 손대지 않아도** 다음 빌드에서 웹 페이지가 되고 표지에 카드가 생긴다.
    새 문서를 위해 이 파일을 고칠 일은 없다. 폴더를 훑어서 발견한다.

  분류 정책 (한 곳에서만 정한다)
    · docs/research/*.md   → 게시. 근거·실측 기록은 이 프로젝트의 공개 자산이다.
    · 그 외 (LEDGER · DECISIONS · ops/ · notices/) → 내부 문서, 게시하지 않는다.
      원장·결정로그는 우리 작업 상태이지 독자의 읽을거리가 아니다.
    · 개별 예외: 문서 안에 `<!-- web: skip -->` 이 있으면 건너뛴다(발견됐다는 사실은 보고).

  내용 점검 (게시 전에 기계가 본다)
    · h1 이 없으면 게시하지 않는다. 제목 없는 페이지는 표지 카드도 못 만든다.
    · 증거 표기(`확인됨` / `추측` / `미측정` / `미확인`)를 칩으로 렌더해
      **어디까지가 검증된 사실인지 독자가 한눈에** 알게 한다. 원문 표기가 곧 웹 표기다.
    · 증거 표기가 하나도 없으면 경고를 남긴다(중단하지는 않는다. 문서 성격에 따라 없을 수 있다).
    · 민감정보는 이 단계가 아니라 [4] scan 이 배포 직전에 잡는다(공개될 파일 자체를 본다).

  디자인: 다른 문서 페이지와 같은 껍데기(team_access CSS)를 쓴다. 파비콘·다크모드·토글은
  뒤 단계가 PAGES 를 훑으며 자동으로 넣는다. 여기서 신경 쓰지 않는다.
"""
import io, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mdpage
import redact
import team_access
import buildtime

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)

# lab 클론 위치 후보: 기계마다 다르다.
#   ★ 2026-09-02. **작업 공간 상대 경로를 맨 앞에 둔다.**
#     전에는 기기 절대경로가 맨 앞이라, 격리된 작업 공간에서 빌드해도 이 표를
#     쓰는 모듈 17개가 «진짜 lab» 을 읽고 썼다. 재현 빌드의 격리가 조용히
#     새는 자리였다 (실측: 격리 빌드가 실제 lab 의 versions.json 을 고쳤다).
#     기기 이름이 박힌 경로를 앞에 두지 않는다 (철칙 1).
# ★ 2026-09-13. 빌드가 foothold-lab 안으로 들어왔다. 더듬을 것이 없다.
#
#   여기 있던 «_lab-main 을 맨 앞에» 규칙을 **뒤집는다.** 만든 뜻은 옳았다
#   (여러 세션이 브랜치를 흔들면 연속 빌드가 재현되지 않는다). 그런데 그것이
#   2026-09-13 에 **26 커밋을 조용히 가렸다.** 빌드는 사흘 전 문서를 읽으며
#   아무 말도 하지 않았고, 「고쳤는데 화면이 안 바뀐다」로 나타났다.
#
#   지금은 빌드와 문서가 «같은 저장소» 에 있다. 그래서 커밋 하나가 곧 한
#   입력이고, 기본값은 자기 저장소를 읽는 것이 맞다.
#   고정 입력이 필요한 재현 빌드는 FOOTHOLD_LAB 로 «명시해» 부른다.
LAB_CANDIDATES = __import__('roots').lab_candidates()


def restrict(root):
    """재현 빌드 전용. 작업 공간 밖의 lab 후보를 지운다.

    ★ 왜 필요한가
      후보에 기기 절대경로가 있으면, 격리 공간에서 빌드해도 이 표를 쓰는
      모듈이 진짜 lab 을 읽고 쓴다. A 의 쓰기가 B 의 입력을 바꾸면 A/B 비교가
      독립이 아니다. 그래서 재현 모드는 «범위 밖 후보를 아예 지운다».
      목록을 제자리에서 줄이므로 이미 import 한 모듈에도 그대로 먹는다.

    쓸 수 있는 lab 을 돌려준다. 없으면 None 이고, 부르는 쪽이 소리 내어 죽는다.
    """
    root = os.path.abspath(root)
    keep = [p for p in LAB_CANDIDATES
            if os.path.abspath(p) == root
            or os.path.abspath(p).startswith(root + os.sep)]
    LAB_CANDIDATES[:] = keep
    for p in keep:
        if os.path.isdir(os.path.join(p, 'docs')):
            return p
    return None

PUBLISH_DIR = 'research'          # 게시 대상 폴더 (docs/ 기준)
PREFIX = 'research-'              # 생성 파일 이름 앞머리
INDEX = 'research.html'           # 목록 페이지

# 증거 표기 → 칩 등급
CHIPS = {
    '확인됨': ('ok', '확인됨'),
    '검증됨': ('ok', '검증됨'),
    '실측': ('ok', '실측'),
    # 저장소 코드에서 읽어 확인했으나 실행은 안 한 것: 실측(확인됨)보다 한 단계 아래
    '코드확인': ('guess', '코드확인'),
    '추측': ('guess', '추측'),
    '가설': ('guess', '가설'),
    '미측정': ('todo', '미측정'),
    '미확인': ('todo', '미확인'),
    '미착수': ('todo', '미착수'),
}

import standing as _standing

CHIP_CSS = """
/* ★ 2026-09-13. 여기에 도해용 토큰(--accent --bad --ok …)을 정의했다가
 * **걷어냈다.** `:root[data-theme="dark"]` 블록이 하나뿐인데 그것을 새 팔레트로
 * 덮어써서, 원래 있던 --paper · --card · --ink 정의가 사라졌다.
 * 실측: 완비 관문이 「테마 오버라이드가 반쪽이다 (light)」로 **53장**을 잡았다.
 * 그대로 나갔으면 어두운 테마에서 53장이 배경을 잃었다.
 *
 * 애초에 필요 없다. 도해를 본문에 넣는 길을 물렸으므로(위 mdpage 주석 참조)
 * 토큰은 **SVG 파일 안**에 있어야 한다. `tools/svg_selfcontained.py` 가
 * `docs/assets/visual/` 의 원본에 넣는다. 거기가 빌드가 읽는 자리다.
 */
.mdsvg{margin:20px 0;padding:0;overflow-x:auto}
.mdsvg svg{display:block;max-width:100%;height:auto}
.ev{display:inline-block;padding:.05rem .4rem;border-radius:3px;font-size:.68rem;
  font-weight:800;letter-spacing:.04em;vertical-align:.06em;white-space:nowrap;
  border:1px solid transparent}
.ev-ok{background:var(--dim-soft);color:var(--dim);border-color:var(--dim)}
.ev-guess{background:var(--note-soft);color:var(--note);border-color:var(--note)}
.ev-todo{background:var(--paper-2);color:var(--ink-3);border-color:var(--rule)}
.evlegend{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0 0;font-size:.72rem;color:var(--ink-3)}
.rcards{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));margin:18px 0}
.rcard{display:block;text-decoration:none;color:inherit;background:var(--card);
  border:1px solid var(--rule);border-radius:6px;padding:14px 16px;transition:border-color .15s}
.rcard:hover{border-color:var(--dim)}
.rcard .rt{font-weight:800;font-size:1rem;margin:.2rem 0 .35rem}
.rcard .rd{font-size:.8rem;color:var(--ink-2);line-height:1.55}
.rcard .rm{font-size:.7rem;color:var(--ink-3);margin-top:.5rem;letter-spacing:.04em}
.rcard .rno{display:inline-block;min-width:1.7em;text-align:center;background:var(--paper-2);border:1px solid var(--rule);border-radius:3px;font-size:.72rem;color:var(--ink-3);margin-right:.15rem;vertical-align:.06em}
/* 대표 그림. 카드가 «무엇에 관한 글인지»를 제목보다 빨리 말해준다 */
.rcard.has-thumb{padding:0;overflow:hidden;display:flex;flex-direction:column}
.rcard .rthumb{background:var(--paper-2);border-bottom:1px solid var(--rule);
  aspect-ratio:16/7;overflow:hidden}
.rcard .rthumb img{width:100%;height:100%;object-fit:cover;display:block;transition:.2s}
.rcard.has-thumb .rbody{padding:14px 16px}
.rcard:hover .rthumb img{transform:scale(1.03)}
/* 목록 상단 배너: 최신 다이제스트만. (질문 지도는 표지로 승격: 팀장 컨펌 2026-08-12)
   이모지 없이 브랜드 토큰만 쓴다. */
.dgbar{margin:16px 0 4px}
.dgbar a{display:flex;align-items:baseline;gap:.55rem;flex-wrap:wrap;text-decoration:none;
  color:inherit;border:1px solid var(--rule);background:var(--note-soft);border-radius:6px;
  padding:.6rem .9rem;font-size:.85rem;transition:border-color .15s}
.dgbar a .k{font-size:.62rem;font-weight:800;letter-spacing:.16em;color:var(--note);
  text-transform:uppercase}
.dgbar a span{color:var(--ink-3);font-size:.72rem}
.dgbar a:hover{border-color:var(--note)}
""" + _standing.CSS


def publishable(md):
    """이 문서가 웹에 나가는가. (나가나, 왜 아닌가)

    ★ 2026-08-28. 이 판정이 `docs_pages` 안에만 있었다. 그래서 `mdlinks` 는
      폴더 규칙만 보고 «폐기» 문서에도 링크 주소를 만들어 줬고, 결과가
      **죽은 링크**였다. 판정하는 곳을 하나로 만든다 (커널 철칙 4).
    """
    if '<!-- web: skip -->' in md:
        return False, '문서가 게시 거부(web: skip)'
    if re.search(r'^>\s*상태\s*:\s*폐기', md, re.M):
        return False, '상태가 「폐기」 (저장소에는 남는다)'
    return True, ''


def _svg_chain(steps, loop_back=None, note=None):
    """가로 단계 흐름 SVG. 박스+화살표, 브랜드 토큰 색. 좁은 화면은 viewBox 축소로 대응."""
    n = len(steps)
    bw, bh, gap, pad = 132, 46, 34, 6
    w = pad * 2 + bw * n + gap * (n - 1)
    h = 96 if loop_back else 66
    y = 10
    parts = ['<svg class="rptflow" viewBox="0 0 %d %d" role="img" '
             'style="width:100%%;height:auto;display:block;margin:14px 0" '
             'font-family="inherit">' % (w, h)]
    for i, s in enumerate(steps):
        x = pad + i * (bw + gap)
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="6" '
                     'fill="var(--card)" stroke="var(--dim)" stroke-width="1.6"/>' % (x, y, bw, bh))
        lines = s.split('\n')
        for j, ln in enumerate(lines):
            ty = y + bh / 2 + (j - (len(lines) - 1) / 2) * 14 + 4
            parts.append('<text x="%d" y="%.0f" text-anchor="middle" font-size="12" '
                         'font-weight="700" fill="var(--ink)">%s</text>' % (x + bw / 2, ty, ln))
        if i < n - 1:
            ax = x + bw
            parts.append('<path d="M%d %d L%d %d" stroke="var(--dim)" stroke-width="1.6"/>'
                         % (ax + 4, y + bh // 2, ax + gap - 8, y + bh // 2))
            parts.append('<path d="M%d %d l-7 -4 v8 z" fill="var(--dim)"/>'
                         % (ax + gap - 4, y + bh // 2))
    if loop_back:
        x1 = pad + bw / 2
        x2 = pad + (n - 1) * (bw + gap) + bw / 2
        yy = y + bh + 18
        parts.append('<path d="M%.0f %d V%d H%.0f V%d" fill="none" stroke="var(--note)" '
                     'stroke-width="1.6" stroke-dasharray="5 4"/>' % (x2, y + bh + 2, yy, x1, y + bh + 8))
        parts.append('<path d="M%.0f %d l-4 7 h8 z" fill="var(--note)"/>' % (x1, y + bh + 4))
        parts.append('<text x="%.0f" y="%d" text-anchor="middle" font-size="11" '
                     'fill="var(--note)" font-weight="700">%s</text>'
                     % ((x1 + x2) / 2, yy - 5, loop_back))
    parts.append('</svg>')
    return ''.join(parts)


def _card2(a_title, a_html, b_title, b_html):
    """원본 PDF 의 2열 카드(상단 굵은 보더). 색만 브랜드 토큰."""
    card = ('<div style="border:1px solid var(--rule);background:var(--paper-2);'
            'padding:14px 16px;background:var(--paper)">'
            '<div style="font-weight:800;margin-bottom:8px;font-size:.95rem">%s</div>%s</div>')
    return ('<div style="display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));'
            'margin:16px 0">' + card % (a_title, a_html) + card % (b_title, b_html) + '</div>')


def _report_svgs(html):
    flow6 = _svg_chain(['험지 설계', '강화학습', '미학습 지형\n평가', '개선·재학습',
                        '디지털 트윈\n구축', '렌더·시연\n영상'])
    trackb = _svg_chain(['ROS2 기초\nUbuntu 24.04', 'Go2 연결\nSDK·TF', 'SLAM\n맵핑·위치추정',
                         'Nav2\n자율주행', '험지 코스\n실기 시연'])
    loop = _svg_chain(['기준 정책\n분석', '학습 지형\n구성', '강화학습',
                       '학습·미학습\n지형 평가', '실패 원인\n분석', '지형·보상·물리\n조정'],
                      loop_back='재학습 반복')
    deploy = _svg_chain(['로봇 센서\n데이터', 'Observation\n생성', 'Policy\n추론',
                         'Joint 목표', 'Joint 제어', '실제 Go2'])
    drflow = _svg_chain(['기본 Policy\n평가', '취약점\n확인', '필요 Randomization\n추가',
                         '동일 환경에서\n효과 검증'])
    chips = lambda ws: ' '.join('<code>%s</code>' % w for w in ws)
    dirab = _card2('방향 A · Proprioception 중심',
                   '<p style="margin:.3rem 0;font-size:.85rem">실제 Robot 에서 직접 얻을 수 있는 정보로 Policy 를 구성한다.</p>'
                   '<p style="margin:.5rem 0">%s</p>'
                   '<p style="margin:.4rem 0;font-size:.8rem;color:var(--ink-2)"><b>검토점:</b> 구현 현실성이 높지만 '
                   '지형 사전 정보 없이 목표 성능을 낼 수 있는지 확인 필요</p>'
                   % chips(['IMU', 'Joint Position', 'Joint Velocity', 'Previous Action', 'Command']),
                   '방향 B · 외부 센서 활용',
                   '<p style="margin:.3rem 0;font-size:.85rem">LiDAR 또는 Depth Camera 로 주변 Terrain 정보를 생성해 Policy 입력에 포함한다.</p>'
                   '<p style="margin:.5rem 0">%s</p>'
                   '<p style="margin:.4rem 0;font-size:.8rem;color:var(--ink-2)"><b>검토점:</b> 지형 인지가 가능하지만 '
                   '센서 처리·동기화·지연과 구현 난이도가 증가</p>'
                   % chips(['LiDAR', 'Depth Camera', 'Terrain 정보']))
    navrl = _card2('Nav2 · 어디로 이동할 것인가',
                   '<p style="margin:.3rem 0;font-size:.85rem">SLAM 으로 구성된 지도와 센서 정보를 바탕으로 경로 및 '
                   '이동 명령을 생성한다. 출력인 <b>cmd_vel</b> 이 RL Policy 의 command 로 전달된다.</p>',
                   'RL Policy · 어떻게 걸을 것인가',
                   '<p style="margin:.3rem 0;font-size:.85rem">Nav2 의 이동 명령을 받아 실제 관절 제어를 수행하며, '
                   '지형 조건에 적응해 험지 보행을 담당한다.</p>')
    stats = ('<div style="display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin:6px 0 18px">'
             + ''.join('<div style="border:1px solid var(--rule);padding:12px 14px;background:var(--dim-soft)">'
                       '<div style="font-size:.66rem;font-weight:800;letter-spacing:.14em;color:var(--ink-3);text-transform:uppercase">%s</div>'
                       '<div style="font-weight:800;margin-top:4px">%s</div></div>' % kv
                       for kv in (('문서 용도', '팀 공유 · 미팅 의사결정'),
                                  ('중간 목표', '시뮬 RL + 디지털 트윈'),
                                  ('최종 목표', '순정 Go2 실기 자율주행'))) + '</div>')
    for mark, svg in (('flow6', flow6), ('loop', loop), ('deploy', deploy), ('trackb', trackb),
                      ('drflow', drflow), ('dirAB', dirab), ('navrl', navrl), ('stats', stats)):
        html = re.sub(r'<p>(?:<span class="vlink">)?%s(?:</span>)?</p>' % mark,
                      lambda m, s=svg: s, html)
    return html


# 원본 PDF 의 섹션 아이브로: «0N · EN TAG» 를 한글 제목 위에 단다
_RPT_TAGS = ['EXECUTIVE SUMMARY', 'WHY THIS PROJECT', 'MILESTONES', 'TRACK A · SIMULATION',
             'TRACK B · AUTONOMY', 'BRIDGE', 'OPERATIONS', 'DECISIONS REQUIRED', 'FINAL DEFINITION',
             'EVIDENCE LINKS']


def _report_eyebrows(html):
    def one(m):
        n = int(m.group(1))
        tag = _RPT_TAGS[n - 1] if n <= len(_RPT_TAGS) else 'SECTION'
        return ('<section id="s%d"><div class="rpt-eyebrow">%02d · %s</div><h2>' % (n, n, tag))
    return re.sub(r'<section id="s(\d+)"><h2>', one, html)


def find_lab():
    """자산(그림·CSV)을 가져올 기준 클론. 문서 자체는 collect_docs 가 전 후보를 훑는다."""
    best, n = None, -1
    for p in LAB_CANDIDATES:
        d = os.path.join(p, 'docs', PUBLISH_DIR)
        if os.path.isdir(d):
            c = len([f for f in os.listdir(d) if f.endswith('.md')])
            if c > n:
                best, n = p, c
    return best


def collect_docs():
    """모든 lab 후보 경로의 research 문서를 모아 파일명당 **가장 최신본**을 고른다.

    ★ 기기가 둘이라 클론도 둘이다(작업 클론 · 볼트 옆 미러). 첫 후보만 보면
      다른 쪽에만 있는 새 문서가 조용히 빠진다. 실제로 «컴퓨팅 자원 계획» 이
      그렇게 한 번 누락됐다(2026-08-13). 조용한 누락이 가장 나쁘다.
    """
    found = {}
    for p in LAB_CANDIDATES:
        d = os.path.join(p, 'docs', PUBLISH_DIR)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith('.md'):
                continue
            f = os.path.join(d, fn)
            m = buildtime.mtime(f)
            if fn not in found or m > found[fn][1]:
                found[fn] = (f, m)
    return dict(sorted((k, v[0]) for k, v in found.items()))


def chipify(html):
    """`확인됨` 같은 코드 표기를 증거 칩으로. 원문 표기가 곧 웹 표기가 된다."""
    def one(m):
        word = m.group(1)
        cls, label = CHIPS[word]
        return '<span class="ev ev-%s">%s</span>' % (cls, label)
    pat = re.compile(r'<code>(%s)</code>' % '|'.join(map(re.escape, CHIPS)))
    return pat.sub(one, html)


def writer_of(md):
    """메타 5줄의 «> 작성: 이름 · YYYY-MM-DD HH:MM» 을 그대로 돌려준다.

    ★ 2026-08-28 팀장 지적: 「연구 문서마다 발행일 날짜 시간도 하라고 했는데
      하나도 안 지켜졌다」. 두 겹의 문제였다.
        (1) 원본 md 27개 중 23개에 시각이 없었다 -> git 최초 커밋 시각으로 메웠다
        (2) **회의록·다이제스트·현장 페이지는 「작성」 줄 자체를 안 보여줬다**
            연구 페이지만 보여주고 있었다. 읽는 사람은 언제 것인지 알 수 없었다.
      읽는 곳을 하나로 만든다. 게시기마다 따로 뽑으면 또 한 곳이 빠진다.
    """
    m = re.search(r'^>\s*작성\s*:\s*(.+?)$', md, re.M)
    return m.group(1).strip() if m else '미기재'


_VERS = {}


def _vers():
    """판 원장. 한 번만 읽는다 (#112)."""
    if not _VERS:
        lab = next((x for x in LAB_CANDIDATES
                   if os.path.isdir(os.path.join(x, 'docs'))), None)
        p = os.path.join(lab or '', 'docs', 'ops', 'versions.json')
        if lab and os.path.isfile(p):
            import json
            try:
                _VERS.update(json.load(io.open(p, encoding='utf-8')))
            except ValueError:
                pass
        _VERS.setdefault('__loaded__', 1)
    return _VERS


def ver_of(md, rel=None):
    """화면에 세울 판.

    ★ #112. 정본은 `docs/ops/versions.json` 원장이다. md 의 «> 판:» 은
      사람이 선언하는 큰 판만 뜻하고, 소수점은 빌드가 붙인다.
      원장에 없으면(새 문서) md 가 적은 것을 그대로 쓴다.
    """
    if rel:
        e = _vers().get(rel)
        if e and e.get('ver'):
            return e['ver']
    m = re.search(r'^>\s*판\s*:\s*(v[\d.]+)\s*$', md, re.M)
    return m.group(1) if m else ''

def issue_of(md):
    """머리의 «> 이슈: #94 #100» 을 돌려준다 (#111).

    ★ 팀장 9/1: 「문서가 어떤 이슈를 따르는지 파악이 되어있고 기재가
      되어있는지」. 없으면 빈 문자열이고, 관문이 아직 경고만 낸다.
    """
    m = re.search(r'^>\s*이슈\s*:\s*(.+)$', md, re.M)
    return ' '.join(re.findall(r'#\d{1,4}', m.group(1))) if m else ''


def lede_of(md):
    """상단 요약 추출. «> 요지:» 가 있으면 그것이 정본이다.

    없으면 첫 인용줄을 쓰되, «작성 …» 같은 메타 줄은 요약이 아니므로 건너뛴다.
    (일부 문서 상단에 날짜 줄이 요약처럼 떠 있던 문제의 원인이었다: 팀장 지적 2026-08-12)
    """
    m = re.search(r'^>\s*요지:\s*(.+)$', md, re.M)
    if m:
        return re.sub(r'[*`\[\]]', '', m.group(1)).strip()[:160]
    for line in md.split('\n'):
        t = line.strip()
        if t.startswith('>') and len(t) > 6:
            t = re.sub(r'^>+\s*', '', t)
            if re.match(r'^(작성|갱신|범위|상태|시작|v\d)', t):
                continue
            t = re.sub(r'[*`\[\]]|\(\.\./[^)]*\)', '', t)
            return t[:160]
    for line in md.split('\n'):
        t = line.strip()
        if t and not t.startswith(('#', '>', '-', '|', '!')):
            return re.sub(r'[*`]', '', t)[:160]
    return ''


def shell(title, eyebrow, lede, body, meta_rows, doc_label,
          home_href='index.html', home_label='← 표지로', stand=''):
    # 개별 연구 문서의 «뒤로»는 표지가 아니라 목록(research.html)으로 보낸다.
    #   표지로 튕겨 나가 목록을 다시 찾아 들어가는 동선을 팀장이 지적했다(2026-08-12).
    metas = ''.join('<div><span class="k">%s</span><span class="v">%s</span></div>' % kv
                    for kv in meta_rows)
    # ★ 2026-08-29. 「이 글이 선 자리」를 본문 «앞»에 둔다. 독자는 허브나
    #   검색에서 문서 하나에 곧바로 떨어지므로, 읽기 전에 위치를 알아야 한다.
    body = (stand or '') + body
    return (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>%s · FOOTHOLD</title>\n'
        '<meta name="description" content="%s">\n'
        '<style>%s%s</style>\n</head>\n<body>\n\n'
        '<div class="top"><div class="row">'
        '<a class="home" href="%s">%s</a>'
        '<span class="doc">%s</span><span class="sp"></span>'
        '<button class="pdfbtn" id="pdfBtn" type="button">PDF 저장</button>'
        '</div><div id="prog"></div></div>\n\n'
        '<div class="wrap">\n\n<div class="hero">\n'
        '  <div class="eyebrow">%s</div>\n  <h1>%s</h1>\n'
        '  <p class="lede">%s</p>\n  <div class="meta">%s</div>\n'
        '  <div class="evlegend"><span><span class="ev ev-ok">확인됨</span> 직접 확인·실측</span>'
        '<span><span class="ev ev-guess">추측</span> 근거는 있으나 미검증</span>'
        '<span><span class="ev ev-todo">미측정</span> 아직 하지 않음</span></div>\n'
        '</div>\n\n%s\n\n</div>\n<script>%s</script>\n</body>\n</html>\n'
        % (title, lede.replace('"', "'")[:150], team_access.CSS, CHIP_CSS,
           home_href, home_label,
           doc_label, eyebrow, title, lede, metas, body, team_access.JS))


def build():
    lab = find_lab()
    if not lab:
        print('  [!] foothold-lab 클론 없음. 문서 게시 건너뜀')
        return []

    src_dir = os.path.join(lab, 'docs', PUBLISH_DIR)
    made, cards, skipped = [], [], []

    # ★ 문서가 참조하는 그림을 함께 옮긴다.
    #   이게 없어서 «시각 증거» 페이지의 이미지가 전부 404 였다(2026-08-12).
    #   문서만 게시하고 그림을 두고 오면, 페이지는 200 인데 내용이 비어 있다. 조용한 실패다.
    #   영상(mp4)은 옮기지 않는다. lab 은 LFS 로 갖고 있지만 웹에 얹기엔 무겁다.
    n_img = 0
    for sub in ('visual', 'eval', 'video'):
        s = os.path.join(lab, 'docs', 'assets', sub)
        if not os.path.isdir(s):
            continue
        d = os.path.join(VAULT, 'assets', sub)
        os.makedirs(d, exist_ok=True)
        for f in sorted(os.listdir(s)):
            if os.path.splitext(f)[1].lower() not in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.csv', '.mp4'):
                continue
            sp, dp = os.path.join(s, f), os.path.join(d, f)
            if (not os.path.exists(dp)) or buildtime.mtime(sp) > buildtime.mtime(dp) \
                    or os.path.getsize(sp) != os.path.getsize(dp):
                shutil.copy2(sp, dp)
            n_img += 1
    print('  자산 %d개 반영 (assets/visual · assets/eval)' % n_img)

    docs = collect_docs()
    extra = [k for k in docs if not os.path.exists(os.path.join(src_dir, k))]
    if extra:
        print('  다른 클론에서 추가로 발견: %s' % ', '.join(extra))
    for fn, path in docs.items():
        md = io.open(path, encoding='utf-8').read()
        slug = fn[:-3]

        # 문서 간 .md 링크를 웹 링크로 재작성. 안 하면 (xxx.md) 가 죽은 글자로 게시된다
        #   (2026-08-13 실측: omniverse-stack 등 3편에서 링크가 텍스트로 나가고 있었다).
        #   대상 md 가 실제로 있을 때만 바꾼다: 죽은 링크를 새로 만들지 않는다.
        def _weblink(m):
            return ('](research-%s.html)' % m.group(1)
                    if (m.group(1) + '.md') in docs
                    else m.group(0))
        md = re.sub(r'\]\(([a-z0-9-]+)\.md\)', _weblink, md)
        for a, b in (('](../FLOW.md)', '](flow.html)'), ('](../COLLAB.md)', '](collab.html)'),
                     ('](../QUESTIONS.md)', '](questions.html)')):
            md = md.replace(a, b)

        ok, why = publishable(md)
        if not ok:
            skipped.append((slug, why))
            continue

        title = mdpage.h1(md)
        if title == '문서':
            skipped.append((slug, 'h1 제목 없음'))
            continue

        # ★ 2026-08-28. 대외비 금액 가림이 운영 문서(ops_pages)에만 걸려 있었다.
        #   연구 문서는 그냥 나갔고, runpod-team-ops 에 우리 «지출 한도»와
        #   «청구액»이 공개 웹에 실려 있었다. 게시하는 모든 경로에 같은 문을 단다.
        md = redact.apply(md, 'foothold-lab / docs/%s/%s' % (PUBLISH_DIR, fn))
        lede = lede_of(md)
        body = chipify(mdpage.render(md.split('\n', 1)[1] if md.startswith('#') else md))
        counts = {k: len(re.findall(r'<span class="ev ev-%s">' % v[0], body))
                  for k, v in (('확인', ('ok', '')), ('추측', ('guess', '')), ('미측정', ('todo', '')))}
        if sum(counts.values()) == 0:
            print('  [경고] %s: 증거 표기(`확인됨`/`추측`)가 하나도 없음' % slug)

        # 작성: 메타 5줄의 «> 작성: 이름 · YYYY-MM-DD HH:MM» 이 원본이다.
        #   2026-08-27: 전에는 날짜만 읽어서, 표준을 지킨 문서일수록 카드에
        #   이름이 안 보였다. 누가 썼는지 모르면 물어볼 사람을 모른다.
        wm = re.search(r'^>\s*작성\s*:\s*(.+?)$', md, re.M)
        writer = wm.group(1).strip() if wm else ''
        dm = re.search(r'(\d{4}-\d{2}-\d{2})', writer) if writer else None
        if not dm:                                   # 옛 형식 (날짜만)
            dm = re.search(r'작성\s*(\d{4}-\d{2}-\d{2})', md)
            writer = dm.group(1) if dm else ''
        wdate = dm.group(1) if dm else '9999-99-99'

        out = PREFIX + slug + '.html'
        io.open(os.path.join(VAULT, out), 'w', encoding='utf-8', newline='\n').write(
            shell(title, 'Research · 근거 기록', lede, body,
                  ([('판', ver_of(md))] if ver_of(md) else []) +
                  ([('이슈', issue_of(md))] if issue_of(md) else []) +[('작성', writer if writer else '미기재'),
                   ('원본', 'foothold-lab / docs / %s / %s' % (PUBLISH_DIR, fn)),
                   ('증거', '확인 %d · 추측 %d · 미측정 %d'
                    % (counts['확인'], counts['추측'], counts['미측정']))],
                  'FOOTHOLD · 연구 기록',
                  home_href='research.html', home_label='← 연구 기록으로',
                  # ★ 2026-08-29. 온톨로지의 참조 관계를 화면에서 처음 쓰는 자리.
                  #   85개를 뽑아 놓고 아무 데도 안 쓰고 있었다.
                  stand=''))  # 결정 20260830-hub-v3: 상단 블록 제거, 관계는 화면 뒤에서만
        made.append(out)
        # 대표 그림: 문서가 처음 부르는 이미지를 쓴다. 카드가 «무엇에 관한 글인지»를
        #   제목보다 빨리 말해준다. 그림이 없는 문서는 글자 카드로 남는다.
        mt = re.search(r'<img[^>]+src="([^"]+)"', body)
        cards.append((out, title, lede, counts, mt.group(1) if mt else None, wdate))

    # ★ 연구가 진행된 순서가 보이게: 작성일 오름차순으로 정렬하고 번호를 단다 (팀장 2026-08-12)
    cards.sort(key=lambda x: (x[5], x[0]))

    # ── 주간 다이제스트: docs/digest/*.md (컨펌 2026-08-12) ──
    #    주간 리포트(무엇을 했나)와 다른 문서: «무엇을 알게 됐나»만. 최신 것이 목록 상단에 걸린다
    dg_dir = os.path.join(lab, 'docs', 'digest')
    digests = []
    if os.path.isdir(dg_dir):
        for fn in sorted(os.listdir(dg_dir)):
            if not fn.endswith('.md'):
                continue
            dmd = io.open(os.path.join(dg_dir, fn), encoding='utf-8').read()
            dtitle = mdpage.h1(dmd)
            dbody = chipify(mdpage.render(dmd.split('\n', 1)[1] if dmd.startswith('#') else dmd))
            dout = 'digest-' + fn[:-3] + '.html'
            io.open(os.path.join(VAULT, dout), 'w', encoding='utf-8', newline='\n').write(
                shell(dtitle, 'Digest · 이번 주 알게 된 것', lede_of(dmd), dbody,
                      [('작성', writer_of(dmd)),
                       ('원본', 'foothold-lab / docs / digest / %s' % fn)],
                      'FOOTHOLD · 주간 다이제스트',
                      home_href='research.html', home_label='← 연구 기록으로'))
            made.append(dout)
            digests.append((dout, dtitle))

    # ── 질문 지도: docs/QUESTIONS.md → questions.html (컨펌 2026-08-12) ──
    qp = os.path.join(lab, 'docs', 'QUESTIONS.md')
    if os.path.exists(qp):
        qmd = io.open(qp, encoding='utf-8').read()
        qbody = chipify(mdpage.render(qmd.split('\n', 1)[1] if qmd.startswith('#') else qmd))
        io.open(os.path.join(VAULT, 'questions.html'), 'w', encoding='utf-8', newline='\n').write(
            shell(mdpage.h1(qmd), 'Guide · 질문으로 찾기', lede_of(qmd), qbody,
                  ([('판', ver_of(qmd))] if ver_of(qmd) else []) +
                  ([('이슈', issue_of(qmd))] if issue_of(qmd) else []) +[('작성', writer_of(qmd)),
                   ('원본', 'foothold-lab / docs / QUESTIONS.md')],
                  'FOOTHOLD · 질문으로 찾기'))
        made.append('questions.html')

    # ── 프로젝트 보고서: docs/REPORT.md → project-report.html (팀장 지시 2026-08-19) ──
    #    한 장으로 프로젝트 전체를 설명하는 페이지. 멘토에게 보여주는 용도.
    rp = os.path.join(lab, 'docs', 'REPORT.md')
    if os.path.exists(rp):
        rmd = io.open(rp, encoding='utf-8').read()
        # ★ 2026-08-28. 게시 여부를 안 보는 손 치환을 뺐다. mdlinks 가 맡는다.
        #   (회의록에서 이 치환 때문에 폐기 문서로 가는 죽은 링크가 나갔다)
        # 보고서형 스킨: h2 의 «1. » 번호를 떼고 CSS 카운터(01·02…)가 크게 단다
        rmd = re.sub(r'^## \d+\.\s*', '## ', rmd, flags=re.M)
        rbody = chipify(mdpage.render(rmd.split('\n', 1)[1] if rmd.startswith('#') else rmd))
        # 원본 PDF 의 시각 언어(단계 흐름 도식)를 SVG 로 복원 (팀장 지적 2026-08-19).
        #   md 는 SVG 를 못 담으므로 마커를 렌더 후 치환한다.
        rbody = _report_svgs(rbody)
        rpage = shell(mdpage.h1(rmd), 'Report · 프로젝트 보고서', lede_of(rmd), rbody,
                      [('원자료', '임석헌(부팀장) 정리 보고서 2026-08-18'),
                       ('일정', '중간 9/30 · 최종 12/11')],
                      'FOOTHOLD · 프로젝트 보고서')
        # 보고서형 스킨 v2 (팀장 지시 2026-08-19: 원본 PDF 포맷 그대로, 색만 브랜드).
        #   백지 흐름 + 섹션 아이브로(0N · EN TAG) + 상단 굵은 보더 카드 + 회색 콜아웃 + 번호칩 안건.
        rpage = _report_eyebrows(rpage)
        rpage = rpage.replace('</head>', '''<style>
.wrap section{margin:34px 0;padding-top:22px;border-top:1px solid var(--rule)}
.rpt-eyebrow{font-size:.7rem;font-weight:800;letter-spacing:.22em;color:var(--ink-3);
  text-transform:uppercase;margin-bottom:6px}
.wrap section>h2{margin:0 0 14px;padding:0;border:none;font-size:1.35rem;font-weight:800}
.wrap section h3{margin:1.4rem 0 .5rem;font-size:1.02rem;font-weight:800}
.wrap section blockquote{background:var(--paper-2);border-left:4px solid var(--ink);
  padding:13px 18px;margin:16px 0;font-style:normal;border-radius:0}
.wrap section blockquote h3{margin:.1rem 0 .4rem;font-size:.72rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--dim)}
.wrap section ol{counter-reset:agd;list-style:none;padding-left:0}
.wrap section ol>li{counter-increment:agd;margin:.7rem 0;padding-left:2.5rem;position:relative}
.wrap section ol>li::before{content:counter(agd,decimal-leading-zero);position:absolute;
  left:0;top:.1rem;background:var(--ink);color:var(--paper);font-size:.68rem;font-weight:800;
  padding:.18rem .42rem;border-radius:3px;letter-spacing:.06em}
.wrap section code{background:var(--paper);border:1px solid var(--rule);border-radius:4px;
  padding:.14rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}
</style></head>''', 1)
        io.open(os.path.join(VAULT, 'project-report.html'), 'w', encoding='utf-8', newline='\n').write(rpage)
        made.append('project-report.html')

    # ── 현장 확인 목록: docs/FIELD-CHECK-*.md → field-check-*.html ──
    #    방문 당일 폰으로 열고, PDF 저장 버튼으로 종이로도 들고 간다
    for fn in sorted(os.listdir(os.path.join(lab, 'docs'))):
        if not (fn.startswith('FIELD-CHECK') and fn.endswith('.md')):
            continue
        fmd = io.open(os.path.join(lab, 'docs', fn), encoding='utf-8').read()
        # 웹에서 살아있는 링크로 재작성: research/*.md → research-*.html, FLOW.md → flow.html.
        # 내부 볼트(MAI_UNIVERSE) 링크는 웹에 존재하지 않으므로 링크를 풀어 텍스트만 남긴다.
        # ★ 2026-08-28. 게시 여부를 안 보는 손 치환을 뺐다. mdlinks 가 맡는다.
        fmd = re.sub(r'\[([^\]]+)\]\((?:\.\./)*MAI_UNIVERSE/[^)]*\)', r'\1 (내부 볼트)', fmd)
        fbody = chipify(mdpage.render(fmd.split('\n', 1)[1] if fmd.startswith('#') else fmd))
        fout = fn[:-3].lower() + '.html'
        io.open(os.path.join(VAULT, fout), 'w', encoding='utf-8', newline='\n').write(
            shell(mdpage.h1(fmd), 'Field · 현장 확인 목록', lede_of(fmd), fbody,
                  ([('판', ver_of(fmd))] if ver_of(fmd) else []) +
                  ([('이슈', issue_of(fmd))] if issue_of(fmd) else []) +[('작성', writer_of(fmd)),
                   ('원본', 'foothold-lab / docs / %s' % fn),
                   ('사용법', '현장에서 폰으로 열거나, 우상단 PDF 저장으로 인쇄')],
                  'FOOTHOLD · 현장 확인'))
        made.append(fout)

    # ── 회의 기록: docs/meetings/*.md → meeting-*.html (팀장 지시 2026-08-20) ──
    #    운영·협력 회의의 확정 사항만 공개 게시. 상세 전사·화자 기록은 내부 볼트에 남는다
    mt_dir = os.path.join(lab, 'docs', 'meetings')
    if os.path.isdir(mt_dir):
        for fn in sorted(os.listdir(mt_dir)):
            if not fn.endswith('.md') or fn == 'README.md':
                continue
            mmd = io.open(os.path.join(mt_dir, fn), encoding='utf-8').read()
            # ★ 2026-08-28. 여기에 손으로 쓴 「research/x.md -> research-x.html」
            #   치환이 있었다. 그 치환은 대상이 «실제로 게시되는가» 를 안 본다.
            #   그래서 상태가 「폐기」 라 웹에서 내린 문서에도 주소를 만들어
            #   죽은 링크가 됐다. mdlinks 가 바로 이 중복을 없애려고 만든 것이다.
            mmd = re.sub(r'\]\(([0-9a-z-]+)\.md\)', r'](meeting-\1.html)', mmd)
            mmd = re.sub(r'\[([^\]]+)\]\((?:\.\./)*MAI_UNIVERSE/[^)]*\)', r'\1 (내부 볼트)', mmd)
            mbody = chipify(mdpage.render(mmd.split('\n', 1)[1] if mmd.startswith('#') else mmd))
            mout = 'meeting-' + fn[:-3].lower() + '.html'
            io.open(os.path.join(VAULT, mout), 'w', encoding='utf-8', newline='\n').write(
                shell(mdpage.h1(mmd), 'Meeting · 회의 기록', lede_of(mmd), mbody,
                      ([('판', ver_of(mmd))] if ver_of(mmd) else []) +
                      ([('이슈', issue_of(mmd))] if issue_of(mmd) else []) +[('작성', writer_of(mmd)),
                       ('원본', 'foothold-lab / docs / meetings / %s' % fn),
                       ('상세', '전체 전사·화자 기록은 내부 볼트 00_meetings')],
                      'FOOTHOLD · 회의 기록'))
            made.append(mout)

    # 목록 페이지. 새 문서가 늘면 여기도 저절로 늘어난다
    def _card(no, h, t, l, c, thumb, wdate):
        head = ('<div class="rthumb"><img src="%s" alt="" loading="lazy"></div>' % thumb) if thumb else ''
        dtxt = wdate if wdate != '9999-99-99' else '작성일 미기재'
        return ('<a class="rcard%s" href="%s">%s<div class="rbody">'
                '<div class="rt"><span class="rno">%02d</span> %s</div>'
                '<div class="rd">%s</div>'
                '<div class="rm">%s · 확인 %d · 추측 %d · 미측정 %d</div></div></a>'
                % (' has-thumb' if thumb else '', h, head, no, t, l,
                   dtxt, c['확인'], c['추측'], c['미측정']))

    items = ''.join(_card(i + 1, h, t, l, c, th, wd)
                    for i, (h, t, l, c, th, wd) in enumerate(cards))
    # 목록 상단 배너: 최신 다이제스트만 («어디부터 보나»의 답). 질문 지도는 표지에 산다
    banner = ''
    if digests:
        dh, dt = digests[-1]
        banner = ('<div class="dgbar"><a href="%s"><span class="k">Digest</span>'
                  '<b>%s</b><span>5분 요약 · 팀 공유용</span></a></div>' % (dh, dt))
    io.open(os.path.join(VAULT, INDEX), 'w', encoding='utf-8', newline='\n').write(
        shell('연구 기록', 'Research · 우리가 직접 확인한 것',
              '조사와 실측의 원본 기록이다. 결론만이 아니라 <b>틀렸던 판단과 그 정정</b>도 남긴다. '
              '번복의 이력이 곧 검증의 증거다.',
              banner + '<div class="rcards">%s</div>' % items,
              [('문서', '%d편' % len(cards)),
               ('원본', 'foothold-lab / docs / %s/' % PUBLISH_DIR),
               ('갱신', '문서가 올라오면 다음 빌드에 자동 반영')],
              'FOOTHOLD · 연구 기록'))
    made.append(INDEX)

    print('  게시 %d편 + 목록 1 · 건너뜀 %d' % (len(cards), len(skipped)))
    for s, why in skipped:
        print('     - %s (%s)' % (s, why))
    return made, cards


SEC_OPEN, SEC_CLOSE = '<!--research:auto-->', '<!--/research:auto-->'


def _front_picks(vault, limit=4):
    """표지에 세울 문서. 온톨로지의 «노출 가치» 가 정한다.

    ★ 손으로 고르지 않는다. 고르면 낡는다.
      `web_worthy` 가 「높음」 이고 `stale` 이 비어 있는 것만, 인용 많은 순으로.
      노출 가치는 사람이 뒤집을 수 있고(overrides) 그 값이 이긴다.
    """
    import json
    lab = next((x for x in LAB_CANDIDATES
               if os.path.isdir(os.path.join(x, 'docs'))), None)
    if not lab:
        return []
    gp = os.path.join(lab, 'docs', 'ops', 'doc-graph.json')
    if not os.path.isfile(gp):
        return []
    try:
        g = json.load(io.open(gp, encoding='utf-8'))
    except Exception:
        return []
    import mdlinks
    out = []
    for d in sorted(g, key=lambda x: -len(x.get('children') or [])):
        if d.get('web_worthy') != '높음' or d.get('stale'):
            continue
        page = mdlinks.resolve('docs/' + d['path'])
        if not page or not vault or not os.path.exists(os.path.join(vault, page)):
            continue
        kind = d.get('kind') or '문서'
        area = ' · '.join(a.split('/')[1] for a in (d.get('areas') or [])) or '전체'
        out.append((page, '%s · %s' % (kind, area),
                    d.get('title') or page, (d.get('purpose_reason') or '')[:96]))
        if len(out) >= limit:
            break
    return out


def index_section(cards, vault=None):
    """표지에 넣을 '연구 기록' 섹션. 최신 3편 + 길잡이 카드 + 전체보기.

    길잡이(질문으로 찾기)는 사이트 전역 안내라 연구 목록이 아니라 표지에 산다
    (팀장 컨펌 2026-08-12). 현장 확인 목록은 존재하는 동안만 카드가 뜬다.
    """
    items = ''.join(
        '<a class="doc" href="%s"><div class="tag">Research · 근거 기록</div>'
        '<div class="t">%s</div><div class="d">%s</div></a>' % (h, t, l)
        for h, t, l, _c, _th, _wd in list(reversed(cards))[:3])
    guides = ''
    if vault and os.path.exists(os.path.join(vault, 'project-report.html')):
        guides += ('<a class="doc" href="project-report.html"><div class="tag">Report · 보고서</div>'
                   '<div class="t">프로젝트 보고서</div>'
                   '<div class="d">한 장으로 보는 전체 계획: 목표 · 단계 · 평가 체계 · 결정 안건. '
                   '멘토에게 보여줄 때 이 페이지부터.</div></a>')
    if vault and os.path.exists(os.path.join(vault, 'pitch.html')):
        # ★ 장수를 손으로 적지 않는다. 「10장」으로 박아두고 덱이 12장이 된 채
        #   웹에 나가 있었다(2026-08-26). 원천에서 센다.
        import selfclaim
        n_slides = selfclaim.count_slides(
            io.open(os.path.join(vault, 'pitch.html'), encoding='utf-8').read())
        guides += ('<a class="doc" href="pitch.html"><div class="tag">Deck · 발표</div>'
                   '<div class="t">프로젝트 소개 덱 (%d장)</div>'
                   '<div class="d">전체화면 발표용. 킥오프·외부 소개는 이 페이지 하나로. '
                   '방향키나 클릭으로 넘긴다.</div></a>' % n_slides)
    guides += ('<a class="doc" href="questions.html"><div class="tag">Guide · 길잡이</div>'
              '<div class="t">질문으로 찾기</div>'
              '<div class="d">«이 정보 어디 있지?»에 답하는 지도. '
              '궁금한 문장을 찾아 누르면 해당 문서로 바로 간다.</div></a>')
    if vault and os.path.exists(os.path.join(vault, 'chosun-materials.html')):
        guides += ('<a class="doc" href="chosun-materials.html"><div class="tag">Team · 팀 전용</div>'
                   '<div class="t">팀 자료실 (암호)</div>'
                   '<div class="d">조선대 수업 자료 + 팀 내부 문서(예산). 비밀번호 필요 (디스코드 리소스 채널). '
                   '외부 공유 금지.</div></a>')
    # ★ 2026-08-29 (#76 · #89). 여기서 회의록과 현장 문서를 «전부» 훑어 넣었다.
    #   그래서 표지 「길잡이」 절에 14개가 쌓였고 그중 8개가 회의록이었다.
    #   회의 허브에 이미 있는 것을 표지가 통째로 다시 건 것이다. 중복 노출이다.
    #
    #   이제 온톨로지의 «노출 가치» 축으로 고른다. 조건 둘을 다 만족해야 표지에 선다.
    #     노출 가치 「높음」  ·  폐기된 사실을 안 안고 있을 것
    #   그 값은 doc-graph.json 에 있고 매 빌드마다 다시 그려진다. 손 목록이 아니다.
    for href, tag, title, why in _front_picks(vault):
        guides += ('<a class="doc" href="%s"><div class="tag">%s</div>'
                   '<div class="t">%s</div><div class="d">%s</div></a>'
                   % (href, tag, title, why))
    # ★ 2026-08-29 (#76 3번 · 6-7). 「길잡이」 절을 폐지했다.
    #   다른 절의 문서를 다시 가리키는 절이라 층위가 섞였고, 표지에서 같은 글이
    #   두 번 보였다. 그 카드들은 「참고」 절로 갔다.
    #   이 생성기는 이제 «연구 기록» 한 절만 내보낸다.
    br = chr(10)
    return (SEC_OPEN + br +
            '<h2 class="sec">연구 기록 <span class="en">Research</span></h2>' + br +
            '<p class="lede" style="margin:-2px 0 14px;font-size:.82rem;'
            'color:var(--ink-3)">우리가 직접 재서 나온 숫자. 이 프로젝트의 근거다.</p>' + br +
            ('<div class="docs work">%s</div>' % items) + br +
            '<p style="margin:2px 0 26px;font-size:.8rem">'
            '<a href="%s" style="color:var(--dim);font-weight:700">전체 %d편 보기 →</a></p>'
            % (INDEX, len(cards)) + br + SEC_CLOSE)


def inject_index(vault, cards):
    """표지에 섹션을 넣거나 갱신한다. 문서가 늘면 여기도 저절로 갱신된다.

    ★ 마커로 감싼 구역만 통째로 갈아끼운다. 사람이 쓴 나머지 표지 내용은 건드리지 않는다.
    """
    p = os.path.join(vault, 'index.html')
    if not (cards and os.path.exists(p)):
        return False
    s = io.open(p, encoding='utf-8').read()
    # 결정 20260830-hub-v3: 표지의 연구 기록 절은 없앤다 (삼중 겹침).
    # 마커째 지워 과거 표지에서도 사라지게 한다.
    sec = ''
    if SEC_OPEN in s and SEC_CLOSE in s:
        a, b = s.index(SEC_OPEN), s.index(SEC_CLOSE) + len(SEC_CLOSE)
        if s[a:b] == sec:
            return False
        s = s[:a] + sec + s[b:]
    else:
        return False                # 절이 폐지됐다. 마커가 없으면 할 일도 없다
    io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
    return True
