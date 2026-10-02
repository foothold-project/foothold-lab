# -*- coding: utf-8 -*-
"""세 기둥(Track A · Bridge Digital Twin · Track B) 되짚기 + 다음 PoC 흐름 한 장 · 33쪽 kicker.

팀장 지시 2026-10-02:
  - 30·31 사이에 우리 Track A / Track B / Bridge(Digital Twin) 기존 계획을 한 번 언급하고,
    디지털 트윈 과정인 다음 PoC 실험을 간단히 소개한다(기획 발표 자료 가져와도 됨).
  - 33쪽 「다음 실험은 지형·명령·관측을 함께 보되…」 는 Track A 의 남은 과제·다음 걸음임이 보여야 한다.

근거(문구는 여기서만 가져온다 · 지어내지 않는다):
  - deliverables/plan/assets/overview.svg          세 기둥 제목 · 물음 · 도구 줄 · 「하나의 제어 파이프라인으로 연결하지 않는다」
  - deliverables/plan/proposal.md 1절               세 축 표 · 범위 밖(2026-08-19 합의 · 저수준 정책 이식 제외)
  - inbox/jay/20260916-3dgs-test/RESULTS-3dgs-terrain.md §0 §10   PoC 8 단계 · «통과»는 관문 통과이지 품질 판정 아님 · 남은 일
  - inbox/jay/20260916-3dgs-test/DESIGN-real-to-sim.md §1-2 §4 §5-1 §6 §7 §11   다음 PoC 절차 · 합격선(제안) · 재촬영 · 축척 · 평가 하네스
  - SECTION-MAP.md 2.5 · 6.5 · 6.6 · 10.3            정책 이식 화살표 금지 · 3DGS 시각 재현 ≠ 물리 지형 검증
  - 이 덱 31·32·33·34쪽(closing_revision.py)         현재 상태 문구와 톤

끼우는 자리: 「실제 공간을, 보행을 시험할 공간으로 가져오고 있습니다」 바로 앞 · 같은 section(다음 걸음).
단계: steps=1 · 「지금 어디까지」는 0단계부터(팀장: 아래가 비어 보였다) · spoken 의 (클릭) 1개 == steps (아래 assert).
"""
from .intro_story import make, src

TWIN_TITLE = '실제 공간을, 보행을 시험할 공간으로 가져오고 있습니다'
NEXT_TITLE = '다음 실험은 지형·명령·관측을 함께 보되, 바꾸는 원인을 나누겠습니다'
BRIDGE_TITLE = '기획 때 세운 세 기둥 위에서, 지금 어디까지 왔는지 짚고 갑니다'

CLICK = '(클릭)'


def _pillar(cls, kicker, question, easy, tools, now_lines):
    tools_html = ''.join(f'<li>{t}</li>' for t in tools)
    now_html = ''.join(f'<p>{t}</p>' for t in now_lines)
    return (f'<article class="pillar {cls}">'
            f'<small>{kicker}</small>'
            f'<h3>{question}</h3>'
            f'<p class="easy">{easy}</p>'
            f'<ul class="tools">{tools_html}</ul>'
            f'<div class="now reveal" data-step="0"><span>지금 어디까지</span>{now_html}</div>'
            f'</article>')


def bridge_slide():
    pillars = (
        '<div class="pillars">'
        + _pillar('track-a', 'TRACK A · 시뮬레이션과 강화학습', '어디까지 걸을 수 있는가',
                  '시뮬레이션 안에서 걷는 법을 배우고,<br>낯선 지형에서 얼마나 걷는지 잽니다.',
                  ['Isaac Sim · Isaac Lab · PPO 학습', '절차적 확장 지형 · 난이도 단계', '미경험 지형 평가 · held-out 원본',
                   '<b>난이도 경계와 이동 폭</b> · 생존 · 전진 · 속도추종 · 이탈'],
                  ['오늘 보신 <b>foothold-v2</b> 까지 · 남은 과제는 뒤 장에서', '미경험 8종 통과 개선 · 정지 전환 낙상 감소'])
        + _pillar('bridge', 'BRIDGE · DIGITAL TWIN (REAL TO SIM)', '두 트랙이 평가에 쓸 공간',
                  '진짜 장소를 찍어서, 로봇이 걸어 볼 수 있는<br>가상 공간으로 다시 세웁니다.',
                  ['3DGS 로 실제 공간을 복원', '배경(보이는 것)과 충돌 지형(발이 닿는 것)을 따로', 'Isaac Sim USD 로 두 트랙이 같은 공간을 평가',
                   '<b>원본 구간은 학습에 쓰지 않는 held-out 평가장</b>'],
                  ['촬영 → 3DGS → 메시 → USD → 정책 실행 · <b>9/16 PoC</b> 한 번',
                   '축척 · 실제 지면 오차 · 충돌·관측 정합은 <b class="warn">미검증</b> · 다음 장'])
        + _pillar('track-b', 'TRACK B · 실기 자율 보행', '목표까지 스스로 갈 수 있는가',
                  '진짜 로봇이 지도를 만들고 길을 찾아<br>목표까지 갑니다. 걷기는 Go2 순정 보행입니다.',
                  ['Unitree Go2 · LiDAR · 카메라 · IMU', 'ROS 2 · SLAM 지도와 위치 · YOLO 인지', 'Nav2 경로 계획과 재계획',
                   '<b>목표 지점 자율 보행</b> · 도달률 · 무충돌 · 재계획 성공률'],
                  ['순정 보행 위 항법으로 범위 확정 (8/19 합의 · 그다음 장)', '우리 학습 정책의 실기 이식은 <b>목표가 아님</b>'])
        + '</div>'
        + '<p class="pillar-rule">두 트랙을 하나의 제어 파이프라인으로 연결하지 않습니다. Bridge 가 복원한 <b>같은 실제 공간</b>을 기준으로 각각 검증합니다.</p>'
    )
    flow_cells = [
        ('촬영', '다시 찍는다', '낮게 · 지그재그 · 10 m 이상<br>폰 원본 · 축척 기준 포함'),
        ('3DGS 복원', '사진으로 공간을 세운다', 'COLMAP 카메라 포즈<br>→ 3D Gaussian Splatting'),
        ('충돌 메시', '발이 닿을 바닥을 만든다', '2.5D 높이 격자 + 대조군<br>(Poisson · COLMAP dense)'),
        ('Isaac USD', '시뮬레이션에 넣는다', '배경(NuRec)과 충돌체를<br>따로 만들어 겹친다'),
        ('정책 실행', '걸려 본다', 'sim/eval 하네스 · heading 고정<br>100판 · 평지 기준선과 나란히'),
        ('검증', '맞는지 잰다', '축척(규격 대조 · 실측) · 바닥 오차<br>±2 cm(제안 합격선) · 스캔 유한값'),
    ]
    flow = '<div class="poc-flow reveal" data-step="1"><small>다음 PoC · DIGITAL TWIN 의 흐름 · 아직 수행 전</small><div class="cells">'
    for i, (name, easy, hard) in enumerate(flow_cells):
        flow += f'<div class="cell"><b>{name}</b><p>{easy}</p><span>{hard}</span></div>'
        if i < len(flow_cells) - 1:
            flow += '<i class="arrow"></i>'
    flow += ('</div><p class="poc-note">9/16 PoC 의 «통과»는 파일 생성 · 실행 관문을 지났다는 뜻이지 품질 판정이 아닙니다. '
             '보기 좋은 복원과 물리적으로 맞는 바닥은 다릅니다.</p></div>')
    body = '<div class="bridge-wrap">' + pillars + flow + '</div>'
    spoken = ('보행 정책 이야기는 여기까지입니다. 잠깐 기획 발표 때 세운 그림으로 돌아가겠습니다. 기둥이 셋입니다. '
              '왼쪽 Track A 는 시뮬레이션과 강화학습으로 「어디까지 걸을 수 있는가」를 묻습니다. '
              '가운데 Bridge, Digital Twin 은 실제 공간을 3DGS 로 복원해 두 트랙이 평가에 쓸 공간을 만듭니다. '
              '오른쪽 Track B 는 실제 로봇이 「목표까지 스스로 갈 수 있는가」를 묻습니다. '
              '두 트랙을 하나의 제어 파이프라인으로 잇지 않고, 같은 실제 공간을 기준으로 각각 검증합니다. '
              '지금 어디까지 왔는지 보면, Track A 는 오늘 보여드린 v2 까지입니다. '
              'Bridge 는 촬영에서 3DGS 복원, 충돌 메시, Isaac Sim USD, 정책 실행까지 한 번 이어 본 PoC 단계이고 다음 장에서 보여드립니다. '
              'Track B 는 순정 Go2 보행 위에 ROS 2, SLAM, Nav2 를 올리는 항법이고, 저희 학습 정책을 실기에 옮기는 것은 목표가 아닙니다. 그다음 장에서 설명합니다. '
              '(클릭) 그래서 다음 PoC 는 Digital Twin 입니다. 흐름은 한 줄입니다. 다시 촬영하고, 3DGS 로 복원하고, 발이 닿을 충돌 메시를 만들고, '
              'Isaac Sim USD 로 넣고, 정책을 걸려 보고, 축척과 관측과 바닥이 맞는지 검증합니다. '
              '복원이 보기 좋은 것과 물리적으로 맞는 바닥인 것은 다릅니다. 축척, 실제 지면 대비 정확도, 충돌과 관측의 정합은 아직 남은 일입니다.')
    assert spoken.count(CLICK) == 1
    source = (src('기획서 1절 · 세 축', '../../../../deliverables/plan/proposal.md') + ' · '
              + src('Real-to-Sim 설계안 · 다음 PoC 절차', '../../20260916-3dgs-test/DESIGN-real-to-sim.md'))
    return make('다음 걸음', BRIDGE_TITLE, body, spoken, source,
                kind='closing-revision bridge-page', steps=1,
                note='세 기둥의 제목·물음·도구 줄은 기획서 overview.svg 문구를 그대로 옮겼다. '
                     '「지금 어디까지」는 이 덱의 앞 장(v2 성과)과 9/16 PoC 결과(RESULTS-3dgs-terrain.md), 8/19 합의(기획서 1절 범위 밖)에서만 가져왔다. '
                     'PoC 흐름 여섯 칸은 DESIGN-real-to-sim.md 의 재촬영(7절) · 방법 비교(5-1) · 축척(6절) · 평가 하네스(11-2) · 합격선(4절, 제안)이다. '
                     '아직 수행 전 계획이며 Track B 의 현재 진척은 근거 미확인이라 완료로 적지 않았다.')


def apply(slides):
    titles = [s['title'] for s in slides]
    assert BRIDGE_TITLE not in titles
    i = titles.index(TWIN_TITLE)
    slides.insert(i, bridge_slide())
    nxt = next(s for s in slides if s['title'] == NEXT_TITLE)
    assert 'track-a-kicker' not in nxt['body']
    nxt['body'] = '<p class="track-a-kicker">TRACK A · 남은 과제 · 다음 걸음</p>' + nxt['body']
    nxt['kind'] = (nxt.get('kind', '') + ' track-a-next-page').strip()
    return slides
