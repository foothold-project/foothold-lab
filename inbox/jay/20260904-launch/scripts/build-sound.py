# -*- coding: utf-8 -*-
"""FOOTHOLD 런칭 사운드. 격자는 전부 실측값이다.

  발 접지 간격 208 ms    foot 컷 프레임차 FFT 지배 주파수 4.805 Hz 의 역수
  8분음표 0.2083333 초   같은 값. 러프컷 컷 길이의 단위이기도 하다
  4분음표 0.4166667 초   킥을 강조하는 자리. 접지를 전부 때리면 뭉갠다
  템포 144 BPM           8분음표가 정확히 4.8 Hz
  드론 기음 76.88 Hz     4.805 Hz 를 네 옥타브 올린 값. 숫자에서 나온 음이다

시각은 러프컷에서 읽는다. 여기에 베끼지 않는다.
러프컷이 v5 · v6 · v7 로 세 번 바뀌었고 그때마다 밀렸다.
  컷 구성   조립 스크립트의 CUTS 를 읽는다
  엔딩 사건 sound/title-events.json 을 읽는다 (measure-title-events.py 가 만든다)

층 구성
  1 발자국 저역   0.000 에서 rise 끝까지. formation 구간은 비운다
  2 배경 드론     처음부터 끝까지
  3 우쉬          카메라가 실제로 움직이는 두 곳만
  4 엔딩          측정한 타이틀 사건에 맞춘다
"""
import ast, json, os, re, subprocess, sys, wave
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
RC = LAB + "/inbox/jay/20260904-roughcut/foothold-roughcut.mp4"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "sound"))

SR = 48000
E = 30.0 / 144
Q = 2 * E
ROOT = 4.805 * 2 ** 4          # 76.88 Hz
GAIT = 1.0 / E                 # 4.8 Hz. 실측 4.805 Hz 와 같은 값
rng = np.random.default_rng(4805)


# ---------------------------------------------------------------- 재료를 읽는다
def read_cuts():
    src = open(BUILD, encoding="utf-8").read()
    cuts = ast.literal_eval(re.search(r"^CUTS\s*=\s*(\[.*?^\])", src, re.S | re.M).group(1))
    f = re.search(r"^FORM_E,\s*TITLE_E\s*=\s*(\d+),\s*(\d+)", src, re.M)
    return cuts, int(f.group(1)), int(f.group(2))


CUTS, FORM_E, TITLE_E = read_cuts()

# 프레임 수는 measure-title-events.py 가 실제로 디코딩해서 센 값을 쓴다.
# ffmpeg 의 진행 표시(frame=)는 먹싱 기준이라 디코딩 결과와 한 프레임 어긋난다.
# 두 곳에서 따로 세면 갈라지므로 재는 곳을 하나로 둔다.
_ev_path = os.path.normpath(os.path.join(OUT, "title-events.json"))
if not os.path.exists(_ev_path):
    sys.exit("먼저 measure-title-events.py 를 돌려라: " + _ev_path)
_EV0 = json.load(open(_ev_path, encoding="utf-8"))
NF = _EV0["frames"]
# 조립된 그림이 있으면 그 길이를 따른다. 그림이 기준이다.
_vf = os.path.normpath(os.path.join(HERE, "..", "work", "video-frames.json"))
if os.path.exists(_vf):
    NF = json.load(open(_vf, encoding="utf-8"))["frames"]
DUR = NF / 50.0
N = int(round(DUR * SR))
t = np.arange(N) / SR

# 컷 경계와 주요 시각
bounds, acc = [], 0.0
for c in CUTS:
    bounds.append(acc)
    acc += c[2] * E
T_WALK_END = acc                       # rise 끝. 로봇이 걷는 것이 끝나는 시각
T_FORM_END = acc + FORM_E * E          # formation 끝
T_TITLE = T_FORM_END - 0.5             # 디졸브 시작
T_DOLLY = bounds[6]
T_RISE = bounds[7]

EV = _EV0


def pick(what, which=-1, after=0.0):
    v = [e["t"] for e in EV["events"] if e["what"] == what and e["t"] >= after]
    return v[which] if v else None


T_WORD = pick("흰글자 등장", 0, T_TITLE)         # 워드마크 등장
T_GLITCH = pick("흰글자 소멸", 0, T_TITLE)       # 워드마크가 부서진다
T_UNFOLD = pick("흰글자 등장", -1, T_GLITCH)     # FIND THE NEXT STEP 펼침
T_CUT = pick("흰글자 소멸", -1, T_UNFOLD)        # 절단. 가장 큰 포인트
T_KO = pick("티얼 등장", -1, T_CUT)              # 한국어 문구
T_LOCK = pick("락업 착지", -1, T_TITLE)          # 락업 착지


# ---------------------------------------------------------------- 도구
def env(n, atk, dec, curve=2.5):
    a = max(1, int(atk * SR)); d = max(1, int(dec * SR))
    e = np.zeros(n); m = min(a, n)
    e[:m] = np.linspace(0, 1, m) ** 0.6
    if n > a:
        k = min(d, n - a)
        e[a:a + k] = np.exp(-curve * np.linspace(0, 1, k) * 3.0)
    return e


def place(dst, sig, at, gain=1.0):
    i = int(round(at * SR))
    if i >= len(dst):
        return
    if i < 0:
        sig = sig[-i:]; i = 0
    j = min(len(dst), i + len(sig))
    dst[i:j] += sig[:j - i] * gain


def _shape(x, H):
    return np.fft.irfft(np.fft.rfft(x) * H, len(x))


def band(x, lo, hi):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return _shape(x, (1 / (1 + (lo / np.maximum(f, 1e-6)) ** 4)) * (1 / (1 + (f / hi) ** 4)))


def lp(x, fc):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return _shape(x, 1 / (1 + (f / fc) ** 4))


def hp(x, fc):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return _shape(x, 1 / (1 + (fc / np.maximum(f, 1e-6)) ** 4))


# ------------------------------------------------- 층 1a. 정격 펄스. 뼈대다.
ground = np.zeros(N)
PL = int(0.32 * SR)
lt = np.arange(PL) / SR
# 피치를 55 Hz 에서 40 Hz 로 떨어뜨리면 무게가 생긴다
inst = 40 + 15 * np.exp(-lt / 0.070)
base = np.sin(2 * np.pi * np.cumsum(inst) / SR) * env(PL, 0.008, 0.120, 2.4)
sub45 = np.sin(2 * np.pi * 45 * lt) * env(PL, 0.006, 0.120, 2.4)
grit = band(rng.normal(0, 1, PL), 45, 85) * env(PL, 0.010, 0.100, 2.8)
pulse = base * 0.62 + sub45 * 0.40 + grit * 0.30

n_pulse = 0
k = 0
while k * E <= T_WALK_END + 1e-9:
    at = k * E
    strong = (k % 2 == 0)                      # 4분음표마다 강조
    lvl = np.interp(at, [0.0, 3.333, T_DOLLY, T_RISE, T_WALK_END],
                        [0.55, 0.68, 0.80, 0.92, 1.00])
    place(ground, pulse, at, 0.80 * lvl * (1.0 if strong else 0.62))
    n_pulse += 1
    k += 1

# ------------------------------------------------- 층 1b. 알갱이. 살이다.
# 4096마리가 완전히 같은 위상이 아니다. foot 과 side 컷을 보면 개체마다 발이 어긋난다.
# 개체를 여러 마리 두고 각자 위상을 조금씩 흩뜨려 쌓으면 정격 펄스가 아니라 군중의 울림이 된다.
# 실측 지배 주파수가 4.805 Hz 로 뚜렷하니 위상이 흩어진 정도는 작다. 표준편차를 22 ms 로 둔다.
AGENTS = 96
JITTER = 0.022
grain = np.zeros(N)
GL = int(0.075 * SR)
glt = np.arange(GL) / SR
for a in range(AGENTS):
    rate = GAIT * (1.0 + rng.normal(0, 0.004))     # 개체마다 걸음 속도가 미세하게 다르다
    ph = rng.normal(0, JITTER)
    amp = 0.5 + 0.5 * rng.random()
    k = 0
    while True:
        at = k / rate + ph
        if at > T_WALK_END:
            break
        if at >= 0:
            thump = np.sin(2 * np.pi * (52 + 30 * np.exp(-glt / 0.02)) * glt)
            tick = band(rng.normal(0, 1, GL), 120, 900)
            g = (thump * 0.7 + tick * 0.5) * env(GL, 0.0015, 0.045, 4.0)
            lvl = np.interp(at, [0.0, T_DOLLY, T_RISE, T_WALK_END], [0.6, 0.85, 1.0, 1.0])
            place(grain, g, at, amp * lvl)
        k += 1
grain = lp(grain, 240.0) * (0.85 / max(1e-9, np.abs(grain).max()))

# 컷이 바뀌는 지점에서 저역을 살짝 눌렀다 놓으면 컷이 소리로도 읽힌다.
duck = np.ones(N)
for b in bounds[1:] + [T_WALK_END]:
    i = int(b * SR)
    w = int(0.055 * SR)
    a0, a1 = max(0, i - w // 3), min(N, i + w)
    if a1 > a0:
        prof = np.concatenate([np.linspace(1.0, 0.55, i - a0), np.linspace(0.55, 1.0, a1 - i)])
        duck[a0:a1] = np.minimum(duck[a0:a1], prof[:a1 - a0])
foot_layer = (ground + grain * 0.55) * duck
# formation 구간은 비운다. 소리가 빠지면 다음 것이 커진다.
foot_layer *= np.interp(t, [0, T_WALK_END, T_WALK_END + 0.28], [1, 1, 0])

# ------------------------------------------------- 층 2. 배경 드론
drone = np.zeros(N)
for mul, amp in [(1.0, 0.55), (1.5, 0.26), (2.0, 0.34), (3.0, 0.19),
                 (4.0, 0.12), (6.0, 0.070), (8.0, 0.038)]:
    drift = 1.0 + 0.0016 * np.sin(2 * np.pi * 0.055 * t + mul)
    ph = 2 * np.pi * np.cumsum(ROOT * mul * drift) / SR
    drone += (np.sin(ph) + 0.16 * np.sin(3 * ph) + 0.07 * np.sin(5 * ph)) * amp
# 440 Hz 근처에 아주 작은 배음 하나. 오르간 같은 결이 난다.
drone += np.sin(2 * np.pi * 443.0 * t) * 0.020 * (0.6 + 0.4 * np.sin(2 * np.pi * t / 8.0))
drone /= 2.4
# 8초 주기의 아주 느린 스웰
drone *= 1.0 + 0.13 * np.sin(2 * np.pi * t / 8.0 - 0.6)
drone *= np.interp(t, [0.0, 1.2, T_DOLLY, T_RISE, T_WALK_END, T_FORM_END,
                       T_CUT, T_CUT + 0.22, T_KO, T_LOCK, T_LOCK + 1.3, DUR - 0.5, DUR],
                      [0.0, 0.28, 0.44, 0.62, 0.86, 0.74,
                       0.80, 0.34, 0.72, 0.58, 0.88, 0.82, 0.0])

# 상승 오르간. rise 에서 네 음이 올라가 대형에 앉는다.
fig = np.zeros(N)
step = (T_WALK_END - T_RISE) / 4.0
for i, mul in enumerate([2.0, 2.4, 3.0, 4.0]):
    ln = int(1.9 * SR); lt2 = np.arange(ln) / SR
    f0 = ROOT * mul
    v = (np.sin(2 * np.pi * f0 * lt2) + 0.22 * np.sin(2 * np.pi * 2 * f0 * lt2)
         + 0.10 * np.sin(2 * np.pi * 3 * f0 * lt2))
    place(fig, v * env(ln, 0.10, 0.85, 1.4), T_RISE + i * step, 0.155)

# ------------------------------------------------- 층 3. 우쉬
whoosh = np.zeros(N)


def make_whoosh(pre, post, f_a, f_b, q):
    n = int((pre + post) * SR)
    lt2 = np.arange(n) / SR
    x = lt2 / (pre + post)
    nz = rng.normal(0, 1, n)
    out = np.zeros(n)
    nb = 26
    for i in range(nb):
        u = i / (nb - 1)
        fc = f_a * (f_b / f_a) ** u
        out += band(nz, fc * 0.80, fc * 1.25) * np.exp(-((x - u) ** 2) / (2 * q ** 2))
    out /= nb ** 0.5
    return out * np.where(lt2 < pre, (lt2 / pre) ** 2.0,
                          np.exp(-3.2 * (lt2 - pre) / max(post, 1e-6)))


place(whoosh, make_whoosh(0.42, 0.38, 170, 2600, 0.19), T_DOLLY - 0.42, 0.50)   # 0.80초
place(whoosh, make_whoosh(0.30, 0.34, 240, 4400, 0.17), T_RISE - 0.30, 0.58)    # 0.64초
LN = int(0.9 * SR)
lift = np.sin(2 * np.pi * np.cumsum(np.linspace(55, 130, LN)) / SR) * env(LN, 0.30, 0.55, 1.6)
place(whoosh, lift, T_RISE - 0.30, 0.32)

# ------------------------------------------------- 층 4. 엔딩
acc_l = np.zeros(N)

# 워드마크 등장. 아주 낮게 받친다.
WN = int(1.1 * SR); lt2 = np.arange(WN) / SR
place(acc_l, np.sin(2 * np.pi * ROOT * 2 * lt2) * env(WN, 0.18, 0.55, 1.6), T_WORD, 0.10)

# 글리치. 워드마크가 부서진다. 짧고 거친 디지털 찢김.
GN = int(0.26 * SR)
gl = band(rng.normal(0, 1, GN), 700, 9000)
sq = np.sign(np.sin(2 * np.pi * 92 * np.arange(GN) / SR))       # 거친 결
gl = (gl * 0.8 + sq * 0.25) * env(GN, 0.0008, 0.055, 5.0)
step_n = int(0.012 * SR)                                        # 계단으로 끊어 디지털 느낌
for s in range(0, GN - step_n, step_n * 2):
    gl[s:s + step_n] *= 0.25
place(acc_l, gl, T_GLITCH, 0.30)

# 중앙에 선이 그어지고 문구가 펼쳐진다. 금속성 상승음.
RN = int(0.55 * SR); lt2 = np.arange(RN) / SR
riser = np.sin(2 * np.pi * np.cumsum(np.geomspace(320, 2100, RN)) / SR)
riser += 0.35 * np.sin(2 * np.pi * np.cumsum(np.geomspace(480, 3150, RN)) / SR)
place(acc_l, riser * (lt2 / lt2[-1]) ** 1.8 * np.exp(-((lt2 - RN / SR) ** 2) / 0.08), T_UNFOLD - 0.55, 0.16)

# 절단. 가장 큰 포인트다. 금속 베는 소리와 서브 드롭.
SN = int(0.62 * SR); lt2 = np.arange(SN) / SR
pre = band(rng.normal(0, 1, SN), 400, 7000) * (lt2 / lt2[-1]) ** 3.0
pre += np.sin(2 * np.pi * np.cumsum(np.geomspace(220, 900, SN)) / SR) * (lt2 / lt2[-1]) ** 3.4 * 0.45
place(acc_l, pre, T_CUT - 0.62, 0.30)
CN = int(0.30 * SR); lt2 = np.arange(CN) / SR
blade = band(rng.normal(0, 1, CN), 2600, 11000) * env(CN, 0.0004, 0.045, 6.5)
blade += np.sin(2 * np.pi * 3100 * lt2) * env(CN, 0.0004, 0.018, 8.0) * 0.30
place(acc_l, blade, T_CUT, 0.34)
DN = int(1.5 * SR); lt2 = np.arange(DN) / SR
drop = np.sin(2 * np.pi * np.cumsum(30 + 62 * np.exp(-lt2 / 0.075)) / SR) * env(DN, 0.0015, 0.55, 1.9)
place(acc_l, drop, T_CUT, 0.72)

# 한국어 문구. 드론이 부풀고 다른 소리는 비운다. 위 드론 곡선이 맡는다.

# 락업 착지. 낮은 임팩트 한 방과 긴 꼬리. 때리지 않는다.
IN_ = int(2.2 * SR); lt2 = np.arange(IN_) / SR
land = np.sin(2 * np.pi * np.cumsum(36 + 26 * np.exp(-lt2 / 0.10)) / SR) * env(IN_, 0.012, 0.75, 1.5)
air = band(rng.normal(0, 1, IN_), 1800, 8000) * env(IN_, 0.006, 0.12, 4.0) * 0.070
place(acc_l, land + air, T_LOCK, 0.46)
tail = DUR - T_LOCK
for mul, amp in [(1.0, 0.16), (1.5, 0.11), (2.0, 0.18), (3.0, 0.12), (4.0, 0.075)]:
    ln = int(tail * SR); lt2 = np.arange(ln) / SR
    v = np.sin(2 * np.pi * ROOT * mul * lt2) + 0.18 * np.sin(2 * np.pi * 2 * ROOT * mul * lt2)
    e = np.minimum(1.0, lt2 / 0.8) * np.interp(lt2, [0, tail - 0.5, tail], [1, 1, 0])
    place(acc_l, v * e, T_LOCK, amp)

# ------------------------------------------------- 합
mix = foot_layer + drone + fig + whoosh + acc_l
# 마스터 트림. 손 안 대면 -13.9 LUFS 로 나온다. 요구가 -16 근처라 2.1 dB 내린다.
# 값은 ebur128 로 재서 맞췄다.
MASTER_TRIM_DB = -2.1
mix *= 10 ** (MASTER_TRIM_DB / 20)
mix = hp(mix, 26.0)                                  # 스피커 보호
mix *= np.interp(t, [0, 0.04, DUR - 0.40, DUR], [0, 1, 1, 0])
wide = whoosh * 0.30 + fig * 0.35 + grain * 0.10
L, R = mix + wide * 0.5, mix - wide * 0.5

CEIL = 10 ** (-1.2 / 20)                             # -1.2 dBFS. 요구는 -1 을 넘지 않는 것
for i, ch in enumerate((L, R)):
    pk = np.abs(ch).max()
    if pk > CEIL:
        ch = np.tanh(ch / pk * 1.08) * CEIL
    if i == 0:
        L = ch
    else:
        R = ch

os.makedirs(OUT, exist_ok=True)
path = os.path.normpath(os.path.join(OUT, "foothold-launch-sound.wav"))
data = (np.clip(np.stack([L, R], axis=1), -1, 1) * 32767).astype(np.int16)
with wave.open(path, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(data.tobytes())

spec = {
    "roughcut_frames": NF, "duration_s": round(DUR, 4),
    "eighth_ms": round(E * 1000, 3), "quarter_ms": round(Q * 1000, 3), "bpm": 144,
    "gait_hz": round(GAIT, 4), "drone_root_hz": round(ROOT, 3),
    "cut_bounds_s": [round(b, 4) for b in bounds],
    "walk_end_s": round(T_WALK_END, 4), "formation_end_s": round(T_FORM_END, 4),
    "title_start_s": round(T_TITLE, 4),
    "whoosh_s": [round(T_DOLLY, 4), round(T_RISE, 4)],
    "ending": {"wordmark": T_WORD, "glitch": T_GLITCH, "unfold": T_UNFOLD,
               "cut": T_CUT, "korean": T_KO, "lockup": T_LOCK},
    "ground_pulses": n_pulse, "grain_agents": AGENTS, "grain_jitter_ms": JITTER * 1000,
    "peak_dbfs": round(20 * np.log10(max(np.abs(L).max(), np.abs(R).max())), 2),
}
json.dump(spec, open(os.path.join(OUT, "sound-spec.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

print(f"썼다  {path}")
print(f"  러프컷 {NF} 프레임 · {DUR:.3f}초 · {SR} Hz 스테레오 · {data.nbytes/1e6:.1f} MB")
print(f"  8분음표 {E*1000:.2f} ms · 4분음표 {Q*1000:.2f} ms · 드론 기음 {ROOT:.2f} Hz")
print(f"  층1 정격 펄스 {n_pulse} 개 + 알갱이 개체 {AGENTS} 마리 (위상 표준편차 {JITTER*1000:.0f} ms)")
print(f"     0.000 에서 {T_WALK_END:.3f} 초. formation({T_WALK_END:.3f} 에서 {T_FORM_END:.3f})은 비웠다")
print(f"  층2 드론 0.000 에서 {DUR:.3f} 초")
print(f"  층3 우쉬 {T_DOLLY:.3f} 초(dolly 진입) · {T_RISE:.3f} 초(rise 진입)")
print(f"  층4 엔딩  워드마크 {T_WORD} · 글리치 {T_GLITCH} · 펼침 {T_UNFOLD}")
print(f"            절단 {T_CUT} · 한국어 {T_KO} · 락업 {T_LOCK}")
print(f"  컷 경계 더킹 {len(bounds)} 곳")
print(f"  최대 진폭 L {np.abs(L).max():.4f} · R {np.abs(R).max():.4f} "
      f"({spec['peak_dbfs']:.2f} dBFS)")
