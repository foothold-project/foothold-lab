# -*- coding: utf-8 -*-
"""러프컷 v4. 앞부분 더 조이고 · formation 짧게 · 타이틀로 디졸브."""
import os, subprocess, sys, json
FF   = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB  = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
CINE = LAB + "/sim/eval/results/20260903-flat-army-cine"
FORM = r"C:/Users/AI-WS01/orca/workspaces/foothold-lab/army-cine/sim/eval/results/20260904-flat-army-formation/flat_army_F_4096_formation.mp4"
SP   = os.path.dirname(os.path.abspath(__file__))
SEG  = os.path.join(SP, "seg4"); os.makedirs(SEG, exist_ok=True)
FPS, Q, XF = 50, 60.0/144, 0.5      # 4분음표 0.41667 s · 디졸브 0.5 s

# foot 은 12.3 초로 옮겼다. 16 초에 다리가 화면 중앙으로 치고 들어오는 것을 피한다.
CUTS = [
    ("foot",      12.30, 2, None,  "발이 지면을 딛는다"),
    ("side",       1.00, 2, None,  "옆으로 흐르는 다리들"),
    ("aisle",     13.00, 2, None,  "대군 안쪽 통로"),
    ("lead",      11.00, 3, None,  "앞모습. 얼굴"),
    ("underfoot", 15.00, 2, None,  "지면 7 cm"),
    ("orbit",     15.00, 3, "out", "선회. 감속하며 다음 컷에 넘긴다"),
    ("dolly",      4.00, 8, "in",  "달리 아웃. 감속을 받아 가속한다"),
    ("rise",      13.50, 6, "out", "수직 상승. 빠르게 들어와 멎는다"),
]
FORM_Q, TITLE_Q = 6, 22             # 대형 2.5 s · 타이틀 9.167 s

def run(c):
    r = subprocess.run(c, capture_output=True)
    if r.returncode != 0:
        print(" ".join(str(x) for x in c)[:280]); print(r.stderr[-1200:].decode("utf8","replace")); sys.exit(1)

def curve(k, D):
    if k == "in":  g = f"{D}*pow(T/{D},2)"
    elif k == "out": g = f"{D}*(1-pow(1-T/{D},2))"
    else: return ""
    return f"setpts=PTS-STARTPTS,setpts='{g}/TB',"

parts = []
for i,(n, ss, q, cv, note) in enumerate(CUTS):
    D = q*Q; dst = f"{SEG}/{i:02d}_{n}.mp4"
    run([FF,"-y","-ss",str(ss),"-t",f"{D:.5f}","-i",f"{CINE}/flat_army_A_4096_{n}.mp4",
         "-vf",curve(cv,D)+f"fps={FPS},format=yuv420p","-an",
         "-c:v","libx264","-preset","medium","-crf","18",dst])
    parts.append(dst)
    print(f"  {i} {n:10} {D:5.3f}초 ({q}q){'  '+cv if cv else '    '}  {note}")

D = FORM_Q*Q; d = f"{SEG}/08_formation.mp4"
run([FF,"-y","-ss","0","-t",f"{D:.5f}","-i",FORM,
     "-vf",f"reverse,setpts=PTS-STARTPTS,setpts='{D}*(1-pow(1-T/{D},2))/TB',fps={FPS},format=yuv420p",
     "-an","-c:v","libx264","-preset","medium","-crf","18",d])
parts.append(d); print(f"  8 formation  {D:5.3f}초 ({FORM_Q}q)  out   역재생. 글자로 모이며 멎는다")

lst = os.path.join(SEG,"list.txt")
open(lst,"w",encoding="utf-8").write("".join("file '"+p.replace("\\","/")+"'\n" for p in parts))
A = os.path.join(SEG,"partA.mp4")
run([FF,"-y","-f","concat","-safe","0","-i",lst,"-c:v","libx264","-preset","medium","-crf","18",
     "-pix_fmt","yuv420p",A])
durA = (sum(c[2] for c in CUTS)+FORM_Q)*Q

Dt = TITLE_Q*Q; B = os.path.join(SEG,"partB.mp4")
run([FF,"-y","-t",f"{Dt:.5f}","-i",f"{SP}/foothold-ending-title.mp4",
     "-vf",f"fps={FPS},format=yuv420p","-an","-c:v","libx264","-preset","medium","-crf","18",B])

# 디졸브: 로봇 글자가 정본 워드마크로 채워진다
out = os.path.join(SP,"foothold-roughcut.mp4")
off = durA - XF
run([FF,"-y","-i",A,"-i",B,
     "-filter_complex",f"[0:v][1:v]xfade=transition=fade:duration={XF}:offset={off:.5f},format=yuv420p[v]",
     "-map","[v]","-c:v","libx264","-preset","slow","-crf","18",
     "-pix_fmt","yuv420p","-movflags","+faststart",out])
tot = durA + Dt - XF
print(f"\n러프컷 v4  {len(parts)+1}컷 · {tot:.2f}초 · {os.path.getsize(out)/1e6:.1f} MB")
print(f"  앞 6컷 {sum(c[2] for c in CUTS[:6])*Q:.2f}초 (v3 8.33 / v2 16.5)")
print(f"  formation {FORM_Q*Q:.2f}초 (v3 5.00)  ·  디졸브 {XF}초로 타이틀 연결")
