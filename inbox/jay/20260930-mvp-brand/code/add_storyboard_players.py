# -*- coding: utf-8 -*-
"""스토리보드 A.html 의 컷 썸네일을 누르면 그 컷의 영상이 재생되게 한다.

- VIDEOS 의 컷 → 영상(스토리보드 파일 기준 상대 경로). 영상이 있는 카드에 ▶ 표시.
- EXTRA 카드(엔딩 등)를 s1718 카드 뒤에 붙인다.
- 다시 돌려도 이전에 넣은 블록을 지우고 새로 넣는다(표식 주석 사이).

사용: python add_storyboard_players.py
"""
import base64, io, json, re, subprocess, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "키비주얼 스토리보드 A.html"
FF = r"C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"
S = "_out/review/"

VIDEOS = {
    "s02": S + "tone/s02.mp4", "s03": S + "tone/s03.mp4", "s04": S + "tone/s04.mp4",
    "s10": S + "tone/s10.mp4", "s10b": S + "s10b_v1.mp4",
    "s12": S + "tone/s12.mp4", "s13": S + "tone/s13.mp4",
    "s15": S + "tone/s15.mp4", "s15b": S + "tone/s15b.mp4", "s16": S + "tone/s16.mp4",
    "s1718": S + "s1718_tail.mp4",
    # 기존 영상 (라이브러리 원본 · 프리비즈 조립 소스, 검수용 H.264 사본)
    "s01": S + "tone/s01.mp4", "s05": S + "tone/s05.mp4", "s06": S + "tone/s06.mp4",
    "s07": S + "tone/s07.mp4", "s08": S + "tone/s08.mp4", "s09": S + "tone/s09.mp4",
    "s11": S + "tone/s11.mp4", "s14": S + "tone/s14.mp4",
}
# (카드 id, 제목, 경로 표기, 영상, 썸네일 시각)
EXTRA = [
    ("s11-15", "폭풍 구간 이어보기 s11→s15", "전조 → 진입 → 더 깊이 → 치고 나옴 → 착착 · 디졸브 없음 (10/01 v3)", S + "storm_s11_s15.mp4", 20.0),
    ("s19A", "엔딩 모션그래픽 A", "Higgsfield 배경판 + 원본 로고 레이어 · 과감", S + "ending_v2A.mp4", 3.0),
    ("s19B", "엔딩 모션그래픽 B", "Higgsfield 배경판 + 원본 로고 레이어 · 절제", S + "ending_v2B.mp4", 11.0),
    ("s19C", "엔딩 C · 빛 라인 → 로고 윤곽 두르기", "s1718 대열 → B 배경 + 윤곽 광 (팀장 아이디어)", S + "s1718_tail_C.mp4", 6.8),
    ("s19D", "엔딩 D · LiDAR 스캔 리빌", "s1718 대열 → B 배경 + 청록 스캔 (제안)", S + "s1718_tail_D.mp4", 6.65),
]
FULL = (S + "FULL_v6.mp4", "전체 v6 · 10/01 · 디졸브 없음 · 폭풍: s11 3초 → s12 2.5초 → 대치 원경(해 먹힘) 2초 → s12_v2 흙에 덮임 → s13 3초부터 · s14 s15 먼지 · s17 크림")
DROP = {"s10b": "제외 (그림상 안 맞음 · 10/01)", "s14_old": ""}
B0, B1 = "<!-- players:start -->", "<!-- players:end -->"


def thumb(path, sec):
    raw = subprocess.run([FF, "-v", "error", "-ss", str(sec), "-i", str(ROOT / path), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    im = Image.open(io.BytesIO(raw)).convert("RGB").resize((640, 360))
    b = io.BytesIO(); im.save(b, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def main():
    t = HTML.read_text(encoding="utf-8")
    t = re.sub(re.escape(B0) + r".*?" + re.escape(B1), "", t, flags=re.S)
    vids = {k: v for k, v in VIDEOS.items() if (ROOT / v).exists()}
    extra = "".join(
        f'<figure class="card b" data-extra="{cid}"><img src="{thumb(v, s)}" alt="{cid}"><figcaption><b>{cid}</b> {title}'
        f'<span class="route b">{route}</span></figcaption></figure>'
        for cid, title, route, v, s in EXTRA if (ROOT / v).exists())
    for cid, *_ , v, _s in EXTRA:
        if (ROOT / v).exists(): vids[cid] = v
    block = B0 + """
<style>
figure.card.has-v{cursor:pointer;position:relative}
figure.card.drop img{filter:brightness(.35) grayscale(.6)}
figure.card.drop figcaption{opacity:.55}
figure.card .dropnote{display:block;color:#e66;font-size:12px;margin-top:4px}
figure.card.has-v::after{content:"\\25B6";position:absolute;left:10px;top:10px;width:30px;height:30px;border-radius:50%;
  background:rgba(0,0,0,.6);color:#fff;font-size:13px;line-height:30px;text-align:center;pointer-events:none}
#vp{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;align-items:center;justify-content:center;z-index:99;flex-direction:column;gap:10px}
#vp.on{display:flex}#vp video{max-width:92vw;max-height:82vh;background:#000}
#vp p{color:#ddd;font:13px sans-serif;margin:0}
</style>
<div id="vp"><video id="vpv" controls playsinline></video><p id="vpc"></p></div>
<script>
(function(){
var V=""" + json.dumps(vids, ensure_ascii=False) + """, D=""" + json.dumps(DROP, ensure_ascii=False) + """, EX=""" + json.dumps(extra, ensure_ascii=False) + """;
var g=document.querySelector('.grid'); if(!g)return;
var F=""" + json.dumps(FULL, ensure_ascii=False) + """; var h=document.querySelector('h2.sec');
if(F&&h){h.insertAdjacentHTML('beforebegin','<h2 class="sec">0. '+F[1]+'</h2><video src="'+F[0]+'" controls preload="metadata" style="width:100%;max-height:72vh;background:#000;border-radius:6px;margin:0 0 28px"></video>');}
var last=g.querySelector('img[alt="s1718"]'); if(last&&EX){last.closest('figure').insertAdjacentHTML('afterend',EX);}
g.querySelectorAll('figure.card').forEach(function(f){
  var a=f.querySelector('img').getAttribute('alt');
  if(D[a]){f.classList.add('drop');f.querySelector('figcaption').insertAdjacentHTML('beforeend','<span class="dropnote">'+D[a]+'</span>');}
  if(!V[a])return; f.classList.add('has-v');
  f.addEventListener('click',function(){var vp=document.getElementById('vp'),v=document.getElementById('vpv');
    v.src=V[a];document.getElementById('vpc').textContent=a+' · '+V[a]+'  (밖을 누르면 닫힘)';vp.classList.add('on');v.play();});
});
document.getElementById('vp').addEventListener('click',function(e){if(e.target.id==='vp'){var v=document.getElementById('vpv');v.pause();this.classList.remove('on');}});
document.addEventListener('keydown',function(e){if(e.key==='Escape')document.getElementById('vp').click();});
})();
</script>
""" + B1
    assert t.count("</body>") == 1
    t = t.replace("</body>", block + "</body>")
    HTML.write_text(t, encoding="utf-8")
    print("영상 연결:", ", ".join(sorted(vids)))
    missing = [k for k, v in VIDEOS.items() if not (ROOT / v).exists()]
    if missing: print("아직 없음:", missing)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
