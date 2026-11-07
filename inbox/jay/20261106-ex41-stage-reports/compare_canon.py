"""Read PR #586 pinned source and compare stage-end numbers, not stage-wide minima."""
import csv,json,re,statistics,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).parent;D=ROOT/'data'
REF='5c1f6d6ca45f73837ff98cbc1a0f7feccdd89dc3'
p=subprocess.run(['gh','api',f'repos/foothold-project/foothold-lab/contents/docs/research/20261107-ex41-canon-m12000.md?ref={REF}','-H','Accept: application/vnd.github.raw+json'],capture_output=True,check=True)
text=p.stdout.decode('utf-8-sig');(D/'canon-pr586.txt').write_text(text,encoding='utf-8')
cells=list(csv.DictReader((D/'command_cells.csv').open(encoding='utf-8-sig')))
push=list(csv.DictReader((D/'push_stage_end.csv').open(encoding='utf-8-sig')))
sy=json.loads((D/'w45_evidence.json').read_text(encoding='utf-8'))['symmetry']
rows=[]
for stage,n in [('S2e',5500),('T0′',6000)]:
 line=next(x for x in text.splitlines() if x.startswith(f'| {stage} |'))
 c=[x.strip() for x in line.strip('|').split('|')]
 declared=[int(x) for x in re.findall(r'\d+',c[4])[:3]]
 actual=[sum(float(r['error'])>.15 for r in cells if int(r['iteration'])==n and r['mode']==m) for m in ['eval_gt','eval_pred','probe_prop_only']]
 min_alive=min(int(r['alive']) for r in cells if int(r['iteration'])==n)
 actual_push=[min(float(r['worst_direction_survival_fraction']) for r in push if int(r['iteration'])==n and r['cell'].startswith(t+'/')) for t in ['flat','random_rough','pyramid_stairs']]
 declared_push=[float(x) for x in re.findall(r'\d+\.\d+',c[6])]
 ss=[r['symmetry'] for r in sy if r['iteration']==n and r['mode']=='eval_gt']
 mean=statistics.mean(ss);low=sum(x<.8 for x in ss)
 expected_mean=float(c[7].split()[0]);expected_low=int(re.search(r'미만 (\d+)',c[7]).group(1))
 checks={'exceed_015':actual==declared,'alive':min_alive==int(c[5].split('/')[0]),'push_rounded_3':all(f'{a:.3f}'==f'{b:.3f}' for a,b in zip(actual_push,declared_push)),'S_rounded_2':f'{mean:.2f}'==f'{expected_mean:.2f}','S_below08':low==expected_low}
 assert all(checks.values()),(stage,checks)
 rows.append({'stage':stage,'iteration':n,'source_line':line,'checks':checks,'over_015':actual,'end_min_alive':min_alive,'stage_wide_min_alive':min(int(r['alive']) for r in cells if n-499<=int(r['iteration'])<=n),'push_worst_across_modes':actual_push,'S_mean_gt':mean,'S_below08_gt':low})
out={'pr':'https://github.com/foothold-project/foothold-lab/pull/586','commit':REF,'source_sha256':hashlib.sha256(p.stdout).hexdigest(),'stages':rows,'numeric_disagreements':0,'notes':['Stage-end minimum differs from minimum over all boundaries of a stage; not a numerical disagreement.','Video missing count is time-dependent; current readback is w45_evidence.json, not the prior count 9.','S aggregation does not establish the actual mirror trigger rule.']}
(D/'canon_comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False))
