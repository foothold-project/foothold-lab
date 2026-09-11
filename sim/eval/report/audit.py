# -*- coding: utf-8 -*-
"""발행 전 관문. **원자료에서 다시 세어 보고서와 맞대어 본다.**

    python sim/eval/report/audit.py

분류: 운영
작성: 오흥재 · 2026-09-12 04:40
근거: `Claude/verify-report-v1-round3-result.md` 8번
요지: 문구가 있나가 아니라 수치가 맞나를 센다
상태: 확정

## 왜 다시 썼나

첫 판은 「금지된 문구가 있나」만 봤다. 그래서 **조작한 보고서를 전부
통과시켰다** `확인됨` (2026-09-12 검증 3회차 8번 · 격리 복사본에서 재현).

| 넣은 오류 | 첫 판 | 지금 |
|---|---|---|
| 전체 판 수 43,200 -> 99,999 | 통과 | 막는다 |
| rails 성공 48/100 -> 99/100 | 통과 | 막는다 |
| HUD 오차 0.18~0.24 -> 9.18~9.24 | 통과 | 막는다 |
| 표에 `class` 를 붙이고 머리칸 삭제 | 통과 | 막는다 |
| 배포 영상을 전부 없앰 | 통과 | 막는다 |

## 무엇을 세나

1. **원자료에서 다시 센다.** 판 수 · 성적표 분모 · rails 축 조합 ·
   기준선 실패 갈래 · 1.5 m/s 속도추종. 그 값이 본문에 있나
2. **trace 에서 HUD 오차를 다시 잰다.** 본문이 적은 범위와 맞나
3. **영상을 연다.** 색인의 `width` 를 믿지 않고 디코딩한다. 자른 기록의
   장수와 맞나. 배포본 해시가 색인과 같나
4. **HTML 을 파싱한다.** 속성이 붙어도 표를 찾고 칸을 센다
5. **배포본과 생성본이 바이트로 같나**
6. 남은 것만 문구 검사다. 자료로 못 세는 것에만 쓴다

## 뿌리와 산출 자리

| 변수 | 기본값 |
|---|---|
| `FOOTHOLD_REPO` | 이 파일 기준 저장소 뿌리 |
| `FOOTHOLD_REPORT_OUT` | `sim/eval/results/report-v1` |
| `FOOTHOLD_SITE` | `../foothold-site` |
| `FOOTHOLD_GALLERY` | `sim/eval/results/20260911-gallery-1080` |
"""
from __future__ import annotations


import csv
import filecmp
import hashlib
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("FOOTHOLD_REPO") or os.path.abspath(
    os.path.join(HERE, "..", "..", ".."))
OUT = os.environ.get("FOOTHOLD_REPORT_OUT") or os.path.join(
    LAB, "sim", "eval", "results", "report-v1")
SITE = os.environ.get("FOOTHOLD_SITE") or os.path.abspath(
    os.path.join(LAB, "..", "foothold-site"))
RAW = os.path.join(LAB, "sim", "eval", "results", "maindata-v1")
sys.path.insert(0, os.path.join(LAB, "sim", "eval"))
from terrains import TERRAIN_SETS  # noqa: E402
GALLERY = os.environ.get("FOOTHOLD_GALLERY") or os.path.join(
    LAB, "sim", "eval", "results", "20260911-gallery-1080")

HTML = io.open(os.path.join(OUT, "report-v1.html"), encoding="utf-8").read()
PLAIN = re.sub(r"<[^>]+>", " ", HTML)
DIGITS = re.sub(r"[\s,]", "", PLAIN)

# 어느 절만 돌까. 시험이 영상 디코딩 없이 수치 절만 돌리려는 것이다.
# **기본은 전부**다. 안 주면 하나도 안 빠진다.
ONLY = set()

for _i, _a in enumerate(sys.argv):
    if _a == "--only" and _i + 1 < len(sys.argv):
        ONLY = {x.strip() for x in sys.argv[_i + 1].split(",") if x.strip()}


def wanted(section):
    return not ONLY or section in ONLY


fails = []


def check(no, what, ok, detail=""):
    print("  %s  %-50s %s" % ("OK " if ok else "[X]", "%s. %s" % (no, what), detail))

    if not ok:
        fails.append("%s. %s %s" % (no, what, detail))


def says(value):
    """본문이 그 수를 말하나. 천 단위 쉼표와 빈칸을 빼고 센다."""
    return re.sub(r"[\s,]", "", str(value)) in DIGITS


AX = ("survival_success", "progress_success", "tracking_success", "direction_success")
KO = {"survival_success": "생존", "progress_success": "전진",
      "tracking_success": "속도추종", "direction_success": "방향"}


def truthy(x):
    return str(x).strip().lower() in ("1", "true")


def rows_of(model, tset, d, v):
    path = os.path.join(RAW, model, tset, "d%s" % d, "v%s" % v,
                        "generalization_raw.csv")

    if not os.path.isfile(path):
        return []

    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ── 1. 원자료를 다시 센다 ───────────────────────────────────────────
print("== 1. 원자료를 다시 세어 본문과 맞댄다 ==")

total = 0
score = 0

for base, _dirs, files in os.walk(RAW):
    if "generalization_raw.csv" not in files:
        continue

    with io.open(os.path.join(base, "generalization_raw.csv"),
                 encoding="utf-8") as handle:
        n = max(0, sum(1 for _ in csv.reader(handle)) - 1)

    total += n

    if os.path.basename(os.path.dirname(base)) == "d0.5":
        score += n

check("1a", "전체 원자료 판 수", says(total), "%d 판" % total)
check("1b", "성적표 분모", says(score), "%d 판" % score)

cell = {}
raw_rows = {}


def num(text):
    """유한한 실수만. 색인 생성기와 같은 규칙."""
    import math

    try:
        value = float(text)
    except (TypeError, ValueError):
        return None

    return value if math.isfinite(value) else None


for model in ("baseline", "A", "foothold-v1"):
    for tset in ("rough6", "unseen10"):
        for v in ("0.5", "1", "1.5"):
            for r in rows_of(model, tset, "0.5", v):
                key = (r["terrain"], model, v)
                win, cnt, combo = cell.get(key, (0, 0, {}))

                if truthy(r["overall_success"]):
                    win += 1
                else:
                    down = " + ".join(KO[a] for a in AX if not truthy(r[a]))
                    combo[down] = combo.get(down, 0) + 1

                cell[key] = (win, cnt + 1, combo)
                raw_rows.setdefault(key, []).append(r)

rw, rn, rc = cell[("rails", "foothold-v1", "1")]


def anchored(pattern, *want):
    """**문맥에 걸어서** 센다. 그냥 숫자가 있나만 보면 「48」이 9번 나와 통과한다."""
    m = re.search(pattern, PLAIN)

    if not m:
        return False, "그 문장을 못 찾았다"

    got = tuple(re.sub(r"[\s,]", "", g) for g in m.groups())
    ours = tuple(re.sub(r"[\s,]", "", str(w)) for w in want)
    return got == ours, "본문 %s · 실측 %s" % ("/".join(got), "/".join(ours))

ok, why = anchored(r"성공 (\d+)/(\d+)[^가-힣]{0,4}\s*실패 (\d+)판 가운데 (\d+)판",
                   rw, rn, rn - rw, rc.get("방향", 0))
check("1c", "rails 캡션의 성공·실패·방향 단독", ok, why)

ok, why = anchored(r"실패 (\d+)판 가운데 (\d+)판은\s*방향 축만",
                   rn - rw, rc.get("방향", 0))
check("1d", "rails 방향 단독 실패", ok, why)

tr_pass = tr_n = 0

for tset in ("rough6", "unseen10"):
    for r in rows_of("foothold-v1", tset, "0.5", "1.5"):
        tr_pass += truthy(r["tracking_success"])
        tr_n += 1

ok, why = anchored(r"속도추종 축을 통과한 판이 ([\d,]+) / ([\d,]+)", tr_pass, tr_n)
check("1e", "1.5 m/s 속도추종 통과", ok, why)

# wave 캡션의 「종합 성공 n/m」 도 그 칸의 실측이어야 한다.
ok, why = anchored(r"종합 성공 (\d+)/(\d+)\. 속도추종 기준",
                   cell[("wave", "foothold-v1", "1.5")][0],
                   cell[("wave", "foothold-v1", "1.5")][1])
check("1j", "wave 캡션의 종합 성공이 실측과 같다", ok, why)

# 시연 캡션이 적은 「이 자리 성공 n/m」 이 그 칸의 실제 값인가.
# gap 의 세 모델 캡션이 보고서에 나오는 순서대로다.
caption = [tuple(int(x) for x in m)
           for m in re.findall(r"이 자리 성공 (\d+)/(\d+)", PLAIN)]
want = [(cell[("gap", m, "1")][0], cell[("gap", m, "1")][1])
        for m in ("baseline", "A", "foothold-v1")]
check("1g", "시연 캡션의 성적이 그 칸의 실측과 같다", caption == want,
      "본문 %s · 실측 %s" % (caption, want))

only = one = many = other = failed = 0

for tset in ("rough6", "unseen10"):
    for r in rows_of("baseline", tset, "0.5", "1.5"):
        if truthy(r["overall_success"]):
            continue

        failed += 1
        down = [a for a in AX if not truthy(r[a])]

        if down == ["tracking_success"]:
            only += 1
        elif "tracking_success" in down and len(down) == 2:
            one += 1
        elif "tracking_success" in down:
            many += 1
        else:
            other += 1

check("1f", "기준선 1.5 m/s 실패 갈래",
      all(says(x) for x in (failed, only, one, many)),
      "%d = %d + %d + %d + %d" % (failed, only, one, many, other))

# 성적표 표 144칸을 «한 칸씩» 원자료와 맞댄다. 어느 한 칸만 바꿔도 잡힌다
# `확인됨` (2026-09-12 검증 4회차 3번 · boxes 를 100 에서 7 로 바꿔도 통과했다).
TABLES = re.findall(r"<table\b[^>]*>.*?</table>", HTML, re.S)
MODELS = ("baseline", "A", "foothold-v1")
SPEEDS = ("0.5", "1", "1.5")
wrong = []
seen_keys = []

for tbl in TABLES:
    # 성적표는 모델마다 `colspan="3"` 을 쓰는 두 줄짜리 머리를 갖는다.
    # 그것으로 고른다. 모델 이름만 보면 모델 설명 표가 걸린다.
    if tbl.count('colspan="3"') < 3 or "지형" not in tbl:
        continue

    body = re.search(r"<tbody\b[^>]*>(.*?)</tbody>", tbl, re.S)

    if not body:
        continue

    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body.group(1), re.S):
        cols = [re.sub(r"<[^>]+>", "", c).strip()
                for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr, re.S)]

        if len(cols) != 10:
            continue

        terrain = cols[0]
        i = 1

        for model in MODELS:
            for v in SPEEDS:
                key = (terrain, model, v)

                if key not in cell:
                    i += 1
                    continue

                win, n, _combo = cell[key]
                want = "%g" % round(100.0 * win / n, 1)
                got = cols[i].replace("%", "").strip()
                seen_keys.append(key)

                # **빈칸도 실패다.** `if got and ...` 로 두면 지워 버리기만 하면
                # 통과한다 `확인됨` (2026-09-12 검증 5회차 1번).
                if got not in (want, "%.1f" % (100.0 * win / n)):
                    wrong.append("%s %s %s: 본문 %r · 실측 %s"
                                 % (terrain, model, v, got, want))

                i += 1

# 144칸이 «정확히» 있고 겹치지 않아야 한다. 「100칸 이상」은 기준이 아니다.
want_keys = {(t, m, v) for (t, m, v) in cell}
have_keys = set(seen_keys)
short = want_keys - have_keys
dupes = len(seen_keys) != len(have_keys)

check("1h", "성적표 표가 원자료와 한 칸씩 같다",
      not wrong and not short and not dupes and len(seen_keys) == len(cell),
      "%d칸 대조(기대 %d) · 빠짐 %d · 중복 %s · %s"
      % (len(seen_keys), len(cell), len(short), dupes,
         "; ".join(wrong[:3]) or "전부 맞다"))

# 집합 평균도 원자료에서 다시 낸다
avg = {}

for (terrain, model, v), (win, n, _c) in cell.items():
    tset = "rough6" if terrain in TERRAIN_SETS["rough6"][0] else "unseen10"
    a, b = avg.get((tset, model, v), (0.0, 0))
    avg[(tset, model, v)] = (a + 100.0 * win / n, b + 1)

# **표의 그 칸에서 본다.** 본문 어딘가에 그 숫자가 있나만 보면 두 값을 서로
# 바꿔 넣어도 통과한다 `확인됨` (2026-09-12 검증 6회차 1번 · 65.8 과 97.3 을
# 맞바꿨더니 막힌 것 0건이었다).
LABEL = {"기존 험지 6종": "rough6", "미경험 험지 10종": "unseen10"}
bad_avg = []
avg_seen = 0

for tbl in TABLES:
    if "집합" not in tbl[:200] or "기준선 대비" not in tbl:
        continue

    body = re.search(r"<tbody\b[^>]*>(.*?)</tbody>", tbl, re.S)

    if not body:
        continue

    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body.group(1), re.S):
        cols = [re.sub(r"<[^>]+>", "", c).strip()
                for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr, re.S)]

        if len(cols) != 6 or cols[0] not in LABEL:
            continue

        tset = LABEL[cols[0]]
        v = cols[1]

        for i, model in enumerate(MODELS):
            key = (tset, model, v)

            if key not in avg:
                bad_avg.append("표에 %s 가 있는데 원자료에 없다" % (key,))
                continue

            total_pct, k = avg[key]
            want = "%.1f" % (total_pct / k)
            avg_seen += 1

            if cols[2 + i] != want:
                bad_avg.append("%s %s %s: 본문 %r · 실측 %s"
                               % (tset, model, v, cols[2 + i], want))

        # 「기준선 대비」 차이도 그 행에서 센다
        base = avg.get((tset, "baseline", v))
        newest = avg.get((tset, "foothold-v1", v))

        if base and newest:
            want_gap = "%+.1f" % (newest[0] / newest[1] - base[0] / base[1])

            if cols[5] != want_gap:
                bad_avg.append("%s %s 차이: 본문 %r · 실측 %s"
                               % (tset, v, cols[5], want_gap))

check("1i", "집합 평균표가 원자료와 한 칸씩 같다",
      avg_seen == len(avg) and not bad_avg,
      "%d칸 대조(기대 %d) · %s"
      % (avg_seen, len(avg), "; ".join(bad_avg[:3]) or "전부 맞다"))

# 참여도 표도 한 칸씩
eng_bad = []
eng_seen = 0
# **원자료에서 직접 낸다.** 생성기가 적어 둔 `report_numbers.json` 을 읽으면
# 검사 대상이 준 답을 그대로 믿는 것이다 (2026-09-12 검증 6회차 뒤).


def quant(values, ratio):
    """선형 보간 분위. 생성기와 같은 규칙."""
    if not values:
        return None
    order = sorted(values)
    pos = ratio * (len(order) - 1)
    low = int(pos)
    high = min(low + 1, len(order) - 1)
    return order[low] + (order[high] - order[low]) * (pos - low)


def mean_of(values):
    return (sum(values) / len(values)) if values else None

ENG_NUM = {}
for (_terrain, _model, _v), _rows in raw_rows.items():
    if _model != "foothold-v1" or _v != "1":
        continue
    _ratios = [x for x in (num(r.get("terrain_engagement_ratio")) for r in _rows)
               if x is not None]
    if not _ratios:
        continue
    ENG_NUM[_terrain] = {
        "scan": mean_of([x for x in (num(r.get("terrain_relief_scan_m")) for r in _rows)
                         if x is not None]),
        "under": mean_of([x for x in (num(r.get("terrain_relief_underfoot_m"))
                                      for r in _rows) if x is not None]),
        "ratio": mean_of(_ratios),
        "ratio_p50": quant(_ratios, 0.50),
    }

for tbl in TABLES:
    if "중앙 광선 기복" not in tbl:
        continue

    body = re.search(r"<tbody\b[^>]*>(.*?)</tbody>", tbl, re.S)

    if not body:
        continue

    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body.group(1), re.S):
        cols = [re.sub(r"<[^>]+>", "", c).strip()
                for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr, re.S)]

        if len(cols) != 8 or cols[0] not in ENG_NUM:
            continue

        e = ENG_NUM[cols[0]]
        eng_seen += 1

        for col, want, what in ((2, "%.3f" % e["scan"], "스캔 기복"),
                                (3, "%.3f" % e["under"], "중앙 광선 기복"),
                                (4, "%.2f" % e["ratio"], "참여도 평균"),
                                (5, "%.2f" % e["ratio_p50"], "중앙값")):
            if cols[col] != want:
                eng_bad.append("%s %s: 본문 %r · 실측 %s"
                               % (cols[0], what, cols[col], want))

check("1k", "참여도 표가 계산값과 한 칸씩 같다",
      eng_seen >= 10 and not eng_bad,
      "%d줄 · %s" % (eng_seen, "; ".join(eng_bad[:3]) or "전부 맞다"))


# ── 2. HUD 오차를 trace 에서 다시 잰다 ──────────────────────────────
print("== 2. HUD 오차를 trace 에서 다시 잰다 ==")
means = []

for name in ("repeated_boxes", "repeated_cylinders", "wave"):
    stem = "%s-v1.5-baseline" % name
    path = os.path.join(GALLERY, "cuts", stem, stem + ".trace.csv")

    if not os.path.isfile(path):
        continue

    with io.open(path, encoding="utf-8") as handle:
        body = [line for line in handle if not line.startswith("#")]

    got = []

    for r in csv.DictReader(body):
        try:
            # 열 이름은 `cmd_vx_mps` 다. `command_vx_mps` 는 주석줄의 이름이라
            # 그것으로 찾으면 조용히 0개가 나온다 (2026-09-12 에 겪었다).
            got.append(abs(float(r["vx_mps"]) - float(r["cmd_vx_mps"])))
        except (KeyError, TypeError, ValueError):
            pass

    if got:
        means.append(sum(got) / len(got))

stated = re.search(r"전후 오차는 ([\d.]+)~([\d.]+)", PLAIN)

if means and stated:
    lo, hi = min(means), max(means)
    ok = (abs(float(stated.group(1)) - lo) < 0.02
          and abs(float(stated.group(2)) - hi) < 0.02)
    check("2a", "본문의 전후 오차 범위가 trace 와 맞다", ok,
          "실측 %.2f~%.2f · 본문 %s~%s" % (lo, hi, stated.group(1), stated.group(2)))
else:
    check("2a", "trace 와 본문 문장을 둘 다 찾았다", False,
          "trace %d개 · 본문 문장 %s" % (len(means), bool(stated)))


# ── 3. 영상을 열어서 잰다 ───────────────────────────────────────────
print("== 3. 영상을 열어서 잰다 ==")
import av  # noqa: E402

vids = sorted(set(re.findall(r'<video src="([^"]+)"', HTML)))
bad = []

for src in (vids if wanted("video") else []):
    if src.startswith("data:"):
        bad.append("base64 로 심었다")
        continue

    path = os.path.join(SITE, src.lstrip("/"))

    if not os.path.isfile(path):
        bad.append("%s 없다" % src)
        continue

    container = av.open(path)

    try:
        stream = container.streams.video[0]
        size = (stream.codec_context.width, stream.codec_context.height)
        frames = sum(1 for _ in container.decode(stream))
    finally:
        container.close()

    if size != (1920, 1080):
        bad.append("%s %dx%d" % (src, size[0], size[1]))
        continue

    stem = os.path.basename(src)[:-4]
    rec = os.path.join(GALLERY, "cuts", stem, stem + ".trim.trim.json")

    if os.path.isfile(rec):
        want = json.load(io.open(rec, encoding="utf-8"))["kept_frames"]

        if frames != want:
            bad.append("%s 장수 %d, 자른 기록은 %d" % (src, frames, want))

check("3a", "본문이 쓰는 영상이 1080p 이고 자른 장수와 같다"
      + ("" if wanted("video") else " [건너뜀]"),
      (bool(vids) and not bad) if wanted("video") else True,
      "%d개 · %s" % (len(vids), "; ".join(bad[:3]) or "전부 맞다"))

MAN = json.load(io.open(os.path.join(SITE, "gallery", "v1", "manifest.json"),
                        encoding="utf-8"))
miss = []

for clip in (MAN["clips"] if wanted("video") else []):
    path = os.path.join(SITE, "gallery", "v1", clip["file"])

    if not os.path.isfile(path):
        miss.append(clip["file"] + " 없다")
        continue

    digest = hashlib.sha256()

    with io.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    if digest.hexdigest() != clip.get("sha256"):
        miss.append(clip["file"] + " 해시가 다르다")

check("3b", "배포된 컷이 색인의 해시와 같다"
      + ("" if wanted("video") else " [건너뜀]"), not miss,
      "%d개 · %s" % (len(MAN["clips"]), "; ".join(miss[:3]) or "전부 맞다"))


# ── 3c. 색인의 «전부» 를 연다 ───────────────────────────────────────
#
# 본문이 쓰는 11개만 보면, 색인에 있는 나머지 73개가 어떤 상태든 해시만 맞으면
# 통과한다 `확인됨` (2026-09-12 검증 4회차 3번 · 파일을 바꿔치기하고 색인의
# 해시·크기만 맞췄더니 통과했다).
#
# 장수의 정답도 절단 기록이 아니라 **trace 에서 다시 센다.** 기록이 없으면
# 그것이 곧 실패다.
def frames_wanted(stem):
    """trace 에서 전진 5.0 m 를 처음 넘는 표본까지. 못 넘으면 표본 전부."""
    path = os.path.join(GALLERY, "cuts", stem, stem + ".trace.csv")

    if not os.path.isfile(path):
        return None, "trace 가 없다"

    with io.open(path, encoding="utf-8") as handle:
        body = [line for line in handle if not line.startswith("#")]

    rows = list(csv.DictReader(body))

    if not rows or "fwd_m" not in rows[0]:
        return None, "trace 에 fwd_m 이 없다"

    for i, r in enumerate(rows):
        try:
            if float(r["fwd_m"]) >= 5.0:
                return i + 1, None
        except (TypeError, ValueError):
            pass

    return len(rows), None


def trace_step(stem):
    """trace 의 표본 간격. 「결정 한 번에 한 장」이 참인지 재는 잣대다."""
    path = os.path.join(GALLERY, "cuts", stem, stem + ".trace.csv")

    if not os.path.isfile(path):
        return None

    with io.open(path, encoding="utf-8") as handle:
        body = [line for line in handle if not line.startswith("#")]

    times = []

    for r in csv.DictReader(body):
        try:
            times.append(float(r["t_s"]))
        except (KeyError, TypeError, ValueError):
            return None

    if len(times) < 2:
        return None

    return (times[-1] - times[0]) / (len(times) - 1)


off = []

for clip in (MAN["clips"] if wanted("video") else []):
    path = os.path.join(SITE, "gallery", "v1", clip["file"])

    if not os.path.isfile(path):
        off.append(clip["file"] + " 없다")
        continue

    container = av.open(path)

    try:
        stream = container.streams.video[0]
        size = (stream.codec_context.width, stream.codec_context.height)
        tb = stream.time_base
        stamps = [float(f.pts * tb) for f in container.decode(stream)
                  if f.pts is not None]
        frames = len(stamps)
    finally:
        container.close()

    if size != (1920, 1080):
        off.append("%s %dx%d" % (clip["file"], size[0], size[1]))
        continue

    if frames != clip.get("frames"):
        off.append("%s 장수 %d, 색인은 %s" % (clip["file"], frames, clip.get("frames")))
        continue

    want, why = frames_wanted(clip["id"])

    if want is None:
        off.append("%s · %s" % (clip["file"], why))
        continue

    if frames != want:
        off.append("%s 장수 %d, trace 기준 %d" % (clip["file"], frames, want))
        continue

    # **장수만 맞으면 안 된다.** 같은 장수를 25 fps 로 구우면 길이가 두 배인
    # 영상이 통과한다 `확인됨` (2026-09-12 검증 5회차 3번).
    #
    # 정책이 결정 한 번에 한 장이므로, **프레임 간격이 trace 의 시간 간격과
    # 같아야** 「초당 50장」이라는 본문 설명이 참이 된다.
    if len(stamps) >= 2:
        step = (stamps[-1] - stamps[0]) / (len(stamps) - 1)
        want_step = trace_step(clip["id"])

        if want_step is None:
            off.append("%s · trace 의 t_s 를 못 읽었다" % clip["file"])
        elif abs(step - want_step) > 0.001:
            off.append("%s 프레임 간격 %.4f초, trace 는 %.4f초"
                       % (clip["file"], step, want_step))

check("3c", "색인의 컷 전부가 1080p 이고 trace 기준 장수와 같다"
      + ("" if wanted("video") else " [건너뜀]"), not off,
      "%d개 · %s" % (len(MAN["clips"]), "; ".join(off[:3]) or "전부 맞다"))

# 갤러리 평가 칸을 원자료와 맞댄다
gap = []
ev_keys = []

for ev in MAN["evaluations"]:
    key = (ev["terrain"], ev["model"], ("%g" % ev["speed_mps"]))
    ev_keys.append(key)

    if key not in cell:
        gap.append("%s 가 원자료에 없다" % ev["id"])
        continue

    win, n, _c = cell[key]

    if ev["successes"] != win or ev["episodes"] != n:
        gap.append("%s 색인 %d/%d · 실측 %d/%d"
                   % (ev["id"], ev["successes"], ev["episodes"], win, n))
        continue

    # **표시 지표도 센다.** 성공 횟수만 보면 성공률을 7 로 바꿔도 통과한다
    # `확인됨` (2026-09-12 검증 5회차 2번).
    want_rate = round(100.0 * win / n, 1)

    if abs(ev["success_rate"] - want_rate) > 0.05:
        gap.append("%s 성공률 %s · 실측 %.1f" % (ev["id"], ev["success_rate"], want_rate))
        continue

    eng = [x for x in (num(r.get("terrain_engagement_ratio")) for r in raw_rows[key])
           if x is not None]
    want_eng = round(sum(eng) / len(eng), 3) if eng else None

    if ev["engagement"] != want_eng or ev["engagement_n"] != len(eng):
        gap.append("%s 참여도 %s(%s) · 실측 %s(%d)"
                   % (ev["id"], ev["engagement"], ev["engagement_n"], want_eng, len(eng)))
        continue

    if ev["difficulty"] != MAN["difficulty"]:
        gap.append("%s 난이도 %s" % (ev["id"], ev["difficulty"]))

# 평가 칸이 «정확히» 144개고 겹치지 않아야 한다. 하나 지우면 143칸으로 통과했다.
missing_ev = set(cell) - set(ev_keys)

check("3d", "갤러리 색인의 평가 칸이 원자료와 같다",
      not gap and not missing_ev and len(ev_keys) == len(set(ev_keys)) == len(cell),
      "%d칸(기대 %d) · 빠짐 %d · %s"
      % (len(ev_keys), len(cell), len(missing_ev), "; ".join(gap[:3]) or "전부 맞다"))

# 컷에 베껴 둔 지표가 그 평가 칸과 같은가
byid = {e["id"]: e for e in MAN["evaluations"]}
copied = []

for clip in MAN["clips"]:
    ev = byid.get(clip["evaluation_id"])

    if ev is None:
        copied.append("%s 의 evaluation_id 가 없다" % clip["id"])
        continue

    if (clip.get("success_rate") != ev["success_rate"]
            or clip.get("engagement") != ev["engagement"]
            or clip.get("episodes") != ev["episodes"]):
        copied.append("%s 가 평가 칸과 다르다" % clip["id"])

check("3e", "컷에 베낀 지표가 평가 칸과 같다", not copied,
      "%d컷 · %s" % (len(MAN["clips"]), "; ".join(copied[:3]) or "전부 맞다"))


# ── 4. 표를 파싱해서 센다 ───────────────────────────────────────────
print("== 4. 표를 파싱해서 센다 ==")


def cells_in(tr):
    n = 0

    for m in re.finditer(r"<t[hd]\b([^>]*)>", tr):
        cs = re.search(r'colspan\s*=\s*"(\d+)"', m.group(1))
        n += int(cs.group(1)) if cs else 1

    return n


bad_tables = []

for i, tbl in enumerate(re.findall(r"<table\b[^>]*>.*?</table>", HTML, re.S)):
    head = re.search(r"<thead\b[^>]*>(.*?)</thead>", tbl, re.S)
    body = re.search(r"<tbody\b[^>]*>(.*?)</tbody>", tbl, re.S)

    if not head or not body:
        continue

    want = max(cells_in(tr) for tr in re.findall(r"<tr\b[^>]*>.*?</tr>",
                                                 head.group(1), re.S))
    got = {cells_in(tr) for tr in re.findall(r"<tr\b[^>]*>.*?</tr>",
                                             body.group(1), re.S)}

    if got and got != {want}:
        bad_tables.append("표%d 머리 %d 줄 %s" % (i, want, sorted(got)))

check("4a", "모든 표의 머리칸과 줄 칸수가 같다", not bad_tables, " ".join(bad_tables))


# ── 5. 배포본과 생성본 ──────────────────────────────────────────────
print("== 5. 배포본과 생성본 ==")
deployed = os.path.join(SITE, "report-v1.html")
made = os.path.join(OUT, "report-v1.html")
check("5a", "배포된 보고서가 생성본과 바이트로 같다",
      os.path.isfile(deployed) and filecmp.cmp(deployed, made, shallow=False),
      "foothold-site/report-v1.html")


# ── 6. 자료로 못 세는 것만 문구 검사 ────────────────────────────────
print("== 6. 자료로 못 세는 것 ==")

for text in ("절반이 걸립니다", "그 속도를 냅니다", "발로 탄 것", "비켜 갔다",
             "같은 100 판의 한 장면", "제대로 타고",
             "명령 속도를 실제로 냅니다", "일부 판만 크게 탔"):
    check("6", "「%s」 없다" % text, text not in PLAIN)

check("6", "참여도 계산식이 본문에 있다",
      "중앙 광선 높이 범위 / 스캔 전체 높이 범위" in PLAIN)
check("6", "발 접촉을 안 잰다고 적는다", "발이 닿았는지를 재지 않습니다" in PLAIN)
# **한정 문장이 «있는지»도 센다.** 금지 문구만 세면 그것을 안 쓰면서 같은
# 뜻으로 다시 쓸 수 있다 `확인됨` (2026-09-12 검증 6회차 5번).
check("6", "wave 캡션이 판정 기준으로 한정돼 있다",
      "명령 속도를 정확히 낸다는 뜻은 아닙니다" in PLAIN)
check("6", "참여도의 한계를 밝힌다", "이 비율만으로" in PLAIN)
# heredoc 이 백슬래시를 먹으면 정규식이 조용히 아무것도 안 잡는다 `확인됨`
# (2026-09-12 · `\\b` 가 0x08 로 박혀 성적표 144칸이 0칸 대조였다).
ctrl = []
scanned = 0

for base, _dirs, files in os.walk(os.path.join(LAB, "sim", "eval")):
    if "__pycache__" in base or "results" in base:
        continue

    for name in sorted(files):
        if not name.endswith(".py"):
            continue

        try:
            text = io.open(os.path.join(base, name), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue

        scanned += 1

        for code in (0x01, 0x02, 0x07, 0x08, 0x0b, 0x0c, 0x1b):
            if chr(code) in text:
                ctrl.append("%s 에 0x%02x" % (name, code))

check("6", "sim/eval 어디에도 제어문자가 없다", scanned > 10 and not ctrl,
      "%d개 훑음 · %s" % (scanned, "; ".join(ctrl[:3]) or "깨끗"))
check("6", "em dash 없다", chr(8212) not in HTML)
check("6", "%% 안 샜다", "%%" not in HTML)

print()
print("  막힌 것 %d건" % len(fails))

for line in fails:
    print("    " + line)

raise SystemExit(1 if fails else 0)
