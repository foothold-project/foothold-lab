# -*- coding: utf-8 -*-
"""s1718(대군이 FOOTHOLD 로 모인 상승) 끝을 엔딩 모션그래픽 워드마크에 맞춰 디졸브한다.

1. s1718 마지막 프레임에서 밝은 대열의 경계 상자를 잰다.
2. 엔딩 워드마크 경계 상자 WM 에 맞도록 s1718 전체에 배율 · 이동을 건다(보정이 1 px 미만이면 생략).
3. 기존 조립(build_full43.py 의 tail)과 같이 엔딩을 ED_SS 초부터 붙이고 XF 초 디졸브한다.

사용: python compose_tail.py <s1718.mp4> <ending.mp4> <출력.mp4> [엔딩 길이 초, 기본 4.0 · 끝까지면 9.4]
"""
import subprocess, sys, re, io
import numpy as np
from PIL import Image

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
WM = (600, 496, 1314, 585)          # 엔딩 3.0 초 워드마크 경계 상자 (원본 · 합성본 동일, 실측)
ED_SS, ED_DUR, XF, FPS = 2.6, 4.0, 0.4, 30
THR = 140


def dur(p):
    e = subprocess.run([FF, "-hide_banner", "-i", p], capture_output=True, text=True, errors="replace").stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", e).groups()
    return int(h) * 3600 + int(m) * 60 + float(s), ("Audio:" in e)


def last_bbox(p):
    raw = subprocess.run([FF, "-v", "error", "-sseof", "-0.05", "-i", p, "-update", "1", "-frames:v", "1",
                          "-vf", "scale=1920:1080", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True, check=True).stdout
    a = np.asarray(Image.open(io.BytesIO(raw)).convert("L")) > THR
    a[:300] = False; a[800:] = False                      # 글자 띠 밖의 밝은 잡음 제외
    ys, xs = np.where(a)
    return xs.min(), ys.min(), xs.max(), ys.max()


def main(s1718, ending, out, ed_dur=None):
    global ED_DUR
    if ed_dur: ED_DUR = float(ed_dur)
    bb = last_bbox(s1718)
    sx = (WM[2] - WM[0]) / (bb[2] - bb[0]); sy = (WM[3] - WM[1]) / (bb[3] - bb[1])
    s = (sx + sy) / 2
    tx = WM[0] - bb[0] * s; ty = WM[1] - bb[1] * s
    print("s1718 끝 경계", bb, "→ 배율", round(s, 4), "이동", round(tx, 1), round(ty, 1))
    if abs(s - 1) * 1920 < 1 and abs(tx) < 1 and abs(ty) < 1:
        fix = "scale=1920:1080"
    else:
        W2, H2 = round(1920 * s), round(1080 * s)
        # 확대 후 crop / 축소 후 pad 로 경계 상자를 WM 에 맞춘다
        if s >= 1:
            fix = f"scale={W2}:{H2},crop=1920:1080:{round(-tx)}:{round(-ty)}"
        else:
            fix = f"scale={W2}:{H2},pad=1920:1080:{round(tx)}:{round(ty)}:color=0x12161d"
    d, has_a = dur(s1718)
    off = d - XF
    fc = (f"[0:v]setpts=PTS-STARTPTS,{fix},fps={FPS},format=yuv420p,settb=AVTB[a];"
          f"[1:v]trim=start={ED_SS}:duration={ED_DUR},setpts=PTS-STARTPTS,fps={FPS},format=yuv420p,settb=AVTB[b];"
          f"[a][b]xfade=transition=fade:duration={XF}:offset={off:.3f},format=yuv420p[v];"
          + (f"[0:a]asetpts=PTS-STARTPTS[aa];" if has_a else f"anullsrc=r=48000:cl=stereo,atrim=duration={d:.3f}[aa];") +
          f"[1:a]atrim=start={ED_SS}:duration={ED_DUR},asetpts=PTS-STARTPTS[ab];"
          f"[aa][ab]acrossfade=d={XF}[au]")
    subprocess.run([FF, "-y", "-v", "error", "-i", s1718, "-i", ending, "-filter_complex", fc,
                    "-map", "[v]", "-map", "[au]", "-c:v", "libx264", "-crf", "16", "-preset", "slow",
                    "-c:a", "aac", "-b:a", "192k", out], check=True)
    print(out, f"(s1718 {d:.2f}s + 엔딩 {ED_SS}~{ED_SS+ED_DUR}s, 디졸브 {XF}s @ {off:.2f}s)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(*sys.argv[1:5])
