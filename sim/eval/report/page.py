# -*- coding: utf-8 -*-
"""종합보고서 1차 · HTML. 수치는 report_numbers.json 에서만 읽는다.

분류: 운영
작성: Claude 세션 (오흥재 지시) · 2026-09-11 23:45
근거: maindata-v1 지형 16종 x 모델 3 x 속도 3 · 14,400 에피소드
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
SWEEP = D.get("sweep", {})  # (지형|난이도|속도) -> 성공률 %. 없으면 빈 표


_A = lambda t, d, v='1.0': SWEEP.get('A|%s|%s|%s' % (t, d, v))
_B = lambda t, d, v='1.0': SWEEP.get('B|%s|%s|%s' % (t, d, v))
_BL = lambda t, d, v='1.0': SWEEP.get('baseline|%s|%s|%s' % (t, d, v))
# ── 학습 설정 · 이 수치는 여기 «한 곳» 에만 있다 ──────────────────────
#   2026-09-15. 틈 폭을 고쳤는데 네 자리 중 한 자리만 고쳐져 있었다.
#   본문은 rng() 로 읽는다. 자리를 하나로 만들어 어긋날 수 없게 한다.
#   근거: 평가 기준 문서 `20260911-eval-protocol-v2.md` 모델 표 (모델마다
#   SHA-256 앞자리와 학습 시각까지 적혀 있다: A 54064c77 · B c7612aef).
#   2026-09-15 팀장 확정. 지형 «배합» 은 그 문서에도 없어 TRAIN_MIX 참조.
TRAIN = {
    'baseline': {'gap': None, 'iter': 1500},
    'A': {'gap': (0.05, 0.20), 'iter': 1500},
    'B': {'gap': (0.15, 0.40), 'iter': 1500},
}
TRAIN_MIX = ('gap', 0.1, 0.9)      # 더한 지형 · 그 비중 · 기존 험지 6종 몫


def rng(m):
    """그 모델이 학습한 틈 폭. 없으면 「없음」."""
    g = TRAIN[m]['gap']
    return '없음' if g is None else '%.2f ~ %.2f m' % g


def itr(m):
    """그 모델의 학습 반복 횟수."""
    return '{:,}'.format(TRAIN[m]['iter'])


_UNSEEN = ["gap", "pit", "rails", "stepping_stones", "floating_ring",
           "star", "wave", "discrete_obstacles", "repeated_boxes",
           "repeated_cylinders"]


def _avg(model, d, v):
    """그 모델 · 난이도 · 속도에서 미경험 지형 평균. 없는 칸은 빼고 센다."""
    vals = [SWEEP[k] for k in
            ("%s|%s|%s|%s" % (model, t, d, v) for t in _UNSEEN)
            if k in SWEEP]
    return sum(vals) / len(vals) if vals else 0.0


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
CURVE = io.open(os.path.join(S, "chart_curve.svg"), encoding="utf-8").read()


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
    raise SystemExit("갤러리 web/ 이 없다: %s. FOOTHOLD_GALLERY로 지정한다" % TINY)


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

# ★ 2026-09-14 신설. 포스터(첫 화면 그림)가 사는 곳.
#   `--link` 로 갤러리를 가리킬 때만 쓴다. 통째로 박는 모드에서는 페이지가
#   수 MB 로 불어나므로 안 건다.
#   `LINK` 는 `.../v1/web/` 꼴이라 형제 폴더 `posters/` 를 본다.
POSTERS = os.path.join(GALLERY, "posters")


def _poster_link(link):
    """영상 주소에서 포스터 주소를 만든다.

    ★ 짐작하지 않는다. 실제 배포본은 `/gallery/v1/clips/` 를 쓴다.
      처음에 `web/` 를 기준으로 잘랐다가 안 맞았다 · 로컬 폴더 이름(`web/`)과
      배포 주소(`clips/`)가 달랐다. **마지막 폴더 이름을 무엇이든 바꾼다.**
    """
    if not link:
        return ""
    s = link.rstrip("/")
    return s.rsplit("/", 1)[0] + "/posters/"


POSTER_LINK = _poster_link(LINK)

# 포스터가 없던 컷. 끝에서 «수만» 알린다. 없다고 죽이지는 않는다 ·
# 포스터는 있으면 좋은 것이지 본문이 달라고 한 것이 아니다.
POSTER_MISSING = []


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

    # ★ 2026-09-14 팀장 지적: 「갤러리에서는 썸네일이 보이는데 종합보고서는
    #   영상이 처음에 블랙으로 떠 있다」. 폰에서 특히 그렇다.
    #
    #   `preload="metadata"` 는 첫 프레임을 안 그린다. 갤러리는 포스터 이미지를
    #   따로 깔아서 멀쩡했고, 여기는 안 깔아서 검정이었다. 포스터는 **이미
    #   144장 다 있다** (`gallery/v1/posters/`). 걸기만 하면 된다.
    #
    #   이름은 «정확히» 맞춘다. `startswith` 로 고르면 `gap-v1` 이
    #   `gap-v1.5.jpg` 를 집는다 (실측으로 확인했다). 확장자만 바꾼다.
    poster = ''
    if LINK:
        cand = os.path.join(POSTERS, stem + '.jpg') if POSTERS else ''
        if cand and os.path.isfile(cand):
            poster = ' poster="%s"' % (POSTER_LINK + stem + '.jpg')
        else:
            POSTER_MISSING.append(stem)

    return ('<figure><video src="%s"%s controls '
            'preload="metadata" playsinline muted loop></video>'
            '<figcaption><span class="who">%s</span>%s%s</figcaption></figure>'
            % (src, poster, who, why, rate))


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
  --gnav-width:960px; --gnav-pad:24px;  /* 전역바가 이 폭을 따라온다 */
  /* porcelain · lieflat-charts color-presets.js · 차트와 같은 체계 */
  --ink:#081F5C; --ink-2:#2a3f74; --ink-3:#41527e; --line:#d6dced;
  --bg:#f7f2eb; --card:#ffffff; --accent:#1d6b58; --warn:#8a5b12; --bad:#a8341f;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  /* 전역바가 찾는 이름. 없으면 바가 자기 기본값으로 칠해 본문과 색이 어긋난다. */
  --paper:#f7f2eb; --paper-2:#eee7dc; --rule:#d6dced;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ink:#e6edfa; --ink-2:#b3c2de; --ink-3:#93a4c4; --line:#243254;
  --bg:#0b1020; --card:#141c30; --accent:#5fd0ae; --warn:#e0b55c; --bad:#f0836a;
  --paper:#0b1020; --paper-2:#141c30; --rule:#243254;
}}
:root[data-theme="dark"]{
  --ink:#e6edfa; --ink-2:#b3c2de; --ink-3:#93a4c4; --line:#243254;
  --bg:#0b1020; --card:#141c30; --accent:#5fd0ae; --warn:#e0b55c; --bad:#f0836a;
  --paper:#0b1020; --paper-2:#141c30; --rule:#243254;
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
/* ★ 2026-09-14 (#422). 첫머리「이번에 얻은 것」다섯 줄.
   번호를 크게 두어 읽는 사람이 «몇 개인지» 를 먼저 보게 한다.
   각 줄 끝의 «-> N» 이 근거 절이다. 약한 회색을 안 쓴다 (웹 규칙). */
ol.find{margin:1.1rem 0 0;padding:0;list-style:none;counter-reset:f}
ol.find li{counter-increment:f;position:relative;padding:.85rem 0 .85rem 2.6rem;
  border-top:1px solid var(--rule);line-height:1.75}
ol.find li:last-child{border-bottom:1px solid var(--rule)}
ol.find li::before{content:counter(f,decimal-leading-zero);position:absolute;
  left:0;top:.9rem;font:800 .78rem/1 var(--mono);color:var(--accent);
  letter-spacing:.04em}
ol.find b{color:var(--ink)}
.to{display:inline-block;margin-left:.4rem;font:700 .72rem/1 var(--mono);
  color:var(--ink-2);white-space:nowrap}
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
/* 서사 사슬. 번호가 «걸음 순서» 를 뜻하므로 번호를 크게 살린다.
   .find 는 나란한 발견이라 번호가 라벨이지만, 여기서는 번호가 뜻이다. */
ol.chain{list-style:none;counter-reset:ch;padding:0;margin:18px 0}
ol.chain li{counter-increment:ch;position:relative;padding:0 0 0 46px;
  margin:0 0 18px}
ol.chain li::before{content:counter(ch,decimal-leading-zero);
  position:absolute;left:0;top:1px;font-family:var(--mono,monospace);
  font-size:.82rem;font-weight:700;color:var(--dim);
  border:1px solid var(--rule);border-radius:99px;
  width:28px;height:28px;display:grid;place-items:center}
ol.chain li:not(:last-child)::after{content:"";position:absolute;
  left:13px;top:32px;bottom:-14px;width:1px;background:var(--rule)}
/* 첫 <b> 만 걸음 제목이다. 그냥 li>b 로 잡으면 본문 안의 강조까지
   블록이 되어 「겹치는 것이 0종 / 입니다」 처럼 줄이 끊긴다 (실측). */
ol.chain li>b:first-child{display:block;margin-bottom:3px}
figure svg{display:block;width:100%;height:auto}
/* 2026-09-14. svg 만 있고 img 가 없었다. 07 절 보상 지도가 1000 px 로
   그려져 912 px 짜리 상자에서 오른쪽 109 px 가 잘려 나갔다. 「막는다」의
   마지막 글자가 안 보였다. 같은 규칙이 사는 두 자리 중 한쪽만 있었던 것. */
figure img{display:block;width:100%;height:auto}
/* 영상 12개는 오늘은 안 넘친다. flex 가 눌러 주고 있을 뿐 묶는 규칙은
   없었다 (관문 9c 가 잡았다). 눌러 주는 쪽이 바뀌면 조용히 새니 묶는다. */
figure video{display:block;width:100%;height:auto}
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
    """site의 전역바를 가져온다.

    **없으면 웹에서 갤러리로 가는 길이 없다** `확인됨` (2026-09-12 · 127개
    페이지에 있는 전역바가 이 보고서에만 없었다. 팀장이 잡았다).

    전에는 `index.html` 에서 규칙을 **평면으로 베꼈다.** 그러면 `@media` 의
    중괄호가 풀려 안쪽 규칙이 조건 없이 적용된다. 그래서 밝은 화면인데
    **흰 로고**가 떴고, `--paper` 를 안 쓰는 이 페이지에서 **바가 투명**
    해졌다 `확인됨` (둘 다 2026-09-12 팀장 지적).

    이제 베끼지 않는다. `tools/gnav_extract.py` 가 만든 한 벌을 링크한다.
    머리 조각에는 테마 부팅 스크립트도 들어 있다. 그것이 없으면 표식이
    안 달려 **site 기본값(밝음)을 무시하고 어두운 화면으로 열린다.**
    """
    got = []

    for name in ("gnav.html", "gnav-head.html"):
        path = os.path.join(SITE_DIR, "assets", name)

        if not os.path.isfile(path):
            raise SystemExit("assets/%s가 없다. tools/gnav_extract.py를 "
                             "먼저 돌린다" % name)

        got.append(io.open(path, encoding="utf-8").read().strip())

    bar = re.sub(r'href="(?!/|https?:)([^"]+)"', r'href="/\1"', got[0])
    bar = bar.replace('src="assets/', 'src="/assets/')
    bar = bar.replace('class="on"', 'class=""')
    return bar, got[1]


NAV, NAV_HEAD = site_nav()

# **온전한 문서로 낸다.** 조각으로 내면 doctype 도 charset 도 뷰포트도 없다.
# 파일로 저장해 열면 한글이 깨지고 휴대폰에서 조판이 무너진다 `확인됨`
# (2026-09-04 에 PDF 로 같은 일을 겪었다).
p = ['<!doctype html>', '<html lang="ko">', "<head>", '<meta charset="utf-8">',
     '<meta name="viewport" content="width=device-width,initial-scale=1">',
     '<title>FOOTHOLD 종합보고서 1차</title>',
     '<meta name="description" content="기준선 NVIDIA vs A vs foothold-v1 · '
     '난이도 0.5 성적표 14,400 에피소드 · 전체 원자료 43,200 에피소드">',
     # 파비콘. 이 장은 `build.py` 가 굽는 페이지가 아니라서 전역 head 를
     # 안 받는다. 그래서 여기 직접 적는다 (배포 전 점검 [파비콘] 이 잡았다).
     '<link rel="icon" type="image/svg+xml" '
     'href="assets/brand/foothold-favicon.svg">',
     '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
     'family=IBM+Plex+Sans+KR:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">',
     "<style>%s</style>" % CSS, NAV_HEAD, "</head>", "<body>",
     NAV, '<div class="wrap">']

p.append('<div class="head">'
         '<p>분류: 보고</p>'
         '<p>작성: 오흥재 · 2026-09-11</p>'
         '<p>근거: 지형 16종 x 모델 3 x 속도 3 · %s 에피소드 · 측정 규격 2</p>'
         '<p>요지: foothold-v1은 기존 험지를 유지하면서 미경험 험지 gap의 성공률을 1 %%에서 100 %%로 올렸다</p>'
         '<p>상태: 검토 중</p></div>' % format(EPISODES, ","))

p.append("<h1>FOOTHOLD 종합보고서 1차</h1>")
p.append('<p class="lead">Unitree Go2 사족보행 정책을 미경험 험지에서 평가한 결과입니다. '
         '기준선(NVIDIA 공식 체크포인트), 중간 모델 A, 그리고 이번 배포 대상인 '
         'foothold-v1(모델 B)을 같은 조건에서 비교합니다.</p>')
# ★ 2026-09-15 astra 지적. 「미경험 험지」가 세 모델 모두에게 미경험인 것처럼
#   읽힌다. 그중 다섯은 A 와 v1 이 «학습에 넣은» 지형이다. 첫 등장에 밝힌다.
p.append('<div class="note">이 보고서에서 <b>「미경험 험지」</b>는 '
         '기준선(NVIDIA 공식 체크포인트)이 학습하지 않은 지형 10종을 뜻합니다. '
         '그중 다섯 종(<span class="mono">gap · pit · rails · '
         'stepping_stones · floating_ring</span>)은 <b>A와 foothold-v1의 학습에 '
         '포함했습니다.</b> 따라서 「미경험」은 기준선에만 해당하는 분류입니다.</div>')

# ── 0 · 이번에 한 일 (서사 사슬) ───────────────────────────────────────
# ★ 2026-09-15 팀장 지시: 「우선 우리가 학습 설계와 레시피를 소개해야할 것 같아
#   ... 전체 서사가 눈에 확 들어오고서 보고서형태의 흐름이 가면 좋을 것 같다」
#
#   맞다. 전에는 «결과» 다섯 줄로 시작했다. 결과는 «왜 그렇게 했나» 없이는
#   읽히지 않는다. 사슬을 먼저 놓고 그 뒤에 결과를 둔다.
#
#   각 칸의 수는 전부 아래 절에서 다시 나온다. 새로 만든 것이 없다.
p.append('<h2><span class="n">00</span>이번에 한 일</h2>')
p.append('<p>진행 과정은 다음 여섯 단계입니다. 각 단계의 근거는 연결된 절에서 설명합니다.</p>')

_A = lambda t, d, v='1.0': SWEEP.get('A|%s|%s|%s' % (t, d, v))
_B = lambda t, d, v='1.0': SWEEP.get('B|%s|%s|%s' % (t, d, v))
_BL = lambda t, d, v='1.0': SWEEP.get('baseline|%s|%s|%s' % (t, d, v))

_steps = [
    ('학습 지형에 구멍이 없었다',
     'NVIDIA 공식 체크포인트가 학습한 지형에는 구멍이 있는 지형이 없습니다 '
     '(<span class="mono">holes=False</span> · 코드에서 확인). '
     '평가에 쓴 신규 지형 10종은 <b>그 학습 지형에 하나도 들어 있지 않습니다.</b>', '02'),
    ('그래서 <span class="mono">gap</span>을 10 % 섞었다',
     '학습 지형에 <span class="mono">gap</span> <b>하나만</b> 비중 0.1로 더했습니다. '
     '기존 험지 6종이 나머지 0.9를 나눠 가집니다. '
     '<b>기존 험지의 성공률을 지키면서 틈만 새로 가르치기 위해서입니다.</b>', '03'),
    ('100 iteration만 먼저 돌려 가능성을 봤다',
     '사전학습 체크포인트를 불러온 뒤 학습 지형에 <span class="mono">gap</span>을 추가해 '
     '<b>학습 반복(iteration) 100회</b>만 더 돌렸습니다. 기존 험지 6종의 '
     '성공률이 유지되는지 먼저 확인한 것입니다. <b>그 결과를 바탕으로</b> '
     '학습 지형의 비중을 그대로 두고 <b>A와 B를 각각 1,500회 학습</b>했습니다.', '03'),
    ('그런데 학습한 틈 폭이 평가 조건보다 좁았다',
     '모델 <b>A</b>는 폭 ' + rng('A') + '의 틈에서 학습했습니다. '
     '기준 평가 조건(난이도 0.5)의 틈 폭은 <b>0.275 m</b>입니다. '
     'A의 <span class="mono">gap</span> 성공률은 난이도 0.3까지 100 %%, '
     '0.5에서 <b>%s %%</b>입니다. '
     '<b>평가의 틈 폭이 학습 범위를 벗어난 것이 실패 원인인지는 아직 확인하지 못했습니다.</b>', '07'),
    ('학습 범위를 평가 범위와 똑같이 맞췄다',
     '모델 <b>B</b>는 폭 ' + rng('B') + '의 틈에서 학습했습니다. 평가 하네스의 '
     '<span class="mono">gap_width_range</span>와 <b>같은 값</b>입니다. '
     'A와 B는 <b><span class="mono">gap_width_range</span> 한 줄만</b> 다릅니다.', '03'),
    ('B를 <span class="mono">foothold-v1</span>로 배포한다',
     '<b>명령 속도 1.0 m/s로 평가한</b> 난이도 0.1~1.0의 10개 조건 모두에서 '
     '<span class="mono">gap</span>의 종합 성공률이 <b>100 %</b>이고, '
     '기존 험지 6종에서도 성공률이 낮아진 지형은 없습니다. '
     '다른 속도는 08절에 따로 있습니다.', '05'),
]

p.append('<ol class="chain">')
for _i, (_t, _b, _to) in enumerate(_steps, 1):
    _body = _b
    if '%s %%' in _body:
        _body = _body % ('%.0f' % (_A('gap', '0.5') or 0))
    p.append('<li><b>%s</b><br>%s <span class="to">-> %s</span></li>'
             % (_t, _body, _to))
p.append('</ol>')

# ── 1 · 무엇을 얻었나 ─────────────────────────────────────────────────
# ★ 2026-09-15. 수치를 «규격 2» 스윕에서 다시 읽는다. 전에는 결함 규격으로 잰
#   `20260910-difficulty-sweep` 을 읽었고, 게다가 그것은 **NVIDIA 기준선** 숫자인데
#   모델을 안 밝히고 우리 정책 이야기 뒤에 붙였다. 둘이 한꺼번에 틀렸다.
#   관문 `tools/no_cite_guard.py` 가 이제 그 폴더를 읽으면 세운다.
p.append('<h2><span class="n">01</span>무엇을 얻었나</h2>')
p.append('<p>주요 결과는 다섯 가지입니다. 모두 측정 규격 2를 적용했고, '
         '모델과 평가 조건을 함께 적었습니다.</p>')

p.append('<ol class="find">')

p.append('<li><b>미경험 험지 <span class="mono">gap</span>의 성공률을 크게 높였습니다.</b> '
         '기준 평가 조건(난이도 0.5 · 명령 속도 1.0 m/s · 지형마다 100 에피소드)에서 '
         '성공률은 기준선 %.0f %%, foothold-v1 %.0f %%입니다. '
         '난이도를 1.0까지 올려도 <b>100 %%</b>입니다. '
         '<span class="to">-> 05 · 07</span></li>'
         % (g("gap", "baseline", "1"), g("gap", "foothold-v1", "1")))

p.append('<li><b>A의 학습 범위는 기준 평가의 틈 폭을 포함하지 않았습니다.</b> '
         'A(0.05~0.20 m)의 <span class="mono">gap</span> 성공률은 난이도 0.3까지 %.0f %%를 '
         '지키다가 0.5에서 <b>%.0f %%</b>로 떨어집니다. B(0.15~0.40 m)는 같은 조건에서 '
         '<b>%.0f %%</b>입니다. 평가의 틈은 0.275 m입니다. '
         '<span class="to">-> 03 · 07</span></li>'
         % (_A('gap', '0.3') or 0, _A('gap', '0.5') or 0, _B('gap', '0.5') or 0))

p.append('<li><b>기존 험지 6종 중 3종은 성공률이 올랐고 나머지 3종은 100 %%를 지켰습니다.</b> '
         '난이도 0.5 · 1.0 m/s에서 <span class="mono">boxes</span> %.0f -> %.0f %% · '
         '<span class="mono">pyramid_stairs_inv</span> %.0f -> %.0f %% · '
         '<span class="mono">random_rough</span> %.0f -> %.0f %%로 올랐고, '
         '나머지 셋은 100 %%를 지켰습니다. <b>기준선은 학습에 포함된 지형에서도 '
         '일부 성공률이 낮았습니다.</b> <span class="to">-> 05</span></li>'
         % (_BL('boxes', '0.5') or 0, _B('boxes', '0.5') or 0,
            _BL('pyramid_stairs_inv', '0.5') or 0, _B('pyramid_stairs_inv', '0.5') or 0,
            _BL('random_rough', '0.5') or 0, _B('random_rough', '0.5') or 0))

p.append('<li><b>1.5 m/s에서 기준선과 foothold-v1의 성공률 차이가 큽니다.</b> 미경험 10종 · 난이도 0.1에서 '
         '명령 속도를 1.5 m/s로 올리면 기준선의 평균 종합 성공률이 <b>%.0f %%</b>인데 '
         'foothold-v1은 <b>%.0f %%</b>를 지킵니다. '
         '<span class="to">-> 08</span></li>'
         % (_avg('baseline', '0.1', '1.5'), _avg('B', '0.1', '1.5')))

p.append('<li><b>성공률 숫자 하나로는 실패 양상이 안 드러납니다.</b> '
         '<span class="mono">rails</span>는 기준 평가 조건에서 %.0f %%인데, '
         '실패한 에피소드 중 상당수는 <b>방향 기준</b>만 충족하지 못했습니다. 개선 방향을 정하려면 네 평가 항목을 나눠 봐야 합니다. '
         '<span class="to">-> 09</span></li>'
         % g("rails", "foothold-v1", "1"))

p.append('</ol>')

# ── 1 ──────────────────────────────────────────────────────────────────
p.append('<h3>핵심 결과</h3>')

gap_base = g("gap", "baseline", "1")
gap_v1 = g("gap", "foothold-v1", "1")
p.append('<p><strong>foothold-v1은 기존 험지 6종의 성적을 유지하거나 끌어올리면서, '
         '미경험 험지 <span class="mono">gap</span>의 성공률을 (난이도 0.5 · 1.0 m/s · 100 에피소드 기준) %.0f %%에서 %.0f %%로 '
         '올렸습니다.</strong> 다만 <span class="mono">stepping_stones</span>는 세 모델 '
         '모두 0 %%이고, <span class="mono">rails</span>는 %.0f %%에 머뭅니다.</p>'
         % (gap_base, gap_v1, g("rails", "foothold-v1", "1")))

p.append('<p>아래는 그 주장의 근거입니다. 같은 지형, 같은 속도, 같은 난수에서 '
         '세 모델이 무엇을 하는지 보십시오.</p>')
p.append(clips([
    ("gap-v1-baseline", "기준선 NVIDIA",
     "이 조건의 평가 성공: %d/%d. <strong>별도로 촬영한 이 시연에서는</strong> 앞다리가 틈에 "
     "빠지고 몸통이 가장자리에 걸립니다. 100 에피소드가 모두 그렇다는 뜻은 아닙니다"
     % (BD["gap|baseline|1"]["win"], BD["gap|baseline|1"]["n"])),
    ("gap-v1-A", "A · 학습 틈 폭 0.05~0.20 m",
     "이 조건의 평가 성공: %d/%d. 평가 틈 폭은 0.275 m로 A의 학습 범위 밖입니다. "
     "학습 범위를 벗어난 틈 폭이 실패 원인인지는 아직 확인하지 못했습니다(미확인)"
     % (BD["gap|A|1"]["win"], BD["gap|A|1"]["n"])),
    ("gap-v1", "foothold-v1",
     "이 조건의 평가 성공: %d/%d. 이 시연에서는 뒷발이 가장자리를 딛고 앞발이 먼저 "
     "건넙니다" % (BD["gap|foothold-v1|1"]["win"], BD["gap|foothold-v1|1"]["n"])),
]))

# ── 2 ──────────────────────────────────────────────────────────────────
# ── 2 · 왜 gap 이었나 ─────────────────────────────────────────────────
p.append('<h2><span class="n">02</span>왜 <span class="mono">gap</span> 이었나</h2>')
p.append('<p><span class="mono">gap</span>을 고른 까닭은 '
         '<b>기준선의 학습 지형에 구멍이 없었기 때문</b>입니다.</p>')
p.append('<p>NVIDIA 공식 체크포인트가 학습한 지형은 여섯 종입니다. 코드에서 확인한 설정은 '
         '계단 두 종 모두 <span class="mono">holes=False</span>이고 '
         '<span class="mono">boxes</span>도 기본값이 <span class="mono">False</span>'
         '입니다. <b>학습 지형에는 바닥이 뚫린 구간이 없습니다.</b></p>')
p.append('<div class="note"><b>높이 스캔은 광선으로 바닥까지의 거리를 잽니다.</b> '
         '<span class="mono">gap</span> 평가에서는 일부 광선이 지형에 닿지 않았습니다. '
         '기준선의 학습 지형 여섯 종은 평가 10종과 <b>겹치는 것이 0종</b>입니다 '
         '(지형 «종류» 기준). <b>학습 중에도 같은 관측값이 나왔는지, 정책이 그 값을 '
         '어떻게 처리하는지는 확인하지 못했습니다.</b></div>')
p.append('<p>이번에는 대응 방법으로 구멍이 있는 지형 '
         '(<span class="mono">gap</span>)을 학습에 추가했습니다.</p>')

# ── 3 · 레시피 ────────────────────────────────────────────────────────
p.append('<h2><span class="n">03</span>레시피 · A와 B는 한 줄만 다릅니다</h2>')
p.append('<p class="prov"><b>학습 설정 전체를 전수 감사했습니다.</b> 팀장이 직접 돌린 '
         '기준선(2026-08-11 · AI-WS01 · <span class="mono">resume false</span> · '
         '1,500 iteration · seed 42)과 임석헌 원본'
         '(<span class="mono">0909_nvidia_gap_v3_seed42_iter900</span> · NAS 백업)을 '
         'YAML 키 단위로 맞대어 보았습니다(650 대 674). '
         '기준선에만 있고 석헌 쪽에 없는 항목은 <b>0개</b>입니다. '
         '<span class="mono">2026-09-18 실측</span></p>')
p.append('<p>사전학습 체크포인트는 <b>기존 험지 6종</b>만 배운 상태입니다. 거기서 '
         '<b>값 17개를 바꾸고 2블록을 더했습니다.</b> 그동안 이 절은 '
         '<span class="mono">gap</span>을 <span class="mono">proportion 0.1</span>로 '
         '더했다는 것만 적고 있었는데, 실제로 바뀐 것은 그보다 많습니다. '
         '<b>계획 단계에서는 실패 5종을 모두 넣는 안이었지만, 실제로 돌린 것은 '
         'gap 하나입니다.</b></p>')
p.append('<div class="tw"><table><thead><tr>'
         '<th>묶음</th><th>항목</th><th>NVIDIA 기본</th><th>foothold-v1</th>'
         '</tr></thead><tbody>'
         '<tr><td><b>명령 6</b></td><td class="mono">lin_vel_x</td>'
         '<td class="mono">(-1.0, 1.0)</td><td class="mono"><b>(0.5, 1.5)</b></td></tr>'
         '<tr><td></td><td class="mono">lin_vel_y</td><td class="mono">(-1.0, 1.0)</td>'
         '<td class="mono"><b>(0.0, 0.0)</b></td></tr>'
         '<tr><td></td><td class="mono">ang_vel_z</td><td class="mono">(-1.0, 1.0)</td>'
         '<td class="mono"><b>(0.0, 0.0)</b></td></tr>'
         '<tr><td></td><td class="mono">heading_command</td><td class="mono">True</td>'
         '<td class="mono"><b>False</b></td></tr>'
         '<tr><td></td><td class="mono">rel_heading_envs</td><td class="mono">1.0</td>'
         '<td class="mono"><b>0.0</b></td></tr>'
         '<tr><td></td><td class="mono">rel_standing_envs</td><td class="mono">0.02</td>'
         '<td class="mono"><b>0.0</b></td></tr>'
         '<tr><td><b>리셋 3</b></td><td class="mono">pose_range.yaw</td>'
         '<td class="mono">(-3.14, 3.14)</td>'
         '<td class="mono"><b>(-0.05, 0.05)</b></td></tr>'
         '<tr><td></td><td class="mono">pose_range.x</td><td class="mono">(-0.5, 0.5)</td>'
         '<td class="mono"><b>(-0.1, 0.1)</b></td></tr>'
         '<tr><td></td><td class="mono">pose_range.y</td><td class="mono">(-0.5, 0.5)</td>'
         '<td class="mono"><b>(-0.2, 0.2)</b></td></tr>'
         '<tr><td><b>관측 1</b></td><td class="mono">height_scan.func</td>'
         '<td class="mono">height_scan</td>'
         '<td class="mono"><b>height_scan_with_gap</b></td></tr>'
         '<tr><td><b>커리큘럼 1</b></td><td class="mono">max_init_terrain_level</td>'
         '<td class="mono">5</td><td class="mono"><b>2</b></td></tr>'
         '<tr><td><b>지형 비율 6</b></td>'
         '<td class="mono">pyramid_stairs 외 3종</td><td class="mono">0.2</td>'
         '<td class="mono"><b>0.18</b></td></tr>'
         '<tr><td></td><td class="mono">hf_pyramid_slope 외 1종</td>'
         '<td class="mono">0.1</td><td class="mono"><b>0.09</b></td></tr>'
         '</tbody></table></div>')
p.append('<p class="cap">값이 다른 17개입니다. 더한 2블록은 '
         '<span class="mono">forward_gap</span>(proportion 0.1 · 접근거리 1.5 · '
         '슬래브 두께 1.0)과 <span class="mono">fell_below_terrain</span> '
         '종료항(상대높이 -3.0)입니다. <b>보상 11항 · 물리 · PhysX · 액추에이터 · '
         '<span class="mono">episode_length_s</span> 20 · '
         '<span class="mono">num_envs</span> 4096 · seed 42는 하나도 안 바뀌었습니다.</b></p>')
p.append('<div class="note"><b>이 17개 가운데 9개가 「전진 전용」 제약입니다.</b> '
         '명령 6개와 리셋 3개가 함께 걸려, 학습 중에 로봇은 '
         '<b>앞으로만 0.5 ~ 1.5 m/s로 걷는 상황</b>만 겪었습니다. '
         '제자리에 서거나, 천천히 가거나, 돌거나, 옆으로 가는 명령은 '
         '<b>한 번도 주어지지 않았습니다.</b> '
         '이것은 임석헌의 레시피가 원래 그랬던 것이고 재현 과정에서 생긴 차이가 '
         '아닙니다. 무엇을 잃었는지는 <b>11절</b>에 적었습니다.</div>')
p.append('<p>먼저 학습을 <b>100회</b> 반복해 기존 험지의 성공률이 유지되는지 확인했고, '
         '그 뒤 1,500 iteration으로 두 차례 돌렸습니다.</p>')
p.append('<div class="tw"><table><thead><tr>'
         '<th>모델</th><th>학습한 틈 폭</th><th>iteration</th>'
         '<th class="num">gap 난이도 0.5</th><th class="num">gap 난이도 1.0</th>'
         '</tr></thead><tbody>'
         '<tr><td class="mono">기준선 NVIDIA</td><td>%s</td>'
         '<td class="num">%s</td>'
         '<td class="num">%.0f %%</td><td class="num">%.0f %%</td></tr>'
         '<tr><td class="mono">A</td><td>%s</td><td class="num">%s</td>'
         '<td class="num">%.0f %%</td><td class="num">%.0f %%</td></tr>'
         '<tr><td class="mono">B = foothold-v1</td><td><b>%s</b></td>'
         '<td class="num">%s</td>'
         '<td class="num"><b>%.0f %%</b></td><td class="num"><b>%.0f %%</b></td></tr>'
         '</tbody></table></div>'
         % (rng('baseline'), itr('baseline'),
            _BL('gap', '0.5') or 0, _BL('gap', '1.0') or 0,
            rng('A'), itr('A'),
            _A('gap', '0.5') or 0, _A('gap', '1.0') or 0,
            rng('B'), itr('B'),
            _B('gap', '0.5') or 0, _B('gap', '1.0') or 0))
p.append('<p class="cap">gap의 종합 성공률 · 명령 속도 1.0 m/s · '
         '조건마다 100 에피소드 · 규격 2.</p>')
# ★ 2026-09-15 팀장 지시: 「도식화, 곡선 등 추가되어야하는 부분이 있다면」.
#   이야기의 척추가 표로만 있었다. 두 범위와 한 점의 관계는 «자 위에» 놓아야
#   한눈에 들어온다. `tools/make_range_fig.py` 가 굽는다 (자기시험 8/8).
p.append('<figure class="mdimg"><img src="assets/visual/eval-v2-range.svg" '
         'alt="A와 B가 학습한 틈 폭 범위를 평가의 틈 범위와 한 자에 놓은 그림" '
         'loading="lazy">'
         '<figcaption>그림 · A와 B의 학습 틈 폭 범위와 기준 평가의 틈 폭을 같은 눈금에 '
         '표시했습니다. A가 학습한 최대 틈 폭은 0.20 m로, 기준 평가의 0.275 m보다 '
         '0.075 m 좁습니다</figcaption></figure>')
p.append('<div class="note"><b>A와 B는 둘 다 NVIDIA 공식 체크포인트에서 '
         '각각 출발했습니다.</b> A를 이어받아 B를 학습한 것이 아닙니다. '
         '두 모델의 차이는 <span class="mono">gap_width_range</span> '
         '<b>한 줄뿐이고</b> 나머지 학습 설정은 같습니다.'
         '<br>두 모델 모두 <b>워크스테이션 AI-WS01에서 직접 학습</b>했습니다. '
         'A는 임석헌의 학습 방식을 그대로 재현한 것이고, B는 학습 틈 폭 범위를 '
         '평가 기준과 같게 넓혀 같은 조건으로 1,500회 학습한 것입니다. '
         '<span class="mono">팀장 확인</span>'
         '<br><b>「그대로 재현했다」는 이제 실측으로 확인됐습니다.</b> '
         '팀장 기준선과 임석헌 원본을 YAML 키 단위로 전수 대조한 결과 '
         '기준선에만 있고 석헌 쪽에 없는 항목이 <b>0개</b>였습니다. '
         '재현에 오류는 없었고, <b>레시피 자체가 전진 전용이었습니다.</b>'
         '<br>다만 <b>출발 구조는 다릅니다.</b> 임석헌 쪽은 '
         '100 → 500 → 900회로 <b>이어붙인 누적 1,500회</b>이고, '
         'A와 B는 NVIDIA에서 <b>각각 한 번에 1,500회</b>입니다. '
         '<a href="https://github.com/foothold-project/foothold-lab/issues/428">#428</a>'
         '에 계보를 적어 두었습니다.'
         '<br><b>「NVIDIA에서 출발했다」도 파일을 열어 확인했습니다.</b> '
         '학습이 이어받은 <span class="mono">nvidia_pretrained.pt</span>는 '
         '공식 <span class="mono">checkpoint.pt</span>와 파일이 같지 않습니다'
         '(<span class="mono">1891ab2b</span> 대 <span class="mono">f2aa77bf</span> · '
         '217바이트 차이). 그래서 열어 보니 <b>가중치 17개가 하나도 빠짐없이 같고</b> '
         '<span class="mono">optimizer_state_dict</span>와 '
         '<span class="mono">infos</span>도 같았습니다. '
         '<b>다른 것은 <span class="mono">iter</span> 값 하나뿐입니다(1499에서 0).</b> '
         '반복 횟수만 0으로 되감은 같은 가중치라는 뜻입니다. '
         '<span class="mono">2026-09-18 실측</span></div>')
p.append('<p><b>왜 범위를 바꿨나.</b> 평가 하네스에 설정된 틈 폭 범위는 '
         '<span class="mono">gap_width_range=(0.15, 0.40)</span>이고, '
         '기준 평가 조건인 난이도 0.5에서 실제 틈은 <b>0.275 m</b>입니다. '
         'A가 학습한 최대 틈 폭은 0.20 m이므로 <b>기준 평가의 틈 폭은 A의 학습 범위 밖입니다.</b> '
         'B는 학습 범위를 평가 범위와 <b>같게</b> 두었습니다. '
         '그 한 줄 말고 <b>나머지 학습 설정은 A와 완전히 같습니다.</b></p>')

p.append('<h2><span class="n">04</span>비교 대상</h2>')
p.append('<div class="tw"><table><thead><tr><th>이름</th><th>무엇인가</th>'
         '<th>학습한 틈 폭</th><th>출처</th></tr></thead><tbody>'
         '<tr><td class="mono">기준선 NVIDIA</td><td>Isaac Lab 공식 Go2 험지 체크포인트</td>'
         '<td class="mono">없음</td><td class="mono">.pretrained_checkpoints</td></tr>'
         '<tr><td class="mono">A</td><td>기존 험지 6종 재학습 · 틈 학습 추가</td>'
         '<td class="mono">' + rng('A') + '</td>'
         '<td class="mono">model_1500.pt</td></tr>'
         '<tr><td class="mono">foothold-v1</td><td>틈 폭을 넓혀 재학습</td>'
         '<td class="mono">' + rng('B') + '</td>'
         '<td class="mono">models/foothold-v1.pt</td></tr>'
         '</tbody></table></div>')
p.append('<p class="cap">A와 B의 <b>학습한 틈 폭</b>은 팀장 확인이 근거입니다. 실행 당시 설정은 '
         '<a href="https://github.com/foothold-project/foothold-lab/issues/428">#428</a>에서 받는 중입니다.</p>')
p.append('<p><b>기준 성적표</b>는 세 모델을 같은 평가 하네스 · 같은 난수(seed 42) · '
         '난이도 0.5 · 명령 속도 1.0 m/s에서 비교한 것입니다. 지형마다 100 에피소드입니다. '
         '다른 속도의 기준 평가는 05절에, 난이도별 결과는 07절에, '
         '난이도 0.1의 속도 비교는 08절에 있습니다.</p>')

# ── 3 ──────────────────────────────────────────────────────────────────
p.append('<h2><span class="n">05</span>성적표</h2>')
p.append('<p>난이도 0.5, 명령 속도 1.0 m/s, 지형마다 100 에피소드에서의 성공률입니다. '
         '생존 · 전진 · 속도추종 · 방향의 네 평가 기준을 모두 충족해야 성공으로 판정합니다.</p>')
p.append('<div class="note"><b>이 표의 모든 수치는 '
         '「0.5 ~ 1.5 m/s 직진」 조건에서 잰 것입니다.</b> '
         'foothold-v1이 학습한 명령 범위가 그 구간뿐이고(03절), '
         '평가 하네스도 같은 구간만 잽니다. '
         '<b>정지 · 저속(0.5 m/s 미만) · 제자리 회전 · 횡이동은 이 표에 들어 있지 않습니다.</b> '
         '범용 보행 성능이 아니라 <b>전진 조건에서의 성능</b>으로 읽어 주십시오.</div>')
p.append('<figure>%s<figcaption>지형 16종 x 모델 3 · 난이도 0.5 · 1.0 m/s · '
         '지형마다 100 에피소드. 칸 안의 수가 성공률이고 진할수록 높습니다.</figcaption></figure>'
         % MATRIX)

p.append("<h3>속도별 전체 결과</h3>")
p.append('<p class="cap">난이도 0.5 · 명령 속도 m/s · 종합 성공률 % · 지형마다 100 에피소드.</p>')
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
p.append('<h2><span class="n">06</span>무엇이 달라졌나</h2>')

p.append("<h3>기존 험지의 성공률은 유지하거나 높였습니다</h3>")
p.append('<div class="tw"><table><thead><tr><th>지형 집합</th><th>속도</th>'
         '<th class="num">기준선</th><th class="num">A</th>'
         '<th class="num">foothold-v1</th><th class="num">기준선 대비 (%p)</th>'
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
p.append('<p>각 지형 집합의 평균 종합 성공률입니다. 기존 험지 6종에서 foothold-v1은 세 속도 모두 '
         '기준선을 웃돕니다. 특히 1.5 m/s에서 기준선은 평균 %.1f %%인데 '
         'foothold-v1은 %.1f %%입니다.</p>'
         % (avg("rough6", "baseline", "1.5"), avg("rough6", "foothold-v1", "1.5")))

p.append("<h3>기준선의 1.5 m/s 실패는 속도추종 축에 몰려 있습니다</h3>")
p.append('<p>명령 속도 1.5 m/s에서 기준선이 실패한 각 에피소드를, '
         '<strong>충족하지 못한 평가 항목의 조합</strong>에 따라 분류했습니다. '
         '축별 합계로는 어느 에피소드가 어느 항목을 못 채웠는지 알 수 없어, 각 에피소드의 네 항목을 '
         '모두 보고 분류했습니다.</p>')

bad4 = [(t, AXES[(t, "baseline")]) for t in TERR
        if (t, "baseline") in AXES and AXES[(t, "baseline")]["failed"] > 0]

p.append('<div class="tw"><table><thead><tr><th>지형</th><th class="num">실패 에피소드</th>'
         '<th class="num">속도추종만</th><th class="num">속도추종+1축</th>'
         '<th class="num">속도추종+2축 이상</th><th class="num">속도추종 통과 · 다른 항목 실패</th>'
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

p.append('<p>난이도 0.5, 지형마다 100 에피소드입니다. 실패한 %d 에피소드 가운데 '
         '<strong>에피소드 %d개(%.0f %%)는 속도추종 기준만 충족하지 못했습니다.</strong> '
         '나머지 세 축은 통과했다는 뜻이고, 그 에피소드에서 로봇은 넘어지지 않고 '
         '통과선도 넘었습니다. <b>속도추종 기준은 평면 평균 오차 0.25 m/s이고 '
         '이 오차에는 전후 방향뿐 아니라 좌우 방향 오차도 들어갑니다.</b> 그래서 이 항목의 탈락을 «명령보다 '
         '느리게 갔다»로 읽으면 안 됩니다. 잰 것은 오차가 한계를 넘었다는 '
         '점입니다.</p>'
         % (sum_failed, sum_only, 100.0 * sum_only / sum_failed))
# 네 갈래를 «다» 적는다. 합이 실패 에피소드 수와 맞는 것이 보여야 한다.
# 「두 축 이상」은 속도추종을 포함해 세는지 아닌지가 중의적이라 쓰지 않는다.
p.append('<p>나머지 %d 에피소드는 이렇게 갈립니다. '
         '속도추종 <strong>외에 다른 항목 하나도</strong> 충족하지 못한 에피소드가 %d, '
         '<strong>두 축 이상이 더</strong> 떨어진 에피소드가 %d입니다. '
         '속도추종 기준을 충족했지만 다른 기준 때문에 실패한 에피소드는 %d입니다. '
         '네 범주를 더하면 %d로 전체 실패 에피소드 수와 같습니다.</p>'
         % (sum_failed - sum_only, sum_one, sum_many, sum_other,
            sum_only + sum_one + sum_many + sum_other))
p.append('<p>두 축 이상이 더 떨어진 %d 에피소드는 '
         '<span class="mono">floating_ring</span> · '
         '<span class="mono">stepping_stones</span> · <span class="mono">gap</span> · '
         '<span class="mono">pyramid_stairs_inv</span>에 몰려 있고, '
         '그 지형에서는 실제로 넘어지거나 통과선까지 못 갔습니다.</p>' % sum_many)
p.append('<div class="note"><p><strong>이 표를 「기준선이 고속 험지에서 무너진다」로 '
         '읽으면 과장입니다.</strong> 대부분은 생존 · 전진 · 방향을 통과하고 '
         '속도추종 축에서만 떨어집니다. <b>이 표만으로는 속도 부족과 좌우 오차의 '
         '몫을 가를 수 없습니다.</b> '
         '<strong>기준선의 실패 에피소드는 모두 속도추종 축에서도 떨어졌습니다.</strong> '
         'foothold-v1도 <strong>모든 에피소드에서 이 축을 통과하지는 않습니다.</strong> '
         '같은 조건에서 속도추종 축을 통과한 에피소드가 %s / %s이고, '
         '<span class="mono">stepping_stones</span>는 %d/%d, '
         '<span class="mono">rails</span>는 %d/%d입니다.</p>'
         '<p>이 결과는 시뮬레이션에서 얻었습니다. 실제 로봇에서도 같은 결과가 나오는지는 '
         '재보지 않았습니다(미확인).</p></div>'
         % (f"{TR15['pass']:,}", f"{TR15['n']:,}",
            TR15["per"]["stepping_stones"][0], TR15["per"]["stepping_stones"][1],
            TR15["per"]["rails"][0], TR15["per"]["rails"][1]))

p.append('<p>같은 지형(<span class="mono">wave</span>)을 1.5 m/s 명령으로 걷는 장면입니다. '
         '<strong>셋 다 넘어지지 않습니다.</strong> 기준선 시연의 trace를 평가 방식으로 '
         '다시 계산하면 평면 평균 오차가 기준을 벗어나 '
         '속도추종 기준을 못 채웁니다.</p>')
p.append('<div class="note"><p><strong>영상은 평가 에피소드 자체가 아닙니다.</strong> '
         '같은 체크포인트·지형·난이도·난수로 <strong>따로 촬영한 한 에피소드</strong>이고, '
         '성적표의 100 에피소드 중 하나를 꺼낸 것이 아닙니다. 옆의 성공률은 그 자리의 '
         '100 에피소드 집계이고, 영상은 같은 조건에서 로봇이 무엇을 하는지 보여 줍니다.</p>'
         '<p><strong>HUD의 추종 표시는 평가의 속도추종 판정과 다른 계산입니다.</strong> '
         'HUD는 그 시점까지의 <strong>전후 방향</strong> 오차 '
         '<span class="mono">abs(vx - 명령속도)</span>의 누적 평균을 보여 줍니다. '
         '평가는 전후와 좌우를 합친 <strong>평면</strong> 오차를 누적합니다. '
         '판정 한계 0.25 m/s를 사이에 두고 갈리기도 합니다. 기준선 1.5 m/s '
         '시연 세 편의 trace를 다시 재 보면 전후 오차는 0.18~0.24로 한계 안이고 '
         '같은 표본의 평면 오차는 0.25~0.30으로 한계 밖입니다 '
         '(<span class="mono">repeated_boxes</span> · '
         '<span class="mono">repeated_cylinders</span> · '
         '<span class="mono">wave</span>). '
         '<strong>HUD를 보고 판정을 역산하지 마십시오.</strong></p>'
         '<p>영상은 %s 초당 %s장이고, 지형이 끝나는 자리까지만 잘랐습니다. '
         '초당 장수는 임의값이 아니라 <strong>정책이 결정을 내리는 주기</strong>입니다 '
         '(물리 200 Hz · 4스텝에 결정 1번 · 결정 1번에 프레임 1장).</p></div>'
         % (VIDEO_SIZE, VIDEO_FPS))
p.append(clips([
    ("wave-v1.5-baseline", "기준선 NVIDIA · 1.5 m/s 명령",
     "종합 0 %. 생존 100 · 전진 100 · <strong>속도추종 0</strong>. 넘어지지 않았고 평면 속도 오차가 한계를 넘었습니다"),
    ("wave-v1.5-A", "A · 1.5 m/s 명령", "종합 100 %"),
    ("wave-v1.5", "foothold-v1 · 1.5 m/s 명령", ("종합 성공 %d/%d. 속도추종 기준인 평면 평균 오차 0.25 m/s 이내를 "
      "100 에피소드 모두 통과했습니다. 명령 속도를 정확히 낸다는 뜻은 아닙니다"
      % (BD["wave|foothold-v1|1.5"]["win"], BD["wave|foothold-v1|1.5"]["n"]))),
]))

# ── 5 ──────────────────────────────────────────────────────────────────
# ── 난이도 곡선 ─────────────────────────────────────────────────────
#
# **한 점만 보면 「어디서 무너지나」를 못 본다.** 성적표는 난이도 0.5 한 칸이라
# 기준선이 거기서 50 % 라는 것만 말한다. 곡선은 그 앞뒤를 말한다.
p.append('<h2><span class="n">07</span>난이도를 올리면 어떻게 되나</h2>')
p.append('<p>지금까지는 난이도 <strong>0.5</strong> 한 칸만 봤습니다. 그 한 칸은 '
         '「지금 어느 쪽이 낫나」는 말해 주지만 <strong>어느 난이도부터 떨어지나</strong>는 '
         '말해 주지 않습니다. 미경험 험지 10종을 난이도 0.1부터 1.0까지 '
         '열 단으로 잰 것이 아래입니다.</p>')
p.append('<figure>%s<figcaption>각 점은 미경험 험지 10종의 <b>평균</b> 종합 성공률입니다. '
         '지형마다 100 에피소드라 한 점에 1,000 에피소드가 들어갑니다. '
         '명령 속도 1.0 m/s · 규격 2. 점은 <strong>실제 측정값</strong>이고 '
         '선은 그 점을 이은 것입니다. 잰 적 없는 구간으로 늘이지 않았습니다. '
         '자료는 <span class="mono">20260911-v3-fixedscan</span>이고, 규격은 '
         '폴더 이름이 아니라 각 실행의 '
         '<span class="mono">height_scan_miss_value</span>가 1.0인지 확인해 측정 규격을 구분했습니다.'
         '</figcaption></figure>' % CURVE)
p.append('<p>기준선은 난이도가 오를수록 <strong>76 %에서 37 %로</strong> 내려갑니다. '
         'foothold-v1은 <strong>90 %에서 77 %</strong>로, 열 단을 다 올려도 '
         '기준선의 가장 쉬운 칸(난이도 0.1 · 76 %)보다 높습니다. A는 그 사이입니다.</p>')
p.append('<div class="note"><b>이 곡선을 읽을 때 조심할 것 둘.</b>'
         '<br>하나 · <span class="mono">floating_ring</span>은 난이도가 오르면 '
         '고리가 낮아져 장애물의 <strong>종류가 바뀝니다</strong>. 이 지형만은 '
         '오른쪽이 더 어렵다는 뜻이 아닙니다.'
         '<br>둘 · 이것은 <strong>미경험 험지 열 종의 평균</strong>입니다. '
         '아래 표는 그중 다섯 종을 골라 다섯 난이도만 발췌한 것입니다.</div>')

# ── 지형별 난이도 축 ───────────────────────────────────────────────────
# ★ 2026-09-14 (#422). 전에는 「지형 하나하나는 평가 정본 2부에 있습니다」로
#   넘겼다. 팀장 지시대로 «발견» 은 여기서 답한다. 넘기면 아무도 안 따라간다.
#   수는 스윕 원자료에서 읽는다. 손으로 안 박는다.
if SWEEP:
    _T = ["gap", "pit", "rails", "floating_ring", "stepping_stones"]
    _D = ["0.1", "0.3", "0.5", "0.7", "1.0"]
    _MM = [("baseline", "기준선"), ("A", "A"), ("B", "v1")]
    _rows = ""
    for _t in _T:
        for _mi, (_m, _ml) in enumerate(_MM):
            _c = "".join(
                '<td class="num">%s</td>'
                % ("%.0f" % SWEEP["%s|%s|%s|1.0" % (_m, _t, _d)]
                   if ("%s|%s|%s|1.0" % (_m, _t, _d)) in SWEEP else "·")
                for _d in _D)
            # rowspan 을 안 쓴다. 관문 [4a] 가 줄마다 칸 수를 세는데
            # rowspan 은 줄마다 칸이 달라져 어긋난 것처럼 보인다.
            _rows += '<tr><td class="mono">%s</td><td>%s</td>%s</tr>' % (_t, _ml, _c)
    # ★ 2026-09-15 astra 지적: 이 표의 자료가 09절 재현 회계(43,200)에
    #   안 들어 있다. 읽는 사람은 같은 자료로 여긴다. 출처를 밝힌다.
    p.append('<p><b>지형마다 성공률이 떨어지는 난이도가 다르고, 모델마다 그 난이도가 옮겨갑니다.</b> '
             '규격 2 · 1.0 m/s · 칸마다 100 에피소드 · 단위 %.</p>')
    p.append('<div class="note">이 표와 위 곡선은 '
             '<span class="mono">20260911-v3-fixedscan</span>에서 옵니다. '
             '전체 조합은 3 x 16 x 10 x 3 = 1,440칸입니다. 그중 <b>954칸 95,400 에피소드</b>를 '
             '쟀습니다. 미경험 10종은 난이도 10칸을 다 재고(900칸), 기존 험지 6종은 '
             '난이도 0.5 한 칸만 쟀기 때문입니다(54칸). '
             '<b>13절 집계표의 43,200 과는 다른 자료</b>이니 더하지 마십시오. '
             '기준 성적표(난이도 0.5 · 1.0 m/s)는 16종 x 3모델 x 100 = <b>4,800 에피소드</b>이고, '
             '세 속도를 합치면 14,400입니다. 각 성공률의 분모는 100 에피소드입니다. '
             '13절의 43,200은 그 평가와 별도 난이도 평가를 합친 집계입니다.</div>')
    p.append('<div class="tw"><table class="wide"><thead><tr>'
             '<th>지형</th><th>모델</th>%s</tr></thead><tbody>%s</tbody></table></div>'
             % ("".join('<th class="num">난이도 %s</th>' % _d for _d in _D), _rows))
    p.append('<p><b><span class="mono">gap</span>에서 A와 foothold-v1의 차이가 뚜렷합니다.</b> '
             '기준선은 가장 쉬운 칸에서도 %.0f %%이고, A는 0.3까지 버티다 '
             '0.5에서 %.0f %%로 떨어지고, v1은 난이도 1.0까지 %.0f %%입니다. '
             'A가 학습한 최대 틈이 0.20 m이고 난이도 0.5의 틈이 0.275 m 라 '
             '<b>A는 평가의 틈 폭을 학습에서 본 적이 없습니다.</b></p>'
             % (_BL("gap", "0.1") or 0, _A("gap", "0.5") or 0, _B("gap", "1.0") or 0))
    p.append('<p><span class="mono">floating_ring</span>은 거꾸로 갑니다. '
             '이 지형은 <b>난이도 설정값이 커질수록 고리가 낮아집니다.</b> '
             '그래서 설정값이 오른 것을 «더 어려워졌다»로 읽을 수 없습니다. '
             '그것이 성공률 상승의 원인인지까지는 확인하지 않았습니다.</p>')
    p.append('<div class="note"><b><span class="mono">stepping_stones</span>만 '
             '안 열렸습니다.</b> 1.0 m/s에서 난이도 0.1은 기준선 58 · A 88 · B 99 %로 '
             '올랐는데, <b>난이도 0.2부터 1.0까지 잰 모든 칸에서 세 모델 모두 0 %</b>'
             '입니다. 범위를 넓혀도 0.1 한 칸 밖으로는 안 나갔습니다. '
             '돌 사이가 약 14 cm이고 높이 스캔 격자가 0.1 m 라 <b>관측 설정이 '
             '실패에 얼마나 관여하는지는 아직 확인하지 못했습니다.</b> '
             '<span class="mono">미확인</span></div>'
             )
p.append('<p>난이도 0.5 칸에서 이 곡선과 앞의 성적표는 <strong>같은 값</strong>입니다 '
         '(기준선 50.5 % · A 76.6 % · foothold-v1 84.7 %). 난이도 0.5 · 1.0 m/s에서 '
         '미경험 10종의 모델별 평균이 기준 성적표와 일치한다는 뜻입니다. 두 자료가 같은 것을 '
         '재고 있다는 뜻입니다.</p>')
# ── 8 · 속도 ──────────────────────────────────────────────────────────
# ★ 2026-09-15 신설. 팀장이 「속도별 0.5 · 1.0 · 1.5 를 확인 해본 결과」 를
#   서사에 넣자고 했다. 재 보니 보고서에 아예 없던 가장 큰 결과가 여기 있었다.
p.append('<h2><span class="n">08</span>속도를 바꾸면 어떻게 되나</h2>')
p.append('<p><b>난이도 0.1에서</b> 명령 속도 0.5 · 1.0 · 1.5 m/s를 비교했습니다. '
         '미경험 10종의 평균 종합 성공률입니다.</p>')

if SWEEP:
    _rows = ''
    for _m, _label in (('baseline', '기준선 NVIDIA'), ('A', 'A'),
                       ('B', 'B = foothold-v1')):
        _cells = ''.join('<td class="num">%.0f</td>' % _avg(_m, '0.1', _v)
                         for _v in ('0.5', '1.0', '1.5'))
        _rows += '<tr><td class="mono">%s</td>%s</tr>' % (_label, _cells)
    p.append('<div class="tw"><table><thead><tr><th>모델</th>'
             '<th class="num">0.5 m/s</th><th class="num">1.0 m/s</th>'
             '<th class="num">1.5 m/s</th></tr></thead><tbody>%s</tbody></table></div>'
             % _rows)

p.append('<p><b>둘이 보입니다.</b> 하나 · <b>명령 속도를 낮춘다고 종합 성공률이 '
         '올라가지는 않습니다.</b> '
         '기준선과 foothold-v1은 0.5 m/s가 1.0 m/s보다 낮습니다 '
         '(%.1f 대 %.1f · %.1f 대 %.1f). <b>다만 A는 세 속도가 거의 같습니다</b> '
         '(%.1f · %.1f · %.1f) 라 이 경향이 모든 정책에 있는 것은 아닙니다.</p>'
         % (_avg('baseline', '0.1', '0.5'), _avg('baseline', '0.1', '1.0'),
            _avg('B', '0.1', '0.5'), _avg('B', '0.1', '1.0'),
            _avg('A', '0.1', '0.5'), _avg('A', '0.1', '1.0'),
            _avg('A', '0.1', '1.5')))
p.append('<p>둘 · <b>1.5 m/s에서 기준선과 foothold-v1의 차이가 큽니다.</b> 난이도 0.1에서 '
         '기준선의 종합 성공률은 1.0 m/s의 %.0f %%에서 1.5 m/s의 %.0f %%로 '
         '떨어지는데, foothold-v1은 %.0f %%를 지킵니다. '
         '<b>왜 그런지는 이 자료로 못 가릅니다.</b></p>'
         % (_avg('baseline', '0.1', '1.0'), _avg('baseline', '0.1', '1.5'),
            _avg('B', '0.1', '1.5')))
p.append('<div class="note">이 표는 <b>난이도 0.1 한 칸</b>의 평균입니다. '
         '속도와 난이도를 함께 올린 칸은 따로 봐야 합니다.</div>')

p.append('<h2><span class="n">09</span>성공률만으로는 안 보이는 것</h2>')
p.append('<p>생존 · 전진 · 속도추종 · 방향의 네 기준을 모두 충족해야 성공입니다. 그런데 장애물을 '
         '<strong>비켜 가도</strong> 그 조건은 채워집니다. 그래서 이번 에피소드에 '
         '<strong>몸통 아래 광선이 어느 높이 폭을 지났는가</strong>를 재는 열 셋을 더했습니다.</p>')
p.append('<figure>%s<figcaption>가로가 참여도, 세로가 성공률입니다. 오른쪽 위는 '
         '중앙 광선이 지난 높이 폭이 스캔 전체와 비슷하면서 성공률도 높은 쪽, '
         '왼쪽 위는 그 폭이 작은데 성공률은 높은 쪽입니다. 이 비율은 '
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
         '한 에피소드 동안 몸통 아래 <strong>중앙 광선 하나</strong>가 지나간 높이 폭을, '
         '<strong>스캔 전체</strong>가 본 높이 폭으로 나눈 값입니다. '
         '0과 1 사이로 자릅니다.</p>'
         '<p class="mono" style="font-size:.86rem">'
         '참여도 = min(1, max(0, 중앙 광선 높이 범위 / 스캔 전체 높이 범위))</p>'
         '<p>높이 범위의 단위는 m이고 비율은 단위가 없습니다. 스캔 전체 기복이 '
         '0.02 m 미만이면 나눗셈이 뜻을 잃으므로 <strong>비웁니다.</strong> '
         '난이도 0.5 · 1.0 m/s · foothold-v1에서 비는 것은 '
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
         '<span class="mono">star</span>는 성공률 100 ' + PCT + '인데 참여도 '
         '중앙값이 표시 자릿수에서 0.00입니다.</strong> 시연 한 편에서 막대 사이를 '
         '지나는 경로를 봤고, 평가 100 에피소드 전체의 경로는 확인하지 않았습니다. '
         '난이도 0.5에서 star의 막대 높이는 '
         '0.105 m인데, 몸통 아래 광선이 지나간 높이 폭은 평균 '
         + ("%.3f" % st["under"]) + ' m입니다.</p>'
         '<p><strong>평균보다 분포가 분명합니다.</strong> 참여도 중앙값이 '
         + ("%.2f" % st["ratio_p50"]) + '이고 10~90 분위가 '
         + ("%.2f ~ %.2f" % (st["ratio_p10"], st["ratio_p90"])) + '입니다. '
         '중앙값이 표시 자릿수에서 0.00이고, 비율이 정확히 1인 에피소드는 %d개였습니다. '
         % st["ones"] + 
         '평균은 ' + ("%.2f" % st["ratio"]) + '입니다. 중앙값과 그 개수만으로 '
         '나머지가 어떻게 흩어졌는지는 말할 수 없습니다.</p>'
         '<p>Isaac의 star 지형은 막대가 중심에서 바깥으로 뻗습니다. 막대 사이를 따라 '
         '바깥쪽으로 걸으면 막대를 가로지르지 않는 경로가 가능합니다. 다만 그 경로를 '
         '실제로 확인한 것은 영상 한 에피소드뿐입니다(미확인).</p>'
         '<p>반대로 <span class="mono">rails</span>와 '
         '<span class="mono">stepping_stones</span>는 참여도 중앙값이 '
         + ("%.2f" % ENG["rails"]["ratio_p50"]) + '와 '
         + ("%.2f" % ENG["stepping_stones"]["ratio_p50"]) + '인데 성공률이 '
         + fmt(g("rails", "foothold-v1", "1")) + ' ' + PCT + '와 '
         + fmt(g("stepping_stones", "foothold-v1", "1")) + ' ' + PCT
         + '입니다. 참여도가 높은데 성공률이 낮은 조건입니다. 이 비율만으로 실패 원인을 말할 수는 없습니다.</p></div>')
# **성공률로 원인을 말하지 않는다.** 어느 축에서 떨어졌는지 세어서 적는다
# `확인됨` (2026-09-12 검증 2회차 1번 · rails 실패 52 에피소드 중 27 에피소드는 방향 축만
# 떨어졌다. 「걸렸다」고 쓰면 종합 실패율을 물리적 걸림으로 바꿔 말하는 것이다).
_rails = BD["rails|foothold-v1|1"]
_step = BD["stepping_stones|foothold-v1|1"]
_rails_dir = _rails["combo"].get("방향", 0)

p.append('<p>참여도가 높다고 실패하는 것도, 낮다고 성공하는 것도 아닙니다. '
         '아래 셋은 난이도 0.5 · 1.0 m/s에서 <strong>따로 촬영한 시연 한 에피소드씩</strong>이고, '
         '옆의 수치는 같은 조건 100 에피소드의 집계입니다.</p>')
p.append(clips([
    ("star-v1", "star · 참여도 중앙값 %.2f" % ENG["star"]["ratio_p50"],
     "성공 %d/%d. 몸통 아래 광선이 지난 높이 폭이 대체로 작았습니다"
     % (BD["star|foothold-v1|1"]["win"], BD["star|foothold-v1|1"]["n"])),
    ("rails-v1", "rails · 참여도 중앙값 %.2f" % ENG["rails"]["ratio_p50"],
     "성공 %d/%d. 실패 %d에피소드 가운데 %d에피소드는 <strong>방향 축만</strong> 떨어졌습니다"
     % (_rails["win"], _rails["n"], _rails["n"] - _rails["win"], _rails_dir)),
    ("stepping_stones-v1", "stepping_stones · 참여도 중앙값 %.2f"
     % ENG["stepping_stones"]["ratio_p50"],
     "성공 %d/%d. 실패는 전부 세 축 이상이 함께 떨어졌습니다"
     % (_step["win"], _step["n"])),
]))
p.append('<div class="note"><p><strong>참여도는 발이 닿았는지를 재지 않습니다.</strong> '
         '몸통 아래 중앙 광선이 지난 높이 폭을, 스캔 전체가 본 높이 폭으로 나눈 값입니다. '
         '어느 길로 우회했는지, 장애물을 끝까지 갔는지는 이 비율만으로 알 수 없습니다. '
         '</p></div>')
p.append('<p><span class="mono">gap</span>은 <strong>이 조건에서</strong> 잴 수 '
         '없습니다. 난이도 0.5 · 1.0 m/s · foothold-v1의 100 에피소드 모두 스캔 전체 '
         '기복이 0.02 m에 못 미쳐 비어 있습니다. 다른 모델·속도에서는 유효값이 몇 '
         '에피소드 잡히기도 하므로 「gap은 언제나 못 잰다」로 넓히지 마십시오. '
         '<b>네 축은 평가 기준을 채웠는지를 보여 줍니다.</b> 발이 실제로 어디에 '
         '닿았는지와 어떤 경로로 지났는지는 따로 봐야 합니다.</p>')

# ── 6 ──────────────────────────────────────────────────────────────────
# ── 무엇을 잘하라고 가르쳤나 ───────────────────────────────────────────
# ★ 2026-09-14 (#422) 팀장 지목. 보상 지도는 «어떻게 쟀나» 가 아니라
#   «왜 그렇게 움직이나» 라서 발견 쪽이다. 평가 정본에서 여기로 옮긴다.
p.append('<h2><span class="n">10</span>무엇을 잘하라고 가르쳤나</h2>')
p.append('<p>성적이 갈리는 까닭을 보려면 <b>무엇에 상을 주고 무엇에 벌을 '
         '주었는지</b>를 봐야 합니다. 아래는 학습 실행이 저장한 '
         '<span class="mono">params/env.yaml</span>에서 그대로 읽은 것입니다.</p>')
p.append('<figure class="mdimg"><img src="assets/visual/eval-v2-fig08.svg" '
         'alt="Go2 몸의 어디에 어떤 보상이 걸리는가" loading="lazy">'
         '<figcaption>그림 · 보상 10개와 종료 조건 3개가 몸의 어디에 걸리는지. '
         '사진은 실제 평가 렌더에서 오린 것입니다</figcaption></figure>')
p.append('<p><span class="mono">lin_vel_z_l2</span>의 가중치가 '
         '<b>-2.00</b>으로, 몸통이 위아래로 움직이는 데 벌점을 줍니다. '
         '절댓값 2.00은 속도추종 보상의 절댓값 1.50보다 큽니다. '
         '<b>다만 항마다 계산식과 값의 범위가 달라 가중치의 크기만으로 '
         '실제 기여를 견줄 수는 없습니다.</b> 틈이나 턱을 넘으려면 몸이 위아래로 '
         '움직여야 하니 이 항이 그 동작을 누르는지 <b>확인할 항목</b>이지만, '
         '그렇다고 확인한 것은 아닙니다. <span class="mono">미확인</span></p>')
p.append('<div class="note"><b>다만 보상만 바꿔서는 아무 일도 안 일어납니다.</b> '
         '기준선은 구멍이 없는 지형에서 학습된 NVIDIA 공식 체크포인트입니다. '
         '보상을 고치려면 <b>재학습이 전제</b>입니다. 그리고 우리는 아직 NVIDIA '
         '보상을 한 항도 안 바꿨습니다 <span class="mono">확인됨</span>.</div>')

p.append('<h2><span class="n">11</span>아직 안 되는 것</h2>')
p.append("<ul>")
p.append('<li><strong>전진 말고는 평가하지 않았습니다.</strong> '
         'foothold-v1은 <b>앞으로만 0.5 ~ 1.5 m/s로 걷도록</b> 학습됐습니다. '
         '명령 조건 6개와 리셋 조건 3개가 함께 걸려, 학습 중에 '
         '<b>제자리에 서거나 · 0.5 m/s보다 천천히 가거나 · 제자리에서 돌거나 · '
         '옆으로 가는 명령이 한 번도 주어지지 않았습니다</b>(03절). '
         '평가 하네스도 같은 구간만 재기 때문에 <b>이 손실은 앞의 성적표 어디에도 '
         '나타나지 않습니다.</b> '
         '곧 「기존 험지 6종을 지켰다」는 <b>전진 조건 안에서만</b> 참입니다. '
         '정지 · 저속 · 회전 · 횡이동에서 이 모델이 어떤지는 '
         '<b>잘하는지 못하는지가 아니라 아직 모릅니다.</b> '
         '이것은 임석헌 레시피가 원래 그랬던 것이고 재현 오류가 아닙니다'
         '(<a href="https://github.com/foothold-project/foothold-lab/issues/428">#428</a>). '
         '<b>2차의 첫 과제입니다.</b></li>')
p.append('<li><strong><span class="mono">stepping_stones</span> 0 %.</strong> '
         '난이도 0.5 · 세 속도 전부에서 세 모델 모두 0 %입니다. 1.0 m/s 난이도 0.1에서는 '
         '기준선 58 % · A 88 % · foothold-v1 99 %인데 <b>난이도 0.2부터 세 모델 모두 '
         '0 %</b>로 떨어집니다 (07절). '
         '2차의 첫 과제입니다.</li>')
_r = BD["rails|foothold-v1|1"]
p.append('<li><strong><span class="mono">rails</span> %.0f %%.</strong> '
         '100 에피소드 모두 참여도 1.00이지만 그것으로 실패 원인을 말할 수 없습니다. '
         '실패 %d 에피소드 가운데 가장 많은 세 조합은 %s이고, 나머지 %d 에피소드는 '
         '다른 조합입니다. 속도를 1.5 m/s로 올리면 '
         '%.0f %%까지 떨어집니다.</li>'
         % (g("rails", "foothold-v1", "1"),
            _r["n"] - _r["win"],
            " · ".join("%s %d에피소드" % (k, v) for k, v in
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

p.append('<li><strong>장애물 구간은 지형마다 다릅니다.</strong> 난이도 0.5의 실행 기록이 적어 둔 구간은 시작 %.2f~%.2f m, 끝 %.2f~%.2f m입니다. '
         '진행 방향으로 구간이 가장 짧은 지형은 <span class="mono">%s</span> (%.2f~%.2f m)와 <span class="mono">%s</span> (%.2f~%.2f m)입니다. '
         '발판이 0.75 m 인 지형에서는 통과선 3.0 m까지 2.25 m가 남지만, <strong>그 뺄셈을 모든 지형에 그대로 쓰면 안 됩니다.</strong> '
         '지금 결과는 이 길이의 장애물 구간에서 얻은 성공률입니다. 더 긴 연속 장애물에서도 '
         '통과 성능이 유지되는지는 따로 재야 합니다. corridor 방식 재설계가 2차 검토 대상입니다.</li>'
         % (_zstart[0], _zstart[-1], _zend[0], _zend[-1],
            _narrow[0][0], _narrow[0][1][0], _narrow[0][1][1],
            _narrow[1][0], _narrow[1][1][0], _narrow[1][1][1]))
p.append('<li><strong>머리 접촉 세 열은 검증 전까지 인용하지 않습니다.</strong> '
         '첫 표본이 앞 에피소드의 접촉력을 물려받을 수 있고, 그 비율을 아직 확인하지 '
         '못했습니다.</li>')
p.append("</ul>")

p.append('<p><span class="mono">stepping_stones</span>에서 세 모델이 어떻게 '
         '실패하는지입니다. 2차는 이 결과를 기준으로 개선을 주장하게 됩니다.</p>')
p.append(clips([
    ("stepping_stones-v1-baseline", "기준선 NVIDIA", "성공률 0 %"),
    ("stepping_stones-v1-A", "A", "성공률 0 %"),
    ("stepping_stones-v1", "foothold-v1", "성공률 0 %"),
]))

# ── 7 ──────────────────────────────────────────────────────────────────
# ── 남은 질문 ─────────────────────────────────────────────────────────
# ★ 2026-09-15 팀장이 적어 준 세 질문. 답을 아는 척하지 않는다.
#   모르는 것을 «모른다» 로 적는 것도 보고서의 일이다.
p.append('<h3>남은 질문 셋</h3>')
p.append('<ol class="find">')
p.append('<li><b>NVIDIA는 왜 이것을 안 했나.</b> '
         '우리는 <span class="mono">gap</span> 하나를 학습 구성에 '
         '10 %만 더해 이만큼을 얻었습니다. 개발자가 손댈 자리로 '
         '남긴 것인지, 다른 까닭이 있는지 '
         '<b>우리는 모릅니다.</b> 공식 문서에서 근거를 못 찾았습니다.</li>')
p.append('<li><b>0.5 m/s의 성공률은 왜 1.0 m/s보다 낮았나.</b> 난이도 0.1에서 기준선과 '
         'foothold-v1은 0.5 m/s의 성공률이 1.0 m/s보다 낮습니다 '
         '(A는 예외로 세 속도가 거의 같습니다). 평가 성공률이 명령 속도에 따라 '
         '달랐다는 점까지가 확인한 것이고, <b>학습 속도 설정과의 관계는 '
         '확인하지 못했습니다.</b></li>')
p.append('<li><b>다음 레시피는 어디를 봐야 하나.</b> 지금 자료로는 '
         '<span class="mono">stepping_stones</span>가 난이도 0.2에서 '
         '세 모델 모두 0 %입니다. 난이도 0.1에서는 셋 다 올랐는데 그 한 칸 밖으로 '
         '안 나갔습니다. <b>관측 쪽</b>을 먼저 보려 합니다. 돌 간격이 약 14 cm이고 '
         '높이 스캔 격자가 0.1 m 라, 관측이 돌과 틈을 어떻게 표현하는지부터 볼 참입니다. '
         '관측 설정이 실패에 얼마나 기여했는지는 <span class="mono">미확인</span>입니다.</li>')
p.append('</ol>')

p.append('<h2><span class="n">12</span>재현</h2>')
p.append("<pre>git pull origin main" + NL +
         "pip install av        # Isaac이 도는 파이썬에 한 번만" + NL + NL +
         "# maindata-v1 평가 자료 (성적표와 그 원자료)" + NL +
        "#   07 · 08절의 난이도·속도 표는 20260911-v3-fixedscan이고" + NL +
        "#   아래 명령으로는 안 나옵니다. 그 자료의 재현은 평가 기준 문서를 보십시오." + NL +
         "python sim/eval/run_matrix.py \\" + NL +
         "    --model baseline=&lt;pt&gt; --model A=&lt;pt&gt; \\" + NL +
         "    --model foothold-v1=models/foothold-v1.pt \\" + NL +
         "    --out_dir sim/eval/results/maindata-v1" + NL + NL +
         "# 근거 영상 전부" + NL +
         "python sim/eval/render_gallery.py \\" + NL +
         "    --checkpoint models/foothold-v1.pt \\" + NL +
         "    --raw_csv sim/eval/results/maindata-v1</pre>")
p.append('<h2><span class="n">13</span>근거 영상 전체</h2>')
# **수를 손으로 적지 않는다.** 갤러리 색인에서 읽는다.
# 전에는 「모두 84컷」 이 박혀 있었고, 대조컷을 28개 더 채운 뒤에도
# 그대로 남았다 `확인됨` (2026-09-12 · 발행 관문도 못 잡았다).
_book = json.load(io.open(os.path.join(
    os.environ.get("FOOTHOLD_SITE")
    or os.path.abspath(os.path.join(REPO, "..", "foothold-site")),
    "gallery", "v1", "manifest.json"), encoding="utf-8"))
_cuts = _book["counts"]
_main = _cuts["clips"] - _cuts["comparison_clips"]
p.append('<p>이 보고서에 실린 것은 주장마다 한두 장씩 고른 것입니다. '
         '지형 %d종 x 속도 %d종 %d컷과 모델 대조 %d컷, 모두 %d컷이 '
         '<strong>gallery-v1</strong>에 있습니다. 평가 칸 %d개 가운데 %d개는 '
         '성적만 있고 영상이 없습니다. '
         '보고서 1차와 gallery-v1이 한 세트입니다.</p>'
         % (_cuts["terrains"], len(_cuts["speeds"]), _main,
            _cuts["comparison_clips"], _cuts["clips"],
            _cuts["evaluations"], _cuts["evaluations_without_clip"]))
p.append('<p>영상은 전진 5.0 m에서 잘렸습니다. 난이도 0.5에서 장애물 구간이 '
         '가장 멀리 가는 지형도 4.00 m에서 끝나고 그 뒤는 평평한 테두리라 '
         '볼 것이 없기 때문입니다. 지형마다 구간이 달라 어떤 영상은 앞쪽에서 '
         '이미 볼 것이 끝납니다. 넘어져서 그만큼 못 간 에피소드는 '
         '그대로 다 남아 있습니다. 배속 단추는 재생기의 '
         '<span class="mono">playbackRate</span>를 바꿉니다. 다만 느리게 틀어도 '
         '새 프레임이 생기지는 않아, 원본 초당 50장이 0.25배에서는 12.5장으로 보입니다.</p>')

p.append('<p>있어야 할 칸은 <span class="mono">sim/eval/matrix.py</span>가 선언합니다. '
         '한 칸이라도 비면 실행기가 0이 아닌 코드로 끝나고, 보고서 생성기도 거부합니다. '
         '측정 규격과 판정 정의는 '
         '<a href="/research-20260911-eval-protocol-v2.html">평가 기준 문서</a> '
         '입니다 (저장소는 '
         '<span class="mono">docs/research/20260911-eval-protocol-v2.md</span>).</p>')

# 에피소드 수를 두 개로 나눠 적는다. 성적표 분모와 전체 원자료는 다른 수다.
_score = STATUS["roles"].get("성적표", {"declared": 0, "present": 0, "cells": 0})
_curve = STATUS["roles"].get("곡선", {"declared": 0, "present": 0, "cells": 0})

# ★ 2026-09-15 astra 지적. 앞에서는 «지형 x 모델 x 난이도 x 속도» 를 한 칸으로
#   세는데 이 표의 「칸」은 «지형 묶음 x 모델 x 조건» 단위라 뜻이 다르다.
#   같은 낱말이 두 뜻이면 읽는 사람이 더한다. 표 앞에 무엇을 세는지 적는다.
p.append('<p class="cap">여기서 «칸»은 한 번의 평가 실행입니다. '
         '07절의 «칸»(모델 하나 x 지형 하나 x 난이도 하나 x 속도 하나)과 '
         '단위가 다릅니다.</p>')
p.append('<table><thead><tr><th>무리</th><th class="num">칸</th>'
         '<th class="num">선언한 에피소드</th><th class="num">있는 에피소드</th></tr></thead><tbody>'
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
             '본문의 성적표는 난이도 0.5의 %s 에피소드를 분모로 하고 그 칸은 다 찼습니다. '
             '비어 있는 것은 난이도 곡선 쪽이며, 그만큼 곡선의 한 부분이 그려지지 '
             '않았습니다.</p><p class="mono" style="font-size:.8rem">%s</p></div>'
             % (len(STATUS["missing"]), f"{_score['declared']:,}",
                " · ".join(STATUS["missing"])))
else:
    # ★ 2026-09-15 astra 지적. 「난이도 곡선까지 합한」 이라 적으면 07절의
    #   곡선(20260911-v3-fixedscan · 95,400)과 출처가 부딪친다. 이 회계는
    #   `maindata-v1` 한 자료의 것이다. 어느 자료의 회계인지 밝힌다.
    p.append('<p>선언한 %d칸이 모두 찼습니다. 이 표는 '
             '<span class="mono">maindata-v1</span> 한 자료의 회계입니다. '
             '본문의 성적표는 난이도 0.5의 %s 에피소드가 분모이고, '
             '이 자료 전체는 %s 에피소드입니다. '
             '<b>07절의 난이도 표와 곡선은 다른 자료</b>'
             '(<span class="mono">20260911-v3-fixedscan</span> · 954칸)이니 '
             '더하지 마십시오.</p>'
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
        raise SystemExit("문서에 %s가 없다" % _must)

# 원칙 2 · 조용한 실패를 소리 나게. 달라고 한 컷이 없으면 여기서 죽는다.
if WANTED_MISSING and "--allow_missing_clips" not in sys.argv:
    for _stem in WANTED_MISSING:
        print("  [X] 본문이 쓰는 컷이 없다: %s.mp4" % _stem)
    raise SystemExit("컷 %d개가 %s에 없다. 갤러리를 마저 굽거나 "
                     "--allow_missing_clips를 준다" % (len(WANTED_MISSING), TINY))

out = os.path.join(S, "report-v1.html")
io.open(out, "w", encoding="utf-8").write(html)
print("  %s  %.2f MB" % (os.path.basename(out), len(html.encode("utf-8")) / 1048576))
