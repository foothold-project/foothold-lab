"""Matched, receipt-verified CPU review of four guarded model_1000 captures.

No training, GPU calls, or source modification. Timestamps in the HUD use the
recorder's actual frame-to-step index, not an assumed two steps per frame.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
RAW = Path('C:/Users/AI-WS01/s2_lab/run_20261024')
OUT = ROOT / 'figs/ex28-u1000-review'
MEDIA = RAW / 'b1000_matched_review'
SOURCES = [
    ('EX-23 flat', RAW/'ex23_model1000_flat_guarded24i_r2'),
    ('B flat', RAW/'b_model1000_flat_guarded24i'),
    ('EX-23 rough', RAW/'ex23_model1000_rough_guarded24i'),
    ('B rough', RAW/'b_model1000_rough_guarded24i'),
]
sys.path.insert(0, 'C:/mai/wt/foothold-lab/lead-tmp-start-b')
from foothold_s2.eval.seq_video import verify_done

plt.rcParams.update({'font.family':'Malgun Gothic', 'axes.unicode_minus':False,
                     'font.size':10})
COLORS = ['#007F78', '#D46B30', '#365C8D', '#AB4576']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def support(c):
    """Counts, not trot classification; constant four-foot stance cannot pass."""
    count = c.sum(axis=1)
    diag = (count == 2) & ((c[:, 0] & c[:, 3]) | (c[:, 1] & c[:, 2]))
    bound = (count == 2) & ((c[:, 0] & c[:, 1]) | (c[:, 2] & c[:, 3]))
    return {'two_contact_n':int((count == 2).sum()),
            'diagonal_only_fraction':float(diag.mean()),
            'front_or_hind_only_fraction':float(bound.mean()),
            'diagonal_given_two_contact':float(diag.sum()/(count == 2).sum()) if (count == 2).any() else None,
            'four_contact_fraction':float((count == 4).mean()),
            'no_contact_fraction':float((count == 0).mean())}


def checks():
    assert support(np.ones((5,4),bool))['diagonal_only_fraction'] == 0
    assert support(np.ones((5,4),bool))['diagonal_given_two_contact'] is None
    assert support(np.array([[1,0,0,1],[0,1,1,0]],bool))['diagonal_given_two_contact'] == 1
    assert support(np.array([[1,1,0,0],[0,0,1,1]],bool))['front_or_hind_only_fraction'] == 1


def load():
    rows = []
    for label, folder in SOURCES:
        verify_done(folder/'review.done')
        j = json.loads((folder/'review.json').read_text(encoding='utf-8'))
        z = dict(np.load(folder/'review_feet.npz', allow_pickle=False))
        assert len(z['t']) == 600 and z['joint_pos'].shape == (600,12)
        assert z['foot_names'].tolist() == ['FL_foot','FR_foot','RL_foot','RR_foot']
        assert int(z['map_use_gt'].sum()) == 600 and j['resets'] == int(z['done'].sum())
        assert j['physics']['mode'] == 'fixed' and j['seed'] == 42
        assert not j['render_retry_checks'], 'This matched set expects no retry'
        assert np.allclose(np.diff(z['t']), .02)
        assert len(j['step_contract']['video_sample_step_indices']) == 300
        reader = cv2.VideoCapture(str(folder/'review.mp4')); n = 0; means = []; frames = []
        while True:
            ok, f = reader.read()
            if not ok: break
            means.append(float(f.mean())); frames.append(f); n += 1
        reader.release()
        assert n == 300 and min(means) >= 3, (folder,n,min(means))
        rows.append((label,folder,j,z,frames))
    for a,b in [(0,1),(2,3)]:
        for k in ['task_selection','physics','perception_timing','policy_modes','segments','step_contract']:
            assert rows[a][2][k] == rows[b][2][k], (a,b,k)
        for key in ['command','t','seg','foot_names','joint_names']:
            assert np.array_equal(rows[a][3][key],rows[b][3][key]), key
    return rows


def metrics(rows):
    results = {}
    for label,folder,j,z,frames in rows:
        contact = z['foot_contact']; dt = float(z['dt'])
        speed = np.linalg.norm(np.diff(z['foot_xy'],axis=0)/dt,axis=-1)
        segments = []
        for s in range(4):
            mask = (z['seg'] == s) & (z['t'] >= 3*s+1) & ~z['done']
            valid = mask[1:,None] & mask[:-1,None] & contact[1:] & contact[:-1] & ~z['done'][:-1,None]
            h = z['body_height_foot_center_m'][mask]
            q = np.rad2deg(z['joint_pos'][mask])
            row = {'segment':s, 'window_s':[3*s+1,3*s+3], 'samples':int(mask.sum()),
                'vx_mps':float(z['vx'][mask].mean()), 'vy_mps':float(z['vy'][mask].mean()),
                'wz_radps':float(z['wz'][mask].mean()),
                'height_contact_center_m':float(np.nanmean(h)), 'height_valid_n':int(np.isfinite(h).sum()),
                'roll_abs_p95_deg':float(np.percentile(np.abs(np.rad2deg(z['roll'][mask])),95)),
                'pitch_abs_p95_deg':float(np.percentile(np.abs(np.rad2deg(z['pitch'][mask])),95)),
                'duty_fraction':contact[mask].mean(0).tolist(),
                'contact_center_xy_speed_mean_mps':float(speed[valid].mean()) if valid.any() else None,
                'contact_center_xy_speed_p95_mps':float(np.percentile(speed[valid],95)) if valid.any() else None,
                'joint_rom_p95_p05_deg':(np.percentile(q,95,axis=0)-np.percentile(q,5,axis=0)).tolist(),
                'joint_angle_median_deg':np.median(q,axis=0).tolist(),
                'torque_abs_p95_nm':np.nanpercentile(np.abs(z['applied_torque_last_substep'][mask]),95,axis=0).tolist(),
                'support':support(contact[mask])}
            if s >= 2:
                sign = 1 if s == 2 else -1
                row['wz_one_second_means_radps'] = [float(z['wz'][(z['t'] >= 3*s+i) & (z['t'] < 3*s+i+1)].mean()) for i in range(3)]
                row['correct_yaw_sign_fraction'] = float((sign*z['wz'][mask]>0).mean())
                row['signed_target_tracking_ratio'] = float(sign*z['wz'][mask].mean()/1.2)
            segments.append(row)
        # Single 8 x 8 m tile, centred by TerrainGenerator. This is a code-derived
        # bound, not a recovered contact-triangle or final-mesh measurement.
        root_out = np.any(np.abs(z['root_pos_w'][:,:2]) > 4.0, axis=1)
        foot_out = np.any(np.abs(z['foot_xy']) > 4.0, axis=(1,2))
        boundary = {'basis':'Current consumer code: single centred 8 x 8 m tile; final mesh not reconstructed',
                    'half_extent_m':4.0,
                    'root_first_out_s':float(z['t'][root_out][0]) if root_out.any() else None,
                    'any_foot_first_out_s':float(z['t'][foot_out][0]) if foot_out.any() else None,
                    'turn_root_x_min_m':float(z['root_pos_w'][z['t']>=6,0].min()),
                    'v05_window_all_feet_inside':bool((~foot_out[(z['t']>=1)&(z['t']<3)]).all())}
        results[label] = {'folder':str(folder), 'checkpoint_sha256':j['checkpoint_sha256'],
                         'source_sha256':{k:sha(folder/k) for k in ['review.mp4','review.json','review_feet.npz','review.done']},
                         'decoded_frames':len(frames), 'resets':int(z['done'].sum()),
                         'gt_frames':int(z['map_use_gt'].sum()),
                         'roll_abs_max_deg':float(np.max(np.abs(np.rad2deg(z['roll'])))),
                         'roll_last_deg':float(np.rad2deg(z['roll'][-1])), 'tile_boundary':boundary, 'segments':segments}
    boundary_sources = [
        ROOT/'measurement-sol24i/record_sol24i.py',
        Path('C:/mai/wt/foothold-lab/lead-tmp-start-b/foothold_s2/eval/terrain_sets.py'),
        Path('C:/mai/wt/foothold-lab/lead-tmp-start-b/sim/eval/generalization_env_cfg.py'),
        Path('C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_generator.py'),
    ]
    result = {'recording':'600 control ticks, 300 video frames, 12 s, fixed physics, seed 42, mean/mean, saved GT',
              'boundary_analysis_source_sha256':{str(p):sha(p) for p in boundary_sources},
              'metric_window':'Last 2 s of each 3 s segment, terminal rows excluded; no resets in this set',
              'height_definition':'root z minus mean contacting foot-link center z; no foot radius offset; not COM height',
              'limitations':['One sequential-command episode per terrain and policy, not success rate or independent turning trials',
                             'Rough is the starting tile name. Later forward and turn windows pass its code-derived boundary; not pure rough-surface results',
                             'Foot-link center XY speed is not contact-point tangential slip',
                             'Torque is only the last physics substep, not peak torque or energy',
                             'Joint angle magnitude alone does not determine gait quality'],
              'known_input_checks':'four-foot stance, diagonal-only, fore/hind-only all passed',
              'clips':results}
    (OUT/'matched_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def plots(rows):
    fig,axes=plt.subplots(2,2,figsize=(13,7),layout='constrained')
    for ax,(label,_,_,z,_) in zip(axes.flat,rows):
        ax.fill_between(z['t'],z['foot_xy'][:,:,0].min(1),z['foot_xy'][:,:,0].max(1),color=COLORS[0],alpha=.18,label='네 발 x 범위')
        ax.plot(z['t'],z['root_pos_w'][:,0],color=COLORS[0],label='몸통 root x')
        ax.axhline(4,color=COLORS[1],ls='--',label='코드로 계산한 타일 끝 x=4 m')
        ax.axvspan(6,12,color=COLORS[1],alpha=.08,label='회전 명령 구간')
        ax.set(title=label,xlabel='초',ylabel='세계 x (m)',xlim=(0,12));ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('지형 이름과 실제 위치를 구분: 최종 메시·접촉 삼각형은 미확인',fontsize=14)
    fig.savefig(OUT/'terrain_boundary.png',dpi=145);plt.close(fig)
    fig, axes = plt.subplots(4,3,figsize=(17,12),layout='constrained')
    for row,(label,_,j,z,_) in enumerate(rows):
        ax = axes[row,0]
        for y,k in enumerate([0,3,1,2]):
            ax.broken_barh([(float(t),.02) for t in z['t'][z['foot_contact'][:,k]]],(3-y-.35,.7),facecolors=COLORS[y//2])
        ax.set(yticks=[3,2,1,0],yticklabels=['FL','RR','FR','RL'],title=label.replace('rough','rough 출발')+' · 발 접지 위상',xlim=(0,12))
        ax = axes[row,1]
        for key,color,col in [('vx',COLORS[0],0),('wz',COLORS[1],2)]:
            ax.plot(z['t'],z[key],color=color,label=key+' 실제')
            ax.plot(z['t'],z['command'][:,col],ls='--',color=color,label=key+' 명령')
        ax.set(title='명령 반응',ylabel='vx m/s · wz rad/s',ylim=(-1.6,1.6),xlim=(0,12)); ax.legend(fontsize=8,ncol=2)
        ax=axes[row,2]; ax.plot(z['t'],z['body_height_foot_center_m'],color=COLORS[0],label='접지 발 중심 기준')
        ax.set(title='몸통 root 높이 · 무게중심 높이 아님',ylabel='m',ylim=(.17,.43),xlim=(0,12)); ax.legend(fontsize=8)
        for ax in axes[row]:
            for x in [3,6,9]: ax.axvline(x,color='#444444',ls=':',lw=.7)
            ax.set_xlabel('시뮬레이션 초');ax.grid(alpha=.18)
    fig.suptitle('model_1000 · 같은 촬영기·물리 조건. 약 5.2초 이후 타일 경계, 회전은 순수 험지 시험 아님',fontsize=14)
    fig.savefig(OUT/'gait_height_commands.png',dpi=145);plt.close(fig)
    for terrain,ids in [('flat',[0,1]),('rough',[2,3])]:
        fig,axes=plt.subplots(3,4,figsize=(15,9),layout='constrained')
        for k,ax in enumerate(axes.flat):
            for color,i in zip(COLORS,ids):
                label,_,_,z,_=rows[i];ax.plot(z['t'],np.rad2deg(z['joint_pos'][:,k]),color=color,label=label,lw=1)
            ax.set(title=rows[0][3]['joint_names'][k].replace('_joint',''),xlabel='초',ylabel='도'); ax.grid(alpha=.2)
        axes.flat[0].legend();fig.suptitle(terrain+' · 관절각은 위상·접촉·몸 기울기와 함께 해석',fontsize=15)
        fig.savefig(OUT/f'joint_angles_{terrain}.png',dpi=130);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(14,7),layout='constrained')
    for row,(terrain,ids) in enumerate([('flat',[0,1]),('rough',[2,3])]):
        for col,key in enumerate(['roll','pitch']):
            ax=axes[row,col]
            for color,i in zip(COLORS,ids):
                label,_,_,z,_=rows[i];ax.plot(z['t'],np.rad2deg(z[key]),label=label,color=color)
            ax.set(title=terrain+' · '+key,xlabel='초',ylabel='도');ax.grid(alpha=.2);ax.legend()
    fig.suptitle('몸 기울기 · roll 좌우, pitch 앞뒤. 관절각과 다른 값',fontsize=15)
    fig.savefig(OUT/'body_tilt.png',dpi=145);plt.close(fig)


def ass_time(t):
    return f'{int(t//3600)}:{int(t//60)%60:02d}:{t%60:05.2f}'


def video(rows):
    MEDIA.mkdir(exist_ok=True)
    ass='[Script Info]\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 720\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Arial,16,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,0,0,0,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'
    for panel,(label,folder,j,z,_) in enumerate(rows):
        for frame,i in enumerate(j['step_contract']['video_sample_step_indices']):
            t=frame/25; cmd=z['command'][i]
            hud=f'sim {z["t"][i]:.2f}s | cmd vx {cmd[0]:.1f} wz {cmd[2]:+.1f} | actual {z["vx"][i]:+.2f}, {z["wz"][i]:+.2f}'
            outside=bool(np.any(np.abs(z['foot_xy'][i])>4.0))
            tile_note='Foot outside tile XY bounds (code-derived)' if outside else 'Within tile XY bounds (code-derived)'
            for y,text in [(28,hud),(47,f'body height {z["body_height_foot_center_m"][i]:.3f} m | GT | resets {int(z["done"][:i].sum())}'),(66,tile_note)]:
                pos=f'{{\\pos({panel%2*640+10},{panel//2*360+y})}}'
                ass+=f'Dialogue: 0,{ass_time(t)},{ass_time(t+.04)},Default,,0,0,0,,{pos}{text}\n'
    ap=MEDIA/'comparison_hud.ass';ap.write_text(ass,encoding='utf-8')
    filters=[]
    for i,(label,*_) in enumerate(rows):
        title=f'{label.upper().replace("ROUGH","ROUGH-START")} | model_1000'
        filters.append(f"[{i}:v]setpts=PTS-STARTPTS,scale=640:360,drawbox=x=0:y=0:w=iw:h=86:color=black:t=fill,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{title}':x=10:y=4:fontsize=20:fontcolor=white[v{i}]")
    escaped=ap.as_posix().replace(':',r'\:')
    filters.append(f"[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|640_0|0_360|640_360[g];[g]ass=filename='{escaped}'[out]")
    one=MEDIA/'comparison_1x.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y']
    for _,folder,*_ in rows: cmd+=['-i',str(folder/'review.mp4')]
    cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-an','-r','25','-frames:v','300','-c:v','libx264','-crf','19','-pix_fmt','yuv420p',str(one)]
    subprocess.run(cmd,check=True)
    slow=MEDIA/'comparison_05x.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-i',str(one),'-vf','setpts=2*PTS,fps=25,tpad=stop_mode=clone:stop_duration=0.08','-an','-frames:v','600','-c:v','libx264','-crf','19','-pix_fmt','yuv420p',str(slow)],check=True)
    outputs=[]
    for p,n in [(one,300),(slow,600)]:
        cap=cv2.VideoCapture(str(p));decoded=0
        while cap.read()[0]:decoded+=1
        cap.release();assert decoded==n
        outputs.append({'file':str(p),'sha256':sha(p),'decoded_frames':decoded})
    (OUT/'video_manifest.json').write_text(json.dumps({'sources':[{'folder':str(r[1]),'receipt_sha256':sha(r[1]/'review.done')} for r in rows],
        'outputs':outputs,'slow_motion':'0.5x playback repeats source frames; no generated motion; final frame held to 24s'},ensure_ascii=False,indent=2),encoding='utf-8')


def grids(rows):
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
    for kind,times in [('overview',[0,1,3,4,6,7,9,11]),('stride',[4+i*.08 for i in range(12)])]:
        for label,folder,j,z,frames in rows:
            cols=4;w=480;h=270
            canvas=Image.new('RGB',(cols*w,((len(times)+cols-1)//cols)*(h+28)),'#f4f4f0');draw=ImageDraw.Draw(canvas)
            for k,t in enumerate(times):
                f=frames[round(t*25)];im=Image.fromarray(cv2.cvtColor(f,cv2.COLOR_BGR2RGB)).resize((w,h))
                x=k%cols*w;y=k//cols*(h+28);canvas.paste(im,(x,y+28));draw.text((x+6,y+3),f'{label} | {t:.2f} s',font=font,fill='#152730')
            canvas.save(OUT/(label.lower().replace(' ','_')+'_'+kind+'.jpg'),quality=94)


def report(result):
    clips=result['clips']
    train=json.loads((OUT/'training_data.json').read_text(encoding='utf-8'))['runs']
    forward=[]; turns=[]; boundary=[]; slip=[]
    for label,c in clips.items():
        a,b=c['segments'][:2]; sp=b['support']; n=sp['two_contact_n']
        d=round(sp['diagonal_only_fraction']*b['samples'])
        forward.append(f'| {label} | {a["vx_mps"]:.3f} | {a["height_contact_center_m"]:.3f} | {b["vx_mps"]:.3f} | {b["height_contact_center_m"]:.3f} | {d}/{n} ({100*d/n:.1f}%) |')
        a,b=c['segments'][2:]; x=a['wz_one_second_means_radps']; y=b['wz_one_second_means_radps']
        turns.append(f'| {label} | {x[0]:+.3f} → {x[2]:+.3f} | {y[0]:+.3f} → {y[2]:+.3f} | {100*a["support"]["four_contact_fraction"]:.0f}% / {100*b["support"]["four_contact_fraction"]:.0f}% |')
        tb=c['tile_boundary']
        assert tb['v05_window_all_feet_inside']
        boundary.append(f'| {label} | {tb["any_foot_first_out_s"]:.2f} | {tb["root_first_out_s"]:.2f} | {tb["turn_root_x_min_m"]:.3f} |')
        slip.append(f'| {label} | {c["segments"][1]["contact_center_xy_speed_mean_mps"]:.3f} |')
    training=[]
    a=train['EX-23']['last25_mean'];b=train['EX-28 B']['last25_mean']
    for key,label,scale in [('episode','최근 종료 에피소드 길이(s)',.02),('reward','누적 에피소드 보상',1),('linear','전진 보상 항',1),('angular','회전 보상 항',1),('stalled','정체 분류 비율',1),('level','평균 지형 난이도 행',1),('gt','실제 GT 선택 비율',1)]:
        training.append(f'| {label} | {a[key]*scale:.4f} | {b[key]*scale:.4f} |')
    body="""> 분류: 실험
> 작성: 오흥재 (lead_tmp 직접 촬영·집계) · 2026-10-24
> 근거: B·EX-23 model_1000 원본 JSON·NPZ·MP4 · TensorBoard · 촬영 소스 · ASTRA24g 독립 집계
> 요지: B도 몸을 세우고 전진한다. 마찰 단독 포복설은 약해졌고, 지속 회전은 미완성이다. 회전 구간은 거친 타일 밖으로 나가므로 순수 험지 시험이 아니다.
> 상태: 1000번 중간 분석 확인됨 · B는 1500번까지 계속 · EX-29 재개 보류
> 판: v1.0

# EX-28 B 1000번 · EX-23 같은 회차와의 비교

**B는 넓은 마찰 분포로 학습했어도 몸을 세우고 전진한다. 회전은 처음 반응한 뒤 속도가 크게 줄어든다.** EX-23도 1000번에서는 지속 회전이 미숙하고, 이번 평지 촬영 마지막에는 옆으로 크게 기울어진다. 따라서 「마찰을 고정해야만 전진을 배운다」는 강한 설명은 지지되지 않는다. 마찰이 무관하다거나 다른 DR 하나가 원인이라는 뜻은 아니다.

**촬영 한계도 발견했다.** 코드와 세계좌표를 대조하면 약 5.2초부터 발이 8 m 타일 밖으로 나간다. 전진 0.5 m/s 구간은 타일 내부지만, 이후 1.0 m/s 구간은 내부와 경계를 섞고 회전은 순수 험지 구간이 아니다. 이 한계를 영상 자막·표·그림에 함께 표시했다. 최종 메시의 접촉 삼각형은 미확인이다.

실행은 [팀장 직접 결정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6379481102)대로 **1000번 촬영·분석 후 1500번까지 학습하고 자연 종료**한다. model_1000은 0번부터 센 완료 1001갱신, model_1500은 완료 1501갱신이다. 새 실험이나 EX-29 재개를 승인한 기록이 아니다.

## 1. 영상과 원자료

- [2행 2열 비교 영상 1배속](https://github.com/foothold-project/foothold-lab/releases/download/research-ex28-1000-20261024/ex23-b1000-comparison-1x.mp4), [0.5배속](https://github.com/foothold-project/foothold-lab/releases/download/research-ex28-1000-20261024/ex23-b1000-comparison-05x.mp4). 열은 EX-23 / B, 행은 flat / rough 출발이다. 네 판 모두 model_1000이다.
- 로컬: `C:/Users/AI-WS01/s2_lab/run_20261024/b1000_matched_review/comparison_1x.mp4`, `comparison_05x.mp4`.
- [수치와 원본 SHA](figs/ex28-u1000-review/matched_metrics.json), [영상 목록·SHA](figs/ex28-u1000-review/video_manifest.json), [CPU 분석 코드](analyze_b1000_1024.py), [원자료 묶음](https://github.com/foothold-project/foothold-lab/releases/download/research-ex28-1000-20261024/ex23-b1000-evidence.zip).

![같은 시각의 네 화면](figs/ex28-u1000-review/comparison_frame_8s.jpg)

명령은 0~3초 전진 0.5 m/s, 3~6초 전진 1.0 m/s, 6~9초 좌회전 +1.2 rad/s, 9~12초 우회전 −1.2 rad/s다. 평균 표는 각 구간 마지막 2초, 즉 100개 제어행이다. **100개 독립 실험이 아니다.** 회전 표는 처음 1초와 마지막 1초를 따로 보여 준다. HUD는 실제 `video_sample_step_indices`로 원자료와 맞췄다.

## 2. 전진 · 몸 높이 · 보행 위상

아래 `rough`는 출발 지형 이름이다. 0.5 명령의 집계 구간은 코드상 타일 내부이고, 1.0 명령의 집계 구간은 타일 끝을 포함한다.

| 자료 | 0.5 명령 속도(m/s) | 그때 몸 높이(m) | 1.0 명령 속도(m/s) · 경계 포함 | 그때 몸 높이(m) | 대각 / 두 발 접지 표본 · 1.0 구간 |
|---|---:|---:|---:|---:|---:|
[[FORWARD]]

몸 높이는 **몸통 root의 z에서 접촉 중인 발 링크 중심 z의 평균을 뺀 값**이다. 무게중심(COM) 높이나 발바닥 접촉면 높이가 아니다. 발 반지름을 더하지 않았다. 정의가 다른 과거 높이와 숫자만 빼서 비교하지 않는다. 회전 끝에 기울어진 몸의 높이도 정상 자세의 증거로 쓰지 않는다.

대각 접지는 FL(앞왼쪽)+RR(뒤오른쪽), 또는 FR(앞오른쪽)+RL(뒤왼쪽) 두 발만 접지한 상태다. 표의 분모는 두 발 접지 표본이다. 전체 100행 중 대각 두 발은 EX-23 flat 75행, B flat 68행, EX-23 rough 64행, B rough 62행이다. 모든 발을 붙인 정지는 대각 접지 100%가 되지 않도록 분모 없음으로 처리한다. 답을 아는 네 발 서기·대각 쌍·앞뒤 쌍 입력으로 함수를 먼저 확인했다.

![발 접지·속도·몸 높이](figs/ex28-u1000-review/gait_height_commands.png)

전진의 위상과 0.08초 프레임 띠에서 대각 쌍이 반복 교대한다. B의 1.0 명령 구간에서 앞 두 발 또는 뒤 두 발만 접지한 비율은 flat 3%, rough 출발 1%다. 순간 접촉만으로 앞뒤 쌍 도약(bounding)이라고 부르지 않는다. 이번 구간에는 EX-15처럼 앞뒤 쌍 도약이 지속되는 모습이 확인되지 않았다. 대각 분율 하나만으로 보행 전체의 안정성이나 완성도를 인증하지도 않는다.

## 3. 회전은 처음 반응과 지속 능력을 나눠 본다

| 자료 | 좌회전 처음 1초 → 마지막 1초(rad/s) | 우회전 처음 1초 → 마지막 1초(rad/s) | 좌/우 마지막 2초 네 발 접지율 |
|---|---:|---:|---:|
[[TURNS]]

명령은 끝까지 ±1.2 rad/s인데 속도가 유지되지 않는다. B는 처음 요구한 방향으로 돌고, 이후 발을 거의 계속 붙인 채 각속도가 0에 가까워진다. 관절도 전진 중의 주기적 굽힘·폄에서 거의 고정된 자세로 바뀐다. **처음부터 명령을 무시했다는 설명은 틀리다. 몸을 비튼 뒤 발을 바꾸며 회전을 이어가는 동작이 미완성인 패턴**이다. 이는 관찰에 맞는 해석이며 보상·관절 한계·학습량 중 어느 것이 원인인지는 분리하지 않았다.

EX-23 flat은 예외를 따로 남긴다. 11초 이후 roll(몸 좌우 기울기)이 최대 **[[TILT]]°**로 커지고 영상에서도 옆으로 무너지는 진행이 보인다. 그때도 reset은 0이다. **reset 0은 넘어지지 않았다는 증거가 아니다.** 크게 기울어진 몸의 z축 각속도는 지면 기준 순수 회전 속도와도 다르다. B의 네 발 유지 관찰을 EX-23의 이 구간까지 일반화하지 않는다.

![몸 기울기](figs/ex28-u1000-review/body_tilt.png)

![EX-23 flat 끝의 기울기 · 11~11.96초](figs/ex28-u1000-review/ex23_flat_turn_end.jpg)

### 타일 경계에 관한 추가 제한

촬영기 [512~520행](measurement-sol24i/record_sol24i.py#L512)은 random_rough 한 타일을 만든다. 소비 소스 `lead-tmp-start-b/foothold_s2/eval/terrain_sets.py:111,139~143`, `sim/eval/generalization_env_cfg.py:32`와 설치 Isaac Lab `terrain_generator.py:181~187`을 직접 읽었다. 8×8 m 타일을 중심 정렬하므로 x·y는 −4~4 m다. 20 m border는 주변 바닥을 늘리며 거친 타일을 늘리지 않는다.

| 자료 | 첫 발이 타일 범위 밖인 시각(s) | root가 밖인 시각(s) | 회전 구간 root x 최솟값(m) |
|---|---:|---:|---:|
[[BOUNDARY]]

![세계좌표와 코드상 타일 끝](figs/ex28-u1000-review/terrain_boundary.png)

ASTRA가 먼저 지적했고 lead_tmp도 생성 코드와 NPZ를 별도로 대조했다. **6~12초를 순수 험지 회전 성능으로 보고하지 않는다.** 최종 생성 메시·발의 접촉 삼각형 ID는 저장 자료에서 확인하지 못했다. 따라서 좌표와 코드에 근거한 제한으로 적으며 실제 삼각형 접촉까지 재구성했다고 주장하지 않는다. `physics.applied_config`는 생성기 교체 전에 저장되어 그 안의 10행·23열도 최종 평가 지형이 아니다. 현재 실행 파일은 고치지 않았고, 다음 촬영에서 경계 내 명령 구간을 확보해야 한다는 점을 기록했다.

## 4. 관절각 · 발 XY 기록의 의미

![flat 관절각](figs/ex28-u1000-review/joint_angles_flat.png)

[rough 출발 관절각](figs/ex28-u1000-review/joint_angles_rough.png). hip은 좌우 벌림, thigh·calf는 허벅지·종아리 관절이다. 각도가 크거나 보폭이 커 보인다는 사실만으로 좋은 보행은 아니다. 교대 시점·접촉·몸 기울기·속도 추종을 함께 읽는다. 좌우 hip 원시 각도 차이를 그대로 해부학적 비대칭으로 부르지 않는다.

접지한 두 연속 제어행 사이 발 링크 중심 XY 이동을 0.02초로 나누고 reset 경계를 제외했다.

| 자료 | 1.0 명령 구간 접지 발 중심 XY 속력 평균(m/s) · 경계 포함 |
|---|---:|
[[SLIP]]

이것은 **미끄러짐 참고값**이다. 발 중심은 접촉점과 다르고 발이 굴러도 이동한다. 실제 표면 법선·접촉점 접선 속도가 없으므로 미끄럼 속도로 확정하지 않는다. joint target·torque는 마지막 물리 substep 값이며, substep 전체 최대 토크나 에너지 자료는 아니다. 저장 NPZ는 발·관절·몸·명령·지도 배열을 담은 압축 NumPy 원자료다.

## 5. 학습 곡선과 마찰 가설

![학습 곡선](figs/ex28-u1000-review/training_curves.png)

| 976~1000 로그 평균 | EX-23 | B |
|---|---:|---:|
[[TRAINING]]

전진·회전 보상과 에피소드 길이는 비슷한 흐름이고 B의 평균 지형 행은 조금 낮다. 이 값들은 다른 마찰 표본·학습 경로에서 나온 훈련 기록이다. 독립 성공률이나 통계적 동등성 검정이 아니다. 특히 회전 보상이 남아 있다는 사실만으로 지속 회전이 가능하다고 말하면 영상과 어긋난다. 같은 학습 시계에 따라 함께 오르는 곡선의 피어슨 상관으로 인과를 증명하지 않는다. [상관·산점도 원칙](NOTE-correlation-mechanics-1024.md)을 따른다.

처치는 EX-23의 정적 마찰 0.8·동적 0.6 고정을 B에서 각각 0.2~1.2, 64 buckets로 바꾸고 동적≤정적으로 보정한 것이다. 모든 환경이 항상 0.2였던 것은 아니다. COM·PD gain·motor strength 무작위화는 끄고 행동 지연은 0인 EX-23 설정을 유지했으며, 몸통 질량 추가 −1~3 kg는 양쪽 모두 남아 있다.

이번 평가에서는 두 정책 모두 로봇 재질 정적 약 0.8·동적 약 0.6으로 고정했다. **넓은 마찰로 학습한 B도 이 고정 평가에서 전진할 수 있다**는 결과다. 가장 미끄러운 학습 조건에서의 평가 성능, 마찰 효과의 완전한 부재, 다른 DR 하나가 과거 포복의 원인이라는 주장은 미확인이다. 한 시드·역사 대조이며 같은 시드를 썼어도 학습 난수 소비 경로가 완전히 같다는 보장은 없다. [과거 실험 전체 조건표](ANALYSIS-experiment-failures-1024.md)와 연결해 해석한다.

B는 model_1500까지 계속한다. 회전이 그때 살아날지 예단하지 않는다. EX-29는 정지 상태를 보존한다. 후진·횡이동·성과 기반 지형 전환·DR 복원을 포함한 다음 본류 설계는 별도 논의이며 이 중간 결과가 누락된 요구를 해소하지 않는다.

## 6. 검증 범위와 실패 보존

`확인됨`: 네 성공 원본 각각 300프레임 전체 CPU 해독, 영수증 SHA 일치, 600개 제어행, 실제 정책 지도 입력 GT 600/600, 같은 seed 42·평가 물리값·mean latent/mean action·명령이다. 실제 질량·COM·재질·기록된 PD readback도 짝끼리 같다. PD readback은 첫 actuator의 8관절이라 전체 12관절 실측으로 확대하지 않는다. `step_contract.physics_dt_s=.02`는 필드 이름과 달리 제어 간격이다. 실제 물리 dt는 .005초, decimation은 4다.

정확히 같은 순차 명령을 한 episode에서 수행했으므로 독립 좌/우 회전 성공률이 아니다. 앞선 전진·좌회전의 몸 상태와 지도·GRU 이력이 뒤 구간에 남는다. 실제 지도 선택은 설정만이 아니라 `_advance(use_gt)` 입력에서 기록했다. 따라서 이 촬영은 복원 지도만 쓰는 실기 검증이 아니다.

기존 consumer의 B1000 자동 rough는 `dark_or_missing_brightness`로 실패했다. 성공 영수증이 없으며 원본은 보존했다. 별도 보호 촬영으로 B rough 13:32:06~13:33:16, flat 13:33:34~13:34:39에 rc0·300프레임·600행을 확인했다. 네 성공 원본의 렌더 재시도는 0이고 정상 렌더 전후 물리 상태 불변 검사를 통과했다. EX-23 flat의 앞선 검정 지속 실패도 보존했다. 기술 검사에 실패한 원본과 재시도를 구분했으며 보행이 좋은 시도를 골라 바꾼 것이 아니다. [촬영 검증 기록](NOTE-capture-render-1024.md).

lead_tmp의 시각 판독은 각 원본 0·1·3·4·6·7·9·11초, 전진 4~4.88초 0.08초 간격, EX-23 flat 끝 11~11.96초 0.08초 간격이다. 300프레임을 모두 개별 시각 판독했다는 뜻은 아니다. NPZ 600행 전체를 도표화해 이상 구간을 더 촘촘히 봤다. 1배속 300프레임·0.5배속 600프레임을 전체 해독했고, 0.5배속은 원프레임을 반복한 재생용 영상이다.

ASTRA24g는 별도 집계로 4개 자료×4개 구간의 속도·높이·접지 개수를 대조해 일치를 확인했고, 타일 경계 문제를 찾아냈다. lead_tmp도 해당 코드·세계좌표·수치를 다시 확인했다. LUNA24e의 영상 의견과 별개로 이 보고서는 직접 확인한 범위만 결론에 썼다. 검토 보고서 원본은 각 세션 worktree에 보존한다.

원자료 뿌리: `C:/Users/AI-WS01/s2_lab/run_20261024/`.

| 자료 | 하위 폴더 |
|---|---|
| EX-23 flat | ex23_model1000_flat_guarded24i_r2 |
| EX-23 rough | ex23_model1000_rough_guarded24i |
| B flat | b_model1000_flat_guarded24i |
| B rough | b_model1000_rough_guarded24i |

각 폴더의 `review.mp4`·`review.json`·`review_feet.npz`·`review.done`을 묶음으로 보존했다.

| 판 | 체크포인트 SHA-256 |
|---|---|
| EX-23 model_1000 | `[[EXSHA]]` |
| B model_1000 | `[[BSHA]]` |

B 실행 고정 커밋은 `d9517fb9929f23e2bf5c0b51fe46a1b2df20f237`, 보호 촬영기 원작업 커밋은 `90c5c2425860d00e28f5d3ab8fa897b64efbc38e`다. [보존 촬영 소스](measurement-sol24i/record_sol24i.py), [실행 원장](RUN-EX28-29-1024.md), [실험 지도](../20261021-experiments/EXP-MAP.md).

| 판 | 변경 |
|---|---|
| v1.0 · 10/24 | model1000 짝 비교·전진·지속 회전·끝 기울기·타일 경계·촬영 실패 보존 |
"""
    replacements={'FORWARD':'\n'.join(forward),'TURNS':'\n'.join(turns),'BOUNDARY':'\n'.join(boundary),'SLIP':'\n'.join(slip),'TRAINING':'\n'.join(training),'TILT':f'{clips["EX-23 flat"]["roll_abs_max_deg"]:.1f}','EXSHA':clips['EX-23 flat']['checkpoint_sha256'],'BSHA':clips['B flat']['checkpoint_sha256']}
    for k,v in replacements.items(): body=body.replace('[['+k+']]',v)
    assert '[[' not in body
    (ROOT/'RESULT-B1000-1024.md').write_text(body,encoding='utf-8')


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True);checks();rows=load();result=metrics(rows)
    plots(rows);grids(rows);video(rows);report(result)
    print(json.dumps({k:[{key:r[key] for key in ['segment','vx_mps','wz_radps','height_contact_center_m','support']} for r in v['segments']] for k,v in result['clips'].items()},ensure_ascii=False))
