"""분류: 실험
작성: 오흥재 작업을 위한 Codex · 2026-09-17
근거: WORKER-08-scale.md, DESIGN-real-to-sim.md 6절, recon/recon_ipm.py
요지: CPU 프레임별 노면 표시 폭과 관측 연석 높이로 조건부 축척 구간 산출.
인자만으로 실행: python -B poc_scale_lane_width.py --base <작업 폴더>
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

import numpy as np
import cv2
from scipy import stats, ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read_image(path):
    return cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)


def save_image(path, im):
    cv2.imencode('.png', im)[1].tofile(str(path))


def plain(x):
    if isinstance(x, dict): return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [plain(v) for v in x]
    if isinstance(x, np.ndarray): return plain(x.tolist())
    if isinstance(x, np.generic): return plain(x.item())
    if isinstance(x, float) and not np.isfinite(x): return None
    return x


def dump(path, obj):
    path.write_text(json.dumps(plain(obj), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf8')


def summary(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if not len(v): return dict(n=0, median=None, mad=None, std=None, q05=None, q95=None)
    med = np.median(v)
    return dict(n=len(v), median=med, mad=np.median(abs(v-med)), std=np.std(v, ddof=1) if len(v)>1 else 0., q05=np.quantile(v,.05), q95=np.quantile(v,.95))


def pca(xy):
    c = xy.mean(0)
    vals, vec = np.linalg.eigh(np.cov(xy.T))
    d = vec[:, -1]
    if d[0]<0: d=-d
    return c, d, vals


def cameras(base, M):
    folder = base/'_out/colmap/undistorted'
    cam = next(l.split() for l in (folder/'sparse_txt/cameras.txt').read_text().splitlines() if l and not l.startswith('#'))
    W,H = map(int, cam[2:4]); fx,fy,cx,cy=map(float,cam[4:8])
    K=np.array([[fx,0,cx],[0,fy,cy],[0,0,1.]])
    poses={}
    lines=[l for l in (folder/'sparse_txt/images.txt').read_text().splitlines() if not l.startswith('#')]
    for i in range(0,len(lines),2):
        p=lines[i].split()
        if len(p)<10: continue
        w,x,y,z=map(float,p[1:5]); t=np.array(list(map(float,p[5:8])))
        Rwc=np.array([[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w], [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w], [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]])
        # Exact convention from the coordinator's verified recon_ipm.py.
        C=-Rwc.T@t
        poses[p[9]]=(Rwc@np.linalg.inv(M[:3,:3]), M[:3,:3]@C+M[:3,3])
    return poses,K,W,H


def candidates(mosaic, meta):
    px,xmin,xmax,ymin,ymax=meta
    hsv=cv2.cvtColor(mosaic, cv2.COLOR_BGR2HSV)
    h,s,v=[hsv[:,:,i] for i in range(3)]
    masks={'yellow':(h>=15)&(h<=40)&(s>=70)&(v>=110), 'white':(s<=45)&(v>=190)}
    rows=[]; pointsets={}
    for color,mask in masks.items():
        mask=cv2.morphologyEx(mask.astype('uint8'),cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
        n,labels,st,cent=cv2.connectedComponentsWithStats(mask,8)
        for i in range(1,n):
            if st[i,4]<300: continue
            yy,xx=np.nonzero(labels==i); xy=np.c_[xmin+xx*px,ymin+yy*px]
            c,d,e=pca(xy); u=(xy-c)@d
            key=f'{color}_{i}'
            row=dict(id=key,color=color,area_m2=st[i,4]*px**2,point_xy_m=c,axis_xy=d,length_m=np.ptp(u),elongation=np.sqrt(e[1]/max(e[0],1e-10)),intercept_y_m=c[1]-c[0]*d[1]/d[0])
            rows.append(row);pointsets[key]=xy
    return sorted(rows,key=lambda r:-r['area_m2']),pointsets


def targets_from_candidates(rows, points, Cs):
    # Geometric identification inspected on annot_mosaic: long yellow components,
    # A intercept near -0.3, B near +2.9. No width or legal prior enters selection.
    targets={}
    for name, intercept in [('yellow_A',-.3),('yellow_B',2.9)]:
        sel=[r for r in rows if r['color']=='yellow' and r['length_m']>=3 and r['elongation']>10 and abs(r['intercept_y_m']-intercept)<.35 and -.3<r['axis_xy'][1]<-.1]
        xy=np.concatenate([points[r['id']] for r in sel])
        near=np.min(np.linalg.norm(np.c_[xy,np.zeros(len(xy))][:,None,:]-Cs[None,:,:],axis=2),axis=1)<4
        c,d,e=pca(xy[near]); n=np.array([-d[1],d[0]])
        u=(xy[near]-c)@d
        targets[name]=dict(point=c,axis=d,normal=n,u_min=np.min(u),u_max=np.max(u),components=[r['id'] for r in sel],length_m=np.ptp(u),kind='yellow')
    # Most conspicuous road white stripe (right side), individually inspected.
    white=[r for r in rows if r['color']=='white' and r['length_m']>=3 and r['point_xy_m'][0]>4 and abs(r['axis_xy'][0])<.4]
    wr=max(white,key=lambda r:r['length_m']) if white else None
    if wr:
        xy=points[wr['id']]; c,d,e=pca(xy)
        dist=np.min(np.linalg.norm(np.c_[xy,np.zeros(len(xy))][:,None,:]-Cs[None,:,:],axis=2),axis=1)
        white_status=dict(status='대상 없음: 식별한 백색 실선은 카메라 4 m 이내 조건 불충족',candidate=wr,nearest_camera_distance_m=float(dist.min()))
    else: white_status=dict(status='대상 없음: 백색 직선 후보 없음')
    # A straight upper stroke of the left painted character, away from junction.
    d=targets['yellow_A']['axis']; c=np.array([-2.24,.696]); n=np.array([-d[1],d[0]])
    targets['text_stroke']=dict(point=c,axis=d,normal=n,u_min=-.45,u_max=.38,components=['manual text ROI, overview'],length_m=.83,kind='yellow',auxiliary=True)
    return targets,white_status


def profile_measure(values, offsets):
    # Red-green mean is a brightness channel on yellow paint; no HSV threshold
    # enters the edge measurement. Outer quarters are independent backgrounds.
    N=len(values); q=N//4
    left=float(np.median(values[:q]));right=float(np.median(values[-q:]))
    core=abs(offsets)<=.024
    paint=float(np.median(values[core]));contrast=paint-(left+right)/2
    ans=dict(background_left=left,background_right=right,paint=paint,contrast=contrast,width_m=np.nan,left_edge_m=np.nan,right_edge_m=np.nan,flat_pixels=0,reason='')
    if contrast<=0: ans['reason']='nonpositive_contrast';return ans
    # Flat part is the contiguous >=90% contrast run containing central maximum.
    mid=np.flatnonzero(abs(offsets)<=.07)
    peak=int(mid[np.argmax(values[mid])]); flat=values>=(left+right)/2+.9*contrast
    l=r=peak
    while l>0 and flat[l-1]: l-=1
    while r<N-1 and flat[r+1]: r+=1
    ans['flat_pixels']=r-l+1 if flat[peak] else 0
    tl=(left+paint)/2; tr=(right+paint)/2
    a=peak
    while a>0 and values[a]>=tl: a-=1
    b=peak
    while b<N-1 and values[b]>=tr: b+=1
    if a==0 or b==N-1 or values[a+1]==values[a] or values[b]==values[b-1]:
        ans['reason']='no_two_crossings';return ans
    le=offsets[a]+(tl-values[a])/(values[a+1]-values[a])*(offsets[a+1]-offsets[a])
    re=offsets[b-1]+(tr-values[b-1])/(values[b]-values[b-1])*(offsets[b]-offsets[b-1])
    ans.update(width_m=re-le,left_edge_m=le,right_edge_m=re)
    if ans['flat_pixels']<3: ans['reason']='flat_under_3_pixels'
    elif abs(left-right)>.3*contrast: ans['reason']='background_asymmetry'
    return ans


def remap(img,P,shape,Rcm,Cm,K,W,H):
    pc=(P-Cm)@Rcm.T
    uv=(K@pc.T).T;z=uv[:,2]
    u=uv[:,0]/np.where(abs(z)<1e-9,1e-9,z);v=uv[:,1]/np.where(abs(z)<1e-9,1e-9,z)
    ok=(z>0)&(u>=0)&(u<W-1)&(v>=0)&(v<H-1)
    mu=np.where(ok,u,0).astype('float32').reshape(shape);mv=np.where(ok,v,0).astype('float32').reshape(shape)
    rect=cv2.remap(img,mu,mv,cv2.INTER_LINEAR)
    return rect,ok.reshape(shape)


def measure_frames(base,out,targets,poses,K,W,H,args):
    offsets=np.arange(-.6,.6001,args.pixel)
    geometry={};records=[];examples={};saved={}
    for name,t in targets.items():
        uu=np.arange(t['u_min']+.02,t['u_max']-.02,args.spacing)
        centres=t['point']+uu[:,None]*t['axis'];xy=centres[:,None,:]+offsets[None,:,None]*t['normal']
        P=np.c_[xy.reshape(-1,2),np.zeros(xy.shape[0]*xy.shape[1])]
        geometry[name]=(uu,centres,P,xy.shape[:2])
    for fi,frame in enumerate(sorted(poses)[::args.frame_step]):
        Rcm,Cm=poses[frame];img=None
        for name,t in targets.items():
            uu,centres,P,shape=geometry[name]
            dist=np.linalg.norm(np.c_[centres,np.zeros(len(centres))]-Cm,axis=1)
            # Work only where at least some profile centres satisfy near distance.
            if not np.any(dist<=args.max_distance): continue
            if img is None: img=read_image(base/'_out/colmap/undistorted/images'/frame)
            rect,valid=remap(img,P,shape,Rcm,Cm,K,W,H)
            signal=rect[:,:,[1,2]].astype(float).mean(2)
            hsv=cv2.cvtColor(rect,cv2.COLOR_BGR2HSV)
            color_mask=(hsv[:,:,0]>=15)&(hsv[:,:,0]<=40)&(hsv[:,:,1]>=70)&(hsv[:,:,2]>=110)&valid
            # Keep the central paint run only, excluding neighboring text/curb.
            stripe=np.zeros(shape,bool)
            for j in range(shape[0]):
                ids=np.flatnonzero(color_mask[j]&(abs(offsets)<.08))
                if not len(ids): continue
                peak=ids[np.argmin(abs(offsets[ids]))];l=r=peak
                while l>0 and color_mask[j,l-1]: l-=1
                while r<shape[1]-1 and color_mask[j,r+1]: r+=1
                stripe[j,l:r+1]=True
            # Physical sampling preserves anisotropic 20 mm / 2 mm distances.
            dt=ndimage.distance_transform_edt(np.pad(stripe,1),sampling=(args.spacing,args.pixel))[1:-1,1:-1]
            area_width=stripe.sum(1)*args.pixel
            dt_width=2*dt.max(1)
            good=0
            for j,u in enumerate(uu):
                row=dict(target=name,frame=frame,axis_m=u,x_m=centres[j,0],y_m=centres[j,1],z_m=0.,camera_distance_m=dist[j])
                m=profile_measure(signal[j],offsets)
                m['area_length_width_m']=float(area_width[j])
                m['distance_transform_width_m']=float(dt_width[j])
                if not valid[j].all(): m['reason']='invalid_pixel'
                elif dist[j]>args.max_distance: m['reason']='camera_over_4m'
                row.update(m);records.append(row)
                if not m['reason']:
                    good+=1
                    if name not in examples: examples[name]=(offsets.copy(),signal[j].copy(),row.copy())
            if good>15 and name not in saved:
                # Persist a true 2 mm by 2 mm IPM strip for this measured frame.
                fine_u=np.arange(t['u_min'],t['u_max'],args.pixel)
                xy=t['point']+fine_u[:,None,None]*t['axis']+offsets[None,:,None]*t['normal']
                PF=np.c_[xy.reshape(-1,2),np.zeros(xy.shape[0]*xy.shape[1])]
                rf,vf=remap(img,PF,xy.shape[:2],Rcm,Cm,K,W,H);rf[~vf]=0
                save_image(out/'ipm'/f'{name}_{Path(frame).stem}.png',rf)
                saved[name]=dict(frame=frame,pixel_m=args.pixel,u_origin_m=fine_u[0],normal_origin_m=offsets[0],point_xy_m=t['point'],axis_xy=t['axis'],normal_xy=t['normal'],shape=rf.shape)
        if fi%25==0: print('frames',fi,'/',len(poses),'profiles',len(records),flush=True)
    for name in targets:
        rr=[r for r in records if r['target']==name]
        median_contrast=float(np.median([r['contrast'] for r in rr if r['reason'] not in ('invalid_pixel','camera_over_4m') and r['contrast']>0]))
        for r in rr:
            if not r['reason'] and r['contrast']<.5*median_contrast:r['reason']='contrast_under_half_median'
            r['accepted']=not bool(r['reason'])
        targets[name]['median_contrast']=median_contrast
    with (out/'profiles.csv').open('w',newline='',encoding='utf8') as f:
        wr=csv.DictWriter(f,fieldnames=list(records[0]));wr.writeheader();wr.writerows(records)
    dump(out/'ipm/metadata.json',saved)
    return records,examples


def regression(x,y,groups,rng,B):
    x=np.asarray(x);y=np.asarray(y);groups=np.asarray(groups)
    fit=stats.linregress(x,y)
    ids=np.unique(groups); sufficient=[]
    for g in ids:
        xx=x[groups==g];yy=y[groups==g]
        sufficient.append([len(xx),xx.sum(),yy.sum(),(xx*xx).sum(),(xx*yy).sum()])
    sufficient=np.array(sufficient)
    sums=sufficient[rng.integers(0,len(ids),(B,len(ids)))].sum(1)
    n,sx,sy,sxx,sxy=sums.T
    slopes=(sxy-sx*sy/n)/(sxx-sx*sx/n)
    return dict(slope_m_per_m=fit.slope,intercept_m=fit.intercept,r=fit.rvalue,ci95_frame_bootstrap=np.quantile(slopes,[.025,.975]),frames=len(ids),profiles=len(x))


def aggregate(records,targets,rng,B):
    result={};boots={}
    for name in targets:
        rr=[r for r in records if r['target']==name];aa=[r for r in rr if r['accepted']]
        frames={}
        for frame in sorted({r['frame'] for r in aa}):
            fr=[r for r in aa if r['frame']==frame]
            frames[frame]=dict(median_m=np.median([r['width_m'] for r in fr]),n=len(fr),distance_m=np.median([r['camera_distance_m'] for r in fr]))
        med=np.array([v['median_m'] for v in frames.values()])
        boots[name]=np.median(med[rng.integers(0,len(med),(B,len(med)))],axis=1)
        result[name]=dict(geometry=targets[name],attempted=len(rr),accepted=len(aa),rejected_reasons=Counter(r['reason'] for r in rr if not r['accepted']),profiles=summary([r['width_m'] for r in aa]),frame_medians=summary(med),frame_median_ci95=np.quantile(boots[name],[.025,.975]),by_frame=frames,distance_regression=regression([r['camera_distance_m'] for r in aa],[r['width_m'] for r in aa],[r['frame'] for r in aa],rng,B),position_regression=regression([r['axis_m'] for r in aa],[r['width_m'] for r in aa],[r['frame'] for r in aa],rng,B))
        estimators={}
        for field in ('width_m','area_length_width_m','distance_transform_width_m'):
            fm=[np.median([r[field] for r in aa if r['frame']==frame]) for frame in frames]
            estimators[field]=summary(fm)
        result[name]['estimator_comparison']=dict(same_accepted_profiles=len(aa),frame_summaries=estimators,area_relative_difference=estimators['area_length_width_m']['median']/np.median(med)-1,dt_relative_difference=estimators['distance_transform_width_m']['median']/np.median(med)-1,area_vs_dt_relative_difference=estimators['distance_transform_width_m']['median']/estimators['area_length_width_m']['median']-1,zero_color_width_profiles=sum(r['area_length_width_m']==0 for r in aa),method='50% brightness crossing versus central connected HSV mask area/length and anisotropic Euclidean distance-transform diameter; identical accepted profile rows')
        ww=np.array([r['width_m'] for r in aa]);dd=np.array([r['camera_distance_m'] for r in aa]);q1,q3=np.quantile(ww,[.25,.75]);iqr=q3-q1;inside=(ww>=q1-1.5*iqr)&(ww<=q3+1.5*iqr)
        result[name]['tail_sensitivity']=dict(rule='exploratory 1.5 IQR fences; does not change accepted profiles or primary regression',lower_m=q1-1.5*iqr,upper_m=q3+1.5*iqr,flagged=int((~inside).sum()),retained=int(inside.sum()),slope_inside_fences_m_per_m=stats.linregress(dd[inside],ww[inside]).slope,accepted_width_range_m=[ww.min(),ww.max()],accepted_distance_range_m=[dd.min(),dd.max()])
    ratio=result['yellow_A']['frame_medians']['median']/result['yellow_B']['frame_medians']['median']
    return result,dict(A_over_B=ratio,ci95=np.quantile(boots['yellow_A']/boots['yellow_B'],[.025,.975]),method='independent frame bootstrap, spatially overlapping frames are not independent captures')


def load_splat(base,M):
    path=base/'_out/splat/splat.ply'
    props=[];count=0
    with path.open('rb') as f:
        while True:
            line=f.readline().decode('ascii').strip()
            if line.startswith('element vertex'):count=int(line.split()[-1])
            if line.startswith('property float '):props.append((line.split()[-1],'<f4'))
            if line=='end_header': offset=f.tell();break
    a=np.memmap(path,mode='r',offset=offset,dtype=np.dtype(props),shape=(count,))
    sel=a['opacity']>=np.log(.1/.9)
    xyz=np.stack([a[k][sel] for k in ('x','y','z')],1).astype(float)@M[:3,:3].T+M[:3,3]
    rgb=np.clip(.5+.28209479177*np.stack([a[f'f_dc_{i}'][sel] for i in range(3)],1),0,1)
    return xyz,rgb


def splat_widths(xyz,rgb,targets):
    hsv=cv2.cvtColor((rgb[:,::-1]*255).astype('uint8').reshape(-1,1,3),cv2.COLOR_BGR2HSV)[:,0]
    mask=(abs(xyz[:,2])<.03)&(hsv[:,0]>=15)&(hsv[:,0]<=40)&(hsv[:,1]>=70)&(hsv[:,2]>=110)
    pts=xyz[mask,:2]; result={}
    for name in ('yellow_A','yellow_B'):
        t=targets[name];u=(pts-t['point'])@t['axis'];v=(pts-t['point'])@t['normal']
        v=v[(u>=t['u_min'])&(u<=t['u_max'])&(abs(v)<.4)]
        edges=np.arange(-.4,.4001,.005);cent=(edges[:-1]+edges[1:])/2
        h,_=np.histogram(v,edges); smooth=ndimage.gaussian_filter1d(h.astype(float),1)
        peak=int(np.argmax(smooth));half=smooth[peak]/2;l=r=peak
        while l>0 and smooth[l]>=half:l-=1
        while r<len(smooth)-1 and smooth[r]>=half:r+=1
        le=np.interp(half,smooth[l:l+2],cent[l:l+2]);re=np.interp(half,smooth[r-1:r+1][::-1],cent[r-1:r+1][::-1])
        result[name]=dict(n=len(v),width_fwhm_m=re-le,left_m=le,right_m=re,bin_m=.005,smoothing_sigma_bins=1,counts=h,bin_centers_m=cent)
        result[name]['peak_offset_m']=cent[peak]
        core=v[abs(v)<.2]
        result[name]['central_roi_diagnostic']=dict(half_width_m=.2,n=len(core),q05_q95_m=np.quantile(core,[.05,.95]),span90_m=np.ptp(np.quantile(core,[.05,.95])),fraction_near_negative_edge=float(np.mean((core>-.08)&(core<-.035))))
        result[name]['color_sensitivity']=[]
        for sat in (70,40,20):
            sel=(abs(xyz[:,2])<.03)&(hsv[:,0]>=15)&(hsv[:,0]<=40)&(hsv[:,1]>=sat)&(hsv[:,2]>=110)
            pp=xyz[sel,:2];uu=(pp-t['point'])@t['axis'];vv=(pp-t['point'])@t['normal'];vv=vv[(uu>=t['u_min'])&(uu<=t['u_max'])&(abs(vv)<.2)]
            hh,_=np.histogram(vv,edges);ss=ndimage.gaussian_filter1d(hh.astype(float),1);pk=int(np.argmax(ss));ha=ss[pk]/2;ll=rr=pk
            while ll>0 and ss[ll]>=ha:ll-=1
            while rr<len(ss)-1 and ss[rr]>=ha:rr+=1
            el=np.interp(ha,ss[ll:ll+2],cent[ll:ll+2]);er=np.interp(ha,ss[rr-1:rr+1][::-1],cent[rr-1:rr+1][::-1])
            result[name]['color_sensitivity'].append(dict(saturation_min=sat,n=len(vv),span90_m=np.ptp(np.quantile(vv,[.05,.95])),fwhm_m=er-el))
    return result


def curb_measure(base,xyz,targets,out):
    a=np.load(base/'_out/mesh/grid_audit.npz');xs=a['x_m'];ys=a['y_m'];height=a['height_final_m'];obs=a['observed_mask']
    d=targets['yellow_A']['axis'];n=targets['yellow_A']['normal'];cn=targets['yellow_A']['point']@n-.60
    us=np.arange(-3.,3.01,.1); vv=np.arange(-.6,.6001,.025)
    def sample(P):
        ix=np.rint((P[:,0]-xs[0])/(xs[1]-xs[0])).astype(int);iy=np.rint((P[:,1]-ys[0])/(ys[1]-ys[0])).astype(int)
        inside=(ix>=0)&(ix<len(xs))&(iy>=0)&(iy<len(ys));ix=ix.clip(0,len(xs)-1);iy=iy.clip(0,len(ys)-1)
        return height[iy,ix],obs[iy,ix]&inside
    # Fit the actual height transition near the visually located curb.
    edgepts=[]
    scan=np.arange(cn-.3,cn+.3001,.025)
    for u in us:
        P=u*d+scan[:,None]*n;z,ok=sample(P)
        deriv=-np.diff(z); valid=ok[:-1]&ok[1:]
        if valid.any():
            j=np.argmax(np.where(valid,deriv,-np.inf))
            if deriv[j]>.008:edgepts.append(P[j]+.0125*n)
    ep=np.array(edgepts); eu=ep@d;ev=ep@n
    fit=stats.theilslopes(ev,eu);cn=float(fit.intercept);dn=d+fit.slope*n;dn/=np.linalg.norm(dn);nn=np.array([-dn[1],dn[0]]);c=cn*n
    rows=[];curves=[];spl=[]
    for u in np.arange(-3.,3.01,.05):
        P=c+u*dn+vv[:,None]*nn;z,ok=sample(P)
        step=float(np.median(z[vv<-.2])-np.median(z[vv>.2]))
        primary=bool(abs(u*10-round(u*10))<1e-7)
        row=dict(axis_m=u,primary_0_1m=primary,accepted=bool(ok.all()),unobserved_samples=int((~ok).sum()),height_m=step)
        rows.append(row)
        if ok.all() and primary:curves.append((u,z))
        rel=xyz[:,:2]-(c+u*dn);along=rel@dn;across=rel@nn
        sl=(abs(along)<.05)&(across<-.2)&(across>-.6)&(xyz[:,2]>-.3)&(xyz[:,2]<.5)
        sr=(abs(along)<.05)&(across>.2)&(across<.6)&(xyz[:,2]>-.3)&(xyz[:,2]<.5)
        if primary and sl.sum()>=3 and sr.sum()>=3:spl.append(dict(axis_m=u,height_m=float(np.median(xyz[sl,2])-np.median(xyz[sr,2])),sidewalk_n=int(sl.sum()),road_n=int(sr.sum())))
    dump(out/'curb_profiles.json',dict(grid=rows,splat=spl,normal_offsets_m=vv,accepted_grid_curves=[dict(axis_m=u,height_m=z) for u,z in curves]))
    primary_rows=[r for r in rows if r['primary_0_1m']]
    return dict(point_xy_m=c,axis_xy=dn,normal_xy=nn,grid_source='height_final_m with all sampled observed_mask cells true; prior smoothing can include neighbors',grid=summary([r['height_m'] for r in primary_rows if r['accepted']]),attempted=len(primary_rows),rejected_interpolated_or_outside=sum(not r['accepted'] for r in primary_rows),dense_0_05m=summary([r['height_m'] for r in rows if r['accepted']]),dense_attempted=len(rows),dense_rejected=sum(not r['accepted'] for r in rows),splat=summary([r['height_m'] for r in spl]),edge_fit_n=len(ep)),(vv,curves)


def hypotheses(agg,curb,targets):
    A=agg['yellow_A']['frame_medians']['median'];B=agg['yellow_B']['frame_medians']['median']
    n=targets['yellow_A']['normal'];gap=abs((targets['yellow_B']['point']-targets['yellow_A']['point'])@n)
    results={}
    for h,ar,br in [('H1',(.1,.15),(.1,.15)),('H2',(.1,.15),(.15,.2)),('H3',(.15,.2),(.15,.2))]:
        constraints={'yellow_A':dict(m=A,spec_m=ar),'yellow_B':dict(m=B,spec_m=br),'curb':dict(m=curb['grid']['median'],spec_m=(.15,.25)), 'lane_spacing':dict(m=gap,spec_m=(3.,3.5))}
        for v in constraints.values():v['k_interval']=[v['spec_m'][0]/v['m'],v['spec_m'][1]/v['m']]
        core_keys=('yellow_A','yellow_B','curb')
        lo=max(constraints[k]['k_interval'][0] for k in core_keys);hi=min(constraints[k]['k_interval'][1] for k in core_keys)
        all_lo=max(v['k_interval'][0] for v in constraints.values());all_hi=min(v['k_interval'][1] for v in constraints.values())
        line_lo=max(constraints[k]['k_interval'][0] for k in ('yellow_A','yellow_B'));line_hi=min(constraints[k]['k_interval'][1] for k in ('yellow_A','yellow_B'))
        relaxed_lo=max(constraints[k]['k_interval'][0] for k in ('yellow_A','yellow_B','curb'));relaxed_lo=max(relaxed_lo,2.75/gap)
        results[h]=dict(constraints=constraints,intersection_bounds=[lo,hi],status='survives' if lo<=hi else 'rejected',k_interval=[lo,hi] if lo<=hi else [],phone_height_m=[1.4*lo,1.4*hi] if lo<=hi else [],limiting_lower=max(constraints,key=lambda k:constraints[k]['k_interval'][0]),limiting_upper=min(constraints,key=lambda k:constraints[k]['k_interval'][1]),paint_only_k=[line_lo,line_hi] if line_lo<=line_hi else [],urban_relaxed_k=[relaxed_lo,hi] if relaxed_lo<=hi else [],no_lane_upper_bound_k=[max(line_lo,constraints['curb']['k_interval'][0],2.75/gap),min(line_hi,constraints['curb']['k_interval'][1])])
        v=results[h]
        v['limiting_lower']=max(core_keys,key=lambda k:constraints[k]['k_interval'][0]);v['limiting_upper']=min(core_keys,key=lambda k:constraints[k]['k_interval'][1])
        v['with_lane_3_3_5_k']=[all_lo,all_hi] if all_lo<=all_hi else []
        v['urban_relaxed_k']=[relaxed_lo,min(hi,3.5/gap)] if relaxed_lo<=min(hi,3.5/gap) else []
        if v['no_lane_upper_bound_k'][0]>v['no_lane_upper_bound_k'][1]:v['no_lane_upper_bound_k']=[]
        plo=max(lo,1.2/1.4);phi=min(hi,1.7/1.4)
        v['phone_prior']=dict(confidence='추측',prior_height_m=[1.2,1.7],intersection_bounds=[plo,phi],k_interval=[plo,phi] if plo<=phi else [],phone_height_m=[1.4*plo,1.4*phi] if plo<=phi else [],reason='공집합: 규격 가정과 폰 높이 범위의 교집합 없음' if plo>phi else '존속')
        k=v['no_lane_upper_bound_k']
        v['no_lane_upper_bound_phone_height_m']=[1.4*x for x in k]
        v['no_lane_upper_bound_phone_prior_k']=[max(k[0],1.2/1.4),min(k[1],1.7/1.4)] if k and max(k[0],1.2/1.4)<=min(k[1],1.7/1.4) else []
        v['measurement_sensitivity']={}
        for mode in ('frame_q05_q95','distance_drift_full_span'):
            intervals={};ranges={}
            for key in core_keys:
                q=constraints[key];m=q['m']
                if key=='curb':ml=mh=m
                elif mode=='frame_q05_q95':ml=agg[key]['frame_medians']['q05'];mh=agg[key]['frame_medians']['q95']
                else:
                    delta=abs(agg[key]['distance_regression']['slope_m_per_m'])*(4.-1.24);ml=m-delta;mh=m+delta
                ranges[key]=[ml,mh];intervals[key]=[q['spec_m'][0]/mh,q['spec_m'][1]/ml]
            sl=max(q[0] for q in intervals.values());sh=min(q[1] for q in intervals.values())
            v['measurement_sensitivity'][mode]=dict(measurement_ranges_m=ranges,per_target_k=intervals,k_interval=[sl,sh] if sl<=sh else [],intersection_bounds=[sl,sh],phone_height_m=[1.4*sl,1.4*sh] if sl<=sh else [],interval_width=max(0,sh-sl),widening_from_point=max(0,sh-sl)-max(0,hi-lo),interpretation='compatibility union over possible measured widths; not simultaneous confidence interval; curb held fixed')
    return results,gap


def figures(out,mosaic,meta,targets,agg,records,examples,curb,curves,hs):
    colors={'yellow_A':'#936000','yellow_B':'#176b5b','text_stroke':'#674b91'}
    def save(fig,name):fig.savefig(out/'figs'/name,dpi=170,bbox_inches='tight');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,8));ax.imshow(mosaic[:,:,::-1],extent=[meta[1],meta[2],meta[4],meta[3]])
    for name,t in targets.items():
        u=np.arange(t['u_min'],t['u_max'],.2);p=t['point']+u[:,None]*t['axis'];ax.plot(*p.T,label=name,color=colors[name],lw=2)
        for pt in p:ax.plot(*(pt+np.array([[-.2],[.2]])*t['normal']).T,color=colors[name],alpha=.7,lw=.6)
    cc=curb['point_xy_m'];dd=curb['axis_xy'];pp=np.array([cc-3*dd,cc+3*dd]);ax.plot(*pp.T,color='#d33136',label='curb')
    ax.set(xlim=(-4.5,7.5),ylim=(5,-3),xlabel='Mesh x (assumed m)',ylabel='Mesh y (assumed m)',title='Measurement axes and perpendicular profile samples');ax.legend();save(fig,'fig_ipm_overview.png')
    fig,axes=plt.subplots(len(examples),1,figsize=(9,3*len(examples)))
    for ax,(name,(x,y,row)) in zip(np.atleast_1d(axes),examples.items()):
        ax.plot(x,y,color=colors[name]);ax.axhline((row['paint']+row['background_left'])/2,color='#333333',ls=':');ax.axhline((row['paint']+row['background_right'])/2,color='#555555',ls=':')
        ax.axvline(row['left_edge_m'],color='#333333',ls='--');ax.axvline(row['right_edge_m'],color='#333333',ls='--');ax.set(xlabel='Normal offset (assumed m)',ylabel='Mean R,G (0..255)',title=f'{name}: {row["frame"]}, width {row["width_m"]:.4f} m')
    fig.tight_layout();save(fig,'fig_profiles.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for name,a in agg.items():
        vals=[r['width_m'] for r in records if r['target']==name and r['accepted']];axes[0].hist(vals,50,histtype='step',density=True,label=name,color=colors[name]);axes[1].hist([v['median_m'] for v in a['by_frame'].values()],25,histtype='step',label=name,color=colors[name])
    for ax in axes:ax.set_xlabel('Width (assumed m)');ax.legend()
    axes[0].set(title='Accepted profiles',ylabel='Density (1/m)');axes[1].set(title='Frame median distribution',ylabel='Frames');save(fig,'fig_width_hist.png')
    fig,axes=plt.subplots(1,len(agg),figsize=(15,4))
    for ax,(name,a) in zip(axes,agg.items()):
        rr=[r for r in records if r['target']==name and r['accepted']];xx=np.array([r['camera_distance_m'] for r in rr]);yy=np.array([r['width_m'] for r in rr]);ax.scatter(xx[::5],yy[::5],s=2,alpha=.15,color=colors[name]);reg=a['distance_regression'];x=np.array([xx.min(),xx.max()]);ax.plot(x,reg['intercept_m']+reg['slope_m_per_m']*x,color='#222222');ax.set(xlabel='Camera distance (assumed m)',ylabel='Width (assumed m)',title=name)
    fig.tight_layout();save(fig,'fig_width_vs_distance.png')
    fig,ax=plt.subplots(figsize=(9,5));vv,cc=curves
    for u,z in cc:ax.plot(vv,z,alpha=.4,lw=1)
    ax.axvspan(-.6,-.2,color='#176b5b',alpha=.1,label='Sidewalk plateau');ax.axvspan(.2,.6,color='#936000',alpha=.1,label='Road plateau');ax.set(xlabel='Curb normal offset (assumed m)',ylabel='Grid height (assumed m)',title=f'Observed-only curb profiles: n={len(cc)}');ax.legend();save(fig,'fig_curb_profiles.png')
    fig,ax=plt.subplots(figsize=(10,4))
    for i,(h,v) in enumerate(hs.items()):
        lo,hi=v['intersection_bounds']
        if lo<=hi:ax.plot([lo,hi],[i,i],lw=8,color='#176b5b');ax.text(hi+.01,i,f'{lo:.4f} to {hi:.4f}',va='center')
        else:ax.plot([hi,lo],[i,i],ls=':',color='#b42318');ax.scatter([hi,lo],[i,i],marker='x',color='#b42318');ax.text(lo+.01,i,f'empty: lower {lo:.4f} > upper {hi:.4f}',va='center')
    ax.set_yticks(range(3),list(hs));ax.set(xlabel='Scale correction k (dimensionless)',title='Conditional intersection: paint + curb (lane spacing excluded)',ylim=(-.5,2.5));ax.set_xlim(.7,1.8);save(fig,'fig_scale_intervals.png')


def report(out,result,args):
    result=plain(result)
    a=result['targets'];h=result['hypotheses'];c=result['curb'];f=lambda x:f'{x:.5f}' if x is not None else '미측정'
    lines=['# 노면 표시와 연석의 조건부 규격 추정 축척', '', '> 분류: 실험', f'> 작성: 오흥재 작업을 위한 Codex · {datetime.now():%Y-%m-%d %H:%M}', '> 근거: WORKER-08-scale.md · DESIGN-real-to-sim.md 6절 · profiles.csv · measurements.json', '> 요지: 프레임별 도색 폭과 관측 연석 단차에서 가설별 축척 허용 구간을 계산하며 단일 값을 확정하지 않는다', '> 상태: 검토중', '> 판: v1.0','','## 0. 결론','','모든 길이는 폰 높이 1.4 m 가정으로 만들어진 메시 좌표의 값이다. `확인됨`은 이 자료에서 계산을 재현했다는 뜻이며 현장 실측을 뜻하지 않는다. 규격 적용과 시공 상태는 `미확인`이다.','','| 가설 | 모든 적용 대상 교집합 k | 폰 높이 m | 판정 근거 |','|---|---|---|---|']
    for name,v in h.items():
        lo,hi=v['intersection_bounds'];lines.append(f'| {name} | '+(f'{lo:.5f} ~ {hi:.5f} | {1.4*lo:.5f} ~ {1.4*hi:.5f} | 조건부 존속' if lo<=hi else f'공집합 | 공집합 | 기각: {v["limiting_lower"]} 하한 {lo:.5f} > {v["limiting_upper"]} 상한 {hi:.5f}')+' |')
    lines+=['','이 표는 차로 간격 3.00 ~ 3.50 m를 하나의 시공 시나리오로 가정한 결과다. 법령의 차로 값은 최소값이므로 3.50 m를 실제 차로의 법적 상한으로 해석하지 않는다. 해당 선들이 차로 경계인지도 `미확인`이다. 단일 축척은 확정하지 않는다.','','## 1. 방법','','검증된 recon_ipm.py의 world -> mesh 변환과 Rcm = Rwc @ inv(Rm), Cm = Rm @ C + tm을 그대로 사용했다. z=0 평면 점을 각 원본 undistort 영상에 투영하고 cv2.remap INTER_LINEAR로 읽었다. 후보는 모자이크 HSV 마스크의 연결 성분 PCA로 추출했으며 전체 목록은 candidates.json에 있다. 측정은 모자이크 평균 영상에서 수행하지 않았다.','','황색의 R·G 채널 평균 밝기를 사용했다. 주축 간격 0.02 m, 수직 샘플 간격 0.002 m, 수직 범위 -0.60 ~ +0.60 m이다. 양 끝 1/4 구간의 중앙값을 배경으로 하고 중심 ±0.024 m 중앙값을 도색 밝기로 잡았다. 양쪽 배경과 도색의 각 50 % 교차점을 선형 보간했다. 중심 ±0.07 m에서 최대 밝기점과 연결된 90 % 이상 구간이 3 화소 미만이면 기각했다. 대비가 대상 전체 양의 대비 중앙값의 0.5배 미만, 양쪽 배경 차가 대비의 0.3배 초과, 영상 밖 화소 포함, 카메라 거리 4 m 초과도 기각했다. 폭 범위로 사후 제거하지 않았다.','','| 대상 | 통과점 x,y (m) | 주축 단위벡터 x,y | 후보 길이 m |','|---|---|---|---|']
    for name,v in a.items():
        t=v['geometry'];lines.append(f'| {name} | {t["point"]} | {t["axis"]} | {t["length_m"]:.4f} |')
    lines += ['',f'백색 실선: {result["white_1"]["status"]}. 후보 자세와 최단 거리는 measurements.json의 white_1에 기록했다. text_stroke는 노면 문자의 직선 획을 수동 지정한 보조 측정이며 법정 규격을 적용하지 않았다.','','![측정 위치](figs/fig_ipm_overview.png)','','![교차점 예시](figs/fig_profiles.png)','','## 2. 측정값과 분포','','대표 폭은 프레임별 폭 중앙값들의 중앙값이다. 프레임마다 같은 가중치를 준다. MAD는 중앙값 절대편차이며 정규분포 환산을 하지 않았다.','','| 대상 | 채택 프로파일 / 시도 | 프레임 수 | 대표 폭 m | 프레임 SD m | 프레임 MAD m | 프레임 중앙값 5 ~ 95 % m |','|---|---|---|---|---|---|']
    for name,v in a.items():
        s=v['frame_medians'];lines.append(f'| {name} | {v["accepted"]} / {v["attempted"]} | {s["n"]} | {f(s["median"])} | {f(s["std"])} | {f(s["mad"])} | {f(s["q05"])} ~ {f(s["q95"])} |')
    lines+=['','기각 사유별 개수와 모든 프레임 중앙값은 JSON에, 기각을 포함한 모든 수직 프로파일은 CSV에 기록했다. 프로파일별 표본 분포와 프레임별 분포를 구분한다.','','![폭 분포](figs/fig_width_hist.png)','','## 3. 자기 진단 넷','','회귀는 채택 프로파일 전체의 최소제곱 기울기이며 95 % 구간은 프레임을 묶음으로 재표집한 부트스트랩이다. 연속 프레임의 시간 상관과 공통 포즈·평면 오차를 제거한 신뢰구간은 아니다. 위치 회귀도 함께 기록했다.','','| 대상 | 거리 회귀 m/m | 95 % 구간 | 위치 회귀 m/m |','|---|---|---|---|']
    for name,v in a.items():
        r=v['distance_regression'];ci=r['ci95_frame_bootstrap'];lines.append(f'| {name} | {r["slope_m_per_m"]:.6f} | {ci[0]:.6f} ~ {ci[1]:.6f} | {v["position_regression"]["slope_m_per_m"]:.6f} |')
    ratio=result['yellow_ratio'];lines += ['',f'프레임 산포는 2절의 SD와 MAD다. 황색 A/B 폭 비는 {ratio["A_over_B"]:.5f}, 프레임 재표집 95 % 구간은 {ratio["ci95"][0]:.5f} ~ {ratio["ci95"][1]:.5f}다. 이 비만으로 선 종류를 확정할 수 없다.','','거리 기울기가 0과 구별되는 대상은 거리와 연관된 계통 변화가 있는 것으로 기록한다. 도색 자체의 위치 변화, 시점·노출, 평면 오차를 이 자료만으로 분리하지 못한다. 이 회귀로 폭을 보정하지 않았다.','','![거리 진단](figs/fig_width_vs_distance.png)','','스플랫 경로는 sigmoid(opacity) ≥ 0.1, 메시 |z| < 0.03 m, SH 0차 rgb = 0.5 + 0.28209479177 × f_dc로 황색을 추출했다. 주축 수직 점밀도 히스토그램의 반치전폭(FWHM)을 쟀다. 5 mm bin, 가우시안 σ=1 bin이다. 가우시안 중심 밀도 폭이므로 도색의 광학적 경계와 동일한 추정량은 아니다. 또한 같은 사진과 카메라를 공유하므로 통계적으로 독립인 현장 검증이 아니다.','','| 대상 | 황색 점 수 | 스플랫 FWHM m | 영상 대표 폭 대비 차 m |','|---|---|---|---|']
    for name,v in result['splat_widths'].items():lines.append(f'| {name} | {v["n"]} | {v["width_fwhm_m"]:.5f} | {v["width_fwhm_m"]-a[name]["frame_medians"]["median"]:+.5f} |')
    lines+=['','## 4. 연석','','연석 후보를 모자이크와 높이 격자에서 찾고, 근방 관측 칸의 높이 하강 위치를 Theil-Sen 직선으로 맞췄다. 그 선을 따라 0.1 m 간격으로 수직 단면을 취했다. 도로는 수직 좌표 +0.2 ~ +0.6 m, 보도는 -0.6 ~ -0.2 m의 중앙값이며 보도에서 도로를 뺀다. height_final_m을 최근접 칸으로 읽고 단면의 모든 칸이 observed_mask일 때만 채택했다. 기존 평활화가 인접 보간 높이를 참조했을 가능성은 남는다.','','| 경로 | 채택 n | 중앙값 m | MAD m | 5 ~ 95 % m |','|---|---|---|---|---|']
    for name in ('grid','splat'):
        s=c[name];lines.append(f'| {name} | {s["n"]} | {f(s["median"])} | {f(s["mad"])} | {f(s["q05"])} ~ {f(s["q95"])} |')
    lines += ['',f'격자 시도 {c["attempted"]}개 중 보간·미관측·범위 밖 칸이 섞인 {c["rejected_interpolated_or_outside"]}개를 버렸다. 스플랫은 같은 단면의 주축 ±0.05 m 띠 안에서 양쪽 각각 3점 이상일 때 계산했다. 관측 칸 제한은 없으며 단차용 점의 z 범위는 -0.3 ~ +0.5 m다. 기존 전체 높이 히스토그램 0.14 m와 다른 국소 측정이다. 턱낮춤과 서로 다른 단차 집단 여부는 분포 그림과 단면 기록으로 남기며 종류는 미확인이다.','','![연석 단면](figs/fig_curb_profiles.png)','','## 5. 규격 대조와 가설','','규격 출처는 [설계안 6-2-1](../../DESIGN-real-to-sim.md#6-2-1-법정-규격값--조사-결과)을 직접 읽어 전재했다. 이번 작업에서 법령 개정 여부를 새로 확인하지 않았으며 아래는 설계안의 규격 가정이다.','','| 기준자 | 적용 범위 | 설계안에 명시된 원 근거 |','|---|---|---|','| 차선 도색 | 0.10 ~ 0.15 m | 경찰청 교통노면표시 설치·관리 매뉴얼 제2장 제2절 표 2-1 |','| 중앙선 | 0.15 ~ 0.20 m | 같은 매뉴얼 표 2-1 |','| 시공 오차 | 도면보다 좁지 않고 +0.01 m 이내 | 주택공사 전문시방서 41770 3.6.1 |','| 연석 | 실무 표준 0.15 m, 지침상 0.15 ~ 0.25 m, 법정 상한 0.25 m | 보도 설치 및 관리 지침 2-7 · 도로의 구조·시설 기준에 관한 규칙 제16조제2항제1호 |','| 차로 | 설계속도별 최소 3.00 ~ 3.50 m, 도시 40 km/h 이하 등 2.75 m 완화 | 같은 규칙 제10조제3항 |','| 횡단보도 | 폭 0.45 ~ 0.50 m, 간격은 폭의 1.5배 | 도로교통법 시행규칙 별표6 일련번호 532 |','| 정지선 | 0.30 ~ 0.60 m | 별표6 일련번호 530 |','','횡단보도와 정지선은 이번 측정 대상이 아니며 미측정이다. 시공오차 +1 cm는 기본 규격 범위를 확장하는 데 사용하지 않았다. 연석은 지침의 가정이지 모든 연석에 적용되는 법정 하한이 아니다. 경사형·턱낮춤은 적용 대상이 다르며 현장 확인이 필요하다.','','H1은 황색 둘 다 차선 계열, H2는 가까운 A가 차선·먼 B가 중앙선, H3은 둘 다 중앙선이라고 가정한다. 백색 실선은 측정 조건 미충족으로 제외했다. 연석은 관측 격자의 중앙값을 기본값으로 적용하고 스플랫 수치는 교차 진단으로만 사용한다.','','각 측정 m에 대해 [lo/m, hi/m]를 구한다. 실제 장면 유닛당 미터는 k × '+f'{result["assumed_scale_m_per_unit"]:.14f}'+', 폰 높이는 k × 1.4 m다. 다음 표의 간격은 두 황색 축 사이 수직 거리 '+f'{result["lane_spacing_m"]:.5f} m'+ '이며 실제 차로 폭이라는 대응은 미확인이다.','','| 가설 | 항목 | 측정 m | 규격 m | 허용 k |','|---|---|---|---|---|']
    for name,v in h.items():
        for key,q in v['constraints'].items():lines.append(f'| {name} | {key} | {q["m"]:.5f} | {q["spec_m"][0]:.2f} ~ {q["spec_m"][1]:.2f} | {q["k_interval"][0]:.5f} ~ {q["k_interval"][1]:.5f} |')
    lines+=['','보조 시나리오도 함께 기록한다. 차로 3.5 m 상한을 제거한 값은 법적 최소라는 성격을 반영한 민감도 분석이다. 빈 구간은 가능한 축척이 없다.','','| 가설 | 도색만 k | 도시 완화 2.75 ~ 3.50 m k | 차로 상한 제거 k |','|---|---|---|---|']
    for name,v in h.items():lines.append(f'| {name} | {v["paint_only_k"]} | {v["urban_relaxed_k"]} | {v["no_lane_upper_bound_k"]} |')
    lines+=['','![가설별 구간](figs/fig_scale_intervals.png)','','## 6. 한계와 미확인','','성인이 앞을 보며 폰을 드는 높이 1.2 ~ 1.7 m라는 참고 범위는 작업서의 상식적 대조이며 `추측`이다. 이를 축척 구간의 필터나 사전확률로 사용하지 않았다. 높이 구간이 이 범위와 겹쳐도 현장 축척을 확인한 것이 아니다.','','표시의 법적 종류, 실제 시공 폭, 연석 형태, 차로 경계 대응은 미확인이다. 지면은 z=0 평면으로 가정했고 기울기와 포즈 오차는 공통 계통 오차다. 2 mm 출력 간격은 원본 광학 해상도나 정확도가 2 mm라는 뜻이 아니다. 연속 프레임은 독립 촬영이 아니며 부트스트랩 구간은 계통 오차를 모두 포함하지 않는다. 단차와 도색의 규격 가정이 동시에 맞지 않으면 그 가정 조합을 기각하며, 복원 전체의 좋고 나쁨을 판정하지 않는다.','','## 7. 재현 명령','','```powershell',f'& "C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe" -B "{args.base.as_posix()}/poc_scale_lane_width.py" --base "{args.base.as_posix()}" --seed {args.seed} --bootstrap {args.bootstrap}','```','','CPU만 사용한다. 원본·정찰 파일은 읽기 전용으로 취급했다. pip·시스템 설치, GPU 환경변수 변경, git 스테이징·커밋은 수행하지 않았다.','','관문 집계: '+json.dumps(result['gates'],ensure_ascii=False)+'. 세부 수치는 measurements.json, 전체 프로파일은 profiles.csv, 연석 단면은 curb_profiles.json에 있다.','','| 판 | 날짜 | 내용 |','|---|---|---|','| v1.0 | 2026-09-17 | 프레임별 도색과 관측 연석 단차로 조건부 규격 구간 계산 |']
    extra=['### 추가 진단: 같은 표본의 세 폭 추정량','','50 % 교차점 채택 프로파일과 동일한 행에 HSV 색 마스크(15 ≤ H ≤ 40, S ≥ 70, V ≥ 110)를 적용했다. 중심 ±0.08 m에서 가장 가까운 황색 화소와 연결된 획만 사용했다. 면적/길이는 그 행의 황색 면적(화소 수 × 0.002 × 0.02 m²)을 주축 길이 0.02 m로 나눈 값이다. 거리변환은 주축 0.02 m·수직 0.002 m의 물리 간격을 사용한 2차원 유클리드 거리변환 최대 반지름의 두 배다. 두 마스크 추정량은 같은 색 임계값을 공유하지만 50 % 밝기 교차와는 임계 기준이 다르다. 표는 동일 채택 행을 프레임별로 중앙값 집계한 뒤 다시 중앙값을 취했다.','','| 대상 | 같은 프로파일 수 | 50 % m | 면적/길이 m | 거리변환 m | 면적 대 50 % | 거리변환 대 50 % |','|---|---|---|---|---|---|---|']
    for name,v in a.items():
        e=v['estimator_comparison'];s=e['frame_summaries'];extra.append(f'| {name} | {e["same_accepted_profiles"]} | {s["width_m"]["median"]:.5f} | {s["area_length_width_m"]["median"]:.5f} | {s["distance_transform_width_m"]["median"]:.5f} | {100*e["area_relative_difference"]:+.2f} % | {100*e["dt_relative_difference"]:+.2f} % |')
    extra+=['','이 차이는 같은 표본에서 추정량과 임계값을 바꿀 때 생기는 민감도다. 수렴 판정의 사전 허용치는 작업서에 없으므로 임의 합격선을 만들지 않고 차이 자체를 보고한다. 정찰의 약 25 % 차이와 비교하되, 정찰의 98백분위 거리변환과 현재 프레임 중앙값은 집계법도 다르다. 차이가 남으면 지면 평면·카메라 자세에 의한 역투영 계통 오차의 신호일 수 있으나, 임계값·마모·화소화만으로도 차이가 생겨 원인을 확정하지 못한다. 채택값은 50 % 교차 그대로다.','']
    prior=['### 추가 제약: 폰 높이 1.2 ~ 1.7 m','','위 표의 규격 가정 교집합 계산은 `확인됨`이며 규격의 현장 적용은 `미확인`이다. 여기에 상식적 폰 높이 범위를 추가한 아래 교집합은 `추측`이다. 기본 결과와 별도로 계산했다.','','| 가설 | 규격 가정만 k | 폰 높이 제약 추가 k | 추가 후 폰 높이 m |','|---|---|---|---|']
    for name,v in h.items():prior.append(f'| {name} | {v["k_interval"] or "공집합"} | {v["phone_prior"]["k_interval"] or "공집합"} | {v["phone_prior"]["phone_height_m"] or "공집합"} |')
    prior+=['','차로의 법적 최소값을 실제 상한으로 오해하지 않도록, 3.50 m 상한을 뺀 시나리오의 높이 구간도 병기한다. 이 경우 중앙선 가설의 존속 여부가 달라질 수 있으며 기본 표의 기각을 일반적 기각으로 확장하지 않는다.','','| 가설 | 차로 상한 제거 k | 폰 높이 m | 여기에 폰 높이 제약 추가 k (`추측`) |','|---|---|---|---|']
    for name,v in h.items():prior.append(f'| {name} | {v["no_lane_upper_bound_k"] or "공집합"} | {v["no_lane_upper_bound_phone_height_m"] or "공집합"} | {v["no_lane_upper_bound_phone_prior_k"] or "공집합"} |')
    prior+=['','빈 구간은 명시한 가정 조합의 교집합이 없다는 뜻이다. 기본 구간에서 살아남았던 가설이 폰 높이 제약만으로 추가 기각됐는지는 위 두 열을 비교한다.','']
    body='\n'.join(lines)+'\n'
    body=body.replace('## 4. 연석','\n'.join(extra)+'\n## 4. 연석')
    body=body.replace('## 6. 한계와 미확인','\n'.join(prior)+'\n## 6. 한계와 미확인')
    body=body.replace('이를 축척 구간의 필터나 사전확률로 사용하지 않았다.','기본 규격 가정 결과는 이 범위로 제한하지 않았으며 별도 추가 제약 표에만 사용했다.')
    body=body.replace('> 판: v1.0','> 판: v1.1')
    body=body.replace('모든 적용 대상 교집합 k','도색 + 연석 교집합 k')
    body=body.replace('이 표는 차로 간격 3.00 ~ 3.50 m를 하나의 시공 시나리오로 가정한 결과다.','이 표는 황색 도색 둘과 연석만의 교집합이다. 차로 간격은 기본 결론에서 제외하고 5절의 보조 시공 시나리오로 남겼다.')
    diagnostics=['### 스플랫 경로 불일치 추가 조사','','| 대상 | 기본 FWHM m | 봉우리 수직 위치 m | ±0.20 m 안 점 수 | 그 점들의 5 ~ 95 % 폭 m |','|---|---|---|---|---|']
    for name,v in result['splat_widths'].items():
        q=v['central_roi_diagnostic'];diagnostics.append(f'| {name} | {v["width_fwhm_m"]:.5f} | {v["peak_offset_m"]:.5f} | {q["n"]} | {q["span90_m"]:.5f} |')
    diagnostics+=['','| 대상 | 채도 하한 | 점 수 (±0.20 m) | FWHM m | 5 ~ 95 % 폭 m |','|---|---|---|---|---|']
    for name,v in result['splat_widths'].items():
        for q in v['color_sensitivity']:diagnostics.append(f'| {name} | {q["saturation_min"]} | {q["n"]} | {q["fwhm_m"]:.5f} | {q["span90_m"]:.5f} |')
    diagnostics+=['','황색 A의 점밀도 봉우리는 축 중심이 아닌 음의 경계 쪽에 있고, 중심 ±0.20 m로 주변 문자를 줄여도 좁은 FWHM이 남는다. 그러나 5 ~ 95 % 점 분포는 영상 폭 정도를 덮는다. 따라서 중심 심만 남았다고 단정할 수 없고, 비균일한 경계 점밀도 때문에 FWHM이 선 전체 폭과 달라지는 현상이 관측된다. 채도 완화 실험도 원인을 완전히 분리하지 못한다. **스플랫 FWHM 경로는 영상 대표 폭을 뒷받침하지 못했다. 점밀도 편향의 발생 원인은 미확인이다.** 5 ~ 95 % 폭은 원인 조사이며 요구된 FWHM을 대체하지 않는다.','']
    body=body.replace('### 추가 진단: 같은 표본의 세 폭 추정량','\n'.join(diagnostics)+'\n### 추가 진단: 같은 표본의 세 폭 추정량')
    sensitivity=['### 차로 간격 보조 시나리오','','| 가설 | 기본 도색 + 연석 k | 차로 3.00 ~ 3.50 m 추가 k |','|---|---|---|']
    for name,v in h.items():sensitivity.append(f'| {name} | {v["k_interval"] or "공집합"} | {v["with_lane_3_3_5_k"] or "공집합"} |')
    sensitivity+=['','H3은 도색 + 연석에서는 존속하지만 차로 3.00 ~ 3.50 m를 넣으면 기각된다. 따라서 그 기각은 약한 차로 대응·상한 가정에 의존하며 기본 결론으로 채택하지 않는다. H2는 도색 둘의 구간 자체가 겹치지 않는다.','','### 폭 불확실성의 k 민감도','','폭을 [m_low, m_high] 범위로 허용하면 가능한 규격 대응의 합집합은 [lo/m_high, hi/m_low]다. 이 구간을 대상끼리 교집합했다. 프레임 5 ~ 95 % 범위는 폭 산포이며 추정 오차의 신뢰구간이 아니다. 거리 민감도는 |기울기| × (4.00 - 1.24 m)를 대표 폭 양쪽에 각각 더하고 뺀 보수적 범위다. 실제 주어진 폭 변화의 절반이 아닌 전체를 양쪽에 사용한다. 연석은 기본 대표값에 고정했다. 이 둘은 별도의 민감도 분석이며 확률적 오차 전파나 현장 정확도 보증이 아니다.','','| 대상 | 거리 기울기의 2.76 m 변화량 mm | 대표 폭 대비 % | 95 % 기울기 구간이 0 포함 |','|---|---|---|---|']
    for name,v in a.items():
        slope=v['distance_regression']['slope_m_per_m'];ci=v['distance_regression']['ci95_frame_bootstrap'];delta=abs(slope)*2.76;sensitivity.append(f'| {name} | {delta*1000:.3f} | {delta/v["frame_medians"]["median"]*100:.2f} | {ci[0]<=0<=ci[1]} |')
    sensitivity+=['','1.24 ~ 4 m는 정찰에서 제시한 전체 기준 범위다. 대상별 실제 채택 거리보다 넓을 수 있으므로 이 표는 회귀 외삽을 포함한 스트레스 분석이다.','','| 가설 | 폭 범위 방식 | 가능한 k | 폰 높이 m | 점추정 대비 k 폭 증가 |','|---|---|---|---|---|']
    for name,v in h.items():
        for mode,q in v['measurement_sensitivity'].items():sensitivity.append(f'| {name} | {mode} | {q["k_interval"] or "공집합"} | {q["phone_height_m"] or "공집합"} | {q["widening_from_point"]:.5f} |')
    sensitivity+=['','이 표에서 새로 살아나는 가설이 있으면 폭 점추정에 민감한 기각이다. 어떤 분석도 단일 축척을 확정하지 않는다.','']
    body=body.replace('### 추가 제약: 폰 높이 1.2 ~ 1.7 m','\n'.join(sensitivity)+'\n### 추가 제약: 폰 높이 1.2 ~ 1.7 m')
    dc=c['dense_0_05m'];curb_extra=f'\n0.05 m 간격 보조 재측정은 {c["dense_attempted"]}개 중 {dc["n"]}개 채택, {c["dense_rejected"]}개 제외이며 중앙값 {dc["median"]:.5f} m, MAD {dc["mad"]:.5f} m, 5 ~ 95 % {dc["q05"]:.5f} ~ {dc["q95"]:.5f} m다. 같은 5 cm 격자를 공유하는 추가 단면이므로 독립 표본이 늘었다고 해석하지 않는다. 기본 n={c["grid"]["n"]}의 작은 표본에서 MAD가 꼬리 산포를 대표하지 못할 수 있어 5 ~ 95 % 범위도 함께 사용해야 한다.\n\n설계안 6-2-2의 0.14 m 전체 높이 히스토그램 예시는 이번 국소 관측 단차 {c["grid"]["median"]:.5f} m로 대체하는 근거를 제공한다. 따라서 0.15/0.14 = 1.071배 예시를 이번 측정에 재사용하지 않는다. 새 측정에서 표준 0.15 m와 맞으려면 k={.15/c["grid"]["median"]:.5f}가 필요하지만 이 비 하나로 축척을 확정하지 않는다.\n'
    body=body.replace('## 5. 규격 대조와 가설',curb_extra+'\n## 5. 규격 대조와 가설')
    body=body.replace('기본 결과와 별도로 계산했다.','기본 결과와 별도로 계산했다. k는 가정 축척의 배율이고 폰 높이도 1.4 × k로 움직이므로, 이는 규격이 맞으려면 폰 높이가 얼마여야 하는지를 묻는 조건부 대조다. 범위를 벗어나면 규격 적용과 폰 높이 가정을 동시에 유지할 수 없으며 어느 가정이 틀렸는지는 현장 확인 전 미확인이다.')
    body += '\n| v1.1 | 2026-09-17 | 기본 결론에서 차로 제외, 빈 구간 정규화, 세 추정량 비교, 폰 높이 추가 제약, 폭 불확실성·스플랫·연석 보조 진단 추가. CHANGELOG-08.md 참조 |\n'
    body=body.replace('|---|---|---|---|---|---|\n| yellow_A', '|---|---|---|---|---|---|---|\n| yellow_A')
    body=body.replace('계산 |\n\n| v1.1','계산 |\n| v1.1')
    body=body.replace('| [] |','| 공집합 |').replace('| [] |','| 공집합 |')
    body=body.replace('| False |','| 아니요 |')
    body=re.sub(r'\[(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?), (-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)\]',lambda m:f'[{float(m[1]):.5f}, {float(m[2]):.5f}]',body)
    h3p=h['H3']['phone_prior'];h3k=h3p['k_interval'];h3height=h3p['phone_height_m']
    caveat='\n기본 표는 대표 폭을 고정한 조건부 결과다. H2는 이 조건에서 기각되지만 프레임 산포 또는 거리 변화량을 허용하면 좁은 교집합이 다시 생긴다(5절). 따라서 H2를 확정적으로 배제하지 않는다. '
    if h3k:caveat+=f'폰 높이 1.2 ~ 1.7 m를 추가한 별도 추측에서는 H3이 k {h3k[0]:.5f} ~ {h3k[1]:.5f}, 폰 높이 {h3height[0]:.5f} ~ {h3height[1]:.5f} m로 좁아진다. '
    rejected_by_phone=[name for name,v in h.items() if v['k_interval'] and not v['phone_prior']['k_interval']]
    caveat+=f'폰 높이 제약만으로 추가 기각되는 가설: {", ".join(rejected_by_phone) or "없음"}.\n'
    body=body.replace('## 1. 방법',caveat+'\n## 1. 방법')
    if all('tail_sensitivity' in v for v in a.values()):
        tails=['### 거리 회귀의 꼬리 표본 민감도','','| 대상 | 실제 채택 거리 m | 채택 폭 최솟값·최댓값 m | 1.5 IQR 밖 개수 | 그 안에서만 재계산한 기울기 m/m |','|---|---|---|---|---|']
        for name,v in a.items():
            q=v['tail_sensitivity'];dr=q['accepted_distance_range_m'];wr=q['accepted_width_range_m'];tails.append(f'| {name} | {dr[0]:.5f} ~ {dr[1]:.5f} | {wr[0]:.5f} ~ {wr[1]:.5f} | {q["flagged"]} | {q["slope_inside_fences_m_per_m"]:.6f} |')
        tails+=['','이 표는 폭 분포의 Q1 - 1.5 IQR ~ Q3 + 1.5 IQR 범위만 사용한 사후 진단이다. 채택 규칙·대표 폭·기본 회귀·그 95 % 구간은 바꾸지 않았다. 황색 A처럼 꼬리 표본을 제외하면 회귀가 크게 바뀌는 경우, 기본 양의 기울기를 지면·포즈의 거리 편향으로 곧바로 해석할 수 없다. 좁은 교차점이 실제 마모인지 국소 잘못된 검출인지는 미확인이다. 거리 기반 k 민감도는 보수적인 스트레스 분석으로 유지한다.','']
        body=body.replace('### 스플랫 경로 불일치 추가 조사','\n'.join(tails)+'\n### 스플랫 경로 불일치 추가 조사')
    report_lines=body.splitlines()
    for i,line in enumerate(report_lines):
        if i and re.fullmatch(r'\|(?:---\|)+',line):
            report_lines[i]='|'+'---|'*(report_lines[i-1].count('|')-1)
    body='\n'.join(report_lines)+'\n'
    (out/'REPORT-08.md').write_text(body,encoding='utf8')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True);ap.add_argument('--pixel',type=float,default=.002);ap.add_argument('--spacing',type=float,default=.02);ap.add_argument('--max-distance',type=float,default=4.);ap.add_argument('--frame-step',type=int,default=1);ap.add_argument('--bootstrap',type=int,default=2000);ap.add_argument('--seed',type=int,default=430);args=ap.parse_args()
    base=args.base.resolve();out=base/'_out/scale';out.mkdir(exist_ok=True)
    for sub in ('figs','ipm'):(out/sub).mkdir(exist_ok=True)
    required=['_out/colmap/undistorted/images','_out/colmap/undistorted/sparse_txt','_out/mesh/ground_stats.json','_out/mesh/grid_audit.npz','_out/splat/splat.ply','_out/scale/recon/mosaic_mean.png','_out/scale/recon/mosaic_meta.npy']
    missing=[s for s in required if not (base/s).exists()]
    if missing:raise SystemExit('선행 조건 없음: '+str(missing))
    cv2.setNumThreads(2);rng=np.random.default_rng(args.seed)
    source=json.loads((base/'_out/mesh/ground_stats.json').read_text(encoding='utf8'));M=np.array(source['transform']['world_to_mesh_4x4']);poses,K,W,H=cameras(base,M)
    mosaic=read_image(out/'recon/mosaic_mean.png');meta=np.load(out/'recon/mosaic_meta.npy');rows,pts=candidates(mosaic,meta);dump(out/'candidates.json',rows)
    targets,white=targets_from_candidates(rows,pts,np.array([p[1] for p in poses.values()]));print('targets',plain(targets),flush=True)
    records,examples=measure_frames(base,out,targets,poses,K,W,H,args)
    agg,ratio=aggregate(records,targets,rng,args.bootstrap);print('widths', {k:plain(v['frame_medians']) for k,v in agg.items()},flush=True)
    xyz,rgb=load_splat(base,M);sw=splat_widths(xyz,rgb,targets);curb,curves=curb_measure(base,xyz,targets,out);hs,gap=hypotheses(agg,curb,targets)
    gates=dict(G1=sum(v['accepted']>=200 and v['frame_medians']['n']>=20 for name,v in agg.items() if name.startswith('yellow'))>=2 and (out/'profiles.csv').exists(),G2=all(np.isfinite(sw[k]['width_fwhm_m']) and np.isfinite(agg[k]['distance_regression']['slope_m_per_m']) and np.all(np.isfinite(agg[k]['distance_regression']['ci95_frame_bootstrap'])) and np.isfinite(agg[k]['frame_medians']['std']) for k in sw) and np.all(np.isfinite(ratio['ci95'])),G3=len(hs)==3 and all('phone_height_m' in h and 'phone_prior' in h for h in hs.values()))
    result=dict(created=datetime.now().isoformat(),assumed_scale_m_per_unit=source['scale']['meters_per_scene_unit'],parameters=vars(args)|{'base':str(base)},pose_count=len(poses),targets=agg,white_1=white,yellow_ratio=ratio,splat_widths=sw,curb=curb,lane_spacing_m=gap,hypotheses=hs,gates=gates)
    dump(out/'measurements.json',result);figures(out,mosaic,meta,targets,agg,records,examples,curb,curves,hs);report(out,result,args)
    print('curb',plain(curb),'hypotheses',plain(hs),'gates',gates,flush=True)


if __name__=='__main__':main()
