# -*- coding: utf-8 -*-
"""영상에서 3DGS 학습용 프레임을 뽑는다 (PoC 1단계).

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-16
근거: RESEARCH-3dgs-terrain.md G1-4 의 적용안
요지: 3 프레임 창마다 가장 선명한 한 장을 고르고, 이웃 대비 유독 흐린 것을 버린다.
      그대로 디코드한 판(plain)과 HLG 를 SDR 로 톤매핑한 판(sdr) 두 벌을 만든다.

쓰는 법
    <isaac311 python> poc_frames.py --video <mp4> --out _frames [--window 3] [--drop_ratio 0.6]

산출물 (전부 .gitignore 대상 · 경로만 기록한다)
    _frames/frames.csv      order, frame_index, time_s, lapvar, kept, reason
    _frames/plain/NNNN.jpg  OpenCV 디코드 그대로 (품질 95)
    _frames/sdr/NNNN.jpg    ffmpeg zscale + tonemap(hable) 로 HLG -> bt709 SDR (q:v 2)
    NNNN 은 원본 프레임 번호(0 시작)다. 두 벌의 같은 번호는 같은 프레임이다.

선명도는 그레이 전체 프레임의 라플라시안 분산이다. 절대값은 장면마다 달라서
문턱을 고정하지 않고, 창 25 프레임의 이동 중앙값 대비 비율(drop_ratio)로 버린다.
"""
import argparse
import csv
import os
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")


def sharpness_all(video):
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise SystemExit("영상을 못 열었다: " + video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    vals = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        vals.append(cv2.Laplacian(g, cv2.CV_64F).var())
    cap.release()
    return np.asarray(vals), fps


def rolling_median(x, w):
    half = w // 2
    out = np.empty_like(x)
    for i in range(len(x)):
        lo, hi = max(0, i - half), min(len(x), i + half + 1)
        out[i] = np.median(x[lo:hi])
    return out


def select_frames(lap, window, drop_ratio, med_window):
    med = rolling_median(lap, med_window)
    rows = []
    for k in range(0, len(lap), window):
        seg = lap[k:k + window]
        idx = k + int(np.argmax(seg))
        kept = lap[idx] >= drop_ratio * med[idx]
        rows.append((idx, float(lap[idx]), bool(kept), "" if kept else "blur<%.2fx median" % drop_ratio))
    return rows


def write_plain(video, picks, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    want = {i for i, _, kept, _ in picks if kept}
    cap = cv2.VideoCapture(video)
    i = 0
    n = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i in want:
            # 한글 경로에서도 안전하게: imencode 뒤 tofile (cv2.imread/imwrite 는 Windows 유니코드 경로에 약하다)
            ok_enc, buf = cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 95])
            buf.tofile(os.path.join(out_dir, "%04d.jpg" % i))
            n += 1
        i += 1
    cap.release()
    return n


def write_sdr(video, picks, out_dir):
    """HLG(arib-std-b67 · bt2020) 를 bt709 SDR 로 톤매핑해서 고른 프레임만 쓴다."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(out_dir, exist_ok=True)
    idx = [i for i, _, kept, _ in picks if kept]
    sel = "+".join("eq(n\\,%d)" % i for i in idx)
    vf = ("select='%s',zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
          "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p") % sel
    tmp_pattern = os.path.join(out_dir, "seq%04d.jpg")
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-vf", vf,
           "-fps_mode", "vfr", "-q:v", "2", tmp_pattern]
    subprocess.run(cmd, check=True)
    # ffmpeg 는 1 부터 순번을 매긴다. 원본 프레임 번호로 이름을 바꾼다.
    n = 0
    for order, i in enumerate(idx, start=1):
        src = os.path.join(out_dir, "seq%04d.jpg" % order)
        if os.path.exists(src):
            os.replace(src, os.path.join(out_dir, "%04d.jpg" % i))
            n += 1
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True)
    p.add_argument("--out", default="_frames")
    p.add_argument("--window", type=int, default=3, help="이 수의 연속 프레임마다 한 장")
    p.add_argument("--drop_ratio", type=float, default=0.6, help="이동 중앙값 대비 이 비율 아래면 버린다")
    p.add_argument("--med_window", type=int, default=25)
    p.add_argument("--skip_sdr", action="store_true")
    a = p.parse_args()

    lap, fps = sharpness_all(a.video)
    picks = select_frames(lap, a.window, a.drop_ratio, a.med_window)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "frames.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["order", "frame_index", "time_s", "lapvar", "kept", "reason"])
        for order, (i, v, kept, why) in enumerate(picks):
            w.writerow([order, i, "%.3f" % (i / fps), "%.1f" % v, int(kept), why])
    n_plain = write_plain(a.video, picks, os.path.join(a.out, "plain"))
    n_sdr = 0 if a.skip_sdr else write_sdr(a.video, picks, os.path.join(a.out, "sdr"))
    kept = [v for _, v, k, _ in picks if k]
    print("frames %d · fps %.3f · lapvar min/median/max %.0f / %.0f / %.0f"
          % (len(lap), fps, lap.min(), np.median(lap), lap.max()))
    print("picked %d of %d windows · dropped %d · kept lapvar min %.0f"
          % (len(kept), len(picks), len(picks) - len(kept), min(kept)))
    print("written plain %d · sdr %d -> %s" % (n_plain, n_sdr, os.path.abspath(a.out)))


if __name__ == "__main__":
    main()
