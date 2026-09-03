# -*- coding: utf-8 -*-
"""연출 10컷에서 구간을 잘라 러프컷을 만든다."""
import os, subprocess, sys, json
FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
CINE = LAB + "/sim/eval/results/20260903-flat-army-cine"
TITLE = LAB + "/inbox/jay/20260903-ending-title/foothold-ending-title.mp4"
OUT = os.path.dirname(os.path.abspath(__file__))
SEG = os.path.join(OUT, "segments"); os.makedirs(SEG, exist_ok=True)

# (파일, 시작초, 길이초, 설명)  구간은 움직임 실측으로 골랐다
CUTS = [
    ("foot",      14.0, 5.0, "발이 지면을 딛는다. 가장 가까운 것부터"),
    ("side",       0.5, 4.0, "옆으로 흐르는 다리들. 발소리를 붙일 자리"),
    ("lead",      10.0, 5.0, "앞모습. 얼굴이 보인다"),
    ("orbit",     14.0, 5.0, "선회. 개체가 가장 크다"),
    ("aisle",     12.0, 4.0, "대군 안쪽 통로"),
    ("underfoot", 14.0, 4.0, "지면 7 cm. 대군이 넘어간다"),
    ("dolly",      3.0,10.0, "달리 아웃. 규모가 드러난다"),
    ("rise",      11.5, 8.5, "수직 상승. 10 m 선이 중앙을 가른다"),
]
FPS = 50

def run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(r.stderr[-1200:].decode("utf8", "replace")); sys.exit(1)
    return r

parts = []
for i, (name, ss, dur, note) in enumerate(CUTS):
    src = f"{CINE}/flat_army_A_4096_{name}.mp4"
    dst = f"{SEG}/{i:02d}_{name}.mp4"
    run([FF, "-y", "-ss", str(ss), "-t", str(dur), "-i", src,
         "-vf", f"fps={FPS},format=yuv420p", "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", dst])
    parts.append(dst)
    print(f"  {i:02d} {name:10} {ss:5.1f} +{dur:4.1f}초  {note}")

# 엔딩 타이틀은 30fps 라 50fps 로 맞춘다 (러프컷 임시 조치)
t = f"{SEG}/{len(CUTS):02d}_title.mp4"
run([FF, "-y", "-i", TITLE, "-vf", f"fps={FPS},format=yuv420p", "-an",
     "-c:v", "libx264", "-preset", "medium", "-crf", "18", t])
parts.append(t)
print(f"  {len(CUTS):02d} title      0.0 +12.0초  엔딩 타이틀 (30 -> 50 fps 변환)")

lst = os.path.join(SEG, "list.txt")
with open(lst, "w", encoding="utf-8") as f:
    for p in parts:
        f.write("file '" + p.replace("\\", "/") + "'\n")

final = os.path.join(OUT, "foothold-roughcut.mp4")
run([FF, "-y", "-f", "concat", "-safe", "0", "-i", lst,
     "-c:v", "libx264", "-preset", "slow", "-crf", "18",
     "-pix_fmt", "yuv420p", "-movflags", "+faststart", final])
dur = sum(c[2] for c in CUTS) + 12.0
print(f"\n러프컷  {final}")
print(f"  {len(parts)}컷 · {dur:.1f}초 · {os.path.getsize(final)/1e6:.1f} MB")
