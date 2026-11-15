"""U206 research slides. All rates are recalculated from episode-level CSVs."""
from pathlib import Path
import csv
import html
import json

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
RESULTS = ROOT / 'sim/eval/results'
MEDIA = '../../20260929-mvp-submission/source/media/'
STILLS = '../../../../sim/eval/results/20260928-terrain-shots/stills/'
MODELS = ['NVIDIA', 'v1', 'v2']
ROOTS = dict(zip(MODELS, [RESULTS/'20260921-nvidia-axis1', RESULTS/'maindata-v1/foothold-v1', RESULTS/'20260923-v2rs/v2g2-feetair01-iter3000']))
ROUGH = ['pyramid_stairs','pyramid_stairs_inv','boxes','random_rough','hf_pyramid_slope','hf_pyramid_slope_inv']
UNSEEN = ['discrete_obstacles','floating_ring','pit','repeated_boxes','repeated_cylinders','star','stepping_stones','wave']
NAMES = {'pyramid_stairs':'오르막 계단','pyramid_stairs_inv':'내리막 계단','boxes':'상자 지형','random_rough':'불규칙 바닥','hf_pyramid_slope':'오르막 경사','hf_pyramid_slope_inv':'내리막 경사','gap':'틈 · gap','rails':'턱 · rails','discrete_obstacles':'불연속 장애물','floating_ring':'고리 장애물','pit':'함몰 지형 · pit','repeated_boxes':'반복 상자','repeated_cylinders':'반복 원기둥','star':'방사형 장애물','stepping_stones':'디딤돌','wave':'물결 지형'}

def _read(root, difficulty=.5, speed=None, terrains=None):
    rows=[]
    for f in sorted(root.glob('*/*/*/generalization_raw.csv')):
        m=json.loads((f.parent/'run_manifest.json').read_text(encoding='utf-8'))
        if float(m['terrain_difficulty_range'][0]) != difficulty: continue
        if speed is not None and float(m['command_vx_mps']) != speed: continue
        if float(m['command_vx_mps']) not in (.5,1.,1.5): continue
        assert m['eval_spec_version']==2
        with f.open(encoding='utf-8-sig',newline='') as h:
            rows.extend(r for r in csv.DictReader(h) if terrains is None or r['terrain'] in terrains)
    return rows

def _rate(rows, axis='overall_success'):
    assert rows, 'Missing raw evidence'
    return 100*sum(r[axis].lower()=='true' for r in rows)/len(rows)

def _source(label, path='inbox/jay/20260929-mvp-presentation/PPT-U206-EVIDENCE.md'):
    return f'<a href="../../../../{path}" target="_blank" rel="noopener">{html.escape(label)}</a>'

def _video(file, label):
    assert (HERE.parent/'20260929-mvp-submission/source/media'/file).exists(),file
    return f'<figure class="rr-film"><video controls muted playsinline preload="none" poster="{MEDIA+file.replace(".mp4",".jpg")}" src="{MEDIA+file}"></video><figcaption>{label}</figcaption></figure>'

def _still(name):
    assert (ROOT/'sim/eval/results/20260928-terrain-shots/stills'/f'{name}.png').exists()
    return f'<img src="{STILLS}{name}.png" alt="{NAMES[name]}">'

def _slide(title, body, spoken, section='MVP 성과', source='', note=''):
    return dict(title=title,body=f'<div class="rr-wrap">{body}</div>',spoken=spoken,note=note or spoken,section=section,source=source or _source('평가 원자료 재집계 · 조건과 파일'),kind='research-revision',steps=0)

def _bottom(text):return f'<p class="rr-bottom">{text}</p>'
def _condition(text):return f'<p class="rr-condition">{text}</p>'

def revise_research(slides):
    """Mutate the slide list after enrich/revise/refine. Do not touch introduction/technical scenes."""
    def replace(old,new):
        i=next(i for i,s in enumerate(slides) if s['title']==old)
        slides[i]=new
    def insert_before(title,new):
        i=next(i for i,s in enumerate(slides) if s['title']==title);slides.insert(i,new)
    data={m:_read(p) for m,p in ROOTS.items()}
    assert all(len(r)==4800 for r in data.values())

    # Explain the concrete change in task distribution before the input-code detail.
    tiles=''.join(f'<figure>{_still(t)}<figcaption>{NAMES[t]}</figcaption></figure>' for t in ROUGH)
    body='<div class="rr-terrain-compare"><div><h3>출발 정책이 배운 여섯 지형</h3><div class="rr-six">'+tiles+'</div></div><div class="rr-gap-hero"><h3>추가할 경험: 바닥이 끊긴 틈</h3>'+_still('gap')+'<p>기존 6종 90% + forward_gap 10%</p></div></div>'+_bottom('내려가는 바닥을 걷는 것과, 바닥이 없는 틈을 건너는 것은 다른 경험입니다.')
    body=body.replace(_still('gap'),f'<img src="{MEDIA}train-gap-forward.jpg" alt="실제 학습에 추가한 forward_gap">')
    body=body.replace('<p>기존 6종 90% + forward_gap 10%</p>','<p>기존 6종 90% + forward_gap 10%</p><p>첫 학습: 전진 0.5~1.5 m/s<br>횡이동 0 · 회전 0</p>')
    replace('틈을 만나게 하고, 바닥이 없다는 입력도 바로잡았습니다',_slide('왜 첫 과제로 gap을 골랐을까요?',body,'기존 정책도 계단과 경사, 불규칙한 바닥을 배웠습니다. 내려가는 계단도 있었습니다. 하지만 바닥이 끊긴 틈은 다른 과제였습니다. 그래서 기존 경험을 남긴 채 틈을 추가하고, 바닥을 못 찾았을 때 입력이 어떻게 들어가는지도 확인했습니다.','실패에서 시작한 실험',_source('rough6 구성과 forward_gap 10%','sim/policy/gap_env_cfg.py')))
    ray_svg='''<svg class="rr-ray-svg" viewBox="0 0 1340 230" role="img" aria-label="같은 광선이 표면을 맞히거나 빈 틈에서 미검출되는 차이"><g stroke="#3b575b" stroke-width="3"><path d="M60 183H310V155H410V183H565" fill="none"/><path d="M770 183H900M1110 183H1280"/><path d="M900 183V222M1110 183V222" stroke-dasharray="6 7"/></g><g fill="#234d51"><rect x="245" y="20" width="140" height="40" rx="12"/><rect x="945" y="20" width="140" height="40" rx="12"/></g><g stroke="#087668" stroke-width="3" stroke-dasharray="8 7"><path d="M280 62V181M350 62V154M980 62V225M1050 62V225"/></g><g fill="#087668"><circle cx="280" cy="183" r="7"/><circle cx="350" cy="155" r="7"/></g><g font-size="25" fill="#203b40"><text x="262" y="105" text-anchor="end">표면 충돌점 있음</text><text x="1125" y="110">충돌점 없음</text></g></svg>'''
    body=ray_svg+'<div class="rr-code-compare"><div><h3>기본 함수: 높이 차를 그대로 계산</h3><p>sensor_z − hit_z − offset</p><p>미검출 +∞ → 계산 −∞ → clip <b>−1</b></p><p class="rr-note">−1 은 「바닥이 더 높다」 쪽 값이라<br>없는 바닥을 있다고 전하게 됩니다.</p></div><div><h3>FOOTHOLD: 미검출을 먼저 구분</h3><p>isfinite로 유효한 충돌점인지 확인</p><p>미검출 → 「여기는 바닥이 없다」 <b>+1</b></p><p class="rr-note">구멍을 따로 분류해 학습한 것이 아니라,<br>관측값이 전하는 뜻을 바로잡은 것입니다.</p></div></div>'+_bottom('입력 235개는 유지하고, 바닥을 못 맞힌 광선의 의미를 바로잡았습니다.')
    replace('바닥에 닿지 않은 광선은 낮은 지면으로 구분합니다',_slide('바닥을 못 찾았다는 정보도 올바르게 전달해야 했습니다',body,'광선이 표면에 닿으면 높이 차를 계산할 수 있습니다. 그런데 바닥이 없는 틈에서는 충돌점이 무한대로 들어옵니다. 대조한 기본 함수는 이를 별도로 구분하지 않아 클리핑 뒤 반대 방향인 마이너스1이 됐습니다. 저희는 유효값인지 먼저 검사하고, 바닥을 못 찾았다는 것을 플러스1로 구분해 넣었습니다. 여기가 구멍이라는 것을 정책에 알리는 값입니다. 지형 경험과 입력 처리를 함께 보완한 것입니다.','실패에서 시작한 실험',_source('기본 함수와 미검출 처리 대조','sim/eval/gap_observations.py'),note='로컬 IsaacLab observations.py:292–300과 대조. 모든 NVIDIA 버전에 대한 일반화 아님. 기본 입력 차원·ray 수 유지. 현재 세 모델 평가에는 동일 miss 처리를 적용.'))

    # Combine evaluation axes and comparison conditions in one readable page.
    body='<div class="rr-eval"><div><h3>축 1 · 지형 통과</h3><div class="rr-axis-chain"><span>생존</span><b>∩</b><span>전진</span><b>∩</b><span>속도 추종</span><b>∩</b><span>방향 유지</span></div><p>네 조건을 모두 만족해야 성공입니다.</p><p>16종 × 3속도 × 100판 = 모델당 <b>4,800판</b></p></div><div><h3>축 2 · 명령 수행</h3><p>정지 · 유지 · 회전 명령을 주고<br>낙상과 실제 움직임을 별도로 확인합니다.</p><p>지형 통과율에 합쳐 하나의 점수로 만들지 않습니다.</p></div></div><div class="rr-protocol"><p><b>NVIDIA → v1 → v2</b></p><p>난이도 0.5 · 속도 0.5 / 1.0 / 1.5 m/s<br>지형·속도당 100판 · 평가 시드 42</p><p>전진 ≥ 3m · 속도 MAE ≤ 0.25m/s<br>3m 지점의 방향 오차 ≤ 0.75m</p></div>'+_bottom('같은 평가 조건으로 비교합니다. 학습량이 같거나 독립 최종시험이라는 뜻은 아닙니다.')
    replace('지형 통과와 명령 수행을 두 축으로 평가했습니다',_slide('지형을 건너는 능력과 명령을 따르는 능력을 함께 봅니다',body,'험지를 건너는 능력과 명령을 따르는 능력을 두 축으로 확인했습니다. 지형 성공은 살아남는 것뿐 아니라 전진, 속도 추종, 방향까지 모두 만족해야 합니다. 세 모델은 같은 난이도와 속도에서 비교했습니다. 그래서 성공률이 낮다고 곧 넘어진 것은 아닙니다.'))
    slides[:]=[s for s in slides if s['title']!='같은 평가 조건에서 세 모델을 비교했습니다']

    # Two side-by-side halves keep all 16 terrain rows above a 22px type floor.
    def matrix(terrains):
        h='<table class="rr-matrix"><thead><tr><th>지형</th>'+''.join(f'<th>{m}</th>' for m in MODELS)+'</tr></thead><tbody>'
        for t in terrains:
            h+='<tr><td>'+NAMES[t]+'</td>'
            for m in MODELS:
                r=[r for r in data[m] if r['terrain']==t];assert len(r)==300;v=_rate(r)
                h+=f'<td style="--rr-fill:{v}%"><span>{v:.1f}%</span></td>'
            h+='</tr>'
        return h+'</tbody></table>'
    avg=''.join(f'<div><span>{m}</span><strong>{_rate(data[m]):.2f}%</strong></div>' for m in MODELS)
    body='<div class="rr-overall">'+avg+'</div><div class="rr-double"><div><h3>기존 6종 + 추가학습 관련 gap·rails</h3>'+matrix(ROUGH+['gap','rails'])+'</div><div><h3>세 정책에 공통으로 학습되지 않은 8종</h3>'+matrix(UNSEEN)+'</div></div>'+_condition('d0.5 · 세 속도 합산 · 지형당 300판 · 전체 4,800판 / 모델')
    insert_before('1.0 m/s에서 공통 미경험 8종의 성공률이 높아졌습니다',_slide('전체 지형에서 무엇이 달라졌는지 먼저 보겠습니다',body,'먼저 학습한 지형까지 포함한 전체 결과입니다. 기존 여섯 지형에서의 능력을 유지하면서, 집중해서 학습한 gap과 rails가 좋아졌습니다. 오른쪽은 세 정책 모두 학습에 넣지 않은 여덟 지형입니다. 이쪽에서도 향상이 있지만 디딤돌은 여전히 어렵습니다. 다음에는 이 여덟 지형만 따로 보겠습니다.'))

    # Real pit footage replaces the floating-ring example as requested.
    pit=''
    for m,filetag in zip(MODELS,['nvidia','v1','v2']):
        r=_read(ROOTS[m],speed=1.5,terrains=['pit']);assert len(r)==100
        pit+=f'<div>{_video(f"hero-pit-v15-{filetag}.mp4",m)}<p class="rr-video-rate">{_rate(r):.0f}% <span>성공 / 100판</span></p></div>'
    replace('숫자와 함께, 같은 조건의 움직임을 봅니다',_slide('학습하지 않은 함몰 지형에서도 움직임이 달라졌습니다','<div class="rr-triple">'+pit+'</div>'+_condition('pit · 난이도 0.5 · 명령 1.5m/s · 영상은 각 한 판의 예시')+_bottom('낙상뿐 아니라 전진 거리와 명령 속도를 함께 봅니다.'),'이번에는 학습하지 않은 pit, 함몰 지형입니다. 같은 조건의 세 모델을 나란히 보겠습니다. 아래 수치는 각각 백 판의 성공률이고, 영상은 한 판의 예시입니다. NVIDIA의1.5미터퍼세컨드는 원래 학습 명령 범위 밖이라는 점도 함께 봐야 합니다.'))
    for s in slides:
        if s['title']=='학습하지 않은 함몰 지형에서도 움직임이 달라졌습니다':
            s['body']=s['body'].replace('영상은 각 한 판의 예시','영상은 각 한 판의 예시<br>NVIDIA 1.5m/s는 학습 명령 범위 밖 · 개발 중 반복 평가한 지형')

    # Weight comparison from all 48 cells, not hand-entered report percentages.
    bars=''
    for weight,name in [(.01,'v2b-r'),(.1,'v2g2-feetair01'),(1.,'v2g-feetair1')]:
        rr=_read(RESULTS/'20260923-v2rs'/f'{name}-iter3000');assert len(rr)==4800
        rate=_rate(rr);n=sum(r['overall_success']=='True' for r in rr)
        bars+=f'<div class="rr-reward-row"><span>가중치 <b>{weight:g}</b></span><div class="rr-bar"><i style="width:{rate}%"></i></div><strong>{rate:.2f}%</strong><span>{n:,} / 4,800</span></div>'
    body='<div class="rr-reward-intro"><h3>feet_air_time</h3><p>발이 공중에 머무르는 시간에 관한 기존 보상항<br>발 높이나 착지 위치를 직접 보상하는 항은 아닙니다.</p></div><div class="rr-reward-chart">'+bars+'</div>'+_condition('같은 평가 48칸 · d0.5 · 16종 × 3속도 · 각 100판 · iter3000 후보')+_bottom('이 비교에서는 0.1 후보를 채택했습니다. 한 가중치의 보편적 우월성을 입증한 결과는 아닙니다.')
    replace('보상 가중치도 비교했습니다',_slide('발을 들어 옮기는 경험을 보상 가중치로도 비교했습니다',body,'rails를 넘는 디딤을 개선하기 위해 발의 체공시간 보상 가중치도 비교했습니다. 새로운 보상함수를 만든 것은 아닙니다. 전체48칸을 같은 조건으로 다시 재니 이 비교에서는0.1후보가 가장 높았습니다. 다만 학습시드에 따른 차이도 있어 이 가중치가 언제나 낫다고 말하지는 않습니다.','실패에서 시작한 실험',_source('후보별 원CSV · 전체 48칸 재집계','sim/eval/results/20260923-v2rs')))

    # Do not hide a regression behind the average.
    v2s=RESULTS/'20260924-observe/sweep/v2g2-feetair01-iter3000'
    videos='<div class="rr-regression-videos">'+_video('regress-stairsinv-d09-v1.mp4','v1 · 내리막 계단')+_video('regress-stairsinv-d09-v2.mp4','v2 · 같은 조건')+'</div>'
    h='<table class="rr-failure-table"><thead><tr><th>100판 집계</th><th>전체 성공</th><th>생존</th><th>전진</th><th>속도 추종</th><th>방향</th></tr></thead><tbody>'
    for m,p in [('v1',ROOTS['v1']),('v2',v2s)]:
        rr=_read(p,.9,1.5,['pyramid_stairs_inv']);assert len(rr)==100
        h+='<tr><td>'+m+'</td>'+''.join(f'<td>{_rate(rr,a):.0f}%</td>' for a in ['overall_success','survival_success','progress_success','tracking_success','direction_success'])+'</tr>'
    body=videos+h+'</tbody></table>'+_condition('pyramid_stairs_inv · 난이도 0.9 · 명령 1.5m/s · 영상은 대표 한 판')+_bottom('살아남고 전진해도, 요구한 속도를 유지하는 문제는 남았습니다.')
    insert_before('디딤돌에서는 평가 시드에 따라 성공률이 흔들렸습니다',_slide('더 어려운 내리막 계단에서는 속도 추종이 낮아졌습니다',body,'전체 평균이 좋아졌어도 모든 조건이 함께 좋아진 것은 아닙니다. 난이도0.9 내리막계단을1.5속도로 내려갈 때 v2는 생존백퍼센트였지만 속도추종은3퍼센트였습니다. 무너진다는 말보다, 움직일 수 있어도 요구한 속도를 유지하지 못한다는 해석이 맞습니다. 이런 조건을 다음 실험에 남겨 두었습니다.','남은 과제'))
    # Keep the initial curriculum and adoption argument, without duplicate empty pages.
    initial=next(s for s in slides if s['title']=='첫 학습은 틈 10%와 전진 명령 제한으로 시작했습니다')
    terrain=next(s for s in slides if s['title']=='왜 첫 과제로 gap을 골랐을까요?')
    terrain['spoken']+=' '+initial.get('spoken',initial['note'])
    decision=next(s for s in slides if s['title']=='후보 탐색은 병렬로, 채택은 전체 평가로 바꿨습니다')
    reward=next(s for s in slides if s['title']=='발을 들어 옮기는 경험을 보상 가중치로도 비교했습니다')
    reward['spoken']+=' '+decision.get('spoken',decision['note'])
    reward['body']=reward['body'].replace('이 비교에서는 0.1 후보를 채택했습니다. 한 가중치의 보편적 우월성을 입증한 결과는 아닙니다.','병렬로 후보 탐색 → 전체 지형·명령 재평가 → 버전별 채택<br><span class="rr-adoption-note">이번 비교는 0.1 채택 · 한 가중치의 보편적 우월성을 입증한 결과는 아닙니다.</span>')
    slides[:]=[s for s in slides if s is not initial and s is not decision]
    return slides
