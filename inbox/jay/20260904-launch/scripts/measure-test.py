# -*- coding: utf-8 -*-
"""시험 변환 두 개를 원본과 견준다. 컷 경계가 제자리에 있는지 · 밝기가 어떻게 바뀌었는지."""
import subprocess, numpy as np, sys
FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
D = r"C:/Users/AI-WS01/orca/workspaces/foothold-lab/hf-launch/inbox/jay/20260904-launch/test"
W, H = 320, 180
# 앞 4초에 들어 있는 컷 경계. 러프컷 구성 그대로다.
BOUND = [0.625, 1.250, 1.875, 2.708, 3.333]
NAMES = [("foot",0,.625),("side",.625,1.25),("aisle",1.25,1.875),
         ("lead",1.875,2.708),("underfoot",2.708,3.333),("orbit",3.333,4.0)]

def load(path, fps):
    p = subprocess.run([FF,"-v","error","-i",path,"-vf",f"scale={W}:{H},fps={fps}",
                        "-pix_fmt","gray","-f","rawvideo","-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (W*H)
    return a[:n*W*H].reshape(n,H,W).astype(np.float32), n

for tag, path, fps in [("원본", f"{D}/src-00-04.mp4", 50),
                       ("seedance_2_5", f"{D}/hf-seedance25.mp4", 24),
                       ("gemini_1_1", f"{D}/hf-gemini11.mp4", 24)]:
    f, n = load(path, fps)
    dur = n/fps
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1,2))
    b = f.mean(axis=(1,2))
    print(f"\n=== {tag} · {n} 프레임 · {dur:.3f}초 · {fps} fps ===")
    print(f"  전체 평균 밝기 {b.mean():6.1f}")
    # 컷 경계 검출: 프레임차 봉우리
    thr = d.mean() + 3.0*d.std()
    pk = [i for i in range(1, len(d)-1) if d[i] > thr and d[i] >= d[i-1] and d[i] >= d[i+1]]
    # 붙은 봉우리 합치기
    merged = []
    for i in pk:
        if merged and i - merged[-1] < int(0.10*fps): continue
        merged.append(i)
    det = [round(i/fps, 3) for i in merged]
    print(f"  검출된 컷 경계 {det}")
    print(f"  기대값(원본 구성) {BOUND}")
    if tag != "원본":
        sc = dur/4.0
        print(f"  길이비 {sc:.4f}. 이 비로 되돌린 경계 {[round(x/sc,3) for x in det]}")
    print("  컷별 평균 밝기")
    for nm, a0, z0 in NAMES:
        s = slice(int(a0*fps*dur/4.0)+1, int(z0*fps*dur/4.0)-1)
        v = b[s]
        print(f"    {nm:10} {v.mean():6.1f}" if len(v) else f"    {nm:10}   표본없음")
