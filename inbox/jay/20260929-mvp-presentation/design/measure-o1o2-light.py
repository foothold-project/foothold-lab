from pathlib import Path
import numpy as np,json
from PIL import Image,ImageFilter
from scipy.ndimage import gaussian_filter,shift,zoom
from scipy.optimize import minimize
r=Path(__file__).resolve().parents[1]
a=np.array(Image.open(r/'output/o1o2-match-2.png').convert('RGB')).astype(float)
b=np.array(Image.open(r/'output/o1o2-match-3.png').convert('RGB')).astype(float)
def norm(x):
 g=np.log1p(x.mean(2));return g-gaussian_filter(g,7)
aa=norm(a);bb=norm(b)
mask=(a.mean(2)>15)&(b.mean(2)>10)
def loss(v):
 z=shift(bb,v,order=1);return np.mean((aa[mask]-z[mask])**2)
opt=minimize(loss,[0,0],method='Powell',bounds=[(-15,15),(-15,15)])
v=opt.x;aligned=shift(b,[*v,0],order=1,mode='nearest')
gain=(gaussian_filter(a.mean(2),18)+4)/(gaussian_filter(aligned.mean(2),18)+4)
gain=np.clip(gain,.25,3)
corrected=np.clip(aligned*gain[:,:,None],0,255).astype(np.uint8)
Image.fromarray(corrected).save(r/'output/o1o2-light-matched-preview.png')
report={'translation_yx':v.tolist(),'loss_before':loss([0,0]),'loss_after':loss(v),'gain_minmax':[float(gain.min()),float(gain.max())]}
(r/'assets/o1o2-light-match-plan.json').write_text(json.dumps(report,indent=2));print(report)

