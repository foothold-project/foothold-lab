# -*- coding: utf-8 -*-
"""러프컷 엔딩의 두 지점을 직접 잰다. 판이 바뀌면 다시 돌린다.
  절단 순간   FIND THE NEXT STEP 흰 글자가 잘려 사라지는 프레임
  락업 착지   스택 락업의 티얼 심볼이 마지막으로 올라와 끝까지 남는 프레임
"""
import subprocess, numpy as np, sys
FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
RC = sys.argv[1] if len(sys.argv) > 1 else \
     r"C:/Users/AI-WS01/orca/workspaces/foothold-lab/roughcut/inbox/jay/20260904-roughcut/foothold-roughcut.mp4"
W, H, FPS = 480, 270, 50
p = subprocess.run([FF,"-v","error","-i",RC,"-vf",f"scale={W}:{H},fps={FPS}",
                    "-pix_fmt","rgb24","-f","rawvideo","-"], capture_output=True)
a = np.frombuffer(p.stdout, np.uint8)
n = a.size // (W*H*3)
f = a[:n*W*H*3].reshape(n,H,W,3).astype(np.int16)
t = np.arange(n)/FPS
print(f"러프컷 {n} 프레임 · {n/FPS:.3f}초")

TEAL = np.array([0x3e,0xc7,0xb4])
teal = (np.abs(f-TEAL).sum(axis=3) < 150).sum(axis=(1,2))
ink  = (f.min(axis=3) > 150).sum(axis=(1,2))

# 락업: 마지막 프레임의 티얼 수준이 락업 수준이다. 그 수준에 올라 끝까지 남는 첫 프레임.
fin = np.median(teal[-int(0.6*FPS):])
hold = int(1.2*FPS)
lock = None
for i in range(n-1, 0, -1):
    if teal[i] < fin*0.55:
        lock = t[i+1]; break
print(f"\n락업 착지")
print(f"  마지막 구간 티얼 {fin:.0f} 화소")
print(f"  그 수준에 올라 끝까지 남는 첫 시각 {lock:.3f}초")
i0 = int(lock*FPS)
print("  전후 프레임:", " ".join(f"{teal[k]}" for k in range(max(0,i0-4), min(n,i0+6))))

# 절단: 락업 전에 흰 글자가 안정적으로 있다가 사라지는 마지막 지점
pre = teal[:i0]
# 흰 글자가 400 화소 넘게 유지되던 구간의 끝
big = ink[:i0] > 300
if big.any():
    last = np.where(big)[0][-1]
    lvl = np.median(ink[max(0,last-int(1.2*FPS)):last])
    cut = t[last+1]
    print(f"\n절단 순간")
    print(f"  흰 글자 기준 {lvl:.0f} 화소")
    print(f"  마지막으로 사라지는 시각 {cut:.3f}초")
    print("  전후 프레임:", " ".join(f"{ink[k]}" for k in range(max(0,last-4), min(n,last+6))))
else:
    print("\n절단 순간: 흰 글자 구간을 못 찾았다")

print(f"\n요약  절단 {cut:.3f}초 · 락업 {lock:.3f}초 · 총 {n/FPS:.3f}초")
