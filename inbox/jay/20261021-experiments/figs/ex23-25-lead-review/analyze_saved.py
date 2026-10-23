"""Read-only CPU analysis of saved EX-23/25 observations. No simulator imports."""
from pathlib import Path
import csv
import hashlib
import io
import json
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
import yaml

OUT = Path(__file__).resolve().parent
ROOT = Path('C:/Users/AI-WS01/s2_lab/videos/mid500_1022')
LOG = Path('C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl')
RUNS = {'EX23 G1': 'ex23r_1500', 'EX25 G0': 'ex25_1500'}
COLORS = {'EX23 G1': '#00766F', 'EX25 G0': '#B34B20'}
plt.rcParams.update({'font.family': 'Malgun Gothic', 'font.size': 11, 'axes.unicode_minus': False})

def pair_stats(c, names):
    idx = {str(n).split('_')[0]: i for i, n in enumerate(names)}
    a = np.zeros(4, dtype=bool)
    a[[idx['FL'], idx['RR']]] = True
    b = ~a
    A = np.all(c == a, axis=1)
    B = np.all(c == b, axis=1)
    both = A | B
    two = c.sum(axis=1) == 2
    seq = A[both]
    return (float(both.sum()/two.sum()) if two.any() else None,
            int(np.count_nonzero(seq[1:] != seq[:-1])), int(two.sum()))

names = ['FL_foot', 'FR_foot', 'RL_foot', 'RR_foot']
a = [True, False, False, True]
b = [False, True, True, False]
assert pair_stats(np.array([a, b, a, b]), names) == (1., 3, 4)
assert pair_stats(np.array([a]*4), names) == (1., 0, 4)
assert pair_stats(np.array([[True]*4]), names) == (None, 0, 0)
assert np.mean(np.abs(np.array([1., 1.])-1.)) == 0

rows, evidence, data = [], [], {}
for label, folder in RUNS.items():
    for scene in ('flat', 'rough'):
        path = ROOT / folder / f'run_{scene}_feet.npz'
        meta_path = path.with_name(f'run_{scene}.json')
        d = np.load(path, allow_pickle=False)
        meta = json.loads(meta_path.read_text(encoding='utf8'))
        data[(label, scene)] = d
        for f in (path, meta_path, ROOT/folder/f'run_{scene}.mp4'):
            evidence.append({'path': str(f), 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()})
        assert len(d['t']) == 600 and np.all(np.diff(d['t']) > 0)
        assert np.array_equal(d['seg_cmds'], [[.5,0,0],[1,0,0],[0,0,1.2],[0,0,-1.2]])
        assert meta['resets'] == 0
        for seg, cmd in enumerate(d['seg_cmds']):
            mask = d['seg'] == seg
            tail = mask & (d['t'] >= d['t'][mask][0]+1.5)
            diag, switch, n2 = pair_stats(d['foot_contact'][mask], d['foot_names'])
            target, actual = (cmd[0], d['vx']) if seg < 2 else (cmd[2], d['wz'])
            rows.append(dict(run=label, scene=scene, segment=seg, command=float(target),
                height_m=float(np.nanmedian(d['body_height'][mask])),
                vx_tail=float(d['vx'][tail].mean()), wz_tail=float(d['wz'][tail].mean()),
                tracking_mae_tail=float(np.abs(actual[tail]-target).mean()),
                roll_rms_deg=float(np.sqrt(np.mean(np.rad2deg(d['roll'][mask])**2))),
                pitch_rms_deg=float(np.sqrt(np.mean(np.rad2deg(d['pitch'][mask])**2))),
                roll_std_deg=float(np.std(np.rad2deg(d['roll'][mask]))),
                pitch_std_deg=float(np.std(np.rad2deg(d['pitch'][mask]))),
                pitch_absmax_deg=float(np.abs(np.rad2deg(d['pitch'][mask])).max()),
                diagonal_ratio=diag, diagonal_switches=switch, two_contact_samples=n2,
                contact_samples=int(mask.sum()), resets_total=meta['resets'], source=str(path)))
with (OUT/'segments.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
(OUT/'provenance.json').write_text(json.dumps({'known_input_checks':4,'files':evidence},indent=2),encoding='utf8')

for scene in ('flat','rough'):
    fig, axes = plt.subplots(4,1,figsize=(12,9),sharex=True)
    for label in RUNS:
        d=data[(label,scene)]; t=d['t']
        for ax, key in zip(axes, ('vx','wz','body_height','roll')):
            y=np.rad2deg(d[key]) if key=='roll' else d[key]
            ax.plot(t,y,color=COLORS[label],label=label,linewidth=1.3)
    d=data[('EX23 G1',scene)]
    axes[0].plot(d['t'],d['seg_cmds'][d['seg'],0],'k--',label='명령',linewidth=1)
    axes[1].plot(d['t'],d['seg_cmds'][d['seg'],2],'k--',label='명령',linewidth=1)
    for ax, title in zip(axes,('몸 좌표 전진 속도 (m/s)','몸 좌표 회전 속도 (rad/s)','접지 발 기준 몸 높이 (m)','몸 roll (도)')):
        ax.set_ylabel(title); ax.grid(alpha=.2)
        for x in (3,6,9): ax.axvline(x,color='#666666',ls=':',lw=.8)
    axes[0].legend(ncol=3); axes[-1].set_xlabel('기록 시간 (초), 명령은 3초마다 변경, 구간 사이 reset 없음')
    fig.suptitle(f'1500회 G1 / G0 · {scene} · 한 궤적의 원 시계열, 평활 없음')
    fig.tight_layout(); fig.savefig(OUT/f'response_{scene}.png',dpi=140); plt.close(fig)

    fig,axes=plt.subplots(2,1,figsize=(14,5),sharex=True)
    for ax,label in zip(axes,RUNS):
        d=data[(label,scene)]
        for j,name in enumerate(d['foot_names']):
            for start in np.where(d['foot_contact'][:,j])[0]:
                ax.broken_barh([(float(d['t'][start]),float(d['dt']))],(j-.28,.56),facecolors=('#00766F' if str(name).split('_')[0] in ('FL','RR') else '#B34B20'))
        ax.set_yticks(range(4),d['foot_names']); ax.set_title(label); ax.set_ylim(3.7,-.7)
        for x in (3,6,9):ax.axvline(x,color='#333333',ls=':',lw=1)
    axes[-1].set_xlabel('시간 (초) · 실선 막대 = 접지, 같은 색 = 대각 짝')
    fig.suptitle(f'1500회 네 발 접촉 위상 · {scene} · 0.5 전진 / 1.0 전진 / +1.2 회전 / -1.2 회전')
    fig.tight_layout();fig.savefig(OUT/f'phase_{scene}.png',dpi=140);plt.close(fig)

    # CPU decode, full-clip sample at 1,3,5,7,9,11 seconds; preserve HUD.
    sheet=Image.new('RGB',(3*640,4*380),'white');draw=ImageDraw.Draw(sheet)
    for k,label in enumerate(RUNS):
        for n,t in enumerate((1,3,5,7,9,11)):
            video=ROOT/RUNS[label]/f'run_{scene}.mp4'
            out=subprocess.run(['ffmpeg','-v','error','-hwaccel','none','-ss',str(t),'-i',str(video),'-frames:v','1','-vf','scale=640:360','-f','image2pipe','-vcodec','png','pipe:1'],capture_output=True,check=True)
            im=Image.open(io.BytesIO(out.stdout));x=(n%3)*640;y=(k*2+n//3)*380
            draw.text((x+8,y+3),f'{label} {scene} t={t}s',fill='black');sheet.paste(im,(x,y+20))
    sheet.save(OUT/f'contact_{scene}.png')

# Saved EX-12 (learned estimator) is relevant to interpretation, not just EX-11 zero-estimator.
old=LOG/'foothold_s2_x11/2026-10-22_01-34-08_ex12-est-learned/params'
new=LOG/'foothold_s2_x23/2026-10-22_23-00-45_ex25-g0/params'
diffs=[]
def walk(a,b,path):
    if isinstance(a,dict) and isinstance(b,dict):
        for key in sorted(set(a)|set(b)):walk(a.get(key,'<missing>'),b.get(key,'<missing>'),path+'.'+str(key))
    elif a != b: diffs.append({'field':path,'ex12':a,'ex25':b})
for name in ('env.yaml','agent.yaml'):
    aa=yaml.load((old/name).read_text(encoding='utf8'),Loader=yaml.BaseLoader)
    bb=yaml.load((new/name).read_text(encoding='utf8'),Loader=yaml.BaseLoader)
    walk(aa,bb,name)
(OUT/'ex12_ex25_saved_cfg_diff.json').write_text(json.dumps(diffs,ensure_ascii=False,indent=2),encoding='utf8')

joint_paths={
    'EX11 1500': ROOT.parent/'joint_1022/ex11_flat_feet.npz',
    'EX23 G1': ROOT/'ex23r_1500/run_flat_feet.npz',
    'EX25 G0': ROOT/'ex25_1500/run_flat_feet.npz',
    'v2': ROOT.parent/'joint_1022/v2_flat_feet.npz',
}
joint_rows=[]
fig,axes=plt.subplots(1,3,figsize=(14,5))
for r,(label,path) in enumerate(joint_paths.items()):
    d=np.load(path,allow_pickle=False); mask=d['seg']==1
    q=np.rad2deg(d['joint_pos'][mask]); mid=np.median(q,axis=0)
    lo,hi=np.percentile(q,[25,75],axis=0)
    for i,name in enumerate(d['joint_names']):
        joint_rows.append(dict(run=label,joint=str(name),median_deg=mid[i],q25_deg=lo[i],q75_deg=hi[i],source=str(path)))
    for j,kind in enumerate(('hip','thigh','calf')):
        idx=[i for i,name in enumerate(d['joint_names']) if kind in name]
        x=np.arange(4)+(r-1.5)*.15
        axes[j].errorbar(x,mid[idx],yerr=np.array([mid[idx]-lo[idx],hi[idx]-mid[idx]]),fmt='o',capsize=3,label=label,color={**COLORS,'EX11 1500':'#7956A1','v2':'#333333'}[label])
        axes[j].set_xticks(range(4),[str(d['joint_names'][i]).split('_')[0] for i in idx]);axes[j].set_title(kind)
        axes[j].grid(alpha=.2)
axes[0].set_ylabel('기록된 관절각 (도) · 점=중앙값, 막대=25~75 백분위')
axes[2].legend();fig.suptitle('평지 전진 1.0 · 3~6초 · hip 좌우 부호가 다르므로 원 부호를 보존')
fig.tight_layout();fig.savefig(OUT/'joint_comparison.png',dpi=150);plt.close(fig)
with (OUT/'joints.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=joint_rows[0].keys());w.writeheader();w.writerows(joint_rows)
print(json.dumps({'segments':len(rows),'cfg_differences':len(diffs),'output':str(OUT)},ensure_ascii=False))
