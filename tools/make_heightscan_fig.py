# -*- coding: utf-8 -*-
"""정책이 지형을 «무엇으로» 보는지 실제 캡처 위에 실척으로 그린다.

분류: 도구
작성: 오흥재 · 2026-09-28
근거: 팀장 지시 「실제 우리 Go2 시뮬레이션에서 캡쳐를 하던가 해서 캡쳐한
      이미지 위에서 그림을 그려주는게 좋을 것 같다 (그림 혹은 영상으로 설명
      보완)」

    python tools/make_heightscan_fig.py

## 숫자는 전부 학습 시각 저장본에서 읽는다

`params/env.yaml` 의 `height_scanner` 다. 손으로 적은 값이 없다.

```
    pattern_cfg.func          grid_pattern
    pattern_cfg.resolution    0.1 m
    pattern_cfg.size          (1.6, 1.0) m
    pattern_cfg.direction     (0, 0, -1)      아래로 쏜다
    ray_alignment             yaw             요만 따라 돈다
    drift_range               (0, 0)          잡음 없음
```

격자는 `-size/2 .. +size/2` 를 `resolution` 간격으로 끊으므로
**x 17 개 · y 11 개 = 187 개**다.

**이 수를 체크포인트로 반증했다.** `actor.0.weight` 가 (512, 235) 이고
몸통·관절이 3+3+3+3+12+12+12 = 48 이라 235 - 48 = 187 로 맞는다 `확인됨`.

## 실척을 어떻게 맞추나

축척을 「가운데 값 하나」로 쓰지 않는다. **카메라를 그대로 세워서 한 점씩
투영한다.** trace 에 카메라가 적혀 있다.

```
    eye     (-5.0, 0.0, 8.9)
    target  (-4.0, 0.0, 0.1)
    hfov    60 도 · 1920 x 1080
```

검산으로 `target` 을 투영해 화면 정중앙 (960, 540) 이 나오는지 본다.
한 값으로 밀면 화면 가장자리에서 16 % 까지 어긋난다 (모서리가 카메라에서
10.5 m 이고 가운데는 8.8 m 다). 로봇이 가운데 있지 않으므로 그 차이가 그림에
그대로 남는다. 그래서 점마다 투영한다.

## 로봇을 어떻게 찾나

밝기만 보면 못 찾는다 `확인됨` (지형 면이 253 까지 올라가 로봇과 안 갈린다).
**로봇은 밝은 몸통 옆에 짙은 그림자가 붙는다.** 지형 면에는 안 붙는다.
3 x 3 칸 안에 «235 넘는 곳»과 «90 아래인 곳»이 같이 있는 자리를 고른다.

## 글꼴

**HUD 글꼴을 쓰지 않는다.** 그것은 부분집합이라 아는 낱말 말고는 네모로
나온다 `확인됨` (2026-09-28 에 두 번 당했다). 시스템 한글 글꼴을 쓴다.
"""
from __future__ import print_function

import glob
import io
import json
import math
import os
import sys

import imageio.v2 as iio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(HERE, 'sim', 'eval', 'results', '20260928-terrain-shots')
RUN = (r'C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/'
       r'2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000')
OUT = os.path.join(HERE, 'docs', 'assets', 'visual', 'v2-height-scan.png')

# **지형은 `rails` 다.** `random_rough` 은 면마다 흰색·검정이라 「밝은 몸통 +
# 짙은 그림자」 로 로봇을 못 가린다 `확인됨` (두 번 다 지형을 잡았다).
# `rails` 는 바닥이 평평한 밝은 회색이라 로봇이 또렷하고, 레일 모서리에
# 격자가 걸치면 «스캔이 무엇을 보는가» 도 같이 보인다.
TERRAIN = 'rails'

KO_BOLD = 'C:/Windows/Fonts/malgunbd.ttf'
KO_REG = 'C:/Windows/Fonts/malgun.ttf'


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return ImageFont.load_default()


def read_scanner():
    """격자 규격을 저장본에서 읽는다. 여기서 짓지 않는다."""
    txt = io.open(os.path.join(RUN, 'params', 'env.yaml'), encoding='utf-8').read()
    blk = txt[txt.index('height_scanner:'):][:2000]
    j = blk.index('pattern_cfg:')
    res = float(blk[blk.index('resolution:', j):].split('\n')[0].split(':')[1])
    lines = blk[blk.index('size:', j):].split('\n')
    return res, float(lines[1].strip().lstrip('- ')), float(lines[2].strip().lstrip('- '))


def best_frame(d):
    mp4 = glob.glob(os.path.join(SHOTS, d, '*.mp4'))[0]
    r = iio.get_reader(mp4)
    n = r.count_frames()
    out = None
    for fr in (0.20, 0.35, 0.50, 0.70, 0.90):
        im = np.asarray(r.get_data(min(n - 1, int(n * fr))))[:, :, :3]
        if out is None or im.std() > out.std():
            out = im
    r.close()
    return out


def find_robot(g):
    """밝은 몸통 + 바로 옆 짙은 그림자. 지형 면에는 그림자가 안 붙는다."""
    H, W = g.shape
    C = 24
    gy, gx = H // C, W // C
    mx = np.zeros((gy, gx))
    mn = np.zeros((gy, gx))
    for y in range(gy):
        for x in range(gx):
            b = g[y * C:(y + 1) * C, x * C:(x + 1) * C]
            mx[y, x], mn[y, x] = b.max(), b.min()
    # **대비가 큰 것이 로봇이다** (흰 몸통 + 짙은 그림자). 가운데를 우선했더니
    # 지형 그늘을 잡았다 `확인됨` (대비 159 · 그림에 로봇이 안 보였다).
    # 다만 격자가 화면 밖으로 나가면 안 되므로 테두리 240 px 안쪽만 본다.
    M = 240
    cands = []
    for y in range(1, gy - 1):
        for x in range(1, gx - 1):
            hi = mx[y - 1:y + 2, x - 1:x + 2].max()
            lo = mn[y - 1:y + 2, x - 1:x + 2].min()
            if hi <= 235 or lo >= 90:
                continue
            px, py = x * C + C // 2, y * C + C // 2
            if px < M or px > W - M or py < M or py > H - M:
                continue
            cands.append((hi - lo, px, py))
    if not cands:
        return None, 0.0
    cands.sort(reverse=True)
    con, px, py = cands[0]
    return (px, py), con


def main():
    res, sx, sy = read_scanner()
    nx = int(round(sx / res)) + 1
    ny = int(round(sy / res)) + 1
    print('격자 %.1f x %.1f m · 간격 %.2f m -> %d x %d = %d 개'
          % (sx, sy, res, nx, ny, nx * ny))

    tr = json.load(io.open(glob.glob(
        os.path.join(SHOTS, TERRAIN, '*.json'))[0], encoding='utf-8'))
    cam = tr['camera']
    W, H = tr['resolution']
    E = np.array(cam['eye_m'], float)
    T = np.array(cam['target_m'], float)
    hfov = math.radians(cam['final_horizontal_fov_deg'])

    fwd = (T - E) / np.linalg.norm(T - E)
    right = np.cross(fwd, np.array([0.0, 0.0, 1.0]))
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    foc = (W / 2.0) / math.tan(hfov / 2.0)

    def proj(P):
        d = np.asarray(P, float) - E
        zc = float(np.dot(d, fwd))
        if zc <= 1e-6:
            return None
        return (W / 2.0 + float(np.dot(d, right)) / zc * foc,
                H / 2.0 - float(np.dot(d, up)) / zc * foc)

    # **검산.** target 이 정중앙으로 안 가면 카메라를 잘못 세운 것이다.
    chk = proj(T)
    if abs(chk[0] - W / 2.0) > 1.0 or abs(chk[1] - H / 2.0) > 1.0:
        raise SystemExit('** 투영 검산 실패: target -> %s **' % (chk,))
    print('투영 검산 통과 · target -> (%.1f, %.1f)' % chk)

    Z = float(T[2])

    def unproj(px, py):
        """화면 점을 바닥 평면 z = Z 로 되쏜다."""
        xc = (px - W / 2.0) / foc
        yc = -(py - H / 2.0) / foc
        ray = fwd + right * xc + up * yc
        if abs(ray[2]) < 1e-9:
            return None
        t = (Z - E[2]) / ray[2]
        return E + ray * t

    raw = best_frame(TERRAIN)
    at, contrast = find_robot(raw.mean(axis=2))
    if at is None:
        raise SystemExit('** 로봇을 못 찾았다 **')
    print('로봇 화면 자리 %s · 대비 %.0f' % (at, contrast))

    ground = unproj(at[0], at[1])
    print('그 자리의 바닥 좌표 (%.2f, %.2f, %.2f)' % tuple(ground))

    still = os.path.join(SHOTS, 'stills', TERRAIN + '.png')
    im = Image.open(still).convert('RGB')
    d = ImageDraw.Draw(im, 'RGBA')

    # 격자 187 점을 «한 점씩» 투영한다
    pts = []
    for iy in range(ny):
        for ix in range(nx):
            wx = ground[0] - sx / 2.0 + ix * res
            wy = ground[1] - sy / 2.0 + iy * res
            p = proj((wx, wy, Z))
            if p:
                pts.append(p)

    corners = [proj((ground[0] + a * sx / 2.0, ground[1] + b * sy / 2.0, Z))
               for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    d.polygon([tuple(c) for c in corners], outline=(255, 90, 40, 255))
    for i in range(4):
        d.line([tuple(corners[i]), tuple(corners[(i + 1) % 4])],
               fill=(255, 90, 40, 255), width=4)
    for p in pts:
        d.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3],
                  fill=(255, 190, 60, 235), outline=(120, 40, 0, 255))

    f_big = font(KO_BOLD, 34)
    f_mid = font(KO_REG, 21)
    f_dim = font(KO_BOLD, 30)

    # 치수
    mid_b = ((corners[0][0] + corners[1][0]) / 2, (corners[0][1] + corners[1][1]) / 2)
    d.text((mid_b[0] - 40, mid_b[1] + 14), '%.1f m' % sx, font=f_dim,
           fill=(255, 255, 255), stroke_width=4, stroke_fill=(20, 20, 24))
    mid_r = ((corners[1][0] + corners[2][0]) / 2, (corners[1][1] + corners[2][1]) / 2)
    d.text((mid_r[0] + 16, mid_r[1] - 18), '%.1f m' % sy, font=f_dim,
           fill=(255, 255, 255), stroke_width=4, stroke_fill=(20, 20, 24))

    # 자를 판. 로봇을 왼쪽에 두어 **오른쪽을 설명 상자에 내준다.**
    CW, CH, LEFT, TOP = 1500, 760, 430, 380
    cx0 = int(max(0, min(W - CW, at[0] - LEFT)))
    cy0 = int(max(0, min(H - CH, at[1] - TOP)))

    # 상자는 자르기 전 좌표로 둔다. 격자는 가로 1.0 m (약 190 px) 뿐이라
    # 오른쪽에 자리가 넉넉하다.
    bw, bh = 560, 212
    bx = cx0 + CW - bw - 30
    by = cy0 + 30
    d.rectangle([bx, by, bx + bw, by + bh], fill=(16, 18, 22, 228))
    d.text((bx + 22, by + 16), 'height_scan', font=f_big, fill=(255, 190, 60))
    for i, t in enumerate([
            '%d x %d = %d 개 · 격자 간격 %.2f m' % (nx, ny, nx * ny, res),
            '몸통 밑 %.1f x %.1f m 를 곧장 아래로 훑는다' % (sx, sy),
            '정책이 지형을 아는 통로는 이것 하나다',
            '관측 235 칸 중 %d 칸 · 나머지 48 은 몸통과 관절' % (nx * ny)]):
        d.text((bx + 22, by + 68 + i * 30), t, font=f_mid, fill=(226, 230, 236))

    # **자른다.** 1920 x 1080 전체에서는 격자가 손톱만 하다.
    im = im.crop((cx0, cy0, cx0 + CW, cy0 + CH))
    im = im.resize((int(CW * 1.25), int(CH * 1.25)), Image.LANCZOS)

    if not os.path.isdir(os.path.dirname(OUT)):
        os.makedirs(os.path.dirname(OUT))
    im.save(OUT, optimize=True)
    print('만듦 %s · %.0f KB'
          % (os.path.relpath(OUT, HERE), os.path.getsize(OUT) / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
