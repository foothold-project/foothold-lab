# -*- coding: utf-8 -*-
"""엔딩 타이틀을 배경판(plate)과 글자판(type)으로 나눠 촬영한다.

원본 inbox/jay/20260903-ending-title/foothold-ending-title.html 은 고치지 않는다.
사본을 _out/ending_work/ 에 만들고 ?layer=plate|type 스위치만 덧붙인다.

  plate : 배경 캔버스 · 찢김 · 비네트만. 글자 · 선 · 푸터 숨김 → MP4 (Higgsfield 로 다시 만들 판)
  type  : 글자 · 선 · 푸터만, 배경 투명 → RGBA PNG 시퀀스 (원본 픽셀 그대로 얹을 판)

타이밍 · 로고 크기 · 위치는 원본 스크립트(shoot-ending-title.py)와 같은 1920x1080 · 30fps · 12초.

사용: python shoot_ending_layers.py plate|type
"""
import os, sys, subprocess, shutil, concurrent.futures as cf, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # inbox/jay
SRC = ROOT / "20260903-ending-title" / "foothold-ending-title.html"
WORK = ROOT / "20260930-mvp-brand" / "_out" / "ending_work"
PAGE = WORK / "ending_layers.html"
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
FFMPEG = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
FPS, DUR, W, H = 30, 12.0, 1920, 1080
N = int(round(FPS * DUR))
WORKERS = 6

INJECT = """
<style>
.L-plate .slate,.L-plate .blade,.L-plate .stamp{visibility:hidden!important}
.L-type #bg,.L-type .tear,.L-type .vig{display:none!important}
html.L-type,html.L-type body,.L-type .wrap.clean,.L-type .stage-shell,.L-type .stage{background:transparent!important}
</style>
<script>
(function(){var L=new URLSearchParams(location.search).get("layer");
if(L){document.documentElement.classList.add("L-"+L);document.getElementById("wrap").classList.add("L-"+L);}})();
</script>
"""


def build_page():
    WORK.mkdir(parents=True, exist_ok=True)
    t = SRC.read_text(encoding="utf-8")
    assert t.count("</body>") == 1
    PAGE.write_text(t.replace("</body>", INJECT + "</body>"), encoding="utf-8")


def shot(args):
    layer, i, fr = args
    t = i / FPS
    out = fr / f"f{i:04d}.png"
    url = PAGE.as_uri() + f"?shot=1&layer={layer}&t={t:.4f}"
    prof = fr / f".p{i}"
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=1", "--no-sandbox", "--mute-audio",
           "--disable-extensions", "--disable-background-networking",
           f"--user-data-dir={prof}", f"--window-size={W},{H}",
           "--virtual-time-budget=2500", f"--screenshot={out}", url]
    if layer == "type":
        cmd.insert(2, "--default-background-color=00000000")
    subprocess.run(cmd, capture_output=True, timeout=120)
    return i, out.is_file() and out.stat().st_size > 1000


def main(layer):
    build_page()
    fr = WORK / f"frames_{layer}"
    shutil.rmtree(fr, ignore_errors=True); fr.mkdir(parents=True)
    t0 = time.time(); bad = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for k, (i, ok) in enumerate(ex.map(shot, [(layer, i, fr) for i in range(N)]), 1):
            if not ok: bad.append(i)
            if k % 60 == 0: print(f"  {layer} {k}/{N}  {time.time()-t0:.0f}s", flush=True)
    for _ in range(3):
        if not bad: break
        print(f"  재촬영 {len(bad)}장", flush=True)
        with cf.ThreadPoolExecutor(3) as ex:
            bad = [i for i, ok in ex.map(shot, [(layer, i, fr) for i in bad]) if not ok]
    print(f"{layer}: 촬영 {N-len(bad)}/{N} · {time.time()-t0:.1f}초")
    if bad:
        print("실패 프레임:", bad[:10]); sys.exit(1)
    for p in fr.glob(".p*"): shutil.rmtree(p, ignore_errors=True)
    if layer == "plate":
        mp4 = WORK / "plate_src.mp4"
        subprocess.run([FFMPEG, "-y", "-v", "error", "-framerate", str(FPS), "-i", str(fr / "f%04d.png"),
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(mp4)], check=True)
        print("MP4", mp4)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
