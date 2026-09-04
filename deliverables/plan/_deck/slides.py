# -*- coding: utf-8 -*-
"""FOOTHOLD 9/4 기획 발표 덱 17장.

  숫자는 정본에서만 온다.
    sim/eval/results/20260903-rough10-1.0mps/summary-thr1.5.csv   미경험 험지 10종
    sim/eval/results/20260903-flat-10m-spec20s/                   평지 기준선
  브랜드 자산 = foothold-brand/assets/logo/v1 · 서체 Pretendard 내장.
  금지: 평지 20초·10 m 와 험지 6초·3 m 혼용 · RAILS 표기 · GPS 서사 · em dash · 외부 서체
  바닥 띠에 편집 메모를 쓰지 않는다. 소속과 쪽 번호만 둔다.
"""
import io
import json
import hashlib
import base64
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(io.open(os.path.join(HERE, 'assets.json'), encoding='utf-8'))
# 폰트와 영상은 base64 로 박아두지 않고 원본에서 그때그때 만든다.
# 박아두면 원본이 바뀌어도 눈치채지 못하고, 무엇이 들어갔는지도 알 수 없다.
# 영상 교체는 저장소의 720p 사본을 갱신하고 이 스크립트를 한 번 돌리면 끝난다.
FONT_FILE = os.path.join(HERE, 'PretendardVariable.woff2')
MP4_FILE = os.path.join(HERE, os.pardir, 'assets', 'foothold-roughcut-720.mp4')
POSTER_FRAME = 45          # 군집이 자리를 잡은 뒤. 인쇄본은 이 정지 화면을 쓴다

if 'font' not in A:
    A['font'] = base64.b64encode(io.open(FONT_FILE, 'rb').read()).decode()

if 'army_mp4' not in A:
    import av
    from PIL import Image
    _raw = io.open(MP4_FILE, 'rb').read()
    A['army_mp4'] = 'data:video/mp4;base64,' + base64.b64encode(_raw).decode()
    _c = av.open(MP4_FILE)
    _st = _c.streams.video[0]
    _f = [f for i, f in enumerate(_c.decode(_st)) if i <= POSTER_FRAME]
    _c.close()
    assert len(_f) > POSTER_FRAME, '영상이 %d프레임보다 짧다' % POSTER_FRAME
    _im = _f[POSTER_FRAME].to_image().resize((1280, 720), Image.LANCZOS)
    _b = io.BytesIO()
    _im.save(_b, 'JPEG', quality=82, optimize=True)
    A['army_poster'] = base64.b64encode(_b.getvalue()).decode()
    print('  영상 %.2f MB · sha %s · 포스터 %d번 프레임'
          % (len(_raw) / 1e6, hashlib.sha256(_raw).hexdigest()[:12], POSTER_FRAME))
ORG = '인공지능사관학교 7기 · AI Physical 실증 2팀'
TOTAL = 19


def img(key, alt, cls=''):
    src = A[key] if A[key].startswith('data:') else 'data:image/jpeg;base64,' + A[key]
    return '<img src="%s" alt="%s"%s>' % (src, alt, (' class="%s"' % cls) if cls else '')


def lockup(surface):
    return img('lockup_dark' if surface == 'night' else 'lockup_light', 'FOOTHOLD', 'lk')


TEN = [('discrete', 'Discrete', 97, 'ok'), ('wave', 'Wave', 100, 'ok'),
       ('star', 'Star', 100, 'ok'), ('boxes', 'Boxes', 100, 'ok'),
       ('cylinders', 'Cylinders', 100, 'ok'),
       ('rails', 'rails(턱·장애물)', 4, 'stall'), ('pit', 'pit(구덩이)', 3, 'stall'),
       ('stones', 'stones(디딤돌)', 0, 'fall'), ('gap', 'gap(틈)', 0, 'fall'),
       ('ring', 'ring(뜬 고리)', 0, 'stall')]

FAIL = [('stepping_stones(디딤돌)', '오현민', 'fall', 0, 20, 1.05),
        ('gap(틈)', '임석헌', 'fall', 0, 21, 0.92),
        ('rails(턱·장애물 극복)', '맹라현', 'stall', 4, 85, 2.64),
        ('pit(구덩이)', '이민우', 'stall', 3, 97, 1.57),
        ('floating_ring(뜬 고리)', '오흥재', 'stall', 0, 86, 1.06)]

SL = []


def slide(n, surface, inner, band=None):
    SL.append((n, surface, band or surface, inner))


def foot(n):
    return '<div class="ft"><em>%s</em><b>%02d / %d</b></div>' % (ORG, n, TOTAL)


def frame(n, surface, eyebrow, title, sub, body, tcls='t-lg', cond=None, top0=False):
    return ('<div class="pad">'
            '<div class="hd">%s<div class="eyebrow">%s</div></div>'
            '<div class="body%s"><div><h2 class="%s">%s</h2>%s%s</div>%s</div>%s</div>'
            % (lockup(surface), eyebrow, ' top0' if top0 else '', tcls, title,
               ('<p class="sub">%s</p>' % sub) if sub else '',
               ('<p class="cond">%s</p>' % cond) if cond else '',
               ('<div class="gap">%s</div>' % body) if body else '',
               foot(n)))


# 01 표지 · 로봇 없는 지형 배경 ─────────────────────────────────────────────
slide(1, 'night',
      '<div class="hero">%s<div class="veil l"></div></div>'
      '<div class="pad" style="justify-content:space-between">'
      '<div class="org">%s</div>'
      '<div><div class="lockup-hero">%s%s</div>'
      '<p class="claim">현실에서 발을 내딛기 전에,<br>시뮬레이션에서 다음 한 발을 검증한다.</p></div>'
      '<div class="org">2026-09-04 기획 발표</div></div>'
      % (img('bg', '안개 낀 지형과 멀리 보이는 목표 불빛'), ORG,
         img('symbol_rev', '', 'sym'), img('wordmark_rev', 'FOOTHOLD', 'wm')), band='video')

# 02 팀 소개 ─────────────────────────────────────────────────────────────
MEMBERS = [('오흥재', 'B/항법 · C/운영', '프로젝트 리딩과 실기 항법, 팀 인프라'),
           ('임석헌', 'A/정책학습', '강화학습 정책과 보상 설계, 학습 반복'),
           ('맹라현', 'A/지형씬제작 · A/트윈렌더', '시뮬 지형 제작과 실공간 복원, 렌더'),
           ('오현민', 'A/평가 · B/인지', '평가 하네스와 지표, LiDAR 카메라 인지'),
           ('이민우', 'B/항법 · C/기록', 'SLAM 과 Nav2 자율 보행, 정본 기록')]
slide(2, 'paper', frame(
    2, 'paper', '팀', 'TEAM FOOTHOLD',
    '강화학습, 시뮬레이션, 인지, 항법, 기록을 한 사람이 하나씩 맡아 각자 대체 불가능한 축을 갖는다.',
    '<div class="people">%s</div>'
    % ''.join('<div class="pcard"><b>%s</b><i>%s</i><span>%s</span></div>' % m for m in MEMBERS),
    tcls='t-xl'))

# 02 명제 ─────────────────────────────────────────────────────────────────
slide(3, 'night',
      '<div class="pad"><div class="hd">%s<div class="eyebrow">문제</div></div>'
      '<div class="body"><div>'
      '<h2 class="t-xl">길은 알아도,<br>다음 발을 디딜 수 없으면<br>도착하지 못한다.</h2>'
      '<p class="sub" style="font-size:2.0cqw;margin-top:2.4cqw;max-width:44ch">'
      '지도와 경로는 어디로 갈지를 알려 준다. 지금 이 지면을 밟아도 되는지는 알려 주지 않는다. 그래서 먼저 걸을 수 있어야 한다.</p>'
      '</div></div>%s</div>' % (lockup('night'), foot(3)))

# 03 수요 ─────────────────────────────────────────────────────────────────
slide(4, 'night',
      '<div class="scene">%s<div class="wash" style="background:'
      'linear-gradient(100deg,rgba(9,12,17,.94) 0%%,rgba(9,12,17,.86) 34%%,'
      'rgba(9,12,17,.42) 62%%,rgba(9,12,17,.25) 100%%)"></div></div>'
      '<div class="pad">'
      '<div class="hd">%s<div class="eyebrow">수요</div></div>'
      '<div class="body"><div style="max-width:52%%">'
      '<h2 class="t-lg" style="color:#fff">걷는 로봇은 이미<br>사람 대신 현장에 들어간다</h2>'
      '<p class="sub" style="color:#b6c0cb">지하 공동구, 터널, 산업 설비의 점검 구간에서 '
      '바퀴가 못 가는 계단과 배관 사이를 사족보행 로봇이 걷는다.</p>'
      '<div class="two" style="gap:2.2cqw;margin-top:2.0cqw">'
      '<div><div class="kicker" style="color:var(--teal-lit);font-size:2.4cqw">주 1,800회</div>'
      '<p class="note" style="color:#a3aebb;margin-top:.4cqw">AB InBev 브루어리에서 '
      '사족보행 로봇이 도는 점검 횟수. 첫 6개월에 약 150건의 이상을 찾아냈다.</p></div>'
      '<div><div class="kicker" style="color:var(--teal-lit);font-size:2.4cqw">고전압 구역</div>'
      '<p class="note" style="color:#a3aebb;margin-top:.4cqw">National Grid 는 사람이 제한적으로만 '
      '들어가던 구역을 로봇으로 훨씬 자주 점검하게 바꿨다.</p></div></div>'
      '<p class="callout" style="margin-top:1.9cqw;background:rgba(10,14,20,.72);color:#cdd5de;'
      'box-shadow:inset 0 0 0 1px #2b3743">위 현장은 <b style="color:#fff">지도가 있는 곳</b>이다. '
      '실제 점검 구간에서는 지도에 없던 장애가 생기고 지면이 달라진다. '
      '<b style="color:#fff">처음 보는 지형을 만났을 때</b> 로봇은 멈춘다.</p>'
      '</div></div>%s</div>'
      % (img('im_field', '작업자 둘이 지켜보는 실제 점검 현장을 사족보행 로봇이 걷는다'),
         lockup('night'), foot(4)))

# 04 정의 · Real to Sim to Real ─────────────────────────────────────────────
VCAP = ('<div class="vcap">'
        '<svg viewBox="0 0 24 24" role="img" aria-label="순회 화살표">'
        '<path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1" fill="none" stroke="currentColor" '
        'stroke-width="2.1" stroke-linecap="round"/>'
        '<path d="M20.6 1.9v4.6h-4.6" fill="none" stroke="currentColor" '
        'stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        '학습에 쓰지 않은 원본 지형으로 돌아와 검증한다</div>')
slide(5, 'paper', frame(
    5, 'paper', '프로젝트 정의', '같은 지형을 두 번 본다.<br>현실에서 재고, 시뮬레이션에서 넓힌다',
    '현실에서 기록하고, 시뮬레이션에서 한계를 넓히고, 다시 그 현장으로 돌아온다.',
    '<div class="splitL">'
    '<figure class="imgband tall" style="margin:0">'
    + img('im_route', '같은 길의 왼쪽 절반은 실제 돌바닥, 오른쪽 절반은 삼각 메시로 그려져 있다')
    + '<figcaption class="mini" style="margin-top:.55cqw">'
      '한 길인데 왼쪽은 실제 지면, 오른쪽은 시뮬레이션이 읽은 같은 지면</figcaption></figure>'
      '<div class="vloop">'
    + '<div class="vnode"><i>REAL</i><span style="grid-column:2"><b>실제 지형</b>'
      '점검 구간을 영상 · LiDAR · 점군으로 기록한다</span></div>'
      '<div class="vnode on"><i>SIM</i><span style="grid-column:2"><b>보행 한계를 넓힌다</b>'
      'Digital Twin 으로 옮기고 미경험 험지로 확장해, 어디서 무너지는지 재고 그 경계를 민다</span></div>'
      '<div class="vnode"><i>REAL</i><span style="grid-column:2"><b>현장에서 실증</b>'
      '같은 구간에서 목표 지점까지 실제로 자율 보행한다</span></div>'
      + VCAP
    + '</div></div>',
    tcls='t-md', top0=True))

# 05 섹션 ────────────────────────────────────────────────────────────────
slide(6, 'night',
      '<div class="pad"><div class="hd">%s<div class="eyebrow">접근</div></div>'
      '<div class="body"><div>'
      '<h2 class="t-xl">성공을 꾸미기 전에,<br>실패의 경계를 쟀다.</h2>'
      '<p class="sub" style="font-size:1.9cqw;margin-top:2.2cqw;max-width:48ch">'
      '지형별 처방과 검증 지표를 짐작으로 정하지 않기 위해서다. '
      '평지에서 기준 정책과 평가 장치가 정상인지 먼저 확인하고, '
      '그 다음 미경험 험지에서 어디가 반복해서 무너지는지 찾았다.</p></div></div>%s</div>'
      % (lockup('night'), foot(6)))

# 06 평지 기준선 ──────────────────────────────────────────────────────────
slide(7, 'paper',
      '<div class="pad"><div class="hd">%s<div class="eyebrow">기준선 · 실측</div></div>'
      '<div class="body"><div class="two" style="align-items:center;gap:3.2cqw">'
      '<div><div class="huge" style="font-size:9.2cqw;color:var(--teal)">100<span class="u"> / 100</span></div>'
      '<p class="sub" style="margin-top:1.5cqw;font-size:1.8cqw;color:var(--ink)">평지 보행 성공. '
      '<b>20초 생존 · 10 m 전진 · 1.0 m/s 속도 추종</b> 셋을 모두 만족한 판이다.</p>'
      '<p class="cond">NVIDIA 공식 체크포인트 · seed 42 · 100 episode<br>AI-WS01 RTX 5080 · Isaac Lab 37ddf62</p></div>'
      '<div><h2 class="t-md">평지 100판은 성과가 아니라<br>출발선이다</h2>'
      '<p class="sub">기본 보행이 되는지 먼저 확인했기 때문에, 이후의 실패를 「걷지 못함」이 아니라 '
      '<b>「처음 보는 지형에 적응하지 못함」</b>으로 읽을 수 있다.</p>'
      '<ul class="bul" style="margin-top:1.6cqw">'
      '<li>생존 100 / 100 · 10 m 전진 100 / 100 · 속도 추종 100 / 100</li>'
      '<li>전 판 20초 완주 · 평균 전진 19.08 m</li>'
      '<li>쉬운 환경의 높은 성공률은 여기까지만 보고한다</li>'
      '</ul></div></div></div>%s</div>' % (lockup('paper'), foot(7)), band='evid')

# 07 미경험 험지 10종 ─────────────────────────────────────────────────────
tiles = ''.join(
    '<div class="tile %s"><figure>%s<div class="bar"></div></figure>'
    '<div class="lab"><span class="nm">%s</span><span class="pc">%d%%</span></div></div>'
    % (cls, img(key, '%s 지형 평가 화면' % nm), nm, pc) for key, nm, pc, cls in TEN)
slide(8, 'paper', frame(
    8, 'paper', '실측 · 미경험 험지 10종', '10개 지형, 결과는 정확히 둘로 갈렸다',
    '험지 조건은 6초 안에 통과선 3 m 다. 속도와 판수를 두 배로 올려 다시 재도 실패하는 지형은 같았다.',
    '<div class="grid10">%s</div>' % tiles, tcls='t-md',
    cond='지형당 100 episode · 총 1,000판 · 6초 · 통과선 3 m · 1.0 m/s · 방향 임계 1.5 m',
    top0=True), band='evid')

# 08 실패 양상 ────────────────────────────────────────────────────────────
X0, XMAX = 36.0, 94.0


def bar_svg():
    sc = (XMAX - X0) / 3.3
    gate = X0 + 3.0 * sc
    rows, y = [], 8.5
    for nm, who, mode, ok, surv, fwd in FAIL:
        col = 'var(--red-lit)' if mode == 'fall' else 'var(--amber-lit)'
        w = fwd * sc
        end = X0 + w
        if end + 9 > gate:
            lab = ('<text x="%.2f" y="%.2f" fill="#0d1117" font-size="2.7" font-weight="700" '
                   'text-anchor="end" font-family="Pretendard,sans-serif">%.2f m</text>' % (end - 1.2, y + 3.3, fwd))
        else:
            lab = ('<text x="%.2f" y="%.2f" fill="#e9ecef" font-size="2.7" '
                   'font-family="Pretendard,sans-serif">%.2f m</text>' % (end + 1.3, y + 3.3, fwd))
        rows.append(
            '<text x="%.2f" y="%.2f" fill="#cbd3dc" font-size="2.75" font-weight="600" text-anchor="end">%s</text>'
            '<rect x="%.2f" y="%.2f" width="%.2f" height="4.4" rx="0.4" fill="%s"/>%s'
            % (X0 - 1.6, y + 3.3, nm, X0, y, w, col, lab))
        y += 8.0
    return ('<svg viewBox="0 0 100 50" width="100%%" role="img" aria-label="실패 5종의 평균 전진 거리와 통과선 3 m">'
            '<line x1="%.2f" y1="5" x2="%.2f" y2="47" stroke="#4b5865" stroke-width="0.35" stroke-dasharray="1.2 1.2"/>'
            '<text x="%.2f" y="3.6" fill="#7f8b99" font-size="2.5" font-family="Pretendard,sans-serif">0 m</text>'
            '<line x1="%.2f" y1="5" x2="%.2f" y2="47" stroke="var(--teal-lit)" stroke-width="0.6"/>'
            '<text x="%.2f" y="3.6" fill="var(--teal-lit)" font-size="2.8" font-weight="700" text-anchor="end">통과선 3 m</text>'
            '%s</svg>' % (X0, X0, X0, gate, gate, gate - 1.0, ''.join(rows)))


slide(9, 'night', frame(
    9, 'night', '실패 양상', '같은 실패가 아니다.<br>넘어지는 지형과 멈추는 지형',
    '<span style="color:var(--red-lit)">낙상형 둘</span>은 생존이 먼저고 '
    '<span style="color:var(--amber-lit)">전진불능형 셋</span>은 거리가 먼저라, 처방도 지표도 달라진다.',
    '<div class="two" style="gap:3cqw;align-items:start">'
    '<div>%s<p class="mini" style="margin-top:.8cqw">막대 = 판당 평균 전진 거리 · 100판 평균</p></div>'
    '<div><table><thead><tr><th>지형</th><th>담당</th><th>양상</th><th class="r">성공</th><th class="r">생존</th></tr></thead>'
    '<tbody>%s</tbody></table>'
    '</div></div>'
    % (bar_svg(),
       ''.join('<tr><td>%s</td><td class="who">%s</td><td><span class="tag %s">%s</span></td>'
               '<td class="n r">%d%%</td><td class="n r">%d%%</td></tr>'
               % (nm, who, mode, '낙상' if mode == 'fall' else '전진불능', ok, surv)
               for nm, who, mode, ok, surv, fwd in FAIL)),
    tcls='t-md', top0=True), band='evid')

# 09 구조 · 키 비주얼이 그대로 아키텍처다 ─────────────────────────────────────
slide(10, 'night',
      '<div class="hero">%s<div class="veil" style="background:'
      'linear-gradient(180deg,rgba(9,12,17,.94) 0%%,rgba(9,12,17,.62) 22%%,rgba(9,12,17,.2) 46%%,rgba(9,12,17,.5) 100%%)"></div></div>'
      '<div class="anno">'
      '<svg class="link" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
      '<line x1="20" y1="74" x2="43" y2="65" stroke="#3ec7b4" stroke-width="0.2" stroke-dasharray="0.9 0.9"/>'
      '<line x1="76" y1="46" x2="85" y2="59" stroke="#dc9a30" stroke-width="0.2" stroke-dasharray="0.9 0.9"/>'
      '</svg>'
      '<div class="dot a" style="left:43%%;top:65%%"></div>'
      '<div class="dot b" style="left:85%%;top:59%%"></div>'
      '<div class="lbl a" style="left:16%%;top:80%%"><b>Track A</b>'
      '<span>이 지면에 발을 디딜 수 있는가<br>가상에서 한계를 재고 민다</span></div>'
      '<div class="lbl b" style="left:72%%;top:40%%"><b>Track B</b>'
      '<span>저 목표까지 갈 수 있는가<br>현장에서 자율 보행을 검증한다</span></div>'
      '<div class="lbl c" style="left:60%%;top:80%%;max-width:40cqw"><b>Digital Twin</b>'
      '<span>두 질문이 같은 지형, 같은 좌표계 위에 있다. 그래서 하나의 프로젝트다.</span></div>'
      '</div>'
      '<div class="pad" style="justify-content:flex-start">'
      '<div class="hd">%s<div class="eyebrow">시스템 구조</div></div>'
      '<div style="margin-top:2.0cqw"><h2 class="t-lg" style="color:#fff;max-width:18ch">'
      '현실 하나,<br>두 개의 검증</h2></div>'
      '<div style="flex:1"></div>%s</div>'
      % (img('hero', 'FOOTHOLD 키 비주얼. 로봇이 메시로 그려진 건너편 지면에 앞발을 내밀고 멀리 목표 불빛이 있다'),
         lockup('night'), foot(10)), band='evid')

# 10 Track A ─────────────────────────────────────────────────────────────
slide(11, 'paper', frame(
    11, 'paper', 'Track A · 정책', '다섯 레시피를 찾고,<br>하나의 정책으로 합친다',
    '다섯 사람이 실패를 하나씩 맡지만, 최종 산출물은 지형별 정책 다섯 개가 아니라 정책 하나다.',
    '<div class="two" style="gap:3cqw">'
    '<div><div class="eyebrow" style="margin-bottom:1.1cqw">병렬 레시피 탐색</div><ol class="steps">'
    '<li><span>담당자가 자기 지형의 <b>물리·관측 가능성을 먼저 판정</b>한다</span></li>'
    '<li><span>난이도 경계를 3~4단계로 측정한다</span></li>'
    '<li><span>기존 rough 0.6 + 담당 지형 0.4 로 레시피를 탐색한다</span></li>'
    '<li><span>한 번에 변수 하나만 바꾸고 <b>기존 rough 회귀를 함께 기록</b>한다</span></li>'
    '<li><span>작동한 비율 · 보상 · 난이도 시작점 · 하이퍼파라미터를 한 장에 남긴다</span></li></ol></div>'
    '<div><div class="eyebrow" style="margin-bottom:1.1cqw">최종 통합</div><ul class="bul">'
    '<li>다섯 정책의 <b>가중치를 합치는 것이 아니다</b></li>'
    '<li>다섯 레시피를 한 cfg 로 통합해 <b>혼합 단일 런 1개</b>를 학습한다</li>'
    '<li>계획값 · rough 계열 합계 0.5 + 신규 5종 각 0.1</li>'
    '<li>공식 체크포인트 resume 와 scratch 런을 <b>같은 평가 하네스</b>로 비교한다</li></ul>'
    '<p class="callout" style="margin-top:1.4cqw"><b>왜 섞어서 학습하나.</b> 신규 지형만 따로 학습하면 '
    '기존 rough 능력을 잊는다. 섞어서 학습하고 회귀를 함께 재는 것은 한 쌍이다.</p></div></div>',
    tcls='t-lg', top0=True))

# 11 Track B · 기술 사슬 ───────────────────────────────────────────────────
ICON = {
    'eye': '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="3" fill="currentColor"/>',
    'hub': '<circle cx="12" cy="12" r="2.6" fill="currentColor"/><circle cx="4" cy="5" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="20" cy="5" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="4" cy="19" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="20" cy="19" r="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6 6.5 10 10M18 6.5 14 10M6 17.5 10 14M18 17.5 14 14" stroke="currentColor" stroke-width="1.4"/>',
    'map': '<path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M9 4v13.5M15 6.5V20" stroke="currentColor" stroke-width="1.4"/>',
    'route': '<circle cx="5" cy="19" r="2.4" fill="currentColor"/><circle cx="19" cy="5" r="2.4" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M5 16.5c0-6 5-4 8-6.5S19 8 19 7.6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-dasharray="2.4 2"/>',
    'dog': '<rect x="6" y="8.5" width="12" height="4" rx="1.2" fill="currentColor"/><circle cx="8.5" cy="7" r="1.3" fill="currentColor"/><path d="M7.5 12.5 5.5 16l1.8 3M11 12.5 9.5 16l2 3M14 12.5l1.6 3.5-1.4 3M17 12.5l2 3.5-1.6 3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
}


def cnode(icon, name, sub, on=False):
    return ('<div class="cnode%s"><svg viewBox="0 0 24 24" role="img" aria-label="%s">%s</svg>'
            '<b>%s</b><span>%s</span></div>' % (' on' if on else '', name, ICON[icon], name, sub))


THUMB = {
 'cloud': ('<rect width="100" height="62" fill="var(--paper-2)"/>'
           '<path d="M4 46 L20 34 L34 40 L50 26 L66 33 L82 22 L96 30" fill="none" '
           'stroke="var(--ink-3)" stroke-width="1.1" stroke-dasharray="2 2"/>'
           + ''.join('<circle cx="%d" cy="%d" r="1.1" fill="var(--teal)"/>' % (4+i*6, 47-abs((i%7)-3)*3.2)
                     for i in range(16))
           + '<path d="M50 6 L34 20 L66 20 Z" fill="none" stroke="var(--ink-2)" stroke-width="1.1"/>'),
 'graph': ('<rect width="100" height="62" fill="var(--paper-2)"/>'
           '<line x1="26" y1="18" x2="50" y2="31" stroke="var(--ink-3)" stroke-width="1"/>'
           '<line x1="26" y1="44" x2="50" y2="31" stroke="var(--ink-3)" stroke-width="1"/>'
           '<line x1="50" y1="31" x2="76" y2="18" stroke="var(--ink-3)" stroke-width="1"/>'
           '<line x1="50" y1="31" x2="76" y2="44" stroke="var(--ink-3)" stroke-width="1"/>'
           '<rect x="12" y="12" width="20" height="12" rx="1.5" fill="var(--card)" stroke="var(--ink-2)" stroke-width="1"/>'
           '<rect x="12" y="38" width="20" height="12" rx="1.5" fill="var(--card)" stroke="var(--ink-2)" stroke-width="1"/>'
           '<rect x="68" y="12" width="20" height="12" rx="1.5" fill="var(--card)" stroke="var(--ink-2)" stroke-width="1"/>'
           '<rect x="68" y="38" width="20" height="12" rx="1.5" fill="var(--card)" stroke="var(--ink-2)" stroke-width="1"/>'
           '<circle cx="50" cy="31" r="6" fill="var(--teal)"/>'),
 'grid': ('<rect width="100" height="62" fill="var(--paper-2)"/>'
          + ''.join('<line x1="%d" y1="6" x2="%d" y2="56" stroke="var(--rule)" stroke-width=".5"/>' % (10+i*10, 10+i*10) for i in range(9))
          + ''.join('<line x1="10" y1="%d" x2="90" y2="%d" stroke="var(--rule)" stroke-width=".5"/>' % (6+i*10, 6+i*10) for i in range(6))
          + ''.join('<rect x="%d" y="%d" width="10" height="10" fill="var(--ink-2)"/>' % c
                    for c in ((20,16),(30,16),(60,26),(70,26),(30,36),(40,46),(70,46)))
          + '<path d="M22 50 l5-8 5 8 -5-2.5z" fill="var(--teal)"/>'),
 'route': ('<rect width="100" height="62" fill="var(--paper-2)"/>'
           + ''.join('<line x1="%d" y1="6" x2="%d" y2="56" stroke="var(--rule)" stroke-width=".5"/>' % (10+i*10, 10+i*10) for i in range(9))
           + ''.join('<line x1="10" y1="%d" x2="90" y2="%d" stroke="var(--rule)" stroke-width=".5"/>' % (6+i*10, 6+i*10) for i in range(6))
           + ''.join('<rect x="%d" y="%d" width="10" height="10" fill="var(--ink-3)" opacity=".55"/>' % c
                     for c in ((30,16),(40,16),(60,36),(70,36)))
           + '<polyline points="18,50 28,50 28,32 48,32 48,44 68,44 68,20 82,20" fill="none" '
             'stroke="var(--teal)" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>'
           '<circle cx="18" cy="50" r="2.6" fill="var(--teal)"/>'
           '<circle cx="82" cy="20" r="3.4" fill="none" stroke="var(--teal)" stroke-width="2"/>'),
 'steps': ('<rect width="100" height="62" fill="var(--paper-2)"/>'
           '<path d="M6 50 C28 50 34 34 52 34 C70 34 76 20 94 20" fill="none" '
           'stroke="var(--rule)" stroke-width="1.4" stroke-dasharray="3 3"/>'
           + ''.join('<ellipse cx="%d" cy="%d" rx="3.2" ry="2.1" fill="%s"/>'
                     % (x, y, 'var(--teal)' if x > 60 else 'var(--ink-3)')
                     for x, y in ((14, 53), (24, 45), (34, 47), (44, 39),
                                  (54, 41), (64, 33), (74, 35), (84, 27)))),
}


def cnode2(icon, key, name, sub, out, on=False):
    """위에 아이콘, 이름 아래에 그 단계가 남기는 산출물 그림."""
    return ('<div class="cnode%s">'
            '<svg class="ico" viewBox="0 0 24 24" role="img" aria-label="%s">%s</svg>'
            '<b>%s</b><span>%s</span>'
            '<svg class="thumb" viewBox="0 0 100 62" role="img" aria-label="%s 산출물">%s</svg>'
            '<em>%s</em></div>'
            % (' on' if on else '', name, ICON[icon], name, sub, name, THUMB[key], out))


CHAIN = (cnode2('eye', 'cloud', '인지', '카메라 · 4D LiDAR', '점군과 깊이')
         + cnode2('hub', 'graph', 'ROS 2', '좌표 · 센서 · 상태', '노드 그래프')
         + cnode2('map', 'grid', 'SLAM', '위치 추정 · 지도', '점유 격자 지도')
         + cnode2('route', 'route', 'Nav2', '경로 계획 · 재계획', '주행 경로')
         + cnode2('dog', 'steps', 'Go2 보행', '검증된 순정 보행', '실제 발자국', True))
slide(12, 'paper', frame(
    12, 'paper', 'Track B · 자율 보행', '보행을 다시 만들지 않고<br>임무를 완성한다',
    '걷는 것은 Go2 가 하고, 우리는 보고 위치를 알고 길을 정해 목표까지 연결한다. 단계마다 남는 산출물이 다음 단계의 입력이다.',
    '<div class="chain">' + CHAIN + '</div>',
    tcls='t-lg', top0=True))

# 12 기술 선택 ────────────────────────────────────────────────────────────
TECH = [('현실 장비를 다치지 않고 수천 번 넘어져야 한다', 'Isaac Sim / Isaac Lab',
         '병렬 물리 시뮬레이션. 1,000판을 하룻밤에 돌린다'),
        ('넘어지는 법을 스스로 고쳐야 한다', 'PPO / RSL-RL',
         'NVIDIA 공식 체크포인트에서 이어 학습하고 같은 하네스로 비교한다'),
        ('시뮬레이터를 믿어도 되는지 확인해야 한다', 'MuJoCo',
         '엔진이 다른 곳에서 한 번 더 잰다'),
        ('실제 지형을 그대로 옮겨야 한다', 'COLMAP / 3DGS / LiDAR',
         '현장의 장면과 지형 특성을 Twin 입력으로 만든다'),
        ('장면과 자산이 한 표현이어야 한다', 'USD / Omniverse',
         '시뮬레이션 · 시각화 · 협업이 같은 파일을 본다'),
        ('센서와 좌표와 모듈이 연결돼야 한다', 'ROS 2',
         '인지 · 위치 · 경로 · 로봇 상태의 공통 기반'),
        ('목표 지점까지 스스로 가야 한다', 'SLAM / Nav2',
         '위치 추정과 지도화, 경로 계획과 재계획'),
        ('반복 실행이 막히면 안 된다', 'RunPod / AI-WS01 RTX 5080',
         'headless 평가와 학습을 병렬로 돌린다')]
slide(13, 'paper', frame(
    13, 'paper', '기술 선택', '기술은 문제가 정했다',
    '도구를 먼저 고르지 않고, 풀어야 하는 문제를 적은 다음 그 문제가 요구하는 것을 골랐다.',
    '<table><thead><tr><th style="width:36%%">풀어야 하는 문제</th><th style="width:23%%">선택</th>'
    '<th>왜 이것이어야 하나</th></tr></thead><tbody>%s</tbody></table>'
    % ''.join('<tr><td>%s</td><td class="who">%s</td><td style="color:var(--ink-2)">%s</td></tr>' % r
              for r in TECH),
    tcls='t-lg', top0=True))

# 13 KPI ─────────────────────────────────────────────────────────────────
slide(14, 'paper', frame(
    14, 'paper', 'KPI', '어디까지 걸을 수 있게 됐는가로<br>성과를 잰다',
    '통과율만 보면 지형을 쉽게 만들어도 올라가니, 같은 난이도에서 얼마나 더 갔는지를 본다. 근거가 없는 칸은 비워 두었다.',
    '<table><thead><tr><th style="width:13%%">상태</th><th style="width:24%%">지표</th>'
    '<th style="width:31%%">지금</th><th>목표</th></tr></thead><tbody>'
    '<tr><td><span class="tag m">실측</span></td><td class="who">평지 보행 성공</td>'
    '<td class="n">100 / 100</td><td>그대로 유지</td></tr>'
    '<tr><td><span class="tag m">실측</span></td><td class="who">통과 5종 성공률</td>'
    '<td class="n">97 ~ 100%</td><td class="n">97% 아래로 내려가지 않는다</td></tr>'
    '<tr><td><span class="tag m">실측</span></td><td class="who">10종 평균 낙상률</td>'
    '<td class="n">19.1%</td><td class="n">20% 를 넘지 않는다</td></tr>'
    '<tr><td><span class="tag d">확정</span></td><td class="who">전진불능형 · 전진 거리</td>'
    '<td class="n">rails 2.64 · pit 1.57 · ring 1.06 m</td>'
    '<td>판당 전진 중앙값이 <b>통과선 3 m</b>를 넘는다</td></tr>'
    '<tr><td><span class="tag d">확정</span></td><td class="who">속도 추종을 재는 방법</td>'
    '<td>6초를 <b>완주한 판만</b> 놓고 잰다</td>'
    '<td>넘어져 일찍 끝난 판이 유리해지는 것을 막는다</td></tr>'
    '<tr><td><span class="tag p">미정</span></td><td class="who">난이도 경계 이동폭</td>'
    '<td style="color:var(--ink-3)">경계값을 아직 재지 않았다</td>'
    '<td style="color:var(--ink-3)">난이도 격자 · 지형당 1,000판을 돌린 뒤 정한다</td></tr>'
    '<tr><td><span class="tag p">미정</span></td><td class="who">낙상형 생존율</td>'
    '<td class="n" style="color:var(--ink-3)">stones 20% · gap 21%</td>'
    '<td style="color:var(--ink-3)">어느 난이도부터 생존이 오르는지 본 뒤 정한다</td></tr>'
    '</tbody></table>', tcls='t-lg', top0=True), band='evid')

# 14 WBS · 간트 ───────────────────────────────────────────────────────────
GATES = [(0.5, '09/04', '기획 발표', 0), (2.2, '09/12', 'A-정책', 1), (5.6, '09/30', 'MVP', 0),
         (12.0, '11/07', 'NAV', 0), (17.0, '12/11', 'FINAL', 0)]
LANES = [('Track A', 'var(--teal)', [(0.3, 5.4), (5.6, 11.6)]),
         ('Digital Twin', 'var(--amber)', [(1.4, 6.0), (7.0, 13.0)]),
         ('Track B', 'var(--teal-ink)', [(6.0, 12.2), (12.4, 17.2)]),
         ('공통 운영·기록', 'var(--ink-3)', [(0.0, 17.4)])]
MONTHS = [(0.0, '8월'), (3.0, '9월'), (7.4, '10월'), (11.8, '11월'), (16.0, '12월')]


def gantt():
    """8월 1일부터 12월 11일까지를 17.6주로 본다. 한 축, 한 스케일.

    ★ 처음에 viewBox 를 100x42 로 두었더니 1 단위가 10px 이라 글자가 거대해졌다.
      높이를 실제 자리에 맞추고 글자 크기를 그 단위로 다시 잡는다.
    """
    L, R, W = 15.5, 98.0, 17.6
    sc = (R - L) / W

    def x(w):
        return L + w * sc

    TOP, BOT = 3.4, 18.6
    out = []
    for w, lab in MONTHS:
        out.append('<text x="%.2f" y="2.3" fill="var(--ink-3)" font-size="1.45">%s</text>' % (x(w), lab))
        out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="var(--rule)" stroke-width="0.12"/>'
                   % (x(w), TOP, x(w), BOT))
    y = TOP + 0.9
    for name, col, spans in LANES:
        out.append('<text x="%.2f" y="%.2f" fill="var(--ink)" font-size="1.5" font-weight="700" '
                   'text-anchor="end">%s</text>' % (L - 1.4, y + 1.9, name))
        for a, b in spans:
            out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="2.5" rx="0.4" fill="%s" opacity=".88"/>'
                       % (x(a), y, max(1.0, (b - a) * sc), col))
        y += 3.7
    for w, d, g, dy in GATES:
        gx = x(w)
        out.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="var(--ink)" '
                   'stroke-width="0.16" stroke-dasharray="0.7 0.6"/>' % (gx, TOP, gx, BOT))
        out.append('<circle cx="%.2f" cy="%.2f" r="0.5" fill="var(--ink)"/>' % (gx, BOT))
        anchor = 'start' if w < 1 else ('end' if w > 16 else 'middle')
        gy = BOT + 2.1 + dy * 3.0
        out.append('<text x="%.2f" y="%.2f" fill="var(--ink)" font-size="1.5" font-weight="700" '
                   'text-anchor="%s">%s</text>' % (gx, gy, anchor, g))
        out.append('<text x="%.2f" y="%.2f" fill="var(--ink-3)" font-size="1.28" text-anchor="%s" '
                   'font-family="Pretendard,sans-serif">%s</text>' % (gx, gy + 1.75, anchor, d))
    return ('<svg class="gantt" viewBox="0 0 100 27" width="100%%" role="img" '
            'aria-label="8월부터 12월 11일까지 업무 4축과 관문 5개">%s</svg>' % ''.join(out))


slide(15, 'paper', frame(
    15, 'paper', 'WBS', '8월부터 12월 11일까지,<br>업무 4축과 관문 5개',
    '축마다 담당과 산출물이 붙어 있고, 관문은 날짜가 아니라 다음 단계로 넘어가도 되는 증거를 정한다.',
    '%s<p class="mini" style="margin-top:.25cqw">'
    'Track A = A/정책학습 + A/평가 · Digital Twin = A/지형씬제작 + A/트윈렌더 · '
    'Track B = B/항법 + B/인지 · 공통 = C/기록 + C/운영</p>' % gantt(),
    tcls='t-lg', top0=True), band='evid')

# 15 팀 ──────────────────────────────────────────────────────────────────
TEAM_L = [('오흥재', 'B/항법 · C/운영', 'ring(뜬 고리)', 'stall', '관측만으로 열리는 문제인지 먼저 가린다'),
          ('임석헌', 'A/정책학습', 'gap(틈)', 'fall', '낙상을 줄일 보상과 커리큘럼을 찾는다'),
          ('맹라현', 'A/지형씬 · A/트윈', 'rails(턱·장애물)', 'stall', '남은 0.36 m 를 여는 지형과 박자를 찾는다')]
TEAM_R = [('오현민', 'A/평가 · B/인지', 'stones(디딤돌)', 'fall', '낙상과 인지를 같은 기준으로 판정한다'),
          ('이민우', 'B/항법 · C/기록', 'pit(구덩이)', 'stall', 'SLAM 과 Nav2 로 실제 목표까지 잇는다')]


def per(t):
    nm, lane, terr, mode, q = t
    return ('<div class="per"><span class="tag %s">%s</span>'
            '<span class="who2">%s<em>%s</em></span><span class="q">%s</span></div>'
            % (mode, terr, nm, lane, q))


slide(16, 'paper', frame(
    16, 'paper', '팀', 'FIVE TERRAINS.<br>ONE POLICY. ONE TEAM.',
    '다섯이 험지를 하나씩 맡아 각자 다른 답을 찾지만, 한 축으로 움직이고 정책 하나로 모인다.',
    '<div class="conv"><div class="side">%s</div>'
    '<div class="core">%s<b>ONE POLICY<br>ONE TEAM</b><span>혼합 단일 런 1개</span></div>'
    '<div class="side">%s</div></div>'
    % (''.join(per(t) for t in TEAM_L), img('symbol_rev', '', ''), ''.join(per(t) for t in TEAM_R)),
    tcls='t-lg', top0=True))

# 16 엔딩 · 이미지만 ───────────────────────────────────────────────────────
slide(17, 'night',
      '<div class="hero">%s</div>'
      % img('hero', 'FOOTHOLD 키 비주얼. 로봇이 검증된 다음 발디딤에 앞발을 내민다'), band='video')

# 18 영상 · 4096 군단. 발표에서 전체 화면으로 튼다 ─────────────────────────
slide(18, 'night',
      '<div class="vid">'
      '<video controls preload="metadata" playsinline poster="data:image/jpeg;base64,'
      + A['army_poster'] + '" src="' + A['army_mp4'] + '" '
      'aria-label="FOOTHOLD 러프컷. Go2 근접과 4096대 군집 렌더"></video>'
      '<img class="print-only" src="data:image/jpeg;base64,' + A['army_poster'] + '" '
      'alt="FOOTHOLD 러프컷 한 장면">'
      '<div class="tagline"><span class="tv">TARGET VISION</span>'
      '시뮬레이터에서 천 번 넘어지고,<br>현장에서는 넘어지지 않는다.</div>'
      '<div class="meta">FOOTHOLD roughcut v8 · 4,096 · 21s</div>'
      '</div>', band='video')

# 19 마침 ────────────────────────────────────────────────────────────────
slide(19, 'night',
      '<div class="pad" style="justify-content:center;align-items:center">'
      '<div class="finis">'
      '<div class="lockup-hero" style="gap:1.5cqw">%s%s</div>'
      '<div style="font-size:1.55cqw;color:#cdd5de;line-height:1.55">'
      'Unitree Go2 미경험 험지 적응 프로젝트<br>'
      '<span style="font-family:var(--mono);font-size:1.25cqw;color:#93a0ae">2026.07 ~ 2026.12.11</span></div>'
      '<img class="qr" src="%s" alt="foothold-project.vercel.app QR 코드">'
      '<div class="url">foothold-project.vercel.app</div>'
      '<div class="names">오흥재 · 임석헌 · 오현민 · 맹라현 · 이민우</div>'
      '<div class="org">%s</div>'
      '</div></div>'
      % (img('symbol_rev', '', 'sym'), img('wordmark_rev', 'FOOTHOLD', 'wm'), A['qr'], ORG),
      band='video')

# ── 조립 ─────────────────────────────────────────────────────────────────
out = []
for n, surface, band, inner in SL:
    out.append('<div class="row"><div class="gut"><i>%02d</i><u class="%s"></u></div>'
               '<section class="s %s" aria-label="슬라이드 %02d">%s</section></div>'
               % (n, band, surface, n, inner))

tpl = io.open(os.path.join(HERE, 'deck.tpl.html'), encoding='utf-8').read()
html = (tpl.replace('{{SLIDES}}', '\n'.join(out))
           .replace('{{FONT}}', A['font'])
           .replace('{{LOCKUP_DARK}}', A['lockup_dark'])
           .replace('16장 · 10분', '%d장 · 10분' % TOTAL))
# 배포본은 «완전한 문서» 여야 한다. charset 이 없으면 file:// 로 열 때 HTTP 헤더가
# 없어 브라우저가 Windows-1252 로 읽고 한글이 통째로 깨진다. 구글드라이브에서 받아
# 더블클릭하는 발표 PC 가 정확히 그 경로다.
NL = chr(10)
HEAD = ('<!doctype html>' + NL + '<html lang="ko">' + NL + '<head>' + NL
        + '<meta charset="utf-8">' + NL
        + '<meta name="viewport" content="width=device-width,initial-scale=1">' + NL
        + '<meta name="color-scheme" content="dark">' + NL)
doc = HEAD + html.replace('</style>', '</style>' + NL + '</head>' + NL + '<body>', 1) + NL + '</body>' + NL + '</html>' + NL
assert doc.count('<body>') == 1 and doc.count('charset') == 1
io.open(os.path.join(HERE, os.pardir, 'proposal-deck.html'), 'w', encoding='utf-8', newline='').write(doc)
# 아티팩트(웹 뷰어)는 프레임 안에서 열리고 그쪽 정책이 심어 둔 폰트를 막을 수 있다.
# 그래서 확인용 사본에만 웹폰트를 한 겹 덧댄다. 허용된 곳은 fonts.googleapis.com 뿐이다.
# 발표용 배포본에는 넣지 않는다. 발표장에 인터넷이 없어도 흔들리면 안 되기 때문이다.
WEBFONT = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
           'family=Noto+Sans+KR:wght@400;500;700;900&display=swap">' + NL)
io.open(os.path.join(HERE, 'deck.artifact.html'), 'w', encoding='utf-8', newline='').write(WEBFONT + html)
io.open(os.path.join(HERE, 'preview.html'), 'w', encoding='utf-8', newline='').write(
    '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    '<style>body{margin:0}img{max-width:100%}</style></head><body>' + html + '</body></html>')
print('슬라이드 %d장 · 배포본 %.2f MB (완전 문서) · 아티팩트본 %.2f MB'
      % (len(SL), len(doc.encode('utf-8')) / 1e6, len(html.encode('utf-8')) / 1e6))
assert len(SL) == TOTAL
visible = re.sub(r'data:[a-z0-9/+.-]+;base64,[A-Za-z0-9+/=]+', '', html)
for bad in ('RAILS', '20 s · 10 m', 'GPS', chr(8212), 'Archivo', 'fonts.googleapis', '멘토'):
    assert bad not in visible, '금지 표현: %r' % bad
print('검사 통과 · 편집 메모 제거 · 쪽 번호 · 멘토 표기 없음')
