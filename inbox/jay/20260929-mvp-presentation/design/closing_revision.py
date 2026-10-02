"""U206 closing scenes. Read existing evidence and preserve the original brand lockup."""
from pathlib import Path
import re

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
REPORT = 'https://foothold-project.vercel.app/research-20260928-v2-mvp-report'
POC = '../../20260916-3dgs-test/'


def make(title, body, spoken, source='', kind='closing-revision', note='', steps=0):
    return dict(section='다음 걸음', title=title, body=body, spoken=spoken,
                note=note or spoken, source=source, kind=kind, steps=steps)


def link(label, url):
    return f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'


def film(src, caption, poster='', sound=False):
    flags = 'data-autoplay="sound"' if sound else 'data-autoplay="muted" muted loop'
    poster_attr = f' poster="{poster}"' if poster else ''
    return (f'<figure class="closing-film"><video controls playsinline preload="metadata" '
            f'{flags}{poster_attr} src="{src}"></video><figcaption>{caption}</figcaption></figure>')


def nav_diagram():
    nodes = [
        (0, '현장을 관측', '센서', ['LiDAR · 깊이 카메라', '주변 형상과 장애물']),
        (300, '같은 좌표로 연결', 'ROS 2', ['센서 · TF · 로봇 상태', '모듈 사이의 데이터 전달']),
        (600, '위치를 추정', 'SLAM', ['현재 위치와 지도', '어디에 있는가']),
        (900, '경로를 계획', 'Nav2', ['목표까지 계획 · 추종', '어디로 갈 것인가']),
        (1200, '발걸음을 실행', 'Go2 순정 보행', ['전진 · 횡이동 · 회전 명령', '몸을 어떻게 움직일 것인가']),
    ]
    out = ['<svg class="closing-nav-svg" viewBox="0 0 1472 370" role="img" aria-label="센서, ROS2, SLAM, Nav2, Go2 순정 보행으로 이어지는 실기 항법 계획">',
           '<defs><marker id="closing-nav-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10Z" fill="#0e7a6e"/></marker></defs>']
    for i, (x, kicker, title, lines) in enumerate(nodes):
        out.append(f'<g transform="translate({x} 80)"><rect x="1" y="1" width="270" height="196" rx="3" fill="{ "#e0f0ed" if i == 4 else "#eeece6"}" stroke="#c4cec7"/><text x="20" y="34" class="nav-kicker">{kicker}</text><text x="20" y="78" class="nav-title">{title}</text><text x="20" y="124" class="nav-line">{lines[0]}</text><text x="20" y="158" class="nav-line">{lines[1]}</text></g>')
        if i < 4:
            out.append(f'<path d="M{x+274} 178 H{x+294}" class="nav-arrow"/>')
    out.extend([
        '<text x="1035" y="25" text-anchor="middle" class="nav-goal">사용자가 지정한 목표</text><path d="M1035 38 V69" class="nav-arrow"/>',
        '<path d="M1335 282 V326 H735 V282" class="nav-feedback"/><text x="1035" y="359" text-anchor="middle" class="nav-line">로봇 상태를 다시 확인하며 경로와 명령을 갱신</text>',
        '</svg>',
    ])
    return ''.join(out)


def original_closing():
    path = REPO / 'deliverables/plan/proposal-deck-presented.html'
    text = path.read_text(encoding='utf-8')
    sections = re.findall(r'<section\b[\s\S]*?</section>', text)
    last = next(s for s in sections if 'aria-label="슬라이드 19"' in s.split('>')[0])
    inner = re.sub(r'^<section[^>]*>|</section>$', '', last)
    return '<div class="closing-original">' + inner + '</div>'


def closing_slides():
    result = []
    result.append(make(
        '실제 공간을, 보행을 시험할 공간으로 가져오고 있습니다',
        '<div class="closing-poc"><div class="poc-sources">' +
        film(POC+'test_20260916_112122728.mp4', '출발점 · 직접 촬영한 실제 공간', POC+'_out/colmap/undistorted/images/0000.jpg') +
        '<figure class="poc-comparison"><img src="../assets/u207-splat-view.png" alt="복원한 스플랫과 발이 닿는 바닥 충돌 메시를 함께 띄운 뷰어 화면"><figcaption><b>스플랫된 공간의 모습</b>과 <b>발이 닿는 바닥 충돌 메시</b><br><span>주황 선은 촬영 궤적입니다. 축척과 실제 지면 오차는 미검증입니다.</span></figcaption></figure></div><div class="poc-result">' +
        film(POC+'_out/nurec/go2_B_mesh_hidden/run.mp4', '복원한 배경 + 충돌 지형 + Go2 정책 실행', POC+'_out/nurec/render_a_nurec.png') +
        '<div class="poc-result-note"><b>이번에 연결한 것</b><p>촬영 → 공간 복원 → 물리 지형 → 정책 실행</p><span>12초 PoC · 낙상과 재시작 포함 · 축척과 실제 지면 오차는 추가 검증</span></div></div></div>',
        '보행 연구는 프로젝트가 끝날 때까지 이어갑니다. 동시에 실제 공간을 시뮬레이션으로 가져오는 작업도 진행했습니다. 왼쪽은 직접 촬영한 공간이고, 그 아래는 복원한 모습과 바닥 메시입니다. 스플랫은 공간의 모습을, 충돌 메시는 발이 닿는 바닥을 맡습니다. 오른쪽은 이 둘을 Isaac Sim 안에서 연결하고 정책을 실행한 기록입니다. 아직 복원 정확도나 안정 보행을 입증한 것은 아닙니다. 실제 축척과 관측, 충돌 바닥이 맞는지 검증을 이어가야 합니다.',
        link('Digital Twin PoC · 실행 기록과 한계', POC+'RESULTS-3dgs-terrain.md'),
        note='기존32쪽의 세 축 개요를 PoC 설명과 통합. 비교판의 반입 경로는 원 보고서에서 미확인. 성공률 자료로 사용하지 않는다. 원본 영상은 음소거 자동 반복, 시뮬레이션도 음소거 반복.'))

    result.append(make(
        '실기에서는 순정 보행 위에, 목표까지 가는 능력을 연결합니다',
        '<div class="closing-navigation"><div class="nav-purpose"><span>TRACK B · 실기 항법</span><p>보는 것에서, 위치를 알고 목적지에 도달하는 것까지.</p></div>' + nav_diagram() +
        '<div class="nav-boundary"><b>실기 항법에 집중하기 위한 선택</b><p>학습 정책의 이식 검증과 분리해, Go2 순정 보행으로 목표 주행·정지·복귀를 검증합니다.</p></div></div>',
        '실제 로봇에서는 목적지까지 가는 과제에 집중합니다. 센서로 주변을 보고, ROS2로 정보를 연결합니다. SLAM으로 위치와 지도를 얻고, Nav2로 경로와 주행 명령을 만듭니다. 발걸음은 Go2의 순정 보행을 사용합니다. 저희가 학습한 정책을 실기에 이식했다고 말하는 것이 아닙니다. 보행 연구와 실기 항법을 병행하면서, 각각 무엇이 검증됐는지 분리해 확인하겠습니다.',
        link('기획발표 12쪽 · Track B 구성', '../../../../deliverables/plan/proposal-deck-presented.html'),
        note='도식은 앞으로 통합·검증할 구조. 현재 작동 완료를 뜻하지 않는다. 센서의 기종은 확인된 보유 모듈과 실제 연결 단계가 달라 본 도식에서 특정하지 않는다. Nav2가 관절 목표를 직접 출력하는 것으로 그리지 않는다.'))

    result.append(make(
        '다음 실험은 지형·명령·관측을 함께 보되, 바꾸는 원인을 나누겠습니다',
        '<div class="closing-experiments"><div class="experiment-question"><span>다음 연구 질문</span><h3>지형을 건너면서도,<br>멈추고 방향을 바꿀 수 있을까?</h3><div class="experiment-sequence"><span>험지 보행</span><i>→</i><span>감속 · 정지</span><i>→</i><span>회전 · 재출발</span></div><p>지형 통과와 명령 수행을<br>하나의 과제 안에서 확인합니다.</p></div><div class="experiment-design"><div><span class="experiment-label">조건</span><h3>지형과 명령의 결합</h3><p>같은 구간에서 명령을 전환하고<br>기존 험지 능력의 유지도 평가</p></div><div><span class="experiment-label">입력 · 구조</span><h3>관측과 신경망 대조</h3><p>시간 이력 · 지형 표현 · 후보 구조를<br>같은 과제와 학습 예산으로 비교</p></div><div><span class="experiment-label">검증</span><h3>한 번의 좋은 결과를 넘어</h3><p>여러 학습·평가 시드로 재확인<br>모델 선택과 최종 시험을 분리</p></div></div></div>',
        '다음에는 험지를 지나면서 멈추고, 방향을 바꾸고, 다시 출발하는 과제를 보려고 합니다. 동시에 관측과 신경망도 탐구합니다. 다만 구조를 바꾸면 좋아질 것이라고 결론부터 정하지 않겠습니다. 같은 과제와 학습 예산에서 비교하고, 여러 시드에서도 효과가 유지되는지 보겠습니다. 개발하면서 반복 확인한 지형과 마지막 시험에 쓸 지형도 구분할 계획입니다.',
        link('후속 실험 방향 · MVP 정본', REPORT),
        note='기존35·36쪽 통합. 시간 이력, 신경망 변경의 효과는 아직 확인하지 않은 질문이다. 횡이동은 기존 축2의 검증 완료 항목이 아니다.'))

    result.append(make(
        '확인한 한 걸음을 바탕으로, 세 과제를 끝까지 이어갑니다',
        '<div class="closing-roadmap"><div class="roadmap-head"><span>프로젝트의 세 흐름</span><b>지금 확인한 것</b><b>다음에 확인할 것</b></div><div class="roadmap-row"><div><strong>보행 연구</strong><span>TRACK A</span></div><p>학습 조건을 바꾸고<br>험지·정지 전환의 개선 확인</p><p>좁은 디딤 · 회전 · 명령 전환<br>관측과 신경망 대조 실험</p></div><div class="roadmap-row"><div><strong>실제 공간</strong><span>DIGITAL TWIN</span></div><p>촬영에서 복원·충돌 바닥,<br>정책 실행까지 연결한 PoC</p><p>축척 · 지면 오차 · 관측 정합<br>같은 실제 지형에서 보행 평가</p></div><div class="roadmap-row"><div><strong>실기 항법</strong><span>TRACK B</span></div><p>순정 Go2 보행을 사용하는<br>항법 통합 방향 합의</p><p>센서 · 지도 · 경로 통합<br>목표 주행 · 정지 · 복귀 검증</p></div><div class="roadmap-gates"><span><b>MVP</b>현재의 출발점</span><i></i><span><b>11.07 · NAV</b>실기 항법 검증</span><i></i><span><b>12.11 · FINAL</b>전체 프로젝트 검증</span></div></div>',
        '이번 MVP에서는 실패를 먼저 확인하고, 학습 조건을 바꾸며 무엇이 개선되고 어디에 한계가 남는지 살폈습니다. 여기서 보행 연구가 끝나는 것은 아닙니다. 실제 공간을 가져오는 작업과 실기 항법도 함께 이어갑니다. 다음 관문은 실제 목표 주행을 검증하는 것이고, 마지막 발표까지 세 흐름을 함께 쌓아가겠습니다. 마지막으로, 저희 FOOTHOLD가 추구하는 가치를 담은 영상을 보시겠습니다.',
        link('기획발표 WBS · NAV 11/07 · FINAL 12/11', '../../../../deliverables/plan/proposal-deck-presented.html'),
        note='기존37·38쪽 통합. 일정은 프로젝트의 검증 관문이며 실제 달성을 보장하는 표가 아니다. Track B의 현재 칸은 통합 완료로 쓰지 않는다.'))

    result.append(make(
        'FOOTHOLD가 추구하는 가치',
        film('../../20260930-mvp-brand/_out/review/FULL_v6.mp4', 'FOOTHOLD 브랜드 영상', '../../20260930-mvp-brand/_out/keyvis/lib_thumbs/38-1355-nano-opening.jpg', sound=True),
        '영상을 시청합니다. 영상이 끝나면 다음 버튼으로 마무리 한 장, 이 로봇을 어느 현장에 먼저 보낼 것인지로 넘어갑니다.',
        kind='cinema', note='사용자가 승인한 브랜드 영상 파일을 그대로 사용. 소리 포함 자동 재생, 반복하지 않음. 브라우저가 재생을 막으면 controls의 재생 버튼을 사용.'))
    # ★ 2026-10-02 팀장 지시. 영상 뒤에 «어느 현장에 먼저 보낼 것인가» 로 마무리한다.
    #   숫자와 사례는 전부 기획서(deliverables/plan/proposal.md 2절) 인용이다.
    result.append(make(
        '잘 걷는 로봇을, 어느 현장에 먼저 보낼 것인가',
        '<div class="closing-target"><div class="target-primary"><span>먼저 겨냥하는 현장</span><h3>사람이 들어가기 어려운 곳의<br>반복 점검</h3><div class="target-sites"><div><b>산업 설비 플랜트</b><p>제철 · 양조 · 전력 설비의<br>고위험 구역 정기 점검</p></div><div><b>지하 공동구 · 터널</b><p>계단 · 경사 · 협소 통로가 섞인<br>반복 순찰 구간</p></div></div><p class="target-why">작업을 대신하는 로봇이 아닙니다. 사람보다 먼저 들어가<br>영상 · 온도 · 가스 · 설비 상태를 확인하는 로봇입니다.</p></div><div class="target-market"><div><span class="experiment-label">이미 도입</span><h3>National Grid</h3><p>고위험 설비 점검 주기 <b>연 1회 → 2주</b></p></div><div><span class="experiment-label">이미 도입</span><h3>AB InBev</h3><p>매주 약 <b>1,800건</b> 점검 · 첫 6개월에 이상 상태 <b>약 150건</b> 발견</p></div><div><span class="experiment-label">국내</span><h3>KCC건설 · 한국수자원공사</h3><p>공사 현장 안전관리 · 고위험 반복 점검에 도입 시작 (2026)</p></div><div class="target-path"><span>서비스까지</span><b>보행 검증 · MVP</b><i></i><b>목표 지점 자율 주행 · 11.07</b><i></i><b>현장 시연 · 12.11</b></div></div></div><p class="target-note">이번 단계의 범위는 보행 검증까지입니다. 실제 산업 투입과 방폭 운용은 그다음 단계입니다.</p>',
        '영상에서 보신 것처럼 저희가 만드는 것은 잘 걷는 로봇입니다. 그 로봇을 어디에 먼저 보낼지도 정했습니다. 사람이 들어가기 어려운 현장의 반복 점검입니다. 제철소나 양조장 같은 산업 설비, 그리고 지하 공동구와 터널입니다. 이미 실제 도입 사례가 있습니다. National Grid 는 로봇 도입 뒤 고위험 설비 점검 주기를 연 1회에서 2주로 줄였고, AB InBev 는 매주 1,800건을 점검합니다. 국내에서도 KCC건설과 한국수자원공사가 도입을 시작했습니다. 저희는 보행 검증을 지나 목표 지점 자율 주행, 그리고 현장 시연으로 갑니다. 이번 단계의 범위는 보행 검증까지이고, 실제 산업 투입은 그다음입니다.',
        link('기획서 2절 · 도입 사례와 적용 후보', '../../../../deliverables/plan/proposal.md'),
        note='팀장 지시(2026-10-02): 단순 실험이 아니라 비즈니스·서비스로 보이게 특정 타깃으로 마무리. 근거는 기획서 2절(도입 사례 · National Grid, AB InBev, KCC건설, 한국수자원공사)과 적용 후보(지하 공동구·터널·산업 설비 점검). 1차 타깃을 산업 설비 플랜트로 둔 것은 덱 6~7쪽의 사례(AB InBev, 제철)와 맞춘 선택이다. 기획서 「실제 산업 투입·재난 대응·방폭 운용은 범위 밖」을 화면에서 지우지 않는다. 숫자는 기획서 인용이며 우리 실측이 아니다.'))
    result.append(make(
        'Q&A', '<div class="closing-qa">Q&amp;A</div>',
        '질문 있으시면 말씀해 주십시오. 질의응답이 끝나면 마지막 장으로 넘기겠습니다.',
        kind='qa-slide', note='Q&A만 중앙에 크게 표시. 다른 텍스트나 로고를 추가하지 않는다.'))
    result.append(make(
        'FOOTHOLD · 내일의 발걸음', original_closing(),
        '발표 서두에 말씀드렸듯이, 저희가 원하는 목표는 뚜렷합니다. 어느 환경에서도 잘 걷는 로봇을 만드는 것입니다. 지금까지 내일의 발걸음이 기대되는 팀 FOOTHOLD의 오흥재였습니다. 감사합니다.',
        kind='qa-slide', note='기획발표 원본19장의 로고·QR·URL·팀원·소속·프로젝트기간 DOM을 그대로 읽어 재사용. 그림으로 재생성하지 않음.'))
    return result


def revise_closing(slides):
    """Mutate the existing dict list after U205 refine; preserve every earlier slide."""
    anchors = ('세 작업은 프로젝트 끝까지 함께 이어집니다',
               '실제 공간을, 보행을 시험할 공간으로 가져오고 있습니다')
    start = next((i for i, s in enumerate(slides) if s['title'] in anchors), None)
    if start is None:
        raise ValueError('U206 closing anchor not found; refusing to replace by page number')
    slides[start:] = closing_slides()
    return slides
