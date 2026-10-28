"""Final CPU consistency, provenance, output-link and checksum checks."""
from pathlib import Path
import csv,json,hashlib,re,subprocess
O=Path(__file__).resolve().parent
REPORT=O.parents[2]/'20261028-experiments/RESULT-EX35-EXT-1028.md'
def js(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
raw=js(O/'sources.json');extra=js(O/'supplement_sources.json')
unchanged=0
for r in [*raw,*extra]:
    if 'path' in r:
        assert sha(Path(r['path']))==r['sha256'],r['path'];unchanged+=1
prec=js(O/'precision.json');provenance=[]
ppo=Path('C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/algorithms/ppo.py')
for r in prec['checkpoints']:
    mf=js(Path(r['path']).with_name('manifest.json'));files=mf['files']['imported_sha256']
    names=[k for k in files if k=='rsl_rl.algorithms.ppo']
    assert len(names)==1, names
    assert files[names[0]]==sha(ppo),(r['label'],files[names[0]],sha(ppo))
    b=subprocess.check_output(['git','-C','C:/mai/wt/foothold-lab/impl-w19','show',mf['git']['head']+':foothold_s2/runners/start_runner.py'])
    expected=files['foothold_s2.runners.start_runner']
    assert expected in (hashlib.sha256(b).hexdigest(),hashlib.sha256(b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')).hexdigest())
    assert b'torch.backends.cudnn.allow_tf32 = False' in b and b'torch.backends.cuda.matmul.allow_tf32 = False' in b
    provenance.append({'run':r['label'],'ppo_module':'rsl_rl.algorithms.ppo','ppo_sha256':sha(ppo),'manifest_ppo_hash_match':True,'runner_commit_hash_match':True,'tf32_code_disabled':True})
rr=list(csv.DictReader((O/'training_by_update.csv').open(encoding='utf-8-sig')))
e=[r for r in rr if 2001<=int(r['iter'])<=3000]
assert len(e)==1000 and sum(float(r['Loss/learning_rate'])<1.000001e-5 for r in e)==45
assert sum(float(r['Loss/learning_rate'])<1.000001e-5 for r in e if int(r['iter'])>=2901)==0
text=REPORT.read_text(encoding='utf-8');assert '\u2014' not in text
audit={'raw_file_hash_rechecks':unchanged,'unchanged':True,'precision_source':provenance,
       'extends_update_count':1000,'lr_floor_count':45,'last100_lr_floor_count':0,
       'video_decode_frames':sum(r['decoded_frames'] for r in js(O/'video_audit.json')),
       'no_gpu_or_training_execution':True,'report':str(REPORT)}
(O/'final_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
# Canonical LF for text mirrors Git, raw bytes for binary assets.
text_ext={'.py','.md','.json','.csv','.txt'}
hashes=[]
for p in sorted(O.iterdir()):
    if not p.is_file() or p.name=='SHA256SUMS.txt':continue
    b=p.read_bytes()
    if p.suffix in text_ext:
        b=b.replace(b'\r\n',b'\n');p.write_bytes(b)
        assert '\u2014' not in b.decode('utf-8-sig'),p.name
    hashes.append(hashlib.sha256(b).hexdigest()+'  '+p.name)
(O/'SHA256SUMS.txt').write_text('\n'.join(hashes)+'\n',encoding='utf-8')
for target in re.findall(r'\]\(([^)]+)\)',text):
    if not target.startswith(('http','C:','#')):assert (REPORT.parent/target).exists(),target
print(json.dumps({'files':len(hashes),'report_lines':len(text.splitlines()),'hashes_rechecked':unchanged,'ppo_provenance':provenance},ensure_ascii=False))
