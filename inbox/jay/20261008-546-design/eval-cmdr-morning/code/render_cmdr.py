"""Render the page's #cmdr section at 1920 / 1366 / 390 wide, light and dark, and crop it (lead 10/13, page v17 check)."""
import io
import os
import re
import subprocess
import sys

from PIL import Image

SP = "C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/09bbf294-fda0-4c7b-81c5-e23f793f2be2/scratchpad"
T = "C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/e12page/shots5"
CH = "C:/Program Files/Google/Chrome/Application/chrome.exe"
SEC = sys.argv[1] if len(sys.argv) > 1 else "cmdr"
src = os.path.join(SP, "e12page", "index.html")
probe = os.path.join(SP, "e12page", "_probe.html")
s = io.open(src, encoding="utf-8").read()
js = ("<script>window.addEventListener('load',()=>setTimeout(()=>{const e=document.getElementById('%s');const r=e.getBoundingClientRect();"
      "const p=document.createElement('pre');p.id='pos';p.textContent=JSON.stringify([Math.round(r.top+scrollY),Math.round(r.height),"
      "document.documentElement.scrollWidth]);document.body.appendChild(p)},1500));</script>") % SEC
io.open(probe, "w", encoding="utf-8").write(s.replace("</body>", js + "</body>"))
os.makedirs(T, exist_ok=True)
for w in (1920, 1366, 390):
    dom = subprocess.run([CH, "--headless=new", "--disable-gpu", f"--window-size={w},1080", "--virtual-time-budget=6000", "--dump-dom",
                          "file:///" + probe], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    m = re.search(r'<pre id="pos">\[(\d+),(\d+),(\d+)\]', dom)
    top, hgt, sw = map(int, m.groups())
    H = min(top + hgt + 40, 30000)
    for scheme, name in ((1, "light"), (0, "dark")):
        out = os.path.join(T, f"v17_{SEC}_{w}_{name}.png")
        subprocess.run([CH, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--blink-settings=preferredColorScheme={scheme}",
                        f"--window-size={w},{H}", "--virtual-time-budget=8000", f"--screenshot={out}", "file:///" + src], capture_output=True)
        im = Image.open(out)
        crop = im.crop((0, top, w, min(top + hgt, im.size[1])))
        crop.save(out)
        print(w, name, "section top", top, "height", hgt, "page scrollWidth", sw, "saved", crop.size)
os.remove(probe)
