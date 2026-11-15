"""Slide-specific visual arguments. Read evidence rather than hand-enter chart values."""
from pathlib import Path
import csv,json

def enrich(slides, ctx):
    root, here = ctx['ROOT'], ctx['HERE']
    pic, clip, table, source = (ctx[k] for k in ('pic','clip','table','source'))
    def find(title): return next(s for s in slides if s['title']==title)
    def set_(title,body,kind='evidence',foot=None,note=None):
        s=find(title);s['body']=body;s['kind']=kind
        if foot:s['source']=foot
        if note:s['note']=note
        return s
    def condition(text):return '<div class="condition">'+text+'</div>'
    def finding(text):return '<div class="finding">'+text+'</div>'
    def terrain(name):return f'<img src="../../../../sim/eval/results/20260928-terrain-shots/stills/{name}.png" alt="{name}">'
    def local(label,path):return source(label,'../../../../'+path)
    audit={}
    def raw_rate(path,terrain_name=None):
        rows=[];files=[]
        for f in sorted((root/path).glob('**/d0.5/**/generalization_raw.csv')):
            files.append(str(f.relative_to(root)).replace('\\','/'))
            rows.extend(r for r in csv.DictReader(f.open(encoding='utf-8-sig')) if terrain_name is None or r['terrain']==terrain_name)
        expected=300 if terrain_name else 4800
        assert len(rows)==expected,(path,len(rows),expected)
        total=sum(r['overall_success'].lower()=='true' for r in rows)
        audit[path]={'files':files,'terrain':terrain_name,'success':total,'episodes':len(rows),'percent':total/len(rows)*100}
        return total/len(rows)*100
    # ★ 2026-10-02. 계보에 「잃은 것」을 넣으려면 축 2 숫자가 필요하다.
    #   손으로 적지 않는다. 기록된 요약과 per_env 를 둘 다 읽고 어긋나면 멈춘다.
    #   sim/eval/results/20260929-axis2-fall/{nvidia,v1,v2}/{hold,stop,turn}
    #   ★ 이 수치는 «낙상 수» 다. 성공률이 아니다 (probe_manifest 의
    #     not_a_judgement: 판정은 eval_generalization 의 네 축 AND 하나다).
    def fall(model, probe):
        base = root/'sim/eval/results/20260929-axis2-fall'/model
        mf = json.loads((base/'probe_manifest.json').read_text(encoding='utf-8'))
        su = mf['summary'][probe]
        rows = json.loads((base/probe/'per_env.json').read_text(encoding='utf-8'))
        mine = sum(1 for r in rows if r.get('fell'))
        assert mine == su['fell_count'], (model, probe, mine, su['fell_count'])
        assert su['envs'] == len(rows) == 64, (model, probe, su['envs'], len(rows))
        audit['axis2/%s/%s' % (model, probe)] = {
            'fell': su['fell_count'], 'envs': su['envs'],
            'checkpoint': mf['policy_checkpoint'].replace(chr(92), '/').split('/')[-1],
            'seed': mf['seed'], 'what': su['what']}
        return su['fell_count']

    def compare(videos, captions, values=None):
        return '<div class="evidence-videos">'+''.join('<div>'+clip(v,c)+(f'<div class="result-value">{values[i]}</div>' if values else '')+'</div>' for i,(v,c) in enumerate(zip(videos,captions)))+'</div>'

    set_('미경험 험지란 무엇일까요?',
      '<div class="terrain-story">'+pic('terrain-question-bright-v1.png','폭과 단차, 틈이 달라지는 지형')+
      '<span class="terrain-label at-gap">틈 · 연속된 바닥이 끊김</span><span class="terrain-label at-width">폭 · 디딜 수 있는 면적</span><span class="terrain-label at-step">단차 · 다음 발의 높이</span></div>'+
      finding('학습 때 경험한 조건을 벗어나도, 다음 발을 디딜 수 있을까?')+
      condition('현실에는 마찰·재료 강도·미끄러움도 존재합니다. 이번 실측 범위는 시뮬레이션 지형입니다.'),'terrain-scene')
    set_('우리는 발을 옮겨 지지점을 바꾸는 이동에 주목했습니다',
      '<div class="foot-choice"><div>'+pic('go2-reference/side-walk.png','Go2 공식 보행 프레임')+'</div><div class="choice-argument"><p class="lead">지면에서 수행할 임무</p><p>센서를 운반해 가까이에서 관찰하고,<br>필요한 위치에서 멈추고 다시 이동합니다.</p><hr><p class="lead">끊긴 바닥의 이동</p><p>발을 들어 디딜 위치를 바꿉니다.<br>지지와 균형은 매 걸음 다시 확보해야 합니다.</p></div></div>'+
      finding('우리의 연구 범위: 불연속적인 지면에서 보행을 이어가는 정책'),
      foot=source('Unitree Go2 공식 보행 자료','https://www.unitree.com/go2'))
    set_('위험 현장에 먼저 들어갈 로봇을 필요로 합니다',
      '<div class="document-proof"><figure>'+pic('fire-demand-seoul-excerpt.png','중소벤처기업부 제2026-309호 PDF16쪽 서울시 소방본부 항목 발췌')+'<figcaption>공식 공고 16쪽 · 서울시 소방본부 항목 확대</figcaption></figure><div><p class="proof-origin">서울시 소방본부 · 2026년 공공 수요</p><blockquote>현장 지휘 지원 및<br>대원 안전 확보 보행 로봇</blockquote><p>위험 구역의 정보를 얻고<br>대원이 현장을 판단하도록 돕는 역할입니다.</p><div class="fact-boundary">수요가 제시된 근거<br><b>현장 도입 완료나 우리 시스템의 실증 성과는 아님</b></div></div></div>',
      foot=source('중소벤처기업부 제2026-309호 · 공고 PDF16쪽','../assets/fire-demand-official.pdf#page=16'))
    set_('반복 점검을 맡기고, 사람은 수리에 집중합니다',
      '<div class="industry-proof"><div class="industry-photo">'+pic('deck-ab-inbev-spot.jpg','AB InBev에서 점검하는 Spot')+'</div><div class="industry-work"><p class="proof-origin">AB InBev · Leuven 공장</p><h3>점검을 수행하는 로봇</h3><p><strong>1,800</strong>건 / 주<br>반복적인 열·음향 점검</p><h3>발견한 문제를 처리하는 사람</h3><p>가동 중 누출을 찾아<br>수리와 예방정비에 집중</p></div></div><div class="industry-results"><div><span>첫 6개월</span><b>약 150건</b><span>이상 발견</span></div><div><span>평균 수리 기간</span><b>수개월 → 13일</b><span>제조사 공개 고객 사례</span></div></div>',
      foot=source('Boston Dynamics · AB InBev 고객 사례','https://bostondynamics.com/case-studies/energy-savings-predictive-maintenance-at-ab-inbevs-largest-european-brewery/'))
    set_('현장의 필요에서, 우리의 첫걸음으로',
      '<div class="story-agenda"><p>현장의 필요를 보았습니다.<br>이제 저희가 내디딘 첫걸음을 말씀드리겠습니다.</p><ol><li><b>어떻게 걷고 배우는가</b><span>Go2의 관측, 행동과 학습</span></li><li><b>실패를 보고 무엇을 바꿨는가</b><span>gap부터 명령 수행까지의 실험</span></li><li><b>무엇이 달라졌는가</b><span>같은 조건의 수치와 실제 움직임</span></li><li><b>다음에는 어디로 가는가</b><span>남은 보행 과제와 실제 공간·항법</span></li></ol></div>','chapter')
    set_('오늘의 이야기를 함께할 Unitree Go2입니다',
      '<div class="robot-hero">'+pic('go2-reference/go2-side-neutral-v2.png','Go2 형상 참고 이미지')+'<div class="robot-spec"><p>Unitree Go2</p><strong>12<span>자유도</span></strong><p>4개의 다리<br>다리마다 hip · thigh · calf</p></div></div>'+finding('이 로봇의 몸에서 얻은 정보는 어떻게 한 걸음이 될까요?'),
      foot=source('Unitree Go2 · 형상 참고 이미지 / 관절 구조는 프로젝트 설정과 대조','https://www.unitree.com/go2'))
    set_('이 로봇은 어떤 정보를 얻을 수 있을까요?',
      '<div class="hardware-proof"><div class="hardware-main">'+pic('go2-reference/component-map.jpg','Go2 공식 구성도')+'</div><div><div class="reveal" data-step="0"><h3>기본 기체</h3><p>전면 카메라 · 기본 LiDAR L2<br>몸체 자세 · 관절 위치와 속도</p></div><div class="reveal" data-step="1"><h3>팀의 추가 보유 모듈</h3><div class="module-pair">'+pic('go2-reference/module-d435i.png','D435i')+pic('go2-reference/module-hesai.png','HESAI-360')+'</div><p>Orin NX 16GB · D435i · HESAI-360</p></div><div class="reveal" data-step="2"><p class="finding">다음은 시뮬레이터에서 정책에 넣는 관측입니다.</p><p class="small">추가 모듈의 장착·연동 완료를 뜻하지 않습니다.</p></div></div></div>',
      foot=source('공식 기체 도해 · 사용자 보유 모듈 확인','../GO2-HARDWARE-REFERENCE.md'))
    set_('시뮬레이션 속 Go2가 받는 정보입니다',
      '<div class="observation-proof"><div class="scan-proof"><img src="../../20260929-mvp-submission/source/media/v2-height-scan.png" alt="높이 스캔 구조"><p>센서 위치에서 광선을 내려 지면 높이를 계산</p></div><div class="observation-list"><h3>관측 입력 <b>235</b></h3>'+table(['몸 상태·명령·이전 행동','48'],[['선속도 · 각속도 · 투영 중력','3+3+3'],['속도 명령','3'],['관절 위치 · 관절 속도','12+12'],['이전 행동','12']])+'<div class="scan-total"><span>지형 높이 스캔</span><b>187</b></div></div></div>'+finding('몸이 지금 어떤 상태인지, 어디로 가라는 명령인지, 주변 바닥이 어떤 높이인지'),
      foot=local('관측 항목과 높이 스캔 처리','sim/policy/gap_observations.py'))
    s=find('관측이 들어오면 12개 관절 목표가 나옵니다')
    s['body']='<div class="policy-diagram"><div class="policy-input reveal" data-step="0"><h3>관측</h3><b>235</b><p>몸·명령·이전 행동 48<br>높이 스캔 187</p></div><div class="policy-mlp reveal" data-step="1"><h3>Actor · MLP</h3><div class="layer-bars"><div><i style="height:210px"></i><b>512</b></div><div><i style="height:152px"></i><b>256</b></div><div><i style="height:100px"></i><b>128</b></div></div><p>은닉층별 뉴런 수</p></div><div class="policy-action reveal" data-step="2"><h3>출력</h3><b>12</b><p>기준 관절 자세 + 출력 × 스케일<br>관절 위치 목표로 변환</p></div></div><div class="policy-loop reveal" data-step="3">관절을 움직인 결과를 다시 관측하고, 다음 행동을 계산합니다.</div>'
    s['kind']='evidence'
    set_('학습에서는 critic이 행동의 결과를 평가하도록 돕습니다',
      '<div class="learning-diagram"><div><p class="proof-origin">로봇의 실행</p><h3>Actor가 행동을 선택</h3><p>관측을 받아 관절 목표를 출력</p></div><div class="experience"><p class="proof-origin">환경에서 얻는 경험</p><h3>다음 관측과 보상</h3><p>속도 추종 · 자세 · 접촉 · 움직임의 비용</p></div><div><p class="proof-origin">학습 시 사용하는 평가</p><h3>Critic이 가치를 추정</h3><p>행동의 결과가 기대보다 좋았는지 평가</p></div><div class="learning-update"><h3>PPO 업데이트</h3><p>경험을 모아 Actor와 Critic의 가중치를 갱신</p></div></div>'+condition('현재 Actor / Critic: MLP 512·256·128 · 실제 행동 출력은 Actor 경로'),
      foot=source('MVP 종합보고서 · PPO 학습 및 네트워크 설정'))
    initial=list(csv.DictReader((root/'sim/eval/results/20260903-rough10-1.0mps/summary-thr1.5.csv').open(encoding='utf-8-sig')))
    initial_raw=list(csv.DictReader((root/'sim/eval/results/20260903-rough10-1.0mps/generalization_raw.csv').open(encoding='utf-8-sig')))
    for summary in initial:
        group=[r for r in initial_raw if r['terrain']==summary['terrain']]
        assert len(group)==100
        successes=sum(all(r[k].lower()=='true' for k in ['survival_success','progress_success','tracking_success']) and float(r['peak_lateral_drift_m'])<=1.5 for r in group)
        assert abs(successes/100-float(summary['overall_success_rate']))<1e-9
    audit['initial_diagnosis']={'raw':'sim/eval/results/20260903-rough10-1.0mps/generalization_raw.csv','episodes':1000,'direction_threshold_m':1.5,'summary_matches':True,'eval_spec':1}
    names={'discrete_obstacles':'불규칙 장애물','wave':'물결 지형','stepping_stones':'디딤돌','gap':'틈','pit':'움푹한 지형','rails':'솟은 턱','star':'별 모양 경사','floating_ring':'떠 있는 고리','repeated_boxes':'반복 상자','repeated_cylinders':'반복 원기둥'}
    failed={'gap','stepping_stones','pit','rails','floating_ring'}
    body=condition('기획 당시 진단 · 2026-09-03 · 1.0 m/s · 난이도0.5 · 지형당100판')+'<div class="baseline-ten">'
    for r in sorted(initial,key=lambda r:(r['terrain'] not in failed,list(names).index(r['terrain']))):
        n=r['terrain'];v=float(r['overall_success_rate'])*100
        body+=f'<figure class="{"problem" if n in failed else "pass"}">'+terrain(n)+f'<figcaption><span>{names[n]}<small>{n}</small></span><b>{v:.0f}%</b></figcaption></figure>'
    body+='</div>'+finding('10종 중 다섯 지형에서 문제가 드러났습니다. 같은 실패였을까요?')+condition('당시 ray miss 입력 결함을 포함한 구규격 진단입니다. 최신 모델의 성과와 직접 비교하지 않습니다.')
    set_('무엇을 더 가르칠지, 실패에서 찾았습니다',body,'baseline-proof',local('9/3 실제 집계 · summary-thr1.5.csv','sim/eval/results/20260903-rough10-1.0mps/summary-thr1.5.csv'))
    frows=[]
    for n in ['gap','stepping_stones','pit','rails','floating_ring']:
        r=next(r for r in initial if r['terrain']==n)
        frows.append([n]+[f'{float(r[k])*100:.0f}%' for k in ['overall_success_rate','survival_rate','progress_success_rate','tracking_success_rate']])
    set_('실패 지형을 나누고, 먼저 시도할 과제를 골랐습니다',
      condition('기획 당시 같은 100판에서 본 결과 · 성공률과 생존율을 구분')+table(['지형','종합 성공','생존','전진','속도 추종'],frows)+
      '<div class="failure-reading"><p><b>gap · 디딤돌</b><br>생존부터 어려움</p><p><b>pit · rails · 고리</b><br>살아 있어도 전진·추종에 실패</p></div>'+finding('FIVE RECIPE, ONE SOLUTION · 문제를 나눠 탐색하되, 먼저 gap의 경험과 입력을 확인'),
      foot=local('당시 진단표 · 구규격, 최신 성과와 직접 비교 금지','sim/eval/results/20260903-rough10-1.0mps/summary-thr1.5.csv'))
    set_('틈을 만나게 하고, 바닥이 없다는 입력도 바로잡았습니다',
      '<div class="gap-decision"><div>'+clip('train-gap-forward.mp4','새로 추가한 forward_gap 학습 지형')+'</div><div><h3>왜 gap부터였을까?</h3><div class="reveal" data-step="0"><p class="decision-label">학습 경험의 빈자리</p><p>기본 rough6에 틈이 없었습니다.<br>틈을 마주하고 건너는 경험을 추가했습니다.</p></div><div class="reveal" data-step="1"><p class="decision-label">관측 처리의 빈자리</p><p>광선이 바닥에 닿지 않는 경우를<br>유한한 높이 값과 구분해야 했습니다.</p></div></div></div>'+finding('지형을 추가하기 전에, “바닥이 없다”는 입력부터 확인했습니다.'),
      foot=local('gap 지형·관측 정의','sim/policy/gap_env_cfg.py'))
    s=find('바닥에 닿지 않은 광선은 낮은 지면으로 구분합니다')
    s['body']=s['body'].split('<table>')[0]+'<div class="code-comparison"><div><h3>대조한 기본 함수</h3><pre>height = sensor_z - hit_z - offset\n\n미검출 hit_z = inf\nheight = -inf → clip(-1, 1) = -1</pre></div><div><h3>추가한 미검출 처리</h3><pre>valid = isfinite(hit_z) &amp; isfinite(height)\nheight = where(valid, height, +1.0)\n\n깊은 낙차 방향의 값으로 구분</pre></div></div>'
    s['source']=local('실제 구현 · height_scan_with_gap()','sim/policy/gap_observations.py');s['kind']='code-proof'
    set_('첫 학습은 틈 10%와 전진 명령 제한으로 시작했습니다',
      '<div class="training-design"><div>'+clip('train-gap-forward.mp4','forward_gap · 전진 방향에 배치한 틈')+'</div><div><h3>지형의 구성</h3><div class="terrain-share"><i></i></div><p>기존 rough6 <b>90%</b> · forward_gap <b>10%</b></p><h3>명령의 범위</h3>'+table(['명령','설정'],[['전진 vₓ','0.5~1.5 m/s'],['횡이동 vᵧ','0'],['회전 ωz','0']])+'</div></div>'+finding('틈을 향해 전진하는 경험에 먼저 학습을 집중했습니다.'),
      foot=local('학습 지형 proportion 및 명령 범위','sim/policy/gap_env_cfg.py'))
    # ★ 2026-10-02 팀장 지적: 「얻은 것은 보여지는데 잃은게 안보여지는 것 같아」.
    #   전진만 가르친 대가를 수치로 세운다. 축 2 는 평지 프로브 64환경·시드42 이고
    #   «낙상 수» 다 (성공률 아님). 세 칸 다 보여야 다음 장의 「명령을 다시 열었다」가
    #   왜 필요했는지가 선다.
    gap_nv = raw_rate('sim/eval/results/20260921-nvidia-axis1', 'gap')
    gap_v1_ = raw_rate('sim/eval/results/maindata-v1/foothold-v1', 'gap')
    led = ('<div class="lineage-ledger">'
           '<div class="led-gain"><span>얻은 것</span>'
           f'<p>틈 통과 <i>{gap_nv:.1f}%</i> → <b>{gap_v1_:.1f}%</b></p>'
           '<small>gap · 난이도 0.5 · 세 속도 300판</small></div>'
           '<div class="led-loss"><span>잃은 것 · 전진만 가르친 대가</span>'
           + table(['평지 명령 프로브', 'NVIDIA', 'v1'],
                   [['정지 · 4초 전진 뒤 명령 0',
                     f'{fall("nvidia","stop")} / 64', f'<b>{fall("v1","stop")} / 64</b>'],
                    ['유지 · 20초 내내 명령 0',
                     f'{fall("nvidia","hold")} / 64', f'<b>{fall("v1","hold")} / 64</b>'],
                    ['회전 · 제자리 요레이트',
                     f'{fall("nvidia","turn")} / 64', f'<b>{fall("v1","turn")} / 64</b>']])
           + '<small>낙상한 환경 수입니다. 성공률이 아닙니다.</small></div></div>')
    set_('전진 보행은 개선됐습니다. 멈춤은 별도로 확인해야 했습니다',
      compare(['lineage-gap-v1.mp4','axis2-stop-v1.mp4'],['v1 · gap을 건너는 모습','v1 · 4초 전진 뒤 정지 명령'])+
      led+finding('학습에서 횡이동과 회전을 0으로 잠갔습니다. 회전 명령에서는 64판 모두 넘어집니다. 명령을 다시 열면 두 능력을 함께 가져갈 수 있을까?')+condition('gap 영상은 한 판의 예시 · 축2는 64환경, 평가 시드42의 평지 프로브'),
      foot=source('v1 평가 원자료 · 축2 probe_manifest 와 per_env.json'),
      note='축 2 수치는 sim/eval/results/20260929-axis2-fall 의 기록 요약과 per_env 를 '
           '둘 다 읽어 대조한 값이다. 낙상 수이며 성공률이 아니다. 평지 프로브라 '
           '지형 통과 능력과 같은 축으로 더하지 않는다. NVIDIA 열은 같은 프로브의 '
           '같은 조건 실측이다.')
    gap_v1=raw_rate('sim/eval/results/maindata-v1/foothold-v1','gap')
    gap_d=raw_rate('sim/eval/results/20260918-D-axis1','gap')
    gap_e=raw_rate('sim/eval/results/20260920-E-axis1','gap')
    gap_f=raw_rate('sim/eval/results/20260920-F-axis1','gap')
    set_('명령을 넓힌 후보에서는 gap 성능이 낮아졌습니다',
      compare(['lineage-gap-v1.mp4','lineage-gap-D-fail.mp4'],['v1 · 전진 중심 설정','후보 D · heading과 정지 명령 개방'],[f'{gap_v1:.1f}%',f'{gap_d:.1f}%'])+
      '<div class="lineage-ledger wide">'
      '<div class="led-gain"><span>되찾으려 한 것</span>'
      '<p>heading과 정지 명령을 다시 열어<br>앞 장의 정지 · 회전 낙상을 줄이는 것</p>'
      '<small>그 후보의 축 2 는 따로 재지 않았습니다. 미확인이지 해결이 아닙니다.</small></div>'
      '<div class="led-loss"><span>대신 잃은 것</span>'
      f'<p>틈 통과 <i>{gap_v1:.1f}%</i> → <b>{gap_d:.1f}%</b></p>'
      '<small>전진에 묶여 있을 때보다 틈을 마주하는 경험이 줄었습니다.</small></div></div>'+
      condition('gap · 난이도0.5 · 0.5/1.0/1.5 m/s 각100판의 평균 · 영상은 개별 예시')+
      finding('명령을 열면 틈 경험이 줄어듭니다. 그렇다면 어느 방향으로 가도 틈을 만나게 하면 어떨까?'),
      foot=source('v1·D 실험 계보 · 여러 설정의 동시 변경, 단일 원인 분리 아님'),
      note='후보 D 는 gap 성적으로 걸렀다. 이 후보의 축 2 프로브는 돌리지 않았으므로 '
           '「명령을 열었더니 정지·회전이 좋아졌다」고 말할 수 없다. 안 잰 것이다. '
           '또한 D 는 여러 설정을 함께 바꾼 판이라 gap 하락을 명령 개방 하나의 효과로 '
           '단정하지 않는다.')
    set_('어느 방향으로 가도 틈을 만나도록 지형을 바꿨습니다',
      compare(['train-gap-forward.mp4','train-gap-omni.mp4'],['forward_gap · 정면에 있는 틈','omni_gap · 주변을 둘러싼 틈'])+
      '<div class="comparison-reading"><p>다른 방향으로 움직이면<br>틈을 마주하지 않을 수 있음</p><p>방향을 바꿔도<br>틈을 마주하는 경험을 늘림</p></div>'+finding(f'omni_gap과 최소 전진 속도0.4를 함께 적용한 F: gap {gap_f:.1f}%')+condition('난이도0.5 · 세 속도 각100판 평균 · 지형 변경 하나의 효과로 분리한 실험은 아님'),
      foot=source('F: omni_gap + vx_min0.4 · 실제 학습 지형과 계보 결과'))
    set_('방향·정지·디딤 경험을 함께 조정했습니다',
      '<div class="settings-proof"><div>'+terrain('rails')+'<p>rails · 일정 높이로 솟은 사각 테두리</p></div><div>'+table(['관찰','설정','목적'],[['방향에 따라 틈 경험 변화','omni_gap · heading','변한 방향에서도 틈 경험'],['전진 편중','정지 명령 표집0.1','멈춰 있는 명령 경험'],['솟은 턱에서 디딤 문제','rails 추가','발을 들어 장애물 넘기']])+'</div></div>'+condition('vₓ 0.4~1.5 m/s · vᵧ 0 유지 · 정지 표집 비율은 전체 시간의 비율과 다름')+
      '<div class="lineage-ledger wide">'
      '<div class="led-gain"><span>되찾은 것 · 같은 평지 프로브</span>'
      + table(['', 'v1', 'v2'],
              [['정지', f'{fall("v1","stop")} / 64', f'<b>{fall("v2","stop")} / 64</b>'],
               ['유지', f'{fall("v1","hold")} / 64', f'<b>{fall("v2","hold")} / 64</b>'],
               ['회전', f'{fall("v1","turn")} / 64', f'<b>{fall("v2","turn")} / 64</b>']])
      + '<small>낙상한 환경 수 · 64환경 · 시드 42</small></div>'
      '<div class="led-loss"><span>아직 남은 것</span>'
      f'<p>회전은 <b>{fall("v2","turn")} / 64</b> 로, 같은 프로브의 '
      f'NVIDIA <i>{fall("nvidia","turn")} / 64</i> 보다 높습니다.</p>'
      '<small>험지와 명령이 결합된 조건은 아직 재지 않았습니다.</small></div></div>'+
      finding('새로운 능력을 추가할 때마다 기존 지형도 다시 평가했습니다.'),foot=source('v2 params/env.yaml · 축2 probe_manifest'),
      note='되찾은 것과 남은 것을 같은 프로브로 나란히 둔다. v2 의 회전 낙상은 '
           'NVIDIA 보다 높다. 이것을 숨기지 않는다. 또한 v1 -> v2 는 지형·명령·'
           '보상을 함께 바꾼 판이라 이 회복을 한 가지 변경의 효과로 단정하지 않는다.')
    reward_rows=[]
    for weight,model,label in [('0.01','v2b-r','v2b-r'),('1.0','v2g-feetair1','v2g1'),('0.1','v2g2-feetair01','v2g2 · 채택')]:
        value=raw_rate(f'sim/eval/results/20260923-v2rs/{model}-iter3000')
        reward_rows.append([weight,label,f'{value:.2f}%'])
    set_('보상 가중치도 비교했습니다',
      '<div class="reward-proof"><div><h3>feet_air_time</h3><p>발이 공중에 머무르는 시간에 관한<br>기존 보상항의 가중치를 조정했습니다.</p><p class="small">높은 발 들기나 안전한 착지점을<br>직접 보상하는 항은 아닙니다.</p></div><div>'+table(['가중치','후보','전체16종 평균'],reward_rows)+'</div></div>'+condition('난이도0.5 · 16종 × 3속도 = 48칸 평균 · 후보별 학습 실행 차이를 포함')+finding('같은 레시피의 추가 학습 시드에서는92.94%,93.52%. 단일 실행의 차이를 원인으로 확정하지 않습니다.'),foot=local('v2 후보별 generalization_raw.csv 재계산','sim/eval/results/20260923-v2rs'))
    set_('후보 탐색은 병렬로, 채택은 전체 평가로 바꿨습니다',
      '<div class="method-proof"><div><p class="proof-origin">기획에서 출발</p><h3>FIVE RECIPE, ONE SOLUTION</h3><p>지형별 해결 설정을 모아<br>하나의 혼합 학습으로 통합</p></div><div><p class="proof-origin">실험에서 얻은 판단</p><h3>좋아진 능력이 다시 낮아질 수 있음</h3><p>gap 개선 뒤 명령 확대에서 퇴행 관찰<br>설정의 결합 효과를 따로 확인해야 함</p></div></div><div class="version-process"><span>병렬 후보 탐색</span><span>전체 지형·명령 재평가</span><span>버전별 채택</span></div>'+finding('탐색은 계속 병렬로 진행하고, 채택은 이전 능력 유지까지 확인합니다.'),foot=source('기획 제안 · 연구 방식 변경 #399','https://github.com/foothold-project/foothold-lab/issues/399'))
    set_('실제 공간을 가져오는 작업도 함께 진행했습니다',
      '<div class="twin-proof"><figure><video controls muted playsinline preload="none" poster="../../20260916-3dgs-test/_out/nurec/render_a_nurec.png" src="../../20260916-3dgs-test/_out/nurec/go2_B_mesh_hidden/run.mp4"></video><figcaption>실제 공간의 스플랫 배경과 충돌 메시 위 Go2 실행</figcaption></figure><div><h3>스마트폰 촬영에서 시뮬레이션까지</h3><p>35.9초 영상<br>287 / 287 이미지 등록<br>3DGS 복원 · 지면 메시 · USD 충돌체</p><h3>현재 확인한 범위</h3><p>배경 렌더와 정책 로드·추론·이동</p><h3>남은 검증</h3><p>실제 축척 · 충돌체와 관측의 정합성<br>실제 지면 대비 정확도</p></div></div>'+condition('2026-09-16 PoC · 12초 실행에 낙상·재시작 포함 · 보행 성능 비교 자료 아님'),
      foot=source('Real-to-Sim 실제 실행 기록','../../20260916-3dgs-test/RESULTS-3dgs-terrain.md'))

    # Per-terrain evidence complements the average, without changing the narrative order.
    s=find('1.0 m/s에서 공통 미경험 8종의 성공률이 높아졌습니다')
    rows=list(csv.DictReader((root/'sim/eval/results/20260928-v2-sweep/sweep_long.csv').open(encoding='utf-8-sig')))
    unseen=['discrete_obstacles','floating_ring','pit','repeated_boxes','repeated_cylinders','star','stepping_stones','wave']
    vals={}
    for n in unseen:
        vals[n]=[next(float(r['overall_success_rate'])*100 for r in rows if r['model']==m and float(r['difficulty'])==.5 and float(r['speed'])==1 and r['terrain']==n) for m in ['nv','v1','v2']]
    mean=[sum(v[i] for v in vals.values())/8 for i in range(3)]
    matrix='<table class="terrain-results"><thead><tr><th>미경험 지형</th><th>NVIDIA</th><th>v1</th><th>v2</th></tr></thead><tbody>'
    for n,v in vals.items():matrix+='<tr><td>'+n+'</td>'+''.join(f'<td class="{"weak" if a<50 else ""}">{a:.0f}%</td>' for a in v)+'</tr>'
    matrix+='</tbody></table>'
    s['body']='<div class="result-proof"><div class="result-averages">'+''.join(f'<div><span>{m}</span><b>{v:.1f}<small>%</small></b><i style="width:{v}%"></i></div>' for m,v in zip(['NVIDIA','foothold-v1','foothold-v2'],mean))+'</div><div>'+matrix+'</div></div>'+condition('1.0 m/s · 난이도0.5 · 공통 미경험8종 ×100판 · 평가 시드42')+finding('NVIDIA 대비 +28.5%p. v1에서 얻은 개선 위에 v2의 추가 향상이 이어졌습니다.')
    s['source']=local('sweep_long.csv 재계산 · gap/rails 제외','sim/eval/results/20260928-v2-sweep/sweep_long.csv');s['kind']='result-proof-slide'
    # Remove claim-only reference labels. Every unchanged source remains visible in notes.
    for s in slides:
        if s['kind']=='normal':s['kind']='research'
    spoken={
      '첫걸음':'그럼 저희 FOOTHOLD 프로젝트의 첫걸음을 함께 시작하겠습니다.',
      '우리가 건너려는 길은 이런 모습입니다':'방금 어둠 속에서 보셨던 길입니다. 바닥이 끊겨 있고, 높이와 폭도 제각각이죠. 우리가 이런 길을 처음 만난다면 어떻게 건너야 할까요?',
      '미경험 험지란 무엇일까요?':'미경험 험지는 한 번도 경험하지 않은 조건의 지형입니다. 현실의 바닥은 마찰, 경사, 틈의 폭처럼 여러 조건이 달라집니다. 저희는 그중 학습에서 만나지 않은 지형을 걷는 문제에 집중했습니다. 그럼 이런 곳에서 임무를 수행하려면 어떤 로봇이 적합할까요?',
      '이 길을 건너려면 어떤 이동 방식이 적합할까요?':'드론도 있고, 바퀴가 달린 로봇도 있고, 사족보행 로봇도 있습니다. 사실 목적에 따라 모두 정답일 수 있습니다. 저희가 사족보행을 고른 이유도 다른 로봇이 못 가기 때문이 아니라, 지면을 따라 이동하며 발 디딤을 바꾸는 능력을 연구하고 싶었기 때문입니다.',
      '우리는 발을 옮겨 지지점을 바꾸는 이동에 주목했습니다':'발을 들어 다음 지지점을 선택할 수 있다는 것이 다리를 쓰는 이동의 특징입니다. 다만 발을 옮기는 동안에도 몸의 균형을 유지해야 하죠. 저희는 이 보행에 집중했습니다. 그렇다면 현장에서도 이런 능력을 필요로 할까요?',
      '위험 현장에 먼저 들어갈 로봇을 필요로 합니다':'서울시 소방본부가 실제로 제시한 수요입니다. 현장 지휘를 돕고 대원의 안전을 확보하는 보행 로봇을 필요로 한다는 것입니다. 그럼 이미 로봇을 운영 중인 산업 현장에서는 어떤 변화가 있었을까요?',
      '반복 점검을 맡기고, 사람은 수리에 집중합니다':'이 공장에서는 Spot이 매주1800건의 개별 점검을 수행합니다. 첫6개월 동안 약150건의 이상을 발견했고, 평균 수리 기간은 수개월에서13일로 줄었습니다. 로봇이 반복 점검을 맡으면서 사람은 발견한 문제를 고치는 데 집중할 수 있게 된 것이죠. 이런 역할을 할 수 있다면, 낯선 바닥에서도 임무 지점까지 도달하는 보행 능력의 가치는 크지 않을까요?',
      '현장의 필요에서, 우리의 첫걸음으로':'그래서 저희는 미경험 험지 적응 정책에 주목했습니다. 앞서 현장의 필요성을 보았다면, 이제 우리가 풀고자 하는 문제는 무엇이며, 어떻게 해결하려 했고, 어떤 성과를 얻었는지, 앞으로 무엇이 남았는지 말씀드리겠습니다. 먼저 오늘 이야기를 함께할 로봇을 소개합니다.',
      '오늘의 이야기를 함께할 Unitree Go2입니다':'Unitree의 Go2입니다. 네 다리에 관절이 세 개씩 있어서12개의 자유도를 가집니다. 이 관절을 움직이기 위해 로봇은 어떤 정보를 얻을 수 있을까요?',
      '이 로봇은 어떤 정보를 얻을 수 있을까요?':'기체에는 카메라와 LiDAR가 있고, 몸의 자세와 관절 상태도 알 수 있습니다. 저희는 Orin NX16GB와 D435i, HESAI-360도 추가로 보유하고 있습니다. 이제 이 로봇을 시뮬레이션으로 옮겨, 실제로 보행 정책에 어떤 정보가 들어가는지 보겠습니다.',
      '시뮬레이션 속 Go2가 받는 정보입니다':'몸 상태와 명령, 이전 행동을 합쳐48개입니다. 여기에 주변 지형의 높이를 나타내는187개 값을 더합니다. 로봇은 이235개의 입력을 바탕으로 다음 행동을 정합니다. 그럼 이 정보가 신경망에서 어떻게 움직임으로 바뀔까요?',
      '관측이 들어오면 12개 관절 목표가 나옵니다':'관측이 Actor 신경망으로 들어갑니다.512개,256개,128개의 뉴런으로 이루어진 층을 거쳐12개의 행동 값이 나옵니다. 이 값에 스케일과 기준 자세를 적용해서 각 관절의 위치 목표를 만듭니다. 움직인 뒤에는 바뀐 몸 상태와 지형을 다시 관측합니다.',
      '신경망의 출력은 다시 이 로봇의 한 걸음이 됩니다':'방금 보신 출력이 이렇게 로봇의 한 걸음이 됩니다. 실제 저희 정책이 틈을 건너는 모습입니다. 그런데 처음부터 모든 바닥에서 잘 걷지는 않겠죠. 그렇다면 이 행동을 어떻게 더 잘하도록 학습시킬까요?',
      '학습에서는 critic이 행동의 결과를 평가하도록 돕습니다':'움직인 결과로 다음 관측과 보상을 얻습니다. Critic은 상태의 가치를 추정해 행동의 결과를 평가하는 데 도움을 줍니다. 모은 경험으로 Actor와 Critic의 가중치를 업데이트하는 방식입니다. 이 경험을 한 대에서만 모으면 오래 걸리겠죠.',
      '한 대의 경험을, 4,096개 환경에서 함께 모읍니다':'그래서4096개의 환경에서 동시에 경험을 모읍니다. 여러 환경에서 얻은 경험이 하나의 공통 정책에 반영됩니다. 저희는 NVIDIA의 사전학습 정책에서 출발했습니다. 이제 중요한 질문은 무엇을 더 가르쳐야 하는가입니다. 그래서 먼저 실패를 보았습니다.',
      '무엇을 더 가르칠지, 실패에서 찾았습니다':'기획 때 먼저10종의 지형에서 현재 정책을 시험했습니다. 여기서 다섯 지형에 문제가 드러났습니다. 왜 실패하는지 알아야 다음 학습을 정할 수 있기 때문입니다. 그런데 실패라고 해도 모두 같은 모습은 아니었습니다.',
      '실패 지형을 나누고, 먼저 시도할 과제를 골랐습니다':'틈과 디딤돌에서는 살아남기부터 어려웠습니다. 반면 pit이나 rails, 고리에서는 살아 있어도 충분히 전진하거나 명령 속도를 따라가지 못했습니다. 그래서 다섯 과제를 나눠 탐색하는 계획을 세웠습니다. 그중 먼저 gap에 집중했습니다.',
      '틈을 만나게 하고, 바닥이 없다는 입력도 바로잡았습니다':'왜 gap부터였을까요? 기본 학습 지형에는 이런 틈을 건너는 경험이 없었습니다. 그리고 바닥이 없어 높이 스캔이 닿지 않는 경우를 어떻게 처리하는지도 확인해야 했습니다. 지형을 학습시키는 일과 입력을 바로잡는 일이 함께 필요했습니다.',
      '바닥에 닿지 않은 광선은 낮은 지면으로 구분합니다':'광선이 바닥에 닿으면 높이를 계산할 수 있습니다. 그런데 닿지 않으면 무한대가 들어옵니다. 대조한 기본 함수에서는 이 값이 계산과 클리핑을 거치며 반대 방향의 값이 됩니다. 저희는 유한한 값인지 먼저 검사하고, 미검출을 깊은 낙차 방향의 값으로 구분했습니다.',
      '첫 학습은 틈 10%와 전진 명령 제한으로 시작했습니다':'이렇게 입력을 보완하고, 학습 지형의10퍼센트에 gap을 넣었습니다. 처음에는 전진 명령으로 제한해서 틈을 향해 가는 경험에 집중했습니다. 그 결과 틈을 건너는 행동을 얻었습니다. 다만 전진만 잘한다고 끝난 것은 아니었습니다.',
      '전진 보행은 개선됐습니다. 멈춤은 별도로 확인해야 했습니다':'얻은 것부터 보겠습니다. 왼쪽에서 틈을 건넙니다. 틈 통과가0.3퍼센트에서86퍼센트가 됐습니다. 그런데 대가가 있었습니다. 학습에서 횡이동과 회전을 0으로 잠갔기 때문입니다. 같은 평지 프로브에서 정지는64판 중13판, 유지는5판에서 넘어졌고, 회전은64판 모두 넘어졌습니다. 같은 조건의 NVIDIA는 정지와 유지가0판, 회전이4판입니다. 전진만 가르친 대가입니다. 그래서 명령을 다시 열어 보았습니다.',
      '명령을 넓힌 후보에서는 gap 성능이 낮아졌습니다':'정지와 회전을 되찾으려고 명령을 다시 열었습니다. 그랬더니 이번에는 틈 통과가86퍼센트에서33.3퍼센트로 떨어졌습니다. 하나를 되찾으려다 다른 하나를 잃은 것입니다. 다만 이 후보의 축2는 따로 재지 않았으니, 정지와 회전이 좋아졌다고 말할 수는 없습니다. 안 잰 것입니다. 또 여러 설정을 함께 바꿨기 때문에 원인을 하나로 단정하지도 않습니다. 그래서 명령이 아니라 지형을 보았습니다. 어느 방향으로 가도 틈을 만나게 하면 어떨까요?',
      '어느 방향으로 가도 틈을 만나도록 지형을 바꿨습니다':'정면에만 틈이 있으면 다른 방향으로 움직일 때는 틈을 만나지 않을 수 있습니다. 그래서 주변을 둘러싸는 omni_gap으로 바꾸고 최소 전진 속도도 함께 조정했습니다. 이 후보에서는 gap 성공률99퍼센트를 얻었습니다. 지형만이 아니라 명령과 경험을 함께 설계해야 했습니다.',
      '방향·정지·디딤 경험을 함께 조정했습니다':'방향을 바꿔도 틈을 경험하게 하고, 멈춰 있는 명령을 학습하도록 표집 비율을 조정했습니다. 솟은 턱을 넘는 경험을 위해 rails도 추가했습니다. 그 결과 같은 평지 프로브에서 정지는13판에서0판, 유지는5판에서0판, 회전은64판에서7판으로 내려왔습니다. 다만 회전은 같은 프로브의 NVIDIA 4판보다 아직 높습니다. 여러 가지를 함께 바꾼 판이라 이 회복을 한 가지 변경의 효과로 단정하지도 않습니다.',
      '보상 가중치도 비교했습니다':'발이 공중에 머무르는 시간과 관련된 보상 가중치도 비교했습니다. 이 조건에서는0.1 후보의 결과가 가장 높아 채택했습니다. 다만 학습 시드를 바꾸면 차이가 있기 때문에, 이 가중치 하나가 개선을 보장한다고 결론 내리지는 않았습니다.',
      '후보 탐색은 병렬로, 채택은 전체 평가로 바꿨습니다':'이 과정에서 기획 때의 접근도 달라졌습니다. 각각 잘 찾은 설정을 모으면 함께 좋아질 거라고 가정하기 어려웠습니다. 한 능력을 개선하는 동안 다른 능력이 낮아질 수 있었기 때문입니다. 후보 탐색은 병렬로 하되, 채택할 때는 전체를 다시 평가하는 방식으로 바꿨습니다. 그럼 이렇게 만든 현재 모델은 실제로 얼마나 달라졌을까요?',
    }
    spoken.update({
      '지형 통과와 명령 수행을 두 축으로 평가했습니다':'결과는 두 축으로 확인했습니다. 첫 번째는 지형을 통과하는가, 두 번째는 기본 명령을 따르는가입니다. 지형 성공은 살아남는 것뿐 아니라 전진, 속도 추종, 방향 유지까지 만족해야 합니다. 따라서 성공률이 낮다고 모두 넘어진 것은 아닙니다.',
      '같은 평가 조건에서 세 모델을 비교했습니다':'NVIDIA, v1, 현재 v2를 같은 평가 조건에서 비교했습니다. 어느 모델도 학습에 넣지 않은 공통8종을 따로 모았습니다. gap과 rails는 학습과 겹치므로 이 평균에서 뺐습니다. 먼저 같은1.0미터퍼세컨드에서 보겠습니다.',
      '1.0 m/s에서 공통 미경험 8종의 성공률이 높아졌습니다':'NVIDIA는62퍼센트, v1은87.4퍼센트, v2는90.5퍼센트였습니다. 큰 개선은 v1에서 얻었고, v2에서 추가 향상이 있었습니다. 오른쪽을 보면 평균만으로는 가려지는 지형별 차이도 확인할 수 있습니다. 디딤돌은 여전히 어렵습니다.',
      '목표 속도를 바꾸면 기준선의 차이가 더 크게 드러납니다':'속도를 바꾸면 결과가 어떻게 달라질까요? 세 속도를 함께 보면 이렇습니다. 여기서1.5는 NVIDIA의 기본 학습 명령 범위 밖입니다. 그래서 전체 평균만으로 비교하지 않고 속도별 결과를 함께 보여드립니다. 실제 움직임도 보겠습니다.',
      '숫자와 함께, 같은 조건의 움직임을 봅니다':'고리 지형에서 같은 조건으로 평가한 세 모델입니다. 영상은 각각 한 판의 예시이고, 아래 성공률은100판의 집계입니다. 성공하지 못한 로봇도 반드시 넘어지는 것은 아닙니다. 전진과 속도 추종을 함께 보시면 차이가 드러납니다.',
      '정지 명령 전환 때의 낙상이 줄었습니다':'앞서 v1에서 확인했던 정지 문제도 다시 보겠습니다. 같은64환경에서 v1은13번 넘어졌고 v2는넘어지지 않았습니다. NVIDIA도 이 조건에서는넘어지지 않았습니다. 개선한 것은 정지 전환의 낙상이며, 모든 정지 응답이 완벽해졌다는 뜻은 아닙니다.',
      '회전과 넓은 명령 조건은 아직 검증이 더 필요합니다':'그럼 무엇이 남았을까요? 회전과 더 넓은 명령 조건입니다. 전진 중심의 험지 통과가 좋아져도 후퇴나 횡이동, 험지에서의 회전까지 해결되는 것은 아닙니다. 이 조건들은 실제 움직임과 지표를 함께 보면서 더 검증해야 합니다.',
      '디딤돌에서는 평가 시드에 따라 성공률이 흔들렸습니다':'디딤돌도 남았습니다. 같은1.0속도에서 평가 시드만 바꿨을 때 성공률이0에서24퍼센트 사이였습니다. 좋은 한 번의 영상으로 안정적으로 건넌다고 말하기 어려운 이유입니다. 좁은 디딤을 다루는 경험과 관측을 다음에 더 살펴보려 합니다.',
      '세 작업은 프로젝트 끝까지 함께 이어집니다':'여기까지가 보행 정책에서 얻은 성과와 남은 문제였습니다. 처음에 보았던 현장으로 나가려면 실제 공간을 가져오는 일과 실제 로봇이 길을 찾는 일도 필요합니다. 그래서 보행 연구, Digital Twin, 실기 항법을 프로젝트 끝까지 함께 진행합니다.',
      '실제 공간을 가져오는 작업도 함께 진행했습니다':'실제로 촬영한 공간을 복원해서 시뮬레이션으로 가져오는 작업도 진행했습니다. 지금 보시는 것은 복원 배경과 충돌 지형을 연결한 실제 실행입니다. 로드와 이동까지 확인했지만 낙상도 있었고, 실제 축척과 충돌 지형의 정확도는 더 확인해야 합니다.',
      '실기에서는 순정 보행 위에 항법을 검증합니다':'실기에서는 Go2의 순정 보행을 사용하고 항법에 집중합니다. 지도를 만들고 목표점까지 가고 멈추고 돌아오는 과제를 검증하려는 것입니다. 저희 학습 정책을 실기에 이식했다는 성과와는 구분합니다. 보행과 항법의 불확실성을 한꺼번에 섞지 않기 위한 선택입니다.',
      '다음 학습은 지형과 명령을 함께 만나는 과제로 설계합니다':'다음 보행 과제는 험지를 지나야 목표에 도달하도록 만들고, 그 과정에서 감속과 정지, 회전도 함께 경험하도록 설계하려 합니다. 새 과제에서 좋아지는 것뿐 아니라 기존에 배운 능력을 유지하는지도 다시 확인하겠습니다.',
      '관측과 신경망의 효과도 분리해서 비교하겠습니다':'관측의 시간 이력과 지형 표현, 신경망 구조도 비교할 계획입니다. 더 큰 구조가 해결책이라고 먼저 정하지 않고, 같은 과제와 학습 예산에서 여러 시드로 비교하겠습니다. 현재의 개선과 앞으로 검증할 가설을 구분해서 이어가겠습니다.',
      'MVP 이후에도 세 흐름을 병행합니다':'MVP에서 보행 연구를 끝내고 항법으로 넘어가는 일정은 아닙니다. 정책과 신경망 실험, 실제 공간 복원, 실기 항법을 최종 발표까지 병행합니다. 각 흐름에서 확인한 것을 다음 검증으로 연결하겠습니다.',
      '실패를 확인했고, 다음 실험의 출발점을 만들었습니다':'저희는 먼저 실패를 보았습니다. 틈을 건너는 경험과 입력을 보완했고, 명령을 넓힐 때 생기는 문제를 다시 확인하며 현재 모델까지 왔습니다. 아직 남은 과제도 분명합니다. 이제 처음에 보셨던 현장으로 돌아가, 저희가 다음에 이어가고 싶은 걸음을 보여드리겠습니다. 다음 영상은 그 목표를 표현한 콘셉트입니다.',
      '현장으로 이어갈 다음 걸음':'클로징 영상을 재생합니다. 임무와 브랜드 영상이 끝나면 Q&A로 넘어갑니다.',
      'Q&A':'경청해 주셔서 감사합니다. 질문 받겠습니다.',
    })
    for s in slides:
        if s['title'] in spoken:s['spoken']=spoken[s['title']]
    (here/'PPT-EVIDENCE-AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
