# -*- coding: utf-8 -*-
"""컷 검수 시트: 발 · 돌이 있는 화면 아래쪽 절반을 원본 해상도에서 잘라 시각 표시와 함께 타일로 붙인다.

돌이 생기거나 사라지는지, 발이 돌을 딛는지, 점프가 있는지를 4fps 시트는 놓친다(10/01 s12 · s14).
기본 6fps · 아래 절반 · 한 칸 폭 400px.

사용: python qc_sheet.py <영상.mp4> <출력.jpg> [fps=6] [y0=0.45]
"""
import subprocess, sys, io
from PIL import Image, ImageDraw

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"


def main(src, out, fps=6.0, y0=0.45, cols=8, w=400):
    raw = subprocess.run([FF, "-v", "error", "-i", src, "-vf", f"fps={fps},scale=1920:1080",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    frames, i = [], 0
    sig = b"\x89PNG\r\n\x1a\n"
    parts = raw.split(sig)[1:]
    for p in parts:
        im = Image.open(io.BytesIO(sig + p)).convert("RGB")
        im = im.crop((0, int(1080 * y0), 1920, 1080))
        im = im.resize((w, round(w * im.height / im.width)))
        ImageDraw.Draw(im).text((4, 2), f"{i / fps:.2f}s", fill=(255, 255, 0))
        frames.append(im); i += 1
    h = frames[0].height
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h))
    for k, im in enumerate(frames):
        sheet.paste(im, ((k % cols) * w, (k // cols) * h))
    sheet.save(out, quality=85)
    print(out, len(frames), "frames")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], float(a[2]) if len(a) > 2 else 6.0, float(a[3]) if len(a) > 3 else 0.45)
