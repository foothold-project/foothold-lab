"""Reproduce real E1-again m250/m500 reports without writing the run."""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
from collections import Counter
from boundary_read import run,RUN,PARENT,CODE


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--iterations',type=int,nargs='+',default=[250,500])
    p.add_argument('--effective-from',type=int,choices=(750,1000),default=1000)
    p.add_argument('--c1-code-root',type=Path);a=p.parse_args()
    rows=[]
    for n in a.iterations:
        out=a.out/f'm{n}'
        d=run(RUN/f'eval/scores/m{n}/ex42_score.json',PARENT,RUN,CODE,out,
              c1_code_root=a.c1_code_root,effective_from=a.effective_from)
        audit=d['approved_table']['current'];off=d['decision']['map_off_survival'];c=d['curves']['current']
        rows.append(dict(iteration=n,score=d['current']['score_path'],checkpoint_sha256=d['current']['checkpoint_sha256'],
            report=str(out/'report.json'),report_sha256=hashlib.sha256((out/'report.json').read_bytes()).hexdigest(),
            original=d['original_rule_decision']['rule'],off_state=off['state'],off_n=len(off['items']),
            off_non64=[r for r in off['items'] if r['survival']!=64],
            low={k:v for k,v in d['current']['metrics'].items() if k.startswith('low/') and '/fwd' in k and k.endswith('/R')},
            diagnostic_counts=dict(Counter(r['interpretation'] for r in d['decision']['GT_PRED_diagnosis'])),
            lr_floor_count=c['lr_floor_count'],lr_n=c['lr_n'],lr_floor_fraction=c['lr_floor_fraction'],
            kl_probe_spikes=c['kl_probe_spikes'],kl_probe_n=c['kl_probe_n'],
            core_source_errors=audit['errors'],wide_missing=audit.get('wide_errors'),
            sources=audit['sources'],curve_sources=d['curves']['sources']))
    text=['# E1 m250·m500 새 승인표 재계산',
          '> 분류: A/평가',f'> 작성: analyst-lx · {datetime.now():%Y-%m-%d %H:%M}',
          '> 근거: 원장 de8a3b7f · 5f2e7c3b · 7ba9f2be · P1 JSON/NPZ · tfevents 바이트 사본',
          '> 요지: 과거 경계는 기록용 재계산, 운영 결과와 처방은 변경하지 않음',
          '> 상태: CPU 실측 · C1 추가 Kit 칸 미측정','',
          '| 경계 | 기존 규칙 | 끔 생존 | 64 미만 칸 | lr 바닥/창 | 진단 KL >0.02/창 |',
          '|---|---|---|---|---|---|']
    for r in rows:
        below=' · '.join(f'{x["cell"]} {x["survival"]}/{x["valid"]}' for x in r['off_non64']) or '없음'
        text.append(f'| m{r["iteration"]} | {r["original"]} | {r["off_state"]} ({r["off_n"]}칸) | {below} | {r["lr_floor_count"]}/{r["lr_n"]} ({r["lr_floor_fraction"]:.1%}) | {r["kl_probe_spikes"]}/{r["kl_probe_n"]} |')
    text += ['','| 경계·레벨·속도 | GT R | PRED R | 끔 R (기록) |','|---|---|---|---|']
    for r in rows:
        for lev in (0,5):
            for speed in (.1,.2):
                vals=[r['low'][f'low/L{lev}/{m}/fwd{speed}/R'] for m in ('eval_gt','eval_pred','probe_prop_only')]
                text.append(f'| m{r["iteration"]} L{lev} {speed} | '+' | '.join(f'{v:.6f}' for v in vals)+' |')
    text += ['', '확인됨: source reader가 checkpoint·seed·P1 SHA·원자료 값을 대조했다. 지도 끔의 R은 생존 조건에 쓰지 않는다.',
             '미측정: C1의 고정 L3/L6/L9와 끝점 새 Kit 칸. 이를 기존 저속 칸으로 대체하지 않는다.',
             '진단 KL은 scheduler의 실제 미니배치 KL이 아니다. 곡선 숫자는 경고·기록이며 설정 변경이 아니다.',
             'GT 통과·PRED 미달은 지각 경로 점검 후보, GT 미달은 정책·과제 점검 후보. 원인 확정이 아니다.','']
    text += ['기존 규칙의 m500 KEEP과 실제 다음 처방은 별개다. lead는 23:07 원장의 한 경계 큰 하락 예외로 b2 slow_track 0→0.2를 적용했다. 도구는 이 결정을 취소하거나 소급 바꾸지 않는다.','']
    for r in rows:
        text += [f'm{r["iteration"]}: {r["report"]} · SHA `{r["report_sha256"]}`',
                 f'원자료 오류: {r["core_source_errors"]}. C1: {r["wide_missing"]}.',
                 f'진단 분류: {r["diagnostic_counts"]}.','']
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'DE8-REPLAY.md').write_text('\n'.join(text).rstrip()+'\n')
    (a.out/'DE8-REPLAY.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    print(a.out/'DE8-REPLAY.md')

if __name__=='__main__':main()
