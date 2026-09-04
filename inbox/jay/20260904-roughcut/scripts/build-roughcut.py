# -*- coding: utf-8 -*-
"""러프컷 v5. 앞을 8분음표 격자로 더 조이고 dolly 곡선을 완화 · formation 축소."""
import os, subprocess, sys
FF   = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB  = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
CINE = LAB + "/sim/eval/results/20260903-flat-army-cine"
FORM = LAB + "/sim/eval/results/20260904-flat-army-formation/flat_army_F_4096_formation.mp4"
SP   = os.path.dirname(os.path.abspath(__file__))
SEG  = os.path.join(SP,"seg7"); os.makedirs(SEG, exist_ok=True)
FPS, E, XF = 50, 30.0/144, 0.5        # 8분음표 0.20833 s = 실측 발 접지 간격 · 디졸브 0.5 s

# 길이 단위가 8분음표다. 실측 발 접지가 208 ms 이므로 컷 지점이 발걸음에 떨어진다.
CUTS = [
    ("foot",      12.30, 3, None,   "발이 지면을 딛는다"),
    ("side",       1.00, 3, None,   "옆으로 흐르는 다리들"),
    ("aisle",     13.00, 3, None,   "대군 안쪽 통로"),
    ("lead",      11.00, 4, None,   "앞모습. 얼굴"),
    ("underfoot", 15.00, 3, None,   "지면 7 cm"),
    ("orbit",     15.00, 4, "out",  "선회. 감속하며 넘긴다"),
    ("dolly",      4.00,16, "soft", "달리 아웃. 45 퍼센트 속도로 들어와 가속"),
    ("rise",      16.667,16,"out",  "수직 상승. 105 m 에서 282 m 부감까지 올라 도착한다"),
]
FORM_E, TITLE_E = 5, 44               # 대형 1.042 s · 타이틀 9.167 s

def run(c):
    r = subprocess.run(c, capture_output=True)
    if r.returncode != 0:
        print(" ".join(str(x) for x in c)[:280]); print(r.stderr[-1200:].decode("utf8","replace")); sys.exit(1)

def curve(k, D):
    if k == "out":  g = f"{D}*(1-pow(1-T/{D},2))"                  # 시작 200 퍼센트 -> 끝 0
    elif k == "soft": g = f"{D}*(0.45*(T/{D})+0.55*pow(T/{D},2))"  # 시작 45 -> 끝 155 퍼센트
    elif k == "in": g = f"{D}*pow(T/{D},2)"                        # 시작 0 -> 끝 200 (v4 에서 너무 강했다)
    else: return ""
    return f"setpts=PTS-STARTPTS,setpts='{g}/TB',"

parts=[]
for i,(n,ss,e,cv,note) in enumerate(CUTS):
    D=e*E; dst=f"{SEG}/{i:02d}_{n}.mp4"
    run([FF,"-y","-ss",str(ss),"-t",f"{D:.5f}","-i",f"{CINE}/flat_army_A_4096_{n}.mp4",
         "-vf",curve(cv,D)+f"fps={FPS},format=yuv420p","-an",
         "-c:v","libx264","-preset","medium","-crf","18",dst])
    parts.append(dst); print(f"  {i} {n:10} {D:5.3f}초 ({e}e){'  '+cv if cv else '      '}  {note}")

D=FORM_E*E; d=f"{SEG}/08_formation.mp4"
run([FF,"-y","-ss","0","-t",f"{D:.5f}","-i",FORM,
     "-vf",f"reverse,setpts=PTS-STARTPTS,setpts='{D}*(1-pow(1-T/{D},2))/TB',fps={FPS},format=yuv420p",
     "-an","-c:v","libx264","-preset","medium","-crf","18",d])
parts.append(d); print(f"  8 formation  {D:5.3f}초 ({FORM_E}e)  out    역재생. 글자로 모이며 멎는다")

lst=os.path.join(SEG,"list.txt")
open(lst,"w",encoding="utf-8").write("".join("file '"+p.replace("\\","/")+"'\n" for p in parts))
A=os.path.join(SEG,"partA.mp4")
run([FF,"-y","-f","concat","-safe","0","-i",lst,"-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p",A])
durA=(sum(c[2] for c in CUTS)+FORM_E)*E
Dt=TITLE_E*E; B=os.path.join(SEG,"partB.mp4")
run([FF,"-y","-t",f"{Dt:.5f}","-i",f"{SP}/foothold-ending-title.mp4",
     "-vf",f"fps={FPS},format=yuv420p","-an","-c:v","libx264","-preset","medium","-crf","18",B])
out=os.path.join(SP,"foothold-roughcut.mp4")
run([FF,"-y","-i",A,"-i",B,"-filter_complex",
     f"[0:v][1:v]xfade=transition=fade:duration={XF}:offset={durA-XF:.5f},format=yuv420p[v]",
     "-map","[v]","-c:v","libx264","-preset","slow","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",out])
print(f"\n러프컷 v5  {durA+Dt-XF:.2f}초 · {os.path.getsize(out)/1e6:.1f} MB")
print(f"  앞 6컷 {sum(c[2] for c in CUTS[:6])*E:.3f}초 (v4 5.833 / v3 8.33)")
print(f"  formation {FORM_E*E:.3f}초 (v4 2.500)")
