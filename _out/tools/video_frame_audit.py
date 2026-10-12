# -*- coding: utf-8 -*-
"""영상 프레임 전수 검사 (10/12 E1·E2 HUD 영상 24 편 결함을 잡은 것)

원래 이름 audit_frames.py. 사용: python video_frame_audit.py [경로 일부 ...] (WEB 상수의 폴더를 훑는다)
환경 변수: AUDIT_WEB (훑을 폴더) · AUDIT_OUT (결과 json) · AUDIT_FPS (기본 all = 전 프레임 · 숫자면 그 fps 로 표본)

웹 사본 영상 전수 검사: 카메라가 가려져 의미 없는 프레임 · 검은 프레임 · 단색(파란) 프레임.

3D 화면 영역만 본다 (위 HUD 판 · 아래 판정 띠 제외). 기본은 전 프레임.
4 fps 표본은 검은 프레임 한 장을 놓친다 (10/12 하위 작업이 깨 보고 확인 · 1/501 이 4 fps 에서 0).
전 프레임 판은 옛 결함 24 편을 24/24 잡았고, 바꾼 332 편 282,190 프레임에서 0 이었다 (10/12 lead).
판정 (프레임):
  dark    : 영역 평균 밝기 < 20
  flat    : 영역 밝기 표준편차 < 6 (단색으로 덮임)
  blue    : 파랑 우세 화소 (b > r + 25 and b > g + 10) 비율 > 0.35
출력: audit_frames.json · 영상별 걸린 프레임 수 · 구간
"""
import json
import os
import subprocess
import sys

import numpy as np

WEB = os.environ.get('AUDIT_WEB', 'C:/isaac/ext/go2_rl_robotlab/_eval/out/web')
OUT = os.environ.get('AUDIT_OUT', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audit_frames.json'))
W, H = 160, 90
SAMPLE = os.environ.get('AUDIT_FPS', 'all')
Y0, Y1 = 28, 77          # 720p 기준 y 224 ~ 616 (HUD 판 아래 · 판정 띠 위)


def src_fps(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
                        '-of', 'csv=p=0', path], capture_output=True, text=True, check=True).stdout.strip()
    a, b = r.split('/')
    return float(a) / float(b)


def frames(path):
    vf = f'scale={W}:{H}' if SAMPLE == 'all' else f'fps={SAMPLE},scale={W}:{H}'
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf,
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
    a = np.frombuffer(p.stdout, np.uint8)
    return a.reshape(-1, H, W, 3)

res = []
files = sorted(os.path.join(d, f).replace('\\', '/') for d, _, fs in os.walk(WEB) for f in fs if f.endswith('.mp4'))
if len(sys.argv) > 1:
    files = [f for f in files if any(k in f for k in sys.argv[1:])]
for i, f in enumerate(files):
    fr = frames(f).astype(np.float32)
    reg = fr[:, Y0:Y1]
    lum = reg.mean(axis=3)
    mean = lum.mean(axis=(1, 2))
    std = lum.std(axis=(1, 2))
    r, g, b = reg[..., 0], reg[..., 1], reg[..., 2]
    blue = ((b > r + 25) & (b > g + 10)).mean(axis=(1, 2))
    bad = (mean < 20) | (std < 6) | (blue > 0.35)
    idx = np.nonzero(bad)[0]
    FPS = src_fps(f) if SAMPLE == 'all' else float(SAMPLE)
    spans = []
    for k in idx:
        t = k / FPS
        if spans and t - spans[-1][1] <= 1.0 / FPS + 1e-6:
            spans[-1][1] = t
        else:
            spans.append([t, t])
    res.append({'file': os.path.relpath(f, WEB).replace('\\', '/'), 'n': int(len(fr)), 'bad': int(len(idx)),
                'frac': round(len(idx) / max(1, len(fr)), 3), 'spans': [[round(a, 2), round(b2, 2)] for a, b2 in spans],
                'min_std': round(float(std.min()), 1), 'max_blue': round(float(blue.max()), 3), 'min_mean': round(float(mean.min()), 1)})
    if (i + 1) % 50 == 0:
        print(i + 1, '/', len(files), flush=True)
json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
flag = [x for x in res if x['bad']]
print('videos', len(res), 'flagged', len(flag))
for x in sorted(flag, key=lambda x: -x['frac'])[:40]:
    print(f"{x['frac']:.2f} {x['bad']:3d}/{x['n']:3d} std{x['min_std']:5.1f} blue{x['max_blue']:.2f} mean{x['min_mean']:5.1f} {x['file']} {x['spans'][:3]}")
