"""ASTRA-23b: read-only source video/NPZ analysis. CPU only; no simulator imports.
Run with isaac311/python.exe visual_metrics.py. Output beside this script and ../../figs/astra-23b.
"""
from pathlib import Path
import hashlib,json,csv
import numpy as np
import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
FIG=HERE.parent.parent/'figs/astra-23b';FIG.mkdir(parents=True,exist_ok=True)
ROOT=Path('C:/Users/AI-WS01/s2_lab/videos/mid500_1022')
OLD=json.loads((HERE/'metrics-23a.json').read_text(encoding='utf8'))['rows']

def spans(mask,t,dt=.02):
    edges=np.diff(np.r_[False,mask,False].astype(int))
    return [(float(t[a]),float(t[b-1]+dt),int(b-a)) for a,b in zip(np.where(edges==1)[0],np.where(edges==-1)[0])]

def onset(w,t,sign,start,threshold=.2):
    # At least 10 consecutive samples (0.20 s). Return onset, not completion.
    ss=[x for x in spans(sign*w>=threshold,t) if x[2]>=10]
    return None if not ss else float(ss[0][0]-start)

assert spans(np.array([0,1,1,0],bool),np.arange(4)*.02)==[(.02,.06,2)]
assert onset(np.r_[np.zeros(10),np.ones(10)],np.arange(20)*.02,1,0)==.2
assert onset(-np.ones(20),np.arange(20)*.02,1,0) is None
assert onset(np.r_[np.ones(9),0,np.ones(9)],np.arange(19)*.02,1,0) is None

rows=[];provenance=[];data={};videos=[]
for group,folder in [('G1','ex23r_1500'),('G0','ex25_1500')]:
 for scene in ['flat','rough']:
    p=ROOT/folder/f'run_{scene}_feet.npz';d=dict(np.load(p,allow_pickle=False));data[group,scene]=d
    for src in [p,p.with_name(f'run_{scene}.json'),p.with_name(f'run_{scene}.mp4')]:
        provenance.append({'file':str(src),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'bytes':src.stat().st_size})
    for seg in range(4):
        m=d['seg']==seg;t=d['t'][m];c=d['foot_contact'][m];z=d['foot_z'][m];w=d['wz'][m]
        old=next(x for x in OLD if x['run']==folder and x['clip']==f'run_{scene}' and x['seg']==seg)
        r={'group':group,'scene':scene,'seg':seg,'old':old,'roll_std_deg':float(np.rad2deg(d['roll'][m]).std()),'pitch_std_deg':float(np.rad2deg(d['pitch'][m]).std()),'height_p10_p90':np.nanpercentile(d['body_height'][m],[10,90]).tolist(),'joint_rom_p95_p5':dict(zip(d['joint_names'].tolist(),(np.percentile(d['joint_pos'][m],95,axis=0)-np.percentile(d['joint_pos'][m],5,axis=0)).tolist()))}
        for ax in ['roll','pitch']:
            vals=np.rad2deg(d[ax][m]);k=int(np.argmax(np.abs(vals)));r[ax+'_max']={'abs_deg':float(abs(vals[k])),'signed_deg':float(vals[k]),'t':float(t[k])}
        if seg>=2:
            sign=1 if seg==2 else -1
            r['wz_half_second_bins']=[{'start':float(a),'mean':float(w[(t>=a)&(t<a+.5)].mean())} for a in np.arange(seg*3,seg*3+3,.5)]
            r['turn_onset_delay_s']={str(th):onset(w,t,sign,seg*3,th) for th in [.1,.2,.4]}
            r['reverse_spans_gt_0p1']=[x for x in spans(sign*w<-.1,t) if x[2]>=5]
            r['signed_body_wz_integral_deg']=float(np.rad2deg((sign*w).sum()*.02))
        feet={}
        for f,name in enumerate(d['foot_names']):
            air=spans(~c[:,f],t);stance=spans(c[:,f],t);clears=[]
            for a,b,n in air:
                ii=np.where((t>=a-1e-7)&(t<b-1e-7))[0]
                if len(ii) and ii[0]>0 and ii[-1]<len(t)-1:
                    clears.append({'start':a,'end':b,'height_m':float(z[ii,f].max()-(z[ii[0]-1,f]+z[ii[-1]+1,f])/2)})
            feet[str(name)]={'duty':float(c[:,f].mean()),'stance_max':max(stance,key=lambda x:x[2]) if stance else None,'air_max':max(air,key=lambda x:x[2]) if air else None,'closed_swings':clears}
        r['feet']=feet;rows.append(r)
    cap=cv2.VideoCapture(str(p.with_name(f'run_{scene}.mp4')))
    assert cap.isOpened();fps=cap.get(cv2.CAP_PROP_FPS);frames=[];idx=0;seen=0
    # Decode every frame. Retain overview frames at 5 fps plus the final frame.
    while True:
        ok,im=cap.read()
        if not ok:break
        if idx%5==0:
            small=cv2.resize(im,(320,180));cv2.rectangle(small,(0,0),(320,20),(0,0,0),-1)
            cv2.putText(small,f'{group} {scene} {idx/fps:.2f}s',(4,15),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),1);frames.append(small)
        last=im;idx+=1
    cap.release();assert idx==300,(group,scene,idx);assert len(frames)==60
    # Separate overview covers all four commands, not just good forward frames.
    grid=np.concatenate([np.concatenate(frames[i:i+6],axis=1) for i in range(0,60,6)],axis=0)
    cv2.imwrite(str(FIG/f'{group}_{scene}_overview.jpg'),grid,[cv2.IMWRITE_JPEG_QUALITY,88])
    videos.append({'group':group,'scene':scene,'fps':fps,'decoded_frames':idx,'sampled_frames':len(frames),'last_video_time_s':(idx-1)/fps})

for scene in ['flat','rough']:
 fig,axes=plt.subplots(5,1,figsize=(14,12),sharex=True,gridspec_kw={'height_ratios':[1,1,1,1,1]})
 for group,color in [('G1','#006e7f'),('G0','#b34823')]:
    d=data[group,scene];t=d['t']
    axes[0].plot(t,d['wz'],label=group,color=color,lw=1)
    axes[1].plot(t,d['body_height'],label=group,color=color,lw=1)
    axes[2].plot(t,np.rad2deg(d['roll']),label=group+' roll',color=color,lw=1)
    axes[2].plot(t,np.rad2deg(d['pitch']),label=group+' pitch',color=color,lw=1,ls='--')
    ax=axes[3 if group=='G1' else 4]
    for j,n in enumerate(d['foot_names']):
        for a,b,_ in spans(d['foot_contact'][:,j],t):ax.plot([a,b],[3-j,3-j],lw=5,color=color,solid_capstyle='butt')
    ax.set_yticks(range(4),['RR','RL','FR','FL']);ax.set_ylabel(group+' contact')
 axes[0].plot([0,6,6,9,9,12],[0,0,1.2,1.2,-1.2,-1.2],color='black',ls=':',label='command')
 axes[0].set_ylabel('body wz (rad/s)');axes[1].set_ylabel('height (m)');axes[2].set_ylabel('roll / pitch (deg)')
 for ax in axes:
    for x in [3,6,9]:ax.axvline(x,color='gray',lw=.6)
    ax.grid(alpha=.18);ax.set_xlim(0,12)
 for ax in axes[:3]:ax.legend(loc='upper left',ncol=4)
 axes[-1].set_xlabel('stored observation time (s)');fig.suptitle(scene+' | G1 EX23 vs G0 EX25 | 1500 | one recorded trajectory')
 fig.tight_layout();fig.savefig(FIG/f'{scene}_signals.png',dpi=120);plt.close(fig)

keyrows=[]
for scene in ['flat','rough']:
 for group,folder in [('G1','ex23r_1500'),('G0','ex25_1500')]:
    cap=cv2.VideoCapture(str(ROOT/folder/f'run_{scene}.mp4'));frames=[]
    for sec in [6.0,7.0,7.6,8.8,10.8,11.96]:
        cap.set(cv2.CAP_PROP_POS_MSEC,sec*1000);ok,im=cap.read();assert ok
        im=cv2.resize(im,(320,180));cv2.rectangle(im,(0,0),(320,20),(0,0,0),-1)
        cv2.putText(im,f'{group} {scene} {sec:.2f}s',(4,15),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),1);frames.append(im)
    cap.release();keyrows.append(np.concatenate(frames,axis=1))
cv2.imwrite(str(FIG/'turn_comparison.jpg'),np.concatenate(keyrows,axis=0),[cv2.IMWRITE_JPEG_QUALITY,92])
(HERE/'visual_metrics.json').write_text(json.dumps({'known_input_checks':4,'rows':rows,'videos':videos,'provenance':provenance},ensure_ascii=False,indent=2),encoding='utf8')
for r in rows:
 o=r['old'];print(r['group'],r['scene'],r['seg'],'h/vx/wz/diag',*[round(o[k],3) if o[k] is not None else None for k in ['height','vx','wz','diag']],'roll/pitchSTD',round(r['roll_std_deg'],2),round(r['pitch_std_deg'],2),'onset',r.get('turn_onset_delay_s'),'reverse',r.get('reverse_spans_gt_0p1'))
 print('feet',[(k,round(v['duty'],2),v['stance_max'],len(v['closed_swings']),round(np.median([s['height_m'] for s in v['closed_swings']]),3) if v['closed_swings'] else None) for k,v in r['feet'].items()])
print('known checks 4; decoded',sum(x['decoded_frames'] for x in videos),'frames; saved',HERE/'visual_metrics.json')
