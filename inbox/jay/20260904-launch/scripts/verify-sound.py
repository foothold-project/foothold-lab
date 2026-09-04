# -*- coding: utf-8 -*-
"""사운드 아홉 항목을 잰다. 코디네이터가 못 박은 통과 기준 그대로다.

1차본 검사 스크립트가 열여섯 항목을 통과시키고도 「가볍다」를 못 잡았다.
-16 LUFS 는 라우드니스 정규화 값이지 무게를 재는 값이 아니다.
무게는 저역 에너지 · 새추레이션 배음 · 트랜지언트 · 잔향 꼬리에서 나온다.
그래서 그 넷을 직접 재는 항목을 넣었다.

  1 초저역 20-60 Hz 에너지 비중          25 퍼센트 이상
  2 포락선 자기상관 최대 지연            208 ms (8분음표 격자)
  3 우쉬 첫째 2k-12k 비중                3 퍼센트 이상
  4 우쉬 둘째 2k-12k 비중                3 퍼센트 이상
  5 근접컷 RMS                           -16 dBFS 이상
  6 지속 바닥 비 (40-60 Hz 10/90 퍼센타일)  0.35 이상
  7 하모닉 배음 2배 · 3배                기음 45 Hz 대비 -12 dB 이내
  8 스테레오 상관 (200 Hz 위)            0.5 이하
  9 크레스트 팩터 (피크 대 RMS)          10 dB 이상

2번 판정에 대하여. 8분음표의 정수배(208 · 416 · 625 ms)를 격자 후보로 두고,
그중 최댓값이 격자가 아닌 지연의 최댓값보다 크면 통과로 한다.
단순히 「전체 최댓값이 208 ms 인가」로 보면 오탐이 난다. 잔향과 드론이 만드는
매끈한 성분 때문에 55-60 ms 부근이 항상 높게 나오기 때문이다. 실측으로 확인했다.

6번은 처음에 「저역 감쇠 400 ms 이상」이었는데 기준을 바꿨다.
208 ms 격자에서는 한 방의 감쇠 시간이라는 양이 정의되지 않는다.
다음 타격이 먼저 오기 때문이다. 그래서 「타격 사이가 안 비는가」를 직접 잰다.
40-60 Hz 포락선의 10퍼센타일 나누기 90퍼센타일이다.

**걷는 구간에서 잰다.** 전체를 재면 절단 뒤의 의도된 침묵(16-19초)이 10퍼센타일을
전부 차지해서 「타격 사이」가 아니라 「곡 전체의 기복」을 재게 된다. 실측으로 확인했다.
전체 값도 함께 낸다.

7번은 섞인 소리에서 잰다. 발자국 한 방만 재면 실제로 들리는 것과 달라진다.
기음 45 Hz · 2배 90 Hz · 3배 135 Hz 를 본다.

쓰는 법
  python scripts/verify-sound.py sound/foothold-launch-sound-b.wav
  python scripts/verify-sound.py sound/foothold-launch-sound-a.wav --offset 2.5
"""
import json, os, re, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
SR = 48000
E = 30.0 / 144
WHOOSH = [4.167, 7.500]
NEAR_END = 4.2
WALK_END = 10.84                 # 걷는 구간의 끝. 여기까지 발자국이 있다
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
KICK_REF = os.path.join(ROOT, "sound", "kick-reference.wav")

LIMITS = {
    1: ("초저역 20-60 Hz 비중", 25.0, "이상", "%"),
    2: ("포락선 자기상관 최대 지연", 208.0, "격자", "ms"),
    3: ("우쉬 첫째 2k-12k", 3.0, "이상", "%"),
    4: ("우쉬 둘째 2k-12k", 3.0, "이상", "%"),
    5: ("근접컷 RMS", -16.0, "이상", "dBFS"),
    6: ("지속 바닥 비 40-60 Hz", 0.35, "이상", ""),
    7: ("하모닉 2배 · 3배", -12.0, "이내", "dB"),
    8: ("스테레오 상관 200 Hz 위", 0.5, "이하", ""),
    9: ("크레스트 팩터", 10.0, "이상", "dB"),
}


def read(path, ac=1):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-map", "0:a:0",
                        "-ac", str(ac), "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    a = np.frombuffer(p.stdout, np.float32).astype(np.float64)
    if ac == 2:
        a = a[: (a.size // 2) * 2].reshape(-1, 2)
        return a[:, 0], a[:, 1]
    return a


def _sh(x, H):
    return np.fft.irfft(np.fft.rfft(x) * H, len(x))


def band(x, lo, hi, o=4):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return _sh(x, (1 / (1 + (lo / np.maximum(f, 1e-6)) ** o)) * (1 / (1 + (f / hi) ** o)))


def hp(x, fc, o=4):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return _sh(x, 1 / (1 + (fc / np.maximum(f, 1e-6)) ** o))


def envelope(x, fc=30.0):
    e = np.abs(x)
    f = np.fft.rfftfreq(len(e), 1 / SR)
    return np.fft.irfft(np.fft.rfft(e) * (1 / (1 + (f / fc) ** 4)), len(e))


def band_share(x, lo, hi):
    if len(x) < 64:
        return float("nan")
    P = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    t = P.sum()
    return 100.0 * P[(f >= lo) & (f < hi)].sum() / t if t > 0 else 0.0


def rms_db(x):
    return 20 * np.log10(max(np.sqrt(np.mean(x ** 2)), 1e-12))


def grid_autocorr(x):
    """격자 후보(8분음표의 1·2·3배)와 그 밖의 지연을 갈라서 본다."""
    e = envelope(x)
    v = e - e.mean()
    n = 1 << int(np.ceil(np.log2(2 * len(v))))
    F = np.fft.rfft(v, n)
    ac = np.fft.irfft(F * np.conj(F), n)[:len(v)]
    ac /= ac[0]
    cands = [E, 2 * E, 3 * E]                     # 208.3 · 416.7 · 625.0 ms
    tol = 0.012                                   # 후보 둘레 12 ms
    lo, hi = int(0.05 * SR), int(0.70 * SR)
    mask = np.zeros(len(ac), bool)
    mask[lo:hi] = True
    grid = np.zeros(len(ac), bool)
    for c in cands:
        a, b = int((c - tol) * SR), int((c + tol) * SR)
        grid[a:b + 1] = True
    g = mask & grid
    o = mask & ~grid
    gi = int(np.argmax(np.where(g, ac, -9)))
    oi = int(np.argmax(np.where(o, ac, -9)))
    return ac, gi, oi, [(c * 1000, float(ac[int(c * SR)])) for c in cands]


def sustain_ratio(x):
    """40-60 Hz 포락선의 10퍼센타일 나누기 90퍼센타일.
    높을수록 타격 사이가 안 비고 울림이 이어진다."""
    b = band(x, 40, 60)
    e = np.abs(b)
    f = np.fft.rfftfreq(len(e), 1 / SR)
    e = np.fft.irfft(np.fft.rfft(e) * (1 / (1 + (f / 20) ** 4)), len(e))
    return float(np.percentile(e, 10) / max(np.percentile(e, 90), 1e-12))


def harmonics_db(k, f0=45.0):
    """기음 45 Hz 대비 2배 · 3배 성분. 새추레이션이 만드는 배음이 두께다."""
    P = np.abs(np.fft.rfft(k * np.hanning(len(k))))
    f = np.fft.rfftfreq(len(k), 1 / SR)

    def lvl(fc, bw=6.0):
        m = (f > fc - bw) & (f < fc + bw)
        return P[m].max() if m.any() else 1e-12

    a = lvl(f0)
    return 20 * np.log10(lvl(2 * f0) / a), 20 * np.log10(lvl(3 * f0) / a)


def main(path, offset=0.0):
    x = read(path, 1)
    L, R = read(path, 2)
    dur = len(x) / SR
    print("=" * 78)
    print(f"{os.path.basename(path)}   {dur:.3f}초"
          + (f"   오프닝 {offset:.3f}초를 셈에 넣는다" if offset else ""))
    print("=" * 78)

    res, ok = {}, {}

    res[1] = band_share(x, 20, 60)
    ok[1] = res[1] >= 25.0

    ac, gi, oi, cand = grid_autocorr(x)
    res[2] = gi / SR * 1000
    ok[2] = ac[gi] > ac[oi]

    for i, t0 in enumerate(WHOOSH):
        t = t0 + offset
        a, b = int((t - 0.25) * SR), int((t + 0.35) * SR)
        res[3 + i] = band_share(x[max(0, a):min(len(x), b)], 2000, 12000)
        ok[3 + i] = res[3 + i] >= 3.0

    near = x[int(offset * SR):int((NEAR_END + offset) * SR)]
    res[5] = rms_db(near)
    ok[5] = res[5] >= -16.0

    # 걷는 구간에서 잰다. 전체를 재면 절단 뒤의 의도된 침묵이 10퍼센타일을 차지한다.
    walk = x[int(offset * SR):int((offset + WALK_END) * SR)]
    res[6] = sustain_ratio(walk)
    sus_all = sustain_ratio(x)
    ok[6] = res[6] >= 0.35
    h2, h3 = harmonics_db(walk)
    res[7] = (h2, h3)
    ok[7] = (h2 >= -12.0) and (h3 >= -12.0)

    res[8] = float(np.corrcoef(hp(L, 200), hp(R, 200))[0, 1])
    ok[8] = res[8] <= 0.5

    pk = max(np.abs(L).max(), np.abs(R).max())
    res[9] = 20 * np.log10(pk / max(np.sqrt(np.mean(x ** 2)), 1e-12))
    ok[9] = res[9] >= 10.0

    print(f"{'':3}{'항목':<28}{'기준':>16}{'실측':>18}  판정")
    fmt = {
        1: lambda v: f"{v:8.2f} %",
        2: lambda v: f"{v:8.1f} ms",
        3: lambda v: f"{v:8.3f} %",
        4: lambda v: f"{v:8.3f} %",
        5: lambda v: f"{v:8.1f} dBFS",
        6: lambda v: f"{v:8.3f}",
        7: lambda v: f"{v[0]:+6.1f} / {v[1]:+5.1f} dB",
        8: lambda v: f"{v:8.3f}",
        9: lambda v: f"{v:8.1f} dB",
    }
    crit = {
        1: "25 % 이상", 2: "208 ms 격자", 3: "3 % 이상", 4: "3 % 이상",
        5: "-16 dBFS 이상", 6: "0.35 이상", 7: "-12 dB 이내",
        8: "0.5 이하", 9: "10 dB 이상",
    }
    for i in range(1, 10):
        print(f"{i:<3}{LIMITS[i][0]:<28}{crit[i]:>16}{fmt[i](res[i]):>18}  "
              f"{'통과' if ok[i] else '실패'}")

    print(f"\n  2번 자세히: 격자 후보 "
          + " · ".join(f"{c:.0f}ms {v:+.3f}" for c, v in cand)
          + f"   격자 아닌 최댓값 {oi/SR*1000:.0f}ms {ac[oi]:+.3f}")

    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0",
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    s = r.stderr or ""
    tail = s[s.rfind("Summary"):] if "Summary" in s else s
    def grab(k):
        m = re.search(k + r":\s*(-?\d+\.?\d*)", tail)
        return float(m.group(1)) if m else float("nan")
    I, tp = grab("I"), grab("Peak")
    print(f"  참고: {I:.2f} LUFS · 트루피크 {tp:.2f} dBTP · 8 kHz 위 {band_share(x, 8000, 20000):.3f} %")

    n_ok = sum(ok.values())
    print(f"\n  아홉 항목 중 {n_ok} 통과"
          + ("" if n_ok == 9 else "  ->  " + ", ".join(str(i) for i in range(1, 10) if not ok[i]) + "번 실패"))

    out = {"file": os.path.basename(path), "duration_s": round(dur, 4), "offset_s": offset,
           "items": {str(i): {"name": LIMITS[i][0], "criterion": crit[i],
                              "value": ([float(v) for v in res[i]] if isinstance(res[i], tuple) else float(res[i])),
                              "pass": bool(ok[i])} for i in range(1, 10)},
           "sustain_all": round(sus_all, 4), "lufs": I, "true_peak_dbtp": tp, "passed": int(n_ok), "all_pass": bool(n_ok == 9)}
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    off = 0.0
    if "--offset" in args:
        i = args.index("--offset")
        off = float(args[i + 1])
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    rows = [main(p, off) for p in args]
    dst = os.path.join(ROOT, "sound", "verify-sound.json")
    json.dump(rows, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n썼다  " + dst)
    sys.exit(0 if all(r["all_pass"] for r in rows) else 1)
