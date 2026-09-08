# -*- coding: utf-8 -*-
"""사운드 아홉 항목을 잰다. 코디네이터가 못 박은 통과 기준 그대로다.

1차본 검사 스크립트가 열여섯 항목을 통과시키고도 「가볍다」를 못 잡았다.
-16 LUFS 는 라우드니스 정규화 값이지 무게를 재는 값이 아니다.
무게는 저역 에너지 · 새추레이션 배음 · 트랜지언트 · 잔향 꼬리에서 나온다.
그래서 그 넷을 직접 재는 항목을 넣었다.

  1 초저역 20-60 Hz 에너지 비중          25 퍼센트 이상 (첫 컷 이후 구간에서)
  2 포락선 자기상관 최대 지연            208 ms 격자 (걷는 구간에서)
  3 우쉬 첫째 2k-12k 비중                3 퍼센트 이상 (창 0.6초)
  4 우쉬 둘째 2k-12k 비중                3 퍼센트 이상 (창 0.6초)
  5 근접컷 RMS                           -16 dBFS 이상
  6 지속 바닥 비 (40-60 Hz 10/90 퍼센타일)  0.35 이상
  7 하모닉 배음 2배 · 3배                기음 45 Hz 대비 -12 dB 이내
  8 스테레오 상관 (200 Hz 위)            0.5 이하
  9 크레스트 팩터 (피크 대 RMS)          10 dB 이상

1번과 2번을 구간을 나눠 재는 이유. A 판은 앞에 2.5초 오프닝이 붙는데
그 구간은 **의도적으로 거의 침묵**이고 발자국 간격도 넓게 시작해 208 ms 로 좁혀 온다.
전체 평균으로 재면 두 성질이 섞여 흐려진다. 실측이다.

  오프닝 0-2.5초     초저역 85.57 % · 격자 +0.414 대 비격자 +0.621 (격자가 최대가 아니다)
  본편 2.5-23.06초   초저역 53.20 % · 격자 +0.721 대 +0.570 (격자가 최대)
  걷는 구간 2.5-13.33초                +0.811 대 +0.480 (더 뚜렷하다)

오프닝에 격자가 없는 것은 결함이 아니라 연출이다. 무음을 억지로 채우면
「멀리서 들어온다」가 죽는다. 그래서 1번은 첫 컷 이후에서, 2번은 걷는 구간에서 잰다.
오프닝 값은 판정에 넣지 않고 참고로 함께 적는다. 6번을 걷는 구간에서 재는 것과 같은 원리다.

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
    1: ("초저역 20-60 Hz (본편)", 25.0, "이상", "%"),
    2: ("자기상관 최대 (걷는 구간)", 208.0, "격자", "ms"),
    3: ("우쉬 첫째 2k-12k", 3.0, "이상", "%"),
    4: ("우쉬 둘째 2k-12k", 3.0, "이상", "%"),
    5: ("근접컷 RMS", -16.0, "이상", "dBFS"),
    6: ("지속 바닥 비 40-60 Hz", 0.35, "이상", ""),
    7: ("하모닉 2배 · 3배", -12.0, "이내", "dB"),
    8: ("스테레오 상관 200 Hz 위", 0.5, "이하", ""),
    9: ("크레스트 팩터", 10.0, "이상", "dB"),
}


def read(path, ac=1):
    """항상 스테레오로 읽고 모노는 여기서 (L+R)/2 로 만든다.

    ffmpeg 의 `-ac 1` 에 기대면 안 된다. **다운믹스 이득이 출력 형식에 따라 다르다.**
    같은 입력에 같은 `-ac 1` 을 걸고 형식만 바꿔 재면 이렇게 나온다. 실측이다.

      -f f32le   채널 RMS 의 1.414214 배   부동소수라 클리핑 걱정이 없어 에너지 보존
      -f s16le   채널 RMS 의 1.000000 배   정수라 클리핑 보호로 0.5/0.5 정규화
      -f s32le   채널 RMS 의 1.000000 배   위와 같다

    진폭을 0.2 에서 0.7 로 바꿔도 비는 그대로다. 신호에 따라 도는 것이 아니라
    형식으로 정해진다. **그래서 `-f s16le` 로 확인하면 「평균이 맞다」는 결론이 나온다.**
    실제로 그렇게 확인해 본 사람이 있었다. 형식을 안 맞추면 서로 다른 것을 보게 된다.

    우리는 f32le 로 읽으므로 sqrt(2) 를 맞는다. 그래서 절대 크기를 쓰는 항목이 틀어졌다.
      5번 근접컷 RMS 가 최대 3 dB 크게 나왔다
      9번 크레스트가 그만큼 작게 나왔다 (10.49 로 보고했는데 참값은 13.34)
    비중과 비율을 재는 항목(1 · 3 · 4 · 6 · 7)은 배율이 약분되어 영향이 없다.

    형식에 안 흔들리게 하려고 `-ac 2` 로 읽고 여기서 직접 평균한다. 그것이 요점이다.
    """
    p = subprocess.run([FF, "-v", "error", "-i", path, "-map", "0:a:0",
                        "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    a = np.frombuffer(p.stdout, np.float32).astype(np.float64)
    a = a[: (a.size // 2) * 2].reshape(-1, 2)
    if ac == 2:
        return a[:, 0], a[:, 1]
    return a.mean(axis=1)


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

    # 1번은 첫 컷 이후에서 잰다. 오프닝의 침묵이 평균을 희석한다.
    body = x[int(offset * SR):]
    res[1] = band_share(body, 20, 60)
    sub_open = band_share(x[:int(offset * SR)], 20, 60) if offset > 0.05 else float("nan")
    ok[1] = res[1] >= 25.0

    # 2번은 걷는 구간에서 잰다. 오프닝은 간격이 넓게 시작하므로 격자가 있을 수 없다.
    walk_seg = x[int(offset * SR):int((offset + WALK_END) * SR)]
    ac, gi, oi, cand = grid_autocorr(walk_seg)
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

    # 크레스트는 채널 피크 나누기 채널 RMS 다. 모노로 내려 재지 않는다.
    pk = max(np.abs(L).max(), np.abs(R).max())
    ch_rms = np.sqrt(np.mean(np.concatenate([L, R]) ** 2))
    res[9] = 20 * np.log10(pk / max(ch_rms, 1e-12))
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
           "sustain_all": round(sus_all, 4), "sub_opening_pct": (None if offset <= 0.05 else round(sub_open, 3)), "lufs": I, "true_peak_dbtp": tp, "passed": int(n_ok), "all_pass": bool(n_ok == 9)}
    return out


def lead_in_seconds(x, sr=SR, hop_s=0.1, margin_db=3.0):
    """앞에 붙은 조용한 구간의 길이를 잰다.

    오프닝은 무음이 아니다. 먼 발자국과 드론이 깔린다. 그래서 무음 길이로는
    못 찾는다. 대신 **소리가 본편 수준에 올라오는 자리**를 찾는다.
    0.1초 단위 RMS 가 파일 60퍼센타일의 3 dB 안에 처음 드는 자리다.

    실측이다. A 판 2.50초 · B 판 0.10초 · 1차본 1.60초.
    포락선 백분위로도 해 봤는데 A 와 B 가 거의 같게 나와서 못 가른다.
    오프닝의 드론이 포락선을 채워서 그렇다."""
    hop = int(hop_s * sr)
    n = len(x) // hop
    if n < 8:
        return 0.0
    r = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) for i in range(n)])
    rdb = 20 * np.log10(np.maximum(r, 1e-12))
    ok = rdb >= float(np.percentile(rdb, 60)) - margin_db
    if not ok.any() or ok[0]:
        return 0.0
    return float(np.argmax(ok)) * hop_s


def whoosh_at(x, offset, sr=SR):
    """그 오프셋으로 쟀을 때 우쉬 두 곳의 2k-12k 비중."""
    out = []
    for t0 in WHOOSH:
        t = t0 + offset
        lo, hi = int((t - 0.25) * sr), int((t + 0.35) * sr)
        out.append(band_share(x[max(0, lo):min(len(x), hi)], 2000, 12000))
    return out


def check_offset(paths):
    """`--offset` 을 안 붙였는데 붙였어야 하면 멈춘다.

    안 붙이고 돌리면 우쉬 창이 오프닝에 떨어져 3 · 4 · 5 · 6번이 **거짓으로
    실패한다.** 우쉬가 8.592 퍼센트인데 0.001 퍼센트로 나온다. 한 번 속으면
    다음 사람도 속는다.

    앞에 조용한 구간이 있다는 것만으로는 멈추지 않는다. 그것만 보면 1차본
    (앞이 1.60초 완만하게 차오른다)에서 헛돈다. **오프셋을 옮겼을 때 우쉬가
    실제로 되살아나는 경우**에만 멈춘다. 증상 자체를 보는 것이다."""
    bar = LIMITS[3][1]
    for p in paths:
        x = read(p)
        lead = lead_in_seconds(x)
        if lead <= 0.5:
            continue
        now, moved = whoosh_at(x, 0.0), whoosh_at(x, lead)
        if min(now) >= bar or min(moved) < bar:
            continue
        print()
        print(f"멈춘다. {os.path.basename(p)} 는 앞에 {lead:.2f}초가 붙어 있다.")
        print(f"  지금 자리에서 우쉬가 {now[0]:.3f} · {now[1]:.3f} 퍼센트다 "
              f"(기준 {bar} 퍼센트).")
        print(f"  {lead:.2f}초 옮겨서 재면 {moved[0]:.3f} · {moved[1]:.3f} 퍼센트다.")
        print("  창이 오프닝에 떨어져 3 · 4 · 5 · 6번이 거짓으로 실패한다.")
        print()
        print("  이렇게 돌려라")
        print(f"    python scripts/verify-sound.py {p} --offset {lead:.1f}")
        print()
        print("  앞에 붙은 것이 없다고 확신하면 `--offset 0` 을 명시해라.")
        sys.exit(2)


if __name__ == "__main__":
    args = sys.argv[1:]
    off = 0.0
    if "--offset" in args:
        i = args.index("--offset")
        off = float(args[i + 1])
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    if "--offset" not in sys.argv:
        check_offset(args)
    rows = [main(p, off) for p in args]
    dst = os.path.join(ROOT, "sound", "verify-sound.json")
    json.dump(rows, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n썼다  " + dst)
    sys.exit(0 if all(r["all_pass"] for r in rows) else 1)
