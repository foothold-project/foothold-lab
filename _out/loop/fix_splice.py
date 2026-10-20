# -*- coding: utf-8 -*-
r"""`splice_report.py` 의 `video_rows` 를 성한 것으로 갈아 끼운다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 기억 「긴 한글 heredoc 은 Write 로」 · Bash heredoc 이 백슬래시를 먹어
      `\n` 이 진짜 줄바꿈이 되면서 문자열이 깨졌다. 오늘 두 번째다.
요지: 함수 하나를 «줄 범위로» 잘라내고 성한 것을 넣는다.
"""

from __future__ import annotations

import ast
import io
import sys

P = "_out/loop/splice_report.py"

GOOD = '''def video_rows():
    """찍힌 영상을 «그대로 볼 수 있게» 넣는다. 없으면 없다고 적는다."""
    import glob
    if not os.path.isdir(CLIP_ROOT):
        return "_영상은 평가가 끝난 뒤에 찍습니다._"
    out, n = [], 0
    for label, _, _ in MODELS:
        for name, cond, why in CLIPS:
            mp4 = sorted(glob.glob(os.path.join(CLIP_ROOT, label, name, "*.mp4")))
            if not mp4:
                continue
            rel = "/" + mp4[0].replace(os.sep, "/").replace("\\\\", "/")
            out.append(
                "**%s · %s** · %s\\n\\n"
                '<video src="%s" controls preload="metadata" '
                'playsinline muted loop style="width:100%%;height:auto"></video>\\n'
                % (label, name, why, rel))
            n += 1
    if n == 0:
        return "_아직 찍힌 영상이 없습니다._"
    return "\\n".join(out)
'''


def main() -> int:
    lines = io.open(P, encoding="utf-8").read().split("\n")

    # `def video_rows():` 부터 다음 최상위 `def ` 앞까지를 갈아 끼운다
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("def video_rows():"):
            start = i
            break
    if start is None:
        print("  ** video_rows 를 못 찾았다 **")
        return 1

    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("def ") or lines[j].startswith("CLIPS"):
            end = j
            break
    if end is None:
        print("  ** 함수 끝을 못 찾았다 **")
        return 1

    print("  %d ~ %d 행을 갈아 끼운다 (%d 줄)" % (start + 1, end, end - start))
    new = lines[:start] + GOOD.split("\n") + lines[end:]
    t = "\n".join(new)

    try:
        ast.parse(t)
    except SyntaxError as e:
        print("  ** 아직 문법 오류 · %s 행 %s **" % (e.msg, e.lineno))
        return 1

    io.open(P, "w", encoding="utf-8").write(t)
    print("  문법 통과 · 썼다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
