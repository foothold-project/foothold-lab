# -*- coding: utf-8 -*-
"""FOOTHOLD 런칭 사운드 · 듄 2 결로 다시 만든다.

1차본이 왜 가벼웠나. 실측으로 짚었다.
  - 바닥이 없다. 드론 기음이 76.88 Hz 라 20-60 Hz 가 11.88 퍼센트뿐이다.
  - 발자국 감쇠가 120 ms 다. 짧아서 두드림이 아니라 딱딱거림이 된다.
  - 우쉬에 공기가 없다. 2k-12k 가 0.9 와 1.0 퍼센트다. 사실상 안 들린다.
  - 무언 보컬이 없다. 듄의 결이 거기서 온다.
  - 스테레오가 거의 모노다. 듄의 공간감은 폭에서 온다.
  - 근접 컷이 뒤보다 5 dB 작다. 시작이 약하다.

그래서 이렇게 짠다. 요란하지 않고 두껍고 넓고 어둡다.
  층 1  지속 서브 드론 30-50 Hz. 처음부터 끝까지. 이것이 바닥이다.
  층 2  발자국. 포화된 저역 타악. 208 ms 격자. 감쇠 400-700 ms.
        80-250 Hz 에 새추레이션. 깨끗한 사인은 얇다. 배음을 만들어 두께를 낸다.
  층 3  무언 보컬 패드. 포먼트 700 / 1200 / 2600 Hz. 아주 느린 비브라토. 배경이다.
  층 4  우쉬. 카메라가 실제로 움직이는 두 곳만. 2-8 kHz 에 공기를 담는다.
  층 5  엔딩. 타이틀 사건에 맞춘다.
  층 6  오프닝. 멀리서 들어오는 저역 발자국. 간격이 좁아지고 필터가 열린다.

  마감  잔향 3초 · 하스 지연으로 폭 · 6.5 kHz 위 깎기 · -16 LUFS · -1 dBTP

숫자는 실측에서 나온다. 여기서 만들지 않는다.
  발 접지 208 ms      foot 컷 프레임차 FFT 지배 주파수 4.805 Hz 의 역수
  8분음표 0.2083333초 같은 값. 컷 길이의 단위
  144 BPM             8분음표가 4.8 Hz
  드론 기음 38.44 Hz  4.805 Hz 를 세 옥타브 올린 값. 30-50 Hz 안이다.
                      1차본은 네 옥타브 올려 76.88 Hz 로 갔고 그래서 바닥이 없었다.

시각은 베끼지 않는다. 컷 구성은 러프컷 조립 스크립트에서, 엔딩 사건은
sound/title-events.json 에서, 그림 길이는 work/video-frames.json 에서 읽는다.
"""
import ast, json, os, re, subprocess, sys, wave
import numpy as np
from scipy.signal import fftconvolve

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.join(ROOT, "sound")

SR = 48000
FPS = 50
E = 30.0 / 144                  # 8분음표 0.2083333초 = 실측 발 접지 208 ms
GAIT = 1.0 / E                  # 4.8 Hz
SUB = 4.805 * 2 ** 3            # 38.44 Hz. 30-50 Hz 안에 들어온다
OPEN_E = 12                     # 오프닝 8분음표 12개 = 2.5초. 첫 컷이 박자에 떨어진다
TARGET_LUFS = -16.0
TARGET_TP = -1.5        # 상한 -1 에 딱 붙이지 않는다. 인코딩 뒤에 넘칠 수 있다
rng = np.random.default_rng(4805)

# 층별 무게. 여기 하나만 고치면 된다. 값은 재서 맞췄다.
#
# 첫 판은 드론을 너무 크게 잡아서 20-60 Hz 가 73.9 퍼센트가 됐고
# 포락선을 드론이 먹어서 208 ms 가 최대가 아니게 됐다(60 ms 가 나왔다).
# 바닥은 「들리는」 것이지 「덮는」 것이 아니다. 드론을 내리고 중역을 올린다.
G_DRONE = 0.32          # 지속 서브. 바닥이되 덮지 않는다
G_FOOT = 1.00           # 발자국. 격자가 포락선에서 최대여야 한다
G_VOICE = 1.45          # 무언 보컬. 중역을 채운다
G_WHOOSH = 2.30         # 우쉬. 2k-12k 를 3 퍼센트 위로 올린다
G_FIG = 0.80            # 상승 음형
G_END = 1.00            # 엔딩
G_OPEN = 0.85           # 오프닝
KICK_SUB  = 0.85        # 발자국의 서브(58->36 Hz). 초저역 20-60 비중을 여기서 올린다.
                        # 드론을 올려 채우면 포락선이 매끈해져 208 ms 격자가 죽는다.
                        # 발자국 자체의 서브를 올리면 깊이와 격자를 같이 얻는다.
KICK_BODY = 1.25        # 발자국의 80-250 Hz 몸통. 「300 의 두께」가 여기서 나온다
KICK_DRIVE = 6.0        # 몸통 새추레이션 드라이브. 배음이 두께다.
                        # 3.2 에서는 3배 배음이 -14.7 dB 로 기준(-12 이내)에 못 미쳤다.
                        # 6.0 으로 올리니 -7.0 dB 다. 실측으로 정한 값이다.
WHOOSH_AIR = 2.40       # 우쉬의 2-8 kHz 공기 층
SIDECHAIN = 0.55        # 발자국이 나머지를 누르는 깊이. 격자를 전 대역에 새긴다
LOW_VERB = 0.35
G_FLOOR = 0.0           # 지속 바닥 50 Hz. 0 으로 둔다.
                        # 넣어 봤지만 지속 바닥 비가 0.340 에서 0.336 으로 오히려 내려갔다.
                        # 포락선은 신호의 합이지 포락선의 합이 아니라 그렇다.
                        # 대신 초저역 비중이 79 퍼센트로 튀고 우쉬가 0.14 퍼센트로 묻혔다.         # 저역 전용 긴 잔향. 타격 사이 골을 메워 지속 바닥을 올린다


# ------------------------------------------------------------------ 재료
def read_cuts():
    src = open(BUILD, encoding="utf-8").read()
    cuts = ast.literal_eval(re.search(r"^CUTS\s*=\s*(\[.*?^\])", src, re.S | re.M).group(1))
    f = re.search(r"^FORM_E,\s*TITLE_E\s*=\s*(\d+),\s*(\d+)", src, re.M)
    return cuts, int(f.group(1)), int(f.group(2))


# ------------------------------------------------------------------ 도구
def _shape(x, H):
    return np.fft.irfft(np.fft.rfft(x) * H, len(x))


def lp(x, fc, order=4):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return _shape(x, 1.0 / (1.0 + (f / fc) ** order))


def hp(x, fc, order=4):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return _shape(x, 1.0 / (1.0 + (fc / np.maximum(f, 1e-6)) ** order))


def band(x, lo, hi, order=4):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return _shape(x, (1.0 / (1.0 + (lo / np.maximum(f, 1e-6)) ** order))
                  * (1.0 / (1.0 + (f / hi) ** order)))


def shelf_down(x, fc, db):
    """fc 위를 db 만큼 내린다. 듄은 어두운 스펙트럼이다."""
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = 10 ** (db / 20.0)
    H = 1.0 + (g - 1.0) * (1.0 / (1.0 + (fc / np.maximum(f, 1e-6)) ** 2))
    return _shape(x, H)


def resonance(x, f0, q, gain):
    """포먼트 하나. 좁은 봉우리를 더한다."""
    f = np.fft.rfftfreq(len(x), 1 / SR)
    H = 1.0 + gain / (1.0 + ((f - f0) / (f0 / q)) ** 2)
    return _shape(x, H)


def env(n, atk, dec, curve=2.5, atk_curve=0.6):
    e = np.zeros(n)
    a = max(1, int(atk * SR))
    m = min(a, n)
    e[:m] = np.linspace(0, 1, m) ** atk_curve
    if n > a:
        k = n - a
        e[a:] = np.exp(-curve * np.linspace(0, 1, k) * (k / (dec * SR)) ** 0.0
                       * (np.arange(k) / max(1, dec * SR)) * 0 + 0)
        # 지수 감쇠. dec 는 e 배 떨어지는 데 걸리는 시간이다.
        e[a:] = np.exp(-(np.arange(k) / SR) / dec * curve)
    return e


def place(dst, sig, at, gain=1.0):
    i = int(round(at * SR))
    if i >= len(dst):
        return
    if i < 0:
        sig = sig[-i:]
        i = 0
    j = min(len(dst), i + len(sig))
    if j > i:
        dst[i:j] += sig[:j - i] * gain


def saturate(x, drive):
    """하모닉 디스토션. 깨끗한 사인은 얇다. 배음을 만들어 두께를 낸다."""
    if x.size == 0:
        return x
    p = np.abs(x).max()
    if p < 1e-12:
        return x
    return np.tanh(x / p * drive) / np.tanh(drive) * p


def reverb_ir(dur, fc, seed, predelay=0.02):
    """감쇠하는 잡음. 어둡게 깎는다. 규모는 잔향에서 나온다."""
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = r.normal(0, 1, n) * np.exp(-t / (dur / 4.5))
    ir[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    ir = lp(ir, fc)
    ir = np.concatenate([np.zeros(int(predelay * SR)), ir])
    return ir / np.sqrt((ir ** 2).sum())


def conv(x, ir):
    return fftconvolve(x, ir)[:len(x)]


def lufs_and_peak(path):
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0",
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    s = r.stderr or ""
    tail = s[s.rfind("Summary"):] if "Summary" in s else s
    def grab(k):
        m = re.search(k + r":\s*(-?\d+\.?\d*)", tail)
        return float(m.group(1)) if m else float("nan")
    return grab("I"), grab("Peak")


def write_wav(path, L, R):
    d = (np.clip(np.stack([L, R], axis=1), -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(d.tobytes())
    return d.nbytes


# ------------------------------------------------------------------ 본체
def main(open_e=OPEN_E, suffix="a"):
    CUTS, FORM_E, TITLE_E = read_cuts()

    # 그림 길이가 기준이다. 조립된 그림이 있으면 그것을 따른다.
    vf = os.path.join(ROOT, "work", "video-frames.json")
    ev_path = os.path.join(OUT, "title-events.json")
    EV = json.load(open(ev_path, encoding="utf-8"))
    T_OPEN = open_e * E                       # 오프닝 길이. A 는 2.5초, B 는 0
    if os.path.exists(vf):
        NF = json.load(open(vf, encoding="utf-8"))["frames"]
        DUR = NF / FPS
        # 오프닝을 포함한 길이다. 본편 시각은 T_OPEN 만큼 뒤로 간다.
    else:
        NF = None
        DUR = T_OPEN + EV["duration"]
    N = int(round(DUR * SR))
    t = np.arange(N) / SR

    # 컷 경계. 본편 시각에 오프닝을 더한다.
    bounds, acc = [], 0.0
    for c in CUTS:
        bounds.append(T_OPEN + acc)
        acc += c[2] * E
    T_WALK_END = T_OPEN + acc                     # rise 끝
    T_FORM_END = T_WALK_END + FORM_E * E
    T_DOLLY, T_RISE = bounds[6], bounds[7]
    T_TITLE = T_FORM_END - 0.5

    def pick(what, which=-1, after=0.0):
        v = [T_OPEN + e["t"] for e in EV["events"]
             if e["what"] == what and T_OPEN + e["t"] >= after]
        return v[which] if v else None

    T_WORD = pick("흰글자 등장", 0, T_TITLE)
    T_GLITCH = pick("흰글자 소멸", 0, T_TITLE)
    T_UNFOLD = pick("흰글자 등장", -1, T_GLITCH)
    T_CUT = pick("흰글자 소멸", -1, T_UNFOLD)
    T_KO = pick("티얼 등장", -1, T_CUT)
    T_LOCK = pick("락업 착지", -1, T_TITLE)

    print(f"길이 {DUR:.4f}초 ({N} 표본)  오프닝 {T_OPEN:.4f}초 = 8분음표 {OPEN_E}개")
    print(f"  첫 컷 {T_OPEN:.4f}  dolly {T_DOLLY:.4f}  rise {T_RISE:.4f}  "
          f"걷기 끝 {T_WALK_END:.4f}  타이틀 {T_TITLE:.4f}")

    # ---------------------------------------------- 층 1. 지속 서브 드론. 바닥이다.
    drone = np.zeros(N)
    for mul, amp in [(1.0, 1.00), (1.5, 0.34), (2.0, 0.34), (3.0, 0.12), (4.0, 0.060)]:
        drift = 1.0 + 0.0020 * np.sin(2 * np.pi * 0.043 * t + mul * 1.7)
        ph = 2 * np.pi * np.cumsum(SUB * mul * drift) / SR
        drone += np.sin(ph) * amp
    # 아주 느린 스웰 둘을 겹친다. 천천히 변한다.
    drone *= (1.0 + 0.16 * np.sin(2 * np.pi * t / 9.0 - 0.7)) \
             * (1.0 + 0.09 * np.sin(2 * np.pi * t / 3.7 + 1.1))
    drone = saturate(drone, 1.5)              # 배음을 아주 조금. 순수 사인은 스피커에서 사라진다
    drone /= np.abs(drone).max()
    # 다이내믹 대비. 오프닝은 거의 침묵. 첫 컷에서 바닥이 들어온다.
    if T_OPEN > 0.05:
        # A 판. 오프닝은 거의 침묵이고 첫 컷에서 바닥이 들어온다.
        lx = [0.0, T_OPEN * 0.35, T_OPEN - 0.02, T_OPEN]
        ly = [0.16, 0.30, 0.40, 0.62]
    else:
        # B 판. 오프닝이 없으므로 0.000초에서 바로 바닥이 서 있다.
        lx = [0.0, 0.05]
        ly = [0.0, 0.62]
    drone_lvl = np.interp(t,
        lx + [T_DOLLY, T_RISE, T_WALK_END, T_FORM_END, T_CUT, T_CUT + 0.25,
              T_KO, T_LOCK, T_LOCK + 1.4, DUR - 0.6, DUR],
        ly + [0.72, 0.86, 1.00, 0.80, 0.92, 0.42, 0.86, 0.70, 1.00, 0.92, 0.0])
    drone *= drone_lvl

    # ---------------------------------------------- 층 2. 발자국. 포화된 저역 타악.
    # 감쇠 봉투를 두 단으로 짠다. 여기가 이 사운드의 핵심이다.
    #
    # 한 단짜리 긴 감쇠(400-700 ms 한 방)로는 안 된다. 격자가 208 ms 인데
    # 감쇠가 620 ms 면 다음 타가 올 때 앞 타가 71 퍼센트 남아 있다. 포락선이
    # 거의 안 파이고 발 접지 격자가 사라진다. 첫 판에서 실측으로 확인했다.
    # 포락선 자기상관의 최대가 208 ms 가 아니라 93 ms 로 나왔다.
    #
    # 그래서 「빠른 타격 + 긴 꼬리」로 나눈다.
    #   타격 85 ms   포락선을 판다. 격자가 여기서 산다
    #   꼬리 580 ms  무게를 끈다. 400-700 ms 요구가 여기서 지켜진다
    # 208 ms 뒤 남는 양이 0.30 이라 포락선이 70 퍼센트 파인다.
    ATK_DEC, TAIL_DEC, TAIL_AMP = 0.085, 0.620, 0.38

    def two_stage(lt, scale=1.0):
        return (np.exp(-lt / (ATK_DEC * scale)) * (1.0 - TAIL_AMP)
                + np.exp(-lt / (TAIL_DEC * scale)) * TAIL_AMP)

    def kick(strong):
        scale = 1.0 if strong else 0.72
        n = int(1.60 * SR)
        lt = np.arange(n) / SR
        e = two_stage(lt, scale)
        # 서브. 58 Hz 에서 36 Hz 로 떨어진다. 무게가 여기서 난다.
        f_inst = 45 + 20 * np.exp(-lt / 0.085)
        sub = np.sin(2 * np.pi * np.cumsum(f_inst) / SR) * e
        # 몸통 80-250 Hz. 여기에 새추레이션을 건다. 「300 의 두께」가 여기서 나온다.
        # 90 Hz(2배)와 135 Hz(3배)에 정확히 둔다. 45 Hz 기음의 배음 계열이다.
        body = (np.sin(2 * np.pi * 90 * lt) * 0.85
                + np.sin(2 * np.pi * 135 * lt) * 0.60
                + np.sin(2 * np.pi * 180 * lt) * 0.30
                + band(rng.normal(0, 1, n), 80, 250) * 0.6)
        body *= two_stage(lt, scale * 0.60)
        body = saturate(band(body, 80, 250), KICK_DRIVE)
        # 흙. 아주 짧은 잡음 한 겹. 발이 땅을 긁는 소리다.
        dirt = band(rng.normal(0, 1, n), 180, 900) * np.exp(-lt / 0.045) * 0.30
        k = sub * KICK_SUB + body * KICK_BODY + dirt
        k[:int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
        return k / np.abs(k).max()

    K_STRONG, K_WEAK = kick(True), kick(False)
    ground = np.zeros(N)
    n_pulse = 0
    k = 0
    while T_OPEN + k * E <= T_WALK_END + 1e-9:
        at = T_OPEN + k * E
        strong = (k % 2 == 0)
        # 근접 컷을 뒤와 같은 무게로 시작한다. 1차본은 0.55 로 시작해 5 dB 작았다.
        lvl = np.interp(at, [T_OPEN, T_DOLLY, T_RISE, T_WALK_END], [0.94, 0.97, 1.00, 1.00])
        place(ground, K_STRONG if strong else K_WEAK, at, lvl * (1.0 if strong else 0.66))
        n_pulse += 1
        k += 1

    # 알갱이. 4096마리가 완전히 같은 위상이 아니다. 정격 펄스만 두면 메트로놈이 된다.
    AGENTS, JITTER = 96, 0.022
    grain = np.zeros(N)
    GL = int(0.34 * SR)
    glt = np.arange(GL) / SR
    g_sub = np.sin(2 * np.pi * np.cumsum(44 + 26 * np.exp(-glt / 0.03)) / SR)
    g_bod = band(rng.normal(0, 1, GL), 90, 320)
    for a in range(AGENTS):
        rate = GAIT * (1.0 + rng.normal(0, 0.004))
        ph = rng.normal(0, JITTER)
        amp = 0.5 + 0.5 * rng.random()
        dec = 0.09 + 0.07 * rng.random()
        g = (g_sub * 0.75 + g_bod * 0.45) * np.exp(-glt / dec)
        kk = 0
        while True:
            at = T_OPEN + kk / rate + ph
            if at > T_WALK_END:
                break
            if at >= T_OPEN - 0.05:
                place(grain, g, at, amp)
            kk += 1
    grain = lp(grain, 300.0)
    grain *= 0.9 / max(1e-9, np.abs(grain).max())

    # 컷 경계에서 저역을 살짝 눌렀다 놓는다. 컷이 소리로도 읽힌다. 깊게 누르지 않는다.
    duck = np.ones(N)
    for b in bounds[1:] + [T_WALK_END]:
        i = int(b * SR)
        w = int(0.050 * SR)
        a0, a1 = max(0, i - w // 3), min(N, i + w)
        if a1 > a0:
            prof = np.concatenate([np.linspace(1.0, 0.72, i - a0), np.linspace(0.72, 1.0, a1 - i)])
            duck[a0:a1] = np.minimum(duck[a0:a1], prof[:a1 - a0])
    foot = (ground + grain * 0.60) * duck
    foot *= np.interp(t, [0, T_WALK_END, T_WALK_END + 0.30], [1, 1, 0])

    # ---------------------------------------------- 층 3. 무언 보컬 패드. 듄의 결이다.
    # 포먼트 700 / 1200 / 2600 Hz. 아주 느린 비브라토. 크게 넣지 않는다. 배경이다.
    voice = np.zeros(N)
    for vi, (mul, det) in enumerate([(2.0, 0.0), (2.0, 0.004), (3.0, -0.003),
                                     (4.0, 0.002), (6.0, -0.0015)]):
        f0 = SUB * mul * (1.0 + det)
        vib = 1.0 + 0.0035 * np.sin(2 * np.pi * t / (5.5 + vi * 0.9) + vi)
        ph = 2 * np.pi * np.cumsum(f0 * vib) / SR
        v = np.zeros(N)
        for h, a in [(1, 1.0), (2, 0.55), (3, 0.38), (4, 0.24), (5, 0.17),
                     (6, 0.12), (8, 0.075), (10, 0.05), (12, 0.035)]:
            v += np.sin(ph * h + vi * 0.7) * a
        voice += v * (0.9 - 0.12 * vi)
    voice /= np.abs(voice).max()
    for f0, q, g in [(700.0, 7.0, 5.0), (1200.0, 9.0, 3.2), (2600.0, 11.0, 2.0)]:
        voice = resonance(voice, f0, q, g)
    voice = lp(voice, 3800.0)
    voice /= np.abs(voice).max()
    voice *= np.interp(t,
        [0.0, T_OPEN, T_DOLLY, T_RISE, T_WALK_END, T_FORM_END, T_CUT, T_CUT + 0.3,
         T_KO, T_LOCK, T_LOCK + 1.5, DUR - 0.6, DUR],
        [0.0, 0.06,   0.16,    0.34,   0.52,      0.34,        0.46,  0.10,
         0.44, 0.34,   0.58,        0.50,      0.0])

    # 상승 음형. rise 에서 네 음이 올라가 대형에 앉는다.
    fig = np.zeros(N)
    step = (T_WALK_END - T_RISE) / 4.0
    for i, mul in enumerate([2.0, 2.5, 3.0, 4.0]):
        ln = int(2.2 * SR)
        lt = np.arange(ln) / SR
        f0 = SUB * mul
        v = (np.sin(2 * np.pi * f0 * lt) + 0.30 * np.sin(2 * np.pi * 2 * f0 * lt)
             + 0.14 * np.sin(2 * np.pi * 3 * f0 * lt))
        place(fig, v * env(ln, 0.16, 0.95, 1.4), T_RISE + i * step, 0.20)

    # ---------------------------------------------- 층 4. 우쉬. 공기를 담는다.
    whoosh = np.zeros(N)

    def make_whoosh(pre, post, f_a, f_b, q, air):
        n = int((pre + post) * SR)
        lt = np.arange(n) / SR
        x = lt / (pre + post)
        nz = rng.normal(0, 1, n)
        out = np.zeros(n)
        nb = 24
        for i in range(nb):
            u = i / (nb - 1)
            fc = f_a * (f_b / f_a) ** u
            out += band(nz, fc * 0.78, fc * 1.30) * np.exp(-((x - u) ** 2) / (2 * q ** 2))
        out /= nb ** 0.5
        # 공기 층. 2-8 kHz 를 따로 얹는다. 1차본에 이것이 없어 2k-12k 가 1 퍼센트였다.
        a = band(rng.normal(0, 1, n), 2200, 8000)
        a *= np.exp(-((x - 0.62) ** 2) / (2 * 0.26 ** 2))
        out = out / max(1e-9, np.abs(out).max()) + a / max(1e-9, np.abs(a).max()) * air
        sh = np.where(lt < pre, (lt / pre) ** 1.8, np.exp(-3.0 * (lt - pre) / max(post, 1e-6)))
        return out * sh

    place(whoosh, make_whoosh(0.44, 0.40, 150, 4200, 0.20, WHOOSH_AIR), T_DOLLY - 0.44, 0.62)
    place(whoosh, make_whoosh(0.32, 0.36, 220, 6200, 0.18, WHOOSH_AIR * 1.15), T_RISE - 0.32, 0.70)
    LN = int(1.0 * SR)
    lift = np.sin(2 * np.pi * np.cumsum(np.linspace(48, 120, LN)) / SR) * env(LN, 0.34, 0.55, 1.6)
    place(whoosh, lift, T_RISE - 0.32, 0.40)

    # ---------------------------------------------- 층 5. 엔딩
    acc_l = np.zeros(N)
    WN = int(1.4 * SR)
    lt = np.arange(WN) / SR
    place(acc_l, np.sin(2 * np.pi * SUB * 2 * lt) * env(WN, 0.22, 0.70, 1.5), T_WORD, 0.16)

    GN = int(0.28 * SR)
    gl = band(rng.normal(0, 1, GN), 600, 7000)
    sq = np.sign(np.sin(2 * np.pi * 92 * np.arange(GN) / SR))
    gl = (gl * 0.8 + sq * 0.25) * env(GN, 0.001, 0.055, 5.0)
    st = int(0.012 * SR)
    for s in range(0, GN - st, st * 2):
        gl[s:s + st] *= 0.25
    place(acc_l, gl, T_GLITCH, 0.34)

    RN = int(0.60 * SR)
    lt = np.arange(RN) / SR
    riser = np.sin(2 * np.pi * np.cumsum(np.geomspace(300, 2000, RN)) / SR)
    riser += 0.35 * np.sin(2 * np.pi * np.cumsum(np.geomspace(450, 3000, RN)) / SR)
    place(acc_l, riser * (lt / lt[-1]) ** 1.8, T_UNFOLD - 0.60, 0.18)

    # 절단. 가장 큰 포인트다. 앞에 긴장을 쌓고 서브를 떨어뜨린다.
    SN = int(0.75 * SR)
    lt = np.arange(SN) / SR
    pre = band(rng.normal(0, 1, SN), 350, 6500) * (lt / lt[-1]) ** 3.0
    pre += np.sin(2 * np.pi * np.cumsum(np.geomspace(200, 850, SN)) / SR) * (lt / lt[-1]) ** 3.4 * 0.5
    place(acc_l, pre, T_CUT - 0.75, 0.34)
    CN = int(0.34 * SR)
    lt = np.arange(CN) / SR
    blade = band(rng.normal(0, 1, CN), 2400, 9500) * env(CN, 0.0005, 0.050, 6.0)
    blade += np.sin(2 * np.pi * 2900 * lt) * env(CN, 0.0005, 0.020, 8.0) * 0.30
    place(acc_l, blade, T_CUT, 0.30)
    DN = int(2.4 * SR)
    lt = np.arange(DN) / SR
    drop = np.sin(2 * np.pi * np.cumsum(28 + 58 * np.exp(-lt / 0.085)) / SR) * np.exp(-lt / 0.85)
    drop = saturate(drop, 2.2)
    place(acc_l, drop, T_CUT, 0.90)

    # 락업 착지. 낮은 임팩트 한 방과 긴 꼬리. 때리지 않는다.
    IN_ = int(2.8 * SR)
    lt = np.arange(IN_) / SR
    land = np.sin(2 * np.pi * np.cumsum(34 + 24 * np.exp(-lt / 0.11)) / SR) * np.exp(-lt / 1.05)
    land = saturate(land, 2.0)
    air = band(rng.normal(0, 1, IN_), 1600, 7000) * env(IN_, 0.008, 0.13, 4.0) * 0.075
    place(acc_l, land + air, T_LOCK, 0.55)
    tail = DUR - T_LOCK
    for mul, amp in [(1.0, 0.22), (1.5, 0.13), (2.0, 0.20), (3.0, 0.13), (4.0, 0.080)]:
        ln = int(tail * SR)
        lt = np.arange(ln) / SR
        v = np.sin(2 * np.pi * SUB * mul * lt) + 0.20 * np.sin(2 * np.pi * 2 * SUB * mul * lt)
        e = np.minimum(1.0, lt / 0.9) * np.interp(lt, [0, tail - 0.6, tail], [1, 1, 0])
        place(acc_l, v * e, T_LOCK, amp)

    # ---------------------------------------------- 층 6. 오프닝
    # 멀리서 들어온다. 간격을 넓게 시작해 208 ms 로 좁혀 온다.
    # 저주파만 남는다. 첫 컷이 붙는 순간 필터가 열린다. 그림보다 소리가 먼저 도착한다.
    # 자리를 뒤에서부터 잡는다. 마지막 타가 첫 컷 한 박자 앞(T_OPEN - E)에 오고
    # 그 다음 박이 첫 컷의 첫 발자국이다. 그래야 첫 컷이 박자 위에 떨어진다.
    # 간격은 뒤로 갈수록 넓어진다. 들을 때는 넓은 데서 208 ms 로 좁혀 오는 것이 된다.
    opening = np.zeros(N)
    times, at, gap = [], T_OPEN - E, E
    while T_OPEN > 0.05 and at > 0.12:
        times.append(at)
        gap *= 1.36
        at -= gap
    times = sorted(times)
    hits = len(times)
    for at in times:
        frac = at / max(T_OPEN, 1e-9)
        # 멀리 있는 것은 고역이 없다. 다가오면서 필터가 열린다.
        fc = 90.0 * (420.0 / 90.0) ** (frac ** 1.5)
        far = lp(K_STRONG, fc)
        place(opening, far, at, (0.34 + 0.62 * frac ** 1.4) / max(1e-9, np.abs(far).max()))
    if T_OPEN > 0.05:
        wind = band(rng.normal(0, 1, N), 40, 800) * np.interp(
            t, [0, T_OPEN * 0.5, T_OPEN, T_OPEN + 0.4], [0.10, 0.24, 0.30, 0.0])
        opening = opening + wind * 0.5
        # 오프닝에도 서브 바닥을 깐다. 「거의 침묵」이 「아무것도 없음」은 아니다.
        # 이것이 없으면 A 판에서 두 가지가 깨진다. 실측으로 확인했다.
        #   초저역 20-60 이 22.9 퍼센트로 희석된다 (오프닝이 길이의 12 퍼센트다)
        #   포락선에 큰 느린 성분이 생겨 208 ms 가 최대가 아니게 된다
        # 바닥을 깔면 둘 다 풀린다. 소리는 여전히 아주 작다.
        bed = (np.sin(2 * np.pi * SUB * t) + 0.35 * np.sin(2 * np.pi * SUB * 1.5 * t))
        bed *= np.interp(t, [0, T_OPEN * 0.30, T_OPEN, T_OPEN + 0.25],
                            [0.30, 0.52, 0.70, 0.0])
        opening = opening + bed * 0.55

    # ---------------------------------------------- 합치고 마감
    # 지속 바닥. 50 Hz 정현파 한 겹을 사이드체인 없이 깐다.
    # 40-60 Hz 창 한가운데다. 이것이 「타격 사이가 안 비게」 하는 층이다.
    # 더킹을 걸지 않는 것이 핵심이다. 눌리면 골이 다시 생긴다.
    # 비(10퍼센타일/90퍼센타일)는 양쪽에 같은 양을 더하면 오른다.
    floor50 = np.sin(2 * np.pi * 50.0 * t) + 0.30 * np.sin(2 * np.pi * 50.0 * 2 * t + 0.7)
    floor50 *= np.interp(t, [0, max(T_OPEN, 0.05), T_WALK_END, T_FORM_END, DUR - 0.5, DUR],
                            [0.55, 1.00, 1.00, 0.80, 0.70, 0.0])

    # 사이드체인 더킹. 발자국이 나머지를 208 ms 마다 눌렀다 놓는다.
    # 드론과 잔향은 그 자체로 매끈해서 포락선에 격자를 안 남긴다. 눌러야 남는다.
    # 짐머 결의 「숨쉬는」 느낌도 여기서 난다.
    trig = np.abs(ground) + np.abs(opening) * 0.8
    trig = lp(trig, 12.0)
    trig = trig / max(1e-9, trig.max())
    duck_sc = 1.0 - SIDECHAIN * np.clip(trig * 1.6, 0, 1)

    # 우쉬는 안 누른다. 전환은 뚫고 나와야 하고, 누르면 2k-12k 공기가 같이 죽는다.
    # 첫 판에서 우쉬까지 눌렀더니 5.5 퍼센트가 2.1 퍼센트로 떨어졌다.
    wide_ducked = voice * 0.60 * G_VOICE + fig * G_FIG
    wide_free = whoosh * G_WHOOSH + acc_l * 0.45 * G_END
    dry_wide = wide_ducked * duck_sc + wide_free
    dry_mono = (drone * G_DRONE * duck_sc + floor50 * G_FLOOR + foot * G_FOOT + opening * G_OPEN
                + acc_l * 0.55 * G_END + voice * 0.45 * G_VOICE * duck_sc)

    # 잔향 3초. 규모는 잔향에서 나온다. 좌우를 다른 잡음으로 만들어 폭을 낸다.
    irL = reverb_ir(3.0, 3200, 11, 0.018)
    irR = reverb_ir(3.0, 3200, 29, 0.026)
    wetL = conv(dry_wide * 0.55 + dry_mono * 0.30, irL)
    wetR = conv(dry_wide * 0.55 + dry_mono * 0.30, irR)
    # 저역에만 긴 잔향을 하나 더 보낸다. 타격 사이의 골을 메운다.
    # 지속 바닥 비(40-60 Hz 10/90 퍼센타일)가 이것으로 오른다.
    irLow = reverb_ir(2.6, 160, 91, 0.006)
    low_send = lp(foot * G_FOOT + drone * G_DRONE * 0.5, 90.0)
    wet_low = conv(low_send, irLow) * LOW_VERB
    # 잔향에도 같은 더킹을 건다. 3초 꼬리가 안 눌리면 격자가 다시 메워진다.
    wetL, wetR = wetL * duck_sc, wetR * duck_sc

    # 하스 지연 18 ms. 듄의 공간감은 폭에서 온다. 저역은 모노로 둔다.
    HAAS = int(0.018 * SR)
    wide_d = np.concatenate([np.zeros(HAAS), dry_wide])[:N]
    L = dry_mono + dry_wide * 0.92 + wide_d * 0.30 + wetL * 1.7 + wet_low
    R = dry_mono + wide_d * 0.92 + dry_wide * 0.30 + wetR * 1.7 + wet_low
    # 120 Hz 아래는 좌우를 같게 한다. 저역이 갈라지면 스피커에서 사라진다.
    m = (L + R) * 0.5
    lowm = lp(m, 120.0)
    L = hp(L, 120.0) + lowm
    R = hp(R, 120.0) + lowm

    L = shelf_down(L, 6500.0, -9.0)           # 6.5 kHz 위를 깎는다. 듄은 어둡다
    R = shelf_down(R, 6500.0, -9.0)
    L, R = hp(L, 24.0), hp(R, 24.0)           # 스피커 보호
    fade = np.interp(t, [0, 0.05, DUR - 0.45, DUR], [0, 1, 1, 0])
    L, R = L * fade, R * fade

    pk = max(np.abs(L).max(), np.abs(R).max())
    L, R = L / pk * 0.92, R / pk * 0.92

    os.makedirs(OUT, exist_ok=True)
    path = os.path.normpath(os.path.join(OUT, f"foothold-launch-sound-{suffix}.wav"))
    write_wav(path, L, R)

    # 라우드니스를 재서 맞춘다. 재고 고치고 다시 잰다.
    for it in range(6):
        I, tp = lufs_and_peak(path)
        d_l = TARGET_LUFS - I
        d_p = TARGET_TP - tp
        g = min(d_l, d_p)
        print(f"  마감 {it}: {I:7.2f} LUFS · 트루피크 {tp:6.2f} dBTP · 라우드니스 보정 {d_l:+.2f} dB")
        if abs(d_l) < 0.15 and d_p > -0.05:
            break
        # 라우드니스를 먼저 맞추고, 넘치는 피크는 소프트 클립으로 눌러 천장 아래로 넣는다.
        # 예전에는 min(라우드니스 보정, 피크 여유) 를 썼는데 피크에 걸리면 게인이 0 이 되어
        # -18.6 LUFS 에서 멈췄다. 크레스트가 13.9 dB 나 있어 누를 여유가 있었는데도 그랬다.
        L, R = L * 10 ** (d_l / 20.0), R * 10 ** (d_l / 20.0)
        ceil = 10 ** (TARGET_TP / 20.0) * 0.94        # 트루피크 여유를 둔다
        pkn = max(np.abs(L).max(), np.abs(R).max())
        if pkn > ceil:
            drive = min(3.0, max(1.05, pkn / ceil))
            L = np.tanh(L / pkn * drive) / np.tanh(drive) * ceil
            R = np.tanh(R / pkn * drive) / np.tanh(drive) * ceil
        write_wav(path, L, R)
    nb = write_wav(path, L, R)
    I, tp = lufs_and_peak(path)

    # 발자국 한 방을 따로 남긴다. 저역 감쇠와 배음은 섞인 소리에서 못 잰다.
    # 208 ms 마다 다음 타가 오기 때문에 400 ms 감쇠를 관찰할 자리가 없다.
    kref = os.path.normpath(os.path.join(OUT, "kick-reference.wav"))
    write_wav(kref, K_STRONG * 0.9, K_STRONG * 0.9)

    corr = float(np.corrcoef(L, R)[0, 1])
    spec = {
        "duration_s": round(DUR, 4), "frames": NF, "sr": SR,
        "opening_s": round(T_OPEN, 4), "opening_eighths": OPEN_E, "opening_hits": hits, "opening_gaps_s": [round(g, 4) for g in
            [times[i + 1] - times[i] for i in range(len(times) - 1)]],
        "eighth_ms": round(E * 1000, 3), "bpm": 144, "gait_hz": round(GAIT, 4),
        "sub_root_hz": round(SUB, 3),
        "cut_bounds_s": [round(b, 4) for b in bounds],
        "walk_end_s": round(T_WALK_END, 4), "formation_end_s": round(T_FORM_END, 4),
        "title_start_s": round(T_TITLE, 4),
        "whoosh_s": [round(T_DOLLY, 4), round(T_RISE, 4)],
        "ending": {"wordmark": T_WORD, "glitch": T_GLITCH, "unfold": T_UNFOLD,
                   "cut": T_CUT, "korean": T_KO, "lockup": T_LOCK},
        "ground_pulses": n_pulse, "grain_agents": AGENTS,
        "kick_attack_decay_s": ATK_DEC, "kick_tail_decay_s": TAIL_DEC,
        "kick_tail_amp": TAIL_AMP, "sidechain": SIDECHAIN, "reverb_s": 3.0, "haas_ms": 18.0,
        "formants_hz": [700, 1200, 2600], "shelf_hz": 6500, "shelf_db": -9.0,
        "lufs": I, "true_peak_dbtp": tp, "lr_correlation": round(corr, 4),
    }
    json.dump(spec, open(os.path.join(OUT, "sound-spec.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"\n썼다  {path}  {nb/1e6:.1f} MB")
    print(f"  {DUR:.3f}초 · 오프닝 {T_OPEN:.3f}초(타격 {hits}회) · 서브 기음 {SUB:.2f} Hz")
    print(f"  발자국 {n_pulse}개 · 타격 {ATK_DEC*1000:.0f} ms + 꼬리 {TAIL_DEC*1000:.0f} ms"
          f"(진폭 {TAIL_AMP:.2f}) · 알갱이 {AGENTS}마리 · 사이드체인 {SIDECHAIN:.2f}")
    print(f"  잔향 3.0초 · 하스 18 ms · 6.5 kHz 위 -9 dB")
    print(f"  {I:.2f} LUFS · 트루피크 {tp:.2f} dBTP · 좌우 상관 {corr:+.3f}")


if __name__ == "__main__":
    # 두 판을 낸다. B 는 오프닝 없는 20.56초, A 는 오프닝 2.5초를 앞에 둔 23.06초.
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("b", "both"):
        print("### B 판 (오프닝 없음)")
        main(open_e=0, suffix="b")
    if which in ("a", "both"):
        print("\n### A 판 (오프닝 2.5초)")
        main(open_e=OPEN_E, suffix="a")
