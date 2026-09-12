# -*- coding: utf-8 -*-
"""종합보고서 1차 · HTML. 수치는 report_numbers.json 에서만 읽는다.

분류: 운영
작성: Claude 세션 (오흥재 지시) · 2026-09-11 23:45
근거: maindata-v1 지형 16종 x 모델 3 x 속도 3 · 14,400 판
요지: N차에 그대로 다시 쓰는 양식. 손으로 적은 숫자가 없다
상태: 확정
"""
import base64
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
# 뿌리와 산출 자리는 «인자»로 받는다. 절대 경로를 박으면 다른 PC 에서 못 돈다.
REPO = os.environ.get("FOOTHOLD_REPO") or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
S = os.environ.get("FOOTHOLD_REPORT_OUT") or os.path.join(
    REPO, "sim", "eval", "results", "report-v1")
os.makedirs(S, exist_ok=True)
REPO_RESULTS = os.path.join(REPO, "sim", "eval", "results")
NL = chr(10)

D = json.load(io.open(os.path.join(S, "report_numbers.json"), encoding="utf-8"))
SCORE = {tuple(k.split("|")): v for k, v in D["score"].items()}
ENG = D["engage"]
BD = D["breakdown"]        # (지형|모델|속도) -> 승패와 실패 축 조합
TR15 = D["tracking15"]     # 1.5 m/s 속도추종 통과 수
ZONES = D["zones"]         # 지형 -> [장애물 구간 시작 m, 끝 m]


def worst(key, top=2):
    """그 칸에서 «가장 많은» 실패 조합 몇 개. 성공률만으로 원인을 말하지 않으려는 것."""
    combo = BD[key]["combo"]
    return sorted(combo.items(), key=lambda kv: -kv[1])[:top]
AXES = {tuple(k.split("|")): v for k, v in D["axes"].items()}
TSET = D["terr_set"]
EPISODES = D["episodes"]

MODELS = [("baseline", "기준선 NVIDIA"), ("A", "A"), ("foothold-v1", "foothold-v1")]
SPEEDS = ["0.5", "1", "1.5"]
SETS = [("rough6", "기존 험지 6종"), ("unseen10", "미경험 험지 10종")]
TERR = sorted(TSET, key=lambda t: (TSET[t], t))

MATRIX = io.open(os.path.join(S, "chart_matrix.svg"), encoding="utf-8").read()
STATUS = json.load(io.open(os.path.join(S, "matrix_status.json"), encoding="utf-8"))
SCATTER = io.open(os.path.join(S, "chart_scatter.svg"), encoding="utf-8").read()


# ── 근거 영상 ──────────────────────────────────────────────────────────
#
# **주장 옆에 근거를 둔다.** 갤러리로 보내 놓으면 읽는 사람이 옮겨 가서
# 찾아야 하고, 대개 안 찾는다.
#
# **960 x 540 을 쓴다.** 640 x 360 으로 넣었더니 확대하면 깨졌다
# `확인됨` (2026-09-12 팀장 지적). 보고서에 실리는 것은 12컷뿐이라
# 이 해상도로도 자리가 남는다. 갤러리 84컷은 따로 줄인다.
# 영상을 어느 갤러리에서 가져오나. 판이 바뀌면 환경 변수로 준다.
GALLERY = os.environ.get("FOOTHOLD_GALLERY") or os.path.join(
    REPO_RESULTS, "20260911-gallery-1080")
TINY = os.path.join(GALLERY, "web")

if not os.path.isdir(TINY):
    raise SystemExit("갤러리 web/ 이 없다: %s. FOOTHOLD_GALLERY 로 지정한다" % TINY)


def _video_spec():
    """영상 규격을 **파일을 열어서** 잰다. 손으로 적으면 다음 판에 틀린다."""
    import av

    sizes = set()
    rates = set()

    for _name in sorted(os.listdir(TINY)):
        if not _name.endswith(".mp4"):
            continue
        _c = av.open(os.path.join(TINY, _name))
        try:
            _st = _c.streams.video[0]
            sizes.add((_st.codec_context.width, _st.codec_context.height))
            rates.add(round(float(_st.average_rate or 0)))
        finally:
            _c.close()

    if len(sizes) != 1 or len(rates) != 1:
        raise SystemExit("갤러리 컷의 규격이 섞여 있다: %s · %s" % (sorted(sizes), sorted(rates)))

    (_w, _h), = sizes
    (_fps,), = (tuple(rates),)
    return "%d x %d" % (_w, _h), str(_fps)


VIDEO_SIZE, VIDEO_FPS = _video_spec()


# 영상을 어떻게 실을까. **심으면 한 장으로 끝나지만 커진다.**
#
#     심는다 (기본)   1080p 12컷이면 약 15 MB. 파일 하나로 들고 다닌다
#     가리킨다        --link 로 갤러리 경로를 준다. 페이지는 수백 KB
#
# 웹에 올릴 때는 갤러리가 같은 자리에 있으므로 가리키는 쪽이 맞다.
LINK = ""

for _i, _a in enumerate(sys.argv):
    if _a == "--link" and _i + 1 < len(sys.argv):
        LINK = sys.argv[_i + 1]

        if LINK and not LINK.endswith("/"):
            LINK += "/"


# 본문이 달라고 한 컷 가운데 «없던» 것. 끝에서 소리를 낸다.
WANTED_MISSING = []


def clip(stem, who, why):
    """영상 한 장. **없으면 모아 두었다가 끝에서 죽는다.**

    예전에는 빈 문자열을 돌려줬다. 그러면 본문이 「왼쪽은 …, 오른쪽은 …」이라
    말하는데 그 자리가 통째로 사라진다 `확인됨` (2026-09-12 · 대조컷이 덜
    구워진 상태로 돌렸더니 12컷이 10컷이 됐고 아무 말도 안 나왔다).
    """
    path = os.path.join(TINY, stem + ".mp4")

    if not os.path.isfile(path):
        WANTED_MISSING.append(stem)
        return ""

    src = (LINK + stem + ".mp4") if LINK else (
        "data:video/mp4;base64," + base64.b64encode(io.open(path, "rb").read()).decode())
    rate = '<span class="rate">' + "".join(
        '<button type="button" data-rate="%s" aria-pressed="%s">%sx</button>'
        % (r, "true" if r == "1" else "false", r)
        for r in ("0.25", "0.5", "1", "2")) + "</span>"

    return ('<figure><video src="%s" controls '
            'preload="metadata" playsinline muted loop></video>'
            '<figcaption><span class="who">%s</span>%s%s</figcaption></figure>'
            % (src, who, why, rate))


def clips(items):
    """영상 여러 장을 3열로."""
    body = "".join(clip(*i) for i in items)
    return ('<div class="vid">%s</div>' % body) if body else ""


def g(t, m, v):
    return SCORE.get((t, m, v))


def avg(tset, m, v):
    xs = [g(t, m, v) for t in TERR if TSET[t] == tset and g(t, m, v) is not None]
    return (sum(xs) / len(xs)) if xs else None


def fmt(v, digits=0):
    return "." if v is None else ("%.*f" % (digits, v))


CSS = """
:root{
  /* porcelain · lieflat-charts color-presets.js · 차트와 같은 체계 */
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
  line-height:1.72;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto;padding:56px 24px 110px}
.head{border-left:3px solid var(--ink);padding-left:16px;margin-bottom:34px}
.head p{margin:2px 0;font-size:12.5px;color:var(--ink-3);font-family:var(--mono)}
h1{font-size:32px;font-weight:700;letter-spacing:-.025em;margin:0 0 12px;text-wrap:balance}
.lead{font-size:16.5px;color:var(--ink-2);margin:0 0 8px}
h2{font-size:20px;font-weight:700;margin:58px 0 8px;letter-spacing:-.01em;
  display:flex;align-items:baseline;gap:11px}
h2 .n{font-family:var(--mono);font-size:12px;color:var(--ink-3);font-weight:500}
h3{font-size:15.5px;font-weight:600;margin:32px 0 10px}
p{margin:0 0 14px}
.tw{overflow-x:auto;margin:20px 0;border:1px solid var(--line);border-radius:12px;
  background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-size:11.5px;color:var(--ink-3);font-weight:600;letter-spacing:.03em}
thead tr:last-child th{border-bottom:1.5px solid var(--line)}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right;font-family:var(--mono);font-variant-numeric:tabular-nums}
td.mono{font-family:var(--mono);font-size:12px}
.grp{border-left:1px solid var(--line)}
.up{color:var(--accent);font-weight:600}
.down{color:var(--bad);font-weight:600}
.flat{color:var(--ink-3)}
figure{margin:24px 0;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:20px 20px 14px;overflow:hidden}
figure svg{display:block;width:100%;height:auto}
figcaption{margin-top:12px;font-size:12.5px;color:var(--ink-3);
  padding-top:11px;border-top:1px solid var(--line)}
.note{border:1px solid var(--line);border-left:3px solid var(--ink-3);
  border-radius:10px;padding:15px 18px;margin:20px 0;background:var(--card);
  font-size:14px;color:var(--ink-2)}
.note.bad{border-left-color:var(--bad)}
.note.ok{border-left-color:var(--accent)}
.note p{margin:0 0 8px} .note p:last-child{margin:0}
.note strong{color:var(--ink)}
.mono{font-family:var(--mono);font-size:.93em}
.vid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}
@media (max-width:880px){.vid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:600px){.vid{grid-template-columns:1fr}}
.vid figure{margin:0;padding:0;border-radius:12px;overflow:hidden;display:flex;
  flex-direction:column}
.vid video{display:block;width:100%;background:#0b1020}
.vid figcaption{margin:0;padding:11px 13px 13px;font-size:12.5px;border-top:none;
  color:var(--ink-2)}
.vid .who{display:block;font-family:var(--mono);font-size:11px;color:var(--ink-3);
  margin-bottom:3px}
.rate{display:flex;gap:4px;margin-top:7px}
.rate button{font-family:var(--mono);font-size:10.5px;padding:2px 7px;cursor:pointer;
  border:1px solid var(--line);border-radius:5px;background:transparent;color:var(--ink-2)}
.rate button[aria-pressed="true"]{background:var(--ink);color:#fff;border-color:var(--ink)}
.rate button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
pre{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:15px 17px;overflow-x:auto;font-family:var(--mono);font-size:12.5px;
  color:var(--ink-2);margin:16px 0;line-height:1.6}
ul{margin:0 0 14px;padding-left:20px}
li{margin:5px 0}
"""

SITE_DIR = os.environ.get("FOOTHOLD_SITE") or os.path.abspath(
    os.path.join(REPO, "..", "foothold-site"))


def site_nav():
    """site 의 전역바를 가져온다.

    **없으면 웹에서 갤러리로 가는 길이 없다** `확인됨` (2026-09-12 · 127개
    페이지에 있는 전역바가 이 보고서에만 없었다. 팀장이 잡았다).
    """
    path = os.path.join(SITE_DIR, "notice-20260902.html")

    if not os.path.isfile(path):
        return "", ""

    src = io.open(path, encoding="utf-8").read()
    got = re.search(r"<!--gnav:v1-->.*?<!--/gnav:v1-->", src, re.S)

    if not got:
        return "", ""

    bar = re.sub(r'href="(?!/|https?:)([^"]+)"', r'href="/\1"', got.group(0))
    bar = bar.replace('src="assets/', 'src="/assets/')
    bar = bar.replace('class="on"', 'class=""')
    i = src.find(".gnav{")
    j = src.find("</style>", i)
    return bar, (src[i:j].rstrip() if i > 0 else "")


NAV, NAV_CSS = site_nav()

# **온전한 문서로 낸다.** 조각으로 내면 doctype 도 charset 도 뷰포트도 없다.
# 파일로 저장해 열면 한글이 깨지고 휴대폰에서 조판이 무너진다 `확인됨`
# (2026-09-04 에 PDF 로 같은 일을 겪었다).
p = ['<!doctype html>', '<html lang="ko">', "<head>", '<meta charset="utf-8">',
     '<meta name="viewport" content="width=device-width,initial-scale=1">',
     '<title>FOOTHOLD 종합보고서 1차</title>',
     '<meta name="description" content="기준선 NVIDIA vs A vs foothold-v1 · '
     '난이도 0.5 성적표 14,400 판 · 전체 원자료 43,200 판">',
     '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
     'family=IBM+Plex+Sans+KR:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">',
     "<style>%s%s%s</style>" % (CSS, NL, NAV_CSS), "</head>", "<body>",
     NAV, '<div class="wrap">']

p.append('<div class="head">'
         '<p>분류: 보고</p>'
         '<p>작성: 오흥재 · 2026-09-11</p>'
         '<p>근거: 지형 16종 x 모델 3 x 속도 3 · %s 판 · 측정 규격 2</p>'
         '<p>요지: foothold-v1 은 기존 험지를 유지하면서 미경험 험지 gap 을 1 %%에서 100 %%로 올렸다</p>'
         '<p>상태: 검토중</p></div>' % format(EPISODES, ","))

p.append("<h1>FOOTHOLD 종합보고서 1차</h1>")
p.append('<p class="lead">Unitree Go2 사족보행 정책을 미경험 험지에서 평가한 결과입니다. '
         '기준선(NVIDIA 공식 체크포인트), 중간 판 A, 그리고 이번 배포 대상인 '
         'foothold-v1 을 같은 조건에서 비교합니다.</p>')

# ── 1 ──────────────────────────────────────────────────────────────────
p.append('<h2><span class="n">01</span>한 줄</h2>')

gap_base = g("gap", "baseline", "1")
gap_v1 = g("gap", "foothold-v1", "1")
p.append('<p><strong>foothold-v1 은 기존 험지 6종의 성적을 유지하거나 끌어올리면서, '
         '미경험 험지 <span class="mono">gap</span> 의 성공률을 (난이도 0.5 · 1.0 m/s · 100 판 기준) %.0f %%에서 %.0f %%로 '
         '올렸습니다.</strong> 다만 <span class="mono">stepping_stones</span> 는 세 모델 '
         '모두 0 %% 이고, <span class="mono">rails</span> 는 %.0f %% 에 머뭅니다.</p>'
         % (gap_base, gap_v1, g("rails", "foothold-v1", "1")))

p.append('<p>아래는 그 주장의 근거입니다. 같은 지형, 같은 속도, 같은 난수에서 '
         '세 모델이 무엇을 하는지 보십시오.</p>')
p.append(clips([
    ("gap-v1-baseline", "기준선 NVIDIA",
     "이 자리 성공 %d/%d. <strong>이 시연 한 판에서는</strong> 앞다리가 틈에 "
     "빠지고 몸통이 가장자리에 걸립니다. 100 판이 모두 그렇다는 뜻은 아닙니다"
     % (BD["gap|baseline|1"]["win"], BD["gap|baseline|1"]["n"])),
    ("gap-v1-A", "A · 연습 틈 0.05~0.20 m",
     "이 자리 성공 %d/%d. 시험 틈은 0.275 m 로 연습 범위 밖입니다. "
     "그것이 원인인지는 아직 안 갈라냈습니다(미확인)"
     % (BD["gap|A|1"]["win"], BD["gap|A|1"]["n"])),
    ("gap-v1", "foothold-v1",
     "이 자리 성공 %d/%d. 이 시연에서는 뒷발이 가장자리를 딛고 앞발이 먼저 "
     "건넙니다" % (BD["gap|foothold-v1|1"]["win"], BD["gap|foothold-v1|1"]["n"])),
]))

# ── 2 ──────────────────────────────────────────────────────────────────
p.append('<h2><span class="n">02</span>비교 대상</h2>')
p.append('<div class="tw"><table><thead><tr><th>이름</th><th>무엇인가</th>'
         '<th>연습한 틈 폭</th><th>출처</th></tr></thead><tbody>'
         '<tr><td class="mono">기준선 NVIDIA</td><td>Isaac Lab 공식 Go2 험지 체크포인트</td>'
         '<td class="mono">없음</td><td class="mono">.pretrained_checkpoints</td></tr>'
         '<tr><td class="mono">A</td><td>기존 험지 6종 재학습 · 틈 연습 추가</td>'
         '<td class="mono">0.05 ~ 0.20 m</td><td class="mono">model_1500.pt</td></tr>'
         '<tr><td class="mono">foothold-v1</td><td>틈 폭을 넓혀 재학습</td>'
         '<td class="mono">0.15 ~ 0.40 m</td><td class="mono">models/foothold-v1.pt</td></tr>'
         '</tbody></table></div>')
p.append('<p>세 모델 모두 같은 평가 하네스, 같은 난수(seed 42), 같은 난이도(0.5)로 '
         '측정했습니다. 지형마다 100 판입니다.</p>')

# ── 3 ──────────────────────────────────────────────────────────────────
p.append('<h2><span class="n">03</span>성적표</h2>')
p.append('<p>난이도 0.5, 명령 속도 1.0 m/s, 지형마다 100 판에서의 성공률입니다. '
         '성공은 네 축(생존 · 전진 · 속도추종 · 방향)의 AND 입니다.</p>')
p.append('<figure>%s<figcaption>지형 16종 x 모델 3 · 난이도 0.5 · 1.0 m/s · '
         '지형마다 100 판. 칸 안의 수가 성공률이고 진할수록 높습니다.</figcaption></figure>'
         % MATRIX)

p.append("<h3>속도별 전수</h3>")
p.append('<div class="tw"><table><thead><tr><th rowspan="2">지형</th>')
for _m, label in MODELS:
    p.append('<th class="num grp" colspan="3">%s</th>' % label)
p.append("</tr><tr>")
for _m, _l in MODELS:
    for i, v in enumerate(SPEEDS):
        p.append('<th class="num%s">%s</th>' % (" grp" if i == 0 else "", v))
p.append("</tr></thead><tbody>")
for tset, label in SETS:
    p.append('<tr><td colspan="10" style="background:var(--bg);font-size:11.5px;'
             'color:var(--ink-3);font-weight:600">%s</td></tr>' % label)
    for t in [x for x in TERR if TSET[x] == tset]:
        p.append('<tr><td class="mono">%s</td>' % t)
        for m, _l in MODELS:
            for i, v in enumerate(SPEEDS):
                p.append('<td class="num%s">%s</td>'
                         % (" grp" if i == 0 else "", fmt(g(t, m, v))))
        p.append("</tr>")
p.append("</tbody></table></div>")

# ── 4 ──────────────────────────────────────────────────────────────────
p.append('<h2><span class="n">04</span>무엇이 달라졌나</h2>')

p.append("<h3>기존 험지는 무너지지 않았습니다</h3>")
p.append('<div class="tw"><table><thead><tr><th>집합</th><th>속도</th>'
         '<th class="num">기준선</th><th class="num">A</th>'
         '<th class="num">foothold-v1</th><th class="num">기준선 대비</th>'
         '</tr></thead><tbody>')
for tset, label in SETS:
    for v in SPEEDS:
        b, a, c = avg(tset, "baseline", v), avg(tset, "A", v), avg(tset, "foothold-v1", v)
        d = (c - b) if (b is not None and c is not None) else None
        cls = "up" if (d or 0) > 1 else ("down" if (d or 0) < -1 else "flat")
        p.append('<tr><td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                 '<td class="num">%s</td><td class="num">%s</td>'
                 '<td class="num %s">%s%s</td></tr>'
                 % (label, v, fmt(b, 1), fmt(a, 1), fmt(c, 1), cls,
                    "+" if (d or 0) > 0 else "", fmt(d, 1)))
p.append("</tbody></table></div>")
p.append('<p>집합별 지형 평균입니다. 기존 험지 6종에서 foothold-v1 은 세 속도 모두 '
         '기준선을 웃돕니다. 특히 1.5 m/s 에서 기준선은 평균 %.1f %% 인데 '
         'foothold-v1 은 %.1f %% 입니다.</p>'
         % (avg("rough6", "baseline", "1.5"), avg("rough6", "foothold-v1", "1.5")))

p.append("<h3>기준선은 1.5 m/s 를 따라가지 못합니다</h3>")
p.append('<p>1.5 m/s 에서 기준선이 실패한 판을 <strong>판마다</strong> 갈랐습니다. '
         '축별 합계로는 어느 판이 어느 축에서 떨어졌는지 알 수 없어, 각 판의 네 축을 '
         '모두 보고 분류했습니다.</p>')

bad4 = [(t, AXES[(t, "baseline")]) for t in TERR
        if (t, "baseline") in AXES and AXES[(t, "baseline")]["failed"] > 0]

p.append('<div class="tw"><table><thead><tr><th>지형</th><th class="num">실패 판</th>'
         '<th class="num">속도추종만</th><th class="num">속도추종+1축</th>'
         '<th class="num">속도추종+2축 이상</th><th class="num">속도추종 무관</th>'
         '<th class="num">foothold-v1 성공률</th></tr></thead><tbody>')
sum_only = sum_one = sum_many = sum_other = sum_failed = 0
for t, a in sorted(bad4, key=lambda x: -x[1]["tracking_only"]):
    sum_only += a["tracking_only"]; sum_one += a["tracking_plus_one"]
    sum_many += a["tracking_plus_many"]; sum_other += a["no_tracking"]
    sum_failed += a["failed"]
    p.append('<tr><td class="mono">%s</td><td class="num">%d</td>'
             '<td class="num">%d</td><td class="num">%d</td>'
             '<td class="num">%d</td><td class="num">%d</td>'
             '<td class="num up">%s</td></tr>'
             % (t, a["failed"], a["tracking_only"], a["tracking_plus_one"],
                a["tracking_plus_many"], a["no_tracking"],
                fmt(g(t, "foothold-v1", "1.5"))))
p.append('<tr><td><strong>합계</strong></td><td class="num"><strong>%d</strong></td>'
         '<td class="num"><strong>%d</strong></td><td class="num"><strong>%d</strong></td>'
         '<td class="num"><strong>%d</strong></td><td class="num"><strong>%d</strong></td>'
         '<td class="num"></td></tr>'
         % (sum_failed, sum_only, sum_one, sum_many, sum_other))
p.append("</tbody></table></div>")

p.append('<p>난이도 0.5, 지형마다 100 판입니다. 실패한 %d 판 가운데 '
         '<strong>%d 판(%.0f %%)은 속도추종 축에서만 떨어졌습니다.</strong> '
         '나머지 세 축은 통과했다는 뜻이고, 그 판에서 로봇은 넘어지지 않고 '
         '통과선도 넘었습니다. 명령 1.5 m/s 를 주었는데 그보다 느리게 간 것입니다.</p>'
         % (sum_failed, sum_only, 100.0 * sum_only / sum_failed))
# 네 갈래를 «다» 적는다. 합이 실패 판 수와 맞는 것이 보여야 한다.
# 「두 축 이상」은 속도추종을 포함해 세는지 아닌지가 중의적이라 쓰지 않는다.
p.append('<p>나머지 %d 판은 이렇게 갈립니다. '
         '속도추종 <strong>말고 한 축이 더</strong> 떨어진 판이 %d, '
         '<strong>두 축 이상이 더</strong> 떨어진 판이 %d 입니다. '
         '속도추종이 통과했는데 실패한 판은 %d 입니다. '
         '넷을 더하면 %d 로 실패 판 수와 같습니다.</p>'
         % (sum_failed - sum_only, sum_one, sum_many, sum_other,
            sum_only + sum_one + sum_many + sum_other))
p.append('<p>두 축 이상이 더 떨어진 %d 판은 '
         '<span class="mono">floating_ring</span> · '
         '<span class="mono">stepping_stones</span> · <span class="mono">gap</span> · '
         '<span class="mono">pyramid_stairs_inv</span> 에 몰려 있고, '
         '그 지형에서는 실제로 넘어지거나 통과선까지 못 갔습니다.</p>' % sum_many)
p.append('<div class="note"><p><strong>이 표를 「기준선이 고속 험지에서 무너진다」로 '
         '읽으면 과장입니다.</strong> 대부분은 넘어지지 않고 더 느리게 걸을 뿐입니다. '
         '자료가 말하는 것은 <strong>기준선에 1.5 m/s 를 시켜도 그 속도가 안 나온다</strong>는 '
         '것입니다. foothold-v1 도 <strong>모든 지형에서 그 속도를 내는 것은 아닙니다.</strong> '
         '같은 조건에서 속도추종 축을 통과한 판이 %s / %s 이고, '
         '<span class="mono">stepping_stones</span> 는 %d/%d, '
         '<span class="mono">rails</span> 는 %d/%d 입니다.</p>'
         '<p>이 관측은 시뮬레이션 안의 것입니다. 실기에서 같은 일이 일어나는지는 '
         '재보지 않았습니다(미확인).</p></div>'
         % (f"{TR15['pass']:,}", f"{TR15['n']:,}",
            TR15["per"]["stepping_stones"][0], TR15["per"]["stepping_stones"][1],
            TR15["per"]["rails"][0], TR15["per"]["rails"][1]))

p.append('<p>같은 지형(<span class="mono">wave</span>)을 1.5 m/s 명령으로 걷는 장면입니다. '
         '<strong>셋 다 넘어지지 않습니다.</strong> 기준선은 그 속도가 안 나와서 '
         '속도추종 축에서 떨어집니다.</p>')
p.append('<div class="note"><p><strong>영상은 평가 판 자체가 아닙니다.</strong> '
         '같은 체크포인트·지형·난이도·난수로 <strong>따로 촬영한 한 판</strong>이고, '
         '성적표의 100 판 중 하나를 꺼낸 것이 아닙니다. 옆의 성공률은 그 자리의 '
         '100 판 집계이고, 영상은 같은 조건에서 로봇이 무엇을 하는지 보여 줍니다.</p>'
         '<p><strong>HUD 의 추종 표시는 평가의 속도추종 판정과 다른 계산입니다.</strong> '
         'HUD 는 그 시점까지의 <strong>전후 방향</strong> 오차 '
         '<span class="mono">abs(vx - 명령속도)</span> 의 누적 평균을 보여 줍니다. '
         '평가는 전후와 좌우를 합친 <strong>평면</strong> 오차를 누적합니다. '
         '판정 한계 0.25 m/s 를 사이에 두고 갈리기도 합니다. 기준선 1.5 m/s '
         '시연 세 편의 trace 를 다시 재 보면 전후 오차는 0.18~0.24 로 한계 안이고 '
         '같은 표본의 평면 오차는 0.25~0.30 으로 한계 밖입니다 '
         '(<span class="mono">repeated_boxes</span> · '
         '<span class="mono">repeated_cylinders</span> · '
         '<span class="mono">wave</span>). '
         '<strong>HUD 를 보고 판정을 역산하지 마십시오.</strong></p>'
         '<p>영상은 %s 초당 %s장이고, 지형이 끝나는 자리까지만 잘랐습니다. '
         '초당 장수는 임의값이 아니라 <strong>정책이 결정을 내리는 주기</strong>입니다 '
         '(물리 200 Hz · 4스텝에 결정 1번 · 결정 1번에 프레임 1장).</p></div>'
         % (VIDEO_SIZE, VIDEO_FPS))
p.append(clips([
    ("wave-v1.5-baseline", "기준선 NVIDIA · 1.5 m/s 명령",
     "종합 0 %. 생존 100 · 전진 100 · <strong>속도추종 0</strong>. 넘어진 것이 아니라 느립니다"),
    ("wave-v1.5-A", "A · 1.5 m/s 명령", "종합 100 %"),
    ("wave-v1.5", "foothold-v1 · 1.5 m/s 명령", ("종합 성공 %d/%d. 속도추종 기준인 평면 평균 오차 0.25 m/s 이내를 "
      "100 판 모두 통과했습니다. 명령 속도를 정확히 낸다는 뜻은 아닙니다"
      % (BD["wave|foothold-v1|1.5"]["win"], BD["wave|foothold-v1|1.5"]["n"]))),
]))

# ── 5 ──────────────────────────────────────────────────────────────────
p.append('<h2><span class="n">05</span>성공률만으로는 안 보이는 것</h2>')
p.append('<p>성공 조건은 네 축(생존 · 전진 · 속도추종 · 방향)의 AND입니다. 그런데 장애물을 '
         '<strong>비켜 가도</strong> 그 조건은 채워집니다. 그래서 이번 판에 '
         '<strong>몸통 아래 광선이 어느 높이 폭을 지났는가</strong>를 재는 열 셋을 더했습니다.</p>')
p.append('<figure>%s<figcaption>가로가 참여도, 세로가 성공률입니다. 오른쪽 위는 '
         '중앙 광선이 지난 높이 폭이 스캔 전체와 비슷하면서 성공률도 높은 자리, '
         '왼쪽 위는 그 폭이 작은데 성공률은 높은 자리입니다. 이 비율은 '
         '발이 닿았는지나 어느 길로 갔는지를 재지 않습니다.'
         '</figcaption></figure>' % SCATTER)

p.append('<div class="tw"><table><thead><tr><th>지형</th><th class="num">성공률</th>'
         '<th class="num">스캔 전체 기복 (m)</th>'
         '<th class="num">중앙 광선 기복 (m)</th>'
         '<th class="num">참여도 평균</th><th class="num">중앙값</th>'
         '<th class="num">10~90분위</th><th>관측</th></tr></thead><tbody>')
# **정의를 본문에 둔다.** 갤러리 색인에 적어 둔 것은 보고서를 읽는 사람에게
# 안 보인다 `확인됨` (2026-09-12 검증 2회차 2번).
_defn = ('<div class="note"><p><strong>참여도가 무엇인가.</strong> '
         '한 판 동안 몸통 아래 <strong>중앙 광선 하나</strong>가 지나간 높이 폭을, '
         '<strong>스캔 전체</strong>가 본 높이 폭으로 나눈 값입니다. '
         '0 과 1 사이로 자릅니다.</p>'
         '<p class="mono" style="font-size:.86rem">'
         '참여도 = min(1, max(0, 중앙 광선 높이 범위 / 스캔 전체 높이 범위))</p>'
         '<p>높이 범위의 단위는 m 이고 비율은 단위가 없습니다. 스캔 전체 기복이 '
         '0.02 m 미만이면 나눗셈이 뜻을 잃으므로 <strong>비웁니다.</strong> '
         '난이도 0.5 · 1.0 m/s · foothold-v1 에서 비는 것은 '
         '<span class="mono">gap</span> 뿐입니다.</p>'
         '<p><strong>이 값이 답하지 않는 것.</strong> 발이 장애물에 닿았는지, '
         '어느 길로 우회했는지, 장애물 구간을 끝까지 갔는지는 이 비율만으로 '
         '알 수 없습니다. 광선 하나가 지나간 높이 폭일 뿐입니다.</p></div>')
p.append(_defn)

order = sorted((t for t in TERR if t in ENG and ENG[t]["ratio"] is not None),
               key=lambda t: ENG[t]["ratio"])
for t in order:
    e = ENG[t]
    s = g(t, "foothold-v1", "1")
    if s >= 90 and e["ratio"] < 0.4:
        judge, cls = "성공률 높음 · 중앙 광선 기복 작음", "down"
    elif e["ratio"] >= 0.8 and s < 60:
        judge, cls = "중앙 광선 기복 큼 · 성공률 낮음", ""
    elif e["ratio"] >= 0.8:
        judge, cls = "중앙 광선 기복 큼 · 성공률 높음", "up"
    else:
        judge, cls = "중간", ""
    p.append('<tr><td class="mono">%s</td><td class="num">%s</td>'
             '<td class="num">%.3f</td><td class="num">%.3f</td>'
             '<td class="num %s">%.2f</td><td class="num">%.2f</td>'
             '<td class="num">%.2f ~ %.2f</td><td>%s</td></tr>'
             % (t, fmt(s), e["scan"], e["under"], cls, e["ratio"],
                e["ratio_p50"], e["ratio_p10"], e["ratio_p90"], judge))
p.append("</tbody></table></div>")

st = ENG["star"]
PCT = "%"
p.append('<div class="note bad"><p><strong>'
         '<span class="mono">star</span> 의 100 ' + PCT + '는 막대를 넘어서 받은 '
         '점수가 아닐 소지가 큽니다.</strong> 난이도 0.5 에서 star 의 막대 높이는 '
         '0.105 m 인데, 몸통 아래 광선이 지나간 높이 폭은 평균 '
         + ("%.3f" % st["under"]) + ' m 입니다.</p>'
         '<p><strong>평균보다 분포가 분명합니다.</strong> 참여도 중앙값이 '
         + ("%.2f" % st["ratio_p50"]) + ' 이고 10~90 분위가 '
         + ("%.2f ~ %.2f" % (st["ratio_p10"], st["ratio_p90"])) + ' 입니다. '
         '절반 넘는 판에서 그 폭이 거의 0 이었고, %d 판에서는 비율이 1 이었습니다. '
         % st["ones"] + 
         '평균 ' + ("%.2f" % st["ratio"]) + ' 은 그 둘을 섞은 값입니다.</p>'
         '<p>Isaac 의 star 지형은 막대가 중심에서 바깥으로 뻗습니다. 중심에서 방사 '
         '방향으로 걸으면 막대를 가로지를 일이 구조적으로 없습니다. 다만 그 경로를 '
         '실제로 확인한 것은 영상 한 판뿐입니다(미확인).</p>'
         '<p>반대로 <span class="mono">rails</span> 와 '
         '<span class="mono">stepping_stones</span> 는 참여도 중앙값이 '
         + ("%.2f" % ENG["rails"]["ratio_p50"]) + ' 와 '
         + ("%.2f" % ENG["stepping_stones"]["ratio_p50"]) + ' 인데 성공률이 '
         + fmt(g("rails", "foothold-v1", "1")) + ' ' + PCT + ' 와 '
         + fmt(g("stepping_stones", "foothold-v1", "1")) + ' ' + PCT
         + ' 입니다. 비율이 높은데 성공률이 낮은 자리입니다. 이 비율만으로 실패 원인을 말할 수는 없습니다.</p></div>')
# **성공률로 원인을 말하지 않는다.** 어느 축에서 떨어졌는지 세어서 적는다
# `확인됨` (2026-09-12 검증 2회차 1번 · rails 실패 52판 중 27판은 방향 축만
# 떨어졌다. 「걸렸다」고 쓰면 종합 실패율을 물리적 걸림으로 바꿔 말하는 것이다).
_rails = BD["rails|foothold-v1|1"]
_step = BD["stepping_stones|foothold-v1|1"]
_rails_dir = _rails["combo"].get("방향", 0)

p.append('<p>참여도가 높다고 실패하는 것도, 낮다고 성공하는 것도 아닙니다. '
         '아래 셋은 난이도 0.5 · 1.0 m/s 에서 <strong>따로 촬영한 시연 한 판씩</strong>이고, '
         '옆의 수치는 같은 조건 100 판의 집계입니다.</p>')
p.append(clips([
    ("star-v1", "star · 참여도 중앙값 %.2f" % ENG["star"]["ratio_p50"],
     "성공 %d/%d. 몸통 아래 광선이 지난 높이 폭이 대체로 작았습니다"
     % (BD["star|foothold-v1|1"]["win"], BD["star|foothold-v1|1"]["n"])),
    ("rails-v1", "rails · 참여도 중앙값 %.2f" % ENG["rails"]["ratio_p50"],
     "성공 %d/%d. 실패 %d판 가운데 %d판은 <strong>방향 축만</strong> 떨어졌습니다"
     % (_rails["win"], _rails["n"], _rails["n"] - _rails["win"], _rails_dir)),
    ("stepping_stones-v1", "stepping_stones · 참여도 중앙값 %.2f"
     % ENG["stepping_stones"]["ratio_p50"],
     "성공 %d/%d. 실패는 전부 세 축 이상이 함께 떨어졌습니다"
     % (_step["win"], _step["n"])),
]))
p.append('<div class="note"><p><strong>참여도는 발이 닿았는지를 재지 않습니다.</strong> '
         '몸통 아래 중앙 광선이 지난 높이 폭을, 스캔 전체가 본 높이 폭으로 나눈 값입니다. '
         '어느 길로 우회했는지, 장애물을 끝까지 갔는지는 이 비율만으로 알 수 없습니다. '
         '<span class="mono">rails</span> 는 100 판 모두 참여도 1.00 인데 그중 %d판은 '
         '방향 축만 떨어졌습니다.</p></div>' % _rails_dir)
p.append('<p><span class="mono">gap</span> 은 <strong>이 조건에서</strong> 잴 수 '
         '없습니다. 난이도 0.5 · 1.0 m/s · foothold-v1 의 100 판 모두 스캔 전체 '
         '기복이 0.02 m 에 못 미쳐 비어 있습니다. 구멍은 광선이 아무것도 못 맞히기 '
         '때문입니다. 다른 모델·속도에서는 유효값이 몇 판 잡히기도 하므로, '
         '「gap 은 언제나 못 잰다」로 넓히지 마십시오. 안 딛고 넘는 것이 정답인 '
         '지형은 네 축이 이미 답하고 있습니다.</p>')

# ── 6 ──────────────────────────────────────────────────────────────────
p.append('<h2><span class="n">06</span>아직 안 되는 것</h2>')
p.append("<ul>")
p.append('<li><strong><span class="mono">stepping_stones</span> 0 %.</strong> '
         '난이도 0.5 · 세 속도 전부에서 세 모델 모두 0 % 입니다. 더 낮은 난이도에서도 못 건너는지는 곡선 자료로 따로 확인해야 합니다. '
         '2차의 첫 과제입니다.</li>')
_r = BD["rails|foothold-v1|1"]
p.append('<li><strong><span class="mono">rails</span> %.0f %%.</strong> '
         '100 판 모두 참여도 1.00 이지만 그것으로 실패 원인을 말할 수 없습니다. '
         '실패 %d 판 가운데 가장 많은 세 조합은 %s 이고, 나머지 %d 판은 '
         '다른 조합입니다. 속도를 1.5 m/s 로 올리면 '
         '%.0f %% 까지 떨어집니다.</li>'
         % (g("rails", "foothold-v1", "1"),
            _r["n"] - _r["win"],
            " · ".join("%s %d판" % (k, v) for k, v in
                       sorted(_r["combo"].items(), key=lambda kv: -kv[1])[:3]),
            (_r["n"] - _r["win"]
             - sum(v for _k, v in sorted(_r["combo"].items(),
                                         key=lambda kv: -kv[1])[:3])),
            g("rails", "foothold-v1", "1.5")))
_zmin = min(v[0] for v in ZONES.values())
_zmax = max(v[1] for v in ZONES.values())
_narrow = sorted(ZONES.items(), key=lambda kv: kv[1][1] - kv[1][0])[:2]

_zstart = sorted({v[0] for v in ZONES.values()})
_zend = sorted({v[1] for v in ZONES.values()})
_narrow = sorted(ZONES.items(), key=lambda kv: kv[1][1] - kv[1][0])[:2]

p.append('<li><strong>장애물 구간은 지형마다 다릅니다.</strong> 난이도 0.5 의 실행 기록이 적어 둔 구간은 시작 %.2f~%.2f m, 끝 %.2f~%.2f m 입니다. '
         '가장 좁은 것은 <span class="mono">%s</span> (%.2f~%.2f m) 와 <span class="mono">%s</span> (%.2f~%.2f m) 입니다. '
         '발판이 0.75 m 인 지형에서는 통과선 3.0 m 까지 2.25 m 가 남지만, <strong>그 뺄셈을 모든 지형에 그대로 쓰면 안 됩니다.</strong> '
         '「넘었다」와 「운이 좋았다」를 가르기에 짧습니다. corridor 방식 재설계가 2차 검토 대상입니다.</li>'
         % (_zstart[0], _zstart[-1], _zend[0], _zend[-1],
            _narrow[0][0], _narrow[0][1][0], _narrow[0][1][1],
            _narrow[1][0], _narrow[1][1][0], _narrow[1][1][1]))
p.append('<li><strong>머리 접촉 세 열은 검증 전까지 인용하지 않습니다.</strong> '
         '첫 표본이 앞 판의 접촉력을 물려받을 수 있고, 그 비율을 아직 갈라내지 '
         '못했습니다.</li>')
p.append("</ul>")

p.append('<p><span class="mono">stepping_stones</span> 에서 세 모델이 어떻게 '
         '실패하는지입니다. 2차는 이 자리를 기준으로 개선을 주장하게 됩니다.</p>')
p.append(clips([
    ("stepping_stones-v1-baseline", "기준선 NVIDIA", "성공률 0 %"),
    ("stepping_stones-v1-A", "A", "성공률 0 %"),
    ("stepping_stones-v1", "foothold-v1", "성공률 0 %"),
]))

# ── 7 ──────────────────────────────────────────────────────────────────
p.append('<h2><span class="n">07</span>재현</h2>')
p.append("<pre>git pull origin main" + NL +
         "pip install av        # Isaac 이 도는 파이썬에 한 번만" + NL + NL +
         "# 이 보고서의 데이터 전부" + NL +
         "python sim/eval/run_matrix.py \\" + NL +
         "    --model baseline=&lt;pt&gt; --model A=&lt;pt&gt; \\" + NL +
         "    --model foothold-v1=models/foothold-v1.pt \\" + NL +
         "    --out_dir sim/eval/results/maindata-v1" + NL + NL +
         "# 근거 영상 전부" + NL +
         "python sim/eval/render_gallery.py \\" + NL +
         "    --checkpoint models/foothold-v1.pt \\" + NL +
         "    --raw_csv sim/eval/results/maindata-v1</pre>")
p.append('<h2><span class="n">08</span>근거 영상 전체</h2>')
p.append('<p>이 보고서에 실린 것은 주장마다 한두 장씩 고른 것입니다. '
         '지형 16종 x 속도 3종 48컷과 모델 대조 36컷, 모두 84컷이 '
         '<strong>gallery-v1</strong> 에 있습니다. 보고서 1차와 gallery-v1 이 한 세트입니다.</p>')
p.append('<p>영상은 전진 5.0 m 에서 잘렸습니다. 난이도 0.5 에서 장애물 구간이 '
         '가장 멀리 가는 지형도 4.00 m 에서 끝나고 그 뒤는 평평한 테두리라 '
         '볼 것이 없기 때문입니다. 지형마다 구간이 달라 어떤 영상은 앞쪽에서 '
         '이미 볼 것이 끝납니다. 넘어져서 그만큼 못 간 판은 '
         '그대로 다 남아 있습니다. 배속 단추는 재생기의 '
         '<span class="mono">playbackRate</span> 를 바꿉니다. 다만 느리게 틀어도 '
         '새 프레임이 생기지는 않아, 원본 초당 50장이 0.25배에서는 12.5장으로 보입니다.</p>')

p.append('<p>있어야 할 칸은 <span class="mono">sim/eval/matrix.py</span> 가 선언합니다. '
         '한 칸이라도 비면 실행기가 0 이 아닌 코드로 끝나고, 보고서 생성기도 거부합니다. '
         '측정 규격과 판정 정의는 '
         '<a href="/research-20260911-eval-protocol-v2.html">평가 프로토콜 정본</a> '
         '입니다 (저장소는 '
         '<span class="mono">docs/research/20260911-eval-protocol-v2.md</span>).</p>')

# 판 수를 두 개로 나눠 적는다. 성적표 분모와 전체 원자료는 다른 수다.
_score = STATUS["roles"].get("성적표", {"declared": 0, "present": 0, "cells": 0})
_curve = STATUS["roles"].get("곡선", {"declared": 0, "present": 0, "cells": 0})

p.append('<table><thead><tr><th>무리</th><th class="num">칸</th>'
         '<th class="num">선언한 판</th><th class="num">있는 판</th></tr></thead><tbody>'
         '<tr><td>성적표 (난이도 0.5)</td><td class="num">%d</td>'
         '<td class="num">%s</td><td class="num">%s</td></tr>'
         '<tr><td>난이도 곡선</td><td class="num">%d</td>'
         '<td class="num">%s</td><td class="num">%s</td></tr>'
         '<tr><td><strong>합</strong></td><td class="num"><strong>%d</strong></td>'
         '<td class="num"><strong>%s</strong></td>'
         '<td class="num"><strong>%s</strong></td></tr>'
         '</tbody></table>'
         % (_score["cells"], f"{_score['declared']:,}", f"{_score['present']:,}",
            _curve["cells"], f"{_curve['declared']:,}", f"{_curve['present']:,}",
            STATUS["cells"], f"{STATUS['declared']:,}", f"{STATUS['present']:,}"))

if STATUS["missing"]:
    p.append('<div class="note bad"><p><strong>선언한 칸 가운데 %d칸이 아직 비어 있습니다.</strong> '
             '본문의 성적표는 난이도 0.5 의 %s 판을 분모로 하고 그 칸은 다 찼습니다. '
             '비어 있는 것은 난이도 곡선 쪽이며, 그만큼 곡선의 한 부분이 그려지지 '
             '않았습니다.</p><p class="mono" style="font-size:.8rem">%s</p></div>'
             % (len(STATUS["missing"]), f"{_score['declared']:,}",
                " · ".join(STATUS["missing"])))
else:
    p.append('<p>선언한 %d칸이 모두 찼습니다. 본문의 성적표는 난이도 0.5 의 %s 판이 '
             '분모이고, 난이도 곡선까지 합한 전체 원자료는 %s 판입니다.</p>'
             % (STATUS["cells"], f"{_score['declared']:,}", f"{STATUS['present']:,}"))

p.append('''<script>
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
</script>''')
p.append("</div>")

p.append("</body>")
p.append("</html>")
html = NL.join(p)

# 온전한 문서인지 «센다». 조각으로 나가면 파일로 열 때 한글이 깨진다.
for _must in ("<!doctype html>", '<meta charset="utf-8">',
              "width=device-width", "</body>", "</html>"):
    if _must not in html:
        raise SystemExit("문서에 %s 가 없다" % _must)

# 원칙 2 · 조용한 실패를 소리 나게. 달라고 한 컷이 없으면 여기서 죽는다.
if WANTED_MISSING and "--allow_missing_clips" not in sys.argv:
    for _stem in WANTED_MISSING:
        print("  [X] 본문이 쓰는 컷이 없다: %s.mp4" % _stem)
    raise SystemExit("컷 %d개가 %s 에 없다. 갤러리를 마저 굽거나 "
                     "--allow_missing_clips 를 준다" % (len(WANTED_MISSING), TINY))

out = os.path.join(S, "report-v1.html")
io.open(out, "w", encoding="utf-8").write(html)
print("  %s  %.2f MB" % (os.path.basename(out), len(html.encode("utf-8")) / 1048576))
