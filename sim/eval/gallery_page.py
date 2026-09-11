"""갤러리 HTML 한 장. `render_gallery.py` 가 부른다.

분류: 운영
작성: 오흥재 · 2026-09-11 22:25
근거: 팀장이 컨펌한 2026-09-11 갤러리 형식
요지: mp4 를 그대로 싣고 재생기 배속으로 0.25~2배를 고르게 한다. 파일은 한 벌
상태: 확정

## 왜 따로 두나

`render_gallery.py` 는 돌리는 일, 여기는 **보이는 일**이다. 형식을 고칠 때
촬영 코드를 안 건드리게 가른다.

## 배속을 여기서 안 만든다

`<video>` 의 `playbackRate` 를 단추로 바꾼다. 파일은 한 벌이고 보는 사람이
고른다.

**다만 느리게 튼다고 새 프레임이 생기지는 않는다.** 원본이 초당 50장이라
0.25배에서는 초당 12.5장이 보인다. 그 한계를 페이지에 적어 둔다. 나중에
「왜 0.25배가 끊기느냐」를 다시 묻지 않게.
"""

from __future__ import annotations

import csv
import io
import json
import os

NL = chr(10)

CSS = """
:root{
  /* porcelain · 보고서와 같은 체계 (AGENTS.md 4-1) */
  --ink:#081F5C; --ink-2:#2a3f74; --ink-3:#41527e; --line:#d6dced;
  --bg:#f7f2eb; --card:#ffffff; --accent:#1d6b58; --warn:#8a5b12; --bad:#a8341f;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ink:#e6edfa; --ink-2:#b3c2de; --ink-3:#93a4c4; --line:#243254;
  --bg:#0b1020; --card:#141c30; --accent:#5fd0ae; --warn:#e0b55c; --bad:#f0836a;
}}
:root[data-theme="dark"]{
  --ink:#e6edfa; --ink-2:#b3c2de; --ink-3:#93a4c4; --line:#243254;
  --bg:#0b1020; --card:#141c30; --accent:#5fd0ae; --warn:#e0b55c; --bad:#f0836a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"IBM Plex Sans KR",system-ui,-apple-system,"Malgun Gothic",sans-serif;
  line-height:1.65;-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:48px 24px 96px}
h1{font-size:30px;font-weight:700;letter-spacing:-.02em;margin:0 0 10px;text-wrap:balance}
.sub{color:var(--ink-2);font-size:15px;margin:0 0 18px}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 34px;padding:0}
.meta span{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);
  border:1px solid var(--line);border-radius:999px;padding:3px 10px}
h2{font-size:19px;font-weight:700;margin:52px 0 6px;letter-spacing:-.01em;
  display:flex;align-items:baseline;gap:10px}
h2 .n{font-family:var(--mono);font-size:12px;color:var(--ink-3);font-weight:500}
h3{font-size:15px;font-weight:600;margin:30px 0 12px;color:var(--ink)}
.lede{color:var(--ink-2);font-size:14.5px;margin:0 0 20px}
.note{border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:20px 0;
  background:var(--card);font-size:14px;color:var(--ink-2)}
.note p{margin:0 0 9px} .note p:last-child{margin:0}
.note.bad{border-left:3px solid var(--bad)}
.note strong{color:var(--ink)}
.mono{font-family:var(--mono);font-size:.92em}
.grid{display:grid;gap:18px}
.grid.three{grid-template-columns:repeat(3,1fr)}
@media (max-width:900px){.grid.three{grid-template-columns:repeat(2,1fr)}}
@media (max-width:620px){.grid.three{grid-template-columns:1fr}}
figure{margin:0;background:var(--card);border:1px solid var(--line);
  border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
video{display:block;width:100%;background:#0b0d10}
figcaption{padding:12px 14px 14px;font-size:13px;color:var(--ink-2);flex:1}
.tags{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px;align-items:center}
.tag{font-family:var(--mono);font-size:10.5px;color:var(--ink-3);
  border:1px solid var(--line);border-radius:5px;padding:2px 6px}
.tag.ok{color:var(--accent);border-color:currentColor}
.tag.warn{color:var(--warn);border-color:currentColor}
.tag.bad{color:var(--bad);border-color:currentColor}
.rate{display:flex;gap:4px;margin-left:auto}
.rate button{font-family:var(--mono);font-size:10.5px;padding:2px 7px;cursor:pointer;
  border:1px solid var(--line);border-radius:5px;background:transparent;color:var(--ink-3)}
.rate button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.rate button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.tw{overflow-x:auto;margin:18px 0;border:1px solid var(--line);border-radius:12px;
  background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:9px 13px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-size:11.5px;color:var(--ink-3);font-weight:600;letter-spacing:.03em}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums}
td.mono{font-family:var(--mono);font-size:12px}
.hi{color:var(--bad);font-weight:600}
pre{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px;overflow-x:auto;font-family:var(--mono);font-size:12.5px;
  color:var(--ink-2);margin:14px 0}
"""

JS = """
document.querySelectorAll('.rate').forEach(function(bar){
  var v = bar.closest('figure').querySelector('video');
  bar.querySelectorAll('button').forEach(function(b){
    b.addEventListener('click', function(){
      v.playbackRate = parseFloat(b.dataset.rate);
      bar.querySelectorAll('button').forEach(function(o){
        o.setAttribute('aria-pressed', o === b ? 'true' : 'false');
      });
    });
  });
});
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_stats(raw_dir, difficulty=0.5):
    """`generalization_raw.csv` 들에서 지형별 성공률과 참여도를 접는다.

    **주어진 난이도만 읽는다.** 결과 폴더에는 성적표(d0.5)와 곡선(d0.1~d0.7)이
    함께 있어서, 안 가리면 곡선이 성적표를 덮는다 `확인됨`
    (2026-09-12 검증 · 색인 84컷 중 12컷이 틀린 값을 달고 있었다).

    없으면 빈 것을 돌려준다. 갤러리는 그래도 나온다.
    """
    if not raw_dir or not os.path.isdir(raw_dir):
        return {}

    want = os.sep + ("d%g" % difficulty) + os.sep
    rows = []

    for base, _dirs, files in os.walk(raw_dir):
        if "generalization_raw.csv" in files and want in (base + os.sep):
            path = os.path.join(base, "generalization_raw.csv")
            rows += list(csv.DictReader(io.open(path, encoding="utf-8")))

    if not rows:
        return {}

    stat = {}

    for row in rows:
        stat.setdefault(row["terrain"], []).append(row)

    out = {}

    for terrain, group in stat.items():
        engage = [x for x in (_num(r.get("terrain_engagement_ratio")) for r in group)
                  if x is not None]
        scan = [x for x in (_num(r.get("terrain_relief_scan_m")) for r in group)
                if x is not None]
        under = [x for x in (_num(r.get("terrain_relief_underfoot_m")) for r in group)
                 if x is not None]
        wins = sum(1 for r in group
                   if str(r.get("overall_success", "")).strip().lower() in ("1", "true"))

        out[terrain] = {
            "n": len(group),
            "success": 100.0 * wins / len(group),
            "scan": (sum(scan) / len(scan)) if scan else None,
            "under": (sum(under) / len(under)) if under else None,
            "engage": (sum(engage) / len(engage)) if engage else None,
        }

    return out


def _rate_bar():
    out = ['<span class="rate">']

    for rate in ("0.25", "0.5", "1", "2"):
        pressed = "true" if rate == "1" else "false"
        out.append('<button type="button" data-rate="%s" aria-pressed="%s">%sx</button>'
                   % (rate, pressed, rate))

    out.append("</span>")

    return "".join(out)


def _head_stats(stat):
    """지형 제목 뒤에 붙는 수치."""
    if not stat:
        return ""

    out = "  ·  성공률 %.0f%%" % stat["success"]

    if stat["engage"] is not None:
        out += "  ·  참여도 %.2f" % stat["engage"]

    return out


def _figure(root, stem, stat, tags):
    """영상 한 장. 없으면 빈 문자열."""
    path = os.path.join(clip_dir(root)[0], stem + ".mp4")

    if not os.path.isfile(path):
        return ""

    # **파일을 가리킨다. 심지 않는다.** 84컷을 base64 로 심으면 194 MB 가 되어
    # 브라우저가 못 연다 `확인됨` (2026-09-12). 이 페이지는 `web/` 옆에 있으므로
    # 상대 경로로 열린다.
    src = "%s/%s.mp4" % (clip_dir(root)[1], stem)
    tags = list(tags)

    if stat:
        cls = ("ok" if stat["success"] >= 90
               else ("bad" if stat["success"] <= 30 else "warn"))
        tags.append('<span class="tag %s">%.0f%%</span>' % (cls, stat["success"]))

    return ('<figure><video src="%s" controls '
            'preload="none" playsinline muted loop></video>'
            '<figcaption><div class="tags">%s%s</div>'
            '<span class="mono">%s</span></figcaption></figure>'
            % (src, "".join(tags), _rate_bar(), stem))


def clip_dir(root):
    """영상을 어디서 읽나. `tiny/` 가 있으면 그것을 쓴다.

    한 장짜리 HTML 에 84컷을 원본 해상도로 박으면 30 MB 가 넘는다. 검토용
    사본(`tiny/`)은 같은 컷을 작게 담은 것이고, **원본은 `web/` 에 그대로**
    남아 site 가 파일로 내보낸다.

    보고서에 싣는 12컷은 `web/` 원본을 쓴다. 거기는 자리가 남는다.
    """
    tiny = os.path.join(root, "tiny")

    if os.path.isdir(tiny) and any(f.endswith(".mp4") for f in os.listdir(tiny)):
        return tiny, "tiny"

    return os.path.join(root, "web"), "web"


def scan_web(root):
    """`web/` 폴더에 실제로 있는 것을 읽는다.

    **부르는 쪽이 준 목록을 안 쓴다.** GPU 를 나눠 돌리면 각자 제 몫만
    알고 있어서, 그 목록으로 만들면 **나중 샤드가 앞 샤드를 덮어** 절반짜리
    갤러리가 나온다 `확인됨` (2026-09-11 · 48컷을 찍었는데 24개만 실렸다).

    파일 이름이 곧 선언이다. `<지형>-v<속도>[-<표>].mp4`.
    """
    web, _kind = clip_dir(root)

    if not os.path.isdir(web):
        return []

    out = []

    for name in sorted(os.listdir(web)):
        if not name.endswith(".mp4"):
            continue

        stem = name[:-4]

        if "-v" not in stem:
            continue

        terrain, rest = stem.rsplit("-v", 1)
        bits = rest.split("-", 1)

        try:
            speed = float(bits[0])
        except ValueError:
            continue

        label = bits[1] if len(bits) > 1 else ""
        out.append((stem, terrain, speed, label))

    return out


def video_spec(root, found):
    """영상 규격을 **파일을 열어서** 잰다.

    예전에는 `960 x 540 · 50 fps` 를 박아 뒀다. 해상도를 올린 뒤에도 그대로
    나와서 틀린 값을 보여 줬다 `확인됨` (2026-09-12).
    """
    try:
        import av
    except ImportError:
        return "규격 미확인"

    sizes = set()
    rates = set()

    for stem, _t, _v, _label in found:
        path = os.path.join(root, "web", stem + ".mp4")

        if not os.path.isfile(path):
            continue

        container = av.open(path)

        try:
            stream = container.streams.video[0]
            sizes.add((stream.codec_context.width, stream.codec_context.height))
            rates.add(round(float(stream.average_rate or 0)))
        finally:
            container.close()

    if len(sizes) != 1 or len(rates) != 1:
        return "규격이 섞였다: %s · %s" % (sorted(sizes), sorted(rates))

    (w, h), = sizes
    (fps,), = (tuple(rates),)
    return "%d x %d · %d fps" % (w, h, fps)


def render_page(root, cuts, args):
    """HTML 한 장. `web/` 폴더를 직접 읽는다. `cuts` 는 안 줘도 된다."""
    found = scan_web(root)

    if not found:
        raise RuntimeError("%s/web 에 mp4 가 없습니다." % root)

    # 표가 없는 것이 기준 모델, 있는 것이 대조 모델이다.
    main = [f for f in found if not f[3]]
    compare = [f for f in found if f[3]]

    stats = load_stats(args.raw_csv, getattr(args, "difficulty", 0.5))
    title = args.title or "대표 영상 · %s" % os.path.basename(args.checkpoint)

    page = ["<title>%s</title>" % title,
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=IBM+Plex+Sans+KR:wght@400;600;700&'
            'family=IBM+Plex+Mono:wght@400;500&display=swap">',
            "<style>%s</style>" % CSS,
            '<div class="wrap">',
            "<h1>%s</h1>" % title,
            '<p class="sub">HUD 는 캡처가 아니라 같은 시뮬레이션의 계측을 프레임마다 '
            '얹은 것입니다. 각 영상의 <strong>배속 단추</strong>로 0.25배에서 2배까지 '
            '골라 보실 수 있습니다.</p>',
            '<p class="meta"><span>측정 규격 2</span><span>난이도 %g</span>'
            '<span>%s</span><span>지형 %d종 · 속도 %d종</span>'
            '<span>%s</span></p>'
            % (args.difficulty, video_spec(root, found),
               len({f[1] for f in found}), len({f[2] for f in found}),
               os.path.basename(args.checkpoint))]

    page.append(
        '<div class="note"><p><strong>배속은 재생기가 맡습니다.</strong> 파일은 한 벌이고 '
        '단추가 <span class="mono">playbackRate</span> 를 바꿉니다. 다만 느리게 틀어도 '
        '<strong>새 프레임이 생기지는 않습니다.</strong> 원본이 초당 50장이라 0.25배에서는 '
        '초당 12.5장이 보입니다. 발이 어디에 닿는지 확인하는 데는 충분하고, 부드러운 '
        '슬로우모션이 필요하면 촬영을 200 Hz 로 해야 하는데 실측 비용이 '
        '<strong>프레임당 약 100배</strong>입니다.</p>'
        '<p>영상은 <strong>지형 구간까지만</strong> 잘랐습니다. 지형은 출발점 앞 4~5 m 에서 '
        '끝나고 그 뒤는 평평한 테두리라 볼 것이 없습니다. 넘어져서 그만큼 못 간 판은 '
        '그대로 다 남아 있습니다.</p></div>')

    # ── 참여도 ────────────────────────────────────────────────────────
    if stats:
        page.append('<h2><span class="n">01</span>성공률만 보면 안 되는 이유</h2>')
        page.append('<p class="lede">「넘어지지 않고 통과선을 넘었다」가 성공입니다. '
                    '그런데 장애물을 <strong>비켜 가도</strong> 그 조건은 채워집니다. '
                    '그래서 «실제로 지형을 탔는가»를 재는 열을 넣었습니다.</p>')
        page.append('<div class="tw"><table><thead><tr><th>지형</th>'
                    '<th class="num">판</th><th class="num">성공률</th>'
                    '<th class="num">주변 기복</th><th class="num">발로 탄 것</th>'
                    '<th class="num">참여도</th><th>읽는 법</th></tr></thead><tbody>')

        shown = sorted({f[1] for f in found} & set(stats),
                       key=lambda t: (stats[t]["engage"]
                                      if stats[t]["engage"] is not None else 9))

        for terrain in shown:
            s = stats[terrain]
            e = s["engage"]

            if e is None:
                judge, cls = "이 열로는 못 잰다", ""
            elif s["success"] >= 90 and e < 0.4:
                judge, cls = "성공률이 높지만 <span class='hi'>비켜 갔다</span>", "hi"
            elif e >= 0.8 and s["success"] < 60:
                judge, cls = "제대로 타고 실패했다", ""
            elif e >= 0.8:
                judge, cls = "제대로 타고 성공했다", ""
            else:
                judge, cls = "일부만 탔다", ""

            page.append(
                '<tr><td class="mono">%s</td><td class="num">%d</td>'
                '<td class="num">%.0f%%</td><td class="num">%s</td>'
                '<td class="num">%s</td><td class="num %s">%s</td><td>%s</td></tr>'
                % (terrain, s["n"], s["success"],
                   ("%.3f" % s["scan"]) if s["scan"] is not None else ".",
                   ("%.3f" % s["under"]) if s["under"] is not None else ".",
                   cls, ("%.2f" % e) if e is not None else ".", judge))

        page.append("</tbody></table></div>")
        page.append('<p class="lede">단위는 m 입니다. <strong>주변 기복</strong>은 몸 주변 '
                    '1.6 x 1.0 m 안에 넘을 것이 있었는가, <strong>발로 탄 것</strong>은 몸 '
                    '바로 아래 지면이 위아래로 얼마나 움직였는가입니다. 판정은 안 바꿨습니다 · '
                    '성공률은 여전히 네 축의 AND 입니다.</p>')

    # ── 영상 ──────────────────────────────────────────────────────────
    # ── 성적표 영상 · 지형마다 속도 셋을 «나란히» ─────────────────────
    page.append('<h2><span class="n">02</span>지형별 · 속도 셋</h2>')
    page.append('<p class="lede">한 줄에 <strong>0.5 · 1.0 · 1.5 m/s</strong> 를 '
                '나란히 놓았습니다. 같은 지형을 속도만 바꿔 본 것이라 옆으로 '
                '견주시면 됩니다. 배속 단추는 그 영상에만 적용됩니다.</p>')

    by_terrain = {}

    for stem, terrain, speed, _label in main:
        by_terrain.setdefault(terrain, []).append((stem, speed))

    for terrain in sorted(by_terrain):
        page.append("<h3>%s%s</h3>" % (terrain, _head_stats(stats.get(terrain))))
        page.append('<div class="grid three">')

        for stem, speed in sorted(by_terrain[terrain], key=lambda x: x[1]):
            page.append(_figure(root, stem, stats.get(terrain),
                                ['<span class="tag">%g m/s</span>' % speed]))

        page.append("</div>")

    # ── 대조 영상 · 같은 자리에서 모델을 «나란히» ─────────────────────
    if compare:
        page.append('<h2><span class="n">03</span>모델 대조</h2>')
        page.append('<p class="lede">한 줄에 <strong>기준선 · A · foothold-v1</strong> 을 '
                    '나란히 놓았습니다. 지형·속도·난수가 같으므로 차이는 정책에서만 '
                    '옵니다. 성적 격차가 20 %p 이상인 자리와, 세 모델이 모두 0 % 인 '
                    '자리만 담았습니다.</p>')

        cells = {}

        for stem, terrain, speed, label in compare:
            cells.setdefault((terrain, speed), {})[label] = stem

        for stem, terrain, speed, label in main:
            if (terrain, speed) in cells:
                cells[(terrain, speed)][""] = stem

        ORDER = [("baseline", "기준선 NVIDIA"), ("A", "A · 연습 틈 0.20 m"),
                 ("", "foothold-v1")]

        for terrain, speed in sorted(cells):
            page.append("<h3>%s · %g m/s%s</h3>"
                        % (terrain, speed, _head_stats(stats.get(terrain))))
            page.append('<div class="grid three">')

            for key, shown in ORDER:
                stem = cells[(terrain, speed)].get(key)

                if not stem:
                    continue

                page.append(_figure(root, stem, None,
                                    ['<span class="tag">%s</span>' % shown]))

            page.append("</div>")

    # ── 다시 만드는 법 ────────────────────────────────────────────────
    page.append('<h2><span class="n">04</span>같은 것을 다시 만들려면</h2>')
    page.append('<p class="lede">저장소를 받은 사람이 <strong>옵션 없이 한 줄</strong>로 '
                '같은 결과를 냅니다.</p>')
    page.append("<pre>git pull origin main" + NL +
                "pip install av        # Isaac 이 도는 파이썬에 한 번만" + NL + NL +
                "python sim/eval/render_gallery.py \\" + NL +
                "    --checkpoint models/foothold-v1.pt</pre>")
    page.append('<div class="note"><p>지형·속도·시점·길이·자르는 자리가 전부 기본값입니다. '
                '시점은 옵션이 아니라 <strong>지형이 정합니다</strong> '
                '(<span class="mono">render_gallery.py</span> 의 '
                '<span class="mono">VIEW_BY_TERRAIN</span>). 중간에 끊겨도 같은 명령을 '
                '다시 주면 이미 만든 컷은 건너뛰고 이어서 합니다.</p>'
                '<p>성공률과 참여도를 얹으려면 평가 결과 폴더를 '
                '<span class="mono">--raw_csv</span> 로 주십시오. 안 주면 영상만 나옵니다.</p></div>')

    page.append("</div>")
    page.append("<script>%s</script>" % JS)

    out = os.path.join(root, "gallery.html")
    io.open(out, "w", encoding="utf-8").write(NL.join(page))

    return out
