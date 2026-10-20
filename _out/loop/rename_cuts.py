# -*- coding: utf-8 -*-
"""이미 구운 컷 폴더의 이름을 **json 에서 읽어** 고친다. 다시 굽지 않는다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: 갤러리 이름 규칙이 지형 «전체 이름» 이라는 것을 늦게 알았다
요지: 폴더 이름만 바꾼다. mp4 는 그대로다. 30 분짜리 재렌더를 안 한다.

## 다뤄야 하는 경우 넷 · 실제로 다 나왔다

**① 그냥 이름이 틀린 것** · `inv-v1` -> `pyramid_stairs_inv-v1`

**② 사슬** · `boxes-v1` 이 `repeated_boxes` 를 담고 있고, `roughboxes-v1` 이
rough6 의 `boxes` 를 담고 있다. `roughboxes-v1` 을 `boxes-v1` 로 옮기려면
먼저 `boxes-v1` 이 비어야 한다. **그래서 두 단계로 옮긴다.** 전부 임시 이름으로
옮긴 뒤 최종 이름으로 옮긴다. 순서를 사람이 풀지 않는다.

**③ 같은 칸이 둘** · 중단된 재렌더가 `stones-v1` 과 `stepping_stones-v1` 을
둘 다 만들었다. 같은 지형·속도·프레임 수다. **sha256 은 다르다** (x264 가
스레드 일정에 따라 비트가 달라진다). 그래서 **sha 로 같은지 판단하지 않는다.**
`(지형, 속도, 프레임 수)` 가 같으면 같은 칸으로 보고, **이름이 맞는 쪽을 남긴다.**

**④ 덜 구운 것** · `floating_ring-v1` 에 mp4 는 있는데 json 이 없다. 작업을
중단한 자리다. **지운다.** json 이 없으면 지형도 프레임 수도 모른다.
「있다」와 「온전하다」는 다르다.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys

LAB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if not os.path.isdir(os.path.join(LAB, "sim", "eval")):
    raise SystemExit("** 저장소 뿌리를 잘못 잡았다: %s **" % LAB)
CUTS = os.path.join(LAB, "sim", "eval", "results", "20260928-v2-clips", "cuts")

TMP = ".__renaming__"


def read(d):
    """`(지형, 속도, 프레임)` · 못 읽으면 `None`."""
    if not os.path.isdir(d):
        return None
    js = [f for f in os.listdir(d) if f.endswith(".json")]
    mp4 = [f for f in os.listdir(d)
           if f.endswith(".mp4") and not f.endswith(".hud.mp4")]
    if not js or not mp4:
        return None
    m = json.load(io.open(os.path.join(d, js[0]), encoding="utf-8"))
    t, vx, fr = m.get("terrain"), m.get("command_vx_mps"), m.get("frames")
    if not t or vx is None:
        return None
    return (t, float(vx), fr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    names = [n for n in sorted(os.listdir(CUTS))
             if os.path.isdir(os.path.join(CUTS, n)) and not n.startswith(TMP)]

    info = {}
    broken = []
    for n in names:
        got = read(os.path.join(CUTS, n))
        if got is None:
            broken.append(n)
        else:
            info[n] = got

    # 칸마다 후보를 모은다
    by_cell = {}
    for n, (t, vx, fr) in info.items():
        by_cell.setdefault((t, vx, fr), []).append(n)

    drop, plan = [], {}
    for (t, vx, fr), cands in sorted(by_cell.items()):
        want = "%s-v%g" % (t, vx)
        if len(cands) > 1:
            # 이름이 맞는 쪽을 남긴다. 없으면 첫 번째를 남긴다
            keep = want if want in cands else sorted(cands)[0]
            for c in cands:
                if c != keep:
                    drop.append((c, "같은 칸 중복 · %s 를 남긴다" % keep))
            cands = [keep]
        src = cands[0]
        if src != want:
            plan[src] = want

    print("  컷 폴더 %d · 읽은 것 %d · 덜 구운 것 %d" % (len(names), len(info), len(broken)))
    print("  이름 바꿀 것 %d · 지울 것 %d" % (len(plan), len(drop) + len(broken)))
    print()
    for n in broken:
        print("    %-26s ** 지운다 · json 이 없다 (덜 구움) **" % n)
    for n, why in drop:
        print("    %-26s 지운다 · %s" % (n, why))
    for src, dst in sorted(plan.items()):
        print("    %-26s -> %s" % (src, dst))

    # 사슬이 있나 (목표가 다른 원본의 이름인가)
    chains = [(s, d) for s, d in plan.items() if d in plan]
    if chains:
        print()
        print("  사슬 %d 건 · 두 단계로 옮긴다" % len(chains))
        for s, d in chains:
            print("    %s -> %s (그 자리는 %s 가 비운다)" % (s, d, d))

    if not a.write:
        print()
        print("  «예행이다». 아무것도 안 움직였다. 움직이려면 --write 를 준다")
        return 0

    for n in broken:
        shutil.rmtree(os.path.join(CUTS, n))
    for n, _why in drop:
        shutil.rmtree(os.path.join(CUTS, n))

    # 두 단계 · 전부 임시로 옮긴 뒤 최종 이름으로
    staged = []
    for src, dst in plan.items():
        tmp = os.path.join(CUTS, "%s%s" % (TMP, dst))
        shutil.move(os.path.join(CUTS, src), tmp)
        staged.append((tmp, os.path.join(CUTS, dst)))
    for tmp, dst in staged:
        if os.path.exists(dst):
            print("  ** 목표가 아직 차 있다: %s **" % dst)
            return 1
        shutil.move(tmp, dst)

    print()
    print("  지운 폴더 %d · 이름 바꾼 폴더 %d"
          % (len(broken) + len(drop), len(staged)))

    # 되읽는다
    left = [n for n in sorted(os.listdir(CUTS))
            if os.path.isdir(os.path.join(CUTS, n))]
    wrong, nojson = [], []
    cells = {}
    for n in left:
        if n.startswith(TMP):
            wrong.append((n, "임시 이름이 남았다"))
            continue
        got = read(os.path.join(CUTS, n))
        if got is None:
            nojson.append(n)
            continue
        t, vx, fr = got
        want = "%s-v%g" % (t, vx)
        if want != n:
            wrong.append((n, "이름이 %s 여야 한다" % want))
        cells.setdefault((t, vx), []).append(n)
    dups = {k: v for k, v in cells.items() if len(v) > 1}

    if wrong or nojson or dups:
        for n, why in wrong:
            print("  ** %s · %s **" % (n, why))
        for n in nojson:
            print("  ** %s · json 이 없다 **" % n)
        for k, v in dups.items():
            print("  ** 칸 %s 에 폴더 둘: %s **" % (k, v))
        return 1

    print("  되읽음 · 폴더 %d 개 · 이름 전부 맞음 · 겹치는 칸 없음" % len(left))
    print("  채워진 칸 %d / 48" % len(cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
