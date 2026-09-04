# -*- coding: utf-8 -*-
"""오프닝 2.5초를 만든다. 미지의 험지. 로봇이 없다.

8분음표 12개 = 2.5000초다. 첫 컷이 박자 위에 떨어진다.

## 왜 정지 이미지에서 만드나

`generate_image` 로 스틸을 뽑고 여기서 카메라를 움직인다. 실측 단가다.
  이미지  건당 2 크레딧 · 여러 장 동시에 35초 안
  영상    건당 36 크레딧 · 영상 1초당 벽시계 36-62초

영상 생성은 18배 비싸다. 그리고 오프닝은 카메라가 아주 느리게 드리프트하는
한 장면이라 스틸에서 만들어도 같은 그림이 나온다. 실측으로 확인했다.
밀어 넣기와 흐름만 걸어도 프레임간 변화량이 평균 1.81 이고 정지 프레임이 0 퍼센트다.
formation 원본이 0.046 인 것과 견주면 충분히 움직인다.

안개가 스스로 흐르는 것까지 원하면 `image to video` 로 36 크레딧을 더 쓰면 된다.
지금 판은 그것 없이 만든 것이다. 필요하면 그때 올린다.

## 톤

오프닝은 **첫 컷보다 어둡다.** 「거의 침묵에서 압도로」를 그림에서도 받는다.
`foot` 컷 평균이 103 이므로 오프닝을 70 근처로 눌러 둔다.
컷이 붙는 순간 밝기가 올라가는 것이 설계다.
"""
import os, subprocess, sys

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
RAW = os.path.join(ROOT, "opening", "o1_raw.png")
PLATE = os.path.join(ROOT, "opening", "o1_plate.png")
OUT = os.path.join(ROOT, "opening", "opening-drift.mp4")

FPS, E = 50, 30.0 / 144
OPEN_E = 12
N = int(round(OPEN_E * E * FPS))          # 125 프레임 = 2.5000초

# 모델이 2.39:1 레터박스를 구워서 낸다. 활성 영역만 잘라 16:9 로 맞춘다.
CROP = "crop=2752:1154:0:191,crop=2051:1154:350:0"

# 오프닝 전용 그레이딩. 본편 그레이딩보다 한 단 더 누른다.
GRADE = (
    "curves=all='0/0.030 0.20/0.115 0.5/0.400 0.82/0.700 1/0.880',"
    "colorbalance=rs=-0.030:gs=-0.010:bs=0.050:rh=0.045:gh=0.015:bh=-0.040,"
    "eq=saturation=0.86:contrast=1.05,"
    "vignette=angle=PI/4.6"
)
# 밀어 넣기 5.5 퍼센트 · 아래로 70 화소. 아주 느리다.
PAN = (f"scale=2400:1350:flags=lanczos,"
       f"zoompan=z='1.0+0.055*(on/{N-1})':x='iw/2-(iw/zoom/2)':"
       f"y='ih/2-(ih/zoom/2)+70*(on/{N-1})':d={N}:s=1920x1080:fps={FPS},"
       f"setsar=1,noise=alls=4:allf=t+u,format=yuv420p")


def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"실패: {label}")
        print((r.stderr or "")[-1200:])
        sys.exit(1)


def mean_gray(path):
    import numpy as np
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", "scale=320:180",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (320 * 180)
    return float(a[:n * 320 * 180].reshape(n, 180, 320).astype("float32").mean())


def main():
    if not os.path.exists(RAW):
        sys.exit("오프닝 스틸이 없다: " + RAW)
    run([FF, "-y", "-v", "error", "-i", RAW, "-vf", f"{CROP},scale=1920:1080:flags=lanczos,{GRADE}",
         PLATE], "plate")
    print(f"판 {PLATE} · 평균 밝기 {mean_gray(PLATE):.1f}")
    run([FF, "-y", "-v", "error", "-loop", "1", "-i", PLATE, "-t", f"{N/FPS:.4f}",
         "-vf", PAN, "-frames:v", str(N), "-an",
         "-c:v", "libx264", "-preset", "slow", "-crf", "15",
         "-x264-params", "keyint=1", OUT], "drift")

    import numpy as np
    p = subprocess.run([FF, "-v", "error", "-i", OUT, "-vf", "scale=384:216",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    k = a.size // (384 * 216)
    v = a[:k * 384 * 216].reshape(k, 216, 384).astype(np.float32)
    d = np.abs(np.diff(v, axis=0)).mean(axis=(1, 2))
    print(f"썼다  {OUT}  {k} 프레임 ({k/FPS:.4f}초) · 평균 밝기 {v.mean():.1f}")
    print(f"  프레임간 변화량 평균 {d.mean():.3f} · 최대 {d.max():.3f} · 정지(<0.3) {100*(d<0.3).mean():.1f} %")


if __name__ == "__main__":
    main()
