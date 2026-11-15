# -*- coding: utf-8 -*-
"""MuJoCo clip block for the RoboGauge section (lead 10/13 16:50). Reads rg_videos.json (every-frame check passed), makes a
poster per web copy (frame at 10 %), and writes the block between the RG-VIDEOS markers in v5_rg.html.
Clip choice is the run script's (robogauge/run_video_queue.sh 3-5): friction 0.6 · seed 0 · each terrain at the reference
policy's highest passed level at friction 0.6, for both policies; plus E1 20,000 at its own highest passed level where lower."""
import io
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SP = "C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/09bbf294-fda0-4c7b-81c5-e23f793f2be2/scratchpad/e12page"
R = json.load(open(os.path.join(HERE, "rg_videos.json"), encoding="utf-8"))
assert R["all_ok"] and R["selftest_ok"]
KO = {"flat": "평지 · 최고 속도", "wave": "물결", "slope_fd": "경사 앞으로", "slope_bd": "경사 뒤로",
      "stairs_fd": "계단 앞으로", "stairs_bd": "계단 뒤로", "obstacle": "장애물"}
clips = {}
for n, c in R["clips"].items():
    m = re.match(r"(e1_model_20000|ref_sym_v5\.1)__(flat|wave|slope_fd|slope_bd|stairs_fd|stairs_bd|obstacle)_(maxvel|L\d+)_F0\.6_s0\.mp4", n)
    who, ter, lv = m.groups()
    clips.setdefault(ter, []).append((who, lv, c))
os.makedirs(os.path.join(SP, "p"), exist_ok=True)
tiles = []
for ter in ("flat", "wave", "slope_fd", "slope_bd", "stairs_fd", "stairs_bd", "obstacle"):
    ref = [x for x in clips[ter] if x[0].startswith("ref")]
    e1 = [x for x in clips[ter] if x[0].startswith("e1")]
    ref_lv = ref[0][1] if ref else None
    row = []
    for who, lv, c in sorted(ref, key=lambda x: x[1]) + sorted(e1, key=lambda x: (x[1] != ref_lv, x[1])):
        web = c["web"]
        poster = "p/" + web.replace(".mp4", ".jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{0.1 * c['web_audit']['frames'] / 30.0:.2f}", "-i", os.path.join(SP, "v", web),
                        "-frames:v", "1", "-q:v", "4", os.path.join(SP, poster)], check=True)
        sec = c["web_audit"]["frames"] / 30.0
        if who.startswith("ref"):
            tag, name = '<span class="tag ref">저자</span>', "저자 정책 (sym v5.1)"
        else:
            tag, name = '<span class="tag e1">E1</span>', "E1 20,000"
        if lv == "maxvel":
            lvtxt = "최고 속도 명령"
        elif lv == ref_lv and who.startswith("ref"):
            lvtxt = f"{lv[1:]} 단계 · 저자 정책이 통과한 가장 높은 단계"
        elif lv == ref_lv:
            lvtxt = f"{lv[1:]} 단계 · 저자 정책과 같은 단계"
        else:
            lvtxt = f"{lv[1:]} 단계 · E1 이 통과한 가장 높은 단계"
        row.append(f'    <article class="tile"><div class="th">{tag}<b>{name} · {KO[ter]}</b></div>\n'
                   f'      <video controls preload="none" playsinline muted poster="{poster}"><source src="v/{web}" type="video/mp4"></video>\n'
                   f'      <div class="cap"><span class="why">{lvtxt} · 마찰 0.6 · {sec:.0f} 초</span></div></article>')
    tiles.append("\n".join(row))
block = ('<!-- RG-VIDEOS -->\n  <h3>MuJoCo 에서 걷는 모습 (RoboGauge 시험 장면)</h3>\n'
         '  <p class="sub">같은 지형 · 같은 마찰 (0.6, 시험 범위 0.2 ~ 1.0 의 가운데) · 같은 시드에서 저자 정책과 E1 20,000 을 나란히 찍었습니다. '
         '단계는 저자 정책이 마찰 0.6 에서 통과한 가장 높은 단계이고, E1 이 통과한 가장 높은 단계가 더 낮으면 그 단계도 함께 넣었습니다. '
         '영상은 시험의 한 판이며, 점수는 위 표의 여러 판 결과입니다. 19 편 모든 프레임을 검사했습니다 (검은 · 단색 프레임 0).</p>\n'
         + "\n".join(f'  <div class="urow rg">\n{t}\n  </div>' for t in tiles) + "\n<!-- /RG-VIDEOS -->\n")
p = os.path.join(HERE, "v5_rg.html")
s = io.open(p, encoding="utf-8").read()
if "<!-- RG-VIDEOS -->" in s:
    s = re.sub(r"<!-- RG-VIDEOS -->.*?<!-- /RG-VIDEOS -->\n", lambda _: block, s, flags=re.S)
else:
    i = s.rindex("</section>")
    s = s[:i] + block + s[i:]
io.open(p, "w", encoding="utf-8").write(s)
print("tiles", sum(t.count("<article") for t in tiles), "rows", len(tiles))
