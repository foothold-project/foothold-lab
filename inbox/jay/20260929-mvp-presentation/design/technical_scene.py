"""Actual v2 configuration, authored as reversible click stages around one Go2."""
from .intro_story import make, src
import re

SOURCE=src('Go2 · 관측 · 네트워크 · 제어 근거','../PPT-TECHNICAL-SCENE-EVIDENCE.md')

def stage(n,html,cls=''):
    return f'<div class="tech-layer {cls}" data-only-step="{n}">{html}</div>'

def card(cls,kicker,title,body):
    return f'<article class="tech-label {cls}"><small>{kicker}</small><h3>{title}</h3><p>{body}</p></article>'

def line(frame,text):
    # v6 카드 글줄 점등. frame 은 build_v6.py apply() 의 프레임 번호(그 동작이 화면에 나타나는 첫 프레임).
    return f'<span data-from="{frame}">{text}</span>'

def lines(paths,dots):
    return '<svg class="tech-leaders" viewBox="0 0 1600 900" aria-hidden="true">'+''.join(f'<path class="leader" d="{p}"/>' for p in paths)+''.join(f'<circle cx="{x}" cy="{y}" r="4"/>' for x,y in dots)+'</svg>'

def neural(name,out):
    xs=[25,97,169,241,313];counts=[5,7,6,5,out if out==1 else 6]
    ys=[[105+(j-(n-1)/2)*20 for j in range(n)] for n in counts]
    edges=''.join(f'<path d="M{xs[k]} {a} L{xs[k+1]} {b}"/>' for k in range(4) for a in ys[k] for b in ys[k+1])
    nodes=''.join(f'<circle cx="{x}" cy="{y}" r="4" style="--delay:{k*.18}s"/>' for k,x in enumerate(xs) for y in ys[k])
    labels=''.join(f'<text x="{x}" y="202">{t}</text>' for x,t in zip(xs,['235','512','256','128',str(out)]))
    return f'<svg class="neural-network" viewBox="0 0 338 225" role="img" aria-label="{name}:235,512,256,128,{out}"><g class="synapses">{edges}</g><g class="neurons">{nodes}</g>{labels}</svg>'

def height_print():
    points={(i,j):(120+i*32+j*14,82+j*16-i*1.3-(14 if i>9 else 0)) for i in range(17) for j in range(11)}
    edges=[]
    for (i,j),(x,y) in points.items():
        for neighbor in [(i+1,j),(i,j+1)]:
            if neighbor in points:
                a,b=points[neighbor];edges.append(f'<path d="M{x} {y} L{a} {b}"/>')
    dots=''.join(f'<circle cx="{x}" cy="{y}" r="1.7"/>' for x,y in points.values())
    return '<svg class="scan-print" viewBox="0 0 900 380" aria-label="높이 관측 187개 지점 설명 도식">'+''.join(edges)+dots+'</svg>'

def technical_slides():
    hardware='<div class="technical-world hardware-world"><img class="technical-robot" data-shared="go2" src="../assets/go2-blender/go2-front-v5.png" alt="실제 Go2 USD 모델"><canvas class="continuous-player" width="1600" height="1200" aria-label="실제 Go2: 턴테이블 · 네 다리 · 관절 · 발 접촉 · 피드백 · 센서 · 명령 애니메이션(설명용 기구학)"></canvas>'
    hardware+=stage('0','<p class="tech-opening">Unitree <b>Go2</b><span>관측을 받아, 열두 관절의 움직임으로.</span></p>')
    hardware+=stage('1',card('label-left','관절 / ACTUATION','한 다리에 세 회전축',line(446,'고관절 외전·내전')+'<br>'+line(460,'허벅지 굽힘·폄')+'<br>'+line(474,'무릎 굽힘·폄'))+card('label-right','총 12 자유도',line(490,'4개의 다리 × 3개의 관절'),'각 관절의 움직임을 조합해<br>발의 위치와 몸의 자세를 제어합니다.')+'<div class="joint-key" data-from="446"><i></i> 원: 회전 중심 · 선: 회전축</div>')
    hardware+=stage('2',card('label-left','발 / CONTACT','바닥을 딛고, 몸을 지탱합니다.',line(552,'발끝 접촉이 몸을 지지합니다.')+'<br>EDU 구성: 발끝 힘 센서')+card('label-right','관절 / FEEDBACK','목표 각도를 따라 움직입니다.',line(567,'모터 토크')+' → '+line(581,'관절 회전')+' → '+line(583,'발 이동')+'<br>'+line(605,'관절 위치·속도는 다시 상태 정보로 돌아옵니다.')))
    hardware+=stage('3',card('label-left','전면 카메라','주변을 영상으로 봅니다.',line(665,'기본 광각 카메라: RGB 영상')+'<br>상단 마이크: 음성·인터컴')+card('label-right','4D LiDAR','주변의 거리를 측정합니다.',line(697,'점군으로 공간과 장애물을 표현')+'<br>공식 Go2 소개: L2')+'<p class="tech-small-note">하드웨어가 얻을 수 있는 정보 · 현재 보행 정책에 직접 넣는 관측은 다음 단계에서 구분합니다.</p>')
    hardware+=stage('4','<div class="module-strip"><figure data-from="1214"><img src="../assets/module-d435i-official.png" alt="팀의 D435i 모듈"><figcaption><b>RealSense D435i</b><span>RGB · 깊이 영상 · IMU</span></figcaption></figure><figure data-from="1191"><img src="../assets/hesai-isolated-u206.png" alt="팀의 HESAI 모듈"><figcaption><b>HESAI-360</b><span>3D 공간 인지와 항법</span></figcaption></figure><figure data-from="1168"><img src="../assets/orin-isolated-u206.png" alt="NVIDIA Jetson Orin NX 모듈"><figcaption><b>Orin NX 16GB</b><span>인지·항법 연산</span></figcaption></figure></div><p class="tech-small-note">팀이 보유한 추가 모듈 · 장착 자리는 Unitree Go2 EDU 구성과 같음 · D435i 는 RealSense 공식 메시, 연산 모듈 · HESAI 형상은 근사 · 기본 Go2의 RGB 카메라와 추가 Depth 카메라는 다른 장비입니다.</p>')
    hardware+=stage('5',card('label-left','명령 / BODY FRAME','어느 방향으로 움직일까요?',line(727,'<code>vₓ</code> 전진 · 후진')+'<br>'+line(771,'<code>vᵧ</code> 좌 · 우 횡이동')+'<br>'+line(819,'<code>ωz</code> 좌 · 우 회전'))+card('label-right','명령은 세 축','발의 움직임은 정책이 만듭니다.','몸체 기준의 목표 속도를 입력합니다.<br>발 하나하나의 궤적을 직접 지시하지 않습니다.'))
    hardware+='</div>'
    hw=make('로봇의 이해','어떤 정보를 보고, 무엇을 움직일까요?',hardware,
      '오늘 우리 프로젝트와 함께 이야기를 풀어갈 Unitree Go2입니다. 한 다리에 세 개의 회전 관절이 있고, 네 다리를 합쳐 열두 자유도를 제어합니다. 모터가 관절을 돌리면 발의 위치가 바뀌고, 바닥과의 접촉이 몸을 지탱합니다. 앞에는 주변을 보는 카메라와 거리를 측정하는 LiDAR가 있습니다. 기본 카메라와 별도로, 저희 팀은 깊이 영상을 얻는 D435i와 HESAI 모듈, Orin NX도 가지고 있습니다. 이런 장비로 얻을 수 있는 정보와 지금 실험에서 사용하는 입력은 구분해서 보겠습니다. 그리고 사용자에게 받는 명령은 전후, 횡이동, 회전입니다. 이 간단한 명령을 열두 관절의 움직임으로 바꾸려면 무엇이 필요할까요?',SOURCE,kind='intro authored technical-page hardware-page',steps=5,
      note='실제 USD 기반 모델. 표시된 기계 동작은 설명용 관절 애니메이션이다. 기본 카메라는 RGB, D435i가 추가 깊이 카메라. L2는 공식 소개 및 사용자 제공 자료 기준이며 대여 개체의 세대를 직접 검사한 결과는 아니다. 모터 토크 수치를 제품 최고제원과 시뮬 설정으로 혼용하지 않는다.')
    obs='<div class="technical-world policy-world"><div class="sim-floor"><canvas class="scan-canvas" width="900" height="380" aria-label="17 곱하기 11 높이 검사 격자 설명"></canvas></div><img class="policy-robot" data-shared="go2" src="../assets/go2-blender/go2-front-v4.png" alt="같은 Go2 모델">'
    obs=obs.replace('</canvas>','</canvas>'+height_print())
    obs+=stage('0','<p class="tech-opening">이 Go2가 받는 입력은<br><b>무엇일까요?</b></p>')
    obs+=stage('1','<div class="obs-list"><small>몸 상태 · 명령 · 이전 행동</small><h3>48<span>개</span></h3><dl><dt>선속도 · 각속도 · 투영 중력</dt><dd>3 + 3 + 3</dd><dt>전후 · 횡이동 · 회전 명령</dt><dd>3</dd><dt>관절 위치 · 관절 속도</dt><dd>12 + 12</dd><dt>직전 행동</dt><dd>12</dd></dl></div><div class="height-explain"><small>주변 지면 높이</small><h3>187<span>개</span></h3><p>17 × 11 · 간격 0.1 m</p><p>몸체를 중심으로<br>1.6 m × 1.0 m 범위를 검사합니다.</p><span class="method-note">시뮬레이션 지면 RayCaster</span></div><p class="policy-total">48 + 187 = <b>235</b>개의 관측</p>')
    obs+=stage('2 3 4','<div class="observation-bus"><span>몸 상태 · 명령 · 이전 행동 <b>48</b></span><span>지면 높이 <b>187</b></span><strong>관측 235</strong></div><div class="actor-block"><small>실행 / ACTOR</small><h3>다음 행동을 계산합니다.</h3>'+neural('Actor',12)+'<p>관절별 행동 12개</p></div><svg class="policy-flows" viewBox="0 0 1600 900"><path class="flow-line" d="M800 242 L1100 242 L1100 390 L1150 390"/><path class="flow-line return-flow" d="M1170 573 L1090 573 L1000 650 L947 650"/><circle class="signal a-signal" r="4"><animateMotion dur="2s" repeatCount="indefinite" path="M800 242 L1100 242 L1100 390 L1150 390"/></circle><circle class="signal b-signal" r="4"><animateMotion dur="2s" repeatCount="indefinite" path="M1170 573 L1090 573 L1000 650 L947 650"/></circle></svg>')
    obs+=stage('2','<div class="action-explain"><small>위치 목표로 변환</small><code>q_target = q_default<br>+ 0.25 × action</code><p>PD 제어 → 모터 토크 → 관절 움직임</p><p>출력 12개는 직접 토크가 아닙니다.</p></div>')
    obs+=stage('3 4','<div class="critic-block"><small>학습 / CRITIC</small><h3>상태의 가치를 추정합니다.</h3>'+neural('Critic',1)+'<p>가치 1개 → PPO 학습에 사용</p></div><svg class="policy-flows" viewBox="0 0 1600 900"><path class="flow-line" d="M800 242 L505 242 L505 390 L445 390"/><circle class="signal" r="4"><animateMotion dur="2s" repeatCount="indefinite" path="M800 242 L505 242 L505 390 L445 390"/></circle></svg><p class="learning-caption">같은 관측을 받는 <b>별도의 두 신경망</b> · Critic은 관절을 직접 제어하지 않습니다.</p>')
    obs+=stage('4','<div class="learning-loop"><span>행동</span><i>→</i><span>새 상태 · 보상</span><i>→</i><span>PPO 갱신</span><i>→</i><span>다음 행동</span></div>')
    obs=obs.replace('M800 242 L1100 242 L1100 390 L1150 390','M1100 267 L1100 390 L1150 390').replace('M800 242 L505 242 L505 390 L445 390','M505 267 L505 390 L445 390')
    obs+='<p class="policy-diagram-note">관측·신경망 구조 설명 도식 · 격자와 신호는 실측 로그가 아닙니다.</p></div>'
    pol=make('보행 정책의 이해','관측이, 다음 발걸음이 되기까지',obs,
      '시뮬레이션 속 Go2도 같은 구조를 가지고 있습니다. 몸의 움직임과 기울기, 관절 위치와 속도, 수행할 명령, 이전 행동을 합쳐 48개의 값을 받습니다. 여기에 몸 주변 지면을 17 곱하기 11개 지점에서 검사한 높이 187개를 더합니다. 총 235개입니다. 현재 정책은 RGB 영상이나 실물 LiDAR 점군을 그대로 넣는 구조는 아닙니다. 이 관측이 Actor를 통과하면 열두 관절의 행동이 나오고, 기준 자세에 더해 관절 위치 목표가 됩니다. 제어기가 목표를 따라 모터를 움직이면서 한 걸음이 만들어집니다. 학습할 때는 같은 관측을 받은 별도의 Critic이 상태의 가치를 추정합니다. 행동의 결과와 보상을 모아 정책을 갱신하는 것입니다. 이렇게 보고, 움직이고, 다시 관측하는 과정을 반복합니다.',SOURCE,kind='intro authored technical-page policy-page',steps=4,
      note='v2 체크포인트의 실제 MLP: Actor235-512-256-128-12, Critic235-512-256-128-1, ELU. 점과 높이 격자의 모션은 설명 도식이며 실제 활성값/실시간 높이 로그가 아니다. 입력 순서와 크기는 원자료 확인. 접촉력/RGB/Depth/점군을 235 직접입력으로 연결하지 않는다.')
    army='<div class="technical-world army-world"><div class="army-film"><video muted playsinline preload="metadata" poster="../../20260929-mvp-submission/source/media/train-army.jpg" src="../../20260929-mvp-submission/source/media/train-army.mp4"></video></div><div class="army-single"><canvas class="army-player" width="1600" height="1200" aria-label="Go2 · 명령 장면에서 정면으로 돌아 대군 속으로"></canvas><div class="army-ground"></div></div><div class="army-caption"><small>ISAAC LAB · 병렬 학습</small><h3><span class="env-counter">1</span><em>개 환경</em></h3><p>같은 정책으로, 서로 다른 경험을 모읍니다.</p></div><p class="army-render-note" data-step="2">학습 설정 4,096개 · 화면은 600개 환경으로 렌더한 학습 시연</p><p class="army-next" data-step="2">그렇다면, 무엇을 먼저 가르쳐야 했을까요?</p></div>'
    army=army.replace('class="army-render-note" data-step="2"','class="army-render-note" data-step="1"')
    arm=make('학습과 평가','한 대의 경험을, 4,096개 환경에서 함께 모읍니다',army,
      '이 한 대가 경험하는 과정을 여러 환경에서 동시에 모으면 어떨까요? 저희는 실제 학습에서 4,096개 환경을 병렬로 사용했습니다. 화면은 학습 과정을 볼 수 있도록 600개 환경으로 렌더한 시연입니다. 서로 다른 지형과 명령에서 얻은 경험으로 같은 정책을 학습합니다. 그런데 이렇게 학습하기 전에, 우리는 현재 어디에 서 있는지 먼저 알아야 했습니다. 그래서 성공하는 모습만 보기보다 실패 데이터에 집중했습니다.',SOURCE,kind='intro authored technical-page army-page',steps=2,note='정면 Go2에서 실제 학습 영상으로 전환하고 영상 영역을 확대 상태에서 원래 프레임으로 축소한다. 원본 Isaac 카메라가 실제 한 로봇에서 4096 전체까지 연속 촬영한 영상이라고 주장하지 않는다. 4096은 env.yaml 실제학습 설정, train-army는 600개 렌더.')
    # U206 inserts two explanatory stops before the existing joint stages.
    hw['body']=re.sub(r'data-only-step="([1-5])"',lambda m:f'data-only-step="{int(m[1])+2}"',hw['body'])
    hw['body']+=stage('1',card('label-left','같은 기체, 같은 관절','몸체와 네 다리의 연결','몸체의 자세와 네 발의 접촉을<br>함께 제어해야 합니다.'))
    hw['body']+=stage('2',card('label-left','네 개의 다리 모듈','지지점을 바꾸는 네 다리','각 다리는 몸체에 연결되고,<br>세 관절이 발의 위치를 만듭니다.'))
    hw['steps']=7
    pol['body']=re.sub(r'<div class="sim-floor">.*?</div>','',pol['body'],count=1,flags=re.S)
    pol['body']=re.sub(r'<img class="policy-robot"[^>]+>','<canvas class="policy-v5-player" width="1600" height="1200" aria-label="Go2 정면에서 그 자리에서 돌아 측면 · 위에서 내려오는 레이저가 187개 지면 높이 검사 지점을 훑는다(설명용)"></canvas><img class="policy-v5-print" src="../assets/go2-blender/go2-side_grid-v5.png" alt="같은 Go2 측면과 몸체 기준 지면 검사 격자">',pol['body'],count=1)
    pol['body']=pol['body'].replace('M1170 573 L1090 573 L1000 650 L947 650','M1170 573 L1090 573 L1000 520 L940 485')
    return [hw,pol,arm]
