"""W10 independent CPU readback. Writes only beside this script, never live data."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import csv
import hashlib
import json
import math
import re
import statistics as st
import subprocess

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
PREVIOUS = HERE.parent / '20261106-ex41-stage-reports/data'
RUN = Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522')
TARGET = '3a97fae8'
DOC = 'inbox/jay/20261104-ex41-restart/EX41-ANALYSIS.md'
STAGES = [('S2a',750),('S2b',2750),('S2c',3750),('S2d',5000),('S2e',5500),('T0′',6000)]
MODES = ['eval_gt','eval_pred','probe_prop_only']
KEYS = {'vx':'vx_abs_error_mean_alive_mps','vy':'vy_abs_error_mean_alive_mps',
        'wz':'wz_abs_error_mean_alive_radps'}
SOURCES = {}

def load(p):
    p = Path(p)
    b = p.read_bytes()
    SOURCES[str(p)] = {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
    return json.loads(b)

def axis(case):
    return 'wz' if case.startswith('spin') else 'vy' if case.startswith('side') else 'vx'

def sym(a,b):
    return min(a,b)/max(a,b) if max(a,b)>0 else None

def med_error(cell,key):
    vals = [e[key] for e in cell['per_env']]
    assert vals and all(math.isfinite(v) for v in vals)
    return st.median(vals)

def celltext(x):
    return str(x).replace('|',r'\|').replace('\n',' ')

def table(head,rows):
    return '\n'.join('| '+' | '.join(celltext(v) for v in row)+' |' for row in [head,['---']*len(head),*rows])

def pairs_from_raw(score,doc,mode):
    out=[]
    for name,row in score['metrics']['critic_mirror_symmetry']['modes'][mode].items():
        lr=[]
        if name.startswith('map64/'):
            for case in row['source_cases']:
                c=doc['modes'][mode][case]
                speed=math.hypot(*c['command'][:2])
                values=[e['yaw_follow_mean_alive']*e['samples_alive']/doc['steps']
                        if name=='map64/spin' else
                        e['command_xy_projection_integral_m']/(speed*doc['steps']*doc['policy_dt_s'])
                        for e in c['per_env']]
                lr.append(st.median(values))
        else:
            m=re.fullmatch(r'w78/L(\d+)_a(\d+)_(.+)',name)
            assert m,name
            level,angle,kind=m.groups()
            cells=score['metrics']['w78_v2_periodic_sides']['cells'][mode]
            for side in ['left','right']:
                per=cells[f'L{level}_a{angle}_stairs_side_{side}']['per_env']
                per=[e for e in per if e['kind']==kind]
                lr.append(st.median(e['movement_phases'][0]['distance_projected_m']/
                                    e['movement_phases'][0]['planned_distance_m'] for e in per))
        s=sym(*lr)
        assert s is not None and all(math.isfinite(x) for x in [*lr,s])
        assert abs(lr[0]-row['left'])<1e-10 and abs(lr[1]-row['right'])<1e-10
        assert abs(s-row['symmetry'])<1e-10
        out.append({'pair':name,'left':lr[0],'right':lr[1],'S':s})
    assert len(out)==20
    return out

def main():
    # Known answers: median differs from mean; sign survives extreme selection;
    # angular unit conversion changes the mixed mean; rounded bounds do not hold raw.
    assert med_error({'per_env':[{'x':1},{'x':2},{'x':90}]},'x')==2
    assert axis('diag-back+side-')=='vx' and axis('side-0.5')=='vy' and axis('spin-1.2')=='wz'
    assert math.isclose(sym(.6,.8),.75) and sym(0,0) is None
    assert st.mean([.01,.02])!=st.mean([.01,math.degrees(.02)])
    assert abs(-.0023417371826676223)>.002 and f'{-.0023417371826676223:+.3f}'=='-0.002'
    DATA.mkdir(exist_ok=True)
    target=subprocess.run(['git','show',f'{TARGET}:{DOC}'],cwd=HERE,capture_output=True,check=True).stdout
    text=target.decode('utf-8');(DATA/'W10-3a97fae8.txt').write_bytes(target)
    declared={}
    for ln,line in enumerate(text.splitlines(),1):
        if line.startswith('| ') and any(line.startswith('| '+s+' |') for s,_ in STAGES):
            cells=[x.strip() for x in line.strip('|').split('|')]
            declared[cells[0]]={'line':ln,'cells':cells}
    assert len(declared)==6
    prior=list(csv.DictReader((PREVIOUS/'command_cells.csv').open(encoding='utf-8-sig')))
    result={'captured_at':datetime.now().astimezone().isoformat(),'target_commit':TARGET,
            'target_doc':DOC,'target_sha256':hashlib.sha256(target).hexdigest(),
            'known_answers':5,'stage_rows':[],'field_checks':[],'command_cells':[],
            'symmetry_pairs':[],'w78':[]}
    for stage,n in STAGES:
        src=next(r['source'] for r in prior if int(r['iteration'])==n)
        doc=load(src)
        scores=list((RUN/'eval/scores').glob(f'score_{n}_*.json'));assert len(scores)==1
        score=load(scores[0])
        ev=next(e for e in score['evidence'] if Path(e['path'])==Path(src))
        assert ev['sha256']==SOURCES[str(Path(src))]['sha256']
        assert score['checkpoint_sha256']==doc['checkpoint_sha256']
        measured={};survival={};over={};allpairs={}
        for mode in MODES:
            measured[mode]={};survival[mode]=[]
            for case,c in doc['modes'][mode].items():
                per=c['per_env'];assert len(per)==64
                errors={a:med_error(c,key) for a,key in KEYS.items()}
                p=next(r for r in prior if int(r['iteration'])==n and r['mode']==mode and r['case']==case)
                assert all(abs(errors[a]-float(p[a]))<1e-12 for a in KEYS)
                e=errors[axis(case)];alive=sum(x['alive_at_end'] for x in per)
                measured[mode][case]=e;survival[mode].append(alive)
                result['command_cells'].append({'stage':stage,'iteration':n,'mode':mode,'case':case,
                    'axis':axis(case),'unit':'rad/s' if axis(case)=='wz' else 'm/s',
                    'error':e,'alive':alive,'source':src,'pointer':f'/modes/{mode}/{case}/per_env'})
            assert len(measured[mode])==13
            over[mode]=sum(e>.15 for e in measured[mode].values())
            allpairs[mode]=pairs_from_raw(score,doc,mode)
            for p in allpairs[mode]:result['symmetry_pairs'].append({'stage':stage,'iteration':n,'mode':mode,**p})
        diffs={}
        for mode in MODES[1:]:
            delta={c:e-measured['eval_gt'][c] for c,e in measured[mode].items()}
            extreme=max(delta,key=lambda c:abs(delta[c]))
            lin=[v for c,v in delta.items() if axis(c)!='wz'];ang=[v for c,v in delta.items() if axis(c)=='wz']
            diffs[mode]={'mixed_mean':st.mean(delta.values()),'linear11_mean_mps':st.mean(lin),
                         'angular2_mean_radps':st.mean(ang),'extreme_case':extreme,'extreme':delta[extreme],
                         'delta_by_case':delta}
        ss=[p['S'] for p in allpairs['eval_gt']]
        summary={'mean':st.mean(ss),'min':min(ss),'below_08':sum(x<.8 for x in ss)}
        pred,off=[diffs[m] for m in MODES[1:]]
        display=[f'm{6000+n}',f"{pred['mixed_mean']:+.3f} · {pred['extreme_case']} {pred['extreme']:+.3f}",
                 f"{off['mixed_mean']:+.3f} · {off['extreme_case']} {off['extreme']:+.3f}",
                 ' · '.join(str(over[m]) for m in MODES),
                 ' · '.join(str(min(survival[m])) for m in MODES),
                 f"{summary['mean']:.3f} · {summary['min']:.3f} · {summary['below_08']}"]
        for label,old,new in zip(['누적 회차','복원-정답','끔-정답','0.15 초과 수','생존 최저','GT 대칭'],declared[stage]['cells'][1:],display):
            result['field_checks'].append({'stage':stage,'line':declared[stage]['line'],'field':label,'published':old,'recomputed':new,'equal':old==new})
        terrain=doc['modes']['eval_gt']['fwd1.0']['per_env']
        result['stage_rows'].append({'stage':stage,'iteration':n,'delta':diffs,'symmetry_gt':summary,
            'over_015':over,'min_alive':{m:min(survival[m]) for m in MODES},
            'terrain_counts':dict(Counter(e['kind'] for e in terrain)),
            'levels':dict(Counter(e['level'] for e in terrain)),
            'assignment_sha256':doc['fixed_terrain']['assignment_sha256'],
            'source':src,'score':str(scores[0]),'map_input':doc['map_input'],
            'envs':doc['envs'],'steps':doc['steps'],'seed':doc['eval_seed']})
    queue=json.loads(Path('D:/mai-tmp/gpu/queue.json').read_bytes())
    for ident in [555,747]:
        q=next(x for x in queue['items'] if x['id']==ident)
        folder=Path(q['argv'][q['argv'].index('--out')+1])
        files=[{'path':str(p),'bytes':p.stat().st_size} for p in folder.rglob('*.json')]
        complete=[p for p in folder.rglob('terrain_skill_v2.json')]
        result['w78'].append({'id':ident,'state':q['state'],'title':q['title'],'folder':str(folder),
                              'json_files':files,'complete_result_present':bool(complete),
                              'status':'검증할 새 결과 있음' if complete else '대기 · 최종 결과 없음'})
    result['sources']=list(SOURCES.values())
    assert len({x['assignment_sha256'] for x in result['stage_rows']})==1
    assert all(x['terrain_counts']==result['stage_rows'][0]['terrain_counts'] for x in result['stage_rows'])
    assert all(x['levels']==result['stage_rows'][0]['levels'] for x in result['stage_rows'])
    result['interpretation_lines']={name:next(i for i,line in enumerate(text.splitlines(),1) if pattern in line)
                                   for name,pattern in [('definition','아래 「오차 차」'),
                                                        ('bound','여섯 단계 모두 복원'),
                                                        ('off','지도 끔이 정답보다'),
                                                        ('terrain','`미확인` 지형에서')]}
    result['same_count']=sum(r['equal'] for r in result['field_checks'])
    result['different_count']=sum(not r['equal'] for r in result['field_checks'])
    assert len(result['command_cells'])==234 and len(result['symmetry_pairs'])==360
    (DATA/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    write_report(result)
    print(json.dumps({'same':result['same_count'],'different':result['different_count'],
                      'raw_cells':len(result['command_cells']),'raw_symmetry_pairs':len(result['symmetry_pairs']),
                      'w78':result['w78']},ensure_ascii=False))

def write_report(r):
    rows=r['stage_rows'];e=next(x for x in rows if x['stage']=='S2e')
    regress=rows[-1]['delta']['probe_prop_only']['delta_by_case']['back1.0']
    source=rows[-1]['source'];base=f'https://github.com/foothold-project/foothold-lab/blob/{TARGET}/{DOC}'
    lines=['> 분류: A/평가 · 독립 수치 검토',f'> 작성: analyst · {r["captured_at"]}',
           '> 근거: W10 3a97fae8 §1 · 단계 끝 map64 원자료 234칸 · 좌우 대칭 원행 360쌍',
           '> 요지: 표 36칸 표시값은 같음. 단위 혼합 평균·±0.002 단정·평지 및 보행 동일 해석은 고쳐야 함.',
           '> 상태: W10 검토 완료 · 문서 해석 고침 3 · W18 전체 W78 대기', '',
           '# W10 지도 셋 표 독립 대조', '',
           f'대상은 [EX41-ANALYSIS.md]({base}) {TARGET} 고정판이다. 학습·GPU·대기열·다른 세션 원문은 수정하지 않았다. 표에서 같음은 인쇄된 소수 셋째 자리 값의 일치이며 해석의 타당성이나 통계적 동등성을 뜻하지 않는다.', '',
           '## 판정', '',
           table(['항목','결과','필요한 고침'],[
               ['표 계산',f'{r["same_count"]}/36 같음 · 다름 {r["different_count"]}','표시값 자체는 유지 가능. 아래 단위 분리표로 고치는 것을 권고'],
               ['고침 1 · 단위', 'm/s 11칸과 rad/s 2칸을 평균','단일 m/s 수치로 설명하지 말고 선속도·각속도를 분리'],
               ['고침 2 · 경계 단정',f'S2e 혼합 평균 {e["delta"]["eval_pred"]["mixed_mean"]:+.9f}', '반올림 -0.002를 근거로 실제 값도 ±0.002 안이라 하면 틀림'],
               ['고침 3 · 과제/보행 해석','map64 연속 지형 7종 L0~2, 순수 평지 아님','평지·W57 명칭 정정. 오차 평균이 작아도 걷는 모양 동일·지도가 불필요함은 미확인'],
               ['W18','m3750 부분 파일 · m6000 최종 결과 없음','기존 보고서 W78 대기 유지. 완결 결과가 오면 그 칸만 갱신']]), '',
           '여기서 고침 3건은 보고서 해석의 정정 요구다. 학습 중단이나 실행 관문 실패를 새로 선언한 것이 아니다.', '',
           '## 원자료와 집계 방법', '',
           'W45의 975칸은 map64 25개 저장본(부모 포함) × 지도 3모드 × 13명령이다. W10은 이 중 단계 끝 여섯 저장본의 234칸을 사용한다. 각 JSON의 per_env 오차를 다시 읽어 env별 alive 구간 평균 절대오차의 64 env 중앙값을 계산했다. W45 CSV는 경로 탐색과 재대조용이며 숫자를 복사해 판정하지 않았다.', '',
           '회전은 wz(rad/s), 순수 옆걸음은 vy(m/s), 나머지는 vx(m/s)를 택했다. 대각 vy와 정지 wz가 이 주축 요약에서 빠지는 점을 명시한다. 0.15 초과 개수는 기존 표의 집계 재현이며 새로운 보행 합격선이 아니다. 가장 큰 칸은 절댓값 최대의 차이이며 부호는 보존했다.', '',
           'S는 실제/계획 이동 비의 좌우 min/max다. map64 4쌍은 per_env 이동량·살아 있는 시간에서, 정기 W78 16쌍은 per_env movement_phases 거리에서 재계산했다. 단계 끝 W78 전체 240조합을 뜻하지 않는다. 각 모드의 퇴행·생존·위상은 이미 [단계 보고](../20261106-ex41-stage-reports/README.md)에 분리되어 있다.', '',
           '## 표의 모든 칸 대조', '',
           table(['단계','원문 행','칸','원문','원자료 재계산 표시값','판정'],[
               [x['stage'],x['line'],x['field'],x['published'],x['recomputed'],'같음' if x['equal'] else '다름'] for x in r['field_checks']]), '',
           '## 같은 단위끼리 나눈 수정안', '',
           '아래도 13명령 중 선택한 주축만의 기술 통계다. 선속도 11칸과 각속도 2칸을 분리하며, 같은 저장본 반복 측정의 잡음 폭을 재지 않았으므로 우열의 통계 검정이나 동등성 검정으로 부르지 않는다.', '',
           table(['단계','복원-GT 선속도 11칸 m/s','복원-GT 회전 2칸 rad/s','끔-GT 선속도 11칸 m/s','끔-GT 회전 2칸 rad/s'],[
               [x['stage'],*[f'{x["delta"][m][k]:+.6f}' for m in MODES[1:] for k in ['linear11_mean_mps','angular2_mean_radps']]] for x in rows]), '',
           f'지도 끔의 선속도 평균 차는 여섯 단계 모두 음수다. 그러나 회전 2칸 평균은 S2c·S2d·S2e에서 양수다. 따라서 모든 축이나 모든 명령에서 지도 끔이 낫다는 해석은 성립하지 않는다. m6000의 끔 back1.0은 정답보다 오차가 {regress:+.6f} m/s 커지는 반례다. 다른 칸의 감소가 평균에서 이를 상쇄한다.', '',
           '## 평가 지형과 해석 세 줄', '',
           '원문 위치: '+ ' · '.join(f'[{name} {ln}행]({base}#L{ln})' for name,ln in r['interpretation_lines'].items())+'.', '',
           table(['지형','env 수'],list(rows[-1]['terrain_counts'].items())), '',
           table(['레벨','env 수'],list(rows[-1]['levels'].items())), '',
           f'근거: `{source}`의 /terrain_columns, /fixed_terrain, /modes/eval_gt/fwd1.0/per_env/{{kind,level}}. 여섯 저장본의 배치 해시가 모두 {rows[-1]["assignment_sha256"]}로 같다. 실제 발이 매 순간 평탄부·단차 중 어디를 딛었는지는 이 표만으로 확정하지 않는다. 따라서 순수 평지라고 단정할 수 없고, 반대로 모든 시간 험지를 밟았다고도 단정하지 않는다.', '',
           table(['원문 해석','독립 판단','대체 문장'],[
               ['복원-GT ±0.002 안, 걷는 모양 거의 같음','정정 필요','표시 반올림은 그 범위지만 S2e 원값은 밖이다. 작은 주축 평균 차만으로 위상·발 끌림·보행 모양 동일성은 알 수 없다.'],
               ['끔 평균이 조금 작음, 평지에서 지도 불필요','첫 산술만 같음 · 이유 미확인','끔의 선속도 주축 평균은 낮다. 일부 회전·후진은 더 나쁘며 지도 원인 효과나 불필요성을 입증한 비교가 아니다.'],
               ['지형 차 미확인','범위를 좁혀 쓰면 동의','L0~2 7종 혼합 평가와 정기 W78 계단 옆걸음의 지도별 차이는 일부 측정되어 있다. 단계 끝 전체 W78·고난도 일반화와 원인 해석은 미확인이다.']]), '',
           'T0′ force_gt 해제는 AdaSmpl의 정답·복원 혼합을 허용한다. 복원 지도만 쓴 학습으로 바뀐 것으로 설명하지 않는다. GT/Pred/OFF는 같은 정책의 평가 입력 모드이며, 전개된 궤적까지 같은 단일 상태 개입 실험이 아니다.', '',
           '## W18 결과 도착 확인', '',
           table(['작업','대기열 상태','완결 결과','읽은 파일'],[
               [x['id'],x['state'],x['status'],'; '.join(Path(p['path']).name for p in x['json_files']) or '없음'] for x in r['w78']]), '',
           '대기열의 실행 표시는 실제 진도·완료 증거로 쓰지 않았다. eval_receipt.json의 존재만으로 PASS를 뜻하지 않는다. terrain_skill_v2.partial.json은 이름 그대로 부분 결과다. 완료 결과·체크포인트 정체·조합 수·원자료를 확인하기 전 기존 W78 칸은 대기다.', '',
           '## 재현과 한계', '',
           '- [감사 코드](audit_w10.py), [원자료 경로·SHA·수치](data/audit.json), [고정한 W10 원문](data/W10-3a97fae8.txt). 모든 표 숫자는 스크립트가 생성했다.',
           '- isaac311 Python으로 `audit_w10.py` 실행. 쓰기는 이 보고 폴더만, 원자료·대기열은 읽기만이다. GPU 라이브러리나 학습 코드를 실행하지 않는다.',
           '- 답을 아는 입력 5묶음: 중앙값/평균 구별, 축 선택, 대칭 분모, 혼합 단위 반례, 반올림 경계 반례.',
           '- 숫자·조건 대조 범위이며 새로운 전편 영상 판독을 한 보고가 아니다. 위상·곡선·대표 영상 증거는 W45와 기존 단계 보고를 참조한다.','']
    report='\n'.join(lines)
    assert '\u2014' not in report
    (HERE/'VERIFY-W10-MAP3.md').write_text(report,encoding='utf-8')

if __name__=='__main__':main()
