# -*- coding: utf-8 -*-
import subprocess, os, shutil
FF = r"C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
SP = r"C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/85e9e940-5633-48ed-a407-2d9aafc96e93/scratchpad"
LR = SP + "/launch_render"
SB = SP + "/sb2"; RO = SP + "/rough"
IC = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260904-launch/design/isaac-cuts"
ED = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260903-ending-title/foothold-ending-title.mp4"
W = LR + "/full43_seg"; os.makedirs(W, exist_ok=True)
shutil.copyfile(r"C:/Windows/Fonts/malgun.ttf", W + "/font.ttf")
os.chdir(W)

def lab(t):
    return (f"drawbox=x=0:y=0:w=iw:h=46:color=black@0.42:t=fill,"
            f"drawtext=fontfile=font.ttf:text='{t}':x=22:y=13:fontsize=21:fontcolor=white@0.9:shadowx=1:shadowy=1")

# per-cut lighting tame (blown highlights -> readable silhouettes). Isaac clay is geometry-only for AI anyway.
LIGHT_FIX = {"02": "eq=brightness=-0.07:contrast=1.14:gamma=0.88:saturation=1.05",
             "04": "eq=brightness=-0.05:contrast=1.12:gamma=0.90:saturation=1.05"}
# (id, src(None=placeholder color), ss, dur, label)
SEG = [
 ("01", f"{SB}/01.mp4",                                    0.0, 2.5, "01  원경 인서트"),
 ("02", f"{LR}/cut04_far/flat_army_A_4096_horizon.mp4",   0.4, 2.8, "02  지평선 접근  (저 멀리 실루엣 / 원경사진 합성 후공정)"),
 ("03", f"{LR}/test_footplant/flat_army_A_1_footplant.mp4", 1.6, 1.8, "03  첫 발  (앵트, 발 착지 / 먼지 FX)"),
 ("04", f"{IC}/cut02_20260905-horizon45.mp4",              2.0, 1.8, "04  더 다가옴  (02보다 가까이, 아직 먼지속)"),
 ("05", f"{SB}/09.mp4",                                    0.0, 1.6, "05  행렬 내부"),
 ("06", f"{SB}/05.mp4",                                    0.3, 1.4, "06  측면 통과"),
 ("07", f"{SB}/07.mp4",                                    0.1, 1.1, "07  근접 측면"),
 ("08", f"{SB}/08.mp4",                                    0.0, 1.0, "08  통로"),
 ("09", f"{RO}/07.mp4",                                    0.36, 0.9, "09  스침"),
 ("10", f"{LR}/cut03_firststep/flat_army_A_4096_firststep2.mp4", 1.8, 1.2, "10  발밑  (앵트)"),
 ("10b", f"{LR}/cut03_footstep/flat_army_A_4096_footstep.mp4",  2.0, 1.2, "10b 발 스침  (기존 03 이동)"),
 ("11", f"{SB}/11.mp4",                                    0.0, 1.4, "11  선회  (규모)"),
 ("12", f"{SB}/12.mp4",                                    0.2, 1.8, "12  폭풍  (저 멀리서 다가옴 + 카메라 헤치고 들어감 / seedance 재연출)"),
 ("13", f"{LR}/cut13_punch/flat_army_F_4096_punch.mp4",   0.2, 1.4, "13  폭풍 통과  (seedance 재연출)"),
 ("14", f"{SB}/14.mp4",                                    0.2, 1.8, "14  일렬 행군  (seedance 1열 종대 / 본작업서 Go2로 재생성)"),
 ("15", f"{LR}/cut15_stop/flat_army_A_4096_legs.mp4",     2.8, 1.5, "15  발 멈춤 착착!  (감속 정지)"),
 ("15b", f"{LR}/cut15b_footstop/flat_army_A_4096_footstop.mp4", 2.8, 0.8, "15b 발 타이트 쿵  (seedance 재촬영: 먼지+단체 발 멈춤)"),
 ("16", f"{LR}/band_sweep/flat_army_F_4096_sweep.mp4",   0.0, 2.8, "16  끝없는 대군  (endless retreat)"),
]
# 19 ending hard-concatenated at the end (climaxrise now does the letter reveal)

def seg(sid, src, ss, dur, label, out):
    if src is None:
        cmd=[FF,"-y","-f","lavfi","-i",f"color=c=0x141210:s=1280x720:d={dur}:r=30","-vf",lab(label),
             "-c:v","libx264","-preset","veryfast","-crf","22","-pix_fmt","yuv420p","-an",out]
    else:
        lf = LIGHT_FIX.get(sid)
        vf=f"scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1,fps=30," + (lf+"," if lf else "") + lab(label)
        cmd=[FF,"-y","-ss",str(ss),"-t",str(dur),"-i",src,"-vf",vf,"-c:v","libx264","-preset","veryfast",
             "-crf","22","-pix_fmt","yuv420p","-an","-r","30",out]
    r=subprocess.run(cmd,capture_output=True,text=True,errors="replace")
    assert os.path.isfile(out), f"{sid}: "+r.stderr[-500:]
    print("ok",sid)

segfiles=[]
for sid,src,ss,dur,label in SEG:
    o=f"s{sid}.mp4"; seg(sid,src,ss,dur,label,o); segfiles.append(o)
# 17-18 reveal8k (영화적 클라이맥스 version) + 19 logo, dissolved together as a tail
seg("1718", f"{LR}/reveal8k/flat_army_F_8192_reveal8k.mp4", 0.0, 6.4, "17-18  드론 상승 -> FOOTHOLD (8192)", "s1718.mp4")
seg("19", ED, 2.6, 4.0, "19  로고", "s19.mp4")
r=subprocess.run([FF,"-y","-i","s1718.mp4","-i","s19.mp4","-filter_complex",
    "[0:v][1:v]xfade=transition=fade:duration=0.4:offset=6.0,format=yuv420p[v]",
    "-map","[v]","-c:v","libx264","-preset","veryfast","-crf","22","-pix_fmt","yuv420p","-r","30","tail.mp4"],capture_output=True,text=True,errors="replace")
print("tail xfade rc",r.returncode)
with open("list.txt","w") as f:
    for x in segfiles: f.write("file '" + x + "'\n")
    f.write("file 'tail.mp4'\n")
final=LR+"/full43_v3.mp4"
subprocess.run([FF,"-y","-f","concat","-safe","0","-i","list.txt","-c:v","libx264","-preset","slow","-crf","24","-pix_fmt","yuv420p","-movflags","+faststart",final],capture_output=True)
body_dur=sum(d for _,_,_,d,_ in SEG)+6.4+4.0-0.4
print("body_dur",round(body_dur,1),"final size",os.path.getsize(final) if os.path.isfile(final) else "FAIL")
