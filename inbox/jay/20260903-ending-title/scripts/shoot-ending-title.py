# -*- coding: utf-8 -*-
"""엔딩 타이틀 HTML 을 프레임별로 촬영해 MP4 로 굽는다."""
import os, sys, subprocess, shutil, concurrent.futures as cf, urllib.parse, time

SP = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(SP, "shotpage.html")
FR = os.path.join(SP, "frames")
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
FFMPEG = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
FPS, DUR, W, H = 30, 12.0, 1920, 1080
N = int(round(FPS * DUR))
WORKERS = 6

def shot(i):
    t = i / FPS
    out = os.path.join(FR, f"f{i:04d}.png")
    url = "file:///" + PAGE.replace("\\", "/") + "?shot=1&t=" + f"{t:.4f}"
    prof = os.path.join(FR, f".p{i%WORKERS}")
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=1", "--no-sandbox", "--mute-audio",
           "--disable-extensions", "--disable-background-networking",
           f"--user-data-dir={prof}", f"--window-size={W},{H}",
           "--virtual-time-budget=2500", f"--screenshot={out}", url]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    ok = os.path.isfile(out) and os.path.getsize(out) > 2000
    return i, ok, (r.stderr[-160:].decode("utf8", "replace") if not ok else "")

def main():
    shutil.rmtree(FR, ignore_errors=True); os.makedirs(FR, exist_ok=True)
    t0 = time.time(); bad = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for k, (i, ok, err) in enumerate(ex.map(shot, range(N)), 1):
            if not ok: bad.append((i, err))
            if k % 30 == 0:
                print(f"  {k}/{N}  {time.time()-t0:.0f}s", flush=True)
    print(f"촬영 {N-len(bad)}/{N} · {time.time()-t0:.1f}초")
    if bad:
        print("실패:", bad[:3]); sys.exit(1)
    mp4 = os.path.join(SP, "foothold-ending-title.mp4")
    r = subprocess.run([FFMPEG, "-y", "-framerate", str(FPS),
        "-i", os.path.join(FR, "f%04d.png"), "-c:v", "libx264", "-preset", "slow",
        "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4],
        capture_output=True)
    if r.returncode != 0:
        print(r.stderr[-900:].decode("utf8", "replace")); sys.exit(1)
    print(f"MP4  {mp4}  {os.path.getsize(mp4)/1e6:.2f} MB  {N} 프레임 · {FPS} fps · {DUR}초")

main()
