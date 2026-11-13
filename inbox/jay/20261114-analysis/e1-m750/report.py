"""Build the m750 evidence report from frozen #802 output and scalar snapshots."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import shutil

import numpy as np

MODES = ('eval_gt', 'eval_pred', 'probe_prop_only')
LABELS = {'eval_gt':'GT', 'eval_pred':'PRED', 'probe_prop_only':'지도 끔'}
ORDER = ('parent', 'earlier', 'previous', 'current')
CASES = ('fwd0.1','fwd0.2','side+0.2','side-0.2')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def projection_ratio(v, alive, commanded):
    if v.shape != (300,64) or alive.shape != v.shape or not np.isfinite(v).all():
        raise ValueError('Raw array dimensions or finite values invalid')
    return float(np.median(np.sum(v * alive, axis=0) * .02 / (commanded * 6.)))


def independent_check(d):
    # Known answer includes terminated envs: planned whole 6 s, not survivor time.
    v=np.full((300,64),.1);alive=np.ones_like(v,dtype=bool);alive[150:]=False
    assert abs(projection_ratio(v,alive,.1)-.5)<1e-12
    checks=[]
    for name in ('earlier','previous','current'):
        snap=d[name];root=Path(snap['score_path']).parent
        for level in (0,5):
            folder=root/f'e1_v2/L{level}'
            doc=json.loads((folder/'map_modes.json').read_text())
            for mode in MODES:
                for case in ('fwd0.1','fwd0.2'):
                    path=folder/doc['env_arrays'][mode+'/'+case]
                    assert sha(path)==snap['sources'][str(path)], 'Source changed since boundary reading'
                    with np.load(path,allow_pickle=False) as z:
                        measured=projection_ratio(z['vx'].astype(float),z['alive'].astype(bool),float(case[3:]))
                        if np.any(z['alive'][1:]>z['alive'][:-1]):
                            raise ValueError('Alive becomes true after termination')
                    expected=snap['metrics'][f'low/L{level}/{mode}/{case}/R']
                    assert abs(measured-expected)<1e-12
                    checks.append({'iteration':snap['iteration'],'cell':f'L{level}/{mode}/{case}',
                                   'ratio':measured,'absolute_difference':abs(measured-expected),'path':str(path),'sha256':sha(path)})
    snap=d['previous'];root=Path(snap['score_path']).parent
    for seed in (7,13):
        for level in (0,5):
            folder=root/f'e1_v2_repeat_seed{seed}/e1_v2/L{level}'
            doc=json.loads((folder/'map_modes.json').read_text())
            assert doc['checkpoint_sha256']==snap['checkpoint_sha256'] and doc['eval_seed']==seed
            primary=json.loads((root/f'e1_v2/L{level}/map_modes.json').read_text())
            for key in ('commands','fixed_terrain','dr_off'):
                assert doc[key]==primary[key], f'Repeat condition differs: {key}'
            assert doc['ex42_mesh']['mesh_sha256']==primary['ex42_mesh']['mesh_sha256']
            for mode in MODES:
                for case in ('fwd0.1','fwd0.2'):
                    path=folder/doc['env_arrays'][mode+'/'+case]
                    assert sha(path)==snap['sources'][str(path)]
                    with np.load(path,allow_pickle=False) as z:
                        identity=json.loads(str(z['run_identity'].item()))
                        assert identity['eval_seed']==seed and identity['checkpoint_sha256']==snap['checkpoint_sha256']
                        assert abs(float(z['dt'])-.02)<1e-8
                        measured=projection_ratio(z['vx'].astype(float),z['alive'].astype(bool),float(case[3:]))
                    expected=snap['repeats'][str(seed)][f'low/L{level}/{mode}/{case}/R']
                    assert abs(measured-expected)<1e-12
                    checks.append({'iteration':snap['iteration'],'seed':seed,'cell':f'L{level}/{mode}/{case}',
                                   'ratio':measured,'absolute_difference':abs(measured-expected),'path':str(path),'sha256':sha(path)})
    return {'known_input':'PASS: half episode .1 m/s equals R=.5, not R=1', 'raw_checks':checks}


def table(headers, rows):
    def safe(x):
        return str(x).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| '+' | '.join(map(safe,headers))+' |',
                      '| '+' | '.join('---' for _ in headers)+' |']+
                     ['| '+' | '.join(map(safe,row))+' |' for row in rows])+'\n'


def plot(d, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,4,figsize=(14,7),constrained_layout=True)
    colors=('#147D92','#B54E2F','#4F498A')
    for i,level in enumerate((0,5)):
        for j,case in enumerate(CASES):
            ax=axes[i,j]
            for mode,color in zip(MODES,colors):
                vals=[d[name]['metrics'][f'low/L{level}/{mode}/{case}/R'] for name in ORDER]
                ax.plot([0,250,500,750],vals,marker='o',color=color,label=LABELS[mode] if mode!='probe_prop_only' else 'OFF')
            if case.startswith('fwd'):
                ax.axhline(.3 if case=='fwd0.1' else .6,color='#666666',linestyle=':',label='R6 trigger reference')
            ax.axvspan(500,750,color='#E3C26E',alpha=.12)
            ax.set_title(f'L{level} {case} (seed 42)')
            ax.set_xticks([0,250,500,750],['parent','250','500','750'])
            ax.set_ylim(0,1.05);ax.grid(alpha=.2);ax.set_ylabel('Progress ratio R')
    axes[0,0].legend(fontsize=8)
    fig.suptitle('E1 low-speed probes: single-seed observations, no causal effect estimate')
    fig.savefig(out/'low_speed_boundaries.png',dpi=145);plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--scratch',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    d=json.loads((a.scratch/'m750/report.json').read_text())
    curves=json.loads((a.scratch/'curves/summary.json').read_text())
    assert d['iteration']==750 and d['decision']['effective_from']==1000
    assert not d['decision']['apply_ready'] and not d['parent_condition_mismatches']
    assert all(not d[k]['errors'] for k in ORDER)
    checks=independent_check(d);a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'independent_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    def value(name,level,mode,case,metric='R'):
        return d[name]['metrics'][f'low/L{level}/{mode}/{case}/{metric}']
    def triplet(key):
        return ' → '.join(f'{d[n]["metrics"][key]:.3f}' for n in ORDER)
    raw_scores={n:json.loads(Path(d[n]['score_path']).read_text()) for n in ORDER}
    c=d['current'];decision=d['decision'];ap=d['approved_table']['current']
    forward=[x for x in d['comparisons'] if x['cell'].startswith('low/') and '/fwd' in x['cell'] and x['cell'].endswith('/R') and '/probe_prop_only/' not in x['cell']]
    assert len(forward)==8
    falling=sum(x['previous_delta']<0 for x in forward)
    summary={'format':'analyst-e1-m750-review/1','created_at':dt.datetime.now().astimezone().isoformat(),
             'inputs':{'boundary_report':str(a.scratch/'m750/report.json'),'sha256':sha(a.scratch/'m750/report.json'),
                       'curves_summary':str(a.scratch/'curves/summary.json'),'curves_sha256':sha(a.scratch/'curves/summary.json')},
             'snapshots':{n:{k:d[n][k] for k in ('iteration','checkpoint_sha256','plan_sha256','sources','metrics','repeats','maintenance','maintenance_modes','overall','errors','warnings')} for n in ORDER},
             'decision':decision,'off_monitor':decision['map_off_survival'],
             'wide_errors':ap['wide_errors'],'independent_raw_checks':len(checks['raw_checks']),
             'GT_PRED_forward_declined_cells':falling,'conditions_mismatch':d['parent_condition_mismatches']}
    (a.out/'EVIDENCE.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    for src,name in [(a.scratch/'curves/curves_1_750.png','curves_1_750.png'),
                     (a.scratch/'curves/scalars.csv','scalars.csv'),(a.scratch/'curves/windows50.csv','windows50.csv'),
                     (a.scratch/'curves/summary.json','curves_summary.json'),
                     (a.scratch/'m750/mode_cells.csv','mode_cells.csv'),
                     (a.scratch/'m750/adjustment.draft.json','adjustment.draft.json')]:
        shutil.copyfile(src,a.out/name)
    plot(d,a.out)
    repeat_rows=[]
    for level in (0,5):
        for case in ('fwd0.1','fwd0.2'):
            for mode in MODES[:2]:
                key=f'low/L{level}/{mode}/{case}/R'
                vals=[d['previous']['metrics'][key]]+[d['previous']['repeats'][str(seed)][key] for seed in (7,13)]
                repeat_rows.append([f'L{level} {case} {LABELS[mode]}',
                                    ' / '.join(f'{v:.4f}' for v in vals),f'{min(vals):.4f}~{max(vals):.4f}',
                                    f'{max(vals)-min(vals):.4f}',f'{c["metrics"][key]:.4f}',
                                    '아래' if c['metrics'][key]<min(vals) else '안/위'])
    now=dt.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')
    h=['# E1 다시 학습 m750: 저속 보행과 유지 능력', '',
       '> 분류: A/평가',f'> 작성: analyst-lx · {now}',
       '> 근거: lead 00:56 · 원자료 TensorBoard 1~750 · m250/m500/m750 P1 · #802 기록 판독',
       '> 요지: 전진 저속은 직전보다 낮아졌고, 옆걸음은 좌우가 엇갈렸다. 기존 유지와 지도 끔 생존은 통과했다.',
       '> 상태: CPU 원자료 대조 완료 · 현재 시험 구간 기록 · 설정 적용 없음', '> 판: v1.0','',
       f'**실측:** slow_track 가중을 켠 뒤의 m750에서 GT·PRED × L0/L5 × 전진 0.1/0.2 **{falling}/{len(forward)}칸 모두 m500보다 진행 비율이 낮아졌다.** 옆 +0.2는 높아졌고 옆 −0.2는 낮아졌다. 따라서 이번 경계는 느린 보행이 전반적으로 좋아졌다는 증거가 아니다.', '',
       f'**실측:** 기존 유지 GT·PRED는 {c["maintenance"]}, 지도 끔 생존 감시 {len(ap["off_cells"])}칸은 모두 64/64다. 서 있기 성공도 지도 셋 모두 64/64다. 저속 전진에서 주로 드러난 문제는 넘어짐보다 **명령을 받고도 거의 나아가지 않음**이다.', '',
       '**추론 한계:** m500 이후 slow_track=0을 그대로 둔 동시 대조군이 없다. 보상·명령 영수증상 바뀐 보상은 slow_track 하나지만 이어 학습·리셋·정책의 자연 변동까지 분리한 인과 효과가 아니다. 이 구간에서 해당 처방의 이득이 입증되지 않았다고 말할 수 있다.', '',
       '## 조건과 출처', '',
       'L0는 여기서 평지가 아니라 연속 지형 묶음의 레벨 0이다. map64·저속·Y1 비교는 seed42·64 env·300 step(6초), 같은 메시·열 배치·고정 마찰의 칸별 비교다. 별도 평지 서기는 3초 중 첫1초를 빼며, D44는 그 영수증의 별도 시간 계약이다. 부모는 지정된 P1 예행 m13250이며, 오래된 별도 G1b 자료로 바꿔 넣지 않았다. 부모의 실행 plan은 달라도 평가 칸의 비교 fingerprint는 일치한다.', '',
       table(['저장본','체크포인트 SHA256','기존 유지','전체 졸업'],[[{'parent':'부모 m13250','earlier':'m250','previous':'m500','current':'m750'}[n],d[n]['checkpoint_sha256'],d[n]['maintenance'],d[n]['overall']] for n in ORDER]),
       '현재 학습 plan SHA: `'+c['plan_sha256']+'`. 평가 메시 SHA: `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95`.', '',
       '학습 1~250·251~500·501~750은 서로 다른 tfevents 세 파일이다. 각 파일에 250회, 전체 750회이며 중복 0·누락 0이다. 두 rank의 보상 영수증은 일치한다. b1→b2는 명령 슬롯·범위·low_forward_fraction=0.4가 같고 slow_track만 0→0.2다. 첫 구간 보상은 초기 manifest/plan 근거이고 별도 실시간 RewardManager 영수증은 없다는 한계를 보존한다.', '',
       '## 목표 명령별 변화', '',
       '각 칸은 **부모 → m250 → m500 → m750**. R은 시작 64 env 각각의 예정된 전체 6초 명령 거리 대비 진행 비율의 중앙값이다. 전진은 NPZ 몸앞 vx 적분, 옆은 JSON의 명령 방향 투영거리로 계산한다. 사망한 env를 분모에서 빼지 않는다.', '',
       table(['레벨·명령','GT R','PRED R','지도 끔 R'],[[f'L{l} {case}']+[triplet(f'low/L{l}/{m}/{case}/R') for m in MODES] for l in (0,5) for case in CASES]),
       '![저속 명령 경계 비교](low_speed_boundaries.png)', '',
       'm500에는 seed42·7·13 반복이 이미 있다. seed·체크포인트·명령·지형 배치·DR 조건을 대조하고 NPZ를 재계산했다. 아래는 그 **관측 범위**이며 신뢰구간이 아니다. m750 seed42의 전진 여덟 칸은 모두 m500 세 시드 최솟값보다 낮다. 다만 m750의 seed7·13이 없어 양쪽의 같은 시드 반복 효과를 확정할 수 없다.', '',
       table(['칸','m500 seed42 / 7 / 13','m500 범위','범위 폭','m750 seed42','이전 범위 대비'],repeat_rows),
       '전진 0.1 정체 수는 2~4초 몸앞 속도 평균 <0.05 m/s인 env 수다. 이 구간의 모든 전진 env가 생존하므로 사망 때문에 생긴 정체 수가 아니다.', '',
       table(['레벨','GT m500 → m750','PRED m500 → m750','끔 m500 → m750'],[[f'L{l}']+[f"{value('previous',l,m,'fwd0.1','stalled_2to4s')} → {value('current',l,m,'fwd0.1','stalled_2to4s')} /64" for m in MODES] for l in (0,5)]),
       '## 기존 능력과 머리 방향', '',
       '아래는 m750 유지 13명령. 각 칸은 **생존 수 / vx·vy·wz 절댓값 오차 중앙값**이다. 속도 오차는 m/s, yaw rate 오차는 rad/s. 생존은 시작 64개 분모다. 원래 유지표 PASS가 모든 기술의 향상을 뜻하지는 않는다.', '',
       table(['명령','GT: 생존 / vx·vy·wz','PRED: 생존 / vx·vy·wz','끔: 생존 / vx·vy·wz'],[[case]+[f"{raw_scores['current']['map64'][m][case]['alive_at_end']}/64 / "+'·'.join(f"{raw_scores['current']['map64'][m][case][k]:.3f}" for k in ('vx_abs_error_median_mps','vy_abs_error_median_mps','wz_abs_error_median_radps')) for m in MODES] for case in raw_scores['current']['map64']['eval_gt']]),
       'Y1은 각 env 마지막 생존 시점까지 순 yaw 변화 절댓값의 중앙값·p90이다. 아래는 m500→m750, 단위 rad. 회전의 부호가 다른 env끼리 상쇄하는 계산을 하지 않는다.', '',
       table(['명령','GT 중앙값 / p90','PRED 중앙값 / p90','끔 중앙값 / p90'],[[case]+[' / '.join('→'.join(f"{d[n]['metrics'][f'yaw/L2/{m}/{case}/{k}']:.3f}" for n in ('previous','current')) for k in ('median_abs_rad','p90_abs_rad')) for m in MODES] for case in ('fwd0.5','fwd1.0')]),
       'D44 성공 수(기존 영수증 기준). 회전 네 칸은 판정, 정지→재출발은 현재 출구의 기록 칸이다.', '',
       table(['D44 칸','m250','m500','m750','m750 생존'],[[key]+[str(raw_scores[n]['d44_cells'][key]['success_count'])+'/64' for n in ('earlier','previous','current')]+[str(v['survival_count'])+'/64'] for key,v in raw_scores['current']['d44_cells'].items()]),
       '지도 끔 감시 21칸의 실제 수:', '',
       table(['칸','m500 생존','m750 생존','분모'],[[k, d['approved_table']['previous']['off_cells'][k]['survival'],v['survival'],v['valid']] for k,v in ap['off_cells'].items()]),
       '## 학습 곡선', '',
       '![학습 곡선](curves_1_750.png)', '',
       'LR 바닥은 **각 PPO update 끝의 값**이 1e-5인 횟수다. 미니배치 시간의 비중이 아니다. PPO·지각 진단 KL은 scheduler가 각 미니배치에서 쓴 실제 KL과 다르다. #806 장치는 후속 실행을 위한 것이며 이번 곡선에서 미니배치 원인을 실측했다고 쓰지 않는다.', '',
       table(['학습 구간','LR 바닥 횟수','PPO 진단 KL>0.02','action std 평균','평균 에피소드 steps','보상/step 평균','slow_track 로그 평균'],[[f"{s['first']}~{s['last']}",f"{s['lr_floor_n']}/{s['n']}",s['ppo_kl_gt_002_n'],f"{s['std']['mean']:.4f}",f"{s['episode']['mean']:.1f}",f"{s['reward_per_step_mean']:.5f}",f"{s['slow_track']['mean']:.6f}"] for s in curves['segments250']]),
       '첫 업데이트의 에피소드 합·길이 버퍼는 재시작마다 비워진다. 251·501 근처의 합 보상·에피소드 길이 급락을 보행 붕괴로 읽지 않는다. 보상/step은 매 update의 평균 에피소드 보상÷평균 길이를 계산한 뒤 창 평균이며, 전체 rollout을 가중 합친 평균과는 다르다. 각 보상 항은 `RewardManager`의 가중치·dt가 들어간 에피소드 누계를 최대 에피소드 초로 나눈 값이다.', '',
       '50회 저장본 단위 전체 표: [CURVES-50.md](CURVES-50.md). 원 숫자: [windows50.csv](windows50.csv), [scalars.csv](scalars.csv). 보상 항 상승과 느린 전진 개선을 같은 뜻으로 취급하지 않는다.', '',
       '## #802 기록 판독', '',
       f"실제 출력: `{decision['rule']} · {decision['next_segment']}`. `apply_ready=false`, 조정 payload 없음. GT/PRED 여덟 전진 칸이 모두 비증가라 R6 증량 후보가 되지만, side−0.4가 처방 직전 m500 대비 GT/PRED·L0/L5에서 모두 0.05 넘게 내려 증량은 보류된다. 보상 변경 뒤 관측은 한 경계뿐이므로 두 경계 되돌림을 완성했다고 세지 않는다.", '',
       '이 run은 시험 구간이다. `--effective-from 1000`으로 실행했으며 m750에 새 승인표를 소급 적용하지 않았다. 새 표를 반사실로 걸면 C1 소비/자료 미완비 때문에 EVIDENCE_HOLD이며, 이것이 실제 m750 운영 중단 명령은 아니다. 이번 코드 실행은 GPU·학습·운영 원장·설정을 바꾸지 않았다.', '',
       '## 기준 의심 여섯 칸', '',
       table(['검토 축','실측 또는 공백','해석과 다음 판단의 한계'],[
           ['목표 대비',f'전진 GT/PRED 8칸 모두 m500 대비 하락. 전진0.1은 4칸 모두 R<0.3, 전진0.2는 4칸 모두 R>0.6.', '0.2가 문턱을 넘은 것과 처방 뒤 개선된 것은 다르다. 다음 실행의 기준을 결과에 맞춰 낮추지 않는다.'],
           ['곡선',f"보상/step 평균 {curves['segments250'][1]['reward_per_step_mean']:.5f}→{curves['segments250'][2]['reward_per_step_mean']:.5f}; slow_track 로그는 0→{curves['segments250'][2]['slow_track']['mean']:.6f}.", '전체 env·명령 평균의 상승이 저속 전진 개선을 가린다. 항이 실제로 켜진 것은 확인되지만 어떤 명령에서 보상/gradient를 벌었는지는 이 로그로 분리하지 못한다.'],
           ['세 지도 대조','GT·PRED 전진 및 옆의 변화 방향이 일치. 지도 끔은 생존 21칸 모두64이며 전진0.1 하락 폭은 더 작다.', 'PRED만의 실패가 아니다. 우선 정책·명령별 보상 경쟁을 점검할 근거지만, 지도 경로가 원인에서 제외됐다는 증명도 아니다.'],
           ['구간 중간',f"L0 GT 전진0.1 R {value('earlier',0,'eval_gt','fwd0.1'):.3f}→{value('previous',0,'eval_gt','fwd0.1'):.3f}→{value('current',0,'eval_gt','fwd0.1'):.3f}.", 'slow_track를 켜기 전부터 하락했다. 저장본은50회마다 있어도 중간 저장본의 같은 저속 시험지는 없다. 하락 시점·지속을 곡선만으로 확정하지 않는다.'],
           ['규칙이 못 보는 칸','기존 유지13은 통과하지만0.1은 거의 정체. 옆+0.2 상승·−0.2 하락이 서로 가려질 수 있다. C1/L9·새 접촉 원자료 미확인.', '방향별 값을 합치지 않는다. 유지 PASS를 보행 위상·발 끌림 전체 PASS로 확대하지 않는다. 새 R5 접촉 근거를 만들어 채우지 않는다.'],
           ['기준 자체','m500 전진0.1 세 시드 관측 폭은 위 표처럼 과거 R 반복폭0.007보다 크다. m750은 seed42만 있다.', '과거m2000 반복폭은 현재정책의 잡음 상한이나 신뢰구간이 아니다. m750 여덟 전진 값은 m500 세 시드 최솟값 아래지만, 양쪽 반복과 동시 대조군 없이 보상 인과·일반화를 확정하지 않는다. 등록 문턱을 이 결과에 맞춰 바꾸지는 않는다.']]),
       '## 재현과 검증', '',
       f'독립 확인: 알려진 입력에서 6초 중3초만 움직인 R=0.5를 확인했고, m250/m500/m750의 전진 NPZ36칸과 m500 seed7·13의24칸을 합쳐 **{len(checks["raw_checks"])}칸**을 다른 집계 함수로 다시 계산해 #802 값과 차이 <1e-12였다. 이벤트 중복의 최신 wall_time 선택·같은시각 값 충돌 거절·빠진 회차 거절 시험도 통과했다.', '',
       '원자료별 경로·SHA·조건·정밀 숫자는 [EVIDENCE.json](EVIDENCE.json), [independent_checks.json](independent_checks.json), [curves_summary.json](curves_summary.json)에 있다. 큰 NPZ·TensorBoard 원본은 운영 자료에서 읽기만 하고, 이벤트 바이트 사본은 아래 scratch에 보존했다.', '',
       f'분석 scratch: `{a.scratch}`. #802 원본 출력: `{a.scratch}/m750/REPORT.md`.', '',
       '코드 근거: [boundary_read.py](../../20261113-analysis/e1-boundary-rules/boundary_read.py) 101~230행(칸·생존·정체·yaw 재계산), 271~344행(처방 영수증), [boundary_approved.py](../../20261113-analysis/e1-boundary-rules/boundary_approved.py) 9~30행(끔 생존), 97행 이후(적용 경계). 보상 로그 정의는 `/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py:116`·`:150`, 재시작 버퍼는 실행 고정 사본의 `foothold_s2/runners/start_runner.py` `learn()` 시작부다.', '',
       '```bash',
       "CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261114-analysis/e1-m750/curves.py --out /home/jay/mai/tmp/analyst/e1-m750-review-1114/curves",
       "CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261113-analysis/e1-boundary-rules/boundary_read.py --score /home/jay/data/foothold/s2_lab/ex42_main_20261113_174400/main/EX-42-B-E1-again_20261113_174400/eval/scores/m750/ex42_score.json --out /home/jay/mai/tmp/analyst/e1-m750-review-1114/m750 --effective-from 1000",
       "CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261114-analysis/e1-m750/report.py --scratch /home/jay/mai/tmp/analyst/e1-m750-review-1114 --out inbox/jay/20261114-analysis/e1-m750",
       '```','',
       '| 판 | 내용 |','|---|---|','| v1.0 | 세 구간 곡선과 m750 기록 판독, 여섯 검토 축 |']
    (a.out/'REPORT.md').write_text('\n'.join(h)+'\n',encoding='utf-8')
    header=f'# E1 m750 학습 곡선 · 50회 단위 표\n\n> 분류: A/평가\n> 작성: analyst-lx · {now}\n> 근거: 이벤트 세 파일1~750 · curves_summary.json\n> 요지: 저장본50회 단위의 학습 상태와 보상 항\n> 상태: CPU 계산 · 누락0 · 중복0\n\n'
    (a.out/'CURVES-50.md').write_text(header+(a.scratch/'curves/TABLES.md').read_text(),encoding='utf-8')
    lines=[f'{sha(path)}  {path.name}' for path in sorted(a.out.iterdir()) if path.is_file() and path.name!='SHA256SUMS']
    (a.out/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'independent_checks':len(checks['raw_checks']),'forward_declines':falling,'rule':decision['rule'],'off':decision['map_off_survival']['state'],'report':str(a.out/'REPORT.md')},ensure_ascii=False))


if __name__=='__main__':
    main()
