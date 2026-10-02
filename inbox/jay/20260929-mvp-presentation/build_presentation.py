"""Build the presentation in the user-approved cover URL. Sources remain editable."""
from pathlib import Path
import csv, json, re, html, shutil, os, importlib
from design.evidence_layouts import enrich
from design.intro_story import revise, COVER_NOTES
from design.scene_revision import refine, USER_COVER_NOTES
from design.research_revision import revise_research
from design.closing_revision import revise_closing
from design.media_u206 import revise_media
from design import spoken_steps, axes_scene, experiment_frame, failure_types, terrain_catalog, charts_u209, compare_tables, bridge_slide
COVER_NOTES=USER_COVER_NOTES

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=HERE/'output'
MEDIA=HERE.parent/'20260929-mvp-submission/source/media'
REPORT='https://foothold-project.vercel.app/research-20260928-v2-mvp-report'
SLIDES=[]
def esc(x): return html.escape(str(x),quote=True)
def pic(file, alt='', cls=''):
    return f'<img class="{cls}" src="../assets/{file}" alt="{esc(alt)}">'
def research_pic(file, alt=''):
    return f'<img src="../../20260929-mvp-submission/source/media/{file}" alt="{esc(alt)}">'
def clip(file, caption, poster=None, cinema=False):
    if cinema:
        src='../assets/'+file
        po='../assets/'+poster if poster else ''
    else:
        src='../../20260929-mvp-submission/source/media/'+file
        po='../../20260929-mvp-submission/source/media/'+(poster or file.replace('.mp4','.jpg'))
    return f'<figure class="film"><video controls playsinline preload="none" poster="{po}" src="{src}" {"" if cinema else "muted"}></video><figcaption>{caption}</figcaption></figure>'
def add(section,title,body,note,source='',kind='normal',steps=0):
    SLIDES.append(dict(section=section,title=title,body=body,note=note,source=source,kind=kind,steps=steps))
def lead(text,sub=''):return f'<p class="lead">{text}</p>'+ (f'<p class="explain">{sub}</p>' if sub else '')
def pair(a,b,ratio=''):
    # ★ .pair 는 1.12fr : 1fr 로 «일부러» 비대칭이다. 글+그림 쌍에는 맞다.
    #   그런데 «영상 둘을 견주는» 쌍에서는 같은 1280x720 원본이 748px 과
    #   668px 로 다르게 떠서 높이도 윗선도 어긋났다 (실측 27쪽).
    #   양쪽이 다 영상일 때만 같은 칸으로 둔다.
    both = a.count('class="film"') == 1 and b.count('class="film"') == 1
    cls = ('pair ' + ratio + (' pair-even' if both and not ratio else '')).strip()
    return f'<div class="{cls}"><div>{a}</div><div>{b}</div></div>'
def bars(labels,values, suffix='%',maximum=100):
    return '<div class="bars">'+''.join(f'<div class="barrow"><span>{esc(l)}</span><div class="bartrack"><i style="width:{v/maximum*100}%;background:{c}"></i></div><strong>{v:.1f}{suffix}</strong></div>' for l,v,c in zip(labels,values,['#61707d','#20333d','#0e7a6e']))+'</div>'
def flow(items):return '<div class="flow">'+''.join(f'<div><b>{a}</b><p>{b}</p></div>' for a,b in items)+'</div>'
def table(head,rows):return '<table><thead><tr>'+''.join('<th>'+str(h)+'</th>' for h in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table>'
def source(text,url=REPORT):return f'<a href="{url}" target="_blank" rel="noopener">{text}</a>'
def media_if(file, fallback):return file if (HERE/'assets'/file).exists() else fallback

def make_slides():
    add('현장의 필요','첫걸음',clip('film-opening-v7.mp4','', 'terrain-question-bright-v1.png',True),
        '인사를 마치고 영상을 재생합니다. 첫 디딤이 끝나면 “그럼 FOOTHOLD의 첫걸음을 함께 시작하겠습니다.”라고 말하고 넘깁니다. 이 영상은 연구의 필요성을 전달하는 콘셉트 영상이며 실기 실험 결과가 아닙니다.',kind='cinema')
    add('현장의 필요','이런 길이라면, 어떤 로봇을 보내시겠습니까?',pic('terrain-question-bright-v1.png','끊긴 바닥과 물, 좁은 지지면이 이어지는 산업 공간','full-photo')+'<div class="photo-question">이 길을 건너<br>점검 지점까지 가려면?</div>',
        '영상에서 어둠 속에 보였던 바닥을 다시 보여줍니다. 틈, 높이 차, 좁은 폭을 짚고 청중이 이동 방법을 떠올릴 시간을 줍니다. 특정 재난 현장 실사로 설명하지 않습니다.',kind='photo')
    add('현장의 필요','미경험은 로봇이 배운 조건과의 차이입니다',pair(research_pic('v2-terrain-catalog.png','평가 지형 16종'),lead('같은 한 걸음도<br>바닥이 달라지면 달라집니다.','높이 · 틈의 폭 · 경사 · 마찰 · 배치')+'<p class="callout">이번 MVP는 학습에 포함하지 않은 지형에서<br>보행 정책을 평가했습니다.</p>'),
        '현실에서는 재료와 마찰도 변합니다. 다만 이번 실험이 모든 현실 변수를 검증한 것은 아닙니다. 미경험은 위험해 보인다는 뜻이 아니라 학습 경험과의 관계입니다. 그렇다면 어떤 이동 방식을 연구할까요?',source('프로젝트 평가 지형 카탈로그'))
    add('현장의 필요','이동 방식은 임무에 따라 고릅니다', '<div class="mobility">'+''.join('<figure>'+pic(media_if(f,fb),l)+f'<figcaption><b>{l}</b><p>{t}</p></figcaption></figure>' for f,fb,l,t in [
        ('deck-elios3.jpg','go2-reference/component-map.jpg','비행','공중에서 접근하고 관찰하기'),('deck-unitree-b2w.png','go2-reference/side-walk.png','바퀴와 다리','주행과 발 디딤을 함께 활용하기'),('deck-deep-lite3.jpg','go2-reference/front-render.jpg','다리','지면을 짚고 지지점을 바꾸기')])+'</div><p class="callout">접근 위치와 경로, 탑재 장비, 체류 조건에 맞는 선택이 필요합니다.</p>',
        '드론도 실내와 지하에서 점검할 수 있습니다. 모두 목적에 맞는 답입니다. 우리는 지면을 따라 센서를 운반하고, 멈추고, 다시 이동하는 과정에서 생기는 보행 문제를 골랐습니다.',source('Flyability · Unitree · DEEP Robotics 공식 자료','../PPT-VISUAL-SOURCES.md'))
    add('현장의 필요','우리가 연구하는 것은 다음 디딤을 이어가는 보행입니다',pair(pic('go2-reference/side-walk.png','Go2 공식 보행 영상의 측면'),lead('발을 들어<br>지지점을 바꾸는 이동','불연속적인 바닥에서 균형과 이동을 함께 유지해야 합니다.')+'<p class="callout">잘 걷는 것에는 멈춤과 방향 전환도 포함됩니다.</p>'),
        '네 다리라고 항상 세 발이 지면에 붙는 것은 아닙니다. 동적인 보행까지 포함해 균형을 유지해야 합니다. 산양의 좁은 디딤이 인상적인 이유도 여기 있습니다. 동물의 구조를 그대로 모방했다는 주장은 하지 않습니다.',source('Unitree Go2 공식 보행 자료','https://www.unitree.com/go2'))
    if (HERE/'assets/deck-goat.jpg').exists():
        add('현장의 필요','좁은 디딤에서도 움직임은 이어집니다',pic('deck-goat.jpg','좁은 암벽 지지면을 이용하는 산양','full-photo')+'<div class="photo-question">딛을 곳을 바꾸며<br>다음 걸음을 이어갑니다.</div>', '산양 장면은 발 디딤의 의미를 직관적으로 보여주는 짧은 비유입니다. 90도 경사나 관절 토크 수치, 우리 로봇의 동일 능력으로 설명하지 않습니다.',source('사진 출처','../PPT-VISUAL-SOURCES.md'),kind='photo')
    add('현장의 필요','위험 현장에 먼저 들어갈 보행 로봇의 수요가 있습니다',lead('현장 지휘 지원과<br>대원 안전 확보'),'서울시 소방본부가 제시한 수요 과제입니다. 이미 현장 도입이 끝났다는 뜻은 아닙니다. 필요한 일을 확인한 뒤, 실제 운영 사례로 이어갑니다.',source('중소벤처기업부 제2026-309호 · 서울시 소방본부 수요 과제','https://www.mss.go.kr/site/smba/ex/bbs/View.do?bcIdx=1067938&cbIdx=310'),kind='statement')
    SLIDES[-1]['body'] += '<div class="statement-detail"><p>보행 로봇을 통한 위험 현장 대응</p><b>정부 공고에 제시된 수요 과제</b><p>적용 수요의 근거이며, 우리 시스템의 실증 성과는 아닙니다.</p></div>'
    add('현장의 필요','반복 점검을 맡기고, 사람은 수리에 집중합니다',pair(pic('deck-ab-inbev-bottling.jpg','AB InBev 설비 점검 사례'),'<p class="eyebrow">AB InBev · Spot 도입 사례</p>'+lead('평균 수리 기간<br><span class="muted">수개월</span> → <em>13일</em>')+'<div class="metrics"><div><strong>1,800</strong><span>주당 개별 점검</span></div><div><strong>약 150</strong><span>첫 6개월 발견한 이상</span></div></div><p>가동 소음 속에서도 공기 누출을 탐지하고,<br>기술자는 수리와 예방정비에 집중했습니다.</p>'),
        '소방 과제와 다른 산업 적용 사례입니다. 과거에는 누출 소리를 듣기 위해 라인을 멈춰야 했지만 이 사례에서는 가동 중 점검이 가능합니다. 150건은 이상 발견이며 수리 완료 건수가 아닙니다. 제조사 고객 사례이고 우리 실측이나 투자수익률은 아닙니다. 이런 임무를 가능하게 하는 이동 능력을 이제 살펴보겠습니다.',source('Boston Dynamics · AB InBev 고객 사례','https://bostondynamics.com/case-studies/energy-savings-predictive-maintenance-at-ab-inbevs-largest-european-brewery/'))
    add('연구 질문','오늘 말씀드릴 이야기', '<div class="agenda">'+''.join(f'<div><span>{i:02}</span><b>{a}</b><p>{b}</p></div>' for i,(a,b) in enumerate([('현장의 필요','왜 이 이동 능력을 연구하는가'),('연구 질문','무엇을 배우고 어떻게 평가하는가'),('실패에서 시작한 실험','관찰이 다음 선택으로 이어진 과정'),('MVP 성과','험지 통과와 명령 수행의 변화'),('남은 과제','아직 불안정한 지형과 행동'),('다음 걸음','보행 연구·공간 복원·실기 항법')],1))+'</div>',
        '현장의 필요를 보았습니다. 이제 로봇이 어떻게 배우는지, 무엇이 실패했는지, 그 실패를 통해 무엇을 바꾸었는지 말씀드리겠습니다. 그리고 해결한 것과 남은 것을 나누겠습니다.')
    add('연구 질문','험지를 잘 건너면서 기본 명령도 유지할 수 있을까?',pair(clip('lineage-gap-v2.mp4','험지 통과'),clip('axis2-stop-v2.mp4','정지 명령에 대한 응답')),
        '이번 연구 질문은 험지 통과 하나로 끝나지 않습니다. 임무 중에는 멈추고 방향을 바꿔야 합니다. 그래서 지형과 명령을 서로 다른 평가 축으로 봅니다.',source('FOOTHOLD 실제 시뮬레이션 평가 영상'))
    add('연구 질문','세 작업은 프로젝트 끝까지 함께 이어집니다',flow([('Track A · 보행 연구','학습 조건과 신경망을 실험하고<br>험지·명령 수행을 평가'),('Digital Twin · 실제 공간','촬영한 공간을 복원하고<br>충돌 지형과 축척 검증'),('Track B · 실기 항법','Go2 순정 보행 위에서<br>ROS2·SLAM·Nav2 주행 검증')])+'<p class="callout">이번 발표의 실측 중심은 Track A입니다.</p>',
        '기획 때의 순차 종료 그림을 바꾸었습니다. 보행 연구와 Digital Twin도 최종 발표까지 병행합니다. Track B는 우리가 학습한 정책을 증류해 올리는 일정이 아닙니다. 순정 보행을 이용해 항법 자체를 검증합니다.',source('프로젝트 방향 · Track A / Digital Twin / Track B','../SECTION-MAP.md'))
    add('학습과 평가','우리와 함께 걷는 로봇, Unitree Go2',pair(pic('go2-reference/front-render.jpg','Unitree Go2 공식 정면 이미지'),lead('네 다리 × 세 관절<br><em>12 자유도</em>','각 다리의 hip · thigh · calf 관절을 제어합니다.')+'<p class="callout">보행 정책은 관측을 받아<br>12개 관절의 위치 목표를 만듭니다.</p>'),
        '여기서부터 같은 기체를 따라갑니다. 외형을 소개한 뒤 센서와 관측, 신경망, 관절 움직임으로 이어집니다. 정책 출력은 곧바로 토크가 아니라 관절 위치 목표입니다.',source('Unitree Go2 · 프로젝트 관절 정의','https://www.unitree.com/go2'))
    add('학습과 평가','기체의 센서와 팀의 추가 모듈',pair(pic('go2-reference/component-map.jpg','Go2 센서와 관절 공식 구성 도해'),'<div class="reveal" data-step="0"><h3>기본 기체</h3><p>전면 카메라 · 기본 LiDAR L2<br>관절 상태와 몸체 자세</p></div><div class="reveal" data-step="1"><h3>팀의 추가 보유 모듈</h3><p>Orin NX 16GB<br>Depth Camera D435i<br>HESAI-360</p></div><div class="reveal" data-step="2"><p class="callout">장비 보유와 현재 정책 입력 연결은<br>구분해서 봐야 합니다.</p></div>'),
        '클릭마다 기본 센서, 추가 보유 모듈, 정책과의 차이를 설명합니다. 팀의 추가 모듈은 사용자 확인 구성입니다. 모두 장착·연동이 끝났다고 말하지 않습니다. 현재 보행 연구의 높이 스캔은 시뮬레이터에서 얻습니다.',source('팀 장비 구성 기록 · 공식 제품 도해','../GO2-HARDWARE-REFERENCE.md'),steps=2)
    add('학습과 평가','현재 정책은 235개의 값을 입력받습니다',pair(research_pic('v2-height-scan.png','현재 정책의 height scan 설명'),'<div class="input-total"><strong>235</strong><span>관측 입력</span></div>'+flow([('187','지형 높이 스캔'),('48','몸 상태 · 명령 · 이전 행동')])+'<p class="callout">실물 센서 원본 영상이 아닌,<br>정책이 쓰도록 구성한 수치입니다.</p>'),
        '187은 높이 스캔입니다. 나머지 48에는 몸 상태뿐 아니라 명령과 이전 행동도 있습니다. 48개 전체를 고유수용감각이라고 부르지 않습니다. 같은 정보가 어떻게 행동으로 바뀌는지 이어 보겠습니다.',source('현재 관측 구조 · 프로젝트 실험 보고서'))
    add('학습과 평가','관측이 들어오면 12개 관절 목표가 나옵니다','<div class="network"><div class="net-input reveal" data-step="0"><h3>관측 235</h3><p>몸 상태·명령·이전 행동 48<br>지형 높이 187</p></div><div class="net-stack reveal" data-step="1"><b>Actor · MLP</b><div class="layers"><span>512</span><span>256</span><span>128</span></div></div><div class="net-output reveal" data-step="2"><h3>출력 12</h3><p>관절 위치 목표<br>스케일·기준 자세 적용 후 제어</p></div></div><div class="network-return reveal" data-step="3">움직인 뒤의 몸 상태와 지형이 다음 관측이 됩니다.</div>',
        '첫 클릭에서 관측이 actor로 들어갑니다. 두 번째 클릭에서 출력이 나오고 관절 제어기로 전달됩니다. 마지막 클릭에서 움직임이 다음 관측으로 돌아옵니다. 그림은 층별 차원과 정보 흐름을 설명하는 도식입니다. 실제 모든 뉴런을 그렸다는 뜻은 아닙니다.',source('Actor MLP 512·256·128 · 현재 정책 설정'),steps=3)
    add('학습과 평가','학습에서는 critic이 행동의 결과를 평가하도록 돕습니다',flow([('환경에서 경험 수집','관측 · 행동 · 보상 · 다음 관측'),('Critic · MLP 512·256·128','상태의 가치를 추정해<br>행동 결과의 평가를 도움'),('PPO 업데이트','수집한 경험으로<br>actor와 critic을 갱신')])+'<p class="callout">Actor는 행동을 출력하고, critic은 학습을 돕습니다.</p>',
        'critic을 actor와 관절 사이에 놓지 않습니다. 실행할 때 행동을 만드는 경로와 학습할 때 갱신하는 경로가 다릅니다. 명령은 무엇을 할지, 보상은 어떤 행동을 좋게 볼지, 정책은 어떻게 행동할지를 정합니다.',source('PPO · Actor/Critic 구조 · 프로젝트 설정'))
    add('학습과 평가','4,096개 환경의 경험으로 하나의 정책을 업데이트합니다',clip('train-army.mp4','실제 학습 진행 시각화 · 화면에 렌더된 로봇 수와 전체 학습 환경 수는 다릅니다.')+'<p class="video-overlay-number">4,096 <span>학습 환경</span></p>',
        '한 환경에서 넘어지는 동안 다른 환경에서도 경험을 모읍니다. 모은 경험이 공통 정책 갱신에 쓰입니다. 이 영상은 이미 걷는 NVIDIA 가중치에서 추가 학습되는 모습을 보여줍니다. 4096배 비용 절감이나 처음부터 걸음마를 배운 영상으로 말하지 않습니다.',source('학습 설정 num_envs=4096 · train-army 실제 렌더'),kind='bigvideo')
    add('실패에서 시작한 실험','먼저, 우리가 서 있는 곳을 확인했습니다',lead('무엇을 더 가르칠지 정하려면<br>어디서 실패하는지 알아야 합니다.')+flow([('평지 기준선','기본 보행과 평가 장치 점검'),('미경험 10종','낯선 지형에서 현재 정책 시험'),('실패 양상','넘어짐과 전진하지 못함을 구분')]),
        '기획 발표의 출발점이었습니다. 성공 장면을 고르기 전에 기준선이 어디까지 하는지 먼저 보았습니다. 그래야 다음 학습 과제를 정할 수 있기 때문입니다.',source('기획 발표의 실패 중심 접근','../../../../deliverables/plan/proposal-deck-presented.html'))
    add('실패에서 시작한 실험','실패 지형을 나누고, 먼저 시도할 과제를 골랐습니다',pair(research_pic('v2-terrain-catalog.png','평가 지형 카탈로그'),lead('10종에서 만난 문제<br>다섯 과제로 나눠 탐색')+'<p>낙상, 발 디딤 실패, 전진 불능을 구분하고<br>지형마다 필요한 변경을 찾았습니다.</p><p class="callout">첫 선택은 <b>gap</b>이었습니다.</p>'),
        '10종과 다섯 과제는 기획 시점의 진단입니다. 뒤에서 보일 현재의 공통 미경험 8종 평균과 다른 집합입니다. 왜 gap부터였는지 다음 장에서 관측과 학습 경험 두 가지로 설명하겠습니다.',source('기획 발표 · 이후 gap 실험 설계'))
    add('실패에서 시작한 실험','틈을 만나게 하고, 바닥이 없다는 입력도 바로잡았습니다',pair(clip('train-gap-forward.mp4','forward_gap · 학습 지형'),'<div class="reveal" data-step="0">'+lead('새로운 지형 경험')+'<p>기본 학습 지형에 없던 틈을 추가합니다.</p></div><div class="reveal" data-step="1">'+lead('미검출 광선의 처리')+'<p>바닥에 닿지 않은 스캔을<br>낮은 지면 방향의 값으로 구분합니다.</p></div>'),
        '모든 틈이 광선 미검출인 것은 아닙니다. 바닥이 없는 경우 ray miss를 따로 처리했습니다. 경험 추가만의 문제도, 입력 코드만의 문제도 아니었습니다. 두 변경을 함께 수행했습니다.',source('sim/policy/gap_env_cfg.py · gap_observations.py','../../../../sim/policy/gap_observations.py'),steps=1)
    add('실패에서 시작한 실험','바닥에 닿지 않은 광선은 낮은 지면으로 구분합니다','<div class="ray-diagram"><div class="ray-side"><h3>광선이 표면에 닿는 경우</h3><div class="ray-line"></div><div class="ground"></div><p>센서 높이 − 충돌점 높이 − offset</p></div><div class="ray-side missing"><h3>바닥이 없어 닿지 않는 경우</h3><div class="ray-line"></div><div class="ground"></div><p>유한값 검사 → miss_value = +1</p></div></div>'+table(['대조한 기본 처리','FOOTHOLD 보완'],[['hit z = inf → 높이 −inf → clip −1','비유한값을 검사하고 +1로 치환']]),
        '대조한 로컬 Isaac Lab 기본 함수에는 ray miss를 별도로 처리하는 분기가 없었습니다. clip까지 거치면 의도와 다른 부호가 됩니다. 별도 함수에서 isfinite로 검사하고 깊은 낙차 방향인 +1로 보완했습니다. NVIDIA의 모든 버전에 동일하다고 일반화하지 않습니다.',source('코드 대조 HEAD 37ddf62 · gap_observations.py','../REVISION-story-direction.md'))
    add('실패에서 시작한 실험','첫 학습은 틈 10%와 전진 명령 제한으로 시작했습니다',pair(clip('train-gap-forward.mp4','정면으로 배치한 틈을 반복 경험'),'<div class="metrics"><div><strong>10<span>%</span></strong><span>forward_gap 학습 비중</span></div></div>'+table(['명령','첫 실험 설정'],[['전진 속도','0.5~1.5 m/s'],['횡이동','0 m/s'],['회전','0 rad/s']])+'<p class="callout">먼저 틈을 향해 걸어가도록<br>학습 경험을 집중했습니다.</p>'),
        '틈 지형을 전체의 10퍼센트로 넣고 전진 방향에 학습을 집중했습니다. 나머지 지형을 없앤 것이 아닙니다. 이 선택은 gap을 만나는 경험을 늘리는 대신 명령의 다양성을 제한했습니다.',source('gap_env_cfg.py · 학습 지형 비율과 명령 범위','../../../../sim/policy/gap_env_cfg.py'))
    add('실패에서 시작한 실험','전진 보행은 개선됐습니다. 멈춤은 별도로 확인해야 했습니다',pair(clip('lineage-gap-v1.mp4','v1 · gap 통과 예시'),clip('axis2-stop-v1.mp4','v1 · 정지 명령 전환 예시')),
        'gap을 건너는 행동을 얻었습니다. 하지만 전진 영상만 보면 보이지 않는 문제가 있습니다. 정지하라는 명령을 주었을 때도 안정적으로 멈추는가입니다. 그래서 기본 명령 평가를 열었습니다.',source('v1 지형 평가와 64환경 정지 프로브'))
    add('실패에서 시작한 실험','명령을 넓힌 후보에서는 gap 성능이 낮아졌습니다',pair(clip('lineage-gap-v1.mp4','v1 · 전진 중심'),clip('lineage-gap-D-fail.mp4','명령 설정 변경 후보 D · 실패 예시'))+'<p class="callout">다른 능력을 얻는 동안, 이미 배운 능력도 다시 확인해야 했습니다.</p>',
        '명령을 넓힌 후보에서 gap 성능 저하를 관찰했습니다. 이 비교에는 여러 설정 변경이 있으므로 명령 하나만이 원인이라고 단정하지 않습니다. 중요한 것은 실제로 틈을 마주하는 학습 경험이 충분한가라는 다음 질문입니다.',source('실험 계보 · 후보 D 비교. 영상은 한 에피소드 예시'))
    add('실패에서 시작한 실험','어느 방향으로 가도 틈을 만나도록 지형을 바꿨습니다',pair(clip('train-gap-forward.mp4','forward_gap · 정면에 있는 틈'),clip('train-gap-omni.mp4','omni_gap · 주변을 둘러싼 틈'))+'<p class="callout">명령의 다양성과 실제 지형 경험을 함께 설계합니다.</p>',
        '정면에만 틈이 있으면 방향이 바뀔 때 틈을 피해 가는 경험이 많아질 수 있습니다. 그래서 주변을 둘러싼 형태로 바꾸었습니다. 같은 시점의 두 영상을 재생하며 경험 분포가 어떻게 달라지는지 보여줍니다.',source('forward_gap / omni_gap 실제 학습 지형 렌더'))
    add('실패에서 시작한 실험','방향·정지·디딤 경험을 함께 조정했습니다',table(['관찰한 문제','설계에 반영한 것','해석 범위'],[['방향 전환 때 틈 경험이 달라짐','omni_gap과 heading 명령','어느 방향에서도 과제를 경험'],['전진만으로는 정지 응답을 확인하기 어려움','정지 명령 표집 비율 0.1','전체 시간의 10%라는 뜻은 아님'],['솟은 턱을 넘는 디딤 부족','rails 지형 추가','추가한 지형을 unseen에 포함하지 않음']])+'<p class="callout">각 변경을 평가하고, 채택한 조건을 다시 함께 확인했습니다.</p>',
        'heading, 정지 표본, rails를 같은 질문에 대응시키되 각각의 효과가 완전히 분리됐다고 말하지 않습니다. 전진 명령은 0.4에서 1.5, 횡이동은 여전히 0인 제한도 있습니다. 실제 각속도와 reset 각도는 부록 설정을 따릅니다.',source('v2 학습 설정·계보 기록'))
    add('실패에서 시작한 실험','보상 가중치도 비교했습니다',lead('feet_air_time<br><em>0.01 · 0.1 · 1.0</em>')+'<div class="statement-detail"><p>발이 공중에 머무르는 시간에 관한 보상항</p><p>발 높이, 안전한 착지점, 실제 접촉력을 직접 보상하는 항은 아닙니다.</p><b>0.1 설정의 v2g2 · iter3000을 채택해 평가</b></div>',
        '새로운 보상 함수를 발명한 성과로 말하지 않습니다. 기존 체공시간 항의 가중치를 비교했습니다. 전체 16종 48칸의 탐색 평균과 뒤에서 제시할 공통 미경험8종 평균은 서로 다른 집계입니다. 단일 학습 실행의 차이를 반복시드 인과결론으로 확대하지 않습니다.',source('MVP 보고서 · 보상 가중치 비교'),kind='statement')
    add('실패에서 시작한 실험','후보 탐색은 병렬로, 채택은 전체 평가로 바꿨습니다', '<div class="method-change"><div><p class="eyebrow">기획</p><h3>FIVE RECIPE, ONE SOLUTION</h3><p>지형별 해결 방법을 병렬로 탐색하고<br>설정을 모아 혼합 학습</p></div><div><p class="eyebrow">변경</p><h3>후보 탐색 → 버전별 채택·재평가</h3><p>새 성능뿐 아니라<br>기존 능력의 퇴행도 함께 확인</p></div></div><p class="callout">한 과제의 개선이 다른 과제에도 그대로 이어지지는 않았습니다.</p>',
        '다섯 레시피의 방향을 버리고 하나만 순차로 탐색한 것이 아닙니다. 후보는 함께 탐색하되, 합치면 좋아질 것이라는 가정을 내려놓고 채택할 때마다 전체를 평가했습니다. 신경망 다섯 개 가중치를 단순 평균했다는 뜻도 아닙니다.',source('연구 방식 변경 · 이슈 #399','https://github.com/foothold-project/foothold-lab/issues/399'))
    add('MVP 성과','지형 통과와 명령 수행을 두 축으로 평가했습니다',flow([('축 1 · 지형 통과','생존 · 전진 · 속도 추종 · 방향 유지<br>네 조건을 모두 만족'),('축 2 · 명령 수행','정지 · 유지 · 회전 프로브<br>명령 전환 뒤 실제 반응 확인')])+'<p class="callout">성공률 0%가 곧 낙상률 100%는 아닙니다.</p>',
        '네 조건 중 속도 추종만 실패해도 성공으로 집계되지 않습니다. 따라서 성공률과 실제 영상을 함께 봅니다. 회전·정지의 별도 평가를 지형 통과율에 합쳐 하나의 만능 점수로 만들지 않습니다.',source('평가 프로토콜 · 성공 정의'))
    add('MVP 성과','같은 평가 조건에서 세 모델을 비교했습니다',table(['항목','비교 조건'],[['모델','NVIDIA · foothold-v1 · foothold-v2'],['지형','공통 미경험 8종 · gap과 rails 제외'],['난이도','0.5'],['목표 속도','0.5 · 1.0 · 1.5 m/s'],['표본','지형·속도마다 100 에피소드 · 평가 시드 42']])+'<p class="callout">개발 중 반복 평가한 지형 집합입니다. 독립 최종 시험과 구분합니다.</p>',
        '같은 평가 조건이지 같은 학습량이라는 뜻은 아닙니다. v1과 v2의 학습 설정과 예산은 다릅니다. 모델을 고르는 동안 반복해 보았으므로 독립된 최종 홀드아웃 평가라고 말하지 않습니다.',source('sweep_long.csv · 모델별 generalization_raw.csv'))
    add('MVP 성과','1.0 m/s에서 공통 미경험 8종의 성공률이 높아졌습니다',bars(['NVIDIA','foothold-v1','foothold-v2'],[62,87.375,90.5])+'<p class="callout">NVIDIA → v2 <b>+28.5%p</b> · v1 → v2 <b>+3.1%p</b></p>',
        '먼저 기준선의 학습 속도 범위 안인1.0에서 보겠습니다. 큰 향상은 v1에서 나타났고 v2에서 추가 향상이 있었습니다. 우리 연구의 흐름은 NVIDIA에서 현재 모델까지 이어지지만, 각각 어느 단계의 향상인지 구분해 설명합니다.',source('d0.5 · 8종 × 100판 · 평가 시드42 · 원자료 재집계'))
    add('MVP 성과','목표 속도를 바꾸면 기준선의 차이가 더 크게 드러납니다','__SPEED_CHART__<p class="callout">세 속도 평균: NVIDIA <b>43.9%</b> · v1 <b>86.7%</b> · v2 <b>88.5%</b></p>',
        '1.5m/s는 NVIDIA 기본 학습 명령 범위 밖입니다. 따라서 평균만 크게 제시하지 않고 속도별 결과를 함께 보여줍니다. 평균값은 각 지형·속도 칸의 산술평균입니다.',source('d0.5 · 공통 미경험8종 · 속도마다800판 · NVIDIA1.5m/s 학습범위 밖'))
    add('MVP 성과','숫자와 함께, 같은 조건의 움직임을 봅니다','<div class="triple">'+''.join(clip(f'hero-floatingring-v15-{m}.mp4',l) for m,l in [('nvidia','NVIDIA · 0%'),('v1','v1 · 87%'),('v2','v2 · 99%')])+'</div><p class="callout">floating_ring · 1.5 m/s · d0.5 · 각 성공률은 100판 집계, 영상은 한 판의 예시</p>',
        '세 영상은 동시에 재생할 수 있습니다. NVIDIA가 반드시 넘어지는 영상이라고 설명하지 않습니다. 살아 있지만 요구한 속도나 전진 조건을 만족하지 못할 수도 있습니다. 이 장의1.5는 앞 장의1.0평균과 다릅니다.',source('FOOTHOLD floating_ring 비교 영상 · NVIDIA1.5m/s 학습범위 밖'))
    add('MVP 성과','정지 명령 전환 때의 낙상이 줄었습니다',pair(clip('axis2-stop-v1.mp4','v1 · 낙상 13/64'),clip('axis2-stop-v2.mp4','v2 · 낙상 0/64'))+'<p class="callout">같은 프로브의 NVIDIA도 0/64 · 무낙상이 완전한 정지를 뜻하지는 않습니다.</p>',
        '4초 전진 뒤 정지 명령을 줬습니다.64환경 시드42에서 v1은13번, v2는0번 넘어졌습니다. 이 수치는 정지 성공률이 아니라 정지 과정의 낙상입니다. 남은 속도와 자세 응답도 따로 확인해야 합니다.',source('64환경 · seed42 · 4초 전진 후 정지 · per_env.json 재집계'))
    add('남은 과제','회전과 넓은 명령 조건은 아직 검증이 더 필요합니다',pair(clip('axis2-turn-v2.mp4','v2 · 회전 프로브'),lead('험지 통과의 개선이<br>모든 행동의 완성을 뜻하지는 않습니다.')+'<p>회전 · 후퇴 · 횡이동 · 저속<br>험지와 명령이 결합된 조건</p><p class="callout">측정 조건별로 낙상과 추종 실패를 구분합니다.</p>'),
        '계속되는 연구의 질문입니다. 전진만 좋아졌다고 실제 임무 전체가 해결된 것은 아닙니다. 일부 프로브의 판정표만으로 범용 보행이 완성됐다고 말하지 않습니다.',source('축2 명령 평가 · 현재 제한'))
    add('남은 과제','디딤돌에서는 평가 시드에 따라 성공률이 흔들렸습니다',pair(clip('stepping-stones-v2.mp4','stepping_stones · 실패 예시'),'<div class="seedplot">'+''.join(f'<div><span>시드 {s}</span><i style="height:{v*7+4}px"></i><b>{v}%</b></div>' for s,v in zip([42,1,2,3,4],[24,1,3,19,0]))+'</div><p class="callout">1.0 m/s에서 다섯 시드 <b>0~24%</b><br>한 시드의 좋은 결과만으로 안정성을 말할 수 없습니다.</p>'),
        '평가 시드에 따른 변동입니다. 다섯 번 독립적으로 새 정책을 학습한 결과로 말하지 않습니다. 디딤돌의 좁은 지지면에서 어떤 경험과 관측이 필요한지 다음 실험을 설계해야 합니다.',source('stepping_stones · d0.5 · 1.0m/s · 평가 시드별100판'))
    add('다음 걸음','실제 공간을 가져오는 작업도 함께 진행했습니다',pair('<img src="../../20260916-3dgs-test/figs/fig2_grid_25d.png" alt="실제 지면 후보로 생성한 2.5D 메시">',lead('촬영 → 공간 복원<br>→ 충돌 지형 → 보행 시험')+'<p>스마트폰 영상에서 복원한 공간을<br>Isaac Sim의 배경·충돌체로 연결했습니다.</p><p class="callout">축척과 실제 지면 대비 정확도,<br>충돌·관측의 정합성 검증은 남아 있습니다.</p>'),
        '복원이 예쁘게 보이는 것과 물리적으로 올바른 보행 지형인 것은 다릅니다. 기존 PoC에서 파일 생성과 정책 로드·추론·이동은 확인했지만 낙상도 있었고 정책 성능 비교 조건은 아니었습니다. 이것도 프로젝트 끝까지 이어갑니다.',source('9월16일 Real-to-Sim PoC 결과','../../20260916-3dgs-test/RESULTS-3dgs-terrain.md'))
    add('다음 걸음','실기에서는 순정 보행 위에 항법을 검증합니다',pair(pic('go2-reference/module-hesai.png','Go2 추가 센서 구성'),flow([('인지·지도','LiDAR · 카메라 · SLAM'),('경로·주행 명령','Nav2 · 목표점 · 복귀'),('실제 보행','Go2 순정 보행 제어')])+'<p class="callout">저수준 정책 이식의 불확실성을 분리하고<br>실기 목표 주행에 집중합니다.</p>'),
        '연구 정책을 교사학생 증류로 실기에 이식한 성과가 아닙니다. 보행 연구와 항법의 실패 원인을 한 번에 섞지 않도록 순정 보행을 사용하기로 했습니다. 이 장은 항법 구조와 검증 계획이며 현재 실기 임무 완료를 보고하는 장이 아닙니다.',source('Track B 합의 · Go2 추가 모듈','../GO2-HARDWARE-REFERENCE.md'))
    add('다음 걸음','다음 학습은 지형과 명령을 함께 만나는 과제로 설계합니다',flow([('목표와 경유점','험지를 지나야 도달하는 경로'),('명령 전환','걷기 · 감속 · 정지 · 회전'),('재평가','새 과제 성능과 기존 능력 유지')])+'<p class="callout">어떤 혼합이 효과적인지는 앞으로 비교할 실험 질문입니다.</p>',
        '직선 거리 보상만 주면 지름길로 과제를 피할 수도 있습니다. 실제로 험지를 만나게 하는 경유점과 명령 전환을 함께 설계합니다. 아직 수행하지 않은 제안임을 명확히 합니다.',source('다음 학습 과제 설계','../SECTION-MAP.md'))
    add('다음 걸음','관측과 신경망의 효과도 분리해서 비교하겠습니다',table(['현재','다음 비교','판단 기준'],[['높이 스캔과 현재 상태','시간 이력 · 지형 표현','같은 과제와 학습 예산'],['Actor/Critic MLP','후보 구조의 대조 실험','여러 학습·평가 시드'],['개발 중 반복 평가','모델 선택·최종 시험 분리','지형과 명령의 결합 조건']])+'<p class="callout">새 구조가 해결책이라는 결론을 먼저 정하지 않습니다.</p>',
        '현재 기여는 학습 조건과 관측 처리의 보완, 추가 학습, 두 축의 평가입니다. 새로운 신경망 구조의 효과는 다음 검증 질문입니다. 기존 논문은 각자 과제가 다르므로 좋은 GIF만 보고 같은 결과를 기대하지 않습니다.',source('후속 연구 계획 · 비교 조건','../SECTION-MAP.md'))
    add('다음 걸음','MVP 이후에도 세 흐름을 병행합니다','<div class="timeline"><div class="timeline-head"><span>MVP · 현재</span><span>실기 항법 검증</span><span>최종 발표</span></div>'+''.join(f'<div class="lane"><b>{a}</b><div><span>{b}</span><span>{c}</span></div></div>' for a,b,c in [('Track A','지형·명령·관측 비교','다중 시드·기존 능력 재평가'),('Digital Twin','공간 복원과 축척 검증','물리 지형·보행 평가 연결'),('Track B','센서·지도·경로 통합','목표 주행·정지·복귀 검증')])+'</div>',
        'MVP에서 A가 종료되고 B가 시작되는 직렬 일정이 아닙니다. 정책 연구와 공간 복원도 최종 발표까지 계속됩니다. 각 흐름의 실제 완료 여부는 해당 실험 증거로 판단합니다.',source('사용자 확정 프로젝트 방향 · 병행 WBS','../SECTION-MAP.md'))
    add('다음 걸음','실패를 확인했고, 다음 실험의 출발점을 만들었습니다', '<div class="closing-findings"><div><h3>확인한 것</h3><p>미경험 8종의 통과 개선<br>정지 전환에서 낙상 감소<br>지형과 명령을 함께 평가하는 체계</p></div><div><h3>이어갈 것</h3><p>좁은 디딤과 회전의 안정성<br>관측·신경망 비교<br>실제 공간과 실기 항법 검증</p></div></div><p class="closing-slogan">Find the next foothold.</p>',
        '끝으로 우리가 향하는 현장으로 돌아갑니다. 다음 영상은 지금 실기에서 완수했다는 증거가 아니라 보행 연구가 향하는 임무를 보여주는 콘셉트입니다. 그 구분을 말로 한 번 짚고 클로징을 재생합니다.',source('현재 성과와 다음 과제의 구분'))
    ending=next((f for f in ['film-ending-v8.mp4','film-ending-v7.mp4','film-ending-v3.mp4','film-ending-v2.mp4','film-ending-brand-v2.mp4','film-ending-v1.mp4'] if (HERE/'assets'/f).exists()),'film-ending-v1.mp4')
    add('다음 걸음','현장으로 이어갈 다음 걸음',clip(ending,'','ending-e2-sunburst-v1.png',True),
        '임무 수행과 브랜드 클로징이 끝나면 다음 슬라이드로 넘깁니다. 소리 재생은 발표자가 시작합니다. 현재 파일의 영화 음악은 임시 믹스이며 최종 사운드 교체 대상입니다.',kind='cinema')
    add('Q&A','Q&A','<div class="qa">Q&A</div>','질문을 받습니다. 연구 결과의 조건은 보고서와 부록에서 확인할 수 있습니다.',kind='qa-slide')
    add('부록','관측 48개와 지형 높이 187개의 구성',table(['입력','차원'],[['선속도 · 각속도 · 투영 중력','3 + 3 + 3'],['속도 명령','3'],['관절 위치 · 관절 속도','12 + 12'],['이전 행동','12'],['높이 스캔','187'],['합계','235']]),'실제 정책 관측 설정과 대조한 구조입니다. 발바닥 압력 센서나 카메라 원본을 이 표에 임의로 추가하지 않습니다.',source('관측 설정 · 보고서의 입력 차원'))
    add('부록','주요 근거와 실제 자료',table(['자료','확인 위치'],[['MVP 실측 보고서',source('연구 과정·결과·한계')],['실험 원자료','sim/eval/results/20260928-v2-sweep/sweep_long.csv'],['실제 영상','FOOTHOLD 갤러리 · 제출 보고서 수록 영상'],['추가 실험 계보',source('설정과 가중치 출발점','https://foothold-project.vercel.app/research-20260928-rl-lineage.html')],['발표 요구·자산 출처','USER-REQUIREMENTS-LOG.md · PPT-VISUAL-SOURCES.md']]),'모델 버전의 설명 순서가 가중치가 모두 차례로 전달됐다는 뜻은 아닙니다. 구현과 실험 조건은 계보 및 원자료를 기준으로 답합니다.',source('FOOTHOLD 프로젝트','https://foothold-project.vercel.app'))

def apply_user_story_order():
    """The user's spoken narrative overrides the earlier topic-based section map."""
    by_title={s['title']:s for s in SLIDES}
    def take(title):
        return by_title.pop(title)
    question=take('험지를 잘 건너면서 기본 명령도 유지할 수 있을까?')
    tracks=take('세 작업은 프로젝트 끝까지 함께 이어집니다')
    # Do not interrupt the agenda -> Go2 -> observation -> action -> training sequence.
    SLIDES[:]=[s for s in SLIDES if s is not question and s is not tracks]
    # The question belongs in the v1 failure beat. Do not preview v2's solution here.
    stop=next(s for s in SLIDES if s['title']=='전진 보행은 개선됐습니다. 멈춤은 별도로 확인해야 했습니다')
    stop['note']='틈을 건너는 행동을 얻었습니다. 그런데 멈추라는 명령에서도 안정적일까요? 두 번째 영상이 그 문제를 보여줍니다. 그래서 전진에 묶어 둔 명령 설정을 넓혔습니다. 다음 화면에서 그때 gap에 어떤 변화가 생겼는지 보겠습니다.'
    tracks['section']='다음 걸음'
    tracks['note']='여기까지가 보행 정책에서 확인한 성과와 남은 문제입니다. 처음 보았던 현장까지 가려면 실제 공간을 가져오는 일과 실기에서 길을 찾는 일도 필요합니다. 그래서 보행 연구, Digital Twin, 실기 항법을 끝까지 병행합니다. 먼저 실제 공간을 가져온 과정을 보겠습니다.'
    idx=next(i for i,s in enumerate(SLIDES) if s['title']=='실제 공간을 가져오는 작업도 함께 진행했습니다')
    SLIDES.insert(idx,tracks)
    # Close the observation -> network -> joint motion loop before explaining learning.
    idx=next(i for i,s in enumerate(SLIDES) if s['title']=='학습에서는 critic이 행동의 결과를 평가하도록 돕습니다')
    SLIDES.insert(idx,dict(section='학습과 평가',title='신경망의 출력은 다시 이 로봇의 한 걸음이 됩니다',
        body=pair(clip('lineage-gap-v2.mp4','현재 정책으로 움직이는 Go2 · 실제 평가 영상'),
            lead('관측 → 행동 → 다음 관측')+'<p>12개 출력을 스케일·기준 자세와 결합해<br>관절 위치 목표로 전달합니다.</p><p class="callout">발을 옮기면 몸 상태와 지형 관측도 달라집니다.</p>'),
        note='방금 신경망에서 나온 값이 이 로봇의 관절 목표가 됩니다. 움직인 결과를 다시 관측하고 다음 행동을 정합니다. 지금 영상은 이 정책으로 움직이는 실제 시뮬레이션입니다. 그렇다면 이 행동을 어떻게 더 잘하게 만들까요? 다음에는 행동의 결과로 학습하는 과정을 보겠습니다. 관절별 출력 값과 이 영상이 동기화된 시각화는 아직 아닙니다.',source=source('정책 실행 · 실제 gap 평가 영상'),kind='normal',steps=0))
    changes={
      '이런 길이라면, 어떤 로봇을 보내시겠습니까?':(
        '우리가 건너려는 길은 이런 모습입니다',
        '영상에서 빛으로 잠깐 보였던 지형을 밝은 화면으로 다시 봅니다. 틈과 높이 차, 좁아지는 디딤을 짚습니다. 이런 길에서 우리가 말하는 미경험은 무엇일까요?'),
      '미경험은 로봇이 배운 조건과의 차이입니다':(
        '미경험 험지란 무엇일까요?',
        '한 번도 경험하지 않은 조건입니다. 현실의 바닥은 높이, 마찰, 경사, 틈과 폭이 달라집니다. 이번 MVP에서 확인한 범위는 학습에 넣지 않은 지형입니다. 그럼 이런 길을 지나 임무 지점에 가려면 어떤 로봇이 적합할까요?'),
      '이동 방식은 임무에 따라 고릅니다':(
        '이 길을 건너려면 어떤 이동 방식이 적합할까요?',
        '드론, 바퀴와 다리를 함께 쓰는 로봇, 사족보행 로봇이 있습니다. 모두 목적에 따라 답이 될 수 있습니다. 드론도 지하 점검에 쓰입니다. 우리는 그중 지면을 따라 장비를 운반하고 멈추며, 끊긴 바닥에서 디딤을 바꾸는 보행 문제에 집중했습니다.'),
      '우리가 연구하는 것은 다음 디딤을 이어가는 보행입니다':(
        '우리는 발을 옮겨 지지점을 바꾸는 이동에 주목했습니다',
        '바퀴가 못 가고 드론도 못 가기 때문이라는 설명은 아닙니다. 우리가 연구할 문제는 불연속적인 지면에서 디딤을 이어가는 능력입니다. 네 다리의 지지와 균형을 이용하는 이 이동이 실제 현장에서도 필요할까요?'),
      '위험 현장에 먼저 들어갈 보행 로봇의 수요가 있습니다':(
        '위험 현장에 먼저 들어갈 로봇을 필요로 합니다',
        '서울시 소방본부가 제시한 수요 과제입니다. 대원 안전과 현장 지휘 지원을 위해 보행 로봇을 필요로 한다는 근거입니다. 도입 완료 사례는 아닙니다. 그렇다면 이미 운영 중인 산업 현장에서는 어떤 변화가 있었을까요?'),
      '반복 점검을 맡기고, 사람은 수리에 집중합니다':(
        '반복 점검을 맡기고, 사람은 수리에 집중합니다',
        'AB InBev 사례에서는 주당1800건의 개별 점검과 첫6개월 약150건의 이상 발견을 보고합니다. 평균 수리 기간은 수개월에서13일로 줄었습니다.150건은 수리 완료 건수가 아닙니다. 제조사 공개 사례의 수치입니다. 이렇게 임무 지점에 도달하는 이동 능력의 가치가 있습니다. 그래서 저희는 낯선 지형에서 보행을 이어가는 문제에 주목했습니다.'),
      '오늘 말씀드릴 이야기':(
        '현장의 필요에서, 우리의 첫걸음으로',
        '현장에서 왜 필요한지 보았습니다. 이제 우리가 어떤 문제를 풀려고 했는지, 무엇을 바꿨고 어떤 결과를 얻었는지, 앞으로 무엇이 남았는지 말씀드리겠습니다. 먼저 이 이야기를 함께할 로봇을 소개합니다.'),
      '우리와 함께 걷는 로봇, Unitree Go2':(
        '오늘의 이야기를 함께할 Unitree Go2입니다',
        'Go2입니다. 네 다리에 세 관절씩,12자유도를 갖습니다. 이 로봇이 바닥을 보고 몸을 움직이려면 어떤 정보가 필요할까요? 같은 기체에서 센서와 몸 상태로 시선을 옮깁니다. 턴테이블과 분해 연출은 아직 제작되지 않았습니다.'),
      '기체의 센서와 팀의 추가 모듈':(
        '이 로봇은 어떤 정보를 얻을 수 있을까요?',
        '기체의 센서와 저희가 추가로 보유한 모듈입니다. 추가 보유와 연결 완료는 구분합니다. 이제 같은 로봇을 시뮬레이션으로 옮겨 보겠습니다. 여기서는 센서 사진 자체가 아니라 정책에 들어가는 몸 상태와 지형 높이 값에 집중합니다.'),
      '현재 정책은 235개의 값을 입력받습니다':(
        '시뮬레이션 속 Go2가 받는 정보입니다',
        '몸 상태와 명령, 이전 행동48개에 지형 높이187개가 들어갑니다. 이 높이 값은 현재 시뮬레이터에서 계산합니다. 실물 카메라나LiDAR가 그대로 연결돼 들어온다고 말하지 않습니다. 이235개 값이 다음 행동을 만드는 입력입니다. 그 값이 어디로 가는지 따라가 보겠습니다.'),
      '4,096개 환경의 경험으로 하나의 정책을 업데이트합니다':(
        '한 대의 경험을, 4,096개 환경에서 함께 모읍니다',
        '방금 본 한 번의 행동과 학습을4096개 환경에서 병렬로 경험합니다. 화면에 렌더된 대수와 전체 학습 환경 수는 다릅니다. 출발점은 이미 걷는NVIDIA정책입니다. 그럼 이 정책에 무엇을 더 가르쳐야 할까요? 저희는 먼저 어디에서 실패하는지를 보았습니다.'),
      '먼저, 우리가 서 있는 곳을 확인했습니다':(
        '무엇을 더 가르칠지, 실패에서 찾았습니다',
        '기획 발표에서부터 실패를 먼저 본 이유입니다. 현재 정책의 수준을 알아야 다음 학습을 정할 수 있습니다. 미경험10종을 시험하고, 문제를 보인 지형들을 나눠 해결 방법을 찾았습니다. 다음 화면이 그 다섯 과제입니다.'),
    }
    for s in SLIDES:
        if s['title'] in changes:s['title'],s['note']=changes[s['title']]
    terrain=next(s for s in SLIDES if s['title']=='실패 지형을 나누고, 먼저 시도할 과제를 골랐습니다')
    terrain['body']='<div class="terrain-five">'+''.join(f'<figure><img src="../../../../sim/eval/results/20260928-terrain-shots/stills/{name}.png" alt="{name} 지형"><figcaption>{name}</figcaption></figure>' for name in ['gap','rails','stepping_stones','pit','floating_ring'])+'</div><p class="callout">FIVE RECIPE, ONE SOLUTION · 지형별 해결 방법을 병렬로 탐색하는 계획</p>'
    terrain['note']='기획에서는 gap,rails,stepping_stones,pit,floating_ring 다섯 과제를 나누고 학습 설정을 모으려 했습니다. 이 사진은 지형을 설명하는 현재 렌더이며 최초10종 시험의 실패 장면 자체는 아닙니다. 그중 먼저gap에 집중했습니다. 학습 경험에 없던 틈이었고, 바닥이 검출되지 않을 때의 입력 처리도 살펴봐야 했기 때문입니다.'
    terrain['source']=source('기획 발표 §8-3 · 다섯 지형별 레시피','../../../../deliverables/plan/proposal.md')
    # Explicitly keep this a measured profile, not a rendered Digital Twin photograph.
    twin=next(s for s in SLIDES if s['title']=='실제 공간을 가져오는 작업도 함께 진행했습니다')
    twin['body']=twin['body'].replace('실제 지면 후보로 생성한 2.5D 메시','복원 점군과 2.5D 격자의 높이 단면 비교')


def speed_chart():
    rows=list(csv.DictReader((ROOT/'sim/eval/results/20260928-v2-sweep/sweep_long.csv').open(encoding='utf-8-sig')))
    unseen={'discrete_obstacles','floating_ring','pit','repeated_boxes','repeated_cylinders','star','stepping_stones','wave'}
    data={}
    for m in ['nv','v1','v2']:
        vals=[]
        for sp in [.5,1,1.5]:
            group=[float(r['overall_success_rate'])*100 for r in rows if r['model']==m and float(r['difficulty'])==.5 and float(r['speed'])==sp and r['terrain'] in unseen]
            assert len(group)==8,(m,sp,len(group))
            vals.append(sum(group)/len(group))
        data[m]=vals
    labels=['NVIDIA','v1','v2']; colors=['#61707d','#20333d','#0e7a6e']
    h='<div class="speedchart">'
    for j,s in enumerate(['0.5 m/s','1.0 m/s','1.5 m/s *']):
        h+='<div class="speedgroup"><div class="columns">'
        for i,(m,v) in enumerate(data.items()):h+=f'<div><b>{v[j]:.1f}%</b><i style="height:{v[j]*3.3}px;background:{colors[i]}"></i><span>{labels[i]}</span></div>'
        h+=f'</div><h3>{s}</h3></div>'
    return h+'</div><p class="small">* NVIDIA 학습 명령 범위 밖 · 같은 난이도와 평가 조건, 서로 다른 학습 설정·예산</p>',data

def build():
    SLIDES.clear();make_slides();apply_user_story_order();enrich(SLIDES,globals());revise(SLIDES);refine(SLIDES);revise_research(SLIDES);revise_closing(SLIDES)
    revise_media(SLIDES); axes_scene.apply(SLIDES); spoken_steps.apply(SLIDES); experiment_frame.apply(SLIDES)
    # 2026-10-02 병렬 작업 모듈 (순서 중요: 띠 뒤에 실패 유형 · 삽입 장은 제목 기준)
    failure_types.apply(SLIDES); terrain_catalog.apply(SLIDES); charts_u209.apply(SLIDES); compare_tables.apply(SLIDES); bridge_slide.apply(SLIDES)
    # 팀장 마지막 수정 2026-10-02 16:4x: 내리막 계단 속도 추종 장은 뺀다 · 29쪽 정지 전환 영상은 3초부터
    _drop='더 어려운 내리막 계단에서는 속도 추종이 낮아졌습니다'; assert sum(x['title']==_drop for x in SLIDES)==1; SLIDES[:]=[x for x in SLIDES if x['title']!=_drop]
    _st=next(x for x in SLIDES if x['title']=='정지 명령 전환 때의 낙상이 줄었습니다'); _n=_st['body'].count('<video '); assert _n==2,_n; _st['body']=_st['body'].replace('<video ','<video data-start="3" ')
    # 병렬 작업용 확장 고리 (2026-10-02): FOOTHOLD_DECK_EXTRA=design.a,design.b 의 apply(SLIDES) 를 차례로 부른다.
    for _m in [m for m in os.environ.get('FOOTHOLD_DECK_EXTRA','').split(',') if m.strip()]:
        importlib.import_module(_m.strip()).apply(SLIDES)  # 단계 장 멘트에 (클릭) 박기 (2026-10-02)
    chart,data=speed_chart()
    original=(HERE/'design/cover-approved.template.html').read_text(encoding='utf-8')
    basecss=re.search(r'<style>([\s\S]*?)</style>',original).group(1).replace('#slide','#cover')
    cover=re.search(r'<section id="slide"[\s\S]*?</section>',original).group().replace('id="slide"','id="cover"').replace('class="enter"','class="slide cover enter active" data-index="0"')
    oldnote=re.search(r'<div id="notesContent">([\s\S]*?)</div><p class="note-help"',original).group(1)
    oldnote=oldnote[:oldnote.find('<h3>다음 장면과의 연결')]+ '<h3>다음 장면</h3><p>오프닝 재생을 시작합니다. 첫 디딤이 끝나면 “그럼 FOOTHOLD의 첫걸음을 함께 시작하겠습니다.”라고 말하고 다음 장으로 넘깁니다.</p>'
    allnotes=[COVER_NOTES+'<p class="note-cue"><b>넘기기</b> → 「'+esc(SLIDES[0]['title'])+'」</p>']; sections=[]
    for i,s in enumerate(SLIDES,1):
        body=s['body'].replace('__SPEED_CHART__',chart)
        section=s['section'];dark=s['kind'] in ['cinema','photo','qa-slide']
        route='' if dark else f'<div class="route"><span>{section}</span><div class="route-line"><i style="left:{min(i/len(SLIDES)*100,94)}%"></i></div></div>'
        head='' if dark else f'<header><p class="eyebrow">FOOTHOLD <span>· {section}</span></p>{route}<h2>{s["title"]}</h2></header>'
        footer='' if dark else f'<footer><div>{s["source"]}</div><span>{i+1:02} / {len(SLIDES)+1:02}</span></footer>'
        sections.append(f'<section class="slide {s["kind"]}" data-index="{i}" data-steps="{s["steps"]}" aria-label="{esc(s["title"])}">{head}<div class="content">{body}</div>{footer}</section>')
        spoken=s.get('spoken',s['note'])
        # ★ 2026-10-02 팀장 요청: 「메모에 (클릭-혹은 넘기기) 로 슬라이드 넘기면서
        #   자연스럽게 화면이랑 이어서 말할 수 있게 텀을 넣어줘 (간단히 표시)」.
        #   멘트 본문에 섞지 않고 «별도 줄» 로 둔다. 단계수와 다음 장 제목을
        #   여기서 세므로 장을 더하거나 빼도 손으로 고칠 곳이 없다.
        nxt=SLIDES[i]['title'] if i < len(SLIDES) else None
        cue=[]
        if s['steps']: cue.append('<b>클릭 %d번</b>으로 이 장을 진행' % s['steps'])
        if nxt: cue.append(('그다음 ' if s['steps'] else '')+'<b>넘기기</b> → 「%s」' % esc(nxt))
        else: cue.append('<b>마지막 장</b>입니다')
        allnotes.append('<h2>'+esc(s['title'])+'</h2>'
          +'<p class="note-cue">'+' · '.join(cue)+'</p>'
          +'<h3>발표 멘트</h3><p>'+esc(spoken).replace('(클릭)','<i class="cue-click">클릭</i>')+'</p>'
          +'<details><summary>자료 해석·제작 확인</summary><p>'+esc(s['note'])+'</p><p>'+s['source']+'</p></details>')
    css='\n'.join((HERE/('design/'+x)).read_text(encoding='utf8') for x in ['deck.css','intro_story.css','scene_revision.css','technical_scene.css','presentation_u206.css','research_revision.css','closing_revision.css','experiment_frame.css','axes_scene.css','failure_types.css','terrain_catalog.css','charts_u209.css','compare_tables.css','bridge_slide.css','media_fit.css']+[x.strip() for x in os.environ.get('FOOTHOLD_DECK_EXTRA_CSS','').split(',') if x.strip()]+['layout_u208.css'])
    js='\n'.join((HERE/x).read_text(encoding='utf8') for x in ['assets/go2-blender/v4-manifest.js','assets/go2-blender/v4-player.js','assets/go2-blender/v5-manifest.js','assets/go2-blender/v6-manifest.js','assets/go2-blender/v5-player.js','design/remote.js','design/deck.js','design/intro_story.js','design/axes_scene.js','design/compare_tables.js']+[x.strip() for x in os.environ.get('FOOTHOLD_DECK_EXTRA_JS','').split(',') if x.strip()])
    controls='''<nav id="controls"><button onclick="prev()">← 이전</button><button onclick="next()">다음 →</button><span id="counter"></span><button onclick="toggleTOC()">목차</button><button class="m-hide" onclick="fullscreen()">F 전체화면</button><button onclick="toggleNotes()">N 메모</button><button class="m-hide" onclick="openPresenter()">P 별도 창</button><button class="m-hide" onclick="playVideos()">V 영상</button><button class="m-hide" onclick="window.print()">PDF 출력</button><button onclick="toggleRemote()">리모트</button><span id="remoteChip" hidden></span></nav><div id="remote" hidden><b>폰 리모트</b><p>폰에서 대본 페이지를 열고 같은 방 코드를 넣으면, 폰에서 넘길 때 이 화면이 넘어갑니다.</p><label>방 코드 <input type="text" maxlength="24" placeholder="예: foothold" autocomplete="off"></label><button onclick="remoteConnect()">연결</button><button onclick="remoteOff()">끊기</button><span id="remoteStatus">리모트 꺼짐</span></div><aside id="notes" hidden><div class="note-actions"><button onclick="document.querySelector('#notes').classList.toggle('left')">좌우 이동</button><button onclick="openPresenter()">별도 창</button><button onclick="toggleNotes()">닫기</button></div><div id="notesContent"></div></aside><div id="blank" hidden></div><aside id="toc" hidden><button onclick="toggleTOC()">닫기</button><h2>발표 목차</h2><div id="tocItems"></div></aside>'''
    meta=[dict(title='FOOTHOLD · 미경험 험지 적응 정책',section='표지',steps=0)]+[{k:s[k] for k in ['title','section','steps']} for s in SLIDES]
    output='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FOOTHOLD · MVP 중간발표</title><style>'+basecss+'\n'+css+'</style></head><body><main id="viewport">'+cover+''.join(sections)+'</main>'+controls+'<script>const deckMeta='+json.dumps(meta,ensure_ascii=False)+';const deckNotes='+json.dumps(allnotes,ensure_ascii=False).replace('</',r'<\/')+';'+js+'</script></body></html>'
    assert '\u2014' not in output
    if os.environ.get('FOOTHOLD_DECK_OUT'):   # 미리보기 빌드: 공용 산출물(매니페스트·대본 지도)은 안 건드린다
        _o=Path(os.environ['FOOTHOLD_DECK_OUT']); _o.write_text(output,encoding='utf-8'); print(f'{len(meta)} slides -> {_o} (preview)'); return
    (OUT/'FOOTHOLD-MVP-cover.html').write_text(output,encoding='utf-8')
    (HERE/'PPT-BUILD-MANIFEST.json').write_text(json.dumps({'slides':meta,'count':len(meta),'speed_success_percent':data,'entry':'output/FOOTHOLD-MVP-cover.html','template':'design/cover-approved.template.html'},ensure_ascii=False,indent=2),encoding='utf-8')
    mapping=['# 발표 원문과 실제 화면 대응','', '근거: [사용자가 직접 전달한 멘트 원문](USER-SPOKEN-NARRATIVE.md). 아래는 현재 구현 상태이며 최종 승인표가 아니다.','', '| 화면 | 발표 흐름 | 다음 장면과의 연결 |','|---|---|---|']
    mapping += [f'| {i+2} | {s["title"]} | {s.get("spoken",s["note"]).replace("|","·")} |' for i,s in enumerate(SLIDES)]
    (HERE/'PPT-SPOKEN-FLOW-MAP.md').write_text('\n'.join(mapping)+'\n',encoding='utf-8')
    print(f'{len(meta)} slides -> {OUT / "FOOTHOLD-MVP-cover.html"}')
if __name__=='__main__':build()
