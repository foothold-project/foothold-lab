# -*- coding: utf-8 -*-
"""엔딩 타이틀을 HTML 원본에서 다시 굽는다. 50 fps 로 굽는다.

왜 다시 굽나. 러프컷이 쓴 `foothold-ending-title.mp4` 가 저장소에 없다.
`build-roughcut.py` 가 가리키는 경로(roughcut/scripts/)에 파일이 없다.
`20260903-ending-title/` 의 판은 내용이 다르다. 그것으로 조립하니
타이틀 사건이 11.66초에서 13.92초로 밀렸다. 엔딩 사운드가 그 사건에 걸려 있다.

그래서 HTML 원본에서 직접 굽는다. `?shot=1&t=<초>` 로 한 장씩 그린다.
러프컷은 30 fps mp4 를 50 fps 로 올려 썼는데 여기서는 **처음부터 50 fps 로 굽는다.**
프레임 복제가 안 생기므로 자막 움직임이 더 매끈하다.

굽고 나면 `match-ending-offset.py` 가 지금 main 의 B 판 타이틀 구간과 맞춰
러프컷이 쓴 시작 오프셋을 실측으로 찾는다. 추측하지 않는다.

쓰는 법
  python scripts/bake-ending-title.py            전체 12초를 50 fps 로
  python scripts/bake-ending-title.py 4.0        앞 4초만 (확인용)
"""
import concurrent.futures as cf
import os, shutil, subprocess, sys, time

LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
PAGE = LAB + "/inbox/jay/20260903-ending-title/foothold-ending-title.html"
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
FR = os.path.join(ROOT, "worka", "title-frames")
OUT = os.path.join(ROOT, "worka", "ending-title-50.mp4")

FPS, W, H = 50, 1920, 1080
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
WORKERS = 6


def shot(i):
    t = i / FPS
    out = os.path.join(FR, f"f{i:05d}.png")
    url = "file:///" + PAGE.replace("\\", "/") + f"?shot=1&t={t:.4f}"
    prof = os.path.join(FR, f".p{i % WORKERS}")
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=1", "--no-sandbox", "--mute-audio",
           "--disable-extensions", "--disable-background-networking",
           f"--user-data-dir={prof}", f"--window-size={W},{H}",
           "--virtual-time-budget=2500", f"--screenshot={out}", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return i, False, "timeout"
    ok = os.path.isfile(out) and os.path.getsize(out) > 2000
    return i, ok, ("" if ok else (r.stderr[-160:].decode("utf8", "replace")))


def main():
    n = int(round(FPS * DUR))
    shutil.rmtree(FR, ignore_errors=True)
    os.makedirs(FR, exist_ok=True)
    print(f"엔딩 타이틀 {DUR:.2f}초 · {FPS} fps · {n} 프레임 · 작업자 {WORKERS}")
    t0 = time.time()
    bad = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for k, (i, ok, err) in enumerate(ex.map(shot, range(n)), 1):
            if not ok:
                bad.append((i, err))
            if k % 50 == 0:
                el = time.time() - t0
                print(f"  {k}/{n}  {el:.0f}초  (남은 예상 {el/k*(n-k):.0f}초)", flush=True)
    el = time.time() - t0
    print(f"촬영 {n-len(bad)}/{n} · {el:.1f}초 · 프레임당 {el/max(n,1):.2f}초")
    # 실패한 것만 하나씩 다시 찍는다. 프로필 디렉터리를 여럿이 함께 쓰다 가끔 어긋난다.
    for attempt in range(3):
        if not bad:
            break
        retry = [i for i, _ in bad]
        print(f"  다시 찍는다 {len(retry)}장 (시도 {attempt+1})")
        bad = []
        for i in retry:
            j, ok, err = shot(i)
            if not ok:
                bad.append((j, err))
    if bad:
        print("끝내 실패:", bad[:5])
        sys.exit(1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    r = subprocess.run([FF, "-y", "-v", "error", "-framerate", str(FPS),
                        "-i", os.path.join(FR, "f%05d.png"),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                        "-pix_fmt", "yuv420p", "-x264-params", "keyint=1",
                        "-movflags", "+faststart", OUT], capture_output=True)
    if r.returncode != 0:
        print(r.stderr[-900:].decode("utf8", "replace"))
        sys.exit(1)
    print(f"썼다  {OUT}  {os.path.getsize(OUT)/1e6:.2f} MB · {n} 프레임 · {FPS} fps")


if __name__ == "__main__":
    main()
