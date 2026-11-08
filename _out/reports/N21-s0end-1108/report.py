"""Render the checked N21 analysis without manual numeric entries."""
from pathlib import Path
import csv
import hashlib
import json
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'REPORT-analyst-N21-s0end-1108.md'
LABEL={'eval_gt':'정답','eval_pred':'복원','probe_prop_only':'끔'}
T={'flat':'평지','continuous':'연속 7종'}
FIELDS={'vx':'vx 오차','vy':'vy 오차','wz':'yaw 오차','stop_xy':'정지 XY 속도','stop_wz':'정지 yaw 속도'}

def rows(name):
    with (HERE/(name+'.csv')).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))

def f(v): return f'{float(v):.4f}'
def s(v): return f'{float(v):+.4f}'
def integer(v): return str(int(float(v)))
def yes(v): return v is True or v=='True'
def table(headers,data):
    def safe(x): return str(x).replace('|','\\|').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(map(safe,headers))+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(map(safe,r))+' |' for r in data])


def main():
    a=json.loads((HERE/'audit.json').read_text(encoding='utf-8'))
    comp=rows('comparison'); gaps=rows('dr_gaps'); target=rows('target18'); reach=rows('reach_survival')
    errors=[r for r in comp if r['metric']!='alive']; alive=[r for r in comp if r['metric']=='alive']
    assert len(errors)==108 and len(alive)==96 and len(target)==18
    idx={(r['terrain'],r['dr'],r['mode'],r['command']):r for r in alive}
    ridx={(r['terrain'],r['dr'],r['mode'],r['command']):r for r in reach}
    # Two colours for DR state; shape distinguishes checkpoint. Parent bars show the three-seed range.
    parent=json.loads(Path('D:/mai-tmp/analyst/n21-s0end-1108/parent_recheck/audit.json').read_text(encoding='utf-8'))
    pi={(r['terrain'],r['mode'],r['command'],r['metric']):r for r in parent['comparison']}
    fig,axs=plt.subplots(1,2,figsize=(15,7),sharex=True)
    for ax,terrain in zip(axs,['flat','continuous']):
        rr=[r for r in target if r['terrain']==terrain]
        for i,r in enumerate(rr):
            pr=pi[terrain,r['mode'],r['command'],r['metric']]
            for dr,offset,col in [('off',-.13,'#1f648e'),('on',.13,'#ab480d')]:
                y=i+offset
                ax.plot([pr[dr+'_min'],pr[dr+'_max']],[y,y],color=col,lw=3)
                ax.plot([float(r['parent_'+dr+'42']),float(r['endpoint_'+dr+'42'])],[y,y],color=col,lw=1,ls=':')
                ax.scatter(float(r['parent_'+dr+'42']),y,c=col,marker='o',s=36,label='parent '+dr if i==0 else None)
                ax.scatter(float(r['endpoint_'+dr+'42']),y,c=col,marker='X',s=65,label='m13000 '+dr if i==0 else None)
        ax.set_yticks(range(len(rr)),[r['mode'].replace('probe_prop_only','map-off')+' / '+r['command'] for r in rr])
        ax.invert_yaxis(); ax.set_title(terrain+' / L2 / 64 env / 6 seconds')
        ax.set_xlabel('Median alive-sample tracking error (m/s), lower is smaller error')
        ax.grid(axis='x',alpha=.25); ax.legend(loc='upper right',fontsize=8)
    fig.suptitle('N21 target 18 cells: bars = parent seed 42/43/44 range; circle = parent42; X = endpoint42',fontsize=11)
    fig.tight_layout(); fig.savefig(HERE/'target18_errors.png',dpi=160); plt.close(fig)

    tt=a['target18']; changed_alive=[r for r in alive if float(r['delta'])!=0]
    narrower_and_better=[r for r in target if yes(r['gap_smaller']) and yes(r['on_error_smaller'])]
    lines=[
      '> 분류: A/평가 · 일반화 벤치마크 · 지표',
      '> 작성: analyst · '+datetime.now().strftime('%Y-%m-%d %H:%M KST'),
      '> 근거: 원자료 실측 · N21 JSON 16판 및 NPZ '+str(a['npz_checked'])+'개 CPU 재검산 · 부모 시드 42/43/44',
      '> 요지: DR-on 빠른 전진·옆걸음 오차가 더 큰 18칸은 그대로이며, 격차 축소와 실제 오차 감소는 다르다',
      '> 상태: record_only 기록 해석 완료 · 승급/통과 판정 없음 · m13000 시드 반복 미측정',
      '', '# N21 0단계 끝: 부모 m12000과 m13000 비교', '',
      '## 먼저 읽을 결과', '',
      f'**오전 18칸이 줄었는가: 아니오.** 빠른 전진과 양쪽 옆걸음의 {tt["gap_positive"]}/{tt["count"]}칸 모두 m13000에서도 DR-on 오차가 off보다 크고, {tt["gap_above_old_width"]}칸 모두 그 격차가 부모의 시드 폭 W를 넘는다. 다만 격차의 크기는 {tt["gap_smaller"]}칸에서 작아지고 {tt["gap_larger"]}칸에서 커졌다. 이는 통계적 유의성이나 실패 판정이 아니다.', '',
      f'**격차 축소를 강건성 개선으로 읽으면 안 된다.** 축소된 {tt["gap_smaller"]}칸 중 {tt["gap_smaller_but_on_not_smaller"]}칸은 on 오차 자체가 줄지 않았다. off 오차가 더 크게 늘어 간격이 좁아진 것이다. 격차도 줄고 on 오차도 줄어든 것은 '+', '.join(T[r['terrain']]+' '+LABEL[r['mode']]+' '+r['command'] for r in narrower_and_better)+f'의 {len(narrower_and_better)}칸이다. 전체 18칸 중 on 오차 자체가 줄어든 것은 {tt["on_error_smaller"]}칸이다.', '',
      '살아남는 것과 명령을 잘 따르는 것은 다르다. 아래 생존 합은 여러 명령·지도에서 반복한 env-시도 수이며, 독립 로봇 수나 통합 성공률이 아니다. 정지 두 성분을 따로 세므로 조건당 추종 오차는 27성분이다.', '',
      table(['지형','DR','부모 생존 합','m13000 생존 합','오차 감소/증가 성분','부모 폭보다 큰 감소/증가'],
            [[T[r['terrain']],r['dr'],f"{r['parent_alive_sum']}/{r['exposures']}",f"{r['endpoint_alive_sum']}/{r['exposures']}",
              f"{r['error_lower']}/{r['error_higher']}",f"{r['error_lower_over_width']}/{r['error_higher_over_width']}"] for r in a['summary']]), '',
      '## 비교 조건과 실제 검사', '',
      f'- 부모: EX-41 local model_6000, 누적 m12000, SHA `{a["parent_checkpoint"]}`.',
      f'- 이번: EX-42 local model_1000, 누적 m13000, SHA `{a["endpoint_checkpoint"]}`.',
      '- 모든 판: L2 · 64 env · 300 step · dt 0.02 s · 6 s · 대표 8명령 · 지도 셋. 이번 시드는 42 하나다. `n21_point=parent_e0`는 평가 계약 이름이며 저장본이 부모라는 뜻이 아니다. 실제 checkpoint SHA로 구별했다.',
      '- 명령 숫자, 지형 종류와 열·레벨 배정, fixed_terrain, 복원한 지도/추정기 설정이 부모 seed42와 같음을 assert했다. assignment SHA는 종류/레벨 배정 해시다. 지형 메시 높이장 전체의 바이트 동일성은 이 영수증으로 확인할 수 없다.', '',
      table(['지형','DR','부모 seed42 GPU','m13000 GPU','부모 코드','m13000 코드','배정 SHA 앞 12자'],
            [[T[r['terrain']],r['dr'],r['parent_gpu'],r['child_gpu'],r['parent_code_head'][:8],r['child_code_head'][:8],r['assignment_sha256'][:12]] for r in a['protocol']]), '',
      '**교란 조건:** 이번 on/off는 GPU도 다르다. 연속 지형 off는 부모→자식 비교에서도 GPU0→GPU1로 바뀌었다. 부모 seed42와 이번 평가 코드도 같은 HEAD가 아니다. 부모 seed43/44와 이번은 실제 import 모듈 SHA가 전부 같지만, 부모 seed42와는 eval_map_modes·n21_dr_record·start_runner 3모듈이 다르다. [오전 코드 차이](N21-seedwidth-1108/source_diff_d1dfd4f9_to_7916a52.txt)는 off 영수증 지원 및 EX-42 학습/저장 경로 변경을 보인다. 그래도 같은 코드·같은 GPU를 강제한 짝 실험이라고 부르지 않는다. [전체 프로토콜](N21-s0end-1108/protocol.csv).', '',
      'DR-on 실제 질량·마찰 배열은 범위 안이고 부모 seed42와 각 24칸 모두 완전히 같았다. 밀기 seed·시각도 같으며 실제 Δv의 차이는 아래처럼 작지만 바이트까지 같지는 않다. DR-off에는 물리값 readback이 없으므로 설정에서 껐다는 기록 이상을 주장하지 않는다.', '',
      table(['지형','base 질량 kg 최소~최대','정지 마찰 최소~최대','운동 마찰 최소~최대','질량/마찰 동일 칸','부모와 밀기 Δv 최대 차 m/s'],
            [[T[r['terrain']],f"{r['base_mass_range'][0]:.6f}~{r['base_mass_range'][1]:.6f}",
              f"{r['static_range'][0]:.6f}~{r['static_range'][1]:.6f}",f"{r['dynamic_range'][0]:.6f}~{r['dynamic_range'][1]:.6f}",
              f"{r['mass_equal_parent_cells']}/{r['material_equal_parent_cells']}",f"{r['push_max_delta_parent_mps']:.3g}"] for r in a['physical_checks']]), '',
      'DR-on은 마찰만 바꾼 조건이 아니다. 질량·COM·구동기 이득/세기·행동 지연·밀기를 포함하므로 차이를 마찰 하나에 돌릴 수 없다.', '',
      '## 수치의 뜻과 시드 폭', '',
      '- 추종 오차: 각 env에서 첫 종료 전 살아 있는 시간의 절댓값 오차를 평균하고, 64개 env 값의 중앙값을 구했다. 전진/후진은 vx, 옆걸음은 vy, 회전은 yaw를 본다. 정지는 XY 속도(m/s)와 yaw 속도(rad/s)를 따로 본다.',
      '- 생존: 300스텝 끝의 `alive_end` 합. 도중 죽은 env의 오차도 죽기 전 자료로 계산되므로 오차가 낮아도 생존이 나쁠 수 있다. 그래서 두 열을 따로 남긴다.',
      '- 조건별 폭 w = 부모 seed42/43/44 최댓값−최솟값. Δ = m13000(seed42)−부모(seed42). `Δ폭밖`은 abs(Δ)>w이다. `값범위밖`은 이번 값이 부모 최솟값~최댓값 바깥이라는 별개 뜻이다. 둘을 혼동하지 않게 전부 기록했다.',
      '- 오전 18칸의 DR 격차 비교는 원래 정의 그대로 W=max(w_on,w_off), g=오차_on−오차_off를 쓴다. 이번 g와 부모의 3개 g 범위도 CSV에 남겼다.',
      '- 세 시드의 최솟값~최댓값은 신뢰구간이 아니다. 평가 시드 변경은 초기 상태·지형 생성·DR 표본을 함께 바꾸며, 학습 시드 일반화가 아니다. 새 저장본은 반복 측정이 없어 변동폭을 모른다. 부모 폭이 0인 생존도 실제 실패 확률이 0이라는 뜻은 아니다.', '',
      '## 오전에 짚은 18칸', '',
      '단위는 모두 m/s. off/on 숫자를 나란히 두어 격차 축소가 어느 쪽 변화에서 왔는지 보인다. Δg가 음수면 격차 축소다. 모든 행에서 이번 g>W지만 이를 통과/실패 문턱으로 쓰지 않는다.', '',
      table(['지형','지도','명령','부모 off/on','m13000 off/on','부모 g','이번 g','Δg','부모 W'],
            [[T[r['terrain']],LABEL[r['mode']],r['command'],f(r['parent_off42'])+'/'+f(r['parent_on42']),
              f(r['endpoint_off42'])+'/'+f(r['endpoint_on42']),f(r['parent_gap42']),f(r['endpoint_gap42']),s(r['gap_change']),f(r['parent_width_max'])] for r in target]), '',
      '![18칸의 부모 시드 범위와 m13000 오차](N21-s0end-1108/target18_errors.png)', '',
      '그림: 가로 굵은 선은 부모 세 시드의 범위, 동그라미는 부모 seed42, X는 m13000 seed42. 파랑은 DR-off, 갈색은 DR-on이다.', '',
      '## 생존 변화가 있는 칸', '',
      f'전체 {len(alive)}칸 중 seed42 부모 대비 생존 수가 바뀐 {len(changed_alive)}칸만 아래에 펼쳤다. 나머지는 전체 표/CSV에 같은 값으로 남겼다.', '',
      table(['지형','DR','지도','명령','부모→이번 /64','부모 3시드 범위','Δ폭밖','값범위밖'],
            [[T[r['terrain']],r['dr'],LABEL[r['mode']],r['command'],integer(r['parent42'])+'→'+integer(r['endpoint42']),
              integer(r['parent_min'])+'~'+integer(r['parent_max']),'예' if yes(r['delta_exceeds_width']) else '아니오',
              '예' if yes(r['outside_parent_range']) else '아니오'] for r in changed_alive]), '',
      '## 성분별 전체 표', '',
      'Δ는 이번−부모이므로 오차에서 음수는 감소, 양수는 증가다. 생존은 각 /64. 정지 두 성분 때문에 동일 생존이 두 행에 반복된다. 속도와 각속도의 값을 더하지 않는다. [전체 vx/vy/yaw 288성분](N21-s0end-1108/all_axis_components.csv)에는 명령 주축 이외의 오차도 보존했다.', '',
    ]
    for terrain in ['flat','continuous']:
      for dr in ['off','on']:
        rr=[r for r in errors if r['terrain']==terrain and r['dr']==dr]
        lines += ['### '+T[terrain]+' · DR-'+dr, '',
          table(['지도','명령·성분','단위','생존 부모→이번','오차 부모→이번','Δ','부모 범위','w','Δ폭밖/값범위밖'],
           [[LABEL[r['mode']],r['command']+' · '+FIELDS[r['metric']],r['unit'],
             integer(idx[terrain,dr,r['mode'],r['command']]['parent42'])+'→'+integer(idx[terrain,dr,r['mode'],r['command']]['endpoint42']),
             f(r['parent42'])+'→'+f(r['endpoint42']),s(r['delta']),f(r['parent_min'])+'~'+f(r['parent_max']),f(r['parent_width']),
             ('예' if yes(r['delta_exceeds_width']) else '아니오')+'/'+('예' if yes(r['outside_parent_range']) else '아니오')] for r in rr]),'']
    lines += ['## 오전의 기준선 도달 성분도 같은 기준으로 보존', '',
      '오전 parent DR-off seed42의 env별 오차 중앙값을 각 칸의 설명용 기준으로 고정했다. 이번 off 중앙값으로 기준을 다시 만들지 않았다. 정지는 두 성분이 모두 기준 이하일 때 도달이다. 이는 승인된 성공률이나 새 관문이 아니다. [96칸의 기준선 도달·생존·교집합](N21-s0end-1108/reach_survival.csv)을 모두 저장했다. 죽기 전 잠깐 낮은 오차를 낸 env도 도달에 들 수 있으므로 교집합과 생존을 분리했다.', '',
      table(['지형','DR','기준선 도달 부모→이번','끝 생존 부모→이번','두 조건 모두 부모→이번'],
       [[T[t],c]+[str(sum(int(r['parent_'+k]) for r in reach if r['terrain']==t and r['dr']==c))+'→'+str(sum(int(r['endpoint_'+k]) for r in reach if r['terrain']==t and r['dr']==c)) for k in ['reached','alive','both']] for t in ['flat','continuous'] for c in ['off','on']]), '',
      '## 쉬운 map64 및 어려운 지형 결과와 연결', '',
      'lead decisions.tsv 20:2x·20:3x 기록은 쉬운 map64에서 옆걸음 오차 증가, 어려운 L3~L5의 빠른 전진에서 복원·끔 오차 감소를 보고했다. 이번 N21에서도 평지 양쪽 옆걸음의 오차는 세 지도·on/off에서 모두 부모보다 크다. 연속 지형 L2에서는 특히 side−가 세 지도·on/off에서 모두 커졌다. 반면 빠른 전진 끔의 오차는 평지·연속 지형 on/off에서 모두 작아졌다. 이 방향은 서로 다른 기술/조건의 변화가 섞여 있음을 보여준다.', '',
      '**비교 한계:** 어려운 지형 기록은 여기서 새로 재계산한 결과가 아니다. [lead 원문 발췌](N21-s0end-1108/lead_context.txt)는 출처로만 보존했다. map64·L3~L5·N21 L2는 명령 묶음·지형 난이도·DR·GPU 조건이 다르므로 합쳐 성공률을 만들거나, 지각 개선이 옆걸음 저하의 원인이라고 말할 수 없다. 발 위상·미끄럼·발 들기·보상 원인은 이번 자료만으로 미확인이다.', '',
      '## 재현·검증과 남은 한계', '',
      f'- 답을 아는 입력 {a["known_answer_tests"]}개 통과: 중앙값, 폭과 경계값, 범위밖과 폭밖 구별, NaN 거절, 격차 축소와 on 개선 구별, 도달과 생존 분리.',
      f'- 부모 {a["parent_recheck"]["npz_count"]}개 + 이번 {a["npz_checked"]-a["parent_recheck"]["npz_count"]}개 = NPZ {a["npz_checked"]}개를 다시 열어 회차/시드/장치/코드 정체성, alive_end, alive 시간 합, 단조 종료를 확인. 이번 모든 칸의 vx 오차는 NPZ에서 재계산해 JSON과 atol 2e-6으로 대조했다.',
      '- vy·yaw 원시 시계열은 이 NPZ에 없다. 해당 값은 JSON의 64개 env별 집계에서 재집계했으며, 시뮬 원시 프레임부터 독립 재계산한 것은 아니다. 영상은 이번에 새로 보지 않았다.',
      '- 6초 안에서의 거동만 보인다. 장시간 넘어짐률·미경험 지형 일반화·장기 회복·인과는 확인할 수 없다. 2초 밀기는 정지 측정 창과 겹치므로 정지 오차도 외란 포함 값이다.',
      '- 보고서에는 원자료로 계산한 수치를 썼다. [audit.json](N21-s0end-1108/audit.json)에 원자료 경로·SHA·환경 계약을, [SHA256SUMS](N21-s0end-1108/SHA256SUMS)에 산출 해시를 남겼다. 소스·프로세스·운영 원장·GPU는 변경하지 않았다.', '',
      '```powershell',
      "$env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'",
      "& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' '_out/reports/N21-s0end-1108/analyze.py'",
      "& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' '_out/reports/N21-s0end-1108/report.py'",
      '```', '',
      '기존 정의: [오전 N21 판독](REPORT-analyst-N21-1108.md) · [부모 세 시드 폭](REPORT-analyst-N21-seedwidth-1108.md).', '']
    # Assert prose summaries from the numbers instead of relying on manual claims.
    def direction(terrain,commands,drs,modes,sign):
        rr=[r for r in errors if r['terrain']==terrain and r['command'] in commands and r['dr'] in drs and r['mode'] in modes]
        assert rr and all(float(r['delta'])*sign>0 for r in rr)
    direction('flat',['side+0.5','side-0.5'],['off','on'],list(LABEL),1)
    direction('continuous',['side-0.5'],['off','on'],list(LABEL),1)
    for terrain in T: direction(terrain,['fwd1.0'],['off','on'],['probe_prop_only'],-1)
    text='\n'.join(lines)
    assert '\u2014' not in text
    OUT.write_text(text,encoding='utf-8',newline='\n')
    src=Path('D:/mai-wt/foothold-lab/lead-worklist-1103/inbox/jay/20261104-ex41-restart/decisions.tsv')
    selected=[(n,x) for n,x in enumerate(src.read_text(encoding='utf-8-sig').splitlines(),1) if '20:2x' in x or '20:3x' in x]
    selected=[(n,x) for n,x in selected if 'm13000' in x]
    (HERE/'lead_context.txt').write_text('Source: '+str(src)+'\nSHA256: '+hashlib.sha256(src.read_bytes()).hexdigest()+'\n'+'\n'.join(str(n)+': '+x for n,x in selected)+'\n',encoding='utf-8',newline='\n')
    assert len(selected)==2,selected
    files=[p for p in HERE.iterdir() if p.is_file() and p.name!='SHA256SUMS']+[OUT]
    (HERE/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(HERE.parent).as_posix()+'\n' for p in sorted(files)),encoding='utf-8',newline='\n')
    print(json.dumps({'report':str(OUT),'lines':len(lines),'primary_error_rows':len(errors),'survival_rows':len(alive),'prose_direction_assertions':'PASS'},ensure_ascii=False))


if __name__=='__main__': main()
