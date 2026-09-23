# -*- coding: utf-8 -*-
"""평가 48 칸을 «학습 지형 / 닮은 지형 / 새 지형» 으로 가른다.

분류: 도구
작성: Claude 세션 (오흥재 지시) · 2026-09-23
근거: inbox/jay/20260923-lineage/CRITERIA.md v1.0 2 절 · 각 정책이 남긴 `params/env.yaml` 의 `sub_terrains`
요지: 「하락 0 / 48」 한 숫자가 «지킨 것» 과 «일반화한 것» 을 섞는다. 손으로 안 적고 env.yaml 에서 읽는다
상태: 확정
판: v1.0

## 왜 손으로 안 적는가

정책마다 학습 지형이 다릅니다. 실제로 다릅니다.

```
D · E        rough6 여섯 + forward_gap        rails 를 «안» 배웠다
F · H        rough6 여섯 + omni_gap           rails 를 «안» 배웠다
v2a · v2b    rough6 여섯 + omni_gap + rails   rails 를 배웠다
```

**그래서 `rails` 세 칸이 정책에 따라 「학습 지형」이기도 하고 「새 지형」이기도
합니다.** 한 번 손으로 적어 두면 다음 정책에서 조용히 틀립니다.

## 통과선을 둘로 만들지 않습니다

**통과 판정은 48 칸 전체로 합니다** (CRITERIA v1.0 2 절). 이 모듈이 내놓는
분류는 «보고할 때 나눠 읽는 것» 이지 통과선이 아닙니다.

## 「닮은 지형」은 추측하지 않습니다

학습 지형과 평가 지형이 닮았다는 말은 **구현이 스스로 그렇게 적은 것만**
받습니다. 아래 `SIMILAR` 의 `source` 가 그 줄입니다. 출처가 없는 지형이
나오면 이 모듈은 **분류하지 않고 멈춥니다.** 조용히 「새 지형」으로 세면
일반화 주장이 부풀려집니다.
"""

from __future__ import annotations

import io
import os

# --- 학습 지형 <-> 평가 지형 · 구현이 직접 적은 것만 -------------------------
#
# `eval` 이 None 이면 「평가 쪽에 대응하는 칸이 없다」는 뜻이고, 그 근거도
# 같이 적는다. 출처 없이 여기에 줄을 더하지 않는다.
SIMILAR = {
    "omni_gap": {
        "eval": "floating_ring",
        "source": "sim/policy/omni_gap_terrain.py:15",
        "quote": "평가 floating_ring 과 모양이 닮는 교란은 후속 판정에서 별도로 표시한다",
    },
    "forward_gap": {
        "eval": None,
        "source": ("isaaclab_tasks/.../go2/gap_training/gap_wide_env_cfg.py:20-21"),
        "quote": ("지형의 «모양»은 일부러 그대로 둔다. 학습은 앞쪽 슬래브 하나, "
                  "평가는 사방 도랑이다. 모양까지 베끼면 연습을 시험지에 맞추는 "
                  "것이라 일반화가 아니다"),
        # 폭«만» 맞춘 조건(B)이 따로 있다. 폭이 같다고 지형이 닮은 것은
        # 아니므로 분류는 안 바꾸고 `width_note()` 로 따로 알린다.
        "width_note": ("B 조건(`gap_wide`)은 학습 틈 폭을 평가와 같은 "
                       "(0.15, 0.40) 으로 맞췄다 · 폭만 같고 모양은 다르다"),
    },
}

LEARNED, SIMILAR_TO, UNSEEN = "학습", "닮음", "새"
BUCKETS = (LEARNED, SIMILAR_TO, UNSEEN)


def read_sub_terrains(path):
    """`params/env.yaml` -> 학습 지형 이름 목록.

    PyYAML 로 안 읽는다. 이 파일에는 `!!python/tuple` 과 Isaac Lab 클래스
    태그가 들어 있어서 안전한 로더로는 못 열고, 안전하지 않은 로더는 이
    저장소에서 쓰지 않는다. 필요한 것은 «한 단계 아래 키 이름» 뿐이라
    들여쓰기로 읽는다.
    """
    if not os.path.exists(path):
        raise ValueError("`params/env.yaml` 이 없다: %s" % path)
    with io.open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")

    heads = [n for n, line in enumerate(lines) if line.strip() == "sub_terrains:"]
    if not heads:
        raise ValueError("`sub_terrains:` 가 없다: %s" % path)
    if len(heads) > 1:
        raise ValueError(
            "`sub_terrains:` 가 %d 개다 (행 %s) · 어느 것인지 사람이 정해야 한다: %s"
            % (len(heads), ", ".join(str(n + 1) for n in heads), path))

    head = heads[0]
    indent = len(lines[head]) - len(lines[head].lstrip())
    names = []
    for line in lines[head + 1:]:
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip())
        if depth <= indent:
            break
        if depth == indent + 2 and line.rstrip().endswith(":"):
            names.append(line.strip()[:-1])
    if not names:
        raise ValueError("`sub_terrains:` 아래가 비었다: %s" % path)
    return names


def classify(eval_terrains, trained):
    """평가 지형마다 `학습` · `닮음` · `새` 를 붙인다.

    근거 없는 학습 지형이 하나라도 있으면 «분류를 내놓지 않고» 멈춘다.
    """
    eval_terrains = list(eval_terrains)
    trained = list(trained)
    if not eval_terrains:
        raise ValueError("평가 지형이 하나도 없다 · 결과를 못 읽은 것이다")
    if not trained:
        raise ValueError("학습 지형이 하나도 없다 · `env.yaml` 을 못 읽은 것이다")

    unknown = [name for name in trained
               if name not in eval_terrains and name not in SIMILAR]
    if unknown:
        raise ValueError(
            "학습 지형 %s 를 평가 지형에 못 붙인다 · 이름이 같지도 않고 "
            "`SIMILAR` 에 출처도 없다. 구현이 무엇과 닮았다고 적고 있는지 "
            "읽고 `terrain_split.SIMILAR` 에 출처와 함께 넣어야 한다"
            % " · ".join("`%s`" % name for name in sorted(unknown)))

    twins = {}
    for name in trained:
        target = SIMILAR.get(name, {}).get("eval")
        if target:
            twins[target] = name

    out = {}
    for terrain in eval_terrains:
        if terrain in trained:
            out[terrain] = LEARNED
            if terrain in twins:
                raise ValueError(
                    "`%s` 가 학습 지형이면서 `%s` 의 닮은 짝이기도 하다 · "
                    "두 번 세게 된다" % (terrain, twins[terrain]))
        elif terrain in twins:
            out[terrain] = SIMILAR_TO
        else:
            out[terrain] = UNSEEN
    return out


def width_notes(trained):
    """분류는 안 바꾸지만 같이 적어야 하는 단서."""
    return [SIMILAR[name]["width_note"] for name in trained
            if name in SIMILAR and "width_note" in SIMILAR[name]]


def sources(eval_terrains, trained):
    """`닮음` 으로 분류된 칸마다 «그렇게 적은 줄» 을 돌려준다."""
    marks = classify(eval_terrains, trained)
    out = []
    for name in trained:
        target = SIMILAR.get(name, {}).get("eval")
        if target and marks.get(target) == SIMILAR_TO:
            out.append((target, name, SIMILAR[name]["source"],
                        SIMILAR[name]["quote"]))
    return out


def split_cells(keys, trained, terrain_of=lambda key: key[2]):
    """칸 열쇠들을 세 묶음으로 가른다 -> {묶음: [열쇠]}.

    `keys` 는 `(속도, 지형집합, 지형)` 같은 열쇠들이고 `terrain_of` 가
    거기서 지형 이름을 꺼낸다.
    """
    keys = list(keys)
    marks = classify(sorted({terrain_of(key) for key in keys}), trained)

    # `classify` 가 모르는 이름을 돌려주면 그 칸은 어느 묶음에도 안 들어가고
    # 조용히 사라진다. 사라진 칸은 «없는 칸» 이 되므로 여기서 막는다.
    strange = sorted({mark for mark in marks.values() if mark not in BUCKETS})
    if strange:
        raise ValueError(
            "모르는 묶음 이름 %s · 아는 것은 %s 뿐이다"
            % (" · ".join(strange), " · ".join(BUCKETS)))

    # 위의 `strange` 검사를 지나면 모든 칸이 `BUCKETS` 중 하나에 들어간다.
    # 그래서 여기에 「합이 맞나」를 또 두지 않는다. 절대 안 걸리는 검사는
    # 관문이 아니라 관문처럼 «보이는» 줄이고, 그것을 믿으면 안 된다.
    out = {bucket: [] for bucket in BUCKETS}
    for key in keys:
        out[marks[terrain_of(key)]].append(key)
    return out
