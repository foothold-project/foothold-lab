"""Read-only historical posture comparison. CPU only; source records are never changed."""
from pathlib import Path
import hashlib
import json
import math

import numpy as np


HERE = Path(__file__).resolve().parent
MEDIA = Path('C:/Users/AI-WS01/s2_lab/videos')
OUT = HERE / 'figs' / 'posture-history-1024'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample(path, label, iteration):
    metadata = path.with_name(path.name.replace('_feet.npz', '.json'))
    meta = json.loads(metadata.read_text(encoding='utf-8'))
    assert Path(meta['checkpoint']).stem == f'model_{iteration}'
    with np.load(path, allow_pickle=False) as a:
        rows = []
        for s in range(4):
            mask = a['seg'] == s
            tail = mask & (a['t'] >= s * 3 + 1.5)
            finite = mask & np.isfinite(a['body_height'])
            rows.append(dict(segment=s, height_m=float(np.median(a['body_height'][finite])),
                             height_valid_n=int(finite.sum()),
                             vx_tail=float(a['vx'][tail].mean()),
                             wz_tail=float(a['wz'][tail].mean())))
        names = [str(n) for n in a['foot_names']]
        indices = [next(i for i, n in enumerate(names) if n.startswith(leg))
                   for leg in ('FL', 'FR', 'RL', 'RR')]
        c = a['foot_contact'][:, indices].astype(bool)
        window = (a['t'] >= 4) & (a['t'] < 6)
        n = c[window].sum(axis=1)
        contact = dict(n=int(window.sum()),
                       front_equal=float((c[window, 0] == c[window, 1]).mean()),
                       rear_equal=float((c[window, 2] == c[window, 3]).mean()),
                       all_air=float((n == 0).mean()),
                       all_stance=float((n == 4).mean()))
        sample_mask = (a['t'] >= 4.04) & (a['t'] <= 4.16)
        examples = [dict(t=float(a['t'][k]), contact=c[k].astype(int).tolist())
                    for k in np.flatnonzero(sample_mask)]
    return dict(label=label, iteration=iteration, path=str(path), sha256=sha(path),
                metadata_path=str(metadata), metadata_sha256=sha(metadata),
                checkpoint=meta['checkpoint'], restored_modes=meta.get('restored_modes'),
                segments=rows, contact_4to6=contact, examples=examples)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ex23 = [sample(MEDIA / 'mid500_1022' / f'ex23r_{i}' / 'run_flat_feet.npz', 'EX-23', i)
            for i in (500, 1000, 1500)]
    ex11 = sample(MEDIA / 'joint_1022/ex11_flat_feet.npz', 'EX-11', 1500)
    ex15 = []
    for iteration, directory in ((500, 'ex15'), (1000, 'ex15_1000'), (1500, 'ex15_1500')):
        base = MEDIA / 'mid500_1022' / directory
        raw = base / 'run_flat_feet.npz'
        if not raw.exists():
            raw = base / 'ex11_flat_feet.npz'
        ex15.append(sample(raw, 'EX-15', iteration))
    p12 = MEDIA / 'x11_1022/clips/ex12_flat.json'
    j12 = json.loads(p12.read_text(encoding='utf-8'))
    ex12 = dict(path=str(p12), sha256=sha(p12), record_type='existing capture summary, no per-step NPZ',
                segments=j12['per_seg'])
    result = dict(height_definition='root z - (mean contacting foot-center z - 0.022 m); nonfinite excluded',
                  segment_definition='0:.5 m/s; 1:1 m/s; 2:+1.2 rad/s; 3:-1.2 rad/s; each 3 s',
                  velocity_summary='last 1.5 s of each segment',
                  ex23=ex23, ex11=ex11, ex12=ex12, ex15=ex15,
                  stationary_yaw_example=dict(command_wz=1.2, std=.5, linear_weight=1.5,
                                              yaw_weight=.5, yaw_term=.5*math.exp(-1.2**2/.5**2),
                                              note='formula illustration, not measured total reward; before dt scaling'))
    (OUT / 'metrics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    table = ['| EX-23 모델 | 전진 시 몸 높이 | 전진 실제 속도 | 좌회전 실제 속도 | 우회전 실제 속도 |',
             '|---|---:|---:|---:|---:|']
    for row in ex23:
        s = row['segments']
        table.append(f"| {row['iteration']} | {s[1]['height_m']*100:.1f} cm | {s[1]['vx_tail']:.3f} m/s | {s[2]['wz_tail']:+.3f} rad/s | {s[3]['wz_tail']:+.3f} rad/s |")
    (OUT / 'table.md').write_text('\n'.join(table)+'\n', encoding='utf-8')
    print('\n'.join(table))
    print(json.dumps({'ex15': [{k: r[k] for k in ('iteration', 'contact_4to6')} for r in ex15],
                      'height_ex11': ex11['segments'][1]['height_m'],
                      'height_ex12_summary': j12['per_seg']['전진 1.0']['height_median_m']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
