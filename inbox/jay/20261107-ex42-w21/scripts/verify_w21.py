"""Re-read closed sources and independently check W21 cost and condition claims."""
import ast
import hashlib
import json
import re
import statistics
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'data/w21_evidence.json').read_text(encoding='utf-8'))


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def match_stats(values, saved):
    assert saved['n']==len(values)
    for name,value in [('min',min(values)),('median',statistics.median(values)),('max',max(values)),('sum',sum(values))]:
        assert abs(saved[name]-value)<1e-7, (name,saved[name],value)


def main():
    for p,sha in d['source_sha256'].items():
        assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha,p
    assert [r['iteration'] for r in d['map_documents']]==list(range(250,6001,250))
    for r in d['map_documents']:
        raw=load(r['path'])
        assert 'dr' not in raw
        assert sorted(raw['dr_off'])==['add_base_mass','physics_material']
        assert set(raw['modes'])=={'eval_gt','eval_pred','probe_prop_only'}
        assert all(len(v)==13 for v in raw['modes'].values())
        assert all(not any(k.startswith('dr_') for k in cell)
                   for field in ['modes','sequences'] for mode in raw[field].values() for cell in mode.values())
    times=[]
    for r in d['map_receipts']:
        if r['iteration'] not in d['map_cost_latest5_iterations']: continue
        raw=load(r['path']); step=raw['steps']['map64']
        assert raw['device']=='cuda:1' and step['rc']==0
        assert r['seconds']==step['seconds']
        times.append(step['seconds'])
    match_stats(times,d['map_cost_latest5_s'])
    qtimes=[]; ctimes=[]
    for r in d['video_rows']:
        raw=load(r['queue_result']); receipt=load(r['receipt']); review=load(r['review'])
        assert Path(raw['last_json']['receipt'])==Path(r['receipt'])
        assert raw['rc']==0 and receipt['own_result']=='success'
        assert receipt['checkpoint_sha256']==r['checkpoint_sha256']
        assert 'Using device: cuda:1' in Path(r['child_log']).read_text(encoding='utf-8')
        assert review['duration_s']==6
        assert raw['ended']>raw['started']
        qtimes.append(raw['ended']-raw['started']); ctimes.append(review['capture_wall_elapsed_s'])
    match_stats(qtimes,d['video_queue_cost_s']); match_stats(ctimes,d['video_capture_cost_s'])
    linked=[]
    for name,x in d['excerpts'].items():
        p=Path(x['path']); root=next(Path(r) for r in d['source_heads'] if p.is_relative_to(Path(r)))
        rel=p.relative_to(root).as_posix(); head=d['source_heads'][str(root)]
        blob=subprocess.check_output(['git','-C',str(root),'show',head+':'+rel]).decode('utf-8')
        assert blob.replace('\r\n','\n')==p.read_text(encoding='utf-8-sig').replace('\r\n','\n'),name
        linked.append(name)
    report=(ROOT/'EVIDENCE-W21-N2-N17-N21-1107.md').read_text(encoding='utf-8')
    assert '\u2014' not in report
    assert all(line.startswith('> ') for line in report.splitlines()[:5])
    tables=[]; counts=[]
    for line in report.splitlines()+['']:
        if line.startswith('|'):
            counts.append(len(re.split(r'(?<!\\)\|',line))-2)
        elif counts:
            assert len(set(counts))==1,counts
            tables.append({'rows':len(counts),'columns':counts[0]}); counts=[]
    result={'status':'PASS','source_hashes':len(d['source_sha256']),
            'map_documents':24,'map_cost_receipts':5,'video_receipt_joins':len(qtimes),
            'pinned_source_files':len(linked),'markdown_tables':tables,
            'dr_guard_known_inputs':d['guard_known_input'],
            'limit':'No GPU/Kit; timing proxy, not a new N2/N21 run; no video-content adjudication.'}
    (ROOT/'data/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
