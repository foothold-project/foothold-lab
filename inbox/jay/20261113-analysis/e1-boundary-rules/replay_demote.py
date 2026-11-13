"""Recompute the three authorized real known inputs without writing the run."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

from boundary_demote import read_review, write_review, summary
from boundary_read import RUN, CODE


def replay(out):
    out=Path(out).resolve()
    if 's2_lab' in out.parts:
        raise ValueError('replay output must be outside experiment data')
    rows=[];sources={}
    for n in (250,500,750):
        data=read_review(RUN/f'eval/scores/m{n}/ex42_score.json',RUN,CODE)
        if data['state']=='HOLD':
            raise ValueError('known actual boundary became incomplete: '+summary(data))
        write_review(data,out/f'm{n}')
        sources.update(data['run_sources']);sources.update(data['reader_sources'])
        for snap in data['history']:
            sources.update(snap['sources']);sources.update(snap['audit_sources'])
        forward=next(r for r in data['cells'] if r['cell']=='low/L0/fwd0.1/R')
        expected='FIRST_BOUNDARY' if n==250 else 'DEMOTE'
        if forward['state']!=expected:
            raise AssertionError(f'm{n}: expected {expected}, got {forward["state"]}')
        rows.append(dict(iteration=n,state=data['state'],demoted_count=len(data['demoted_cells']),
                         forward_L0_01=forward,off=data['map_off_survival']))
        print(summary(data))
    # Cross-check against the independently archived raw/NPZ answers, not rounded chat values.
    if abs(rows[1]['forward_L0_01']['eval_gt']['adverse_delta']-.13472863091980494)>1e-9:
        raise AssertionError('m250->m500 known GT decline differs')
    if not 0<rows[1]['forward_L0_01']['eval_pred']['adverse_delta']<.10:
        raise AssertionError('same-direction smaller PRED decline differs')
    result=dict(format='analyst-e1-demotion-known-inputs/1',run_root=str(RUN),code_root=str(CODE),
                rows=rows,sources=sources)
    (out/'known_inputs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['# 경계 내림 실제 점수 재생','> 분류: A/평가',
           f'> 작성: analyst-lx · {datetime.now():%Y-%m-%d %H:%M}',
           '> 근거: a76e783d · 동일 run m250/m500/m750 원자료·P1·NPZ',
           '> 요지: m250→m500 전진0.1 GT 하락 0.135의 DEMOTE 재현',
           '> 상태: CPU 실측 · 이 과거 시험 구간에 새 규칙을 적용한 재생, 당시 결정 소급 변경 아님','',
           '| 경계 | 전체 상태 | 내림 칸 수 | 전진0.1 GT R | GT 최고 대비 하락 | PRED R | PRED 최고 대비 하락 | 끔 생존 최솟값 |',
           '|---|---|---|---|---|---|---|---|']
    for r in rows:
        gt=r['forward_L0_01']['eval_gt'];pred=r['forward_L0_01']['eval_pred']
        minimum=min(x['survival'] for x in r['off']['items'])
        lines.append(f'| m{r["iteration"]} | {r["state"]} | {r["demoted_count"]} | '
                     f'{gt["value"]:.6f} | {gt["adverse_delta"]:.6f} | {pred["value"]:.6f} | '
                     f'{pred["adverse_delta"]:.6f} | {minimum}/64 |')
    lines += ['', 'GT와 PRED의 최고값은 모두 m250이다. m750은 직전 m500만 보지 않고 m250과 비교했다.',
              'm500 지도 끔 back1.0은 63/64이고 다른 20칸은 64/64다. m250·m750은 21칸 모두 64/64다.',
              '문턱 근거는 동일 저장본 세 시드 범위로 원장에 고정된 값이며 통계적 유의확률이나 원인 확정이 아니다.',
              '전체 18칸·출처 SHA는 m250/DEMOTE.md, m500/DEMOTE.md, m750/DEMOTE.md와 각 demotion.json에 있다.', '',
              '재현: `python replay_demote.py --out <저장소 밖 결과 폴더>` (isaac311, CPU 환경).']
    (out/'KNOWN-INPUTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    paths=sorted(p for p in out.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in paths),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    replay(p.parse_args().out)
