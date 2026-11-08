from pathlib import Path
import csv, hashlib, json, math, sys, subprocess
from datetime import datetime
from collections import Counter
import numpy as np
import yaml

OUT=Path('D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102/_out/reports')
DATA=OUT/'N21-1108'; DATA.mkdir(parents=True,exist_ok=True)
BASE=Path('D:/mai-tmp/runner/ex42_n21_w63_20261108')
CODE=Path('D:/mai-wt/foothold-lab/runner-ex42-v016')
USD=Path('D:/mai-tmp/analyst/jump-physics-1104')
sys.path.insert(0,str(USD/'usd_reader'))
from pxr import Sdf
MODES=['eval_gt','eval_pred','probe_prop_only']
LABEL={'eval_gt':'정답','eval_pred':'복원','probe_prop_only':'끔'}
CMDS=['fwd0.5','fwd1.0','spin+1.2','spin-1.2','back0.5','side+0.5','side-0.5','stop']
RUNS={'flat':{'on':'gpu0-flat-300','off':'gpu1-flat-300-off'},'continuous':{'on':'gpu0-continuous-300','off':'gpu0-continuous-300-off'}}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def errors(rows,cmd):
    if cmd=='stop':
        return np.array([[r['body_xy_speed_mean_alive_mps'],r['wz_abs_error_mean_alive_radps']] for r in rows])
    k=('wz_abs_error_mean_alive_radps' if cmd.startswith('spin') else 'vy_abs_error_mean_alive_mps' if cmd.startswith('side') else 'vx_abs_error_mean_alive_mps')
    return np.array([[r[k]] for r in rows])
def components(e,threshold,alive):
    reach=np.isfinite(e).all(1)&(e<=threshold).all(1)
    alive=np.array(alive,dtype=bool)
    return {'reached':int(reach.sum()),'alive':int(alive.sum()),'both':int((reach&alive).sum()),'reach_without_alive':int((reach&~alive).sum()),'alive_without_reach':int((~reach&alive).sum())}
def known():
    x=components(np.array([[.1],[.2],[.3],[.4]]),np.array([.25]),[True,False,True,False])
    assert x=={'reached':2,'alive':2,'both':1,'reach_without_alive':1,'alive_without_reach':1}
    assert components(np.array([[.01,.2],[.04,.04]]),np.array([.05,.1]),[True,True])['reached']==1
    assert components(np.array([[float('nan')],[.1]]),np.array([.2]),[True,True])['reached']==1
    assert np.allclose(np.median(np.array([[.1],[.2],[.3],[.4]]),axis=0),[.25])
    assert np.array([0.2,1.2]).min()>=.2 and np.array([0.2,1.2]).max()<=1.2
known()
layer=Sdf.Layer.FindOrOpen(str(USD/'go2.usd'))
nominal={}
def scan(path):
    obj=layer.GetObjectAtPath(path)
    if isinstance(obj,Sdf.AttributeSpec) and obj.name=='physics:mass':
        nominal[str(obj.owner.path).split('/')[-1]]=float(obj.default)
layer.Traverse('/',scan)
assert nominal['base']==6.921000003814697
assert sha(USD/'go2.usd')=='ba171c972b987d8c8fb7157ccad2ba9c0c1fed105755d2d8af46bef96cc11c6d'
docs={}; evidence=[]; checks=[]; physics={}; npz_count=0
for terrain, runs in RUNS.items():
    docs[terrain]={}
    for condition,run in runs.items():
        p=BASE/run/'n21_record_only.json';d=json.loads(p.read_text(encoding='utf-8'));docs[terrain][condition]=d
        evidence.append({'path':str(p),'sha256':sha(p),'code_head':d['run_identity']['code_head'],'gpu_uuid':d['run_identity']['gpu_uuid']})
        assert d['record_only'] and d['envs']==64 and d['steps']==300 and d['policy_dt_s']==.02
        assert set(d['modes'])==set(MODES) and set(d['commands'])==set(CMDS)
        assert all(t['level']==2 for t in d['terrain_tiles'])
        for mode in MODES:
            for cmd in CMDS:
                row=d['modes'][mode][cmd]; qpath=p.parent/d['env_arrays'][f'{mode}/{cmd}']
                q=np.load(qpath); npz_count+=1
                per=sorted(row['per_env'],key=lambda r:r['env'])
                assert [r['env'] for r in per]==list(range(64))
                assert q['vx'].shape==(300,64) and q['alive'].shape==(300,64)
                assert row['alive_envs_at_end']==int(q['alive_end'].sum())==sum(r['alive_at_end'] for r in per)
                assert np.array_equal(q['alive'].sum(0),[r['samples_alive'] for r in per])
                assert np.array_equal(q['alive'][-1],q['alive_end'])
                assert np.all(np.diff(q['alive'].astype(int),axis=0)<=0)
                assert np.allclose((q['vx']*q['alive']).sum(0)*float(q['dt']),q['body_vx_integral_m'],atol=1e-5)
                if cmd.startswith(('fwd','back')):
                    cx=d['commands'][cmd][0]
                    recal=np.sum(np.abs(q['vx']-cx)*q['alive'],axis=0)/np.maximum(q['alive'].sum(0),1)
                    assert np.allclose(recal,[r['vx_abs_error_mean_alive_mps'] for r in per],atol=2e-6)
                    sign=np.sign(cx)
                    assert np.allclose(q['body_vx_integral_m']*sign,[r['command_xy_projection_integral_m'] for r in per],atol=1e-5)
                evidence.append({'path':str(qpath),'sha256':sha(qpath)})
        if condition=='on':
            table_path=Path(d['dr']['table'])
            assert sha(table_path)==d['dr']['table_sha256']
            table=yaml.safe_load(table_path.read_text(encoding='utf-8'))
            preserved=table['domain_randomization']['preserved_startup']
            assert preserved['friction_static_dynamic']==[.2,1.2]
            assert preserved['base_mass_add_kg']==[-1.,3.]
            evidence.append({'path':str(table_path),'sha256':sha(table_path),'preserved_startup':preserved})
            b=d['dr']['readback']; assert len(b)==24
            v=next(iter(b.values()))['actual_values_by_env']; names=v['body_names']; idx=names.index('base')
            masses=np.array(v['mass_kg_by_env_body']); mats=np.array(v['material_coefficients_by_env_shape'])
            ref=np.array([nominal[n] for n in names]); delta=masses[:,idx]-ref[idx]
            assert masses.shape==(64,19) and mats.shape==(64,27,3)
            assert np.isfinite(masses).all() and np.isfinite(mats).all()
            assert np.allclose(np.delete(masses,idx,axis=1),np.delete(ref,idx),atol=1e-6)
            assert ((delta>=-1-1e-6)&(delta<=3+1e-6)).all()
            assert ((mats[:,:,:2]>=.2-1e-6)&(mats[:,:,:2]<=1.2+1e-6)).all()
            assert (mats[:,:,1]<=mats[:,:,0]+1e-6).all() and (mats[:,:,2]==0).all()
            assert all(np.array_equal(masses,np.array(x['actual_values_by_env']['mass_kg_by_env_body'])) and np.array_equal(mats,np.array(x['actual_values_by_env']['material_coefficients_by_env_shape'])) for x in b.values())
            physics[terrain]={'nominal_base_kg':ref[idx],'base_kg':[float(masses[:,idx].min()),float(masses[:,idx].max())],'mass_add_kg':[float(delta.min()),float(delta.max())],'total_kg':[float(masses.sum(1).min()),float(masses.sum(1).max())],'static':[float(mats[:,:,0].min()),float(mats[:,:,0].max())],'dynamic':[float(mats[:,:,1].min()),float(mats[:,:,1].max())],'restitution':[0,0],'unique_material_triplets':len(np.unique(mats.reshape(-1,3),axis=0)),'startup_unchanged_across_24_cells':True,'terrain_env_counts':dict(Counter(t['kind'] for t in d['terrain_tiles']))}
    a,b=docs[terrain]['on'],docs[terrain]['off']
    for k in ['checkpoint_sha256','eval_seed','envs','steps','policy_dt_s','commands','terrain_set','terrain_tiles','terrain_columns','fixed_terrain']:
        assert a[k]==b[k],(terrain,k)
    checks.append({'terrain':terrain,'same_assignment_and_protocol':True,'source_fingerprints_changed':[k for k,v in a['source_sha256'].items() if b['source_sha256'].get(k)!=v]})

rows=[]; kindrows=[]; perrows=[]; stopped=[]; failures=[]
for terrain, pair in docs.items():
 for mode in MODES:
  for cmd in CMDS:
    per={c:sorted(d['modes'][mode][cmd]['per_env'],key=lambda r:r['env']) for c,d in pair.items()}
    threshold=np.median(errors(per['off'],cmd),axis=0)
    r={'terrain':terrain,'mode':mode,'command':cmd,'baseline':threshold.tolist(),'unit':'m/s + rad/s' if cmd=='stop' else 'rad/s' if cmd.startswith('spin') else 'm/s'}
    for condition in ['off','on']:
        values=errors(per[condition],cmd); alive=[x['alive_at_end'] for x in per[condition]]
        r[condition]={**components(values,threshold,alive),'error_medians':np.median(values,axis=0).tolist()}
        if cmd!='stop':
            metric='yaw_follow_mean_alive' if cmd.startswith('spin') else 'command_xy_projection_integral_m'
            r[condition]['realized_median']=float(np.median([x[metric] for x in per[condition]]))
        for j,x in enumerate(per[condition]):
            perrows.append({'terrain':terrain,'mode':mode,'command':cmd,'condition':condition,**x,'baseline_reached':bool(np.isfinite(values[j]).all() and (values[j]<=threshold).all())})
            if not x['alive_at_end']:
                q=np.load(BASE/RUNS[terrain][condition]/pair[condition]['env_arrays'][f'{mode}/{cmd}'])
                failures.append({'terrain':terrain,'mode':mode,'command':cmd,'condition':condition,'env':x['env'],'kind':x['kind'],'first_done_step':int(q['first_done_step'][j]),'end_reason':str(q['end_reason'][j])})
        if cmd=='stop':
            case=pair[condition]['modes'][mode][cmd]
            q=np.load(BASE/RUNS[terrain][condition]/pair[condition]['env_arrays'][f'{mode}/{cmd}'])
            n=int(q['alive'][100:200].any(0).sum()); frac=case['stationary_fraction_2to4s']
            assert abs(frac*n-round(frac*n))<1e-8
            stopped.append({'terrain':terrain,'mode':mode,'condition':condition,'stationary':round(frac*n),'window_envs':n,'alive_end':case['alive_envs_at_end']})
    rows.append(r)
    if terrain=='continuous':
        for kind in sorted(set(x['kind'] for x in per['off'])):
            sub={c:[x for x in p if x['kind']==kind] for c,p in per.items()}
            kt=np.median(errors(sub['off'],cmd),axis=0)
            kr={'terrain':kind,'mode':mode,'command':cmd,'envs':len(sub['off']),'baseline':kt.tolist()}
            for c,p in sub.items(): kr[c]={**components(errors(p,cmd),kt,[x['alive_at_end'] for x in p]),'error_medians':np.median(errors(p,cmd),axis=0).tolist()}
            kindrows.append(kr)

def save_csv(path,records):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader()
        for row in records:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
save_csv(DATA/'cells.csv',rows);save_csv(DATA/'terrain_cells.csv',kindrows);save_csv(DATA/'env_rows.csv',perrows)
save_csv(DATA/'stop_window.csv',stopped)
summary={'physics':physics,'protocol_checks':checks,'cells':rows,'terrain_cells':kindrows,'stop_window':stopped,'failures':failures,'inputs':evidence,'npz_count_checked':npz_count,'known_answer_tests':5,'nominal_usd':{'path':str(USD/'go2.usd'),'sha256':sha(USD/'go2.usd'),'masses':nominal}}
summary['runtime_source_presence']={t:{c:pair[c]['source_sha256'].get('foothold_s2.curriculum.ex40_dr_runtime') for c in ['on','off']} for t,pair in docs.items()}
(DATA/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
def val(v): return '/'.join(f'{x:.3f}' for x in v)
def tab(headers, data):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in data])
lines=[
'> 분류: A/평가 · N21 기록 판독',
'> 작성: analyst · '+datetime.now().strftime('%Y-%m-%d %H:%M'),
'> 근거: W63 원자료 JSON 4개·NPZ 96개 · 고정 코드 d1dfd4f9/1771ee04 · 실행 USD·범위표',
'> 요지: 로봇 질량·마찰 기록은 범위 안이다. 생존과 추종은 다르며, DR-off 실물리값 기록은 비어 있다.',
'> 상태: record_only 해석 완료 · 승급·중단·성능 합격 판정 없음 · GPU/Kit 실행 없음',
'', '# N21 · DR 켬/끔 대표 명령 판독', '',
'## 1. 무엇을 확인했나', '',
'같은 부모 체크포인트 `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`의 로컬 model_6000, 누적 m12000이다. 평지와 연속 지형 각각 고정 L2, 지도 셋, 대표 8명령, 64 env, 300 step × 0.02 s = 6 s를 비교했다. 아래 숫자는 생성기가 읽은 실측·재계산이다. 설정값은 코드 근거, 해석용 참고선은 분석 정의로 구별한다.', '',
tab(['검사','확인 범위'],[
['원자료','각 조건 24셀·24 NPZ, 네 조건 합 96셀·96 NPZ. JSON 생존과 NPZ alive_end·alive 누적 일치'],
['평지 배치','flat 64 env. DR-on GPU0, off GPU1'],
['연속 7종 배치',str(physics['continuous']['terrain_env_counts'])],
['코드','on d1dfd4f9, off 1771ee04. 서로 다른 HEAD. 차이는 off selector·기록 허용 및 시험이고 공통 정책 체크포인트 동일'],
['유효 관측','전진·후진 x 오차와 거리·생존은 NPZ로 재계산. 횡/yaw 오차는 JSON per_env를 재집계. 현재 NPZ에는 vy/wz 원시 시계열이 없어 이 두 오차는 독립 원시 재계산 불가'],
['비교 한계','동일 seed·배치지만 동일 초기 상태/난수 궤적 보장 없음. DR 묶음에는 밀기도 포함']]),'',
'## 2. 질량·마찰은 합의 범위와 맞는가', '',
'**현재 기록된 로봇 강체 질량·충돌 형상 마찰은 범위 안이다.** 범위표 `domain_randomization.preserved_startup`은 정적·동적 마찰 0.2~1.2, 몸통 질량 가산 −1~+3 kg를 보존한다. 여기서 질량은 전체 로봇 질량이 −1~3 kg라는 뜻이 아니다. 몸통 기본값에 이 양을 더한다.', '',
tab(['항목','설정/자산 근거','실측 범위','대조'],[
['몸통 기본값','캐시된 실행 URL USD base.physics:mass','%.9f kg'%nominal['base'],'USD를 CPU로 다시 읽음'],
['몸통 질량','기본값 −1~+3 kg','%.6f~%.6f kg'%tuple(physics['flat']['base_kg']),'64/64 범위 안'],
['몸통 가산분','−1~+3 kg','%.6f~%.6f kg'%tuple(physics['flat']['mass_add_kg']),'64/64 범위 안'],
['전체 로봇 질량','19개 강체 합','%.6f~%.6f kg'%tuple(physics['flat']['total_kg']),'몸통 외 18개는 USD 값과 일치'],
['정적 마찰계수','0.2~1.2','%.6f~%.6f'%tuple(physics['flat']['static']),'64 env × 27 shape 모두 범위 안'],
['동적 마찰계수','0.2~1.2, make_consistent=True','%.6f~%.6f'%tuple(physics['flat']['dynamic']),'범위 안, dynamic > static 0건'],
['반발계수','0','0','마찰 배열의 세 번째 축. 0을 마찰 최솟값으로 잘못 집계하지 않음']]),'',
'[실측] 평지와 연속 지형의 시작 질량·재료 배열은 정확히 같으며, 각 실행의 24셀에서도 변하지 않는다. 무작위 표본이 24배 늘어난 것이 아니다. 재료는 64개 버킷을 27개 형상에 배정하며, 동적 마찰을 정적 마찰 이하로 자르므로 둘이 독립 균등분포인 것은 아니다. 모든 원소의 범위 포함과 실제 다양성은 확인했지만 분포 전체를 검증한 것은 아니다.', '',
'[한계] 읽은 것은 PhysX robot body/shape 값이다. 지면 재료 및 결합 뒤 유효 접촉 마찰을 직접 측정한 것은 아니다. USD 기준 질량은 실행 env.yaml과 같은 URL의 보관 자산이며 SHA를 확인했다. 해당 Kit가 가져온 USD 바이트 해시는 영수증에 없으므로 실행 로더 자산 동일성의 최종 고리는 미확인이다. 다만 몸통 외 18개 실측 질량은 이 USD와 일치한다.', '',
'[중요] DR-off에는 per-env 질량·마찰 readback이 없다. `runtime_events_fired=0`은 n21_dr_record.off_mode_record가 0으로 만드는 메타데이터이며 실제 계측 카운터가 아니다. 이벤트 비활성화 코드와 이 메타데이터를 PhysX 실값 검증이라고 바꿔 말하지 않는다.', '',
'## 3. 기준선 도달과 생존을 나눈 표', '',
'N21 합의에는 도달 합격선이 없다. **이 보고서의 “기준선 수준 도달”은 같은 지형·명령·지도 DR-off의 env별 추종 오차 중앙값 이하**라는 기술 통계다[분석 정의]. 새 관문이 아니며 0.15 같은 옛 합격선을 옮겨 붙이지 않았다. 전진·후진은 vx, 횡은 vy, 회전은 wz의 명령 대비 절대오차를 생존 중 평균한다. 정지는 몸 수평 속도와 yaw 절댓값 평균 두 성분이 각각 off 중앙값 이하여야 한다. 먼저 정의한 식을 모든 48쌍에 동일하게 적용했다.', '',
'표의 화살표는 **DR-off → DR-on**이다. 도달·생존·둘다는 각각 분모 64. 도달만 세면 중간에 종료된 env의 짧은 관측도 들어가므로 “둘다”와 별도로 읽는다. off 도달이 보통 32인 것은 중앙값을 참고선으로 썼기 때문이며 성공률 50%라는 뜻이 아니다. 정지의 두 성분은 AND이므로 off에서도 32보다 적을 수 있다. 연속 7종 표는 실제 배치에 따른 가중 혼합이지 종류별 균등 평균이 아니다.', '',
]
def cell(t,m,c): return next(r for r in rows if r['terrain']==t and r['mode']==m and r['command']==c)
summary_lines=['## 먼저 읽을 해석','',
'- 질량·마찰 실제 배열은 승인 범위에 들어간다. DR-off 물리 readback이 없어서 실제 nominal 물성까지 검증된 대조는 아니다.',
'- 평지에서 끝까지 생존한 수는 모든 지도·명령·DR 조건에서 64/64다. 하지만 전진 1.0과 횡 이동의 추종 오차는 켬에서 커졌다. 생존만 보면 이 차이가 가려진다.',
'- 연속 지형 전진 1.0의 생존은 오히려 켬에서 높다. 아래 표처럼 생존과 추종 오차가 반대 방향으로 움직이므로 한 가지 성공률로 합치지 않는다. 작은 표본의 관측 차이이며 DR의 개선 효과가 입증된 것은 아니다.','',
tab(['지도','연속 fwd1.0 생존 off→on','vx 오차 off→on(m/s)'],[
[LABEL[m],f"{cell('continuous',m,'fwd1.0')['off']['alive']}/64 → {cell('continuous',m,'fwd1.0')['on']['alive']}/64",val(cell('continuous',m,'fwd1.0')['off']['error_medians'])+' → '+val(cell('continuous',m,'fwd1.0')['on']['error_medians'])] for m in MODES]),'',
'- 회전−1.2 오차 중앙값은 세 모드·두 지형에서 거의 같은 수준의 관측값이다. 회전+1.2는 켬에서 소폭 커졌다. 재측정 폭이 없으므로 작은 차이를 개선/악화 확정으로 쓰지 않는다.',
'- 정지 2~4초 조건은 끔 64/64에서 켬 2~3/64로 줄지만, 전원 생존이다. 정확히 창 시작에 밀기를 넣었으므로 “서 있지 못하고 넘어진다”가 아니라 “외란 직후 움직임이 남는다”는 관측이다. 장기 회복·발 접촉은 별도다.',
f"- 관측된 최초 종료 {len(failures)}건 중 {sum(x['kind']=='pyramid_stairs_inv' for x in failures)}건은 역형 계단, {sum(x['kind']=='stage_stairs' for x in failures)}건은 stage_stairs다. 모두 원자료 end_reason=terminated이며 구체 종료 항은 미보존이다. 넘어짐·걸림 원인까지 확정하지 않는다. 실패 env와 최초 tick은 audit.json에 보존했다.",'',
'지도 셋의 우열은 이 표만으로 정하지 않는다. 이 비교는 한 정책에서 입력을 바꿔 평가한 것이며, 지도 유무별 독립 학습 실험이 아니다. 세 모드 모두 비슷한 방향으로 나타난 전진·횡·정지 차이와, 특정 모드의 드문 종료를 나눠 읽는다.','']
insert_at=lines.index('## 1. 무엇을 확인했나')
lines[insert_at:insert_at]=summary_lines
for terrain,title in [('flat','평지'),('continuous','연속 7종 혼합')]:
    lines+=['### '+title,'',tab(['지도·명령','기준 오차','오차 중앙값 off→on','기준선 도달','끝까지 생존','둘다'],[
        [LABEL[r['mode']]+' · '+r['command'],val(r['baseline'])+' '+r['unit'],val(r['off']['error_medians'])+' → '+val(r['on']['error_medians']),f"{r['off']['reached']} → {r['on']['reached']}",f"{r['off']['alive']} → {r['on']['alive']}",f"{r['off']['both']} → {r['on']['both']}"] for r in rows if r['terrain']==terrain]),'']
lines+=['## 4. 이동량·회전량과 정지 성분','',
'거리의 부호를 바로 읽는다. 후진·횡 이동은 몸 x 적분이 아니라 **명령 방향으로 투영한 거리**를 쓴다. 이 값은 몸 좌표계 속도 적분이어서 고정 세계 좌표의 목표점 도달 거리와 다르다. 명령대로 6초 이동하면 0.5 m/s는 3 m, 1.0 m/s는 6 m다. 회전은 평균 실제 yaw / 명령 yaw의 비이며 1이 명령과 같다. 정지 두 열은 m/s와 rad/s로 단위가 다르다. 오차 표도 함께 보아 과속·반대방향을 좋은 결과로 세지 않는다.','',
tab(['지형·지도','전진0.5 m','전진1.0 m','회전+ 비','회전− 비','후진0.5 m','횡+0.5 m','횡−0.5 m'],[
 [t+' · '+LABEL[m]]+[f"{r['off']['realized_median']:.3f} → {r['on']['realized_median']:.3f}" for c in CMDS[:-1] for r in rows if r['terrain']==t and r['mode']==m and r['command']==c]
 for t in RUNS for m in MODES]),'',
'정지의 기존 2~4초 요약은 평균 수평 속도 <0.05 m/s와 평균 yaw 절댓값 <0.1 rad/s를 동시에 센다[기존 코드]. DR-on의 2초 밀기와 창 시작이 겹친다. 따라서 아래 차이는 무외란 정지 능력만이 아니라 외란 직후의 이동·회복도 포함한다. 네 발 지지나 장시간 정지 성공의 대용이 아니다.','',
tab(['지형·지도','2~4초 정지 조건 인원 off→on','생존 off→on'],[
 [t+' · '+LABEL[m],f"{a['stationary']}/{a['window_envs']} → {b['stationary']}/{b['window_envs']}",f"{a['alive_end']}/64 → {b['alive_end']}/64"]
 for t in RUNS for m in MODES
 for a in stopped if a['terrain']==t and a['mode']==m and a['condition']=='off'
 for b in stopped if b['terrain']==t and b['mode']==m and b['condition']=='on']),'',
'## 5. 표본으로 말할 수 있는 것과 없는 것','',
'- [실측] 이 저장본·seed42·L2·6초 창의 관측된 종료, 명령 추종, DR 물성 분포를 말할 수 있다. 평지 24셀은 on/off 모두 64/64 생존이다. 이것을 정상 trot·관절 안전·정지 성공으로 바꾸지 않는다.',
'- [실측] 연속 지형의 전체 64는 계단15+15·boxes12·rough12·경사4+4·stage_stairs2다. 1 env 차이는 전체에서 1.5625%p지만, stage_stairs에서는 50%p다. 종류별 결론은 이 분모를 드러내야 한다. 종류·모드·명령 168쌍은 terrain_cells.csv에 분리했다.',
'- [한계] 300 step은 한 env의 연속 관측 6초이지 독립 실험 300개가 아니다. 같은 정책·난수 시드·공유 지형과 재료 버킷, 재사용 질량 때문에 64 env와 24셀을 독립 시드 반복으로 합치지 않는다. 유의성·일반화 확률·훈련 개선의 인과 효과는 산출하지 않았다.',
'- [한계] on/off는 전체 DR 묶음 비교다. 마찰·질량·COM·이득·세기·지연·밀기 중 무엇이 차이를 만들었는지 분리하지 못한다. 2초 밀기, 초기 상태·난수 소비, 평지 GPU 차이, 코드 HEAD 차이도 남는다. 같은 시드와 같은 지형 배치는 같은 궤적을 보장하지 않는다.',
'- [한계] 명령은 각각 고정된 6초다. 전진→정지→후진, 회전 반전, 빠른 후진·대각, L5/L9·듬성 지형·장시간 누적 실패·실기 성능은 이 묶음에서 측정하지 않았다.',
'- [한계] 부분 생존 동안의 평균 오차는 일찍 종료된 env에서 작아질 수도 있다. 생존과 도달 교집합을 반드시 같이 보며, 관문이나 자동 설정 변경에 연결하지 않는다.',
'- [한계] 영상·접촉 위상·발 미끄럼을 이번 판독에서 새로 확인하지 않았다. 보행이 예쁘다거나 특정 발이 끌린다는 결론을 숫자만으로 붙이지 않는다.','',
'## 6. 근거와 재현','',
tab(['근거','위치'],[
['합의','D:/mai-wt/foothold-lab/lead-worklist-1103/inbox/jay/20261104-ex41-restart/decisions.tsv:297'],
['범위표','runner-ex42-v016/foothold_s2/curriculum/ex41-fixed5000.yaml:42 · preserved_startup'],
['실행 env 설정','C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/main/EX-41-B-main_20261104_235522/params/env.yaml:1631 · :1672'],
['평가 task 상속','sb_tasks.py:10 → tasks/s2_sb_cfg.py:9 → s2_23f_b_cfg.py:13~20 · s2_x23_cfg.py:25~26'],
['PhysX 읽기','runner-ex42-v016/foothold_s2/curriculum/ex40_dr_runtime.py:403~413'],
['마찰 일관화','C:/isaac/isaaclab/source/isaaclab/isaaclab/envs/mdp/events.py:235~241'],
['질량 기본값에서 가산','같은 events.py:371~380'],
['관측·오차 식','runner-ex42-v016/foothold_s2/eval/map_mode_cells.py:129~203'],
['생존·2~4초 정지','runner-ex42-v016/foothold_s2/eval/eval_map_modes.py:500~558'],
['off 0 카운터 생성','runner-ex42-v016/foothold_s2/eval/n21_dr_record.py:142~152'],
['원자료 SHA·세부표','N21-1108/audit.json · cells.csv · terrain_cells.csv · env_rows.csv · stop_window.csv'],
['생성기','D:/mai-tmp/analyst/n21-1108/analyze.py']]),'',
'답을 아는 입력 5건을 먼저 확인했다. 기준 도달과 생존의 교집합이 각각의 수와 다르는 반례, 정지 두 단위 AND, NaN 제외, 짝수 표본 중앙값, 마찰 범위 경계를 확인했다. 이후 NPZ 96개로 생존과 x축 기록을 대조했다. 횡·yaw 원시 시계열 미보존 한계는 위에 표시했다.','',
'소스 목록에서 ex40_dr_runtime은 on에 있고 off에는 키 자체가 없다(off가 해당 모듈을 로드하지 않음). 서로 다른 runtime 파일이 실행됐다는 증거가 아니다. 두 HEAD의 해당 파일 diff도 없다. 실제 변경된 평가기·record 모듈과 누락된 import를 구별한다.','',
]
for item in evidence[:1]: pass
lines+=['### 입력 영수증 SHA','',tab(['조건','SHA256'],[(run,next(e['sha256'] for e in evidence if e['path']==str(BASE/run/'n21_record_only.json'))) for runs in RUNS.values() for run in runs.values()]),'']
(OUT/'REPORT-analyst-N21-1108.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'report':str(OUT/'REPORT-analyst-N21-1108.md'),'physics':physics,'cells':len(rows),'per_env_rows':len(perrows),'npz_checks':npz_count,'failures':failures,'stop_window':stopped},ensure_ascii=False))
