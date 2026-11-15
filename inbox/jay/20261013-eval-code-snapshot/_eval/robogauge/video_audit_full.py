# Every-frame audit for RoboGauge MuJoCo videos.
# Same criteria as foothold-lab _out/tools/video_frame_audit.py (dark / flat / blue), but the region is
# the whole frame (MuJoCo offscreen render has no HUD bands), and the blue rule is reported separately
# because the MuJoCo skybox is blue by design.
# Usage: python video_audit_full.py <dir_with_mp4> <out_json>
import json
import os
import subprocess
import sys

import numpy as np

W, H = 160, 90


def frames(path):
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={W}:{H}',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, H, W, 3)


def n_frames_probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                        'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', path],
                       capture_output=True, text=True, check=True).stdout
    s = json.loads(r)['streams'][0]
    return int(s['nb_read_frames']), s['r_frame_rate'], int(s['width']), int(s['height'])


def audit(path):
    fr = frames(path).astype(np.float32)
    lum = fr.mean(axis=3)
    mean = lum.mean(axis=(1, 2))
    std = lum.std(axis=(1, 2))
    r, g, b = fr[..., 0], fr[..., 1], fr[..., 2]
    blue = ((b > r + 25) & (b > g + 10)).mean(axis=(1, 2))
    dark = mean < 20
    flat = std < 6
    blue_dom = blue > 0.35
    # identical consecutive frames (frozen render) as extra signal
    diff = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2, 3)) if len(fr) > 1 else np.zeros(0)
    frozen = int((diff < 0.05).sum())
    nb, rate, w, h = n_frames_probe(path)
    return {
        'file': os.path.basename(path), 'n_decoded': int(len(fr)), 'n_probe': nb, 'rate': rate, 'size': f'{w}x{h}',
        'dark': int(dark.sum()), 'flat': int(flat.sum()), 'blue_dom': int(blue_dom.sum()),
        'bad_dark_or_flat_idx': [int(i) for i in np.nonzero(dark | flat)[0][:20]],
        'min_mean': round(float(mean.min()), 1), 'min_std': round(float(std.min()), 1),
        'max_blue': round(float(blue.max()), 3), 'frozen_pairs': frozen,
    }


if __name__ == '__main__':
    d, out = sys.argv[1], sys.argv[2]
    files = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith('.mp4'))
    res = [audit(f) for f in files]
    json.dump(res, open(out, 'w', encoding='utf-8'), indent=1)
    for x in res:
        print(f"{x['file']:60s} n={x['n_decoded']}/{x['n_probe']} {x['size']} dark={x['dark']} flat={x['flat']} "
              f"blue={x['blue_dom']} frozen={x['frozen_pairs']} min_mean={x['min_mean']} min_std={x['min_std']}")
