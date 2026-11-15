"""CPU-only plots from immutable checkpoint windows and receipt-verified recordings."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 10})
COLORS = ["#007F78", "#D46B30", "#365C8D", "#AB4576"]
TAGS = {
    "episode": "Train/mean_episode_length", "reward": "Train/mean_reward",
    "linear": "Episode_Reward/track_lin_vel", "angular": "Episode_Reward/track_ang_vel",
    "stalled": "Loss/reward_split/frac_stalled", "gt": "Loss/adasmpl/gt_fraction",
    "tr": "Loss/perception/l_tr", "ie": "Loss/perception/l_ie",
    "level": "Curriculum/terrain_levels", "error_xy": "Metrics/base_velocity/error_vel_xy",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scalars(path, end):
    acc = EventAccumulator(str(path), size_guidance={"scalars": 0})
    acc.Reload()
    values = {}
    for key, tag in TAGS.items():
        if tag not in acc.Tags()["scalars"]:
            continue
        rows = {e.step: float(e.value) for e in acc.Scalars(tag) if 0 <= e.step <= end}
        assert set(rows) == set(range(end + 1)), (tag, len(rows), end)
        assert np.isfinite(list(rows.values())).all(), tag
        values[key] = [rows[i] for i in range(end + 1)]
    return values


def training(args):
    runs = dict(x.split("=", 1) for x in args.run)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    data = {name: {"source": path, "series": scalars(Path(path), args.end)} for name, path in runs.items()}
    for name, row in data.items():
        row["last25_mean"] = {key: float(np.mean(v[-25:])) for key, v in row["series"].items()}
        evidence = Path(row["source"]) / "step_evidence.jsonl"
        if evidence.exists():
            events = [json.loads(s) for s in evidence.read_text(encoding="utf-8").splitlines() if s.strip()]
            events = [e for e in events if 0 <= e["it"] <= args.end]
            row["step_evidence"] = [{k: e[k] for k in ["it", "steps", "termination_counts", "contact_foot_samples", "foot_xy_tangent_speed_mean_mps"]} for e in events]
            row["termination_last25"] = {key: sum(e["termination_counts"].get(key, 0) for e in events if args.end - 24 <= e["it"] <= args.end) for key in ["bad_orientation", "time_out", "foot_below_ground"]}
    panels = [("episode", "최근 종료 에피소드 평균 길이", "초", .02),
              ("reward", "누적 에피소드 보상 · 길이와 함께 해석", "보상", 1),
              ("stalled", "명령별 정체 분류", "비율", 1),
              ("tr", "지도 복원 학습 손실", "손실", 1),
              ("gt", "실제 정답 지도 사용 비중", "비율", 1),
              ("level", "평균 지형 난이도 행", "행", 1)]
    fig, axes = plt.subplots(3, 2, figsize=(14, 10), layout="constrained")
    for ax, (key, title, unit, scale) in zip(axes.flat, panels):
        for (name, row), color in zip(data.items(), COLORS):
            if key in row["series"]:
                ax.plot(np.arange(args.end + 1), np.array(row["series"][key]) * scale, color=color, lw=1.4, label=name)
        ax.set(title=title, xlabel="학습 로그 iteration 번호 (0부터)", ylabel=unit)
        ax.grid(alpha=.22); ax.legend()
    fig.suptitle(args.title + "\n학습 중 기록, 독립 평가 성공률이 아님", fontsize=15)
    fig.savefig(out / "training_curves.png", dpi=150); plt.close(fig)
    if len(data) == 1:
        row = next(iter(data.values()))
        if "step_evidence" in row:
            fig, ax = plt.subplots(figsize=(12, 4.5), layout="constrained")
            for key, label, color in zip(["bad_orientation", "time_out", "foot_below_ground"], ["자세 이상 종료", "시간 만료", "발 지면 아래 종료"], COLORS):
                ax.plot([e["it"] for e in row["step_evidence"]], [e["termination_counts"].get(key, 0) for e in row["step_evidence"]], label=label, color=color)
            ax.set(title="한 갱신의 전체 환경에서 실제 기록된 종료 항목 수", xlabel="학습 로그 iteration 번호", ylabel="건 / 3072환경 × 24step")
            ax.legend(); ax.grid(alpha=.22)
            fig.savefig(out / "termination_counts.png", dpi=150); plt.close(fig)
    result = {"scope": f"indices 0 through {args.end}, inclusive; {args.end + 1} updates", "runs": data,
              "limits": "Historical comparisons are single seed. Episode rewards depend on length. Termination flags may overlap. Foot-center XY velocity is not exact contact-point slip."}
    (out / "training_data.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({name: {"last25": row["last25_mean"], "termination_last25": row.get("termination_last25")} for name, row in data.items()}, ensure_ascii=False))


def captures(args):
    clips = dict(x.split("=", 1) for x in args.clip)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    names = json.loads(Path(args.coordinates).read_text(encoding="utf-8"))
    print('coordinate_metadata_keys',list(names))
    foot_names = names["foot_names"]
    joint_names = names["joint_names"]
    loaded, metrics = {}, {}
    for label, filename in clips.items():
        p=Path(filename); z=np.load(p, allow_pickle=False); loaded[label]=z
        assert len(z['t']) == 600 and z['joint_pos'].shape == (600,12)
        rows=[]
        for i in range(4):
            mask=z['seg']==i; stable=mask & ~z['done'].astype(bool)
            speed=np.linalg.norm(np.diff(z['foot_xy'],axis=0)/float(z['dt']),axis=-1)
            valid=z['foot_contact'][1:] & z['foot_contact'][:-1] & (~z['done'][:-1,None]) & (~z['done'][1:,None]) & mask[1:,None] & mask[:-1,None]
            rows.append({'segment':i,'vx_mean':float(z['vx'][mask].mean()),'wz_mean':float(z['wz'][mask].mean()),
                'reset_count':int(z['done'][mask].sum()),'roll_abs_p95_deg':float(np.percentile(abs(np.rad2deg(z['roll'][mask])),95)),
                'pitch_abs_p95_deg':float(np.percentile(abs(np.rad2deg(z['pitch'][mask])),95)),
                'foot_contact_fraction':z['foot_contact'][mask].mean(0).tolist(),
                'contact_center_xy_speed_mean_mps':float(speed[valid].mean()) if valid.any() else None,
                'joint_rom_p95_p05_deg':(np.percentile(np.rad2deg(z['joint_pos'][stable]),95,axis=0)-np.percentile(np.rad2deg(z['joint_pos'][stable]),5,axis=0)).tolist() if stable.any() else None})
        metrics[label]={'path':str(p),'sha256':sha(p),'segments':rows,'gt_use_count':int(z['map_use_gt'].sum()),'map_samples':len(z['map_use_gt'])}
    fig, axes=plt.subplots(len(clips),2,figsize=(14,3*len(clips)),squeeze=False,layout='constrained')
    order=[0,3,1,2]
    for row,(label,z) in enumerate(loaded.items()):
        ax=axes[row,0]
        for j,k in enumerate(order):
            ax.broken_barh([(float(t),float(z['dt'])) for t in z['t'][z['foot_contact'][:,k]]],(3-j-.35,.7),facecolors=COLORS[0 if j<2 else 1])
        for t in z['t'][z['done']]:ax.axvline(t,color='#AB4576',lw=.8,alpha=.8)
        ax.set(yticks=[3,2,1,0],yticklabels=[foot_names[k].replace('_foot','') for k in order],xlim=(0,12),xlabel='초',title=label+' · 접촉 위상 (세로선: reset)')
        ax=axes[row,1];ax.plot(z['t'],z['vx'],color=COLORS[0],label='실제 vx');ax.plot(z['t'],z['command'][:,0],color=COLORS[0],ls='--',label='명령 vx')
        ax.plot(z['t'],z['wz'],color=COLORS[1],label='실제 wz');ax.plot(z['t'],z['command'][:,2],color=COLORS[1],ls='--',label='명령 wz')
        ax.set(title=label+' · 명령 반응',xlabel='초',ylabel='vx m/s · wz rad/s',xlim=(0,12));ax.legend(ncol=2,fontsize=8)
        for ax in axes[row]:
            for x in [3,6,9]:ax.axvline(x,color='#555555',ls=':',lw=.7)
            ax.grid(alpha=.15)
    fig.savefig(out/'gait_and_commands.png',dpi=145);plt.close(fig)
    fig,axes=plt.subplots(3,4,figsize=(16,10),layout='constrained')
    for ji,ax in enumerate(axes.flat):
        for (label,z),color in zip(loaded.items(),COLORS):ax.plot(z['t'],np.rad2deg(z['joint_pos'][:,ji]),label=label,color=color,lw=.8,alpha=.9)
        ax.set(title=joint_names[ji].replace('_joint',''),xlabel='초',ylabel='각도(°)');ax.grid(alpha=.2)
    axes.flat[0].legend(fontsize=8);fig.suptitle('관절각: 진폭이 크다고 좋은 보행은 아님. reset·위상·몸 기울기와 함께 해석',fontsize=14)
    fig.savefig(out/'joint_angles.png',dpi=135);plt.close(fig)
    result={'clips':metrics,'names_source':str(args.coordinates),'foot_names':foot_names,'joint_names':joint_names,
            'limits':'Names from actual training asset metadata, same asset path and direct data-array order must be cross-checked with recording metadata. Fixed physics, mean action/latent. XY speed is link-center motion, not surface tangent contact slip. Segment means include resets; not independent success rates.'}
    (out/'capture_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(metrics,ensure_ascii=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
    t=s.add_parser('training');t.add_argument('--run',action='append',required=True);t.add_argument('--end',type=int,required=True);t.add_argument('--out',required=True);t.add_argument('--title',required=True)
    c=s.add_parser('captures');c.add_argument('--clip',action='append',required=True);c.add_argument('--out',required=True);c.add_argument('--coordinates',required=True)
    a=p.parse_args();(training if a.mode=='training' else captures)(a)
