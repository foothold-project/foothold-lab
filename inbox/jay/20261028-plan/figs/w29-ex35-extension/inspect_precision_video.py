"""Read-only CPU precision audit and existing-video inspection assets for W29."""
from pathlib import Path
import os, json, csv, hashlib, subprocess
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import cv2

O=Path(__file__).resolve().parent
T=Path('C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb')
B='2026-10-26_01-17-47_sb-main'
E=B+'_resume_20261026_232446_120476'
X=E+'_resume_20261028_050035_157468'
V=Path('C:/mai/wt/foothold-lab/impl-turncases/logs/w26_fall')
sources={}
def source(p):
    p=Path(p); raw=p.read_bytes();sources[str(p)]={'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)};return raw
def js(p):return json.loads(source(p).decode('utf-8-sig'))
def save(n,x): (O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

# PyTorch is used only for trusted local checkpoint deserialization onto CPU.
import torch
precision=[]
for label,d,n in [('SB10',B,1500),('EX35-first',E,2000),('EX35-extend',X,3000)]:
    p=T/d/f'model_{n}.pt';source(p)
    x=torch.load(p,map_location='cpu',weights_only=False)
    pc=x['perception_cfg'];mf=js(T/d/'manifest.json')
    precision.append({'label':label,'iter':n,'path':str(p),'sha256':sources[str(p)]['sha256'],
      'model_dtypes':sorted({str(t.dtype) for t in x['model_state_dict'].values() if torch.is_tensor(t)}),
      'perception_dtypes':sorted({str(t.dtype) for t in x['perception_state_dict'].values() if torch.is_tensor(t)}),
      'ppo_learning_rate':x['ppo_learning_rate'],'optimizer_lr':[g['lr'] for g in x['optimizer_state_dict']['param_groups']],
      'replay_autocast':pc.get('replay_autocast'),'kl_fp32':pc.get('kl_fp32'),
      'microbatch_envs':pc.get('microbatch_envs'),'kl_probe_envs':pc.get('kl_probe_envs'),
      'force_gt':pc.get('force_gt'),'p_map_off':pc.get('p_map_off'),
      'manifest_git':mf['git'],'normalization':{k:v for k,v in mf.get('modes',{}).items() if 'normal' in k},
      'manifest_precision_fields':{k:v for k,v in mf.get('modes',{}).items() if any(s in k for s in ('cast','bf16','tf32','kl_fp32'))}})
    del x
actual=Path('C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/algorithms/ppo.py')
pp=source(actual).decode('utf-8')
commit='3681d7dbe787c01463e50a57246a6f57e4866d0f'
fragments=[]
for name,lines in [('foothold_s2/runners/start_runner.py',[(95,105),(390,421),(609,679),(790,820),(965,1000)]),('foothold_s2/scripts/train_start.py',[])]:
    b=subprocess.check_output(['git','-C','C:/mai/wt/foothold-lab/impl-w19','show',f'{commit}:{name}'])
    txt=b.decode('utf-8');sources[commit+':'+name]={'git':commit,'file':name,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
    if not lines:
        for i,s in enumerate(txt.splitlines(),1):
            if any(t in s for t in ('allow_tf32','set_float32_matmul_precision','replay_autocast','autocast','float16','bf16')):fragments.append(f'{commit}:{name}:{i}: {s}')
    else:
        for a,z in lines:
            fragments.append(f'\n{commit}:{name}:{a}-{z}')
            fragments.extend(f'{i}: {s}' for i,s in enumerate(txt.splitlines(),1) if a<=i<=z)
fragments.append(f'\n{actual}:258-292 sha256 {sources[str(actual)]["sha256"]}')
fragments.extend(f'{i}: {s}' for i,s in enumerate(pp.splitlines(),1) if 258<=i<=292)
(O/'precision_source_lines.txt').write_text('\n'.join(line.rstrip() for line in '\n'.join(fragments).splitlines())+'\n',encoding='utf-8')
save('precision.json',{'actual_interpreter':'isaac311','checkpoints':precision,'ppo_autocast_present':'autocast' in pp,'limitation':'No GPU kernel trace was performed. fp32 describes saved weights and active training code path, not every hardware instruction.'})

font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
video=[]
for p in sorted(V.glob('m*_fell_env*/review.mp4')):
    source(p);d=p.parent;receipt=js(d/'review.done');j=js(d/'review.json');source(d/'review_feet.npz')
    assert all(hashlib.sha256((d/name).read_bytes()).hexdigest()==sha for name,sha in receipt['files'].items())
    with np.load(d/'review_feet.npz',allow_pickle=False) as z:
        resets=[{'index':int(i),'t':float(z['t'][i]),'term':str(z['termination_terms'][i]),'reason':str(z['termination_reason'][i]),'roll':float(z['roll'][i]),'pitch':float(z['pitch'][i])} for i in np.flatnonzero(z['done'])]
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate,duration','-of','json',str(p)]))['streams'][0]
    cap=cv2.VideoCapture(str(p));fps=cap.get(cv2.CAP_PROP_FPS);frames=[]
    while True:
        ok,frame=cap.read()
        if not ok:break
        frames.append(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
    cap.release();assert len(frames)==j['frames']==int(probe['nb_frames'])
    choose=sorted({min(round(t*fps),len(frames)-1) for t in np.arange(0,j['duration_s'],.5)})
    def grid(ids,suffix):
        width,height=384,216;cols=4;rows=(len(ids)+cols-1)//cols
        im=Image.new('RGB',(cols*width,rows*(height+26)),(255,255,255));dr=ImageDraw.Draw(im)
        for c,i in enumerate(ids):
            x=(c%cols)*width;y=(c//cols)*(height+26)
            tile=Image.fromarray(frames[i]);tile.thumbnail((width,height));im.paste(tile,(x,y+26))
            dr.text((x+4,y+2),f'{i/fps:.2f}s | frame {i}',font=font,fill=(15,15,15))
        out=O/f'{d.name}_{suffix}.jpg';im.save(out,quality=90);return str(out)
    g=grid(choose,'2fps')
    dense=[]
    for ii,rr in enumerate(resets):
        ids=sorted({min(max(int(round(t*fps)),0),len(frames)-1) for t in np.arange(max(0,rr['t']-.6),min(j['duration_s'],rr['t']+.16),1/fps)})
        dense.append(grid(ids,f'reset{ii}'))
    video.append({'path':str(p),'receipt':str(d/'review.done'),'receipt_hashes_match':True,'decoded_frames':len(frames),'fps':fps,'duration_s':j['duration_s'],
       'selected_environment':j['selected_environment'],'checkpoint_sha':j['checkpoint_sha256'],'resets':resets,'grid':g,'sampled_frames':choose,'dense_grids':dense,
       'mode':j['map_modes']['map_mode'],'capture_start':j.get('capture_start'),'probe':probe})
save('video_audit.json',video);save('supplement_sources.json',list(sources.values()))
print(json.dumps({'precision':precision,'videos':[{k:v[k] for k in ['path','decoded_frames','resets','grid']} for v in video]},ensure_ascii=False))
