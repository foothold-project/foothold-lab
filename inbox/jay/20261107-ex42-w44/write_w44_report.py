from pathlib import Path
import csv,json,hashlib,math,sys
import numpy as np
R=Path(__file__).resolve().parents[3]
O=R/'inbox/jay/20261107-ex42-w44';D=O/'data';S=R/'inbox/jay/20261106-ex41-stage-reports/data'
def csvread(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def tab(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
geom=csvread(D/'geometry.csv');windows=csvread(D/'training_windows.csv');cmd=csvread(D/'boundary_commands.csv')
feet=csvread(S/'w78_5500_6000_feet_stop.csv')
manifest=json.loads((S/'source_manifest.json').read_text(encoding='utf-8'))
originals={x['path']:x for x in manifest['sources']}
checked=[]
for p in sorted(set(r['source'] for r in cmd)):
    assert sha(Path(p))==originals[p]['sha256'],p
    checked.append({'path':p,'sha256':originals[p]['sha256']})
protocol=json.loads((S/'w78_5500_6000_protocol.json').read_text(encoding='utf-8'))
for key in ('old','new'):
    assert sha(Path(protocol[key]))==protocol[key+'_sha256']

# Snapshot distribution is not a completed-episode success rate.
path=Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/stage_log.jsonl')
def find(x):
    if isinstance(x,dict):
        if 'by_terrain' in x and 'mean_level' in x and any('levels' in r for r in x['by_terrain'].values()):return x
        for v in x.values():
            out=find(v)
            if out is not None:return out
    return None
dist=[]
with path.open(encoding='utf-8') as fp:
    for line_no,line in enumerate(fp,1):
        if 'by_terrain' not in line:continue
        obj=json.loads(line);x=find(obj)
        if x is not None:
            n=x.get('iteration',obj.get('iteration'))
            dist.append({'source_line':line_no,'outer_iteration':obj.get('iteration'),'iteration':n,**x})
(D/'terrain_snapshots.json').write_text('[\n'+',\n'.join(json.dumps(r,ensure_ascii=False,separators=(',',':')) for r in dist)+'\n]\n',encoding='utf-8')
print('terrain snapshots',len(dist),'last',[(x['iteration'],x.get('mean_level')) for x in dist[-3:]])

def g(l,k,key):return float(next(r for r in geom if int(r['L'])==l and r['kind']==k)[key])
text=['> 분류: A/평가 · W44 논의 자료','> 작성: analyst · 2026-11-07',
'> 근거: 생성기 CPU 메시·지지면 측정 · EX-41 원자료 및 W18 359615b1 · #555',
'> 요지: 준비 구간 길이와 L9 노출을 고를 때 사용할 근거·반대 근거·미측정을 구분한다.',
'> 상태: 판단 자료 · 권고·새 문턱·학습 승인 없음','',
'# W44 · 준비 T0′ 1,000/3,000회와 L9 확대의 판단 자료','',
'## 범위부터 구분','',
'이번 「0 단계」는 EX-41 누적 m12000 뒤의 준비 T0′ 연장 후보로 읽었다. 1,000회면 누적 m13000, 3,000회면 m15000이다[산술]. CURRICULUM-GATES §E.1의 E0는 별도로 새 메시·부모 확인 250회다[설계]. 준비 T0′·E0·지형 본학습 예산을 하나의 회차로 합치지 않는다. 아래에는 어느 갈림길을 택하라는 권고가 없다.','',
'## L5~L9가 실제로 뜻하는 크기','',
'연속 지형 생성기의 난도는 d=(L+U)/10, U∈[0,1)이다[코드: Isaac terrain_generator.py:251~264]. L9가 항상 최댓값은 아니다. 아래는 행의 허용 범위와 중간 d=(L+0.5)/10에서 원본 메시 함수를 CPU로 실행한 값이다. 운영 당시 U·전체 메시를 그대로 복원한 측정은 아니다. 단위는 전부 m이며 범위의 위 끝은 제외한다.','',
tab(['L','계단 한 단 범위','중간 메시 실측','boxes 윗면 ±한도(중간)','boxes 윗면 실제 최대 절댓값','이웃 단차 이론 한도(중간)'],[[l,f'{g(l,"pyramid_stairs","lo"):.3f}~{g(l,"pyramid_stairs","hi_exclusive"):.3f}',f'{g(l,"pyramid_stairs","mesh_measured"):.3f}',f'{g(l,"boxes","midpoint"):.5f}',f'{g(l,"boxes","mesh_measured"):.5f}',f'{2*g(l,"boxes","midpoint"):.5f}'] for l in range(5,10)]),'',
'[CPU 측정] 계단·역형 계단은 단 높이가 같고 방향이 다르다. 발판 깊이 0.30, 중앙 평탄부 폭 3.0은 고정이다. 고정 계단(stage_stairs)은 전 레벨 한 단 0.15, 거친 높이장(random_rough)은 높이 범위 0.01~0.06·간격 0.01이 그대로다[코드: rough_go2_cfg.py:10~34; hf_terrains.py:29~30,62~80]. 후자 둘의 L9 기록은 더 큰 기하 난도를 새로 배웠다는 증거가 아니다. boxes의 ±높이와 이웃 사이 단차는 다르며, 2배 상한은 실제 이웃 두 칸에서 반드시 발생한 값이 아니다.','',
'틈은 EX-41의 연속 7종과 W78 240조합에 없던 별도 종류다. 원코드 start_sheet.py의 세 빈 구간을 지지면 상자 끝점으로 직접 재었다. Go2 축척과 평가 확대는 이 코드의 원본 치수에 규칙을 적용한 **계산값**으로 따로 적었다.','',
tab(['L','원코드 틈 실측','Go2 ×1.108 계산','평가 틈 ×1.15 추가 계산','확장E 계단 중간 메시'],[[l,f'{g(l,"start_gen_v1_gaps","mesh_measured"):.4f}',f'{g(l,"start_gen_v1_gaps","mesh_measured")*1.108:.4f}',f'{g(l,"start_gen_v1_gaps","mesh_measured")*1.108*1.15:.4f}',f'{g(l,"paper_ext_v1_stairs_high","mesh_measured"):.4f}'] for l in range(5,10)]),'',
'[코드·설계] 원코드 틈은 0.10→0.70을 L/9로 보간한다(start_sheet.py:47,54~57,158~172). `start_go2_v2`의 x×1.108 및 평가 틈×1.15는 CURRICULUM-GATES §E.2·§E.3의 별도 변형이다. 검사한 runner 가지에는 preset 이름과 평가 배율 함수가 있지만, 원코드 자체의 GAP_WIDTH는 바뀌지 않았다. 이번 계산을 최종 EX-42 전체 메시에서 측정된 치수로 표기하지 않는다. 확장E 계단은 ex42.py:29~35의 0.05→0.30 범위로 만든 다른 종류이며, 기존 연속 L9와 같지 않다.','',
f'같은 연속 계단에서 L5 중간→L9 중간은 {g(9,"pyramid_stairs","midpoint")-g(5,"pyramid_stairs","midpoint"):.3f} m 증가, {100*(g(9,"pyramid_stairs","midpoint")/g(5,"pyramid_stairs","midpoint")-1):.1f}% 증가다[계산]. 상한 L9를 열어도 모든 env가 즉시 L9로 이동하는 것은 아니다. 실제 난도 노출은 종류별 reset·승급·강등 분포에 달려 있다. 틈 노출은 연속 지형 레벨 변경과 다른 축이다.','',
'## L5에서 지금 확인된 수행과 남은 폭','',
'W78는 고정 L5, 시작 방향 네 가지의 해당 지형 env를 모은 중앙값이다. R은 살아 있는 동안의 몸 기준 명령 방향 속도 적분÷전체 예정 거리(무차원)이고 성공률·실제 계단 끝 도착률이 아니다. 아래 각 칸은 누적 m12000 R (m11500 대비 ΔR). 원시 NPZ 각 240개와 코드·설정·시드·장치를 대조한 W18 결과를 재사용한다. 정방향·역형은 지형 생성기 종류 이름이며 실제로 계속 오르거나 내려갔다는 뜻은 아니다. 같은 저장본을 반복해 잰 차이 범위와 영상 전체 판독은 이번 자료에 없다.','']
comp=csvread(S/'w78_5500_6000_comparison.csv');modes=['eval_gt','eval_pred','probe_prop_only']
labels={'pyramid_stairs':'정방향 계단','pyramid_stairs_inv':'역형 계단'}
cases={'stairs_fwd':'전진','stairs_side_left':'왼쪽','stairs_side_right':'오른쪽','stairs_back':'후진'}
rr=[]
for kind in labels:
    for case in cases:
        line=[labels[kind],cases[case]]
        for mode in modes:
            x=next(x for x in comp if x['level']=='5' and x['kind']==kind and x['case']==case and x['mode']==mode)
            line.append(f"{float(x['R_6000']):.3f} ({float(x['delta_R']):+.3f})")
        rr.append(line)
text += [tab(['L5 지형','과제','정답','복원','끔'],rr),'',
'[실측 해석 범위] 전진의 두 지도 켬 모드는 두 종류에서 늘었다. 왼쪽 이동은 세 모드·두 종류에서 줄었다. 정방향 계단의 지도 켬 전진 이동량이 끔보다 작고, 역형에서는 반대다. 따라서 L5에서 더 다듬을 과제가 남았다는 근거와 계속 학습해도 모든 과제가 함께 좋아지지 않는다는 근거가 동시에 있다. 이것만으로 추가 1,000/3,000회 중 어느 길이가 충분한지는 계산할 수 없다.','',
'[발 기록] 아래 표도 CSV에서 생성했다. 끌림은 접촉 힘>1 N인 발 표본 중 수평 발 속도>0.15 m/s인 비율이며 모든 발걸림·미끄럼 사건을 세는 지표가 아니다. 완결 스윙 높이도 장애물 여유 높이와 다르다.','',
tab(['L5 전진 지형','지도','끝 생존 m11500→m12000','끌림 m12000','끌림 변화 %p'], [[labels[kind],mode,
    f"{x['alive_5500']}/{x['n']} → {x['alive_6000']}/{x['n']}",
    f"{100*float(f['drag_6000']):.2f}%", f"{100*(float(f['drag_6000'])-float(f['drag_5500'])):+.2f}"]
    for kind in labels for mode in modes
    for x in [next(x for x in comp if (x['level'],x['kind'],x['case'],x['mode'])==('5',kind,'stairs_fwd',mode))]
    for f in [next(f for f in feet if (f['level'],f['kind'],f['case'],f['mode'])==('5',kind,'stairs_fwd',mode))]]),'',
'[W18 상세 표와 그림](../20261106-ex41-stage-reports/RESULT-EX41-T0prime.md) · [R·거리·생존 원값](../20261106-ex41-stage-reports/data/w78_5500_6000_comparison.csv) · [발·정지 원값](../20261106-ex41-stage-reports/data/w78_5500_6000_feet_stop.csv).','',
'## 경계 추세: 낮은 레벨 유지와 L5 학습을 분리','',
'다음 오차는 map64 L0~2의 기존 명령 유지 칸이다. L5 전용 평가가 아니므로 앞 W78의 R과 합산하지 않는다. 단위 m/s, 각 칸은 생존 구간 절대오차의 64 env 중앙값이다[실측].','']
rr=[]
for mode in modes:
    for case in ['fwd1.0','back1.0','side+0.5','side-0.5']:
        row=[mode,case]
        for n in [3750,5000,5500,5750,6000]:
            x=next(x for x in cmd if int(x['iteration'])==n and x['mode']==mode and x['case']==case)
            row.append(f"{float(x['error']):.3f}")
        rr.append(row)
text += [tab(['지도','명령','m3750','m5000','m5500','m5750','m6000'],rr),'',
'm5000 뒤에도 명령별로 오르내렸으며, T0′ 동안 후진 오차가 줄어든 것과 L5 왼쪽 이동량이 줄어든 것은 양립한다. 경계 간 차이는 학습 변화와 측정 변동이 섞이므로 같은 저장본 반복 폭으로 사용하지 않는다.','',
tab(['학습 구간','갱신 수','lr 하한 횟수','KL probe>0.05 횟수','std 중앙','보상/step 중앙','TR loss 중앙','평균레벨 중앙'],[[f"{r['first']}~{r['last']}",r['n'],r['lr_at_1e5'],r['kl_gt_005'],f"{float(r['std_median']):.4f}",f"{float(r['reward_per_step_median']):.5f}",f"{float(r['tr_loss_median']):.5f}",f"{float(r['level_median']):.3f}"] for r in windows]),'',
'[실측·코드] lr 하한은 1e−5(ex41_critic_mirror.py:178~182). KL probe>0.05는 횟수를 보여주는 기록선이며 새 중단선이 아니다. 마지막 250회는 lr이 매 회 하한인 상태가 아니고 KL probe 초과도 없었다. 그러나 std·lr이 0이 아니라고 더 학습하면 반드시 좋아진다는 뜻은 아니다. 마지막 두 창의 보상/step은 늘고 TR loss는 조금 낮아졌지만, 보상과 지도 복원 손실은 각각 계단 완주와 지도 높이 오차(cm)를 직접 뜻하지 않는다. T0′의 실제 관측 길이는 500회뿐이다.','']
if dist:
    text += ['학습 지형의 주요 저장 회차 스냅샷이다. env 수는 당시 레벨에 있었던 수이고, 성공 에피소드 수나 그 레벨에서 보낸 전체 시간은 아니다. 학습 상한이 L5였으므로 L6 이상이 0인 것은 그 난도에서 실패했다는 뜻이 아니다.','']
    tr=[]
    for n in (4000,5000,5500,5750,6000):
        d=next(d for d in reversed(dist) if d['iteration']==n)
        for kind in ('pyramid_stairs','pyramid_stairs_inv'):
            v=d['by_terrain'][kind]
            tr.append([d['iteration'],labels[kind],v['env_count'],v['levels'][5],sum(v['levels'][6:]),d['source_line']])
    text += [tab(['기록 회차','지형','env 수','L5 수','L6 이상','stage_log 줄'],tr),'']
text += ['## 갈림길별로 무엇을 뒷받침하고 무엇을 증명하지 못하나','',
tab(['갈림길','뒷받침하는 관측','반대쪽 근거·비용','아직 없는 증거'],[
['준비 T0′ 1,000회, L5 조건 유지','현재 T0′ 500회에서 후진 유지 오차와 계단 전진 R이 변했다. 다음 4개 250경계로 방향을 더 관찰할 수 있다[산술].','왼쪽 계단 이동과 끌림은 반대 방향이었다. 추가 1,000회가 해결 길이라는 실측은 없다.','그 설정으로 추가 학습한 곡선·고정L5 반복평가·최종 명령/지도 유지표'],
['준비 T0′ 3,000회, 누적 m15000','현재 T0′의 6배 길이, 12개 250경계다[산술]. 회귀와 회복의 지속 여부를 더 오래 볼 관측 구간을 만든다.','1,000회보다 2,000갱신 더 쓴다. 보상 상승이 옆걸음·발 끌림 개선을 보장하지 않으며 특정 버릇을 더 학습할 수도 있다는 가설은 미검증이다.','1,000~3,000 구간에서 개선이 계속되는지·정체/회귀인지의 실제 경계 곡선'],
['연속 지형 cap을 L9까지 개방','L5 전진은 생존을 유지했고 평균 학습 레벨은 상한에 가까웠다. 명목 L상승이 실제로 더 큰 계단을 제공하는 것은 코드로 확인했다.','계단 중간 한 단은 0.149→0.221m로 증가한다. 현재 L5 옆·후진 이동비가 요구거리보다 작고 L6~9 고정 평가가 없다.','종류·레벨별 L6~9의 지도 셋·명령별 성적, 실제 노출분포, 기존기술 유지'],
['L5→L6→L7→L8→L9 단계 개방','동일 지형의 크기 증분과 그 시점 반응을 각각 관측할 수 있다. 한 단계 중간 단높이 차는 0.018m[계산].','경계를 나눠도 모든 단계 성공이 보장되지 않으며 체류·재도전 예산을 더 소모할 수 있다.','각 레벨의 필요한 실제 체류량·미달/회복 경로와 동일 저장본 반복 폭'],
['틈 또는 확장E를 함께 개방','생성기 치수와 목표 과제는 따로 정의돼 있다.','연속 지형 레벨 증가와 새로운 종류 노출이 섞인다. 기존 W78에는 틈 결과가 없다.','틈/확장E의 최초 성적과 기존 연속 L5 유지, 최종 메시치수 확인']]),'',
'위 표는 선택 자료이고 우선순위를 매기지 않는다. 특히 충분한 학습량·완주·일반화·원인에 대한 새 결론은 만들지 않았다.','',
'## 근거 위치와 재현','',
'- [치수 CSV](data/geometry.csv) · [학습 창 CSV](data/training_windows.csv) · [경계 명령 CSV](data/boundary_commands.csv) · [지형 스냅샷](data/terrain_snapshots.json) · [원본 경로·SHA](data/evidence.json).',
'- EX41 고정 rough_go2_cfg.py:18~34·40~43; Isaac mesh_terrains.py 원함수 AST 실행, terrain_generator.py:251~264; start_sheet.py:47·54~57·158~172; EX42 runner terrains/ex42.py:25~35·38~58. EX41/EX42 연속 preset 파일 SHA 동일 확인.',
'- W78 675·747 원자료 SHA 재확인. 경계 map64 원자료도 이전 감사 manifest의 SHA와 대조했다. 학습 CSV는 W45에서 TensorBoard 원문으로 추출·검증한 버전을 고정해 사용했다.',
'- [CPU 생성기](build_w44.py) → [표 생성기](write_w44_report.py) → [검증](verify_w44.py) 순서. isaac311 Python에서 실행, 원자료 위치는 evidence.json과 스크립트 상수에 고정했다. 운영 사본은 읽기만 한다.',
'- 새 GPU·Kit·학습·평가·운영 파일 변경 없음. CPU 치수 생성은 실기 통과 가능성이나 전체 EX42 메시의 Kit 검증을 대신하지 않는다.','']
(O/'EVIDENCE-W44-T0-L9-1107.md').write_text('\n'.join(text),encoding='utf-8')
ev=json.loads((D/'evidence.json').read_text(encoding='utf-8'));ev['raw_map_sources_rechecked']=checked;ev['terrain_snapshot_source']={'path':str(path),'sha256':sha(path),'rows':len(dist)}
ev['w78_reused_inputs']=[{'path':str(S/p),'sha256':sha(S/p)} for p in ('w78_5500_6000_protocol.json','w78_5500_6000_comparison.csv','w78_5500_6000_feet_stop.csv')]
dump(D/'evidence.json',ev)
print('report rows',len(text),'maps',len(checked))
