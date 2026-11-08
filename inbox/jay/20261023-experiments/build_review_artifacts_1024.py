"""Receipt-checked CPU presentation of B500 and TD200 observations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

FROZEN=Path('C:/mai/wt/foothold-lab/lead-tmp-start-b')
sys.path.insert(0,str(FROZEN))
from foothold_s2.eval.seq_video import verify_done

ROOT=Path(__file__).resolve().parent
RAW=Path('C:/Users/AI-WS01/s2_lab/run_20261024')
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False})
B_ROUGH=RAW/'consumer/captures/f42e9a8963c89047e21452c3fabea68e8f3617c6d196df8a896e81c3cf6d3136'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def ts(s):
    return f'{int(s//3600)}:{int(s//60)%60:02d}:{s%60:05.2f}'

def make_video(name, folders, titles):
    out=ROOT/'figs'/name;out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for folder in folders:
        verify_done(folder/'review.done')
        j=json.loads((folder/'review.json').read_text());z=np.load(folder/'review_feet.npz')
        assert len(z['t'])==600 and not np.isnan(z['vx']).any()
        rows.append((j,z))
    if name=='ex29-u200-review':
        expected=[('flat','pred'),('flat','gt'),('stepping_stones_low','pred'),('stepping_stones_low','gt')]
        for (j,z),(terrain,mode) in zip(rows,expected):
            assert j['checkpoint_sha256']=='5977e6519d3d588a05822d9cba23f592139529fabb2bf357b485fb7fa0d3687b'
            assert j['task_selection']['terrain_type']==terrain and j['task_selection']['level']==0
            assert j['map_modes']['map_mode']['requested']==mode
            assert int(z['map_use_gt'].sum())==(600 if mode=='gt' else 0)
            assert j['physics']['mode']=='fixed' and j['seed']==42
        for a,b in [(0,1),(2,3)]:
            for key in ['task_selection','physics','perception_timing','policy_modes','segments']:
                assert rows[a][0][key]==rows[b][0][key],key
    ass='[Script Info]\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 720\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Arial,16,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,0,0,0,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'
    for panel,(_,z) in enumerate(rows):
        for k in range(300):
            t=k*.04;i=k*2;cmd=z['command'][i];reset=int(z['done'][:i].sum())
            tilt=float(np.rad2deg(np.arccos(np.clip(np.cos(z['roll'][i])*np.cos(z['pitch'][i]),-1,1))))
            text=f't {t:05.2f}s | cmd vx {cmd[0]:.1f} wz {cmd[2]:+.1f} | actual vx {z["vx"][i]:+.2f} wz {z["wz"][i]:+.2f}'
            pos=f'{{\\pos({panel%2*640+10},{panel//2*360+28})}}'
            ass+=f'Dialogue: 0,{ts(t)},{ts(t+.04)},Default,,0,0,0,,{pos}{text}\n'
            pos=f'{{\\pos({panel%2*640+10},{panel//2*360+47})}}'
            ass+=f'Dialogue: 0,{ts(t)},{ts(t+.04)},Default,,0,0,0,,{pos}tilt {tilt:.1f} deg | resets {reset}\n'
    ap=out/'comparison_hud.ass';ap.write_text(ass,encoding='utf-8')
    filters=[]
    for i,title in enumerate(titles):
        filters.append(f"[{i}:v]setpts=PTS-STARTPTS,scale=640:360,drawbox=x=0:y=0:w=iw:h=68:color=black:t=fill,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{title}':x=10:y=4:fontsize=20:fontcolor=white[v{i}]")
    escaped=ap.as_posix().replace(':',r'\:')
    filters.append(f"[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|640_0|0_360|640_360[g];[g]ass=filename='{escaped}'[out]")
    dst=out/'comparison_1x.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y']
    for folder in folders:cmd+=['-i',str(folder/'review.mp4')]
    cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-an','-r','25','-frames:v','300','-c:v','libx264','-crf','19','-pix_fmt','yuv420p',str(dst)]
    subprocess.run(cmd,check=True)
    slow=out/'comparison_05x.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-i',str(dst),'-vf','setpts=2*PTS,tpad=stop_mode=clone:stop_duration=0.08','-an','-r','25','-frames:v','600','-c:v','libx264','-crf','19','-pix_fmt','yuv420p',str(slow)],check=True)
    evidence=[]
    for file,count,duration in [(dst,300,12),(slow,600,24)]:
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames:format=duration','-of','json',str(file)]))
        assert int(probe['streams'][0]['nb_read_frames'])==count
        assert abs(float(probe['format']['duration'])-duration)<.06
        subprocess.run(['ffmpeg','-hide_banner','-v','error','-nostdin','-i',str(file),'-f','null','-'],check=True)
        evidence.append({'file':file.name,'sha256':sha(file),'probe':probe})
    (out/'video_manifest.json').write_text(json.dumps({'inputs':[{'folder':str(f),'receipt_sha256':sha(f/'review.done'),'metadata':j} for f,(j,z) in zip(folders,rows)],'outputs':evidence,'render':'CPU ffmpeg, source timestamps retained in 0.5x video'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'videos':evidence}))

def maps():
    out=ROOT/'figs/ex29-u200-review';sources=[]
    fig,axes=plt.subplots(2,4,figsize=(14,7),layout='constrained')
    for row,kind in enumerate(['flat','stepping_stones_low']):
        file=RAW/f'ex29_model200_{kind}_pred/review_feet.npz';z=np.load(file);i=8
        sources.append({'source':str(file),'sha256':sha(file),'index':i,'time':float(z['map_t'][i])})
        for col,(key,title) in enumerate([('depth','깊이 영상 (m)'),('gt_map','시뮬레이터 정답 높이'),('rough_map','거친 복원 높이'),('refined_map','다듬은 복원 높이')]):
            a=z[key][i];a=a if key=='depth' else a.reshape(32,16)
            lo,hi=(0,3) if key=='depth' else (-1,1)
            im=axes[row,col].imshow(a,cmap='viridis',vmin=lo,vmax=hi,origin='upper');axes[row,col].set(title=f'{kind}\n{title}',xlabel='배열 열',ylabel='배열 행');fig.colorbar(im,ax=axes[row,col],shrink=.75)
    fig.suptitle('EX-29 model_200 · t=0.16초의 실제 입력/지도\n높이 3개는 같은 색 범위. 지도가 생성됨과 보행 성공은 별개',fontsize=14)
    fig.savefig(out/'depth_and_maps.png',dpi=145);plt.close(fig)
    (out/'depth_and_maps.json').write_text(json.dumps({'sources':sources,'height_display_range':[-1,1],'height_units':'m relative to root; clipped [-1,1]; no hit=-1','depth_display_range':[0,3],'display_only':True},indent=2),encoding='utf-8')

if __name__=='__main__':
    if sys.argv[1]=='B':
        make_video('ex28-u500-review',[RAW/'ex23_model500_flat',RAW/'b_model500_flat',RAW/'ex23_model500_rough',B_ROUGH],['EX23 | FLAT | model_500','B | FLAT | model_500','EX23 | ROUGH | model_500','B | ROUGH | model_500'])
    else:
        make_video('ex29-u200-review',[RAW/f'ex29_model200_{t}_{m}' for t,m in [('flat','pred'),('flat','gt'),('stepping_stones_low','pred'),('stepping_stones_low','gt')]],['EX29 | FLAT | PRED | model_200','EX29 | FLAT | GT | model_200','EX29 | LOW STONES | PRED | model_200','EX29 | LOW STONES | GT | model_200'])
        maps()
