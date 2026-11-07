"""CPU-only W45 supplemental evidence; independent arithmetic from source rows."""
import re, math, statistics, json, hashlib
from pathlib import Path
from datetime import datetime
from generate_reports import RUN, TRAIN, MODES, read, raw, dump, SOURCES, csvout

OUT=Path(__file__).parent; DATA=OUT/'data'

def symmetry(left,right):
    return min(left,right)/max(left,right) if max(left,right)>0 else None

def collect():
    assert symmetry(.6,.8)==.7499999999999999
    assert symmetry(0,0) is None
    result={'captured_at':datetime.now().astimezone().isoformat(),'stages':{},'symmetry':[], 'map_usage':[]}
    for n in [5000,5250,5500,5750,6000]:
        score=read(next((RUN/'eval/scores').glob(f'score_{n}_*.json')))
        ev=[e for e in score['evidence'] if e['path'].replace('\\','/').endswith('/map64/map_modes.json')][0]
        doc=read(ev['path']);assert SOURCES[str(Path(ev['path']))]['sha256']==ev['sha256']
        for mode in MODES:
            pairs=score['metrics']['critic_mirror_symmetry']['modes'][mode]
            for name,row in pairs.items():
                if name.startswith('map64/'):
                    left,right=[] ,[]
                    for values,case in zip([left,right],row['source_cases']):
                        cell=doc['modes'][mode][case];speed=math.hypot(*cell['command'][:2])
                        for e in cell['per_env']:
                            values.append(e['yaw_follow_mean_alive']*e['samples_alive']/doc['steps'] if name=='map64/spin' else e['command_xy_projection_integral_m']/(speed*doc['steps']*doc['policy_dt_s']))
                    l,r=statistics.median(left),statistics.median(right)
                else:
                    match=re.fullmatch(r'w78/L(\d+)_a(\d+)_(.+)',name);level,angle,kind=match.groups()
                    cells=score['metrics']['w78_v2_periodic_sides']['cells'][mode]
                    values=[]
                    for side in ['left','right']:
                        cell=cells[f'L{level}_a{angle}_stairs_side_{side}']
                        per=[e for e in cell['per_env'] if e['kind']==kind]
                        # First/only scheduled side-motion phase, includes early-terminated envs.
                        v=[e['movement_phases'][0]['distance_projected_m']/e['movement_phases'][0]['planned_distance_m'] for e in per]
                        values.append(statistics.median(v))
                    l,r=values
                s=symmetry(l,r)
                assert abs(l-row['left'])<1e-10 and abs(r-row['right'])<1e-10,(n,mode,name,l,r,row)
                assert abs(s-row['symmetry'])<1e-10
                result['symmetry'].append({'iteration':n,'mode':mode,'pair':name,'left':l,'right':r,'symmetry':s,'below_08':s<.8,'source':str(next((RUN/'eval/scores').glob(f'score_{n}_*.json'))),'pointer':f'/metrics/critic_mirror_symmetry/modes/{mode}/{name}'})
        if n not in [5500,6000]:continue
        root=next((RUN/'eval/score-watch').glob(f'model_{n}_*'))
        pushroot=root/'stage_end_auxiliary_eval/push_ladder'
        rec=read(pushroot/'eval_receipt.json');bundle=read(pushroot/'push_ladder/push_ladder_bundle.json')
        logs=[]
        for p in sorted((pushroot/'push_ladder').glob('*.log')):
            txt=raw(p).decode('utf-8',errors='replace')
            for ln,line in enumerate(txt.splitlines(),1):
                if 'Using device:' in line: logs.append({'source':str(p),'line':ln,'text':line});break
        argv=rec['steps']['push_ladder']['argv'];dev=argv[argv.index('--device')+1]
        assert logs and all(dev in x['text'] for x in logs)
        p=Path('C:/Users/AI-WS01/s2_lab/_playlists')/f'EX41-m{n:05d}-all.m3u8'
        paths=[Path(x) for x in raw(p).decode('utf-8-sig').splitlines() if x and not x.startswith('#')]
        vd=Path('D:/mai-tmp/runner/ex41_stage_video')/f'model_{n}_{score["checkpoint_sha256"][:12]}'
        # Inventory expected stage cases from original stage job directories, not from the number of files alone.
        attempts=sorted(x for x in (vd/'attempts').glob('*/*/*') if x.is_dir() and x.name.startswith('EX41-'))
        expected={re.search(rf'-m{n}-(.+)-1x$',x.name).group(1) for x in attempts}
        published={re.search(rf'-m{n}-(.+)-1x-(?:success|failure)\.mp4$',x.name).group(1) for x in vd.glob('*.mp4')}
        missing=sorted(expected-published)
        # Frozen output failures (if any) and retries are recorded, never silently called successful.
        recounted=[]
        for child in sorted((pushroot/'push_ladder').glob('*_walk_1.5/push_ladder.json')):
            d=read(child);directions=d['summary']['magnitudes']['1.5']['directions']
            ratios=[r['survivors']/r['envs'] for r in directions.values()]
            assert len(ratios)==8 and all(r['envs']==64 for r in directions.values())
            cell=d['terrain']+'/'+d['map_mode'];v=min(ratios)
            assert v==bundle['stage_criteria']['walk_1.5mps_worst_direction'][cell]['worst_direction_survival_fraction']
            recounted.append({'cell':cell,'source':str(child),'worst':v,'direction_counts':{k:[r['survivors'],r['envs']] for k,r in directions.items()}})
        assert len(recounted)==9
        result['stages'][str(n)]={'checkpoint_sha256':score['checkpoint_sha256'],'playlist':str(p),'playlist_count':len(paths),'expected_video_cases':len(expected),'published_video_cases':len(published),'missing_video_cases':missing,'video_root':str(vd),'receipt_device':rec['device'],'argv_device':dev,'bundle_device':bundle['device'],'device_logs':logs,'receipt_source':str(pushroot/'eval_receipt.json'),'push_source':str(pushroot/'push_ladder/push_ladder_bundle.json'),'push_recomputed':recounted,'map_source':ev['path']}
    # TB values describe actual sampled GT/OFF, not merely force_gt configuration.
    import csv
    with (DATA/'training.csv').open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    for stage,lo,hi in [('S2e',5001,5500),('T0prime',5501,6000)]:
        rr=[r for r in rows if lo<=int(r['iteration'])<=hi]
        for key in ['Loss/adasmpl/gt_fraction','Loss/adasmpl/p_smpl','Loss/map_switch/off_frac','Loss/perception/l_tr']:
            vv=[float(r[key]) for r in rr if r[key]]
            result['map_usage'].append({'stage':stage,'tag':key,'n':len(vv),'min':min(vv),'median':statistics.median(vv),'max':max(vv),'first50':statistics.median(vv[:50]),'last50':statistics.median(vv[-50:])})
    result['sources']=list(SOURCES.values());dump(DATA/'w45_evidence.json',result);csvout(DATA/'symmetry.csv',result['symmetry'])
    print(json.dumps({'stages':{k:{kk:vv for kk,vv in v.items() if kk not in ['device_logs']} for k,v in result['stages'].items()},'symmetry_rows':len(result['symmetry']),'map_usage':result['map_usage']},ensure_ascii=False,indent=2))

if __name__=='__main__':collect()
