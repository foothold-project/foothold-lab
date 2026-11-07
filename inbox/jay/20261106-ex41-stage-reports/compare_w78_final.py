"""W18: audit the final and preceding full W78 bundles; write a paired appendix."""
from __future__ import annotations
import itertools
import json
import argparse
import csv
from pathlib import Path
import numpy as np
import update_w78 as w

P = Path(__file__).resolve().parent


def read_rows(path):
    def value(x):
        if x == '': return None
        if x in ('True', 'False'): return x == 'True'
        try: return json.loads(x)
        except json.JSONDecodeError: return x
    with path.open(encoding='utf-8', newline='') as fp:
        return [{k:value(v) for k,v in r.items()} for r in csv.DictReader(fp)]


def queue_evidence(packs):
    out=[]
    for n,q in ((5500,675),(6000,747)):
        p=Path(f'D:/mai-tmp/gpu/results/item_{q}.json')
        d=json.loads(p.read_text(encoding='utf-8'))
        b=d['last_json']
        assert d['id']==q and d['rc']==0 and b['rc']==0 and b['state']=='done'
        assert b['checkpoint_sha256']==packs[n][0]['checkpoint_sha256']
        assert b['source_git_head']==packs[n][0]['run_identity']['code_head']
        assert b['device']==packs[n][0]['run_identity']['device']
        out.append({'path':str(p),'sha256':w.sha(p),'iteration':n,'queue_id':q,
                    **{k:b[k] for k in ('checkpoint_sha256','source_git_head','device','eval_config_sha256','state','rc','seconds')}})
    assert out[0]['eval_config_sha256']==out[1]['eval_config_sha256']
    path=P/'data/w78_5500_6000_protocol.json'
    doc=json.loads(path.read_text(encoding='utf-8'))
    doc['queue_receipts']=out
    w.dump(path,doc)


def render_cached():
    """Render checked CSVs without repeating the immutable raw NPZ audit."""
    packs = {n:(json.loads((P/f'data/w78_m{n}_audit.json').read_text(encoding='utf-8')),
                read_rows(P/f'data/w78_m{n}_env.csv'),
                read_rows(P/f'data/w78_m{n}_kinds.csv')) for n in (5500,6000)}
    comp=read_rows(P/'data/w78_5500_6000_comparison.csv')
    metrics=read_rows(P/'data/w78_5500_6000_feet_stop.csv')
    queue_evidence(packs)
    appendix=make_appendix(packs,comp,metrics)
    saved=P/'data/w78_m6000_section.txt'
    base=saved.read_text(encoding='utf-8').split('### m11500 → m12000:',1)[0]
    saved.write_text(base+appendix,encoding='utf-8')
    (P/'data/w78_5500_6000_section.txt').write_text(appendix,encoding='utf-8')
    dest=P/'RESULT-EX41-T0prime.md'
    dest.write_text(w.apply_saved_section(dest.read_text(encoding='utf-8'),6000),encoding='utf-8')
    write_note(packs,comp,metrics)


def run():
    packs = {}
    for n in (5500, 6000):
        print(f'audit m{n} begin', flush=True)
        meta, rows, kinds = w.audit(n)
        packs[n] = (meta, rows, kinds)
        w.csv_write(P/f'data/w78_m{n}_env.csv', [{k:v for k,v in r.items() if k != 'heights'} for r in rows])
        w.csv_write(P/f'data/w78_m{n}_kinds.csv', kinds)
        w.dump(P/f'data/w78_m{n}_audit.json', meta)
        print(json.dumps({k:meta[k] for k in ('iteration','value_checks','max_float_delta')}), flush=True)
    old, new = packs[5500][0], packs[6000][0]
    for k in ('source_sha256','dr_off','curriculum_off','cases','terrain_assignments'):
        assert old[k] == new[k], k
    for k in ('code_head','device'):
        assert old['run_identity'][k] == new['run_identity'][k], k
    # All comparisons retain phase, terrain kind and mode; no mixed-unit score.
    comp = []
    metrics = []
    for lv, mode, case, kind in itertools.product([2,5],w.MODES,new['cases'],['pyramid_stairs','pyramid_stairs_inv']):
        if kind not in new['cases'][case]['focus_kinds']:
            continue
        subsets = {n:[r for r in packs[n][1] if (r['level'],r['mode'],r['case'],r['kind'])==(lv,mode,case,kind)] for n in packs}
        a,b = subsets[5500], subsets[6000]
        assert [(r['angle'],r['env']) for r in a] == [(r['angle'],r['env']) for r in b]
        for phase,(command,secs) in enumerate(new['cases'][case]['phases']):
            if not any(command[:2]):
                continue
            r = dict(level=lv,mode=mode,case=case,kind=kind,phase=phase,command=command,seconds=secs,n=len(a))
            for n, subset in subsets.items():
                r[f'R_{n}'] = w.med(x['ratios'][phase] for x in subset)
                r[f'distance_m_{n}'] = w.med(x['distances_m'][phase] for x in subset)
                r[f'alive_{n}'] = sum(x['alive'] for x in subset)
            r['delta_R'] = r['R_6000']-r['R_5500']
            r['delta_distance_m'] = r['distance_m_6000']-r['distance_m_5500']
            comp.append(r)
        r=dict(level=lv,mode=mode,case=case,kind=kind,n=len(a))
        for n, subset in subsets.items():
            r[f'drag_{n}']=sum(x['drag_num'] for x in subset)/sum(x['drag_den'] for x in subset)
            r[f'swing_p50_m_{n}']=w.med(h for x in subset for h in x['heights'])
            r[f'closed_swings_{n}']=sum(len(x['heights']) for x in subset)
            r[f'stop_heading_deg_{n}']=w.med(abs(x['stop_yaw_rad'])*180/np.pi for x in subset if x['stop_yaw_rad'] is not None)
            r[f'stop_rotation_deg_{n}']=w.med(x['stop_abs_wz_rad']*180/np.pi for x in subset if x['stop_abs_wz_rad'] is not None)
            r[f'back_lateral_abs_m_{n}']=w.med(abs(x['back_lateral_m']) for x in subset if x['back_lateral_m'] is not None)
            r[f'stop_valid_{n}']=sum(x['back_lateral_m'] is not None for x in subset)
        metrics.append(r)
    w.csv_write(P/'data/w78_5500_6000_comparison.csv',comp)
    w.csv_write(P/'data/w78_5500_6000_feet_stop.csv',metrics)
    w.dump(P/'data/w78_5500_6000_protocol.json',{'matched_fields':['source_sha256','dr_off','curriculum_off','cases','terrain_assignments','run_identity.code_head','run_identity.device'],
           'old':old['result'],'new':new['result'],'old_sha256':old['result_sha256'],'new_sha256':new['result_sha256'],
           'comparisons':len(comp),'feet_stop_rows':len(metrics), 'known_answers':w.known_answers()})
    queue_evidence(packs)
    w.figure(6000,new,packs[6000][2])
    snippet=w.section(new,packs[6000][1],packs[6000][2])
    # This old generic sentence is no longer true after the preceding checkpoint audit.
    snippet=snippet.replace('다른 저장본과 같은 W78 프로토콜로 재측정하기 전에는 이 단계에서 얼마나 새로 배웠거나 잊었는지 분리할 수 없다.',
                            '아래 보충 절에서 같은 W78 프로토콜의 직전 m5500과 비교했다. 반복 시드·영상 전편 판독·원인 분리는 여전히 별도다.')
    appendix=make_appendix(packs,comp,metrics)
    snippet += appendix
    (P/'data/w78_m6000_section.txt').write_text(snippet,encoding='utf-8')
    dest=P/'RESULT-EX41-T0prime.md'
    dest.write_text(w.apply_saved_section(dest.read_text(encoding='utf-8'),6000),encoding='utf-8')
    (P/'data/w78_5500_6000_section.txt').write_text(appendix,encoding='utf-8')
    write_note(packs,comp,metrics)
    print('paired appendix and T0prime complete',flush=True)


def make_appendix(packs,comp,metrics):
    def signed(x): return f'{x:+.3f}'
    def select(lv,case,kind,mode,phase=0):
        return next(r for r in comp if (r['level'],r['case'],r['kind'],r['mode'],r['phase'])==(lv,case,kind,mode,phase))
    text=['### m11500 → m12000: 같은 시험지에서 바뀐 것','',
          '로컬 m5500(S2e, 대기열 675)과 m6000(T0′, 747)을 비교했다. 아래 모든 Δ는 m6000 − m5500이다. 평가 코드·설정·시드42·cuda:1·지형 배치·레벨·시작 방향·명령 구간을 대조했다. 서로 다른 학습 저장본이며 반복 재측정 잡음 폭은 없다. 효과의 통계적 유의성이나 원인 확정 대신 관측 차이로 읽는다.','',
          '#### 이동 비 R: 무차원','',
          '각 칸은 **m12000 R (직전 대비 ΔR)**. 두 계단 종류를 합치지 않았고, 네 시작 방향의 해당 지형 env 기록을 모은 중앙값이다. 세계 좌표 목표 도착률이나 성공률이 아니다.','']
    basic=['stairs_fwd','stairs_side_left','stairs_side_right','stairs_back']
    tab=[]
    for lv,kind,case in itertools.product([2,5],['pyramid_stairs','pyramid_stairs_inv'],basic):
        line=[f'L{lv}',w.KIND_LABELS[kind],w.CASE_LABELS[case]]
        for mode in w.MODES:
            r=select(lv,case,kind,mode)
            line.append(f"{r['R_6000']:.3f} ({signed(r['delta_R'])})")
        tab.append(line)
    text += [w.table(['레벨','지형','과제',*w.LABELS],tab),'',
             '#### 같은 전진 구간의 거리 m와 생존','',
             '거리 = 몸 기준 명령 방향 속도의 적분이며 world 좌표 변위가 아니다. 칸은 **m12000 거리 m (Δm) · 끝 생존 old→new/전체**. 생존과 거리를 별도 값으로 표시한다.','']
    tab=[]
    for lv,kind in itertools.product([2,5],['pyramid_stairs','pyramid_stairs_inv']):
        line=[f'L{lv}',w.KIND_LABELS[kind]]
        for mode in w.MODES:
            r=select(lv,'stairs_fwd',kind,mode)
            line.append(f"{r['distance_m_6000']:.3f} ({signed(r['delta_distance_m'])}) · {r['alive_5500']}→{r['alive_6000']}/{r['n']}")
        tab.append(line)
    text += [w.table(['레벨','지형',*w.LABELS],tab),'',
             '#### 발 끌림과 스윙 높이: 다른 단위','',
             '계단 전진만. 끌림은 접촉 중 빠르게 움직이는 발 표본의 비율이며 Δ는 percentage point(%p). 스윙은 완결된 비접촉 구간의 기준 접지 대비 높이 중앙값 m. 큰 스윙 수를 독립 실험 수로 세지 않는다.','']
    tab=[]
    for lv,kind,mode in itertools.product([2,5],['pyramid_stairs','pyramid_stairs_inv'],w.MODES):
        r=next(r for r in metrics if (r['level'],r['kind'],r['mode'],r['case'])==(lv,kind,mode,'stairs_fwd'))
        tab.append([f'L{lv}',w.KIND_LABELS[kind],w.LABELS[w.MODES.index(mode)],
                    f"{r['drag_6000']*100:.2f}% ({(r['drag_6000']-r['drag_5500'])*100:+.2f}%p)",
                    f"{r['swing_p50_m_6000']:.3f} ({signed(r['swing_p50_m_6000']-r['swing_p50_m_5500'])})",
                    f"{r['closed_swings_5500']}→{r['closed_swings_6000']}"])
    text += [w.table(['레벨','지형','지도','끌림 비율 (Δ%p)','스윙 m (Δm)','완결 스윙 수'],tab),'',
             '#### 정지 후 후진: 각도 °와 횡이탈 m','',
             'stairs_fwd_stop_back만. 부호 상쇄를 피한 절댓값 중앙값, 각도와 거리를 섞지 않는다. 칸은 m12000 (Δ).','']
    tab=[]
    for lv,mode in itertools.product([2,5],w.MODES):
        subsets={n:[r for r in packs[n][1] if r['level']==lv and r['mode']==mode and r['case']=='stairs_fwd_stop_back' and r['focus']] for n in packs}
        line=[f'L{lv}',w.LABELS[w.MODES.index(mode)]]
        for key,scale in [('stop_yaw_rad',180/np.pi),('stop_abs_wz_rad',180/np.pi),('back_lateral_m',1)]:
            a,b=[w.med(abs(r[key])*scale for r in subsets[n] if r[key] is not None) for n in (5500,6000)]
            line.append(f'{b:.3f} ({signed(b-a)})')
        line.append(' → '.join(f"{sum(r['back_lateral_m'] is not None for r in subsets[n])}/{len(subsets[n])}" for n in (5500,6000)))
        tab.append(line)
    text += [w.table(['레벨','지도','정지 방향 변화 °','정지 회전 누적 °','후진 횡이탈 m','유효 old→new'],tab),'',
             '[전 과제·구간별 비교 CSV](data/w78_5500_6000_comparison.csv) · [발·정지 단위별 CSV](data/w78_5500_6000_feet_stop.csv) · [비교 조건과 해시](data/w78_5500_6000_protocol.json). 복합 과제의 전진·후진 각 구간도 CSV에 따로 남겼다.','']
    text += conclusions(packs,comp,metrics)
    return '\n'.join(text)+'\n'


def conclusions(packs,comp,metrics):
    def row(lv,kind,mode,case='stairs_fwd'):
        return next(r for r in comp if (r['level'],r['kind'],r['mode'],r['case'],r['phase'])==(lv,kind,mode,case,0))
    tab=[]
    for lv,kind in itertools.product([2,5],['pyramid_stairs','pyramid_stairs_inv']):
        rr=[row(lv,kind,mode) for mode in w.MODES]
        gains=[]
        for mode in ('eval_gt','eval_pred'):
            def at(m,a):
                return next(r['ratios'][0] for r in packs[6000][2] if (r['level'],r['kind'],r['mode'],r['case'],r['angle'])==(lv,kind,m,'stairs_fwd',a))
            gains.append(sum(at(mode,a)>at('probe_prop_only',a) for a in (0,30,60,90)))
        tab.append([f'L{lv}',w.KIND_LABELS[kind],f"{rr[0]['R_6000']-rr[2]['R_6000']:+.3f}",
                    f"{rr[1]['R_6000']-rr[2]['R_6000']:+.3f}",f'{gains[0]}/4 · {gains[1]}/4'])
    basics=[r for r in comp if r['case'] in ('stairs_fwd','stairs_side_left','stairs_side_right','stairs_back')]
    lookup={(r['level'],r['kind'],r['case'],r['mode']):r for r in basics}
    pred_gap=max(abs(lookup[(lv,k,c,'eval_pred')]['R_6000']-lookup[(lv,k,c,'eval_gt')]['R_6000']) for lv,k,c in itertools.product([2,5],['pyramid_stairs','pyramid_stairs_inv'],('stairs_fwd','stairs_side_left','stairs_side_right','stairs_back')))
    left=[r for r in basics if r['case']=='stairs_side_left']
    normalleft=[r['delta_R'] for r in left if r['kind']=='pyramid_stairs']
    lines=['### 결론: 지도가 계단에서 일을 하는가','',
      '**명령 방향 이동량에서는 일부 조건에서 도움, 다른 조건에서는 반대다.** 계단 전진의 지도 모드별 이동 비가 다르게 관측됐다. 역형 계단은 지도 켠 쪽이 크고 정방향 계단은 지도 끔 쪽이 크다. 이 방향 차이가 아래 네 시작 방향에서도 반복된다. 두 종류를 합쳐 지도 효과가 없거나 항상 좋다고 쓰면 둘 다 틀린다.','',
      w.table(['레벨','지형','GT−끔 ΔR','Pred−끔 ΔR','켬 R > 끔 R 방향 수(GT · Pred)'],tab),'',
      f'**복원과 정답은 이 평가에서 가깝지만 복원 정확도 검증은 아니다.** 계단 전진·후진·좌우의 지형별 중앙값 비교 {len(basics)//3}칸에서 Pred−GT의 최대 절댓값은 {pred_gap:.3f} R이다. 지도 높이 RMSE나 발 디딜 위치의 정확도는 이번 원자료로 재지 않았다. 지도 입력 사용에 따른 행동 차이는 관측했지만, 로봇이 실제 단차를 미리 읽어 발을 골라 놓았는지는 지도·발 위치의 시간 정렬 또는 영상 판독이 더 필요하다.','',
      f'**마지막 학습 구간은 일괄 개선이 아니다.** 계단 전진은 GT·Pred 두 지형 모두 늘었으나, 계단 왼쪽은 {sum(r["delta_R"]<0 for r in left)}/{len(left)}칸에서 줄었다. 정방향 계단 왼쪽 ΔR은 {min(normalleft):+.3f}~{max(normalleft):+.3f}다. T0′ 보충 표의 발 끌림과 후진 횡이탈도 따로 보아야 한다. 전진이 늘어난 것을 옆걸음·발 끌림까지 좋아진 것으로 확대하지 않는다.','',
      '**다음 단계에 줄 정보.** 계단 전진의 두 지형·네 방향을 유지 칸으로 나누고, 계단 왼쪽 이동과 접촉 중 끌림, 정지 뒤 후진 횡이탈을 회귀 감시 칸에 남긴다. 이 차이를 이유로 지도 입력을 버리거나 새 보상을 곧바로 늘리지는 않는다. 같은 저장본 반복 폭·새 지형·다른 시드가 없으므로 통계적 우열, 원인, 졸업 여부는 미확인이다.','',
      '정방향/역형은 지형 생성기 종류 이름이다. 어느 발이 실제로 올라갔는지·내려갔는지·계단 끝까지 도착했는지는 이동 비만으로 증명하지 않는다.','']
    return lines


def write_note(packs,comp,metrics):
    lines=['> 분류: A/평가 · W18 최종 W78 보충', '> 작성: analyst · 2026-11-07',
           '> 근거: m5500·m6000 W78 원시 NPZ 각 240개 · 대기열 675·747 · #555',
           '> 요지: 계단 지도 효과는 지형 종류에 따라 반대이며 전진 개선과 옆걸음 감소가 함께 관측됐다.',
           '> 상태: 수치 대조 완료 · 원인·반복 폭·졸업 판정 미확인', '',
           '# W18 m12000 · W10 정본 갱신용 근거','',
           'lead 정본의 「m12000 W78 대기」는 이 결과로 교체할 수 있다. 「지도가 계단에서 일을 하는가」는 전면 미확인 대신 아래처럼 측정 범위와 남은 해석을 분리한다. 정본 자체는 이 사본에서 수정하지 않았다.','']
    lines += conclusions(packs,comp,metrics)
    lines += ['## 수치·단위·원자료', '',
              '[T0′ 최종 보고서](RESULT-EX41-T0prime.md)의 「m11500 → m12000」 절에 R(무차원)·명령 방향 적분 거리(m)·끝 생존(기록 수)·끌림(% 및 %p)·스윙 높이(m)·정지 회전(°)·후진 횡이탈(m)을 각각 표로 실었다. 새 평가 합격선을 만들지 않았다.','',
              w.table(['저장본','누적 회차','원시 NPZ','수치 대조','최대 부동소수 차','원문 SHA256'],
                      [[f'm{n}',packs[n][0]['cumulative_iteration'],len(packs[n][0]['npz_sources']),packs[n][0]['value_checks'],f"{packs[n][0]['max_float_delta']:.9g}",packs[n][0]['result_sha256']] for n in (5500,6000)]),'',
              '[비교 조건과 원본 경로](data/w78_5500_6000_protocol.json) · [m5500 감사](data/w78_m5500_audit.json) · [m6000 감사](data/w78_m6000_audit.json) · [생성기](compare_w78_final.py). 기존 1x 영상·위상 근거와 다른 CPU 수치 보충이며 이번에는 영상 전편을 새로 판독하지 않았다.','']
    (P/'W18-W10-FINAL-NOTE.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--render-only',action='store_true')
    args=parser.parse_args()
    render_cached() if args.render_only else run()
