from pathlib import Path
import json,hashlib,numpy as np,csv
ROOT=Path('C:/Users/AI-WS01/s2_lab/videos/mid500_1022')
OUT=Path('C:/Users/AI-WS01/AppData/Local/Temp/astra23a');OUT.mkdir(exist_ok=True)
def pairs(c,names):
 idx={str(n).split('_')[0]:i for i,n in enumerate(names)}
 a=np.zeros(4,bool);a[[idx['FL'],idx['RR']]]=True;b=~a
 A=np.all(c==a,axis=1);B=np.all(c==b,axis=1);two=c.sum(1)==2
 seq=np.where(A|B)[0];sig=A[seq];switch=int((sig[1:]!=sig[:-1]).sum())
 return {'n2':int(two.sum()),'dA':int(A.sum()),'dB':int(B.sum()),'diag':float((A|B).sum()/two.sum()) if two.any() else None,'diag_all':float((A|B).mean()),'diag_switch':switch}
def swings(z,c):
 out=[]
 for j in range(4):
  edges=np.diff(np.r_[True,c[:,j],True].astype(int));beg=np.where(edges==-1)[0];end=np.where(edges==1)[0]
  for a,b in zip(beg,end):
   if a>0 and b<len(c):out.append(float(z[a:b,j].max()-(z[a-1,j]+z[b,j])/2))
 return out
names=['FL_foot','FR_foot','RL_foot','RR_foot'];A=np.array([1,0,0,1],bool);B=~A
assert pairs(np.array([A,B,A,B]),names)['diag_switch']==3
assert pairs(np.tile(A,(20,1)),names)['diag']==1 and pairs(np.tile(A,(20,1)),names)['diag_switch']==0
assert pairs(np.array([[1]*4,[0]*4],bool),names)['diag'] is None
zz=np.tile(np.array([0,.02,.05,0])[:,None],(1,4));cc=np.tile(np.array([1,0,0,1],bool)[:,None],(1,4));assert np.allclose(swings(zz,cc),.05)
files=[]
for n in ['ex23r_300','ex23r_500','ex23r_1000','ex23r_1500','ex25_300','ex25_500','ex25_1000','ex25_1500']:
 files+=list((ROOT/n).glob('run_*_feet.npz'))
files+=list((ROOT/'scratch0811').glob('*_feet.npz'));files += [ROOT/'ex23r_1000/ex11_flat_feet.npz',ROOT.parent/'joint_1022/ex11_flat_feet.npz']
rows=[];provenance=[]
for p in files:
 d=np.load(p,allow_pickle=False);jpath=p.with_name(p.name.replace('_feet.npz','.json'));j=json.loads(jpath.read_text(encoding='utf8'))
 provenance.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
 c=d['foot_contact'];fn=d['foot_names'];dt=float(d['dt']);t=d['t'];bh=d['body_height'];fz=d['foot_z']
 if 'root_z' in d:
  n=c.sum(1);valid=n>0;calc=d['root_z'][valid]-(np.where(c[valid],fz[valid],0).sum(1)/n[valid]-.022)
  assert np.allclose(calc,bh[valid],atol=1e-6),p
 for k,cmd in enumerate(d['seg_cmds']):
  m=d['seg']==k;ct=c[m];tt=t[m];tail=m & (t>=tt[0]+float(d['seg_s'])/2);n=ct.sum(1);sw=swings(fz[m],ct)
  row={'run':p.parent.name,'clip':p.stem.replace('_feet',''),'seg':k,'n':int(m.sum()),'height':float(np.nanmedian(bh[m])),'height_p10':float(np.nanpercentile(bh[m],10)),'height_nan_frac':float(np.isnan(bh[m]).mean()),'vx':float(d['vx'][tail].mean()),'wz':float(d['wz'][tail].mean()),'progress_body':float(d['vx'][m].sum()*dt),'n0frac':float((n==0).mean()),'n2frac':float((n==2).mean()),'n4frac':float((n==4).mean()),'sw_med':float(np.median(sw)) if sw else None,'sw_n':len(sw),'liftoff':float(((~ct[1:])&ct[:-1]).sum()/4/(m.sum()*dt)),'duty':ct.mean(0).tolist(),'resets_total':j['resets'],'reset_times':j.get('reset_times_s',[]),'restored_modes':j.get('restored_modes'),**pairs(ct,fn)}
  if 'pitch' in d:
   row.update(pitch_deg_med=float(np.rad2deg(np.median(d['pitch'][m]))),pitch_deg_absmax=float(np.rad2deg(np.abs(d['pitch'][m]).max())),roll_deg_absmax=float(np.rad2deg(np.abs(d['roll'][m]).max())),joint_medians=dict(zip(d['joint_names'].tolist(),np.median(d['joint_pos'][m],axis=0).tolist())),root_z_med=float(np.median(d['root_z'][m])))
  rows.append(row)
(OUT/'metrics.json').write_text(json.dumps({'known_input_checks':4,'rows':rows,'provenance':provenance},ensure_ascii=False,indent=2),encoding='utf8')
for x in rows:
 if (x['run']=='scratch0811' and x['seg']==1) or (x['run'] in ['ex23r_1000','ex23r_1500','ex25_1000','ex25_1500']):
  print(x['run'],x['clip'],x['seg'],'h %.3f vx %.3f wz %.3f'%(x['height'],x['vx'],x['wz']),'diag',None if x['diag'] is None else round(x['diag'],3),'n2',x['n2'],'A/B',x['dA'],x['dB'],'switch',x['diag_switch'],'air %.2f sw %s'%(x['n0frac'],None if x['sw_med'] is None else round(x['sw_med'],3)),'reset',x['resets_total'],'pitch',round(x.get('pitch_deg_med',0),1))
print('FILES',len(files),'ROWS',len(rows),'OUTPUT',OUT)
