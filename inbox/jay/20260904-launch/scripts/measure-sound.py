# -*- coding: utf-8 -*-
"""사운드를 잰다. 코디네이터가 1차본에서 낸 여섯 값을 같은 방법으로 다시 낸다.

먼저 1차본에 걸어서 코디네이터 값과 맞는지 확인한다. 맞아야 새 값도 믿을 수 있다.

  1 포락선 자기상관 208 ms 지연        1차본 0.657
  2 가장 강한 주기                     1차본 130 ms = 7.69 Hz
  3 우쉬 두 곳 2k-12k 비중             1차본 0.711 퍼센트 · 0.961 퍼센트
  4 0.0-4.2초 근접컷 RMS               1차본 -21.9 dBFS
  5 초저역 20-60 Hz 비중               1차본 11.88 퍼센트
  6 라우드니스와 트루피크              ffmpeg ebur128

쓰는 법
  python scripts/measure-sound.py <mp4 또는 wav> [<또 하나> ...]
"""
import json, os, re, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
SR = 48000
WHOOSH = [4.167, 7.500]          # 카메라가 실제로 움직이는 두 곳
NEAR_END = 4.2                   # 근접 컷 구간의 끝


def mono(path, sr=SR):
    """48 kHz 모노 float 로 읽는다. 코디네이터가 잰 것과 같은 조건이다."""
    p = subprocess.run([FF, "-v", "error", "-i", path, "-map", "0:a:0",
                        "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    return np.frombuffer(p.stdout, np.float32).astype(np.float64)


def envelope(x, sr=SR, fc=30.0):
    """전파 정류 뒤 저역통과. 발자국의 두드림만 남는다."""
    e = np.abs(x)
    f = np.fft.rfftfreq(len(e), 1 / sr)
    E = np.fft.rfft(e) * (1.0 / (1.0 + (f / fc) ** 4))
    return np.fft.irfft(E, len(e))


def autocorr(e, sr=SR, lo_ms=60.0, hi_ms=600.0):
    """포락선 자기상관. 평균을 빼고 0 지연으로 정규화한다."""
    v = e - e.mean()
    n = 1 << int(np.ceil(np.log2(2 * len(v))))
    F = np.fft.rfft(v, n)
    ac = np.fft.irfft(F * np.conj(F), n)[:len(v)]
    ac /= ac[0]
    lo, hi = int(lo_ms * sr / 1000), int(hi_ms * sr / 1000)
    lag = int(np.argmax(ac[lo:hi])) + lo
    return ac, lag


def band_share(x, lo, hi, sr=SR):
    """구간 전체 에너지에서 lo-hi Hz 가 차지하는 비중(퍼센트)."""
    if len(x) < 64:
        return float("nan")
    w = np.hanning(len(x))
    P = np.abs(np.fft.rfft(x * w)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    tot = P.sum()
    if tot <= 0:
        return 0.0
    return 100.0 * P[(f >= lo) & (f < hi)].sum() / tot


def stereo(path, sr=SR):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-map", "0:a:0",
                        "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.float32).astype(np.float64)
    if a.size < 4:
        return None
    a = a[: (a.size // 2) * 2].reshape(-1, 2)
    return a[:, 0], a[:, 1]


def hp200(x, sr=SR):
    f = np.fft.rfftfreq(len(x), 1 / sr)
    return np.fft.irfft(np.fft.rfft(x) * (1.0 / (1.0 + (200.0 / np.maximum(f, 1e-6)) ** 4)), len(x))


def rms_db(x):
    return 20 * np.log10(max(np.sqrt(np.mean(x ** 2)), 1e-12))


def loudness(path):
    """ebur128 로 통합 라우드니스와 트루피크를 읽는다."""
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", path,
                        "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    s = r.stderr or ""
    tail = s[s.rfind("Summary"):] if "Summary" in s else s
    def grab(key):
        m = re.search(key + r":\s*(-?\d+\.?\d*)", tail)
        return float(m.group(1)) if m else float("nan")
    return grab("I"), grab("Peak")


def report(path, offset=0.0):
    """offset 은 오프닝 길이다. 컷 시각이 그만큼 뒤로 가 있으므로 창을 옮겨 잰다.
    1차본과 같은 자리를 재야 견줄 수 있다."""
    x = mono(path)
    dur = len(x) / SR
    print("=" * 74)
    print(f"{os.path.basename(path)}   {dur:.3f}초 · {SR} Hz 모노로 내려 잰다"
          + (f"   (오프닝 {offset:.3f}초를 셈에 넣는다)" if offset else ""))

    e = envelope(x)
    ac, lag = autocorr(e)
    at208 = float(ac[int(round(0.2083333 * SR))])
    print(f"\n  1 포락선 자기상관 208 ms 지연     {at208:+.3f}")
    print(f"  2 가장 강한 주기                  {lag/SR*1000:6.1f} ms = {SR/lag:5.2f} Hz "
          f"(상관 {ac[lag]:+.3f})")
    ok_grid = abs(lag / SR - 0.2083333) < 0.008
    print(f"      {'208 ms 가 최대다' if ok_grid else '208 ms 가 최대가 아니다'}")

    print(f"\n  3 우쉬 2k-12k 비중")
    wh = []
    for t0 in WHOOSH:
        t = t0 + offset
        a, b = int((t - 0.25) * SR), int((t + 0.35) * SR)
        seg = x[max(0, a):min(len(x), b)]
        s = band_share(seg, 2000, 12000)
        wh.append(s)
        print(f"      {t:6.3f}초 앞뒤 0.6초   {s:6.3f} 퍼센트")

    near = x[int(offset * SR):int((NEAR_END + offset) * SR)]
    far = x[int((NEAR_END + offset) * SR):]
    print(f"\n  4 근접컷 RMS  0.0-{NEAR_END}초   {rms_db(near):6.1f} dBFS"
          f"   (뒤 {rms_db(far):6.1f} dBFS · 차 {rms_db(near)-rms_db(far):+.1f} dB)")

    sub = band_share(x, 20, 60)
    low = band_share(x, 20, 120)
    hi8 = band_share(x, 8000, 20000)
    print(f"\n  5 초저역 20-60 Hz 비중            {sub:6.2f} 퍼센트")
    print(f"      20-120 Hz                     {low:6.2f} 퍼센트")
    print(f"      8 kHz 위                      {hi8:6.3f} 퍼센트 (듄은 어둡다. 낮아야 한다)")

    I, pk = loudness(path)
    print(f"\n  6 라우드니스 {I:7.2f} LUFS   트루피크 {pk:6.2f} dBTP")

    LR = stereo(path)
    if LR is None:
        c_all = c_hi = float("nan")
    else:
        L, R = LR
        c_all = float(np.corrcoef(L, R)[0, 1])
        c_hi = float(np.corrcoef(hp200(L), hp200(R))[0, 1])
    print(f"  7 좌우 상관  전대역 {c_all:+.3f}   200 Hz 위 {c_hi:+.3f}")
    print(f"      저역은 모노로 두는 것이 맞다. 폭은 200 Hz 위에서 본다.")

    return {"file": os.path.basename(path), "duration_s": round(dur, 4),
            "autocorr_208ms": round(at208, 4),
            "peak_period_ms": round(lag / SR * 1000, 2),
            "peak_period_hz": round(SR / lag, 4),
            "grid_is_peak": bool(ok_grid),
            "whoosh_2k12k_pct": [round(v, 4) for v in wh],
            "near_rms_dbfs": round(rms_db(near), 2),
            "far_rms_dbfs": round(rms_db(far), 2),
            "sub_20_60_pct": round(sub, 3),
            "low_20_120_pct": round(low, 3),
            "above_8k_pct": round(hi8, 4),
            "lufs": I, "true_peak_dbtp": pk,
            "lr_corr_full": round(c_all, 4), "lr_corr_above200": round(c_hi, 4)}


if __name__ == "__main__":
    args = sys.argv[1:]
    off = 0.0
    if "--offset" in args:
        i = args.index("--offset")
        off = float(args[i + 1])
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    out = [report(p, off) for p in args]
    here = os.path.dirname(os.path.abspath(__file__))
    dst = os.path.normpath(os.path.join(here, "..", "sound", "sound-measured.json"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n썼다  " + dst)
