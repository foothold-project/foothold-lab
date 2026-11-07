"""W44 evidence only: CPU geometry and existing EX-41 observations, no recommendation."""
from pathlib import Path
import ast, csv, hashlib, importlib.util, json, math, subprocess, sys, types
import numpy as np
import torch
import trimesh
import scipy.interpolate as interpolate

REPO=Path(__file__).resolve().parents[3]
OUT=REPO/'inbox/jay/20261107-ex42-w44';OUT.mkdir(exist_ok=True)
DATA=OUT/'data';DATA.mkdir(exist_ok=True)
REPORTS=REPO/'inbox/jay/20261106-ex41-stage-reports'
FROZEN=Path('D:/mai-wt/foothold-lab/ex41-launch-2b01df9a')
RUNNER=Path('D:/mai-wt/foothold-lab/runner-ex42-gates-1107')
LAB=Path('C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains')
sources=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source(p):
    sources.append({'path':str(p),'sha256':sha(p)})
    return p.read_text(encoding='utf-8-sig')
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def table(cols,rows):return '\n'.join(['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']+['| '+' | '.join(str(x) for x in r)+' |' for r in rows])
def writecsv(name,rows):
    with (DATA/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
class CpuTorch:
    cuda=types.SimpleNamespace(is_available=lambda:False)
    def __getattr__(self,k):return getattr(torch,k)
ns={'np':np,'torch':CpuTorch(),'trimesh':trimesh,'interpolate':interpolate}
def funcs(p,names):
    for n in ast.parse(source(p)).body:
        if isinstance(n,ast.FunctionDef) and n.name in names:
            n.decorator_list=[]
            exec(compile('from __future__ import annotations\n'+ast.unparse(n),str(p),'exec'),ns)
funcs(LAB/'trimesh/utils.py',['make_border'])
funcs(LAB/'trimesh/mesh_terrains.py',['pyramid_stairs_terrain','inverted_pyramid_stairs_terrain','random_grid_terrain'])
funcs(LAB/'height_field/hf_terrains.py',['random_uniform_terrain','pyramid_sloped_terrain'])
p=FROZEN/'foothold_s2/terrains/rough_go2_cfg.py';tree=ast.parse(source(p))
assert sha(p)==sha(RUNNER/'foothold_s2/terrains/rough_go2_cfg.py')
source(RUNNER/'foothold_s2/terrains/rough_go2_cfg.py')
constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='continuous_subterrains')
ret=next(n for n in fn.body if isinstance(n,ast.Return)).value
cfgs={}
for k,c in zip(ret.keys,ret.values):
    vals={}
    for kw in c.keywords:
        if kw.arg=='proportion':continue
        if isinstance(kw.value,ast.Tuple):vals[kw.arg]=tuple(constants[x.id] if isinstance(x,ast.Name) else ast.literal_eval(x) for x in kw.value.elts)
        else:vals[kw.arg]=constants[kw.value.id] if isinstance(kw.value,ast.Name) else ast.literal_eval(kw.value)
    cfgs[ast.literal_eval(k)]=vals

# Pure numpy gap generator loaded directly, without package registration/Kit.
sp=FROZEN/'foothold_s2/eval/start_sheet.py';source(sp)
spec=importlib.util.spec_from_file_location('w44_sheet',sp);ss=importlib.util.module_from_spec(spec);spec.loader.exec_module(ss)
ep=RUNNER/'foothold_s2/terrains/ex42.py';source(ep)
spec=importlib.util.spec_from_file_location('w44_ext',ep);ext=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ext;spec.loader.exec_module(ext)
rows=[]
for L in range(5,10):
    lo,hi,mid=L/10,(L+1)/10,(L+.5)/10
    for kind in ('pyramid_stairs','pyramid_stairs_inv','stage_stairs','boxes'):
        cfg=types.SimpleNamespace(size=(8.,8.),horizontal_scale=.1,vertical_scale=.005,downsampled_scale=None,inverted=kind.endswith('_inv'),**cfgs[kind])
        np.random.seed(42);torch.manual_seed(42)
        if kind=='boxes':
            cfg.holes=False
            meshes,_=ns['random_grid_terrain'](mid,cfg)
            a,b=cfg.grid_height_range
            bound=a+(b-a)*mid
            zs=np.unique(np.round(meshes[-2].vertices[:,2],9));zs=zs[zs>-.5]
            assert max(abs(zs))<=bound+1e-7
            r={'L':L,'kind':kind,'metric':'box_top_abs_bound_m','lo':a+(b-a)*lo,'hi_exclusive':a+(b-a)*hi,'midpoint':bound,'mesh_measured':max(abs(zs)),'mesh_min_z':min(zs),'mesh_max_z':max(zs),'extra':'adjacent difference <= 2*bound, not guaranteed actual'}
        else:
            meshes,_=ns['inverted_pyramid_stairs_terrain' if kind.endswith('_inv') else 'pyramid_stairs_terrain'](mid,cfg)
            tops=np.unique(np.round([m.bounds[1,2] for m in meshes],9))
            a,b=cfg.step_height_range;actual=float(np.median(np.diff(tops)));want=a+(b-a)*mid
            assert abs(actual-want)<1e-7
            r={'L':L,'kind':kind,'metric':'step_height_m','lo':a+(b-a)*lo,'hi_exclusive':a+(b-a)*hi,'midpoint':want,'mesh_measured':actual,'mesh_min_z':min(tops),'mesh_max_z':max(tops),'extra':f'step_width={cfg.step_width}; platform={cfg.platform_width}'}
        rows.append(r)
    geom=ss.generate('gaps',L,np.random.default_rng(42))
    # Surface intervals at y=mid. Exclude pit floor, combine overlapping slabs.
    intervals=sorted((float(b[0]),float(b[1])) for b in geom.boxes if b[2]<=ss.SIZE[1]/2<=b[3] and abs(b[5])<1e-9)
    union=[]
    for a,b in intervals:
        if union and a<=union[-1][1]+1e-8:union[-1][1]=max(b,union[-1][1])
        else:union.append([a,b])
    gaps=[b[0]-a[1] for a,b in zip(union,union[1:])]
    assert len(gaps)==3 and np.allclose(gaps,geom.params['gap_width'],atol=1e-10)
    g=float(np.median(gaps))
    rows.append({'L':L,'kind':'start_gen_v1_gaps','metric':'gap_width_m','lo':g,'hi_exclusive':g,'midpoint':g,'mesh_measured':g,'mesh_min_z':-geom.depth,'mesh_max_z':0.,'extra':'exact support boxes; unscaled; not EX41 exposure'})
    exspec=next(x for x in ext.PAPER_EXT_SPECS if x.kind=='stairs_high')
    a,b=exspec.range_value
    cfg=types.SimpleNamespace(size=(8.,8.),step_height_range=(a,b),**dict(exspec.fixed))
    meshes,_=ns['pyramid_stairs_terrain'](mid,cfg)
    tops=np.unique(np.round([m.bounds[1,2] for m in meshes],9))
    actual=float(np.median(np.diff(tops)));assert abs(actual-(a+(b-a)*mid))<1e-7
    rows.append({'L':L,'kind':'paper_ext_v1_stairs_high','metric':'step_height_m','lo':a+(b-a)*lo,'hi_exclusive':a+(b-a)*hi,'midpoint':a+(b-a)*mid,'mesh_measured':actual,'mesh_min_z':min(tops),'mesh_max_z':max(tops),'extra':'EX42 extension; not EX41 W78 test'})
writecsv('geometry.csv',rows)
source(LAB/'terrain_generator.py')

def readcsv(p):
    source(p)
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
train=readcsv(REPORTS/'data/training.csv')
commands=readcsv(REPORTS/'data/command_cells.csv')
selected=[]
for lo,hi in [(3751,5000),(5001,5500),(5501,5750),(5751,6000)]:
    rr=[r for r in train if lo<=int(r['iteration'])<=hi]
    d={'first':lo,'last':hi,'n':len(rr)}
    for tag,short in [('Loss/learning_rate','lr'),('Loss/kl_probe/ppo_mean','kl'),('Policy/mean_noise_std','std'),('Train/mean_reward','reward'),('Train/mean_episode_length','episode_length'),('Curriculum/terrain_levels','level'),('Loss/perception/l_tr','tr_loss'),('Loss/adasmpl/gt_fraction','gt_fraction'),('Loss/map_switch/off_frac','off_fraction')]:
        vv=np.array([float(r[tag]) for r in rr]);assert np.isfinite(vv).all()
        d[short+'_median']=float(np.median(vv));d[short+'_first50']=float(np.median(vv[:50]));d[short+'_last50']=float(np.median(vv[-50:]))
        if short=='lr':d['lr_at_1e5']=int((vv<=1.00001e-5).sum())
        if short=='kl':d['kl_gt_005']=int((vv>.05).sum())
    perstep=[float(r['Train/mean_reward'])/float(r['Train/mean_episode_length']) for r in rr]
    d['reward_per_step_median']=float(np.median(perstep))
    selected.append(d)
writecsv('training_windows.csv',selected)
cmd=[r for r in commands if int(r['iteration'])>=3750]
writecsv('boundary_commands.csv',cmd)
protocol=json.loads((REPORTS/'data/w78_5500_6000_protocol.json').read_text(encoding='utf-8'))
for key in ('old','new'): assert sha(Path(protocol[key]))==protocol[key+'_sha256']
for n in (3750,5500,6000):
    source(REPORTS/f'data/w78_m{n}_audit.json');source(REPORTS/f'data/w78_m{n}_kinds.csv')
for r in selected:
    print({k:r[k] for k in ('first','last','n','lr_at_1e5','kl_gt_005','std_median','reward_median','reward_per_step_median','level_median','tr_loss_median')})
print(table(['L','계단 범위m','중간 메시m','boxes 실제 최대절댓값m','틈 원코드m','틈 Go2축척 계산m','확장 계단 중간m'],[[L,
        f'{next(r for r in rows if r["L"]==L and r["kind"]=="pyramid_stairs")["lo"]:.3f}~{next(r for r in rows if r["L"]==L and r["kind"]=="pyramid_stairs")["hi_exclusive"]:.3f}',
        *[f'{next(r for r in rows if r["L"]==L and r["kind"]==k)["mesh_measured"]:.5f}' for k in ('pyramid_stairs','boxes','start_gen_v1_gaps')],
        f'{next(r for r in rows if r["L"]==L and r["kind"]=="start_gen_v1_gaps")["mesh_measured"]*1.108:.5f}',
        f'{next(r for r in rows if r["L"]==L and r["kind"]=="paper_ext_v1_stairs_high")["mesh_measured"]:.5f}'] for L in range(5,10)]))
dump(DATA/'evidence.json',{'sources':sources,'geometry_rows':len(rows),'device':'cpu','sampling':'d=(L+0.5)/10 mesh; row bounds d=[L/10,(L+1)/10); actual run U not recovered',
     'runner_head':subprocess.check_output(['git','-C',str(RUNNER),'rev-parse','HEAD'],text=True).strip(),
     'scope':'No GPU/Kit/physics. Exact AST mesh functions, pure gap support boxes. EX42 full scene not built.',
     'known_answers':['mesh stair difference equals input height','boxes tops within prescribed signed bound','three measured gap intervals equal source width','W78 final sources match prior audit SHA']})
