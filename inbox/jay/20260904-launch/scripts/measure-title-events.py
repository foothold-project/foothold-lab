# -*- coding: utf-8 -*-
"""엔딩 타이틀 구간의 사건을 프레임 단위로 잰다. 계산이 아니라 화면에서 읽는다.

러프컷이 v5 · v6 · v7 로 세 번 바뀌면서 조립 표에서 계산한 값과 실제 화면이
어긋났다. 그래서 화면에서 직접 읽는다.

  찢김      전체 프레임차 봉우리
  흰 글자   밝은 화소 수가 오르내리는 지점
  티얼      브랜드 티얼(#3ec7b4) 화소 수. 락업 심볼에만 크게 나온다
"""
import json, os, re, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
RC = _args[0] if _args else LAB + "/inbox/jay/20260904-roughcut/foothold-roughcut.mp4"
# --out <경로>  다른 파일에 쓴다. A 판은 B 판이 쓰는 title-events.json 을 덮으면 안 된다.
# --sub <초>    사건 시각에서 그만큼 뺀다. A 판은 앞에 오프닝이 붙어 있어
#               측정값이 절대 시각인데, build-sound2.py 는 본편 기준 시각에
#               오프닝을 더해 쓴다. 규약을 하나로 두려고 여기서 빼 둔다.
_OUT = None
_SUB = 0.0
if "--out" in sys.argv:
    _OUT = sys.argv[sys.argv.index("--out") + 1]
if "--sub" in sys.argv:
    _SUB = float(sys.argv[sys.argv.index("--sub") + 1])
W, H, FPS = 480, 270, 50
TEAL = np.array([0x3e, 0xc7, 0xb4])


def load(path):
    # fps 필터를 걸지 않는다. 원본이 이미 50 fps 인데 재표본화하면 마지막 프레임이 하나 떨어진다.
    # 그 한 프레임 때문에 조립 길이가 20 ms 어긋났다.
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"scale={W}:{H}",
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (W * H * 3)
    return a[:n * W * H * 3].reshape(n, H, W, 3).astype(np.int16), n


def runs(mask, fps, min_len=3):
    """참인 구간을 (시작초, 끝초) 목록으로."""
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if j - i >= min_len:
                out.append((i / fps, j / fps))
            i = j
        else:
            i += 1
    return out


def main():
    f, n = load(RC)
    t = np.arange(n) / FPS
    dur = n / FPS
    gray = f.mean(axis=3)
    d = np.abs(np.diff(gray, axis=0)).mean(axis=(1, 2))
    ink = (f.min(axis=3) > 150).sum(axis=(1, 2))
    teal = (np.abs(f - TEAL).sum(axis=3) < 150).sum(axis=(1, 2))
    print(f"러프컷 {n} 프레임 · {dur:.3f}초")

    # 타이틀 시작. 조립은 8분음표 44개를 타이틀에 쓴다.
    E = 30.0 / 144
    t_title = dur - 44 * E
    print(f"타이틀 시작 {t_title:.3f}초 (총 길이에서 8분음표 44개를 뺀 값)")

    ev = []
    # 1. 찢김 · 글리치. 타이틀 구간의 프레임차 봉우리.
    m = t[:-1] >= t_title
    seg = d[m]
    thr = seg.mean() + 2.2 * seg.std()
    for a, z in runs(d >= thr, FPS, 2):
        if a < t_title:
            continue
        i0, i1 = int(a * FPS), int(z * FPS)
        pk = i0 + int(np.argmax(d[i0:i1 + 1]))
        ev.append(("찢김", round(pk / FPS, 3), f"프레임차 {d[pk]:.2f}"))

    # 2. 흰 글자가 나타나고 사라지는 지점
    big = ink > 300
    for a, z in runs(big, FPS, 5):
        if z < t_title:
            continue
        ev.append(("흰글자 등장", round(a, 3), f"{ink[int(a*FPS)+2]} 화소"))
        ev.append(("흰글자 소멸", round(z, 3), "절단 후보"))

    # 3. 티얼이 올라오는 지점. 마지막 것이 락업이다.
    fin = float(np.median(teal[-int(0.6 * FPS):]))
    on = teal > fin * 0.30
    for a, z in runs(on, FPS, 8):
        if z < t_title:
            continue
        lab = "락업 착지" if z >= dur - 0.1 else "티얼 등장"
        ev.append((lab, round(a, 3), f"최종 {fin:.0f} 화소 대비 {teal[int(a*FPS)+4]/fin*100:.0f} 퍼센트"))

    ev.sort(key=lambda x: x[1])
    print(f"\n  {'시각':>8}  {'무엇':<14} 근거")
    for nm, tt, why in ev:
        print(f"  {tt:8.3f}  {nm:<14} {why}")

    spec = {"roughcut": os.path.basename(RC), "frames": n, "duration": round(dur, 4),
            "title_start": round(t_title - _SUB, 4), "subtracted_s": _SUB,
            "events": [{"t": round(tt - _SUB, 3), "what": nm, "why": why}
                       for nm, tt, why in ev if tt - _SUB > 0]}
    out = _OUT or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "..", "sound", "title-events.json"))
    out = os.path.normpath(out if os.path.isabs(out) else
                           os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", out))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(spec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n{out} 썼다")


if __name__ == "__main__":
    main()
