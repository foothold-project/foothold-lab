"""U202: authored introduction and closing. Research body stays for the next review."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
TERRAIN='../assets/terrain-question-bright-v1.png'
GO2='../assets/go2-reference/go2-character-sunburst-v1.png'

def robot(extra=''):
    return f'<div class="go2-disc {extra}" data-shared="go2"><div class="go2-art" role="img" aria-label="승인된 Go2 캐릭터 시트의 정면" style="background-image:url({GO2})"></div></div>'

def sprite(cls='',row=0):
    return f'<canvas class="pixel-go2 {cls}" width="256" height="256" data-row="{row}" aria-label="픽셀 Go2 동작 애니메이션"></canvas>'

def terrain():
    return f'<img class="terrain-world" data-shared="terrain" src="{TERRAIN}" alt="물 위로 끊긴 디딤과 불규칙한 바닥이 이어지는 산업 공간">'

def src(label,url):
    return f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'

def make(section,title,body,spoken,source='',kind='intro',steps=0,note=''):
    return dict(section=section,title=title,body=body,spoken=spoken,note=note or spoken,source=source,kind=kind,steps=steps)

COVER_NOTES='''<h2>FOOTHOLD의 첫걸음</h2><h3>발표 멘트</h3><p>이번 프로젝트는 저희에게 쉽지 않은 도전이었습니다. 로봇의 보행을 연구하다 보니, 아기가 한 걸음씩 배우며 세상으로 나가는 모습과 닮았다고 느꼈습니다.</p><p>넘어져도 다시 일어나 다음 발을 내딛길 바라는 아빠의 마음이랄까요. 오늘은 저희가 그 실패를 보면서 어떻게 한 걸음을 내디뎠는지 말씀드리겠습니다.</p><p>안녕하세요. Unitree Go2 미경험 험지 적응 정책 프로젝트의 발표를 맡은 FOOTHOLD 팀장 오흥재입니다.</p><p>먼저 저희가 Isaac Sim에서 학습한 내용을 바탕으로 만든 영상을 보시겠습니다. 저희가 어떤 과제에 집중하고 있는지 담았습니다.</p><h3>다음 장면</h3><p>다음 버튼으로 전체 영화 화면에 들어간 뒤 V 또는 재생 버튼을 누릅니다. 자동으로 다음 페이지로 넘기지 않습니다.</p>'''

def intro():
    hmg='https://robotics.hyundai.com/story/media/view.do?seq=35'
    posco='https://newsroom.posco.com/kr/기술잇수다-4편-네-발로-제철소-곳곳-누비며-안전-책/'
    fire='https://www.mss.go.kr/site/smba/ex/bbs/View.do?bcIdx=1067938&cbIdx=310'
    ab='https://bostondynamics.com/case-studies/energy-savings-predictive-maintenance-at-ab-inbevs-largest-european-brewery/'
    items=[]
    items.append(make('현장의 필요','우리가 향하는 곳',
        f'<figure class="film"><video controls playsinline preload="metadata" poster="{TERRAIN}" src="../assets/film-master-v8.mp4"></video><figcaption>FOOTHOLD 전체 영상</figcaption></figure>',
        '사실 저희가 하고자 하는 일은 단순합니다. 사족보행 로봇이 낯선 환경에서도 잘 걷게 하는 것입니다. 영상이 끝나면 그 목표가 왜 중요한지부터 말씀드리겠습니다.',kind='cinema'))
    items.append(make('연구의 출발','왜, 잘 걷는 로봇인가?',
        '<div class="question-stage">'+sprite('hero-pixel')+'<div class="pixel-caption">UNITREE GO2</div><div class="question-trio" data-step="1"><div><small>임무</small><h3>왜 잘 걸어야 할까요?</h3><p>목적지에 닿아야, 임무를 시작합니다.</p></div><div><small>이동 방식</small><h3>왜 사족보행일까요?</h3><p>어떤 길에서, 어떤 몸체가 적합할까요?</p></div><div><small>연구 과제</small><h3>왜 낯선 바닥이 어려울까요?</h3><p>배운 조건 밖에서도, 다음 발을 디딜 수 있을까요?</p></div></div></div>',
        '잘 걷게 하자는 목표는 단순해 보입니다. 그런데 세 가지 질문이 남습니다. 왜 잘 걸어야 하는지, 왜 사족보행을 선택했는지, 그리고 낯선 바닥에서 걷는 일이 왜 어려운지입니다. 먼저 영상 속 이 길을 다시 보겠습니다.',steps=1))
    items.append(make('현장의 필요','이 길을 건너, 점검 지점까지 가려면?',
        terrain()+'<div class="terrain-shade"></div><div class="mission-target" data-step="1"><span class="target-box"></span><div><small>INSPECTION TARGET</small><b>설비 상태 확인</b><span>촬영 · 점검 정보 전송</span></div></div><div class="terrain-claim"><small>MISSION / ACCESS</small><h2>임무의 시작은<br>목적지에 닿는 것.</h2><p data-step="1">센서가 있어도, 그곳까지 갈 수 있어야 합니다.</p></div>',
        '로봇에게 점검 임무가 주어졌습니다. 저 멀리 설비에 도착해야 촬영하고 정보를 보낼 수 있습니다. 그런데 그 앞에는 끊긴 바닥과 좁은 디딤이 있습니다. 임무를 수행하기 위한 첫 번째 조건이 바로 이 길을 잘 걷는 것입니다.',kind='intro terrain-slide',steps=1))
    items.append(make('연구의 출발','미경험 험지란 무엇일까요?',
        terrain()+'<div class="terrain-shade"></div><svg class="terrain-lines" viewBox="0 0 1600 900" aria-hidden="true"><path data-step="1" d="M735 555 L495 380 L260 380 M1010 665 L1185 445 L1430 445"/><path data-step="2" d="M970 770 L1110 680 L1420 680"/><circle cx="735" cy="555" r="5" data-step="1"/><circle cx="1010" cy="665" r="5" data-step="1"/><circle cx="970" cy="770" r="5" data-step="2"/></svg><div class="terrain-heading"><small>UNSEEN TERRAIN</small><h2>학습 때와 다른 바닥.</h2><p>경험한 조건 밖에서도, 다음 발을 디딜 수 있을까요?</p></div><div class="terrain-tag gap-tag" data-step="1"><small>형태 / GEOMETRY</small><h3>틈 · 단차 · 경사</h3><p>발을 얼마나 높이, 얼마나 멀리 옮길까?</p></div><div class="terrain-tag width-tag" data-step="1"><small>배치 / SUPPORT</small><h3>좁은 폭 · 불규칙한 디딤</h3><p>어디를 밟고, 어디에 몸을 지탱할까?</p></div><div class="terrain-tag material-tag" data-step="2"><small>재료 / CONTACT</small><h3>마찰 · 젖음 · 지반 강도</h3><p>딛은 발이 미끄러지거나 꺼지지는 않을까?</p></div><div class="terrain-scope" data-step="2">현실의 변수 예시 · 이번 MVP는 학습에 넣지 않은 지형에서 정책을 평가</div>',
        '미경험은 단순히 험해 보인다는 뜻이 아닙니다. 로봇이 학습한 조건과 다른가의 문제입니다. 틈의 폭과 높이, 경사와 디딤의 배치가 달라집니다. 현실에서는 마찰과 재료 강도까지 달라집니다. 로봇은 그런 차이 속에서도 다음 발을 디딜 수 있을까요? 먼저 실제 현장에서는 어떤 임무를 맡기는지 보겠습니다.',kind='intro terrain-slide',steps=2,
        note='원경은 영화용 이미지. 재료 특성을 사진에서 측정한 것이 아니다. 모든 현실 변수를 현재 MVP에서 검증했다고 말하지 않는다. 이 페이지의 확대는 같은 지형 이미지 내에서만 한다.'))
    items.append(make('현장의 필요','위험한 곳에 먼저 가고, 반복 점검을 맡습니다',
        '<div class="industry-map">'+robot()+'<svg class="orbit-lines" viewBox="0 0 1472 490"><path d="M610 242 L485 80 L290 80 M862 242 L1010 80 L1180 80 M610 270 L460 408 L270 408 M862 270 L1010 408 L1190 408"/></svg><article class="mission-node n-fire" data-step="1"><small>소방 · 현장 대응 / 수요</small><h3>대원보다 먼저 현장 정보를</h3><p>현장 지휘 지원 · 대원 안전 확보<br><small>보행 로봇 공공 수요</small></p><a href="'+fire+'" target="_blank">서울시 소방본부 · 정부 수요 공고</a></article><article class="mission-node n-factory" data-step="1"><img class="case-thumb" src="../assets/intro-kia-factory-spot.jpg" alt="기아 공장의 Spot"><small>제조 · 안전 순찰 / 시범운영</small><h3>사람 · 고온 · 출입 상태 확인</h3><p>야간 공장을 순찰하며 위험 요소 탐지</p><a href="'+hmg+'" target="_blank">기아 오토랜드 광명 · Spot</a></article><article class="mission-node n-steel" data-step="2"><img class="case-thumb" src="../assets/intro-posco-blast-furnace.jpg" alt="포스코 고로의 Spot 점검"><small>제철 · 설비 점검 / 현장 운영</small><h3>무인화 시험: 송풍지관 44개</h3><p>열화상으로 이상 징후 확인</p><a href="'+posco+'" target="_blank">포스코 광양 1고로 · Spot 현장 적용</a></article><article class="mission-node n-value" data-step="2"><small>사람에게 돌아오는 가치</small><h3>노출은 줄이고, 판단에 집중</h3><p>접근 → 관측 → 이상 확인 → 대응</p><span>그러면 실제 운영 효과는 어떨까요?</span></article></div>',
        '소방 현장에서는 대원의 안전을 확보하고 지휘에 필요한 정보를 얻는 보행 로봇의 수요가 있습니다. 공장에서는 야간 안전 순찰, 제철소에서는 설비 점검을 맡깁니다. 광양 1고로 무인화 시험에서는 44개 송풍지관의 데이터를 자동 수집했습니다. 공통점은 위험한 곳에 먼저 가거나 반복 확인을 맡긴다는 것입니다. 그 결과 사람의 일은 어떻게 달라질까요?',
        src('국내 사례의 출처·도입 단계','../PPT-INTRO-SOURCES-20261001.md'),steps=2))
    items.append(make('현장의 필요','로봇은 점검을, 사람은 수리와 예방정비를',
        '<div class="economic-layout"><figure><img src="../assets/deck-ab-inbev-spot.jpg" alt="AB InBev 양조장의 Spot 점검 사례"><figcaption>AB InBev · 유럽 최대 규모 자사 양조장</figcaption></figure><div class="economic-story"><small>반복 점검에서 실제 대응으로</small><div class="economic-shift"><span>설비를 멈춰 누출 소리 확인</span><b>가동 중 점검 · 이상 위치 전달</b></div><div class="economic-metrics" data-step="1"><div><b>1,800<span>회 / 주</span></b><p>개별 점검 수행</p></div><div><b>약 150<span>건</span></b><p>첫 6개월 이상 징후 발견</p></div></div><div class="repair-change" data-step="2"><span>평균 수리 기간</span><strong><s>수개월</s> → 13일</strong><p>기술자는 확인된 문제의 수리에 집중</p></div></div></div>',
        'AB InBev에서는 Spot이 일주일에 1,800회의 개별 점검을 수행합니다. 가동 소음 속에서도 공기 누출을 찾아 기술자에게 전달합니다. 첫 6개월 동안 약 150건의 이상 징후를 발견했고, 평균 수리 기간은 수개월에서 13일로 줄었다고 보고합니다. 로봇이 점검을 맡아 사람이 실제 문제 해결에 집중하게 된 사례입니다. 그렇다면 이런 일을 꼭 사족보행이 해야 할까요?',src('Boston Dynamics · AB InBev 고객 사례',ab),steps=2,
        note='제조사가 공개한 고객 사례. 150건은 수리 완료가 아닌 이상 징후. 한 사람의 1,800건 업무 대체라고 단정하지 않는다. 수리기간 단축을 노동시간/원가 감소율로 바꾸지 않는다.'))
    items.append(make('이동 방식의 선택','같은 임무라도, 길에 따라 이동 방식이 달라집니다',
        '<div class="mobility-stage"><div class="mobility-item flight" data-step="1"><div class="mobility-disc"><img src="../assets/deck-elios3-inspection.jpg" alt="Flyability Elios 3 점검 드론"></div><h3>비행</h3><p class="strength">지면을 넘어, 높은 곳과 내부 공간으로</p><p>체공 시간 · 탑재 · 접촉 조건을 검토</p></div><div class="mobility-item legs">'+robot()+'<h3>사족보행</h3><p class="strength">발을 들어, 디딤을 선택하며</p><p>균형 · 접촉 · 관절을 함께 제어</p></div><div class="mobility-item wheels" data-step="1"><div class="mobility-disc"><img src="../assets/deck-unitree-b2w.png" alt="Unitree B2-W 바퀴와 다리를 결합한 로봇"></div><h3>바퀴 · 다리 결합</h3><p class="strength">이어진 노면에서는 굴러가고</p><p>단차에서는 다리도 활용 · 조건별 비교 필요</p></div></div><div class="mobility-bottom" data-step="1"><b>하나의 정답보다, 임무와 경로에 맞는 선택.</b><span>접근 위치 · 노면 연속성 · 탑재 장비 · 체류 시간</span></div>',
        '드론은 지면을 넘어 공중에서 접근할 수 있고 실내 점검에도 쓰입니다. 바퀴는 이어진 노면에서 강점이 있고, 바퀴와 다리를 결합하기도 합니다. 사람을 위한 공간을 활용하는 이족보행도 있습니다. 모두 목적에 맞는 답이 될 수 있습니다. 저희는 그중 지면의 디딤을 옮겨 가며 임무 지점에 도달하는 문제를 골랐습니다.',src('Flyability Elios 3','https://www.flyability.com/elios-3')+' · '+src('Unitree B2-W','https://www.unitree.com/b2-w'),steps=1))
    items.append(make('연구의 선택','발을 옮겨, 지지점을 바꾸는 이동에 주목했습니다',
        '<div class="foothold-choice">'+robot()+'<div class="choice-text"><small>LOCOMOTION → MISSION</small><h3>다음 발을 어디에 디딜 것인가.</h3><p>불연속적인 바닥에서도<br>디딤과 몸의 균형을 함께 조절합니다.</p><div class="support-sequence" data-step="1"><span>지형을 보고</span><span>발을 옮기고</span><span>몸을 지탱합니다</span></div><div class="choice-next" data-step="2">그런데, 네 발을 잘 움직이는 일은<br>왜 어려울까요?</div></div></div>',
        '사족보행은 발을 하나씩 옮겨 지지점을 바꿀 수 있습니다. 저희가 주목한 것은 이 능력입니다. 발을 옮기는 동안 몸의 균형을 유지하고, 도착한 곳에서 멈추거나 방향을 바꿔야 합니다. 그렇다면 이것을 로봇에게 시키려면 무엇을 함께 제어해야 할까요? 저희가 사용하는 Go2를 보겠습니다.',src('Unitree Go2','https://www.unitree.com/go2'),steps=2))
    items.append(make('로봇의 이해','오늘의 이야기를 함께할 Unitree Go2입니다',
        '<div class="go2-introduction">'+robot('large')+'<canvas class="go2-model" width="640" height="480" data-step="2" aria-label="실제 Go2 USD의 턴테이블과 부품 분리 애니메이션"></canvas><img class="go2-static-print" src="../assets/go2-blender/go2-joints-v3.png" alt="Go2 실제 모델의 관절 강조"><div class="go2-intro-label"><h3 class="spec-print-heading">열두 관절을<br>함께 제어합니다.</h3><small>UNITREE GO2</small><h3 class="spec-heading">보는 것에서,<br>움직이는 것까지.</h3><p class="spec-description" data-step="1">관측 · 명령 · 관절 제어</p><div data-step="1" class="intro-spec-number">4<span>개의 다리</span> × 3<span>개의 관절</span> = 12<span>자유도</span></div><p class="spec-origin" data-step="2">Isaac Lab에서 사용하는 실제 Go2 모델</p></div></div>',
        '오늘의 이야기를 함께할 Unitree Go2입니다. 네 다리마다 세 개의 관절이 있습니다. 총 열두 관절을 움직이면서 몸의 균형을 유지해야 합니다. 다음 클릭부터 실제 학습 환경에서 사용하는 모델을 보겠습니다. 정면, 회전, 부품 분리, 재조립, 열두 관절 순서로 멈춥니다. 부품을 벌려 보여주는 것은 조립 관계를 설명하기 위한 것입니다. 관측과 명령이 이 관절의 움직임으로 어떻게 연결되는지 이어 보겠습니다.',src('Unitree Go2 · 실제 USD와 Blender 검증','../GO2-BLENDER-PRODUCTION.md'),steps=6))
    return items

def revise(slides):
    # Preserve the research section after the robot introduction for staged revision.
    start=next(i for i,s in enumerate(slides) if s['title']=='이 로봇은 어떤 정보를 얻을 수 있을까요?')
    middle=slides[start:]
    for i,s in enumerate(middle):
        if s['title']=='현장으로 이어갈 다음 걸음':
            middle[i]=make('다음 걸음','FOOTHOLD가 추구하는 가치',
                '<figure class="film"><video controls playsinline preload="metadata" src="../../20260930-mvp-brand/_out/review/FULL_v6.mp4" poster="../assets/brand-full-v6-poster.jpg"></video><figcaption>FOOTHOLD 브랜드 런칭 A · 전체 v6</figcaption></figure>',
                '마지막으로 저희가 Isaac Sim에서 학습한 내용을 바탕으로, FOOTHOLD가 추구하는 가치를 담은 영상을 보시겠습니다.',kind='cinema',note='별도 브랜드 작업 폴더의 키비주얼 스토리보드 A가 현재 전체 v6로 연결한 FULL_v6.mp4를 사용한다. O/E 영화 말미의 11초 클로징과 다른 영상이다. 원본 파일과 사운드는 수정하지 않는다.')
        if s['title']=='Q&A':
            template=(ROOT/'design/cover-approved.template.html').read_text(encoding='utf8')
            logo_tag=re.search(r'<img\b(?=[^>]*alt="FOOTHOLD")[^>]*>',template).group()
            logo=re.search(r'src="([^"]+)"',logo_tag).group(1)
            middle[i]=make('다음 걸음','Find the next foothold.',
                '<div class="brand-end"><p class="brand-promise">내일의 발걸음이 기대되는 팀</p><img class="closing-logo" src="'+logo+'" alt="FOOTHOLD"><p class="closing-line">Find the next foothold.</p><p class="closing-korean">불확실한 지형에서도, 다음 걸음을 이어갑니다.</p><a class="closing-site" href="https://foothold-project.vercel.app" target="_blank">foothold-project.vercel.app</a><p class="closing-people">오흥재 · 맹라현 · 오현민 · 이민우 · 임석헌</p><p class="closing-qa" data-step="1">Q&A</p></div>',
                '발표 서두에 말씀드린 것처럼 저희가 원하는 목표는 뚜렷합니다. 어느 환경에서도 잘 걷는 로봇을 만드는 것입니다. 지금까지 내일의 발걸음이 기대되는 팀 FOOTHOLD의 오흥재였습니다. 감사합니다.',kind='intro brand-closing',steps=1)
    slides[:]=intro()+middle
