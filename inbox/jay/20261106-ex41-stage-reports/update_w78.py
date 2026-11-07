"""CPU-only W18 supplement. Read immutable W78 JSON/NPZ, update one stage section.

No simulator imports, no writes to operational sources. Unit-specific values and
case denominators are retained; this script creates no pass/fail thresholds.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
import math
from datetime import datetime
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parent
RUN = Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522')
MODES = ['eval_gt', 'eval_pred', 'probe_prop_only']
LABELS = ['GT 정답', 'Pred 복원', '지도 끔']
STAGES = {750:'S2a', 2750:'S2b', 3750:'S2c', 5000:'S2d', 5500:'S2e', 6000:'T0prime'}
CASE_LABELS = {'stairs_fwd':'계단 전진', 'stairs_side_left':'계단 왼쪽',
 'stairs_side_right':'계단 오른쪽', 'stairs_back':'계단 후진',
 'stairs_fwd_turn_return':'전진→회전→전진', 'stairs_fwd_back_return':'전진→후진',
 'stairs_fwd_stop_back':'전진→정지→후진→정지', 'slope_fwd1.0':'경사 전진 1.0',
 'flat_fwd1.0':'boxes/rough 전진 1.0', 'flat_fwd1.0_heading':'boxes/rough heading 전진'}
KIND_LABELS = {'pyramid_stairs':'정방향 계단', 'pyramid_stairs_inv':'역형 계단',
 'hf_pyramid_slope':'경사', 'hf_pyramid_slope_inv':'역형 경사',
 'random_rough':'rough', 'boxes':'boxes', 'stage_stairs':'stage 계단'}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def med(xs):
    values = [float(x) for x in xs if x is not None]
    return float(np.median(values)) if values else None

def f(x, digits=3):
    return '미측정' if x is None else f'{x:.{digits}f}'

def table(headers, rows):
    def cell(x): return str(x).replace('|', r'\|').replace('\n', ' ')
    return '\n'.join('| '+' | '.join(map(cell, row))+' |' for row in [headers, ['---']*len(headers), *rows])

def movement(vel, alive, command, dt):
    """Body-frame signed command projection / full scheduled commanded distance.

    A failed rollout retains the full planned-distance denominator. This is not
    world displacement, terrain completion, or an error in m/s.
    """
    xy = np.asarray(command[:2], dtype=np.float64)
    speed = float(np.linalg.norm(xy))
    if speed == 0: return None, None
    projection = (vel[:, 0].astype(np.float64)*xy[0]+vel[:, 1].astype(np.float64)*xy[1])/speed
    distance = float(np.sum(projection[alive], dtype=np.float64)*dt)
    return distance/(speed*len(alive)*dt), distance

def swing_heights(contact, z):
    """Peaks between two measured stance samples, relative to endpoint mean z."""
    values, opened = [], 0
    for foot in range(4):
        off = ~contact[:, foot]
        edges = np.diff(np.r_[False, off, False].astype(int))
        for start, end in zip(np.flatnonzero(edges==1), np.flatnonzero(edges==-1)):
            if start == 0 or end == len(off): opened += 1
            else:
                reference = (float(z[start-1, foot])+float(z[end, foot]))/2
                values.append(float(np.max(z[start:end, foot]))-reference)
    return values, opened

def symmetry(left, right):
    if left is None or right is None: return None
    if max(left, right) <= 0: return None
    return min(left, right)/max(left, right)

def known_answers():
    vel = np.tile([0.5, 0, 0], (4, 1))
    assert movement(vel, np.array([1,1,0,0], bool), [0.5,0,0], .02)[0] == .5
    assert movement(-vel, np.ones(4,bool), [-.5,0,0], .02)[0] == 1
    assert movement(vel, np.ones(4,bool), [0,0,1.2], .02) == (None,None)
    contact = np.ones((5,4),bool); contact[1:3,0]=False
    z = np.zeros((5,4)); z[1:3,0]=[.04,.08]
    assert swing_heights(contact,z) == ([.08],0)
    contact[0,1]=False
    assert swing_heights(contact,z) == ([.08],1)
    assert symmetry(.4,.8)==.5 and symmetry(-.4,.8)==-.5 and symmetry(0,0) is None
    assert med([0,0,1])==0
    return ['full scheduled denominator after death','signed backward projection',
            'spin excluded from translation ratio','closed vs open swing',
            'unclipped symmetry and nonpositive denominator','median is not mean']

def audit(n):
    checkpoint = RUN/f'main/EX-41-B-main_20261104_235522/model_{n}.pt'
    checkpoint_sha = sha(checkpoint)
    bundle = RUN/f'eval/score-watch/model_{n}_{checkpoint_sha[:12]}/stage_end_auxiliary_eval/w78_v2'
    result_path = bundle/'w78_v2/terrain_skill_v2.json'
    receipt_path = bundle/'eval_receipt.json'
    doc = json.loads(result_path.read_text(encoding='utf-8-sig'))
    receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
    assert doc['state']=='done' and receipt['state']=='done' and receipt['rc']==0
    assert doc['checkpoint_iter']==n and doc['checkpoint_sha256']==receipt['checkpoint_sha256']==checkpoint_sha
    assert doc['run_identity']['checkpoint_sha256']==checkpoint_sha
    assert doc['run_identity']['code_head']==receipt['source_git_head']
    code_root=Path(receipt['steps']['w78_v2']['cwd'])/'foothold_s2/eval'
    for name,digest in doc['source_sha256'].items():
        assert sha(code_root/name)==digest,('source changed',name)
    assert doc['envs']==64 and doc['eval_seed']==42 and doc['dt_s']==.02
    assert set(doc['modes'])==set(MODES) and doc['levels']==[2,5] and doc['start_angles_deg']==[0,30,60,90]
    assert len(doc['cases'])==10
    expected={(mode,level,angle,case) for mode,level,angle,case in
              itertools.product(MODES,doc['levels'],doc['start_angles_deg'],doc['cases'])}
    found=set(); checks=0; maximum_delta=0.; sources=[]; env_rows=[]; kinds=[]; assignments={}
    def eq(actual, declared, atol=2e-6):
        nonlocal checks, maximum_delta
        checks += 1
        if actual is None or declared is None: assert actual is declared; return
        delta=abs(float(actual)-float(declared));maximum_delta=max(maximum_delta,delta)
        assert delta<=atol,(actual,declared,delta)
    for mode, cells in doc['modes'].items():
        for key, cell in cells.items():
            level,angle,case=cell['level'],cell['stair_start_angle_deg'],cell['case']
            ident=(mode,level,angle,case)
            assert ident not in found; found.add(ident)
            assert key==f'L{level}_a{angle:03d}_{case}'
            raw_path=result_path.parent/cell['raw_file']; raw_sha=sha(raw_path)
            assert raw_sha==cell['raw_sha256']
            sources.append({'path':str(raw_path),'sha256':raw_sha,'mode':mode,'key':key})
            with np.load(raw_path,allow_pickle=False) as archive:
                data={k:archive[k] for k in archive.files}
            alive=data['alive']; dt=float(data['dt']);steps=list(map(int,data['phase_steps']))
            assert alive.shape==(sum(steps),64) and dt==doc['dt_s'] and steps==cell['phase_steps']
            assert not np.any(np.diff(alive.astype(int),axis=0)>0)
            assert np.array_equal(data['contact'],data['contact_force_n']>1)
            assert len(cell['terrain_tiles'])==len(cell['per_env'])==64
            if level not in assignments: assignments[level]=(cell['terrain_assignment_sha256'],cell['terrain_tiles'])
            assert assignments[level]==(cell['terrain_assignment_sha256'],cell['terrain_tiles'])
            phases=doc['cases'][case]['phases']; starts=np.r_[0,np.cumsum(steps)]
            current=[]
            for e,(tile,old) in enumerate(zip(cell['terrain_tiles'],cell['per_env'])):
                assert tile['env']==old['env']==e and tile['level']==old['level']==level
                assert tile['kind']==old['kind']
                eq(bool(alive[-1,e]),old['alive_at_end']); eq(int(alive[:,e].sum()),old['alive_samples'])
                ratios=[]; distances=[]
                for i,(command,seconds) in enumerate(phases):
                    sample=slice(starts[i],starts[i+1]); live=alive[sample,e]
                    ratio,dist=movement(data['body_vel_b'][sample,e],live,command,dt)
                    eq(ratio,old['movement_phases'][i]['movement_ratio'])
                    eq(dist,old['movement_phases'][i]['distance_projected_m'],atol=1e-5)
                    eq(int(live.sum()),old['movement_phases'][i]['alive_samples'])
                    ratios.append(ratio);distances.append(dist)
                count=int(alive[:,e].sum()); con=data['contact'][:count,e]
                speed=np.linalg.norm(data['foot_vel_xy_w'][:count,e],axis=-1)
                drag_num=int(np.sum(con & (speed>.15))); drag_den=int(con.sum())
                eq(drag_num,old['drag_num']);eq(drag_den,old['drag_den'])
                heights,opened=swing_heights(con,data['foot_pos_w'][:count,e,:,2])
                eq(len(heights),old['closed_swing_count']);eq(opened,old['open_swing_count'])
                for h,oh in zip(heights,old['swing_clearance_m']):eq(h,oh)
                row={'mode':mode,'level':level,'angle':angle,'case':case,'env':e,'kind':tile['kind'],
                     'focus':tile['kind'] in cell['requested_kinds'],'alive':int(alive[-1,e]),
                     'ratios':ratios,'distances_m':distances,'drag_num':drag_num,'drag_den':drag_den,
                     'heights':heights,'open_swings':opened,'stop_yaw_rad':None,'stop_abs_wz_rad':None,
                     'back_lateral_m':None}
                if case=='stairs_fwd_stop_back':
                    a,b,c,d=map(int,np.cumsum(steps));q=data['root_quat_w'][:,e].astype(float)
                    yaw=np.arctan2(2*(q[:,0]*q[:,3]+q[:,1]*q[:,2]),1-2*(q[:,2]**2+q[:,3]**2))
                    if alive[a-1,e] and alive[b-1,e]:
                        row['stop_yaw_rad']=float(np.arctan2(np.sin(yaw[b-1]-yaw[a-1]),np.cos(yaw[b-1]-yaw[a-1])))
                        row['stop_abs_wz_rad']=float(np.sum(np.abs(data['body_wz'][a:b,e][alive[a:b,e]]),dtype=float)*dt)
                        remaining=np.flatnonzero(alive[b:c,e])
                        if len(remaining):
                            delta=data['root_pos_w'][b+remaining[-1],e,:2].astype(float)-data['root_pos_w'][b-1,e,:2]
                            row['back_lateral_m']=float(-np.sin(yaw[b-1])*delta[0]+np.cos(yaw[b-1])*delta[1])
                    for ours,theirs in [('stop_yaw_rad','stop_yaw_drift_rad'),('stop_abs_wz_rad','stop_abs_wz_integral_rad'),('back_lateral_m','post_stop_back_lateral_m')]:
                        eq(row[ours],old[theirs],atol=1e-5)
                current.append(row);env_rows.append(row)
            for kind,old in cell['by_terrain_kind'].items():
                subset=[r for r in current if r['kind']==kind]
                ratio=[med(r['ratios'][i] for r in subset) for i in range(len(steps))]
                hs=[h for r in subset for h in r['heights']]
                row={'mode':mode,'level':level,'angle':angle,'case':case,'kind':kind,
                     'focus':kind in cell['requested_kinds'],'n':len(subset),'alive':sum(r['alive'] for r in subset),
                     'ratios':ratio,'drag_num':sum(r['drag_num'] for r in subset),
                     'drag_den':sum(r['drag_den'] for r in subset),'swing_p50_m':med(hs),
                     'closed_swings':len(hs),'open_swings':sum(r['open_swings'] for r in subset)}
                for ours,theirs in [('n','env_count'),('alive','alive_at_end'),('drag_num','drag_num'),('drag_den','drag_den'),('swing_p50_m','swing_clearance_p50_m'),('closed_swings','closed_swing_count'),('open_swings','open_swing_count')]:eq(row[ours],old[theirs])
                for actual,declared in zip(ratio,old['phase_movement_ratio_median']):eq(actual,declared)
                kinds.append(row)
    assert found==expected
    pairs=[]
    for mode,level,angle,kind in itertools.product(MODES,[2,5],[0,30,60,90],['pyramid_stairs','pyramid_stairs_inv']):
        def side(case):return next(r['ratios'][0] for r in kinds if (r['mode'],r['level'],r['angle'],r['kind'],r['case'])==(mode,level,angle,kind,case))
        left,right=side('stairs_side_left'),side('stairs_side_right')
        old=doc['w78_min_lr_ratio'][f'L{level}_a{angle:03d}_{mode}_{kind}']
        eq(left,old['left']);eq(right,old['right']);eq(min(left,right),old['min_lr_ratio'])
        pairs.append({'mode':mode,'level':level,'angle':angle,'kind':kind,'left':left,'right':right,'S':symmetry(left,right)})
    metadata={'captured_at':datetime.now().astimezone().isoformat(),'iteration':n,'cumulative_iteration':6000+n,
      'stage':STAGES[n],'checkpoint':str(checkpoint),'checkpoint_sha256':checkpoint_sha,
      'result':str(result_path),'result_sha256':sha(result_path),'receipt':str(receipt_path),'receipt_sha256':sha(receipt_path),
      'source_sha256':doc['source_sha256'],'run_identity':doc['run_identity'],'dr_off':doc['dr_off'],
      'curriculum_off':doc['curriculum_off'],'cases':doc['cases'],'seconds':receipt['seconds'],
      'combinations':len(found),'env_case_rows':len(env_rows),'kind_case_rows':len(kinds),
      'value_checks':checks,'max_float_delta':maximum_delta,'known_answers':known_answers(),
      'terrain_assignments':{str(level):{'sha256':v[0],'tiles':v[1]} for level,v in assignments.items()},
      'source_code_root':str(code_root),'npz_sources':sources,'symmetry':pairs}
    return metadata,env_rows,kinds

def csv_write(path, rows):
    def clean(x):return json.dumps(x,ensure_ascii=False) if isinstance(x,(list,dict)) else x
    with path.open('w',encoding='utf-8',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(rows[0]));writer.writeheader()
        writer.writerows({k:clean(v) for k,v in row.items()} for row in rows)

def figure(n,meta,kinds):
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':9})
    # lieflat-charts color-presets.js PORCELAIN.RAMP, ordinal quantities.
    cmap=LinearSegmentedColormap.from_list('porcelain',['#D0E3FF','#BAD6EB','#7096D1','#334EAC','#081F5C'])
    ordered=[(case,kind) for case,conf in meta['cases'].items() for kind in conf['focus_kinds']]
    for level in [2,5]:
        fig,axes=plt.subplots(1,3,figsize=(15,11),sharey=True,layout='constrained')
        for ax,mode,label in zip(axes,MODES,LABELS):
            matrix=np.array([[next(r['ratios'][0] for r in kinds if (r['mode'],r['level'],r['angle'],r['case'],r['kind'])==(mode,level,a,c,k)) for a in [0,30,60,90]] for c,k in ordered])
            im=ax.imshow(matrix,cmap=cmap,vmin=0,vmax=1.2,aspect='auto')
            for y in range(len(ordered)):
                for x in range(4):
                    rgb=np.asarray(cmap(np.clip(matrix[y,x]/1.2,0,1))[:3])
                    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
                    luminance=float(np.dot(linear,[.2126,.7152,.0722]))
                    white=1.05/(luminance+.05);black=(luminance+.05)/.05
                    assert max(white,black)>=4.5
                    ax.text(x,y,f'{matrix[y,x]:.2f}',ha='center',va='center',color='white' if white>black else 'black',fontsize=8)
            ax.set_xticks(range(4),['0°','30°','60°','90°']);ax.set_xlabel('시작 방향');ax.set_title(label)
            ax.set_yticks(range(len(ordered)),[CASE_LABELS[c]+' · '+KIND_LABELS[k] for c,k in ordered])
        fig.colorbar(im,ax=axes,label='첫 이동 구간 실제/명령 거리 비(무차원) · 성공률 아님',shrink=.7)
        fig.suptitle(f'EX-41 m{n} · W78 L{level} · 각 지형 env 중앙값')
        fig.savefig(ROOT/f'figs/W78-m{n}-L{level}.png',dpi=135);plt.close(fig)

def section(meta,rows,kinds):
    n=meta['iteration'];s=['## W78 v2와 남은 확인','',
      f"**v1.1 보충 · m{n}(누적 {meta['cumulative_iteration']}) 최종 W78 확인.** L2/L5 × 시작 방향 0/30/60/90° × 명령 10가지 × 지도 셋 = {meta['combinations']}조합이다. 조합당 64 env, 원시 NPZ 240개와 저장본 SHA를 대조했다. {meta['value_checks']:,}개 수치 대조의 최대 부동소수 차는 {meta['max_float_delta']:.2g}이며 비교 허용 오차 이내다. 이번 검사는 완료·수치의 검증이며 새 졸업 판정이 아니다.",'',
      '### 수치를 읽는 법','',
      '- 이동 비 R은 몸 기준 명령 방향 속도를 살아 있는 시간 동안 적분한 거리 ÷ 예정된 전체 명령 거리다. 무차원이며 m/s 오차나 세계 좌표의 목표 도착률이 아니다. 죽은 뒤 시간도 분모에 남고, 여러 이동 구간은 따로 표시한다. 회전·정지 구간을 이동 비로 채점하지 않는다.',
      '- 아래 표는 지정된 지형 두 종류와 시작 방향 네 가지의 env를 합친 중앙값이다. 같은 정책·같은 시드의 반복 환경 기록이며 독립 학습 반복시험의 표본 수가 아니다. 그림·CSV는 종류와 방향을 분리해 평균에 가려지는 차이를 남긴다.',
      '- flat이라는 case 이름은 실제 boxes·random_rough 열을 뜻한다. 순수 평지가 아니다. 계단 열은 pyramid_stairs·pyramid_stairs_inv, 경사는 hf_pyramid_slope·역형이다. 지형 배치와 레벨은 각 조합 원자료에 기록되어 있다.',
      '- 끌림은 접촉 힘 >1 N인 발 표본 중 수평 발 속도 >0.15 m/s 비율이다. 발걸림 횟수나 지면 상대 미끄럼을 전부 설명하지 않는다. 스윙 높이는 완결된 비접촉 구간의 최고 발 z에서 앞뒤 접지 z 평균을 뺀 값이다. 발 앞 장애물 여유 높이나 지형 관통 검사가 아니다.',
      '- dr_off는 원문에 열거된 physics_material·add_base_mass이다. 모든 외란·지연·관측 잡음이 꺼졌다고 확대 해석하지 않는다.','',
      '### 명령별 이동과 생존','',
      '칸 형식: 각 이동 구간 R(시간 순서) · 끝 생존/해당 지형 env 기록 수.','']
    summary=[]
    for level in [2,5]:
        for case,conf in meta['cases'].items():
            line=[f'L{level}',CASE_LABELS[case]]
            for mode in MODES:
                subset=[r for r in rows if r['level']==level and r['case']==case and r['mode']==mode and r['focus']]
                ratios=[med(r['ratios'][i] for r in subset) for i in range(len(conf['phases'])) if any(conf['phases'][i][0][:2])]
                line.append(' → '.join(f(x) for x in ratios)+f" · {sum(r['alive'] for r in subset)}/{len(subset)}")
            summary.append(line)
    s += [table(['레벨','과제',*LABELS],summary),'',f'![W78 L2](figs/W78-m{n}-L2.png)','',f'![W78 L5](figs/W78-m{n}-L5.png)','',
          '### 발과 정지 후 후진','', '각 행은 계단 과제 7종·두 계단 열·네 방향을 모은 기술 통계다. 정지→후진 세 지표는 stairs_fwd_stop_back만 따로 계산한다. 부호 상쇄를 막기 위해 절댓값 중앙값을 사용하고, rad와 m를 섞어 평균하지 않는다.','']
    feet=[]
    for level,mode in itertools.product([2,5],MODES):
        label=LABELS[MODES.index(mode)]
        subset=[r for r in rows if r['level']==level and r['mode']==mode and r['focus'] and r['case'].startswith('stairs_')]
        hs=[h for r in subset for h in r['heights']]
        stop=[r for r in subset if r['case']=='stairs_fwd_stop_back']
        drift=[abs(r['stop_yaw_rad'])*180/math.pi for r in stop if r['stop_yaw_rad'] is not None]
        total=[r['stop_abs_wz_rad']*180/math.pi for r in stop if r['stop_abs_wz_rad'] is not None]
        lateral=[abs(r['back_lateral_m']) for r in stop if r['back_lateral_m'] is not None]
        feet.append([f'L{level}',label,f(sum(r['drag_num'] for r in subset)/sum(r['drag_den'] for r in subset)),
          f(med(hs)),len(hs),f(med(drift),2),f(med(total),2),f(med(lateral)),f'{len(lateral)}/{len(stop)}'])
    s += [table(['레벨','지도','끌림 비율','스윙 p50 m','완결 스윙 수','정지 방향 변화°','정지 회전 누적°','후진 횡이탈 m','유효/전체'],feet),'',
          '### 좌우 대칭과 해석 범위','',
          '원자료 w78_min_lr_ratio는 min(왼쪽 이동 비, 오른쪽 이동 비)다. 대칭 S=min/max와는 다르므로 별도로 재계산했다. 음수·1 초과를 자르지 않았고, 분모 ≤0이면 계산 불가다. 아래 <0.8 수는 기존 P3 관찰선의 기술 통계이며 단계 승급·회복 판정으로 사용하지 않는다.','']
    pair_table=[]
    for level in [2,5]:
        for mode,label in zip(MODES,LABELS):
            pp=[r for r in meta['symmetry'] if r['level']==level and r['mode']==mode]
            valid=[r['S'] for r in pp if r['S'] is not None]
            pair_table.append([f'L{level}',label,f(med(valid)),f(min(valid)) if valid else '미측정',f'{sum(x<.8 for x in valid)}/{len(valid)}',len(pp)-len(valid)])
    s += [table(['레벨','지도','S 중앙값','S 최저','S<0.8/유효 쌍','계산 불가'],pair_table),'',
      '**합친 숫자를 그대로 믿으면 놓치는 차이.** L5 계단 전진의 이동 비를 두 계단 종류로 나누면 아래와 같다. 각 칸은 네 시작 방향에서 계산한 지형별 중앙값의 최솟값~최댓값이다. 지도 끔의 합친 중앙값이 높다는 이유만으로 두 종류에서 모두 우수하다고 해석할 수 없다.','',
      table(['L5 계단 전진 지형',*LABELS],[[KIND_LABELS[kind],*[f"{min(values):.3f}~{max(values):.3f}" for mode in MODES for values in [[r['ratios'][0] for r in kinds if r['level']==5 and r['case']=='stairs_fwd' and r['kind']==kind and r['mode']==mode]]]] for kind in ['pyramid_stairs','pyramid_stairs_inv']]),'',
      '**해석.** 이 저장본에서 각 과제의 수행 정도와 방향 차이를 확인했다. 다른 저장본과 같은 W78 프로토콜로 재측정하기 전에는 이 단계에서 얼마나 새로 배웠거나 잊었는지 분리할 수 없다. 생존이 높아도 요구 거리·회전·발 여유를 달성했다는 뜻이 아니고, 이동 비가 비슷해도 보행 모양이 같다는 뜻은 아니다. 영상 전체 1x 판독·지형별 성공선·반복 폭은 별도 확인 사항이다.', '',
      f"[원자료·해시·대조 영수증](data/w78_m{n}_audit.json) · [전체 지형별 수치](data/w78_m{n}_kinds.csv) · [env별 수치](data/w78_m{n}_env.csv) · [재계산기](update_w78.py). 원자료: `{meta['result']}`. 저장본 SHA256 `{meta['checkpoint_sha256']}`. 평가 코드 `{meta['run_identity']['code_head']}` · {meta['run_identity']['device']} · 시드 42 · 제어 간격 0.02 s. 채집 시각 `{meta['captured_at']}`.",'',
      '영상은 기존에 확인한 GT 표본 프레임 범위를 유지한다. 이번 보충은 새 렌더·GPU·학습·대기열·운영 원장 변경 없이 원자료를 CPU로 다시 계산했다. N1 모든 축 완료나 다음 단계 승인을 선언하지 않는다.','']
    return '\n'.join(s)

def apply_saved_section(text, n):
    saved=ROOT/f'data/w78_m{n}_section.txt'
    if not saved.exists():return text
    start=text.index('## W78 v2와 남은 확인')
    end=text.index('## 재현과 근거 등급',start)
    # W45 has additional material between these two headings; retain it.
    old=text[start:end]
    extra=old.find('\n## ',1)
    tail=old[extra:] if extra>=0 else ''
    text=text[:start]+saved.read_text(encoding='utf-8')+tail+text[end:]
    text=text.replace('· W78 v2 조각 결과 대기 ·','· W78 v2 최종 수치 대조 완료 ·')
    text=text.replace('정식 단계 보고 v1.0','정식 단계 보고 v1.1')
    text=text.replace('전체 영상 판독·W78 v2 완결 판정','전체 영상 판독·W78 v2 졸업 판정')
    return text

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--iteration',type=int,required=True,choices=STAGES);args=ap.parse_args()
    known_answers();meta,rows,kinds=audit(args.iteration)
    n=args.iteration
    csv_write(ROOT/f'data/w78_m{n}_env.csv',[{k:v for k,v in r.items() if k!='heights'} for r in rows])
    csv_write(ROOT/f'data/w78_m{n}_kinds.csv',kinds)
    dump(ROOT/f'data/w78_m{n}_audit.json',meta)
    figure(n,meta,kinds)
    snippet=section(meta,rows,kinds);assert '\u2014' not in snippet
    (ROOT/f'data/w78_m{n}_section.txt').write_text(snippet,encoding='utf-8')
    path=ROOT/f'RESULT-EX41-{STAGES[n]}.md'
    path.write_text(apply_saved_section(path.read_text(encoding='utf-8'),n),encoding='utf-8')
    print(json.dumps({k:meta[k] for k in ['iteration','combinations','env_case_rows','kind_case_rows','value_checks','max_float_delta']},ensure_ascii=False))

if __name__=='__main__':main()
