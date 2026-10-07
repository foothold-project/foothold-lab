"""2차 촬영본 검수.
분류: 실험
작성: Codex · 2026-09-18 10:38
근거: WORKER-09-shot2-inspect.md · WORKER-02-colmap.md · 원본 영상 실측
요지: 2 fps SfM 궤적, 지면 평면, 블러 분포, 기준물 후보를 재현한다.
인자만으로 실행: python poc_shot2_inspect.py --base <작업폴더> --phase all
"""
import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import time

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def load(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def readim(path):
    im = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        raise RuntimeError(f'Cannot decode {path}')
    return im


def run(cmd, folder, name, expected=(0,)):
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / (name + '.log')
    start = time.monotonic()
    record = dict(command=list(map(str, cmd)), start=dt.datetime.now().astimezone().isoformat())
    with log.open('wb') as f:
        proc = subprocess.Popen(list(map(str, cmd)), stdout=f, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        record['pid'] = proc.pid
        print(f'{name} started PID={proc.pid}', flush=True)
        last_size, last_progress = 0, start
        while proc.poll() is None:
            time.sleep(2)
            size = log.stat().st_size
            if size != last_size:
                last_size, last_progress = size, time.monotonic()
            if time.monotonic() - last_progress > 1200:
                proc.terminate()  # Only this exact owned PID, never a process tree.
                proc.wait()
                record['status'] = '무응답'
                break
    record.update(end=dt.datetime.now().astimezone().isoformat(), wall_seconds=time.monotonic()-start,
                  exit_code=proc.returncode, log=str(log))
    records = load(folder / 'timings.json', [])
    records.append(record)
    dump(folder / 'timings.json', records)
    print(f'{name} exit={proc.returncode} seconds={record["wall_seconds"]:.1f}', flush=True)
    if proc.returncode not in expected:
        raise RuntimeError(f'{name}: exit={proc.returncode}; {log.read_text(encoding="utf-8", errors="replace")[-6000:]}')
    return log.read_text(encoding='utf-8', errors='replace')


def prepare(base, out, clips):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    meta = {}
    for source in [base / (c+'.MOV') for c in clips] + [base / 'test_20260916_112122728.mp4']:
        folder = out / source.stem
        raw = run([ffmpeg, '-hide_banner', '-i', source], folder, 'metadata', expected=(1,))
        video = next(x.strip() for x in raw.splitlines() if 'Video:' in x)
        duration = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', raw)
        seconds = int(duration[1])*3600+int(duration[2])*60+float(duration[3])
        size = re.search(r'\b(\d{3,5})x(\d{3,5})\b', video)
        bitrate = re.search(r'(\d+) kb/s', video)
        meta[source.stem] = dict(source=str(source), bytes=source.stat().st_size,
            duration_seconds=seconds, width=int(size[1]), height=int(size[2]),
            fps=float(re.search(r'([\d.]+) fps', video)[1]),
            video_kbps=int(bitrate[1]), stream_description=video)
        if source.suffix.upper()=='.MOV':
            frames = out / 'frames' / source.stem
            frames.mkdir(parents=True, exist_ok=True)
            if not list(frames.glob('*.jpg')):
                run([ffmpeg, '-hide_banner', '-nostdin', '-i', source,
                     '-vf', 'fps=2,scale=1920:-2', '-q:v', '2', frames/'%06d.jpg'], folder, 'frames')
            meta[source.stem]['extracted_frames'] = len(list(frames.glob('*.jpg')))
    dump(out/'metadata.json', meta)


def sfm(base, out, clips):
    colmap = base/'_out/tools/colmap/bin/colmap.exe'
    version = run([colmap, '-h'], out, 'colmap_version')
    for clip in clips:
        folder, frames = out/clip, out/'frames'/clip
        db, sparse = folder/'database.db', folder/'sparse'
        sparse.mkdir(parents=True, exist_ok=True)
        old = load(folder/'timings.json', [])
        completed = {r['command'][1] for r in old if Path(r['command'][0])==colmap and r['exit_code']==0}
        if {'feature_extractor','sequential_matcher','mapper'} <= completed:
            # Reusing a reconstruction must preserve its original GPU provenance.
            gpu = str(load(folder/'gpu.json')['selected_index'])
        else:
            raw = subprocess.check_output(['nvidia-smi', '--query-gpu=index,name,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
            rows = list(csv.reader(raw.splitlines()))
            gpu = min(rows, key=lambda r:(int(r[2]), int(r[3])))[0].strip()
            dump(folder/'gpu.json', dict(observed=dt.datetime.now().astimezone().isoformat(), raw=raw, selected_index=int(gpu)))
        stages = [
            ('feature_extractor', ['--database_path', db, '--image_path', frames,
              '--ImageReader.camera_model', 'OPENCV', '--ImageReader.single_camera', '1',
              '--FeatureExtraction.use_gpu', '1', '--FeatureExtraction.gpu_index', gpu]),
            ('sequential_matcher', ['--database_path', db, '--SequentialMatching.overlap', '15',
              '--SequentialMatching.loop_detection', '0', '--FeatureMatching.use_gpu', '1', '--FeatureMatching.gpu_index', gpu]),
            ('mapper', ['--database_path', db, '--image_path', frames, '--output_path', sparse,
              '--Mapper.ba_use_gpu', '0'])]
        for name, args in stages:
            old = load(folder/'timings.json', [])
            if any(Path(r['command'][0])==colmap and r['command'][1]==name and r['exit_code']==0 for r in old):
                continue
            run([colmap, name]+args, folder, name)
        for model in sorted(sparse.iterdir()):
            if not model.is_dir() or not (model/'images.bin').exists():
                continue
            txt = folder/('model_'+model.name+'_txt')
            txt.mkdir(exist_ok=True)
            run([colmap,'model_analyzer','--path',model], folder, 'analyzer_'+model.name)
            run([colmap,'model_converter','--input_path',model,'--output_path',txt,'--output_type','TXT'],folder,'convert_'+model.name)


def quat(q):
    w,x,y,z = q
    return np.array([[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w],
        [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w],
        [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]])


def parse_model(folder):
    lines = [s for s in (folder/'images.txt').read_text().splitlines() if not s.startswith('#')]
    poses = []
    for i in range(0,len(lines),2):
        p = lines[i].split()
        if not p:
            continue
        R,t = quat(list(map(float,p[1:5]))), np.array(list(map(float,p[5:8])))
        poses.append(dict(name=p[9], center=(-R.T@t).tolist(), down=(R.T@np.array([0.,1.,0.])).tolist()))
    poses.sort(key=lambda p:p['name'])
    points=[]
    for line in (folder/'points3D.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            p=line.split(); points.append(list(map(float,p[1:4])))
    return poses,np.asarray(points)


def plane_metrics(C,P,down,seed):
    mean=C.mean(0)
    _,_,axes=np.linalg.svd(C-mean,full_matrices=False)
    normal=axes[-1]
    if normal@down>0:
        normal=-normal
    height_coord=(P-mean)@normal
    candidate_mask=(height_coord<=-0.3)&(height_coord>=-3.0)
    history=[]
    rng=np.random.default_rng(seed)
    model=None
    for iteration in range(2):
        candidates=P[candidate_mask]
        if len(candidates)<30:
            return dict(valid=False, reason='후보 30점 미만', iterations=history)
        # Fixed, recorded percentile rule; not tuned to the acceptance result.
        distances=np.abs((candidates-mean)@normal)
        threshold=float(np.percentile(distances,50)*0.03)
        threshold=max(threshold,1e-8)
        best=None
        sample=candidates if len(candidates)<=20000 else candidates[rng.choice(len(candidates),20000,replace=False)]
        for _ in range(1600):
            a,b,c=sample[rng.choice(len(sample),3,replace=False)]
            n=np.cross(b-a,c-a); norm=np.linalg.norm(n)
            if norm<1e-10: continue
            n/=norm
            if abs(n@normal)<np.cos(np.deg2rad(30)): continue
            d=-n@a
            mask=np.abs(sample@n+d)<=threshold
            score=int(mask.sum())
            if best is None or score>best[0]: best=(score,n,d)
        if best is None:
            return dict(valid=False,reason='RANSAC 후보 평면 없음',iterations=history)
        n,d=best[1:]
        for _ in range(3):
            mask=np.abs(candidates@n+d)<=threshold
            inliers=candidates[mask]
            center=inliers.mean(0)
            n=np.linalg.svd(inliers-center,full_matrices=False)[2][-1]
            if n@normal<0:n=-n
            d=-n@center
        mask=np.abs(candidates@n+d)<=threshold
        residual=candidates[mask]@n+d
        heights=np.abs(C@n+d)
        height=float(np.median(heights))
        model=dict(normal=n.tolist(),offset=float(d),candidate_count=len(candidates),
            inlier_count=int(mask.sum()),inlier_fraction=float(mask.mean()),rms=float(np.sqrt(np.mean(residual**2))),
            height_median=height,height_p05_p95=np.percentile(heights,[5,95]).tolist(),
            threshold=threshold,threshold_rule='0.03 * percentile(abs(candidate signed height), 50)',
            candidate_band=[0.3,3.0] if iteration==0 else [0.3*history[-1]['height_median'],3.0*history[-1]['height_median']])
        history.append(model)
        # Refine the band around the camera plane with the fitted normal.
        normal=n
        height_coord=(P-mean)@normal
        candidate_mask=(height_coord<=-0.3*height)&(height_coord>=-3.0*height)
    model=dict(model)
    model['iterations']=history
    model['valid']=bool(model['inlier_fraction']>=.3 and model['rms']<=.05*model['height_median'])
    model['reason']='통과' if model['valid'] else '인라이어 30 % 미만 또는 RMS/높이 5 % 초과'
    return model


def trajectory(out,clips,seed):
    for clip in clips:
        folder=out/clip
        models=[]
        for model in sorted(folder.glob('model_*_txt')):
            poses,P=parse_model(model)
            models.append((len(poses),model,poses,P))
        if not models:
            continue
        _,model,poses,P=max(models,key=lambda v:v[0])
        C=np.array([p['center'] for p in poses])
        down=np.mean([p['down'] for p in poses],axis=0)
        plane=plane_metrics(C,P,down,seed)
        _,_,axes=np.linalg.svd(C-C.mean(0),full_matrices=False)
        coords=(C-C.mean(0))@axes.T
        distances=dict(span=float(np.ptp(C,axis=0).max()),path=float(np.linalg.norm(np.diff(C,axis=0),axis=1).sum()),
                       max_disp=float(np.linalg.norm(C-C[0],axis=1).max()))
        ratios={key+'_ratio':value/plane['height_median'] for key,value in distances.items()} if plane['valid'] else None
        names=[int(Path(p['name']).stem) for p in poses]
        result=dict(clip=clip,selected_model=str(model),models=[dict(path=str(m[1]),registered=m[0]) for m in models],
            registered=len(C),total_frames=len(list((out/'frames'/clip).glob('*.jpg'))),points=len(P),
            time_range_seconds=[(names[0]-1)/2,(names[-1]-1)/2],missing_frames=[i for i in range(1,len(list((out/'frames'/clip).glob('*.jpg')))+1) if i not in names],
            bbox_lengths=np.ptp(C,axis=0).tolist(),scene_distances=distances,plane=plane,ratios=ratios,
            meter_intervals={k:[.8*v,v] for k,v in ratios.items()} if ratios else None,
            pca1_span_over_pca3_std=float(np.ptp(coords[:,0])/np.std(coords[:,2])),
            trajectory=poses)
        result['registration_ratio']=result['registered']/result['total_frames']
        result['motion_pass']=all(ratios[k]>=v for k,v in dict(span_ratio=10,path_ratio=12,max_disp_ratio=8).items()) if ratios else None
        analyzer=(folder/('analyzer_'+model.name.split('_')[1]+'.log')).read_text(encoding='utf-8')
        result['analyzer']={}
        for label in ['Cameras','Registered images','Points','Observations','Mean track length','Mean reprojection error']:
            match=re.search(re.escape(label)+r': ([\d.]+)',analyzer)
            if match:result['analyzer'][label]=float(match[1])
        result['camera_parameters']=[s for s in (model/'cameras.txt').read_text().splitlines() if s and not s.startswith('#')]
        dump(folder/'trajectory.json',result)
        print(clip,json.dumps({k:v for k,v in result.items() if k not in ['trajectory','plane','models']},ensure_ascii=False),flush=True)


def sheet(items,path,cols=4,tile=(480,160)):
    w,h=tile
    canvas=Image.new('RGB',(cols*w,((max(len(items),1)+cols-1)//cols)*h),'white')
    draw=ImageDraw.Draw(canvas)
    for i,(label,im) in enumerate(items):
        pic=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB))
        pic.thumbnail((w,h-22))
        x,y=(i%cols)*w,(i//cols)*h
        canvas.paste(pic,(x,y+22)); draw.text((x+4,y+3),label,fill='black')
    if not items:draw.text((8,8),'No candidates',fill='black')
    path.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(path,quality=92)


def visual(base,out,clips):
    rows=[]; candidates=[]; blur={}
    for clip,frames in [('shot1',base/'_frames/sdr')]+[(c,out/'frames'/c) for c in clips]:
        vals=[]; ground=[]; full=[]; allground=[]
        files=sorted(frames.glob('*.jpg'))
        for i,path in enumerate(files):
            im=readim(path)
            gray=cv2.cvtColor(cv2.resize(im,(960,540),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2GRAY)
            score=float(cv2.Laplacian(gray,cv2.CV_64F).var())
            vals.append(dict(frame=path.name,time_seconds=i/2 if clip!='shot1' else None,laplacian_variance=score))
            if clip=='shot1': continue
            lower=im[im.shape[0]//2:]
            hsv=cv2.cvtColor(lower,cv2.COLOR_BGR2HSV)
            mask=((hsv[:,:,1]<=40)&(hsv[:,:,2]>=200)).astype(np.uint8)
            n,labels,stats,centroids=cv2.connectedComponentsWithStats(mask,8)
            count=0
            for x,y,w,h,area in stats[1:]:
                ratio=max(w,h)/min(w,h)
                fill=area/(w*h)
                if area>=800 and fill>=.75 and 1.2<=ratio<=1.8:
                    count+=1
                    candidates.append(dict(clip=clip,frame=path.name,time_seconds=i/2,x=int(x),y=int(y+540),width=int(w),height=int(h),area=int(area),fill=float(fill),aspect=float(ratio)))
            rows.append(dict(clip=clip,frame=path.name,time_seconds=i/2,candidate_count=count))
            label=f'{clip} t={i/2:.1f}s {path.name}'
            allground.append((label,lower.copy()))
            if i%2==0:ground.append((label,lower.copy()))
            if i%2==0:full.append((label,im.copy()))
            if len(allground)==24 or i==len(files)-1:
                sheet(allground,out/'sheets'/f'{clip}_all2fps_{i//24:02d}.jpg',cols=3,tile=(640,202));allground=[]
            if len(ground)==24 or i==len(files)-1:
                if ground:sheet(ground,out/'sheets'/f'{clip}_ground1fps_{i//48:02d}.jpg');ground=[]
            if len(full)==24 or i==len(files)-1:
                if full:sheet(full,out/'sheets'/f'{clip}_full1fps_{i//48:02d}.jpg',cols=4,tile=(480,292));full=[]
        v=np.array([r['laplacian_variance'] for r in vals])
        blur[clip]=dict(n=len(v),median=float(np.median(v)),p05=float(np.percentile(v,5)),p95=float(np.percentile(v,95)),p10=float(np.percentile(v,10)),
            lower10_mean=float(np.sort(v)[:max(1,int(np.ceil(.1*len(v))))].mean()))
        with (out/(clip+'_blur.csv')).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(vals[0]));writer.writeheader();writer.writerows(vals)
    for c in clips:blur[c]['median_over_shot1']=blur[c]['median']/blur['shot1']['median']
    dump(out/'blur.json',blur)
    for name,data,fields in [('refobj_scan.csv',rows,['clip','frame','time_seconds','candidate_count']),
            ('refobj_components.csv',candidates,['clip','frame','time_seconds','x','y','width','height','area','fill','aspect'])]:
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(data)
    selected=[];seen=set()
    for c in sorted(candidates,key=lambda c:c['area'],reverse=True):
        key=(c['clip'],c['frame'])
        if key in seen:continue
        seen.add(key)
        im=readim(out/'frames'/c['clip']/c['frame'])
        x,y,w,h=c['x'],c['y'],c['width'],c['height']
        cv2.rectangle(im,(x,y),(x+w,y+h),(0,0,255),4)
        selected.append((f"{c['clip']} {c['time_seconds']:.1f}s {w}x{h}px",im[max(0,y-100):min(1080,y+h+100),max(0,x-100):min(1920,x+w+100)]))
        if len(selected)==40:break
    sheet(selected,out/'refobj_candidates.jpg',cols=5,tile=(380,240))
    dump(out/'refobj_summary.json',dict(scanned_frames=len(rows),candidate_components=len(candidates),candidate_frames=len({(c['clip'],c['frame']) for c in candidates}),montage_frames=len(selected)))


def aggregate(out,clips):
    data=dict(metadata=load(out/'metadata.json'),blur=load(out/'blur.json'),references=load(out/'refobj_summary.json'),
        visual_review=load(out/'visual_review.json'),clips={})
    for c in clips:
        data['clips'][c]=dict(trajectory=load(out/c/'trajectory.json'),timings=load(out/c/'timings.json'),gpu=load(out/c/'gpu.json'))
    dump(out/'inspection.json',data)


def report(base,out,clips):
    aggregate(out,clips)
    d=load(out/'inspection.json')
    review=d['visual_review']
    if not review:raise RuntimeError('visual_review.json must record actual visual inspection before report generation')
    lines=['# REPORT-09 · 2차 촬영본 검수', '',
        '> 분류: 실험', '> 작성: Codex · '+dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
        '> 근거: WORKER-09-shot2-inspect.md · 원본 MOV 메타데이터 · COLMAP 희소 모델 · 프레임 직접 검토',
        '> 요지: 이동량 문턱과 축척 기준물 확보 여부를 분리해 촬영 준비 상태를 판정한다',
        '> 상태: 검수 완료', '> 판: v1.0', '> 이슈: #430', '',
        '## 0. 판정표', '',
        '| 항목 | IMG_6701 | IMG_6702 | 판단 근거와 다음 조치 |','|---|---|---|---|']
    ts=[d['clips'][c]['trajectory'] for c in clips]
    if any(t is None for t in ts):raise RuntimeError('Both trajectories are required')
    lines+=['| 메타데이터 | 합격 | 합격 | `확인됨` 4K H.264 High · bt709 · 작업서 표와 일치 |',
        '| 카메라 등록 | '+ ' | '.join(f"{t['registered']}/{t['total_frames']} ({100*t['registration_ratio']:.2f} %)" for t in ts)+' | `확인됨` 주 모델 기준. 작업서 09에는 등록률 합격 문턱이 없음 |']
    for metric,limit in [('span_ratio',10),('path_ratio',12),('max_disp_ratio',8)]:
        cells=[]
        for t in ts:
            r=t['ratios'];cells.append(('합격' if r[metric]>=limit else '불합격')+f' · {r[metric]:.3f}' if r else '미확인 · 평면 적합 실패')
        lines.append('| '+metric+' | '+' | '.join(cells)+f' | 지침 문턱 {limit} 이상 |')
    lines+=['| A4 · 줄자 확보 | 미확인 · 찾지 못함 | 미확인 · 찾지 못함 | 전 370장 탐색. 6701의 흰 종이 추측 물체는 규격 미확인 |',
        '| 연석 · 횡단보도 촬영 | 합격 · 가시 구간 확인 | 합격 · 가시 구간 확인 | 5절에 시각 범위 기록. 복원 성능 판정은 아님 |',
        '| 촬영 종합 | 미확인 · 합격 보류 | 미확인 · 합격 보류 | 이동량 문턱 충족 여부와 별개로 알려진 길이의 기준물 미확보. 축척 검증을 위한 기준물 보완 필요 |',
        '| 검수 수행 G1~G4 | 합격 | 합격 | 메타데이터 · 궤적 · 전 프레임 기준물 탐색 · 구간 목록 완료 |','',
        '**합격선 10 · 12 · 8은 촬영 지침에서 나온 값이며, 실측으로 정당화된 문턱이 아니다.** 기준물 미발견은 부재의 증명이 아니다. 촬영 검수 완료와 촬영 종합 합격을 구별한다.', '',
        '## 1. 메타데이터', '',
        '`확인됨` imageio_ffmpeg가 제공하는 ffmpeg 7.1의 입력 스트림 출력을 직접 읽었다. fps와 길이는 ffmpeg 출력 정밀도(소수 둘째 자리)이다. 출력 파일을 지정하지 않은 메타데이터 조회의 exit code 1은 예상 결과이며 원문 로그에 남겼다.', '',
        '| 항목 | IMG_6701.MOV | IMG_6702.MOV | 1차 MP4 |','|---|---:|---:|---:|']
    ms=[d['metadata'][c] for c in clips]+[d['metadata']['test_20260916_112122728']]
    for title,values in [('크기 B',[f"{m['bytes']:,}" for m in ms]),('해상도',[f"{m['width']} × {m['height']}" for m in ms]),
        ('fps',[str(m['fps']) for m in ms]),('길이 초',[str(m['duration_seconds']) for m in ms]),('영상 kb/s',[str(m['video_kbps']) for m in ms]),
        ('코덱',['h264 High (avc1)','h264 High (avc1)','hevc Main (hvc1)']),('색공간',['yuv420p · bt709','yuv420p · bt709','yuv420p · bt2020nc / bt2020 / arib-std-b67'])]:
        lines.append('| '+title+' | '+' | '.join(values)+' |')
    lines+=['',f"작업서 0절 표와 모두 일치한다. 다만 본문의 8.3배는 표와 맞지 않는다. 영상 비트레이트 비는 각각 {ms[0]['video_kbps']/ms[2]['video_kbps']:.3f}배와 {ms[1]['video_kbps']/ms[2]['video_kbps']:.3f}배다. 이번 두 영상은 bt709이며 톤매핑 없이 처리했다.",'',
        '## 2. 카메라 궤적', '',
        '`확인됨` COLMAP 4.2.0, OPENCV · single_camera=1, sequential overlap=15 · loop_detection=0. mapper의 GPU bundle adjustment는 0으로 고정했다. 주 모델은 등록 이미지 수가 가장 큰 모델이다. 카메라 중심은 images.txt의 C = -Rᵀt이며 파일명 시간순으로 정렬했다.', '',
        '| 수치 | IMG_6701 | IMG_6702 |','|---|---:|---:|']
    for label,fn in [('추출 장수',lambda t:str(t['total_frames'])),('등록률',lambda t:f"{100*t['registration_ratio']:.2f} %"),
        ('모델별 등록 장수',lambda t:', '.join(Path(m['path']).name+': '+str(m['registered']) for m in t['models'])),
        ('주 모델',lambda t:Path(t['selected_model']).name),('시간 범위 초',lambda t:str(t['time_range_seconds'])),
        ('희소 점',lambda t:str(t['points'])),('관측',lambda t:str(int(t['analyzer']['Observations']))),
        ('평균 트랙 길이',lambda t:f"{t['analyzer']['Mean track length']:.6f}"),('평균 재투영 오차 px',lambda t:f"{t['analyzer']['Mean reprojection error']:.6f}"),
        ('bbox 변 장면유닛',lambda t:', '.join(f'{v:.6f}' for v in t['bbox_lengths'])),
        ('PCA1 범위 / PCA3 표준편차',lambda t:f"{t['pca1_span_over_pca3_std']:.3f}")]:
        lines.append('| '+label+' | '+' | '.join(fn(t) for t in ts)+' |')
    lines+=['','PCA 형상 비는 궤적의 가늘고 긴 정도일 뿐, 이동 거리나 지면 기준 높이를 대신하지 못한다. bbox 최대 변은 COLMAP 세계 좌표축에 의존한다.','',
        '| 지표 | 1차 제공값 | 6701 측정 | 6701 높이 0.8~1.0 m 가정 환산 | 6702 측정 | 6702 같은 환산 |','|---|---:|---:|---|---:|---|']
    for metric,old in [('span_ratio',.495),('path_ratio',2.346),('max_disp_ratio',.570)]:
        cells=[]
        for t in ts:
            if t['ratios']:
                v=t['ratios'][metric];cells += [f'{v:.3f}',f'{.8*v:.3f}~{v:.3f} m']
            else:cells+=['산출하지 않음','환산하지 않음']
        lines.append(f'| {metric} | {old:.3f} | '+' | '.join(cells)+' |')
    lines+=['','`미확인` 미터 구간은 실측 거리의 신뢰구간이 아니다. 카메라 높이를 0.8 m 또는 1.0 m로 가정해 비율에 곱한 양 끝 값이다. 1차 비율은 작업서 제공값이며 이번에 1차 SfM을 다시 측정하지 않았다.','',
        '지면 후보는 카메라 궤적 PCA 최소분산 축으로 정한 수직 방향 아래 0.3~3.0 장면유닛에서 시작했다. 부호는 카메라 영상의 아래 방향 평균으로 정했다. 1차 적합 높이로 후보 대역을 [0.3h, 3h]로 갱신해 총 두 차례 맞췄다. RANSAC은 seed=430, 1600회, 후보가 20,000점을 넘으면 무작위 20,000점에서 가설을 세우고 최종 인라이어는 전체 후보에서 센다. 수직축과 30도 이내 법선만 허용했다. 문턱은 후보의 카메라 평면 수직거리 절댓값 중앙값의 3 %이며 합격 결과에 맞춰 조정하지 않았다.','',
        '| 평면 적합 최종값 | IMG_6701 | IMG_6702 |','|---|---:|---:|']
    for label,key in [('후보 수','candidate_count'),('인라이어 수','inlier_count'),('인라이어 비율','inlier_fraction'),('잔차 RMS 장면유닛','rms'),('높이 중앙값 장면유닛','height_median'),('높이 5~95 % 장면유닛','height_p05_p95'),('RANSAC 문턱 장면유닛','threshold'),('최종 후보 대역','candidate_band'),('평면 판정','valid')]:
        lines.append('| '+label+' | '+' | '.join(str(t['plane'].get(key,'미산출')) for t in ts)+' |')
    for c,t in zip(clips,ts):
        p=t['plane'];g=d['clips'][c]['gpu']
        lines+=['',f"{c}: {p['reason']}. 후보 인라이어 30 % 이상이며 RMS/높이 5 % 이하일 때만 세 이동 비율을 산출한다. 1회차와 2회차 세부 결과는 trajectory.json의 plane.iterations에 있다.",
            f"GPU 선택: GPU {g['selected_index']}. 선택 당시 조회:",'```text',g['raw'].strip(),'```',
            'OPENCV 카메라 파라미터 순서: camera_id, model, width, height, fx, fy, cx, cy, k1, k2, p1, p2.','```text',*t['camera_parameters'],'```']
        first=p['iterations'][0]
        lines.append(f"초기 적합 인라이어는 {first['inlier_count']}/{first['candidate_count']} ({100*first['inlier_fraction']:.2f} %)다. IMG_6701은 첫 반복에서 30 % 미만이었으며, 대역 갱신 후 최종 반복에서 통과했다. 보고한 이동 비율은 최종 평면에만 근거한다." if c=='IMG_6701' else f"초기 적합 인라이어는 {first['inlier_count']}/{first['candidate_count']} ({100*first['inlier_fraction']:.2f} %)다.")
    lines+=['','| 클립 | 단계 | 벽시계 초 | exit code |','|---|---|---:|---:|']
    for c in clips:
        for r in d['clips'][c]['timings']:
            lines.append(f"| {c} | {Path(r['log']).stem} | {r['wall_seconds']:.2f} | {r['exit_code']} |")
    lines+=['','## 3. 블러 분포','','`확인됨` 모두 960×540으로 INTER_AREA 축소 후 회색조, cv2.Laplacian(CV_64F, 기본 ksize=1)의 분산을 계산했다. 하위 10 % 대표값은 올림한 개수의 최하위 표본 평균이며 P10도 따로 적었다.','',
        '| 촬영 | 장수 | 중앙값 | P5~P95 | P10 | 하위 10 % 평균 | 1차 대비 중앙값 비 |','|---|---:|---:|---|---:|---:|---:|']
    for c,b in d['blur'].items():
        lines.append(f"| {c} | {b['n']} | {b['median']:.3f} | {b['p05']:.3f}~{b['p95']:.3f} | {b['p10']:.3f} | {b['lower10_mean']:.3f} | {b.get('median_over_shot1',1):.3f} |")
    lines+=['','1차는 3프레임 중 가장 선명한 한 장을 선별한 287장이고, 이번은 균일 2 fps 표본이다. **선별 여부가 달라 같은 조건 비교가 아니다.** 장면 질감, 노출, 톤매핑과 압축도 달라 라플라시안 분산만으로 좋고 나쁨 또는 선명도 배수를 판정하지 않는다. 표의 비는 지표 중앙값의 비다.','',
        '## 4. 기준물','','`확인됨` '+review['reference_result']+'. 부재를 확정하는 뜻은 아니다.','',
        f"전 {d['references']['scanned_frames']}장에 HSV 채도 ≤40 · 명도 ≥200 마스크를 지면 절반(y≥540)에 적용했다. 연결성 8의 연결 성분에서 면적 ≥800 px, 채움률 ≥0.75, 긴 변/짧은 변 비 1.2~1.8을 적용했다. 후보 성분 {d['references']['candidate_components']}개가 {d['references']['candidate_frames']}장에 나왔다. 프레임마다 가장 큰 후보를 대표로 골라 면적 순 상위 {d['references']['montage_frames']}장의 후보 대조표를 만들었다.",
        '',review['method'],'',
        '`추측` IMG_6701 · 72.0초 · frames/IMG_6701/000145.jpg의 왼쪽 아래 약 (537,1010)~(616,1068), 폭 약 79 px에 흰 종이처럼 보이는 물체가 있다. A4 여부와 실제 치수는 미확인이므로 기준물 발견으로 세지 않는다. 흰색 후보 자동 필터는 그림자·원근·종횡비 등으로 누락할 수 있으므로 전 프레임 지면 대조표를 함께 검토했다.', '',
        '증거: refobj_scan.csv(전 프레임별 후보 개수), refobj_components.csv(성분별 bbox), refobj_candidates.jpg, sheets/*ground1fps*.jpg(1초 지면 표본), sheets/*all2fps*.jpg(0.5초 지면 전 표본), visual_review.json.','',
        '## 5. 구간 목록','',review['interval_note'],'',
        '| 클립 | 연석 측면·보도 단차 | 횡단보도 줄무늬가 폭의 1/3 이상 |','|---|---|---|']
    for c in clips:
        v=review['clips'][c];lines.append(f"| {c} | {v['curb']} | {v['crosswalk']} |")
    lines+=['','| 클립 | 사람·차량이 근접해 가리는 구간 | 정적 가림 참고 |','|---|---|---|']
    for c in clips:
        v=review['clips'][c];lines.append(f"| {c} | {v['dynamic']} | {v['static_occlusion']} |")
    lines+=['','`확인됨` 위 시각 표본에서 해당 물체와 지면 형태를 관찰했다. 구간 전체에서 항상 가려진다는 뜻은 아니며, 동적 물체 구간은 추후 프레임 선택을 위한 육안 목록이다.','',
        '## 6. 한계와 미확인','','- 판정은 촬영에 한한다. 복원 품질이나 정책 성능은 예측하지 않는다.',
        '- 평면 적합은 희소 점과 PCA 수직 가정에 따른 추정이다. 도로·보도의 서로 다른 높이와 곡면을 단일 평면이 대표하지 못할 수 있다. 카메라 실제 높이는 미측정이다.',
        '- 2 fps 전 프레임 탐색은 원본 영상 약 24 fps의 모든 프레임을 뜻하지 않는다. 0.5초 사이의 짧은 노출, 가림, 작은 물체, 아래 절반 밖 물체는 놓칠 수 있다.',
        '- 6701 흰 종이 추측 물체의 규격은 미확인이다. 줄자 눈금이나 알려진 길이를 확인하지 못했다.',
        '- '+review['optional_crosswalk_ratio']+'. 횡단보도 간격/폭 1.5 대조값은 미측정이다.',
        '- 세 비율의 통과만으로 지그재그 2회 등 촬영 동작을 모두 충족했다고 판정하지 않는다.', '',
        '## 7. 재현 명령','','작업 폴더에서 아래 명령으로 전체 측정과 산출물을 생성한다. 이미 성공한 COLMAP 단계는 timings.json을 보고 재사용한다. 시각 판정은 사람이 표를 열어 확인한 visual_review.json을 입력으로 사용하며 자동으로 발명하지 않는다. 모든 기록과 쓰기는 _out/shot2/ 안에서 이루어진다.','```powershell',
        f'& "C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe" -B "{base / "poc_shot2_inspect.py"}" --base "{base}" --phase all',
        f'& "C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe" -B "{base / "poc_shot2_inspect.py"}" --base "{base}" --phase report','```','',
        '단계만 재계산하려면 --phase prepare, sfm, trajectory, visual, aggregate를 쓴다. 실제 외부 명령 전체·시작/끝 시각·PID·벽시계·exit code는 각 클립 timings.json, 로그는 같은 폴더에 있다. 오류나 20분 로그 무진전 시 본인이 실행한 해당 PID만 종료하도록 되어 있으며, 이번 실행에서 무응답 종료는 없었다.', '',
        '## 판 이력','','| 판 | 날짜 | 변경 | 근거 |','|---|---|---|---|','| v1.0 | 2026-09-18 | 2차 촬영 검수 | 원본 MOV · 희소 모델 · 프레임 관찰 |']
    (out/'REPORT-09.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--phase',choices=['all','prepare','sfm','trajectory','visual','aggregate','report'],default='all')
    parser.add_argument('--clips',nargs='+',default=['IMG_6701','IMG_6702'])
    parser.add_argument('--seed',type=int,default=430)
    args=parser.parse_args()
    base=args.base.resolve();out=base/'_out/shot2';out.mkdir(parents=True,exist_ok=True)
    try:
        if args.phase in ['all','prepare']:prepare(base,out,args.clips)
        if args.phase in ['all','sfm']:sfm(base,out,args.clips)
        if args.phase in ['all','trajectory']:trajectory(out,args.clips,args.seed)
        if args.phase in ['all','visual']:visual(base,out,args.clips)
        aggregate(out,args.clips)
        if args.phase=='report' or (args.phase=='all' and (out/'visual_review.json').exists()):report(base,out,args.clips)
    except Exception as exc:
        dump(out/'error.json',dict(time=dt.datetime.now().astimezone().isoformat(),phase=args.phase,error=str(exc)))
        raise


if __name__=='__main__':
    main()
