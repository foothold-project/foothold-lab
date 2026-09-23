# -*- coding: utf-8 -*-
"""평가 48 칸을 «학습한 / 도랑이 닿는 / 학습에 없던» 지형으로 가른다.

분류: 도구
작성: Claude 세션 (오흥재 지시) · 2026-09-23
근거: inbox/jay/20260923-lineage/CRITERIA.md v1.1 2 절 · 생성 코드 기하 (mesh_terrains.py) · 각 정책이 남긴 params/env.yaml 의 sub_terrains
요지: 「하락 0 / 48」 한 숫자가 여러 종류를 섞는다. 분류는 «생성 코드의 기하» 로 하고 손으로 안 적는다
상태: 확정
판: v2.1

## 판 v2.0 에서 뒤집힌 것

**v1.0 은 `floating_ring` 을 「닮은 지형」으로 놓았습니다. 틀렸습니다.**
그때는 `omni_gap_terrain.py` 머리말의 **주석**을 근거로 삼았습니다.
CRITERIA v1.1 2 절이 그 방식을 막습니다.

```
분류는 지형 «생성 코드의 기하» 로 정한다. 이름이나 주석으로 정하지 않는다
```

생성 코드를 열면 이렇습니다.

```
gap (평가)             make_border + 가운데 상자.  바닥 상자를 «안» 만든다
                       -> 바닥 없는 사각 도랑        mesh_terrains.py:588-593
floating_ring (평가)   띄운 고리 + `# Generate the ground` 전면 바닥 상자
                       -> «연속 바닥» 위의 물체       mesh_terrains.py:632-640
omni_gap (학습)        중심 디딤판과 바깥 착지판 사이가 빈 원형 도랑
forward_gap (학습)     조주판 · 바닥 없는 틈 · 착지판
```

**도랑끼리 닿는 것은 `gap` 이지 `floating_ring` 이 아닙니다.**
`floating_ring` 은 바닥이 끊기지 않으므로 도랑 경험이 닿는 자리가 아닙니다.

## 왜 손으로 안 적는가

정책마다 학습 지형이 다릅니다. 실제로 다릅니다.

```
D · E        rough6 여섯 + forward_gap        rails 를 «안» 배웠다
F · H        rough6 여섯 + omni_gap           rails 를 «안» 배웠다
G            rough6 여섯 + forward_gap        rails 를 «안» 배웠다
v2a · v2b    rough6 여섯 + omni_gap + rails   rails 를 배웠다
```

**`rails` 세 칸이 정책에 따라 「학습한 지형」이기도 하고 「학습에 없던
지형」이기도 합니다.** 한 번 손으로 적어 두면 다음 정책에서 조용히 틀립니다.

## 이름이 같아도 «같은 조건» 이 아닙니다

CRITERIA v1.1 2 절이 요구하는 둘째입니다. 이름이 같아도 범위가 다릅니다.

```
boxes   학습 grid_height_range (0.025, 0.10)
        평가 grid_height_range (0.05, 0.20)   난이도 0.5 에서 0.125
        -> 학습 범위 «밖» 이다
```

**그리고 이름이 `_range` 라고 범위인 것도 아닙니다.** 항목마다 생성기가
다르게 씁니다. 전부 선형 보간으로 놓으면 틀립니다.

```
보간   난이도로 한 값을 뽑는다            grid_height · step_height · slope · rail_height
표본   난이도와 «무관하게» 구간에서 뽑는다  noise_range   hf_terrains.py:62-70
       -> random_rough 는 어느 난이도에서도 학습 상한 0.06 을 넘는다
두 값  범위가 아니라 값 둘이다             rail_thickness_range  mesh_terrains.py:406
       -> `rail_1_thickness, rail_2_thickness = cfg.rail_thickness_range`
모름   소비 코드를 아직 안 읽었다          «밖인지 확인 못 함» 으로 남긴다
```

`RANGE_USE` 가 그 표이고 `range_notes()` 가 셉니다.
**분류는 안 바꾸고 따로 적습니다.**

## 통과선을 둘로 만들지 않습니다

**통과 판정은 48 칸 전체로 합니다** (CRITERIA v1.1 2 절). 이 모듈이 내놓는
분류는 «보고할 때 나눠 읽는 것» 이지 통과선이 아닙니다.

**「일반화를 입증했다」로 쓰지 않습니다.** 지금 평가 집합은 우리가 설계하며
여러 번 들여다본 개발용 집합입니다 (CRITERIA 7 절).
"""

from __future__ import annotations

import ast
import io
import os

# --- 생성 코드가 «바닥 없는 도랑» 을 만드는 지형 -----------------------------
#
# 출처는 «생성 코드의 그 줄» 이다. 주석이나 이름이 아니다.
TRENCH_TRAINING = {
    "omni_gap": ("sim/policy/omni_gap_terrain.py",
                 "중심 디딤판과 바깥 착지판 사이를 비운 원형 도랑"),
    "forward_gap": (".../go2/gap_training/gap_terrain.py",
                    "조주판 · 바닥 없는 틈 · 착지판"),
}

TRENCH_EVAL = {
    "gap": ("isaaclab/terrains/trimesh/mesh_terrains.py:588-593",
            "make_border 와 가운데 상자만 만들고 «바닥 상자를 안 만든다»"),
}

# 닮아 «보이지만» 바닥이 있는 것. 2026-09-23 에 한 번 거꾸로 분류했으므로
# 지워 두지 않고 까닭과 함께 남긴다.
FLOORED_EVAL = {
    "floating_ring": ("isaaclab/terrains/trimesh/mesh_terrains.py:636-640",
                      "`# Generate the ground` 로 전면 바닥 상자를 만든다 · "
                      "바닥이 끊기지 않으므로 도랑이 아니다"),
}

LEARNED = "학습한 지형"
TRENCH_REACH = "도랑이 닿는 지형"
UNSEEN = "학습에 없던 지형"
BUCKETS = (LEARNED, TRENCH_REACH, UNSEEN)

NOTE = {
    LEARNED: "배운 조건을 유지했나 (이름이 같아도 범위는 다를 수 있다)",
    TRENCH_REACH: "다른 기하의 도랑으로 옮겨 갔나",
    UNSEEN: "학습에 없던 조건에서 어떠한가",
}


def read_sub_terrains(path):
    """`params/env.yaml` -> 학습 지형 이름 목록.

    PyYAML 로 안 읽는다. 이 파일에는 `!!python/tuple` 과 Isaac Lab 클래스
    태그가 들어 있어서 안전한 로더로는 못 열고, 안전하지 않은 로더는 이
    저장소에서 쓰지 않는다. 필요한 것은 «한 단계 아래 키 이름» 뿐이라
    들여쓰기로 읽는다.
    """
    return sorted(read_sub_terrain_ranges(path), key=_order(path))


def _order(path):
    """파일에 적힌 차례를 지킨다."""
    names = _sub_terrain_block(path)[1]
    return lambda name: names.index(name)


def _sub_terrain_block(path):
    """(줄 목록, 지형 이름 차례대로, sub_terrains 줄 번호, 들여쓰기)."""
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
    return lines, names, head, indent


def read_sub_terrain_ranges(path):
    """`params/env.yaml` -> {지형: {`*_range` 이름: (아래, 위)}}.

    `!!python/tuple` 아래의 `- 숫자` 두 줄을 읽는다.
    """
    lines, names, head, indent = _sub_terrain_block(path)
    out = {name: {} for name in names}
    current = None
    # **`lines.index(line)` 를 쓰지 않는다.** 지형이 달라도 줄 내용이 같을
    # 수 있어서(`slope_range: !!python/tuple` 는 여러 지형에 그대로 나온다)
    # 첫 자리로 되돌아가 «앞 지형의 값» 을 읽게 된다. 자리 번호로 센다.
    for offset, line in enumerate(lines[head + 1:], start=head + 1):
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip())
        if depth <= indent:
            break
        stripped = line.strip()
        if depth == indent + 2 and stripped.endswith(":"):
            current = stripped[:-1]
            continue
        if current is None or not stripped.endswith("!!python/tuple"):
            continue
        key = stripped.split(":", 1)[0]
        if not key.endswith("_range"):
            continue
        values = []
        for follow in lines[offset + 1:]:
            item = follow.strip()
            if not item.startswith("- "):
                break
            try:
                values.append(float(item[2:]))
            except ValueError:
                break
        if len(values) == 2:
            out[current][key] = (values[0], values[1])
    return out


def read_eval_terrains(*paths):
    """평가 지형 설정 파일들 -> 지형 «이름» 전체.

    `read_eval_ranges` 와 다르다. 저쪽은 `*_range` 가 «있는» 지형만
    돌려준다. `repeated_boxes` · `repeated_cylinders` 처럼 범위 인자가
    없는 지형은 빠진다. 전체 목록으로 그것을 쓰면 그 지형을 배운 정책에서
    「기하 근거 없는 학습 지형」으로 잘못 보고 멈춘다.

    **`*TerrainCfg(...)` 만 센다.** 설정 파일에는 지형이 아닌 사전도 있어서
    (`sensor_cfg` · `miss_value` 같은 것) 아무 호출이나 세면 목록이 부풀고,
    그만큼 「기하 근거 없는 학습 지형」 관문이 헐거워진다.
    """
    out = set()
    for path in paths:
        if not os.path.exists(path):
            raise ValueError("평가 설정이 없다: %s" % path)
        with io.open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if not (isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and isinstance(value, ast.Call)):
                    continue
                called = value.func
                name = (called.attr if isinstance(called, ast.Attribute)
                        else getattr(called, "id", ""))
                if name.endswith("TerrainCfg"):
                    out.add(key.value)
    if not out:
        raise ValueError("평가 지형 이름을 하나도 못 읽었다: %s" % ", ".join(paths))
    return sorted(out)


def read_eval_ranges(*paths):
    """평가 지형 설정 파일들 -> {지형: {`*_range`: (아래, 위)}}.

    `isaaclab` 을 들이지 않고 `ast` 로 읽는다. 평가 설정은 리터럴이라
    그대로 읽힌다. **판정 경로는 안 건드린다. 읽기만 한다.**
    """
    out = {}
    for path in paths:
        if not os.path.exists(path):
            raise ValueError("평가 설정이 없다: %s" % path)
        with io.open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    continue
                if not isinstance(value, ast.Call):
                    continue
                found = {}
                for word in value.keywords:
                    if not word.arg or not word.arg.endswith("_range"):
                        continue
                    try:
                        pair = ast.literal_eval(word.value)
                    except (ValueError, SyntaxError):
                        continue
                    if isinstance(pair, (tuple, list)) and len(pair) == 2:
                        found[word.arg] = (float(pair[0]), float(pair[1]))
                if found:
                    out.setdefault(key.value, {}).update(found)
    if not out:
        raise ValueError("평가 지형 범위를 하나도 못 읽었다: %s" % ", ".join(paths))
    return out


def classify(eval_terrains, trained, known_eval=None, strict=None):
    """평가 지형마다 묶음 이름을 붙인다. 근거가 없으면 «멈춘다».

    `known_eval` 은 **평가 지형 «전체» 목록** 이다. `eval_terrains` 는
    「지금 결과가 «와 있는» 지형」이라 부분 자료에서는 더 짧다. 둘을 안
    가르면 «아직 결과가 안 온» 학습 지형을 «기하를 모르는» 지형으로 잘못
    보고 멈춘다.

    `strict` 는 기본으로 «`known_eval` 을 받았는가» 다. 전체 목록을 모르면
    「결과가 안 온 것」과 「기하를 모르는 것」을 «가를 수 없으므로» 멈추지
    않는다. 대신 `unknown_trained()` 로 물어보고 경고를 찍는 것은 부르는
    쪽의 몫이다. **못 가르는데 멈추면 부분 자료에서 헛경보가 난다.**
    """
    eval_terrains = list(eval_terrains)
    trained = list(trained)
    universe = set(eval_terrains if known_eval is None else known_eval)
    if not eval_terrains:
        raise ValueError("평가 지형이 하나도 없다 · 결과를 못 읽은 것이다")
    if not trained:
        raise ValueError("학습 지형이 하나도 없다 · `env.yaml` 을 못 읽은 것이다")

    # 이름도 안 맞고 도랑 근거도 없는 학습 지형. 둘 중 하나다.
    #   (가) 아직 «결과가 안 온» 평가 지형이다 (부분 자료)
    #   (나) 우리가 «기하를 안 읽은» 지형이다
    # (나) 이면 도랑일 수 있고, 그러면 `gap` 을 「학습에 없던」으로 잘못
    # 센다. 그래서 **도랑 평가 지형이 눈앞에 있을 때만** 멈춘다. 없으면
    # 잘못 셀 자리가 없으므로 멈추지 않는다.
    unknown = [name for name in trained
               if name not in universe and name not in TRENCH_TRAINING]
    at_risk = [name for name in eval_terrains if name in TRENCH_EVAL]
    if strict is None:
        strict = known_eval is not None
    if strict and unknown and at_risk:
        raise ValueError(
            "학습 지형 %s 를 평가 지형에 못 붙인다 · 이름이 같지도 않고 "
            "`TRENCH_TRAINING` 에 «생성 코드 기하» 근거도 없다. 그런데 평가에 "
            "도랑 지형 %s 가 있어서, 저것이 도랑이면 분류가 뒤집힌다. 그 지형의 "
            "생성 코드를 읽고 바닥 없는 도랑인지 확인해 넣어야 한다"
            % (" · ".join("`%s`" % name for name in sorted(unknown)),
               " · ".join("`%s`" % name for name in sorted(at_risk))))

    dug = [name for name in trained if name in TRENCH_TRAINING]

    out = {}
    for terrain in eval_terrains:
        if terrain in trained:
            out[terrain] = LEARNED
        elif terrain in TRENCH_EVAL and dug:
            out[terrain] = TRENCH_REACH
        else:
            out[terrain] = UNSEEN
    return out


def unknown_trained(trained, known_eval=None):
    """기하 근거가 없는 학습 지형. 평가 전체 목록을 모르면 «부분 자료» 일
    수도 있으므로, 이 목록은 «물음» 이지 «판정» 이 아니다."""
    universe = set(known_eval or ())
    return sorted(name for name in trained
                  if name not in universe and name not in TRENCH_TRAINING)


def trench_sources(eval_terrains, trained, known_eval=None):
    """`도랑이 닿는` 으로 분류된 칸마다 «생성 코드의 근거» 를 돌려준다."""
    marks = classify(eval_terrains, trained, known_eval=known_eval)
    dug = [name for name in trained if name in TRENCH_TRAINING]
    out = []
    for terrain in eval_terrains:
        if marks.get(terrain) != TRENCH_REACH:
            continue
        where, why = TRENCH_EVAL[terrain]
        out.append((terrain, dug, where, why))
    return out


def floored_notes(eval_terrains, trained, known_eval=None):
    """바닥이 있어서 «도랑이 아닌» 지형. 거꾸로 분류한 전례가 있어 적는다."""
    marks = classify(eval_terrains, trained, known_eval=known_eval)
    return [(terrain, marks[terrain]) + FLOORED_EVAL[terrain]
            for terrain in eval_terrains if terrain in FLOORED_EVAL]


# --- `*_range` 를 «생성기가 어떻게 쓰는가» --------------------------------
#
# **이름이 `_range` 라고 범위가 아니다.** 소비하는 코드를 읽고 적는다.
# 여기 없는 이름은 «모른다» 로 다루고 추측하지 않는다.
INTERPOLATED, SAMPLED, TWO_VALUES, UNKNOWN_USE = "보간", "표본", "두 값", "모름"

RANGE_USE = {
    # 보간한 뒤 `uniform_(-grid_height, grid_height)` 로 «진폭» 이 된다
    # (mesh_terrains.py:348). 한 값이 아니라 표본 구간의 한쪽 끝이다.
    "grid_height_range": (INTERPOLATED, "mesh_terrains.py:285 · 348"),
    "step_height_range": (INTERPOLATED, "mesh_terrains.py:76 · 176"),
    "rail_height_range": (INTERPOLATED, "mesh_terrains.py:401"),
    "slope_range": (INTERPOLATED, "hf_terrains.py:111-113"),
    # 난이도가 «안» 들어간다. 어느 난이도에서도 이 구간 전체에서 뽑는다.
    "noise_range": (SAMPLED, "hf_terrains.py:62-70"),
    # 범위가 아니라 «안쪽 두께 · 바깥쪽 두께» 두 값이다.
    "rail_thickness_range": (TWO_VALUES, "mesh_terrains.py:406"),
}


def range_notes(trained_ranges, eval_ranges, difficulty=0.5):
    """이름이 같은 지형에서 «평가 조건이 학습 범위 밖» 인 칸.

    돌려주는 것: [(지형, 항목, 쓰임, 출처, 학습범위, 평가범위, d0.5값, 밖인가)]

    **항목마다 생성기가 다르게 씁니다.** 전부 선형 보간이라고 놓으면 틀립니다.

    ```
    보간   난이도로 «설정값» 을 뽑는다      d0.5값 = 아래 + 난이도 x (위 - 아래)
           그 설정값이 학습 범위 밖인가
           생성기가 그 값을 «그대로» 쓰는지 «진폭» 으로 쓰는지는
           또 다르다 (`boxes` 는 진폭이다 · mesh_terrains.py:348)
    표본   난이도와 무관하게 구간에서 뽑는다  잰값이 하나가 아니다
           «구간» 이 학습 범위를 벗어나는가
    두 값  범위가 아니라 값 둘이다          두 값이 각각 학습 쪽과 같은가
    모름   소비 코드를 아직 안 읽었다        «밖인지 확인 못 함» 으로 남긴다
    ```

    `d0.5값` 이 `None` 이면 「한 값으로 말할 수 없다」는 뜻이고,
    `밖인가` 가 `None` 이면 **「밖인지 «확인 못 했다»」** 는 뜻입니다.
    소비 방식을 모르면 넓다는 것만으로 밖이라 세지 않습니다.
    **분류는 안 바꾸고 따로 적기만 합니다.**
    """
    out = []
    for terrain in sorted(set(trained_ranges) & set(eval_ranges)):
        for key in sorted(set(trained_ranges[terrain]) & set(eval_ranges[terrain])):
            low_t, high_t = trained_ranges[terrain][key]
            low_e, high_e = eval_ranges[terrain][key]
            use, source = RANGE_USE.get(key, (UNKNOWN_USE, "소비 코드 안 읽음"))

            if use == INTERPOLATED:
                value = low_e + difficulty * (high_e - low_e)
                outside = value < low_t or value > high_t
            elif use == TWO_VALUES:
                value = None
                outside = (low_e, high_e) != (low_t, high_t)
            elif use == SAMPLED:
                # 구간 전체에서 뽑으므로, 구간이 벗어나면 «벗어난 조건이
                # 실제로 나온다». 한 점으로 말하지 않는다.
                value = None
                outside = low_e < low_t or high_e > high_t
            else:
                # 소비 방식을 모르면 **밖인지도 모른다.** 구간이 넓다고
                # 「밖」으로 세면 안 된다. 보간하는 항목이면 난이도 0.5 의
                # 값이 학습 범위 «안» 일 수 있다. `None` 은 «확인 못 함» 이다.
                value = None
                outside = None
            out.append((terrain, key, use, source,
                        (low_t, high_t), (low_e, high_e), value, outside))
    return out


def split_cells(keys, trained, terrain_of=lambda key: key[2], known_eval=None):
    """칸 열쇠들을 세 묶음으로 가른다 -> {묶음: [열쇠]}."""
    keys = list(keys)
    marks = classify(sorted({terrain_of(key) for key in keys}), trained,
                     known_eval=known_eval)

    # `classify` 가 모르는 이름을 돌려주면 그 칸은 어느 묶음에도 안 들어가고
    # 조용히 사라진다. 사라진 칸은 «없는 칸» 이 되므로 여기서 막는다.
    strange = sorted({mark for mark in marks.values() if mark not in BUCKETS})
    if strange:
        raise ValueError(
            "모르는 묶음 이름 %s · 아는 것은 %s 뿐이다"
            % (" · ".join(strange), " · ".join(BUCKETS)))

    # 위 검사를 지나면 모든 칸이 `BUCKETS` 중 하나에 들어간다. 그래서
    # 「합이 맞나」를 또 두지 않는다. 절대 안 걸리는 검사는 관문이 아니라
    # 관문처럼 «보이는» 줄이고, 그것을 믿으면 안 된다.
    out = {bucket: [] for bucket in BUCKETS}
    for key in keys:
        out[marks[terrain_of(key)]].append(key)
    return out
