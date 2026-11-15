"""U205: continuous product explanation, not independent picture cards."""
import re
from .intro_story import make, src, TERRAIN

FRONT='../assets/go2-blender/go2-front-v5.png'   # 2026-10-05: 10쪽 캔버스 첫 프레임과 같은 카메라(v4 는 화각이 달랐다)
def hero(cls='',shared=True):
    return f'<div class="robot-cutout {cls}"'+(' data-shared="go2"' if shared else '')+f'><img src="{FRONT}" alt="정면을 바라보는 Unitree Go2"></div>'

def leader(key,points,x,y):
    return f'<path class="leader" d="{points}"/><circle class="anchor" cx="{x}" cy="{y}" r="4"/>'

def refine(slides):
    # Cover remains the approved original; this function starts with film at slides[0].
    slides[0]['body']=slides[0]['body'].replace('<video controls','<video data-autoplay controls')
    slides[0]['spoken']='사실 우리가 프로젝트를 통해서 하고자 하는 목적의 메시지는 매우 단순합니다. 사족보행 로봇을 어느 환경이든 잘 걷게 하는 것입니다.'
    slides[1]=make('연구의 출발','왜 로봇을 잘 걷게 하는 것이 중요할까요?',
        '<div class="questions-scene">'+hero('question-robot',False)+'<canvas class="pixel-go2 question-pixel" width="256" height="256" data-row="0" aria-label="Go2가 픽셀로 바뀌어 진행 표시로 이동"></canvas><div class="question-links" data-step="1"><i></i><i></i><i></i></div><div class="questions" data-step="1"><div><small>임무를 수행하려면</small><h3>왜 잘 걸어야 할까요?</h3></div><div><small>다양한 이동 방식 중</small><h3>왜 사족보행일까요?</h3></div><div><small>학습하지 않은 조건에서</small><h3>왜 잘 걷기 어려울까요?</h3></div></div></div>',
        '왜 로봇을 잘 걷게 하는 것이 중요할까요? 왜 우리는 다양한 이동 로봇 중에서도 사족보행 로봇에 집중하고 있는 것일까요? 그리고 왜 로봇을 잘 걷게 하는 것은 어려운 것일까요? 이 질문들을 따라가면, 왜 미경험 험지 적응 정책을 연구하는지 말씀드릴 수 있을 것 같습니다.',kind='intro authored questions-page',steps=2)
    slides[2]['spoken']='너무나 당연한 질문이겠죠? 시청 자료에서 봤듯이 로봇에게 특정 임무가 주어지고, 그 임무를 수행하기 위해서는 경험하지 않은 험지를 지나가야 합니다. 기본적으로 잘 걷는 것이 첫 번째 필수 수행 능력입니다.'
    slides[2]['kind']+=' authored'
    slides[3]['kind']+=' authored'
    slides[3]['body']=f'''<img class="terrain-world" data-shared="terrain" src="{TERRAIN}" alt="점검 목표까지 이어지는 불규칙한 디딤"><div class="terrain-shade"></div>
      <div class="terrain-heading"><small>UNSEEN TERRAIN</small><h2>미경험 험지란 무엇일까요?</h2><p>학습 때 경험한 조건을 벗어나도, 다음 발을 디딜 수 있을까요?</p></div>
      <svg class="terrain-lines" viewBox="0 0 1600 900" aria-hidden="true"><g data-step="1">{leader('geometry','M630 558 L490 380 L410 380',630,558)}</g><g data-step="2">{leader('support','M905 578 L1040 388 L1110 388',905,578)}</g><g data-step="3">{leader('contact','M915 778 L1040 600 L1110 600',915,778)}</g></svg>
      <div class="terrain-tag gap-tag" data-step="1"><small>형태 / GEOMETRY</small><h3>틈 · 단차 · 경사</h3><p>발을 얼마나 높이, 멀리 옮길까?</p></div>
      <div class="terrain-tag width-tag" data-step="2"><small>배치 / SUPPORT</small><h3>좁은 폭 · 불규칙한 디딤</h3><p>어디를 밟고, 몸을 지탱할까?</p></div>
      <div class="terrain-tag material-tag" data-step="3"><small>접촉 / CONTACT</small><h3>마찰 · 미끄러움 · 재료 강도</h3><p>딛은 발은 버티고, 지지해 줄까?</p></div>
      <p class="terrain-scope" data-step="3">현실의 조건들 · 이번 MVP에서는 학습에 넣지 않은 지형에서 정책을 평가했습니다.</p>'''
    slides[3]['steps']=3
    slides[3]['spoken']='그렇다면 미경험 험지란 무엇일까요? 현실 속의 지형은 틈과 단차, 경사도, 디딜 수 있는 폭과 불규칙성이 다릅니다. 바닥의 마찰, 재료 강도, 미끄러움도 달라집니다. 로봇은 학습 때 경험한 조건을 벗어나도 다음 발을 디딜 수 있을까요? 잘 걷는다는 것은 이런 조건들을 함께 극복한다는 뜻입니다. 그럼 실제 현장에서는 사족보행 로봇을 어떻게 활용하고 있을까요?'
    slides[4]=make('현장의 필요','실제 현장에서는 어떤 임무를 맡길까요?',
      '<div class="industry-scene">'+hero('industry-robot')+'''<svg class="industry-connections" viewBox="0 0 1472 570" aria-hidden="true"><g data-step="1"><circle class="robot-ring" cx="736" cy="278" r="172"/><path class="leader" d="M579 208 L506 160 L430 160 M893 208 L966 160 L1042 160"/></g><g data-step="2"><path class="leader" d="M579 348 L506 410 L430 410 M893 348 L966 410 L1042 410"/></g></svg>
      <article class="industry-box fire-box" data-step="1"><small>소방 · 공공 수요</small><h3>대원보다 먼저, 현장 정보를</h3><p>현장 지휘 지원과 대원 안전 확보</p><a href="https://www.mss.go.kr/site/smba/ex/bbs/View.do?bcIdx=1067938&cbIdx=310" target="_blank">서울시 소방본부 · 보행 로봇 수요</a></article>
      <article class="industry-box factory-box" data-step="1"><small>제조 · 안전 순찰</small><h3>사람 · 고온 · 출입 상태 확인</h3><p>야간 공장 순찰과 위험 요소 탐지</p><a href="https://robotics.hyundai.com/story/media/view.do?seq=35" target="_blank">기아 오토랜드 광명 · Spot 시범운영</a></article>
      <article class="industry-box steel-box" data-step="2"><small>제철 · 설비 점검</small><h3>고로의 상태를 열화상으로</h3><p>무인화 시험에서 송풍지관 44개 데이터 수집</p><a href="https://newsroom.posco.com/kr/기술잇수다-4편-네-발로-제철소-곳곳-누비며-안전-책/" target="_blank">포스코 광양 1고로 · Spot</a></article>
      <article class="industry-box value-box" data-step="2"><small>사람에게 돌아오는 가치</small><h3>위험 노출을 줄이고, 대응에 집중</h3><p>접근 → 관측 → 이상 확인 → 대응</p><span>그렇다면 실제 운영 효과는 어떨까요?</span></article><div class="platform-caption" data-step="1">중앙: 연구 플랫폼 Go2 · 현장 사례: 각 기관의 보행 로봇</div></div>''',
      '실제 사족보행 로봇은 여러 특수 임무를 가지고 다양한 산업군에서 활용되고 있습니다. 소방에서는 대원보다 먼저 현장 정보를 확보하려는 공공 수요가 있고, 공장에서는 안전 순찰, 제철소에서는 설비 점검을 맡깁니다. 포스코 광양 1고로의 무인화 시험에서는 44개 송풍지관의 데이터를 수집했습니다. 공통점은 위험한 곳에 먼저 가거나 반복적인 확인을 맡긴다는 것입니다. 그렇다면 로봇을 도입한 뒤 사람의 업무는 어떻게 달라질까요?',src('국내 사례와 도입 단계','../PPT-INTRO-SOURCES-20261001.md'),kind='intro authored industry-page',steps=2)
    slides[5]['kind']='intro authored economy-page'
    slides[5]['body']='''<div class="economy-scene"><figure class="case-photo"><img src="../assets/deck-ab-inbev-spot.jpg" alt="AB InBev 현장의 Spot"><figcaption>AB INBEV · 벨기에 루벤 양조장 / Boston Dynamics</figcaption></figure><div class="economy-evidence"><small>반복 점검에서, 실제 문제 해결로</small><h3>로봇이 점검하고,<br>사람은 수리에 집중합니다.</h3><div class="work-change"><span>설비를 멈춰 누출 소리 확인</span><b>가동 중 누출 감지 · 이상 위치 전달</b></div><div class="economic-metrics" data-step="1"><div><b>1,800<span>회 / 주</span></b><p>개별 점검 수행</p></div><div><b>약 150<span>건</span></b><p>첫 6개월 이상 징후</p></div></div><div class="repair-change" data-step="2"><span>평균 수리 기간</span><strong><s>수개월</s> → 13일</strong></div></div></div>'''
    slides[5]['spoken']='실제 고객 사례를 하나 보겠습니다. AB InBev 양조장에서는 Spot이 일주일에 1,800회의 개별 점검을 수행합니다. 가동 소음 속에서 누출을 찾아 이상 위치를 전달하고, 사람은 수리와 예방정비에 집중합니다. 첫 6개월 동안 약 150건의 이상 징후를 발견했고 평균 수리 기간은 수개월에서 13일로 줄었다고 합니다. 이렇게 로봇이 우리에게 줄 수 있는 가치는 크지 않을까요? 그렇다면 이런 임무를 수행하는 로봇이 꼭 사족보행이어야 할까요?'
    slides[6]['kind']='intro authored mobility-page'
    slides[6]['body']='''<div class="mobility-scene"><div class="mobility-option" data-step="1"><figure><img src="../assets/elios-isolated-u206.png" alt="Elios 3 점검 드론"></figure><small>공중으로 접근</small><h3>드론</h3><p>높은 곳 · 폐쇄 공간 점검</p><p class="tradeoff">체공 시간과 탑재·접촉 조건을 고려</p></div><div class="mobility-option main-option">'''+hero('mobility-robot')+'''<small>디딤을 선택하며 이동</small><h3>사족보행</h3><p>틈 · 단차 · 불연속적인 바닥</p><p class="tradeoff">균형과 접촉, 관절을 함께 제어</p></div><div class="mobility-option" data-step="1"><figure><img src="../assets/b2w-isolated-u206.png" alt="Unitree B2-W"></figure><small>굴러가고, 걸어가고</small><h3>바퀴 · 다리 결합</h3><p>이어진 노면과 단차에 대응</p><p class="tradeoff">경로에 맞춰 이동 방식을 선택</p></div></div><p class="mobility-conclusion" data-step="1">모두 정답이 될 수 있습니다. <b>임무와 지형에 맞는 몸체를 선택합니다.</b></p>'''
    slides[6]['spoken']='그럼 다양한 이동 로봇이 있는데 꼭 사족보행 로봇이어야 할까요? 맞습니다. 이동 로봇에는 다양한 몸체를 가진 로봇이 많습니다. 드론, 사족보행 로봇, 바퀴와 다리가 달린 로봇, 이족보행까지 있습니다. 사실 모두가 정답이라고 할 수 있습니다. 드론은 공중에서 접근하고, 바퀴는 이어진 노면에서 강점이 있습니다. 각각의 목적성이 있는 것입니다. 다만 저희는 불연속적인 바닥에서 발을 옮겨 가며 목적지에 도달하는 과제에 집중했습니다.'
    slides[7]['kind']='intro authored choice-page'
    slides[7]['body']='<div class="choice-scene">'+hero('choice-robot')+'''<div class="choice-copy"><small>우리가 선택한 연구 과제</small><h3>발을 옮겨,<br>지지점을 바꾸는 이동.</h3><p>디딜 곳을 선택하고<br>움직이는 동안 몸의 균형을 유지합니다.</p><div class="support-sequence" data-step="1"><span>지형</span><span>디딤</span><span>균형</span></div><h4 data-step="2">그렇다면, 왜 잘 걷게 하는 것이 어려울까요?</h4></div></div>'''
    slides[7]['spoken']='이러한 이유로 우리는 발을 하나씩 옮기고 지지점을 바꾸면서 몸의 균형을 유지하는 이동에 주목했습니다. 주어진 지형에서 사용자의 임무를 수행할 수 있도록 사족보행 로봇을 선택해 실험을 진행한 것입니다. 그럼 왜 사족보행 로봇을 잘 걷게 하는 것이 어려운지, 우리가 집중해서 풀어갈 과제가 무엇인지 설명드리겠습니다.'
    # U207: retain the three WHY questions; remove only pixel migration.
    slides[1]['body']=re.sub(r'<canvas class="pixel-go2 question-pixel".*?</canvas>', '', slides[1]['body'])
    slides[1]['steps']=1
    # 넘김 표시는 build_presentation 이 전체 장에 «별도 줄» 로 만든다.
    # 멘트 본문에 끼우면 읽을 때 걸린다 (2026-10-02).

    # Ring stays outside all four feet; connectors meet its circumference.
    slides[4]['body']=slides[4]['body'].replace('r="172"','r="190"').replace('M579 208','M559.4 208').replace('M893 208','M912.6 208').replace('M579 348','M559.4 348').replace('M893 348','M912.6 348')
    # The former seven-page technical introduction becomes three continuous scenes.
    from .technical_scene import technical_slides
    end=next(i for i,s in enumerate(slides) if s['title']=='무엇을 더 가르칠지, 실패에서 찾았습니다')
    slides[8:end]=technical_slides()

USER_COVER_NOTES='''<h2>FOOTHOLD의 첫걸음</h2><h3>발표 멘트</h3><p>오늘 발표를 하기 앞서, 이번 프로젝트는 저희에게 굉장히 어려운 프로젝트였습니다.</p><p>저희는 사족보행 로봇의 보행을 연구하고 탐구하는 것이 마치 아기가 한 걸음 한 걸음 발걸음을 내디디며 세상을 향해 걸음마를 시작하는 것과 닮았다고 생각했습니다.</p><p>아직은 어린 아기가 세상을 향해 내딛는 한 걸음을 지켜보는 아빠의 마음이랄까요? 이런 마음을 먼저 공유해드리면서, 우리의 도전적인 첫 발걸음은 어떻게 시작됐는지 그 과정을 소개하겠습니다.</p><p>안녕하세요. 4족보행 Unitree Go2 미경험 험지 적응 정책 프로젝트의 발표를 맡은 FOOTHOLD 팀장 오흥재입니다.</p><p>본격적인 발표에 앞서, 우리 프로젝트가 무엇에 집중하고 어떤 과제를 풀려고 하는지, 저희가 Isaac Sim에서 학습한 내용을 바탕으로 만든 영상을 먼저 시청하시겠습니다.</p><h3>진행</h3><p>다음 버튼을 누르면 전체 영상이 바로 재생됩니다. 영상이 끝나면 다음 버튼으로 질문 장면에 진입합니다.</p>'''
