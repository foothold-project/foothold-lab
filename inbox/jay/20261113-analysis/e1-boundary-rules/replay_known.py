"""Regenerate the three requested known-answer runs, without any simulator."""
import json
from pathlib import Path
from datetime import datetime
from boundary_read import run,PARENT,RUN,CODE
from boundary_rules import LOW_KEYS

def main():
    root=Path(__file__).resolve().parent
    old=Path('/home/jay/data/foothold/s2_lab/ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150')
    jobs=[('known-parent-self',PARENT,0,None,False)]+[(f'known-cmd7seg-m{n}',old/f'eval/scores/m{n}/ex42_score.json',n,
         Path(f'/home/jay/data/foothold/s2_lab/hipan_g1_20261112/m{n}seg'),True) for n in (500,750)]
    summary={}
    for name,source,n,low,historical in jobs:
        r=run(source,PARENT,RUN,CODE,root/name,iteration=n,legacy_low=low,historical=historical)
        expected={0:'BASELINE_ONLY',500:'EVIDENCE_HOLD',750:'EVIDENCE_HOLD'}[n]
        assert r['decision']['rule']==expected,(name,r['decision'])
        assert not r['current']['errors'] and not r['treatment']['errors'],name
        if n==0:assert all(x['parent_delta']==0 for x in r['comparisons'])
        if n:
            missing=r['decision'].get('missing',[])
            assert sum('eval_pred/fwd' in key for key in missing)==4,missing
            assert r['decision']['changes']=={}
            assert json.loads((root/name/'adjustment.draft.json').read_text())['payload'] is None
        summary[name]={
            'score':str(source),'score_sha256':r['current']['sources'][str(source)],
            'rule':r['decision']['rule'],'triggered':r['decision']['triggered'],
            'changes':r['decision']['changes'],'rows':len(r['comparisons']),
            'low':{k:r['current']['metrics'].get(k) for k in LOW_KEYS},
            'missing':r['decision'].get('missing',[]),
            'parent_condition_mismatches':len(r['parent_condition_mismatches']),
            'consumer_validation':r['consumer_validation'],
            'historical_counterfactual':historical}
        print((root/name/'next_segment.txt').read_text().strip())
    out=dict(created_at=datetime.now().astimezone().isoformat(),known_answers=summary)
    (root/'validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return out

if __name__=='__main__':main()
