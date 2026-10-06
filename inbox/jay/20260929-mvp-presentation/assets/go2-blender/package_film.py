# -*- coding: utf-8 -*-
"""필름 프레임(film-frames 또는 film-cycles-frames) → 자막·워드마크·엔드카드를 얹어 mp4 둘 + 접촉 인쇄 + review.json.
  python package_film.py [cycles]
  go2-film-1280.mp4  1280×720 · crf 20 (보관·유튜브 업로드용)
  go2-film-960.mp4    960×540 · crf 24 (아티팩트용)
자막은 덱 문구·숫자를 그대로 옮긴 것(출처: output/FOOTHOLD-MVP-cover.html 의 10·12·22쪽 · 두 잣대 장)."""
import sys, json
from pathlib import Path
import av, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = Path(__file__).resolve().parent
CYC = 'cycles' in sys.argv
SRC = ROOT / ('film-cycles-frames' if CYC else 'film-frames')
FPS = 24; N = 76*FPS + 1
F_SUB = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 30); F_SUB_B = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 30)
F_MARK = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 22); F_END = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 64); F_END2 = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 26)

# (시작초, 끝초, 자막) · 두 줄이면 \n
SUBS = [
    (0.6, 4.0, "Unitree Go2. 네 다리로 걷는 로봇입니다."),
    (4.2, 10.0, "다리는 넷. 다리마다 관절이 셋,\n모두 열두 개의 모터가 몸을 움직입니다."),
    (10.2, 14.0, "관절마다 모터가 들어 있습니다.\n모터가 돌면 다리가 접히고 펴집니다."),
    (14.0, 18.0, "한 다리에 회전축이 셋. 고관절은 벌리고 모으고,\n허벅지와 무릎은 굽히고 폅니다."),
    (18.2, 21.2, "발이 땅에 닿습니다.\n바닥과 닿는 그 접촉이 몸을 받칩니다."),
    (21.3, 24.0, "모터 토크가 관절을 돌리고 발이 움직이면,\n관절의 위치와 속도는 다시 상태 정보로 돌아옵니다."),
    (24.2, 27.3, "머리 앞에는 RGB 카메라.\n로봇이 눈으로 보는 것입니다."),
    (27.4, 31.0, "그 아래 LiDAR 는 빛을 쏘아 거리를 잽니다."),
    (31.2, 36.0, "저희 팀은 여기에 세 가지를 더 얹었습니다."),
    (36.2, 42.0, "연산 모듈 Orin NX 16GB · 3D 공간 인지용 HESAI-360 LiDAR\n깊이 영상과 IMU 를 주는 RealSense D435i"),
    (42.2, 45.4, "정책이 로봇에게 주는 명령은 셋.\n앞으로 가는 속도 vx, 0.4 ~ 1.5 m/s."),
    (45.5, 48.8, "옆으로 가는 속도 vy.\n이번 학습에서는 0 으로 잠갔습니다."),
    (48.9, 52.0, "제자리에서 도는 속도 ωz, -1.0 ~ 1.0 rad/s.\n발을 어디에 놓을지는 정책이 스스로 정합니다."),
    (52.2, 59.0, "발밑 1.6 × 1.0 m 를 187 개 점으로 읽습니다.\n이것이 «높이 스캔», 로봇의 발밑 지도입니다."),
    (59.2, 62.4, "잘 걷는지는 한 판마다 네 가지로 잽니다.\n하나, 넘어지지 않기."),
    (62.5, 64.4, "둘, 출발점에서 3 m 를 앞으로 가기."),
    (64.5, 66.4, "셋, 시킨 속도와 0.25 m/s 넘게 어긋나지 않기."),
    (66.5, 70.0, "넷, 3 m 지점에서 좌우로 0.75 m 넘게 벗어나지 않기.\n하나라도 깨지면 그 판은 실패입니다."),
    (70.2, 75.0, "이 연습을 4,096 개 환경에서 동시에.\n한 대의 경험을 4,096 개 환경에서 함께 모읍니다."),
]
CHAPTERS = [(0, 'S1 등장'), (4, 'S2 네 다리 · 12 모터'), (10, 'S3 투시 · 액추에이터 · 세 회전축'), (18, 'S4 접촉 · 토크 · 피드백'),
            (24, 'S5 카메라 · LiDAR'), (31, 'S6 모듈 장착 · 분해도'), (42, 'S7 명령 vx · vy · ωz'), (52, 'S8 높이 스캔 187 점'),
            (59, 'S9 틈 건너기 · 네 조건'), (70, 'S10 4,096 환경')]

def sub_at(t):
    for a, b, s in SUBS:
        if a <= t < b:
            fade = min(1., (t-a)/.25, (b-t)/.25); return s, max(0., fade)
    return None, 0.

W, H = 1280, 720
vig = Image.new('L', (W, H), 0); dv = ImageDraw.Draw(vig); dv.ellipse((-W*.25, -H*.45, W*1.25, H*1.45), fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(160)); vig_a = np.asarray(vig, dtype=np.float32)/255.
def compose(frame, im):
    t = frame / FPS
    arr = np.asarray(im.convert('RGB'), dtype=np.float32)
    arr = arr * (0.82 + 0.18*vig_a)[..., None]                                   # 은은한 비네트
    out = Image.fromarray(arr.clip(0, 255).astype(np.uint8)); d = ImageDraw.Draw(out, 'RGBA')
    d.text((36, 26), 'FOOTHOLD', font=F_MARK, fill=(255, 255, 255, 170))
    d.text((36 + 118, 29), '· Go2 는 어떻게 걷는가', font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 18), fill=(255, 255, 255, 120))
    s, fa = sub_at(t)
    if s:
        lines = s.split('\n'); widths = [d.textlength(l, font=F_SUB) for l in lines]; bw = max(widths) + 56; bh = 46*len(lines) + 18
        x0 = (W-bw)/2; y0 = H - 54 - bh
        d.rounded_rectangle((x0, y0, x0+bw, y0+bh), radius=10, fill=(8, 10, 10, int(150*fa)))
        for i, (l, wl) in enumerate(zip(lines, widths)):
            d.text(((W-wl)/2, y0 + 12 + 46*i), l, font=F_SUB, fill=(255, 255, 255, int(255*fa)))
    if t >= 74.0:                                                                # 엔드카드로 디졸브
        k = min(1., (t-74.0)/1.2); d.rectangle((0, 0, W, H), fill=(10, 11, 11, int(235*k)))
        if k > .5:
            a = int(255*min(1., (k-.5)/.4)); tw = d.textlength('FOOTHOLD', font=F_END); d.text(((W-tw)/2, H/2-70), 'FOOTHOLD', font=F_END, fill=(255, 255, 255, a))
            s2 = '미경험 험지 적응 · Unitree Go2 · Isaac Lab 4,096 환경 · 2026'; tw2 = d.textlength(s2, font=F_END2); d.text(((W-tw2)/2, H/2+12), s2, font=F_END2, fill=(230, 232, 232, int(a*.8)))
    return out

frames = [SRC / f'frame-{f:04d}.png' for f in range(N)]
missing = [p.name for p in frames if not p.exists()]
assert not missing, ('빠진 프레임', len(missing), missing[:5])
def encode(name, size, crf):
    out = av.open(str(ROOT / name), 'w'); st = out.add_stream('libx264', rate=FPS)
    st.width, st.height = size; st.pix_fmt = 'yuv420p'; st.options = {'crf': str(crf), 'preset': 'slow'}
    for f, p in enumerate(frames):
        im = compose(f, Image.open(p))
        if im.size != size: im = im.resize(size, Image.LANCZOS)
        for pk in st.encode(av.VideoFrame.from_ndarray(np.array(im), format='rgb24')): out.mux(pk)
    for pk in st.encode(): out.mux(pk)
    out.close()
    with av.open(str(ROOT / name)) as v: n = sum(1 for _ in v.decode(video=0))
    assert n == len(frames), (name, n, len(frames))
    return (ROOT / name).stat().st_size / 1048576
tag = 'film-cycles' if CYC else 'film'
r = {'frames': len(frames), 'seconds': round(len(frames)/FPS, 1), 'engine': 'Cycles' if CYC else 'EEVEE',
     'mp4_1280_MB': round(encode(f'go2-{tag}-1280.mp4', (1280, 720), 20), 1), 'mp4_960_MB': round(encode(f'go2-{tag}-960.mp4', (960, 540), 24), 1)}
# 접촉 인쇄: 장면마다 시작·중간·끝
picks = []
for (a, _), (b, _) in zip(CHAPTERS, CHAPTERS[1:] + [(76, '')]):
    picks += [a*FPS + 6, (a+b)//2*FPS, b*FPS - 6]
Wc, Hc = 400, 225; cols = 6; rows = (len(picks) + cols - 1)//cols
sheet = Image.new('RGB', (cols*Wc, rows*Hc), 'black'); d = ImageDraw.Draw(sheet)
for k, f in enumerate(picks):
    im = compose(f, Image.open(frames[f])).resize((Wc, Hc)); x, y = (k % cols)*Wc, (k//cols)*Hc; sheet.paste(im, (x, y)); d.text((x+8, y+6), f'{f/FPS:.1f}s', fill='#ffcc33')
sheet.save(ROOT / f'go2-{tag}-contact.jpg', quality=85)
r['chapters'] = CHAPTERS; r['subs'] = SUBS
(ROOT / f'go2-{tag}-review.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps({k: v for k, v in r.items() if k not in ('chapters', 'subs')}))
