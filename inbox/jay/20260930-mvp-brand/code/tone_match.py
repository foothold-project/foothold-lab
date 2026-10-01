# -*- coding: utf-8 -*-
"""전 컷 톤을 기준 톤 하나에 맞춘다 (10/01 팀장: 「톤 기준 톤 하나 만들어서 맞추라고」).

재기: 컷마다 프레임 6 장에서 밝기 하위 30 % (땅 · 그늘) · 가운데 35~65 % · 상위 30 % (안개 · 하늘) 픽셀의 평균 RGB.
기준 톤: TONE.json 의 lo / mid / hi (RGB 비율). 밝기는 컷마다 그대로 두고 색 비율만 기준에 맞춘다
  → 폭풍 속처럼 어두운 컷도 밝기는 지키고 노랑 · 초록 · 주황 · 분홍 치우침만 같아진다.
맞추기: 채널마다 곱하기 하나(화이트밸런스). 중간 밴드 색 비율이 기준 쪽으로 가게 하고, 중간 밴드 밝기는 유지.
  곱은 어두운 톤 · 중간톤에만 걸고 150~255 에서 1 로 줄여, 하이라이트(해 · 흰 몸체)는 원본 그대로 둔다.
  (이전 판 4: 하이라이트에도 곱해 s14 · s15 해 주변이 청록으로 뜸.) 검정은 0 그대로.
  세기 STRENGTH(0.6) · 채널 곱 범위 GAIN_RANGE(0.85~1.2) 로 컷 자체의 색과 생기를 남긴다.
  이전 판 3: 채널별 감마 → 어두운 쪽 따뜻함까지 빠져 그늘이 회색으로 죽음.
  이전 판 1: lo · hi 두 점 직선 → 중간톤 분홍이 남음(s14 · s15 지적).
  이전 판 2: 다섯 점 곡선 → 밝은 끝을 채널마다 깎아 흰색이 회색으로 죽고 탁해짐(10/01 팀장: 「cliping 된 느낌 · 색이 다 죽었어」).

  python tone_match.py measure <영상...>                  재기만
  python tone_match.py apply <입력> <출력> [in] [out]      기준에 맞춰 출력 (구간 지정 시 그 구간만 잼)
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
TONE = Path(__file__).with_name("TONE.json")


def dur(p):
    e = subprocess.run([FF, "-hide_banner", "-i", p], capture_output=True, text=True, errors="replace").stderr
    h, m, s = e.split("Duration: ")[1].split(",")[0].split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def stats(p, t0=0.0, t1=None):
    t1 = t1 or dur(p)
    px = []
    for t in np.linspace(t0 + 0.1, t1 - 0.1, 6):
        raw = subprocess.run([FF, "-v", "error", "-ss", f"{t:.2f}", "-i", p, "-frames:v", "1", "-vf", "scale=480:270",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if len(raw) == 480 * 270 * 3:
            px.append(np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(float))
    px = np.concatenate(px)
    L = px.mean(1)
    q = np.percentile(L, [30, 35, 65, 70])
    lo = px[L <= q[0]].mean(0)
    mid = px[(L >= q[1]) & (L <= q[2])].mean(0)
    hi = px[L >= q[3]].mean(0)
    return lo, mid, hi


def ratio(v): return v / v.mean()


def fmt(v): return "%3.0f/%3.0f/%3.0f (R-G %+3.0f G-B %+3.0f)" % (*v, v[0] - v[1], v[1] - v[2])


STRENGTH = 0.6                 # 0.8 은 s14 땅이 보랏빛 회색으로 감 (파랑 x1.38)
GAIN_RANGE = (0.85, 1.2)


def gains(bands, tone, strength=STRENGTH):
    """채널별 곱. 중간 밴드 비율을 기준 비율로, 중간 밴드 밝기(채널 평균)는 유지."""
    mid = bands[1]
    k = (mid.mean() * np.array(tone["mid"])) / np.maximum(mid, 1)
    k = k ** strength
    k = k * (mid.mean() / (mid * k).mean())
    return np.clip(k, *GAIN_RANGE)


def curves(bands, tone):
    """채널별 curves 점 문자열. 입력 점이 겹치거나 출력이 뒤집히지 않게 단조로 정리."""
    out = []
    for c in range(3):
        pts = [(0.0, 0.0)]
        for v, key in zip(bands, ("lo", "mid", "hi")):
            pts.append((v[c], v.mean() * tone[key][c]))
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        slope = (y2 - y1) / max(x2 - x1, 1)
        pts.append((255.0, min(255.0, y2 + slope * (255 - x2))))
        clean = []
        for x, y in pts:
            y = min(max(y, 0.0), 255.0)
            if clean and (x <= clean[-1][0] + 1 or y < clean[-1][1]): continue
            clean.append((x, y))
        out.append(" ".join(f"{x / 255:.4f}/{y / 255:.4f}" for x, y in clean))
    return out


def main():
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "measure":
        for p in args:
            lo, mid, hi = stats(p)
            print(f"{Path(p).name:28s} lo {fmt(lo)}  mid {fmt(mid)}  hi {fmt(hi)}")
    elif cmd == "apply":
        src, dst = args[0], args[1]
        t0 = float(args[2]) if len(args) > 2 else 0.0
        t1 = float(args[3]) if len(args) > 3 else None
        tone = json.load(open(TONE, encoding="utf-8"))
        bands = stats(src, t0, t1)
        g = gains(bands, tone)
        w = "(1-pow(clip((val-150)/105,0,1),2)*(3-2*clip((val-150)/105,0,1)))"
        lut = ":".join(f"{c}='clip(val*(1+({g[i]:.4f}-1)*{w}),0,255)'" for i, c in enumerate("rgb"))
        subprocess.run([FF, "-y", "-v", "error", "-i", src, "-vf", f"format=rgb24,lutrgb={lut},format=yuv420p",
                        "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", dst], check=True)
        after = stats(dst, t0, t1)
        print(Path(dst).name + ": " + " | ".join(f"{n} {fmt(a)} -> {fmt(b2)}" for n, a, b2 in zip(("lo", "mid", "hi"), bands, after)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
