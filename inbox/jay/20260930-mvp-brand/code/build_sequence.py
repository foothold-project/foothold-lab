# -*- coding: utf-8 -*-
"""컷 목록을 잘라 이어 붙인다. 컷 사이는 영상 xfade · 소리 acrossfade 로 겹친다(겹침 0 이면 바로 붙임).

사용: python build_sequence.py <목록.json> <출력.mp4>
목록 형식: [{"src": "경로", "in": 0.0, "out": 5.0, "xf": 0.25}, ...]
  xf = 이 컷과 다음 컷이 겹치는 초. 마지막 컷의 xf 는 무시.
소리 없는 컷은 무음을 채운다. 모두 1920x1080 · 24fps 로 맞춘다.
"""
import json, subprocess, sys, re

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
FPS = 24


def has_audio(p):
    e = subprocess.run([FF, "-hide_banner", "-i", p], capture_output=True, text=True, errors="replace").stderr
    return "Audio:" in e


def main(lst, out):
    cuts = json.load(open(lst, encoding="utf-8"))
    args, fc = [], []
    for i, c in enumerate(cuts):
        args += ["-i", c["src"]]
        d = c["out"] - c["in"]
        fc.append(f"[{i}:v]trim=start={c['in']}:end={c['out']},setpts=PTS-STARTPTS,scale=1920:1080,fps={FPS},"
                  f"format=yuv420p,settb=AVTB[v{i}]")
        if has_audio(c["src"]):
            fc.append(f"[{i}:a]atrim=start={c['in']}:end={c['out']},asetpts=PTS-STARTPTS,aresample=48000,"
                      f"aformat=channel_layouts=stereo[a{i}]")
        else:
            fc.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d:.3f}[a{i}]")
        c["d"] = d
    v, a, t = "v0", "a0", cuts[0]["d"]
    for i in range(1, len(cuts)):
        xf = cuts[i - 1].get("xf", 0) or 0
        if xf > 0:
            fc.append(f"[{v}][v{i}]xfade=transition=fade:duration={xf}:offset={t - xf:.3f}[vx{i}]")
            fc.append(f"[{a}][a{i}]acrossfade=d={xf}[ax{i}]")
            t += cuts[i]["d"] - xf
        else:
            fc.append(f"[{v}][{a}][v{i}][a{i}]concat=n=2:v=1:a=1[vx{i}][ax{i}]")
            t += cuts[i]["d"]
        v, a = f"vx{i}", f"ax{i}"
    subprocess.run([FF, "-y", "-v", "error", *args, "-filter_complex", ";".join(fc), "-map", f"[{v}]", "-map", f"[{a}]",
                    "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
    print(out, f"{t:.2f}s", len(cuts), "cuts")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
