# -*- coding: utf-8 -*-
"""자동 생성한 표를 보고서의 «표식 사이» 에 끼워 넣는다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 팀장 지시 「영상, csv, 데이터 등 보고서 기록하고 만들고 웹에 올려」
요지: **표만 자동이고 서사는 사람 것이다.** 표식 밖을 건드리지 않는다.

    <!-- 자동:축1 시작 -->  ...여기만 갈아 끼운다...  <!-- 자동:축1 끝 -->

표식이 없으면 **멈춘다.** 조용히 안 넣는 것을 막는다.

돌리는 법
    python _out/loop/splice_report.py \\
        --report docs/research/20260928-scratch-vs-resume.md \\
        --bundle sim/eval/results/20260928-scratch-vs-resume
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

RUNS = "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia"
LOGS = "C:/isaac/IsaacLab/logs/gap_run_logs"
VERDICT_DIR = "inbox/jay/20260927-methodology"

MODELS = (
    ("v2g2-feetair01", "v2g2-feetair01", 3000),
    ("fs1-scratch-f001", "20260928_fs1-scratch-f001", 4500),
    ("fs2-scratch-f01", "20260928_fs2-scratch-f01", 4500),
    ("fs1b-scratch-f001-g1", "20260928_fs1b-scratch-f001-g1", 4500),
    ("fs2b-scratch-f01-g0", "20260928_fs2b-scratch-f01-g0", 4500),
)


def section(text, name, body):
    """표식 사이를 갈아 끼운다. 표식이 없으면 예외."""
    a = "<!-- 자동:%s 시작 -->" % name
    b = "<!-- 자동:%s 끝 -->" % name
    i, j = text.find(a), text.find(b)
    if i < 0 or j < 0 or j < i:
        raise SystemExit("표식을 못 찾았다: %s" % name)
    return text[: i + len(a)] + "\n" + body.rstrip() + "\n" + text[j:]


def pick(md, heading):
    """`compare.md` 에서 한 절만 떼어 온다."""
    if not os.path.isfile(md):
        return "_`compare.md` 가 아직 없습니다._"
    t = io.open(md, encoding="utf-8").read()
    lines = t.split("\n")
    out, on = [], False
    for ln in lines:
        if ln.startswith("## "):
            on = heading in ln
            continue
        if on:
            out.append(ln)
    body = "\n".join(out).strip()
    return body or "_해당 절이 비어 있습니다._"


def blowup_rows():
    rows = ["| 판 | 완주 | 마지막 체크포인트 | 오류 |", "|---|---|---|---|"]
    import glob

    any_row = False
    for label, frag, last in MODELS:
        d = sorted(glob.glob(os.path.join(RUNS, "*%s*" % frag)))
        if not d:
            continue
        any_row = True
        d = d[0]
        done = os.path.isfile(os.path.join(d, "model_%d.pt" % last))
        cks = [
            int(re.search(r"model_(\d+)\.pt", p).group(1))
            for p in glob.glob(os.path.join(d, "model_*.pt"))
        ]
        mx = max(cks) if cks else 0
        logs = sorted(glob.glob(os.path.join(LOGS, "*%s*.log" % frag)))
        err = ""
        if logs:
            t = io.open(logs[-1], encoding="utf-8", errors="replace").read()
            m = re.findall(r"RuntimeError:.*", t)
            if m:
                err = "`%s`" % m[-1].strip()[:52]
        rows.append("| `%s` | %s | %d | %s |"
                    % (label, "**예**" if done else "**아니오**", mx, err or ""))
    if not any_row:
        return "_학습 폴더가 아직 없습니다._"
    return "\n".join(rows)


def verdict_rows():
    rows = ["| 판 | 판정 |", "|---|---|"]
    any_row = False
    for label, _, _ in MODELS:
        p = os.path.join(VERDICT_DIR, "VERDICT-%s.md" % label)
        if not os.path.isfile(p):
            continue
        any_row = True
        t = io.open(p, encoding="utf-8", errors="replace").read()
        m = re.search(r"^> ?요지: ?(.+)$", t, re.M)
        v = m.group(1).strip() if m else ""
        if not v:
            m = re.search(r"\*\*(배포 후보|미달|미완[^*]*)\*\*", t)
            v = m.group(0) if m else "읽지 못했다"
        rows.append("| [`%s`](../../inbox/jay/20260927-methodology/VERDICT-%s.md) | %s |"
                    % (label, label, v[:150]))
    if not any_row:
        return "_판정문이 아직 없습니다._"
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--bundle", required=True)
    a = ap.parse_args()

    if not os.path.isfile(a.report):
        raise SystemExit("보고서가 없다: %s" % a.report)

    t = io.open(a.report, encoding="utf-8").read()
    cmp_md = os.path.join(a.bundle, "compare.md")

    t = section(t, "판정", verdict_rows())
    t = section(t, "축1", pick(cmp_md, "축 1"))
    t = section(t, "축2", pick(cmp_md, "축 2"))
    t = section(t, "폭주", blowup_rows())

    # em dash 가 섞이면 웹 빌드가 막는다. 넣기 전에 본다.
    if "\u2014" in t:
        raise SystemExit("em dash 가 들어갔다. 빌드가 막는다")

    io.open(a.report, "w", encoding="utf-8").write(t)
    print("  끼워 넣었다 · %s" % a.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
