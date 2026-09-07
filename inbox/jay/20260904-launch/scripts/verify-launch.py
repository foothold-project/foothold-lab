# -*- coding: utf-8 -*-
"""완성본을 검사한다. 주장하는 것을 전부 다시 잰다.

  1 스트림 구성. 오디오 트랙이 실제로 붙었는지
  2 길이와 프레임 수가 러프컷과 같은지
  3 컷별 평균 밝기가 목표대로 하강하는지
  4 formation 과 타이틀이 러프컷과 같은 화면인지 (PSNR)
  5 사운드 라우드니스와 피크
  6 발 접지 208 ms 격자가 소리에 남아 있는지

ffprobe 가 이 환경에 없다. ffmpeg 의 스트림 표시를 읽는다.
"""
import ast, json, os, re, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
RC = LAB + "/inbox/jay/20260904-roughcut/foothold-roughcut.mp4"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "foothold-launch.mp4")
FPS, E = 50, 30.0 / 144
TARGET = {"foot": 126.9, "side": 130.7, "aisle": 118.4, "lead": 155.0,
          "underfoot": 153.8, "orbit": 104.5, "dolly": 63.0, "rise": 51.1}
ok_all = True


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stderr or ""


def check(cond, msg):
    global ok_all
    if not cond:
        ok_all = False
    print(f"  {'통과' if cond else '실패'}  {msg}")
    return cond


def gray(path, w=320, h=180, extra=""):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}{extra}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (w * h)
    return a[:n * w * h].reshape(n, h, w).astype(np.float32)


print("=" * 74)
print("1. 스트림 구성")
info = sh([FF, "-hide_banner", "-i", OUT])
for line in info.splitlines():
    if "Stream #" in line or "Duration" in line:
        print("   " + line.strip())
has_v = "Video:" in info
has_a = "Audio:" in info
check(has_v, "비디오 트랙이 있다")
check(has_a, "오디오 트랙이 있다")
m = re.search(r"Audio: (\w+).*?(\d+) Hz, (\w+)", info)
if m:
    print(f"   오디오 {m.group(1)} · {m.group(2)} Hz · {m.group(3)}")
    check(m.group(2) == "48000", "오디오가 48000 Hz 다")
    check(m.group(3) == "stereo", "오디오가 스테레오다")
check("1920x1080" in info, "해상도가 1920x1080 이다")
check("50 fps" in info, "50 fps 다")

print("\n2. 길이")
v = gray(OUT, 64, 36)
rcv = gray(RC, 64, 36)
print(f"   완성본 {len(v)} 프레임 = {len(v)/FPS:.4f}초")
print(f"   러프컷 {len(rcv)} 프레임 = {len(rcv)/FPS:.4f}초")
check(len(v) == len(rcv), "러프컷과 프레임 수가 같다")
dm = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
dur = int(dm.group(1)) * 3600 + int(dm.group(2)) * 60 + float(dm.group(3))
check(abs(dur - len(v) / FPS) < 0.06, f"컨테이너 길이 {dur:.3f}초가 프레임 수와 맞는다")

print("\n3. 컷별 평균 밝기 · 하강하는 모양을 지켰는지")
cuts = ast.literal_eval(re.search(r"^CUTS\s*=\s*(\[.*?^\])",
                                  open(BUILD, encoding="utf-8").read(), re.S | re.M).group(1))
f = re.search(r"^FORM_E,\s*TITLE_E\s*=\s*(\d+),\s*(\d+)",
              open(BUILD, encoding="utf-8").read(), re.M)
FORM_E = int(f.group(1))
edges, acc = [0], 0.0
for c in cuts:
    acc += c[2] * E
    edges.append(int(np.floor(acc * FPS + 0.5)))
big = gray(OUT)
print(f"   {'컷':<11}{'목표':>7}{'실측':>7}{'차이':>7}")
vals = []
for i, c in enumerate(cuts):
    nm = c[0]
    a, z = edges[i], edges[i + 1]
    got = float(big[a + 1:z - 1].mean()) if z - a > 3 else float(big[a:z].mean())
    vals.append(got)
    d = got - TARGET[nm]
    print(f"   {nm:<11}{TARGET[nm]:7.1f}{got:7.1f}{d:+7.1f}{'' if abs(d) < 3 else '   벗어난다'}")
fa = edges[-1]
fz = fa + int(round(FORM_E * E * FPS))
form_b = float(big[fa + 1:fz - 1].mean())
title_b = float(big[fz + 5:].mean())
print(f"   {'formation':<11}{'':>7}{form_b:7.1f}   원본 그대로")
print(f"   {'타이틀':<11}{'':>7}{title_b:7.1f}   원본 그대로")
check(max(abs(v - TARGET[c[0]]) for v, c in zip(vals, cuts)) < 3.0,
      "여덟 컷 모두 목표 밝기에서 3 이내다")
check(vals[3] > vals[5] > vals[6] > vals[7] > form_b > title_b,
      f"lead {vals[3]:.0f} > orbit {vals[5]:.0f} > dolly {vals[6]:.0f} > "
      f"rise {vals[7]:.0f} > formation {form_b:.0f} > 타이틀 {title_b:.0f} 로 하강한다")

print("\n4. formation 과 타이틀이 러프컷과 같은 화면인지")
tailstart = edges[-1]
r = sh([FF, "-hide_banner", "-i", OUT, "-i", RC, "-lavfi",
        f"[0:v]trim=start_frame={tailstart},setpts=PTS-STARTPTS[a];"
        f"[1:v]trim=start_frame={tailstart},setpts=PTS-STARTPTS[b];[a][b]psnr", "-f", "null", "-"])
pm = re.search(r"PSNR y:([\d.]+|inf).*?average:([\d.]+|inf)", r)
if pm:
    y = pm.group(1)
    print(f"   뒤 구간 PSNR y:{y} average:{pm.group(2)}")
    val = float("inf") if y == "inf" else float(y)
    check(val > 40, f"뒤 구간이 러프컷과 같다 (PSNR y {y} dB, 40 이상이면 재인코딩 잡음 수준)")
else:
    check(False, "PSNR 을 못 읽었다")

print("\n5. 사운드 라우드니스와 피크")
r = sh([FF, "-hide_banner", "-i", OUT, "-filter:a", "ebur128=peak=true", "-f", "null", "-"])
im = re.findall(r"I:\s*(-?[\d.]+) LUFS", r)
pk = re.findall(r"Peak:\s*(-?[\d.]+) dBFS", r)
lra = re.findall(r"LRA:\s*([\d.]+) LU", r)
if im and pk:
    I, P = float(im[-1]), float(pk[-1])
    print(f"   적분 라우드니스 {I:.1f} LUFS · 트루 피크 {P:.1f} dBFS · LRA {lra[-1] if lra else '?'} LU")
    check(P <= -1.0, f"트루 피크 {P:.1f} dBFS 가 -1 dBFS 를 넘지 않는다")
    check(-18.0 <= I <= -13.0, f"라우드니스 {I:.1f} LUFS 가 -16 근처다")
else:
    check(False, "라우드니스를 못 읽었다")

print("\n6. 발 접지 격자가 소리에 남아 있는지")
p = subprocess.run([FF, "-v", "error", "-i", OUT, "-map", "0:a:0", "-ac", "1",
                    "-ar", "48000", "-f", "f32le", "-"], capture_output=True)
a = np.frombuffer(p.stdout, np.float32)
if a.size > 48000:
    X = np.fft.rfft(a)
    fr = np.fft.rfftfreq(len(a), 1 / 48000)
    X[fr > 90] = 0
    env = np.abs(np.fft.irfft(X, len(a)))
    k = 480
    e = env[:len(env) // k * k].reshape(-1, k).mean(axis=1)
    e -= e.mean()
    seg = e[:int(10.84 * 100)]
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 4096))
    ff = np.fft.rfftfreq(4096, 1 / 100)
    msk = (ff > 1) & (ff < 12)
    top = ff[msk][int(np.argmax(S[msk]))]
    print(f"   걷는 구간 저역 포락선 지배 주파수 {top:.3f} Hz -> 간격 {1000/top:.1f} ms")
    print(f"   영상에서 잰 값 4.805 Hz · 208 ms")
    check(abs(top - 4.8) < 0.15, f"{top:.3f} Hz 가 실측 4.805 Hz 와 맞는다")
    # 우쉬 두 곳에 고역이 실제로 있는지
    Y = np.fft.rfft(a)
    fr2 = np.fft.rfftfreq(len(a), 1 / 48000)
    Y[(fr2 < 1500)] = 0
    hi = np.abs(np.fft.irfft(Y, len(a)))
    hk = 4800
    h = hi[:len(hi) // hk * hk].reshape(-1, hk).mean(axis=1)   # 0.1초 단위
    for at, nm in [(4.167, "dolly 진입"), (7.500, "rise 진입")]:
        i = int(at * 10)
        near = h[max(0, i - 4):i + 4].max()
        base = np.median(h[:int(10.8 * 10)])
        print(f"   {nm} {at:.3f}초 고역 봉우리 {near/max(base,1e-9):.1f} 배")
        check(near / max(base, 1e-9) > 1.8, f"{nm}에 우쉬가 있다")
else:
    check(False, "오디오를 못 읽었다")

print("\n" + "=" * 74)
print("전부 통과" if ok_all else "실패한 항목이 있다")
sys.exit(0 if ok_all else 1)
