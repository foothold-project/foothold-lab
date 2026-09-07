# -*- coding: utf-8 -*-
"""물질화 · 탈물질화 전환을 합성으로 만든다. 아이언맨 수트업 방식이다.

생성이 아니라 합성인 이유. 우리는 같은 시뮬레이션 프레임의 원본과 변환본을 둘 다 갖는다.
두 층을 마스크로 섞으면 세계만 바뀐다. 생성 모델에 맡기면 로봇을 다시 그려
효과의 핵심이 깨진다.

다만 실측해 보니 **seedance 도 gemini 도 로봇을 픽셀 단위로 지키지 않는다.**
배치 상관이 seedance foot +0.002 · lead +0.011 · dolly +0.119, gemini dolly +0.177 이다.
그래서 이 스크립트의 목적은 「어긋남이 경계 잡음에 묻히는가」를 눈으로 확인하는 것이다.
경계가 잡음으로 흐트러지고 입자가 앞서 나가고 0.3-0.5초에 지나가면
로봇이 조금 어긋나는 것이 결함이 아니라 「재조립되는 중」으로 읽힐 수 있다.

쓰는 법
  python scripts/materialize.py <원본mp4> <변환본mp4> <출력mp4> <길이초> [up|down]
"""
import os, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
W, H, FPS = 1920, 1080, 50
TEAL = np.array([0x3e, 0xc7, 0xb4], np.float32)     # 브랜드 티얼. 아주 얇게만 쓴다


def frames(path, n=None):
    vf = f"scale={W}:{H},fps={FPS}"
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", vf,
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    k = a.size // (W * H * 3)
    v = a[:k * W * H * 3].reshape(k, H, W, 3)
    if n and k < n:
        v = np.concatenate([v, np.repeat(v[-1:], n - k, axis=0)])
    return v[:n] if n else v


def smooth_noise(h, w, scale, rng):
    """저해상도 잡음을 키워 부드러운 얼룩을 만든다. 경계를 직선으로 두지 않는다."""
    sh, sw = max(2, h // scale), max(2, w // scale)
    n = rng.random((sh, sw)).astype(np.float32)
    y = np.linspace(0, sh - 1, h)
    x = np.linspace(0, sw - 1, w)
    y0 = np.clip(y.astype(int), 0, sh - 2)
    x0 = np.clip(x.astype(int), 0, sw - 2)
    fy = (y - y0)[:, None]
    fx = (x - x0)[None, :]
    a = n[y0][:, x0]
    b = n[y0][:, x0 + 1]
    c = n[y0 + 1][:, x0]
    d = n[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy)


def build(src, sty, out, dur, direction="up", seed=4805, band=0.10, teal=0.22):
    rng = np.random.default_rng(seed)
    n = int(round(dur * FPS))
    A = frames(src, n).astype(np.float32)
    B = frames(sty, n).astype(np.float32)

    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    if direction == "up":
        coord = 1.0 - yy            # 아래에서 위로. 0(아래)에서 1(위)
    else:
        coord = yy                  # 위에서 아래로
    # 경계를 흐트러뜨릴 잡음 둘. 굵은 얼룩과 잔 얼룩을 겹친다.
    n1 = smooth_noise(H, W, 34, rng)
    n2 = smooth_noise(H, W, 9, rng)
    jitter = (n1 - 0.5) * 0.13 + (n2 - 0.5) * 0.05

    p2 = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                           "-pix_fmt", "yuv420p", "-x264-params", "keyint=1", out],
                          stdin=subprocess.PIPE)
    for k in range(n):
        p = (k + 0.5) / n
        # 경계 위치. 시작과 끝에 여유를 둬서 화면 밖에서 들어오고 나간다.
        edge = -band + p * (1.0 + 2 * band)
        d = (coord - edge + jitter) / band
        M = np.clip(0.5 - d * 0.5, 0.0, 1.0)[..., None]      # M=1 인 곳이 변환본이다

        # 알갱이가 앞서 나간다. 경계 앞쪽에 짧은 수명의 점을 흩뿌린다.
        # 입자는 경계 바로 앞에만 둔다. 넓게 뿌리면 화면 전체에 흰 점이 깔린다.
        adv = np.clip(1.0 - np.abs(d) / 1.1, 0, 1) ** 2
        spk = (rng.random((H, W)).astype(np.float32) < (adv * 0.013))
        M = np.clip(M + spk[..., None] * 0.85, 0, 1)

        out_f = A[k] * (1 - M) + B[k] * M

        # 경계 안에 밝은 선과 발광. 넓게 칠하면 촌스럽다. 아주 얇게 둔다.
        # 밝은 선은 아주 얇게. 넓게 칠하면 촌스럽다.
        line = np.exp(-(d ** 2) / 0.055)[..., None]
        out_f = out_f + line * TEAL[None, None, :] * teal
        out_f = out_f + line * 9.0                           # 흰 발광 한 겹
        out_f = out_f + spk[..., None] * TEAL[None, None, :] * 0.22

        p2.stdin.write(np.clip(out_f, 0, 255).astype(np.uint8).tobytes())
    p2.stdin.close()
    p2.wait()
    return n


if __name__ == "__main__":
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    src, sty, out, dur = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
    direction = sys.argv[5] if len(sys.argv) > 5 else "up"
    n = build(src, sty, out, dur, direction)
    print(f"썼다  {out}  {n} 프레임 ({n/FPS:.3f}초) · {direction}")
