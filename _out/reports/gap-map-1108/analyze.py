"""Read-only C-layer audit. No Isaac/torch/GPU import. Issue #555."""
import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import numpy as np

OUT = Path(__file__).parent
SRC = Path('D:/mai-wt/foothold-lab/canon216-m12000-gpu0')
OLD = Path('D:/mai-tmp/scripter/c76_all216_1105/manifest.json')
ROOTS = [Path('D:/mai-tmp/lead/canon216_m12000') / p for p in ('out', 'out_gpu1')]
MODES = ('eval_gt', 'eval_pred', 'probe_prop_only')

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(name, obj): (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
def write_csv(name, rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)

def parse_cell(s):
    m=re.fullmatch(r'(gaps|balance_beams)_L([0-5])_(eval_gt|eval_pred|probe_prop_only)',s)
    return (m[1],int(m[2]),m[3]) if m else None

def map_metrics(gt, pred):
    """GT pit/support contrast, not global MAE alone. Frames with both surfaces."""
    g=gt.reshape(len(gt),-1); p=pred.reshape(len(pred),-1)
    top=np.quantile(g,.9,axis=1)
    pit=g < top[:,None]-.10
    support=np.abs(g-top[:,None])<.02
    valid=(pit.sum(1)>=4)&(support.sum(1)>=32)
    gd=[]; pd=[]; pe=[]
    for i in np.flatnonzero(valid):
        gd.append(float(np.median(g[i,support[i]])-np.median(g[i,pit[i]])))
        pd.append(float(np.median(p[i,support[i]])-np.median(p[i,pit[i]])))
        pe.extend(np.abs(p[i,pit[i]]-g[i,pit[i]]).tolist())
    return dict(map_frames=len(g),pit_visible_frames=int(valid.sum()),
                gt_pit_contrast_m=float(np.median(gd)) if gd else None,
                pred_pit_contrast_m=float(np.median(pd)) if pd else None,
                pit_mae_m=float(np.mean(pe)) if pe else None,
                global_mae_m=float(np.mean(np.abs(p-g))),
                gt_span95_m=float(np.median(np.maximum(np.quantile(abs(g-np.median(g,axis=1)[:,None]),.95,axis=1),.05))),
                maps_finite=bool(np.isfinite(g).all() and np.isfinite(p).all()))

def trial(model, cell, rp, selected, metadata=None):
    r=read(rp); npz=rp.parent/'review_feet.npz'; a=read(rp.parent.parent/'attempt.json')
    kind,lv,mode=parse_cell(cell)
    with np.load(npz,allow_pickle=False) as n:
        pos=n['root_pos_w']; done=n['done'].astype(bool); dt=float(n['dt'])
        term=done & ~n['time_out'].astype(bool)
        stop=int(np.flatnonzero(done)[0])+1 if done.any() else len(pos)
        first=pos[:stop]
        # First episode, first assigned 8 m tile only for map reconstruction comparison.
        col=int(r['task_selection']['col']); offset=np.array([lv*8-40,col*8-200])
        local=first[:,:2]-offset
        map_n=min(stop,len(n['gt_map']))
        mask=(local[:map_n,0]>=0)&(local[:map_n,0]<8)&(local[:map_n,1]>=2)&(local[:map_n,1]<6)
        # No spatial remap: pre-step maps and pose share the same recorder step.
        mm=map_metrics(n['gt_map'][:map_n][mask],n['refined_map'][:map_n][mask]) if mask.any() else {}
        row=dict(model=model,cell=cell,kind=kind,level=lv,mode=mode,seed=r['seed'],
                 ordinal=a['ordinal'],selected=selected,receipt_result=a.get('result'),
                 steps=len(pos),duration_s=len(pos)*dt,reset_count=int(done.sum()),
                 non_timeout_done=int(term.sum()),survived_full=not bool(term.any()),
                 first_episode_s=stop*dt,first_episode_dx_m=float(first[-1,0]-first[0,0]),
                 first_episode_max_dx_m=float(np.max(first[:,0]-first[0,0])),
                 first_episode_max_tile_x_m=float(local[:,0].max()),
                 first_episode_reached_tile_goal_x7=bool((local[:,0]>=7).any()),
                 first_episode_left_assigned_tile=bool((local[:,0]>=8).any()),
                 start_x=float(pos[0,0]),start_y=float(pos[0,1]),
                 map_gt_fraction=float(np.mean(n['map_use_gt'])),
                 contact_force_recorded=any('force' in k for k in n.files),
                 **mm,review=str(rp),npz=str(npz),npz_sha256=sha(npz),
                 receipt_sha_matches=sha(npz)==a['files']['review_feet.npz'],
                 review_sha_matches=sha(rp)==a['files']['review.json'],
                 recorder_root=r['measurement_recorder']['source_root'],
                 checkpoint=r['checkpoint'],checkpoint_sha=r.get('checkpoint_sha256'))
    return row

def geometry():
    spec=importlib.util.spec_from_file_location('start_sheet_cpu',SRC/'foothold_s2/eval/start_sheet.py')
    ss=importlib.util.module_from_spec(spec); spec.loader.exec_module(ss)
    draws=np.random.default_rng(20261026).uniform(size=(50,10))
    rows=[]
    for kind,col in [('gaps',45),('balance_beams',35)]:
        for lv in range(6):
            difficulty=(lv+draws[col,lv])/10
            seed=int.from_bytes(hashlib.sha256(('%s|%.12f'%(kind,difficulty)).encode()).digest()[:8],'little')
            geom=ss.generate(kind,lv,np.random.default_rng(seed))
            r=dict(kind=kind,level=lv,col=col,difficulty=float(difficulty),seed=seed,depth_m=geom.depth,params=geom.params,
                   support_boxes=geom.boxes[geom.supports].tolist())
            if kind=='gaps':
                p=geom.params['platform_length']; g=geom.params['gap_width']
                r['gap_intervals_x']=[[1+(i+1)*p+i*g,1+(i+1)*(p+g)] for i in range(3)]
            rows.append(r)
    return rows

def tests():
    g=np.zeros((2,32,16)); g[:,10:12]=-.4
    out=map_metrics(g,g.copy()); assert abs(out['pred_pit_contrast_m']-.4)<1e-12 and out['pit_mae_m']==0
    out=map_metrics(g,np.zeros_like(g)); assert out['pred_pit_contrast_m']==0 and abs(out['pit_mae_m']-.4)<1e-12
    g[:]=0; assert map_metrics(g,g)['pit_visible_frames']==0
    assert parse_cell('gaps_L6_eval_gt') is None
    assert parse_cell('balance_beams_L5_probe_prop_only')==('balance_beams',5,'probe_prop_only')
    print('known-input checks: 5 PASS')

def main():
    tests(); rows=[]; coverage=[]; errors=[]
    old=read(OLD)['cells']
    for c in old:
        if parse_cell(c['cell']):
            rows.append(trial('EX40_m6000',c['cell'],Path(c['review']),True))
    for root in ROOTS:
        for cell_dir in sorted((root/'attempts').glob('*')):
            if not parse_cell(cell_dir.name): continue
            receipt=root/'receipts'/f'{cell_dir.name}_success.json'
            selected=read(receipt).get('attempt_dir') if receipt.exists() else None
            for rp in sorted(cell_dir.glob('*/*/review.json')):
                if not (rp.parent.parent/'attempt.json').exists():
                    errors.append(dict(path=str(rp),reason='no completed attempt receipt')); continue
                try: rows.append(trial('EX41_m12000',cell_dir.name,rp,selected is not None and Path(selected)==rp.parent.parent))
                except Exception as e: errors.append(dict(path=str(rp),reason=repr(e)))
    for model in ('EX40_m6000','EX41_m12000'):
        for kind in ('gaps','balance_beams'):
            for lv in range(6):
                for mode in MODES:
                    rr=[r for r in rows if (r['model'],r['kind'],r['level'],r['mode'])==(model,kind,lv,mode)]
                    coverage.append(dict(model=model,cell=f'{kind}_L{lv}_{mode}',raw_trials=len(rr),selected=sum(r['selected'] for r in rr),
                                         first_goal=sum(r['first_episode_reached_tile_goal_x7'] for r in rr),full_survival=sum(r['survived_full'] for r in rr)))
    dump('trials.json',rows); dump('coverage.json',coverage); dump('errors.json',errors); dump('geometry.json',geometry())
    write_csv('trials.csv',rows); write_csv('coverage.csv',coverage)
    print(json.dumps(dict(trials=len(rows),cells=sum(c['raw_trials']>0 for c in coverage),missing=[c for c in coverage if not c['raw_trials']],errors=errors,
                          hash_failures=sum(not r['receipt_sha_matches'] or not r['review_sha_matches'] for r in rows)),ensure_ascii=False))
    for r in rows:
        if r['cell'].startswith('gaps_L0'): print({k:r[k] for k in ('model','mode','seed','ordinal','selected','survived_full','first_episode_max_dx_m','pit_visible_frames','gt_pit_contrast_m','pred_pit_contrast_m','pit_mae_m')})

if __name__=='__main__': main()
