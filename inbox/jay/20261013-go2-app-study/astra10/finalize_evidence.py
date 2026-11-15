"""Bounded provenance checks and offline arithmetic fixtures for ASTRA10."""
from pathlib import Path
import hashlib, json, math, urllib.request

ROOT = Path(__file__).resolve().parent
def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for part in iter(lambda: f.read(1024*1024), b''): h.update(part)
    return h.hexdigest()

manifest = json.loads((ROOT/'evidence/runtime-web-manifest.json').read_text('utf-8'))
verified=[]
for row in manifest:
    p=ROOT/'runtime-web'/row['path']
    if not p.is_file(): continue
    assert p.stat().st_size==row['bytes']
    assert digest(p)==row['sha256']
    verified.append(row['path'])

public=[]
commit='8beafb4200965b33c64718e2717f975eff06d54e'
for target,name in [('libvoxel-Bqa6xB-f.wasm','libslam.wasm'),('libvoxel-doIu-r8s.wasm','libvoxel.wasm')]:
    url=f'https://raw.githubusercontent.com/legion1581/unitree_ui/{commit}/public/{name}'
    with urllib.request.urlopen(url,timeout=30) as res: data=res.read(1024*1024)
    local=ROOT/'extracted/assets/dist/assets'/target
    assert data==local.read_bytes()
    public.append({'url':url,'official_file':target,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'byte_identical':True})

r,w,h=.05,3,2
ox,oy,yaw=10,20,math.pi/2
centers=[]
for j in range(h):
    for i in range(w):
        gx,gy=(i+.5)*r,(j+.5)*r
        x,y=ox+math.cos(yaw)*gx-math.sin(yaw)*gy,oy+math.sin(yaw)*gx+math.cos(yaw)*gy
        u=(math.cos(yaw)*(x-ox)+math.sin(yaw)*(y-oy))/r
        v=(-math.sin(yaw)*(x-ox)+math.cos(yaw)*(y-oy))/r
        assert math.floor(u)==i and math.floor(v)==j
        centers.append({'cell':[i,j],'world':[x,y],'inverse':[u,v]})
data=[0,100,-1,50,0,100]
canvas=[data[i+w*j] for j in reversed(range(h)) for i in range(w)]
assert canvas==[50,0,100,0,100,-1]
assert math.isclose(math.degrees(2*math.atan(640/(2*320))),90)
assert (round(math.cos(math.pi-yaw)),round(-math.sin(math.pi-yaw)))==(0,-1)
assert round(46/.05)*round(27/.05)==496800

files=[]
for rel in ['downloads/UnitreeGo.apk','downloads/UnitreeGo-cn.apk','downloads/Unitree-EULA.docx',
            'runtime-web/assets/main-LIOZh9o1.js','runtime-web/js/store/store.-Ml-K330.js',
            'runtime-web/js/slam/Slam.BsJuOfhQ.js']:
    p=ROOT/rel
    files.append({'path':rel,'bytes':p.stat().st_size,'sha256':digest(p)})
out={'runtime_assets_verified':len(verified),'runtime_assets':verified,'public_wasm_comparison':public,
     'coordinate_fixture':{'centers':centers,'canvas_rows':canvas,'fov_synthetic_degrees':90,'grid_cells':496800,'assertions_passed':True},
     'key_files':files,'limits':'Synthetic inputs and file equality only. No robot/ROS runtime or map GUI validation.'}
(ROOT/'evidence/final-verification.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'runtime_assets_verified':len(verified),'public_wasm_equal':len(public),'coordinate_assertions_passed':True}))
