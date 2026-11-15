# -*- coding: utf-8 -*-
"""새 배경판 위에 원본 글자판(RGBA 360장)을 얹어 엔딩 12초를 만든다.

로고 · 슬로건 · 락업 픽셀은 shoot_ending_layers.py type 판 그대로다. 배경판만 바뀐다.
배경판 길이가 12초가 아니면(Seedance 출력은 11.7초 등) 영상과 소리를 함께 12초로 늘이거나 줄인다.

사용: python compose_ending.py <배경판.mp4> <출력.mp4>
"""
import subprocess, sys, re
from pathlib import Path

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
WORK = Path(__file__).resolve().parents[1] / "_out" / "ending_work"
TYPE = WORK / "frames_type" / "f%04d.png"
DUR, FPS = 12.0, 30


def probe(p):
    err = subprocess.run([FF, "-hide_banner", "-i", str(p)], capture_output=True, text=True, errors="replace").stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s), ("Audio:" in err)


def main(plate, out):
    d, has_a = probe(plate)
    k = DUR / d
    vf = (f"[0:v]scale=1920:1080,setpts={k:.6f}*PTS,fps={FPS},trim=duration={DUR},format=yuv420p[bg];"
          f"[1:v]format=rgba[ty];[bg][ty]overlay=0:0:shortest=1,format=yuv420p[v]")
    cmd = [FF, "-y", "-v", "error", "-i", str(plate), "-framerate", str(FPS), "-i", str(TYPE),
           "-filter_complex", vf, "-map", "[v]"]
    if has_a:
        cmd += ["-map", "0:a", "-af", f"atempo={1/k:.6f},apad,atrim=0:{DUR}", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-crf", "16", "-preset", "slow", "-t", str(DUR), str(out)]
    subprocess.run(cmd, check=True)
    print(f"{out}  (배경판 {d:.2f}s x{k:.4f} → {DUR}s, 소리 {'있음' if has_a else '없음'})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
