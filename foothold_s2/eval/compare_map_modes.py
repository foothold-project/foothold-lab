"""eval_map_modes 가 낸 map_modes.json 여러 개를 같은 표로 나란히 놓는다 (창 1 평가용, CPU).

    python -m foothold_s2.eval.compare_map_modes <parent.json> <ex30.json> <ex31.json> [--reference <ex25_g0.json>]

세 파일이 같은 조건(env 수 · 스텝 · 꺼진 DR · curriculum 끔 · 모드 · 명령 · 지형 해시)에서 나온 것이 아니면 표를 만들지 않고 멈춘다. 해석은 적지 않고 숫자만 놓는다.
"""

from __future__ import annotations

import json
import sys

from foothold_s2.eval import fixed_terrain

COLUMNS = (("body_vx_integral_median_m", "vx적분 m"), ("yaw_follow_median", "요추종"), ("stalled_fraction_2to4s", "멈춤"), ("alive_envs_at_end", "생존"))


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fixed_key(result: dict):
    """고정 칸 비교 열쇠: 배열 SHA · rows · cols · num_envs. 기록에 칸이 더 붙어도(levels · fixed_level 등) SHA 가 같으면 같은 칸이다. 고정 안 함은 None."""
    f = result.get("fixed_terrain")

    if f is None:
        return None

    return tuple(f.get(k) for k in ("assignment_sha256", "rows", "cols", "num_envs"))


def seed_key(result: dict):
    """평가 시드(키 없으면 옛 기본 42)와 칸 기하 해시 전체(듬성 판만 있음, 없으면 None). 둘이 다르면 같은 조건 비교가 아니다."""
    return result.get("eval_seed", 42), (result.get("terrain_geometry_sha256") or {}).get("total")


def check_same_conditions(results: dict) -> None:
    names = list(results)
    first = results[names[0]]
    hashes = set(first["terrain_hash"].values())

    if len(hashes) != 1:
        raise ValueError(f"{names[0]} 안에서 지형 해시가 하나가 아니다: {hashes}")
    for name in names[1:]:
        r = results[name]
        for key in ("task", "envs", "steps", "dr_off", "curriculum_off"):
            if r[key] != first[key]:
                raise ValueError(f"{name} 의 {key} 가 {names[0]} 와 다르다: {r[key]!r} != {first[key]!r}")
        if fixed_key(r) != fixed_key(first):
            raise ValueError(f"{name} 의 fixed_terrain 이 {names[0]} 와 다르다: {fixed_key(r)!r} != {fixed_key(first)!r}")
        if seed_key(r) != seed_key(first):
            raise ValueError(f"{name} 의 (eval_seed, 기하 해시) 가 {names[0]} 와 다르다: {seed_key(r)!r} != {seed_key(first)!r}. 시드 반복은 같은 모델끼리 따로 묶는다")
        if set(r["terrain_hash"].values()) != hashes:
            raise ValueError(f"{name} 의 지형 해시가 {names[0]} 와 다르다")
        if list(r["modes"]) != list(first["modes"]) or any(list(r["modes"][m]) != list(first["modes"][m]) for m in first["modes"]):
            raise ValueError(f"{name} 의 모드 · 명령 목록이 다르다")


REFERENCE_NOTE = "EX-25 는 마찰 고정(0.8/0.6) 으로 학습, 평가는 마찰 무작위 끔 같은 조건"


def check_reference(results: dict, ref: dict) -> None:
    """지도 없음 참조(EX-25 G0)는 task 만 다를 수 있다. 지형 해시 · env 수 · steps · 꺼진 DR · curriculum 끔 · 명령 목록이 같고, 지도 없는 체크포인트의 모드 'none' 하나일 때만 받는다."""
    first = results[next(iter(results))]

    if ref.get("map_input") != "none" or list(ref["modes"]) != ["none"]:
        raise ValueError("참조 열은 map_input=none 체크포인트의 모드 'none' 하나여야 한다: %r %r" % (ref.get("map_input"), list(ref["modes"])))
    for key in ("envs", "steps", "dr_off", "curriculum_off"):
        if ref[key] != first[key]:
            raise ValueError(f"참조 열의 {key} 가 다르다: {ref[key]!r} != {first[key]!r}")
    if fixed_key(ref) != fixed_key(first):
        raise ValueError("참조 열의 fixed_terrain 이 다르다: %r != %r" % (fixed_key(ref), fixed_key(first)))
    if set(ref["terrain_hash"].values()) != set(first["terrain_hash"].values()):
        raise ValueError("참조 열의 지형 해시가 다르다")
    if seed_key(ref) != seed_key(first):
        raise ValueError("참조 열의 (eval_seed, 기하 해시) 가 다르다: %r != %r" % (seed_key(ref), seed_key(first)))
    if list(ref["modes"]["none"]) != list(first["modes"][next(iter(first["modes"]))]):
        raise ValueError("참조 열의 명령 목록이 다르다")


def reference_table(results: dict, ref: dict) -> str:
    check_reference(results, ref)
    header = ["명령"] + [f"EX-25(지도 없음): {short}" for _, short in COLUMNS]
    lines = ["", "지도 없음 참조 열 (" + REFERENCE_NOTE + ")", "", "| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]

    for cmd, row in ref["modes"]["none"].items():
        lines.append("| " + " | ".join([cmd] + [f"{row[k]:.2f}" if isinstance(row[k], float) else str(row[k]) for k, _ in COLUMNS]) + " |")
    lines.append("")
    lines.append(f"참조 체크포인트: iter {ref['checkpoint_iter']} sha256 {ref['checkpoint_sha256'][:12]} · task {ref['task']}")

    return "\n".join(lines)


def table(results: dict, reference: dict | None = None) -> str:
    check_same_conditions(results)
    names = list(results)
    header = ["모드", "명령"] + [f"{n}: {short}" for n in names for _, short in COLUMNS]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    first = results[names[0]]

    for mode in first["modes"]:
        for cmd in first["modes"][mode]:
            cells = []
            for n in names:
                row = results[n]["modes"][mode][cmd]
                cells += [f"{row[k]:.2f}" if isinstance(row[k], float) else str(row[k]) for k, _ in COLUMNS]
            lines.append("| " + " | ".join([mode, cmd, *cells]) + " |")
    meta = ["", "조건: " + ", ".join(f"{n}: iter {results[n]['checkpoint_iter']} sha256 {results[n]['checkpoint_sha256'][:12]}" for n in names) + f" · 지형 해시 {next(iter(first['terrain_hash'].values()))[:12]} 동일 · envs {first['envs']} steps {first['steps']}"]
    if first.get("fixed_terrain"):
        meta.append("지형: " + fixed_terrain.describe(first["fixed_terrain"]))
    else:
        meta.append("지형: 고정 안 함(학습 reset 이 뽑은 칸, 모델끼리 해시가 같을 때만 비교)")

    out = "\n".join(lines + meta)

    return out + reference_table(results, reference) if reference is not None else out


def main(argv):
    paths = argv[1:]
    reference = None

    if "--reference" in paths:
        i = paths.index("--reference")
        reference = load(paths[i + 1])
        paths = paths[:i] + paths[i + 2:]

    if len(paths) < (1 if reference is not None else 2):
        raise SystemExit("usage: compare_map_modes <parent.json> [<ex30.json> <ex31.json> ...] [--reference <ex25_g0.json>]")
    labels = ["parent", "ex30", "ex31"] + [f"run{i}" for i in range(3, len(paths))]
    print(table({labels[i]: load(p) for i, p in enumerate(paths)}, reference))


if __name__ == "__main__":
    main(sys.argv)
