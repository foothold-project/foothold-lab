# -*- coding: utf-8 -*-
"""난이도 곡선 하나. **세 모델을 같은 그림에 놓는다.**

    python sim/eval/report/curve.py --out sim/eval/results/report-v1/chart_curve.svg

분류: 운영
작성: 오흥재 · 2026-09-12 23:40
근거: `20260911-v3-fixedscan` 세 모델 x 10난이도 x 3속도 x 미경험 10종 = 90실행 · codex 8회차
요지: 성적표 한 점만으로는 「어디서 무너지나」를 못 본다. 곡선이 그것을 말한다
상태: 확정

## 왜 이것이 있나

팀장: 「스윕 곡선으로 비교했던 것들도 올려도 되지 않냐. 그래프라 잘 보인다」

보고서가 난이도 곡선 28,800판을 **세기만 하고 그리지 않았다.**

처음에는 `maindata-v1` 만 보고 「곡선은 foothold-v1 것뿐」 이라고 판단했는데,
codex 8회차가 `20260911-v3-fixedscan` 에 **세 모델 전부** d0.1~1.0 이 있다고
반증했다 `확인됨`. 그래서 세 모델을 같이 그린다.

## 규격을 어떻게 가르나

이 폴더의 manifest 에는 `eval_spec_version` 이 없다. 대신
`height_scan_miss_value` 가 **1.0** 이다. 빗나간 광선을 +1(구멍)로 읽는 것이
규격 2 이므로 그 값으로 가른다. **1.0 이 아닌 실행은 안 쓴다.**

## 무엇을 조심하나

| 함정 | 어떻게 |
|---|---|
| 지형마다 난이도 축의 뜻이 다르다 | `floating_ring` 은 난이도가 오르면 «쉬워진다». 따로 적는다 |
| `random_rough` 는 난이도를 거의 안 탄다 | 곡선이 평평한 것이 성적이 좋아서가 아니다 |
| 안 잰 구간을 이어 그리면 거짓말 | 측정점만 잇고 밖으로 늘이지 않는다 |
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SWEEP = os.path.join(REPO, "sim", "eval", "results", "20260911-v3-fixedscan")

# 이 폴더의 B 는 foothold-v1 과 같은 체크포인트다. 이름만 다르다.
SHOW = [("baseline", "기준선 NVIDIA", "#8c93a1"),
        ("A", "A", "#c98a2e"),
        ("B", "foothold-v1", "#1d6b58")]
SETS = ("unseen10",)


def rate_of(path):
    """그 실행의 종합 성공률. **CSV 를 직접 센다.**"""
    got = os.path.join(path, "generalization_summary.csv")

    if not os.path.isfile(got):
        return None

    ok = n = 0

    with io.open(got, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            hit = row.get("overall_success_rate") or row.get("overall_success")

            if hit is None:
                continue

            eps = float(row.get("episodes") or row.get("n") or 100)
            ok += float(hit) * (eps if float(hit) <= 1.0 else eps / 100.0)
            n += eps

    return (100.0 * ok / n) if n else None


def gather():
    """`(모델, 속도, 난이도) -> 성공률 %`. 규격 2 인 것만."""
    out, skipped = {}, 0

    for key, _label, _color in SHOW:
        for tset in SETS:
            base = os.path.join(SWEEP, key, tset, "runs")

            if not os.path.isdir(base):
                continue

            for name in sorted(os.listdir(base)):
                one = os.path.join(base, name)
                book = os.path.join(one, "run_manifest.json")

                if not os.path.isfile(book):
                    continue

                spec = json.load(io.open(book, encoding="utf-8"))
                miss = spec.get("height_scan_miss_value")

                # **규격 2 만 쓴다.** 빗나간 광선을 +1 로 읽은 것.
                if miss is None or abs(float(miss) - 1.0) > 1e-6:
                    skipped += 1
                    continue

                bits = name.replace("v", "").split("-d")

                if len(bits) != 2:
                    continue

                speed, hard = float(bits[0]), float(bits[1])
                got = rate_of(one)

                if got is not None:
                    out[(key, speed, hard)] = got

    return out, skipped


def svg(data, speed):
    """한 속도의 곡선 셋."""
    # 오른쪽에 **이름표 자리**를 남긴다. 18 일 때
    # 「foothold-v1」 이 「fo」 로 잘렸다 `확인됨` (2026-09-12 화면 실측).
    W, H = 760, 330
    L, R, T, B = 58, 96, 30, 46
    hard = sorted({h for (_k, v, h) in data if abs(v - speed) < 1e-6})

    if not hard:
        return ""

    x = lambda h: L + (h - hard[0]) / (hard[-1] - hard[0]) * (W - L - R)
    y = lambda p: T + (100 - p) / 100.0 * (H - T - B)
    out = ['<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" '
           'role="img" aria-label="난이도가 오를수록 미경험 험지 10종의 종합 '
           '성공률이 어떻게 되나. 명령 속도 %s m/s.">' % (W, H, ("%g" % speed))]

    for p in (0, 25, 50, 75, 100):
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="var(--line)" '
                   'stroke-width="1"/>' % (L, y(p), W - R, y(p)))
        out.append('<text x="%d" y="%.1f" font-size="10.5" text-anchor="end" '
                   'fill="var(--ink-3)">%d</text>' % (L - 7, y(p) + 3.5, p))

    for h in hard:
        out.append('<text x="%.1f" y="%d" font-size="10.5" text-anchor="middle" '
                   'fill="var(--ink-3)">%g</text>' % (x(h), H - B + 17, h))

    out.append('<text x="%d" y="%d" font-size="11" fill="var(--ink-3)">난이도</text>'
               % (W - R - 34, H - B + 34))
    out.append('<text x="%d" y="%d" font-size="11" fill="var(--ink-3)">성공률 %%</text>'
               % (L - 48, T - 12))

    for key, label, color in SHOW:
        pts = [(x(h), y(data[(key, speed, h)])) for h in hard
               if (key, speed, h) in data]

        if not pts:
            continue

        # **측정점만 잇는다.** 안 잰 구간으로 늘이지 않는다.
        out.append('<polyline fill="none" stroke="%s" stroke-width="2.2" '
                   'points="%s"/>'
                   % (color, " ".join("%.1f,%.1f" % p for p in pts)))

        for px, py in pts:
            out.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>'
                       % (px, py, color))

        out.append('<text x="%.1f" y="%.1f" font-size="11.5" font-weight="700" '
                   'fill="%s">%s</text>'
                   % (pts[-1][0] + 6, pts[-1][1] + 4, color, label))

    out.append("</svg>")
    return "".join(out)


def main():
    p = argparse.ArgumentParser(description="난이도 곡선 한 장")
    p.add_argument("--out", required=True)
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args()

    data, skipped = gather()

    if not data:
        raise SystemExit("규격 2 인 실행을 하나도 못 찾았다: %s" % SWEEP)

    got = svg(data, args.speed)

    if not got:
        raise SystemExit("속도 %g 의 자료가 없다" % args.speed)

    io.open(args.out, "w", encoding="utf-8").write(got)
    models = sorted({k for (k, _v, _h) in data})
    hard = sorted({h for (_k, v, h) in data if abs(v - args.speed) < 1e-6})
    print("  %s · %.1f KB" % (os.path.basename(args.out),
                              len(got.encode("utf-8")) / 1024))
    print("  모델 %s · 난이도 %d단 (%g~%g) · 칸 %d · 규격 2 아님으로 건너뛴 실행 %d"
          % (", ".join(models), len(hard), hard[0], hard[-1], len(data), skipped))

    for key, label, _c in SHOW:
        row = [(h, data[(key, args.speed, h)]) for h in hard
               if (key, args.speed, h) in data]

        if row:
            print("    %-12s %s" % (label, " ".join("%.0f" % v for _h, v in row)))

    # **조용한 실패를 막는다.** 곡선 셋이 다 있어야 「세 모델 비교」다.
    drew = {k for (k, v, _h) in data if abs(v - args.speed) < 1e-6}

    if len(drew) < 3:
        raise SystemExit("속도 %g 에 모델이 %d개뿐이다" % (args.speed, len(drew)))

    if len(hard) < 5:
        raise SystemExit("난이도가 %d단뿐이다. 곡선이라 부르기 어렵다" % len(hard))

    # **글자가 그림 밖으로 나가면 잘린다.** 오류는 안 난다.
    # 이름표가 「foothold-v1」 에서 「fo」 로 잘렸다 `확인됨` (2026-09-12 화면 실측).
    wide = int(re.search(r'viewBox="0 0 ([0-9]+)', got).group(1))
    over = [m.group(2) for m
            in re.finditer(r'<text x="([0-9.]+)"[^>]*>([^<]+)</text>', got)
            if float(m.group(1)) + len(m.group(2)) * 7.0 > wide]

    if over:
        raise SystemExit("그림 밖으로 나가는 글자 %d개: %s"
                         % (len(over), " · ".join(over[:3])))


if __name__ == "__main__":
    main()
